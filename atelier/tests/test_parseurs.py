#!/usr/bin/env python3
"""Tests hors-ligne : analyse des flux, classement d'erreurs, stockage, nouvelles.

    python -m unittest discover -s atelier\\tests -v
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import agents  # noqa: E402
import claude_cli  # noqa: E402
import codex_cli  # noqa: E402
import kimi_cli  # noqa: E402
from nouvelles import VeilleNouvelles  # noqa: E402
from stockage import Stockage  # noqa: E402


def ctx():
    return agents.nouveau_contexte()


class TestCodex(unittest.TestCase):
    def test_nouveau_fil(self):
        cmd = codex_cli.construire_commande("codex.exe", "Bonjour", None)
        self.assertEqual(cmd[1:3], ["exec", "--json"])
        self.assertIn("--sandbox", cmd)
        self.assertEqual(cmd[-1], "Bonjour")

    def test_reprise(self):
        cmd = codex_cli.construire_commande("codex.exe", "Suite", "abc-123")
        self.assertEqual(cmd[1:3], ["exec", "resume"])
        self.assertIn("abc-123", cmd)
        self.assertNotIn("--sandbox", cmd)

    def test_thread_started(self):
        c = ctx()
        act = codex_cli.traiter_ligne(
            json.dumps({"type": "thread.started", "thread_id": "t-1"}), c
        )
        self.assertEqual(act, [("session", "t-1")])
        self.assertEqual(c["session"], "t-1")

    def test_deltas_puis_item_complete_sans_doublon(self):
        c = ctx()
        codex_cli.traiter_ligne(json.dumps({"type": "turn.started"}), c)
        act = codex_cli.traiter_ligne(
            json.dumps({"type": "agent_message", "delta": "Bonjour "}), c
        )
        self.assertEqual(act, [("texte", "Bonjour ")])
        codex_cli.traiter_ligne(
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {"type": "agent_message", "text": "Bonjour monde"},
                }
            ),
            c,
        )
        act = codex_cli.traiter_ligne(
            json.dumps({"type": "turn.completed", "message": "Bonjour monde"}), c
        )
        self.assertEqual(act, [("fin_tour", None)])

    def test_message_complet_si_pas_de_delta(self):
        c = ctx()
        codex_cli.traiter_ligne(json.dumps({"type": "turn.started"}), c)
        codex_cli.traiter_ligne(
            json.dumps(
                {"type": "item.completed", "item": {"type": "agent_message", "text": "Salut"}}
            ),
            c,
        )
        act = codex_cli.traiter_ligne(json.dumps({"type": "turn.completed"}), c)
        self.assertIn(("texte", "Salut"), act)

    def test_erreur(self):
        c = ctx()
        act = codex_cli.traiter_ligne(
            json.dumps({"type": "error", "message": "quota exceeded"}), c
        )
        self.assertEqual(act[0][0], "erreur")


class TestClaude(unittest.TestCase):
    def test_nouveau_fil(self):
        cmd = claude_cli.construire_commande("claude.exe", "Bonjour", None)
        self.assertIn("-p", cmd)
        self.assertIn("--output-format", cmd)
        self.assertIn("stream-json", cmd)
        self.assertEqual(cmd[-1], "Bonjour")

    def test_reprise(self):
        cmd = claude_cli.construire_commande("claude.exe", "Suite", "s-9")
        self.assertIn("--resume", cmd)
        self.assertIn("s-9", cmd)

    def test_init_et_texte(self):
        c = ctx()
        act = claude_cli.traiter_ligne(
            json.dumps({"type": "system", "subtype": "init", "session_id": "s-1"}), c
        )
        self.assertEqual(act, [("session", "s-1")])
        act = claude_cli.traiter_ligne(
            json.dumps(
                {
                    "type": "assistant",
                    "message": {"content": [{"type": "text", "text": "Voici."}]},
                }
            ),
            c,
        )
        self.assertEqual(act, [("texte", "Voici.")])

    def test_pensee_et_outil_non_affiches(self):
        c = ctx()
        act = claude_cli.traiter_ligne(
            json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {"type": "thinking", "thinking": "secret"},
                            {"type": "tool_use", "name": "Bash"},
                        ]
                    },
                }
            ),
            c,
        )
        self.assertEqual(act, [("activite", "outil")])

    def test_resultat_erreur(self):
        c = ctx()
        act = claude_cli.traiter_ligne(
            json.dumps({"type": "result", "is_error": True, "result": "not logged in"}),
            c,
        )
        self.assertEqual(act[0][0], "erreur")


class TestKimi(unittest.TestCase):
    def test_nouveau_fil(self):
        cmd = kimi_cli.construire_commande("kimi.exe", "Bonjour", None)
        self.assertEqual(cmd[:3], ["kimi.exe", "-p", "Bonjour"])
        self.assertIn("stream-json", cmd)

    def test_reprise(self):
        cmd = kimi_cli.construire_commande("kimi.exe", "Suite", "k-1")
        self.assertIn("-S", cmd)
        self.assertIn("k-1", cmd)

    def test_session_et_texte(self):
        c = ctx()
        act = kimi_cli.traiter_ligne(json.dumps({"sessionId": "k-77", "type": "init"}), c)
        self.assertEqual(act, [("session", "k-77")])
        act = kimi_cli.traiter_ligne(json.dumps({"type": "text", "text": "Bonjour"}), c)
        self.assertEqual(act, [("texte", "Bonjour")])
        act = kimi_cli.traiter_ligne(
            json.dumps({"type": "delta", "delta": " !", "sessionId": "k-77"}), c
        )
        self.assertEqual(act, [("texte", " !")])

    def test_pensee_ignoree_erreur_reconnue(self):
        c = ctx()
        self.assertEqual(kimi_cli.traiter_ligne(json.dumps({"type": "thinking"}), c), [])
        act = kimi_cli.traiter_ligne(json.dumps({"type": "error", "message": "boom"}), c)
        self.assertEqual(act, [("erreur", "boom")])


class TestClasserErreur(unittest.TestCase):
    def test_connexion(self):
        etat, _ = agents.classer_erreur("Error: not logged in, please login")
        self.assertEqual(etat, agents.Etat.CONNEXION)

    def test_quota(self):
        etat, _ = agents.classer_erreur("HTTP 429: rate limit reached")
        self.assertEqual(etat, agents.Etat.QUOTA)

    def test_secret_masque(self):
        message = "invalid api key sk-ABCDEFGHIJKLMNOP used"
        etat, texte = agents.classer_erreur(message)
        self.assertEqual(etat, agents.Etat.CONNEXION)
        self.assertNotIn("sk-ABCDEFGH", texte)

    def test_generique(self):
        etat, texte = agents.classer_erreur("segmentation fault")
        self.assertEqual(etat, agents.Etat.ERREUR)
        self.assertIn("segmentation fault", texte)


class TestStockage(unittest.TestCase):
    def test_aller_retour(self):
        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "atelier.json"
            st = Stockage(chemin)
            st.fixer_session("codex", "t-1")
            st.ajouter_message("codex", "moi", "Bonjour")
            st.ajouter_message("codex", "agent", "Salut")
            st.enregistrer()
            st2 = Stockage(chemin)
            st2.charger()
            self.assertEqual(st2.session("codex"), "t-1")
            self.assertEqual(len(st2.messages("codex")), 2)
            self.assertEqual(st2.messages("codex")[0]["auteur"], "moi")

    def test_fichier_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            st = Stockage(Path(tmp) / "rien.json")
            st.charger()
            self.assertIsNone(st.session("kimi"))

    def test_limite_messages(self):
        with tempfile.TemporaryDirectory() as tmp:
            st = Stockage(Path(tmp) / "a.json")
            for i in range(450):
                st.ajouter_message("kimi", "moi", f"m{i}")
            self.assertEqual(len(st.messages("kimi")), 400)
            self.assertEqual(st.messages("kimi")[-1]["texte"], "m449")


class TestNouvelles(unittest.TestCase):
    def test_lecture_incrementale(self):
        with tempfile.TemporaryDirectory() as tmp:
            veille = VeilleNouvelles(tmp)
            fic = Path(tmp) / "nouvelles.jsonl"
            fic.write_text(
                '{"source": "codex", "titre": "Lot prêt", "texte": "Valide."}\n'
                "ligne invalide\n"
                '{"texte": "Sans source"}\n',
                encoding="utf-8",
            )
            nouvelles = veille.lire_nouveau()
            self.assertEqual(len(nouvelles), 2)
            self.assertEqual(nouvelles[0]["source"], "codex")
            self.assertEqual(nouvelles[1]["source"], "")
            self.assertEqual(veille.lire_nouveau(), [])
            with fic.open("a", encoding="utf-8") as flux:
                flux.write('{"source": "kimi", "texte": "Encore"}\n')
            nouvelles = veille.lire_nouveau()
            self.assertEqual(len(nouvelles), 1)
            self.assertEqual(nouvelles[0]["source"], "kimi")


if __name__ == "__main__":
    unittest.main()
