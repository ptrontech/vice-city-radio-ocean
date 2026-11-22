// Seconde mission de la régie. L'ingénieure utilise les places du véhicule réellement conduit.
function seatAvailable(car){
    const n=N("GET_MAXIMUM_NUMBER_OF_PASSENGERS",car);
    for(let i=0;i<n;i++)if(N("IS_CAR_PASSENGER_SEAT_FREE",car,i))return true;
    return false;
}
function cancelJob(text) {
    if(!mission)return;
    if(mission.kind==="reportage")removePed(mission.guest);
    if(mission.kind==="frequence")clearFrequency(mission);
    if(mission.kind==="dossier")finDossier(mission);
    clearObjective();mission=null;if(text)say(text);
}
function startReport(pos){
    if(mission||!state.local||!near(pos,local,10))return false;
    mission={kind:"reportage",step:0,guest:null,car:null,stop:clockNow()+cfg.delaiSecondes*1000,nextOrder:0,pick:[285,-1103,12]};
    target(local);menu="";say("Le direct du News Cafe. Viens chercher Alma en voiture avec une place libre.");return true;
}
function tickReport(pos,player) {
    const m=mission;
    if(m.guest!==null && !alive(m.guest)){cancelJob("Le direct est annule. Retourne a la regie pour reprendre.");return;}
    if(m.guest===null && near(pos,local,78)){
        N("REQUEST_MODEL",22);
        if(!N("HAS_MODEL_LOADED",22))return;
        const start=[local[0]+1,local[1],local[2]];
        m.guest=N("CREATE_CHAR",5,22,start[0],start[1],ground(start));N("SET_CHAR_OBJ_WAIT_ON_FOOT",m.guest);
        N("MARK_MODEL_AS_NO_LONGER_NEEDED",22);
    }
    if(m.guest===null)return;
    const car=N("IS_CHAR_IN_ANY_CAR",player)?N("STORE_CAR_CHAR_IS_IN_NO_SAVE",player):null;
    if(m.step===0){
        if(car===null||!near(pos,local,20))return;
        if(N("IS_CHAR_IN_CAR",m.guest,car)){
            m.step=1;m.car=car;target(m.pick);say("Alma est montee. Conduis-la au repere jaune et arrete la voiture.");return;
        }
        if(clockNow()>m.nextOrder && seatAvailable(car)){
            N("SET_CHAR_OBJ_ENTER_CAR_AS_PASSENGER",m.guest,car);m.nextOrder=clockNow()+3500;
        }
    }else if(m.step===1){
        if(N("IS_CAR_DEAD",m.car)||!N("IS_CHAR_IN_CAR",m.guest,m.car)){cancelJob("Transport interrompu. La regie attend.");return;}
        if(car===m.car && near(pos,m.pick,9) && Math.abs(N("GET_CAR_SPEED",car))<2) {
            m.step=2;N("SET_CHAR_OBJ_LEAVE_CAR",m.guest,car);say("Garde la voiture a l'arret. Alma descend pour le direct.");
        }
    }else if(!N("IS_CHAR_IN_ANY_CAR",m.guest)){
        if(change(s=>{s.missions++;s.caisse+=cfg.primeReportage;s.reserve+=cfg.revenu+revenuEquipe(s)+propertyIncome(s);s.xp+=s.equipe;})){
            // Le personnage reste dans le monde comme piéton ordinaire.
            N("MARK_CHAR_AS_NO_LONGER_NEEDED",m.guest);m.guest=null;
            cancelJob("");say("Direct a l'antenne. +"+cfg.primeReportage+" $ et une emission de reputation.");
        }
    }
}
