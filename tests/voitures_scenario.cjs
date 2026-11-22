// Vérifie le séquençage et les marqueurs sans démarrer Vice City.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname,"../jeu/77_essai_voitures.js"),"utf8");

function preparer(delaiInfini=false) {
    const instants=[], preuves=[], modeles=[], supprimes=[], couleurs=[];
    let heure=0, pilote=null, actif=null, indiceAuto=80, dernierModele=0, restaurations=0;
    const sol=13.828;
    function N(nom,...args) {
        switch(nom) {
        case "GET_TIME_OF_DAY": return {hours:12,minutes:27};
        case "GET_GROUND_Z_FOR_3D_COORD": return sol;
        case "HAS_MODEL_LOADED": return !delaiInfini && dernierModele===args[0];
        case "REQUEST_MODEL": dernierModele=args[0];return;
        case "CREATE_CAR":
            actif={id:++indiceAuto,modele:args[0],x:args[1],y:args[2],z:sol+.55};
            modeles.push(args[0]);return actif.id;
        case "GET_CAR_MODEL": assert.equal(args[0],actif.id);return actif.modele;
        case "IS_CHAR_IN_ANY_CAR": return pilote!==null;
        case "IS_CHAR_IN_CAR": return pilote===args[1];
        case "WARP_CHAR_INTO_CAR": pilote=args[1];return;
        case "WARP_CHAR_FROM_CAR_TO_COORD": pilote=null;return;
        case "GET_CAR_COORDINATES": return {x:actif.x,y:actif.y,z:actif.z};
        case "GET_OFFSET_FROM_CAR_IN_WORLD_COORDS":
            return {x:actif.x+args[1],y:actif.y+args[2],z:actif.z+args[3]};
        case "CHANGE_CAR_COLOUR": couleurs.push(args.slice(1));return;
        case "DELETE_CAR": assert.equal(actif.id,args[0]);supprimes.push(args[0]);actif=null;return;
        case "RESTORE_CAMERA_JUMPCUT": restaurations++;return;
        case "SET_FIXED_CAMERA_POSITION": case "POINT_CAMERA_AT_POINT":
            assert.ok(args.every(Number.isFinite));return;
        case "SET_AREA_VISIBLE":case "DISPLAY_RADAR":case "FORCE_WEATHER_NOW":case "SET_TIME_OF_DAY":
        case "REQUEST_COLLISION":case "LOAD_SCENE":case "MARK_MODEL_AS_NO_LONGER_NEEDED":
        case "SET_CAR_HEADING":case "SET_CAR_FORWARD_SPEED":case "RELEASE_WEATHER":return;
        default:throw Error(nom);
        }
    }
    const ctx={N,alive:()=>true,testMove:()=>{},menu:"",bootId:"BOOT",
        report:()=>{},verdict:(titre,ok)=>{preuves.push([titre,ok]);return ok;},
        writeKey:(file,cle,valeur)=>{assert.equal(file,"essai.ini");instants.push([heure,cle,valeur]);}};
    vm.createContext(ctx);vm.runInContext(source,ctx);
    return {instants,preuves,modeles,supprimes,couleurs,restaurations:()=>restaurations,
        pas:(t,libre=true)=>{heure=t;return ctx.testVoitures1986(10,libre,t);}};
}

const essai=preparer();
assert.equal(essai.pas(0,false),false);
for(let t=0;t<80000;t+=100)essai.pas(t);
assert.deepEqual(essai.modeles,[175,205,156,145]);
assert.equal(new Set(essai.supprimes).size,4);
assert.equal(new Set(essai.couleurs.map(String)).size,4);
const films=essai.instants.filter(x=>x[1]==="filmVoitures").map(x=>x[2]);
assert.deepEqual(films,["BOOT-admiral","BOOT-sabre","BOOT-police","BOOT-cheetah","BOOT-fin"]);
const plans=essai.instants.filter(x=>x[1]==="planVoitures");
for(const [i,nom] of ["admiral","sabre","police","cheetah"].entries()) {
    assert.equal(plans[i*2][2],"BOOT-"+nom+"-avant");
    assert.equal(plans[i*2+1][2],"BOOT-"+nom+"-arriere");
}
for(let i=0;i<8;i++)assert.ok(plans[i+1][0]-plans[i][0]>=7000);
assert.equal(essai.preuves.length,4);
assert.ok(essai.preuves.every(x=>x[1]));
assert.equal(essai.restaurations(),1);

const enPanne=preparer(true);
enPanne.pas(0);
assert.equal(enPanne.pas(18100),true);
assert.deepEqual(enPanne.instants.map(x=>x.slice(1)),[["erreurVoitures","BOOT-admiral-chargement"]]);
assert.equal(enPanne.restaurations(),1);

const interrompu=preparer();
interrompu.pas(0);interrompu.pas(1000);
assert.equal(interrompu.pas(1100,false),true);
assert.equal(interrompu.supprimes.length,1);
assert.equal(interrompu.restaurations(),1);
console.log("Quatre voitures, huit plans de sept secondes, échec de chargement et interruption vérifiés.");
