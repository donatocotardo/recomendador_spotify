import argparse
import os
import subprocess
import sys
import time
import tkinter as tk

BG = "#121212"
CARD = "#181818"
HOVER = "#282828"
VERDE = "#1DB954"
TEXTO = "#FFFFFF"
GRIS = "#B3B3B3"
FUENTE = "Segoe UI"

SCRIPTS = {
    "descargar": "descargar_datos.py",
    "enriquecer": "enriquecer_lastfm.py",
    "genero": "elegir_genero.py",
    "recomendar": "recomendar.py",
    "revisar": "revisar_artistas.py",
    "playlist": "crear_playlist.py",
    "album": "recomendar_album.py",
}

FLUJOS = {
    "playlist": ["descargar", "enriquecer", "genero", "recomendar", "revisar", "playlist"],
    "album": ["descargar", "album"],
}


def menu():
    eleccion = {}
    root = tk.Tk()
    root.title("Recomendador")
    root.geometry("760x520")
    root.configure(bg=BG)

    tk.Label(root, text="¿Qué quieres hacer hoy?", bg=BG, fg=TEXTO,
             font=(FUENTE, 24, "bold")).pack(anchor="w", padx=32, pady=(28, 4))
    tk.Label(root, text="Elige una opción para empezar", bg=BG, fg=GRIS,
             font=(FUENTE, 11)).pack(anchor="w", padx=32)

    actualizar = tk.BooleanVar(value=not os.path.exists("data/guardadas.csv"))

    def elegir(modo):
        eleccion["modo"] = modo
        eleccion["actualizar"] = actualizar.get()
        root.destroy()

    def tarjeta(titulo, desc, modo):
        marco = tk.Frame(root, bg=CARD, padx=22, pady=18, cursor="hand2")
        marco.pack(fill="x", padx=32, pady=(18, 0))
        t = tk.Label(marco, text=titulo, bg=CARD, fg=TEXTO, font=(FUENTE, 15, "bold"),
                     anchor="w", cursor="hand2")
        t.pack(fill="x")
        d = tk.Label(marco, text=desc, bg=CARD, fg=GRIS, font=(FUENTE, 10), anchor="w",
                     justify="left", wraplength=640, cursor="hand2")
        d.pack(fill="x", pady=(4, 0))
        widgets = (marco, t, d)
        for w in widgets:
            w.bind("<Button-1>", lambda e: elegir(modo))
            w.bind("<Enter>", lambda e: [x.config(bg=HOVER) for x in widgets])
            w.bind("<Leave>", lambda e: [x.config(bg=CARD) for x in widgets])

    tarjeta("Crear una playlist con artistas recomendados",
            "Eliges género, descartas los artistas que no te interesan y se crea la playlist en tu Spotify.",
            "playlist")
    tarjeta("Recomiéndame un álbum",
            "Te propongo un álbum de un artista que llevas tiempo sin escuchar, o de uno nuevo para ti.",
            "album")

    tk.Checkbutton(root, text="Actualizar mis datos antes (Spotify y Last.fm)",
                   variable=actualizar, bg=BG, fg=GRIS, selectcolor="#2A2A2A",
                   activebackground=BG, activeforeground=TEXTO,
                   font=(FUENTE, 10)).pack(anchor="w", padx=32, pady=(22, 0))

    root.mainloop()
    return eleccion.get("modo"), eleccion.get("actualizar", False)


def ejecutar(nombre, script):
    print(f"\n{'=' * 50}\n{nombre.upper()}  ({script})\n{'=' * 50}")
    inicio = time.time()
    resultado = subprocess.run([sys.executable, script])
    if resultado.returncode != 0:
        print(f"\nEl paso '{nombre}' ha fallado. Pipeline detenido.")
        sys.exit(resultado.returncode)
    print(f"\n{nombre} terminado en {time.time() - inicio:.0f}s")


parser = argparse.ArgumentParser(description="Recomendador de Spotify")
parser.add_argument("--modo", choices=FLUJOS, help="playlist o album (sin esto se abre el menú)")
parser.add_argument("--saltar", nargs="+", choices=SCRIPTS, default=[], help="pasos a omitir")
parser.add_argument("--solo", nargs="+", choices=SCRIPTS, help="ejecutar solo estos pasos")
args = parser.parse_args()

if args.solo:
    pasos = [p for p in SCRIPTS if p in args.solo]
else:
    saltar = set(args.saltar)
    modo = args.modo
    if modo is None:
        modo, actualizar = menu()
        if modo is None:
            sys.exit(0)
        if not actualizar:
            saltar |= {"descargar", "enriquecer"}
    pasos = [p for p in FLUJOS[modo] if p not in saltar]

for paso in pasos:
    ejecutar(paso, SCRIPTS[paso])

print("\nTodo listo.")