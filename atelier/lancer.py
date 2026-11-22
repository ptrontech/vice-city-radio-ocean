#!/usr/bin/env python3
"""Lancement de l'atelier « GTA Vice City, amélioration ».

    python atelier\\lancer.py
    python atelier\\lancer.py --notifications E:\\ViceCityAtelier\\Nouvelles

Option --selftest : construit la fenêtre sans l'afficher, puis quitte.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass


def principale(argv=None) -> int:
    analyseur = argparse.ArgumentParser(
        prog="lancer.py",
        description="Atelier de collaboration « GTA Vice City, amélioration »",
    )
    analyseur.add_argument(
        "--notifications",
        metavar="DOSSIER",
        default=None,
        help="dossier surveillé contenant nouvelles.jsonl (nouvelles des autres chantiers)",
    )
    analyseur.add_argument(
        "--selftest",
        action="store_true",
        help="construit la fenêtre sans l'afficher, puis quitte",
    )
    args = analyseur.parse_args(argv)

    import fenetre
    from instance_windows import FenetreUnique

    instance = None if args.selftest else FenetreUnique()
    if instance and instance.deja_ouverte:
        return 0
    application = fenetre.Application(dossier_nouvelles=args.notifications)
    if instance:
        instance.suivre(application)
    if args.selftest:
        application.withdraw()
        application.update_idletasks()
        application.fermer()
        print("auto-test OK : la fenêtre s'est construite sans erreur.")
        return 0
    application.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(principale())
