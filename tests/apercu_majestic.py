"""Vérifications du cadrage et de l’ombre d’étude sur un panneau synthétique."""
import importlib.util
from pathlib import Path
import sys
import unittest

DISPONIBLE = all(importlib.util.find_spec(n) is not None for n in ("numpy", "PIL"))
if DISPONIBLE:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "outils"))
    import apercu_majestic as apercu
    import numpy as np


@unittest.skipUnless(DISPONIBLE, "NumPy et Pillow sont nécessaires au rendu local")
class Rendu(unittest.TestCase):
    def test_projection_barycentrique(self):
        panneau = np.array([(0., 0.), (4., 0.), (0., 4.)])
        y, x, poids = apercu.ecran_triangle(panneau, 4, 4)
        np.testing.assert_allclose(poids.sum(1), np.ones(len(poids)))
        np.testing.assert_allclose(poids @ panneau, np.column_stack([x + .5, y + .5]))
        self.assertIsNone(apercu.ecran_triangle(np.zeros((3,2)),4,4))

    def test_pan_vertical_a_l_ombre(self):
        xyz = np.array([[0.,-1.,0.], [0.,1.,0.], [0.,0.,2.]])
        panneau = (xyz, np.zeros((3,2)), np.full((3,4), 255), np.array([[1,0,0,2]]), [("", np.ones(4))])
        ombres = apercu.Ombres([panneau], resolution=64)
        image = apercu.rendre([panneau], {}, ombres, (64,64), (-3.,0.,1.), (0.,0.,1.), 60.)
        self.assertEqual(image.size, (64,64))
        self.assertLess(image.getpixel((32,32))[0], 180)

    def test_ombre_portee_et_surface_eclairee(self):
        xyz = np.array([[-2.,-2.,0.], [2.,-2.,0.], [2.,2.,0.], [-2.,2.,0.]])
        faces = np.array([[1,0,0,2], [2,0,0,3]])
        lumiere = apercu.Ombres([(xyz, None, None, faces, None)], resolution=128)
        centre = np.array([0.,0.,0.])
        echantillons = np.array([centre, centre - apercu.SOLEIL, [3.,2.7,-.5]])
        np.testing.assert_allclose(lumiere.visibilite(echantillons), [1., 0., 1.])


if __name__ == "__main__":
    unittest.main()
