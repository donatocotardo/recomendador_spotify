import os
import tkinter as tk
import webbrowser
from urllib.parse import quote

import pandas as pd

RUTA_RECS = "data/recomendaciones_artistas.csv"
RUTA_FEEDBACK = "data/feedback.csv"
N_MOSTRAR = 30

BG = "#121212"
CARD = "#181818"
VERDE = "#1DB954"
TINTE_SI = "#143D26"
TINTE_NO = "#3A1A1D"
TEXTO = "#FFFFFF"
GRIS = "#B3B3B3"
FUENTE = "Segoe UI"


def cargar_feedback():
    if os.path.exists(RUTA_FEEDBACK):
        df = pd.read_csv(RUTA_FEEDBACK)
        return dict(zip(df["artista"], df["decision"]))
    return {}


def boton(padre, texto, comando, bg="#2A2A2A", hover="#3E3E3E", fg=TEXTO, size=11):
    b = tk.Label(padre, text=texto, bg=bg, fg=fg, font=(FUENTE, size, "bold"),
                 padx=14, pady=6, cursor="hand2")
    b.bind("<Button-1>", lambda e: comando())
    b.bind("<Enter>", lambda e: b.config(bg=hover))
    b.bind("<Leave>", lambda e: b.config(bg=bg))
    return b


class App(tk.Tk):
    def __init__(self, filas, previas):
        super().__init__()
        self.title("Recomendador")
        self.geometry("760x780")
        self.minsize(600, 500)
        self.configure(bg=BG)
        self.previas = previas
        self.decisiones = {}
        self.tarjetas = {}
        self.protocol("WM_DELETE_WINDOW", self.guardar_y_salir)

        cabecera = tk.Frame(self, bg=BG, padx=24, pady=18)
        cabecera.pack(fill="x")
        tk.Label(cabecera, text="Tus recomendaciones", bg=BG, fg=TEXTO,
                 font=(FUENTE, 22, "bold")).pack(anchor="w")
        tk.Label(cabecera, text="Descarta con ✕ los que no te interesen. El resto entra en la playlist",
                 bg=BG, fg=GRIS, font=(FUENTE, 10)).pack(anchor="w")

        pie = tk.Frame(self, bg="#000000", padx=24, pady=14)
        pie.pack(side="bottom", fill="x")
        self.contador = tk.Label(pie, bg="#000000", fg=GRIS, font=(FUENTE, 10))
        self.contador.pack(side="left")
        boton(pie, "Guardar y salir", self.guardar_y_salir,
              bg=VERDE, hover="#1ED760", fg="#000000").pack(side="right")

        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0, yscrollincrement=30)
        self.canvas.pack(fill="both", expand=True)
        self.interior = tk.Frame(self.canvas, bg=BG)
        ventana = self.canvas.create_window((0, 0), window=self.interior, anchor="nw")
        self.interior.bind("<Configure>",
                           lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(ventana, width=e.width))
        self.bind_all("<MouseWheel>",
                      lambda e: self.canvas.yview_scroll(-2 if e.delta > 0 else 2, "units"))

        for _, fila in filas.iterrows():
            self.crear_tarjeta(fila)
        self.actualizar_contador()

    def crear_tarjeta(self, f):
        artista = f["artista"]
        tarjeta = tk.Frame(self.interior, bg=CARD, padx=16, pady=12)
        tarjeta.pack(fill="x", padx=20, pady=4)

        texto = tk.Frame(tarjeta, bg=CARD)
        texto.pack(side="left", fill="x", expand=True)
        nombre = tk.Label(texto, text=artista, bg=CARD, fg=TEXTO,
                          font=(FUENTE, 13, "bold"), anchor="w")
        nombre.pack(fill="x")

        detalle = f"Afinidad {f['score']:.2f}"
        tags = f.get("tags")
        if isinstance(tags, str) and tags:
            detalle += "  ·  " + tags
        sub = tk.Label(texto, text=detalle, bg=CARD, fg=GRIS, font=(FUENTE, 9), anchor="w")
        sub.pack(fill="x")

        acciones = tk.Frame(tarjeta, bg=CARD)
        acciones.pack(side="right")
        boton(acciones, "Escuchar",
              lambda a=artista: webbrowser.open("https://open.spotify.com/search/" + quote(a))
              ).pack(side="left", padx=4)
        boton(acciones, "✕", lambda a=artista: self.decidir(a, "no"),
              hover="#5A2A2E").pack(side="left", padx=4)

        self.tarjetas[artista] = [tarjeta, texto, nombre, sub, acciones]

    def decidir(self, artista, decision):
        if self.decisiones.get(artista) == decision:
            del self.decisiones[artista]
            color = CARD
        else:
            self.decisiones[artista] = decision
            color = TINTE_SI if decision == "si" else TINTE_NO
        for w in self.tarjetas[artista]:
            w.config(bg=color)
        self.actualizar_contador()

    def actualizar_contador(self):
        descartados = sum(1 for d in self.decisiones.values() if d == "no")
        entran = len(self.tarjetas) - descartados
        self.contador.config(text=f"{descartados} descartados  ·  {entran} entrarán en la playlist")

    def guardar_y_salir(self):
        total = {**self.previas, **self.decisiones}
        pd.DataFrame({"artista": list(total), "decision": list(total.values())}
                     ).to_csv(RUTA_FEEDBACK, index=False)
        self.destroy()


if __name__ == "__main__":
    recs = pd.read_csv(RUTA_RECS)
    previas = cargar_feedback()
    pendientes = recs[~recs["artista"].isin(previas)].head(N_MOSTRAR)
    if pendientes.empty:
        print("No hay artistas nuevos por revisar.")
    else:
        App(pendientes, previas).mainloop()