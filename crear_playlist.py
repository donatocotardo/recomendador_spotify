import os
import time
import unicodedata, re
import pandas as pd
import requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("LASTFM_API_KEY")
URL = "https://ws.audioscrobbler.com/2.0/"

N_ARTISTAS = 20          # cuántos artistas de la lista usar
CANCIONES_POR_ARTISTA = 2


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    scope="playlist-modify-private user-library-read"
))

recs = pd.read_csv("data/recomendaciones_artistas.csv")
if os.path.exists("data/feedback.csv"):
    fb = pd.read_csv("data/feedback.csv")
    rechazados = set(fb.loc[fb["decision"] == "no", "artista"])
    recs = recs[~recs["artista"].isin(rechazados)]
recs = recs.head(N_ARTISTAS)

guardadas_ids = set(pd.read_csv("data/guardadas.csv")["track_id"])

uris = []
for artista in recs["artista"]:
    # Canciones más populares del artista según Last.fm
    try:
        r = requests.get(URL, params={
            "method": "artist.getTopTracks", "artist": artista,
            "api_key": API_KEY, "format": "json", "autocorrect": 1, "limit": 8,
        }, timeout=10).json()
        temas = [t["name"] for t in r["toptracks"]["track"]]
    except Exception:
        print(f"  Sin canciones en Last.fm: {artista}")
        continue
    time.sleep(0.25)

    # Buscar cada una en Spotify
    añadidas = 0
    for tema in temas:
        if añadidas >= CANCIONES_POR_ARTISTA:
            break
        try:
            res = sp.search(q=f'track:"{tema}" artist:"{artista}"', type="track", limit=5)
        except Exception as e:
            print(f"  Error buscando '{tema}': {e}")
            continue
        for t in res["tracks"]["items"]:
            mismo_artista = any(norm(a["name"]) == norm(artista) for a in t["artists"])
            if mismo_artista and t["id"] not in guardadas_ids and t["uri"] not in uris:
                uris.append(t["uri"])
                añadidas += 1
                print(f"  + {artista} - {t['name']}")
                break

print(f"\n{len(uris)} canciones encontradas")

# Crear la playlist privada
usuario = sp.current_user()["id"]
playlist = sp._post("me/playlists", payload={
    "name": "Recomendador v1",
    "public": False,
    "description": "Generada por mi recomendador en Python",
})

for i in range(0, len(uris), 100):
    sp._post(f"playlists/{playlist['id']}/items", payload={"uris": uris[i:i + 100]})

print("Playlist creada:", playlist["external_urls"]["spotify"])