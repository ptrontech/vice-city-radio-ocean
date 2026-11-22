"""Vérification sur COL1 privé, du perron au salon, avec empreinte de piéton."""
from hashlib import sha256
from math import ceil, dist, hypot, sqrt
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"outils"))
import collision_hall_majestic as seuil
import hall_majestic as hall
import maillage_rw as rw
from textures import ENTRY, SECTOR, name


def membres(col,i):
    return [(col.points[a],col.points[b],col.points[c]) for a,b,c,*_ in col.faces[i:]]


def appuis(col,x,y):
    z=[b[5] for b in col.boites if b[0]<=x<=b[3] and b[1]<=y<=b[4]]
    for a,b,c in membres(col,0):
        ax=b[0]-a[0]; ay=b[1]-a[1]; bx=c[0]-a[0]; by=c[1]-a[1]
        det=ax*by-ay*bx
        if det>=-1e-8:continue  # Une surface de marche COL1 est horaire.
        u=((x-a[0])*by-(y-a[1])*bx)/det
        v=(ax*(y-a[1])-ay*(x-a[0]))/det
        if min(u,v,1-u-v)>=-.00001:z.append(a[2]+u*(b[2]-a[2])+v*(c[2]-a[2]))
    return max((h for h in z if h<-9.92),default=None)


def obstacle(col,x,y,z,rayon=.29):
    for a,b,c,d,e,f,*_ in col.boites:
        if c-.001<=z<=f+.001 and hypot(max(a-x,x-d,0),max(b-y,y-e,0))<rayon:
            return True
    for tri in membres(col,0):
        # La coupe horizontale d'un triangle donne le segment testé contre le disque du piéton.
        coupe=[]
        for k,a in enumerate(tri):
            b=tri[k-1]
            if min(a[2],b[2])<z<=max(a[2],b[2]):
                t=(z-a[2])/(b[2]-a[2])
                coupe.append((a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])))
        if len(coupe)!=2:continue
        (a,b),(c,d)=coupe
        ux,uy=c-a,d-b
        t=max(0.,min(1.,((x-a)*ux+(y-b)*uy)/max(ux*ux+uy*uy,1e-12)))
        if hypot(x-a-t*ux,y-b-t*uy)<rayon:return True
    return False


@unittest.skipUnless(os.environ.get("MAJESTIC_VC_ORIGINE"),"Copie personnelle facultative")
class SeuilPC(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        racine=Path(os.environ["MAJESTIC_VC_ORIGINE"])
        dossier=racine/"models"
        index={name(n):(o,k) for o,k,n in ENTRY.iter_unpack((dossier/"gta3.dir").read_bytes())}
        with (dossier/"gta3.img").open("rb") as f:
            def lire(n):
                o,k=index[n];f.seek(o*SECTOR);return f.read(k*SECTOR)
            cls.original=lire("oceandrv.col")
            _,_,_,_,g,m=rw.ouvrir_modele(lire("od_majestic2c_dy.dff"))
        cls.surface=g.surface(rw.noms_materiaux(m));cls.rep=hall.Repere.lire(cls.surface)
        cls.change=seuil.ouvrir_collision_hall(cls.original)
        cls.a=seuil.Collision(dict(seuil.blocs(cls.original))[seuil.NOM])
        cls.b=seuil.Collision(dict(seuil.blocs(cls.change))[seuil.NOM])

    def test_enregistrement_unique_repetition_et_retrait(self):
        a=list(seuil.blocs(self.original));b=list(seuil.blocs(self.change))
        self.assertEqual([n for n,_ in a],[n for n,_ in b])
        self.assertEqual(len(a),165)
        self.assertEqual([n for (n,d),(_,e) in zip(a,b) if d!=e],[seuil.NOM])
        self.assertEqual(dict(a)["od_majestic2c_nt"],dict(b)["od_majestic2c_nt"])
        self.assertEqual(seuil.ouvrir_collision_hall(self.change),self.change)
        # Une bascule de l'index rétablit l'entrée originale en entier, avec son alignement.
        temoin=b"".join(data for _,data in a)
        self.assertEqual(temoin,self.original[:len(temoin)])
        self.assertEqual(sha256(temoin).hexdigest(),"3c9b3f141c762deaf57d47cc6445d5dcc201cda55b426606080888af44a5056e")

    def test_chemin_avec_largeur_et_hauteur_de_pieton(self):
        chemin=[(3.18,-1.06),(-2.40,-1.06),(-1.48,2.20),(-1.39,4.68),
                (-3.21,5.72),(-3.25,7.01)]
        echantillons=0;derniere=None
        for a,b in zip(chemin,chemin[1:]):
            n=ceil(dist(a,b)/.10)
            for i in range(n+1):
                r=i/n; x,y,z=self.rep.monde((a[0]+r*(b[0]-a[0]),a[1]+r*(b[1]-a[1]),0))
                appui=appuis(self.b,x,y)
                self.assertIsNotNone(appui)
                if derniere is not None:self.assertLess(abs(appui-derniere),.13)
                derniere=appui
                for hauteur in (.37,.94,1.55):
                    self.assertFalse(obstacle(self.b,x,y,appui+hauteur),(i,a,b,hauteur))
                echantillons+=1
        self.assertGreater(echantillons,140)
        for y,ferme in ((-1.10,False),(.80,True),(3.3,True),(-4.6,True)):
            x=.74 if abs(y)>2.2 else -.035
            p=self.rep.monde((x,y,1.1))
            self.assertTrue(obstacle(self.a,*p))
            self.assertEqual(obstacle(self.b,*p),ferme)
        for x,y in ((-3.03,1.02),(-5.95,-1.90),(-2.18,6.15)):
            self.assertTrue(obstacle(self.b,*self.rep.monde((x,y,.60))))
        for x,y in ((-1.05,6.5),(-9.5,7.5)):
            a,b,_=self.rep.monde((x,y,0))
            self.assertGreater(appuis(self.a,a,b)-appuis(self.b,a,b),.65)

    def test_terrasse_preservee_et_battant_aligne(self):
        # Au bord extérieur du retour et devant les vitrines de la rue, la terrasse
        # conserve la même hauteur sur chaque point d'une grille de 10 centimètres.
        for i in range(-155,18):
            for j in range(107,122):
                x,y,_=self.rep.monde((i/10,j/10,0))
                self.assertAlmostEqual(appuis(self.a,x,y),appuis(self.b,x,y),places=4)
        for i in range(10,31):
            for j in range(23,102):
                x,y,_=self.rep.monde((i/10,j/10,0))
                self.assertAlmostEqual(appuis(self.a,x,y),appuis(self.b,x,y),places=4)
        fermee=hall.construire_hall(self.surface)
        ouverte=hall.construire_hall(self.surface,porte_ouverte=True)
        self.assertEqual(len(fermee),len(ouverte))
        verres_deplaces=[t for t,u in zip(ouverte,fermee) if t[0]=="verre" and t!=u]
        self.assertEqual(len(verres_deplaces),2)
        verre=[self.rep.local(v[:3]) for t in verres_deplaces for v in t[1:]]
        self.assertLess(min(v[0] for v in verre),-1.97)
        self.assertLess(max(v[1] for v in verre),-1.52)
        self.assertTrue(obstacle(self.b,*self.rep.monde((-1.05,-1.89,.97))))


if __name__=="__main__":unittest.main()
