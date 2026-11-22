// Le roster garde son ordre. Le premier contrat, Rafa, est le seul poste disponible à la régie.
const positionEmployeRegie=[local[0]-2,local[1]+1.5,local[2]];
let employeRegie=null, modeleEmployeDemande=false;
function premierGardeTerrain(s=state){
    return s.local===1&&s.equipe>0&&s.affecte===1?1:0;
}
function effectifTerrain(s=state){
    return s.equipe-premierGardeTerrain(s);
}
function tarifEmployeRegie(){
    const base=Number.isFinite(cfg.revenu)?Math.max(0,Math.floor(cfg.revenu)):0;
    const prime=Number.isFinite(cfg.primeEmploye)?Math.floor(cfg.primeEmploye):Math.floor(base/2);
    return Math.max(0,Math.min(250,base,prime));
}
function revenuEquipe(s){
    // Fonction pure appelée uniquement à l'intérieur du règlement d'une émission.
    return premierGardeTerrain(s)?tarifEmployeRegie():0;
}
function peutRejoindreRegie(i,pos){
    return i===0&&state.local===1&&!premierGardeTerrain()&&near(pos,local,18);
}
function libererModeleEmploye(){
    if(modeleEmployeDemande){N("MARK_MODEL_AS_NO_LONGER_NEEDED",15);modeleEmployeDemande=false;}
}
function nettoyerEmployeRegie(){
    libererModeleEmploye();
    if(employeRegie!==null)removePed(employeRegie);
    employeRegie=null;
}
function tickEmployeRegie(pos){
    if(!premierGardeTerrain()||!near(pos,local,90)){
        nettoyerEmployeRegie();return;
    }
    if(alive(employeRegie)||!near(pos,local,65))return;
    if(employeRegie!==null)nettoyerEmployeRegie();
    if(!modeleEmployeDemande){N("REQUEST_MODEL",15);modeleEmployeDemande=true;}
    if(!N("HAS_MODEL_LOADED",15))return;
    const spot=positionEmployeRegie;
    employeRegie=N("CREATE_CHAR",4,15,spot[0],spot[1],ground(spot));
    libererModeleEmploye();
    if(!alive(employeRegie)){employeRegie=null;return;}
    N("SET_CHAR_HEADING",employeRegie,120);
    N("SET_CHAR_AS_PLAYER_FRIEND",employeRegie,0,true);
    N("SET_CHAR_STAY_IN_SAME_PLACE",employeRegie,true);
    N("SET_CHAR_OBJ_WAIT_ON_FOOT",employeRegie);
}
function affecterRegie(pos,auTravail){
    if(!state.local||!state.equipe||!near(pos,local,9)||typeof auTravail!=="boolean")return false;
    if(Boolean(premierGardeTerrain())===auTravail)return false;
    if(!change(s=>{s.affecte=auTravail?1:0;}))return false;
    if(auTravail){
        // Le PNJ de terrain pouvait encore suivre ou occuper une voiture. Le poste a son propre objectif natif.
        removePed(guards[0]);guards[0]=null;
        tickEmployeRegie(pos);
        say("Rafa prend le comptoir. Sa prime sera creditee a la prochaine emission.");
    }else{
        if(state.equipe===1)order="suivre";
        if(alive(employeRegie)){
            const h=employeRegie;employeRegie=null;guards[0]=h;
            N("SET_CHAR_STAY_IN_SAME_PLACE",h,false);
            N("SET_CHAR_OBJ_NO_OBJ",h);
            N("SET_CHAR_HEED_THREATS",h,true);
            if(order==="attendre")N("SET_CHAR_OBJ_WAIT_ON_FOOT",h);
            else N("SET_CHAR_AS_LEADER",h,N("GET_PLAYER_CHAR",0));
        }else nettoyerEmployeRegie();
        say(order==="attendre"?"Rafa rejoint l'equipe qui attend sur place.":"Rafa quitte le comptoir et revient en escorte.");
    }
    return true;
}
function optionsEmployeRegie(pos){
    if(!state.local||!state.equipe)return;
    const occupe=Boolean(premierGardeTerrain());
    ImGui.TextWrapped(occupe?"Rafa tient le comptoir. Prime de "+tarifEmployeRegie()+" $ par emission.":"Poste du News Cafe disponible : "+tarifEmployeRegie()+" $ par emission.");
    if(near(pos,local,9))
        button(occupe?"Rappeler Rafa en escorte":"Affecter Rafa au comptoir",()=>affecterRegie(pos,!occupe));
    else ImGui.TextWrapped("Rends-toi au comptoir pour changer son affectation.");
}
