// Baux radio dans deux intérieurs d'origine. Les portes et les escaliers restent gérés par Vice City.
// Repérage sur les triangles des modèles ht_upstairs et ml_record des fichiers hotel.col et mall.col.
// Les positions de porte suivent les déclencheurs de la campagne, pas le centre visuel des bâtiments.
const propertyLots = [
    {
        id: "bien-hotel", bit: 1, price: 720, income: 45, name: "Salon de la suite 317",
        entrance: [228.2, -1277.3, 12.0], desk: [229.0, -1266.0, 20.07], groundZ: 19.07,
        directions: "Ocean View Hotel, Ocean Drive. Entre par la reception, monte l'escalier jusqu'a la chambre de Tommy, puis approche du salon pres du lit.",
        use: "Loue a la radio l'usage professionnel du salon pour ses interviews. La chambre de Tommy garde sa fonction d'origine."
    },
    {
        id: "bien-mall", bit: 2, price: 1050, income: 85, name: "Rayon radio du disquaire",
        entrance: [353.3, 1124.5, 19.4], desk: [361.0, 1108.0, 25.36], groundZ: 24.36,
        directions: "North Point Mall, Vice Point. Entre par la porte ouest, monte a l'etage puis approche des bacs chez le disquaire au sud de cette entree.",
        use: "Exploite un rayon de cassettes dans le magasin de disques. Les emissions de la radio alimentent les ventes."
    }
];

function propertyFor(id) {
    return propertyLots.find(lot => lot.id === id);
}

function ownsProperty(ledger, lot) {
    return (ledger.biens & lot.bit) !== 0;
}

function propertyIncome(ledger) {
    return propertyLots.reduce((amount, lot) => amount + (ownsProperty(ledger, lot) ? lot.income : 0), 0);
}

function propertyPlace(pos) {
    for (const lot of propertyLots) {
        if (Math.hypot(pos.x - lot.desk[0], pos.y - lot.desk[1]) > 3.35 ||
            Math.abs(pos.z - lot.desk[2]) > 1.25) continue;
        // Sonder sous le plafond. L'autre étage, le trottoir et le toit ne partagent pas ce sol.
        const floor = N("GET_GROUND_Z_FOR_3D_COORD", lot.desk[0], lot.desk[1], lot.groundZ + 1.65);
        if (Number.isFinite(floor) && Math.abs(floor - lot.groundZ) < 0.65) return lot.id;
    }
    return "";
}

function propertyMapMarks() {
    // Le radar mène à la porte de rue. Le marqueur 3D par défaut flotterait dans celle-ci.
    return propertyLots.map(lot => {
        const handle = mark(lot.entrance, 6);
        N("CHANGE_BLIP_DISPLAY", handle, 2);
        return handle;
    });
}

function canUseProperty(id, pos) {
    return !ONMISSION && propertyPlace(pos) === id &&
        !N("IS_CHAR_IN_ANY_CAR", N("GET_PLAYER_CHAR", 0));
}

function buyProperty(id, pos) {
    const lot = propertyFor(id);
    if (!lot || !canUseProperty(id, pos) || ownsProperty(state, lot) || state.caisse < lot.price) return false;
    if (!change(next => { next.caisse -= lot.price; next.biens = (next.biens || 0) | lot.bit; })) return false;
    say("Bail signe. " + lot.name + " rapporte " + lot.income + " $ par nouvelle emission.");
    return true;
}

function withdrawProperty(id, pos) {
    const lot = propertyFor(id);
    if (!lot || !canUseProperty(id, pos) || !ownsProperty(state, lot) || state.reserve <= 0) return false;
    const total = state.reserve;
    if (!change(next => { next.caisse += next.reserve; next.reserve = 0; })) return false;
    say("Recettes de la radio retirees : " + total + " $.");
    return true;
}

function isPropertyMenu(name) {
    return name === "biens" || propertyLots.some(lot => name === lot.id || name === lot.id + "-confirmer");
}

function drawPropertyMenu(pos) {
    if (menu === "biens") {
        ImGui.TextWrapped("Guide des baux. Les reperes cyan indiquent les entrees des batiments. Les signatures et les retraits se font sur place.");
        const here = propertyPlace(pos);
        for (const lot of propertyLots) {
            ImGui.Separator();
            ImGui.TextWrapped(lot.name + (ownsProperty(state, lot) ? " | bail actif" : " | bail " + lot.price + " $"));
            ImGui.TextWrapped(lot.directions);
            if (here === lot.id) button("Ouvrir le comptoir", () => openMenu(lot.id));
        }
        return;
    }
    const lot = propertyLots.find(item => menu === item.id || menu === item.id + "-confirmer");
    if (!lot) return;
    ImGui.TextWrapped(lot.name);
    ImGui.TextWrapped(lot.use);
    ImGui.TextWrapped("Revenu : " + lot.income + " $ par nouvelle emission terminee. Tous les comptoirs partagent la meme reserve.");
    if (!canUseProperty(lot.id, pos)) {
        ImGui.TextWrapped(lot.directions);
        return;
    }
    if (ownsProperty(state, lot)) {
        ImGui.TextWrapped("Bail actif. Reserve de la radio : " + state.reserve + " $.");
        if (state.reserve > 0) button("Retirer les recettes", () => withdrawProperty(lot.id, pos));
    } else if (menu === lot.id + "-confirmer") {
        button("Confirmer le bail  " + lot.price + " $", () => {
            if (buyProperty(lot.id, pos)) openMenu(lot.id);
        });
        button("Annuler", () => openMenu(lot.id));
    } else if (state.caisse >= lot.price) {
        button("Examiner le bail  " + lot.price + " $", () => openMenu(lot.id + "-confirmer"));
    } else {
        ImGui.TextWrapped("Loyer d'installation : " + lot.price + " $. Il te manque " + (lot.price - state.caisse) + " $.");
    }
}
