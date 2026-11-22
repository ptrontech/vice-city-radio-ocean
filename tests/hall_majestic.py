"""Perspectives du hall reconstruit sur Vice City PC. Les DFF commerciaux restent facultatifs."""
import os
import sys
import unittest
from math import dist, isfinite
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"outils"))
import hall_majestic as hall
import maillage_rw as rw
from textures import ENTRY, SECTOR, name


def surface_temoin():
    # Trois faces sur rue, un angle en trois pans et deux baies sur le retour.
    lignes=(((.77,-12.08),(.77,-7.12)),((.77,-7.12),(.77,-2.16)),
            ((.77,2.16),(.77,5.78)),((.77,5.78),(-.165,8.05)),
            ((-.165,8.05),(-1.58,9.45)),((-1.58,9.45),(-3.84,10.39)),
            ((-3.84,10.39),(-9.95,10.39)),((-9.95,10.39),(-16.07,10.39)),
            ((0.,-2.16),(0.,2.16)))
    pos=[]; faces=[]
    for i,(a,b) in enumerate(lignes):
        j=len(pos);mat=int(i==8)
        pos.extend(((*a,0.),(*b,0.),(*b,3.28),(*a,3.28)))
        faces.extend(((j,j+1,j+2,mat),(j,j+2,j+3,mat)))
    return dict(positions=pos,triangles=faces,materiaux=("hotelwindow2","hot_doors"))


def premier(tris,origine,cible,ignorer=()):
    # Intersection rayon/triangle, avec le même rejet du dos que le rendu du jeu.
    def moins(a,b):return tuple(x-y for x,y in zip(a,b))
    def dot(a,b):return sum(x*y for x,y in zip(a,b))
    def croix(a,b):return a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]
    direction=moins(cible,origine)
    distance=dist(origine,cible)
    direction=tuple(a/distance for a in direction)
    meilleur=None
    for mat,a,b,c in tris:
        if mat in ignorer:continue
        ab=moins(b[:3],a[:3]);ac=moins(c[:3],a[:3])
        p=croix(direction,ac); det=dot(ab,p)
        if det<1e-7:continue
        delta=moins(origine,a[:3]);u=dot(delta,p)/det
        if u<-.00001 or u>1.00001:continue
        q=croix(delta,ab);v=dot(direction,q)/det
        d=dot(ac,q)/det
        if v>=-.00001 and u+v<=1.00001 and d>.001 and (meilleur is None or d<meilleur[0]):
            meilleur=(d,mat)
    return meilleur


# Depuis les deux rues, la même suspension est visée au-dessus des fauteuils.
VOIES=(
    # Yeux mesurés sur les deux cadrages de validation du Majestic.
    ((32.735,-8.671,5.129),(-3.055,1.40,.85),"hot_doors",{"metal","laiton","bois"},.22),
    ((15.341,-4.347,4.229),(-3.055,1.40,.85),"hot_doors",{"metal","laiton","bois"},.22),
    ((11.4,-1.9,2.17),(-3.055,1.00,.85),"hot_doors",{"metal","laiton","bois"},.22),
    ((-2.0,16.4,2.18),(-4.13,8.19,.85),"hotelwindow2",{"velours"},.85),
    ((12.,4.20,2.20),(-3.02,7.64,2.29),"hotelwindow2",{"lumiere","laiton"},.44),
    ((-6.30,17.,2.20),(-3.02,7.64,2.29),"hotelwindow2",{"lumiere","laiton"},.44),
)


class Hall3D(unittest.TestCase):
    def controle(self,surface,nuit=False):
        rep=hall.Repere.lire(surface)
        tris=hall.construire_hall(surface,nuit)
        self.assertLessEqual(len(tris),6000)
        self.assertGreater(len(tris),3000)
        self.assertEqual({t[0] for t in tris},
                         {"platre","bois","lin","laiton","verre","velours","sol","lumiere","metal"})
        self.assertEqual(sum(t[0]=="verre" for t in tris),22)
        self.assertTrue(all(len(v)==8 and all(isfinite(k) for k in v)
                            and all(isinstance(k,int) and 0<=k<=255 for k in v[3:6])
                            for t in tris for v in t[1:]))
        # Les faces commerciales restent ici pour certifier de quelle baie part le rayon.
        vieux=[(surface["materiaux"][m],*(surface["positions"][i] for i in (a,b,c)))
               for a,b,c,m in surface["triangles"]]
        for oeil,cible,ouverture,materiaux,ecart in VOIES:
            depart,fin=rep.monde(oeil),rep.monde(cible)
            with self.subTest(oeil=oeil,cible=cible):
                d,ancien=premier(vieux,depart,fin)
                self.assertEqual(ancien,ouverture)
                vitre=premier(tris,depart,fin)
                self.assertEqual(vitre[1],"verre")
                self.assertLess(abs(vitre[0]-d),.12)
                distance,mat=premier(tris,depart,fin,("verre",))
                self.assertIn(mat,materiaux)
                support=premier(vieux,depart,fin,("hot_doors","hotelwindow2"))
                self.assertTrue(support is None or support[0]>distance)
                self.assertLessEqual(abs(distance-dist(depart,fin)),ecart)
                self.assertGreater(distance-vitre[0],1.90)
        self.assertAlmostEqual(rep.local(rep.monde((3.5,2.4,1.9)))[0],3.5,places=5)
        return rep,tris

    def test_volume_commun_et_objets_visibles_des_deux_rues(self):
        self.controle(surface_temoin())

    def test_foyers_et_ombres_sont_localises(self):
        rep=hall.Repere.lire(surface_temoin())
        h=hall.Hall(rep,True)
        eclaire=h.eclairer((-3.00,7.34,.11),(0,0,1),"sol",hall.PIERRE,1.)
        ombre=h.eclairer((-5.62,-5.37,.11),(0,0,1),"sol",hall.PIERRE,1.)
        self.assertGreater(eclaire[0],ombre[0]*1.38)
        self.assertGreater(eclaire[0]-eclaire[2],ombre[0]-ombre[2])
        self.assertGreater(h.eclairer((0,0,2),(-1,0,0),"lumiere",hall.OPALE,1.)[0],220)
        h.ombre(0,0,1,1)
        self.assertEqual(len(h.tris),36)
        self.assertLess(h.tris[0][1][3],h.tris[1][2][3])

    @unittest.skipUnless(os.environ.get("MAJESTIC_VC_ORIGINE"),"Copie personnelle facultative")
    def test_neuf_ouvertures_et_vues_sur_les_deux_dff_commerciaux(self):
        dossier=Path(os.environ["MAJESTIC_VC_ORIGINE"])/"models"
        index={name(n):(o,k) for o,k,n in ENTRY.iter_unpack((dossier/"gta3.dir").read_bytes())}
        with (dossier/"gta3.img").open("rb") as f:
            for modele,nuit in (("od_majestic2c_dy.dff",False),("od_majestic2c_nt.dff",True)):
                with self.subTest(modele=modele):
                    o,k=index[modele];f.seek(o*SECTOR)
                    _,_,_,_,geo,mats=rw.ouvrir_modele(f.read(k*SECTOR))
                    self.controle(geo.surface(rw.noms_materiaux(mats)),nuit)


if __name__=="__main__":
    unittest.main()
