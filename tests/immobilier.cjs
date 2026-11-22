// Tests de règles immobilières. Les collisions et les transitions de porte sont validées séparément en jeu.
const test = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const code = readFileSync(path.join(__dirname, "..", "jeu", "08_immobilier.js"), "utf8");

function session(options = {}) {
    const player = { state: { caisse: 2060, reserve: 0, ...options.sauvegarde },
        ONMISSION: false, car: false, floor: 19.07, writable: true, writes: 0,
        menu: "", labels: [], actions: [], say() {}, mark() { return 1; } };
    player.N = name => {
        if (name === "GET_GROUND_Z_FOR_3D_COORD") return player.floor;
        if (name === "GET_PLAYER_CHAR") return 1;
        if (name === "IS_CHAR_IN_ANY_CAR") return player.car;
        throw new Error(name);
    };
    player.change = edit => {
        if (!player.writable) return false;
        const next = { ...player.state };
        edit(next);
        player.state = next;
        player.writes++;
        return true;
    };
    player.ImGui = { TextWrapped(text) { player.labels.push(text); }, Separator() {} };
    player.button = (label, action) => player.actions.push({ label, action });
    player.openMenu = name => { player.menu = name; };
    vm.createContext(player);
    vm.runInContext(code, player);
    return player;
}

const hotel = { x: 229, y: -1266, z: 20.07 };
const mall = { x: 361, y: 1108, z: 25.36 };

test("Une ancienne sauvegarde gagne le premier bail et un second achat exige son propre étage", () => {
    const p = session();
    assert.equal(p.propertyIncome(p.state), 0);
    p.menu = "bien-hotel";
    p.drawPropertyMenu(hotel);
    p.actions.find(a => a.label.includes("Examiner")).action();
    assert.equal(p.menu, "bien-hotel-confirmer");
    assert.equal(p.writes, 0);
    p.actions.length = 0;
    p.drawPropertyMenu(hotel);
    p.actions.find(a => a.label.includes("Confirmer")).action();
    assert.equal(p.state.biens, 1);
    assert.equal(p.state.caisse, 1340);
    assert.equal(p.menu, "bien-hotel");
    assert.equal(p.buyProperty("bien-hotel", hotel), false);
    assert.equal(p.buyProperty("bien-mall", hotel), false);
    p.floor = 24.36;
    assert.equal(p.buyProperty("bien-mall", mall), true);
    assert.equal(p.state.biens, 3);
    assert.equal(p.state.caisse, 290);
    assert.equal(p.propertyIncome(p.state), 130);
    assert.equal(p.writes, 2);
});

test("La réserve reste unique entre sites même après réouverture de la sauvegarde", () => {
    const p = session({ sauvegarde: { biens: 3, caisse: 290 } });
    p.change(s => { s.reserve += p.propertyIncome(s); });
    const loaded = session({ sauvegarde: JSON.parse(JSON.stringify(p.state)) });
    assert.equal(loaded.state.reserve, 130);
    assert.equal(loaded.withdrawProperty("bien-hotel", hotel), true);
    const reloaded = session({ sauvegarde: JSON.parse(JSON.stringify(loaded.state)) });
    reloaded.floor = 24.36;
    assert.equal(reloaded.withdrawProperty("bien-mall", mall), false);
    assert.equal(reloaded.state.caisse, 420);
    assert.equal(reloaded.state.reserve, 0);
});

test("Le mauvais étage, la rue, un sol absent et un véhicule ne peuvent pas activer le bail", () => {
    const p = session();
    p.floor = 11.03;
    assert.equal(p.propertyPlace(hotel), "");
    p.floor = Number.NaN;
    assert.equal(p.propertyPlace(hotel), "");
    p.floor = 19.07;
    assert.equal(p.propertyPlace({ ...hotel, z: 12.0 }), "");
    assert.equal(p.propertyPlace({ x: 228.2, y: -1277.3, z: 12 }), "");
    p.car = true;
    assert.equal(p.buyProperty("bien-hotel", hotel), false);
    p.car = false;
    p.ONMISSION = true;
    assert.equal(p.buyProperty("bien-hotel", hotel), false);
    assert.equal(p.writes, 0);
});

test("Fonds insuffisants et échec d’enregistrement laissent le portefeuille intact", () => {
    const p = session({ sauvegarde: { caisse: 719 } });
    assert.equal(p.buyProperty("bien-hotel", hotel), false);
    p.state.caisse = 720;
    p.writable = false;
    assert.equal(p.buyProperty("bien-hotel", hotel), false);
    assert.equal(p.state.biens, undefined);
    assert.equal(p.state.caisse, 720);
    assert.equal(p.writes, 0);
});
