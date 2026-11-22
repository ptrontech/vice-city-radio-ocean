"""Tests synthétiques de la façade de l'hôtel. Lancer : python tests/facades.py

Toutes les textures sont fabriquées ici par formules et générateur congruentiel : aucune
donnée du jeu. Le béton synthétique est encodé avec l'encodeur BC1 du module.
"""
import contextlib
import importlib.util
import io
import json
import math
from pathlib import Path
import re
import tempfile
import unittest
import unittest.mock
from struct import pack

_CHEMIN = Path(__file__).resolve().parents[1] / "outils" / "facades.py"
_SPEC = importlib.util.spec_from_file_location("facades_outil", _CHEMIN)
facades = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(facades)
textures = facades.textures

VER = 0x1803FFFF
FILTRE = 0x1106          # échantillonneur inventé : doit survivre tel quel


def lcg(graine):
    etat = graine
    while True:
        etat = (etat * 1103515245 + 12345) & 0x7FFFFFFF
        yield etat / 0x7FFFFFFF


def plans_beton(plat=False, graine=7, n=128):
    """Matériau inventé n×n, périodique : variation douce, joints de panneau, grain."""
    hasard = lcg(graine)
    R, G, B = [], [], []
    for y in range(n):
        for x in range(n):
            lum = 0.0 if plat else (12 * math.sin(2 * math.pi * x / n) * math.cos(4 * math.pi * y / n)
                                    + (next(hasard) - .5) * 16)
            joint = -45 if (not plat and (x < 2 or y < 2)) else 0
            R.append(150 + lum + joint)
            G.append(145 + lum + joint)
            B.append(138 + lum + joint)
    return R, G, B


def raster(nom, cote, niveaux, alpha=0, fmt=0x0200, nom_masque=b"masque"):
    en_tete = pack("<IIHHBBBB", fmt, alpha, cote, cote, 16, len(niveaux), 4, 1)
    corps = b"".join(pack("<I", len(n)) + n for n in niveaux)
    return (pack("<II", 8, FILTRE) + nom.encode().ljust(32, b"\0") + nom_masque.ljust(32, b"\0")
            + en_tete + corps)


def native(donnees):
    return textures.wrap(0x15, VER, textures.wrap(1, VER, donnees) + textures.wrap(3, VER, b""))


def txd(beton=None, decoration=True, nom_beton="Bow_Abattoir_Conc2", padding=True, cote=128, extras=()):
    beton = beton if beton is not None else raster(
        nom_beton, cote, [facades.encoder_bc1(plans_beton(n=cote), cote, cote)])
    parts = [native(beton)]
    if decoration:
        hasard = lcg(99)
        octets = bytes(int(next(hasard) * 256) for _ in range(2048))
        parts.append(native(raster("clevelanderdetails", 64, [octets], fmt=0x0300)))
    for nom, graine in extras:                                   # autres textures du dictionnaire
        hasard = lcg(graine)
        parts.append(native(raster(nom, 32, [bytes(int(next(hasard) * 256) for _ in range(512))], fmt=0x0300)))
    corps = textures.wrap(1, VER, pack("<HH", len(parts), 9)) + b"".join(parts) + textures.wrap(3, VER, b"")
    blob = textures.wrap(0x16, VER, corps)
    return blob + (bytes(2048 - len(blob) % 2048) if padding else b"")


def charger(blob):
    version, parts = textures.dictionary(blob)
    return {t[3]: t for t in textures.natives(parts)}, parts


class Facades(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.avant = txd()
        cls.apres = facades.ameliorer_txd("HTL_EXT03.TXD", cls.avant)
        cls.mesures = facades.verifier(cls.avant, cls.apres)

    def test_interface_et_structure(self):
        self.assertIn("htl_ext03.txd", facades.TXD_CIBLES)
        a, pa = charger(self.avant)
        b, pb = charger(self.apres)
        self.assertEqual(list(a), list(b))                       # noms et ordre
        self.assertEqual(list(b), ["bow_abattoir_conc2", "clevelanderdetails"])
        self.assertEqual(a["clevelanderdetails"][4], b["clevelanderdetails"][4])   # identique à l'octet
        self.assertEqual(pa[0], pb[0])                           # chunk de structure du dictionnaire
        self.assertEqual(a["bow_abattoir_conc2"][4][:72], b["bow_abattoir_conc2"][4][:72])  # nom, masque, sampler
        self.assertEqual(int.from_bytes(b["bow_abattoir_conc2"][4][4:8], "little"), FILTRE)

    def test_alpha_dimensions_et_mipmaps(self):
        r = facades.lire_raster(charger(self.apres)[0]["bow_abattoir_conc2"][4])
        self.assertEqual((r["w"], r["h"], r["alpha"], r["niveaux"]), (256, 256, 0, 9))
        self.assertTrue(r["fmt"] & 0x8000 and not r["fmt"] & 0x4000)
        tailles = [(max(1, 256 >> k) + 3) // 4 for k in range(9)]
        self.assertEqual([len(m) for m in r["mips"]], [t * t * 8 for t in tailles])
        self.assertEqual(256 >> 8, 1)                            # dernier niveau 1×1
        for k, m in enumerate(r["mips"]):                        # aucun bloc transparent : décodage réussi
            facades.decoder_bc1(m, max(1, 256 >> k), max(1, 256 >> k))

    def test_lumiere_teinte_et_melange_des_niveaux(self):
        source = facades.decoder_materiau(self.avant)[0][1]
        niveaux = facades.decoder_materiau(self.apres)
        self.assertEqual([c for c, _ in niveaux], [256 >> k for k in range(9)])
        moy = lambda p: sum(p) / len(p)
        for s, t in zip(source, niveaux[0][1]):                  # niveau 256 : moyennes RGB conservées
            self.assertLess(abs(moy(s) - moy(t)), 1.5)
        self.assertLess(self.mesures["ecart_lumiere_max"], facades.TOLERANCE_LUMIERE)
        self.assertLess(self.mesures["decalage_teinte_max"], facades.TOLERANCE_TEINTE)
        self.assertLess(self.mesures["ecart_mipmaps_max"], facades.TOLERANCE_MIPMAPS)

    def test_niveau_d_origine_copie_bit_pour_bit(self):
        a = facades.lire_raster(charger(self.avant)[0]["bow_abattoir_conc2"][4])
        b = facades.lire_raster(charger(self.apres)[0]["bow_abattoir_conc2"][4])
        self.assertEqual(b["mips"][1], a["mips"][0])
        self.assertNotEqual(b["mips"][0], a["mips"][0])
        self.assertTrue(self.mesures["niveau_origine_identique"])
        self.assertEqual((self.mesures["cote_source"], self.mesures["cote"], self.mesures["mipmaps"]), (128, 256, 9))
        self.assertIs(self.mesures["empreinte_origine"], False)   # béton synthétique
        with self.assertRaisesRegex(ValueError, "empreinte"):
            facades.ameliorer_txd("htl_ext03.txd", self.avant, exiger_empreinte=True)

    def test_amelioration_reelle_et_non_simple_interpolation(self):
        R, G, B = facades.decoder_bc1(charger(self.avant)[0]["bow_abattoir_conc2"][4][92:92 + 8192], 128, 128)
        plans, stats = facades.ameliorer_pixels(R, G, B)
        self.assertTrue(.15 <= stats["rms_grain"] <= facades.RMS_MAX + .01, stats)   # faible amplitude
        self.assertLessEqual(stats["crete"], facades.CRETE_MAX + 1e-9)
        simple = [facades.agrandir([float(v) for v in c], 128) for c in (R, G, B)]
        ecart = math.sqrt(sum((a - b) ** 2 for p, q in zip(plans, simple) for a, b in zip(p, q)) / (3 * 256 * 256))
        self.assertGreater(ecart, .15)
        self.assertLess(ecart, 3.2)
        niveau0 = charger(self.apres)[0]["bow_abattoir_conc2"][4][92:92 + 32768]
        self.assertNotEqual(niveau0, facades.encoder_bc1(simple, 256, 256))      # pas l'interpolation seule
        # Le grain s'ajoute à l'identique sur R, V, B : pas de dérive de teinte.
        d = [[a - b for a, b in zip(p, q)] for p, q in zip(plans, simple)]
        for k in (1, 2):
            self.assertLess(max(abs(x - y) for x, y in zip(d[0], d[k])), 1e-9)

    def test_grain_moyenne_nulle_bords_et_torique(self):
        # Source à deux bandes (bords verticaux en x = 0 et x = 64) avec grain partout.
        hasard = lcg(3)
        L = [(170 if (x % 128) < 64 else 90) + (next(hasard) - .5) * 16 for y in range(128) for x in range(128)]
        grain, stats = facades.calculer_grain(L, L, L)
        m = 256
        for y in range(0, 128, 9):                               # moyenne nulle par bloc 2×2
            for x in range(0, 128, 7):
                i = 2 * y * m + 2 * x
                self.assertAlmostEqual(grain[i] + grain[i + 1] + grain[i + m] + grain[i + m + 1], 0, places=9)
        proche = [abs(grain[y * m + x]) for y in range(m) for x in (126, 127, 128, 129)]
        loin = [abs(grain[y * m + x]) for y in range(m) for x in range(40, 80)]
        self.assertLess(sum(proche) / len(proche), .6 * sum(loin) / len(loin))   # bords du matériau épargnés
        # Échantillonnage torique : agrandir(décalage) == décalage(agrandir) de 2 pixels, exactement.
        c = [float((x * 7 + y * 13) % 31) + (x == 5) * 40 for y in range(16) for x in range(16)]
        decale = [c[y * 16 + (x - 1) % 16] for y in range(16) for x in range(16)]
        g1, g2 = facades.agrandir(c, 16), facades.agrandir(decale, 16)
        for y in range(32):
            for x in range(32):
                self.assertAlmostEqual(g2[y * 32 + x], g1[y * 32 + (x - 2) % 32], places=9)
        self.assertLessEqual(self.mesures["couture_apres"], self.mesures["couture_avant"] * 1.25 + .15)

    def test_codec_bc1(self):
        plan = [float(x * 8 + y * 2) for y in range(16) for x in range(16)]
        decode = facades.decoder_bc1(facades.encoder_bc1((plan, plan, plan), 16, 16), 16, 16)
        self.assertLess(sum(abs(a - b) for a, b in zip(plan, decode[0])) / 256, 5.0)   # 565 : pas de ~4 niveaux
        constant = facades.decoder_bc1(facades.encoder_bc1(([100.0] * 16,) * 3, 4, 4), 4, 4)
        self.assertLess(max(abs(v - 100) for v in constant[0]), 3)
        transparent = pack("<HHI", 0x0000, 0xFFFF, 0xFFFFFFFF)   # mode 3 couleurs, indice 3
        with self.assertRaisesRegex(ValueError, "transparent"):
            facades.decoder_bc1(transparent, 4, 4)

    def test_determinisme(self):
        self.assertEqual(facades.ameliorer_txd("htl_ext03.txd", self.avant), self.apres)
        self.assertEqual(facades.ameliorer_txd("models/htl_ext03.txd", bytearray(self.avant)), self.apres)

    def test_refus_explicites(self):
        with self.assertRaisesRegex(ValueError, "n'est pas une cible"):
            facades.ameliorer_txd("generic.txd", self.avant)
        with self.assertRaisesRegex(ValueError, "0 occurrence"):
            facades.ameliorer_txd("htl_ext03.txd", txd(nom_beton="autre_beton"))
        with self.assertRaisesRegex(ValueError, "déjà amélioré"):
            facades.ameliorer_txd("htl_ext03.txd", self.apres)
        deux_niveaux = raster("bow_abattoir_conc2", 128, [bytes(8192), bytes(2048)])
        with self.assertRaisesRegex(ValueError, "2 niveau"):
            facades.ameliorer_txd("htl_ext03.txd", txd(deux_niveaux))
        avec_alpha = raster("bow_abattoir_conc2", 128, [bytes(8192)], alpha=1)
        with self.assertRaisesRegex(ValueError, "BC1 opaque"):
            facades.ameliorer_txd("htl_ext03.txd", txd(avec_alpha))
        lisse = raster("bow_abattoir_conc2", 128, [facades.encoder_bc1(plans_beton(plat=True), 128, 128)])
        with self.assertRaisesRegex(ValueError, "trop lisse"):
            facades.ameliorer_txd("htl_ext03.txd", txd(lisse))
        transparent = raster("bow_abattoir_conc2", 128, [pack("<HHI", 0, 0xFFFF, 0xFFFFFFFF) * 1024])
        with self.assertRaisesRegex(ValueError, "transparent"):
            facades.ameliorer_txd("htl_ext03.txd", txd(transparent))
        with self.assertRaises(ValueError):
            facades.ameliorer_txd("htl_ext03.txd", self.avant[:3000])

    def test_verifier_detecte_les_alterations(self):
        def altere(nom, delta):
            octets = bytearray(self.apres)
            octets[self.apres.index(nom) + delta] ^= 0xFF
            return bytes(octets)
        # Le nom commence à l'octet 8 du raster : +90 -> un octet de pixels du décor, -4 -> sampler.
        with self.assertRaisesRegex(ValueError, "a changé"):
            facades.verifier(self.avant, altere(b"clevelanderdetails", 32 + 32 + 16 + 10))
        with self.assertRaisesRegex(ValueError, "échantillonneur"):
            facades.verifier(self.avant, altere(b"Bow_Abattoir_Conc2", -4))
        with self.assertRaisesRegex(ValueError, "Noms"):
            facades.verifier(self.avant, self.apres.replace(b"clevelanderdetails", b"clevelanderdetailz"))

    def test_comparatif_et_ligne_de_commande(self):
        with tempfile.TemporaryDirectory() as dossier:
            d = Path(dossier)
            (d / "avant.txd").write_bytes(self.avant)
            (d / "apres.txd").write_bytes(self.apres)
            sortie = io.StringIO()
            with contextlib.redirect_stdout(sortie):
                code = facades.main([str(d / "avant.txd"), str(d / "apres.txd"), str(d / "cmp.ppm")])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(sortie.getvalue())["mipmaps"], 9)
            image = (d / "cmp.ppm").read_bytes()
            self.assertEqual(len(image), len(b"P6\n512 256\n255\n") + 512 * 256 * 3)
            erreur = io.StringIO()
            with contextlib.redirect_stderr(erreur):
                self.assertEqual(facades.main([str(d / "absent.txd"), str(d / "apres.txd")]), 2)
                self.assertEqual(facades.main([str(d / "avant.txd"), str(d / "avant.txd")]), 2)
                self.assertEqual(facades.main([]), 2)
            self.assertIn("Usage", erreur.getvalue())

    def test_source_sans_octets_de_pixels(self):
        source = _CHEMIN.read_text(encoding="utf-8")
        self.assertNotRegex(source, r"(\\x[0-9a-fA-F]{2}){6}")
        self.assertNotRegex(source, r"\bb[\"'][^\"']{24,}[\"']")


AUTRES = (("od_autre_mur", 5), ("od_enseigne", 6))


class FacadeCrepi(unittest.TestCase):
    """Seconde cible : od_hotels1.txd, matériau hotelpeach 64 -> 128, huit niveaux."""

    @classmethod
    def setUpClass(cls):
        cls.avant = txd(nom_beton="hotelpeach", cote=64, extras=AUTRES)
        cls.apres = facades.ameliorer_txd("OD_HOTELS1.TXD", cls.avant)
        cls.mesures = facades.verifier(cls.avant, cls.apres, "hotelpeach")

    def test_cibles_et_dimensions(self):
        self.assertEqual(facades.TXD_CIBLES, ("htl_ext03.txd", "od_hotels1.txd"))
        self.assertEqual(facades.MATERIAUX["od_hotels1.txd"], "hotelpeach")
        r = facades.lire_raster(charger(self.apres)[0]["hotelpeach"][4])
        self.assertEqual((r["w"], r["h"], r["alpha"], r["niveaux"]), (128, 128, 0, 8))
        tailles = [(max(1, 128 >> k) + 3) // 4 for k in range(8)]
        self.assertEqual([len(m) for m in r["mips"]], [t * t * 8 for t in tailles])
        self.assertEqual(128 >> 7, 1)                            # huitième niveau : 1×1
        self.assertEqual((self.mesures["cote_source"], self.mesures["cote"], self.mesures["mipmaps"]), (64, 128, 8))

    def test_niveau_64_identique_et_autres_textures_conservees(self):
        a, pa = charger(self.avant)
        b, pb = charger(self.apres)
        self.assertEqual(list(a), list(b))
        for nom in ("clevelanderdetails", "od_autre_mur", "od_enseigne"):
            self.assertEqual(a[nom][4], b[nom][4], nom)          # identiques à l'octet
        self.assertEqual(a["hotelpeach"][4][:72], b["hotelpeach"][4][:72])   # nom, masque, sampler
        self.assertEqual([p for i, p in enumerate(pa) if i != a["hotelpeach"][0]],
                         [p for i, p in enumerate(pb) if i != b["hotelpeach"][0]])
        ra, rb = (facades.lire_raster(t["hotelpeach"][4]) for t in (a, b))
        self.assertEqual(rb["mips"][1], ra["mips"][0])           # palette exacte au niveau d'origine
        self.assertLess(self.mesures["ecart_lumiere_max"], facades.TOLERANCE_LUMIERE)
        self.assertLess(self.mesures["decalage_teinte_max"], facades.TOLERANCE_TEINTE)
        self.assertLess(self.mesures["couture_apres"], self.mesures["couture_avant"] * 1.25 + .15)

    def test_grain_borne_et_determinisme(self):
        R, G, B = facades.decoder_materiau(self.avant, "hotelpeach")[0][1]
        plans, stats = facades.ameliorer_pixels(R, G, B, n=64)
        self.assertEqual(len(plans[0]), 128 * 128)
        self.assertTrue(.15 <= stats["rms_grain"] <= facades.RMS_MAX + .01, stats)
        self.assertEqual(facades.ameliorer_txd("od_hotels1.txd", self.avant), self.apres)

    def test_empreinte_de_l_original(self):
        self.assertIs(self.mesures["empreinte_origine"], False)  # données synthétiques : autre empreinte
        with self.assertRaisesRegex(ValueError, "empreinte"):
            facades.ameliorer_txd("od_hotels1.txd", self.avant, exiger_empreinte=True)
        brut = charger(self.avant)[0]["hotelpeach"][4]
        import hashlib
        reference = {"hotelpeach": hashlib.sha256(brut[88:]).hexdigest()}
        with unittest.mock.patch.dict(facades.ORIGINE_SHA256, reference):
            self.assertEqual(facades.ameliorer_txd("od_hotels1.txd", self.avant, exiger_empreinte=True), self.apres)
            self.assertIs(facades.verifier(self.avant, self.apres, "hotelpeach")["empreinte_origine"], True)

    def test_refus_de_taille_ou_de_cible(self):
        with self.assertRaisesRegex(ValueError, "attendu en 64×64"):
            facades.ameliorer_txd("od_hotels1.txd", txd(nom_beton="hotelpeach", cote=128))
        with self.assertRaisesRegex(ValueError, "déjà amélioré"):
            facades.ameliorer_txd("od_hotels1.txd", self.apres)
        with self.assertRaisesRegex(ValueError, "0 occurrence"):
            facades.ameliorer_txd("od_hotels1.txd", txd())       # TXD du béton donné à la cible crépi
        with self.assertRaisesRegex(ValueError, "0 occurrence"):
            facades.ameliorer_txd("htl_ext03.txd", self.avant)   # et inversement
        with self.assertRaisesRegex(ValueError, "Matériau inconnu"):
            facades.verifier(self.avant, self.apres, "autre")
        # Un résultat de crépi vérifié comme béton est rejeté, pas toléré.
        with self.assertRaises(ValueError):
            facades.verifier(self.avant, self.apres, facades.MATERIAU_BETON)

    def test_verifier_detecte_un_niveau_modifie_ou_un_autre_materiau_touche(self):
        octets = bytearray(self.apres)
        debut = self.apres.index(b"hotelpeach") + 32 + 32 + 16 + 4 + 8192 + 4  # premier octet du niveau 1
        octets[debut] ^= 0x01
        with self.assertRaisesRegex(ValueError, "octet pour octet"):
            facades.verifier(self.avant, bytes(octets), "hotelpeach")
        autre = bytearray(self.apres)
        autre[self.apres.index(b"od_enseigne") + 32 + 32 + 16 + 10] ^= 0xFF
        with self.assertRaisesRegex(ValueError, "a changé"):
            facades.verifier(self.avant, bytes(autre), "hotelpeach")

    def test_comparatif_ppm_coherent_avec_le_beton_par_defaut(self):
        with tempfile.TemporaryDirectory() as dossier:
            d = Path(dossier)
            (d / "avant.txd").write_bytes(self.avant)
            (d / "apres.txd").write_bytes(self.apres)
            sortie = io.StringIO()
            with contextlib.redirect_stdout(sortie):
                code = facades.main([str(d / "avant.txd"), str(d / "apres.txd"), str(d / "c.ppm"),
                                     "--materiau", "hotelpeach"])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(sortie.getvalue())["cote"], 128)
            self.assertEqual((d / "c.ppm").read_bytes()[:15], b"P6\n256 128\n255\n")
            self.assertEqual(len((d / "c.ppm").read_bytes()), len(b"P6\n256 128\n255\n") + 256 * 128 * 3)
            erreur = io.StringIO()
            with contextlib.redirect_stderr(erreur):              # sans --materiau : béton par défaut -> refus
                self.assertEqual(facades.main([str(d / "avant.txd"), str(d / "apres.txd")]), 2)
                self.assertEqual(facades.main([str(d / "avant.txd"), str(d / "apres.txd"), "--materiau"]), 2)
            self.assertIn("Usage", erreur.getvalue())


if __name__ == "__main__":
    unittest.main()
