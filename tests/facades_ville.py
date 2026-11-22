"""Contrôles synthétiques de l'inventaire, du retrait exact et de l'alignement UV."""
from collections import Counter
import importlib.util
from pathlib import Path
from struct import pack,iter_unpack
import sys
import unittest

RACINE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(RACINE/"outils"))
import baies_atlas_ville as atlas
import facades_ville as ville
import maillage_rw as rw
import releve_facades_ville as releve
from ombres_majestic import liste_indices
import textures
from voisinage_facades_ville import unite_affine,inverse,locale,appliquer

spec=importlib.util.spec_from_file_location("fixture_maillage",RACINE/"tests/maillage_rw.py")
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)

def modele():
    points=((0.,0.,0.),(4.,0.,0.),(4.,0.,3.),(0.,0.,3.))
    faces=((0,1,2,0),(0,2,3,0))
    uv=((0.,1.),(1.,1.),(1.,0.),(0.,0.))
    block=fixture.block
    geo=rw.Geometrie(0x1002e,bytes((208,187,142,255))*4,
        [b"".join(pack("<2f",*p) for p in uv)],b"".join(rw.TRI.pack(b,a,m,c) for a,b,c,m in faces),
        (2.,0.,1.5,3.0,1,0),b"".join(rw.VEC.pack(*p) for p in points),b"")
    mt=block(1,pack("<Ii",1,-1))+fixture.material("window3256")
    obj=block(1,geo.ecrire())+block(8,mt)+block(3,block(rw.BIN_MESH,liste_indices(faces))+block(0x105,b"exemple"))
    return block(16,block(1,bytes(12))+block(26,block(1,pack("<I",1))+block(15,obj))+block(3,b""))

def plan(source,mode="piece"):
    b={"nom":"window3256","faces":[0,1],"materiau":0,"largeur":4.,"hauteur":3.,
       "centre":(2.,0.,0.),"n":(0.,-1.),"mode":mode,"profondeur":1.4 if mode=="piece" else .16,
       "deplacement":.16 if mode=="retrait" else 0.,"vitrine":False,"nuit":False,"graine":31}
    return {"nom":"test","source":ville.empreinte(source),"famille":"habitation","geometries":[{"index":0,"baies":[b]}]}

class TestFacades(unittest.TestCase):
    def test_source_et_idempotence(self):
        source=modele();p=plan(source);sortie=ville.transformer(source,p);p["sortie"]=ville.empreinte(sortie)
        self.assertEqual(ville.transformer(sortie,p),sortie)
        self.assertEqual(ville.transformer(sortie+bytes(56),p),sortie+bytes(56))
        self.assertEqual(ville.retirer(sortie,source,p),source)
        alien=sortie.replace(b"exemple",b"etrange")
        with self.assertRaises(ValueError):ville.transformer(alien,p)
        with self.assertRaises(ValueError):ville.retirer(alien,source,p)

    def test_cadre_original_uv_et_index(self):
        src=modele()
        for mode in ("piece","retrait"):
            b=ville.transformer(src,plan(src,mode));_,_,_,sections,g,m=rw.ouvrir_modele(b)
            self.assertEqual(rw.noms_materiaux(m),("window3256",""))
            s=g.surface(("window3256",""));uv=list(iter_unpack("<2f",g.uv[0]))
            extension=list(textures.chunks(rw.corps(sections,3)))
            self.assertEqual(rw.corps(extension,0x105),b"exemple")
            self.assertEqual(Counter(map(fixture.orientee,fixture.splits(rw.corps(extension,rw.BIN_MESH)))),
                             Counter(map(fixture.orientee,s["triangles"])))
            vitrage=[f for f in s["triangles"] if f[3]==0]
            self.assertGreater(len(vitrage),2)
            for a,k,c,_ in vitrage:
                for i in (a,k,c):
                    x,y,z=s["positions"][i]
                    self.assertAlmostEqual(uv[i][0],x/4,5);self.assertAlmostEqual(uv[i][1],1-z/3,5)
            # Le matériau commercial encadre la baie ; au centre il disparaît dans
            # la pièce, ou reste identifiable au fond de l'embrasure dans l'autre mode.
            prof={round(s["positions"][i][1],3) for f in vitrage for i in f[:3]}
            self.assertEqual(prof,{0.} if mode=="piece" else {0.,.16})
            self.assertGreater(max(p[1] for p in s["positions"]),1.2 if mode=="piece" else .14)

    def test_mur_derriere_et_miroir_uv(self):
        src=modele();surf=rw.lire_surface(src);uv=[(0,1),(1,1),(1,0),(0,0)]
        b=next(releve.rectangles(surf,uv))
        obs=((0.,.18,0.),(4.,.18,0.),(4.,.18,3.))
        self.assertEqual(releve.prof_libre(b,[(8,obs,releve.encadre(obs))],[1.4,.12]),.12)
        self.assertEqual(releve.prof_libre(b,[(0,obs,releve.encadre(obs))],[1.4,.12]),1.4)
        b["nom"]="villadarkwind512"
        geo=[surf["positions"][i] for i in surf["triangles"][0][:3]]
        direct=atlas.diviser(b,geo,uv[:3]);miroir=atlas.diviser(b,geo,[(1-u,v) for u,v in uv[:3]])
        self.assertTrue(direct and miroir)
        self.assertAlmostEqual(min(q["centre"][0] for q in direct),4-max(q["centre"][0] for q in miroir))

    def test_repere_ipl_et_prisme(self):
        t=unite_affine(lambda p:(10-2*p[1],-3+3*p[0],7+1.5*p[2]))
        inv=inverse(t)
        for xyz in ((0.,0.,0.),(5.,3.,2.),(-3.,8.,-2.)):
            self.assertEqual(locale(inv,appliquer(t,xyz)),xyz)
        self.assertTrue(releve.interieur_triangle([(-2.,0.,1.),(3.,0.,1.),(1.,1.,3.)],((0,-.1,0),(2.,.4,2.))))
        self.assertFalse(releve.interieur_triangle([(-2.,1.,1.),(3.,1.,1.),(1.,1.,3.)],((0,-.1,0),(2.,.4,2.))))

if __name__=="__main__":
    unittest.main()
