# Natation de Tommy

La nage se déclenche au contact de l’eau profonde quand Tommy est à pied, hors mission de la campagne d’origine. Les axes de déplacement de Vice City servent à avancer et à tourner. Maintenir **Sprint** accélère. Maintenir **S’accroupir** plonge. Maintenir **Sauter** remonte et permet de sortir par une berge ou un ponton accessible. **Entrer dans un véhicule** rend la main aux commandes d’embarquement du jeu. Sur le clavier PC d’origine, **C** correspond à S’accroupir et **Espace** à Sauter. Ces actions suivent les affectations du clavier et de la manette. [Commandes de Vice City dans Sanny Builder](https://docs.sannybuilder.com/scm-documentation/vc/buttons)

La jauge indique une réserve d’environ seize secondes après immersion complète. Reprendre de l’air en surface la remplit progressivement. À zéro, Tommy perd quatorze points de vie par seconde de jeu tant qu’il reste immergé. La mécanique conserve la santé et l’armure courantes. Les sauvegardes GTA conservent leur format d’origine.

Le script lit la géométrie des plans d’eau dans le `data/water.dat` de la copie personnelle. Le moteur fournit le contact réel, le sol et les obstacles. L’extension C++ applique l’animation aquatique déjà présente à Tommy, incline son seul modèle pendant le dessin, puis restaure le repère graphique du jeu. Les commandes privées prennent le personnage courant et des valeurs bornées. [CLEO Redux C++ SDK](https://re.cleo.li/docs/en/cpp-sdk.html) · [Plugin-SDK](https://github.com/DK22Pac/plugin-sdk)

## Projets examinés

Le *Great Swimming Mod* de NRShaggy utilisait déjà les actions Sprint et Saut dans l’eau. La version de Serega présentée avec de nouvelles animations emploie un script et un remplacement de `ped.ifp` qui modifie aussi l’animation de noyade des passants. Radio Océan réutilise les actions d’origine et l’API ouverte de la version PC pour ajouter une profondeur contrôlée, le souffle et la noyade du seul personnage joueur. [Fiche du créateur de Great Swimming Mod](https://www.gtagarage.com/mods/show.php?id=14934) · [Présentation de la version animée](https://libertycity.net/files/gta-vice-city/107784-swimming-in-gta-vc-with-new-animation.html)

## Recompiler le rendu sous Windows

Le jeu utilise le binaire x86 livré dans `medias/RadioOceanNatation.cleo`. Pour le recompiler, employer les outils C++ x86 de Visual Studio 2019 et le SDK Windows 10. Prendre Plugin-SDK à la révision `62a1080902627b3edec0124acf02127ba8c0dcdb` et les deux fichiers `SDK/cleo_redux_sdk.h` et `SDK/cleo_redux.lib` de CLEO Redux 1.5.1 à la révision `bbf6773fe8cc1bfa95c73509a25928f97b0d8d13`. [Plugin-SDK épinglé](https://github.com/DK22Pac/plugin-sdk/tree/62a1080902627b3edec0124acf02127ba8c0dcdb) · [SDK CLEO épinglé](https://github.com/cleolibrary/CLEO-Redux/tree/bbf6773fe8cc1bfa95c73509a25928f97b0d8d13/SDK)

```powershell
python natif/natation/construire.py --plugin-sdk C:/dev/plugin-sdk --cleo-sdk C:/dev/cleo-sdk --sortie medias/RadioOceanNatation.cleo
node --test tests/natation.cjs
```

Le préparateur vérifie l’empreinte binaire et les numéros de commandes avant l’installation. Une reconstruction avec un autre compilateur peut changer cette empreinte. L’essai du profil **Validation** se sélectionne avec `scenario=natation` dans `Validation/essai.ini`. Les phases de la prise sont publiées dans `filmNage`. Le déplacement d’essai transmet des commandes au même système de nage que le joueur. L’épuisement se déroule à la vitesse normale du moteur. Le scénario termine par la mort du personnage d’essai.
