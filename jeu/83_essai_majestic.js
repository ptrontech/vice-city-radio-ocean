// Comparaison de la façade du Majestic, deux cadrages identiques de jour et de nuit.
const vuesMajestic=[
    {nom:"jour-rue",heure:14,modele:3110,oeil:[306,-1001,16],vise:[272.8,-985.8,23.2]},
    {nom:"jour-porte",heure:14,modele:3110,oeil:[289.5,-994,15.1],vise:[275.2,-986,14.4]},
    {nom:"nuit-rue",heure:22,modele:3111,oeil:[306,-1001,16],vise:[272.8,-985.8,23.2]},
    {nom:"nuit-porte",heure:22,modele:3111,oeil:[289.5,-994,15.1],vise:[275.2,-986,14.4]}
];
let indiceMajestic=-1, debutMajestic=0, prochaineHeureMajestic=0, vuePreteMajestic=false, mesureMajestic=false;
function cadrerMajestic(p, index) {
    indiceMajestic=index;
    const v=vuesMajestic[index];
    if(index===0) {testMove(p,[293,-1003,11]);N("DISPLAY_RADAR",false);}
    menu="";
    N("SET_TIME_OF_DAY",v.heure,0);N("FORCE_WEATHER_NOW",0);
    N("REQUEST_COLLISION",268.638,-985.696);N("REQUEST_MODEL",v.modele);N("LOAD_SCENE",268.638,-985.696,24.49);
    N("SET_FIXED_CAMERA_POSITION",...v.oeil,0,0,0);N("POINT_CAMERA_AT_POINT",...v.vise,2);
    benchScene("Majestic "+v.nom,v.heure,0);
    vuePreteMajestic=false; mesureMajestic=false; debutMajestic=Date.now(); prochaineHeureMajestic=0;
}
function testMajestic(p,free) {
    if(!free || indiceMajestic>=vuesMajestic.length)return;
    if(indiceMajestic<0){cadrerMajestic(p,0);return;}
    const v=vuesMajestic[indiceMajestic], t=Date.now(), age=t-debutMajestic;
    if(t>=prochaineHeureMajestic){N("SET_TIME_OF_DAY",v.heure,0); prochaineHeureMajestic=t+800;}
    if(!mesureMajestic)mesureMajestic=benchTick();
    if(!vuePreteMajestic && age>1700 && N("HAS_MODEL_LOADED",v.modele)){
        const visible=N("IS_POINT_ON_SCREEN",...v.vise,1);
        verdict("Majestic "+v.nom+" modele "+v.modele+" charge et point vise a l'ecran",visible);
        report("PHOTO Majestic "+v.nom+" heure="+JSON.stringify(N("GET_TIME_OF_DAY"))+" oeil="+v.oeil+" cible="+v.vise+" meteo=0");
        writeKey("essai.ini","planMajestic",bootId+"-"+v.nom);vuePreteMajestic=true;
    }
    if(!vuePreteMajestic && age>20000){verdict("chargement du modele Majestic "+v.modele,false);indiceMajestic=vuesMajestic.length;return;}
    if(!vuePreteMajestic || !mesureMajestic)return;
    if(age<32000 && readKey("essai.ini","captureMajestic")!==bootId+"-"+v.nom)return;
    if(age>=32000)report("CAPTURE Majestic "+v.nom+" non confirmee par la fenetre");
    const suivant=indiceMajestic+1;
    if(suivant<vuesMajestic.length){cadrerMajestic(p,suivant);return;}
    N("RESTORE_CAMERA_JUMPCUT");N("DISPLAY_RADAR",true);N("RELEASE_WEATHER");
    N("MARK_MODEL_AS_NO_LONGER_NEEDED",3110);N("MARK_MODEL_AS_NO_LONGER_NEEDED",3111);
    indiceMajestic=suivant;report("FIN Majestic deux cadres jour et nuit");
}
