const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const code = fs.readFileSync(path.join(__dirname,"../jeu/13_natation.js"),"utf8");
function moteur() {
    const jeu={pos:{x:0,y:0,z:6.02},vie:87,vehicule:false,noyade:true,eau:true,fond:0,obstacle:false};
    const notes=[];
    const c={cfg:{eauxNatation:[[6,-100,-100,100,100]]},showTextBox:()=>{},alive:()=>true,posOf:()=>({...jeu.pos}),
        N:(nom,...args)=>{
            switch(nom){
            case "IS_CHAR_IN_WATER":return jeu.eau;
            case "IS_CHAR_IN_ANY_CAR":return jeu.vehicule;
            case "IS_CHAR_ON_FOOT":return !jeu.vehicule;
            case "RADIO_NAGE_ETAT":return Number(jeu.noyade);
            case "SET_CHAR_DROWNS_IN_WATER":jeu.noyade=args[1];notes.push(nom);return;
            case "IS_AREA_OCCUPIED":return jeu.obstacle;
            case "GET_GROUND_Z_FOR_3D_COORD":return jeu.fond;
            case "GET_CHAR_HEADING":return 0;
            case "GET_CHAR_HEALTH":return jeu.vie;
            case "SET_CHAR_HEALTH":jeu.vie=args[1];notes.push(nom);return;
            case "RADIO_NAGE_POSITION":case "SET_CHAR_COORDINATES":jeu.pos={x:args[1],y:args[2],z:args[3]};notes.push(nom);return;
            case "DOES_CHAR_EXIST":return true;
            case "SET_CHAR_HEADING":case "RADIO_NAGE_POSTURE":case "DRAW_RECT":return;
            default:throw Error(nom);
            }
        },ImGui:new Proxy({},{get:()=>()=>{}})};
    vm.createContext(c);vm.runInContext(code,c);
    const lire=()=>vm.runInContext("nage",c);
    let now=100;
    function avancer(secs,inputs={},libre=true){let nageur=false;for(let i=0;i<Math.round(secs*20);i++){
        now+=50;nageur=c.tickNage(1,libre,now,{avant:0,tourner:0,plonger:false,remonter:false,vite:false,monter:false,...inputs});
    }return nageur;}
    return {jeu,notes,lire,avancer};
}
test("respirer en surface, plonger, reprendre de l’air sans rendre de vie",()=>{
    const t=moteur();
    assert.ok(t.avancer(2,{avant:1}));assert.ok(t.jeu.pos.y>3);assert.equal(t.jeu.vie,87);
    t.avancer(4,{plonger:true});assert.ok(t.jeu.pos.z<3);assert.ok(t.lire().air<14);
    t.avancer(5,{remonter:true});assert.ok(t.jeu.pos.z>5.9);assert.equal(t.lire().air,16);assert.equal(t.jeu.vie,87);
});
test("les dégâts affectent uniquement la vie réelle puis aboutissent à la noyade",()=>{
    const t=moteur();t.avancer(14,{plonger:true});assert.equal(t.jeu.vie,87);
    t.avancer(3,{plonger:true});assert.ok(t.jeu.vie<87);t.avancer(7,{plonger:true});assert.equal(t.jeu.vie,0);
});
test("un bateau, une mission et la sortie sur la rive rendent les privilèges initiaux",()=>{
    const t=moteur();t.jeu.noyade=false;t.avancer(1);t.avancer(.1,{},false);
    assert.equal(t.lire(),null);assert.equal(t.jeu.noyade,false);
    t.jeu.noyade=true;t.avancer(1);t.jeu.vehicule=true;
    assert.equal(t.avancer(.1),false);assert.equal(t.jeu.noyade,true);
    t.jeu.vehicule=false;t.avancer(1);t.jeu.fond=6.6;
    t.avancer(.1,{avant:1,remonter:true});assert.equal(t.lire(),null);assert.equal(t.jeu.noyade,true);assert.ok(t.jeu.pos.z>=6.6);
});
test("un mur bloque le mouvement, une plage sèche ou un véhicule ne déclenche pas la nage",()=>{
    const t=moteur();t.jeu.eau=false;assert.equal(t.avancer(1),false);assert.deepEqual(t.notes,[]);
    t.jeu.eau=true;t.jeu.vehicule=true;assert.equal(t.avancer(.1),false);t.jeu.vehicule=false;t.jeu.obstacle=true;
    t.avancer(1,{avant:1});assert.equal(t.jeu.pos.y,0);
});

test("maintenir Entrer en immersion laisse le souffle puis la vie diminuer",()=>{
    const t=moteur();t.avancer(2,{plonger:true});
    assert.ok(t.lire().profondeur>1);
    t.avancer(16,{plonger:true,monter:true});
    assert.equal(t.lire().air,0);assert.ok(t.jeu.vie<87);
    t.avancer(7,{plonger:true,monter:true});assert.equal(t.jeu.vie,0);
});
