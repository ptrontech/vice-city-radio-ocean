"""Fenêtres repérées sur les matériaux PC composites, exprimées en coordonnées UV."""
from math import ceil,floor
from struct import unpack_from
import re

from releve_facades_ville import local,monde

# Les atlas ne sont pas reproduits. Seules ces coordonnées sont appliquées
# si les UV des deux triangles correspondent effectivement au cadrage d'origine.
REGIONS={
    "villadarkwind512": ((.060,.075,.277,.258),(.419,.076,.619,.255),(.777,.09,.925,.283),
                         (.076,.639,.289,.879),(.452,.630,.774,.886)),
    "huswin2562hi": ((.291,.256,.773,.719),),
    "grewin256hi": ((.115,.435,.866,.711),),
    "peshutwin1256hi": ((.384,.205,.617,.573),),
    "abluwin": ((.061,.041,.926,.221),),
    "dt_posh_hotel_window": ((.059,.13,.406,.883),(.563,.13,.909,.883)),
    "ci_manswin1": ((.418,.343,.610,.755),),
    "ci_manswin1bl": ((.418,.343,.610,.755),),
    "decowindow1_2256": ((.217,.328,.805,.878),),
}
# Relevés sur la copie PC : panneaux d'enduit, tableaux multiples indissociables,
# volets peints, fresques et devantures existantes déjà transparentes.
ENDUIT={"wallwhtwind256","wallwind128","dt_yellowwin2","sjmwin2f","alleyandwindow256"}
PIECES={"residentialwin4_256","residentialwin1_256","villadarkwind512",
        "dt_posh_hotel_window","ci_manswin1","ci_manswin1bl","decowindow1_2256","acwindow1256","dt_greenwindow"}
PROTEGES=re.compile(r"seethr|stain|classiclogo|door|neon|sign|displayad|broken")


def diviser(baie,xyz,uv):
    """Résout l'affinité UV→plan métrique, y compris miroir, carrelage et rotation."""
    region=REGIONS.get(baie["nom"])
    if not region:
        return [baie]
    loc=[local(p,baie) for p in xyz]
    xy=[(q[0],q[2]) for q in loc]
    du1,dv1=(uv[1][k]-uv[0][k] for k in (0,1))
    du2,dv2=(uv[2][k]-uv[0][k] for k in (0,1))
    det=du1*dv2-du2*dv1
    if abs(det)<1e-7:
        return []
    def vers_plan(u,v):
        s=((u-uv[0][0])*dv2-(v-uv[0][1])*du2)/det
        t=(du1*(v-uv[0][1])-dv1*(u-uv[0][0]))/det
        return tuple(xy[0][k]+s*(xy[1][k]-xy[0][k])+t*(xy[2][k]-xy[0][k]) for k in (0,1))
    # Le quatrième coin est obtenu par affinité des UV vers les deux axes du panneau.
    xy0=vers_plan(0,0);u1=vers_plan(1,0);v1=vers_plan(0,1)
    axe_u=[u1[i]-xy0[i] for i in (0,1)];axe_v=[v1[i]-xy0[i] for i in (0,1)]
    if min(abs(v) for v in axe_u)>.035*max(abs(v) for v in axe_u) or min(abs(v) for v in axe_v)>.035*max(abs(v) for v in axe_v):
        return []
    a,b=baie["uv_bornes"];result=[]
    if ceil(b[0])-floor(a[0])>10 or ceil(b[1])-floor(a[1])>10:
        return []
    for iu in range(floor(a[0]),ceil(b[0])):
        for iv in range(floor(a[1]),ceil(b[1])):
            for u0,v0,u1,v1 in region:
                coins=[vers_plan(iu+u,iv+v) for u in (u0,u1) for v in (v0,v1)]
                x0,z0=map(min,zip(*coins));x1,z1=map(max,zip(*coins))
                if x0<-.025 or z0<-.025 or x1>baie["largeur"]+.025 or z1>baie["hauteur"]+.025:
                    continue
                if x1-x0<.58 or z1-z0<.53:
                    continue
                result.append(dict(baie,centre=monde(((x0+x1)/2,0,z0),baie),largeur=x1-x0,hauteur=z1-z0,
                                   repetitions=1.,sous_baie=True))
    return result


def profil_raster(data):
    """Transparence et couleur moyenne du vrai raster, obtenues sur ses blocs BC."""
    opaque=not bool(unpack_from("<I",data,76)[0]) and data[87] not in (3,5)
    if data[87] not in (1,3,5) or len(data)<104:
        return opaque,None
    n=unpack_from("<I",data,88)[0]
    stride=8 if data[87]==1 else 16
    if n<stride or len(data)<92+n:
        return opaque,None
    total=[0,0,0];nombre=0
    for i in range(0,n//stride,max(1,(n//stride)//37)):
        offset=92+i*stride+(0 if stride==8 else 8)
        a,b=unpack_from("<HH",data,offset)
        for v in (a,b):
            total[0]+=((v>>11)&31)*255/31;total[1]+=((v>>5)&63)*255/63;total[2]+=(v&31)*255/31
            nombre+=1
    return opaque,tuple(round(x/nombre) for x in total)
