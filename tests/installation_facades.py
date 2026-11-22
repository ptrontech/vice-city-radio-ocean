"""L’essai sur l’archive personnelle est activé par VICE_CITY_ORIGINE."""
from hashlib import sha256
from math import hypot
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "outils"))
import facades
import ancrage_majestic
import relief_majestic
import installer_facades
import maillage_rw
from marquise_majestic import prolonger_marquise
import textures


def index(dossier):
    return list(textures.ENTRY.iter_unpack((dossier / "gta3.dir").read_bytes()))


def dictionnaire(dossier, entree):
    secteur, taille, _ = entree
    with (dossier / "gta3.img").open("rb") as image:
        image.seek(secteur * textures.SECTOR)
        return image.read(taille * textures.SECTOR)


def aires_par_materiau(surface):
    aires = [0.] * len(surface["materiaux"])
    sommets = surface["positions"]
    for a, b, c, materiau in surface["triangles"]:
        u = [y - x for x, y in zip(sommets[a], sommets[b])]
        v = [y - x for x, y in zip(sommets[a], sommets[c])]
        aires[materiau] += hypot(u[1]*v[2] - u[2]*v[1], u[2]*v[0] - u[0]*v[2],
                                  u[0]*v[1] - u[1]*v[0]) / 2
    return aires


class Installation(unittest.TestCase):
    def test_protection_de_l_original(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "distincte"):
                installer_facades.installer(tmp, tmp)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_marquise_arrondie_et_reversible_par_geometrie(self):
        # Dalle rectangulaire fictive et vitrine de référence au-dessous.
        terrain = {
            "materiaux": ("bow_abattoir_conc2", "hotelwindow2"),
            "positions": ((-12,-14,-9.39), (12,-14,-9.39), (12,14,-9.39), (-12,14,-9.39),
                          (7,2,-13.6), (7,-3,-13.6), (7,2,-10.34)),
            "triangles": ((0,1,2,0), (0,2,3,0), (4,5,6,1)),
        }
        jour = prolonger_marquise(terrain)
        nuit = prolonger_marquise(terrain, nuit=True)
        self.assertEqual(len(jour), len(nuit))
        self.assertGreater(len(jour), 150)
        self.assertEqual([[v[:3] for v in t] for t in jour], [[v[:3] for v in t] for t in nuit])
        self.assertNotEqual(jour, nuit)
        coins = [v for t in jour for v in t]
        self.assertAlmostEqual(max(v[0] for v in coins), 13.49)
        self.assertAlmostEqual(max(v[1] for v in coins), 15.49)
        self.assertGreater(min(v[2] for v in coins), -10.34)
        self.assertEqual(prolonger_marquise({**terrain, "triangles": terrain["triangles"][:2]}), [])

    @unittest.skipUnless(os.environ.get("VICE_CITY_ORIGINE"), "copie personnelle non fournie")
    def test_pose_reprise_et_retrait(self):
        origine = Path(os.environ["VICE_CITY_ORIGINE"]).resolve()
        with TemporaryDirectory() as tmp:
            travail = Path(tmp)
            modeles = travail / "models"
            src = origine / "models"
            attendues = installer_facades.VOIRIE
            install = lambda actives: installer_facades.installer(origine, travail, actives)
            self.assertEqual(install(False)["sha256"], attendues)
            avant = index(modeles)
            # Échec après l’image agrandie, juste avant le nouvel index.
            remplacer = textures.replace

            def interrompre(fichier, somme, ecrire):
                if fichier.name == "gta3.dir":
                    raise OSError("arrêt simulé")
                remplacer(fichier, somme, ecrire)

            with patch.object(textures, "replace", side_effect=interrompre):
                with self.assertRaisesRegex(OSError, "arrêt simulé"):
                    install(True)
            self.assertEqual(index(modeles), avant)
            actif = install(True)
            apres = index(modeles)
            self.assertEqual(len(avant), len(apres))
            affectees = [i for i, (a, b) in enumerate(zip(avant, apres)) if a != b]
            self.assertEqual({textures.name(avant[i][2]) for i in affectees}, installer_facades.ENTREES)
            for i in affectees:
                nom = textures.name(avant[i][2])
                self.assertEqual(avant[i][2], apres[i][2])
                a = dictionnaire(src, avant[i])
                b = dictionnaire(modeles, apres[i])
                if nom in installer_facades.MODELES:
                    original, relief = maillage_rw.lire_surface(a), maillage_rw.lire_surface(b)
                    self.assertEqual(relief["positions"][:len(original["positions"])], original["positions"])
                    self.assertEqual(relief["materiaux"][:-1], original["materiaux"])
                    # La cuisson subdivise la surface réceptrice, sans changer les
                    # dimensions de chacune des surfaces de matériau originales.
                    for a0, a1 in zip(aires_par_materiau(original), aires_par_materiau(relief)):
                        self.assertAlmostEqual(a0, a1, delta=max(.003, a0 * 1e-5))
                    aretes = ancrage_majestic.coutures_toit(original)
                    self.assertGreaterEqual(len(aretes), 8)
                    altitudes = [p[2] for a, b, _ in aretes for p in (a, b)]
                    self.assertGreater(max(altitudes) - min(altitudes), 3.)
                    panneaux = relief_majestic._preparer(original)["panneaux"]["hotelwindow1"]
                    self.assertEqual(len(panneaux), 24)
                    murs = ancrage_majestic.parements(original)
                    ajouts = [tuple(relief["positions"][i] for i in (a,b,c))
                              for a,b,c,m in relief["triangles"] if m == len(original["materiaux"])]
                    for p in panneaux:
                        s0, s1, z0, z1 = p["s0"], p["s1"], p["z0"], p["z1"]
                        sc, zc = (s0+s1)/2, (z0+z1)/2
                        for x,z in ((s0-.10,zc), (s1+.10,zc), (sc,z0-.10), (sc,z1+.10)):
                            parametres = p["t"], p["n"], x, z, p["d"]
                            facade = ancrage_majestic.profondeur(murs, *parametres)
                            garniture = ancrage_majestic.profondeur(ajouts, *parametres)
                            self.assertIsNotNone(garniture)
                            self.assertGreater(garniture, facade if facade is not None else p["d"])
                    self.assertGreater(len(relief["triangles"]), len(original["triangles"]))
                    self.assertEqual(len(relief["materiaux"]), len(original["materiaux"]) + 1)
                    continue
                mesures = facades.verifier(a, b, facades.MATERIAUX[nom])
                self.assertTrue(mesures["empreinte_origine"])
                self.assertTrue(mesures["niveau_origine_identique"])
                self.assertTrue(mesures["autres_textures_identiques"])
            dates = {n: (modeles/n).stat().st_mtime_ns for n in attendues}
            self.assertEqual(install(True), actif)
            self.assertEqual({n: (modeles/n).stat().st_mtime_ns for n in attendues}, dates)

            # Un suffixe étranger doit rester intact pendant une tentative de retrait.
            fichier = modeles / "gta3.img"
            taille = fichier.stat().st_size
            with fichier.open("ab") as image:
                image.write(b"ATELIER-ESSAI")
            with self.assertRaisesRegex(ValueError, "étrangers"):
                install(False)
            self.assertEqual(index(modeles), apres)
            with fichier.open("r+b") as image:
                image.seek(taille)
                self.assertEqual(image.read(), b"ATELIER-ESSAI")
                image.truncate(taille)

            # Le retrait doit retrouver la voirie améliorée à l’octet, puis la
            # réinstallation doit retrouver exactement l’archive active antérieure.
            self.assertEqual(install(False)["sha256"], attendues)
            self.assertEqual({n: textures.digest(modeles/n).hexdigest() for n in attendues}, attendues)
            self.assertEqual(install(True), actif)
            self.assertEqual(sha256((modeles/"gta3.dir").read_bytes()).hexdigest(), actif["sha256"]["gta3.dir"])
            self.assertEqual(textures.digest(src/"gta3.img").hexdigest(), textures.RETAIL["gta3.img"])


if __name__ == "__main__":
    unittest.main()
