"""Tests synthétiques de l'aperçu météo. Lancer : python tests/apercu_meteo.py"""
import contextlib
import importlib.util
import io
from pathlib import Path
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET

_CHEMIN = Path(__file__).resolve().parents[1] / "outils" / "apercu_meteo.py"
_SPEC = importlib.util.spec_from_file_location("apercu_meteo_outil", _CHEMIN)
apercu = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(apercu)

SVG = "{http://www.w3.org/2000/svg}"
NOMS = ("SUNNY", "CLOUDY", "RAINY", "FOGGY", "EXTRA", "THUNDERSTORM", "SPECIAL")


def valeurs(section, heure, orage):
    """Données inventées : aucune valeur du jeu."""
    v = [100.0] * 52
    d = 5 if orage else 0
    v[15:18] = [10 + section + 2 - d, 20 + heure - d, 30 - d]      # ciel haut
    v[18:21] = [60 + section, 70 + heure, 80 + d]                  # horizon
    v[48:51] = [20, 60 + heure, 90 - d]                            # eau
    v[51] = 180
    return v


def palette(orage, noms=NOMS, fin="\n"):
    lignes = ["// En-tête libre inventé" + fin]
    for s in range(7):
        lignes.append(f"//////////// {noms[s]}" + fin)
        for h in range(24):
            lignes.append(" ".join(f"{x:g}" for x in valeurs(s, h, orage)) + f"\t// {h} h" + fin)
    return "".join(lignes)


def textes(svg):
    racine = ET.fromstring(svg)
    return racine, [" ".join("".join(t.itertext()).split()) for t in racine.iter(SVG + "text")]


class ApercuMeteo(unittest.TestCase):
    def setUp(self):
        self.base, self.orage = palette(False), palette(True)
        self.svg = apercu.construire_apercu(self.base, self.orage)

    def test_svg_autonome_accessible_et_deterministe(self):
        racine, lignes = textes(self.svg)
        self.assertEqual(racine.get("role"), "img")
        self.assertEqual(racine.get("lang"), "fr")
        self.assertTrue(racine.find(SVG + "title").text)
        self.assertTrue(racine.find(SVG + "desc").text)
        schemas = [g for g in racine.iter(SVG + "g") if g.get("role") == "img"]
        self.assertEqual(len(schemas), 2 * 3 * 2)           # base/orage × 3 heures × 2 sections
        self.assertTrue(all(g.get("aria-label") and g.find(SVG + "title") is not None for g in schemas))
        self.assertIn("pas une capture du jeu", " ".join(lignes))
        self.assertEqual(self.svg, apercu.construire_apercu(self.base, self.orage))
        self.assertNotIn("\r", self.svg)
        self.assertNotRegex(self.svg, r"https?://(?!www\.w3\.org)|<image|<script|href=")

    def test_couleurs_chiffrees_et_heures_echantillonnees(self):
        _, lignes = textes(self.svg)
        texte = "\n".join(lignes)
        # Section 2, 2 h : haut du ciel (14, 22, 30) en base, (9, 17, 25) en orage.
        self.assertIn("Ciel haut : 14 22 30 (#0E161E)", texte)
        self.assertIn("Ciel haut : 9 17 25 (#091119)", texte)
        self.assertIn("Mer : 20 62 90 (#143E5A), opacité 180/255", texte)
        for h in (2, 6, 23):
            self.assertRegex(texte, rf"Section 2 · RAINY — {h} h")
            self.assertRegex(texte, rf"Section 5 · THUNDERSTORM — {h} h")
        self.assertNotRegex(texte, r"— (0|12|18) h")

    def test_section_speciale_selon_le_nom_de_l_entete(self):
        noms = NOMS[:5] + ("CALM",) + NOMS[6:]
        svg = apercu.construire_apercu(palette(False, noms), palette(True, noms))
        racine, lignes = textes(svg)
        texte = "\n".join(lignes)
        self.assertNotIn("Section 5 ·", texte)
        self.assertIn("section non affichée", texte)
        self.assertEqual(len([g for g in racine.iter(SVG + "g") if g.get("role") == "img"]), 6)

    def test_les_deux_sections_rainy_du_jeu_classique(self):
        noms = ("SUNNY", "CLOUDY", "RAINY", "FOGGY", "EXTRASUNNY", "RAINY", "EXTRACOLOURS")
        root, lignes = textes(apercu.construire_apercu(palette(False,noms), palette(True,noms)))
        self.assertEqual(len([g for g in root.iter(SVG + "g") if g.get("role") == "img"]), 12)
        for heure in (2, 6, 23):
            self.assertIn(f"Section 5 · Ouragan (RAINY) — {heure} h", lignes)
        self.assertFalse(any("Section 6" in ligne for ligne in lignes))

    def test_fins_de_ligne_windows_acceptees(self):
        crlf = apercu.construire_apercu(palette(False, fin="\r\n"), palette(True, fin="\r\n"))
        self.assertEqual(crlf, self.svg)

    def test_entrees_invalides_expliquees(self):
        un = self.base.splitlines()
        court = "\n".join(l if i != 5 else " ".join(l.partition("//")[0].split()[:51]) for i, l in enumerate(un))
        with self.assertRaisesRegex(ValueError, r"Palette de base, ligne 6 : 51 colonnes au lieu de 52"):
            apercu.construire_apercu(court, self.orage)
        with self.assertRaisesRegex(ValueError, "structure inattendue"):
            apercu.construire_apercu(self.base, "\n".join(self.orage.splitlines()[:-1]))
        with self.assertRaisesRegex(ValueError, "Palette orage, ligne 3 : valeur non numérique"):
            apercu.construire_apercu(self.base, _jeton_invalide(self.orage))
        with self.assertRaisesRegex(ValueError, "valeur non finie"):
            apercu.construire_apercu(self.base, self.orage.replace("180", "1e999", 1))
        with self.assertRaisesRegex(ValueError, "plus de 7 sections"):
            apercu.construire_apercu(self.base + "//////////// EXTRA\n", self.orage)
        with self.assertRaisesRegex(ValueError, "pas les mêmes en-têtes"):
            apercu.construire_apercu(self.base, palette(True, NOMS[:2] + ("DRY",) + NOMS[3:]))
        with self.assertRaisesRegex(ValueError, "précèdent le premier en-tête"):
            apercu.construire_apercu(" ".join(["1"] * 52) + "\n" + self.base, self.orage)
        with self.assertRaises(TypeError):
            apercu.construire_apercu(b"x", self.orage)

    def test_ligne_de_commande(self):
        with tempfile.TemporaryDirectory() as dossier:
            d = Path(dossier)
            (d / "base.dat").write_text(self.base, encoding="latin-1")
            (d / "orage.dat").write_text(self.orage, encoding="latin-1")
            sortie = d / "apercu.svg"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(apercu.main([str(d / "base.dat"), str(d / "orage.dat"), str(sortie)]), 0)
            self.assertEqual(sortie.read_text(encoding="utf-8"), self.svg)

            def echec(*args):
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    code = apercu.main(list(map(str, args)))
                return code, err.getvalue()

            code, message = echec(d / "absent.dat", d / "orage.dat", d / "x.svg")
            self.assertEqual(code, 2)
            self.assertIn("introuvable", message)
            code, message = echec(d / "base.dat", d / "orage.dat", d / "x.txt")
            self.assertEqual(code, 2)
            self.assertIn(".svg", message)
            code, message = echec(d / "base.dat", d / "orage.dat", d / "base.dat")
            self.assertEqual(code, 2)
            (d / "mauvais.dat").write_text("rien d'utile\n", encoding="latin-1")
            code, message = echec(d / "mauvais.dat", d / "orage.dat", d / "x.svg")
            self.assertEqual(code, 2)
            self.assertIn("structure inattendue", message)
            self.assertFalse((d / "x.svg").exists())
            code, message = echec(d / "base.dat")
            self.assertEqual(code, 2)
            self.assertIn("Usage", message)


def _jeton_invalide(texte):
    lignes = texte.splitlines(keepends=True)
    i = next(k for k, l in enumerate(lignes) if l[:1].isdigit())
    jetons = lignes[i].partition("//")[0].split()
    jetons[3] = "abc"
    lignes[i] = " ".join(jetons) + "\n"
    return "".join(lignes)


if __name__ == "__main__":
    unittest.main()
