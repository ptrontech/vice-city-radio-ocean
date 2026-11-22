"""Cas de reprise des profils Windows, avec des blocs de test synthétiques."""
from pathlib import Path
import os
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"outils"))
import demarrage


def ecrire_slot(path, motif, date):
    corps=struct.pack("<I",42000)+bytes([motif])*71000
    path.write_bytes(corps+struct.pack("<I",sum(corps)&0xFFFFFFFF))
    os.utime(path,(date,date))


class Reprise(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        base=Path(tmp.name);self.perso=base/"source";self.perso.mkdir()
        self.profil=base/"campagne";self.profil.mkdir()
        p=patch.object(demarrage,"documents_originaux",return_value=self.perso);p.start();self.addCleanup(p.stop)
    def test_import_absent_choisit_le_plus_recent_et_preserve_la_source(self):
        ecrire_slot(self.perso/"GTAVCsf2.b",5,1700000005)
        ecrire_slot(self.perso/"GTAVCsf5.b",6,1700000010)
        self.assertEqual(demarrage.reprise("Campagne",self.profil,True),5)
        self.assertEqual((self.profil/"GTAVCsf2.b").read_bytes(),(self.perso/"GTAVCsf2.b").read_bytes())
        ecrire_slot(self.perso/"GTAVCsf2.b",9,1700000020)
        self.assertEqual(demarrage.reprise("Campagne",self.profil,True),5)
        self.assertNotEqual((self.profil/"GTAVCsf2.b").read_bytes(),(self.perso/"GTAVCsf2.b").read_bytes())
    def test_libre_independant_et_reprise_sans_videos(self):
        ecrire_slot(self.perso/"GTAVCsf1.b",3,1700000000)
        self.assertEqual(demarrage.reprise("Libre",self.profil,True),9)
        self.assertFalse(any(self.profil.iterdir()))
        ecrire_slot(self.profil/"GTAVCsf7.b",4,1700000010)
        self.assertEqual(demarrage.reprise("Libre",self.profil,True),7)
    def test_fichier_invalide_reste_disponible_dans_le_menu(self):
        p=self.profil/"GTAVCsf3.b";p.write_bytes(b"incomplet")
        ecrire_slot(self.perso/"GTAVCsf2.b",2,1700000000)
        self.assertEqual(demarrage.reprise("Campagne",self.profil,True),-1)
        self.assertEqual(p.read_bytes(),b"incomplet")
        self.assertFalse((self.profil/"GTAVCsf2.b").exists())
        ecrire_slot(self.profil/"GTAVCsf1.b",7,1700000010)
        self.assertEqual(demarrage.reprise("Campagne",self.profil,True),1)
    def test_sans_importation_en_mode_classique_ou_de_validation(self):
        ecrire_slot(self.perso/"GTAVCsf1.b",3,1700000000)
        self.assertEqual(demarrage.reprise("Campagne",self.profil,False),-1)
        self.assertEqual(demarrage.reprise("Validation",self.profil,True),9)
        self.assertEqual(demarrage.reprise("Libre",self.profil,False),9)
        self.assertEqual(demarrage.reprise("Campagne",self.profil,True,4),4)
        self.assertFalse(any(self.profil.iterdir()))
        with self.assertRaises(ValueError):
            demarrage.reprise("Campagne",self.profil,True,11)

    def test_seul_un_arret_anormal_avant_moteur_est_repris(self):
        log=self.profil/"cleo_redux.log"
        self.assertTrue(demarrage.echec_avant_moteur(0xC0000005,False,log,None))
        self.assertFalse(demarrage.echec_avant_moteur(0,False,log,None))
        self.assertFalse(demarrage.echec_avant_moteur(0xC000041D,True,log,None))
        log.write_text('New event received: "init runtime"\n',encoding="utf-8")
        self.assertFalse(demarrage.echec_avant_moteur(0xC0000005,False,log,None))
        # Un ancien journal laissé par une autre session ne constitue pas un nouveau démarrage.
        self.assertTrue(demarrage.echec_avant_moteur(0xC000041D,False,log,demarrage.signature_log(log)))

    def test_ecran_noir_limite_aux_films_de_la_session_en_cours(self):
        log = self.profil / "cleo_redux.log"
        self.assertFalse(demarrage.avant_runtime(log, None))
        log.write_text("Started scanning the CLEO directory for boot scripts at E:/Jeu/CLEO", encoding="utf-8")
        self.assertTrue(demarrage.avant_runtime(log, None))
        self.assertFalse(demarrage.avant_runtime(log, demarrage.signature_log(log)))
        with log.open("a", encoding="utf-8") as f:
            f.write('\nNew event received: "init runtime"')
        self.assertFalse(demarrage.avant_runtime(log, None))
        log.write_text('Started scanning the CLEO directory for boot scripts at E:/Jeu/CLEO\nNew event received: "host shut down"', encoding="utf-8")
        self.assertFalse(demarrage.avant_runtime(log, None))

    def test_compatibilite_locale_au_processus(self):
        parent = {"GARDE": "oui"}
        enfant = demarrage.environnement_jeu(parent)
        self.assertEqual(parent, {"GARDE": "oui"})
        self.assertEqual(enfant["__COMPAT_LAYER"], "DWM8And16BitMitigation HIGHDPIAWARE")
        self.assertEqual(demarrage.environnement_jeu(enfant), enfant)
        custom = demarrage.environnement_jeu({"__COMPAT_LAYER": "DPIUNAWARE"})
        self.assertEqual(custom["__COMPAT_LAYER"], "DPIUNAWARE DWM8And16BitMitigation")


if __name__=="__main__":unittest.main()
