# -*- coding: utf-8 -*-
"""Tests synthétiques de outils/decor_facades_ville.py (aucun asset, aucun jeu).

Lancement, depuis la racine du worktree :
    python -m unittest tests/decor_facades_ville.py -v
"""
import ast
import importlib.util
import itertools
import math
import random
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
SOURCE = RACINE / "outils" / "decor_facades_ville.py"

_spec = importlib.util.spec_from_file_location("decor_facades_ville", SOURCE)
decor = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(decor)

FAMILLES = decor.FAMILLES
EPS = 1e-9


def baie(mode, largeur, hauteur, profondeur, nuit=False, vitrine=False, teinte=None):
    b = {"largeur": largeur, "hauteur": hauteur, "profondeur": profondeur,
         "mode": mode, "nuit": nuit, "vitrine": vitrine}
    if teinte is not None:
        b["teinte"] = teinte
    return b


def normale(tri):
    a, b, c = tri
    u = [b[i] - a[i] for i in range(3)]
    v = [c[i] - a[i] for i in range(3)]
    return (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])


def cas_pieces():
    for L, H, P in itertools.product((0.8, 1.2, 2.5, 6.0, 12.0), (0.8, 1.5, 3.0, 5.0), (0.9, 1.4, 2.0)):
        for i, f in enumerate(FAMILLES):
            for g in range(3):
                yield baie("piece", L, H, P, nuit=bool(g % 2), vitrine=bool((g + i) % 2)), f, g


def cas_retraits():
    for L, H, P in itertools.product((0.8, 1.2, 2.5, 6.0, 12.0), (0.8, 1.5, 3.0, 5.0), (0.1, 0.2, 0.28)):
        for i, f in enumerate(FAMILLES):
            for g in range(3):
                yield baie("retrait", L, H, P, nuit=bool(g % 2), vitrine=bool((g + i) % 2)), f, g


def cas_corniches():
    for L, H in itertools.product((0.8, 3.0, 12.0, 65.0), (0.8, 3.0, 12.0, 40.0)):
        for f in FAMILLES:
            for g in range(3):
                yield baie("corniche", L, H, 0.12, nuit=bool(g % 2)), f, g


def tous_les_cas():
    yield from cas_pieces()
    yield from cas_retraits()
    yield from cas_corniches()


class FormeEtBornes(unittest.TestCase):
    def test_format_des_triangles(self):
        for b, f, g in tous_les_cas():
            for tri in decor.construire_decor(b, f, g):
                self.assertEqual(len(tri), 3)
                for s in tri:
                    self.assertEqual(len(s), 6)
                    self.assertTrue(all(math.isfinite(v) for v in s[:3]))
                    for k in s[3:]:
                        self.assertIs(type(k), int)
                        self.assertTrue(0 <= k <= 255)

    def test_budgets(self):
        for b, f, g in tous_les_cas():
            n = len(decor.construire_decor(b, f, g))
            self.assertLess(n, {"piece": 100, "retrait": 46, "corniche": 28}[b["mode"]], (b, f, g))

    def test_bornes_geometriques(self):
        for b, f, g in tous_les_cas():
            L, H, P = b["largeur"], b["hauteur"], b["profondeur"]
            for tri in decor.construire_decor(b, f, g):
                for x, y, z, *_ in tri:
                    self.assertTrue(-EPS <= x <= L + EPS, (b, f, x))
                    self.assertTrue(-0.13 - EPS <= y <= P + EPS, (b, f, y))
                    self.assertTrue(-EPS <= z <= H + EPS, (b, f, z))

    def test_pas_de_triangle_degenere(self):
        for b, f, g in tous_les_cas():
            for tri in decor.construire_decor(b, f, g):
                nx, ny, nz = normale(tri)
                self.assertGreater(nx * nx + ny * ny + nz * nz, 1e-14)

    def test_cas_extremes_non_vides(self):
        pour_piece = decor.construire_decor(baie("piece", 0.8, 0.8, 0.9), "commerce", 1)
        self.assertGreaterEqual(len(pour_piece), 10)  # coque au minimum
        self.assertTrue(decor.construire_decor(baie("retrait", 0.8, 0.8, 0.1), "bureau", 1))
        self.assertTrue(decor.construire_decor(baie("corniche", 65, 40, 0.12), "public", 1))

    def test_entrees_invalides(self):
        with self.assertRaises(ValueError):
            decor.construire_decor(baie("piece", 2, 2, 1), "inconnue", 1)
        with self.assertRaises(ValueError):
            decor.construire_decor(baie("autre", 2, 2, 1), "deco", 1)


class Winding(unittest.TestCase):
    def test_aucune_face_tournee_vers_l_arriere(self):
        for b, f, g in tous_les_cas():
            for tri in decor.construire_decor(b, f, g):
                self.assertLessEqual(normale(tri)[1], 1e-6, (b["mode"], f))

    def test_coque_du_compartiment_orientee_vers_l_observateur(self):
        attendu = [(2, 1), (2, -1), (0, 1), (0, -1), (1, -1)]  # sol, plafond, gauche, droite, fond
        for L, H, P in ((0.8, 0.8, 0.9), (3.0, 3.0, 1.5), (12.0, 5.0, 2.0)):
            for f in FAMILLES:
                tris = decor.construire_decor(baie("piece", L, H, P), f, 7)
                for i, (axe, signe) in enumerate(attendu):
                    for tri in tris[2 * i:2 * i + 2]:
                        n = normale(tri)
                        self.assertGreater(n[axe] * signe, 1e-9, (f, i))
                        autres = [abs(n[k]) for k in range(3) if k != axe]
                        self.assertLess(max(autres), 1e-9)

    def test_corniche_dessus_vers_le_haut_et_dessous_vers_le_bas(self):
        H = 5.0
        tris = decor.construire_decor(baie("corniche", 8, H, 0.12), "deco", 3)
        dessus = [t for t in tris if all(abs(s[2] - H) < EPS for s in t)]
        self.assertTrue(dessus)
        for t in dessus:
            self.assertGreater(normale(t)[2], 0)
        horizontaux_bas = [t for t in tris if abs(t[0][2] - t[1][2]) < EPS and abs(t[1][2] - t[2][2]) < EPS
                           and t[0][2] < H - EPS]
        for t in horizontaux_bas:
            self.assertLess(normale(t)[2], 0)

    def test_retours_du_retrait_tournes_vers_l_ouverture(self):
        L = 2.0
        tris = decor.construire_decor(baie("retrait", L, 1.6, 0.2), "habitation", 2)
        # retours = plans d'embrasure qui montent au-dessus de l'appui (les flancs de l'appui sont exclus)
        H, P = 1.6, 0.2

        def est_retour(t, x):
            # plan d'embrasure : dans le plan x, profond de 0 à P, montant jusqu'au linteau
            ys = [s[1] for s in t]
            return (all(abs(s[0] - x) < EPS for s in t) and any(abs(s[2] - H) < EPS for s in t)
                    and min(ys) > -EPS and max(ys) < P + EPS)

        gauche = [t for t in tris if est_retour(t, 0.0)]
        droite = [t for t in tris if est_retour(t, L)]
        self.assertTrue(gauche and droite)
        self.assertTrue(all(normale(t)[0] > 0 for t in gauche))
        self.assertTrue(all(normale(t)[0] < 0 for t in droite))


class Piece(unittest.TestCase):
    def test_mobilier_et_relief(self):
        for f in FAMILLES:
            for g in range(6):
                b = baie("piece", 3.0, 3.0, 1.6)
                tris = decor.construire_decor(b, f, g)
                self.assertGreater(len(tris), 30, (f, g))
                ys = {round(s[1], 2) for t in tris for s in t}
                self.assertGreaterEqual(len(ys), 6, (f, g))
                # volume autonome : sommets nettement détachés des parois et du fond
                libres = [s for t in tris[10:] for s in t if 0.15 < s[1] < 1.6 - 0.05 and 0.1 < s[0] < 2.9]
                self.assertTrue(libres, (f, g))

    def test_coque_complete_et_fond_a_la_profondeur(self):
        tris = decor.construire_decor(baie("piece", 4.0, 3.0, 1.5), "bureau", 1)
        fond = tris[8:10]
        for t in fond:
            for s in t:
                self.assertAlmostEqual(s[1], 1.5)

    def test_signatures_par_famille(self):
        # Sans rideau de fer ni caprice : chaque famille produit une écriture différente.
        sorties = {f: decor.construire_decor(baie("piece", 3.0, 3.0, 1.6), f, 5) for f in FAMILLES}
        self.assertEqual(len({tuple(v) for v in sorties.values()}), len(FAMILLES))

    def test_commerce_a_des_objets_sur_etageres(self):
        tris = decor.construire_decor(baie("piece", 3.0, 3.0, 1.6), "commerce", 4)
        fond = [t for t in tris[10:] if all(s[1] > 1.6 - 0.45 for s in t)]
        self.assertGreater(len(fond), 15)

    def test_piece_trop_petite_peut_renvoyer_peu(self):
        tris = decor.construire_decor(baie("piece", 0.8, 0.8, 0.9), "habitation", 2)
        self.assertLess(len(tris), 100)
        self.assertGreaterEqual(len(tris), 10)

    def test_nuit_change_les_couleurs_pas_la_forme(self):
        jour = decor.construire_decor(baie("piece", 3, 3, 1.5, nuit=False), "deco", 2)
        nuit = decor.construire_decor(baie("piece", 3, 3, 1.5, nuit=True), "deco", 2)
        self.assertEqual(len(jour), len(nuit))
        self.assertNotEqual(jour, nuit)
        pos = lambda ts: [tuple(s[:3]) for t in ts for s in t]
        self.assertEqual(pos(jour), pos(nuit))


class Retrait(unittest.TestCase):
    def test_vitre_non_repeinte(self):
        for b, f, g in cas_retraits():
            P = b["profondeur"]
            for tri in decor.construire_decor(b, f, g):
                self.assertFalse(all(abs(s[1] - P) < EPS for s in tri), (b, f))

    def test_appui_et_retours_presents(self):
        b = baie("retrait", 2.0, 1.5, 0.2)
        tris = decor.construire_decor(b, "habitation", 1)
        self.assertGreaterEqual(len(tris), 12)
        self.assertTrue(any(all(s[2] < 0.06 + EPS for s in t) and any(s[1] < -0.01 for s in t) for t in tris))

    def test_vitrine_libre_au_sol_et_consoles_courtes(self):
        for L, H, P in itertools.product((0.8, 2.5, 12.0), (0.8, 2.5, 5.0), (0.1, 0.28)):
            for f in FAMILLES:
                for g in range(3):
                    b = baie("retrait", L, H, P, vitrine=True)
                    for tri in decor.construire_decor(b, f, g):
                        plan_retour = all(abs(s[0]) < EPS for s in tri) or all(abs(s[0] - L) < EPS for s in tri)
                        if not plan_retour:
                            self.assertGreaterEqual(min(s[2] for s in tri), 0.4 * H - EPS, (L, H, f))
                        self.assertGreaterEqual(min(s[1] for s in tri), -0.12 - EPS)

    def test_saillie_de_l_appui_bornee(self):
        for b, f, g in cas_retraits():
            for tri in decor.construire_decor(b, f, g):
                self.assertGreaterEqual(min(s[1] for s in tri), -0.13 - EPS)


class Corniche(unittest.TestCase):
    def test_bande_superieure_seulement(self):
        for b, f, g in cas_corniches():
            H = b["hauteur"]
            tris = decor.construire_decor(b, f, g)
            self.assertGreaterEqual(len(tris), 12, (b, f))
            for tri in tris:
                for s in tri:
                    self.assertGreaterEqual(s[2], H - 0.66 - EPS)
                    self.assertLessEqual(s[1], EPS)

    def test_etagement_et_retour(self):
        L, H = 6.0, 4.0
        tris = decor.construire_decor(baie("corniche", L, H, 0.12), "public", 9)
        profondeurs = sorted({round(s[1], 4) for t in tris for s in t if s[1] < -EPS})
        self.assertGreaterEqual(len(profondeurs), 3)  # au moins trois ressauts
        retours = [t for t in tris if all(abs(s[0]) < EPS for s in t) or all(abs(s[0] - L) < EPS for s in t)]
        self.assertTrue(retours)

    def test_lames_ou_agrafes_au_plus_deux(self):
        for g in range(30):
            tris = decor.construire_decor(baie("corniche", 20, 10, 0.12), "deco", g)
            # les lames sont les seuls volumes qui ne couvrent pas toute la largeur
            # on exclut les retours de la tablette, sur les plans x=0 et x=L
            def sur_bout(t):
                return all(abs(s[0]) < EPS for s in t) or all(abs(s[0] - 20) < EPS for s in t)

            etroits = [t for t in tris if not sur_bout(t)
                       and max(s[0] for s in t) - min(s[0] for s in t) < 1.0]
            self.assertTrue(any(sur_bout(t) for t in tris))  # les retours existent bien
            xs = sorted({round(min(s[0] for s in t), 3) for t in etroits})
            amas = sum(1 for i, x in enumerate(xs) if i == 0 or x - xs[i - 1] > 0.5)
            self.assertLessEqual(amas, 2)
            self.assertLessEqual(len(tris), 27)


class VariationEtDeterminisme(unittest.TestCase):
    def test_deterministe(self):
        for b, f, g in itertools.islice(tous_les_cas(), 0, None, 37):
            a = decor.construire_decor(b, f, g)
            random.seed(1234)
            c = decor.construire_decor(b, f, g)
            random.seed(99)
            d = decor.construire_decor(dict(b), f, g)
            self.assertEqual(a, c)
            self.assertEqual(a, d)

    def test_entree_non_modifiee(self):
        b = baie("piece", 3, 3, 1.5, teinte=(200, 180, 150))
        copie = dict(b)
        decor.construire_decor(b, "deco", 5)
        self.assertEqual(b, copie)

    def test_graines_donnent_des_variantes(self):
        for mode, dims in (("piece", (3.0, 3.0, 1.6)), ("retrait", (3.0, 2.0, 0.2)),
                           ("corniche", (10.0, 6.0, 0.12))):
            for f in FAMILLES:
                variantes = {tuple(decor.construire_decor(baie(mode, *dims), f, g)) for g in range(24)}
                minimum = 4 if mode == "retrait" else 12
                if mode == "corniche":
                    minimum = 8
                self.assertGreaterEqual(len(variantes), minimum, (mode, f))

    def test_costumes_de_pieces_differents(self):
        for f in FAMILLES:
            couleurs = {decor.construire_decor(baie("piece", 3, 3, 1.6), f, g)[8][0][3:] for g in range(24)}
            self.assertGreaterEqual(len(couleurs), 3, f)

    def test_pas_de_motif_repete_a_l_identique(self):
        tris = decor.construire_decor(baie("piece", 3, 3, 1.6), "commerce", 11)
        formes = [tuple(sorted((round(s[0] - t[0][0], 3), round(s[1] - t[0][1], 3), round(s[2] - t[0][2], 3))
                               for s in t)) + tuple(t[0][3:]) for t in tris[10:]]
        self.assertGreater(len(set(formes)), len(formes) * 0.4)

    def test_teinte_influence_architecture(self):
        sans = decor.construire_decor(baie("retrait", 2, 2, 0.2), "deco", 1)
        rouge = decor.construire_decor(baie("retrait", 2, 2, 0.2, teinte=(200, 60, 60)), "deco", 1)
        self.assertNotEqual(sans, rouge)
        self.assertEqual(len(sans), len(rouge))


class Hygiene(unittest.TestCase):
    def test_source_sans_dependance_ni_acces_fichier(self):
        arbre = ast.parse(SOURCE.read_text(encoding="utf-8"))
        modules = set()
        for n in ast.walk(arbre):
            if isinstance(n, ast.Import):
                modules.update(a.name.split(".")[0] for a in n.names)
            elif isinstance(n, ast.ImportFrom):
                modules.add((n.module or "").split(".")[0])
        self.assertLessEqual(modules, {"__future__", "math", "random"})
        appels = {n.func.id for n in ast.walk(arbre) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        self.assertFalse(appels & {"open", "exec", "eval", "__import__"})


if __name__ == "__main__":
    unittest.main()
