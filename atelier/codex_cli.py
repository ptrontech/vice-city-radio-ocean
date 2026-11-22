"""Connecteur Codex CLI : codex exec --json, reprise via codex exec resume."""
from __future__ import annotations

import json

# Options normales de sandbox de codex exec :
# --sandbox read-only | workspace-write | danger-full-access
BAC_A_SABLE = "read-only"

_ACTIVITE_OUTIL = {
    "reasoning": "raisonnement",
    "tool_call": "outil",
    "local_shell_call": "commande",
    "command_execution": "commande",
    "file_change": "modification de fichier",
    "patch": "modification de fichier",
    "web_search": "recherche web",
    "mcp_tool_call": "outil MCP",
}


def construire_commande(exe: str, message: str, reprise: str | None) -> list[str]:
    if reprise:
        return [exe, "exec", "resume", "--json", "--skip-git-repo-check", reprise, "--", message]
    return [exe, "exec", "--json", "--sandbox", BAC_A_SABLE, "--skip-git-repo-check", "--", message]


def traiter_ligne(ligne: str, ctx: dict) -> list[tuple[str, object]]:
    ligne = ligne.strip()
    if not ligne:
        return []
    try:
        obj = json.loads(ligne)
    except ValueError:
        if "error" in ligne.lower():
            ctx["bruts"].append(ligne[:200])
        return []
    if not isinstance(obj, dict):
        return []
    type_evenement = obj.get("type")
    if type_evenement == "thread.started":
        sid = obj.get("thread_id")
        if isinstance(sid, str) and sid:
            ctx["session"] = sid
            return [("session", sid)]
        return []
    if type_evenement == "turn.started":
        ctx["texte_tour"] = 0
        ctx["candidat_final"] = ""
        return []
    if type_evenement == "agent_message":
        delta = obj.get("delta")
        if isinstance(delta, str) and delta:
            ctx["texte_tour"] = ctx.get("texte_tour", 0) + 1
            return [("texte", delta)]
        message = obj.get("message")
        if isinstance(message, str) and message:
            ctx["candidat_final"] = message
        return []
    if type_evenement == "item.completed":
        item = obj.get("item")
        if isinstance(item, dict):
            type_item = item.get("type")
            if type_item == "agent_message":
                texte = item.get("text")
                if isinstance(texte, str) and texte:
                    ctx["candidat_final"] = texte
                return []
            if type_item in _ACTIVITE_OUTIL:
                return [("activite", _ACTIVITE_OUTIL[type_item])]
        return []
    if type_evenement == "turn.completed":
        actions: list[tuple[str, object]] = []
        if ctx.get("texte_tour", 0) == 0:
            candidat = ctx.get("candidat_final", "")
            if candidat:
                actions.append(("texte", candidat))
                ctx["texte_tour"] = 1
        actions.append(("fin_tour", None))
        return actions
    if type_evenement == "error":
        return [("erreur", str(obj.get("message") or "erreur Codex"))]
    return []
