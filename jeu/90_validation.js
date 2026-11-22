// Cette séquence n'est appelée que dans le profil Validation. Aucune commande de test en campagne ou en libre.
let testStep=0, testWhen=0, testAge=Date.now(), loggedAt=0, testCar=0, shotPhase=0;
let frameBucket=[], realLast=0, sceneStart=0, scenario="", diagLast=0;
const essai=mode==="Validation"?readKey("essai.ini","scenario"):"";
const benchOnly=essai==="reference";
let demoTaxi=null, demoDriver=null, firstCarPos=null;
function report(line){log("PREUVE | "+line);}
function testMove(actor,p) {N("REQUEST_COLLISION",p[0],p[1]);N("SET_CHAR_COORDINATES",actor,p[0],p[1],ground(p));}
function verdict(name,ok){report((ok?"OK ":"ECHEC ")+name);return ok;}
function benchTick() {
    const t=Date.now();
    if(realLast && t>realLast)frameBucket.push(t-realLast);
    realLast=t;
    if(t-sceneStart<12500)return false;
    const durations=frameBucket.slice(8).sort((a,b)=>a-b);
    if(durations.length>20){
        const at=p=>durations[Math.min(durations.length-1,Math.floor(durations.length*p))];
        report("MESURE "+scenario+" n="+durations.length+" mediane_ms="+at(.5)+" p95_ms="+at(.95)+" p99_ms="+at(.99));
    }
    frameBucket=[];realLast=0;return true;
}
function benchScene(name,hour,weather){
    scenario=name;N("SET_TIME_OF_DAY",hour,0);N("FORCE_WEATHER_NOW",weather);
    realLast=0;frameBucket=[];sceneStart=Date.now();report("SCENE "+name);
}
function testTick(playing,p,free,now) {
    if(testStep===99)return;
    const t=Date.now();
    if(t-loggedAt>9000 && testStep<14){
        loggedAt=t;report("etape="+testStep+" etat joueur="+playing+" libre="+free+" mission="+ONMISSION+" pos="+(playing?JSON.stringify(posOf(p)):"-"));
    }
    if(!playing||!alive(p))return;
    if(!free){
        // L'introduction de la vraie campagne se joue aussi en validation. On attend la fin des cinématiques.
        return;
    }
    if(t<testWhen)return;
    const pos=posOf(p);
    switch(testStep){
    case 0:
        report("profil "+mode+" generation="+state.generation+" missions="+state.missions+" local="+state.local+" equipe="+state.equipe+" reserve="+state.reserve);
        if(essai==="mesure"){
            const s=[state.generation,state.missions,state.caisse,state.local,state.equipe,state.xp,state.reserve].join(",");
            verdict("restauration exacte apres fermeture "+s,s===readKey("essai.ini","attendu"));
            testStep=14;break;}
        if(!benchOnly && state.missions>=4 && state.local && state.equipe){
            const snapshot=[state.generation,state.missions,state.caisse,state.local,state.equipe,state.xp,state.reserve].join(",");
            const attendu=readKey("essai.ini","attendu");
            verdict("restauration apres relance "+snapshot,snapshot===attendu);
            testStep=99;return;
        }
        if(benchOnly){testStep=14;break;}
        testMove(p,contact);testStep=1;testWhen=t+850;break;
    case 1:
        if(!near(pos,contact,7))return;
        startJob(pos);if(!verdict("course acceptee en moteur",!!mission)){testStep=99;return;}
        testMove(p,mission.pick);testStep=2;testWhen=t+600;break;
    case 2:
        if(!mission){testMove(p,contact);testStep=1;testWhen=t+700;return;}
        if(mission.step!==1) return;
        testMove(p,contact);testStep=3;testWhen=t+600;break;
    case 3:
        if(mission)return;
        if(state.missions<3){testStep=1;break;}
        verdict("palier trois livraisons",state.missions===3 && capacity()===1);
        verdict("recrutement",recruit(pos));testStep=4;testWhen=t+2000;break;
    case 4:
        if(!alive(guards[0])||!alive(pedContact))return;
        verdict("contact et garde presents",true);setOrder("attendre");setOrder("suivre");
        testMove(p,local);testStep=5;testWhen=t+650;break;
    case 5:
        verdict("achat puis doublon bloque",buy(pos)&&!buy(pos));
        testMove(p,contact);testStep=6;testWhen=t+650;break;
    case 6:
        startJob(pos);if(!mission)return;
        testMove(p,mission.pick);testStep=7;testWhen=t+600;break;
    case 7:
        if(!mission || mission.step!==1)return;
        testMove(p,contact);testStep=8;testWhen=t+650;break;
    case 8:
        if(mission)return;
        testMove(p,local);testStep=9;testWhen=t+650;break;
    case 9:
        verdict("recette unique",state.reserve===cfg.revenu&&collect(pos)&&!collect(pos));
        testMove(p,contact);testStep=10;testWhen=t+650;break;
    case 10:
        askInes("Tu te souviens de mes quatre emissions et de ma regie ?");N("REQUEST_MODEL",130);
        testStep=11;break;
    case 11:
        if(!N("HAS_MODEL_LOADED",130))return;
        testCar=N("CREATE_CAR",130,pos.x+3,pos.y,pos.z+.2);N("MARK_MODEL_AS_NO_LONGER_NEEDED",130);
        N("WARP_CHAR_INTO_CAR",p,testCar);testStep=12;testAge=t;break;
    case 12:
        if(!N("IS_CHAR_IN_CAR",guards[0],testCar) && t-testAge<16000)return;
        verdict("garde passager",N("IS_CHAR_IN_CAR",guards[0],testCar));
        testStep=13;break;
    case 13:
        if(pending)return;
        report("conversation "+memoryLabel+" / "+reply);verdict("dialogue livre",!!reply&&!!memoryLabel);
        verdict("etat sauvegarde",readState().missions===4&&readState().local===1&&readState().equipe===1);
        testStep=14;break;
    case 14:
        // Même point, même direction, même caméra sur les deux profils de mesure.
        if(N("IS_CHAR_IN_ANY_CAR",p)){N("WARP_CHAR_FROM_CAR_TO_COORD",p,contact[0],contact[1],contact[2]);}
        if(testCar){N("DELETE_CAR",testCar);testCar=0;}
        N("REQUEST_MODEL",150);if(!N("HAS_MODEL_LOADED",150))return;
        const node=N("GET_CLOSEST_CAR_NODE_WITH_HEADING",contact[0],contact[1]+12,contact[2]);
        demoTaxi=N("CREATE_CAR",150,node.nodeX,node.nodeY,node.nodeZ+0.8);N("SET_CAR_HEADING",demoTaxi,node.angle);
        demoDriver=N("CREATE_RANDOM_CHAR_AS_DRIVER",demoTaxi);N("SET_CAR_CRUISE_SPEED",demoTaxi,17);
        N("CAR_WANDER_RANDOMLY",demoTaxi);N("MARK_MODEL_AS_NO_LONGER_NEEDED",150);firstCarPos=N("GET_CAR_COORDINATES",demoTaxi);
        if(!benchOnly){const dim=ImGui.GetDisplaySize();report("affichage "+JSON.stringify(dim));}
        testMove(p,contact);N("SET_CHAR_HEADING",p,24);N("SET_CAMERA_BEHIND_PLAYER");menu="";recentHub="contact";
        benchScene("avenue-jour",14,0);testStep=15;break;
    case 15:
        if(benchTick()){
            const end=N("GET_CAR_COORDINATES",demoTaxi);report("circulation taxi distance_m="+Math.round(Math.hypot(end.x-firstCarPos.x,end.y-firstCarPos.y)));
            benchScene("avenue-nuit",23,0);testStep=16;}break;
    case 16:
        if(benchTick()){benchScene("avenue-pluie",19,2);testStep=17;}break;
    case 17:
        if(benchTick()){
            N("RELEASE_WEATHER");if(demoDriver!=null)removePed(demoDriver);if(demoTaxi!=null)N("DELETE_CAR",demoTaxi);
            report("FIN mesures");writeKey("essai.ini","termine","oui");testStep=essai==="mesure"?18:99;
        }break;
    case 18:
        testMove(p,local);testStep=19;testWhen=t+900;break;
    case 19:
        if(!near(pos,local,8))return;
        if(!startReport(pos)){report("ECHEC lancement reportage");testStep=99;return;}
        N("REQUEST_MODEL",130);testStep=20;break;
    case 20:
        if(!N("HAS_MODEL_LOADED",130)||!mission||mission.guest===null)return;
        testCar=N("CREATE_CAR",130,local[0]+4,local[1],ground(local));
        N("WARP_CHAR_INTO_CAR",p,testCar);N("MARK_MODEL_AS_NO_LONGER_NEEDED",130);testStep=21;testAge=t;break;
    case 21:
        if(!mission||t-testAge>24000){report("ECHEC embarquement journaliste");testStep=99;return;}
        if(mission.step!==1)return;
        verdict("journaliste montee en passagere",N("IS_CHAR_IN_CAR",mission.guest,testCar));
        N("SET_CAR_COORDINATES",testCar,mission.pick[0],mission.pick[1],ground(mission.pick));N("SET_CAR_FORWARD_SPEED",testCar,0);
        testStep=22;testAge=t;break;
    case 22:
        if(mission && t-testAge<18000)return;
        verdict("transport et recompense",!mission && state.missions>Number(readKey("essai.ini","attendu").split(",")[1]));
        if(N("IS_CHAR_IN_ANY_CAR",p))N("WARP_CHAR_FROM_CAR_TO_COORD",p,contact[0],contact[1],contact[2]);
        if(testCar){N("DELETE_CAR",testCar);testCar=0;}
        testMove(p,contact);testStep=23;testWhen=t+500;break;
    case 23:{
        const avant=state.generation;startJob(pos);
        if(!mission){report("ECHEC preparation delai");testStep=99;return;}
        mission.stop=clockNow()-1;tickJob(pos);
        verdict("echec sans paiement et repere retire",!mission && !objective && state.generation===avant);
        const entitlement=loadSport().brevet||sprintGrant();
        tickSprint(p,true,clockNow()+250);verdict("sprint natif applique a pied",entitlement && loadSport().brevet && sprintApplied===p);
        report("FIN validation complete");testStep=99;break;
    }
    }
}
while(true){wait(0);tick();}
