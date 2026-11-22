const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const assert = require("node:assert/strict");
const { test } = require("node:test");

test("les caméras et le test du seuil quittent l’intérieur de la sauvegarde avant le streaming", () => {
    for (const scenario of ["volumes", "seuil"]) {
        let interieur = 1;
        let chargement = false;
        const contexte = vm.createContext({
            N(nom, ...args) {
                if (nom === "SET_AREA_VISIBLE") interieur = args[0];
                if (nom === "SET_CHAR_COORDINATES" || nom === "LOAD_SCENE") assert.equal(interieur, 0);
                if (nom === "LOAD_SCENE") chargement = true;
            },
            testMove() { assert.equal(interieur, 0); },
            writeKey() {},
            menu: "",
            bootId: "essai"
        });
        for (const nom of ["82_essai_volume.js", "81_essai_seuil.js"]) {
            const source = fs.readFileSync(path.join(__dirname, "..", "jeu", nom), "utf8");
            vm.runInContext(source, contexte);
        }
        vm.runInContext(scenario === "volumes" ? "testVolumes(0,true)" : "testSeuil(0,true)", contexte);
        assert.equal(chargement, true);
    }
});
