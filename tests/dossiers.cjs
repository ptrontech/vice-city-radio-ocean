const {test}=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs"), path=require("node:path"), vm=require("node:vm");
const projet=path.resolve(__dirname,"..");
const at=a=>({x:a[0],y:a[1],z:a[2]});
function monde(){
    const cfg=JSON.parse(fs.readFileSync(path.join(projet,"config.json"),"utf8"));cfg.racine="essai/";
    const disk=new Map(),peds=new Map();
    const sim={disque:true,car:false,interieur:false,temps:3500,modele:true,quai:true,modeles:[],liberes:[],tues:[]};
    let id=50;
    const ctx={CONFIG:cfg,ONMISSION:false,log(){},propertyIncome:()=>130,revenuEquipe:()=>0,
        quaiRendezvous:[-780.5,-284,8.33],quaiReady:()=>sim.quai};
    ctx.native=(cmd,...a)=>{
        switch(cmd){
        case "READ_STRING_FROM_INI_FILE":return disk.get(a.join("|"))||"";
        case "WRITE_STRING_TO_INI_FILE":if(sim.disque)disk.set(a.slice(1).join("|"),a[0]);return sim.disque;
        case "IS_CHAR_IN_ANY_CAR":return sim.car;
        case "GET_PLAYER_CHAR":return 1;
        case "GET_GAME_TIMER":return sim.temps;
        case "GET_CLOSEST_CHAR_NODE":return {nodeX:a[0]+.5,nodeY:a[1],nodeZ:a[2]-1};
        case "GET_GROUND_Z_FOR_3D_COORD":return a[2]-6;
        case "REQUEST_MODEL":sim.modeles.push(a[0]);return;
        case "HAS_MODEL_LOADED":return sim.modele;
        case "MARK_MODEL_AS_NO_LONGER_NEEDED":sim.liberes.push(a[0]);return;
        case "CREATE_CHAR":++id;peds.set(id,{x:a[2],y:a[3],z:a[4]});return id;
        case "GET_CHAR_COORDINATES":return peds.get(a[0]);
        case "DOES_CHAR_EXIST":return peds.has(a[0]);
        case "IS_CHAR_DEAD":return false;
        case "DELETE_CHAR":peds.delete(a[0]);sim.tues.push(a[0]);return;
        case "ADD_SPHERE":case "ADD_BLIP_FOR_COORD":return ++id;
        case "REMOVE_SPHERE":case "REMOVE_BLIP":case "CHANGE_BLIP_COLOUR":case "CHANGE_BLIP_DISPLAY":
        case "CHANGE_BLIP_SCALE":case "SET_CHAR_HEADING":case "SET_CHAR_OBJ_WAIT_ON_FOOT":return;
        default:throw Error(cmd);
        }
    };
    vm.createContext(ctx);
    for(const f of ["00_demarrage.js","05_reportage.js","09_dossiers.js"])vm.runInContext(fs.readFileSync(path.join(projet,"jeu",f),"utf8"),ctx);
    ctx.ines=at(cfg.contact);
    const run=code=>vm.runInContext(code,ctx);
    run("change(s=>{s.missions=1;s.local=1;})");
    sim.ctx=ctx;sim.run=run;sim.peds=peds;sim.disk=disk;
    sim.demarre=id=>run("commencerDossier("+JSON.stringify(id)+",ines)");
    sim.temoin=()=>{ctx.ici=at(run("mission.point"));run("tickJob(ici)");};
    return sim;
}
test("les quatre archives sont ouvertes dans tout ordre ; Pablo déverrouillé et chaque paiement unique",()=>{
    const m=monde(), r=m.run;assert.equal(m.demarre("medellin"),false);
    const depart=r("state.caisse");
    for(const id of ["faroles","kodra","mangle","volna","medellin"]){
        assert.equal(m.demarre(id),true);m.temoin();
        assert.equal(r("temoinProche(ici)"),true);assert.equal(r("enregistrerTemoin(ici)"),true);
        assert.equal(r("enregistrerTemoin(ici)"),false);
        assert.equal(r("remettreDossier(ici)"),false);assert.equal(r("remettreDossier(ines)"),true);
        assert.equal(r("remettreDossier(ines)"),false);assert.equal(m.demarre(id),false);
    }
    assert.equal(r("readState().dossiers"),31);assert.equal(r("state.caisse"),depart+1920);
    assert.equal(r("state.reserve"),5*230);assert.equal(r("state.missions"),6);
    assert.equal(m.peds.size,0);
});
test("la sauvegarde précédente migre, et un échec d'écriture conserve la bande",()=>{
    const m=monde(),r=m.run;
    assert.equal(r('unpack("2,15,8,650,1,1,5,450,3,0~"+hash("2,15,8,650,1,1,5,450,3,0")).dossiers'),0);
    assert.equal(r('unpack("3,15,8,650,1,1,5,450,3,0,16~"+hash("3,15,8,650,1,1,5,450,3,0,16"))'),null);
    m.demarre("kodra");m.temoin();r("enregistrerTemoin(ici)");m.disque=false;
    assert.equal(r("remettreDossier(ines)"),false);assert.equal(r("mission.step"),1);
    assert.equal(r("state.dossiers"),0);m.disque=true;assert.equal(r("remettreDossier(ines)"),true);
});
test("véhicule, étage distinct, suspension, abandon et plateforme non chargée",()=>{
    const m=monde(),r=m.run;m.ctx.ONMISSION=true;assert.equal(m.demarre("mangle"),false);m.ctx.ONMISSION=false;
    m.car=true;assert.equal(m.demarre("mangle"),false);m.car=false;m.demarre("mangle");m.temoin();
    assert.equal(r("temoinProche({...ici,z:ici.z+5})"),false);m.car=true;assert.equal(r("enregistrerTemoin(ici)"),false);
    m.car=false;r("cancelJob('')");assert.equal(m.peds.size,0);assert.equal(r("state.dossiers"),0);
    r("change(s=>s.dossiers=15)");m.quai=false;m.demarre("medellin");m.temoin();assert.equal(m.peds.size,0);
    m.quai=true;m.temoin();assert.equal(m.peds.size,1);assert.equal(r("mission.fiche.nom"),"Pablo Escobar");
    m.temps=r("mission.stop")+1;r("tickJob(ici)");assert.equal(r("mission"),null);assert.equal(m.peds.size,0);
});
