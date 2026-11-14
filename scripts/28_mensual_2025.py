"""Pregunta 11 · ¿Cuándo gasta cada ministerio? Calendario mensual de ejecución (2024 y 2025)

Obligaciones reconocidas netas y pagos realizados, acumulados mes a mes, por sección del Estado, tomados de las
Estadísticas de ejecución del Presupuesto (art. 135 LGP) de la IGAE de enero a diciembre de 2025
(fuentes/igae/mensual/mensual_MM-25.pdf, tablas «Presupuesto de gastos · Estado de ejecución. Secciones», en miles de euros).
Cada edición trae también la misma cifra acumulada del año anterior, así que de las doce ediciones de 2025 salen los doce
cierres mensuales de 2025 y, como comparación, los de 2024 tal como los publicó la edición de 2025 (REGISTRO B31).

Se pasa a ministerio actual con datos/secciones_ministerio_actual.csv (solo secciones «Ministerio»). 2024 y 2025 tienen
continuidad directa en los 22 y el mismo presupuesto de base (el de 2023 prorrogado), así que son comparables.
Las cifras de 2025 son provisionales. Es calendario de reconocimiento, no de pago al destinatario final.

Entradas: fuentes/igae/mensual/mensual_01-25.pdf … mensual_12-25.pdf (texto en fuentes/igae/_texto/, con pdftotext -layout),
          datos/mensual_secciones.csv, datos/liquidacion_secciones.csv, datos/secciones_ministerio_actual.csv
Salidas:  datos/mensual_seccion_mes.csv, datos/mensual_ministerio_mes.csv, datos/mensual_resumen.csv,
          datos/controles_mensual.csv, preguntas.md (marcas <!-- tabla:mensual_… -->)
Uso: python scripts/28_mensual_2025.py   (ejecutar después del 18, que aporta f, m, p, corto, leer, escribir)
"""
import importlib.util
import re
import subprocess
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datos"
DOC = RAIZ / "preguntas.md"
PDFS = RAIZ / "fuentes" / "igae" / "mensual"
TXT = RAIZ / "fuentes" / "igae" / "_texto"
MESES = list(range(1, 13))
NOMBRE_MES = ["", "ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
TODOS = "22 ministerios"

spec = importlib.util.spec_from_file_location("s18", Path(__file__).with_name("18_catastrofes.py"))
s18 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s18)
f, m, p, corto, leer, escribir = s18.f, s18.m, s18.p, s18.corto, s18.leer, s18.escribir


def num(s):
    s = s.strip()
    if s in ("-", ""):
        return 0
    return int(s.replace(".", "")) if re.fullmatch(r"-?[\d.]+", s) else None


def texto(mes):
    t = TXT / f"mensual_{mes:02d}-25.txt"
    if not t.exists():
        TXT.mkdir(parents=True, exist_ok=True)
        subprocess.run(["pdftotext", "-layout", str(PDFS / f"mensual_{mes:02d}-25.pdf"), str(t)], check=True,
                       stderr=subprocess.DEVNULL)
    return t.read_text(encoding="utf-8").split("\f")


def leer_mes(mes, abrev):
    """{(tipo_pagina, nombre_abreviado): [valores columnas 1..12]} y páginas usadas."""
    out, pags = {}, {"A": [], "B": []}
    for i, pg in enumerate(texto(mes), 1):
        if "ESTADO DE EJECUCIÓN. SECCIONES" not in pg or "PRESUPUESTO DE GASTOS" not in pg or "HASTA EL" not in pg:
            continue
        tipo = "A" if "CRÉDITOS DEFINITIVOS" in pg else ("B" if "PAGOS REALIZADOS" in pg else None)
        if tipo is None:
            continue
        pags[tipo].append(i)
        for linea in pg.split("\n"):
            toks = [x for x in re.split(r"\s{2,}", linea.strip()) if x]
            if len(toks) < 10:
                continue
            nombre = toks[0]
            if nombre in abrev or nombre == "TOTALES":
                vals = [num(x) if re.fullmatch(r"-?[\d.]+|-", x) else None for x in toks[1:]]
                out[(tipo, nombre)] = (toks[1:], vals)
    return out, pags


def main():
    sec = {r["seccion_abreviada"]: r for r in leer(DATOS / "mensual_secciones.csv")}
    ma = {(int(r["anio"]), r["codigo_seccion"]): r for r in leer(DATOS / "secciones_ministerio_actual.csv")}
    ctrl = []

    def control(que, a, b, tol=0, nota=""):
        ctrl.append(dict(control=que, valor_a=a, valor_b=b, diferencia=a - b, tolerancia=tol,
                         correcto="sí" if abs(a - b) <= tol else "NO", nota=nota))

    filas, tot = [], {}
    for mes in MESES:
        datos, pags = leer_mes(mes, set(sec) | {"TOTALES"})
        fuente = (f"IGAE, Estadísticas de ejecución del Presupuesto (art. 135 LGP), {NOMBRE_MES[mes]} 2025, "
                  f"pp. {', '.join(map(str, pags['A'] + pags['B']))} (miles de euros)")
        control(f"{NOMBRE_MES[mes]} 2025 · páginas de secciones encontradas (2 + 2)", len(pags["A"]) + len(pags["B"]), 4)
        for nom, r in sec.items():
            a, b = datos.get(("A", nom)), datos.get(("B", nom))
            control(f"{NOMBRE_MES[mes]} 2025 · {nom[:30]} · fila encontrada con 11 valores", int(bool(a and b and len(a[0]) == 11 and len(b[0]) == 11)), 1)
            if not (a and b):
                continue
            for k, anio in ((0, 2025), (1, 2024)):
                v = lambda x, i: (x[1][i] or 0) * 1000
                filas.append(dict(
                    anio=anio, mes=mes, codigo_seccion=r["codigo_seccion"], seccion=r["seccion"],
                    creditos_definitivos=v(a, k), gastos_comprometidos=v(a, 3 + k), obligaciones=v(a, 6 + k),
                    pagos=v(b, 0 + k), pendiente_pago=v(b, 3 + k),
                    dato="provisional" if anio == 2025 else "comparativo de 2024 publicado en la edición de 2025",
                    fuente=fuente))
        ta, tb = datos[("A", "TOTALES")], datos[("B", "TOTALES")]
        for k, anio in ((0, 2025), (1, 2024)):
            tot[(anio, mes)] = dict(obligaciones=(ta[1][6 + k] or 0) * 1000, pagos=(tb[1][0 + k] or 0) * 1000,
                                    definitivos=(ta[1][0 + k] or 0) * 1000)
            s_ob = sum(x["obligaciones"] for x in filas if x["anio"] == anio and x["mes"] == mes)
            s_pa = sum(x["pagos"] for x in filas if x["anio"] == anio and x["mes"] == mes)
            control(f"{NOMBRE_MES[mes]} {anio} · suma de secciones = TOTALES (obligaciones)", s_ob, tot[(anio, mes)]["obligaciones"], 1000,
                    "la fuente da miles de euros redondeados")
            control(f"{NOMBRE_MES[mes]} {anio} · suma de secciones = TOTALES (pagos)", s_pa, tot[(anio, mes)]["pagos"], 1000)
    escribir(DATOS / "mensual_seccion_mes.csv", filas,
             ["anio", "mes", "codigo_seccion", "seccion", "creditos_definitivos", "gastos_comprometidos", "obligaciones",
              "pagos", "pendiente_pago", "dato", "fuente"])

    # --- controles contra otras fuentes del proyecto
    F = {(x["anio"], x["mes"], x["codigo_seccion"]): x for x in filas}
    for cod, r in ((r["codigo_seccion"], r) for r in sec.values()):
        x = F.get((2025, 12, cod))
        if x:
            control(f"dic 2025 · sección {cod} · obligaciones = datos/mensual_secciones.csv", x["obligaciones"], f(r["obligaciones"]), 1000)
            control(f"dic 2025 · sección {cod} · pagos = datos/mensual_secciones.csv", x["pagos"], f(r["pagos"]), 1000)
    liq = {r["codigo_seccion"]: r for r in leer(DATOS / "liquidacion_secciones.csv") if r["anio"] == "2024"}
    for cod, r in liq.items():
        x = F.get((2024, 12, cod))
        if x:
            control(f"dic 2024 (comparativo de la edición de 2025) · sección {cod} · obligaciones = liquidación 2024",
                    x["obligaciones"], f(r["obligaciones"]), 1000)

    # --- por ministerio actual
    acum = defaultdict(lambda: [0.0, 0.0, 0.0])
    for x in filas:
        r = ma.get((x["anio"], x["codigo_seccion"]))
        if not r or r["tipo"] != "Ministerio":
            continue
        for mi in (r["ministerio_actual"], TODOS):
            a = acum[(mi, x["anio"], x["mes"])]
            a[0] += x["obligaciones"]
            a[1] += x["pagos"]
            a[2] += x["creditos_definitivos"]
    mins = sorted({k[0] for k in acum if k[0] != TODOS})
    out = []
    for mi in mins + [TODOS]:
        for anio in (2024, 2025):
            ant = 0.0
            fin = acum[(mi, anio, 12)][0]
            for mes in MESES:
                o, pa, cd = acum[(mi, anio, mes)]
                out.append(dict(anio=anio, mes=mes, ministerio_actual=mi, obligaciones_acumuladas=o, pagos_acumulados=pa,
                                creditos_definitivos=cd, obligaciones_del_mes=o - ant,
                                pct_del_anio=round(100 * o / fin, 2) if fin else "",
                                pct_pagado=round(100 * pa / o, 2) if o else "",
                                dato="provisional" if anio == 2025 else "comparativo de 2024 publicado en la edición de 2025",
                                fuente="IGAE, Estadísticas de ejecución del Presupuesto (art. 135 LGP), 2025; secciones pasadas a ministerio actual con datos/secciones_ministerio_actual.csv"))
                ant = o
    escribir(DATOS / "mensual_ministerio_mes.csv", out,
             ["anio", "mes", "ministerio_actual", "obligaciones_acumuladas", "pagos_acumulados", "creditos_definitivos",
              "obligaciones_del_mes", "pct_del_anio", "pct_pagado", "dato", "fuente"])
    for anio in (2024, 2025):
        control(f"{anio} · suma de ministerios en diciembre = suma de secciones «Ministerio» de datos/mensual (dic)",
                acum[(TODOS, anio, 12)][0], sum(x["obligaciones"] for x in filas if x["anio"] == anio and x["mes"] == 12
                                              and ma.get((anio, x["codigo_seccion"])) and ma[(anio, x["codigo_seccion"])]["tipo"] == "Ministerio"), 1)
        for mi in mins:
            prev = 0.0
            for mes in MESES:
                o = acum[(mi, anio, mes)][0]
                control(f"{anio} · {corto(mi)} · {NOMBRE_MES[mes]} · acumulado no baja respecto al mes anterior (tolerancia 1 M€)",
                        min(o - prev, 0), 0, 1e6, "una bajada leve puede ser reintegro o anulación; solo se avisa si pasa de 1 M€")
                prev = o

    # --- resumen
    def pct(mi, anio, mes):
        fin = acum[(mi, anio, 12)][0]
        return 100 * acum[(mi, anio, mes)][0] / fin if fin else None

    res = []
    for mi in mins + [TODOS]:
        r = dict(ministerio_actual=mi)
        for anio in (2024, 2025):
            for mes in (3, 6, 9, 10, 11):
                v = pct(mi, anio, mes)
                r[f"pct_hasta_{NOMBRE_MES[mes]}_{anio}"] = None if v is None else round(v, 2)
            r[f"pct_nov_dic_{anio}"] = None if pct(mi, anio, 10) is None else round(100 - pct(mi, anio, 10), 2)
            r[f"pct_dic_{anio}"] = None if pct(mi, anio, 11) is None else round(100 - pct(mi, anio, 11), 2)
            r[f"obligaciones_{anio}"] = acum[(mi, anio, 12)][0]
        res.append(r)
    campos = (["ministerio_actual"] + [f"pct_hasta_{NOMBRE_MES[mes]}_{a}" for a in (2024, 2025) for mes in (3, 6, 9, 10, 11)]
              + [f"pct_{k}_{a}" for a in (2024, 2025) for k in ("nov_dic", "dic")] + [f"obligaciones_{a}" for a in (2024, 2025)])
    escribir(DATOS / "mensual_resumen.csv", res, campos)
    R = {r["ministerio_actual"]: r for r in res}

    # --- tablas
    pc = lambda x: "—" if x is None else f"{x:.1f}".replace(".", ",")
    T = {}
    t = ["| Mes (acumulado al fin del mes) | Obligaciones 2025, M€ | % del año 2025 | Obligaciones 2024, M€ | % del año 2024 |",
         "| --- | ---: | ---: | ---: | ---: |"]
    for mes in MESES:
        c = []
        for anio in (2025, 2024):
            o = acum[(TODOS, anio, mes)][0]
            c += [m(o), pc(pct(TODOS, anio, mes))]
        t.append(f"| {NOMBRE_MES[mes].capitalize()} | " + " | ".join(c) + " |")
    T["mensual_total"] = "\n".join(t)

    orden = sorted(mins, key=lambda mi: -(R[mi]["pct_nov_dic_2025"] or 0))
    t = ["| Ministerio actual | Hasta septiembre 2024, % | Hasta septiembre 2025, % | Noviembre-diciembre 2024, % | Noviembre-diciembre 2025, % | Solo diciembre 2024, % | Solo diciembre 2025, % |",
         "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for mi in orden + [TODOS]:
        b = "**" if mi == TODOS else ""
        r = R[mi]
        t.append(f"| {b}{corto(mi) if mi != TODOS else mi}{b} | {pc(r['pct_hasta_sep_2024'])} | {pc(r['pct_hasta_sep_2025'])} | "
                 f"{pc(r['pct_nov_dic_2024'])} | {pc(r['pct_nov_dic_2025'])} | {pc(r['pct_dic_2024'])} | {pc(r['pct_dic_2025'])} |")
    T["mensual_ministerio"] = "\n".join(t)

    texto_doc = DOC.read_text(encoding="utf-8")
    hechas = 0
    for nombre, tabla in T.items():
        texto_doc, n = re.subn(rf"<!-- tabla:{nombre} -->.*?<!-- /tabla -->",
                               lambda _: f"<!-- tabla:{nombre} -->\n{tabla}\n<!-- /tabla -->", texto_doc, flags=re.S)
        hechas += n
    DOC.write_text(texto_doc, encoding="utf-8")
    escribir(DATOS / "controles_mensual.csv", ctrl, ["control", "valor_a", "valor_b", "diferencia", "tolerancia", "correcto", "nota"])
    malos = [c for c in ctrl if c["correcto"] != "sí"]
    print(f"{len(filas)} filas por sección; {len(out)} por ministerio; {len(ctrl)} controles, {len(malos)} incorrectos; "
          f"preguntas.md: {hechas} de {len(T)} marcas")
    for c in malos[:40]:
        print("  CONTROL INCORRECTO:", c["control"], c["valor_a"], c["valor_b"])
    for nombre, tabla in T.items():
        print(f"\n[{nombre}]\n{tabla}")


if __name__ == "__main__":
    main()
