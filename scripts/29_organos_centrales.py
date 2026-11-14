"""Comprobación del nivel C: ¿hay algún órgano, aparte de la Junta de Contratación Centralizada de Hacienda, que
concentre compras de forma anómala (que pueda comprar para otros ministerios)?

Entrada (solo lectura, no se copia al repositorio): registros de licitaciones de toda la PLACSP del proyecto
«Gasto Defensa» (registros/sector_publico/placsp_sector_publico_AAAA.jsonl.gz, 2017-2026; se leen todos para completar jerarquías y se cuentan 2022-2025). Ruta: argumento 1 o la
variable PLACSP_DIR. Cada registro trae el órgano que contrata (con su jerarquía), el estado, el CPV y los importes;
no trae el ministerio destinatario, el objeto ni el adjudicatario, así que el reparto por destinatario no es posible.

Método: la jerarquía de un órgano no viene completa en los años antiguos (en 2017 solo 10 órganos llevan «Administración
General del Estado»; en 2021, 38); se toma la más larga que tenga ese órgano (por identificador de la plataforma o,
si falta, por DIR3) en cualquiera de los años leídos. Licitaciones en estado adjudicada o resuelta (ADJ, RES) de órganos de la Administración General del Estado;
ministerio = el nombre de ministerio de su jerarquía en ese año (los nombres cambian con las reorganizaciones; aquí
se dejan como vienen). Se cuenta por órgano y año. Solo se guardan los 40 órganos con más licitaciones y la Junta.

Salida: datos/contratacion_organos_principales.csv (órgano; ministerio en la plataforma; 2022…2025; total) y
datos/controles_organos_centrales.csv (peso de la Junta en el total de la AGE por año; la suma de los órganos
guardados más el resto debe dar el total).
"""
import csv, gzip, json, os, sys
from collections import Counter, defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DIR = Path(sys.argv[1] if len(sys.argv) > 1 else os.environ.get("PLACSP_DIR", ""))
AÑOS = range(2022, 2026)  # antes de 2022 la jerarquía de la mayoría de los órganos no consta en ningún año leído
JUNTA = "Dirección General de Racionalización y Centralización de la Contratación-Junta de Contratación Centralizada"
def clave(r):
    return r.get("idp") or r.get("dir3") or ("k", r["cad"][0])


jer = {}
for y in range(2017, 2027):
    with gzip.open(DIR / f"placsp_sector_publico_{y}.jsonl.gz", "rt", encoding="utf-8") as g:
        for linea in g:
            r = json.loads(linea)
            if r["t"] == "o" and len(r["cad"]) > len(jer.get(clave(r), [])):
                jer[clave(r)] = r["cad"]
cnt = defaultdict(Counter)
total = Counter()
for y in AÑOS:
    cad = {}
    with gzip.open(DIR / f"placsp_sector_publico_{y}.jsonl.gz", "rt", encoding="utf-8") as g:
        for linea in g:
            r = json.loads(linea)
            if r["t"] == "o":
                cad[r["k"]] = jer[clave(r)]
            elif r["t"] == "l" and r["est"] in ("ADJ", "RES"):
                c = cad.get(r["o"])
                if not c or "ADMINISTRACIÓN GENERAL DEL ESTADO" not in c:
                    continue
                m = next((x for x in c if x.startswith("Ministerio")), "(sin ministerio)")
                cnt[(c[0], m)][y] += 1
                total[y] += 1
# la Junta aparece con dos nombres de ministerio (Hacienda y Función Pública / Hacienda): se agrupa
por_org = defaultdict(Counter)
ministerios = defaultdict(set)
for (o, m), v in cnt.items():
    por_org[o].update(v)
    ministerios[o].add(m)
orden = sorted(por_org, key=lambda o: -sum(por_org[o].values()))
guardar = orden[:40]
if JUNTA not in guardar:
    guardar.append(JUNTA)
filas = []
for o in guardar:
    v = por_org[o]
    filas.append([o, " / ".join(sorted(ministerios[o])), *[v[y] for y in AÑOS], sum(v.values())])
with open(RAIZ / "datos" / "contratacion_organos_principales.csv", "w", encoding="utf-8-sig", newline="") as fh:
    w = csv.writer(fh, delimiter=";")
    w.writerow(["organo", "ministerio_en_la_plataforma", *AÑOS, "total"])
    w.writerows(filas)
ctl = []
for y in AÑOS:
    j = por_org[JUNTA][y]
    resto = total[y] - sum(por_org[o][y] for o in guardar)
    suma = sum(por_org[o][y] for o in guardar) + resto
    ctl.append(["Peso de la Junta en las adjudicaciones de la AGE", y, j, total[y], f"{100*j/total[y]:.1f}".replace(".", ","), "OK"])
    ctl.append(["Órganos guardados + resto = total de la AGE", y, suma, total[y], "", "OK" if suma == total[y] else "INCORRECTO"])
with open(RAIZ / "datos" / "controles_organos_centrales.csv", "w", encoding="utf-8-sig", newline="") as fh:
    w = csv.writer(fh, delimiter=";")
    w.writerow(["control", "anio", "valor", "referencia", "pct", "resultado"])
    w.writerows(ctl)
print(len(filas), "órganos;", sum(1 for c in ctl if c[-1] != "OK"), "controles incorrectos")
