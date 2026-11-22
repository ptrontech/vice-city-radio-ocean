"""Rive Art déco arrondie du grand auvent en surplomb du Majestic.

Les deux arêtes sur rue sont déduites des triangles de la dalle d'origine.
Le nez déborde de 1,49 m et raccorde les deux rues par un virage à huit stations.
"""
def prolonger_marquise(surface, nuit=False):
    """Prolonge les deux rives sur rue de la dalle originale jusqu’au nez arrondi."""
    from math import atan2, cos, hypot, pi, sin

    noms = surface["materiaux"]
    if "hotelwindow2" not in noms or "bow_abattoir_conc2" not in noms:
        return []
    vitrine, dalle = noms.index("hotelwindow2"), noms.index("bow_abattoir_conc2")
    positions = surface["positions"]
    haut_vitrines = max((positions[index][2] for a, b, c, mat in surface["triangles"]
                         if mat == vitrine for index in (a, b, c)), default=None)
    if haut_vitrines is None:
        return []
    points = {}
    for a, b, c, mat in surface["triangles"]:
        if mat != dalle:
            continue
        p, q, r = (positions[i] for i in (a, b, c))
        z = (p[2] + q[2] + r[2]) / 3
        aire = abs((q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])) / 2
        if haut_vitrines + .4 < z < haut_vitrines + 1.8 and max(p[2], q[2], r[2]) - min(p[2], q[2], r[2]) < .12 and aire > 90:
            for sommet in (p, q, r):
                points[(round(sommet[0], 2), round(sommet[1], 2))] = sommet
    if len(points) != 4:
        return []
    coins = list(points.values())
    centre = tuple(sum(p[i] for p in coins) / 4 for i in range(3))
    coins.sort(key=lambda p: atan2(p[1] - centre[1], p[0] - centre[0]))
    # Les vitrines avant ouvrent sur +X et +Y. Le coin commun est pris dans le
    # modèle de chaque horaire, y compris les quelques centimètres de décalage.
    k = max(range(4), key=lambda i: (coins[i][0] - centre[0]) + (coins[i][1] - centre[1]))
    a, b, c = coins[(k - 1) % 4], coins[k], coins[(k + 1) % 4]

    def unite(p, q):
        dx, dy = q[0] - p[0], q[1] - p[1]
        long = hypot(dx, dy)
        return dx / long, dy / long

    e1, e2 = unite(a, b), unite(b, c)
    n1, n2 = (e1[1], -e1[0]), (e2[1], -e2[0])
    # Petit rayon de raccord. Les trois filets demeurent continus dans le virage.
    rayon = 1.8
    pivot = (b[0] - rayon * e1[0] + rayon * e2[0], b[1] - rayon * e1[1] + rayon * e2[1])
    debut, fin = atan2(n1[1], n1[0]), atan2(n2[1], n2[0])
    ouverture = (fin - debut) % (2 * pi)
    stations = [(a[0] + .25 * e1[0], a[1] + .25 * e1[1], *n1)]
    for j in range(8):
        angle = debut + ouverture * j / 7
        nx, ny = cos(angle), sin(angle)
        stations.append((pivot[0] + rayon * nx, pivot[1] + rayon * ny, nx, ny))
    stations.append((c[0] - .25 * e2[0], c[1] - .25 * e2[1], *n2))

    if nuit:
        ivoire, facade, chanfrein, ombre = (112, 92, 80), (135, 99, 74), (162, 124, 74), (47, 39, 49)
        reflets, cuivre = (242, 179, 102), (104, 78, 70)
    else:
        ivoire, facade, chanfrein, ombre = (222, 201, 165), (198, 168, 126), (168, 132, 92), (100, 85, 82)
        reflets, cuivre = (226, 187, 117), (158, 115, 78)
    triangles = []

    def extruder(profil, teintes):
        # Chaque profil convexe est défini par des couples (débord, hauteur).
        # La traversée des stations et la coupe fermée donnent un volume orienté.
        anneaux = [
            [(x + nx * d, y + ny * d, centre[2] + h) for d, h in profil]
            for x, y, nx, ny in stations
        ]
        def face(v1, v2, v3, teinte):
            triangles.append(((*v1, *teinte), (*v2, *teinte), (*v3, *teinte)))
        for gauche, droite in zip(anneaux, anneaux[1:]):
            for j, teinte in enumerate(teintes):
                j2 = (j + 1) % len(profil)
                face(gauche[j], gauche[j2], droite[j2], teinte)
                face(gauche[j], droite[j2], droite[j], teinte)
        for j in range(1, len(profil) - 1):
            face(anneaux[0][0], anneaux[0][j+1], anneaux[0][j], chanfrein)
            face(anneaux[-1][0], anneaux[-1][j], anneaux[-1][j+1], chanfrein)

    extruder([(-.24, .62), (.77, .62), (1.38, .32), (1.38, -.09), (.73, -.33), (-.24, -.33)],
             [ivoire, ivoire, facade, chanfrein, ombre, ombre])
    extruder([(1.35, .26), (1.44, .24), (1.49, .17), (1.41, .12), (1.35, .14)],
             [reflets, reflets, cuivre, ombre, ombre])
    extruder([(1.35, .03), (1.43, .015), (1.48, -.045), (1.40, -.085), (1.34, -.065)],
             [ivoire, reflets, cuivre, ombre, ombre])
    return triangles
