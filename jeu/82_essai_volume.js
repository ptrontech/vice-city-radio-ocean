// Trois prises géométriques de neuf secondes pour la capture de la fenêtre du jeu.
const prisesVolume=[
    {nom:"hall",modele:3110,heure:14},
    {nom:"chambres",modele:3110,heure:14},
    {nom:"nuit",modele:3111,heure:22}
];
const filmVolume={indice:-1,charge:0,depart:null,horloge:0};
const dureePriseVolume=9000;

function interpolationVolume(a,b,t) {
    return a.map((v,i)=>v+(b[i]-v)*t);
}
function mondeHallVolume(p) {
    // Origine du seuil et rotation mesurées dans le DFF et l'IPL d'Ocean Drive.
    const [x,y,z]=p;
    return [275.031377+.987604921*x+.156960251*y,-987.298706-.156960251*x+.987604921*y,10.870894+z];
}
function cadreVolume(nom,t) {
    // Accélération courte aux extrémités, vitesse uniforme sur le reste du travelling.
    const r=.14;
    let avance;
    if(t<r)avance=t*t/(2*r);
    else if(t>1-r)avance=1-r-(1-t)*(1-t)/(2*r);
    else avance=t-r/2;
    const f=avance/(1-r);
    if(nom==="hall"){
        // Le premier tronçon longe la rue. L'arc contourne les vitrines à 3 m,
        // sans couper la façade. Le point visé quitte le comptoir pour le salon.
        let x,y;
        const rapport=.376;
        if(f<rapport){x=4.25;y=-1.52+7.30*f/rapport;}
        else{
            const k=(f-rapport)/(1-rapport);
            const rayon=8.10-.53*k, angle=k*Math.PI/2;
            x=-3.85+rayon*Math.cos(angle);y=5.78+rayon*Math.sin(angle);
        }
        return [mondeHallVolume([x,y,1.73+.17*f]),
                mondeHallVolume(interpolationVolume([-3.95,1.31,1.42],[-3.1,6.22,1.16],f))];
    }
    if(nom==="chambres"){
        // Première grande baie du premier étage : 4,4 m de déplacement à environ
        // 4,6 m de la vitre, en visant derrière l'embrasure et le rideau plissé.
        return [interpolationVolume([284.956,-977.585,19.291],[284.266,-981.931,19.391],f),
                interpolationVolume([278.675,-978.563,19.381],[278.556,-979.314,19.361],f)];
    }
    // Au seuil, un cadrage fixe garde le comptoir, ses lampes et les clefs à l'image.
    return [mondeHallVolume([.55,-.25,1.72]),mondeHallVolume([-3.72,1,1.54])];
}
function placerCameraVolume(v,t) {
    const [oeil,vise]=cadreVolume(v.nom,t);
    N("SET_FIXED_CAMERA_POSITION",...oeil,0,0,0);
    N("POINT_CAMERA_AT_POINT",...vise,2);
}
function ouvrirPriseVolume(p,index,maintenant) {
    filmVolume.indice=index;
    filmVolume.charge=maintenant;
    filmVolume.depart=null;
    filmVolume.horloge=maintenant+750;
    const v=prisesVolume[index];
    if(index===0){
        testMove(p,[293,-1003,11]);
        menu="";
        N("DISPLAY_RADAR",false);
    }
    N("SET_TIME_OF_DAY",v.heure,0);
    N("FORCE_WEATHER_NOW",0);
    if(index===0 || prisesVolume[index-1].modele!==v.modele){
        N("REQUEST_COLLISION",268.638,-985.696);
        N("REQUEST_MODEL",v.modele);
        N("LOAD_SCENE",268.638,-985.696,24.49);
    }
    placerCameraVolume(v,0);
}
function terminerVolume(reussi) {
    filmVolume.indice=prisesVolume.length;
    N("RESTORE_CAMERA_JUMPCUT");
    N("DISPLAY_RADAR",true);
    N("RELEASE_WEATHER");
    for(const modele of [3110,3111])N("MARK_MODEL_AS_NO_LONGER_NEEDED",modele);
    if(reussi){
        writeKey("essai.ini","filmVolume",bootId+"-fin");
        report("FILM Majestic fin des trois prises de 9 s");
    }
}
function testVolumes(p,free) {
    if(filmVolume.indice>=prisesVolume.length)return;
    if(!free){
        if(filmVolume.indice>=0){
            writeKey("essai.ini","erreurVolume",bootId+"-joueur");
            terminerVolume(false);
        }
        return;
    }
    const maintenant=Date.now();
    if(filmVolume.indice<0){ouvrirPriseVolume(p,0,maintenant);return;}
    const v=prisesVolume[filmVolume.indice];
    if(maintenant>=filmVolume.horloge){
        N("SET_TIME_OF_DAY",v.heure,0);
        filmVolume.horloge=maintenant+750;
    }
    if(filmVolume.depart===null){
        if(maintenant-filmVolume.charge>18000){
            verdict("chargement de la prise "+v.nom,false);
            writeKey("essai.ini","erreurVolume",bootId+"-"+v.nom);
            terminerVolume(false);return;
        }
        // Attendre la mise à jour de l'objet horaire avant d'annoncer la première image.
        const installation=filmVolume.indice===1?180:1000;
        if(maintenant-filmVolume.charge<installation || !N("HAS_MODEL_LOADED",v.modele))return;
        placerCameraVolume(v,0);
        filmVolume.depart=maintenant;
        writeKey("essai.ini","filmVolume",bootId+"-"+v.nom);
        report("FILM Majestic "+v.nom+" pendant 9000 ms, modele="+v.modele);
        return;
    }
    const age=maintenant-filmVolume.depart;
    placerCameraVolume(v,Math.min(1,age/dureePriseVolume));
    if(age<dureePriseVolume)return;
    const suivant=filmVolume.indice+1;
    if(suivant<prisesVolume.length)ouvrirPriseVolume(p,suivant,maintenant);
    else terminerVolume(true);
}
