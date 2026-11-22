# Matières du Majestic

Les veinures du comptoir, le grain du sol et le tissage des fauteuils suivent les coordonnées UV de chaque objet. Le hall et les chambres se construisent dans les deux modèles 3D de Vice City. Le jeu calcule la perspective et l’occultation du mobilier à chaque image.

Cinq photographies de matières de Poly Haven servent de point de départ. Le manifeste contient le lien de téléchargement et l’empreinte SHA-256 de chaque photographie. [Noyer](https://polyhaven.com/a/american_walnut_veneer) · [Terrazzo](https://polyhaven.com/a/terrazzo_tiles) · [Lin](https://polyhaven.com/a/rough_linen) · [Velours](https://polyhaven.com/a/velour_velvet) · [Plâtre](https://polyhaven.com/a/white_plaster_02) · [Licence CC0](https://polyhaven.com/license)

Pour adapter cette technique à un autre bâtiment, repérer ses ouvertures dans le DFF et transmettre leurs plans, les noms des vitres et des parements à `ouvrir_baies`. `meubler` reçoit ensuite les triangles, les coordonnées UV et la matière de chaque objet. La position des ouvertures et le plan de la réception sont propres au Majestic.

Les fichiers BC1 contiennent toutes les résolutions jusqu’à 1 × 1. L’installateur les lit directement. Pour les régénérer, déposer les cinq JPEG dans un même dossier sous les noms `<asset>.jpg` du manifeste, puis exécuter `python outils/compiler_matieres.py chemin_du_dossier` avec Pillow et NumPy. Le compilateur vérifie leurs empreintes et génère aussi le laiton, l’acier et l’opaline. Le verre translucide et l’émail se calculent à l’installation.
