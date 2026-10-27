import argparse
import subprocess
import sys
import time

PASOS = {
    "descargar": "descargar_datos.py",
    "enriquecer": "enriquecer_lastfm.py",
    "recomendar": "recomendar.py",
    "revisar": "revisar_artistas.py",
    "playlist": "crear_playlist.py",
}


def ejecutar(nombre, script):
    print(f"\n{'=' * 50}\n{nombre.upper()}  ({script})\n{'=' * 50}")
    inicio = time.time()
    resultado = subprocess.run([sys.executable, script])
    if resultado.returncode != 0:
        print(f"\nEl paso '{nombre}' ha fallado. Pipeline detenido.")
        sys.exit(resultado.returncode)
    print(f"\n{nombre} terminado en {time.time() - inicio:.0f}s")


parser = argparse.ArgumentParser(description="Recomendador de Spotify")
parser.add_argument("--saltar", nargs="+", choices=PASOS, default=[],
                    help="pasos a omitir")
parser.add_argument("--solo", nargs="+", choices=PASOS,
                    help="ejecutar solo estos pasos")
args = parser.parse_args()

pasos = args.solo if args.solo else [p for p in PASOS if p not in args.saltar]
pasos = [p for p in PASOS if p in pasos]

for paso in pasos:
    ejecutar(paso, PASOS[paso])

print("\nTodo listo.")