"""Stockage local des identifiants de session et du fil visible.

Limité à ce projet : seules les sessions et les messages créés depuis
l'atelier sont conservés ici (atelier/donnees/atelier.json). Aucun historique
privé des CLI n'est lu ni importé.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

LIMITE_MESSAGES = 400
VERSION_FORMAT = 1


class Stockage:
    def __init__(self, chemin: Path):
        self.chemin = Path(chemin)
        self.donnees: dict = {"version": VERSION_FORMAT, "agents": {}}

    def charger(self) -> None:
        try:
            brut = json.loads(self.chemin.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if (
            isinstance(brut, dict)
            and brut.get("version") == VERSION_FORMAT
            and isinstance(brut.get("agents"), dict)
        ):
            self.donnees = brut

    def _agent(self, cle: str) -> dict:
        return self.donnees["agents"].setdefault(cle, {"session": None, "messages": []})

    def session(self, cle: str) -> str | None:
        sid = self._agent(cle).get("session")
        return sid if isinstance(sid, str) and sid else None

    def fixer_session(self, cle: str, sid: str | None) -> None:
        if sid:
            self._agent(cle)["session"] = sid

    def oublier_session(self, cle: str) -> None:
        self._agent(cle)["session"] = None

    def messages(self, cle: str) -> list[dict]:
        return list(self._agent(cle).get("messages", []))

    def ajouter_message(self, cle: str, auteur: str, texte: str, nouvelle: bool = False) -> None:
        messages = self._agent(cle)["messages"]
        messages.append(
            {
                "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "auteur": auteur,
                "texte": texte,
                "nouvelle": nouvelle,
            }
        )
        del messages[:-LIMITE_MESSAGES]

    def enregistrer(self) -> None:
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            prefix="atelier-", suffix=".json", dir=str(self.chemin.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as flux:
                json.dump(self.donnees, flux, ensure_ascii=False, indent=1)
            os.replace(tmp, self.chemin)
        except OSError:
            try:
                os.unlink(tmp)
            except OSError:
                pass
