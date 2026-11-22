# Travailler sur Radio Océan

Commencer par [le guide de jeu](README.md) et [le suivi des essais](SUIVI.md). Les [tâches GitHub](https://github.com/ptrontech/vice-city-radio-ocean/issues) indiquent le chantier, les points d’intégration et l’essai attendu. Une IA avec un accès en lecture peut cloner le projet. Pour proposer du code, utiliser une branche du dépôt si son compte y est autorisé, ou un fork et une pull request. Indiquer le ticket sur la pull request aide les autres contributeurs à repérer le travail en cours.

| Chantier | Fichiers de départ |
| --- | --- |
| Graphismes | `outils/textures.py`, palette et composants dans `outils/installer.py` |
| Missions | `jeu/00_demarrage.js`, `jeu/05_reportage.js`, parcours dans `jeu/90_validation.js` |
| Escortes et travail | Cycle de vie des gardes dans `jeu/00_demarrage.js`, affectations dans `jeu/11_affectations.js` |
| Propriétés et intérieurs | Droits et points d’interaction dans `jeu/08_immobilier.js`, transaction commune dans `change` |
| Dialogues et intentions | `outils/radio.py` pour Ollama et sa mémoire, `jeu/10_radio.js` pour le menu et les actions validées |
| Sprint et compétences | `jeu/12_sprint.js`, réglages dans `config.json`, régressions dans `tests/sprint.cjs` |

Le dépôt contient les sources que nous développons. Pour un essai en moteur, utiliser sa propre installation compatible de Vice City PC 1.0, une copie de travail et le profil Validation. Les archives commerciales, les sauvegardes et les conversations des joueurs restent locales. Les palettes, dictionnaires de textures et index du jeu se construisent à partir de la copie personnelle.

Les scripts `jeu/*.js` sont assemblés dans l’ordre de leur préfixe numérique en un seul script CLEO Redux. La boucle de jeu et le scénario automatisé se trouvent dans `90_validation.js`. Les calculs économiques s’appliquent dans une seule transaction via `change`. Une extension du format du profil doit pouvoir relire la version précédente. Le service de dialogue renvoie un texte et une intention. Le script de jeu vérifie la situation réelle avant d’agir.

Pour signaler un résultat, préciser la version, le profil, la résolution et l’action observée. Distinguer les tests Node/Python des tests dans le moteur de GTA et des essais à la souris ou à la manette. Le [comparatif des projets existants](REUTILISATION.md) aide à choisir un composant avant de commencer une nouvelle implémentation.
