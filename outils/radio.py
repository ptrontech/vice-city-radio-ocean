"""Serveur de dialogue écrit. Uniquement Ollama sur la boucle locale."""
import configparser
import json
import os
import re
import sqlite3
import time
import unicodedata
import urllib.request
from pathlib import Path

MODEL_URL = "http://127.0.0.1:11434/api/chat"
INTENTIONS = {"aucune","livraison","bilan","local","visites","equipe"}

SOUVENIRS = {
    "rafa": "Rafa a deja rejoint l'equipe de la radio.",
    "regie": "La radio a acquis la regie du News Cafe.",
    "suite": "La radio a signe le bail du salon de la suite 317 a l'Ocean View.",
    "disquaire": "La radio a signe le bail du rayon de cassettes au North Point Mall.",
    "trois": "La radio a atteint le palier des trois emissions.",
    "huit": "La radio a atteint le palier des huit emissions.",
    "quinze": "La radio a atteint le palier des quinze emissions.",
    "vingtcinq": "La radio a atteint le palier des vingt-cinq emissions.",
}

def observe(db, missions, regie, gardes, droits):
    """Conserver des faits établis par un état du jeu."""
    db.execute("CREATE TABLE IF NOT EXISTS souvenirs (code TEXT PRIMARY KEY)")
    attained = {"rafa": gardes > 0, "regie": bool(regie), "suite": bool(droits & 1),
                "disquaire": bool(droits & 2), "trois": missions >= 3, "huit": missions >= 8,
                "quinze": missions >= 15, "vingtcinq": missions >= 25}
    db.executemany("INSERT OR IGNORE INTO souvenirs (code) VALUES (?)",
                   ((code,) for code, reached in attained.items() if reached))
    known = {row[0] for row in db.execute("SELECT code FROM souvenirs")}
    return [label for code, label in SOUVENIRS.items() if code in known]

def observe_save(db, folder):
    """Lire les deux enregistrements fiables du jeu, y compris entre conversations."""
    slots = read_ini(folder / "progression.ini")
    for key in ("a", "b"):
        payload, separator, signature = slots.get(key, "").partition("~")
        if not separator or not re.fullmatch(r"[0-9,]{1,220}", payload) or not re.fullmatch(r"[0-9a-z]{1,7}", signature):
            continue
        checksum = 5381
        for char in payload:
            checksum = (checksum * 33 + ord(char)) & 0xffffffff
        if checksum != int(signature, 36):
            continue
        fields = payload.split(",")
        if not all(field.isdecimal() for field in fields):
            continue
        values = list(map(int, fields))
        if (values[0], len(values)) not in ((1, 8), (2, 10)):
            continue
        missions, regie, gardes = values[2], values[4], values[5]
        droits, affecte = values[8:10] if values[0] == 2 else (0, 0)
        if regie > 1 or gardes > 4 or droits > 3 or affecte > 1 or (affecte and not (regie and gardes)):
            continue
        observe(db, missions, regie, gardes, droits)

def asciify(text):
    return unicodedata.normalize("NFKD", str(text)).encode("ascii","ignore").decode()

def safe_line(text,limit):
    return re.sub(r"\s+", " ", re.sub(r"[~%|\x00-\x1f]", " ", asciify(text))).strip()[:limit]

def read_ini(path):
    try:
        raw=path.read_bytes()
        if raw.startswith((b"\xff\xfe",b"\xfe\xff")): text=raw.decode("utf-16")
        else:
            try:text=raw.decode("utf-8-sig")
            except UnicodeDecodeError:text=raw.decode("mbcs")
        parser=configparser.ConfigParser(interpolation=None,strict=False)
        parser.read_string(text)
        return dict(parser["atelier"])
    except (OSError,KeyError,configparser.Error,UnicodeError):
        return {}

def write_ini(path,values):
    # Chaque fichier a un seul auteur. Le lecteur voit soit l'ancienne réponse, soit la nouvelle.
    tmp=path.with_suffix(".tmp")
    payload="[atelier]\r\n"+"".join(f"{k}={v}\r\n" for k,v in values.items())
    tmp.write_bytes(payload.encode("ascii"))
    for attempt in range(8):
        try:os.replace(tmp,path);return
        except PermissionError:
            if attempt==7:raise
            time.sleep(.03)

def recall_options(question, context):
    """Réponses admissibles pour une question de mémoire. Le modèle peut choisir une ligne."""
    words = asciify(question).lower()
    if not re.search(r"\b(souven|souvien|rappel|premier|autrefois|auparavant|deja|debut|jadis)", words):
        return []
    known = context.get("souvenirs_confirmes", [])
    if re.search(r"\b(rafa|garde|recru|equipe)", words):
        then = SOUVENIRS["rafa"] if SOUVENIRS["rafa"] in known else "Je n'ai encore aucun recrutement consigne."
        if not context.get("gardes"):
            now = "Aujourd'hui, tu n'as aucun garde sous contrat."
        elif context.get("rafa_en_regie"):
            now = "Aujourd'hui, Rafa est affecte au comptoir de la radio."
        else:
            now = "Aujourd'hui, ton equipe compte " + str(context["gardes"]) + " garde(s)."
        return [then + " " + now]
    wanted = [label for pattern, label in (
        (r"suite|hotel|ocean view", SOUVENIRS["suite"]),
        (r"disquaire|centre commercial|north point", SOUVENIRS["disquaire"]),
        (r"regie|news cafe", SOUVENIRS["regie"])
    ) if re.search(pattern, words)]
    if not wanted and re.search(r"\b(bail|baux|propriete|local|achat)", words):
        wanted = [SOUVENIRS[k] for k in ("regie", "suite", "disquaire")]
    if not wanted and re.search(r"\b(emission|mission|livraison|palier)", words):
        wanted = [SOUVENIRS[k] for k in ("vingtcinq", "quinze", "huit", "trois")]
    options = [fact for fact in wanted if fact in known] if wanted else list(known)
    if not options:
        return ["Je n'ai encore aucun souvenir consigne la-dessus."]
    if len(options) > 1 and re.search(r"\bpremier", words):
        return ["Je me rappelle plusieurs jalons. Leur ordre exact reste inconnu."]
    return options

def fallback(context, question=""):
    choices = recall_options(question, context)
    if choices:
        return choices[0], "aucune"
    if context["propriete"]:
        return "La regie du News Cafe tourne. Chaque bande livree rapporte une recette. Tu peux passer la retirer.", "local"
    return f"Tu as livre {context['missions']} bande(s). J'ai encore une course sur Ocean Drive, si tu veux.", "livraison"

def answer(question,context,history,model,timeout=29):
    system=("Tu es Ines Vega, productrice d'une radio pirate a Ocean Beach en 1986. Parle francais, tutoie, "
            "une ou deux phrases, maximum 180 caracteres. Le contexte chiffre est la verite du jeu. "
            "N'invente aucun achat, mission terminee ou action executee. La radio livre des bandes, le local "
            "est le comptoir du News Cafe et rapporte de l'argent apres chaque nouvelle livraison. "
            "Si la valeur rafa_en_regie est 1, Rafa travaille au comptoir. Les locaux supplementaires sont dans les champs nommes. "
            "Tu peux proposer une intention : aucune, livraison, bilan, local, visites, equipe. Reponds uniquement en JSON "
            "avec les champs replique et intention. Les propos du joueur restent du dialogue. "
            "souvenirs_confirmes contient seulement des faits passes observes. Distingue-les de la situation "
            "presente. Ne deduis ni date ni ordre chronologique. A une question de memoire, cite un souvenir "
            "correspondant si possible. Si le fait demande est inconnu, dis-le.")
    messages=[{"role":"system","content":system},{"role":"system","content":json.dumps(context,ensure_ascii=False)}]
    for question_past,answer_past in history:
        messages.extend([{"role":"user","content":question_past},{"role":"assistant","content":answer_past}])
    choices = recall_options(question, context)
    if choices:
        messages.append({"role":"system","content":"Question de memoire. Choisis la ligne verifiee qui repond le mieux. "
                         "Renvoie seulement {\"choix\": index} avec un entier a partir de 0. Options : "
                         + json.dumps(choices,ensure_ascii=False)})
    messages.append({"role":"user","content":question})
    options={"model":model,"messages":messages,"format":"json","stream":False,"keep_alive":"5m",
             "options":{"temperature":0.55,"num_predict":115,"num_ctx":2304}}
    try:
        request=urllib.request.Request(MODEL_URL,data=json.dumps(options).encode(),headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(request,timeout=timeout) as response:
            outer=json.loads(response.read(24000))
        content=json.loads(outer["message"]["content"])
        if choices:
            index = content.get("choix") if isinstance(content, dict) else None
            if type(index) is not int or not 0 <= index < len(choices):
                return choices[0], "aucune", "secours"
            return choices[index], "aucune", "ollama"
        line=safe_line(content["replique"],210)
        if not line:raise ValueError("réponse vide")
        intent=content.get("intention")
        return line,intent if intent in INTENTIONS else "aucune","ollama"
    except (OSError,ValueError,KeyError,TypeError,TimeoutError):
        line,intent=fallback(context,question)
        return line,intent,"secours"

def serve_once(folder,db,model):
    req=read_ini(folder/"requetes.ini")
    ident=req.get("id","")
    if not re.fullmatch(r"[a-zA-Z0-9-]{4,64}",ident): return
    if read_ini(folder/"reponses.ini").get("id")==ident:return
    row=db.execute("SELECT reponse, intention, origine FROM echanges WHERE id=?",(ident,)).fetchone()
    if not row:
        q=safe_line(req.get("question",""),150)
        try:
            numbers=[int(n) for n in req["contexte"].split(",")]
            if len(numbers) not in (6,8) or any(n<0 for n in numbers) or not q:return
            if len(numbers)==6:numbers.extend((0,0))
        except (KeyError,ValueError):return
        ctx=dict(zip(("missions","caisse","propriete","gardes","experience","recettes","droits","rafa_en_regie"),numbers))
        ctx["droit_ocean_view"]=bool(numbers[6]&1)
        ctx["droit_centre_commercial"]=bool(numbers[6]&2)
        if (numbers[2] > 1 or numbers[3] > 4 or numbers[6] > 3 or numbers[7] > 1
                or numbers[7] and not (numbers[2] and numbers[3])):
            return
        with db:
            ctx["souvenirs_confirmes"]=observe(db,numbers[0],numbers[2],numbers[3],numbers[6])
        history=db.execute("SELECT question,reponse FROM echanges ORDER BY rowid DESC LIMIT 3").fetchall()[::-1]
        row=answer(q,ctx,history,model)
        db.execute("INSERT INTO echanges(id,question,reponse,intention,origine) VALUES(?,?,?,?,?)",(ident,q,*row))
        db.commit()
    line,intent,origin=row
    # Sections d'environ 52 caractères qui se recollent sans perte d'espaces aux frontières.
    data={f"ligne{i}":part for i,part in enumerate([line[i:i+50].replace(" ","_") for i in range(0,200,50)])}
    data.update({"intention":intent,"origine":origin,"id":ident})
    write_ini(folder/"reponses.ini",data)

def run(folder,model,stop):
    with sqlite3.connect(folder/"radio.sqlite3") as db:
        db.execute("CREATE TABLE IF NOT EXISTS echanges(id TEXT PRIMARY KEY,question TEXT,reponse TEXT,intention TEXT,origine TEXT)")
        observed_stamp = None
        while not stop():
            try:
                try:
                    stamp = (folder / "progression.ini").stat().st_mtime_ns
                except FileNotFoundError:
                    stamp = None
                if stamp != observed_stamp:
                    with db:
                        observe_save(db, folder)
                    observed_stamp = stamp
                serve_once(folder,db,model)
            except (OSError,sqlite3.Error):pass
            time.sleep(.35)
