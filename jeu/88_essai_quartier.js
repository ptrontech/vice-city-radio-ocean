// Parcours isolé sur le profil Validation. Utilise les déclencheurs d'entrée de la campagne.
let quartierEtape=0, quartierDelai=0, quartierTemps=0, quartierLot=0, quartierReserve=0;
let quartierActeur=null, repriseVerifiee=false;
function quartierSuite(n,ms=0){quartierEtape=n;quartierTemps=Date.now();quartierDelai=quartierTemps+ms;}
function testQuartier(p,free) {
    if(!free||quartierEtape===99||Date.now()<quartierDelai)return;
    const pos=posOf(p),lot=propertyLots[quartierLot],now=Date.now();
    if(quartierEtape===0){
        report("QUARTIER debut missions="+state.missions+" caisse="+state.caisse+" biens="+state.biens);
        if(!state.local||!state.equipe){report("ECHEC precondition profil de validation");quartierEtape=99;return;}
        if(state.affecte){testMove(p,local);quartierSuite(30,700);return;}
        testMove(p,local);quartierSuite(1,850);return;
    }
    if(quartierEtape===30){affecterRegie(pos,false);quartierSuite(0,600);return;}
    if(quartierEtape===1){
        const changed=affecterRegie(pos,true);
        if(!verdict("ordre de travail unique",changed && !affecterRegie(pos,true) && effectifTerrain()===state.equipe-1)){quartierEtape=99;return;}
        quartierSuite(2);return;
    }
    if(quartierEtape===2){
        if(!alive(employeRegie)){if(now-quartierTemps>10000){report("ECHEC apparition employe");quartierEtape=99;}return;}
        verdict("employe present au comptoir",true);
        quartierReserve=state.reserve;testMove(p,contact);quartierSuite(3,750);return;
    }
    if(quartierEtape===3){
        startJob(pos);if(!mission){report("ECHEC commande employe");quartierEtape=99;return;}
        testMove(p,mission.pick);quartierSuite(4,650);return;
    }
    if(quartierEtape===4){
        if(!mission||mission.step!==1){if(now-quartierTemps>8000){report("ECHEC collecte");quartierEtape=99;}return;}
        testMove(p,contact);quartierSuite(5,750);return;
    }
    if(quartierEtape===5){
        if(mission)return;
        verdict("prime salariee dans la transaction",state.reserve===quartierReserve+cfg.revenu+revenuEquipe(state)+propertyIncome(state));
        testMove(p,local);quartierSuite(6,850);return;
    }
    if(quartierEtape===6){
        if(!alive(employeRegie)){if(now-quartierTemps>10000){report("ECHEC retour au comptoir");quartierEtape=99;}return;}
        quartierActeur=employeRegie;
        verdict("meme personnage rappele en escorte",affecterRegie(pos,false)&&guards[0]===quartierActeur && alive(guards[0]) && state.affecte===0);
        quartierSuite(7,650);return;
    }
    if(quartierEtape===7){
        if(!lot){verdict("droits immobiliers persistants",state.biens===3 && readState().biens===3);report("FIN parcours quartier biens="+state.biens);quartierEtape=99;return;}
        testMove(p,lot.entrance);report("porte "+lot.id+" approche");quartierSuite(8,3200);return;
    }
    if(quartierEtape===8){
        report("apres porte "+lot.id+" "+JSON.stringify(pos));
        N("SET_CHAR_COORDINATES",p,...lot.desk);quartierSuite(9,950);return;
    }
    if(quartierEtape===9){
        const id=propertyPlace(pos);
        if(id!==lot.id && now-quartierTemps<4800)return;
        report("guichet "+lot.id+" detection="+id+" pos="+JSON.stringify(pos));
        if(id===lot.id){
            const previous=state.caisse,wasOwned=(state.biens&lot.bit)!==0;
            const bought=buyProperty(id,pos);
            verdict("achat "+id+" et refus du doublon",(wasOwned||bought) && !buyProperty(id,pos) && state.caisse===previous-(wasOwned?0:lot.price));
        }else verdict("entree et sol "+lot.id,false);
        testMove(p,lot.entrance);quartierSuite(10,2400);return;
    }
    if(quartierEtape===10){quartierLot++;quartierSuite(7,600);}
}
