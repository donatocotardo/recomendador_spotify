import os
import pandas as pd
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

load_dotenv()

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    scope="user-top-read user-library-read user-read-recently-played"
))

os.makedirs("data", exist_ok=True)


def extraer_pista(t):
    """Convierte un objeto 'track' de Spotify en una fila plana."""
    return {
        "track_id": t["id"],
        "cancion": t["name"],
        "artista": t["artists"][0]["name"],
        "artista_id": t["artists"][0]["id"],
        "album": t["album"]["name"],
        "fecha_album": t["album"].get("release_date"),
        "popularidad": t.get("popularity"),
        "duracion_ms": t.get("duration_ms"),
        "explicita": t.get("explicit"),
    }


# Canciones guardadas
print("Descargando canciones guardadas...")
guardadas = []
offset = 0
while True:
    page = sp.current_user_saved_tracks(limit=50, offset=offset)
    if not page["items"]:
        break
    for item in page["items"]:
        fila = extraer_pista(item["track"])
        fila["guardada_el"] = item["added_at"]
        guardadas.append(fila)
    offset += 50
    if page["next"] is None:
        break
df_guardadas = pd.DataFrame(guardadas)
df_guardadas.to_csv("data/guardadas.csv", index=False)
print(f"  -> {len(df_guardadas)} canciones")

# Top canciones y artistas en los 3 periodos
rangos = {
    "short_term": "últimas 4 semanas",
    "medium_term": "últimos 6 meses",
    "long_term": "último año o mas",
}

top_pistas = []
top_artistas = []
for rango, etiqueta in rangos.items():
    print(f"Descargando tops ({etiqueta})...")
    pistas = sp.current_user_top_tracks(limit=50, time_range=rango)
    for pos, t in enumerate(pistas["items"], 1):
        fila = extraer_pista(t)
        fila["rango"] = rango
        fila["posicion"] = pos
        top_pistas.append(fila)

    artistas = sp.current_user_top_artists(limit=50, time_range=rango)
    for pos, a in enumerate(artistas["items"], 1):
        top_artistas.append({
            "artista_id": a["id"],
            "artista": a["name"],
            "generos": ", ".join(a.get("genres", [])),
            "popularidad": a.get("popularity"),
            "rango": rango,
            "posicion": pos,
        })

pd.DataFrame(top_pistas).to_csv("data/top_canciones.csv", index=False)
pd.DataFrame(top_artistas).to_csv("data/top_artistas.csv", index=False)
print(f"  -> {len(top_pistas)} filas de canciones, {len(top_artistas)} de artistas")

# Escuchas recientes
print("Descargando escuchas recientes...")
recientes = sp.current_user_recently_played(limit=50)
filas = []
for item in recientes["items"]:
    fila = extraer_pista(item["track"])
    fila["escuchada_el"] = item["played_at"]
    filas.append(fila)
pd.DataFrame(filas).to_csv("data/recientes.csv", index=False)
print(f"  -> {len(filas)} escuchas")

print("\nListo. Archivos guardados en la carpeta data/")