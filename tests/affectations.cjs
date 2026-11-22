// node tests/affectations.cjs
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const vm=require("node:vm");
const source=fs.readFileSync(path.join(__dirname,"../jeu/11_affectations.js"),"utf8");
const comptoir={x:245,y:-1226,z:12}, ailleurs={x:800,y:-400,z:12};
function fixture(initial={}) {
    const personnages=new Set([101,102]),appels=[],deleted=[],notes=[];
    const c={
        cfg:{revenu:100},state:{local:1,equipe:2,affecte:0,reserve:0,...initial},
        local:[245,-1226,12],guards:[101,102],order:"suivre",loaded:true,writable:true,version:0,
        alive:h=>personnages.has(h),removePed(h){if(personnages.delete(h))deleted.push(h);},ground:p=>p[2],
        near:(a,b,r)=>Math.hypot(a.x-b[0],a.y-b[1])<=r&&Math.abs(a.z-b[2])<7,
        change(edit){if(!c.writable)return false;const s={...c.state};edit(s);c.state=s;c.version++;return true;},
        say:msg=>notes.push(msg),
        N(name,...args){
            appels.push([name,...args]);
            if(name==="HAS_MODEL_LOADED")return c.loaded;
            if(name==="CREATE_CHAR"){const h=200+appels.length;personnages.add(h);return h;}
            if(name==="GET_PLAYER_CHAR")return 1;
        }
    };
    vm.createContext(c);vm.runInContext(source,c);
    c.nearby=comptoir;c.away=ailleurs;
    return {c,personnages,appels,deleted,run:s=>vm.runInContext(s,c)};
}
let passes=0;
function test(label,fn){fn();passes++;console.log("OK",label);}
test("ordre local atomique et protection des autres gardes",()=>{
    const f=fixture();assert.equal(f.run("affecterRegie(away,true)"),false);
    f.c.writable=false;assert.equal(f.run("affecterRegie(nearby,true)"),false);assert.ok(f.personnages.has(101));f.c.writable=true;
    assert.equal(f.run("affecterRegie(nearby,true)"),true);
    const worker=f.run("employeRegie");assert.ok(f.personnages.has(worker));
    assert.deepEqual(f.deleted,[101]);assert.ok(f.personnages.has(102));assert.equal(f.c.guards[0],null);
    assert.equal(f.run("effectifTerrain()"),1);assert.equal(f.c.state.reserve,0);assert.equal(f.c.version,1);
    assert.equal(f.run("affecterRegie(nearby,true)"),false);assert.equal(f.c.version,1);
    f.c.order="attendre";assert.equal(f.run("affecterRegie(nearby,false)"),true);
    assert.equal(f.c.guards[0],worker);assert.equal(f.c.guards[1],102);
    assert.equal(f.run("effectifTerrain()"),2);assert.equal(f.c.order,"attendre");
    assert.equal(f.c.state.reserve,0);assert.equal(f.run("revenuEquipe(state)"),0);
});
test("prime pure, bornée et sans crédit au chargement ou au retrait de service",()=>{
    const f=fixture({affecte:1});
    assert.equal(f.run("revenuEquipe(state)"),50);assert.equal(f.run("revenuEquipe(state)"),50);
    f.run("tickEmployeRegie(nearby);tickEmployeRegie(nearby)");
    assert.equal(f.c.state.reserve,0);assert.equal(f.c.version,0);
    // Une mission réussie qualifie la prime dans sa transaction de règlement.
    f.c.change(s=>{s.reserve+=f.c.cfg.revenu+f.c.revenuEquipe(s);});
    assert.equal(f.c.state.reserve,150);
    f.run("nettoyerEmployeRegie();tickEmployeRegie(nearby)");
    assert.equal(f.c.state.reserve,150);assert.equal(f.c.version,1);
    f.c.cfg.primeEmploye=999;assert.equal(f.run("revenuEquipe(state)"),100);
    f.c.cfg.revenu=700;assert.equal(f.run("revenuEquipe(state)"),250);
    f.c.cfg.primeEmploye=-50;assert.equal(f.run("revenuEquipe(state)"),0);
    const noGuard=fixture({equipe:0,affecte:1});assert.equal(noGuard.run("revenuEquipe(state)"),0);
    const noOffice=fixture({local:0,affecte:1});assert.equal(noOffice.run("revenuEquipe(state)"),0);
});
test("chargement différé, libération du modèle et un seul employé quand on revient",()=>{
    const f=fixture({affecte:1});f.c.loaded=false;f.run("tickEmployeRegie(nearby);tickEmployeRegie(nearby)");
    assert.equal(f.appels.filter(a=>a[0]==="REQUEST_MODEL").length,1);
    f.run("tickEmployeRegie(away)");assert.equal(f.appels.filter(a=>a[0]==="MARK_MODEL_AS_NO_LONGER_NEEDED").length,1);
    f.c.loaded=true;f.run("tickEmployeRegie(nearby);tickEmployeRegie(nearby)");
    assert.equal(f.appels.filter(a=>a[0]==="CREATE_CHAR").length,1);
    const h=f.run("employeRegie");f.run("tickEmployeRegie(away)");assert.ok(!f.personnages.has(h));
    f.run("tickEmployeRegie(nearby)");assert.equal(f.appels.filter(a=>a[0]==="CREATE_CHAR").length,2);
    assert.equal(f.c.state.affecte,1);assert.equal(f.c.state.reserve,0);
});
test("rappel sans PNJ disponible et sauvegarde de l'ordre",()=>{
    const f=fixture({equipe:1,affecte:1});f.c.order="attendre";
    assert.equal(f.run("peutRejoindreRegie(0,nearby)"),false);
    assert.equal(f.run("affecterRegie(nearby,false)"),true);
    assert.equal(f.c.order,"suivre");assert.equal(f.run("peutRejoindreRegie(0,nearby)"),true);
    const loaded=fixture({...f.c.state});assert.equal(loaded.run("effectifTerrain()"),1);assert.equal(loaded.run("revenuEquipe(state)"),0);
});
test("les deux règlements de mission réels paient la prime une fois et la collecte survit à la relance",()=>{
    const disk=new Map();
    const dir=path.join(__dirname,"../jeu");
    const cfg=JSON.parse(fs.readFileSync(path.join(__dirname,"../config.json"),"utf8"));cfg.racine="jeu/";
    function createWorld(){
        const c={
            CONFIG:cfg,log:()=>{},propertyIncome:()=>0,
            native(name,...a){
                if(name==="READ_STRING_FROM_INI_FILE")return a[2]==="profil"?"Validation":disk.get(a.join("|"))||"";
                if(name==="WRITE_STRING_TO_INI_FILE"){disk.set(a.slice(1).join("|"),a[0]);return true;}
                if(name==="GET_GAME_TIMER")return 100;
                if(name==="GET_PLAYER_CHAR")return 1;
                if(name==="DOES_CHAR_EXIST")return a[0]===88;
                if(name==="IS_CHAR_DEAD"||name==="IS_CHAR_IN_ANY_CAR")return false;
                if(name==="MARK_CHAR_AS_NO_LONGER_NEEDED")return;
                throw new Error("Commande absente du scénario de règlement : "+name);
            }
        };
        vm.createContext(c);
        for(const file of ["00_demarrage.js","05_reportage.js","11_affectations.js"]){
            vm.runInContext(fs.readFileSync(path.join(dir,file),"utf8"),c);
        }
        return s=>vm.runInContext(s,c);
    }
    let run=createWorld();
    run("change(s=>{s.local=1;s.equipe=1;s.affecte=1;})");
    run("mission={kind:'bande',step:1,stop:1000}; const ici={x:contact[0],y:contact[1],z:contact[2]}; tickJob(ici);tickJob(ici);");
    assert.equal(run("state.reserve"),150);assert.equal(run("state.missions"),1);
    run("mission={kind:'reportage',step:2,guest:88,car:55,stop:1000};tickJob(ici);tickJob(ici)");
    assert.equal(run("state.reserve"),300);assert.equal(run("state.missions"),2);assert.equal(run("state.generation"),3);
    run=createWorld();
    assert.equal(run("state.affecte"),1);assert.equal(run("state.reserve"),300);
    run("const ici={x:local[0],y:local[1],z:local[2]}");
    assert.equal(run("collect(ici)"),true);assert.equal(run("collect(ici)"),false);
    assert.equal(run("state.caisse"),cfg.prime+cfg.primeReportage+300);
    const relance=createWorld();assert.equal(relance("state.reserve"),0);assert.equal(relance("state.missions"),2);
});

console.log(passes+" groupes de tests reussis");
