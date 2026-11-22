"""Reconnaissance des baies et des murs à partir de la géométrie PC de Vice City."""
from collections import defaultdict
from math import hypot
import re

from collision_hall_majestic import Collision


# Meubles, véhicules, voies, accessoires et arbres utilisent parfois les mêmes
# matériaux que les bâtiments. Les protéger avant d'examiner les murs.
MOBILIER = re.compile(r"(?:^lod|_lod|^veg|palm|tree|shrub|bush|hedge|plant|grass|railtrack|liftplat|crane|cranewin|baseball|butterf|roadsect|roadseg|road_?\d|alleyroad|coast|beach_?sand|wave|jetty|bollard|fence|gatebar|barrier|train|tram|truck|jumbo|learjet|vehic|yacht|sail|buoy|cargoshp|crgoshp|rustship|dockship|boat(?:yard)?(?:_?hull|deck)|barge|billboard|stadlight|lightpole|lamppost|trafficli|flyover|walkway|handrail|gatestand|_signs?\d|pavement|carwreck|scaffold|bunting|footbridge|_props?[\d_]|interior|_int(?:erior)?[\d_]*$)")
EDIFICE = re.compile(r"build|block|blk|hotel|hote|house|hous|apart|tower|office|hospital|bld|shop|shp|shack|store|club|barber|garage|warehouse|wareh|hanga|term|depot|factor|school|bank|station|villa|mansion|manor|inn|condo|resid|stad|church|chapel|police|museum|diner|cafe|restaurant|pizz|market|pub|casino|cinema|marina|mall|drugstor|booth|factory|firest|printwork")
MATFEN = re.compile(r"window|(?:^|_)(?:win|wnd|gls)[_0-9]|win(?:dows?|dow|d[0-9]|_[a-z0-9]|[1-9])|(?:resid|h[oau]s|hotel|office|shop|shut|apt|deco)[a-z]*win|(?:^|[_a-z])glas[sz]|vitrine|warewin|[a-z]win(?:[0-9]|$)")
HORSFEN = re.compile(r"wine|glass_fence|stained|twink|windmach|windmill|turbine|cabinet|bottl|glassfloor|glassroof|glassdoor|_door|br[o0]ken|shadow|sign|billboard|poster|windshield|clock|shards|acunit|windblank|blankwin|flower.fence")
MUR = re.compile(r"brick|stucco|plaster|marble|(?:(?:white|pink|grey|cream|green|yellow|plain|brown|cement|concrete|hotel|ware|brick|blue|stone|corrug)[a-z_0-9]*wall)|(?:^|_)wall(?:[\d_]|white|green|blue|grey|pink|plain)|wall(?:tex|ext|brick)|^concretemanky|cladding|^corugwall|cementwall|^topwall")
HORSMUR = re.compile(r"door|sign|poster|ground|pave|dockwall|sea_wall|seawall|retaining|graff|tilefloor|stain|shadow|ceiling|_int|intwall|wallpaper|advert|road|fence|tunnel|billboard|graff")
VITRINE = re.compile(r"shopwind|storefront|carshowwin|vitrine|showcase|displaywin|shopglas|commercialwin")
VITRENETTE = re.compile(r"^hotelwindow[12]$|^shopwindow(?:low|high)\d?_|^warehousewin|^warewin[1-9]$|^alleywin[1-9]$|^huswin$|^window\d+[a-z_0-9]*$|^airportwindow|^glas[sz]_?win|^(?:cream|white|green|grey|turq|tide|litegrey|big_?)win[1-9]$|^carshowwin|^dt_fstation_window|^firestation_window|^restwin|^warehousewindow|^win_?\d+|^ml_wind[12]$|^windowhavb|^hotelwin_nt")
PROTEGER = {"od_majestic2c_dy","od_majestic2c_nt"}


def aire_mat(nom):
    if MATFEN.search(nom) and not HORSFEN.search(nom):
        return "fenetre"
    if MUR.search(nom) and not HORSMUR.search(nom):
        return "mur"
    return ""


def famille(nom, mats, quartier):
    contexte=nom+" "+" ".join(mats)
    if re.search(r"wareh|hangar|facto|works|freight|terminal|industrial|garage|warewin",contexte):
        return "industriel"
    if re.search(r"police|school|library|civic|church|stadium|hospital|firest|museum",contexte):
        return "public"
    if re.search(r"store|shop|mall|trader|market|cafe|pizza|diner|restaurant|salon|hair|cinema|drug",contexte):
        return "commerce"
    if re.search(r"office|offc|offic|skysc|bank|financ",contexte):
        return "bureau"
    if quartier in ("oceandrv","oceandn","washintn","washints","nbeachbt","nbeachw","nbeach") and re.search("deco|hotel|inn|tide|beach|hote",contexte):
        return "deco"
    return "habitation"


def arrondir(p):
    return tuple(round(v,3) for v in p)


def coins_rectangle(a,b):
    """Deux triangles doivent dessiner un vrai rectangle vertical avec diagonale commune."""
    coins=sorted(set(map(arrondir,(*a,*b))),key=lambda p:(p[2],p[0],p[1]))
    if len(coins)!=4:
        return None
    p,q,r,s=coins
    if abs(q[2]-p[2])>.060 or abs(s[2]-r[2])>.060:
        return None
    largeur=hypot(q[0]-p[0],q[1]-p[1])
    hauteur=(s[2]+r[2]-p[2]-q[2])*.5
    if largeur<.64 or hauteur<.61 or largeur>82 or hauteur>48:
        return None
    if min(max(hypot(p[0]-c[0],p[1]-c[1]),hypot(q[0]-d[0],q[1]-d[1])) for c,d in ((r,s),(s,r)))>.075:
        return None
    u=tuple(a[1][i]-a[0][i] for i in range(3));v=tuple(a[2][i]-a[0][i] for i in range(3))
    nx,ny=u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2]
    n=hypot(nx,ny)
    if n<.01 or abs(u[0]*v[1]-u[1]*v[0])>.04*n:
        return None
    nx,ny=nx/n,ny/n
    return (sum(c[0] for c in coins)/4,sum(c[1] for c in coins)/4,(p[2]+q[2])/2), (nx,ny), largeur,hauteur


def rectangles(surface, uv):
    pos=surface["positions"];faces=surface["triangles"];mats=surface["materiaux"]
    genres=[aire_mat(m) for m in mats]
    diagonales=defaultdict(list)
    for i,(a,b,c,m) in enumerate(faces):
        if not genres[m]:
            continue
        pts=[pos[a],pos[b],pos[c]]
        for j,k in ((0,1),(1,2),(2,0)):
            u,v=pts[j],pts[k]
            if abs(u[2]-v[2])<.60 or hypot(u[0]-v[0],u[1]-v[1])<.62:
                continue
            diagonales[(m,*sorted((arrondir(u),arrondir(v))))].append(i)
    utilises=set()
    for (m,*_),refs in diagonales.items():
        if len(refs)!=2 or any(i in utilises for i in refs):
            continue
        a,b=[[pos[k] for k in faces[i][:3]] for i in refs]
        result=coins_rectangle(a,b)
        if not result:
            continue
        centre,n,w,h=result
        unites=[uv[k] for i in refs for k in faces[i][:3]]
        uv_bornes=tuple(min(q[k] for q in unites) for k in (0,1)),tuple(max(q[k] for q in unites) for k in (0,1))
        repetitions=max(uv_bornes[1][k]-uv_bornes[0][k] for k in (0,1))
        utilises.update(refs)
        yield {"faces":list(refs),"materiau":m,"nom":mats[m],"genre":genres[m],
               "centre":centre,"n":n,"largeur":w,"hauteur":h,"repetitions":repetitions,"uv_bornes":uv_bornes}


def local(p, baie):
    x,y,z=p;cx,cy,cz=baie["centre"];nx,ny=baie["n"]
    return (-(x-cx)*ny+(y-cy)*nx+baie["largeur"]/2, -(x-cx)*nx-(y-cy)*ny, z-cz)


def monde(p, baie):
    x,y,z=p;cx,cy,cz=baie["centre"];nx,ny=baie["n"]
    u=x-baie["largeur"]/2
    return (cx-ny*u-nx*y,cy+nx*u-ny*y,cz+z)


def encadre(points):
    return tuple(min(p[i] for p in points) for i in range(3)),tuple(max(p[i] for p in points) for i in range(3))


def recouvrent(a,b):
    return all(a[0][k]<=b[1][k] and a[1][k]>=b[0][k] for k in range(3))


def interieur_triangle(triangle, bornes):
    """Intersection exacte du triangle avec la boîte à axes locaux, par clipping convexe."""
    poly=triangle
    for axe in (0,2,1):
        for borne,sens in ((bornes[0][axe],1),(bornes[1][axe],-1)):
            if not poly:
                return False
            neuf=[];a=poly[-1];d0=(a[axe]-borne)*sens
            for b in poly:
                d1=(b[axe]-borne)*sens
                if (d0>=0)!=(d1>=0):
                    f=d0/(d0-d1);neuf.append(tuple(x+f*(y-x) for x,y in zip(a,b)))
                if d1>=0:
                    neuf.append(b)
                a,d0=b,d1
            poly=neuf
    return bool(poly)


def prof_libre(baie, triangles, profondeurs):
    """Contrôle tout le prisme, y compris les cloisons obliques et le doublage coplanaire."""
    w,h=baie["largeur"],baie["hauteur"]
    tol=min(.045,w*.055,h*.055)
    zone=encadre([monde((u,d,v),baie) for u in (tol,w-tol) for d in (-.025,max(profondeurs)) for v in (tol,h-tol)])
    cibles=[]
    for indice,points,bbox in triangles:
        if indice not in baie["faces"] and recouvrent(zone,bbox):
            cibles.append([local(v,baie) for v in points])
    for d in profondeurs:
        if not any(interieur_triangle(tri,((tol,-.019,tol),(w-tol,d,h-tol))) for tri in cibles):
            return d
    return 0.


def geometrie_collision(blob):
    if not blob:
        return [],[]
    col=Collision(blob)
    faces=[]
    for a,b,c,*_ in col.faces:
        pts=col.points[a],col.points[b],col.points[c]
        faces.append((pts,encadre(pts)))
    return faces,[(b[:3],b[3:6]) for b in col.boites]


def barre_collision(baie, collision):
    """Un vitrage près du sol n’est évidé que si sa collision existante ferme déjà la baie."""
    w,h=baie["largeur"],baie["hauteur"]
    pts=[monde((x*w,d,z*h),baie) for x in (.18,.82) for d in (-.30,.33) for z in (.22,.8)]
    zone=encadre(pts)
    faces,boites=collision
    for box in boites:
        if recouvrent(zone,box):
            centre=monde((w*.5,0,h*.53),baie)
            if all(box[0][k]-.18<=centre[k]<=box[1][k]+.18 for k in range(3)):
                return True
    for points,bbox in faces:
        if not recouvrent(zone,bbox):
            continue
        tri=[local(p,baie) for p in points]
        if max(p[1] for p in tri)-min(p[1] for p in tri)>.25+max(w,h)*.12:
            continue
        if interieur_triangle(tri,((.36*w,-.32,.32*h),(.64*w,.36,.72*h))):
            return True
    return False


def corniches_toit(surface):
    """Retourne exclusivement les arêtes horizontales réelles jointives du toit et d’une paroi."""
    pos=surface["positions"];faces=surface["triangles"];mats=surface["materiaux"]
    mini,maxi=encadre(pos)
    hauteur=maxi[2]-mini[2]
    if hauteur<3.25:
        return []
    seuil=mini[2]+.56*hauteur
    rives={}; flancs={}
    for i,(ia,ib,ic,m) in enumerate(faces):
        a,b,c=[pos[k] for k in (ia,ib,ic)]
        if max(a[2],b[2],c[2])<seuil:
            continue
        u=tuple(b[j]-a[j] for j in range(3));v=tuple(c[j]-a[j] for j in range(3))
        nx,ny,nz=u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]
        horizontal=hypot(nx,ny)
        est_toit=nz>0.02 and nz>1.15*horizontal
        est_mur=horizontal>.04 and abs(nz)<.18*horizontal
        if not est_toit and not est_mur:
            continue
        if re.search(r"decal|shadow|sign|advert|billboard|glass|fence|rail|poster|graf",mats[m]):
            continue
        for p,q in ((a,b),(b,c),(c,a)):
            w=hypot(q[0]-p[0],q[1]-p[1])
            if p[2]<seuil or abs(p[2]-q[2])>.080 or not 2.6<=w<=72:
                continue
            k=tuple(sorted((tuple(round(x,2) for x in p),tuple(round(x,2) for x in q))))
            if est_toit:
                rives[k]=True
            else:
                if min(a[2],b[2],c[2])>min(p[2],q[2])-.79:
                    continue
                centre=((p[0]+q[0])*.5,(p[1]+q[1])*.5,(p[2]+q[2])*.5)
                n=(nx/horizontal,ny/horizontal)
                if sum((centre[j]-(mini[j]+maxi[j])*.5)*n[j] for j in (0,1))<-.45:
                    continue
                h=min(2.15,max(.90,centre[2]-min(a[2],b[2],c[2])))
                flancs[k]={"faces":[],"materiau":m,"nom":mats[m],"genre":"mur",
                           "centre":(centre[0],centre[1],centre[2]-h),"n":n,
                           "largeur":w,"hauteur":h,"repetitions":0,"rive":True}
    return [flancs[k] for k in sorted(rives.keys() & flancs.keys())]
