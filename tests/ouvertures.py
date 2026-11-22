"""Géométrie des baies et transmission du verre du Majestic."""
from math import isclose
from pathlib import Path
from struct import unpack_from
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"outils"))
import volume_rw as vr
from matieres_volume import verre_clair


def mur(x,y):
    return vr.Sommet((x,y,0.),(x*32+80.,100.,100.,255.),((x+2)/4,(y+2)/4),(0.,0.,1.))


class Ouvertures(unittest.TestCase):
    def test_fenetre_interieure_decoupe_aire_uv_et_orientation(self):
        face=[mur(-2,-2),mur(2,-2),mur(2,2),mur(-2,2)]
        trou=[((1,0,0),-1),((-1,0,0),-1),((0,1,0),-1),((0,-1,0),-1)]
        pieces=vr.retirer_prisme(face,trou)
        aire=0.
        for piece in pieces:
            a=piece[0]
            for i in range(1,len(piece)-1):
                b,c=piece[i:i+2]
                signe=(b.position[0]-a.position[0])*(c.position[1]-a.position[1])-(c.position[0]-a.position[0])*(b.position[1]-a.position[1])
                self.assertGreater(signe,0)
                aire+=signe/2
            for sommet in piece:
                attendu=mur(*sommet.position[:2])
                self.assertTrue(all(isclose(a,b) for a,b in zip(sommet.uv,attendu.uv)))
                self.assertTrue(all(isclose(a,b) for a,b in zip(sommet.couleur,attendu.couleur)))
        self.assertAlmostEqual(aire,12.)

    def test_une_face_entiere_reste_stable_hors_du_prisme(self):
        triangle=[mur(3,0),mur(5,1),mur(5,0)]
        sortie=vr.retirer_prisme(triangle,[((-1,0,0),-1)])
        self.assertIs(sortie[0],triangle)

    def test_transmission_stable_sur_toutes_les_resolutions_du_verre(self):
        nb,octets=verre_clair()
        self.assertEqual(nb,5)
        pos=0
        for dim in (16,8,4,2,1):
            n=unpack_from("<I",octets,pos)[0]
            self.assertEqual(n,16*((dim+3)//4)**2)
            blocs=octets[pos+4:pos+4+n]
            for i in range(0,n,16):
                self.assertEqual(blocs[i:i+8],b"\x11"*8)
            pos+=4+n
        self.assertEqual(pos,len(octets))


if __name__=="__main__":
    unittest.main()
