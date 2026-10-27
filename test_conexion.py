import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

load_dotenv()

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    scope="user-top-read user-library-read user-read-recently-played playlist-modify-private"
))

usuario = sp.current_user()
print(f"Conectado como: {usuario['display_name']}")

print("\nTus 5 artistas más escuchados:")
top = sp.current_user_top_artists(limit=5, time_range="medium_term")
for i, artista in enumerate(top["items"], 1):
    print(f"{i}. {artista['name']}")