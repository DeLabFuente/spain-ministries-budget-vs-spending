"""Mecanismo de Recuperación y Resiliencia (MRR) por sección, programa y capítulo, 2021-2025.

- 2021-2024: liquidación del Estado, anexos I y II. En cada sección el MRR es un servicio propio, el «SS50»
  (p. ej., 1750 = Transportes), así que se suman las aplicaciones de ese servicio (intermedio privado
  fuentes/igae/_intermedios/liquidacion_aplicaciones.csv, que genera el script 01). La liquidación no da pagos
  por aplicación.
- 2025: estadística mensual de diciembre (provisional), capítulo «Mecanismo de Recuperación y Resiliencia»:
  tabla por secciones (pie MRR00), por capítulos (MRR01) y detalle por sección, programa y concepto (pie MRRSS),
  en miles de euros. Del detalle solo se guarda el agregado por programa y capítulo: los conceptos nombran
  a entidades beneficiarias.

El MRR ya está dentro de las cifras de cada sección (liquidacion_secciones.csv, mensual_secciones.csv); aquí se
separa para ver cuánto del gasto de cada ministerio sale de él. Lo que el MRR transfiere a organismos o a otras
administraciones cuenta como obligación de la sección cuando se transfiere.

Salidas (datos/):
  mrr_secciones.csv          año × sección: iniciales, modificaciones, definitivos, obligaciones, pagos (2025)
                             y peso en las obligaciones de la sección, con su ministerio actual
  mrr_programa_capitulo.csv  año × sección × programa × capítulo: iniciales, definitivos, obligaciones, pagos (2025)
  controles_mrr.csv          cuadres (2025: detalle = tabla por secciones = tabla por capítulos; 2024 → 2025: iniciales
                             prorrogados)
"""
import csv
import re
import subprocess
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datos"
APLIC = RAIZ / "fuentes" / "igae" / "_intermedios" / "liquidacion_aplicaciones.csv"
MENSUAL_PDF = RAIZ / "fuentes" / "igae" / "mensual" / "mensual_12-25.pdf"
MENSUAL_TXT = RAIZ / "fuentes" / "igae" / "_texto" / "mensual_12-25.txt"
ANIO_MENSUAL = 2025
TOL = 1000  # la fuente redondea cada cifra a miles de euros (y el «ajustado» es una resta de cifras redondeadas)


def f(x):
    return float(x.replace(",", ".")) if x not in ("", None) else 0.0


def fmt(x):
    if x is None:
        return ""
    if isinstance(x, float):
        x = round(x, 2)
        return str(int(x)) if x.is_integer() else f"{x:.2f}".rstrip("0").replace(".", ",")
    return x


def num(s):
    """Importe de la mensual: '1.234.567' / '-6.287' / '-' → euros (la fuente está en miles)."""
    s = s.strip()
    if s in ("-", ""):
        return 0.0
    return float(s.replace(".", "").replace(",", ".")) * 1000


def leer_csv(p):
    with open(p, encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter=";"))


def paginas():
    if not MENSUAL_TXT.exists():
        MENSUAL_TXT.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["pdftotext", "-layout", str(MENSUAL_PDF), str(MENSUAL_TXT)], check=True)
    return MENSUAL_TXT.read_text(encoding="utf-8").split("\f")


RX_PIE = re.compile(r"^\s*MRR(\d\d)\s+25\s*$", re.M)
CIFRA = r"(-?[\d.]+|-)"
RX_FILA = re.compile(r"^\s*(?P<cod>[0-9]{2,3}[0-9A-ZÑÇ]{1,3}|000X)\s*-\s*(?P<desc>.*?)\s{2,}"
                     + r"\s+".join([CIFRA] * 8) + r"\s+(?P<pct>-?[\d.,]+|-)\s*$")
RX_SOLO_CODIGO = re.compile(r"^\s*(?P<cod>[0-9]{2,3}[0-9A-ZÑÇ]{1,3}|000X)\s*-\s*(?P<desc>\D.*?)\s*$")
RX_TOTAL = re.compile(r"^\s*" + r"\s+".join([CIFRA] * 8) + r"\s+(-?[\d.,]+|-)\s*$")
RX_NOMBRE = re.compile(r"^\s{0,4}(?P<n>[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ.,ºª /\d-]+?)\s{2,}" + r"\s+".join([CIFRA] * 8) + r"\s+(-?[\d.,]+|-)\s*$")
COLS = ["creditos_iniciales", "adaptacion_prorroga", "modificaciones", "creditos_definitivos", "autorizaciones",
        "compromisos", "obligaciones", "pagos"]


def mensual_mrr(pags):
    """Devuelve (por_seccion de la tabla MRR00, por_capitulo de MRR01, detalle {(sec, prog, cap): sumas},
    totales de cada sección según su página, nombres de programa, páginas por sección)."""
    tabla_sec, tabla_cap, detalle, total_det = {}, {}, defaultdict(lambda: defaultdict(float)), defaultdict(lambda: defaultdict(float))
    nombres, pags_sec = {}, defaultdict(list)
    liq = {r["seccion_abreviada"]: r["codigo_seccion"] for r in leer_csv(DATOS / "mensual_secciones.csv")}
    prog, sec_ant = None, None
    for i, p in enumerate(pags):
        m = RX_PIE.search(p)
        if not m or "RECUPERACI" not in p[:2000]:
            continue
        sec = m.group(1)
        pags_sec[sec].append(i + 1)
        if sec == "00":
            for ln in p.splitlines():
                mm = RX_NOMBRE.match(ln)
                if mm and mm.group("n").strip() in liq:
                    vals = [num(mm.group(k)) for k in range(2, 10)]
                    tabla_sec[liq[mm.group("n").strip()]] = dict(zip(COLS, vals))
            continue
        if sec == "01":
            for ln in p.splitlines():
                mm = re.match(r"^\s*(\d)\.\s+.*?\s{2,}" + r"\s+".join([CIFRA] * 8) + r"\s+(-?[\d.,]+|-)\s*$", ln)
                if mm:
                    tabla_cap[mm.group(1)] = dict(zip(COLS, [num(mm.group(k)) for k in range(2, 10)]))
            continue
        if sec != sec_ant:  # el programa sigue de una página a la siguiente de la misma sección
            prog, sec_ant = None, sec
        pendiente = None   # fila partida: «código-descripción» en una línea y las cifras en la siguiente
        prog_partido = False  # el nombre de un programa partido sigue en la línea de después de las cifras
        for ln in p.splitlines():
            if not ln.strip():
                continue
            mm = RX_FILA.match(ln)
            if mm:
                cod, desc, vals = mm.group("cod"), mm.group("desc"), [num(mm.group(k)) for k in range(3, 11)]
            elif pendiente and (mt := RX_TOTAL.match(ln)):
                (cod, desc), vals = pendiente, [num(mt.group(k)) for k in range(1, 9)]
            else:
                if prog_partido and not re.search(r"\d", ln):
                    nombres[(sec, prog)] += " " + ln.strip()
                    prog_partido = False
                    continue
                ms = RX_SOLO_CODIGO.match(ln)
                pendiente = (ms.group("cod"), ms.group("desc")) if ms else None
                prog_partido = False
                continue
            partida = pendiente is not None
            pendiente, prog_partido = None, False
            vals = dict(zip(COLS, vals))
            if cod == "000X" or (re.match(r"^\d{2}[0-9A-ZÑÇ]{2}$", cod) and not cod.isdigit()):  # programa
                prog = cod
                nombres[(sec, prog)] = re.sub(r"\s+", " ", desc).strip()
                prog_partido = partida
                for k, v in vals.items():
                    total_det[(sec, prog)][k] += v
            else:  # concepto económico: solo se guarda su capítulo
                for k, v in vals.items():
                    detalle[(sec, prog, cod[0])][k] += v
    return tabla_sec, tabla_cap, detalle, total_det, nombres, pags_sec


def main():
    sma = leer_csv(DATOS / "secciones_ministerio_actual.csv")
    info = {(int(r["anio"]), r["codigo_seccion"]): r for r in sma}
    nombre_prog = {(int(r["anio"]), r["codigo_seccion"], r["programa"]): r["programa_nombre"]
                   for r in leer_csv(DATOS / "liquidacion_programa_capitulo.csv")}
    controles = []

    # 2021-2024: servicio SS50 de los anexos
    prog = defaultdict(lambda: defaultdict(float))
    for r in leer_csv(APLIC):
        a = int(r["anio"])
        if a < 2021 or r["servicio"][-2:] != "50" or r["servicio"][:2] != r["seccion"]:
            continue
        x = prog[(a, r["seccion"], r["programa"], r["capitulo"])]
        for k in ("creditos_iniciales", "creditos_definitivos", "obligaciones"):
            x[k] += f(r[k])
    filas_p = []
    for (a, s, p, c), x in sorted(prog.items()):
        filas_p.append(dict(anio=a, codigo_seccion=s, programa=p, programa_nombre=nombre_prog.get((a, s, p), ""), capitulo=c,
                            creditos_iniciales=x["creditos_iniciales"], creditos_definitivos=x["creditos_definitivos"],
                            obligaciones=x["obligaciones"], pagos=None,
                            fuente=f"IGAE, Liquidación {a} vol. I, anexos I y II, servicio {s}50 (euros)"))

    # 2025: mensual de diciembre
    pags = paginas()
    tabla_sec, tabla_cap, detalle, total_det, nombres, pags_sec = mensual_mrr(pags)
    fuente_m = "IGAE, Estadística mensual de ejecución, diciembre de 2025 (provisional), capítulo MRR, p. {} (miles de euros)"
    for (s, p, c), x in sorted(detalle.items()):
        filas_p.append(dict(anio=ANIO_MENSUAL, codigo_seccion=s, programa=p, programa_nombre=nombres.get((s, p), ""),
                            capitulo=c, creditos_iniciales=x["creditos_iniciales"],
                            creditos_definitivos=x["creditos_definitivos"], obligaciones=x["obligaciones"], pagos=x["pagos"],
                            fuente=fuente_m.format("-".join(str(n) for n in (min(pags_sec[s]), max(pags_sec[s])))
                                                   if len(pags_sec[s]) > 1 else pags_sec[s][0])))

    # Controles 2025
    def ctrl(nombre, a, b, filas_sumadas):
        ok = abs(a - b) <= TOL * max(2, filas_sumadas) + 0.01
        controles.append(dict(control=nombre, valor_a=a, valor_b=b, diferencia=a - b, correcto="sí" if ok else "NO"))

    for s, t in sorted(tabla_sec.items()):
        for k in ("creditos_iniciales", "modificaciones", "creditos_definitivos", "obligaciones", "pagos"):
            det = sum(x[k] for (ss, _, _), x in detalle.items() if ss == s)
            n = sum(1 for (ss, _, _) in detalle if ss == s)
            ctrl(f"2025 sección {s} {k}: conceptos = tabla por secciones", det, t[k], n)
            tp = sum(x[k] for (ss, _), x in total_det.items() if ss == s)
            ctrl(f"2025 sección {s} {k}: programas = tabla por secciones", tp, t[k], len([1 for (ss, _) in total_det if ss == s]))
    secs_det = {s for (s, _, _) in detalle}
    controles.append(dict(control="2025 secciones con detalle = secciones de la tabla", valor_a=len(secs_det),
                          valor_b=len(tabla_sec), diferencia=len(secs_det ^ set(tabla_sec)),
                          correcto="sí" if secs_det == set(tabla_sec) else "NO"))
    for c, t in sorted(tabla_cap.items()):
        for k in ("creditos_iniciales", "creditos_definitivos", "obligaciones", "pagos"):
            det = sum(x[k] for (_, _, cc), x in detalle.items() if cc == c)
            ctrl(f"2025 capítulo {c} {k}: conceptos = tabla por capítulos", det, t[k], sum(1 for (_, _, cc) in detalle if cc == c))
    ini24 = sum(r["creditos_iniciales"] for r in filas_p if r["anio"] == 2024)
    ini25 = sum(t["creditos_iniciales"] for t in tabla_sec.values())
    ctrl("Iniciales 2025 (prorrogados) = iniciales 2024", ini25, ini24, 40)

    # Por sección
    filas_s = []
    agg = defaultdict(lambda: defaultdict(float))
    for r in filas_p:
        x = agg[(r["anio"], r["codigo_seccion"])]
        for k in ("creditos_iniciales", "creditos_definitivos", "obligaciones"):
            x[k] += r[k]
        x["pagos"] += r["pagos"] or 0
    for (a, s), x in sorted(agg.items()):
        inf = info.get((a, s), {})
        obl_sec = f(inf.get("obligaciones", ""))
        if a == ANIO_MENSUAL:
            x = dict(tabla_sec[s])  # cifras de la tabla oficial por secciones
        filas_s.append(dict(
            anio=a, dato="provisional (mensual de diciembre)" if a == ANIO_MENSUAL else "definitivo (liquidación)",
            codigo_seccion=s, seccion=inf.get("seccion", ""), ministerio_actual=inf.get("ministerio_actual", ""),
            continuidad=inf.get("continuidad", ""), creditos_iniciales=x["creditos_iniciales"],
            modificaciones=x["creditos_definitivos"] - x["creditos_iniciales"], creditos_definitivos=x["creditos_definitivos"],
            obligaciones=x["obligaciones"], pagos=x["pagos"] if a == ANIO_MENSUAL else None,
            pct_obligaciones_sobre_definitivos=100 * x["obligaciones"] / x["creditos_definitivos"] if x["creditos_definitivos"] else None,
            obligaciones_seccion=obl_sec or None,
            pct_mrr_en_obligaciones_seccion=100 * x["obligaciones"] / obl_sec if obl_sec else None,
            fuente=(fuente_m.format(pags_sec["00"][0]) if a == ANIO_MENSUAL
                    else f"IGAE, Liquidación {a} vol. I, anexos I y II, servicio {s}50 (euros)")))

    campos_s = ["anio", "dato", "codigo_seccion", "seccion", "ministerio_actual", "continuidad", "creditos_iniciales",
                "modificaciones", "creditos_definitivos", "obligaciones", "pagos", "pct_obligaciones_sobre_definitivos",
                "obligaciones_seccion", "pct_mrr_en_obligaciones_seccion", "fuente"]
    campos_p = ["anio", "codigo_seccion", "programa", "programa_nombre", "capitulo", "creditos_iniciales",
                "creditos_definitivos", "obligaciones", "pagos", "fuente"]
    for nombre, campos, filas in (("mrr_secciones.csv", campos_s, filas_s), ("mrr_programa_capitulo.csv", campos_p, filas_p),
                                  ("controles_mrr.csv", ["control", "valor_a", "valor_b", "diferencia", "correcto"], controles)):
        with open(DATOS / nombre, "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh, delimiter=";")
            w.writerow(campos)
            for r in filas:
                w.writerow([fmt(r.get(k)) for k in campos])
    malos = [c for c in controles if c["correcto"] != "sí"]
    print(f"{len(filas_s)} filas por sección, {len(filas_p)} por programa y capítulo; "
          f"{len(controles)} controles, {len(malos)} incorrectos")
    for c in malos[:20]:
        print("  ", c)
    for a in sorted({r["anio"] for r in filas_s}):
        d = sum(r["creditos_definitivos"] for r in filas_s if r["anio"] == a)
        o = sum(r["obligaciones"] for r in filas_s if r["anio"] == a)
        print(f"  {a}: definitivos {d / 1e6:,.1f} M€, obligaciones {o / 1e6:,.1f} M€")


if __name__ == "__main__":
    main()
