"""Vérifie le panneau d'Escobar International sur l'archive commerciale personnelle."""
import os
from pathlib import Path
from struct import iter_unpack, unpack_from
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "outils"))
import affiche_ocean_drive as affiche
import maillage_rw as rw
import textures
from matieres_volume import lire_niveaux


class Panneau(unittest.TestCase):
    def test_raster_complet_jusqu_a_un_pixel(self):
        nombre, donnees = lire_niveaux(affiche.FICHIER, affiche.LARGEUR, affiche.HAUTEUR)
        self.assertEqual(nombre, 10)
        self.assertEqual(unpack_from("<I", donnees, len(donnees)-12)[0], 8)

    @unittest.skipUnless(os.environ.get("VICE_CITY_ORIGINE"), "copie personnelle non fournie")
    def test_une_face_un_raster(self):
        modeles = Path(os.environ["VICE_CITY_ORIGINE"]) / "models"
        index = {textures.name(n): (s, t) for s, t, n in
                 textures.ENTRY.iter_unpack((modeles / "gta3.dir").read_bytes())}
        def lire(nom):
            secteur, taille = index[nom]
            with (modeles / "gta3.img").open("rb") as f:
                f.seek(secteur * textures.SECTOR)
                return f.read(taille * textures.SECTOR)

        original = lire(affiche.MODELE)
        nouveau = affiche.poser_modele(original)
        self.assertEqual(nouveau, affiche.poser_modele(nouveau))
        *_, avant, mat_avant = rw.ouvrir_modele(original)
        *_, apres, mat_apres = rw.ouvrir_modele(nouveau)
        self.assertEqual(rw.noms_materiaux(mat_apres),
                         tuple(affiche.NOM if n==affiche.SOURCE else n for n in rw.noms_materiaux(mat_avant)))
        self.assertEqual(avant.faces, apres.faces)
        self.assertEqual(rw.lire_surface(original)["positions"], rw.lire_surface(nouveau)["positions"])
        indice = rw.noms_materiaux(mat_avant).index(affiche.SOURCE)
        triangles = [(a,b,c) for b,a,m,c in rw.TRI.iter_unpack(avant.faces) if m==indice]
        self.assertEqual(len(triangles), 2)
        coins = {sommet for triangle in triangles for sommet in triangle}
        self.assertEqual(len(coins), 4)
        for i, ((u,v), (s,t)) in enumerate(zip(iter_unpack("<2f",avant.uv[0]), iter_unpack("<2f",apres.uv[0]))):
            self.assertEqual(s,u)
            self.assertAlmostEqual(t, 2*v-1 if i in coins else v, places=6)

        def rasters(blob):
            _, parties = textures.dictionary(blob)
            return {n:(v,tuple(interne),d) for _,v,interne,n,d in textures.natives(parties)}

        ancien = lire(affiche.DICTIONNAIRE)
        pose = affiche.poser_dictionnaire(ancien)
        self.assertEqual(pose, affiche.poser_dictionnaire(pose))
        avant, apres = rasters(ancien), rasters(pose)
        self.assertEqual(set(apres)-set(avant), {affiche.NOM})
        for nom, tex in avant.items():
            self.assertEqual(tex, apres[nom])
        raster = apres[affiche.NOM][2]
        self.assertEqual(unpack_from("<HH",raster,80), (512,256))
        self.assertEqual(raster[85],10)
        self.assertEqual(raster[88:],affiche.FICHIER.read_bytes())


if __name__ == "__main__":
    unittest.main()
