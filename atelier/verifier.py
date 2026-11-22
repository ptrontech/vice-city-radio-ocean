#!/usr/bin/env python3
"""Vérifications hors-ligne de l'atelier.

    python atelier\\verifier.py

Aucun appel aux fournisseurs : on vérifie Tkinter et la présence locale
des trois CLI (chemin + --version). La présence d'un CLI ne prouve pas
l'authentification : l'état réel (connexion, quota) apparaît dans l'atelier
après le premier envoi.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass


def verifier_tkinter() -> tuple[bool, str]:
    try:
        import tkinter as tk

        racine = tk.Tk()
        racine.withdraw()
        racine.update_idletasks()
        racine.destroy()
        return True, f"Tkinter OK (Tk {tk.TkVersion})"
    except Exception as exc:  # noqa: BLE001 - rapport hors-ligne
        return False, f"Tkinter indisponible : {exc}"


def main() -> int:
    import agents

    tout_ok = True
    ok, message = verifier_tkinter()
    tout_ok &= ok
    print(("[OK] " if ok else "[ERREUR] ") + message)

    print("Présence locale des CLI (--version, sans contact réseau) :")
    agents.resoudre_executables()
    nb_presence = 0
    for cle, info in agents.AGENTS.items():
        agents.sonder_version(info, delai=15)
        if info.exe and info.etat == agents.Etat.PRET:
            nb_presence += 1
            print(f"  [OK]      {info.nom:<8} {info.exe}")
            print(f"            {info.version}")
        elif info.exe:
            print(f"  [ANOMALIE] {info.nom:<8} trouvé ({info.exe})")
            print(f"            --version a échoué : {info.detail}")
        else:
            print(f"  [ABSENT]  {info.nom:<8} exécutable introuvable")
    print(f"{nb_presence}/3 CLI présents.")
    print(
        "Note : la présence d'un CLI et une réponse réussie d'un fournisseur sont deux"
    )
    print(
        "états distincts ; la connexion, le quota ou une erreur s'affichent dans"
    )
    print("l'atelier après le premier envoi.")
    return 0 if tout_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
