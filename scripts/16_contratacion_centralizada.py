"""Contratación centralizada en la serie de Hacienda (REGISTRO A21; ficha de Hacienda).

Desde 2021 la Dirección General de Racionalización y Centralización de la Contratación (DGRCC, Junta de
Contratación Centralizada, DIR3 E04962703), que es un órgano de Hacienda, publica en la PLACSP los contratos
basados en acuerdos marco y, desde 2022, los basados en sistemas dinámicos de adquisición. Son compras para toda
la Administración General del Estado, y en la línea base cuentan en Hacienda (ministerio actual del órgano, B12).

Este script cuenta esas adjudicaciones en los registros de la PLACSP del proyecto de Defensa (solo lectura) y
compara la cuota de noviembre-diciembre de Hacienda con la del resto de la AGE antes y después de 2021.

Reglas aproximadas a las de la línea base (recuento propio, no idéntico a ella):
- licitaciones (sindicación 643) con resultado adjudicado o formalizado (códigos 8 y 9), por fecha de adjudicación;
- fuera el establecimiento de acuerdos marco y de sistemas dinámicos (sistema 1 y 2);
- importe de adjudicación con IVA; las licitaciones de 100 M€ o más en un año se separan como «especial».

Entradas:
  ../GASTO DEFENSA/registros/sector_publico/placsp_sector_publico_AAAA.jsonl.gz  (o la carpeta del argumento 1)
  fuentes/contratacion/linea_base_cierre.csv
Salida: datos/contratacion_centralizada_hacienda.csv
Uso: python scripts/16_contratacion_centralizada.py ["ruta a registros/sector_publico"]
"""
import csv
import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
REG = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ.parent / "GASTO DEFENSA" / "registros" / "sector_publico"
LINEA_BASE = RAIZ / "fuentes" / "contratacion" / "linea_base_cierre.csv"
SALIDA = RAIZ / "datos" / "contratacion_centralizada_hacienda.csv"
DGRCC = "E04962703"
SISTEMA = {"3": "basado en acuerdo marco", "4": "basado en sistema dinámico"}
ANIOS = range(2017, 2026)


def f(x):
    return float(x.replace(",", ".")) if x not in ("", None) else 0.0


def num(x, dec=1):
    return f"{x:.{dec}f}".replace(".", ",")


def dgrcc():
    """(año, sistema) -> [n, importe, n nov-dic, importe nov-dic, importe especial]"""
    agg = defaultdict(lambda: [0, 0.0, 0, 0.0, 0.0])
    for anio in ANIOS:
        ks = set()
        with gzip.open(REG / f"placsp_sector_publico_{anio}.jsonl.gz", "rt", encoding="utf-8") as fh:
            for ln in fh:
                r = json.loads(ln)
                if r["t"] == "o":
                    if r.get("dir3") == DGRCC or "Racionalización y Centralización" in r["cad"][0]:
                        ks.add(r["k"])
                elif r["t"] == "l" and r["o"] in ks and r.get("sist") not in ("1", "2"):
                    res = [x for x in r.get("res", []) if x[0] in ("8", "9") and x[1]]
                    especial = sum(x[3] or 0 for x in res) >= 100e6
                    for x in res:
                        y = int(x[1][:4])
                        if y not in ANIOS:
                            continue
                        a = agg[(y, SISTEMA.get(r.get("sist"), "otros"))]
                        if especial:
                            a[4] += x[3] or 0
                            continue
                        a[0] += 1
                        a[1] += x[3] or 0
                        if x[1][5:7] in ("11", "12"):
                            a[2] += 1
                            a[3] += x[3] or 0
    return agg


def linea_base():
    """(grupo H/R, año) -> [importe ordinario, importe ordinario nov-dic]; licitaciones de la AGE."""
    t = defaultdict(lambda: [0.0, 0.0])
    with open(LINEA_BASE, encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh, delimiter=";"):
            if r["bloque"] not in ("Defensa", "Resto de la AGE") or r["es_contrato_menor"] != "No":
                continue
            y = int(r["anio"])
            if y not in ANIOS:
                continue
            g = "H" if r["grupo"] == "Ministerio de Hacienda" else "R"
            t[(g, y)][0] += f(r["importe_ordinario_eur"])
            if r["mes"] in ("11", "12"):
                t[(g, y)][1] += f(r["importe_ordinario_eur"])
    return t


def main():
    dg, lb = dgrcc(), linea_base()
    filas = []
    for y in ANIOS:
        for s in ("basado en acuerdo marco", "basado en sistema dinámico", "otros"):
            a = dg.get((y, s))
            if a and (a[0] or a[4]):
                filas.append({"periodo": str(y), "serie": f"DGRCC: {s}", "adjudicaciones": a[0],
                              "importe_con_iva": round(a[1], 2), "importe_nov_dic": round(a[3], 2),
                              "pct_nov_dic": num(100 * a[3] / a[1]) if a[1] else "",
                              "importe_especial_100M": round(a[4], 2), "fuente": "PLACSP, registros del proyecto de Defensa (recuento propio)"})
    for nombre, ys in (("2017-2020", range(2017, 2021)), ("2021-2025", range(2021, 2026)), ("2017-2025", ANIOS)):
        for g, serie in (("H", "Hacienda (línea base)"), ("R", "AGE sin Hacienda (línea base)")):
            o = sum(lb[(g, y)][0] for y in ys)
            n = sum(lb[(g, y)][1] for y in ys)
            filas.append({"periodo": nombre, "serie": serie, "adjudicaciones": "", "importe_con_iva": round(o, 2),
                          "importe_nov_dic": round(n, 2), "pct_nov_dic": num(100 * n / o), "importe_especial_100M": "",
                          "fuente": "fuentes/contratacion/linea_base_cierre.csv (importe ordinario de licitaciones)"})
    with open(SALIDA, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0]), delimiter=";")
        w.writeheader()
        for r in filas:
            w.writerow({k: (str(v).replace(".", ",") if isinstance(v, float) else v) for k, v in r.items()})
    for r in filas:
        print(r["periodo"], r["serie"], r["adjudicaciones"], r["pct_nov_dic"])
    print("escrito", SALIDA)


if __name__ == "__main__":
    main()
