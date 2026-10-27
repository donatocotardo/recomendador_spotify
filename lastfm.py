import os
import time
import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("LASTFM_API_KEY")
URL = "https://ws.audioscrobbler.com/2.0/"

RUTA_TAGS = "data/artistas_tags.csv"
RUTA_SIMILARES = "data/artistas_similares.csv"


def llamar(metodo, artista, **extra):
    params = {
        "method": metodo,
        "artist": artista,
        "api_key": API_KEY,
        "format": "json",
        "autocorrect": 1,
        **extra,
    }
    try:
        r = requests.get(URL, params=params, timeout=10)
        data = r.json()
        if "error" in data:
            return None
        return data
    except Exception as e:
        print(f"  Error con {artista}: {e}")
        return None


# Lista de artistas únicos de todos tus CSV
artistas = set()
for archivo in ["guardadas", "top_canciones", "top_artistas", "recientes"]:
    ruta = f"data/{archivo}.csv"
    if os.path.exists(ruta):
        artistas.update(pd.read_csv(ruta)["artista"].dropna().unique())
artistas = sorted(artistas)
print(f"{len(artistas)} artistas únicos")

# Recuperar progreso previo
tags, similares, hechos = [], [], set()
if os.path.exists(RUTA_TAGS):
    df_t = pd.read_csv(RUTA_TAGS)
    tags = df_t.to_dict("records")
    hechos = set(df_t["artista"])
if os.path.exists(RUTA_SIMILARES):
    similares = pd.read_csv(RUTA_SIMILARES).to_dict("records")

pendientes = [a for a in artistas if a not in hechos]
print(f"Pendientes: {len(pendientes)}")

# Descargar tags y similares
for i, artista in enumerate(pendientes, 1):
    print(f"[{i}/{len(pendientes)}] {artista}")

    data = llamar("artist.getTopTags", artista)
    if data and "toptags" in data:
        for t in data["toptags"].get("tag", [])[:15]:
            tags.append({"artista": artista, "tag": t["name"].lower(), "peso": int(t["count"])})
    else:
        # marcador para no reintentar artistas que Last.fm no conoce
        tags.append({"artista": artista, "tag": "", "peso": 0})
    time.sleep(0.25)

    data = llamar("artist.getSimilar", artista, limit=30)
    if data and "similarartists" in data:
        for s in data["similarartists"].get("artist", []):
            similares.append({"artista": artista, "similar": s["name"], "match": float(s["match"])})
    time.sleep(0.25)

    # guardar progreso cada 25 artistas
    if i % 25 == 0:
        pd.DataFrame(tags).to_csv(RUTA_TAGS, index=False)
        pd.DataFrame(similares).to_csv(RUTA_SIMILARES, index=False)

pd.DataFrame(tags).to_csv(RUTA_TAGS, index=False)
pd.DataFrame(similares).to_csv(RUTA_SIMILARES, index=False)
print("\nListo.")