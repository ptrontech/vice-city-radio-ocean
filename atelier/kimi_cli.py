"""Messages visibles de Kimi Code et reprise des fils privés du seul atelier."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess


def construire_commande(exe: str, message: str, reprise: str | None) -> list[str]:
    commande = [exe]
    if reprise:
        commande += ["-S", reprise]
    commande += (["--prompt=" + message] if message.startswith("-") else ["-p",message])
    return commande + ["--output-format","stream-json"]


def derniere_session(exe: str, repertoire: Path) -> str | None:
    """Kimi Code 2.7 peut omettre l'identifiant dans le flux de texte."""
    try:
        resultat = subprocess.run(
            [exe, "session", "list", "--cwd", str(repertoire), "--limit", "1", "--json"],
            cwd=repertoire, capture_output=True, timeout=12, stdin=subprocess.DEVNULL,
            creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0),
        )
        lignes = json.loads(resultat.stdout) if resultat.returncode == 0 else []
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None
    if not isinstance(lignes,list) or not lignes or not isinstance(lignes[0],dict):
        return None
    session = lignes[0].get("id")
    return session if isinstance(session,str) and session.startswith("session_") else None


def traiter_ligne(ligne: str, ctx: dict) -> list[tuple[str, object]]:
    try:
        obj = json.loads(ligne)
    except ValueError:
        return []
    if not isinstance(obj,dict):
        return []
    nature, role = str(obj.get("type","")).lower(), obj.get("role")
    if obj.get("error_message") or nature in ("error","aborted","abort","cancelled"):
        erreur = obj.get("error_message") or obj.get("message") or obj.get("error")
        return [("erreur",erreur if isinstance(erreur,str) else "Erreur de la session Kimi")]
    if "think" in nature or "reason" in nature or role in ("tool","user"):
        return []
    actions = []
    if nature.startswith("system") or nature == "init" or role == "assistant":
        sid = obj.get("session_id") or obj.get("sessionId")
        if isinstance(sid,str) and sid and sid != ctx.get("session"):
            ctx["session"] = sid
            actions.append(("session",sid))
    if nature in ("text","delta") and role in (None,"assistant"):
        texte = obj.get("text") if nature == "text" else obj.get("delta")
        if isinstance(texte,str) and texte:
            actions.append(("texte",texte))
        return actions
    if role != "assistant" and nature != "assistant":
        return actions
    contenu = obj.get("content")
    if isinstance(contenu,str) and contenu.strip():
        actions.append(("texte",contenu))
    if isinstance(contenu,list):
        for bloc in contenu:
            if isinstance(bloc,dict) and str(bloc.get("type","")).lower() in ("text","textpart","output_text"):
                texte = bloc.get("text")
                if isinstance(texte,str) and texte.strip():
                    actions.append(("texte",texte))
    return actions
