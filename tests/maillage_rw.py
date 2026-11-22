from collections import Counter
from math import dist
from pathlib import Path
import struct
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"outils"))
import maillage_rw as rw
from textures import wrap, chunks

VERSION=0x1003ffff
def block(tag,body):return wrap(tag,VERSION,body)
def material(nom):
    txt=block(1,bytes(4))+block(2,nom.encode("ascii")+b"\0")+block(2,b"\0")+block(3,b"")
    return block(7,block(1,struct.pack("<I4BIIfff",0,255,255,255,255,0,1,1,0,1))+block(6,txt)+block(3,b""))

def modele(strip=True):
    p=((0,0,0),(1,0,0),(0,1,0))
    geo=rw.Geometrie(0x1002e|int(strip),bytes((120,140,160,255))*3,[bytes(24)],rw.TRI.pack(1,0,0,2),
                     (0.,0.,0.,2.,1,0),b"".join(rw.VEC.pack(*v) for v in p),b"")
    matlist=block(1,struct.pack("<Iii",2,-1,-1))+material("hotelpeach")+material("hotelwindow2")
    idx=struct.pack("<8I",int(strip),1,3,3,0,0,1,2)
    g=block(1,geo.ecrire())+block(8,matlist)+block(3,block(rw.BIN_MESH,idx)+block(0x105,bytes(4)))
    return block(16,block(1,bytes(12))+block(26,block(1,struct.pack("<I",1))+block(15,g))+block(3,b""))

def exemple(surface,nuit=False):
    n=100 if nuit else 220
    a=(3.,0.,0.,n,100,100);b=(3.,1.,0.,n,100,100);c=(3.,.5,1.,n,100,100)
    d=(4.,.5,0.,n,90,90)
    return [(a,b,c),(b,d,c),(d,a,c)]

def splits(payload):
    strip,n,total=struct.unpack_from("<3I",payload)
    off=12
    result=[]
    for _ in range(n):
        count,mat=struct.unpack_from("<2I",payload,off);off+=8
        raw=struct.unpack_from(f"<{count}I",payload,off);off+=count*4
        if strip:
            faces=[]
            for i in range(count-2):
                a,b,c=raw[i:i+3]
                if len({a,b,c})==3:faces.append((b,a,c) if i%2 else (a,b,c))
        else:faces=[raw[i:i+3] for i in range(0,count,3)]
        result.extend((a,b,c,mat) for a,b,c in faces)
    assert off==len(payload)
    return result

def orientee(face):
    a,b,c,m=face
    return min((a,b,c,m),(b,c,a,m),(c,a,b,m))
class Relief(unittest.TestCase):
    def test_strips_et_listes_gardent_faces_et_orientation(self):
        for strip in (True,False):
            with self.subTest(strip=strip):
                src=modele(strip)
                result=rw.appliquer_relief(src+bytes(12),constructeur=exemple)
                self.assertEqual(result,rw.appliquer_relief(src,constructeur=exemple))
                surface=rw.lire_surface(result)
                self.assertEqual(surface["materiaux"],("hotelpeach","hotelwindow2",""))
                self.assertEqual(surface["triangles"][0],(0,1,2,0))
                self.assertEqual(len(surface["positions"]),7)
                self.assertEqual(len(surface["triangles"]),4)
                _,_,_,parts,gm,_=rw.ouvrir_modele(result)
                groups=rw.corps(list(chunks(rw.corps(parts,3))),rw.BIN_MESH)
                self.assertEqual(Counter(map(orientee,splits(groups))),Counter(map(orientee,surface["triangles"])))
                self.assertEqual(gm.couleurs[:12],bytes((120,140,160,255))*3)
                self.assertEqual(len(gm.uv[0]),56)
                for xyz in surface["positions"]:
                    self.assertLessEqual(dist(xyz,gm.sphere[:3]),gm.sphere[3])
    def test_couleur_de_nuit_sans_deplacer_la_geometrie(self):
        jour=rw.appliquer_relief(modele(),constructeur=exemple)
        nuit=rw.appliquer_relief(modele(),nuit=True,constructeur=exemple)
        self.assertEqual(rw.lire_surface(jour),rw.lire_surface(nuit))
        self.assertNotEqual(rw.ouvrir_modele(jour)[4].couleurs,rw.ouvrir_modele(nuit)[4].couleurs)
    def test_entrees_invalides_protegent_la_source(self):
        source=modele()
        for invalid in (source[:-7],source+b"autre",source.replace(b"hotelpeach",b"other-name")):
            with self.subTest(length=len(invalid)),self.assertRaises(ValueError):
                rw.appliquer_relief(invalid,constructeur=exemple)
        with self.assertRaises(ValueError):
            rw.appliquer_relief(source,constructeur=lambda *a,**k:[((0.,0.,0.,999,0,0),)*3])
if __name__=="__main__":unittest.main()
