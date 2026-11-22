"""Chambres en volume derrière les ouvertures de l’hôtel Majestic de Vice City.

Les UV décrivent des matières locales répétables. Chacune des 24 pièces a un sol,
un plafond, deux retours et un mur de fond. Le repère local est exprimé en mètres :
x de gauche à droite le long de la baie, y vers l’intérieur, z depuis son plancher.
"""
from itertools import combinations
from math import ceil, cos, hypot, pi, sin, sqrt

import relief_majestic


# Enduit, rideaux, revêtement du siège. Numéroter les pièces dans chaque aile
# permet de retrouver le même mobilier dans les deux modèles horaires.
PALETTES = (
    ((212, 184, 151), (111, 153, 139), (57, 99, 89)),
    ((198, 191, 164), (192, 152, 106), (115, 71, 62)),
    ((200, 157, 141), (204, 178, 138), (65, 98, 112)),
    ((186, 176, 154), (78, 121, 121), (134, 81, 64)),
    ((196, 185, 161), (133, 98, 100), (68, 103, 82)),
    ((176, 192, 175), (188, 161, 118), (95, 75, 92)),
)
BOIS = (137, 96, 65)
NOYER = (101, 70, 56)
LAITON = (169, 136, 85)
OMBRE = (73, 67, 64)
LIN = (207, 193, 166)
ECHELLE_UV = {"platre": .62, "bois": 1.05, "lin": 2.0, "laiton": .9,
              "velours": 1.55, "sol": .95, "lumiere": 1., "metal": .85}
PROGRAMMES_RUE = ("suite", "bureau", "lits", "salon", "volets", "lecture")
PROGRAMMES_AILES = ("bureau", "lecture", "repos", "salon", "volets", "lits")


def produit(a, b):
    return sum(x * y for x, y in zip(a, b))


def moins(a, b):
    return tuple(x - y for x, y in zip(a, b))


def croix(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def unitaire(v):
    norme = sqrt(produit(v, v))
    if norme < 1e-9:
        raise ValueError("Face de chambre dégénérée")
    return tuple(x/norme for x in v)


def couleur(base, facteur):
    return tuple(round(max(0, min(255, c*facteur))) for c in base)


def empreinte(piece):
    p, d = piece["ouverture"], piece["profondeur"]
    return [tuple(p["t"][k]*s + p["n"][k]*(p["d"]-y) for k in (0, 1))
            for s,y in ((p["s0"],.045), (p["s1"],.045), (p["s1"],d), (p["s0"],d))]


def chevauche(a, b):
    pa, pb = a["ouverture"], b["ouverture"]
    if min(pa["z1"], pb["z1"]) < max(pa["z0"], pb["z0"]) + .20:
        return False
    ca, cb = empreinte(a), empreinte(b)
    for axe in (pa["t"], pa["n"], pb["t"], pb["n"]):
        a0, a1 = min(produit(v, axe) for v in ca), max(produit(v, axe) for v in ca)
        b0, b1 = min(produit(v, axe) for v in cb), max(produit(v, axe) for v in cb)
        if min(a1,b1) - max(a0,b0) < .015:
            return False
    return True


def dispositions(surface):
    """Identité, enveloppe et usage de chaque pièce, stables entre le jour et la nuit."""
    indices = {i for i,nom in enumerate(surface["materiaux"]) if nom == "hotelwindow1"}
    if not any(face[3] in indices for face in surface["triangles"]):
        return []
    baies = relief_majestic._preparer(surface)["panneaux"]["hotelwindow1"]
    if not baies:
        return []
    coupe = (min(p["z0"] for p in baies) + max(p["z0"] for p in baies)) / 2
    groupes = {}
    for p in baies:
        nx, ny = p["n"]
        aile = (0 if nx >= 0 else 2) if abs(nx) >= abs(ny) else (1 if ny >= 0 else 3)
        groupes.setdefault((aile, int(p["z0"] > coupe + .3)), []).append(p)
    pieces = []
    for (aile, etage), baies_face in sorted(groupes.items()):
        for rang, p in enumerate(sorted(baies_face, key=lambda v:v["s0"])):
            indice = 6*aile + 3*etage + rang
            largeur = p["s1"] - p["s0"]
            profondeur = (3.06, 2.63, 2.91, 2.82, 2.34, 3.02)[(indice+2*aile) % 6]
            usage = PROGRAMMES_RUE[indice % 6] if aile == 0 else PROGRAMMES_AILES[(indice + aile + etage) % 6]
            pieces.append(dict(indice=indice, aile=aile, etage=etage, rang=rang, ouverture=p,
                               largeur=largeur, profondeur=profondeur, usage=usage))
    # Deux ailes perpendiculaires se rencontrent près d’un angle de bâtiment.
    # Reculer leur fond à parts égales quand leurs emprises se rencontrent.
    for _ in range(24):
        conflit = False
        for a, b in combinations(pieces, 2):
            if a["aile"] != b["aile"] and chevauche(a, b):
                conflit = True
                a["profondeur"] = max(1.75, a["profondeur"]-.075)
                b["profondeur"] = max(1.75, b["profondeur"]-.075)
        if not conflit:
            break
    if any(chevauche(a,b) for a,b in combinations(pieces,2) if a["aile"] != b["aile"]):
        raise ValueError("Deux chambres d’angle occupent le même volume")
    return pieces


class Chambre:
    def __init__(self, description, nuit):
        self.plan = description
        self.p = description["ouverture"]
        self.id = description["indice"]
        self.w, self.d = description["largeur"], description["profondeur"]
        self.zsol = self.p["z0"] - (.48 if description["etage"] else .52)
        self.h = self.p["z1"] - self.zsol + .10
        self.nuit = nuit
        self.mur, self.tissu, self.assise = PALETTES[(self.id + 2*description["aile"]) % len(PALETTES)]
        self.lampes = []
        self.lumieres_hautes = []
        self.triangles = []

    def monde(self, x, y, z):
        s, d = self.p["s0"] + x, self.p["d"] - y
        return (s*self.p["t"][0] + d*self.p["n"][0],
                s*self.p["t"][1] + d*self.p["n"][1], self.zsol + z)

    def teinter(self, pos, normale, mat, base):
        x, y, z = pos
        if mat == "lumiere":
            return couleur(base, 1.0 if self.nuit else .86)
        lumiere = (.50 if self.nuit else .88) - (.14 if self.nuit else .13)*(y/self.d)
        lumiere += .035 * (z/self.h) + .065*max(0.,-normale[1]) + .04*max(0.,normale[2])
        if self.nuit:
            for lx, ly, lz in (*self.lampes, *self.lumieres_hautes):
                distance2 = (x-lx)**2 + (y-ly)**2 + .75*(z-lz)**2
                lumiere += .38 / (1 + 1.5*distance2)
        return couleur(base, lumiere)

    def face(self, mat, points, normale, base, uv=None):
        direction = unitaire(normale)
        v1, v2 = moins(points[1], points[0]), moins(points[2], points[0])
        croisement = croix(v1,v2)
        if produit(croisement,croisement) < 1e-12:
            raise ValueError("Triangle nul dans la chambre")
        # (tangente, profondeur intérieure, verticale) forme un repère indirect.
        inverser = produit(croisement,direction) > 0
        if uv is None:
            u = unitaire(v1)
            v = unitaire(croix(croisement,u))
            pas = ECHELLE_UV[mat]
            uv = [(produit(moins(p,points[0]),u)*pas, produit(moins(p,points[0]),v)*pas) for p in points]
        vertices = [(*self.monde(*p), *self.teinter(p,direction,mat,base), *coord) for p,coord in zip(points,uv)]
        for j in range(1,len(vertices)-1):
            a,b = (j+1,j) if inverser else (j,j+1)
            self.triangles.append((mat,vertices[0],vertices[a],vertices[b]))

    def bloc(self, mat, x0,x1,y0,y1,z0,z1, base, faces="agdhbs"):
        p=((x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),
           (x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1))
        cotes = (("a",(0,1,5,4),(0,-1,0)), ("g",(0,3,7,4),(-1,0,0)),
                 ("d",(1,2,6,5),(1,0,0)), ("h",(4,5,6,7),(0,0,1)),
                 ("b",(0,1,2,3),(0,0,-1)), ("s",(3,2,6,7),(0,1,0)))
        for tag,indices,n in cotes:
            if tag in faces:
                self.face(mat,[p[i] for i in indices],n,base)

    def cornets(self, mat, x,y,z,h,r0,r1,base, nombre=7, allume=False):
        bas,haut=[],[]
        for j in range(nombre):
            a=2*pi*j/nombre
            bas.append((x+r0*cos(a),y+r0*sin(a),z))
            haut.append((x+r1*cos(a),y+r1*sin(a),z+h))
        for j in range(nombre):
            k=(j+1)%nombre;a=(j+.5)*2*pi/nombre
            self.face(mat,[bas[j],bas[k],haut[k],haut[j]],(cos(a),sin(a),(r0-r1)/h),base)
        self.face(mat,haut,(0,0,1),base)
        if allume:
            self.face("lumiere",bas,(0,0,-1),(247,184,103))

    def coussin(self, mat, x,y,w,prof,z,h,base):
        # Couture biseautée, assise légèrement bombée à la jonction supérieure.
        anneau=lambda xx,yy,ww,pp,zz:[(xx,yy,zz),(xx+ww,yy,zz),(xx+ww,yy+pp,zz),(xx,yy+pp,zz)]
        bas=anneau(x,y,w,prof,z)
        haut=anneau(x+.045,y+.045,w-.09,prof-.09,z+h)
        for j,dir in enumerate(((0,-1,.35),(1,0,.35),(0,1,.35),(-1,0,.35))):
            k=(j+1)%4
            self.face(mat,[bas[j],bas[k],haut[k],haut[j]],dir,base)
        self.face(mat,haut,(0,0,1),base)

    def parois(self):
        w,d,h=self.w,self.d,self.h
        avant=.045
        self.face("sol",[(0,avant,0),(w,avant,0),(w,d,0),(0,d,0)],(0,0,1),(142,111,81))
        self.face("platre",[(0,avant,h),(w,avant,h),(w,d,h),(0,d,h)],(0,0,-1),(207,198,180))
        self.face("platre",[(0,avant,0),(0,d,0),(0,d,h),(0,avant,h)],(1,0,0),couleur(self.mur,.91))
        self.face("platre",[(w,avant,0),(w,d,0),(w,d,h),(w,avant,h)],(-1,0,0),couleur(self.mur,.95))
        self.face("platre",[(0,d,0),(w,d,0),(w,d,h),(0,d,h)],(0,-1,0),self.mur)
        self.bloc("bois", .025,w-.025, d-.035,d-.012, .025,.14,NOYER,"ah")
        self.bloc("platre", .025,w-.025, d-.066,d-.02, h-.15,h-.045,couleur(self.mur,1.05),"ab")
        if w>5.2:
            x=w*(.46 if self.id%2 else .52)
            longueur=min(d-.32,1.38+.12*(self.id%3))
            # Deux espaces distincts à partir du véritable trumeau intérieur.
            self.bloc("platre",x-.07,x+.07,.11,longueur,.015,h-.015,couleur(self.mur,.94),"agds")
            self.bloc("bois",x-.091,x+.091,.07,.115,.04,h-.04,NOYER,"agd")

    def rideau(self, droite, part, attache, mat="lin"):
        # Maillage du rideau avec plis dans la profondeur. L’embrasse et l’ourlet
        # déplacent réellement les sommets, même avec une texture entièrement unie.
        portee=min(self.w*.66, max(.50,self.w*part))
        n=max(6,min(14,ceil(portee/.13)))
        plis=3 if n<9 else 4
        zhaut=self.h-.14
        zbas=.22+.075*(self.id%3)
        niveaux=((zhaut,1.,.00),(zhaut-.20,.96,.015),((zhaut+zbas)*.48,.56 if attache else .98,.075),(zbas,1.03,.025))
        noeuds=[]
        for ip,(z,s,offset) in enumerate(niveaux):
            ligne=[]
            for j in range(n+1):
                f=j/n
                ab=.06+f*portee*s
                x=self.w-ab if droite else ab
                ondulation=sin(2*pi*plis*f + .12*ip)
                y=.255+offset+(.055+.024*(ip>0))*ondulation
                zz=z + (.035*cos(4*pi*f) if ip==3 else 0.)
                ligne.append((x,y,zz))
            noeuds.append(ligne)
        for i in range(3):
            for j in range(n):
                points=[noeuds[i][j],noeuds[i][j+1],noeuds[i+1][j+1],noeuds[i+1][j]]
                du=(points[1][0]-points[0][0],points[1][1]-points[0][1])
                normale=(du[1],-du[0],.04)
                if normale[1]>0:
                    normale=(-normale[0],-normale[1],normale[2])
                rvb=couleur(self.tissu,.86+.14*(.5+.5*cos(2*pi*plis*(j+.5)/n)))
                uv=[(j/n,1-i/3),((j+1)/n,1-i/3),((j+1)/n,1-(i+1)/3),(j/n,1-(i+1)/3)]
                self.face(mat,points,normale,rvb,uv)

    def persienne(self, droite, fraction, inclinaison):
        # Les lames tournent autour de leur axe horizontal. Le vitrage derrière
        # et le fond de chambre peuvent se voir entre deux lames.
        largeur=self.w*fraction
        x0=self.w-largeur-.065 if droite else .065
        x1=x0+largeur
        base=.20; haut=self.h-.20
        for x in (x0,x1-.055):
            self.bloc("bois",x,x+.055,.30,.395,base,haut,couleur(BOIS,.84),"agdh")
        self.bloc("bois",x0,x1,.30,.395,haut-.07,haut,BOIS,"agdb")
        self.bloc("bois",x0,x1,.30,.395,base,base+.07,BOIS,"agdh")
        nombre=12 if fraction>.43 else 10
        pas=(haut-base-.18)/nombre
        amplitude=pas*inclinaison
        for j in range(nombre):
            z=base+.11+j*pas
            pts=[(x0+.047,.282,z+.025),(x1-.047,.282,z+.025),
                 (x1-.047,.445,z+amplitude),(x0+.047,.445,z+amplitude)]
            self.face("bois",pts,(0,-amplitude,.163),couleur(BOIS,1.03))
            self.face("bois",[(x,y,zz-.027) for x,y,zz in pts],(0,amplitude,-.163),couleur(NOYER,.86))
            self.face("bois",[pts[0],pts[1],(pts[1][0],.282,z-.002),(pts[0][0],.282,z-.002)],(0,-1,0),NOYER)

    def lit(self, centre, largeur=1.36, couverture=True):
        d=self.d
        if d < 2.15:
            # Dans les angles étroits, un couchage de 1,90 m tient en travers.
            g=.23 if self.id%2 else self.w-2.13
            y0=d-.11-min(largeur,d-.63)
            prof=d-.11-y0
            self.bloc("bois",g,g+1.90,y0,d-.11,.18,.44,NOYER,"agd")
            self.coussin("lin",g,y0,1.90,prof,.44,.16,LIN)
            self.bloc("bois",g,g+.09,y0-.045,d-.065,.16,1.16,BOIS,"agdh")
            self.coussin("lin",g+.12,y0+.08,.38,prof-.16,.60,.10,LIN)
            if couverture:
                self.coussin("velours",g+1.29,y0, .54,prof,.59,.055,self.assise)
            return
        g=centre-largeur/2
        avant=max(.36,d-2.07)
        self.bloc("bois",g,g+largeur,avant,d-.12,.18,.44,NOYER,"agd")
        self.coussin("lin",g-.02,avant-.015,largeur+.04,d-avant-.13,.44,.16,LIN)
        self.bloc("bois",g-.08,g+largeur+.08,d-.16,d-.055,.16,1.10+.06*(self.id%3),BOIS,"agdh")
        if couverture:
            self.coussin("velours",g-.035,avant+.045,largeur+.07,.60,.59,.055,self.assise)
        if largeur>=1.2:
            for x in (g+.07,g+largeur/2+.02):
                self.coussin("lin",x,d-.59,largeur/2-.095,.37,.60,.10,LIN)
        else:
            self.coussin("lin",g+.07,d-.59,largeur-.14,.37,.60,.11,LIN)

    def fauteuil(self, x,y, largeur=.72):
        g=x-largeur/2
        self.bloc("bois",g+.06,g+largeur-.06,y+.07,y+.67,.14,.37,NOYER,"agds")
        self.coussin("velours",g,y,largeur,.63,.37,.16,self.assise)
        self.bloc("velours",g+.025,g+largeur-.025,y+.53,y+.69,.48,.94,self.assise,"agdh")
        for xx in (g-.045,g+largeur-.055):
            self.bloc("bois",xx,xx+.10,y+.08,y+.60,.52,.64,BOIS,"agdh")

    def bureau(self, x,largeur):
        g=x-largeur/2; d=self.d
        self.bloc("bois",g,g+largeur,d-.68,d-.12,.79,.90,BOIS,"agdhb")
        for xx in (g+.05,g+largeur-.14):
            self.bloc("bois",xx,xx+.09,d-.61,d-.20,.035,.79,NOYER,"agd")
        self.bloc("bois",g+.09,g+largeur-.09,d-.55,d-.31,.65,.78,BOIS,"agd")
        self.bloc("laiton",x-.12,x+.12,d-.57,d-.55,.70,.73,LAITON,"ah")

    def lampe(self, x,y,z, hauteur=.73):
        self.cornets("laiton",x,y,z,.07,.135,.105,LAITON,6)
        self.bloc("laiton",x-.026,x+.026,y-.026,y+.026,z+.07,z+hauteur*.68,LAITON,"agds")
        self.cornets("lin",x,y,z+hauteur*.63,hauteur*.37,.22,.115,(223,183,121),8,allume=True)

    def eclairage_haut(self):
        if not self.lumieres_hautes:
            return
        x,y,z = self.lumieres_hautes[0]
        if self.plan["usage"] in ("salon", "bureau"):
            # La suspension se lit également depuis le trottoir, contre le plafond.
            self.cornets("laiton",x,y,self.h-.065,.06,.095,.11,LAITON,6)
            self.bloc("laiton",x-.019,x+.019,y-.019,y+.019,z+.15,self.h-.055,LAITON,"agds")
            self.cornets("lin",x,y,z-.06,.25,.30 if self.id%2 else .23,.13,(231,190,134),8,allume=True)
        else:
            # Applique à deux étages, avec un retour visible sur l'enduit.
            self.bloc("bois",x-.145,x+.145,self.d-.09,self.d-.025,z-.29,z+.18,NOYER,"agdhb")
            self.bloc("laiton",x-.054,x+.054,y,self.d-.074,z-.165,z-.12,LAITON,"agdhb")
            self.cornets("laiton",x,y,z-.16,.09,.095,.13,LAITON,6)
            self.cornets("lin",x,y,z-.07,.24,.115,.17,(226,184,133),8,allume=True)

    def tete_cannelee(self, x, largeur):
        # Cannelures en relief du noyer, sur le mur au-dessus de certains lits.
        d=self.d
        self.bloc("bois",x-largeur/2,x+largeur/2,d-.108,d-.045,.74,2.04,BOIS,"agdh")
        for i in range(7):
            f=i/6
            xx=x+largeur*(f-.5)*.92
            sommet=1.85+.16*(1-abs(2*f-1))
            self.bloc("bois",xx-.016,xx+.016,d-.141,d-.106,.88,sommet,NOYER,"agdh")

    def etageres(self, x, largeur):
        d=self.d; g=x-largeur/2
        for j in range(2):
            z=1.43+.47*j
            self.bloc("bois",g,g+largeur,d-.27,d-.045,z,z+.055,BOIS,"ahbd")
            for k in range(2+(self.id+j)%3):
                xx=g+.09+k*.105
                h=.14+.045*((self.id+3*k+j)%4)
                self.bloc("lin",xx,xx+.075,d-.21,d-.065,z+.055,z+.055+h,
                          (99+11*k, 102+7*j, 87+4*k),"agdh")

    def meubler(self):
        w,d=self.w,self.d
        sens=self.id%2==0
        centre=lambda f: w*(f if sens else 1-f)
        usage=self.plan["usage"]
        if usage=="suite":
            self.lit(centre(.25),min(1.52,w*.37))
            self.tete_cannelee(centre(.25),min(1.62,w*.39))
            self.fauteuil(centre(.73),max(.78,d-1.54),.80)
            self.etageres(centre(.77),min(1.32,w*.36))
        elif usage=="lits":
            if w>5.2:
                self.lit(centre(.23),1.33)
                self.lit(centre(.75),1.08,False)
                self.tete_cannelee(centre(.75),1.27)
            else:
                self.lit(centre(.47),min(1.26,w*.55))
        elif usage=="bureau":
            self.bureau(centre(.53),min(1.78,w*.67))
            self.fauteuil(centre(.39),max(.57,d-1.80),.60)
            if self.id%3:
                self.etageres(centre(.65),min(.91,w*.31))
        elif usage=="salon":
            self.fauteuil(centre(.24),d-1.12,.78)
            self.fauteuil(centre(.72),max(.69,d-1.72),.67)
            self.etageres(centre(.28),min(1.34,w*.40))
        elif usage=="lecture":
            self.fauteuil(centre(.25),max(.68,d-1.57),.78)
            self.bureau(centre(.72),min(1.52,w*.43))
            self.etageres(centre(.70),min(.96,w*.32))
        elif usage=="repos":
            self.lit(centre(.46),min(1.45,w*.58),False)
            self.etageres(centre(.70),min(.76,w*.26))
        else:
            self.fauteuil(centre(.65),max(.64,d-1.28),.66)
            self.etageres(centre(.33),min(.82,w*.30))
        self.eclairage_haut()
        if self.lampes:
            lx,ly,lz=self.lampes[0]
            self.bloc("bois",lx-.20,lx+.20,ly-.19,ly+.19,.04,.84,NOYER,"agdh")
            self.lampe(lx,ly,.84)
        if usage=="volets":
            self.persienne(sens,.59,.88)
            self.rideau(not sens,.21,False)
        elif usage=="bureau":
            self.persienne(not sens,.28,.62)
        elif usage=="lecture":
            self.rideau(sens,.34,True,mat="velours")
        elif usage=="suite":
            self.rideau(False,.16,True)
            self.rideau(True,.31,False)
        elif usage=="lits":
            self.persienne(sens,.24,.78)
            if w>5.2:
                self.rideau(not sens,.13,True)
        elif usage=="salon":
            self.rideau(sens,.43,True)
        else:
            self.rideau(sens,.24,False)
            self.rideau(not sens,.15,True)

    def construire(self):
        if (self.id + self.plan["aile"])%5 != 4 and self.plan["usage"] != "volets":
            k=(self.id*7+1)%4
            self.lampes=[(self.w*(.14 if self.id%2 else .85),self.d-.42-.045*k,1.41)]
        if self.plan["usage"] in ("bureau","salon"):
            self.lumieres_hautes=[(self.w*(.66 if self.id%2 else .38),self.d*.65,self.h-.79-.12*(self.id%3))]
        elif self.plan["usage"] not in ("volets","repos") and (self.plan["aile"]==0 or self.id%3==0):
            self.lumieres_hautes=[(self.w*(.81 if self.id%2 else .33),self.d-.25,2.36+.14*(self.id%3))]
        self.parois()
        self.meubler()
        return self.triangles


def construire_chambres(surface, nuit=False):
    """Triangles texturés des chambres, compatibles avec le maillage intérieur de l’atelier."""
    return [triangle for plan in dispositions(surface) for triangle in Chambre(plan, nuit).construire()]
