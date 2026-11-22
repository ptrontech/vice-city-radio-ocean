// Recette réservée au profil Validation. Chaque prise garde sa caméra sept secondes.
const catalogueEssaiAutos = [
    {nom:"admiral", id:175, couleurs:[59,59]},
    {nom:"sabre", id:205, couleurs:[14,14]},
    {nom:"police", id:156, couleurs:[2,1]},
    {nom:"cheetah", id:145, couleurs:[36,36]}
];
// Le COL ap_rland04 sous ces coordonnées est plat à 13,828 m sur toute la prise.
const tarmacEssaiAutos = [-1620,-1065,13.828];
const delaiPlanAuto = 7000;
const tournageAutos = {index:0, etape:"attente", depuis:0, auto:null, temps:null, derniere:null};

function signalAuto(cle,valeur) {
    writeKey("essai.ini",cle,bootId+"-"+valeur);
}
function libererAuto(p) {
    const v=tournageAutos.auto;
    if(v!==null) {
        if(alive(p)&&N("IS_CHAR_IN_CAR",p,v))
            N("WARP_CHAR_FROM_CAR_TO_COORD",p,tarmacEssaiAutos[0]+5,tarmacEssaiAutos[1],tarmacEssaiAutos[2]+1);
        N("DELETE_CAR",v);
        tournageAutos.auto=null;
    }
    const fiche=catalogueEssaiAutos[tournageAutos.index];
    if(fiche)N("MARK_MODEL_AS_NO_LONGER_NEEDED",fiche.id);
}
function terminerAutos(p,erreur) {
    libererAuto(p);
    N("RESTORE_CAMERA_JUMPCUT");
    N("DISPLAY_RADAR",true);
    N("RELEASE_WEATHER");
    const heure=tournageAutos.temps;
    if(heure)N("SET_TIME_OF_DAY",heure.hours,heure.minutes);
    tournageAutos.etape="fin";
    if(erreur){
        signalAuto("erreurVoitures",erreur);
        verdict("voitures "+erreur,false);
    }else{
        signalAuto("filmVoitures","fin");
        signalAuto("planVoitures","fin");
        report("FILM voitures 4 modeles, 8 prises terminees");
    }
    return true;
}
function demanderAuto(now) {
    N("REQUEST_MODEL",catalogueEssaiAutos[tournageAutos.index].id);
    tournageAutos.etape="chargement";
    tournageAutos.depuis=now;
}
function amorcerPlanAuto(nom,signe,now) {
    const v=tournageAutos.auto;
    const oeil=N("GET_OFFSET_FROM_CAR_IN_WORLD_COORDS",v,signe*2.35,signe*5.10,1.05);
    const vise=N("GET_OFFSET_FROM_CAR_IN_WORLD_COORDS",v,0,signe*1.03,.14);
    N("SET_FIXED_CAMERA_POSITION",oeil.x,oeil.y,oeil.z,0,0,0);
    N("POINT_CAMERA_AT_POINT",vise.x,vise.y,vise.z,2);
    tournageAutos.etape=signe>0?"avant":"arriere";
    tournageAutos.depuis=now;
    if(signe>0)signalAuto("filmVoitures",nom);
    signalAuto("planVoitures",nom+"-"+tournageAutos.etape);
    report("FILM voitures "+nom+" "+tournageAutos.etape+" 7000 ms");
}
function testVoitures1986(p,free,now=Date.now()) {
    const tour=tournageAutos;
    if(tour.etape==="fin")return true;
    if(!free)return tour.etape==="attente"?false:terminerAutos(p,"joueur");
    if(tour.etape==="attente"){
        // L'essai démarre depuis une sauvegarde ou un nouveau jeu du profil Validation.
        tour.temps=N("GET_TIME_OF_DAY");
        if(N("IS_CHAR_IN_ANY_CAR",p)){
            const pos=posOf(p);
            N("WARP_CHAR_FROM_CAR_TO_COORD",p,pos.x+2,pos.y,pos.z);
        }
        N("SET_AREA_VISIBLE",0);
        menu="";
        N("DISPLAY_RADAR",false);
        N("FORCE_WEATHER_NOW",0);
        N("SET_TIME_OF_DAY",15,15);
        N("REQUEST_COLLISION",tarmacEssaiAutos[0],tarmacEssaiAutos[1]);
        N("LOAD_SCENE",...tarmacEssaiAutos);
        testMove(p,[tarmacEssaiAutos[0]+5,tarmacEssaiAutos[1],tarmacEssaiAutos[2]+1]);
        demanderAuto(now);
        return false;
    }
    const fiche=catalogueEssaiAutos[tour.index];
    const age=now-tour.depuis;
    if(tour.etape==="chargement"){
        if(age>18000)return terminerAutos(p,fiche.nom+"-chargement");
        if(age<850||!N("HAS_MODEL_LOADED",fiche.id))return false;
        const [x,y,z]=tarmacEssaiAutos;
        const sol=N("GET_GROUND_Z_FOR_3D_COORD",x,y,z+4);
        if(!Number.isFinite(sol)||Math.abs(sol-z)>.45)return false;
        tour.auto=N("CREATE_CAR",fiche.id,x,y,sol+.85);
        if(tour.auto===null||tour.auto===undefined||tour.auto<0){
            tour.auto=null;
            return terminerAutos(p,fiche.nom+"-creation");
        }
        N("SET_CAR_HEADING",tour.auto,14);
        N("CHANGE_CAR_COLOUR",tour.auto,...fiche.couleurs);
        N("SET_CAR_FORWARD_SPEED",tour.auto,0);
        N("WARP_CHAR_INTO_CAR",p,tour.auto);
        tour.etape="installation";tour.depuis=now;
        return false;
    }
    if(tour.etape==="installation"){
        if(age>6000)return terminerAutos(p,fiche.nom+"-installation");
        if(age<650||!N("IS_CHAR_IN_CAR",p,tour.auto))return false;
        const pos=N("GET_CAR_COORDINATES",tour.auto);
        if(N("GET_CAR_MODEL",tour.auto)!==fiche.id ||
           Math.hypot(pos.x-tarmacEssaiAutos[0],pos.y-tarmacEssaiAutos[1])>1.3 ||
           pos.z<tarmacEssaiAutos[2]+.15 || pos.z>tarmacEssaiAutos[2]+1.4)return false;
        tour.derniere=pos;
        verdict(fiche.nom+" "+fiche.id+" Tommy au volant, centre "+JSON.stringify(pos),true);
        amorcerPlanAuto(fiche.nom,1,now);
        return false;
    }
    if(age<delaiPlanAuto)return false;
    const pos=N("GET_CAR_COORDINATES",tour.auto);
    const stable=Math.hypot(pos.x-tour.derniere.x,pos.y-tour.derniere.y,pos.z-tour.derniere.z)<1.1;
    if(!stable||!N("IS_CHAR_IN_CAR",p,tour.auto))return terminerAutos(p,fiche.nom+"-deplacement");
    if(tour.etape==="avant"){
        amorcerPlanAuto(fiche.nom,-1,now);
    }else{
        if(tour.index===catalogueEssaiAutos.length-1)return terminerAutos(p,"");
        libererAuto(p);tour.index++;demanderAuto(now);
    }
    return false;
}
