"""Tests du relief du Majestic. Lancer : python tests/relief_majestic.py

Données entièrement synthétiques (rectangles inventés aux proportions annoncées). Un test facultatif
relit les deux sources JSON personnelles en lecture seule si elles existent (variable
RELIEF_MAJESTIC_SOURCES). Ces surfaces restent dans le dossier personnel.
"""
import importlib.util
import json
import math
import os
from pathlib import Path
import unittest

_CHEMIN = Path(__file__).resolve().parents[1] / "outils" / "relief_majestic.py"
_SPEC = importlib.util.spec_from_file_location("relief_majestic_outil", _CHEMIN)
relief = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(relief)

SOURCES = Path(os.environ["RELIEF_MAJESTIC_SOURCES"]) if os.environ.get("RELIEF_MAJESTIC_SOURCES") else None
Z_VITRINES = (-13.62, -10.34)
ETAGES = ((-6.28, -3.2), (1.0, 4.24))


# --------------------------------------------------------------------------- surface synthétique

def _rect(pos, tris, a, b, z0, z1, mat, k):
    """Rectangle vertical : diagonale, partage des sommets et sens varient avec k."""
    base = len(pos)
    coins = [(a[0], a[1], z0), (b[0], b[1], z0), (b[0], b[1], z1), (a[0], a[1], z1)]
    if k % 2 == 0:
        pos.extend(coins)
        i = (base, base + 1, base + 2, base + 3)
        paire = [(i[0], i[1], i[2]), (i[0], i[2], i[3])] if k % 4 == 0 else [(i[0], i[1], i[3]), (i[1], i[2], i[3])]
    else:                                                       # six sommets dupliqués
        ordre = [(0, 1, 2), (0, 2, 3)] if k % 3 else [(0, 1, 3), (1, 2, 3)]
        paire = []
        for tri in ordre:
            debut = len(pos)
            pos.extend(coins[m] for m in tri)
            paire.append((debut, debut + 1, debut + 2))
    if k % 3 == 0:
        paire = [(c, b_, a_) for a_, b_, c in paire]
    tris.extend((a_, b_, c, mat) for a_, b_, c in paire)


def surface_synthetique(decalage=(0.0, 0.0, 0.0), fenetres=True, vitrines=True, porte=True):
    pos, tris = [], []
    k = 0
    if fenetres:
        for etage, (z0, z1) in enumerate(ETAGES):
            plan = 10.0 + 0.8 * etage
            for c in (-6.0, 0.0, 6.0):
                for a, b in (((plan, c - 1), (plan, c + 1)), ((-plan, c - 1), (-plan, c + 1)),
                             ((c - 1, 12.6), (c + 1, 12.6)), ((c - 1, -12.6), (c + 1, -12.6))):
                    _rect(pos, tris, a, b, z0, z1, 1, k)
                    k += 1
    if vitrines:
        arc = [(round(5.8 + 1.5 * math.cos(math.radians(a)), 2), round(8.3 + 1.5 * math.sin(math.radians(a)), 2))
               for a in (0, 30, 60, 90)]
        bandes = [((7.3, -8.0), (7.3, -2.8)), ((7.3, 1.5), (7.3, 5.0)), ((7.3, 5.0), (7.3, 8.3))]
        bandes += list(zip(arc, arc[1:]))
        bandes += [((5.8, 9.8), (2.0, 9.8)), ((2.0, 9.8), (-2.0, 9.8))]
        for a, b in bandes:
            _rect(pos, tris, a, b, Z_VITRINES[0], Z_VITRINES[1], 2, k)
            k += 1
    if porte:
        _rect(pos, tris, (6.55, -2.8), (6.55, 1.5), Z_VITRINES[0], Z_VITRINES[1], 3, k)
    base = len(pos)                                              # bornes du modèle : X±12, Y±14, Z -14.45..14.47
    pos.extend([(-12.0, -14.0, -14.45), (12.0, 14.0, 14.47), (12.0, -14.0, 0.0)])
    tris.append((base, base + 1, base + 2, 0))
    dx, dy, dz = decalage
    return {"positions": tuple((x + dx, y + dy, z + dz) for x, y, z in pos), "triangles": tuple(tris),
            "materiaux": ("mur", "hotelwindow1", "hotelwindow2", "hot_doors")}


# --------------------------------------------------------------------------- outils de mesure

def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def norme(a):
    return math.sqrt(dot(a, a))


def pts(tri):
    return [v[:3] for v in tri]


def normale(tri):
    p = pts(tri)
    c = cross(sub(p[1], p[0]), sub(p[2], p[0]))
    n = norme(c)
    return tuple(x / n for x in c)


def centre(tri):
    p = pts(tri)
    return tuple(sum(q[i] for q in p) / 3 for i in range(3))


def volume_signe(tris):
    return sum(dot(p[0], cross(p[1], p[2])) for p in map(pts, tris)) / 6


def aretes_equilibrees(tris):
    compte = {}
    for t in tris:
        p = [tuple(round(x, 5) for x in q) for q in pts(t)]
        for a, b in ((p[0], p[1]), (p[1], p[2]), (p[2], p[0])):
            compte[(a, b)] = compte.get((a, b), 0) + 1
    return all(compte.get((b, a), 0) == n for (a, b), n in compte.items())


def sommets_uniques(tris):
    return len({tuple(round(x, 4) for x in v[:3]) + tuple(v[3:]) for t in tris for v in t})


def luminance(tri):
    return sum(0.299 * v[3] + 0.587 * v[4] + 0.114 * v[5] for v in tri) / 3


def dans_triangle_xy(p, tri):
    a, b, c = (q[:2] for q in pts(tri))

    def s(u, v, w):
        return (u[0] - w[0]) * (v[1] - w[1]) - (v[0] - w[0]) * (u[1] - w[1])
    d1, d2, d3 = s(p, a, b), s(p, b, c), s(p, c, a)
    return not ((d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0))


def triangle_boite(tri, bas, haut):
    """Test d'intersection triangle / boîte alignée (axes séparateurs) ; le simple contact ne compte pas."""
    c = [(bas[i] + haut[i]) / 2 for i in range(3)]
    e = [(haut[i] - bas[i]) / 2 for i in range(3)]
    v = [sub(p, c) for p in tri]
    f = [sub(v[1], v[0]), sub(v[2], v[1]), sub(v[0], v[2])]
    axes_boite = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
    eps = 1e-7
    for u in axes_boite:
        for arete in f:
            a = cross(u, arete)
            if norme(a) < 1e-12:
                continue
            p = [dot(q, a) for q in v]
            r = sum(e[k] * abs(a[k]) for k in range(3))
            if min(p) >= r - eps or max(p) <= -r + eps:
                return False
    for k in range(3):
        if min(q[k] for q in v) >= e[k] - eps or max(q[k] for q in v) <= -e[k] + eps:
            return False
    n = cross(f[0], f[1])
    if abs(dot(n, v[0])) >= sum(e[k] * abs(n[k]) for k in range(3)) - eps * norme(n):
        return False
    return True


def aire_recouvrement(t1, t2, axe):
    """Aire de l'intersection de deux triangles coplanaires (projection en supprimant `axe`)."""
    i, j = [k for k in range(3) if k != axe]

    def poly(t):
        p = [(q[i], q[j]) for q in pts(t)]
        aire = sum(p[k][0] * p[(k + 1) % 3][1] - p[(k + 1) % 3][0] * p[k][1] for k in range(3))
        return p if aire > 0 else p[::-1]

    sujet, clip = poly(t1), poly(t2)
    for k in range(3):
        a, b = clip[k], clip[(k + 1) % 3]
        entree, sujet = sujet, []
        for m in range(len(entree)):
            p, q = entree[m], entree[(m + 1) % len(entree)]
            dp = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
            dq = (b[0] - a[0]) * (q[1] - a[1]) - (b[1] - a[1]) * (q[0] - a[0])
            if dp >= 0:
                sujet.append(p)
            if (dp >= 0) != (dq >= 0):
                u = dp / (dp - dq)
                sujet.append((p[0] + u * (q[0] - p[0]), p[1] + u * (q[1] - p[1])))
        if not sujet:
            return 0.0
    return abs(sum(sujet[k][0] * sujet[(k + 1) % len(sujet)][1] - sujet[(k + 1) % len(sujet)][0] * sujet[k][1]
                   for k in range(len(sujet)))) / 2


def recouvrements_coplanaires(tris):
    groupes = {}
    for t in tris:
        n = normale(t)
        axe = max(range(3), key=lambda i: abs(n[i]))
        if n[axe] < 0:
            n = tuple(-x for x in n)
        cle = tuple(round(x, 2) for x in n) + (round(dot(n, pts(t)[0]), 2),)
        groupes.setdefault(cle, []).append((t, axe))
    trouves = []
    for membres in groupes.values():
        for a in range(len(membres)):
            ta, axe = membres[a]
            pa = pts(ta)
            for b in range(a + 1, len(membres)):
                tb, _ = membres[b]
                pb = pts(tb)
                if any(max(q[k] for q in pa) <= min(q[k] for q in pb) + 1e-9
                       or max(q[k] for q in pb) <= min(q[k] for q in pa) + 1e-9 for k in range(3)):
                    continue
                if aire_recouvrement(ta, tb, axe) > 1e-6:
                    trouves.append((ta, tb))
    return trouves


def ouvertures(surface):
    donnees = relief._preparer(surface)
    liste = [(nom, p) for nom in (relief.MATERIAU_FENETRES, relief.MATERIAU_VITRINES)
             for p in donnees["panneaux"][nom]]
    porte = relief._porte(donnees["panneaux"][relief.MATERIAU_PORTE])
    if porte:
        liste.append((relief.MATERIAU_PORTE, porte))
    return liste


def traversees(tris, surface):
    """Triangles du relief qui entrent dans le volume libre devant une ouverture."""
    erreurs = []
    for nom, p in ouvertures(surface):
        bas = (p["s0"] + 0.01, p["d"] - 0.01, p["z0"] + 0.01)
        haut = (p["s1"] - 0.01, p["d"] + 1.5, p["z1"] - 0.01)
        for t in tris:
            local = [(q[0] * p["t"][0] + q[1] * p["t"][1], q[0] * p["n"][0] + q[1] * p["n"][1], q[2]) for q in pts(t)]
            if triangle_boite(local, bas, haut):
                erreurs.append((nom, t))
    return erreurs


# --------------------------------------------------------------------------- tests

class ReliefMajestic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.surface = surface_synthetique()
        cls.elements = relief.construire_elements(cls.surface)
        cls.tris = relief.construire_relief(cls.surface)

    def par_nom(self, prefixe):
        return [e for e in self.elements if e["nom"].startswith(prefixe)]

    def test_reconstruction_des_panneaux(self):
        comptes = relief.analyser(self.surface)
        self.assertEqual(comptes["panneaux"], {"hotelwindow1": 24, "hotelwindow2": 8, "hot_doors": 1})
        self.assertEqual(sum(comptes["triangles_orphelins"].values()), 0)   # 48 + 16 + 2 triangles tous appariés
        donnees = relief._preparer(self.surface)["panneaux"]
        nord = [p for p in donnees["hotelwindow1"] if p["n"] == (0.0, 1.0)]
        self.assertEqual(len(nord), 6)
        for p in donnees["hotelwindow1"]:                                    # normales vers l'extérieur
            milieu = (p["d"] * p["n"][0] + p["s0"] * p["t"][0], p["d"] * p["n"][1] + p["s0"] * p["t"][1])
            self.assertGreater(milieu[0] * p["n"][0] + milieu[1] * p["n"][1], 5.0)
        etages = {(p["z0"], p["z1"]) for p in donnees["hotelwindow1"]}
        self.assertEqual(etages, set(ETAGES))

    def test_vitrines_voisines_non_soudees(self):
        # [1.5, 5.0] et [5.0, 8.3] sont accolées avec la même diagonale possible : deux panneaux, pas un.
        vitrines = relief._preparer(self.surface)["panneaux"]["hotelwindow2"]
        droite = sorted((p["s0"], p["s1"]) for p in vitrines if p["n"] == (1.0, 0.0))
        self.assertEqual(len(droite), 3)
        largeurs = sorted(round(b - a, 2) for a, b in droite)
        self.assertEqual(largeurs, [3.3, 3.5, 5.2])

    def test_format_des_triangles(self):
        self.assertTrue(self.tris)
        for tri in self.tris:
            self.assertEqual(len(tri), 3)
            for v in tri:
                self.assertEqual(len(v), 6)
                self.assertTrue(all(isinstance(x, float) for x in v[:3]))
                self.assertTrue(all(isinstance(x, int) and 0 <= x <= 255 for x in v[3:]))

    def test_budget_et_nombre(self):
        triangles, sommets = len(self.tris), sommets_uniques(self.tris)
        detail = {}
        for e in self.elements:
            cat = e["nom"].split(":")[0]
            n, v = detail.get(cat, (0, 0))
            detail[cat] = (n + len(e["triangles"]), v + sommets_uniques(e["triangles"]))
        print(f"\n  relief synthétique : {triangles} triangles, {sommets} sommets distincts ; "
              f"(triangles, sommets) par catégorie : {detail}", end="")
        self.assertGreater(triangles, 900)                    # relief substantiel
        self.assertLess(triangles, 2800)
        self.assertLess(sommets, 3000)

    def test_triangles_non_degeneres(self):
        for tri in self.tris:
            p = pts(tri)
            c = cross(sub(p[1], p[0]), sub(p[2], p[0]))
            aire = norme(c) / 2
            plus_long = max(norme(sub(p[a], p[b])) ** 2 for a, b in ((0, 1), (1, 2), (2, 0)))
            self.assertGreater(aire, 1e-6)
            self.assertGreater(aire / plus_long, 1e-4, tri)                  # ni colinéaire ni sliver

    def test_aucune_surface_coplanaire_superposee(self):
        doubles = recouvrements_coplanaires(self.tris)
        self.assertEqual(doubles, [], doubles[:1])

    def test_aucune_forme_dans_les_ouvertures(self):
        dedans = traversees(self.tris, self.surface)
        self.assertEqual(dedans, [], dedans[:1])
        self.assertEqual(len(ouvertures(self.surface)), 24 + 8 + 1)

    def test_boite_fermee_et_enroulement_exterieur(self):
        tris = relief.boite(0, 2, 0, 3, 0, 4)
        self.assertEqual(len(tris), 12)
        self.assertAlmostEqual(volume_signe(tris), 24.0, places=9)
        self.assertTrue(aretes_equilibrees(tris))
        for t in tris:
            self.assertGreater(dot(normale(t), sub(centre(t), (1, 1.5, 2))), 0)

    def test_prismes_en_gradins_fermes_et_orientes(self):
        for e in relief.construire_elements(self.surface, ferme=True):
            self.assertTrue(aretes_equilibrees(e["triangles"]), e["nom"])
            self.assertGreater(volume_signe(e["triangles"]), 0, e["nom"])
        # Un profil en L concave : volume exact (aire du profil × longueur).
        profil = [(0, 0), (2, 0), (2, 1), (1, 1), (1, 3), (0, 3)]
        tris = relief._extruder(((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)), profil, 0, 5)
        self.assertAlmostEqual(volume_signe(tris), 4.0 * 5, places=9)
        self.assertTrue(aretes_equilibrees(tris))

    def test_encadrements_a_deux_retraits(self):
        donnees = relief._preparer(self.surface)["panneaux"]["hotelwindow1"]
        p = donnees[0]
        montant = next(e for e in self.elements if e["nom"] == "fenetre:0:montant_g")
        fronts = {round(dot(centre(t), p["n"]) - p["d"], 3) for t in montant["triangles"] if dot(normale(t), p["n"]) > 0.99}
        self.assertEqual(fronts, {0.16, 0.09})                                # deux couches, épaisseurs décroissantes
        largeur = [dot(v[:3], p["t"] + (0.0,)) for t in montant["triangles"] for v in t]
        self.assertAlmostEqual(max(largeur) - min(largeur), 0.42, places=6)
        self.assertTrue(0.25 <= sum(relief.BANDES) <= 0.50)
        linteau = next(e for e in self.elements if e["nom"] == "fenetre:0:linteau")
        hauts = {round(centre(t)[2] - p["z1"], 3) for t in linteau["triangles"] if abs(normale(t)[2]) > 0.99}
        self.assertEqual(len(hauts), 3)                                       # sous-face, gradin, dessus
        appui = next(e for e in self.elements if e["nom"] == "fenetre:0:appui")
        ecart = max(dot(v[:3], p["n"] + (0.0,)) for t in appui["triangles"] for v in t) - p["d"]
        self.assertAlmostEqual(ecart, relief.APPUI_SAILLIE, places=6)
        xs = [dot(v[:3], p["t"] + (0.0,)) for t in appui["triangles"] for v in t]
        self.assertAlmostEqual(min(xs), p["s0"] - sum(relief.BANDES) - relief.APPUI_DEBORD, places=6)  # appui débordant

    def test_auvent_proportions_exactes_et_devant_la_porte(self):
        self.assertTrue(1.25 <= relief.AUVENT_PROFONDEUR <= 1.60)
        dessus = [t for e in self.par_nom("auvent") for t in e["triangles"] if normale(t)[2] > 0.99]
        dessous = [t for e in self.par_nom("auvent") for t in e["triangles"] if normale(t)[2] < -0.99]
        haut_porte = Z_VITRINES[1]
        zc0 = haut_porte + relief.AUVENT_HAUTEUR
        self.assertTrue(all(abs(centre(t)[2] - zc0) < 1e-9 for t in dessous))
        self.assertTrue(all(abs(centre(t)[2] - (zc0 + relief.AUVENT_EPAISSEUR)) < 1e-9 for t in dessus))
        face_x = [t for t in dessus if centre(t)[1] < -3.2 and centre(t)[0] > 7]          # tronçon +X à gauche de la porte
        self.assertAlmostEqual(max(v[0] for t in face_x for v in t) - 7.3, relief.AUVENT_PROFONDEUR, places=9)
        face_y = [t for t in dessus if centre(t)[0] < 4.0 and centre(t)[1] > 9.0]         # tronçon +Y
        self.assertAlmostEqual(max(v[1] for t in face_y for v in t) - 9.8, relief.AUVENT_PROFONDEUR, places=9)
        for y in (-2.7, 0.0, 1.4):                                                        # y compris devant la porte
            self.assertTrue(any(dans_triangle_xy((8.0, y), t) for t in dessus), y)
            self.assertTrue(any(dans_triangle_xy((7.4, y), t) for t in dessous), y)
        porte = relief._porte(relief._preparer(self.surface)["panneaux"]["hot_doors"])
        self.assertAlmostEqual(porte["d"], 6.55)
        self.assertAlmostEqual(porte["s1"] - porte["s0"], 4.3)

    def test_consoles_au_dessus_du_passage_et_nez_de_laiton(self):
        consoles = self.par_nom("console")
        self.assertGreaterEqual(len(consoles), 4)
        bas = min(v[2] for e in consoles for t in e["triangles"] for v in t)
        haut = max(v[2] for e in consoles for t in e["triangles"] for v in t)
        self.assertGreaterEqual(bas - Z_VITRINES[1], 0.30)                                # bien au-dessus du passage
        self.assertAlmostEqual(haut, Z_VITRINES[1] + relief.AUVENT_HAUTEUR, places=9)     # sous l'auvent
        nez = self.par_nom("nez")
        self.assertTrue(nez and all(e["filet"] for e in nez))
        self.assertTrue(any(v[3] > v[5] + 40 for e in nez for t in e["triangles"] for v in t))   # laiton chaud

    def test_identite_visuelle(self):
        categories = {e["nom"].split(":")[0] for e in self.elements}
        self.assertEqual(categories, {"fenetre", "vitrine", "socle", "imposte", "auvent", "nez", "console",
                                      "aile", "fronton", "corniche"})
        sombres = [t for t in self.tris if normale(t)[2] < -0.5]
        verticaux = [t for t in self.tris if abs(normale(t)[2]) < 0.2]
        self.assertTrue(sombres and verticaux)
        self.assertTrue(all(v[3:] == relief.DESSOUS for t in sombres for v in t))          # dessous bruns
        self.assertLess(max(luminance(t) for t in sombres), min(luminance(t) for t in verticaux))
        couleurs = {tuple(t[0][3:]) for t in self.tris}
        self.assertGreater(len(couleurs), 12)
        self.assertTrue(all(c[0] >= c[2] for c in couleurs))                                # palette chaude
        self.assertLessEqual(max(sum(c) for c in couleurs), 3 * 255)

    def test_corniche_etagee(self):
        niveaux = sorted(self.par_nom("corniche"), key=lambda e: e["nom"])
        self.assertEqual(len(niveaux), 4)
        saillies = [max(v[0] for t in e["triangles"] for v in t) for e in niveaux]
        self.assertEqual(saillies, sorted(saillies))                                        # chaque étage déborde plus
        self.assertEqual(len(set(round(s, 3) for s in saillies)), 4)

    def test_nuit_reduit_les_plateaux_et_garde_les_filets(self):
        nuit = relief.construire_elements(self.surface, nuit=True)
        self.assertEqual([e["nom"] for e in nuit], [e["nom"] for e in self.elements])
        for jour_e, nuit_e in zip(self.elements, nuit):
            self.assertEqual(len(jour_e["triangles"]), len(nuit_e["triangles"]))
            for a, b in zip(jour_e["triangles"], nuit_e["triangles"]):
                self.assertEqual([v[:3] for v in a], [v[:3] for v in b])                   # même forme
        plateaux = [(a, b) for j, n in zip(self.elements, nuit) if not j["filet"] for a, b in zip(j["triangles"], n["triangles"])]
        filets = [(a, b) for j, n in zip(self.elements, nuit) if j["filet"] for a, b in zip(j["triangles"], n["triangles"])]
        self.assertLess(sum(luminance(b) for _, b in plateaux), 0.5 * sum(luminance(a) for a, _ in plateaux))
        self.assertGreater(sum(luminance(b) for _, b in filets), 0.85 * sum(luminance(a) for a, _ in filets))
        self.assertTrue(all(v[3] >= v[5] for _, b in filets for v in b))                    # filets restés chauds

    def test_variantes_jour_nuit_decalees_reconstruites(self):
        decalage = (0.03, -0.02, 0.01)
        autre = relief.construire_relief(surface_synthetique(decalage))
        self.assertEqual(len(autre), len(self.tris))
        for a, b in zip(self.tris, autre):
            for u, v in zip(a, b):
                self.assertEqual(u[3:], v[3:])
                for k in range(3):
                    self.assertAlmostEqual(v[k] - u[k], decalage[k], places=6)

    def test_surface_incomplete_ou_invalide(self):
        sans_porte = relief.construire_relief(surface_synthetique(porte=False))
        self.assertTrue(sans_porte)
        sans_vitrines = relief.construire_relief(surface_synthetique(vitrines=False, porte=False))
        self.assertTrue(sans_vitrines and len(sans_vitrines) < len(self.tris))
        with self.assertRaisesRegex(ValueError, "positions, triangles et materiaux"):
            relief.construire_relief({"positions": ()})
        with self.assertRaisesRegex(ValueError, "Aucun panneau"):
            relief.construire_relief(surface_synthetique(fenetres=False, vitrines=False, porte=False))
        mauvaise = dict(self.surface, triangles=((0, 1, 10 ** 6, 1),))
        with self.assertRaisesRegex(ValueError, "hors de la liste"):
            relief.construire_relief(mauvaise)

    def test_deterministe(self):
        self.assertEqual(relief.construire_relief(surface_synthetique()), self.tris)


@unittest.skipUnless(SOURCES and (SOURCES / "surface-majestic-dy.json").exists() and (SOURCES / "surface-majestic-nt.json").exists(),
                     "sources JSON personnelles absentes")
class SurfacesReelles(unittest.TestCase):
    """Contrôle local sur les vraies surfaces (lecture seule, rien n'est copié ni écrit)."""

    def test_jour_et_nuit(self):
        resultats = {}
        for suffixe in ("dy", "nt"):
            brut = json.loads((SOURCES / f"surface-majestic-{suffixe}.json").read_text(encoding="utf-8"))
            surface = {"positions": tuple(tuple(p) for p in brut["positions"]),
                       "triangles": tuple(tuple(t) for t in brut["triangles"]),
                       "materiaux": tuple(str(m).lower() for m in brut["materiaux"])}
            comptes = relief.analyser(surface)
            tris = relief.construire_relief(surface)
            nuit = relief.construire_relief(surface, nuit=True)
            doubles = recouvrements_coplanaires(tris)
            dedans = traversees(tris, surface)
            print(f"\n  {suffixe} : {comptes} -> {len(tris)} triangles, {sommets_uniques(tris)} sommets,"
                  f" {len(doubles)} recouvrements coplanaires, {len(dedans)} traversées", end="")
            self.assertEqual(comptes["panneaux"]["hotelwindow1"], 24)
            self.assertEqual(comptes["panneaux"]["hotelwindow2"], 8)
            self.assertEqual(sum(comptes["triangles_orphelins"].values()), 0)
            self.assertLess(len(tris), 2800)
            self.assertLess(sommets_uniques(tris), 3000)
            self.assertEqual(len(tris), len(nuit))
            categories = {e["nom"].split(":")[0] for e in relief.construire_elements(surface)}
            self.assertEqual(categories, {"fenetre", "vitrine", "socle", "imposte", "auvent", "nez", "console",
                                          "aile", "fronton", "corniche"})
            self.assertEqual(doubles, [])
            self.assertEqual(dedans, [])
            resultats[suffixe] = tris
        self.assertEqual(len(resultats["dy"]), len(resultats["nt"]))


if __name__ == "__main__":
    unittest.main()
