const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "../jeu/14_vie_majestic.js"), "utf8");

test("streaming du hall, marche et remplacement après la disparition d'un civil", () => {
    const actifs = new Map(), chargements = new Set(), demandes = [], commandes = [];
    let prochain = 10, proche = true;
    const contexte = vm.createContext({
        cfg:{}, near:() => proche, alive:h => actifs.has(h), posOf:h => actifs.get(h),
        removePed:h => actifs.delete(h),
        N(op, ...v) {
            switch (op) {
            case "REQUEST_MODEL": demandes.push(v[0]); break;
            case "HAS_MODEL_LOADED": return chargements.has(v[0]);
            case "DOES_CHAR_EXIST": return actifs.has(v[0]);
            case "CREATE_CHAR":
                actifs.set(++prochain, {x:v[2],y:v[3],z:v[4]});
                return prochain;
            case "SET_CHAR_OBJ_GOTO_COORD_ON_FOOT": commandes.push(v); break;
            }
        }
    });
    vm.runInContext(source, contexte);
    const tick = t => vm.runInContext("vieMajestic({}, " + t + ")", contexte);
    tick(0); tick(800);
    assert.deepEqual(demandes, [21,82,35]);
    assert.equal(actifs.size, 0);
    for (const modele of demandes) chargements.add(modele);
    tick(1000); tick(9000);
    assert.equal(actifs.size, 3);
    assert.equal(commandes.length, 3);
    const anciens = [...actifs.keys()];
    actifs.delete(anciens[0]);
    tick(9500); tick(14000); tick(22000);
    assert.equal(actifs.size, 2);
    assert.ok(commandes.length > 3);
    tick(70000);
    assert.equal(actifs.size, 3);
    proche = false;
    tick(71000);
    assert.equal(actifs.size, 0);
    proche = true;
    tick(72000);
    assert.equal(actifs.size, 3);
    contexte.cfg.facadesOcean = false;
    tick(73000);
    assert.equal(actifs.size, 0);
});
