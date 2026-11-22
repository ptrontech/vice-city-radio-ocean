// node tests/frequence.cjs
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const vm=require("node:vm");
const dir=path.join(__dirname,"../jeu");
const realCfg=JSON.parse(fs.readFileSync(path.join(__dirname,"../config.json"),"utf8"));
const at=p=>({x:p[0],y:p[1],z:p[2]});

function world({collectes,onMission,state={}}={}) {
    const cfg=JSON.parse(JSON.stringify(realCfg));cfg.racine="jeu/";
    if(collectes)cfg.collectes=collectes;
    const disk=new Map(),peds=new Map(),blips=new Set(),spheres=new Set(),dead=new Set();
    const w={peds,blips,spheres,dead,disk,deleted:[],released:[],requested:0,modelFreed:0,loaded:true,inCar:false,
        writable:true,time:100,playerPos:[0,0,0],unknown:[],said:[],miloCar:null,car:45,freeSeat:true,speed:0,entrees:[],sorties:[]};
    let next=500;
    const ctx={
        CONFIG:cfg,log:()=>{},propertyIncome:()=>45,
        native(name,...a){
            switch(name){
            case "READ_STRING_FROM_INI_FILE":return a[2]==="profil"?"Validation":disk.get(a.join("|"))||"";
            case "WRITE_STRING_TO_INI_FILE":if(w.writable)disk.set(a.slice(1).join("|"),a[0]);return true;
            case "GET_GAME_TIMER":return w.time;
            case "GET_PLAYER_CHAR":return 1;
            case "DOES_CHAR_EXIST":return a[0]===1||peds.has(a[0]);
            case "IS_CHAR_DEAD":return dead.has(a[0]);
            case "IS_CHAR_IN_ANY_CAR":return a[0]===1?w.inCar:w.miloCar!==null;
            case "STORE_CAR_CHAR_IS_IN_NO_SAVE":return w.car;
            case "IS_CHAR_IN_CAR":return w.miloCar===a[1];
            case "GET_CAR_SPEED":return w.speed;
            case "GET_MAXIMUM_NUMBER_OF_PASSENGERS":return 1;
            case "IS_CAR_PASSENGER_SEAT_FREE":return w.freeSeat;
            case "SET_CHAR_OBJ_ENTER_CAR_AS_PASSENGER":w.entrees.push(a);return;
            case "SET_CHAR_OBJ_LEAVE_ANY_CAR":w.sorties.push(a[0]);return;
            case "REQUEST_MODEL":w.requested++;return;
            case "HAS_MODEL_LOADED":return w.loaded;
            case "MARK_MODEL_AS_NO_LONGER_NEEDED":w.modelFreed++;return;
            case "GET_GROUND_Z_FOR_3D_COORD":return a[2]-5;
            case "CREATE_CHAR":{const h=next++;peds.set(h,{x:a[2],y:a[3],z:a[4]});return h;}
            case "DELETE_CHAR":peds.delete(a[0]);w.deleted.push(a[0]);return;
            case "MARK_CHAR_AS_NO_LONGER_NEEDED":w.released.push(a[0]);return;
            case "GET_CHAR_COORDINATES":return peds.get(a[0])||at(w.playerPos);
            case "SET_CHAR_HEADING":case "SET_CHAR_OBJ_WAIT_ON_FOOT":case "SET_CHAR_OBJ_NO_OBJ":case "SET_CHAR_AS_LEADER":
            case "CHANGE_BLIP_COLOUR":case "CHANGE_BLIP_DISPLAY":case "CHANGE_BLIP_SCALE":return;
            case "ADD_BLIP_FOR_COORD":{const b=next++;blips.add(b);return b;}
            case "REMOVE_BLIP":blips.delete(a[0]);return;
            case "ADD_SPHERE":{const s=next++;spheres.add(s);return s;}
            case "REMOVE_SPHERE":spheres.delete(a[0]);return;
            }
            w.unknown.push(name);throw new Error("Commande hors perimetre : "+name);
        }
    };
    if(onMission!==undefined)ctx.ONMISSION=onMission;
    vm.createContext(ctx);
    for(const f of ["00_demarrage.js","05_reportage.js","06_frequence.js","11_affectations.js"])
        vm.runInContext(fs.readFileSync(path.join(dir,f),"utf8"),ctx);
    ctx.at=at;
    w.ctx=ctx;w.run=s=>vm.runInContext(s,ctx);
    w.run("change(s=>{s.missions=1;s.local=1;s.equipe=1;s.affecte=1;})");
    for(const [k,v] of Object.entries(state))w.run("change(s=>{s."+k+"="+v+";})");
    w.start=()=>{w.playerPos=cfg.contact;return w.run("startFrequency(at(contact))");};
    w.tick=p=>{w.time+=500;w.playerPos=p;w.run("tickJob(at("+JSON.stringify(p)+"))");};
    w.cfg=cfg;
    return w;
}
function walkToMeeting(w){
    const lieux=w.run("mission.places");
    for(let i=0;i<lieux.length-1;i++)w.tick(lieux[i]);
    w.tick(lieux[lieux.length-1]);// Milo apparait
    w.tick(lieux[lieux.length-1]);// rencontre
    return lieux;
}
let passes=0;
function test(label,fn){fn();passes++;console.log("OK",label);}

test("lieux : filtre les reperes invalides, garde 2 ou 3 lieux et refuse moins de deux",()=>{
    let w=world();assert.equal(w.start(),true);
    const lieux=w.run("mission.places");
    assert.equal(lieux.length,3);
    for(const p of lieux)assert.ok(realCfg.collectes.some(q=>q.join()===p.join()));
    assert.equal(w.run("mission.kind"),"frequence");
    assert.equal(w.blips.size,1+0+w.run("hubs.length"));assert.equal(w.spheres.size,1);
    w=world({collectes:[[1,2,3],[1,2,3],[NaN,0,0],[5,5],null,"x",[9,9,12]]});
    assert.equal(w.start(),true);assert.equal(w.run("mission.places.length"),2);
    w=world({collectes:[[1,2,3],[1,2,3],[1,"a",3]]});
    assert.equal(w.start(),false);assert.equal(w.run("mission"),null);
    w=world({collectes:undefined});w.cfg.collectes=[];
    assert.equal(world({collectes:[]}).start(),false);
    // La rotation suit la reputation sans quitter les lieux valides.
    const a=world({state:{missions:2}});a.start();
    assert.equal(a.run("mission.places.length"),3);
    assert.notDeepEqual(a.run("mission.places[0]"),lieux[0]);
});

test("eligibilite : reputation, distance, a pied, mission Rockstar et mission deja active",()=>{
    let w=world({state:{missions:0}});
    // missions=0 n'est pas restaurable par change() ; on force via une transaction.
    w.run("change(s=>{s.missions=0;})");assert.equal(w.start(),false);
    w=world();w.playerPos=w.cfg.contact;
    assert.equal(w.run("startFrequency({x:contact[0]+40,y:contact[1],z:contact[2]})"),false);
    w.inCar=true;assert.equal(w.run("startFrequency(at(contact))"),false);w.inCar=false;
    assert.equal(w.run("startFrequency(null)"),false);
    assert.equal(w.run("startFrequency({x:NaN,y:0,z:0})"),false);
    w=world({onMission:true});assert.equal(w.start(),false);assert.equal(w.run("mission"),null);
    w.ctx.ONMISSION=false;assert.equal(w.start(),true);
    assert.equal(w.run("startFrequency(at(contact))"),false);// deja une mission
    w=world();w.run("mission={kind:'bande',step:0,stop:9999}");assert.equal(w.start(),false);
    assert.equal(w.run("mission.kind"),"bande");
});

test("scenario complet : indices, rencontre a pied, retour et paiement unique",()=>{
    const w=world();w.start();
    const brief0=w.run("frequencyBrief()");assert.match(brief0,/Indice 1/);
    const gen0=w.run("state.generation"),before=w.run("({...state})");
    const lieux=w.run("mission.places");
    w.tick(lieux[2]);assert.equal(w.run("mission.step"),0);// hors ordre : pas d'avance
    w.tick(lieux[0]);assert.equal(w.run("mission.step"),1);
    assert.notEqual(w.run("frequencyBrief()"),brief0);
    w.tick(lieux[1]);assert.equal(w.run("mission.step"),2);
    assert.equal(w.peds.size,0);
    w.loaded=false;w.tick(lieux[2]);assert.equal(w.peds.size,0);assert.equal(w.run("mission.model"),true);
    w.loaded=true;w.tick(lieux[2]);assert.equal(w.peds.size,1);assert.equal(w.run("mission.model"),false);
    // en voiture : pas de rencontre
    w.inCar=true;w.tick(lieux[2]);assert.equal(w.run("mission.step"),2);w.inCar=false;
    // trop loin de Milo
    w.tick([lieux[2][0]-5.5,lieux[2][1],lieux[2][2]]);assert.equal(w.run("mission.step"),2);
    w.tick(lieux[2]);assert.equal(w.run("mission.step"),3);
    assert.equal(w.run("state.generation"),gen0);assert.equal(w.run("state.caisse"),before.caisse);
    const milo=[...w.peds.keys()][0];
    // retour sans Milo a portee : pas de paiement
    w.peds.set(milo,{x:0,y:0,z:12});w.tick(w.cfg.contact);
    assert.equal(w.run("mission.kind"),"frequence");assert.equal(w.run("state.generation"),gen0);
    w.peds.set(milo,{x:w.cfg.contact[0]+3,y:w.cfg.contact[1],z:12});
    w.tick(w.cfg.contact);w.tick(w.cfg.contact);w.tick(w.cfg.contact);
    const s=w.run("({...state})");
    assert.equal(s.caisse,before.caisse+440);assert.equal(s.missions,before.missions+1);
    assert.equal(s.xp,before.xp+before.equipe);
    assert.equal(s.reserve,before.reserve+w.cfg.revenu+50+45);
    assert.equal(s.generation,gen0+1);
    assert.equal(w.run("mission"),null);
    assert.equal(w.blips.size,w.run("hubs.length"));assert.equal(w.spheres.size,0);
    assert.deepEqual(w.deleted,[]);assert.deepEqual(w.released,[milo]);assert.ok(w.peds.has(milo));
    assert.equal(w.requested,w.modelFreed>0?w.requested:-1);
});

test("paiement : sauvegarde indisponible puis reprise sans double credit",()=>{
    const w=world();w.start();walkToMeeting(w);
    const milo=[...w.peds.keys()][0];w.peds.set(milo,{x:w.cfg.contact[0]+2,y:w.cfg.contact[1],z:12});
    const g=w.run("state.generation"),c=w.run("state.caisse");
    w.writable=false;w.tick(w.cfg.contact);
    assert.equal(w.run("state.caisse"),c);assert.equal(w.run("state.generation"),g);
    assert.equal(w.run("mission.paid"),false);assert.ok(w.peds.has(milo));
    w.writable=true;w.tick(w.cfg.contact);w.tick(w.cfg.contact);
    assert.equal(w.run("state.caisse"),c+440);assert.equal(w.run("state.generation"),g+1);
});

test("nettoyage : abandon, delai, Milo mort et mission Rockstar liberent PNJ, modele et reperes",()=>{
    const cas=[
        ["abandon",w=>{w.run("frequenceAbandon('Course abandonnee.')");}],
        ["abandon depuis le journal",w=>{w.run("cancelJob('x')");}],
        ["delai",w=>{w.time=w.run("mission.stop")+1;w.tick(w.cfg.contact);}],
        ["Milo mort",w=>{w.dead.add([...w.peds.keys()][0]);w.tick(w.cfg.contact);}],
        ["mission Rockstar",w=>{w.ctx.ONMISSION=true;w.tick(w.cfg.contact);}]
    ];
    for(const [nom,agir] of cas){
        const w=world();w.start();walkToMeeting(w);
        const milo=[...w.peds.keys()][0];assert.equal(w.run("mission.step"),w.run("mission.places.length"));
        const g=w.run("state.generation"),c=w.run("state.caisse");
        agir(w);
        assert.equal(w.run("mission"),null,nom);assert.equal(w.peds.has(milo),false,nom);
        assert.deepEqual(w.deleted,[milo],nom);assert.equal(w.spheres.size,0,nom);
        assert.equal(w.blips.size,w.run("hubs.length"),nom);
        assert.equal(w.run("state.caisse"),c,nom);assert.equal(w.run("state.generation"),g,nom);
        w.run("clearFrequency(mission)");assert.deepEqual(w.deleted,[milo],nom);
    }
    // Abandon pendant le chargement du modele : demande liberee, aucun PNJ.
    const w=world();w.start();const l=w.run("mission.places");
    w.tick(l[0]);w.tick(l[1]);w.loaded=false;w.tick(l[2]);
    assert.equal(w.run("mission.model"),true);const freed=w.modelFreed;
    w.run("frequenceAbandon('')");assert.equal(w.modelFreed,freed+1);assert.equal(w.peds.size,0);
    w.run("clearFrequency({kind:'frequence',milo:null,model:false})");assert.equal(w.modelFreed,freed+1);
    // Delai ou Rockstar avant meme l'apparition de Milo.
    const x=world();x.start();x.ctx.ONMISSION=true;x.tick(x.cfg.contact);
    assert.equal(x.run("mission"),null);assert.equal(x.spheres.size,0);
});

test("Milo embarque dans une voiture arretee et descend avant le paiement au bon etage",()=>{
    const w=world();w.start();const lieux=walkToMeeting(w), depart=lieux[lieux.length-1];
    const milo=w.run("mission.milo"),caisse=w.run("state.caisse");
    assert.match(w.run("brief()"),/place libre/);
    w.inCar=true;w.freeSeat=false;w.tick(depart);
    assert.equal(w.entrees.length,0);
    w.freeSeat=true;w.speed=12;w.time+=1500;w.tick(depart);
    assert.equal(w.entrees.length,0);
    w.speed=0;w.time+=1500;w.tick(depart);w.tick(depart);
    assert.deepEqual(w.entrees,[[milo,w.car]]);
    w.miloCar=w.car;w.tick(depart);
    assert.equal(w.run("mission.trajet"),"a_bord");
    w.peds.set(milo,at(w.cfg.contact));w.tick(w.cfg.contact);
    assert.equal(w.run("state.caisse"),caisse);
    w.inCar=false;w.tick(w.cfg.contact);w.tick(w.cfg.contact);
    assert.deepEqual(w.sorties,[milo]);
    assert.equal(w.run("state.caisse"),caisse);
    w.miloCar=null;w.peds.set(milo,{...at(w.cfg.contact),z:w.cfg.contact[2]+6});
    w.tick(w.cfg.contact);assert.equal(w.run("state.caisse"),caisse);
    w.peds.set(milo,at(w.cfg.contact));w.tick(w.cfg.contact);w.tick(w.cfg.contact);
    assert.equal(w.run("state.caisse"),caisse+440);
});

test("commandes natives limitees au perimetre du projet",()=>{
    const w=world();w.start();walkToMeeting(w);
    const milo=[...w.peds.keys()][0];w.peds.set(milo,{x:w.cfg.contact[0]+1,y:w.cfg.contact[1],z:12});
    w.tick(w.cfg.contact);w.tick(w.cfg.contact);
    assert.deepEqual(w.unknown,[]);
    const src=fs.readFileSync(path.join(dir,"06_frequence.js"),"utf8");
    assert.doesNotMatch(src,/SET_CHAR_COORDINATES|child_process|require\(|eval\(|memory|Memory|KEY|keybd/);
});

console.log(passes+" groupes de tests reussis");
