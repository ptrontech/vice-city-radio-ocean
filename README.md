# Vice City · Radio Océan

Une extension personnelle pour Vice City classique PC 1.0. Inès Vega fait tourner une radio pirate sur Ocean Drive. On commence comme coursier, on recrute une équipe et on finance la régie du News Café.

## Jouer

Double-cliquer sur **Jouer à Radio Océan** dans `E:\ViceCityAtelier`. Le lanceur propose la campagne ou le mode libre. **Mode libre** ouvre une partie indépendante avec trois livraisons et 1 800 $ au compte de la radio. Après l’introduction du jeu, Tommy arrive près d’Inès. **Campagne** garde l’introduction originale et commence la progression de la radio à zéro.

En campagne, aller sur Ocean Drive, sur le trottoir côté plage en face de l’Ocean View. Le repère magenta signale Inès, le vert la régie. Approcher à pied ouvre le menu. Les destinations de mission sont jaunes. Cliquer sur **Accepter la course** ou **Discuter avec Ines**. Pour un message libre, saisir une phrase et cliquer sur **Envoyer le message**. Deux questions sont aussi accessibles à la souris.

Le journal s’ouvre avec **J**. Le lanceur permet de choisir une autre lettre. À la manette, essayer **Sélection**, la croix haut/bas puis le bouton sud pour valider. Les numéros de boutons sont réglables dans `config.json`. Après une modification manuelle du fichier, relancer l’installateur. Un clic sur **Fermer** rend le contrôle à la caméra de GTA.

## Sprint et endurance

Dans le journal ou chez Inès, cliquer sur **Sprint et endurance**. À pied, avancer et maintenir la commande Sprint de GTA (Maj gauche dans la configuration PC d’origine). Les distances courues alimentent des grades à 250, 750 et 1 500 m. Au dernier grade, le joueur peut confirmer son brevet de sprint sans fatigue. Les deux premiers grades marquent la progression du carnet. Le mode libre permet d’essayer le brevet dès l’arrivée. Si tu réaffectes Sprint, sélectionne aussi cette touche dans **Affichage et commandes** du lanceur. Le carnet enregistre chaque palier à sa distance exacte. Les restrictions liées à l’arme restent celles du moteur.

## Missions, équipe et argent

| Activité | Fonctionnement |
| --- | --- |
| Dernière bande avant minuit | Prendre la commande chez Inès, atteindre le repère jaune et revenir avant quatre minutes. Trois points de collecte alternent sur Ocean Drive. Chaque livraison rapporte 360 $ et un point de réputation. |
| Régie du News Café | Sur place, acheter le comptoir extérieur pour 700 $ puis confirmer. Chaque émission livrée après l’achat y dépose 100 $ à retirer. Le comptoir reste à l’extérieur du bâtiment. |
| Le direct du News Café | La régie achetée propose un transport à 520 $. Venir dans une voiture avec une place libre, attendre qu’Alma monte, rejoindre le site du direct et s’arrêter pour qu’elle descende. |
| Suite 317 de l’Ocean View | Le bureau se trouve à l’étage dans la suite de l’hôtel. Le bail de 720 $ rapporte 45 $ par émission. |
| Comptoir du disquaire | Entrer par l’ouest du North Point Mall, rejoindre l’étage du disquaire et confirmer le bail de 1 050 $. Il rapporte 85 $ par émission. |
| Emploi à la régie | Lorsque la régie appartient à la radio, Rafa peut y travailler. Chaque émission réussie ajoute 50 $ à la réserve en plus des recettes des locaux. On peut le rappeler au comptoir pour reprendre l’escorte. |
| Équipe | À 3, 8, 15 et 25 émissions, Inès ouvre respectivement une à quatre places. Un contrat coûte 180 $. Les commandes permettent de suivre, attendre, rejoindre une voiture et renvoyer un membre. Les gardes qui ont perdu le groupe peuvent retrouver le joueur au contact. |

Le compte de la radio paie les contrats et la propriété. L’argent et les sauvegardes des missions Rockstar restent gérés par GTA. Une livraison abandonnée ou expirée ne rapporte rien. Le mod suspend ses personnages et ses repères pendant les missions originales. Une course inachevée se reprend chez le contact.

## Affichage et souris

Le réglage de départ utilise une fenêtre de **1920 × 1080 en 16:9**, avec champ de vision indépendant de la vitesse de la voiture. Le jeu conserve son limiteur. **Affichage et commandes** permet d’activer le 3440 × 1440 au lancement suivant. Les catégories de météo d’origine restent présentes. La palette fait évoluer le ciel indigo, l’horizon de fin de journée, les reflets colorés de l’eau et la distance de vue par temps clair. Project2DFX ajoute des halos lumineux lointains. Sur Ocean Drive, la chaussée et la bordure du trottoir utilisent les variantes 256 × 256 retrouvées dans le jeu, avec leurs niveaux de détail d’origine.

Les profils de jeu ont été initialisés avec une copie de tes réglages de commandes d’avant les essais. Le lanceur se manipule à la souris. Le menu de la radio libère son curseur à la fermeture. Les réglages de sensibilité restent accessibles depuis les options de GTA.

## Sauvegarder et revenir au jeu classique

Chaque achat, recrutement, mission réussie ou retrait écrit immédiatement la progression de la radio. Deux enregistrements contrôlés par somme de vérification permettent de récupérer le dernier état valide. Les sauvegardes de GTA et les conversations d’Inès se trouvent dans le même dossier de profil.

- `E:\ViceCityAtelier\Jeu\Campagne` contient les sauvegardes GTA de la copie modifiée, sa progression de radio et ses dialogues.
- `E:\ViceCityAtelier\Jeu\Libre` est indépendant. Le profil `Validation` est réservé aux essais automatisés.
- Une campagne Radio Océan correspond à un profil. Deux emplacements de sauvegarde Rockstar dans **Campagne** partagent la progression de la radio. Charger une sauvegarde GTA antérieure ne rembobine pas les dépenses de la radio.
- Pour archiver une partie, fermer le jeu puis copier tout le dossier du profil. Pour la restaurer, fermer le jeu et remettre le dossier sauvegardé à cette place.
- Pour jouer à la version d’avant, ouvrir `E:\Games\GTA_VC_1.0\gta-vc.exe`. Ses fichiers utilisateur se trouvent dans les Documents Windows. Leur copie initiale est dans `E:\ViceCityAtelier\SauvegardeInitiale`.
- Pour désinstaller l’extension, fermer le jeu et le lanceur, conserver les profils souhaités hors de `E:\ViceCityAtelier`, puis supprimer le dossier Atelier et son raccourci. L’original reste disponible sur E:.

## Installation et reprise technique

La copie de travail est déjà installée sur ce PC. Pour redéployer les sources ou les réglages, fermer GTA puis exécuter `C:\Python312\python.exe E:\ViceCityAtelier\Projet\outils\installer.py`. Ce programme vérifie le SHA-256 de l’exécutable de travail et des archives avant d’appliquer les composants. Il régénère la palette à partir de la copie d’origine à chaque installation. Garder la structure décrite dans le suivi pour cette version du lanceur.

Le dépôt Git contient notre code, la configuration et la documentation. Les archives, le jeu, les modèles de langue, les sauvegardes et la mémoire de dialogue restent sur ce PC. Le modèle Ollama écoute sur 127.0.0.1. Python interroge le modèle en arrière-plan avec un délai limite. Si le modèle s’arrête, Inès utilise ses répliques de secours. Une proposition d’Inès ne déclenche une action qu’après validation par le jeu et par le joueur.

Sur un autre PC Windows avec Python 3.12 et Tk, cloner le dépôt dans un dossier de projet sous le dossier Atelier, définir `RADIO_OCEAN_ORIGINE` sur l’emplacement de sa propre copie compatible, puis exécuter `python outils/preparer.py` et `python outils/lancer.py`. Le préparateur vérifie et télécharge les dépendances manquantes depuis leurs auteurs. Pour les dialogues avec le modèle, lancer Ollama avec le modèle indiqué dans `config.json`. Les répliques de secours restent disponibles hors ligne.

Les contributeurs et les assistants IA peuvent choisir un [chantier GitHub](https://github.com/ptrontech/vice-city-radio-ocean/issues) et suivre le [guide de contribution](AGENTS.md).

Les projets tiers examinés pour les prochains lots sont répertoriés dans [Réutilisation](REUTILISATION.md). L’inventaire des composants figure dans [Composants](COMPOSANTS.md). Les essais, limites et priorités figurent dans [Suivi](SUIVI.md).
