import csv
import json
import os
import queue
import random
import re
import sys
import threading
import time
import tkinter as tk
import unicodedata
import webbrowser
from io import BytesIO
from urllib.parse import quote

import pandas as pd
import requests
from dotenv import load_dotenv

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = ImageTk = None

load_dotenv()
API_KEY = os.getenv("LASTFM_API_KEY")
URL = "https://ws.audioscrobbler.com/2.0/"
RUTA_VISTOS = "data/albumes_vistos.csv"
PLACEHOLDER_LASTFM = "2a96cbd8b46e442fc41c2b86b821562f"
MAX_PISTAS = 12
IDIOMA_ES = ("spanish", "español", "espanol", "latin", "latino", "latina")

BG = "#121212"
CARD = "#181818"
CHIP = "#2A2A2A"
VERDE = "#1DB954"
TEXTO = "#FFFFFF"
GRIS = "#B3B3B3"
FUENTE = "Segoe UI"


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


def cargar_filtro():
    ruta = "data/filtro.json"
    if not os.path.exists(ruta):
        return {"generos": [], "espanol": False}
    with open(ruta, encoding="utf-8") as f:
        filtro = {"generos": [], "espanol": False}
        filtro.update(json.load(f))
        return filtro


def cumple_filtro(tags, filtro):
    etiquetas = [norm(t) for t in tags]
    generos = [norm(g) for g in filtro["generos"]]
    if generos and not any(g in etiqueta for g in generos for etiqueta in etiquetas):
        return False
    return not filtro["espanol"] or any(
        idioma in etiqueta for idioma in IDIOMA_ES for etiqueta in etiquetas
    )


def lastfm(metodo, **params):
    try:
        r = requests.get(URL, params={"method": metodo, "api_key": API_KEY,
                                      "format": "json", "autocorrect": 1, **params},
                         timeout=10).json()
        return None if "error" in r else r
    except Exception:
        return None
    finally:
        time.sleep(0.2)


def parecido(a, b):
    return min(len(a), len(b)) >= 4 and (a in b or b in a)


def cargar_vistos():
    if not os.path.exists(RUTA_VISTOS):
        return set()
    df = pd.read_csv(RUTA_VISTOS)
    return {(norm(a), norm(b)) for a, b in zip(df["artista"], df["album"])}


def guardar_visto(artista, album):
    nuevo = not os.path.exists(RUTA_VISTOS)
    with open(RUTA_VISTOS, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if nuevo:
            w.writerow(["artista", "album"])
        w.writerow([artista, album])


def cargar_datos():
    guardadas = pd.read_csv("data/guardadas.csv")
    top = pd.read_csv("data/top_artistas.csv")

    pesos = {}
    for a, n in guardadas["artista"].value_counts().items():
        pesos[a] = pesos.get(a, 0) + n
    mult = {"short_term": 3, "medium_term": 2, "long_term": 1}
    for _, f in top.iterrows():
        puntos = (51 - f["posicion"]) / 50 * 5 * mult[f["rango"]]
        pesos[f["artista"]] = pesos.get(f["artista"], 0) + puntos

    recientes = set(top.loc[top["rango"] == "short_term", "artista"])
    if os.path.exists("data/recientes.csv"):
        recientes |= set(pd.read_csv("data/recientes.csv")["artista"])
    recientes_norm = {norm(a) for a in recientes}
    tuyos = {a: p for a, p in pesos.items() if norm(a) not in recientes_norm}

    albumes_guardados = {}
    for a, al in zip(guardadas["artista"], guardadas["album"].fillna("")):
        albumes_guardados.setdefault(norm(a), set()).add(norm(al))

    rechazados = set()
    if os.path.exists("data/feedback.csv"):
        fb = pd.read_csv("data/feedback.csv")
        rechazados = {norm(a) for a in fb.loc[fb["decision"] == "no", "artista"]}

    nuevos = {}
    if os.path.exists("data/recomendaciones_artistas.csv"):
        recs = pd.read_csv("data/recomendaciones_artistas.csv")
        nuevos = {r.artista: r.score for r in recs.itertuples()
                  if norm(r.artista) not in rechazados}

    return {
        "tuyos": tuyos,
        "nuevos": nuevos,
        "conteo": guardadas["artista"].value_counts().to_dict(),
        "albumes_guardados": albumes_guardados,
    }


def url_portada(imagenes):
    for img in reversed(imagenes or []):
        u = img.get("#text", "")
        if u and PLACEHOLDER_LASTFM not in u:
            return u
    return None


def album_de_artista(artista, modo, ocultos, datos, peso, filtro):
    r = lastfm("artist.getTopAlbums", artist=artista, limit=12)
    albumes = r["topalbums"]["album"] if r and "topalbums" in r else []
    guardados = datos["albumes_guardados"].get(norm(artista), set()) if modo == "tuyos" else set()

    validos = []
    for al in albumes:
        n = norm(al.get("name", ""))
        if not n or n == "null":
            continue
        if (norm(artista), n) in ocultos:
            continue
        if any(parecido(n, g) for g in guardados):
            continue
        validos.append(al)
    if not validos:
        return None

    validos = validos[:8]
    al = random.choices(validos, weights=[max(1, int(a.get("playcount", 1))) ** 0.5
                                          for a in validos])[0]
    nombre = al["name"]
    nombre_artista = al.get("artist", {}).get("name", artista)

    r = lastfm("album.getInfo", artist=artista, album=nombre)
    info = (r or {}).get("album", {})

    pistas = info.get("tracks", {})
    pistas = pistas.get("track", []) if isinstance(pistas, dict) else []
    if isinstance(pistas, dict):
        pistas = [pistas]
    pistas = [p["name"] for p in pistas]

    tags = info.get("tags", {})
    tags = tags.get("tag", []) if isinstance(tags, dict) else []
    if isinstance(tags, dict):
        tags = [tags]
    tags = [t["name"] for t in tags if t.get("name")]
    if not cumple_filtro(tags, filtro):
        return None
    tags = ", ".join(tags[:5])

    portada = None
    url = url_portada(info.get("image")) or url_portada(al.get("image"))
    if url:
        try:
            portada = requests.get(url, timeout=10).content
        except Exception:
            pass

    if modo == "tuyos":
        n = datos["conteo"].get(artista, 0)
        if n:
            unidad = "canción guardada" if n == 1 else "canciones guardadas"
            razon = (f"Tienes {n} {unidad} de {nombre_artista}, pero no suena en tus "
                     f"escuchas recientes ni en tu top de las últimas 4 semanas. "
                     f"Parece que no tienes canciones guardadas de este álbum.")
        else:
            razon = (f"{nombre_artista} está en tu top, pero no lo has escuchado "
                     f"últimamente. Parece que no tienes canciones de este álbum.")
    else:
        razon = f"Artista nuevo para ti. Encaja con tu gusto (afinidad {peso:.2f})."

    return {
        "album": nombre,
        "artista": nombre_artista,
        "busqueda": artista,
        "clave": (norm(artista), norm(nombre)),
        "pistas": pistas,
        "tags": tags,
        "razon": razon,
        "portada": portada,
    }


def elegir_album(modo, ocultos, datos, filtro):
    artistas = dict(datos[modo])
    if not artistas:
        if modo == "nuevos":
            raise RuntimeError("Aún no hay artistas recomendados. Ejecuta antes el modo playlist "
                               "o: python main.py --solo genero recomendar")
        raise RuntimeError("No hay artistas en tu biblioteca para este modo.")

    for _ in range(8):
        if not artistas:
            break
        nombres = list(artistas)
        a = random.choices(nombres, weights=[max(artistas[n], 0.1) ** 0.5 for n in nombres])[0]
        peso = artistas.pop(a)
        album = album_de_artista(a, modo, ocultos, datos, peso, filtro)
        if album:
            return album
    raise RuntimeError("No he encontrado álbumes que coincidan con el filtro. "
                       "Prueba con otro género o sin filtro.")


def boton(padre, texto, comando, bg=CHIP, hover="#3E3E3E", fg=TEXTO):
    b = tk.Label(padre, text=texto, bg=bg, fg=fg, font=(FUENTE, 11, "bold"),
                 padx=16, pady=8, cursor="hand2")
    b.bind("<Button-1>", lambda e: comando())
    b.bind("<Enter>", lambda e: b.config(bg=hover))
    b.bind("<Leave>", lambda e: b.config(bg=bg))
    return b


class App(tk.Tk):
    def __init__(self, datos):
        super().__init__()
        self.title("Recomendador · Álbumes")
        self.geometry("860x700")
        self.minsize(760, 620)
        self.configure(bg=BG)

        self.datos = datos
        self.filtro = cargar_filtro()
        self.modo = "tuyos"
        self.actual = None
        self.ocupado = False
        self.cola = queue.Queue()
        self.sesion = set()
        self.vistos = cargar_vistos()
        self.foto = None

        cab = tk.Frame(self, bg=BG, padx=28, pady=20)
        cab.pack(fill="x")
        tk.Label(cab, text="Un álbum para hoy", bg=BG, fg=TEXTO,
                 font=(FUENTE, 22, "bold")).pack(anchor="w")
        tk.Label(cab, text="Elige de dónde quieres que salga", bg=BG, fg=GRIS,
                 font=(FUENTE, 10)).pack(anchor="w")

        pie = tk.Frame(self, bg="#000000", padx=28, pady=14)
        pie.pack(side="bottom", fill="x")
        boton(pie, "Escuchar en Spotify", self.abrir_spotify,
              bg=VERDE, hover="#1ED760", fg="#000000").pack(side="left")
        boton(pie, "Ya lo conozco", self.ya_lo_conozco).pack(side="right")
        boton(pie, "Otro álbum", self.otro).pack(side="right", padx=8)

        modos = tk.Frame(self, bg=BG, padx=28)
        modos.pack(fill="x")
        self.chips = {
            "tuyos": self.crear_chip(modos, "De tus artistas (sin escuchar hace poco)", "tuyos"),
            "nuevos": self.crear_chip(modos, "De artistas nuevos para ti", "nuevos"),
        }
        for c in self.chips.values():
            c.pack(side="left", padx=(0, 8))

        tarjeta = tk.Frame(self, bg=CARD, padx=22, pady=22)
        tarjeta.pack(fill="both", expand=True, padx=28, pady=18)

        marco = tk.Frame(tarjeta, bg=CHIP, width=240, height=240)
        marco.pack(side="left", anchor="n")
        marco.pack_propagate(False)
        self.portada = tk.Label(marco, bg=CHIP, fg=GRIS, text="♪", font=(FUENTE, 64))
        self.portada.pack(fill="both", expand=True)

        der = tk.Frame(tarjeta, bg=CARD)
        der.pack(side="left", fill="both", expand=True, padx=(22, 0))
        self.titulo = tk.Label(der, bg=CARD, fg=TEXTO, font=(FUENTE, 20, "bold"),
                               wraplength=430, justify="left", anchor="w")
        self.titulo.pack(fill="x")
        self.artista = tk.Label(der, bg=CARD, fg=VERDE, font=(FUENTE, 13, "bold"),
                                wraplength=430, justify="left", anchor="w")
        self.artista.pack(fill="x", pady=(2, 10))
        self.razon = tk.Label(der, bg=CARD, fg=GRIS, font=(FUENTE, 10),
                              wraplength=430, justify="left", anchor="w")
        self.razon.pack(fill="x")
        self.tags = tk.Label(der, bg=CARD, fg=GRIS, font=(FUENTE, 9, "italic"),
                             wraplength=430, justify="left", anchor="w")
        self.tags.pack(fill="x", pady=(8, 10))
        self.pistas = tk.Label(der, bg=CARD, fg=TEXTO, font=(FUENTE, 10),
                               justify="left", anchor="nw")
        self.pistas.pack(fill="x")

        self.pintar_chips()
        self.buscar()

    def crear_chip(self, padre, texto, modo):
        c = tk.Label(padre, text=texto, bg=CHIP, fg=TEXTO, font=(FUENTE, 10, "bold"),
                     padx=14, pady=7, cursor="hand2")
        c.bind("<Button-1>", lambda e: self.cambiar_modo(modo))
        return c

    def pintar_chips(self):
        for m, c in self.chips.items():
            activo = m == self.modo
            c.config(bg=VERDE if activo else CHIP, fg="#000000" if activo else TEXTO)

    def cambiar_modo(self, modo):
        if self.ocupado or modo == self.modo:
            return
        self.modo = modo
        self.pintar_chips()
        self.buscar()

    def buscar(self):
        if self.ocupado:
            return
        self.ocupado = True
        self.limpiar("Buscando...")
        ocultos = self.vistos | self.sesion
        threading.Thread(target=self.trabajo, args=(self.modo, ocultos), daemon=True).start()
        self.after(150, self.esperar)

    def trabajo(self, modo, ocultos):
        try:
            self.cola.put(("ok", elegir_album(modo, ocultos, self.datos, self.filtro)))
        except Exception as e:
            self.cola.put(("error", str(e)))

    def esperar(self):
        try:
            tipo, dato = self.cola.get_nowait()
        except queue.Empty:
            self.after(150, self.esperar)
            return
        self.ocupado = False
        if tipo == "ok":
            self.mostrar(dato)
        else:
            self.actual = None
            self.limpiar(dato)

    def limpiar(self, mensaje):
        self.titulo.config(text=mensaje)
        for w in (self.artista, self.razon, self.tags, self.pistas):
            w.config(text="")
        self.poner_portada(None)

    def poner_portada(self, datos_img):
        self.foto = None
        if datos_img and Image is not None:
            try:
                img = Image.open(BytesIO(datos_img)).convert("RGB").resize((240, 240))
                self.foto = ImageTk.PhotoImage(img)
            except Exception:
                self.foto = None
        if self.foto:
            self.portada.config(image=self.foto, text="")
        else:
            self.portada.config(image="", text="♪")

    def mostrar(self, album):
        self.actual = album
        self.sesion.add(album["clave"])
        self.titulo.config(text=album["album"])
        self.artista.config(text=album["artista"])
        self.razon.config(text=album["razon"])
        self.tags.config(text=album["tags"])

        pistas = album["pistas"]
        lineas = [f"{i}. {p}" for i, p in enumerate(pistas[:MAX_PISTAS], 1)]
        if len(pistas) > MAX_PISTAS:
            lineas.append(f"… y {len(pistas) - MAX_PISTAS} más")
        self.pistas.config(text="\n".join(lineas))
        self.poner_portada(album["portada"])

    def otro(self):
        self.buscar()

    def ya_lo_conozco(self):
        if self.ocupado or not self.actual:
            return
        guardar_visto(self.actual["busqueda"], self.actual["album"])
        self.vistos.add(self.actual["clave"])
        self.buscar()

    def abrir_spotify(self):
        if self.actual:
            q = quote(f"{self.actual['album']} {self.actual['artista']}")
            webbrowser.open(f"https://open.spotify.com/search/{q}/albums")


if __name__ == "__main__":
    if not API_KEY:
        print("Falta LASTFM_API_KEY en el archivo .env")
        sys.exit(1)
    try:
        datos = cargar_datos()
    except FileNotFoundError:
        print("Faltan datos. Ejecuta antes: python main.py --solo descargar")
        sys.exit(1)
    App(datos).mainloop()