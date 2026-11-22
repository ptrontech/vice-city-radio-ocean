const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const script = fs.readFileSync(path.join(__dirname, "../jeu/07_quai.js"), "utf8");

function mockWorld() {
    const objects = new Map(), ini = new Map(), loaded = new Set(), requested = new Set();
    let next = 0;
    const ctx = {
        objects, loaded, requested, ini, writes: 0,
        readKey(file, key) { return ini.get(file + key); },
        writeKey(file, key, data) { ini.set(file + key,data); ctx.writes++; },
        N(name,...a) {
            switch(name) {
            case "REQUEST_MODEL": requested.add(a[0]);return;
            case "HAS_MODEL_LOADED": return loaded.has(a[0]);
            case "MARK_MODEL_AS_NO_LONGER_NEEDED": requested.delete(a[0]);return;
            case "CREATE_OBJECT_NO_OFFSET": {
                if(ctx.failAt === a[0])return -1;
                const id=next++;
                objects.set(id,{x:a[1], y:a[2], z:a[3], model:a[0]});
                if(ctx.wrongAt===a[0])objects.get(id).z+=2;
                return id;
            }
            case "DOES_OBJECT_EXIST":return objects.has(a[0]);
            case "GET_OBJECT_COORDINATES":return objects.get(a[0]);
            case "DELETE_OBJECT":objects.delete(a[0]);return;
            case "SET_OBJECT_HEADING":case "SET_OBJECT_COLLISION":case "SET_OBJECT_DYNAMIC":
            case "FREEZE_OBJECT_POSITION":return;
            default:throw Error(name);
            }
        }
    };
    return ctx;
}
const near = {x:-805.2,y:-333,z:8.25}, far = {x:50,y:-800,z:12}, end={x:-780.5,y:-284,z:8.33};
function start(world) {
    const context = vm.createContext({...world});
    vm.runInContext(script,context);
    return context;
}

test("Chargement différé, réutilisation après rechargement du script et fermeture sûre",() => {
    const world=mockWorld(), game=start(world);
    game.tickQuai(near,true,0);
    assert.equal(world.objects.size,0);assert.equal(world.requested.size,3);
    [1431,414,348].forEach(id => world.loaded.add(id));
    game.tickQuai(near,true,500);
    assert.equal(world.objects.size,4);assert.equal(game.quaiPlace(end),"quai");
    for(let t=1000;t<=3500;t+=500)game.tickQuai(near,true,t);
    assert.equal(world.objects.size,4);
    const reload = start(world);
    reload.tickQuai(end,true,0);
    assert.equal(world.objects.size,4);
    reload.tickQuai(end,false,500);
    assert.equal(reload.quaiPlace(end),"");assert.equal(world.objects.size,4);
    reload.tickQuai(far,false,1000);
    assert.equal(world.objects.size,0);
    reload.tickQuai(far,true,1500);assert.equal(world.objects.size,0);
});

test("Échec partiel, objet déplacé et handle réutilisé par un autre script", () => {
    const world=mockWorld(), game=start(world);
    [1431,414,348].forEach(id => world.loaded.add(id));
    world.failAt=414;game.tickQuai(near,true,0);
    assert.equal(world.objects.size,2);assert.equal(game.quaiReady(),false);
    world.failAt=null;world.wrongAt=414;game.tickQuai(near,true,1700);
    assert.equal(world.objects.size,2);
    world.wrongAt=null;game.tickQuai(near,true,3400);
    assert.equal(game.quaiReady(),true);assert.equal(world.objects.size,4);
    const handle=[...world.objects.keys()][0];
    world.objects.set(handle,{x:500,y:500,z:35,model:310});
    game.tickQuai(near,true,4000);
    assert.equal(world.objects.size,5);
    game.tickQuai(far,true,4600);
    assert.equal(world.objects.size,1);assert.equal(world.objects.get(handle).model,310);
});
