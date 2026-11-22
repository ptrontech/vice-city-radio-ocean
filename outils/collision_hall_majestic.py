"""Ouverture mesurée d'un seul battant du Majestic dans le COL1 d'Ocean Drive.

Le plancher, la rampe, la marquise et les 164 autres enregistrements restent ceux
de la copie personnelle. Le bord de la dalle extérieure qui traversait le salon
est découpé selon le vrai contour vitré. Aucune modification de sauvegarde.
"""
from hashlib import sha256
from math import cos, dist, hypot, pi, sin
from struct import Struct, pack, unpack_from

from hall_majestic import ANGLE_PORTE, FOND_RETOUR, FOND_RUE, PLAFOND, SOL, arrondi
from relief_majestic import _poly

NOM="od_majestic2c_dy"
ORIGINAL="1fa8538523ea25fa38e1b989a369a16edad22b948b02f42697a0bf39a9d5b2cb"
MODIFIE="a1cb0d0dffc93d2fb2ce8cbb64c191bffd72cc814fe35b73a6cb9c8aacea92b4"
VEC=Struct("<3f")
FACE=Struct("<3I4B")
BOITE=Struct("<6f4B")
GOND=-2.105


def blocs(blob):
    p=0
    while p+8<=len(blob) and blob[p:p+4]==b"COLL":
        longueur,=unpack_from("<I",blob,p+4)
        fin=p+8+longueur
        if longueur<84 or fin>len(blob):raise ValueError("Enregistrement COL1 tronqué")
        nom=blob[p+8:p+30].split(b"\0",1)[0].decode("latin1").lower()
        yield nom,blob[p:fin]
        p=fin
    if any(blob[p:]):raise ValueError("Données après le dernier enregistrement COL1")


class Collision:
    def __init__(self,blob):
        self.entete=blob[:72]
        p=72
        def lire(stride):
            nonlocal p
            n,=unpack_from("<I",blob,p);p+=4
            b=blob[p:p+n*stride];p+=n*stride
            if len(b)!=n*stride:raise ValueError("Table COL1 incomplète")
            return b
        self.spheres=lire(20);self.lignes=lire(24)
        self.boites=list(BOITE.iter_unpack(lire(BOITE.size)))
        self.points=list(VEC.iter_unpack(lire(VEC.size)))
        self.faces=list(FACE.iter_unpack(lire(FACE.size)))
        if p!=len(blob):raise ValueError("Fin inattendue du modèle COL1")
        self.index={VEC.pack(*a):i for i,a in enumerate(self.points)}

    def tri(self,a,b,c,flags=(0,0,0,0),double=False):
        indices=[]
        for point in (a,b,c):
            cle=VEC.pack(*point)
            if cle not in self.index:
                self.index[cle]=len(self.points); self.points.append(VEC.unpack(cle))
            indices.append(self.index[cle])
        if len(set(indices))!=3:return
        # Dans COL1 le côté extérieur utilise le sens horaire : les six
        # triangles de la dalle d'origine ont tous un produit vectoriel Z négatif.
        self.faces.append((*indices[::-1],*flags))
        if double:self.faces.append((*indices,*flags))

    def ecrire(self):
        def array(bin,table):return pack("<I",len(table))+b"".join(bin.pack(*a) for a in table)
        corps=(self.entete[8:]+pack("<I",len(self.spheres)//20)+self.spheres
               +pack("<I",len(self.lignes)//24)+self.lignes+array(BOITE,self.boites)
               +array(VEC,self.points)+array(FACE,self.faces))
        return b"COLL"+pack("<I",len(corps))+corps


class Repere:
    def __init__(self,battant):
        a,b=sorted(battant,key=lambda p:p[1])
        dx,dy=b[0]-a[0],b[1]-a[1]; l=hypot(dx,dy)
        self.n=(dy/l,-dx/l)
        self.t=(-self.n[1],self.n[0])
        # Décalage entre le plan collision et la face de la porte mesuré sur le DFF.
        self.origine=((a[0]+b[0])/2+.035*self.n[0]+.020*self.t[0],
                      (a[1]+b[1])/2+.035*self.n[1]+.020*self.t[1],a[2]+.012)

    def monde(self,x,y,z):
        ox,oy,oz=self.origine
        return (ox+self.n[0]*x+self.t[0]*y,oy+self.n[1]*x+self.t[1]*y,oz+z)

    def local(self,p):
        dx,dy=p[0]-self.origine[0],p[1]-self.origine[1]
        return (self.n[0]*dx+self.n[1]*dy,self.t[0]*dx+self.t[1]*dy,p[2]-self.origine[2])


def dalle(col,contour,boite):
    xmin,ymin,z0,xmax,ymax,z1,*flags=boite
    # Le L du hall coupe seulement le côté sud de cette boîte. Sa soustraction
    # donne un polygone simple ; les deux coins du trottoir restent en place.
    arc=[]
    for i,b in enumerate(contour):
        a=contour[i-1]; ava=a[1]>=ymin; ap=b[1]>=ymin
        if ava!=ap:
            u=(ymin-a[1])/(b[1]-a[1])
            arc.append((a[0]+u*(b[0]-a[0]),ymin))
        if ap:arc.append(b)
    joint=sorted((i for i,p in enumerate(arc) if abs(p[1]-ymin)<.00001),
                 key=lambda i:arc[i][0])
    if len(joint)!=2 or any(not (xmin<p[0]<xmax and p[1]<ymax) for p in arc):
        raise ValueError("La boîte de la terrasse ne correspond pas au contour attendu")
    gauche,droite=joint
    pas=1 if (gauche+1)%len(arc)!=droite else -1
    encoche=[arc[gauche]]
    while gauche!=droite:
        gauche=(gauche+pas)%len(arc);encoche.append(arc[gauche])
    polygone=[(xmin,ymin),*encoche,(xmax,ymin),(xmax,ymax),(xmin,ymax)]
    for z,n in ((z0,(0,0,-1)),(z1,(0,0,1))):
        for a,b,c in _poly([(*q,z) for q in polygone],n):col.tri(a,b,c,flags)
    for i,b in enumerate(polygone):
        a=polygone[i-1]
        col.tri((*a,z0),(*b,z0),(*b,z1),flags);col.tri((*a,z0),(*b,z1),(*a,z1),flags)


def ouvrir_modele(blob):
    col=Collision(blob)
    def bas(i):
        indices={v for f in col.faces[i:i+2] for v in f[:3]}
        p=[col.points[j] for j in indices]
        return sorted((q for q in p if q[2]<min(r[2] for r in p)+.06),key=lambda q:q[1])
    rep=Repere(bas(18))
    front=[]
    for i in (22,8,18,20,16,14,12,10,24):
        a,b=bas(i)
        a,b=rep.local(a),rep.local(b)
        if not front:
            front=[a,b]
        else:
            if dist(front[-1][:2],b[:2])<dist(front[-1][:2],a[:2]):a,b=b,a
            if dist(front[-1][:2],a[:2])>.15:raise ValueError("Rupture de la façade commerciale")
            front.append(b)
    sud=front[0][1]; ouest=front[-1][0]
    revers=[(ouest,FOND_RETOUR),(FOND_RUE,FOND_RETOUR),(FOND_RUE,sud)]
    xy=[p[:2] for p in front]+revers
    col.faces=col.faces[:18]+col.faces[20:]
    dalle(col,[rep.monde(x,y,0)[:2] for x,y in xy],col.boites.pop(11))
    def mur(a,b,z0,z1,double=True):
        p,q=rep.monde(*a,z0),rep.monde(*b,z0)
        u,v=rep.monde(*a,z1),rep.monde(*b,z1)
        col.tri(p,q,v,double=double);col.tri(p,v,u,double=double)
    # Le battant sud tourne de 78° vers le hall. Le vantail nord reste fermé.
    x=-.035; sud_porte,nord_porte=-2.18,2.14
    mur((x,sud_porte),(x,sud_porte+.11),-.012,2.66)
    mur((x,-.085),(x,nord_porte),-.012,2.66)
    mur((x,sud_porte),(x,nord_porte),2.66,3.27)
    longueur=2.05
    mur((x,GOND),(x-longueur*sin(ANGLE_PORTE),GOND+longueur*cos(ANGLE_PORTE)),.10,2.65)
    for a,b in zip(revers,revers[1:]):mur(a,b,.052,PLAFOND)
    def meuble(poly,z):
        for i,b in enumerate(poly):mur(poly[i-1],b,SOL,z,False)
        for a,b,c in _poly([rep.monde(*q,z) for q in poly],(0,0,1)):col.tri(a,b,c)
    meuble(arrondi(-3.72,1.,.71,2.55,.38,2),1.26)
    for x,y in ((-2.18,6.67),(-4.13,8.19)):
        meuble([(x+.56*cos(i*pi/4),y+.58*sin(i*pi/4)) for i in range(8)],.99)
    return col.ecrire()


def ouvrir_collision_hall(blob):
    morceaux=[]; vu=False
    for nom,bloc in blocs(blob):
        if nom==NOM:
            if vu:raise ValueError("Collision du Majestic en double")
            vu=True; signature=sha256(bloc).hexdigest()
            if signature==ORIGINAL:bloc=ouvrir_modele(bloc)
            elif signature!=MODIFIE:raise ValueError("Collision du Majestic non reconnue")
        morceaux.append(bloc)
    if not vu:raise ValueError("Collision du Majestic introuvable")
    return b"".join(morceaux)


EFFETS_SEUIL={"oceandrv.col":ouvrir_collision_hall}
