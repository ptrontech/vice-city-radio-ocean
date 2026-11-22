// Angles mesurés aux ouvertures des modèles PC, dans le repère monde de l'IPL.
const plansFacadesVille=[
    {nom:"north-beach",id:4187,a:[460.259,768.066,13.592],b:[463.859,768.066,13.701],c:[462.059,772.916,13.519]},
    {nom:"little-havana",id:1216,a:[-1144.953,-366.153,17.113],b:[-1144.483,-369.722,17.185],c:[-1139.909,-367.305,17.065]},
    {nom:"downtown",id:1740,a:[-667.096,818.686,16.270],b:[-667.096,815.086,16.405],c:[-661.033,816.886,16.180]},
    {nom:"aeroport",id:1128,a:[-1354,-485.8,18.4],b:[-1354,-485.8,18.4],c:[-1332.7725,-495.0587,19.8543]}
];
const cameraFacadesVille={index:-1,charge:0,deb:null,heure:0};
function placerPlanFacades(v,f) {
    const l=f*f*(3-2*f);
    const position=v.a.map((a,i)=>a+l*(v.b[i]-a));
    N("SET_FIXED_CAMERA_POSITION",...position,0,0,0);
    N("POINT_CAMERA_AT_POINT",...v.c,2);
}
function fermerFilmFacades(nom) {
    cameraFacadesVille.index=plansFacadesVille.length;
    N("RESTORE_CAMERA_JUMPCUT");N("DISPLAY_RADAR",true);N("RELEASE_WEATHER");
    for(const plan of plansFacadesVille)N("MARK_MODEL_AS_NO_LONGER_NEEDED",plan.id);
    writeKey("essai.ini","filmVille",bootId+"-"+nom);
    report("FILM facades "+nom);
}
function chargerPlanFacades(p,i,t) {
    const v=plansFacadesVille[i],e=cameraFacadesVille;
    e.index=i;e.deb=null;e.charge=t;e.heure=t+750;
    if(!i){menu="";N("DISPLAY_RADAR",false);}
    N("SET_AREA_VISIBLE",0);
    N("SET_TIME_OF_DAY",14,0);N("FORCE_WEATHER_NOW",0);
    N("REQUEST_COLLISION",v.a[0],v.a[1]);N("REQUEST_MODEL",v.id);
    // Le joueur garde en mémoire le secteur filmé. Le poser derrière l'oeil,
    // au niveau de la rue ; il reste ainsi hors champ et la caméra reste fixe.
    const dx=v.a[0]-v.c[0],dy=v.a[1]-v.c[1],norme=Math.hypot(dx,dy);
    testMove(p,[v.a[0]+6*dx/norme,v.a[1]+6*dy/norme,11.5]);
    N("LOAD_SCENE",...v.c);
    placerPlanFacades(v,0);
}
function testFacadesVille(p,free,now) {
    const e=cameraFacadesVille,t=Date.now();
    if(e.index>=plansFacadesVille.length)return;
    if(!free){if(e.index>=0)fermerFilmFacades("interrompu");return;}
    if(e.index<0){chargerPlanFacades(p,0,t);return;}
    const v=plansFacadesVille[e.index];
    if(t>=e.heure){N("SET_TIME_OF_DAY",14,0);e.heure=t+750;}
    if(e.deb===null){
        if(t-e.charge>18000){fermerFilmFacades("echec-"+v.nom);return;}
        if(t-e.charge<1300 || !N("HAS_MODEL_LOADED",v.id))return;
        placerPlanFacades(v,0);e.deb=t;
        writeKey("essai.ini","filmVille",bootId+"-"+v.nom);
        report("FILM ville "+v.nom+" modele "+v.id+" duree=7000 cible="+v.c.join(","));
        return;
    }
    const age=t-e.deb;placerPlanFacades(v,Math.min(1,age/7000));
    if(age<7000)return;
    if(e.index+1===plansFacadesVille.length)fermerFilmFacades("fin");
    else chargerPlanFacades(p,e.index+1,t);
}
