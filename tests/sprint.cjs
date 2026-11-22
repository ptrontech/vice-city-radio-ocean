// Exécuter avec node tests/sprint.cjs. Les scénarios isolent la logique qui ne nécessite pas le moteur.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../jeu/12_sprint.js"), "utf8");
let passes=0;
function fixture(mode="Campagne", entries=new Map(), config={seuilsSprint:[10,20,30]}) {
    const model={time:0,x:0,y:0,z:11,pad:false,key:false,car:false,water:false,free:true,blockWrites:false,awards:[],messages:[]};
    const context={
        cfg:config,mode,menu:"",hash(body){let h=5381;for(const c of body)h=(h*33+c.charCodeAt(0))>>>0;return h.toString(36);},
        readKey:(file,k)=>entries.get(file+"."+k)||"",
        writeKey:(file,k,value)=>{if(!model.blockWrites)entries.set(file+"."+k,String(value));},
        say:message=>model.messages.push(message),
        posOf:()=>({x:model.x,y:model.y,z:model.z}),
        N(name,...args){
            if(name==="IS_CHAR_IN_ANY_CAR")return model.car;
            if(name==="IS_CHAR_IN_WATER")return model.water;
            if(name==="IS_BUTTON_PRESSED")return model.pad;
            if(name==="IS_KEY_PRESSED")return model.key;
            if(name==="SET_PLAYER_NEVER_GETS_TIRED"){model.awards.push(args);return;}
            throw new Error(name);
        }
    };
    vm.createContext(context); vm.runInContext(source,context);
    const run=s=>vm.runInContext(s,context);
    function move(count, metresPerSecond=7){
        for(let i=0;i<count;i++){
            model.time+=180;model.x+=metresPerSecond*.18;
            context.now=model.time;context.free=model.free;
            run("tickSprint(1,free,now)");
        }
    }
    return {model,entries,context,move,run,value:()=>JSON.parse(run("JSON.stringify(loadSport())"))};
}
function test(name,fn){fn();passes++;console.log("OK",name);}
test("les conditions du sprint excluent les voitures, l'eau, les missions, les menus et les teleports",()=>{
    const f=fixture();f.move(35);f.model.pad=true;
    f.model.car=true;f.move(35);f.model.car=false;
    f.model.water=true;f.move(35);f.model.water=false;
    f.model.free=false;f.move(35);f.model.free=true;
    f.context.menu="journal";f.move(35);f.context.menu="";
    f.move(35,2);f.move(5,100);
    assert.equal(f.value().metres,0);assert.deepEqual(f.model.awards,[]);
});
test("paliers, confirmation du brevet et conservation des droits Rockstar",()=>{
    const f=fixture();
    assert.equal(f.run("sprintGrant()"),false);
    f.model.key=true;f.move(12);
    assert.equal(f.value().metres,10);assert.equal(f.run("sprintRank(loadSport().metres)"),1);assert.equal(f.run("sprintGrant()"),false);
    f.move(24);assert.equal(f.value().metres,30);assert.deepEqual(f.model.awards,[]);
    assert.equal(f.run("sprintGrant()"),true);
    f.model.car=true;f.move(10);assert.deepEqual(f.model.awards,[]);
    f.model.car=false;f.move(10);assert.deepEqual(f.model.awards,[[0,true]]);
    f.model.free=false;f.move(10);f.model.free=true;f.move(2);assert.deepEqual(f.model.awards,[[0,true],[0,true]]);
    assert.equal(f.run("sprintGrant()"),false);
    const second=fixture("Campagne",f.entries);assert.equal(second.value().metres,30);assert.equal(second.value().brevet,true);
    assert.equal(fixture("Libre").value().metres,0);
});
test("essai immediat en libre et reprise si une copie de progression est abimee",()=>{
    const f=fixture("Libre");assert.equal(f.run("sprintGrant()"),true);f.model.pad=true;f.move(20);
    const valid=f.value();assert.ok(valid.metres>=10);const key=valid.revision%2?"a":"b";f.entries.set("sport.ini."+key,"incorrect");
    const restored=fixture("Libre",f.entries).value();assert.equal(restored.revision,valid.revision-1);assert.equal(restored.brevet,true);
});
test("interruption des ecritures, desactivation et configuration personnalisee",()=>{
    const f=fixture("Libre");f.model.blockWrites=true;assert.equal(f.run("sprintGrant()"),false);
    assert.equal(f.value().brevet,false);f.model.blockWrites=false;
    assert.equal(f.run("saveSport({...loadSport(),suivi:false})"),true);f.model.key=true;f.move(90);
    assert.equal(f.value().metres,0);assert.deepEqual(f.model.awards,[]);
    const g=fixture("Campagne",new Map(),{seuilsSprint:[3,2,-5],toucheSprint:0});assert.equal(g.run("sprintLastGoal"),1500);
    g.model.key=true;g.move(40);assert.equal(g.value().metres,0);
});
console.log(passes+" groupes de tests reussis");
