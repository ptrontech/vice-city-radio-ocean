# Atelier des IA – Vice City

Cette fenêtre Windows réunit Codex, Claude et Kimi pour le projet Radio Océan. Ouvrir le raccourci **Atelier des IA – Vice City** sur le Bureau. Un deuxième double-clic rappelle la même fenêtre.

## Écrire à un agent

Dans **Moi**, cocher un ou plusieurs destinataires, saisir le message et cliquer sur **Envoyer**. **Tous** sélectionne les trois. Entrée envoie le texte et Maj + Entrée passe à la ligne.

Chaque panneau possède deux onglets. **Discussion** affiche les échanges lancés dans l’atelier. **Journal GTA** affiche les nouvelles réelles du chantier de l’agent. Les nouvelles restent sur le PC. **Nouveau fil** commence une autre discussion avec le destinataire choisi. Les échanges précédents restent lisibles dans l’historique.

**CLI disponible** indique que le programme répond à la vérification de version. **Réponse reçue** apparaît après réception d’un texte. Les erreurs de connexion, de quota et de client absent s’affichent sur le panneau concerné.

## Exécuter depuis les sources

Python 3 avec Tkinter est requis. Les clients officiels Codex, Claude et Kimi utilisent leurs connexions locales existantes.

```powershell
python atelier/lancer.py
& ./atelier/raccourci.ps1
```

Les identifiants des trois fils et les messages sont conservés dans `%LOCALAPPDATA%\RadioOcean\AtelierIA\atelier.json`. Chaque client travaille dans son propre sous-dossier de conversations. La variable `ATELIER_IA_DONNEES` permet de lancer une recette avec un historique isolé.

## Actualité du projet

L’atelier repère le dossier local `RevueClaude` dans son arborescence. Pour en choisir un autre, utiliser le bouton **Dossier des nouvelles…**, `--notifications CHEMIN` ou la variable `ATELIER_JOURNAUX`.

| Panneau | Journal |
| --- | --- |
| Codex | `codex-evenements.jsonl` |
| Claude | `facades-evenements.jsonl` |
| Kimi | `kimi-atelier-activite.jsonl` |

Chaque événement se termine par un saut de ligne et utilise les champs `time` (date ISO), `author`, `kind` et `text`. Le lecteur accepte aussi le format `source`, `titre`, `texte`, `horodatage` dans `nouvelles.jsonl`. Chaque panneau affiche les nouvelles de son auteur. Les résultats bruts des outils sont écartés.

## Vérifier

```powershell
python -m unittest discover -s atelier/tests -v
python atelier/verifier.py
python atelier/lancer.py --selftest
```

Kimi Code a écrit l’interface Tk, les trois connecteurs et le stockage initial. Codex a raccordé les journaux GTA et les exécutables Windows, ajouté le raccourci, l’instance unique et testé les reprises de fil avec les fournisseurs.
