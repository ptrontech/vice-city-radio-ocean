// Validation dans le vrai moteur, réservée au profil isolé du lanceur.
let essaiMiloEtape=0, essaiMiloDepuis=0, essaiMiloLieu=-1, essaiMiloMesure=false;
let essaiMiloActeur=null, essaiMiloAuto=null, essaiMiloSolde=null;
function etapeMilo(n){essaiMiloEtape=n;essaiMiloDepuis=Date.now();}
function testFrequence(p,free){
    if(!free || essaiMiloEtape===99)return;
    const pos=posOf(p), age=Date.now()-essaiMiloDepuis;
    if(essaiMiloEtape>0 && !essaiMiloMesure)essaiMiloMesure=benchTick();
    if(essaiMiloEtape>0 && age>35000){
        verdict("progression Milo etape "+essaiMiloEtape+" position "+JSON.stringify(pos),false);
        etapeMilo(99);return;
    }
    switch(essaiMiloEtape){
    case 0:
        benchScene("Ocean Drive de nuit sous la pluie",23,2);
        report("FREQUENCE debut, profil orage="+Boolean(cfg.nuitsOrage));
        testMove(p,contact);etapeMilo(1);return;
    case 1:
        if(age<750||!near(pos,contact,6))return;
        if(!verdict("Ines confie la recherche de Milo",startFrequency(pos))){etapeMilo(99);return;}
        essaiMiloSolde={...state};etapeMilo(2);return;
    case 2:
        if(!mission){verdict("mission active",false);etapeMilo(99);return;}
        if(mission.step<mission.places.length){
            if(essaiMiloLieu!==mission.step){
                essaiMiloLieu=mission.step;report("repere Milo "+(mission.step+1));
                testMove(p,mission.places[mission.step]);essaiMiloDepuis=Date.now();
            }
            return;
        }
        essaiMiloActeur=mission.milo;
        verdict("Milo rencontre a pied apres les indices",alive(essaiMiloActeur));
        N("REQUEST_MODEL",130);etapeMilo(3);return;
    case 3:
        if(!N("HAS_MODEL_LOADED",130))return;
        essaiMiloAuto=N("CREATE_CAR",130,pos.x+4,pos.y+1,pos.z+.25);
        N("WARP_CHAR_INTO_CAR",p,essaiMiloAuto);N("MARK_MODEL_AS_NO_LONGER_NEEDED",130);
        etapeMilo(4);return;
    case 4:
        if(!N("IS_CHAR_IN_CAR",essaiMiloActeur,essaiMiloAuto))return;
        verdict("Milo monte reellement en passager",true);
        N("REQUEST_COLLISION",contact[0],contact[1]);
        N("SET_CAR_COORDINATES",essaiMiloAuto,contact[0]-3,contact[1],ground(contact));
        N("SET_CAR_FORWARD_SPEED",essaiMiloAuto,0);etapeMilo(5);return;
    case 5:
        if(age<1200)return;
        verdict("aucun paiement dans le vehicule",Boolean(mission)&&state.caisse===essaiMiloSolde.caisse);
        N("WARP_CHAR_FROM_CAR_TO_COORD",p,contact[0]+1,contact[1]+1,ground(contact));
        etapeMilo(6);return;
    case 6:
        if(mission || age<750)return;
        verdict("Milo descendu, prime unique 440 et reputation +1",state.caisse===essaiMiloSolde.caisse+440 &&
            state.missions===essaiMiloSolde.missions+1 && state.generation===essaiMiloSolde.generation+1);
        const droits=(essaiMiloSolde.local?cfg.revenu:0)+revenuEquipe(essaiMiloSolde)+propertyIncome(essaiMiloSolde);
        verdict("recettes des proprietes incluses",state.reserve===essaiMiloSolde.reserve+droits);
        if(essaiMiloAuto!==null){N("MARK_CAR_AS_NO_LONGER_NEEDED",essaiMiloAuto);essaiMiloAuto=null;}
        etapeMilo(7);return;
    case 7:
        if(!essaiMiloMesure)return;
        N("RELEASE_WEATHER");report("FIN parcours Milo");etapeMilo(99);return;
    }
}
