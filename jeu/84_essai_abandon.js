// Scénario réservé au profil Validation : les missions et les suiveurs tournent dans le moteur.
let phaseContrats="reprise", heureContrats=0, etapeIndiceContrats=-1;
let bilanContrats=null, repereContrats=null, temoinContrats=null;
let marcheContrats=null, departMarcheContrats=null, dernierePositionMilo=null;
let pointControleTommy=null, derniereProgressionNative=0, transfertCumuleContrats=0, transfertMaxContrats=0;
let courseNativeContrats=false;
let derniereMesureContrats=0, prochainPasContrats=0, distanceMiloContrats=0, pasContrats=0;

function phaseQAContrats(phase) { phaseContrats=phase; heureContrats=Date.now(); }
function exigerContrats(nom, ok) {
    if (verdict(nom,Boolean(ok))) return true;
    phaseQAContrats("fin");
    return false;
}
function memeBilanContrats(s) {
    return Object.keys(bilanContrats).every(k=>s[k]===bilanContrats[k]);
}
function indicesContrats(p) {
    if (mission.step===mission.places.length) return true;
    if (etapeIndiceContrats!==mission.step) {
        etapeIndiceContrats=mission.step;
        testMove(p,mission.places[mission.step]);
    }
    return false;
}
function ecartContrats(a,b) { return Math.hypot(a.x-b.x,a.y-b.y); }
function testContrats(p,free) {
    if (!free || phaseContrats==="fin") return;
    const t=Date.now(), age=t-heureContrats, pos=posOf(p);
    if (phaseContrats!=="reprise" && age>(phaseContrats.startsWith("marche")?150000:25000)) {
        exigerContrats("duree etape "+phaseContrats+" Milo="+JSON.stringify(alive(temoinContrats)?posOf(temoinContrats):null)+" Tommy="+JSON.stringify(pos),false);
        return;
    }
    switch (phaseContrats) {
    case "reprise": {
        bilanContrats={...state};
        const disque=readState();
        report("REPRISE v3 generation="+state.generation+" dossiers="+state.dossiers+" caisse="+state.caisse+" emissions="+state.missions+" reserve="+state.reserve);
        if (!exigerContrats("cinq dossiers en memoire et sur disque apres nouveau processus",state.dossiers===31 && disque.dossiers===31 && memeBilanContrats(disque))) return;
        testMove(p,contact); phaseQAContrats("depart"); return;
    }
    case "depart":
        if (age<600 || !near(pos,contact,5)) return;
        if (!exigerContrats("contrat confie a pied par Ines",startFrequency(pos))) return;
        repereContrats=objective;
        testMove(p,mission.places[1]); phaseQAContrats("fausse piste"); return;
    case "fausse piste":
        if (age<850) return;
        if (!exigerContrats("fausse piste atteinte sans indice, nouveau repere ni prime",
            near(pos,mission.places[1],5) && mission.step===0 && mission.milo===null && objective===repereContrats && memeBilanContrats(state))) return;
        etapeIndiceContrats=-1; phaseQAContrats("annulation"); return;
    case "annulation":
        if (!mission || !indicesContrats(p)) return;
        temoinContrats=mission.milo; repereContrats=objective;
        if (!exigerContrats("Milo rencontre a pied, marqueur et sphere crees avant abandon",alive(temoinContrats) &&
            !N("IS_CHAR_IN_ANY_CAR",p) && !N("IS_CHAR_IN_ANY_CAR",temoinContrats) && repereContrats && repereContrats.blip!=null && repereContrats.sphere!=null)) return;
        report("ABANDON Milo="+temoinContrats+" blip="+repereContrats.blip+" sphere="+repereContrats.sphere);
        cancelJob("Course abandonnee."); phaseQAContrats("controle abandon"); return;
    case "controle abandon":
        if (age<600) return;
        if (!exigerContrats("abandon supprime le PNJ natif et libere le marqueur et la sphere",!N("DOES_CHAR_EXIST",temoinContrats) && !mission && !objective)) return;
        if (!exigerContrats("aucun gain ni ecriture apres abandon",memeBilanContrats(state) && memeBilanContrats(readState()))) return;
        testMove(p,contact); phaseQAContrats("delai"); return;
    case "delai":
        if (age<650 || !near(pos,contact,5)) return;
        if (!exigerContrats("deuxieme contrat accessible apres abandon",startFrequency(pos))) return;
        mission.stop=clockNow()+500;
        phaseQAContrats("controle delai"); return;
    case "controle delai":
        if (age<950) return;
        if (!exigerContrats("echeance raccourcie traitee par le moteur, objectif libere et zero gain",!mission && !objective &&
            memeBilanContrats(state) && memeBilanContrats(readState()))) return;
        if (!exigerContrats("nouvelle recherche possible apres expiration",startFrequency(pos))) return;
        etapeIndiceContrats=-1; phaseQAContrats("rencontre"); return;
    case "rencontre":
        if (!mission || !indicesContrats(p)) return;
        temoinContrats=mission.milo;
        if (!exigerContrats("rencontre de Milo et ordre de suivi a pied",alive(temoinContrats) && mission.trajet==="a_pied" && !N("IS_CHAR_IN_ANY_CAR",p) && !N("IS_CHAR_IN_ANY_CAR",temoinContrats))) return;
        departMarcheContrats=posOf(temoinContrats); dernierePositionMilo=departMarcheContrats;
        marcheContrats={x:contact[0],y:contact[1]}; prochainPasContrats=t; derniereMesureContrats=t;
        if (!exigerContrats("Milo appartient au groupe actif de Tommy",N("IS_CHAR_IN_CHARS_GROUP",temoinContrats,p))) return;
        report("MARCHE depart "+JSON.stringify(departMarcheContrats)+" contact="+JSON.stringify(contact));
        pointControleTommy=pos; derniereProgressionNative=t;
        N("SET_CHAR_OBJ_GOTO_COORD_ON_FOOT",p,contact[0],contact[1]);
        phaseQAContrats("marche native"); return;
    case "marche native": {
        if (!mission) {phaseQAContrats("arrivee");return;}
        if (!alive(temoinContrats) || N("IS_CHAR_IN_ANY_CAR",p) || N("IS_CHAR_IN_ANY_CAR",temoinContrats)) {
            exigerContrats("Tommy et Milo restent a pied",false);return;
        }
        const milo=posOf(temoinContrats);
        distanceMiloContrats+=ecartContrats(milo,dernierePositionMilo); dernierePositionMilo=milo;
        if(ecartContrats(pos,pointControleTommy)>=1) {pointControleTommy=pos; derniereProgressionNative=t;}
        if (!courseNativeContrats && age>8500 && ecartContrats(pos,marcheContrats)>40) {
            // Tommy et son groupe restent à pied. La course garde une marge avant l'échéance normale.
            N("SET_CHAR_OBJ_RUN_TO_COORD",p,contact[0],contact[1]);
            courseNativeContrats=true;
            report("MARCHE puis course native de Tommy et son suiveur, les controles restent automatiques");
        }
        if(age>5000 && t-derniereMesureContrats>=10000) {
            report("MARCHE sans repositionnement Tommy="+JSON.stringify(pos)+" Milo="+JSON.stringify(milo));
            derniereMesureContrats=t;
        }
        if(t-derniereProgressionNative<6000)return;
        N("SET_CHAR_OBJ_NO_OBJ",p);
        report("MARCHE de Tommy interrompue par le controle normal du joueur; suite par placements de Tommy, mesure immediate de Milo a chaque placement");
        phaseQAContrats("marche"); return;
    }
    case "marche": {
        if (!mission) { phaseQAContrats("arrivee"); return; }
        if (!alive(temoinContrats) || N("IS_CHAR_IN_ANY_CAR",p) || N("IS_CHAR_IN_ANY_CAR",temoinContrats) || mission.trajet!=="a_pied") {
            exigerContrats("Milo et Tommy restent vivants et a pied",false);return;
        }
        const milo=posOf(temoinContrats), avance=ecartContrats(milo,dernierePositionMilo);
        distanceMiloContrats+=avance;
        dernierePositionMilo=milo;
        if(t-derniereMesureContrats>=10000) {
            report("MARCHE Milo="+JSON.stringify(milo)+" Tommy="+JSON.stringify(pos)+" reste="+ecartContrats(milo,marcheContrats).toFixed(1)+" m");
            derniereMesureContrats=t;
        }
        if(t<prochainPasContrats || ecartContrats(pos,milo)>5.8 || near(pos,contact,2)) return;
        const restant=ecartContrats(pos,marcheContrats);
        const portion=Math.min(1,6.5/restant);
        testMove(p,[pos.x+(marcheContrats.x-pos.x)*portion,pos.y+(marcheContrats.y-pos.y)*portion,contact[2]]);
        const transfert=ecartContrats(posOf(temoinContrats),milo);
        transfertCumuleContrats+=transfert;
        transfertMaxContrats=Math.max(transfertMaxContrats,transfert);
        pasContrats++; prochainPasContrats=t+180; return;
    }
    case "arrivee": {
        if(age<900)return;
        const arrivee=dernierePositionMilo;
        const ligne=ecartContrats(arrivee,departMarcheContrats), restant=ecartContrats(arrivee,marcheContrats);
        report("MARCHE fin progression nette Milo="+ligne.toFixed(1)+" m, chemin cumule="+distanceMiloContrats.toFixed(1)+" m, ecart radio="+restant.toFixed(1)+" m, placements QA de Tommy="+pasContrats);
        report("MARCHE deplacement de Milo au meme instant que le placement du leader : total="+transfertCumuleContrats.toFixed(1)+" m, max="+transfertMaxContrats.toFixed(1)+" m, reste observe entre placements="+Math.max(0,distanceMiloContrats-transfertCumuleContrats).toFixed(1)+" m");
        if (!exigerContrats("suiveur livre par le mode a pied, ecart final mesure",ligne>50 && restant<distanceRetourMilo+5)) return;
        const revenus=(bilanContrats.local?cfg.revenu:0)+revenuEquipe(bilanContrats)+propertyIncome(bilanContrats);
        if (!exigerContrats("une seule prime de 440, une emission et un versement des revenus",state.generation===bilanContrats.generation+1 &&
            state.caisse===bilanContrats.caisse+primeFrequence && state.missions===bilanContrats.missions+1 && state.reserve===bilanContrats.reserve+revenus &&
            state.dossiers===31 && readState().generation===state.generation)) return;
        report("FIN echecs et accompagnement de Milo a pied"); phaseQAContrats("fin"); return;
    }
    }
}
