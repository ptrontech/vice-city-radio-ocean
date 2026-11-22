"""Relief architectural du Majestic (od_majestic2c_dy.dff / _nt.dff) : conception 3D en Python standard.

    construire_relief(surface, nuit=False) -> liste de triangles
    triangle = ((x, y, z, r, g, b), (x, y, z, r, g, b), (x, y, z, r, g, b))

`surface` = {"positions": ((x, y, z), ...), "triangles": ((i, j, k, materiau), ...),
"materiaux": ("noms", "en", "minuscules")}. Le module ne lit aucun fichier, n'embarque aucune
donnée commerciale et ne recopie pas le maillage : il n'utilise que les rectangles des matériaux
`hotelwindow1` (fenêtres), `hotelwindow2` (vitrines) et `hot_doors` (porte) ainsi que les bornes
du modèle. Les coordonnées sont locales (flottantes), les couleurs sont des entiers 0..255 : le
nouveau matériau est un blanc uni multiplié par ce prééclairage de sommets. Rien n'est sérialisé
ici (RenderWare, installation et rendu restent à l'intégrateur) et la collision n'est pas touchée.

Méthode
  1. Chaque rectangle de fenêtre est reconstitué à partir de deux triangles : coins arrondis au
     centimètre, hypoténuse commune, angle droit, milieux confondus. Deux vitrines voisines ne
     sont jamais soudées (les demi-rectangles de deux panneaux n'ont pas la même hypoténuse).
  2. La normale extérieure est celle qui s'éloigne du centre du modèle ; chaque panneau reçoit un
     repère (t, n, z) direct, t tangent, n extérieur.
  3. Les volumes sont des prismes extrudés d'un profil en gradins : le profil est orienté par la
     normale attendue de chaque face, donc l'enroulement est toujours dirigé vers l'extérieur.
  4. Couleur par face (aplat) : lumière chaude venue d'en haut, faces inférieures brunes et plus
     sombres, stuc ivoire, terracotta, champagne, filets de laiton doux, socle discret.
  5. La nuit, les plateaux (grandes faces) sont assombris et les filets chauds sont conservés.

Éléments : encadrements à deux retraits (montants, linteau à deux gradins, appui débordant) pour
les 24 ouvertures ; montants libres, socle, imposte, auvent (profondeur 1,40 m, y compris devant la
porte) à nez de laiton, consoles, ailes d'angle Art déco et fronton de porte pour le rez-de-chaussée ;
corniche à quatre étagements. Aucun volume n'entre dans une ouverture de fenêtre, de vitrine ou de
porte.

Budget : les faces enterrées dans le mur ou collées à un volume voisin ne sont pas émises (elles ne
seraient jamais visibles et doubleraient les sommets). `ferme=True` rend chaque volume fermé pour
contrôle de la géométrie.
"""
import math

MATERIAU_FENETRES = "hotelwindow1"
MATERIAU_VITRINES = "hotelwindow2"
MATERIAU_PORTE = "hot_doors"
MATERIAUX_CIBLES = (MATERIAU_FENETRES, MATERIAU_VITRINES, MATERIAU_PORTE)

PRECISION_COINS = 2                 # décimales : coins arrondis au centimètre
ENFOUI = 0.06                       # les volumes pénètrent d'autant dans le mur
BANDES = (0.22, 0.20)               # largeurs des deux retraits de l'encadrement (total 0,42 m)
SAILLIES = (0.16, 0.09)             # saillies des deux retraits, décroissantes vers l'extérieur
HAUTEURS_LINTEAU = (0.26, 0.16)     # hauteurs des deux gradins du linteau
APPUI_SAILLIE, APPUI_HAUTEUR, APPUI_DEBORD = 0.28, 0.16, 0.10
SOCLE_SAILLIE = 0.10
IMPOSTE_SAILLIE = 0.10
AUVENT_PROFONDEUR = 1.40            # 1,25 à 1,60 m
AUVENT_EPAISSEUR = 0.22
AUVENT_HAUTEUR = 0.85               # sous-face de l'auvent au-dessus du haut des vitrines et de la porte
NEZ_SAILLIE, NEZ_HAUTEUR = 0.04, 0.09
CONSOLE_SAILLIE, CONSOLE_HAUTEUR, CONSOLE_LARGEUR = 0.80, 0.50, 0.36
ENTRAXE_CONSOLES, MARGE_CONSOLES = 2.4, 0.65
AILE_DEMI_LARGEUR, AILE_SAILLIES = 0.35, (0.04, 0.18, 0.30)
CORNICHE = ((0.16, 0.12, False), (0.14, 0.24, False), (0.18, 0.38, False), (0.06, 0.42, True))

IVOIRE = (238, 226, 198)
TERRACOTTA = (196, 112, 76)
CHAMPAGNE = (226, 200, 150)
LAITON = (204, 168, 96)
SOCLE = (178, 158, 138)
DESSOUS = (88, 58, 40)              # faces inférieures : brun plus sombre
LUMIERE = (0.38, 0.30, 0.87)
AMBIANT = 0.60
NUIT_PLATEAU, NUIT_FILET = 0.40, 0.92


# --------------------------------------------------------------------------- vecteurs

def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(a):
    return math.sqrt(_dot(a, a))


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


# --------------------------------------------------------------------------- reconstruction des panneaux

def _coin(p):
    return tuple(round(float(x), PRECISION_COINS) for x in p[:3])


def _rectangles(surface, indice):
    """Regroupe deux triangles en rectangle (hypoténuse commune, angles droits, milieux confondus)."""
    positions = surface["positions"]
    tris = []
    for i, j, k, m in surface["triangles"]:
        if m != indice:
            continue
        try:
            t = (_coin(positions[i]), _coin(positions[j]), _coin(positions[k]))
        except IndexError:
            raise ValueError("Indice de sommet hors de la liste des positions") from None
        if len(set(t)) == 3 and _norm(_cross(_sub(t[1], t[0]), _sub(t[2], t[0]))) > 1e-6:
            tris.append(t)
    par_arete = {}
    for n, t in enumerate(tris):
        _, a, b, c = max((sum(x * x for x in _sub(t[a], t[b])), a, b, c)
                         for a, b, c in ((0, 1, 2), (1, 2, 0), (2, 0, 1)))
        ca, cb = _sub(t[a], t[c]), _sub(t[b], t[c])
        if abs(_dot(ca, cb)) > 0.03 * _norm(ca) * _norm(cb):
            continue                                     # pas un demi-rectangle
        par_arete.setdefault(tuple(sorted((t[a], t[b]))), []).append((n, t[c]))
    utilises, rects = set(), []
    for cle in sorted(par_arete):
        a, b = cle
        milieu = tuple((x + y) / 2 for x, y in zip(a, b))
        candidats = par_arete[cle]
        for x in range(len(candidats)):
            n1, c1 = candidats[x]
            if n1 in utilises:
                continue
            for y in range(x + 1, len(candidats)):
                n2, c2 = candidats[y]
                if n2 in utilises or c1 == c2:
                    continue
                if _norm(_sub(milieu, tuple((p + q) / 2 for p, q in zip(c1, c2)))) > 0.03:
                    continue
                utilises.update((n1, n2))
                rects.append((a, c1, b, c2))
                break
    return rects, len(tris) - len(utilises)


def _panneau(coins, centre):
    """Panneau vertical : tangent t, normale extérieure n, abscisses s, offset d, hauteurs z."""
    zs = sorted(coins, key=lambda p: p[2])
    bas, haut = zs[:2], zs[2:]
    if (abs(bas[0][2] - bas[1][2]) > 0.05 or abs(haut[0][2] - haut[1][2]) > 0.05
            or haut[0][2] - bas[1][2] < 0.05):
        return None
    A, B = bas[0][:2], bas[1][:2]
    longueur = _dist(A, B)
    if longueur < 0.05 or any(min(_dist(p[:2], A), _dist(p[:2], B)) > 0.05 for p in haut):
        return None
    n = (-(B[1] - A[1]) / longueur, (B[0] - A[0]) / longueur)
    milieu = ((A[0] + B[0]) / 2 - centre[0], (A[1] + B[1]) / 2 - centre[1])
    if n[0] * milieu[0] + n[1] * milieu[1] < 0:
        n = (-n[0], -n[1])
    t = (n[1], -n[0])
    sa, sb = A[0] * t[0] + A[1] * t[1], B[0] * t[0] + B[1] * t[1]
    return {"n": n, "t": t, "s0": min(sa, sb), "s1": max(sa, sb),
            "d": ((A[0] + B[0]) * n[0] + (A[1] + B[1]) * n[1]) / 2,
            "z0": (bas[0][2] + bas[1][2]) / 2, "z1": (haut[0][2] + haut[1][2]) / 2}


def _preparer(surface):
    try:
        positions, triangles, noms = surface["positions"], surface["triangles"], surface["materiaux"]
    except (TypeError, KeyError):
        raise ValueError("surface : les clés positions, triangles et materiaux sont attendues") from None
    if not len(positions) or not len(triangles):
        raise ValueError("surface vide")
    xs, ys, zs = zip(*(p[:3] for p in positions))
    centre = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
    index = {str(nom).lower(): i for i, nom in enumerate(noms)}
    panneaux, orphelins = {}, {}
    for nom in MATERIAUX_CIBLES:
        panneaux[nom], orphelins[nom] = [], 0
        if nom in index:
            rects, orphelins[nom] = _rectangles(surface, index[nom])
            panneaux[nom] = [p for p in (_panneau(r, centre) for r in rects) if p]
            panneaux[nom].sort(key=lambda p: (round(math.atan2(p["n"][1], p["n"][0]), 2), p["z0"], p["s0"]))
    if not any(panneaux.values()):
        raise ValueError("Aucun panneau exploitable dans hotelwindow1, hotelwindow2 ni hot_doors")
    return {"panneaux": panneaux, "orphelins": orphelins, "bornes": (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)),
            "centre": centre}


def _porte(panneaux):
    """Ouverture de porte : rectangle englobant des panneaux de la direction dominante."""
    if not panneaux:
        return None
    poids = {}
    for p in panneaux:
        cle = (round(p["n"][0], 1), round(p["n"][1], 1))
        poids[cle] = poids.get(cle, 0.0) + (p["s1"] - p["s0"]) * (p["z1"] - p["z0"])
    cle = max(sorted(poids), key=lambda k: poids[k])
    groupe = [p for p in panneaux if (round(p["n"][0], 1), round(p["n"][1], 1)) == cle]
    p = dict(groupe[0])
    p.update(s0=min(q["s0"] for q in groupe), s1=max(q["s1"] for q in groupe),
             z0=min(q["z0"] for q in groupe), z1=max(q["z1"] for q in groupe),
             d=sum(q["d"] for q in groupe) / len(groupe))
    return p


def analyser(surface):
    """Comptes de reconstruction : panneaux par matériau et triangles qui n'ont pas trouvé de partenaire."""
    donnees = _preparer(surface)
    return {"panneaux": {k: len(v) for k, v in donnees["panneaux"].items()},
            "triangles_orphelins": dict(donnees["orphelins"])}


# --------------------------------------------------------------------------- géométrie : prismes à enroulement extérieur

def _orienter(tri, normale):
    a, b, c = tri
    produit = _cross(_sub(b, a), _sub(c, a))
    if _norm(produit) < 2e-6:
        return None
    return tri if _dot(produit, normale) >= 0 else (a, c, b)


def _quad(pts, normale):
    sortie = []
    for tri in ((pts[0], pts[1], pts[2]), (pts[0], pts[2], pts[3])):
        t = _orienter(tri, normale)
        if t:
            sortie.append(t)
    return sortie


def _poly(pts, normale):
    """Triangule un polygone plan simple (découpage d'oreilles) en respectant la normale attendue."""
    nettoye = []
    for k, p in enumerate(pts):
        a, c = pts[k - 1], pts[(k + 1) % len(pts)]
        if _norm(_cross(_sub(p, a), _sub(c, p))) > 1e-8:
            nettoye.append(p)
    pts = nettoye
    if len(pts) < 3:
        return []
    axe = max(range(3), key=lambda i: abs(normale[i]))
    i, j = ((1, 2), (2, 0), (0, 1))[axe]
    signe = 1.0 if normale[axe] > 0 else -1.0
    p2 = [(p[i], p[j]) if signe > 0 else (p[j], p[i]) for p in pts]

    def croix(a, b, c):
        return (p2[b][0] - p2[a][0]) * (p2[c][1] - p2[a][1]) - (p2[b][1] - p2[a][1]) * (p2[c][0] - p2[a][0])

    ordre = list(range(len(pts)))
    if sum(p2[k][0] * p2[(k + 1) % len(pts)][1] - p2[(k + 1) % len(pts)][0] * p2[k][1] for k in ordre) < 0:
        ordre.reverse()
    morceaux = []
    while len(ordre) > 3:
        for pos in range(len(ordre)):
            a, b, c = ordre[pos - 1], ordre[pos], ordre[(pos + 1) % len(ordre)]
            if croix(a, b, c) <= 1e-9:
                continue
            if any(croix(a, b, q) >= -1e-12 and croix(b, c, q) >= -1e-12 and croix(c, a, q) >= -1e-12
                   for q in ordre if q not in (a, b, c)):
                continue
            morceaux.append((a, b, c))
            del ordre[pos]
            break
        else:
            break
    for k in range(1, len(ordre) - 1):                    # dernier triangle, ou éventail de secours
        morceaux.append((ordre[0], ordre[k], ordre[k + 1]))
    sortie = []
    for a, b, c in morceaux:
        t = _orienter((pts[a], pts[b], pts[c]), normale)
        if t:
            sortie.append(t)
    return sortie


def _extruder(rep, profil, w0, w1, omettre=(), caps=(True, True)):
    """Prisme : `profil` = polygone (a, b) dans le plan (u, v) du repère direct (u, v, w), extrudé de w0 à w1.

    `omettre` = indices d'arêtes du profil dont la face latérale n'est pas émise ;
    `caps` = (face à w0, face à w1). Les faces sortantes sont orientées vers l'extérieur."""
    u, v, w = rep
    n = len(profil)
    aire = sum(profil[k][0] * profil[(k + 1) % n][1] - profil[(k + 1) % n][0] * profil[k][1] for k in range(n))
    if abs(aire) < 1e-9:
        return []
    signe = 1.0 if aire > 0 else -1.0

    def pt(a, b, c):
        return tuple(a * u[i] + b * v[i] + c * w[i] for i in range(3))

    tris = []
    for k in range(n):
        if k in omettre:
            continue
        (a0, b0), (a1, b1) = profil[k], profil[(k + 1) % n]
        du, dv = a1 - a0, b1 - b0
        longueur = math.hypot(du, dv)
        if longueur < 1e-9:
            continue
        normale = tuple(signe * (dv * u[i] - du * v[i]) / longueur for i in range(3))
        tris += _quad((pt(a0, b0, w0), pt(a1, b1, w0), pt(a1, b1, w1), pt(a0, b0, w1)), normale)
    if caps[0]:
        tris += _poly([pt(a, b, w0) for a, b in profil], tuple(-x for x in w))
    if caps[1]:
        tris += _poly([pt(a, b, w1) for a, b in profil], w)
    return tris


def boite(x0, x1, y0, y1, z0, z1):
    """Boîte alignée sur les axes, fermée, 12 triangles à enroulement extérieur."""
    profil = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    return _extruder(((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)), profil, z0, z1)


# --------------------------------------------------------------------------- couleurs

def _teinte(normale, base, nuit, filet):
    if normale[2] < -0.5:
        c = list(DESSOUS)
    else:
        lum = math.sqrt(sum(x * x for x in LUMIERE))
        k = AMBIANT + (1 - AMBIANT) * max(0.0, _dot(normale, LUMIERE) / lum)
        c = [base[0] * k, base[1] * k * 0.97, base[2] * k * 0.92]
    if nuit:
        f = NUIT_FILET if filet else NUIT_PLATEAU
        c = [c[0] * f, c[1] * f, c[2] * f * (1.0 if filet else 1.15)]
    return tuple(max(0, min(255, int(round(x)))) for x in c)


def _colorier(tris, base, filet, nuit):
    sortie = []
    for a, b, c in tris:
        produit = _cross(_sub(b, a), _sub(c, a))
        longueur = _norm(produit)
        if longueur < 2e-6:
            continue
        couleur = _teinte(tuple(x / longueur for x in produit), base, nuit, filet)
        sortie.append(tuple((float(p[0]), float(p[1]), float(p[2])) + couleur for p in (a, b, c)))
    return sortie


class _Contexte:
    def __init__(self, nuit, ferme):
        self.nuit, self.ferme, self.elements = nuit, ferme, []

    def omettre(self, indices):
        return () if self.ferme else tuple(indices)

    def caps(self, bas, haut):
        return (True, True) if self.ferme else (bas, haut)

    def ajouter(self, nom, tris, base, filet=False):
        colores = _colorier(tris, base, filet, self.nuit)
        if colores:
            self.elements.append({"nom": nom, "filet": filet, "triangles": colores})


def _rep_tnz(p):
    return ((p["t"][0], p["t"][1], 0.0), (p["n"][0], p["n"][1], 0.0), (0.0, 0.0, 1.0))


def _rep_nzt(p):
    t, n, z = _rep_tnz(p)
    return (n, z, t)


_REP_XYZ = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


# --------------------------------------------------------------------------- encadrements

def _extremites(p):
    return tuple((p["t"][0] * s + p["n"][0] * p["d"], p["t"][1] * s + p["n"][1] * p["d"]) for s in (p["s0"], p["s1"]))


def _voisins(p, autres):
    """Écarts (gauche, droite) au plus proche voisin : colinéaire (écart mesuré) ou d'angle (écart nul)."""
    gauche = droite = None
    pl, pr = _extremites(p)
    for q in autres:
        if q is p or min(q["z1"], p["z1"]) - max(q["z0"], p["z0"]) < 0.2:
            continue
        if _dot(q["n"], p["n"]) < 0.999:                       # pan d'angle : les extrémités se rejoignent
            if min(_dist(pl, e) for e in _extremites(q)) < 0.3:
                gauche = 0.0
            if min(_dist(pr, e) for e in _extremites(q)) < 0.3:
                droite = 0.0
            continue
        if abs(q["d"] - p["d"]) > 1.0:
            continue
        if q["s1"] <= p["s0"] + 0.02:
            ecart = p["s0"] - q["s1"]
            gauche = ecart if gauche is None else min(gauche, ecart)
        elif q["s0"] >= p["s1"] - 0.02:
            ecart = q["s0"] - p["s1"]
            droite = ecart if droite is None else min(droite, ecart)
    return gauche, droite


def _libre(ecart):
    return None if ecart is None else max(0.0, ecart / 2 - 0.03)


def _echelle(libre):
    """Facteur appliqué aux deux retraits d'un montant ; 0 si la place manque."""
    total = sum(BANDES)
    if libre is None:
        return 1.0
    f = min(1.0, libre / total)
    return f if f * total >= 0.10 else 0.0


def _montant(ctx, nom, p, cote, f, z0, z1, bas, haut, couleur):
    """Montant à deux retraits : profil (s, d) en gradins extrudé en z ; la face arrière est enterrée."""
    b1, b2 = BANDES[0] * f, BANDES[1] * f
    d = p["d"]
    s1, s2 = d + SAILLIES[0], d + SAILLIES[1]
    s = p["s0"] if cote < 0 else p["s1"]
    profil = [(s, d - ENFOUI), (s, s1), (s + cote * b1, s1), (s + cote * b1, s2),
              (s + cote * (b1 + b2), s2), (s + cote * (b1 + b2), d - ENFOUI)]
    ctx.ajouter(nom, _extruder(_rep_tnz(p), profil, z0, z1, ctx.omettre({5}), ctx.caps(bas, haut)), couleur)


def _linteau(ctx, nom, p, sa, sb, z_bas, couleur):
    """Linteau à deux gradins : profil (d, z) extrudé le long de t."""
    d = p["d"]
    s1, s2 = d + SAILLIES[0], d + SAILLIES[1]
    h1, h2 = HAUTEURS_LINTEAU
    profil = [(d - ENFOUI, z_bas), (s1, z_bas), (s1, z_bas + h1), (s2, z_bas + h1),
              (s2, z_bas + h1 + h2), (d - ENFOUI, z_bas + h1 + h2)]
    ctx.ajouter(nom, _extruder(_rep_nzt(p), profil, sa, sb, ctx.omettre({5})), couleur)


def _appui(ctx, nom, p, sa, sb, z_haut, couleur):
    d = p["d"]
    profil = [(sa, d - ENFOUI), (sa, d + APPUI_SAILLIE), (sb, d + APPUI_SAILLIE), (sb, d - ENFOUI)]
    ctx.ajouter(nom, _extruder(_rep_tnz(p), profil, z_haut - APPUI_HAUTEUR, z_haut, ctx.omettre({3})), couleur)


def _fenetre(ctx, i, p, toutes):
    ecart_g, ecart_d = _voisins(p, toutes)
    lg, ld = _libre(ecart_g), _libre(ecart_d)
    fg, fd = _echelle(lg), _echelle(ld)
    total = sum(BANDES)
    sa = p["s0"] - fg * total if fg else (p["s0"] + 0.02 if ecart_g is not None else p["s0"])
    sb = p["s1"] + fd * total if fd else (p["s1"] - 0.02 if ecart_d is not None else p["s1"])
    if fg:
        _montant(ctx, f"fenetre:{i}:montant_g", p, -1, fg, p["z0"], p["z1"], False, False, IVOIRE)
    if fd:
        _montant(ctx, f"fenetre:{i}:montant_d", p, +1, fd, p["z0"], p["z1"], False, False, IVOIRE)
    _linteau(ctx, f"fenetre:{i}:linteau", p, sa, sb, p["z1"], IVOIRE)
    def debord(libre, f):
        d = APPUI_DEBORD if libre is None else min(APPUI_DEBORD, max(0.0, libre - f * total - 0.02))
        return d if d >= 0.03 else 0.0
    _appui(ctx, f"fenetre:{i}:appui", p, sa - debord(lg, fg), sb + debord(ld, fd), p["z0"], TERRACOTTA)


# --------------------------------------------------------------------------- bandes en plan (auvent, imposte, corniche)

def _miter(n1, n2):
    d = 1.0 + n1[0] * n2[0] + n1[1] * n2[1]
    if d < 0.2:
        return n1
    return ((n1[0] + n2[0]) / d, (n1[1] + n2[1]) / d)


def _bande(ctx, nom, segs, ferme, dos, face, z0, z1, base, filet=False, caps=(True, True), omettre_dos=True):
    """Bande horizontale le long d'un chemin de segments joints en onglet ; dos/face = distances au chemin."""
    n = len(segs)
    tris = []
    for i, sg in enumerate(segs):
        prec = segs[i - 1] if (i > 0 or ferme) else None
        suiv = segs[(i + 1) % n] if (i < n - 1 or ferme) else None
        joint_p = prec is not None and _dist(prec["Q"], sg["P"]) < 0.05
        joint_q = suiv is not None and _dist(sg["Q"], suiv["P"]) < 0.05
        mp = _miter(sg["n"], prec["n"]) if joint_p else sg["n"]
        mq = _miter(sg["n"], suiv["n"]) if joint_q else sg["n"]
        P, Q = sg["P"], sg["Q"]
        if _dist(P, Q) < 0.05:
            continue
        profil = [(P[0] + dos * mp[0], P[1] + dos * mp[1]), (Q[0] + dos * mq[0], Q[1] + dos * mq[1]),
                  (Q[0] + face * mq[0], Q[1] + face * mq[1]), (P[0] + face * mp[0], P[1] + face * mp[1])]
        omis = ({0} if omettre_dos else set()) | ({1} if joint_q else set()) | ({3} if joint_p else set())
        tris += _extruder(_REP_XYZ, profil, z0, z1, ctx.omettre(omis), ctx.caps(*caps))
    ctx.ajouter(nom, tris, base, filet)


def _orienter_seg(sg, debut):
    if debut == "P":
        return dict(sg)
    copie = dict(sg)
    copie["P"], copie["Q"] = sg["Q"], sg["P"]
    return copie


def _chaines(segs, tol=0.8):
    ordre = sorted(range(len(segs)), key=lambda i: (round(segs[i]["P"][0], 3), round(segs[i]["P"][1], 3),
                                                    round(segs[i]["Q"][0], 3), round(segs[i]["Q"][1], 3)))
    libres, chaines = list(ordre), []
    while libres:
        choix = None
        for i in libres:
            for fin in ("P", "Q"):
                if not any(_dist(segs[i][fin], segs[j][e]) < tol for j in libres if j != i for e in "PQ"):
                    choix = (i, fin)
                    break
            if choix:
                break
        i, fin = choix if choix else (libres[0], "P")
        chaine = [_orienter_seg(segs[i], fin)]
        libres.remove(i)
        while True:
            meilleur = None
            for j in libres:
                for e in "PQ":
                    dd = _dist(chaine[-1]["Q"], segs[j][e])
                    if dd < tol and (meilleur is None or dd < meilleur[0]):
                        meilleur = (dd, j, e)
            if not meilleur:
                break
            chaine.append(_orienter_seg(segs[meilleur[1]], meilleur[2]))
            libres.remove(meilleur[1])
        for a, b in zip(chaine, chaine[1:]):             # raccord : intersection des deux droites, sinon milieu
            na, nb = a["n"], b["n"]
            det = na[0] * nb[1] - na[1] * nb[0]
            da = na[0] * a["Q"][0] + na[1] * a["Q"][1]
            db = nb[0] * b["P"][0] + nb[1] * b["P"][1]
            joint = ((a["Q"][0] + b["P"][0]) / 2, (a["Q"][1] + b["P"][1]) / 2)
            if abs(det) > 0.05:
                x, y = (da * nb[1] - na[1] * db) / det, (na[0] * db - nb[0] * da) / det
                if _dist((x, y), a["Q"]) <= 1.0 and _dist((x, y), b["P"]) <= 1.0:
                    joint = (x, y)
            a["Q"] = b["P"] = joint
        chaines.append(chaine)
    return chaines


def _segment_de(p, virtuel=False):
    t, n, d = p["t"], p["n"], p["d"]
    return {"P": (t[0] * p["s0"] + n[0] * d, t[1] * p["s0"] + n[1] * d),
            "Q": (t[0] * p["s1"] + n[0] * d, t[1] * p["s1"] + n[1] * d), "n": n, "virtuel": virtuel}


def _console(ctx, nom, sg, f, z_haut):
    L = _dist(sg["P"], sg["Q"])
    n = sg["n"]
    t = (n[1], -n[0])
    c = (sg["P"][0] + (sg["Q"][0] - sg["P"][0]) * f, sg["P"][1] + (sg["Q"][1] - sg["P"][1]) * f)
    s, d = c[0] * t[0] + c[1] * t[1], sg["P"][0] * n[0] + sg["P"][1] * n[1]
    p = {"t": t, "n": n}
    profil = [(d + IMPOSTE_SAILLIE, z_haut - CONSOLE_HAUTEUR), (d + CONSOLE_SAILLIE, z_haut - 0.12),
              (d + CONSOLE_SAILLIE, z_haut), (d + IMPOSTE_SAILLIE, z_haut)]
    ctx.ajouter(nom, _extruder(_rep_nzt(p), profil, s - CONSOLE_LARGEUR / 2, s + CONSOLE_LARGEUR / 2,
                               ctx.omettre({2, 3})), TERRACOTTA)


def _gradins(ctx, nom, n, t, s, d, demi, saillies, retrait, z0, z1, base, bas=True, haut=False):
    """Pilastre Art déco à pans coupés : profil symétrique (s, d) en gradin puis en biseau, extrudé en z."""
    s0, s1, s2 = saillies
    profil = [(s - demi, d + s0), (s - demi, d + s1), (s - demi + retrait, d + s2),
              (s + demi - retrait, d + s2), (s + demi, d + s1), (s + demi, d + s0)]
    p = {"t": t, "n": n}
    ctx.ajouter(nom, _extruder(_rep_tnz(p), profil, z0, z1, ctx.omettre({5}), ctx.caps(bas, haut)), base)


def _rez_de_chaussee(ctx, vitrines, porte, bornes):
    zg = bornes[4]
    toutes = list(vitrines)
    porte_virtuelle = None
    if porte:
        memes = sorted(q["d"] for q in vitrines if _dot(q["n"], porte["n"]) > 0.99)
        if memes:
            porte_virtuelle = dict(porte)
            porte_virtuelle["d"] = memes[len(memes) // 2]
    zt = max([p["z1"] for p in vitrines] + ([porte["z1"]] if porte else []))
    zc0 = zt + AUVENT_HAUTEUR
    zc1 = zc0 + AUVENT_EPAISSEUR
    for i, p in enumerate(vitrines):
        avec_porte = toutes + ([porte_virtuelle] if porte_virtuelle else [])
        eg, ed = _voisins(p, avec_porte)
        for cote, ecart, nom in ((-1, eg, "g"), (+1, ed, "d")):
            f = _echelle(_libre(ecart))
            if f:
                _montant(ctx, f"vitrine:{i}:montant_{nom}", p, cote, f, zg, zt, False, True, CHAMPAGNE)
        pg, pd = _voisins(p, toutes)
        pg_colle = pg is not None and pg < 0.06      # voisin colinéaire accolé : l'extrémité est interne
        pd_colle = pd is not None and pd < 0.06
        d = p["d"]
        profil = [(p["s0"], d - ENFOUI), (p["s0"], d + SOCLE_SAILLIE), (p["s1"], d + SOCLE_SAILLIE), (p["s1"], d - ENFOUI)]
        jambage_g, jambage_d = _echelle(_libre(eg)) > 0, _echelle(_libre(ed)) > 0   # un montant libre touche l'extrémité
        if p["z0"] - zg > 0.15:
            ctx.ajouter(f"socle:{i}", _extruder(_rep_tnz(p), profil, zg, p["z0"],
                                                ctx.omettre({3} | ({0} if pg_colle or jambage_g else set())
                                                            | ({2} if pd_colle or jambage_d else set()))),
                        SOCLE)
    segs = [_segment_de(p) for p in vitrines] + ([_segment_de(porte_virtuelle, True)] if porte_virtuelle else [])
    for k, chaine in enumerate(_chaines(segs)):
        _bande(ctx, f"imposte:{k}", chaine, False, -ENFOUI, IMPOSTE_SAILLIE, zt, zc0, TERRACOTTA, caps=(True, False))
        _bande(ctx, f"auvent:{k}", chaine, False, -ENFOUI, AUVENT_PROFONDEUR, zc0, zc1, CHAMPAGNE)
        _bande(ctx, f"nez:{k}", chaine, False, AUVENT_PROFONDEUR, AUVENT_PROFONDEUR + NEZ_SAILLIE,
               zc1 - NEZ_HAUTEUR, zc1, LAITON, filet=True)
        for j, sg in enumerate(chaine):                       # consoles, bien au-dessus du passage
            L = _dist(sg["P"], sg["Q"])
            utile = L - 2 * MARGE_CONSOLES
            if sg.get("virtuel") or utile < 0.2:
                continue
            nb = max(1, int(round(utile / ENTRAXE_CONSOLES)))
            for m in range(nb):
                _console(ctx, f"console:{k}:{j}:{m}", sg, (MARGE_CONSOLES + (m + 0.5) * utile / nb) / L, zc0)
        tourne = [math.degrees(math.acos(max(-1.0, min(1.0, a["n"][0] * b["n"][0] + a["n"][1] * b["n"][1]))))
                  for a, b in zip(chaine, chaine[1:])]
        ailes = [(chaine[0]["P"], chaine[0]["n"]), (chaine[-1]["Q"], chaine[-1]["n"])]
        debut = None
        for j, ang in enumerate(tourne + [0.0]):              # ailes de part et d'autre d'un angle arrondi
            if ang >= 8.0 and debut is None:
                debut = j
            if ang < 8.0 and debut is not None:
                if sum(tourne[debut:j]) >= 45.0:
                    for jj in (debut, j - 1):
                        a, b = chaine[jj], chaine[jj + 1]
                        m = (a["n"][0] + b["n"][0], a["n"][1] + b["n"][1])
                        ailes.append((a["Q"], (m[0] / math.hypot(*m), m[1] / math.hypot(*m))))
                debut = None
        for j, (pt, n) in enumerate(ailes):
            t = (n[1], -n[0])
            _gradins(ctx, f"aile:{k}:{j}", n, t, pt[0] * t[0] + pt[1] * t[1], pt[0] * n[0] + pt[1] * n[1],
                     AILE_DEMI_LARGEUR, AILE_SAILLIES, 0.15, zt, zc0, IVOIRE)
    if porte_virtuelle:                                       # fronton devant la porte, au-dessus de l'ouverture
        t, n = porte_virtuelle["t"], porte_virtuelle["n"]
        milieu = (porte_virtuelle["s0"] + porte_virtuelle["s1"]) / 2
        _gradins(ctx, "fronton", n, t, milieu, porte_virtuelle["d"], (porte_virtuelle["s1"] - porte_virtuelle["s0"]) / 2 + 0.30,
                 (0.04, 0.16, 0.26), 0.25, zt + 0.18, zc0 - 0.12, CHAMPAGNE, bas=True, haut=True)


def _corniche(ctx, fenetres, bornes):
    xmin, xmax, ymin, ymax, _, zmax = bornes
    plans = {}
    for p in fenetres:
        cle = (round(p["n"][0]), round(p["n"][1]))
        if abs(p["n"][0] - cle[0]) < 0.05 and abs(p["n"][1] - cle[1]) < 0.05:
            plans.setdefault(cle, []).append(p["d"])
    mediane = lambda cle, defaut: sorted(plans[cle])[len(plans[cle]) // 2] if cle in plans else defaut
    x1, x0 = mediane((1, 0), xmax - 1.5), -mediane((-1, 0), -(xmin + 1.5))
    y1, y0 = mediane((0, 1), ymax - 1.5), -mediane((0, -1), -(ymin + 1.5))
    segs = [{"P": (x1, y1), "Q": (x1, y0), "n": (1.0, 0.0)}, {"P": (x1, y0), "Q": (x0, y0), "n": (0.0, -1.0)},
            {"P": (x0, y0), "Q": (x0, y1), "n": (-1.0, 0.0)}, {"P": (x0, y1), "Q": (x1, y1), "n": (0.0, 1.0)}]
    haut = zmax - 0.05
    z = haut - sum(h for h, _, _ in CORNICHE)
    for k, (hauteur, saillie, filet) in enumerate(CORNICHE):
        derniere = k == len(CORNICHE) - 1
        _bande(ctx, f"corniche:{k}", segs, True, -0.10, saillie, z, z + hauteur,
               LAITON if filet else CHAMPAGNE, filet=filet, caps=(True, derniere))
        z += hauteur


# --------------------------------------------------------------------------- interface

def construire_elements(surface, nuit=False, ferme=False):
    """Éléments nommés : [{"nom", "filet", "triangles"}, ...] ; `construire_relief` les met à plat."""
    donnees = _preparer(surface)
    fenetres = donnees["panneaux"][MATERIAU_FENETRES]
    vitrines = donnees["panneaux"][MATERIAU_VITRINES]
    porte = _porte(donnees["panneaux"][MATERIAU_PORTE])
    ctx = _Contexte(bool(nuit), bool(ferme))
    for i, p in enumerate(fenetres):
        _fenetre(ctx, i, p, fenetres)
    if vitrines:
        _rez_de_chaussee(ctx, vitrines, porte, donnees["bornes"])
    if fenetres or vitrines:
        _corniche(ctx, fenetres, donnees["bornes"])
    return ctx.elements


def construire_relief(surface, nuit=False, ferme=False):
    """Liste de triangles ((x, y, z, r, g, b) × 3) du relief ; `nuit` assombrit les plateaux, garde les filets."""
    return [tri for element in construire_elements(surface, nuit, ferme) for tri in element["triangles"]]
