import os
import re
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
N_CANDIDATOS = 150
PESO_VECINOS = 0.6
PESO_CONTENIDO = 0.4


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


def doc_desde_tags(pares):
    palabras = []
    for tag, peso in pares:
        t = norm(tag)
        if t:
            palabras += [t] * max(1, int(peso) // 10)
    return " ".join(palabras)


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

mis_norm = {norm(a) for a in mis_artistas} | EXCLUIR
cand = sim[~sim["similar"].map(norm).isin(mis_norm)].copy()

cand["aporte"] = cand["match"] * cand["artista"].map(pesos).fillna(0)
vecinos = cand.groupby("similar")["aporte"].sum()
vecinos = vecinos / vecinos.max()

top_cand = vecinos.sort_values(ascending=False).head(N_CANDIDATOS).index.tolist()
tags_cand = {}
for i, artista in enumerate(top_cand, 1):
    print(f"[{i}/{len(top_cand)}] {artista}")
    try:
        r = requests.get(URL, params={
            "method": "artist.getTopTags",
            "artist": artista,
            "api_key": API_KEY,
            "format": "json",
            "autocorrect": 1,
        }, timeout=10).json()
        tags_cand[artista] = [(t["name"], int(t["count"])) for t in r["toptags"]["tag"][:15]]
    except Exception:
        pass
    time.sleep(0.25)

filas = []
for artista in top_cand:
    if artista not in tags_cand:
        continue
    v = vec.transform([doc_desde_tags(tags_cand[artista])]).toarray().ravel()
    norma = np.linalg.norm(v)
    if norma == 0:
        continue
    filas.append({
        "artista": artista,
        "vecinos": vecinos[artista],
        "contenido": float(v @ perfil / norma),
    })

res = pd.DataFrame(filas)
res["score"] = PESO_VECINOS * res["vecinos"] + PESO_CONTENIDO * res["contenido"]
res = res.sort_values("score", ascending=False)

print("\nTop 25 artistas recomendados:\n")
print(res.head(25).to_string(index=False))
res.to_csv("data/recomendaciones_artistas.csv", index=False)