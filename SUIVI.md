# Suivi de Radio Océan

## Base au 22 novembre 2026

Vice City PC classique 1.0 utilise RenderWare. CLEO a identifié le processus en jeu comme Grand Theft Auto Vice City 1.0. L’exécutable x86 de 3 088 896 octets a pour SHA-256 `04e4db72629eaa786fdd182ac224f4fd6d68806f5f4fe5c1fb5f756dc4da11d7`. Le Lisez-moi du fournisseur décrit une version de compatibilité No-CD. Le codec Miles `mss/Mp3dec.asi` faisait partie de l’installation. L’inspection initiale a trouvé les ressources du jeu classique et aucun chargeur de mods en racine.

L’installation personnelle est dans `E:\Games\GTA_VC_1.0`. L’archive 7z reste dans `E:\GTA Vice City`. La copie de travail est dans `E:\ViceCityAtelier\Jeu`. Au début du projet, les Documents contenaient `gta_vc.set` et zéro sauvegarde de partie. Les réglages d’origine ont été copiés dans `SauvegardeInitiale`. L’exécutable de travail a conservé son empreinte d’origine.

Windows 11 Pro x64 build 26300, Intel Core i5-13600K à 14 cœurs et 20 processeurs logiques, 31,7 Gio de RAM, Radeon RX 6950 XT avec pilote 32.0.21045.29003, écran 3440 × 1440 à 144 Hz. Le jeu classique tourne avec son limiteur de cadence. Le modèle qwen2.5-coder:7b était déjà présent localement dans Ollama.

## Parcours observés dans le jeu

Le profil dédié Validation a lancé une vraie nouvelle partie. Le parcours automatisé déplace Tommy entre les objectifs par script, puis laisse le moteur traiter les acteurs, les places, les récompenses et la sortie du véhicule. Les traces distinguent ces opérations des essais manuels.

- Trois livraisons de bande ont fait progresser la réputation jusqu’au premier contrat. Le moteur a créé Inès et Rafa. Rafa a rejoint une voiture comme passager.
- L’achat du comptoir à 700 $ a réussi une fois. Une nouvelle émission a crédité 100 $. Deux tentatives de retrait n’ont produit qu’un seul paiement.
- Une demande en français a parcouru toute la chaîne du jeu vers Ollama et retour. Inès a évoqué les émissions du profil et sa régie. L’attente a laissé la simulation tourner.
- La partie a été fermée normalement puis relancée dans un autre processus. La génération 8, les cinq émissions, les 1 020 $, le local, le garde, les deux points d’expérience et les 100 $ en réserve ont été relus à l’identique.
- Lors du transport d’Alma, le moteur a confirmé sa présence en passagère, sa descente au site du direct et le paiement de 520 $. Une course expirée a retiré son repère en conservant la caisse et la réputation.
- L’introduction originale et les changements du drapeau de mission ont exercé la suspension du mod. Une campagne complète et ses missions tardives demandent une partie de longue durée.
- Les tests locaux contrôlent aussi les paliers de recrutement, le double achat, les interruptions d’écriture, le dialogue de secours, la répétition d’une requête et les paliers de sprint. Les fichiers personnels des profils jouables restent indépendants de ces essais.

## Réception et chambres du Majestic

À 14 heures, une caméra de Vice City PC traverse le trottoir devant les vitrines et contourne leur angle. Le comptoir masque le casier à clés, puis la jardinière passe devant le salon. Une seconde caméra suit une baie de l’étage sur 4,4 m. À 22 heures, le modèle nocturne montre le comptoir et ses deux luminaires depuis le seuil. Chaque prise dure neuf secondes. Le film provient de la fenêtre de jeu à 1920 × 1080.

L’installateur découpe les doublages du bâtiment et reconstruit 24 chambres et un seul hall derrière la porte et les huit vitrines. Le contrôle des DFF jour et nuit retrouve 13 310 triangles de mobilier, surfaces intérieures et vitrage pour chaque variante. Le passage sud du perron mesure 1,985 m. Dans le profil Validation, un piéton commandé par la native de marche du jeu a parcouru 4,74 m entre le perron et le comptoir. Le suivi de ses positions confirme un passage à 1,06 m de l’axe, du côté sud de la porte. L’autre battant, le comptoir et le muret conservent leurs collisions. La réinstallation a reproduit les empreintes de la version active. Le retrait a restitué les collisions d’origine à l’octet près.

## Travail de l’équipe et baux

Dans le parcours en jeu, Rafa a quitté l’escorte pour tenir la régie. Une émission supplémentaire a crédité les 100 $ habituels et 50 $ pour son travail. Le rappel a transféré le même personnage vivant dans l’équipe. Le script de validation a placé Tommy dans les déclencheurs de porte d’origine. Vice City l’a déplacé à l’intérieur de l’hôtel puis du centre commercial. Le parcours a ensuite positionné Tommy aux deux guichets pour contrôler le bon étage et le sol du jeu.

La signature de la suite 317 a débité 720 $, celle du disquaire a débité 1 050 $. Le deuxième clic sur chaque achat a été refusé. Le profil issu de la première version a conservé ses huit émissions, ses recettes et son garde. À la fin du parcours, la caisse contenait 650 $, la réserve 450 $ et les deux droits étaient acquis. Les étages restent accessibles par les portes et escaliers de la campagne pour une visite manuelle.

## Mesures de cadrage et de cadence

Le profil fenêtré a indiqué 1920 × 1080 dans le titre Windows et dans le moteur de rendu. L’exécutable modifié a chargé SilentPatchVC, WindowedMode, WidescreenFix, VCLodLights et ImGuiRedux. Le champ de vision qui variait avec la vitesse a été désactivé. Les profils de jeu ont reçu les réglages de souris sauvegardés. Le signalement utilisateur de fort zoom, perte de souris puis écran noir est survenu pendant la comparaison. Une tentative ultérieure de la référence avec D3D8 natif fenêtré a aussi donné une exception Windows dans la copie Reference. Le comparatif final utilise la même traduction D3D9 et les mêmes correctifs de base pour les deux rendus.

Les relevés suivants proviennent du moteur, en millisecondes entre mises à jour pendant environ 12,5 secondes par scène. Ils comparent les données visuelles d’origine au profil avec palette retravaillée et Project2DFX. Même résolution, même point près d’Ocean View, même direction et même limiteur. Un taxi de test a parcouru 12 m dans chaque passage de jour. Le relevé PresentMon du démarrage initial est archivé à part. La vidéo d’introduction et le menu ne constituent pas une mesure de conduite.

| Scène | Référence compatible médiane / P95 / P99 | Palette et halos médiane / P95 / P99 |
| --- | --- | --- |
| Avenue avec circulation, 14 h | 33 / 34 / 34 ms | 33 / 34 / 35 ms |
| Avenue de nuit, 23 h | 33 / 34 / 34 ms | 33 / 34 / 34 ms |
| Avenue sous la pluie, 19 h | 33 / 34 / 34 ms | 33 / 34 / 34 ms |

Avec la restauration des deux matériaux 256 × 256 et le module de sprint actifs, le test final a mesuré **33 / 34 / 35 ms** (médiane, P95, P99) pour chacune des trois scènes. Le taxi a parcouru 12 m. Le moteur a exécuté la commande de sprint sans fatigue à pied et terminé de nouveau le transport d’Alma. L’essai automatisé a contrôlé l’appel natif. Le parcours de 1 500 m est couvert par des tests simulés de déplacement.

Le générateur de textures utilise les données déjà présentes dans l’installation. Il conserve les secteurs originaux du fichier d’images, ajoute 641 024 octets et met à jour les deux entrées pertinentes de son index. Les deux matériaux ont neuf niveaux de détail. La comparaison locale se trouve dans `E:\ViceCityAtelier\EssaiTextures\Comparaison-Ocean-Drive.png`. Cette image compare les textures extraites à la même échelle.

Les traces sur le PC sont dans `E:\ViceCityAtelier\Mesures`. Pour répéter, fermer le jeu avant de redéployer les scripts, préparer une copie de référence avec `outils/reference.py` puis utiliser son profil de validation. `outils/mesures.py` conserve les événements du journal CLEO. Un essai court au limiteur ne permet pas de chiffrer la marge GPU ni de conclure à la stabilité pendant une longue partie.

## Revue du carnet de sprint

Claude Code a examiné le calcul des distances et la reprise du carnet. Avec des seuils personnalisés de 10, 20 et 25 m, nous avons reproduit une validation trop tardive du dernier grade. Le correctif enregistre désormais la distance exacte du palier. Chaque nouvelle tentative manuelle signale aussi une écriture refusée. Le lanceur permet de réaffecter la touche suivie à la souris. Sept groupes de régression couvrent notamment ces cas et la reprise d’un enregistrement antérieur après une interruption.

## Milo, la météo et les cinq voix

Sur le profil Validation en 1920 × 1080, Milo a suivi Tommy puis a pris une place passager. La présence du joueur dans la voiture a bloqué le paiement. Après la descente devant Inès, le compte a reçu 440 $, un point de réputation et les revenus attendus des locaux. Le scénario automatisé rapproche le véhicule des objectifs et laisse le moteur gérer l’embarquement et la sortie.

Avec le profil Nuits d’orage de Claude, Ocean Drive à 23 h sous la pluie a donné 366 intervalles de boucle mesurés, une médiane de 33 ms, un 95e centile de 34 ms et un 99e centile de 35 ms. La comparaison de palettes change 16 tranches horaires dans chacun des deux blocs de pluie et d’ouragan. L’aperçu de couleurs se génère avec `outils/apercu_meteo.py`.

Le quai de Little Havana passe les contrôles de 233 points d’appui géométriques. Dans le jeu, Tommy est resté sur les planches aux six emplacements sondés, entre la jetée existante et le banc. Le bouton **Relever le bulletin du ponton** a fonctionné. Les essais de dossiers ont ensuite engendré les cinq témoins, ouvert chaque entretien et accepté une seule remise de bande auprès d’Inès. Les quatre premiers rapportent chacun 280 $ et le dernier 800 $. Le jeu a relu les cinq dossiers dans sa sauvegarde, avec 14 points de réputation et 3 010 $ en caisse sur ce profil de test. Les déplacements de la visite de validation sont automatisés.

Le lancement rapide remplace temporairement les deux films d’introduction par deux passages d’un clip noir et muet de deux secondes généré pour le projet. Sur ce PC, deux lancements ont atteint le moteur de scripts en neuf et dix secondes, dont un suivi de l’intégralité du parcours du quai et des factions. Les vidéos complètes sont accessibles depuis le lanceur. Les essais portent sur des sessions courtes.

## Suivre Milo à pied

Sur le profil Validation, Tommy a conduit Milo jusqu’à la radio en marchant puis en courant. Milo a parcouru 187,1 m en 52 secondes et s’est arrêté à 12,7 m de la radio. Le test utilise la commande native de suivi et enregistre la position des deux personnages. Une seule livraison a versé 440 $ et les revenus attendus. L’abandon, le mauvais indice et l’expiration ont laissé la caisse intacte. Le journal local de cet essai est `Mesures/milo-contrats-marche-et-course-natives.txt`.

## Atelier des trois IA

Dans la fenêtre Windows, Codex, Claude et Kimi ont chacun répondu sur leur compte connecté. À la réouverture de la fenêtre, chaque agent a retrouvé le mot aléatoire placé dans sa discussion. Le double-clic sur le raccourci du Bureau a rappelé la même instance. Les journaux GTA et les échanges saisis dans l’atelier ont leurs propres onglets. [Mode d’emploi](atelier/README.md)

## Lots suivants

| Fonctionnalité | Intérêt et travail restant |
| --- | --- |
| Équipe de deux à quatre | Les seuils et les places sont configurés. Essayer des véhicules pleins, un garde bloqué et plusieurs missions originales avant d’augmenter le plafond. Six à huit gardes exigent des essais de limites et un véhicule d’accompagnement. |
| Garages et conduite | Prototyper une place dans un garage existant et éprouver l’identification d’un véhicule après fermeture. Utiliser ensuite ces mesures pour des grades de conduite. |
| Nouveaux baux | La suite 317 et le disquaire du North Point Mall utilisent les portes et les intérieurs de Vice City. Les vitrines, l’escalier et le plancher ont été localisés dans les cartes et les collisions de l’installation. |
| Vie du quartier | Élargir le catalogue de missions au moyen de scripts VC documentés, puis ajouter des réactions et rôles qui agissent réellement dans le moteur. |
| Nage, vélos et nouvelles animations | Comparer la nage de Vice City Extended Features sur une installation indépendante. Les vélos demandent modèles, animation et physique compatibles VC. |
| Reflets et modèles | Comparer SkyGfx VC sur un profil distinct et mesurer la charge avec les mêmes scènes. Le ray tracing, la voix et les intérieurs supplémentaires restent au stade de l’étude. |

Les décisions sur les projets déjà disponibles et leurs licences sont dans [Réutilisation](REUTILISATION.md) et [Composants](COMPOSANTS.md).
