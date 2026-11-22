"""L’essai sur l’archive personnelle est activé par VICE_CITY_ORIGINE."""
from hashlib import sha256
from functools import lru_cache
from math import hypot
from struct import pack_into, unpack_from
import json
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
import matieres_volume
import volume_rw
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


def empreintes_entrees(dossier, entrees):
    sommes = []
    with (dossier / "gta3.img").open("rb") as image:
        for secteur, taille, _ in entrees:
            image.seek(secteur * textures.SECTOR)
            contenu = image.read(taille * textures.SECTOR)
            if len(contenu) != taille * textures.SECTOR:
                raise ValueError("Entrée tronquée")
            sommes.append(sha256(contenu).digest())
    return sommes


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

    def test_compactage_ordonne_avec_doublons_et_secteurs_deplaces(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp) / "base"
            prets = Path(tmp) / "prets"
            base.mkdir()
            prets.mkdir()
            secteur = textures.SECTOR
            entree = textures.ENTRY.pack
            (base / "gta3.img").write_bytes(b"A"*secteur + b"B"*secteur + b"C"*secteur)
            (base / "gta3.dir").write_bytes(entree(2, 1, b"generic.txd") + entree(1, 1, b"mur.dff")
                                            + entree(0, 1, b"generic.txd"))
            (base / "generic.txd").write_bytes(b"voirie")
            installer_facades.compacter(base, prets, b"D"*(2*secteur),
                                       {1: (installer_facades.TAILLE_VOIRIE // secteur, 2)})
            self.assertEqual([(p,n) for p,n,_ in index(prets)], [(0,1),(1,2),(3,1)])
            self.assertEqual((prets / "gta3.img").read_bytes(), b"C"*secteur+b"D"*(2*secteur)+b"A"*secteur)
            self.assertEqual((prets / "generic.txd").read_bytes(), b"voirie")

    def test_reprise_du_lancement_preserve_un_changement_tiers(self):
        with TemporaryDirectory() as tmp:
            dossier = Path(tmp) / "models"
            journal = dossier / installer_facades.TRANSACTION
            journal.mkdir(parents=True)
            anciens = {n: n.encode() for n in installer_facades.VOIRIE}
            nouveaux = {n: b"v2-" + contenu for n, contenu in anciens.items()}
            a = {n: sha256(v).hexdigest() for n,v in anciens.items()}
            b = {n: sha256(v).hexdigest() for n,v in nouveaux.items()}
            for nom in a:
                (dossier / nom).write_bytes(anciens[nom])
                (journal / nom).write_bytes(nouveaux[nom])
            (journal / installer_facades.MANIFESTE).write_text(json.dumps({"avant":a,"cible":b}), encoding="utf-8")
            with patch.object(installer_facades, "VOIRIE", a), patch.object(installer_facades, "VILLE", b):
                os.replace(journal / "gta3.img", dossier / "gta3.img")
                (dossier / "generic.txd").write_bytes(b"personnel")
                with self.assertRaisesRegex(ValueError, "étrangère"):
                    installer_facades.recuperer(tmp)
                self.assertEqual((dossier / "generic.txd").read_bytes(), b"personnel")
                self.assertEqual((dossier / "gta3.dir").read_bytes(), anciens["gta3.dir"])
                (dossier / "generic.txd").write_bytes(anciens["generic.txd"])
                self.assertTrue(installer_facades.recuperer(tmp))
                self.assertFalse(installer_facades.recuperer(tmp))
                self.assertEqual(installer_facades.etat(dossier), b)

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
            # Les interruptions simulées modifient la destination. La source et son
            # index sont identiques à chaque nouvel essai dans ce répertoire temporaire.
            secteurs = lru_cache(maxsize=1)(installer_facades.produire_secteurs)
            cache = patch.object(installer_facades, "produire_secteurs", secteurs)
            cache.start()
            self.addCleanup(cache.stop)
            install = lambda actives: installer_facades.installer(origine, travail, actives)
            self.assertEqual(install(False)["sha256"], attendues)
            avant = index(modeles)
            sommes_voirie = empreintes_entrees(modeles, avant)
            # Couper la véritable publication après l'IMG et avant le DIR.
            deplacer = os.replace
            def interrompre(source, fichier):
                if Path(fichier) == modeles / "gta3.dir":
                    raise OSError("arrêt simulé")
                deplacer(source, fichier)
            with patch.object(os, "replace", side_effect=interrompre):
                with self.assertRaisesRegex(OSError, "arrêt simulé"):
                    install(True)
            self.assertEqual(index(modeles), avant)
            self.assertTrue(installer_facades.recuperer(travail))
            actif = install(True)
            self.assertEqual(actif["sha256"], installer_facades.VILLE)
            apres = index(modeles)
            self.assertEqual([n for _,_,n in avant], [n for _,_,n in apres])
            self.assertEqual(len(apres), 6043)
            position = 0
            for debut, taille, _ in apres:
                self.assertEqual(debut, position)
                position += taille
            self.assertEqual((modeles/"gta3.img").stat().st_size, position * textures.SECTOR)
            sommes_ville = empreintes_entrees(modeles, apres)
            affectees = [i for i,(a,b) in enumerate(zip(sommes_voirie, sommes_ville)) if a != b]
            plans_ville = installer_facades.facades_ville.inventorier(origine, signer=False)["plans"]
            self.assertEqual({textures.name(avant[i][2]) for i in affectees},
                             installer_facades.ENTREES | set(plans_ville))
            for i in affectees:
                nom = textures.name(avant[i][2])
                self.assertEqual(avant[i][2], apres[i][2])
                a = dictionnaire(src, avant[i])
                b = dictionnaire(modeles, apres[i])
                if nom in installer_facades.MODELES:
                    original, relief = maillage_rw.lire_surface(a), maillage_rw.lire_surface(b)
                    self.assertEqual(relief["positions"][:len(original["positions"])], original["positions"])
                    nuit = installer_facades.MODELES[nom]
                    anciens = tuple(matieres_volume.EMAIL if m == matieres_volume.EMAIL_ORIGINE else m
                                    for m in original["materiaux"])
                    self.assertEqual(tuple(relief["materiaux"][:len(anciens)]), anciens)
                    utilises = {relief["materiaux"][m] for _, _, _, m in relief["triangles"]}
                    self.assertTrue(utilises.isdisjoint(volume_rw.OUVERTURES))
                    self.assertTrue(set(volume_rw.NOMS.values()).issubset(utilises))
                    avant_aires = aires_par_materiau(original)
                    apres_aires = aires_par_materiau(relief)
                    for nom_matiere, a0, a1 in zip(original["materiaux"], avant_aires, apres_aires):
                        tolerance = max(.003, a0 * 1e-5)
                        if nom_matiere in volume_rw.OUVERTURES:
                            self.assertEqual(a1, 0)
                        elif nom_matiere in volume_rw.PEAUX:
                            self.assertLessEqual(a1, a0 + tolerance)
                        else:
                            self.assertAlmostEqual(a0, a1, delta=tolerance)
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
                    self.assertEqual(len(relief["materiaux"]), len(anciens) + 1 + len(volume_rw.NOMS))
                    self.assertLess(len(relief["positions"]), 65_535)
                    continue
                if nom in installer_facades.EFFETS_VOITURES or nom in installer_facades.EFFETS_AFFICHE:
                    self.assertNotEqual(b, a)
                    longueur = 12 + unpack_from("<I", b, 4)[0]
                    self.assertGreater(len(b), 12)
                    self.assertFalse(any(b[longueur:]))
                    continue
                if nom in plans_ville and nom not in installer_facades.ENTREES:
                    self.assertNotEqual(a,b)
                    self.assertEqual(unpack_from("<I", b)[0], maillage_rw.CLUMP)
                    continue
                if nom in installer_facades.EFFETS_SEUIL:
                    collision = installer_facades.EFFETS_SEUIL[nom](a)
                    self.assertEqual(b[:len(collision)], collision)
                    self.assertFalse(any(b[len(collision):]))
                    continue
                if nom in installer_facades.EFFETS_PALMIER:
                    fin = 12 + unpack_from("<I", b, 4)[0]
                    self.assertEqual(b[:fin], installer_facades.EFFETS_PALMIER[nom](a))
                    self.assertNotEqual(a[:fin], b[:fin])
                    continue
                if nom == "od_hotels1.txd":
                    intermediaire = facades.ameliorer_txd(nom, a, exiger_empreinte=True)
                    def natives_txd(blob):
                        return {n: inner for _, _, inner, n, _ in textures.natives(textures.dictionary(blob)[1])}
                    anciens = natives_txd(intermediaire)
                    installes = natives_txd(b)
                    self.assertEqual({n: installes[n] for n in anciens}, anciens)
                    attendus = set(volume_rw.NOMS.values()) | {matieres_volume.EMAIL}
                    self.assertEqual(installes.keys() - anciens.keys(), attendus)
                    raster_verre = installes[volume_rw.NOMS["verre"]][0][2]
                    self.assertEqual(raster_verre[87], 3)
                    self.assertEqual(raster_verre[92:100], bytes([0x11] * 8))
                    b = intermediaire
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
            # Reconstruire la précédente version à secteurs ajoutés puis migrer.
            supplement, pointeurs = secteurs(src, (src / "gta3.dir").read_bytes())
            with (modeles / "gta3.img").open("ab") as image:
                image.write(supplement)
            ancien = bytearray((modeles / "gta3.dir").read_bytes())
            for i, valeurs in pointeurs.items():
                pack_into("<II", ancien, i*textures.ENTRY.size, *valeurs)
            (modeles / "gta3.dir").write_bytes(ancien)
            somme_img = textures.digest(modeles / "gta3.img").hexdigest()
            self.assertEqual(installer_facades.HISTORIQUE[somme_img], sha256(ancien).hexdigest())
            self.assertEqual(install(True), actif)
            self.assertEqual(installer_facades.etat(modeles), installer_facades.VILLE)
            self.assertFalse((modeles / installer_facades.TRANSACTION).exists())
            self.assertEqual(textures.digest(src/"gta3.img").hexdigest(), textures.RETAIL["gta3.img"])


if __name__ == "__main__":
    unittest.main()
