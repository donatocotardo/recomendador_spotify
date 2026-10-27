import json
import os
import re
import sys
import time
import unicodedata

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv
from sklearn.feature_extraction.text import TfidfVectorizer

load_dotenv()
API_KEY = os.getenv("LASTFM_API_KEY")
URL = "https://ws.audioscrobbler.com/2.0/"

EXCLUIR = {"dreamville"}
N_POR_TAG = 40
N_CANDIDATOS_MAX = 220
UMBRAL_TAG = 10
ALIAS = {"rnb": {"rnb", "rb"}, "hiphop": {"hiphop", "rap"}}
IDIOMA_ES = {"spanish", "espanol", "espana", "spain", "latin", "argentin", "mexic",
             "chile", "colombia", "puertorico", "galiza"}


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


def lastfm(metodo, **params):
    try:
        r = requests.get(URL, params={"method": metodo, "api_key": API_KEY,
                                      "format": "json", "autocorrect": 1, **params},
                         timeout=10).json()
        return None if "error" in r else r
    except Exception:
        return None
    finally:
        time.sleep(0.25)


def doc_desde_tags(pares):
    palabras = []
    for tag, peso in pares:
        t = norm(tag)
        if t:
            palabras += [t] * max(1, int(peso) // 10)
    return " ".join(palabras)


filtro = {"generos": [], "espanol": False}
if os.path.exists("data/filtro.json"):
    with open("data/filtro.json", encoding="utf-8") as f:
        filtro.update(json.load(f))
generos = filtro["generos"]
generos_norm = [norm(g) for g in generos]
hay_filtro = bool(generos) or filtro["espanol"]

if os.path.exists("data/feedback.csv"):
    fb = pd.read_csv("data/feedback.csv")
    EXCLUIR |= {norm(a) for a in fb.loc[fb["decision"] == "no", "artista"]}

tags = pd.read_csv("data/artistas_tags.csv").dropna(subset=["tag"])
sim = pd.read_csv("data/artistas_similares.csv")
guardadas = pd.read_csv("data/guardadas.csv")
top_art = pd.read_csv("data/top_artistas.csv")

pesos = {}
for artista, n in guardadas["artista"].value_counts().items():
    pesos[artista] = pesos.get(artista, 0) + n

mult_rango = {"short_term": 3, "medium_term": 2, "long_term": 1}
for _, f in top_art.iterrows():
    puntos = (51 - f["posicion"]) / 50 * 5 * mult_rango[f["rango"]]
    pesos[f["artista"]] = pesos.get(f["artista"], 0) + puntos

mis_artistas = set(pesos)

docs = tags.groupby("artista").apply(
    lambda df: doc_desde_tags(zip(df["tag"], df["peso"]))
)
vec = TfidfVectorizer(token_pattern=r"\S+")
matriz = vec.fit_transform(docs.values)
indice = {a: i for i, a in enumerate(docs.index)}

perfil = np.zeros(matriz.shape[1])
for artista, p in pesos.items():
    if artista in indice:
        perfil += matriz[indice[artista]].toarray().ravel() * p
perfil = perfil / np.linalg.norm(perfil)

excluidos = {norm(a) for a in mis_artistas} | EXCLUIR
cand = sim[~sim["similar"].map(norm).isin(excluidos)].copy()
cand["aporte"] = cand["match"] * cand["artista"].map(pesos).fillna(0)
vecinos = cand.groupby("similar")["aporte"].sum()
vecinos = vecinos / vecinos.max()

n_vecinos = 80 if hay_filtro else 150
pool = vecinos.sort_values(ascending=False).head(n_vecinos).index.tolist()

if hay_filtro:
    if generos:
        consultas = []
        for g in generos:
            consultas += [f"spanish {g}", f"{g} en espanol"] if filtro["espanol"] else [g]
    else:
        consultas = ["spanish"]
    vistos = {norm(a) for a in pool}
    for q in consultas:
        print(f"Buscando artistas del tag '{q}'")
        r = lastfm("tag.getTopArtists", tag=q, limit=N_POR_TAG)
        if not r or "topartists" not in r:
            continue
        for a in r["topartists"].get("artist", []):
            nombre = a["name"]
            if norm(nombre) not in excluidos and norm(nombre) not in vistos:
                pool.append(nombre)
                vistos.add(norm(nombre))
    pool = pool[:N_CANDIDATOS_MAX]

tags_cand = {}
for i, artista in enumerate(pool, 1):
    print(f"[{i}/{len(pool)}] {artista}")
    r = lastfm("artist.getTopTags", artist=artista)
    if r and "toptags" in r:
        tags_cand[artista] = [(t["name"], int(t["count"])) for t in r["toptags"]["tag"][:15]]


def cumple_filtro(pares):
    nt = [norm(t) for t, p in pares if p >= UMBRAL_TAG]
    for g in generos_norm:
        if not any(o in t for o in ALIAS.get(g, {g}) for t in nt):
            return False
    if filtro["espanol"] and not any(o in t for o in IDIOMA_ES for t in nt):
        return False
    return True


filas = []
for artista in pool:
    if artista not in tags_cand:
        continue
    if hay_filtro and not cumple_filtro(tags_cand[artista]):
        continue
    v = vec.transform([doc_desde_tags(tags_cand[artista])]).toarray().ravel()
    norma = np.linalg.norm(v)
    contenido = float(v @ perfil / norma) if norma > 0 else 0.0
    filas.append({
        "artista": artista,
        "vecinos": float(vecinos.get(artista, 0.0)),
        "contenido": contenido,
        "tags": ", ".join(t for t, _ in tags_cand[artista][:4]),
    })

if not filas:
    print("\nNingún artista cumple el filtro. Prueba con menos géneros o sin 'Solo en español'.")
    sys.exit(1)

peso_vecinos, peso_contenido = (0.3, 0.7) if hay_filtro else (0.6, 0.4)
res = pd.DataFrame(filas)
res["score"] = peso_vecinos * res["vecinos"] + peso_contenido * res["contenido"]
res = res.sort_values("score", ascending=False)

print("\nTop 25 artistas recomendados:\n")
print(res.head(25).to_string(index=False))
res.to_csv("data/recomendaciones_artistas.csv", index=False)