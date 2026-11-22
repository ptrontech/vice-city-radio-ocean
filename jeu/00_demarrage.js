// Radio Océan, extension originale pour CLEO Redux, Vice City classique.
const N = native;
const sessionFile = CONFIG.racine+"atelier-session.ini";
const modeLu = N("READ_STRING_FROM_INI_FILE", sessionFile, "atelier", "profil");
const mode = ["Campagne","Libre","Validation"].includes(modeLu) ? modeLu : "Campagne";
const dir = CONFIG.racine+mode + "/";
const cfg = CONFIG;
const contact = cfg.contact, local = cfg.local;
const noms = ["Rafa", "Mina", "Leon", "Vera"];
const roles = ["garde rapproche", "soutien", "chauffeur", "veteran"];
const grades = ["Inconnu", "Habitue", "Associe", "Capitaine", "Figure de Vice"];
const initial = {generation:0, missions:mode==="Libre"?3:0, caisse:mode==="Libre"?1800:0, local:0, equipe:0, xp:0, reserve:0, biens:0, affecte:0};
function hash(s) {
    let value = 5381;
    for (let i=0;i<s.length;i++) value=(value*33+s.charCodeAt(i))>>>0;
    return value.toString(36);
}
function unpack(s) {
    if (!s || typeof s!=="string") return null;
    const [payload, summed] = s.split("~");
    if (hash(payload)!==summed) return null;
    const nums = payload.split(",").map(Number);
    if (nums.some(n=>!Number.isSafeInteger(n)||n<0) || nums[4]>1 || nums[5]>4) return null;
    if (!((nums[0]===1 && nums.length===8) || (nums[0]===2 && nums.length===10))) return null;
    const [,generation,missions,caisse,owned,equipe,xp,reserve,biens=0,affecte=0]=nums;
    if(biens>3 || affecte>1 || (affecte && (!owned || !equipe)))return null;
    return {generation,missions,caisse,local:owned,equipe,xp,reserve,biens,affecte};
}
function readKey(file, key) {
    return N("READ_STRING_FROM_INI_FILE",dir+file,"atelier",key) || "";
}
function writeKey(file,key,value) {
    return N("WRITE_STRING_TO_INI_FILE",String(value),dir+file,"atelier",key);
}
function readState() {
    const valid=["a","b"].map(k=>unpack(readKey("progression.ini",k))).filter(Boolean);
    return valid.sort((a,b)=>b.generation-a.generation)[0] || {...initial};
}
let state=readState();
let message="", menu="", noticeUntil=0, selected=0, focusCount=0, held={}, accept=false;
let mission=null, objective=null, hubs=[], pedContact=null, guards=[], order="suivre", lastVehicle=0;
let pending=null, reply="", proposal="aucune", exchange=0, memoryLabel="";
const bootId=Date.now().toString(36)+"-"+Math.floor(Math.random()*65536).toString(36);
function say(text) {
    message=text; noticeUntil=Date.now()+6500; log("Radio Ocean | "+text);
}
function change(edit) {
    const next={...state};
    edit(next);
    next.generation++;
    const p=[2,next.generation,next.missions,next.caisse,next.local,next.equipe,next.xp,next.reserve,next.biens,next.affecte].join(",");
    const key=next.generation%2 ? "a":"b", packed=p+"~"+hash(p);
    writeKey("progression.ini",key,packed);
    if (readKey("progression.ini",key)!==packed) {say("Sauvegarde indisponible. Reessaie avant de continuer.");return false;}
    state=next;return true;
}
function capacity() {return Math.min(4,cfg.reputation.filter(n=>state.missions>=n).length);}
function near(pos,place,dist) {return Math.hypot(pos.x-place[0],pos.y-place[1])<=dist && Math.abs(pos.z-place[2])<7;}
function clockNow(){return N("GET_GAME_TIMER");}
function posOf(handle){return N("GET_CHAR_COORDINATES",handle);}
function ground(p) {const z=N("GET_GROUND_Z_FOR_3D_COORD",p[0],p[1],p[2]+5);return z>p[2]-4 && z<p[2]+4 ? z+1:p[2];}
function mark(p,color) {
    const blip=N("ADD_BLIP_FOR_COORD",...p);
    N("CHANGE_BLIP_COLOUR",blip,color);
    N("CHANGE_BLIP_DISPLAY",blip,3);
    N("CHANGE_BLIP_SCALE",blip,3);
    return blip;
}
function alive(h){return h!==null && h!==undefined && N("DOES_CHAR_EXIST",h)&&!N("IS_CHAR_DEAD",h);}
function removePed(h) {if(h!==null && h!==undefined && N("DOES_CHAR_EXIST",h)) N("DELETE_CHAR",h);}
function clearObjective() {
    if(!objective)return;
    N("REMOVE_BLIP",objective.blip); N("REMOVE_SPHERE",objective.sphere); objective=null;
}
function target(p){clearObjective();objective={blip:mark(p,4),sphere:N("ADD_SPHERE",...p,2.1)};}
function quiet() {
    cancelJob(""); clearObjective(); menu=""; lastVehicle=0;
    hubs.forEach(b=>N("REMOVE_BLIP",b));hubs=[];
    removePed(pedContact);pedContact=null; guards.forEach(removePed);guards=[];nettoyerEmployeRegie();
}
function openMenu(kind) {menu=kind;selected=0;holdOpen=false;}
function brief() {if(mission && mission.kind==="reportage")return ["Viens au News Cafe en voiture avec une place libre.","Conduis Alma au repere et arrete la voiture.","Attends la descente de la journaliste."][mission.step];return mission ? (mission.step===0?"Recupere la bande au repere jaune.":"Rapporte la bande a Ines."):"Une cassette manque au programme de ce soir.";}
function startJob(pos) {
    if(mission||!near(pos,contact,10))return;
    mission={kind:"bande",step:0,stop:clockNow()+cfg.delaiSecondes*1000,pick:cfg.collectes[state.missions%cfg.collectes.length]};
    target(mission.pick);menu="";say("Derniere bande avant minuit. "+brief());
}
function tickJob(pos) {
    if(!mission)return;
    if(clockNow()>mission.stop){cancelJob("Delai expire. La radio te proposera une autre course.");return;}
    if(mission.kind==="reportage"){tickReport(pos,N("GET_PLAYER_CHAR",0));return;}
    if(mission.step===0 && near(pos,mission.pick,5)) {
        mission.step=1;target(contact);say("Bande recuperee. Retourne voir Ines.");return;
    }
    if(mission.step===1 && near(pos,contact,5)) {
        if(change(s=>{s.missions++;s.caisse+=cfg.prime;s.xp+=s.equipe;s.reserve+=(s.local?cfg.revenu:0)+revenuEquipe(s)+propertyIncome(s);})) {
            clearObjective();mission=null;say("Emission livree. +"+cfg.prime+" $. Reputation "+state.missions+".");
        }
    }
}
function buy(pos) {
    if (!near(pos,local,9)||state.local||state.caisse<cfg.prixLocal) return false;
    if (!change(s=>{s.local=1;s.caisse-=cfg.prixLocal;}))return false;
    say("Le local est a toi. Chaque prochaine livraison alimente sa caisse.");return true;
}
function collect(pos) {
    if (!near(pos,local,9)||!state.local||state.reserve===0)return false;
    const amount=state.reserve;
    if(!change(s=>{s.caisse+=s.reserve;s.reserve=0;}))return false;
    say("Recette retiree : "+amount+" $.");return true;
}
function recruit(pos) {
    if(!near(pos,contact,10)||state.equipe>=capacity()||state.caisse<cfg.prixGarde)return false;
    if(!change(s=>{s.equipe++;s.caisse-=cfg.prixGarde;}))return false;
    order="suivre";say(noms[state.equipe-1]+" rejoint la radio.");return true;
}
function dismiss(){if(!state.equipe)return;if(change(s=>{s.equipe--;s.affecte=Math.min(s.affecte,s.equipe);})){removePed(guards.pop());if(!state.affecte)nettoyerEmployeRegie();say("Contrat termine.");}}
function population(pos,player,now) {
    if(!hubs.length){hubs=[mark(contact,5),mark(local,1),...propertyMapMarks()];}
    if(near(pos,contact,75) && !alive(pedContact)){
        N("REQUEST_MODEL",21);
        if(N("HAS_MODEL_LOADED",21)) {
            removePed(pedContact);pedContact=N("CREATE_CHAR",5,21,contact[0]+1.5,contact[1],ground(contact));
            N("SET_CHAR_HEADING",pedContact,95);N("SET_CHAR_OBJ_WAIT_ON_FOOT",pedContact);N("MARK_MODEL_AS_NO_LONGER_NEEDED",21);
        }
    } else if(pedContact!==null && !near(pos,contact,110)) {removePed(pedContact);pedContact=null;}
    const inCar=N("IS_CHAR_IN_ANY_CAR",player);
    const vehicle=inCar?N("STORE_CAR_CHAR_IS_IN_NO_SAVE",player):0;
    const seatCount=vehicle?N("GET_MAXIMUM_NUMBER_OF_PASSENGERS",vehicle):0;
    let free=0;
    for(let seat=0;seat<seatCount;seat++)if(N("IS_CAR_PASSENGER_SEAT_FREE",vehicle,seat))free++;
    tickEmployeRegie(pos);
    for(let i=premierGardeTerrain();i<state.equipe;i++){
        const model=[15,21,28,19][i];
        let h=guards[i];
        if(!alive(h)){
            if(h!==undefined&&h!==null){removePed(h);guards[i]=null;}
            if(order==="attendre"||(!near(pos,contact,25)&&!peutRejoindreRegie(i,pos))||inCar)continue;
            N("REQUEST_MODEL",model);if(!N("HAS_MODEL_LOADED",model))continue;
            h=N("CREATE_CHAR",4,model,pos.x+1.5+i,pos.y-1.5,pos.z);
            N("SET_CHAR_HEALTH",h,115+15*i);N("SET_CHAR_AS_PLAYER_FRIEND",h,0,true);
            N("SET_CHAR_HEED_THREATS",h,true);guards[i]=h;
            N("MARK_MODEL_AS_NO_LONGER_NEEDED",model);
        }
        if(order==="attendre")continue;
        if(vehicle){
            if(!N("IS_CHAR_IN_ANY_CAR",h)&&free>0 && (vehicle!==lastVehicle||now%4000<620)){
                N("SET_CHAR_OBJ_ENTER_CAR_AS_PASSENGER",h,vehicle);free--;
            }
        }else if(N("IS_CHAR_IN_ANY_CAR",h)) {
            if (lastVehicle || now%4000<620) N("SET_CHAR_OBJ_LEAVE_ANY_CAR",h);
        }else if(lastVehicle || now%3000<620 || (order==="suivre" && now%2000<620)){
            N("SET_CHAR_AS_LEADER",h,player);
        }
    }
    lastVehicle=vehicle;
}
function setOrder(next) {
    order=next;for(const h of guards){if(!alive(h))continue;N("SET_CHAR_OBJ_NO_OBJ",h);
      if(next==="attendre"){N("SET_CHAR_OBJ_WAIT_ON_FOOT",h);}
      else {N("SET_CHAR_AS_LEADER",h,N("GET_PLAYER_CHAR",0));}}
    say(next==="attendre"?"L'equipe attend ici.":"L'equipe te suit et prend les places disponibles.");
}
log("Radio Ocean | profil "+mode+" | generation "+state.generation);
