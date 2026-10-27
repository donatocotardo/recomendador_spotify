import pandas as pd
import numpy as np
import requests
import os
import time
from dotenv import load_dotenv
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import unicodedata, re

def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


load_dotenv()
API_KEY = os.getenv("LASTFM_API_KEY")
URL = "https://ws.audioscrobbler.com/2.0/"

# Cargar datos
tags = pd.read_csv("data/artistas_tags.csv").dropna(subset=["tag"])
sim = pd.read_csv("data/artistas_similares.csv")
guardadas = pd.read_csv("data/guardadas.csv")
top_art = pd.read_csv("data/top_artistas.csv")

# Pesos de cada artista
pesos = {}

# canciones guardadas: 1 punto por canción
for a, n in guardadas["artista"].value_counts().items():
    pesos[a] = pesos.get(a, 0) + n

# tops: más peso cuanto mejor posición y más reciente
mult_rango = {"short_term": 3, "medium_term": 2, "long_term": 1}
for _, f in top_art.iterrows():
    puntos = (51 - f["posicion"]) / 50 * 5 * mult_rango[f["rango"]]
    pesos[f["artista"]] = pesos.get(f["artista"], 0) + puntos

mis_artistas = set(pesos)

# Vectores TF-IDF por artista (tags repetidos según peso)
def doc_artista(df):
    palabras = []
    for _, f in df.iterrows():
        tag = norm(f["tag"])
        tag = tag.replace(" ", "_").replace("-", "_")
        palabras += [tag] * max(1, int(f["peso"] // 10))
    return " ".join(palabras)

docs = tags.groupby("artista").apply(doc_artista)
vec = TfidfVectorizer(token_pattern=r"\S+")
matriz = vec.fit_transform(docs.values)
indice = {a: i for i, a in enumerate(docs.index)}

# Tu perfil = media ponderada de tus artistas
perfil = np.zeros(matriz.shape[1])
for a, p in pesos.items():
    if a in indice:
        perfil += matriz[indice[a]].toarray().ravel() * p
perfil = perfil / np.linalg.norm(perfil)

# Candidatos: similares que no tienes
cand = sim[~sim["similar"].isin(mis_artistas)].copy()

# score de "recomendación por vecinos": suma de match ponderada por cuánto te gusta el artista origen
cand["aporte"] = cand.apply(lambda f: f["match"] * pesos.get(f["artista"], 0), axis=1)
vecinos = cand.groupby("similar")["aporte"].sum()
vecinos = vecinos / vecinos.max()

# Tags de los candidatos
top_cand = vecinos.sort_values(ascending=False).head(150).index.tolist()
tags_cand = {}
for a in top_cand:
    try:
        r = requests.get(URL, params={
            "method": "artist.getTopTags", "artist": a, "api_key": API_KEY,
            "format": "json", "autocorrect": 1}, timeout=10).json()
        tags_cand[a] = [(t["name"].lower(), int(t["count"])) for t in r["toptags"]["tag"][:15]]
    except Exception:
        pass
    time.sleep(0.25)

# Similitud de contenido de cada candidato con tu perfil 
filas = []
for a in top_cand:
    if a not in tags_cand:
        continue
    palabras = []
    for tag, peso in tags_cand[a]:
        palabras += [tag.replace(" ", "_").replace("-", "_")] * max(1, peso // 10)
    v = vec.transform([" ".join(palabras)]).toarray().ravel()
    if np.linalg.norm(v) == 0:
        continue
    coseno = float(v @ perfil / np.linalg.norm(v))
    filas.append({"artista": a, "vecinos": vecinos[a], "contenido": coseno})

res = pd.DataFrame(filas)
res["score"] = 0.6 * res["vecinos"] + 0.4 * res["contenido"]
res = res.sort_values("score", ascending=False)

print("\nTop 25 artistas recomendados:\n")
print(res.head(25).to_string(index=False))
res.to_csv("data/recomendaciones_artistas.csv", index=False)