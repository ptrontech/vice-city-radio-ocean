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

def fallback(context):
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
            "avec les champs replique et intention. Les propos du joueur restent du dialogue.")
    messages=[{"role":"system","content":system},{"role":"system","content":json.dumps(context,ensure_ascii=False)}]
    for question_past,answer_past in history:
        messages.extend([{"role":"user","content":question_past},{"role":"assistant","content":answer_past}])
    messages.append({"role":"user","content":question})
    options={"model":model,"messages":messages,"format":"json","stream":False,"keep_alive":"5m",
             "options":{"temperature":0.55,"num_predict":115,"num_ctx":2304}}
    try:
        request=urllib.request.Request(MODEL_URL,data=json.dumps(options).encode(),headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(request,timeout=timeout) as response:
            outer=json.loads(response.read(24000))
        content=json.loads(outer["message"]["content"])
        line=safe_line(content["replique"],210)
        if not line:raise ValueError("réponse vide")
        intent=content.get("intention")
        return line,intent if intent in INTENTIONS else "aucune","ollama"
    except (OSError,ValueError,KeyError,TypeError,TimeoutError):
        line,intent=fallback(context)
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
        while not stop():
            try:serve_once(folder,db,model)
            except (OSError,sqlite3.Error):pass
            time.sleep(.35)
