"""Contrôles autonomes et contrôle des 20 DFF sur une copie privée de Vice City.

    python tests/voitures_1986.py
    python tests/voitures_1986.py E:/Games/GTA_VC_1.0
"""
from collections import Counter
from math import dist, isfinite
from pathlib import Path
from struct import iter_unpack, pack, unpack_from
import os
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "outils"))
import maillage_rw as rw
import voitures_1986 as v
from textures import ENTRY, chunks, name

BASE = os.environ.get("VOITURES_VC_ORIGINE")
if len(sys.argv)>1 and Path(sys.argv[1]).is_dir():
    BASE = sys.argv.pop(1)


def table_geom(sections):
    return [(ver, list(chunks(data))) for k,ver,data in chunks(rw.corps(sections,rw.GEOMETRY_LIST))
            if k==rw.GEOMETRY]


def decouper_binmesh(data):
    strip,n,total=unpack_from("<3I",data)
    parts=[]
    offset=12
    for _ in range(n):
        quantite,mat=unpack_from("<2I",data,offset)
        ids=unpack_from(f"<{quantite}I",data,offset+8)
        parts.append((mat,ids))
        offset+=8+4*quantite
    assert offset==len(data) and sum(len(ids) for _,ids in parts)==total
    return strip,parts


def triangles_binmesh(strip, indices):
    if not strip:
        yield from zip(indices[::3],indices[1::3],indices[2::3])
        return
    for i in range(2,len(indices)):
        a,b,c=indices[i-2:i+1]
        if a!=b and a!=c and b!=c:
            yield (b,a,c) if i%2 else (a,b,c)


def canon(t):
    # Les trois rotations d'une face ont la même normale. Une inversion la change.
    return min(t,t[1:]+t[:1],t[2:]+t[:2])


class Unites(unittest.TestCase):
    def test_dispatch_et_exclusions(self):
        self.assertEqual(len(v.EFFETS_VOITURES),20)
        for nom in ("Sentinel","SABRE.DFF","models/cheetah.dff",r"dir\BOBCAT.DFF"):
            self.assertTrue(v.cible_voiture(nom))
        for nom in ("gta3.img","stinger.dff","banshee.dff","rhino.dff","sabre.txd","caddy"):
            self.assertFalse(v.cible_voiture(nom))
            self.assertEqual(v.transformer_voiture(nom,b"inchange"),b"inchange")

    def test_polygone_cadre_et_transformation_de_repere(self):
        for rond in (False,True):
            c=v._contour(.40,.02,.25,.105,rond)
            self.assertEqual(len(set(c)),len(c))
            self.assertGreater(sum(x*z2-x2*z for (x,z),(x2,z2) in zip(c,c[1:]+c[:1])),0)
        rep=(((0.,1.,0.),(-1.,0.,0.),(0.,0.,1.)),(1.3,-2.4,.51))
        a=(.53,-.80,.11)
        self.assertLess(dist(v._local(rep,v._monde(rep,a)),a),1e-8)

    def test_deux_entetes_rw_et_troncature(self):
        for ver in (0x0c02ffff,0x1003ffff):
            geo=v.Geometrie(0x10077,pack("<3f",1,1,1) if ver==0x0c02ffff else b"",
                b"",(bytes(24),),pack("<4H",1,0,0,2),(0.,0.,0.,1.,1,1),
                pack("<9f",0,0,0,1,0,0,0,0,1),pack("<9f",0,-1,0,0,-1,0,0,-1,0))
            self.assertEqual(v.Geometrie.lire(geo.ecrire(),ver),geo)
            with self.assertRaises(ValueError):
                v.Geometrie.lire(geo.ecrire()[:-1],ver)

    def test_jonctions_strip_sans_face_parasite(self):
        faces=[(0,1,2),(3,4,5),(4,7,3),(7,8,9)]
        for strip in (0,1):
            mode,parts=decouper_binmesh(rw.ajouter_split(pack("<3I",strip,0,0),faces,2))
            self.assertEqual(list(triangles_binmesh(mode,parts[0][1])),faces)


@unittest.skipUnless(BASE,"indiquer le dossier personnel de Vice City pour le contrôle natif")
class Originaux(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=Path(BASE)
        dossier=root/"models"
        idx={name(n):(o,k) for o,k,n in ENTRY.iter_unpack((dossier/"gta3.dir").read_bytes())}
        lignes=(root/"data/default.ide").read_text(encoding="latin1").splitlines()
        debut=lignes.index("cars")
        cls.ide={p[1]: (int(p[0]),p[2],p[3]) for ligne in lignes[debut+1:lignes.index("end",debut)]
                 if ligne.strip() and ligne.lstrip()[0].isdigit()
                 for p in [[elt.strip() for elt in ligne.split(",")]]}
        cls.dffs={}
        cls.index=idx
        with (dossier/"gta3.img").open("rb") as img:
            for nom,fn in v.EFFETS_VOITURES.items():
                off,nsect=idx[nom]
                img.seek(off*2048)
                original=img.read(nsect*2048)
                cls.dffs[nom]=(original,fn(original))

    def test_selection_reelle_et_idempotence(self):
        self.assertEqual(len(self.ide),107)
        for nom,(source,resultat) in self.dffs.items():
            with self.subTest(nom):
                _,txd,typ=self.ide[nom[:-4]]
                self.assertEqual(typ,"car")
                self.assertIn(txd+".txd",self.index)
                self.assertNotEqual(source,resultat)
                self.assertEqual(v.transformer_voiture(nom,resultat),resultat)
                self.assertEqual(v.transformer_voiture(nom,source),resultat)

    def test_pivots_atomics_dommages_lod_et_evenements_intacts(self):
        for nom,(source,resultat) in self.dffs.items():
            with self.subTest(nom):
                ver,sections=rw.clump(source)
                ver2,suite=rw.clump(resultat)
                self.assertEqual(ver2,ver)
                self.assertEqual([e for e in sections if e[0]!=26],[e for e in suite if e[0]!=26])
                cadres,reps=v._cadres(sections)
                self.assertEqual(v._cadres(suite),(cadres,reps))
                for dummy in ("headlights","taillights","wheel_rf_dummy","wheel_lf_dummy"):
                    self.assertIn(dummy,cadres)
                avant=table_geom(sections)
                apres=table_geom(suite)
                self.assertEqual(len(avant),len(apres))
                intacts=0
                for k,_,d in sections:
                    if k!=20:continue
                    fr,gi,_,_=unpack_from("<4I",rw.corps(list(chunks(d)),1))
                    if cadres[fr].endswith(("_hi_dam","_vlo")):
                        self.assertEqual(avant[gi],apres[gi])
                        intacts+=1
                self.assertGreater(intacts,3)

    def test_faces_indices_matieres_normales_silhouette(self):
        for nom,(source,resultat) in self.dffs.items():
            with self.subTest(nom):
                _,old=rw.clump(source)
                _,new=rw.clump(resultat)
                _,reps=v._cadres(old)
                frame={unpack_from("<2I",rw.corps(list(chunks(d)),1))[1]:
                       unpack_from("<2I",rw.corps(list(chunks(d)),1))[0] for k,_,d in old if k==20}
                ajouts=0
                positions_monde=[]
                for i,((ver,ge),(ver2,mod)) in enumerate(zip(table_geom(old),table_geom(new))):
                    if ge==mod:continue
                    self.assertEqual(ver,ver2)
                    a=v.Geometrie.lire(rw.corps(ge,1),ver)
                    b=v.Geometrie.lire(rw.corps(mod,1),ver)
                    self.assertEqual(b.flags&~0x40,a.flags&~0x40)
                    self.assertTrue(b.positions.startswith(a.positions) and b.normales.startswith(a.normales))
                    self.assertTrue(b.faces.startswith(a.faces))
                    self.assertEqual(a.ancienne_surface,b.ancienne_surface)
                    self.assertEqual(len(a.uv),len(b.uv))
                    self.assertTrue(all(y.startswith(x) for x,y in zip(a.uv,b.uv)))
                    mat=[list(chunks(rw.corps(q,8))) for q in (ge,mod)]
                    self.assertEqual(mat[1][1:len(mat[0])],mat[0][1:])
                    self.assertEqual(rw.corps(mat[1],1)[4:len(rw.corps(mat[0],1))],rw.corps(mat[0],1)[4:])
                    ex1,ex2=[list(chunks(rw.corps(q,3))) for q in (ge,mod)]
                    self.assertEqual([e for e in ex1 if e[0]!=rw.BIN_MESH],[e for e in ex2 if e[0]!=rw.BIN_MESH])
                    kind,old_splits=decouper_binmesh(rw.corps(ex1,rw.BIN_MESH))
                    kind2,new_splits=decouper_binmesh(rw.corps(ex2,rw.BIN_MESH))
                    self.assertEqual((kind,old_splits),(kind2,new_splits[:len(old_splits)]))
                    verts=list(iter_unpack("<3f",b.positions))
                    normes=list(iter_unpack("<3f",b.normales))
                    original_nv=len(a.positions)//12
                    section=b.faces[len(a.faces):]
                    faces=[]
                    for bb,aa,ma,cc in iter_unpack("<4H",section):
                        self.assertTrue(all(original_nv<=idx<len(verts) for idx in (aa,bb,cc)))
                        self.assertLess(ma,unpack_from("<I",rw.corps(mat[1],1))[0])
                        t=canon((aa,bb,cc))
                        faces.append((ma,t))
                        va,vb,vc=[verts[j] for j in (aa,bb,cc)]
                        u=[vb[j]-va[j] for j in range(3)];w=[vc[j]-va[j] for j in range(3)]
                        croix=(u[1]*w[2]-u[2]*w[1],u[2]*w[0]-u[0]*w[2],u[0]*w[1]-u[1]*w[0])
                        self.assertGreater(v._produit(croix,normes[aa]),1e-8)
                    par_split=[(ma,canon(t)) for ma,ids in new_splits[len(old_splits):]
                               for t in triangles_binmesh(kind,ids)]
                    self.assertEqual(Counter(faces),Counter(par_split))
                    for pt,n in zip(verts[original_nv:],normes[original_nv:]):
                        self.assertTrue(all(isfinite(x) for x in pt))
                        self.assertLess(abs(v._produit(n,n)-1),.0001)
                        self.assertLessEqual(dist(pt,b.sphere[:3]),b.sphere[3]+.00001)
                        positions_monde.append(v._monde(reps[frame[i]],pt))
                    ajouts+=len(faces)
                self.assertGreater(ajouts,280)
                self.assertLess(ajouts,920)
                self.assertTrue(all(abs(p[0])<1.09 and -.65<p[2]<.46 for p in positions_monde))
                self.assertGreater(max(p[1] for p in positions_monde),1.9)
                self.assertLess(min(p[1] for p in positions_monde),-1.9)


if __name__=="__main__":
    unittest.main(verbosity=2)
