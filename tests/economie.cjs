const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.join(__dirname, "..");
const CONFIG = {...JSON.parse(fs.readFileSync(path.join(root,"config.json"),"utf8")),racine:"essai/"};
const store = new Map();
let writable = true;
const native = (command, ...args) => {
    if (command === "READ_STRING_FROM_INI_FILE") return store.get(args.join("|")) || "";
    if (command === "WRITE_STRING_TO_INI_FILE") {
        const [value,...key]=args;
        if (writable) store.set(key.join("|"),value);
        return writable;
    }
    if (command === "GET_GAME_TIMER") return 1000;
    return true;
};
const engine = vm.createContext({CONFIG,native,log(){}});
vm.runInContext(fs.readFileSync(path.join(root,"jeu/00_demarrage.js"),"utf8"),engine);
const run = source => vm.runInContext(source,engine);
const place= (coords) => ({x:coords[0],y:coords[1],z:coords[2]});
engine.lieu=place(CONFIG.local);
engine.ines=place(CONFIG.contact);
assert.equal(run("capacity()"),0);
assert.equal(run("buy(lieu)"),false);
for(const [index,num] of CONFIG.reputation.entries()){
    run("change(s=>{s.caisse=2000;s.missions="+num+";})");
    assert.equal(run("capacity()"),index+1);
}
assert.equal(run("buy(lieu)"),true);
assert.equal(run("buy(lieu)"),false);
assert.equal(run("recruit({x:0,y:0,z:0})"),false);
assert.equal(run("recruit(ines)"),true);
run("change(s=>{s.reserve=100;})");
assert.equal(run("collect(lieu)"),true);
assert.equal(run("collect(lieu)"),false);
const saved=run("JSON.stringify(state)");
writable=false;
assert.equal(run("change(s=>{s.caisse+=999;})"),false);
assert.equal(run("JSON.stringify(state)"),saved);
assert.equal(run("JSON.stringify(readState())"),saved);
console.log("OK seuils 3/8/15/25, lieu d'achat, double achat, contrat, retrait unique et interruption d'écriture");
