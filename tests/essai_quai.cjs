const {test} = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const modules = ["07_quai.js","86_essai_quai.js"].map(f =>
    fs.readFileSync(path.join(__dirname,"../jeu",f),"utf8")).join("\n");

function simulation(options = {}) {
    let t = 0, pose = {x:0,y:0,z:20}, depart = 0, sol = 20, lectures = 0;
    const lignes = [];
    const game = vm.createContext({
        mode:"Validation", menu:"", mission:null, noticeUntil:Date.now()+60000,
        message:"Le ponton est ouvert. Ancienne annonce.", state:{caisse:120,reserve:35,generation:8},
        clockNow:() => t, alive:p => p === 1, near:(p,q,d) => Math.hypot(p.x-q[0],p.y-q[1]) <= d,
        posOf() {
            const age = (t-depart)/1000;
            return {...pose,z:Math.max(sol,pose.z - 4.905*age*age) +
                (options.instable && pose.x === -793.5 && age > 1.6 ? 0.22 : 0)};
        },
        N(op,p,x,y,z) {
            if (op === "LOAD_SCENE" || op === "REQUEST_COLLISION") return;
            if (op === "IS_CHAR_IN_ANY_CAR") return false;
            if (op === "IS_CHAR_ON_FOOT") return true;
            if (op === "IS_CHAR_IN_WATER") return game.posOf().z < 6;
            assert.equal(op,"SET_CHAR_COORDINATES");
            pose = {x,y,z}; depart = t;
            const point = chemin.find(q => q[0] === x && q[1] === y);
            sol = point ? point[2] : 11.1;
            if (options.trou && x === -793.5) sol = 5.8;
        },
        ImGui:{TextWrapped() {}},
        openMenu(s) { game.menu = s; },
        button(label,click) { click(); },
        drawMenu(p) {
            if (game.menu !== "quai") return;
            game.button("Signer une commande",() => { game.state.caisse--; });
            game.drawQuaiMenu(p);
        },
        say(s) {
            lectures++;
            if (!options.radioMuette) { game.message = s; game.noticeUntil = Date.now()+6500; }
        },
        report:s => lignes.push(s),
        verdict(s,ok) { lignes.push((ok ? "OK " : "ECHEC ")+s); return ok; }
    });
    vm.runInContext(modules,game);
    const chemin = vm.runInContext("quaiParcours",game);
    const origineBouton = game.button;
    assert.equal(game.testAppuisQuai(1,false),false);
    let fini = false;
    for (; t < 30000 && !fini; t+=50) {
        if (t === 1000 && !options.sansModeles) vm.runInContext("quaiOpen = true",game);
        fini = game.testAppuisQuai(1,true);
    }
    assert.equal(fini,true);
    assert.equal(game.testAppuisQuai(1,true),true);
    assert.equal(game.button,origineBouton);
    assert.deepEqual(game.state,{caisse:120,reserve:35,generation:8});
    return {lignes,ok:game.appuisQuaiReussis(),lectures,pose};
}

test("six prises doubles, un bulletin au banc et aucune action voisine",() => {
    const r = simulation();
    assert.equal(r.ok,true); assert.equal(r.lectures,1);
    assert.equal(r.lignes.filter(s => s.includes("intervalle_ms=600")).length,6);
    assert.equal(r.lignes.filter(s => s.includes("declencheurs=aucun/aucun")).length,5);
    assert.equal(r.lignes.filter(s => s.includes("declencheurs=quai/quai")).length,1);
});

test("un trou ou deux altitudes instables font échouer la traversée",() => {
    for (const option of [{trou:true},{instable:true}]) {
        const r = simulation(option);
        assert.equal(r.ok,false); assert.equal(r.lectures,0);
        assert.ok(r.lignes.includes("ECHEC appui stable travee en biais"));
        assert.equal(r.pose.x,-812);
    }
});

test("un ancien bulletin et un quai sans streaming ne valident pas l'essai",() => {
    const muet = simulation({radioMuette:true});
    assert.equal(muet.ok,false); assert.equal(muet.lectures,1);
    const vide = simulation({sansModeles:true});
    assert.equal(vide.ok,false); assert.equal(vide.lectures,0);
    assert.ok(vide.lignes.includes("ECHEC quai delai de chargement depasse"));
});
