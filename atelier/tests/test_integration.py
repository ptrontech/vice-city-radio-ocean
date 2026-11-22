from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import agents
import kimi_cli
from nouvelles import VeilleNouvelles
from tache import TacheProcessus


class Integration(unittest.TestCase):
    def test_statuts_locaux_et_lignes_incompletes(self):
        with TemporaryDirectory() as dossier:
            rep = Path(dossier)
            schema = {"time":"2026-10-05T12:10:00+02:00","author":"Claude","kind":"livraison","text":"Façades prêtes."}
            chemin = rep / "facades-evenements.jsonl"
            ligne = json.dumps(schema,ensure_ascii=False).encode()
            chemin.write_bytes(ligne[:-2])
            lecteur = VeilleNouvelles(dossier)
            self.assertEqual(lecteur.lire_nouveau(),[])
            with chemin.open("ab") as fichier:
                fichier.write(ligne[-2:]+b"\n")
                fichier.write(json.dumps(dict(schema,author="Outil",kind="résultat")).encode()+b"\n")
            nouvelles = lecteur.lire_nouveau()
            self.assertEqual([(n["source"],n["texte"]) for n in nouvelles],[("claude","Façades prêtes.")])
            self.assertEqual(lecteur.lire_nouveau(),[])
            chemin.write_bytes(ligne+b"\n")
            self.assertEqual(lecteur.lire_nouveau(),[])

    def test_kimi_affiche_une_reponse_visible(self):
        ctx = agents.nouveau_contexte()
        items = [{"type":"thinking","thinking":"privé"},{"type":"text","text":"Reçu."}]
        msg = {"role":"assistant","content":items}
        self.assertEqual(kimi_cli.traiter_ligne(json.dumps(msg),ctx),[("texte","Reçu.")])
        for role in ("tool","user"):
            self.assertEqual(kimi_cli.traiter_ligne(json.dumps(dict(msg,role=role)),ctx),[])

    def test_client_absent_et_lanceur_sans_interpreteur_de_commandes(self):
        absent = agents.AgentInfo("kimi","Kimi","#000")
        agents.sonder_version(absent)
        self.assertEqual(absent.etat,agents.Etat.ABSENT)
        with TemporaryDirectory() as dossier:
            with self.assertRaisesRegex(OSError,"binaire natif"):
                TacheProcessus(["inexistant.cmd","simple message"],Path(dossier)).demarrer()
            if os.name == "nt":
                sh = Path(dossier)/"claude.cmd"
                sh.touch()
                self.assertIsNone(agents._cible_native(sh,"claude"))
                native = sh.parent/"node_modules/@anthropic-ai/claude-code/bin/claude.exe"
                native.parent.mkdir(parents=True)
                native.touch()
                self.assertEqual(agents._cible_native(sh,"claude"),native)
