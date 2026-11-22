"""Tests synthétiques du profil « Nuits d'orage ». Lancer : python tests/nuits_orage.py"""
import importlib.util
from pathlib import Path
import unittest

_CHEMIN = Path(__file__).resolve().parents[1] / "outils" / "nuits_orage.py"
_SPEC = importlib.util.spec_from_file_location("nuits_orage_outil", _CHEMIN)
profil = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(profil)

PLUIE = (2, 5)
HEURES_NUIT = (0, 1, 2, 3, 4, 22, 23)
MODIFIEES = (list(range(0, 3)) + list(range(12, 15)) + list(range(15, 18)) + list(range(18, 21))
             + [29, 33, 34, 35] + list(range(36, 45)) + list(range(48, 52)))


def valeurs(section, heure):
    base = [100 + (section * 7 + heure * 3 + c * 5) % 100 for c in range(52)]
    base[29], base[33], base[34], base[35] = 120, 900.0, 400.0, 60.0
    return base


def ligne(v, fin="", espace=" "):
    texte = []
    for i, x in enumerate(v):
        texte.append(f"{x:.1f}" if i in (33, 34) else str(x))
    return espace.join(texte) + fin


def palette(constante=False, fin="\n"):
    sortie = ["// En-tête libre" + fin]
    for s in range(7):
        noms = ("SUNNY", "CLOUDY", "RAINY", "FOGGY", "EXTRASUNNY", "RAINY", "EXTRACOLOURS")
        sortie.append(f"//////////// {noms[s]}" + fin)
        for h in range(24):
            v = valeurs(0 if constante else s, 0 if constante else h)
            sortie.append(ligne(v, f"\t// heure {h}", espace="  ") + fin)
    return "".join(sortie)


def lignes_donnees(texte):
    sections, courante = [], None
    for l in texte.splitlines():
        if l.startswith("////"):
            courante = []
            sections.append(courante)
        elif l and l[0].isdigit():
            courante.append(l.partition("//")[0].split())
    return sections


class NuitsOrage(unittest.TestCase):
    def setUp(self):
        self.base = palette()
        self.sortie = profil.appliquer_nuits_orage(self.base)
        self.avant = lignes_donnees(self.base)
        self.apres = lignes_donnees(self.sortie)

    def test_structure_et_commentaires(self):
        self.assertEqual(len(self.apres), 7)
        for s in self.apres:
            self.assertEqual(len(s), 24)
            self.assertTrue(all(len(h) == 52 for h in s))
        a, b = self.base.splitlines(), self.sortie.splitlines()
        self.assertEqual(len(a), len(b))
        for x, y in zip(a, b):
            if not x[:1].isdigit():
                self.assertEqual(x, y)
            else:
                self.assertEqual(x.partition("//")[1:], y.partition("//")[1:])
                self.assertEqual(len(x.split("//")[0]) - len(x.split("//")[0].rstrip()),
                                 len(y.split("//")[0]) - len(y.split("//")[0].rstrip()))

    def test_sections_hors_pluie_identiques(self):
        for s in (0, 1, 3, 4, 6):
            self.assertEqual(self.avant[s], self.apres[s])
        base_l, sortie_l = self.base.splitlines(), self.sortie.splitlines()
        for i, (x, y) in enumerate(zip(base_l, sortie_l)):
            if x == y:
                continue
            self.assertTrue(x[:1].isdigit())

    def test_midi_et_colonnes_inchangees(self):
        for s in PLUIE:
            for h in range(9, 17):
                self.assertEqual(self.avant[s][h], self.apres[s][h])
            for h in range(24):
                for c in range(52):
                    if c not in MODIFIEES:
                        self.assertEqual(self.avant[s][h][c], self.apres[s][h][c], (s, h, c))

    def test_changements_reels_la_nuit(self):
        for s in PLUIE:
            for h in HEURES_NUIT:
                av, ap = self.avant[s][h], self.apres[s][h]
                for debut, fin in ((15, 18), (18, 21), (36, 39), (48, 51)):
                    self.assertNotEqual(av[debut:fin], ap[debut:fin], (s, h, debut))
                self.assertLess(float(ap[33]), float(av[33]))
                self.assertLess(float(ap[34]), float(av[34]))
                self.assertLess(float(ap[35]), float(av[35]))

    def test_bornes_rgb_alpha_et_lisibilite(self):
        couleurs = [c for c in MODIFIEES if c not in (29, 33, 34, 35)]
        for s in PLUIE:
            for h in range(24):
                av, ap = self.avant[s][h], self.apres[s][h]
                for c in couleurs:
                    x, y = float(av[c]), float(ap[c])
                    self.assertTrue(0 <= y <= 255, (s, h, c, y))
                    self.assertLessEqual(abs(y - x), 60.5, (s, h, c))
                for c in range(0, 3):
                    self.assertGreaterEqual(float(ap[c]), min(float(av[c]), 28))
                self.assertGreaterEqual(float(ap[33]), .8 * float(av[33]) - .1)
                self.assertLess(float(ap[34]), float(ap[33]))
                self.assertLessEqual(float(ap[29]), 255.0)

    def test_transition_lisse_soir_matin(self):
        constante = profil.appliquer_nuits_orage(palette(constante=True))
        rangees = lignes_donnees(constante)
        for s in PLUIE:
            for h in range(24):
                a, b = rangees[s][h], rangees[s][(h + 1) % 24]
                for c in MODIFIEES:
                    seuil = 0.30 * max(abs(float(a[c])), 1) + 20
                    self.assertLessEqual(abs(float(a[c]) - float(b[c])), seuil, (s, h, c))
        for h in range(24):
            self.assertLessEqual(abs(profil.NUIT[h] - profil.NUIT[(h + 1) % 24]), .27 + 1e-9)

    def test_format_des_nombres_et_fins_de_ligne(self):
        self.assertNotIn("\r", self.sortie)
        crlf = profil.appliquer_nuits_orage(palette(fin="\r\n"))
        self.assertEqual(crlf.replace("\r\n", "\n"), self.sortie)
        for s in self.apres:
            for h in s:
                for c in (33, 34):
                    self.assertRegex(h[c], r"^\d+\.\d{1,6}$")
                for c in (0, 15, 18, 48, 51):
                    self.assertRegex(h[c], r"^\d+$")

    def test_ouragan_et_palettes_speciales(self):
        index = self.base.rindex("//////////// RAINY")
        explicite = self.base[:index] + self.base[index:].replace("RAINY", "HURRICANE", 1)
        self.assertEqual(lignes_donnees(profil.appliquer_nuits_orage(explicite)),self.apres)
        self.assertEqual(self.sortie.split("//////////// EXTRACOLOURS")[1],
                         self.base.split("//////////// EXTRACOLOURS")[1])
        with self.assertRaisesRegex(ValueError, "En-tête météo"):
            profil.appliquer_nuits_orage(self.base.replace("FOGGY", "RAINY"))

    def test_intensites_ou_distances_ecrites_en_entiers(self):
        v = valeurs(2, 0)
        v[29], v[33], v[34], v[35] = 1, 650, -5, 1
        ancienne = ligne(valeurs(2, 0), "\t// heure 0", "  ")
        nouvelle = " ".join(map(str,v)) + "\t// heure 0"
        mod = profil.appliquer_nuits_orage(self.base.replace(ancienne, nouvelle, 1))
        a = list(map(float,lignes_donnees(mod)[2][0]))
        self.assertEqual([a[i] for i in (29,33,34,35)], [1.15,533.0,-6.5,.88])

    def test_erreurs_explicites(self):
        with self.assertRaises(TypeError):
            profil.appliquer_nuits_orage(b"x")
        court = self.base.replace(ligne(valeurs(0, 0), "\t// heure 0", "  "),
                                  ligne(valeurs(0, 0)[:51], "\t// heure 0", "  "))
        with self.assertRaisesRegex(ValueError, "51 colonnes"):
            profil.appliquer_nuits_orage(court)
        with self.assertRaisesRegex(ValueError, "Structure"):
            profil.appliquer_nuits_orage(self.base.rsplit("\n", 2)[0] + "\n")
        with self.assertRaisesRegex(ValueError, "trop de sections"):
            profil.appliquer_nuits_orage(self.base + "//////////// Extra\n")
        with self.assertRaisesRegex(ValueError, "avant la première section"):
            profil.appliquer_nuits_orage(ligne(valeurs(0, 0)) + "\n" + self.base)
        with self.assertRaisesRegex(ValueError, "non numérique"):
            profil.appliquer_nuits_orage(_avec_jeton_invalide(self.base))
        with self.assertRaises(ValueError):
            profil.appliquer_nuits_orage("")


def _avec_jeton_invalide(texte):
    lignes = texte.splitlines(keepends=True)
    for i, l in enumerate(lignes):
        if l[:1].isdigit():
            jetons = l.split("//")[0].split()
            jetons[3] = "abc"
            lignes[i] = " ".join(jetons) + "\n"
            break
    return "".join(lignes)


if __name__ == "__main__":
    unittest.main()
