"""Lector de la Liquidación del Presupuesto del Estado (IGAE, vol. I), todas las secciones.

Entrada: fuentes/igae/liquidacion_estado/liquidacion_estado_AAAA_vol1.pdf (se convierte con pdftotext -layout).
Salidas (separador ';', decimales con coma, UTF-8, importes en euros):
  datos/liquidacion_secciones.csv        sección: iniciales, cada tipo de modificación, definitivos, obligaciones, pagos
                                         (tablas LIQ 003 y LIQ 006, publicadas en miles de euros: se multiplican por 1.000)
  datos/liquidacion_seccion_capitulo.csv sección × capítulo: iniciales (anexos, euros), definitivos, obligaciones, pagos
                                         (tablas LIQ 012-040, miles de euros)
  datos/liquidacion_aplicaciones.csv     cada aplicación presupuestaria (anexo I «PGE» y anexo II «no PGE»):
                                         iniciales, definitivos y obligaciones en euros con céntimos
  datos/controles_liquidacion.csv        cuadres entre tablas (deben dar diferencias de redondeo)
Uso: python scripts/01_leer_liquidacion.py [año ...]   (por defecto, todos los PDF que haya)
"""
import csv
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
FUENTES = RAIZ / "fuentes" / "igae" / "liquidacion_estado"
DATOS = RAIZ / "datos"
TXT = RAIZ / "fuentes" / "igae" / "_texto"
INTERMEDIOS = RAIZ / "fuentes" / "igae" / "_intermedios"

# 2017-2019: el vol. I no trae los anexos por aplicación, así que el código de sección sale del nombre abreviado
# de las tablas LIQ. Códigos comprobados con la liquidación de 2020 (misma estructura que 2019) y con la de 2017
# del proyecto de Defensa (14 Defensa).
CODIGO_POR_NOMBRE = {
    "CASA DE SU MAJESTAD EL REY": "01", "CORTES GENERALES": "02", "TRIBUNAL DE CUENTAS": "03",
    "TRIBUNAL CONSTITUCIONAL": "04", "CONSEJO DE ESTADO": "05", "DEUDA PÚBLICA": "06", "CLASES PASIVAS": "07",
    "CONSEJO GENERAL DEL PODER JUDICIAL": "08", "APORT. MUTUALISMO ADMINISTRATIVO": "09",
    "CONTRATACIÓN CENTRALIZADA": "10",
    "ASUNTOS EXTERIORES Y DE COOPERACIÓN": "12", "ASUNTOS EXT, U. E. Y COOPERACIÓN": "12",
    "JUSTICIA": "13", "DEFENSA": "14", "HACIENDA Y FUNCIÓN PÚBLICA": "15", "HACIENDA": "15", "INTERIOR": "16",
    "FOMENTO": "17", "EDUCACIÓN, CULTURA Y DEPORTE": "18", "EDUCACIÓN Y FORMACIÓN PROFESIONAL": "18",
    "EMPLEO Y SEGURIDAD SOCIAL": "19", "TRABAJO, MIGRACIONES Y S.S.": "19",
    "ENERGÍA, TURISMO Y AGENDA DIGITAL": "20", "INDUSTRIA, COMERCIO Y TURISMO": "20",
    "AGRICULTURA, PESCA Y ALIMENTACIÓN": "21", "POLÍTICA TERRITORIAL Y FUNCIÓN PÚB.": "22",
    "AGRICULT. Y PESCA, ALIM. Y MEDIO AMB.": "23", "TRANSICIÓN ECOLÓGICA": "23", "CULTURA Y DEPORTE": "24",
    "PRESIDENCIA Y PARA LAS ADM. TERRIT.": "25", "PRESIDENCIA, REL., CORTES E IGUALDAD": "25",
    "SANIDAD, SERVICIOS SOCIALES E IGUALDAD": "26", "SANIDAD, CONSUMO Y BIENESTAR SOCIAL": "26",
    "ECONOMÍA, INDUSTRIA Y COMPETITIVIDAD": "27", "ECONOMÍA Y EMPRESA": "27",
    "CIENCIA, INNOVACIÓN Y UNIVERSIDADES": "28", "GASTOS DE DIVERSOS MINISTERIOS": "31",
    "OTRAS RELAC. FINANC. CON ENTES TERRIT.": "32", "FONDOS DE COMPENSACIÓN INTERTERRIT.": "33",
    "RELACIONES FINANCIERAS CON LA U.E.": "34", "RELACIONES FINANCIERAS CON LA U. E.": "34",
    "FONDO DE CONTINGENCIA": "35", "SISTEMAS DE FINANC. DE ENTES TERRIT.": "36",
}

NUM = r"-?[\d.]+(?:,\d+)?|-"
MODS = ["creditos_iniciales", "creditos_extraordinarios_suplementos", "ampliaciones", "transferencias",
        "incorporacion_remanentes", "generaciones_ingresos", "bajas_otras_modificaciones", "creditos_definitivos"]
CAPITULOS = {1: "Gastos de personal", 2: "Gastos corrientes en bienes y servicios", 3: "Gastos financieros",
             4: "Transferencias corrientes", 5: "Fondo de contingencia y otros imprevistos", 6: "Inversiones reales",
             7: "Transferencias de capital", 8: "Activos financieros", 9: "Pasivos financieros"}


def num(s):
    """'12.827.182' -> 12827182.0 ; '-' -> 0.0 ; '1.234,56' -> 1234.56"""
    s = s.strip()
    if s in ("-", ""):
        return 0.0
    return float(s.replace(".", "").replace(",", "."))


def fmt(x, dec=2):
    if x is None:
        return ""
    if dec == 0 or float(x).is_integer():
        return str(int(round(x)))
    return f"{x:.{dec}f}".replace(".", ",")


def paginas(anio):
    pdf = FUENTES / f"liquidacion_estado_{anio}_vol1.pdf"
    TXT.mkdir(parents=True, exist_ok=True)
    txt = TXT / f"estado_{anio}.txt"
    if not txt.exists() or txt.stat().st_mtime < pdf.stat().st_mtime:
        subprocess.run(["pdftotext", "-layout", str(pdf), str(txt)], check=True)
    return txt.read_text(encoding="utf-8").split("\f")


def filas_tabla(pag, n_min):
    """Filas «NOMBRE   n   n   n ...» de una tabla por secciones (nombre en mayúsculas, números al final)."""
    out = []
    for linea in pag.splitlines():
        partes = re.split(r"\s{2,}", linea.strip())
        if len(partes) < n_min + 1:
            continue
        nombre, vals = partes[0], partes[1:]
        if not re.match(r"^[A-ZÁÉÍÓÚÑÜ][A-ZÁÉÍÓÚÑÜ0-9 .,()/'-]+$", nombre) or nombre in ("IMPORTE",):
            continue
        if not all(re.fullmatch(NUM, v) for v in vals):
            continue
        out.append((nombre, [num(v) for v in vals]))
    return out


def tabla_por_titulo(pags, titulo, n_min):
    filas = []
    for i, p in enumerate(pags, 1):
        cab = "\n".join(p.splitlines()[:8])
        if titulo in cab:
            filas += [(n, v, i) for n, v in filas_tabla(p, n_min)]
    return filas


def programa_base(prog):
    """'121M' -> '121M'; '121M2' -> '121M'; en el anexo II el código puede llevar delante dos dígitos pegados
    al servicio ('17501845DA' -> servicio 1750, programa '1845DA' -> '45DA')."""
    if len(prog) >= 6 and re.fullmatch(r"\d{2}(\d{3}[A-ZÑÇ]|\d{2}[A-ZÑÇ]{2}|000X)\w*", prog):
        return prog[2:6]
    return prog[:4]


def leer_anexo(pags, anio):
    """Aplicaciones de los anexos I (PGE) y II (no PGE). Devuelve lista de dicts y resumen por sección del anexo."""
    apps, resumen, programas = [], {}, {}
    sec_pend = None
    rx_prog = re.compile(r"^(\w{4})-(.*?)\s{2,}(" + NUM + r")\s+(" + NUM + r")\s+(" + NUM + r")\s*$")
    rx_app = re.compile(r"^(\d{4})\s*(\w{4,8})\s+(\w{2,7})\s*-(.*?)\s{2,}(" + NUM + r")\s+(" + NUM + r")\s+(" + NUM + r")\s*$")
    # inicio de partida sin importes; también el caso en que pdftotext pega la cola de la descripción
    # anterior a la económica ('3105 496M 48902del juego' y el guion en la línea siguiente)
    rx_inicio = re.compile(r"^(\d{4})\s*(\w{4,8})\s+(\w{2,7}?)(?:\s*-|(?=[a-záéíóú]))(.*)$")
    rx_tres = re.compile(r"^(.*?)\s*(" + NUM + r")\s+(" + NUM + r")\s+(" + NUM + r")\s*$")
    rx_sec = re.compile(r"^(\d{2})-(.+?)\s{2,}(" + NUM + r")\s+(" + NUM + r")\s+(" + NUM + r")\s*$")
    for i, p in enumerate(pags, 1):
        cab = "\n".join(p.splitlines()[:8])
        if "APLICACIÓN NO PGE" in cab:
            anexo = "II no PGE"
        elif "APLICACIÓN PGE" in cab:
            anexo = "I PGE"
        else:
            continue
        portada = "SECCIONES PRESUPUESTARIAS" in cab or "SECCIÓN  " in p[:3000] and not re.search(r"^\d{4}\s", p, re.M)
        pendiente, ultima_partida = None, None   # descripciones largas: los importes caen en la línea siguiente
        for linea in p.splitlines():
            l = linea.strip()
            m = rx_app.match(l)
            if pendiente and not m:
                m3 = rx_tres.match(l)
                if m3:
                    resto, ini, dfn, obl = m3.groups()
                    srv, prog, eco, desc = pendiente
                    m = (srv, prog, eco, (desc + " " + resto).strip(), ini, dfn, obl)
                    pendiente = None
                elif l and not rx_inicio.match(l):
                    pendiente = (*pendiente[:3], pendiente[3] + " " + l.lstrip("-"))
                    continue
            if m is None and rx_inicio.match(l):
                pendiente = rx_inicio.match(l).groups()
                ultima_partida = None
                continue
            if m is not None:
                srv, prog, eco, desc, ini, dfn, obl = m.groups() if hasattr(m, "groups") else m
                apps.append(dict(anio=anio, anexo=anexo, seccion=srv[:2], servicio=srv, programa=programa_base(prog),
                                 programa_completo=prog, economica=eco, capitulo=int(eco[0]), descripcion=desc.strip(),
                                 creditos_iniciales=num(ini), creditos_definitivos=num(dfn),
                                 obligaciones=num(obl), pagina=i))
                ultima_partida = not hasattr(m, "groups")
                continue
            if ultima_partida and l and not re.search(r"\d,\d\d$", l) and not re.match(r"^\w{4}-", l) \
                    and not l.startswith(("PGE", "LIQ")):
                apps[-1]["descripcion"] += " " + l       # cola de una descripción partida
                continue
            ultima_partida = None
            mp = rx_prog.match(l)
            if mp:
                programas[(mp.group(1))] = re.sub(r"\s+", " ", mp.group(2)).strip()
                continue
            if portada:
                m = rx_sec.match(l)
                if not m and sec_pend and rx_tres.match(l):
                    resto, ini, dfn, obl = rx_tres.match(l).groups()
                    m = re.match(r"(.*)", "")
                    c, nombre = sec_pend[0], sec_pend[1] + " " + resto
                    resumen[(anexo, c)] = dict(nombre=re.sub(r"\s+", " ", nombre).strip(), ini=num(ini),
                                               dfn=num(dfn), obl=num(obl), pagina=i)
                    sec_pend = None
                    continue
                sec_pend = None
                mm = re.match(r"^(\d{2})-([A-ZÁÉÍÓÚÑ ,.]+)$", l)
                if mm:
                    sec_pend = mm.groups()
                    continue
                if m:
                    c, nombre, ini, dfn, obl = m.groups()
                    resumen[(anexo, c)] = dict(nombre=re.sub(r"\s+", " ", nombre).strip(), ini=num(ini),
                                               dfn=num(dfn), obl=num(obl), pagina=i)
    return apps, resumen, programas


def procesar(anio):
    pags = paginas(anio)
    apps, resumen, programas = leer_anexo(pags, anio)
    nombres_largos = {c: r["nombre"] for (a, c), r in resumen.items() if a == "I PGE"}
    codigos = sorted(nombres_largos)
    sin_anexo = not codigos

    # LIQ 003 (modificaciones) y LIQ 006 (situación): mismo orden que la portada del anexo I
    mods = [f for f in tabla_por_titulo(pags, "MODIFICACIONES DE CRÉDITO POR SECCIONES", 8) if f[0] != "TOTALES"]
    sit = [f for f in tabla_por_titulo(pags, "SITUACIÓN POR SECCIONES", 6) if f[0] != "TOTALES"]
    if sin_anexo:   # 2017-2019: el volumen no trae los anexos; el código sale del nombre abreviado
        codigos = [CODIGO_POR_NOMBRE[n] for n, _, _ in mods]
        nombres_largos = {c: n for c, (n, _, _) in zip(codigos, mods)}
    assert len(mods) == len(sit) == len(codigos), (anio, len(mods), len(sit), len(codigos))
    secciones, abrev = [], {}
    for c, (n1, v1, p1), (n2, v2, p2) in zip(codigos, mods, sit):
        assert n1 == n2, (n1, n2)
        # comprobación del emparejamiento: los iniciales de LIQ 003 cuadran con la portada del anexo I
        ini_anexo = resumen[("I PGE", c)]["ini"] if not sin_anexo else v1[0] * 1000
        assert abs(v1[0] * 1000 - ini_anexo) <= max(0.002 * ini_anexo, 50_000), (c, n1, v1[0], ini_anexo)
        abrev[n1] = c
        fila = dict(anio=anio, codigo_seccion=c, seccion=nombres_largos[c], seccion_abreviada=n1,
                    hay_anexo="no" if sin_anexo else "sí")
        fila.update({k: v * 1000 for k, v in zip(MODS, v1[:8])})
        fila["obligaciones"] = v2[1] * 1000
        fila["pagos"] = v2[3] * 1000
        fila["fuente"] = f"IGAE, Liquidación {anio} vol. I, LIQ 003 p. {p1} y LIQ 006 p. {p2} (miles de euros)"
        assert abs(v2[0] - v1[7]) <= 1, (c, "definitivos LIQ003 vs LIQ006", v1[7], v2[0])
        secciones.append(fila)

    # LIQ 012-040: distribución por secciones de cada capítulo
    capit = {}
    for cap in CAPITULOS:
        for n, v, p in tabla_por_titulo(pags, f"DISTRIBUCIÓN DEL CAPÍTULO {cap}:", 6):
            if n in abrev:
                capit[(abrev[n], cap)] = dict(definitivos=v[0] * 1000, obligaciones=v[1] * 1000, pagos=v[3] * 1000,
                                              pagina=p)
    ini_cap = defaultdict(float)
    agg_anexo = defaultdict(lambda: [0.0, 0.0, 0.0])
    for a in apps:
        ini_cap[(a["seccion"], a["capitulo"])] += a["creditos_iniciales"]
        g = agg_anexo[(a["seccion"], a["capitulo"])]
        g[0] += a["creditos_iniciales"]; g[1] += a["creditos_definitivos"]; g[2] += a["obligaciones"]
    sec_cap = []
    for c in codigos:
        for cap, nombre in CAPITULOS.items():
            d = capit.get((c, cap))
            if d is None and not ini_cap.get((c, cap)):
                continue
            d = d or dict(definitivos=0, obligaciones=0, pagos=0, pagina=None)
            sec_cap.append(dict(anio=anio, codigo_seccion=c, capitulo=cap, capitulo_nombre=nombre,
                                creditos_iniciales=None if sin_anexo else ini_cap.get((c, cap), 0.0),
                                creditos_definitivos=d["definitivos"],
                                obligaciones=d["obligaciones"], pagos=d["pagos"],
                                fuente=f"Iniciales: anexo I (euros). Resto: LIQ capítulo {cap}"
                                       + (f", p. {d['pagina']}" if d["pagina"] else "") + " (miles de euros)"))

    # Controles
    ctrl = []
    def control(que, c, a, b, tol):
        ctrl.append(dict(anio=anio, control=que, codigo_seccion=c, valor_a=a, valor_b=b, diferencia=a - b,
                         ok="sí" if abs(a - b) <= tol else "NO"))
    for s in secciones:
        c = s["codigo_seccion"]
        suma_mods = sum(s[k] for k in MODS[:7])
        control("iniciales + modificaciones = definitivos (LIQ 003)", c, suma_mods, s["creditos_definitivos"], 20_000)
        caps = [x for x in sec_cap if x["codigo_seccion"] == c]
        for k in ("creditos_definitivos", "obligaciones", "pagos"):
            control(f"suma de capítulos = sección ({k})", c, sum(x[k] for x in caps), s[k], 10_000)
        if sin_anexo:
            continue
        ini_caps = sum(x["creditos_iniciales"] for x in caps)
        control("suma de capítulos = sección (iniciales, anexo I vs LIQ 003)", c, ini_caps, s["creditos_iniciales"],
                0.002 * abs(s["creditos_iniciales"]) + 50_000)
        anexo_def = resumen.get(("I PGE", c), {}).get("dfn", 0) + resumen.get(("II no PGE", c), {}).get("dfn", 0)
        anexo_obl = resumen.get(("I PGE", c), {}).get("obl", 0) + resumen.get(("II no PGE", c), {}).get("obl", 0)
        control("anexos I+II = sección (definitivos)", c, anexo_def, s["creditos_definitivos"], 0.001 * abs(s["creditos_definitivos"]) + 50_000)
        control("anexos I+II = sección (obligaciones)", c, anexo_obl, s["obligaciones"], 0.001 * abs(s["obligaciones"]) + 50_000)
        sum_apps_obl = sum(a["obligaciones"] for a in apps if a["seccion"] == c)
        control("suma de aplicaciones leídas = portadas de los anexos (obligaciones)", c, sum_apps_obl, anexo_obl, 1.0)
    # LIQ 008: grupos de programas por secciones (todos los años; sirve para repartir secciones partidas)
    grupos, g_actual = [], None
    for i, pg in enumerate(pags, 1):
        if "GRUPOS DE PROGRAMAS POR SECCIONES" not in "\n".join(pg.splitlines()[:8]):
            continue
        for linea in pg.splitlines():
            sangria = len(linea) - len(linea.lstrip())
            mg = re.match(r"^\s*(.+?)\s{2,}(" + NUM + r")\s+(" + NUM + r")\s", linea)
            if mg and sangria <= 6 and re.search(r"[a-záéíóú]", mg.group(1)):   # grupo: sangría corta, minúsculas
                txt = re.sub(r"\s+", " ", mg.group(1)).strip()
                mc = re.match(r"^(\w{3,6})-(.*)$", txt)
                g_actual = (mc.group(1), mc.group(2).strip()) if mc else ("", txt)
                continue
            for n, v in filas_tabla(linea, 6):
                if n in abrev and g_actual:
                    grupos.append(dict(anio=anio, grupo_programas=g_actual[0], grupo_nombre=g_actual[1],
                                       codigo_seccion=abrev[n], creditos_definitivos=v[0] * 1000,
                                       obligaciones=v[1] * 1000, pagos=v[3] * 1000,
                                       fuente=f"IGAE, Liquidación {anio} vol. I, LIQ 008 p. {i} (miles de euros)"))
    for c in codigos:
        g = [x for x in grupos if x["codigo_seccion"] == c]
        s_ = next(x for x in secciones if x["codigo_seccion"] == c)
        for k in ("creditos_definitivos", "obligaciones", "pagos"):
            control(f"suma de grupos de programas = sección ({k})", c, sum(x[k] for x in g), s_[k], 20_000)

    # programa × capítulo (agregado de las aplicaciones; es el nivel que se publica)
    pc = defaultdict(lambda: [0.0, 0.0, 0.0])
    for a in apps:
        g = pc[(a["seccion"], a["programa"], a["capitulo"])]
        g[0] += a["creditos_iniciales"]; g[1] += a["creditos_definitivos"]; g[2] += a["obligaciones"]
    prog_cap = [dict(anio=anio, codigo_seccion=k[0], programa=k[1], programa_nombre=programas.get(k[1], ""),
                     capitulo=k[2], creditos_iniciales=v[0], creditos_definitivos=v[1], obligaciones=v[2],
                     fuente=f"IGAE, Liquidación {anio} vol. I, anexos I y II (euros)")
                for k, v in sorted(pc.items())]
    return secciones, sec_cap, prog_cap, grupos, apps, ctrl


def escribir(nombre, filas, campos):
    ruta = DATOS / nombre
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(campos)
        for r in filas:
            w.writerow([fmt(r[k]) if isinstance(r[k], float) else ("" if r[k] is None else r[k]) for k in campos])


def main():
    anios = [int(a) for a in sys.argv[1:]] or sorted(int(re.search(r"(\d{4})", p.name).group(1))
                                                    for p in FUENTES.glob("liquidacion_estado_*_vol1.pdf"))
    S, SC, PC, G, A, C = [], [], [], [], [], []
    for anio in anios:
        s, sc, pc, g, a, c = procesar(anio)
        S += s; SC += sc; PC += pc; G += g; A += a; C += c
        malos = [x for x in c if x["ok"] == "NO"]
        print(f"{anio}: {len(s)} secciones, {len(sc)} filas sección×capítulo, {len(a)} aplicaciones, "
              f"{len(c)} controles, {len(malos)} fallidos")
        for m in malos:
            print("   ", m)
    escribir("liquidacion_secciones.csv", S, ["anio", "codigo_seccion", "seccion", "seccion_abreviada", "hay_anexo"] + MODS
             + ["obligaciones", "pagos", "fuente"])
    escribir("liquidacion_seccion_capitulo.csv", SC, ["anio", "codigo_seccion", "capitulo", "capitulo_nombre",
             "creditos_iniciales", "creditos_definitivos", "obligaciones", "pagos", "fuente"])
    escribir("liquidacion_grupo_programas_seccion.csv", G, ["anio", "grupo_programas", "grupo_nombre",
             "codigo_seccion", "creditos_definitivos", "obligaciones", "pagos", "fuente"])
    escribir("liquidacion_programa_capitulo.csv", PC, ["anio", "codigo_seccion", "programa", "programa_nombre",
             "capitulo", "creditos_iniciales", "creditos_definitivos", "obligaciones", "fuente"])
    # Las aplicaciones se quedan como intermedio: sus descripciones nombran a entidades beneficiarias
    # (subvenciones nominativas) y el proyecto solo publica agregados por programa.
    escribir(INTERMEDIOS / "liquidacion_aplicaciones.csv", A, ["anio", "anexo", "seccion", "servicio", "programa",
             "programa_completo", "economica", "capitulo", "descripcion", "creditos_iniciales",
             "creditos_definitivos", "obligaciones", "pagina"])
    escribir("controles_liquidacion.csv", C, ["anio", "control", "codigo_seccion", "valor_a", "valor_b",
             "diferencia", "ok"])


if __name__ == "__main__":
    main()
