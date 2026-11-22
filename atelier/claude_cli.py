"""Connecteur Claude Code : claude -p --verbose --output-format stream-json."""
from __future__ import annotations

import json


def construire_commande(exe: str, message: str, reprise: str | None) -> list[str]:
    cmd = [exe, "-p", "--verbose", "--output-format", "stream-json"]
    if reprise:
        cmd += ["--resume", reprise]
    cmd.extend(["--", message])
    return cmd


def traiter_ligne(ligne: str, ctx: dict) -> list[tuple[str, object]]:
    ligne = ligne.strip()
    if not ligne:
        return []
    try:
        obj = json.loads(ligne)
    except ValueError:
        return []
    if not isinstance(obj, dict):
        return []
    type_evenement = obj.get("type")
    if type_evenement == "system" and obj.get("subtype") == "init":
        sid = obj.get("session_id")
        if isinstance(sid, str) and sid:
            ctx["session"] = sid
            return [("session", sid)]
        return []
    if type_evenement == "assistant":
        if obj.get("subtype") == "delta":
            delta = obj.get("delta") or {}
            if isinstance(delta, dict) and delta.get("type") == "text_delta":
                texte = delta.get("text")
                if isinstance(texte, str) and texte:
                    return [("texte", texte)]
            return []
        message = obj.get("message") or {}
        actions: list[tuple[str, object]] = []
        contenu = message.get("content") if isinstance(message, dict) else None
        for bloc in contenu or []:
            if not isinstance(bloc, dict):
                continue
            type_bloc = bloc.get("type")
            if type_bloc == "text":
                texte = bloc.get("text")
                if isinstance(texte, str) and texte:
                    actions.append(("texte", texte))
            elif type_bloc == "tool_use":
                actions.append(("activite", "outil"))
            # thinking : volontairement ignoré (pensée interne non affichée)
        return actions
    if type_evenement == "result":
        sid = obj.get("session_id")
        if isinstance(sid, str) and sid:
            ctx["session"] = sid
        if obj.get("is_error"):
            message_erreur = obj.get("result") or obj.get("errors") or "erreur Claude Code"
            return [("erreur", str(message_erreur))]
        return [("fin_tour", None)]
    return []
