"""Contrôles géométriques indépendants. PALMIER_VC_ORIGINE active l'essai sur la copie du joueur."""
from collections import Counter
from hashlib import sha256
from math import dist
import os
from pathlib import Path
from struct import iter_unpack, unpack_from
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"outils"))
import maillage_rw as rw
import palmier_majestic as palm
from textures import ENTRY, SECTOR, chunks, name


class Creation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.forme=palm.Silhouette((0.,0.,4.6),(0.,0.,-.02),(.265,.260),
                                  (.055,-.012,5.4),((-2.8,2.5),(-2.4,2.4),(-.02,9.16)),
                                  (0.,0.,4.57,5.3,1,0))
        cls.arbre=palm.construire_palmes(cls.forme)

    def test_limites_et_normales(self):
        m=self.arbre
        self.assertLessEqual(sum(map(len,m.faces.values())),5000)
        self.assertLess(len(m.positions),14000)
        self.assertEqual({min(p[2] for p in m.positions),max(p[2] for p in m.positions)},
                         set(self.forme.bornes[2]))
        self.assertTrue(all(abs(sum(a*a for a in n)-1)<.00005 for n in m.normales))
        for p in m.positions:
            self.assertTrue(all(a-.025<=v<=b+.025 for v,(a,b) in zip(p,self.forme.bornes)))
            self.assertLessEqual(dist(p,self.forme.sphere[:3]),self.forme.sphere[3])

    def test_folioles_recto_verso_et_uv_ecorce(self):
        m=self.arbre
        def key(a,b,c):
            return min((a,b,c),(b,c,a),(c,a,b))
        faces=Counter(key(*(m.positions[i] for i in tri)) for tri in m.faces[1])
        doubles=sum(n for (a,b,c),n in faces.items() if key(a,c,b) in faces)
        self.assertGreaterEqual(doubles,2600)
        self.assertGreater(len({rgb for rgb in iter_unpack("4B",m.couleurs)}),120)
        self.assertEqual(set(m.couleurs[3::4]),{255})
        uv_tronc={m.uv[i] for tri in m.faces[0] for i in tri}
        self.assertGreater(len(uv_tronc),450)
        self.assertGreater(max(v for _,v in uv_tronc),5)


@unittest.skipUnless(os.environ.get("PALMIER_VC_ORIGINE"),"Copie locale facultative")
class IntegrationPC(unittest.TestCase):
    def test_img_materiaux_indices_collision_et_determinisme(self):
        rep=Path(os.environ["PALMIER_VC_ORIGINE"])/"models"
        offset,taille,_=next(r for r in ENTRY.iter_unpack((rep/"gta3.dir").read_bytes()) if name(r[2])==palm.NOM)
        with (rep/"gta3.img").open("rb") as f:
            f.seek(offset*SECTOR)
            original=f.read(taille*SECTOR)
        rendu=palm.EFFETS_PALMIER[palm.NOM](original)
        self.assertEqual(sha256(rendu).digest(),sha256(palm.transformer_palmier(original)).digest())
        _,p0,_,geo0,g0,_=rw.ouvrir_modele(original)
        _,p1,_,geo,g,mats=rw.ouvrir_modele(rendu)
        self.assertEqual(rw.corps(p0,14),rw.corps(p1,14))
        self.assertEqual(rw.corps(p0,20),rw.corps(p1,20))
        self.assertEqual(g0.sphere[:5],g.sphere[:5])
        self.assertEqual(g.sphere[5],1)
        self.assertEqual(rw.noms_materiaux(mats),("kbbark_test1",""))
        coeffs=[unpack_from("<3f",rw.corps(list(chunks(blob)),rw.STRUCT),16)
                for kind,_,blob in mats if kind==rw.MATERIAL]
        for actual,expected in zip(coeffs,((.14,0.,.20),(.10,0.,.16))):
            for value,ref in zip(actual,expected):
                self.assertAlmostEqual(value,ref,places=5)
        ex0=list(chunks(rw.corps(geo0,rw.EXTENSION)))
        ex1=list(chunks(rw.corps(geo,rw.EXTENSION)))
        self.assertEqual([x for x in ex0 if x[0]!=rw.BIN_MESH],[x for x in ex1 if x[0]!=rw.BIN_MESH])
        b=rw.corps(ex1,rw.BIN_MESH)
        typ,n,ni=unpack_from("<3I",b)
        self.assertEqual((typ,n,ni),(0,2,len(g.faces)//8*3))
        cursor=12; split=[]
        for _ in range(n):
            total,mat=unpack_from("<2I",b,cursor);cursor+=8
            data=b[cursor:cursor+total*4];cursor+=len(data)
            split.extend((a,b,c,mat) for a,b,c in iter_unpack("<3I",data))
        self.assertEqual(cursor,len(b))
        self.assertEqual(split,list(g.surface(rw.noms_materiaux(mats))["triangles"]))
        self.assertLess(max(max(a,b,c) for a,b,c,_ in split),len(g.positions)//12)


if __name__=="__main__":
    unittest.main()
