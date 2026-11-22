"""Ancre les encadrements dans les murs existants et suit les vrais décrochements du toit."""
from math import hypot

PAREMENTS = {"hotelpeach", "majescticalt"}


def projection(p, direction):
    return p[0] * direction[0] + p[1] * direction[1]


def parements(surface):
    noms = surface["materiaux"]
    xyz = surface["positions"]
    return [tuple(xyz[i] for i in (a, b, c)) for a, b, c, m in surface["triangles"] if noms[m] in PAREMENTS]


def profondeur(triangles, t, n, s, z, seuil):
    resultats = []
    for p, q, r in triangles:
        a, b, c = projection(p, t), projection(q, t), projection(r, t)
        det = (b - a) * (r[2] - p[2]) - (c - a) * (q[2] - p[2])
        if abs(det) < .00001:
            continue
        u = ((s - a) * (r[2] - p[2]) - (z - p[2]) * (c - a)) / det
        v = ((b - a) * (z - p[2]) - (q[2] - p[2]) * (s - a)) / det
        if min(u, v, 1 - u - v) >= -.0001:
            d = (1 - u - v) * projection(p, n) + u * projection(q, n) + v * projection(r, n)
            if abs(d - seuil) <= 1.25:
                resultats.append(d)
    return max(resultats, default=None)


def avancees(surface, panneaux):
    murs = parements(surface)
    ecarts = []
    for p in panneaux:
        zc = (p["z0"] + p["z1"]) / 2
        # Les cannelures centrales alternent creux et saillies suivant la largeur.
        # Un unique rayon au milieu placerait le linteau derrière certaines nervures.
        echantillons = [(p["s0"] + (p["s1"] - p["s0"]) * i / 16) for i in range(17)]
        points = [(s, z) for s in echantillons for z in (p["z0"] - .12, p["z1"] + .12)]
        points.extend((s, zc) for s in (p["s0"] - .12, p["s1"] + .12))
        appuis = [profondeur(murs, p["t"], p["n"], s, z, p["d"]) for s, z in points]
        atteint = max((v for v in appuis if v is not None), default=p["d"])
        ecarts.append(min(.95, max(0., atteint - p["d"]) + .13))
    return ecarts


def sortir_encadrement(face, p, ecart):
    # Le dos reste au niveau du vitrage : une embrasure relie le mur porteur
    # à la face visible des jambages, même devant un montant Art déco très saillant.
    nx, ny = p["n"]
    sommets = []
    for x, y, z, r, g, b in face:
        avant = projection((x, y), p["n"]) - p["d"]
        avance = ecart * min(1., max(0., (avant + .06) / .09))
        sommets.append((x + nx * avance, y + ny * avance, z, r, g, b))
    return tuple(sommets)


def coutures_toit(surface):
    murs = parements(surface)
    if not murs:
        return []
    xyz = surface["positions"]
    centre = tuple((min(p[k] for p in xyz) + max(p[k] for p in xyz)) / 2 for k in range(2))
    zmax = max(p[2] for p in xyz)
    bords = {}
    for coin in murs:
        for i in range(3):
            p, q, dessous = coin[i], coin[(i + 1) % 3], coin[(i + 2) % 3]
            dx, dy = q[0] - p[0], q[1] - p[1]
            longueur = hypot(dx, dy)
            if longueur < 2.1 or min(p[2], q[2]) < zmax - 6.2 or abs(p[2] - q[2]) > .7 * longueur:
                continue
            t = (dx / longueur, dy / longueur)
            n = (t[1], -t[0])
            if abs(projection(dessous, n) - projection(p, n)) > .14:
                continue
            f = (projection(dessous, t) - projection(p, t)) / longueur
            if dessous[2] >= p[2] + f * (q[2] - p[2]) - .20:
                continue
            centre_arete = ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
            if projection(centre_arete, n) < projection(centre, n):
                n = (-n[0], -n[1])
            if max(n) < .60 or projection(centre_arete, n) - projection(centre, n) < 7.:
                continue
            d = projection(p, n)
            haut = profondeur(murs, t, n, projection(centre_arete, t), (p[2] + q[2]) / 2 + .10, d)
            if haut is not None and haut > d - .30:
                continue
            cle = tuple(sorted(tuple(round(c, 2) for c in point) for point in (p, q)))
            bords[cle] = (p, q, n)
    return list(bords.values())


def corniches_ancrees(surface, nuit=False):
    # La pièce passe sous l’arête de son propre mur. Aucune hauteur de toit globale.
    teintes = ((174, 142, 105), (158, 127, 91), (121, 97, 76), (78, 64, 61))
    if nuit:
        teintes = ((121, 102, 82), (141, 114, 77), (87, 73, 68), (51, 47, 56))
    profil = ((-.09, .025), (.18, .025), (.34, -.08), (.34, -.16), (.21, -.27), (-.09, -.27))
    teinte = (0, 0, 1, 2, 3, 3)
    faces = []
    for p, q, n in coutures_toit(surface):
        dx, dy = q[0] - p[0], q[1] - p[1]
        if dx * n[1] - dy * n[0] > 0:
            p, q = q, p
        def bord(point):
            return [(point[0] + n[0]*d, point[1] + n[1]*d, point[2] + z) for d, z in profil]
        a, b = bord(p), bord(q)
        def face(v1, v2, v3, rgb):
            faces.append(((*v1, *rgb), (*v2, *rgb), (*v3, *rgb)))
        for j, couleur in enumerate(teinte):
            k = (j + 1) % len(profil)
            face(a[j], a[k], b[k], teintes[couleur])
            face(a[j], b[k], b[j], teintes[couleur])
        for j in range(1, len(profil) - 1):
            face(a[0], a[j + 1], a[j], teintes[2])
            face(b[0], b[j], b[j + 1], teintes[2])
    return faces
