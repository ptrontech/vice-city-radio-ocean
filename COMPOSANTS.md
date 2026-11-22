# Composants de Radio Océan

Les archives ci-dessous restent sur le PC de leur utilisateur dans `E:\ViceCityAtelier\Archives`. Les empreintes complètes des archives installées sont dans `outils/installer.py`. Les notices des auteurs sont conservées dans `Archives\Licences`.

| Composant | Version locale et rôle | Licence ou provenance |
| --- | --- | --- |
| Vice City PC classique | Exécutable x86 compatible retail 1.0. RenderWare. Ressources commerciales lues dans la copie personnelle. | Rockstar. Empreinte de l’exécutable dans le suivi. |
| SilentPatch VC | 1.1 build 12.1. Correctifs de souris, cadence et placements de carte pour le classique. | MIT. [Auteur](https://github.com/CookiePLMonster/SilentPatch) |
| Widescreen Fix VC | Binaire daté du 4 octobre 2026. HUD, proportions, FOV et anticrénelage SMAA. Archive du tag mobile gtavc verrouillée par SHA-256. | GPL-3.0. [Documentation Vice City](https://github.com/ThirteenAG/WidescreenFixesPack/blob/master/.github/docs/gtavc.md) |
| Ultimate ASI Loader et traduction D3D8 vers D3D9 | Chargeur Win32 9.7.4 livré dans l’archive Widescreen Fix. Un seul proxy graphique sur la copie jouable. | MIT pour le chargeur, BSD-2-Clause pour d3d8to9. [Chargeur](https://github.com/ThirteenAG/Ultimate-ASI-Loader) et [d3d8to9](https://github.com/crosire/d3d8to9) |
| Project2DFX VC | VCLodLights daté du 14 novembre 2026, données de halos et Open Limit Adjuster 2.0.6 fourni dans l’archive. | GPL-3.0 et MIT pour Open Limit Adjuster. [Project2DFX](https://github.com/ThirteenAG/III.VC.SA.IV.Project2DFX) et [Open Limit Adjuster](https://github.com/ThirteenAG/III.VC.SA.LimitAdjuster) |
| CLEO Redux | 1.5.1 x86, modules livrés IniFiles et Input. Le script local utilise les commandes documentées par le moteur. Fichiers de langue et API du jeu fournis localement. | CLEO Redux Freeware License Agreement. [Éditeur](https://re.cleo.li/docs/en/introduction.html) |
| ImGuiRedux | Distribution Win32 pour CLEO Redux, verrouillée par empreinte. Fenêtres intégrées avec boutons et texte libre. Le rendu s’appuie sur D3D9. | GPL-3.0. [Auteur](https://github.com/user-grinch/ImGuiRedux) |
| SaveLoader | 3.0.1. Sépare les réglages et les sauvegardes Rockstar par dossier. Le lanceur garde le menu normal en campagne. | GPL-3.0. [Auteur](https://github.com/ThirteenAG/III.VC.SA.SaveLoader) |
| Windowed Mode | 3.0.5. Fenêtre 16:9 centrée ou ultralarge en option. Évite le changement de mode vidéo exclusif lors du retour au bureau. | GPL-3.0. [Auteur](https://github.com/ThirteenAG/III.VC.SA.WindowedMode) |
| Sanny Builder Library | Catalogue vc.json 0.408 et définitions de l’hôte x86 de CLEO. Métadonnées consultées pour les opcodes, les boutons et les couleurs du radar. | Le dépôt consulté ne déclare pas de licence à sa racine. Définitions conservées dans le cache local. [Bibliothèque](https://github.com/sannybuilder/library) |
| PresentMon | Console x64 2.6.0 pour la mesure du démarrage d’origine. Les mesures par scène utilisent ensuite le temps entre deux mises à jour du jeu. | MIT. [Éditeur](https://github.com/GameTechDev/PresentMon) |
| Ollama et Qwen2.5-Coder | Service déjà installé, modèle local 7B, dialogue écrit via l’API de chat locale et stockage SQLite par profil. | [Ollama](https://github.com/ollama/ollama) et [fiche du modèle](https://ollama.com/library/qwen2.5-coder:7b) |

## Pistes examinées

Plugin-SDK fournit une interface C++ pour les jeux classiques, utile pour une future fonctionnalité inaccessible en script. DragonFF sert à créer ou modifier les modèles DFF et TXD dans Blender. Le lot actuel utilise les modèles existants. [Plugin-SDK](https://github.com/DK22Pac/plugin-sdk) et [DragonFF](https://github.com/Parik27/DragonFF).

Vice City Retraced constitue une piste distincte pour les essais de rendu. Une comparaison nécessitera une autre copie, sa chaîne graphique propre et une validation de la compatibilité avec le matériel Radeon. L’édition installée utilise le rendu classique amélioré. [Vice City Retraced](https://www.moddb.com/mods/vice-city-retraced).

Mantella cible Skyrim et Fallout 4. Radio Océan s’inspire de la séparation entre dialogue et moteur de jeu. Le service Python et la validation d’intentions sont écrits pour cette extension. [Mantella](https://github.com/art-from-the-machine/Mantella).
