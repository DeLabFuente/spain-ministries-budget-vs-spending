"""Lector de la Liquidación del Presupuesto de organismos (IGAE, vol. II), versión Excel.

Entrada: fuentes/igae/organismos_excel/AAAA/*.xlsx (descomprimidos de «Liquidación. Ejercicio AAAA (Excel).zip»
  y renombrados organismos_autonomos.xlsx, agencias_estatales.xlsx, otras_entidades.xlsx):
  organismos autónomos, agencias estatales (solo 2017; después van en «otras entidades») y otras entidades.
Salidas (separador ';', decimales con coma, UTF-8, importes en euros; la IGAE publica en miles):
  datos/organismos_gastos.csv    organismo × capítulo (0 = total): créditos iniciales (2023-), definitivos,
                                 obligaciones reconocidas y pagos
  datos/organismos_ingresos.csv  organismo × capítulo (0 = total): previsiones, derechos reconocidos, recaudación
  datos/controles_organismos.csv cuadres: suma de organismos = total del departamento; suma de capítulos = total
Dos formatos:
  2017-2022  hojas «PTO GASTOS ORGANISMOS», «PTO GASTOS OR ORGANISMOS» (obligaciones por capítulo),
             «PTO GASTOS PAGOS ORGAN…», «PTO INGRESOS ORGANISMOS», «PTO INGRESOS DR ORGANISMOS» (derechos por
             capítulo), «PTO INGRESOS COBRO(S) ORGAN…». Créditos definitivos solo en total; no hay iniciales.
  2023-      hojas «Gastos por organismos/entidades», «Modif por …» (iniciales), «Ing por …» y una hoja por
             capítulo («Gastos cap N», «Ing cap N») con definitivos/obligaciones/pagos o previsiones/derechos/
             recaudación de cada organismo.
"""
import csv
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

import openpyxl

RAIZ = Path(__file__).resolve().parent.parent
EXCEL = RAIZ / "fuentes" / "igae" / "organismos_excel"
DATOS = RAIZ / "datos"


def num(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().strip("'")
    if s in ("", "-"):
        return 0.0 if s == "-" else None
    s = s.replace(".", "").replace(",", ".") if re.fullmatch(r"-?[\d.]+(,\d+)?", s) else s
    try:
        return float(s)
    except ValueError:
        return None


def txt(v):
    return "" if v is None else str(v).strip("'").replace("\xa0", " ")


def tipo_de(fichero):
    """Los xlsx se guardan renombrados: organismos_autonomos, agencias_estatales (solo 2017), otras_entidades."""
    n = unicodedata.normalize("NFC", fichero.name.replace("#U00f3", "ó")).lower()
    if "agencias" in n:
        return "Agencia estatal"
    if "otras" in n:
        return "Otras entidades"
    if "organismos" in n:
        return "Organismo autónomo"
    return None


def hoja(wb, *prefijos):
    for p in prefijos:
        for s in wb.sheetnames:
            if s.strip().upper() == p.upper():
                return wb[s]
    for p in prefijos:
        for s in wb.sheetnames:
            if s.strip().upper().startswith(p.upper()):
                return wb[s]
    return None


def filas_antiguas(ws):
    """Formato 2017-2022: devuelve (cabecera_capitulos, lista de (departamento, organismo|None(total), valores))."""
    filas = list(ws.iter_rows(values_only=True))
    cab = None
    for r in filas[:20]:
        if any(re.match(r"(?i)cap[ií]tulo\s*\d", txt(c)) for c in r):
            cab = [(i, int(re.search(r"\d", txt(c)).group())) for i, c in enumerate(r)
                   if re.match(r"(?i)cap[ií]tulo\s*\d", txt(c))]
            break
    out, depto, ni = [], None, None
    for r in filas:
        cel = [txt(c) for c in r]
        nombre_i = next((i for i, c in enumerate(cel[:4]) if c.strip()), None)
        if nombre_i is None:
            continue
        nombre = " ".join(cel[nombre_i].split())
        if re.match(r"(?i)^(M[º°o]\.?|MINISTERIO|TOTAL)\s", nombre):
            ni = nombre_i
        vals = [num(c) for c in r[nombre_i + 1:]]
        hay = any(v is not None for v in vals)
        if re.match(r"(?i)^(M[º°o]\.?|MINISTERIO)\s", nombre) and not hay:
            depto = nombre
            continue
        if not hay or depto is None:
            continue
        if nombre.upper().startswith("TOTAL GENERAL"):
            out.append(("TOTAL GENERAL", None, r[nombre_i + 1:]))
            continue
        if nombre.upper().startswith("TOTAL"):
            out.append((depto, None, r[nombre_i + 1:]))
            continue
        out.append((depto, nombre, r[nombre_i + 1:]))
    return cab, out, ni


def filas_nuevas(ws):
    """Formato 2023-: el departamento va sin sangría (con su total) y los organismos con tabulador."""
    out, depto = [], None
    for r in ws.iter_rows(values_only=True):
        if r[0] is None:
            continue
        crudo = str(r[0])
        nombre = " ".join(crudo.split())
        vals = list(r[1:])
        if not any(num(v) is not None for v in vals):
            continue
        if crudo.startswith("\t") or crudo.startswith(" "):
            out.append((depto, nombre, vals))
        elif nombre.upper().startswith("TOTAL"):
            out.append(("TOTAL GENERAL", None, vals))
        else:
            depto = nombre
            out.append((depto, None, vals))
    return out


def leer_anio(anio):
    gastos, ingresos = [], []
    for f in sorted((EXCEL / str(anio)).glob("*.xlsx")):
        tipo = tipo_de(f)
        if not tipo:
            continue
        wb = openpyxl.load_workbook(f, read_only=True, data_only=True)
        fuente = f"IGAE, Liquidación del Presupuesto {anio}, organismos (Excel): {tipo.lower()} (miles de euros)"
        if hoja(wb, "PTO GASTOS ORGANISMOS"):                       # formato 2017-2022
            G = defaultdict(dict)
            I = defaultdict(dict)
            _, filas, _ = filas_antiguas(hoja(wb, "PTO GASTOS ORGANISMOS"))
            for d, o, v in filas:      # def, obl, %, pagos
                vv = [num(x) for x in v if num(x) is not None]
                G[(d, o, 0)].update(creditos_definitivos=vv[0], obligaciones=vv[1], pagos=vv[3])
            for nombre_hoja, campo, destino in (("PTO GASTOS OR ORGANISMOS", "obligaciones", G),
                                                ("PTO GASTOS PAGOS ORGAN", "pagos", G),
                                                ("PTO INGRESOS DR ORGANISMOS", "derechos_reconocidos", I),
                                                ("PTO INGRESOS COBRO", "recaudacion", I)):
                ws = hoja(wb, nombre_hoja)
                cab, filas, ni = filas_antiguas(ws)
                for d, o, v in filas:
                    for col, cap in cab:
                        x = num(v[col - ni - 1]) if col - ni - 1 < len(v) else None
                        destino[(d, o, cap)][campo] = x or 0.0
            _, filas, _ = filas_antiguas(hoja(wb, "PTO INGRESOS ORGANISMOS"))
            for d, o, v in filas:      # previsiones, derechos, %, recaudación
                vv = [num(x) for x in v if num(x) is not None]
                I[(d, o, 0)].update(previsiones=vv[0], derechos_reconocidos=vv[1], recaudacion=vv[3])
        else:                                                          # formato 2023-
            G = defaultdict(dict)
            I = defaultdict(dict)
            for d, o, v in filas_nuevas(hoja(wb, "Gastos por organismos", "Gastos por entidades")):
                G[(d, o, 0)].update(creditos_definitivos=num(v[0]) or 0.0, obligaciones=num(v[1]) or 0.0,
                                    pagos=num(v[3]) or 0.0)
            for d, o, v in filas_nuevas(hoja(wb, "Modif por organismos", "Modif por entidades")):
                G[(d, o, 0)]["creditos_iniciales"] = num(v[0]) or 0.0
            for d, o, v in filas_nuevas(hoja(wb, "Ing por organismos", "Ing por entidades")):
                I[(d, o, 0)].update(previsiones=num(v[0]) or 0.0, derechos_reconocidos=num(v[1]) or 0.0,
                                    recaudacion=num(v[2]) or 0.0)
            for s in wb.sheetnames:
                m = re.match(r"(?i)^(Gastos|Ing)\s*cap\s*(\d)$", s.strip())
                if not m:
                    continue
                cap = int(m.group(2))
                for d, o, v in filas_nuevas(wb[s]):
                    if m.group(1).lower() == "gastos":
                        G[(d, o, cap)].update(creditos_definitivos=num(v[0]) or 0.0, obligaciones=num(v[1]) or 0.0,
                                              pagos=num(v[3]) or 0.0)
                    else:
                        I[(d, o, cap)].update(previsiones=num(v[0]) or 0.0, derechos_reconocidos=num(v[1]) or 0.0,
                                              recaudacion=num(v[2]) or 0.0)
        for (d, o, cap), x in G.items():
            gastos.append(dict(anio=anio, tipo_entidad=tipo, departamento=d, organismo=o or "", capitulo=cap,
                               fuente=fuente, **{k: v * 1000 for k, v in x.items()}))
        for (d, o, cap), x in I.items():
            ingresos.append(dict(anio=anio, tipo_entidad=tipo, departamento=d, organismo=o or "", capitulo=cap,
                                 fuente=fuente, **{k: v * 1000 for k, v in x.items()}))
    return gastos, ingresos


def controles(filas, campos, anio):
    out = []
    orgs = [r for r in filas if r["organismo"]]
    tot = {(r["tipo_entidad"], r["departamento"], r["capitulo"]): r for r in filas
           if not r["organismo"] and r["departamento"] != "TOTAL GENERAL"}
    gen = {(r["tipo_entidad"], r["capitulo"]): r for r in filas if r["departamento"] == "TOTAL GENERAL"}
    for (t, d, cap), r in tot.items():
        for k in campos:
            if k not in r:
                continue
            s = sum(x.get(k, 0) for x in orgs if x["tipo_entidad"] == t and x["departamento"] == d
                    and x["capitulo"] == cap)
            out.append(dict(anio=anio, control=f"organismos = total del departamento ({k}, cap. {cap})",
                            ambito=f"{t} · {d}", valor_a=s, valor_b=r[k], ok="sí" if abs(s - r[k]) <= 3000 else "NO"))
    for (t, cap), r in gen.items():
        for k in campos:
            if k not in r:
                continue
            s = sum(x.get(k, 0) for x in tot.values() if x["tipo_entidad"] == t and x["capitulo"] == cap)
            out.append(dict(anio=anio, control=f"departamentos = total general ({k}, cap. {cap})", ambito=t,
                            valor_a=s, valor_b=r[k], ok="sí" if abs(s - r[k]) <= 10000 else "NO"))
    # capítulos = total, por organismo
    porg = defaultdict(dict)
    for r in orgs:
        porg[(r["tipo_entidad"], r["departamento"], r["organismo"])][r["capitulo"]] = r
    for (t, d, o), caps in porg.items():
        if 0 not in caps:
            continue
        for k in campos:
            if k not in caps[0] or not any(k in caps[c] for c in caps if c):
                continue
            s = sum(caps[c].get(k, 0) for c in caps if c)
            out.append(dict(anio=anio, control=f"capítulos = total del organismo ({k})", ambito=f"{t} · {o}",
                            valor_a=s, valor_b=caps[0][k], ok="sí" if abs(s - caps[0][k]) <= 3000 else "NO"))
    return out


def escribir(nombre, filas, campos):
    def fmt(x):
        if x is None:
            return ""
        if isinstance(x, float):
            return str(int(round(x))) if x.is_integer() else f"{x:.2f}".replace(".", ",")
        return x
    with open(DATOS / nombre, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(campos)
        for r in filas:
            w.writerow([fmt(r.get(k)) for k in campos])


def main():
    anios = [int(a) for a in sys.argv[1:]] or sorted(int(p.name) for p in EXCEL.iterdir() if p.is_dir())
    G, I, C = [], [], []
    for a in anios:
        g, i = leer_anio(a)
        c = controles(g, ["creditos_iniciales", "creditos_definitivos", "obligaciones", "pagos"], a) + \
            controles(i, ["previsiones", "derechos_reconocidos", "recaudacion"], a)
        G += g; I += i; C += c
        malos = [x for x in c if x["ok"] == "NO"]
        n_org = len({(r["tipo_entidad"], r["organismo"]) for r in g if r["organismo"]})
        print(f"{a}: {n_org} organismos, {len(g)} filas de gasto, {len(i)} de ingreso, {len(c)} controles, "
              f"{len(malos)} fallidos")
        for m in malos[:8]:
            print("   ", m)
    escribir("organismos_gastos.csv", G, ["anio", "tipo_entidad", "departamento", "organismo", "capitulo",
             "creditos_iniciales", "creditos_definitivos", "obligaciones", "pagos", "fuente"])
    escribir("organismos_ingresos.csv", I, ["anio", "tipo_entidad", "departamento", "organismo", "capitulo",
             "previsiones", "derechos_reconocidos", "recaudacion", "fuente"])
    escribir("controles_organismos.csv", C, ["anio", "control", "ambito", "valor_a", "valor_b", "ok"])


if __name__ == "__main__":
    main()
