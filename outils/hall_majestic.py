"""Grand hall du Majestic, construit derrière les neuf ouvertures de la copie locale.

Les mètres sont mesurés depuis le milieu de la porte. X sort vers Ocean Drive,
Y court vers la vitrine arrondie et Z monte depuis le seuil. Les UV ne décrivent
que des matières répétables. Le mobilier, les lampes et les ombres ont du relief.
"""
from dataclasses import dataclass
from math import atan2, ceil, cos, dist, exp, hypot, pi, sin, sqrt

from relief_majestic import _poly, _porte, _preparer

SOL = .103  # La dalle commerciale sur les marches dépasse le bas de la porte de .081 m.
PLAFOND = 3.67
ANGLE_PORTE = 78*pi/180
FOND_RUE = -5.95
FOND_RETOUR = 4.05

PIERRE = (174, 167, 148)
ENDUIT = (190, 162, 126)
NOYER = (102, 64, 45)
ACAJOU = (124, 71, 44)
BRONZE = (154, 111, 59)
LAITON = (201, 156, 83)
VERT = (41, 104, 88)
SOMBRE = (48, 51, 47)
OPALE = (245, 225, 182)


@dataclass
class Repere:
    origine: tuple
    axe: tuple
    baies: tuple
    porte: tuple
    front: tuple

    def monde(self, p):
        nx, ny = self.axe
        x, y, z = p
        return (self.origine[0] + nx*x - ny*y,
                self.origine[1] + ny*x + nx*y, self.origine[2] + z)

    def local(self, p):
        dx, dy = p[0]-self.origine[0], p[1]-self.origine[1]
        nx, ny = self.axe
        return nx*dx+ny*dy, -ny*dx+nx*dy, p[2]-self.origine[2]

    @classmethod
    def lire(cls, surface):
        p = _preparer(surface)["panneaux"]
        if len(p["hotelwindow2"]) != 8 or len(p["hot_doors"]) != 1:
            raise ValueError("Le hall attend les huit baies d'angle et la porte PC du Majestic")
        porte = _porte(p["hot_doors"])
        t, n = porte["t"], porte["n"]
        s = (porte["s0"]+porte["s1"])*.5
        origine = (t[0]*s+n[0]*porte["d"], t[1]*s+n[1]*porte["d"], porte["z0"])
        rep = cls(origine, n, (), (), ())
        def ligne(v):
            def point(s):
                x = v["t"][0]*s+v["n"][0]*v["d"]
                y = v["t"][1]*s+v["n"][1]*v["d"]
                return rep.local((x,y,v["z0"]))[:2]
            a, b = point(v["s0"]), point(v["s1"])
            def angle(q):
                return atan2(q[1]+1., q[0]+6.)
            return (*sorted((a,b),key=angle), v["z1"]-origine[2])
        rep.baies = tuple(ligne(v) for v in p["hotelwindow2"])
        rep.porte = ligne(porte)
        ordonne = sorted((*rep.baies,rep.porte),
                         key=lambda v: atan2(v[0][1]+v[1][1]+2., v[0][0]+v[1][0]+12.))
        contour = []
        for debut,fin,_ in ordonne:
            if not contour or dist(contour[-1],debut) > .025:
                contour.append(debut)
            contour.append(fin)
        rep.front = tuple(contour)
        return rep


def nuance(rgb, k):
    return tuple(max(0,min(255,round(v*k))) for v in rgb)


def arrondi(cx, cy, hx, hy, rayon, stations=4, angle=0.):
    """Rectangle à quatre vrais quarts de cercle, dans l'ordre trigonométrique."""
    pts = []
    for i,(sx,sy) in enumerate(((1,1),(-1,1),(-1,-1),(1,-1))):
        for j in range(stations+1):
            a = (i+j/stations)*pi/2
            x = sx*(hx-rayon)+rayon*cos(a)
            y = sy*(hy-rayon)+rayon*sin(a)
            pts.append((cx+x*cos(angle)-y*sin(angle), cy+x*sin(angle)+y*cos(angle)))
    return pts


def cercle(x,y,r,n=12,ry=None):
    ry = r if ry is None else ry
    return [(x+r*cos(2*pi*i/n), y+ry*sin(2*pi*i/n)) for i in range(n)]


class Hall:
    def __init__(self, rep, nuit):
        self.rep = rep
        self.nuit = nuit
        self.tris = []
        # Chaque foyer correspond à une lampe modélisée. Position, rayon, intensité.
        self.foyers = ((-3.56,-.68,1.77,2.45,.64),(-3.66,2.79,2.23,3.05,.74),
                       (-5.77,-.84,2.02,1.45,.38),(-5.77,4.03,2.02,1.45,.38),(-3.02,7.64,2.29,3.45,1.0),
                       (-12.74,5.26,1.39,2.45,.78),(-3.4,-8.6,2.58,3.45,.78))

    def eclairer(self, p, normale, mat, rgb, ton):
        if mat == "lumiere":
            return nuance((253,210,144) if self.nuit else OPALE,ton)
        if mat == "verre":
            return rgb
        x,y,z = p
        recul=max(0.,min(.77-x,10.39-y))
        jour=exp(-recul/4.)
        calme=(.32+.14*jour) if self.nuit else (.70+.25*jour)
        foyer=sum(amp*exp(-((x-a)**2+(y-b)**2+1.45*(z-c)**2)/(r*r))
                   for a,b,c,r,amp in self.foyers)
        k=foyer*(.86 if self.nuit else .24)
        direction=.83+.17*max(0., .60*normale[0]+.18*normale[1]+.74*normale[2])
        gain=(calme+k, calme+.78*k, calme+(.07 if self.nuit else 0.)+.41*k)
        return tuple(min(255,max(0,round(v*a*ton*direction))) for v,a in zip(rgb,gain))

    def triangle(self, mat, a,b,c, rgb, tons=(1.,1.,1.)):
        u=tuple(q-p for p,q in zip(a,b)); v=tuple(q-p for p,q in zip(a,c))
        n=(u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
        l=sqrt(sum(i*i for i in n))
        if l<1e-8:
            return
        n=tuple(i/l for i in n)
        axe=max(range(3),key=lambda i:abs(n[i]))
        # UV en mètres pour conserver un grain continu du sol aux ombres de contact.
        uv_axes=((1,2),(0,2),(0,1))[axe]
        echelle={"bois":.78,"sol":.68,"lin":1.6,"velours":1.8}.get(mat,.84)
        def sommet(p,k):
            color=self.eclairer(p,n,mat,rgb,k)
            return (*self.rep.monde(p),*color,p[uv_axes[0]]*echelle,p[uv_axes[1]]*echelle)
        self.tris.append((mat,*(sommet(p,k) for p,k in zip((a,b,c),tons))))

    def quad(self, mat, a,b,c,d, couleur):
        self.triangle(mat,a,b,c,couleur)
        self.triangle(mat,a,c,d,couleur)

    def prisme(self, mat, contour, z0,z1, couleur):
        bas=[(*p,z0) for p in contour]; haut=[(*p,z1) for p in contour]
        for i in range(len(contour)):
            j=(i+1)%len(contour)
            self.quad(mat,bas[i],bas[j],haut[j],haut[i],couleur)
        # Les contours du mobilier sont convexes.
        for i in range(1,len(contour)-1):
            self.triangle(mat,haut[0],haut[i],haut[i+1],couleur)
            self.triangle(mat,bas[0],bas[i+1],bas[i],couleur)

    def boite(self, mat, x0,x1,y0,y1,z0,z1,rgb):
        self.prisme(mat,[(x0,y0),(x1,y0),(x1,y1),(x0,y1)],z0,z1,rgb)

    def barre(self,mat,a,b,largeur,z0,z1,rgb):
        dx,dy=b[0]-a[0],b[1]-a[1]
        l=hypot(dx,dy)
        if l<.001:
            return
        qx,qy=-dy*largeur/(2*l),dx*largeur/(2*l)
        self.prisme(mat,[(a[0]-qx,a[1]-qy),(b[0]-qx,b[1]-qy),
                         (b[0]+qx,b[1]+qy),(a[0]+qx,a[1]+qy)],z0,z1,rgb)

    def tour(self, mat, x,y, profil, rgb, n=10, caps=(False,True)):
        anneaux=[[(a,b,z) for a,b in cercle(x,y,r,n)] for r,z in profil]
        for bas,haut in zip(anneaux,anneaux[1:]):
            for i in range(n):
                j=(i+1)%n
                self.quad(mat,bas[i],bas[j],haut[j],haut[i],rgb)
        for ring,garder,reverse in ((anneaux[0],caps[0],True),(anneaux[-1],caps[1],False)):
            if garder:
                for i in range(1,n-1):
                    a,b=ring[i],ring[i+1]
                    self.triangle(mat,ring[0],*((b,a) if reverse else (a,b)),rgb)

    def surface_grille(self, mat, a,b,c, rgb, pas):
        # Les grands plans reçoivent plusieurs sommets dans chaque foyer de lumière.
        n=max(1,ceil(max(dist(a,b),dist(b,c),dist(c,a))/pas))
        def point(i,j):
            return tuple(a[h]+(b[h]-a[h])*i/n+(c[h]-a[h])*j/n for h in range(3))
        for i in range(n):
            for j in range(n-i):
                self.triangle(mat,point(i,j),point(i+1,j),point(i,j+1),rgb)
                if i+j+1<n:
                    self.triangle(mat,point(i+1,j),point(i+1,j+1),point(i,j+1),rgb)

    def ombre(self,x,y,rx,ry):
        # Le bord reprend le matériau ET les UV du sol sous les meubles.
        z=SOL+.006
        anneaux=[(x,y,z)]
        inner=[(*p,z) for p in cercle(x,y,rx*.55,12,ry*.55)]
        outer=[(*p,z) for p in cercle(x,y,rx,12,ry)]
        for i in range(12):
            j=(i+1)%12
            self.triangle("sol",anneaux[0],inner[i],inner[j],PIERRE,(.45,.63,.63))
            self.triangle("sol",inner[i],outer[i],outer[j],PIERRE,(.63,1.,1.))
            self.triangle("sol",inner[i],outer[j],inner[j],PIERRE,(.63,1.,.63))


def enveloppe(h):
    rep=h.rep
    sud=rep.front[0][1]; ouest=rep.front[-1][0]
    fond=[(ouest,FOND_RETOUR),(FOND_RUE,FOND_RETOUR),(FOND_RUE,sud)]
    contour=[*rep.front,*fond]
    for mat,z,n,rgb,pas in (("sol",SOL,(0,0,1),PIERRE,2.95),
                             ("platre",PLAFOND,(0,0,-1),(184,169,145),3.85)):
        for a,b,c in _poly([(*p,z) for p in contour],n):
            h.surface_grille(mat,a,b,c,rgb,pas)
    fond=[rep.front[-1],*fond,rep.front[0]]
    for a,b in zip(fond,fond[1:]):
        # Ce mur à face réelle est regardé depuis l'intérieur du L.
        bas,hauts=((*a,SOL),(*b,SOL)),((*a,PLAFOND),(*b,PLAFOND))
        for x,y,z in ((bas[1],bas[0],hauts[0]),(bas[1],hauts[0],hauts[1])):
            h.surface_grille("platre",x,y,z,ENDUIT,2.65)
        h.barre("bois",a,b,.12,SOL,.36,NOYER)
        h.barre("laiton",a,b,.09,.36,.40,BRONZE)
        h.barre("platre",a,b,.17,3.29,3.48,(171,139,105))
        h.barre("laiton",a,b,.13,3.28,3.31,BRONZE)
    # Lignes incrustées dans l'entrée. Elles s'arrêtent avant la réception.
    for y in (-1.59,1.59):
        h.barre("laiton",(-2.70,y),(-.12,y),.026,SOL+.008,SOL+.014,BRONZE)


def ouvertures(h, porte_ouverte=False):
    vus=[]
    for a,b,haut in h.rep.baies:
        dx,dy=b[0]-a[0],b[1]-a[1]; l=hypot(dx,dy)
        nx,ny=dy/l,-dx/l
        p=(a[0]-.045*nx,a[1]-.045*ny)
        q=(b[0]-.045*nx,b[1]-.045*ny)
        h.quad("verre",(*p,SOL),(*q,SOL),(*q,haut-.03),(*p,haut-.03),(181,200,191))
        h.barre("metal",p,q,.07,SOL,SOL+.075,(65,73,65))
        h.barre("metal",p,q,.07,haut-.075,haut,(68,71,62))
        for v in (p,q):
            if any(dist(v,existant)<.09 for existant in vus):continue
            vus.append(v)
            h.boite("metal",v[0]-.031,v[0]+.031,v[1]-.032,v[1]+.032,SOL,haut,(64,69,60))
    debut_porte=len(h.tris)
    a,b,haut=h.rep.porte
    y0,y1=sorted((a[1],b[1])); axe=-.045; centre=(y0+y1)/2
    for y in (y0+.055,centre-.043,centre+.043,y1-.055):
        h.boite("laiton",axe-.055,axe+.032,y-.038,y+.038,SOL,2.69,BRONZE)
    for ylo,yhi in ((y0+.09,centre-.09),(centre+.09,y1-.09)):
        for z,ep in ((SOL+.01,.125),(2.56,.09)):
            h.boite("metal",axe-.05,axe+.03,ylo,yhi,z,z+ep,(79,77,63))
        h.quad("verre",(axe,ylo,SOL+.14),(axe,yhi,SOL+.14),(axe,yhi,2.56),(axe,ylo,2.56),(185,202,191))
    h.boite("laiton",axe-.04,axe+.027,y0,y1,2.65,2.71,BRONZE)
    h.quad("verre",(axe,y0,2.71),(axe,y1,2.71),(axe,y1,haut-.055),(axe,y0,haut-.055),(181,196,184))
    for y in (centre-.20,centre+.20):
        for z in (1.02,1.41):
            h.boite("laiton",axe+.015,axe+.14,y-.028,y+.028,z-.021,z+.021,LAITON)
        h.tour("laiton",axe+.14,y,[(.024,.997),(.025,1.43)],LAITON,8)

    if porte_ouverte:
        # Une seule charnière entraîne le verre, les deux traverses, la poignée
        # et les montants de ce battant. L'imposte et le vantail nord sont fixes.
        gond=y0+.055
        for i in range(debut_porte,len(h.tris)):
            mat,*verts=h.tris[i]
            points=[h.rep.local(v[:3]) for v in verts]
            if min(q[2] for q in points)>=2.645 or sum(q[1] for q in points)>=3*centre:
                continue
            deplaces=[]
            for (x,y,z),ancien in zip(points,verts):
                dx,dy=x-axe,y-gond
                pos=(axe+dx*cos(ANGLE_PORTE)-dy*sin(ANGLE_PORTE),
                     gond+dx*sin(ANGLE_PORTE)+dy*cos(ANGLE_PORTE),z)
                deplaces.append((*h.rep.monde(pos),*ancien[3:]))
            h.tris[i]=(mat,*deplaces)



def luminaire(h,x,y,z,rayon,pendant=False):
    if pendant:
        h.tour("laiton",x,y,[(.036,z+.15),(.026,PLAFOND-.09),(.10,PLAFOND-.055),
                             (.13,PLAFOND-.015)],BRONZE,8,(False,False))
    else:
        h.tour("laiton",x,y,[(rayon*.82,z-.51),(rayon*.94,z-.475),(.055,z-.425),
                             (.037,z-.16),(.09,z-.115)],LAITON,9,(False,False))
    # Une lentille en opaline en six latitudes, avec deux bagues opaques en laiton.
    h.tour("lumiere",x,y,[(.05,z-.135),(rayon*.85,z-.095),(rayon,z-.018),
                          (rayon*.98,z+.040),(rayon*.67,z+.135),(.065,z+.175)],OPALE,10,(True,False))
    h.tour("laiton",x,y,[(rayon*1.008,z-.023),(rayon*1.008,z+.001)],BRONZE,10,(False,False))
    h.tour("laiton",x,y,[(.09,z+.148),(.07,z+.196)],LAITON,8)


def reception(h):
    x,y=-3.72,1.00
    h.ombre(x,y,.91,2.83)
    def plateau(mat,hx,hy,rayon,z0,z1,rgb):
        h.prisme(mat,arrondi(x,y,hx,hy,rayon,3),z0,z1,rgb)
    plateau("bois",.57,2.43,.30,SOL,.29,(69,49,41))
    plateau("bois",.66,2.50,.37,.27,1.20,ACAJOU)
    plateau("laiton",.674,2.52,.38,.35,.39,BRONZE)
    plateau("sol",.73,2.57,.39,1.18,1.26,(210,195,158))
    plateau("laiton",.695,2.54,.38,1.148,1.18,LAITON)
    # Nervures en demi-rond, y compris de chaque côté du cartouche central.
    for i in range(22):
        yc=y-2.10+i*.20
        if abs(yc-y)<.59:continue
        # Seul le demi-rond devant le panneau est visible.
        bord=[(x+.655+.053*cos(j*pi/3-pi/2),yc+.053*sin(j*pi/3-pi/2)) for j in range(4)]
        for a,b in zip(bord,bord[1:]):
            h.quad("bois",(*a,.40),(*b,.40),(*b,1.145),(*a,1.145),
                   nuance((151,91,51),.86+.10*(i%3)))
    h.boite("laiton",x+.65,x+.69,y-.59,y+.59,.48,1.10,BRONZE)
    h.boite("metal",x+.692,x+.704,y-.56,y+.56,.50,1.08,(47,83,75))
    # Éventail géométrique en laiton sur le panneau de façade du comptoir.
    for i in range(-3,4):
        y1=y+i*.138
        z1=1.009-.028*abs(i)
        h.quad("laiton",(x+.707,y-.018,.55),(x+.707,y+.018,.55),
                        (x+.707,y1+.012,z1),(x+.707,y1-.012,z1),LAITON)
    # Le casier est réellement creux. Les cloisons portent des clefs séparées du fond.
    bx=FOND_RUE+.090
    h.boite("bois",bx,bx+.105,-.68,3.86,1.23,2.49,(86,53,40))
    for z in (1.24,1.63,2.02,2.43):
        h.boite("bois",bx+.10,bx+.355,-.73,3.91,z,z+.047,(146,87,53))
        h.boite("laiton",bx+.352,bx+.363,-.71,3.89,z+.009,z+.026,BRONZE)
    taille=.64
    for i in range(8):
        cy=-.65+i*taille
        h.boite("bois",bx+.09,bx+.33,cy-.018,cy+.018,1.28,2.46,NOYER)
    for i,rang in ((0,0),(0,2),(1,1),(2,0),(2,2),(3,1),(4,2),(5,0),(5,1),(6,2)):
        cy=-.65+(i+.5)*taille+(.065 if i%2 else -.08)
        z=1.45+rang*.39
        h.boite("laiton",bx+.12,bx+.155,cy-.012,cy+.012,z-.035,z+.108,LAITON)
        h.boite("metal",bx+.14,bx+.167,cy-.042,cy+.043,z-.065,z-.010,(143,110,59))
    # Registre posé entrouvert et timbre de réception à silhouette distincte.
    h.prisme("bois",arrondi(x+.07,-.10,.22,.31,.035,2,-.20),1.26,1.30,(71,52,40))
    h.prisme("lin",arrondi(x+.065,-.10,.204,.29,.024,2,-.20),1.30,1.336,(194,154,100))
    h.tour("laiton",x+.30,.78,[(.111,1.26),(.118,1.285),(.094,1.295),(.080,1.345),
                                (.022,1.385)],LAITON,12)
    luminaire(h,-3.56,-.68,1.77,.252)
    luminaire(h,-3.66,2.79,2.23,.336,True)
    # Deux appliques sur la boiserie arrière éclairent le même casier.
    h.boite("bois",FOND_RUE+.03,FOND_RUE+.14,-.98,-.79,1.41,2.69,NOYER)
    for cy in (-.84,4.03):
        h.boite("laiton",bx,bx+.20,cy-.071,cy+.071,1.69,2.38,BRONZE)
        h.boite("lumiere",bx+.202,bx+.23,cy-.048,cy+.048,1.77,2.31,OPALE)


def fauteuil(h,x,y,orientation,teinte):
    def pos(a,b,z):
        return (x+a*cos(orientation)-b*sin(orientation),
                y+a*sin(orientation)+b*cos(orientation),z)
    def assise(mat,hx,hy,r,z0,z1,rgb):
        h.prisme(mat,arrondi(x,y,hx,hy,r,3,orientation),z0,z1,rgb)
    h.ombre(x,y,.76,.68)
    for a in (-.31,.32):
        for b in (-.36,.36):
            px,py,_=pos(a,b,0)
            h.tour("laiton",px,py,[(.041,SOL),(.053,.30)],BRONZE,6)
    assise("bois",.51,.52,.21,.27,.37,NOYER)
    assise("velours",.49,.49,.21,.35,.53,teinte)
    assise("velours",.46,.47,.20,.53,.564,nuance(teinte,1.13))
    # Le dossier enveloppe l'assise. L'accoudoir descend vers les deux extrémités.
    stations=[]
    for i in range(15):
        ang=(64+232*i/14)*pi/180
        haut=.695+.39*((1-cos(ang))/2)**1.6
        c,s=cos(ang),sin(ang)
        stations.append((pos(.60*c,.61*s,.35),pos(.60*c,.61*s,haut),
                         pos(.575*c,.584*s,haut+.045),pos(.489*c,.503*s,haut+.032),
                         pos(.468*c,.483*s,haut-.025),pos(.468*c,.483*s,.39)))
    for a,b in zip(stations,stations[1:]):
        for i,k in enumerate((.74,.96,1.17,1.05,.88,.70)):
            j=(i+1)%6
            h.quad("velours",a[i],b[i],b[j],a[j],nuance(teinte,k))
    for section,reverse in ((stations[0],True),(stations[-1],False)):
        points=section[::-1] if reverse else section
        for j in range(1,len(points)-1):
            h.triangle("velours",points[0],points[j],points[j+1],teinte)


def plante(h,x,y,taille=1):
    h.ombre(x,y,.49,.47)
    h.tour("sol",x,y,[(.26,SOL),(.31,.18),(.39,.71),(.40,.76),(.35,.78)],(145,117,92))
    h.tour("laiton",x,y,[(.385,.67),(.395,.70)],BRONZE,10,(False,False))
    # Chaque lame a une nervure et deux plis visibles des deux côtés.
    for i in range(14):
        ang=i*2.39996
        lon=(.48+.19*sin(1.47*i))*taille
        haute=(.95+.33*cos(2.09*i))*taille
        c,s=cos(ang),sin(ang)
        def p(r,v,z):
            return (x+r*c-v*s,y+r*s+v*c,.73+z)
        base=p(.035,0,0); centre=p(.45*lon,0,.77*haute)
        pointe=p(lon,0,haute)
        g=p(.52*lon,.045,.67*haute); d=p(.52*lon,-.045,.67*haute)
        couleurs=((42,78,48),(53,102,56),(76,110,63))
        for j,(a,b,q) in enumerate(((base,d,centre),(base,centre,g),
                                     (d,pointe,centre),(centre,pointe,g))):
            rgb=couleurs[(i+j)%3]
            h.triangle("lin",a,b,q,rgb)
            h.triangle("lin",q,b,a,nuance(rgb,.74))


def salon(h):
    fauteuil(h,-2.18,6.67,2.46,(52,111,91))
    fauteuil(h,-4.13,8.19,-.56,(57,104,93))
    x,y=-3.22,7.35
    h.ombre(x,y,.59,.54)
    h.tour("laiton",x,y,[(.28,SOL),(.32,.17),(.09,.22),(.067,.55),(.20,.58)],BRONZE)
    h.tour("bois",x,y,[(.47,.57),(.49,.595),(.47,.63)],(137,84,51),12)
    h.prisme("lin",arrondi(x+.075,y-.055,.13,.18,.012,2,.3),.632,.657,(194,157,111))
    h.tour("sol",x-.16,y+.06,[(.053,.63),(.070,.69),(.035,.765)],(141,121,94),9)
    luminaire(h,-3.02,7.64,2.29,.41,True)
    plante(h,-.95,5.37,1.03)
    # Petit salon de lecture sur le retour : une console, une lampe et des revues.
    # Ce retour reste ouvert vers la réception et le coin des deux fauteuils.
    x,y=-12.7,5.28
    h.ombre(x,y,1.36,.48)
    h.boite("bois",x-1.21,x+1.21,y-.36,y+.36,.77,.88,ACAJOU)
    for dx in (-1.07,1.07):
        h.boite("bois",x+dx-.065,x+dx+.065,y-.29,y+.29,SOL,.77,NOYER)
    h.boite("laiton",x-1.19,x+1.19,y+.34,y+.363,.79,.82,BRONZE)
    luminaire(h,-12.74,5.26,1.39,.245)
    for i in range(3):
        h.boite("lin",x+.48,x+.88,y-.18,y+.11,.88+i*.037,.914+i*.037,
                ((141,99,73),(101,121,107),(159,147,113))[i])
    # Relief de plâtre mural en gradins dans la bibliothèque, entièrement en volume.
    for i in range(-4,5):
        a=abs(i)
        h.boite("platre",x+i*.38-.17,x+i*.38+.17,FOND_RETOUR+.03,FOND_RETOUR+.13,
                1.19+.09*a,2.99-.15*a,(176,143,109))
        h.boite("laiton",x+i*.38-.018,x+i*.38+.018,FOND_RETOUR+.132,FOND_RETOUR+.15,
                1.25+.09*a,2.89-.15*a,BRONZE)
    # Le bout sud réchauffe la vue de la seconde baie par un écran et une suspension.
    for i in range(10):
        cy=-10.37+i*.28
        h.boite("bois",FOND_RUE+.045,FOND_RUE+.22,cy-.044,cy+.044,.37,2.84,ACAJOU)
    luminaire(h,-3.40,-8.60,2.58,.35,True)
    plante(h,-3.98,-8.49,1.13)


def construire_hall(surface,nuit=False,porte_ouverte=False):
    """Renvoie des triangles RenderWare par matériau, dans le repère du DFF original."""
    h=Hall(Repere.lire(surface),nuit)
    enveloppe(h)
    ouvertures(h,porte_ouverte)
    reception(h)
    salon(h)
    return h.tris
