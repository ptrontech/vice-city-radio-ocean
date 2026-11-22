// Les deux modules de 42 m réutilisent les maillages de Vice City et leurs collisions.
// Little Havana, modèle 1431. CLEO charge le même modèle que le ponton d'origine juste à l'ouest.
// Plan en unités du jeu. Objets : ID, centre x, y, z sans décalage, cap en degrés.
// L'eau est à 6,00 m, les planches neuves à 7,29 et 7,33 m. Un léger recouvrement relie les trois surfaces.
const quaiPlan = {
  "entree": [
    -805.2,
    -333,
    8.25
  ],
  "rendezvous": [
    -780.5,
    -284,
    8.33
  ],
  "parcours": [
    [
      -805.2,
      -333,
      8.25
    ],
    [
      -801,
      -327.8,
      8.29
    ],
    [
      -796.5,
      -320,
      8.29
    ],
    [
      -793.5,
      -314.81,
      8.29
    ],
    [
      -787.5,
      -304.42,
      8.29
    ],
    [
      -782.9,
      -296.45,
      8.33
    ],
    [
      -780.8,
      -291.5,
      8.33
    ],
    [
      -780.5,
      -284,
      8.33
    ]
  ],
  "objets": [
    [
      1431,
      -793.5,
      -314.8135,
      0.69885,
      330
    ],
    [
      1431,
      -781,
      -295.1269,
      0.73885,
      0
    ],
    [
      414,
      -783,
      -283.5,
      7.735,
      0
    ],
    [
      348,
      -783.2,
      -288.3,
      7.32,
      0
    ]
  ]
};
const quaiEntree = quaiPlan.entree;
const quaiRendezvous = quaiPlan.rendezvous;
const quaiParcours = quaiPlan.parcours;
const quaiModels = [...new Set(quaiPlan.objets.map(part => part[0]))];
let quaiHandles = null;
let quaiRequested = false;
let quaiOpen = false;
let quaiNextTick = 0;

function quaiMatches(handle, part) {
    if (!Number.isInteger(handle) || handle < 0 || !N("DOES_OBJECT_EXIST", handle)) return false;
    const at = N("GET_OBJECT_COORDINATES", handle);
    return Math.abs(at.x - part[1]) < 0.12 && Math.abs(at.y - part[2]) < 0.12 &&
        Math.abs(at.z - part[3]) < 0.12;
}

function quaiRememberHandles() {
    // Journal technique par profil. Aucun montant ou drapeau de progression n'est enregistré ici.
    writeKey("quai-session.ini","objets",quaiHandles.map(handle => handle === null ? "-" : String(handle)).join(","));
}

function quaiRestoreHandles() {
    const remembered = String(readKey("quai-session.ini","objets") || "").split(",");
    quaiHandles = quaiPlan.objets.map((part, index) => {
        const raw = remembered[index] || "";
        if (!/^\d{1,10}$/.test(raw)) return null;
        const handle = Number(raw);
        return quaiMatches(handle,part) ? handle : null;
    });
}

function quaiReleaseModels() {
    if (!quaiRequested) return;
    quaiModels.forEach(model => N("MARK_MODEL_AS_NO_LONGER_NEEDED",model));
    quaiRequested = false;
}

function clearQuai() {
    if (quaiHandles === null) quaiRestoreHandles();
    const hadObjects = quaiHandles.some(h => h !== null);
    // Supprimer d'abord le mobilier, puis les deux planchers.
    for (let i = quaiHandles.length - 1; i >= 0; i--) {
        if (quaiMatches(quaiHandles[i],quaiPlan.objets[i])) N("DELETE_OBJECT",quaiHandles[i]);
        quaiHandles[i] = null;
    }
    quaiOpen = false;
    if (hadObjects) quaiRememberHandles();
    quaiReleaseModels();
}

function quaiOverDeck(pos) {
    // Conserver temporairement les appuis si une mission vanilla démarre alors que Tommy est sur l'eau.
    if (!pos || pos.z < 5 || pos.z > 12) return false;
    return quaiPlan.objets.slice(0,2).some(part => {
        const theta = part[4] * Math.PI / 180;
        const dx = pos.x - part[1], dy = pos.y - part[2];
        const x = dx * Math.cos(theta) + dy * Math.sin(theta);
        const y = -dx * Math.sin(theta) + dy * Math.cos(theta);
        return Math.abs(x) < 5 && Math.abs(y) < 22;
    });
}

function quaiReady() { return quaiOpen; }

function tickQuai(pos, free, now) {
    if (now < quaiNextTick && quaiNextTick - now < 3000) return;
    quaiNextTick = now + 420;
    if (quaiHandles === null) quaiRestoreHandles();
    const distance = pos ? Math.hypot(pos.x - quaiEntree[0],pos.y - quaiEntree[1]) : Infinity;
    if (!free || distance > 205) {
        quaiOpen = false;
        if (!quaiOverDeck(pos)) clearQuai();
        return;
    }
    if (distance > 155 && !quaiOpen) return;
    const complete = quaiPlan.objets.every((part,i) => quaiMatches(quaiHandles[i],part));
    if (complete) {
        quaiReleaseModels();
        quaiOpen = true;
        return;
    }
    quaiOpen = false;
    if (!quaiRequested) {
        quaiModels.forEach(model => N("REQUEST_MODEL",model));
        quaiRequested = true;
    }
    if (!quaiModels.every(model => N("HAS_MODEL_LOADED",model))) return;
    for (let i = 0; i < quaiPlan.objets.length; i++) {
        const part = quaiPlan.objets[i];
        if (quaiMatches(quaiHandles[i],part)) continue;
        const [model,x,y,z,heading] = part;
        const handle = N("CREATE_OBJECT_NO_OFFSET",model,x,y,z);
        if (!quaiMatches(handle,part)) {
            // Un objet à la mauvaise position vient de ce seul appel et peut être libéré immédiatement.
            if (Number.isInteger(handle) && handle >= 0 && N("DOES_OBJECT_EXIST",handle)) N("DELETE_OBJECT",handle);
            quaiNextTick = now + 1500;
            return;
        }
        N("SET_OBJECT_HEADING",handle,heading);
        N("SET_OBJECT_COLLISION",handle,true);
        N("SET_OBJECT_DYNAMIC",handle,false);
        N("FREEZE_OBJECT_POSITION",handle,true);
        quaiHandles[i] = handle;
        quaiRememberHandles();
    }
    quaiReleaseModels();
    quaiOpen = true;
}

function quaiMapMark() {
    const blip = mark(quaiEntree,2);
    N("CHANGE_BLIP_DISPLAY",blip,2);
    return blip;
}

function quaiPlace(pos) {
    if (!quaiOpen || !pos) return "";
    return Math.hypot(pos.x - quaiRendezvous[0],pos.y - quaiRendezvous[1]) < 3 &&
        Math.abs(pos.z - quaiRendezvous[2]) < 1.3 ? "quai" : "";
}

function drawQuaiMenu(pos) {
    ImGui.TextWrapped("Quai de Radio Ocean | Little Havana");
    ImGui.TextWrapped("Suis les planches depuis la rive jusqu'au banc et au lampadaire. Les messages du port sont deposes ici.");
    if (!quaiPlace(pos)) return;
    button("Relever le bulletin du ponton", () => {
        if (mission) say("Message du port. " + brief());
        else say("Le ponton est ouvert. Ines tient la permanence sur Ocean Drive.");
    });
}
