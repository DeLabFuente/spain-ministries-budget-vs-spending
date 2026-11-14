"""Pregunta 5 · Respuesta presupuestaria a las catástrofes (2020-2025), en todas las secciones del Estado.

Sucesos: covid-19 (2020), crisis de la energía y los precios (2022), DANA de 2024 (programa 929D), erupción
volcánica de La Palma (2021) y borrasca Filomena (2021).

Qué mide: las líneas del presupuesto del Estado (aplicaciones de los anexos I «PGE» y II «no PGE») que se pueden
ligar a cada suceso, con su crédito inicial, su crédito definitivo y sus obligaciones reconocidas, por año y por
ministerio actual. Es una COTA INFERIOR: solo entra lo que se identifica con una regla escrita.

Entradas:
  fuentes/igae/_intermedios/liquidacion_aplicaciones.csv   aplicaciones 2020-2024 (script 01)
  fuentes/igae/_texto/mensual_12-25.txt                    2025, anexos por aplicación de la mensual de diciembre
                                                           (provisional), leídos con el lector del script 01
  fuentes/igae/_texto/estado_2024.txt                      solo para el control del programa 929D
  datos/secciones_ministerio_actual.csv                    sección y año -> ministerio actual
  datos/mensual_secciones.csv                              control de la lectura de 2025

Reglas (REGISTRO B21). Dos criterios, que se guardan en la columna `criterio`:
  «descripción»  la descripción de la línea o el nombre del programa nombran el suceso (covid, DANA, volcán, Filomena).
  «regla»        la línea no nombra el suceso y se liga a él por su aplicación y la norma que la creó (lista REGLAS).
Se excluyen las líneas del Mecanismo de Recuperación y Resiliencia (tienen su apartado en la comparativa).
No se cuenta nada de la Seguridad Social, el SEPE ni los demás organismos (solo lo que el Estado les transfiere
con el nombre del suceso), ni los avales, ni las rebajas de impuestos.

Salidas (separador ';', decimales con coma, UTF-8, importes en euros):
  datos/catastrofes_ministerio.csv     suceso × criterio × medida × año × sección × anexo (agregado; sin descripciones)
  datos/catastrofes_resumen.csv        suceso × año
  datos/catastrofes_destino.csv        suceso × a quién va la línea (por su clasificación económica) × año
  datos/controles_catastrofes.csv      cuadres de la lectura
  fuentes/igae/_intermedios/catastrofes_lineas.csv   línea a línea (no se publica: las descripciones nombran a
                                                     beneficiarios de subvenciones nominativas)
  preguntas.md                       tablas entre las marcas <!-- tabla:catastrofes_… --> y <!-- /tabla -->
Uso: python scripts/18_catastrofes.py
"""
import csv
import importlib.util
import re
import subprocess
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datos"
INTERMEDIOS = RAIZ / "fuentes" / "igae" / "_intermedios"
TXT = RAIZ / "fuentes" / "igae" / "_texto"
APLIC = INTERMEDIOS / "liquidacion_aplicaciones.csv"
MENSUAL_TXT = TXT / "mensual_12-25.txt"
MENSUAL_PDF = RAIZ / "fuentes" / "igae" / "mensual" / "mensual_12-25.pdf"
DOC = RAIZ / "preguntas.md"
ANIO_MENSUAL = 2025
ANIOS = list(range(2020, ANIO_MENSUAL + 1))
TOL_SECCION = 15000   # la tabla por secciones de la mensual va en miles de euros y suma capítulos redondeados

SUCESOS = {"covid": "Covid-19", "energia": "Crisis de la energía y los precios", "palma": "Volcán de La Palma",
           "filomena": "Borrasca Filomena", "dana": "DANA de 2024"}
ORDEN = ["covid", "energia", "dana", "palma", "filomena"]

RX_MRR = re.compile(r"mecanismo de recup|mecanismo recup|\bMRR\b|M\.R\.R", re.I)
RX_COVID = re.compile(r"covid|coronavirus|sars-cov|pandemia", re.I)
RX_DANA = re.compile(r"\bdana\b|depresi[oó]n aislada", re.I)
RX_VOLCAN = re.compile(r"(?<![a-záéíóú])volc[aá]n(?:ic|\b)|erupci", re.I)
RX_PALMA = re.compile(r"\bla palma\b", re.I)
RX_PALMA_NO = re.compile(r"Correillo|Astrof[ií]sic|RedIRIS|exhumaci", re.I)   # líneas de la isla ajenas a la erupción
RX_FILOMENA = re.compile(r"filomena", re.I)

# Líneas que no nombran el suceso: (suceso, medida, años, sección, programa, económica (regex), descripción (regex), norma)
# La descripción se exige además de la aplicación para que un cambio de código no cuele otra línea.
REGLAS = [
    ("covid", "Solvencia de empresas", (2020, 2020), "15", "923M", r"879", r"solvencia de empresas estrat",
     "RDL 25/2020, art. 2"),
    ("energia", "Bonificación de carburantes", (2022, 2025), "15", "923M", r"479|489", r"consumo de combustibles",
     "RDL 6/2022, art. 15"),
    ("energia", "Gasóleo profesional y agrario", (2023, 2025), "15", "923M", r"474", r"consumo de gas[oó]leo",
     "RDL 20/2022"),
    ("energia", "Gasóleo profesional y agrario", (2023, 2025), "15", "923M", r"476", r"explotaciones agrarias",
     "RDL 20/2022"),
    ("energia", "Industria intensiva en gas", (2022, 2025), "15", "923M", r"478", r"consumidoras de gas",
     "RDL 6/2022, art. 3"),
    ("energia", "Industria intensiva en gas", (2023, 2025), "20", "422B", r"774", r"precios del gas natural",
     "RDL 20/2022"),
    ("energia", "Ayudas directas al transporte", (2022, 2025), "15", "923M", r"472|473", r"sector del transporte",
     "RDL 6/2022 y RDL 20/2022"),
    ("energia", "Ayudas directas al transporte", (2022, 2025), "17", "441M", r"441|474",
     r"subida de los precios de los carburantes", "RDL 6/2022"),
    ("energia", "Ayuda a rentas bajas", (2022, 2025), "15", "923M", r"480|484", r"bajo nivel de ingresos",
     "RDL 11/2022 y RDL 20/2022"),
    ("energia", "País Vasco y Navarra (apoyo a familias y empresas)", (2022, 2025), "15", "923M", r"451|452",
     r"apoyo p[uú]blico a familias y empresas", "RDL 6/2022, art. 20 (territorios forales)"),
    ("energia", "Sistema eléctrico y gas (a la CNMC)", (2022, 2025), "23", "000X", r"73[2-6]", r"CNMC",
     "RDL 29/2021 (733), RDL 6/2022, art. 2 (732) y RDL 18/2022 (735 y 736); la 734, sin identificar"),
    ("energia", "Descuentos en transporte público y peajes", (2022, 2025), "17", "441M", r".*",
     r"reducci[oó]n.{0,6}precio|reducc precio|descuento del? 100|descto del 100|limitaci[oó]n de revisi[oó]n de tarifas",
     "RDL 11/2022, RDL 14/2022 y RDL 20/2022"),
    ("energia", "Sector agrario y pesquero", (2022, 2025), "21", None, r".*",
     r"marco temporal|costes de producci[oó]n adicionales|precio del gas[oó]leo consumido",
     "Marco temporal de ayudas por la guerra de Ucrania (RDL 6/2022 y RDL 20/2022; en 2023, sin comprobar, RDL 4/2023)"),
]
REGLAS = [(s, med, a, sec, prog, re.compile(r"^(?:" + eco + r")$"), re.compile(desc, re.I), norma)
          for s, med, a, sec, prog, eco, desc, norma in REGLAS]


def f(x):
    return float(x.replace(",", ".")) if x not in ("", None) else 0.0


def fmt(x):
    if isinstance(x, float):
        return str(int(round(x))) if abs(x - round(x)) < 1e-9 else f"{x:.2f}".replace(".", ",")
    return "" if x is None else str(x)


def m(x, dec=None):
    """Millones de euros con punto de millar y coma decimal; un decimal por debajo de 100 M€."""
    if x is None:
        return "—"
    v = x / 1e6
    if dec is None:
        dec = 0 if abs(v) >= 100 else 1
    if round(v, dec) == 0:
        return "—" if x == 0 else ("0" if dec == 0 else "0,0")
    return f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def p(a, b, dec=1):
    return "—" if not b else f"{100 * a / b:.{dec}f}".replace(".", ",")


def corto(mi):
    return re.sub(r"^Ministerio (de la |del |de |para la )", "", mi)


def leer(pth):
    with open(pth, encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter=";"))


def escribir(pth, filas, campos):
    with open(pth, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=campos, delimiter=";", extrasaction="ignore")
        w.writeheader()
        for r in filas:
            w.writerow({k: fmt(r.get(k)) for k in campos})


def lector_01():
    spec = importlib.util.spec_from_file_location("leer_liquidacion", Path(__file__).with_name("01_leer_liquidacion.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def aplicaciones():
    """Todas las aplicaciones 2020-2025: liquidación (CSV del script 01) y mensual de diciembre (texto)."""
    apps = []
    for r in leer(APLIC):
        apps.append(dict(anio=int(r["anio"]), anexo=r["anexo"], seccion=r["seccion"], servicio=r["servicio"],
                         programa=r["programa"], economica=r["economica"], descripcion=r["descripcion"],
                         creditos_iniciales=f(r["creditos_iniciales"]), creditos_definitivos=f(r["creditos_definitivos"]),
                         obligaciones=f(r["obligaciones"]), pagina=int(r["pagina"]), dato="definitivo (liquidación)"))
    if not MENSUAL_TXT.exists():
        subprocess.run(["pdftotext", "-layout", str(MENSUAL_PDF), str(MENSUAL_TXT)], check=True)
    s01 = lector_01()
    pags = MENSUAL_TXT.read_text(encoding="utf-8").split("\f")
    mens, resumen, _ = s01.leer_anexo(pags, ANIO_MENSUAL)
    for r in mens:
        r["dato"] = "provisional (mensual de diciembre)"
        r["capitulo"] = str(r["capitulo"])
    return apps + mens, mens, resumen


DESTINOS = ["Seguridad Social", "Comunidades autónomas", "Entidades locales",
            "Organismos y entidades públicas estatales", "Empresas privadas",
            "Familias e instituciones sin fines de lucro", "Exterior",
            "Aportaciones a fondos y préstamos (capítulo 8)", "Gasto directo del Estado (personal, compras e inversiones)"]


def destino(eco):
    """A quién va la línea, por su clasificación económica (capítulo y artículo)."""
    if eco[0] in "47":
        return {"0": DESTINOS[3], "1": DESTINOS[3], "2": DESTINOS[0], "3": DESTINOS[3], "4": DESTINOS[3],
                "5": DESTINOS[1], "6": DESTINOS[2], "7": DESTINOS[4], "8": DESTINOS[5], "9": DESTINOS[6]}[eco[1]]
    return DESTINOS[7] if eco[0] == "8" else DESTINOS[8]


def clasificar(r):
    """(suceso, criterio, medida, norma) o None."""
    d, a = r["descripcion"], r["anio"]
    if RX_MRR.search(d):
        return None
    if r["programa"] == "929D":
        return "dana", "descripción", "", "RDL 6/2024, RDL 7/2024 y RDL 8/2024 (programa 929D)"
    if a >= 2024 and RX_DANA.search(d):
        return "dana", "descripción", "", "línea con «DANA» fuera del programa 929D"
    if RX_FILOMENA.search(d):
        return "filomena", "descripción", "", "RDL 10/2021"
    if a >= 2021 and RX_VOLCAN.search(d):
        return "palma", "descripción", "", "RDL 20/2021 y otras"
    if a >= 2021 and RX_PALMA.search(d) and not RX_PALMA_NO.search(d):
        return "palma", "regla", "", "línea para la isla de La Palma creada después de la erupción"
    if RX_COVID.search(d):
        if r["economica"] == "42906":
            med = "Transferencia a la Seguridad Social"
        elif r["programa"] == "941O":
            med = "Fondo COVID-19 y ayudas directas (a comunidades autónomas)"
        elif r["seccion"] == "26":
            med = "Sanidad"
        elif (r["programa"], r["economica"]) in (("431O", "875"), ("931M", "470")):
            med = "Solvencia de empresas"
        else:
            med = "Resto"
        return "covid", "descripción", med, ""
    for s, med, (a0, a1), sec, prog, rx_eco, rx_desc, norma in REGLAS:
        if a0 <= a <= a1 and r["seccion"] == sec and (prog is None or r["programa"] == prog) \
                and rx_eco.match(r["economica"]) and rx_desc.search(d):
            return s, "regla", med, norma
    return None


def total_programa(pags, prog):
    """Suma de las cabeceras «929D-Nombre  ini  dfn  obl» (una por servicio) de las páginas de los anexos."""
    num = r"-?[\d.]+(?:,\d+)?|-"
    rx = re.compile(r"^\s*" + prog + r"-.*?\s{2,}(" + num + r")\s+(" + num + r")\s+(" + num + r")\s*$", re.M)
    v = lambda s: 0.0 if s == "-" else float(s.replace(".", "").replace(",", "."))
    tot = [0.0, 0.0, 0.0]
    for pg in pags:
        cab = "\n".join(pg.splitlines()[:8])
        if "APLICACIÓN NO PGE" not in cab and "APLICACIÓN PGE" not in cab:
            continue
        for mm in rx.finditer(pg):
            for i in range(3):
                tot[i] += v(mm.group(i + 1))
    return tot


def main():
    apps, mens, resumen_mens = aplicaciones()
    sec = {(int(r["anio"]), r["codigo_seccion"]): r for r in leer(DATOS / "secciones_ministerio_actual.csv")}

    # ---------- controles de la lectura
    ctrl = []

    def control(que, a, b, tol, nota=""):
        ctrl.append(dict(control=que, valor_a=a, valor_b=b, diferencia=a - b, tolerancia=tol,
                         correcto="sí" if abs(a - b) <= tol else "NO", nota=nota))

    por_sec = defaultdict(lambda: [0.0, 0.0, 0.0])
    for r in mens:
        for i, k in enumerate(("creditos_iniciales", "creditos_definitivos", "obligaciones")):
            por_sec[r["seccion"]][i] += r[k]
    for r in leer(DATOS / "mensual_secciones.csv"):
        c = r["codigo_seccion"]
        for i, k in enumerate(("creditos_iniciales", "creditos_definitivos", "obligaciones")):
            control(f"2025 · sección {c} · {k}: anexos por aplicación = tabla por secciones", por_sec[c][i], f(r[k]),
                    TOL_SECCION, "la tabla va en miles de euros")
    res_sec = defaultdict(lambda: [0.0, 0.0])
    for (anexo, c), v in resumen_mens.items():
        res_sec[c][0] += v["dfn"]
        res_sec[c][1] += v["obl"]
    for c, v in sorted(res_sec.items()):
        control(f"2025 · sección {c} · definitivos: aplicaciones = resumen del anexo", por_sec[c][1], v[0], 0.05)
        control(f"2025 · sección {c} · obligaciones: aplicaciones = resumen del anexo", por_sec[c][2], v[1], 0.05)
    for anio, txt in ((2024, TXT / "estado_2024.txt"), (ANIO_MENSUAL, MENSUAL_TXT)):
        if not txt.exists():
            continue
        cab = total_programa(txt.read_text(encoding="utf-8").split("\f"), "929D")
        lin = [sum(r[k] for r in apps if r["anio"] == anio and r["programa"] == "929D")
               for k in ("creditos_iniciales", "creditos_definitivos", "obligaciones")]
        for i, k in enumerate(("creditos_iniciales", "creditos_definitivos", "obligaciones")):
            control(f"{anio} · programa 929D · {k}: suma de líneas = suma de cabeceras de programa", lin[i], cab[i], 1.0)

    # ---------- clasificación
    lineas = []
    excl_mrr = defaultdict(float)
    for r in apps:
        if r["anio"] not in ANIOS:
            continue
        c = clasificar(r)
        if c is None:
            d = r["descripcion"]
            if RX_MRR.search(d) and (RX_COVID.search(d) or RX_VOLCAN.search(d) or RX_DANA.search(d)
                                     or r["programa"] == "929D"
                                     or (RX_PALMA.search(d) and not RX_PALMA_NO.search(d))):
                excl_mrr[r["anio"]] += r["obligaciones"]
            continue
        s, crit, med, norma = c
        info = sec[(r["anio"], r["seccion"])]
        lineas.append(dict(r, suceso=s, suceso_nombre=SUCESOS[s], criterio=crit, medida=med, norma=norma,
                           destino=destino(r["economica"]),
                           codigo_seccion=r["seccion"], ministerio_actual=info["ministerio_actual"],
                           tipo_seccion=info["tipo"]))

    INTERMEDIOS.mkdir(parents=True, exist_ok=True)
    escribir(INTERMEDIOS / "catastrofes_lineas.csv", lineas,
             ["suceso", "criterio", "medida", "norma", "anio", "dato", "anexo", "codigo_seccion", "ministerio_actual",
              "servicio", "programa", "economica", "destino", "descripcion", "creditos_iniciales",
              "creditos_definitivos", "obligaciones", "pagina"])

    # ---------- agregado publicable
    ag = defaultdict(lambda: dict(lineas=0, creditos_iniciales=0.0, creditos_definitivos=0.0, obligaciones=0.0))
    for r in lineas:
        k = (r["suceso"], r["criterio"], r["medida"], r["anio"], r["dato"], r["codigo_seccion"], r["ministerio_actual"],
             r["tipo_seccion"], r["anexo"])
        ag[k]["lineas"] += 1
        for c in ("creditos_iniciales", "creditos_definitivos", "obligaciones"):
            ag[k][c] += r[c]
    filas = []
    for k in sorted(ag, key=lambda k: (ORDEN.index(k[0]), k[3], k[5], k[1], k[2], k[8])):
        v = ag[k]
        fuente = ("IGAE, Liquidación del Presupuesto del Estado %d, vol. I, anexos por aplicación" % k[3]
                  if k[3] < ANIO_MENSUAL else
                  "IGAE, Estadística mensual de ejecución, diciembre de 2025 (provisional), anexos por aplicación")
        filas.append(dict(suceso=k[0], suceso_nombre=SUCESOS[k[0]], criterio=k[1], medida=k[2], anio=k[3], dato=k[4],
                          codigo_seccion=k[5], ministerio_actual=k[6], tipo_seccion=k[7], anexo=k[8], **v,
                          pct_obligaciones_sobre_definitivos=(round(100 * v["obligaciones"] / v["creditos_definitivos"], 1)
                                                              if v["creditos_definitivos"] else None),
                          fuente=fuente))
    escribir(DATOS / "catastrofes_ministerio.csv", filas,
             ["suceso", "suceso_nombre", "criterio", "medida", "anio", "dato", "codigo_seccion", "ministerio_actual",
              "tipo_seccion", "anexo", "lineas", "creditos_iniciales", "creditos_definitivos", "obligaciones",
              "pct_obligaciones_sobre_definitivos", "fuente"])

    # ---------- resumen suceso × año
    res = {}
    for s in ORDEN:
        for a in ANIOS:
            ls = [r for r in lineas if r["suceso"] == s and r["anio"] == a]
            if not ls:
                continue
            ii = [r for r in ls if r["anexo"] == "II no PGE"]
            res[(s, a)] = dict(
                suceso=s, suceso_nombre=SUCESOS[s], anio=a, dato=ls[0]["dato"], lineas=len(ls),
                secciones=len({r["codigo_seccion"] for r in ls if r["creditos_definitivos"] or r["obligaciones"]}),
                creditos_iniciales=sum(r["creditos_iniciales"] for r in ls),
                creditos_definitivos=sum(r["creditos_definitivos"] for r in ls),
                creditos_definitivos_anexo_ii=sum(r["creditos_definitivos"] for r in ii),
                obligaciones=sum(r["obligaciones"] for r in ls),
                obligaciones_anexo_ii=sum(r["obligaciones"] for r in ii),
                obligaciones_por_regla=sum(r["obligaciones"] for r in ls if r["criterio"] == "regla"))
    for v in res.values():
        v["pct_obligaciones_sobre_definitivos"] = (round(100 * v["obligaciones"] / v["creditos_definitivos"], 1)
                                                   if v["creditos_definitivos"] else None)
        v["pct_credito_anexo_ii"] = (round(100 * v["creditos_definitivos_anexo_ii"] / v["creditos_definitivos"], 1)
                                     if v["creditos_definitivos"] else None)
    escribir(DATOS / "catastrofes_resumen.csv", [res[k] for k in sorted(res, key=lambda k: (ORDEN.index(k[0]), k[1]))],
             ["suceso", "suceso_nombre", "anio", "dato", "lineas", "secciones", "creditos_iniciales",
              "creditos_definitivos", "creditos_definitivos_anexo_ii", "pct_credito_anexo_ii", "obligaciones",
              "obligaciones_anexo_ii", "obligaciones_por_regla", "pct_obligaciones_sobre_definitivos"])

    # ---------- a quién va (suceso × destino × año)
    dst = defaultdict(lambda: dict(lineas=0, creditos_definitivos=0.0, obligaciones=0.0))
    for r in lineas:
        k = (r["suceso"], r["destino"], r["anio"])
        dst[k]["lineas"] += 1
        dst[k]["creditos_definitivos"] += r["creditos_definitivos"]
        dst[k]["obligaciones"] += r["obligaciones"]
    escribir(DATOS / "catastrofes_destino.csv",
             [dict(suceso=k[0], suceso_nombre=SUCESOS[k[0]], destino=k[1], anio=k[2], **dst[k])
              for k in sorted(dst, key=lambda k: (ORDEN.index(k[0]), DESTINOS.index(k[1]), k[2]))],
             ["suceso", "suceso_nombre", "destino", "anio", "lineas", "creditos_definitivos", "obligaciones"])

    # cuadre interno: agregado = resumen = líneas
    for s in ORDEN:
        control(f"{s} · obligaciones 2020-2025: agregado por ministerio = resumen por año",
                sum(r["obligaciones"] for r in filas if r["suceso"] == s),
                sum(v["obligaciones"] for (ss, a), v in res.items() if ss == s), 0.01)
        control(f"{s} · obligaciones 2020-2025: por destino = resumen por año",
                sum(v["obligaciones"] for k, v in dst.items() if k[0] == s),
                sum(v["obligaciones"] for (ss, a), v in res.items() if ss == s), 0.01)
    escribir(DATOS / "controles_catastrofes.csv", ctrl,
             ["control", "valor_a", "valor_b", "diferencia", "tolerancia", "correcto", "nota"])

    # ---------- tablas de preguntas.md
    T = {}
    cab_anios = " | ".join(str(a) if a < ANIO_MENSUAL else f"{a} (prov.)" for a in ANIOS)
    sep_anios = " | ".join("---:" for _ in ANIOS)

    t = [f"| Suceso | {cab_anios} | 2020-2025 |", f"| --- | {sep_anios} | ---: |"]
    for s in ORDEN:
        v = [res[(s, a)]["obligaciones"] if (s, a) in res else None for a in ANIOS]
        t.append(f"| {SUCESOS[s]} | " + " | ".join(m(x) for x in v) + f" | **{m(sum(x or 0 for x in v))}** |")
    T["catastrofes_anio"] = "\n".join(t)

    t = [f"| Suceso | {cab_anios} |", f"| --- | {sep_anios} |"]
    for s in ORDEN:
        c = []
        for a in ANIOS:
            v = res.get((s, a))
            c.append("—" if not v or not v["creditos_definitivos"]
                     else f"{m(v['creditos_definitivos'])} · {p(v['obligaciones'], v['creditos_definitivos'])} %")
        t.append(f"| {SUCESOS[s]} | " + " | ".join(c) + " |")
    T["catastrofes_ejecucion"] = "\n".join(t)

    t = ["| Suceso | Primer año con crédito | Secciones con crédito ese año (y máximo) | Crédito definitivo ese año | "
         "En líneas que no estaban en el presupuesto (anexo II), % | Reconocido ese mismo año, % | "
         "Obligaciones hasta 2025 |", "| --- | :---: | :---: | ---: | ---: | ---: | ---: |"]
    for s in ORDEN:
        a0 = min(a for (ss, a), v in res.items() if ss == s and v["creditos_definitivos"] > 0)
        v = res[(s, a0)]
        amax = max(((vv["secciones"], -a) for (ss, a), vv in res.items() if ss == s))
        t.append(f"| {SUCESOS[s]} | {a0} | {v['secciones']} ({amax[0]} en {-amax[1]}) | {m(v['creditos_definitivos'])} | "
                 f"{p(v['creditos_definitivos_anexo_ii'], v['creditos_definitivos'])} | "
                 f"{p(v['obligaciones'], v['creditos_definitivos'])} | "
                 f"{m(sum(vv['obligaciones'] for (ss, a), vv in res.items() if ss == s))} |")
    T["catastrofes_apertura"] = "\n".join(t)

    mi = defaultdict(lambda: defaultdict(float))
    tipo = {}
    for r in filas:
        mi[r["ministerio_actual"]][r["suceso"]] += r["obligaciones"]
        tipo[r["ministerio_actual"]] = r["tipo_seccion"]
    t = ["| Ministerio actual o sección | " + " | ".join(SUCESOS[s] for s in ORDEN) + " | Total |",
         "| --- | " + " | ".join("---:" for _ in ORDEN) + " | ---: |"]
    for nombre in sorted(mi, key=lambda n: -sum(mi[n].values())):
        if sum(mi[nombre].values()) < 50000:
            continue
        et = corto(nombre) + ("" if tipo[nombre] == "Ministerio" else " *(sección no ministerial)*")
        t.append(f"| {et} | " + " | ".join(m(mi[nombre].get(s, 0.0)) for s in ORDEN)
                 + f" | **{m(sum(mi[nombre].values()))}** |")
    t.append("| **Total** | " + " | ".join(f"**{m(sum(mi[n].get(s, 0.0) for n in mi))}**" for s in ORDEN)
             + f" | **{m(sum(sum(v.values()) for v in mi.values()))}** |")
    T["catastrofes_ministerio"] = "\n".join(t)

    tot_s = {s: sum(v["obligaciones"] for k, v in dst.items() if k[0] == s) for s in ORDEN}
    t = ["| A quién va (obligaciones 2020-2025, % del suceso) | " + " | ".join(SUCESOS[s] for s in ORDEN) + " |",
         "| --- | " + " | ".join("---:" for _ in ORDEN) + " |"]
    for d in DESTINOS:
        vals = [sum(v["obligaciones"] for k, v in dst.items() if k[0] == s and k[1] == d) for s in ORDEN]
        t.append(f"| {d} | " + " | ".join(p(x, tot_s[s]) if x else "—" for x, s in zip(vals, ORDEN)) + " |")
    t.append("| **Total, M€** | " + " | ".join(f"**{m(tot_s[s])}**" for s in ORDEN) + " |")
    T["catastrofes_destino"] = "\n".join(t)

    for s in ("covid", "energia"):
        med = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))
        for r in filas:
            if r["suceso"] == s:
                med[r["medida"]][r["anio"]][0] += r["obligaciones"]
                med[r["medida"]][r["anio"]][1] += r["creditos_definitivos"]
        an = [a for a in ANIOS if any(a in v for v in med.values())]
        t = ["| Medida | " + " | ".join(str(a) if a < ANIO_MENSUAL else f"{a} (prov.)" for a in an)
             + " | Total | Reconocido sobre el crédito de cada año, % |",
             "| --- | " + " | ".join("---:" for _ in an) + " | ---: | ---: |"]
        for k in sorted(med, key=lambda k: -sum(v[0] for v in med[k].values())):
            o = sum(v[0] for v in med[k].values())
            c = sum(v[1] for v in med[k].values())
            t.append(f"| {k} | " + " | ".join(m(med[k][a][0]) if a in med[k] else "—" for a in an)
                     + f" | **{m(o)}** | {p(o, c)} |")
        T[f"catastrofes_{s}"] = "\n".join(t)

    texto = DOC.read_text(encoding="utf-8")
    hechas = 0
    for nombre, tabla in T.items():
        texto, n = re.subn(rf"<!-- tabla:{nombre} -->.*?<!-- /tabla -->",
                           lambda _: f"<!-- tabla:{nombre} -->\n{tabla}\n<!-- /tabla -->", texto, flags=re.S)
        hechas += n
    DOC.write_text(texto, encoding="utf-8")

    malos = [c for c in ctrl if c["correcto"] != "sí"]
    print(f"{len(lineas)} líneas clasificadas; {len(filas)} filas en catastrofes_ministerio.csv; "
          f"{len(ctrl)} controles, {len(malos)} incorrectos; preguntas.md: {hechas} de {len(T)} marcas")
    for c in malos:
        print("  CONTROL INCORRECTO:", c["control"], c["valor_a"], c["valor_b"])
    for s in ORDEN:
        print(f"  {SUCESOS[s]:36}", " ".join(f"{a}: {m(res[(s, a)]['obligaciones']):>8}" for a in ANIOS if (s, a) in res))
    print("  Excluido por ser del Mecanismo de Recuperación (obligaciones, M€):",
          ", ".join(f"{a}: {m(v)}" for a, v in sorted(excl_mrr.items())))
    for nombre, tabla in T.items():
        print(f"\n[{nombre}]\n{tabla}")


if __name__ == "__main__":
    main()
