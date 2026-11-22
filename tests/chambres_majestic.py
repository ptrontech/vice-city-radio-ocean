"""Tests des chambres. VICE_CITY_ORIGINE permet aussi de lire une installation personnelle."""
import itertools
import math
import os
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "outils"))
import chambres_majestic as chambres


def surface_inventee():
    positions, triangles = [], []
    def panneau(a, b, z, h):
        i = len(positions)
        positions.extend([(a[0],a[1],z),(b[0],b[1],z),(b[0],b[1],z+h),(a[0],a[1],z+h)])
        triangles.extend([(i,i+1,i+2,1),(i,i+2,i+3,1)])
    for z in (1., 7.):
        for plan, largeur in ((10., (6.5,4.0,6.7)),(-10.,(2.82,2.81,2.79))):
            for y,w in zip((-8.4, 0., 8.4),largeur):
                panneau((plan,y-w/2),(plan,y+w/2),z,3.30)
        for y in (-14.,14.):
            for x in (-5.,0.,5.):
                panneau((x-1.4,y),(x+1.4,y),z,3.30)
    i=len(positions)
    positions.extend([(-10.8,-15.,-.7),(10.8,-15.,-.7),(10.8,15.,11.3)])
    triangles.append((i,i+1,i+2,0))
    return {"positions":positions,"triangles":triangles,"materiaux":("mur","hotelwindow1")}


def local(piece, v):
    xy = v[:2]
    return (chambres.produit(xy,piece.p["t"])-piece.p["s0"],
            piece.p["d"]-chambres.produit(xy,piece.p["n"]),v[2]-piece.zsol)


def traverse(origine, direction, triangle):
    a,b,c = triangle
    e1,e2 = chambres.moins(b,a), chambres.moins(c,a)
    h = chambres.croix(direction,e2)
    den = chambres.produit(e1,h)
    if abs(den)<1e-8:
        return False
    s=chambres.moins(origine,a)
    u=chambres.produit(s,h)/den
    if u<0 or u>1:
        return False
    q=chambres.croix(s,e1)
    v=chambres.produit(direction,q)/den
    if v<0 or u+v>1:
        return False
    t=chambres.produit(e2,q)/den
    return 1e-5<t<.998


def masques_depuis_la_rue(piece, triangles):
    """Points de mobilier visibles d'un seul des deux yeux séparés de 3 m."""
    surfaces=[(t[0],tuple(local(piece,v) for v in t[1:])) for t in triangles]
    objets=[]
    for mat,tri in surfaces:
        p=tuple(sum(v[k] for v in tri)/3 for k in range(3))
        if mat in ("lin","velours","laiton","lumiere") and p[1]>1. and .55<p[2]<piece.h-.28:
            objets.append(p)
    bord_bas=piece.p["z0"]-piece.zsol
    bord_haut=piece.p["z1"]-piece.zsol
    def ensemble(oeil):
        resultat=set()
        for i,p in enumerate(objets):
            direction=chambres.moins(p,oeil)
            t=-oeil[1]/direction[1]
            x, z=oeil[0]+t*direction[0], oeil[2]+t*direction[2]
            if 0<x<piece.w and bord_bas<z<bord_haut:
                if not any(traverse(oeil,direction,tri) for _,tri in surfaces):
                    resultat.add(i)
        return resultat
    g=ensemble((piece.w/2-1.5,-4.8,1.60))
    d=ensemble((piece.w/2+1.5,-4.8,1.60))
    return len(g-d), len(d-g), len(g&d)


class TestsChambres(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.surface=surface_inventee()
        cls.plans=chambres.dispositions(cls.surface)

    def test_aucune_baie(self):
        s=dict(self.surface,materiaux=("mur","autre"))
        self.assertEqual(chambres.construire_chambres(s),[])

    def test_24_pieces_et_six_programmes_de_rue(self):
        self.assertEqual(len(self.plans),24)
        rue=[p for p in self.plans if p["aile"]==0]
        self.assertEqual([p["usage"] for p in rue],list(chambres.PROGRAMMES_RUE))
        self.assertEqual(sum(p["largeur"]>5.2 for p in rue),4)
        self.assertTrue(all(1.7<=p["profondeur"]<=3.1 for p in self.plans))
        self.assertFalse(any(chambres.chevauche(a,b) for a,b in itertools.combinations(self.plans,2)))

    def test_geometrie_uv_et_orientations(self):
        for plan in self.plans:
            piece=chambres.Chambre(plan,False)
            tris=piece.construire()
            self.assertGreater(len(tris),100)
            for mat,a,b,c in tris:
                self.assertIn(mat,chambres.ECHELLE_UV)
                n=chambres.croix(chambres.moins(b[:3],a[:3]),chambres.moins(c[:3],a[:3]))
                self.assertGreater(chambres.produit(n,n),1e-14)
                uv=(b[6]-a[6])*(c[7]-a[7])-(b[7]-a[7])*(c[6]-a[6])
                self.assertGreater(abs(uv),1e-9)
                for v in (a,b,c):
                    x,y,z=local(piece,v)
                    self.assertTrue(-1e-6<=x<=piece.w+1e-6)
                    self.assertTrue(.0449<=y<=piece.d+1e-6)
                    self.assertTrue(-1e-6<=z<=piece.h+1e-6)
                    self.assertTrue(all(isinstance(val,int) and 0<=val<=255 for val in v[3:6]))
                    self.assertTrue(all(math.isfinite(val) for val in v))
            # Les faces du plancher regardent vers la pièce.
            _,a,b,c=tris[0]
            n=chambres.croix(chambres.moins(b[:3],a[:3]),chambres.moins(c[:3],a[:3]))
            self.assertGreater(n[2],0)
            # Les triangles du mur de fond voient l'ouverture.
            _,a,b,c=tris[8]
            n=chambres.croix(chambres.moins(b[:3],a[:3]),chambres.moins(c[:3],a[:3]))
            self.assertGreater(chambres.produit(n[:2],piece.p["n"]),0)

    def test_separations_rideaux_et_clairevoie(self):
        for p in self.plans[:6]:
            piece=chambres.Chambre(p,False)
            tris=piece.construire()
            if piece.w>5.2:
                xs=(.46 if piece.id%2 else .52)*piece.w
                retours=[]
                for mat,*verts in tris:
                    v=[local(piece,pt) for pt in verts]
                    if mat=="platre" and all(abs(pt[0]-xs)<.071 for pt in v):
                        retours.extend(pt[1] for pt in v)
                self.assertGreater(max(retours)-min(retours),1.22)
            if p["usage"] in ("suite","lecture","salon"):
                plis=[local(piece,v) for mat,*verts in tris if mat in ("lin","velours") for v in verts]
                relief={round(pt[1],3) for pt in plis if .14<pt[1]<.48 and pt[2]>.6}
                self.assertGreater(len(relief),12)
            if p["usage"]=="volets":
                lames=[local(piece,v) for mat,*verts in tris if mat=="bois" for v in verts]
                cotes={round(pt[2],2) for pt in lames if abs(pt[1]-.445)<.001}
                self.assertGreaterEqual(len(cotes),20)

    def test_nuit_identite_et_eclairages_distincts(self):
        jour=chambres.construire_chambres(self.surface)
        nuit=chambres.construire_chambres(self.surface,True)
        self.assertEqual(len(jour),len(nuit))
        self.assertLess(len({v for t in nuit for v in t[1:]}),17500)
        for a,b in zip(jour,nuit):
            self.assertEqual(a[0],b[0])
            self.assertEqual([v[:3]+v[6:] for v in a[1:]],[v[:3]+v[6:] for v in b[1:]])
        self.assertNotEqual(jour,nuit)
        for p in self.plans[:6]:
            jour_piece=chambres.Chambre(p,False).construire()
            nuit_piece=chambres.Chambre(p,True).construire()
            lumiere=lambda tris:[sum(v[3:6])/3 for t in tris if t[0]=="lumiere" for v in t[1:]]
            self.assertEqual(bool(lumiere(nuit_piece)), p["usage"]!="volets")
            if lumiere(nuit_piece):
                self.assertGreater(max(lumiere(nuit_piece)),max(lumiere(jour_piece)))

    def test_parallaxe_mobilier_et_cloison(self):
        piece=chambres.Chambre(self.plans[0],False)
        g,d,commun=masques_depuis_la_rue(piece,piece.construire())
        self.assertGreaterEqual(min(g,d),2)
        self.assertGreaterEqual(commun,3)

    @unittest.skipUnless(os.environ.get("VICE_CITY_ORIGINE"),"installation personnelle facultative")
    def test_les_deux_dff_personnels(self):
        import maillage_rw
        dossier=Path(os.environ["VICE_CITY_ORIGINE"])/"models"
        with (dossier/"gta3.img").open("rb") as archive:
            for suffix in ("dy","nt"):
                nom=f"od_majestic2c_{suffix}.dff".encode()
                record=next((s,n) for s,n,raw in struct.iter_unpack("<II24s",(dossier/"gta3.dir").read_bytes()) if raw.split(b"\0")[0].lower()==nom)
                archive.seek(record[0]*2048)
                surface=maillage_rw.lire_surface(archive.read(record[1]*2048))
                plans=chambres.dispositions(surface)
                self.assertEqual(len(plans),24)
                self.assertFalse(any(chambres.chevauche(a,b) for a,b in itertools.combinations(plans,2)))
                for p in plans:
                    piece=chambres.Chambre(p,suffix=="nt")
                    tris=piece.construire()
                    if p["indice"]==0:
                        g,d,commun=masques_depuis_la_rue(piece,tris)
                        self.assertGreater(min(g,d,commun),2)
                    for triangle in tris:
                        for v in triangle[1:]:
                            x,y,z=local(piece,v)
                            self.assertTrue(-.001<=x<=piece.w+.001 and .044<=y<=piece.d+.001 and -.001<=z<=piece.h+.001)


if __name__=="__main__":
    unittest.main()
