import json
import os
import sys
import tkinter as tk

RUTA = "data/filtro.json"
GENEROS = ["rock", "pop", "rap", "trap", "hip hop", "reggaeton", "indie", "electronic",
           "rnb", "metal", "punk", "flamenco", "jazz", "latin", "folk", "reggae"]

BG = "#121212"
CHIP = "#2A2A2A"
VERDE = "#1DB954"
TEXTO = "#FFFFFF"
GRIS = "#B3B3B3"
FUENTE = "Segoe UI"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Recomendador")
        self.geometry("640x580")
        self.configure(bg=BG)
        self.sel = set()
        self.espanol = False
        self.chips = {}
        self.confirmado = False

        cab = tk.Frame(self, bg=BG, padx=28, pady=22)
        cab.pack(fill="x")
        tk.Label(cab, text="¿Qué te apetece escuchar?", bg=BG, fg=TEXTO,
                 font=(FUENTE, 22, "bold")).pack(anchor="w")
        tk.Label(cab, text="Elige uno o varios géneros. Si no eliges ninguno, usa todo tu gusto.",
                 bg=BG, fg=GRIS, font=(FUENTE, 10)).pack(anchor="w", pady=(2, 0))

        idioma = tk.Frame(self, bg=BG, padx=28)
        idioma.pack(fill="x", pady=(0, 14))
        self.chip_es = self.crear_chip(idioma, "Solo en español", self.alternar_es)
        self.chip_es.pack(anchor="w")

        rejilla = tk.Frame(self, bg=BG, padx=28)
        rejilla.pack(fill="x")
        for i, g in enumerate(GENEROS):
            c = self.crear_chip(rejilla, g.capitalize(), lambda g=g: self.alternar(g))
            c.grid(row=i // 4, column=i % 4, padx=5, pady=5, sticky="ew")
            self.chips[g] = c
        for col in range(4):
            rejilla.columnconfigure(col, weight=1)

        otro = tk.Frame(self, bg=BG, padx=28, pady=18)
        otro.pack(fill="x")
        tk.Label(otro, text="Otro género (separados por comas)", bg=BG, fg=GRIS,
                 font=(FUENTE, 10)).pack(anchor="w")
        self.entrada = tk.Entry(otro, bg=CHIP, fg=TEXTO, insertbackground=TEXTO,
                                relief="flat", font=(FUENTE, 12))
        self.entrada.pack(fill="x", ipady=7, pady=(4, 0))

        pie = tk.Frame(self, bg="#000000", padx=28, pady=16)
        pie.pack(side="bottom", fill="x")
        self.resumen_lbl = tk.Label(pie, bg="#000000", fg=GRIS, font=(FUENTE, 10))
        self.resumen_lbl.pack(side="left")
        cont = tk.Label(pie, text="Continuar", bg=VERDE, fg="#000000",
                        font=(FUENTE, 11, "bold"), padx=18, pady=8, cursor="hand2")
        cont.bind("<Button-1>", lambda e: self.continuar())
        cont.pack(side="right")
        libre = tk.Label(pie, text="Sin filtro", bg=CHIP, fg=TEXTO,
                         font=(FUENTE, 11, "bold"), padx=18, pady=8, cursor="hand2")
        libre.bind("<Button-1>", lambda e: self.guardar([], False))
        libre.pack(side="right", padx=8)

        self.resumen()

    def crear_chip(self, padre, texto, comando):
        c = tk.Label(padre, text=texto, bg=CHIP, fg=TEXTO, font=(FUENTE, 11, "bold"),
                     padx=16, pady=8, cursor="hand2")
        c.bind("<Button-1>", lambda e: comando())
        return c

    def pintar(self, chip, activo):
        chip.config(bg=VERDE if activo else CHIP, fg="#000000" if activo else TEXTO)

    def alternar(self, g):
        self.sel.symmetric_difference_update({g})
        self.pintar(self.chips[g], g in self.sel)
        self.resumen()

    def alternar_es(self):
        self.espanol = not self.espanol
        self.pintar(self.chip_es, self.espanol)
        self.resumen()

    def resumen(self):
        partes = sorted(self.sel) + (["español"] if self.espanol else [])
        self.resumen_lbl.config(
            text="Filtro: " + " + ".join(partes) if partes else "Sin filtro: todo tu gusto")

    def continuar(self):
        extra = [t.strip().lower() for t in self.entrada.get().split(",") if t.strip()]
        self.guardar(sorted(self.sel) + extra, self.espanol)

    def guardar(self, generos, espanol):
        os.makedirs("data", exist_ok=True)
        with open(RUTA, "w", encoding="utf-8") as f:
            json.dump({"generos": generos, "espanol": espanol}, f, ensure_ascii=False)
        self.confirmado = True
        self.destroy()


if __name__ == "__main__":
    app = App()
    app.mainloop()
    if not app.confirmado:
        sys.exit(1)