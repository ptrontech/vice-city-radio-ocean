// Carnet d'endurance. Le moteur conserve l'animation de sprint, la physique et les commandes de Tommy.
// Référence Sanny Builder VC : 0330 SET_PLAYER_NEVER_GETS_TIRED. Il n'existe pas de getter symétrique.
const sprintFile="sport.ini";
const sprintRanks=["Debutant","Habitue de la plage","Coureur","Marathonien"];
const configuredSprint=Array.isArray(cfg.seuilsSprint)?cfg.seuilsSprint:[];
const sprintGoals=configuredSprint.length===3 && configuredSprint.every(
    (v,i)=>Number.isSafeInteger(v)&&v>=10&&(i===0||v>configuredSprint[i-1])
)?configuredSprint:[250,750,1500];
const sprintLastGoal=sprintGoals[2];
const sprintPad=Number.isInteger(cfg.boutonSprint)&&cfg.boutonSprint>=0&&cfg.boutonSprint<=19?cfg.boutonSprint:16;
const sprintKey=Number.isInteger(cfg.toucheSprint)&&cfg.toucheSprint>=0&&cfg.toucheSprint<=254?cfg.toucheSprint:16;
let sport=null, sprintLast=null, sprintFraction=0, sprintApplied=null, sprintConfirm=false;
let sprintNextCheck=0, sprintRetryAfter=0;
function storedSport(value) {
    if(typeof value!=="string")return null;
    const parts=value.split("~");
    if(parts.length!==2||hash(parts[0])!==parts[1])return null;
    const n=parts[0].split(",").map(Number);
    if(n.length!==5||n[0]!==1||n.some(x=>!Number.isSafeInteger(x)||x<0)||n[3]>1||n[4]>1)return null;
    return {revision:n[1],metres:n[2],suivi:n[3]===1,brevet:n[4]===1};
}
function loadSport(){
    if(sport)return sport;
    const slots=["a","b"].map(key=>storedSport(readKey(sprintFile,key))).filter(Boolean);
    sport=slots.sort((a,b)=>b.revision-a.revision)[0]||{revision:0,metres:0,suivi:true,brevet:false};
    return sport;
}
function saveSport(next){
    const rev=loadSport().revision+1;
    const body=[1,rev,next.metres,Number(next.suivi),Number(next.brevet)].join(",");
    const record=body+"~"+hash(body),slot=rev%2?"a":"b";
    writeKey(sprintFile,slot,record);
    if(readKey(sprintFile,slot)!==record){
        if(Date.now()>sprintRetryAfter)say("Le carnet d'endurance ne peut pas etre enregistre.");
        sprintRetryAfter=Date.now()+5000;
        return false;
    }
    sport={...next,revision:rev};sprintRetryAfter=0;
    return true;
}
function sprintRank(metres){
    return sprintGoals.filter(goal=>metres>=goal).length;
}
function sprintStoreDistance(){
    const current=loadSport();
    // L'unité d'entraînement est une tranche complète de dix mètres, conservée immédiatement.
    const gained=Math.floor(sprintFraction/10)*10;
    if(!gained||Date.now()<sprintRetryAfter)return;
    const next=Math.min(sprintLastGoal,current.metres+gained);
    if(!saveSport({...current,metres:next}))return;
    sprintFraction-=gained;
    if(sprintRank(next)>sprintRank(current.metres))say("Endurance : "+sprintRanks[sprintRank(next)]+" !");
}
function suspendSprint(){
    sprintLast=null;sprintNextCheck=0;sprintApplied=null;sprintConfirm=false;
}
function tickSprint(player,free,now){
    if(!free||player==null){suspendSprint();return;}
    const current=loadSport();
    if(now<sprintNextCheck&&sprintNextCheck-now<=200)return;
    sprintNextCheck=now+180;
    if(N("IS_CHAR_IN_ANY_CAR",player)||N("IS_CHAR_IN_WATER",player)){
        sprintLast=null;return;
    }
    if(current.brevet&&sprintApplied!==player){
        // Operation uniquement additive. Une récompense déjà obtenue par les missions d'ambulancier est préservée.
        N("SET_PLAYER_NEVER_GETS_TIRED",0,true);sprintApplied=player;
    }
    if(!current.suivi||current.metres>=sprintLastGoal||menu){sprintLast=null;return;}
    const pressed=N("IS_BUTTON_PRESSED",0,sprintPad)||(sprintKey!==0&&N("IS_KEY_PRESSED",sprintKey));
    if(!pressed){sprintLast=null;return;}
    const point=posOf(player), previous=sprintLast;
    sprintLast={x:point.x,y:point.y,z:point.z,at:now,ped:player};
    if(!previous||previous.ped!==player)return;
    const seconds=(now-previous.at)/1000;
    if(seconds<.10||seconds>.65)return;
    const distance=Math.hypot(point.x-previous.x,point.y-previous.y);
    const speed=distance/seconds;
    if(speed<4.5||speed>12||Math.abs(point.z-previous.z)>Math.max(1.4,distance*.8))return;
    sprintFraction+=distance;
    sprintStoreDistance();
}
function sprintGrant(){
    const current=loadSport();
    if(current.brevet||(!["Libre","Validation"].includes(mode)&&current.metres<sprintLastGoal))return false;
    if(!saveSport({...current,brevet:true}))return false;
    sprintApplied=null;sprintConfirm=false;
    say("Brevet acquis. Utilise la commande Sprint de GTA pour courir sans fatigue.");return true;
}
function drawSprintMenu(){
    const current=loadSport(),rank=sprintRank(current.metres);
    ImGui.TextWrapped("Endurance | "+sprintRanks[rank]+" | "+current.metres+" m");
    ImGui.TextWrapped("A pied, avance avec la commande Sprint de GTA. Au clavier PC d'origine : Maj gauche. Tu peux l'affecter dans les commandes du jeu.");
    if(!current.brevet){
        if(rank<sprintGoals.length)ImGui.TextWrapped("Prochain grade a "+sprintGoals[rank]+" m. Brevet de sprint sans fatigue a "+sprintLastGoal+" m.");
        if(mode==="Libre"||mode==="Validation"||current.metres>=sprintLastGoal){
            if(sprintConfirm){
                ImGui.TextWrapped("Ce brevet est permanent pour ce profil. Une sauvegarde GTA faite ensuite peut aussi le conserver.");
                button("Confirmer le brevet permanent",sprintGrant);
                button("Annuler le brevet",()=>{sprintConfirm=false;});
            }else button("Choisir le sprint sans fatigue",()=>{sprintConfirm=true;});
        }
    }else ImGui.TextWrapped("Brevet actif : Tommy peut sprinter sans limite quand son arme et le jeu le permettent.");
    button(current.suivi?"Suspendre le carnet sportif":"Reprendre le carnet sportif",()=>{
        if(saveSport({...current,suivi:!current.suivi})){
            sprintLast=null;sprintConfirm=false;
            say(sport.suivi?"Entrainement repris.":"Entrainement en pause.");
        }
    });
    button("Revenir au journal",()=>{sprintConfirm=false;openMenu("journal");});
}
