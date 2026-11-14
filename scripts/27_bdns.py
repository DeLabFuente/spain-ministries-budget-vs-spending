"""Pregunta 10 · ¿Qué ayudas y subvenciones concede cada ministerio según la BDNS? (2022-2025)

Agregados de las concesiones del Estado (tipoAdministracion = C) de la Base de Datos Nacional de Subvenciones (BDNS,
API pública SNPSAP de infosubvenciones.es), por año de concesión, ministerio e instrumento. La BDNS solo devuelve
concesiones del Estado desde 2022 (0 en 2017-2021; REGISTRO A39). Se leyó día a día (1.461 días) desde el navegador
integrado, sumando en memoria: NO se guardó ningún registro individual (cada registro trae el nombre del beneficiario,
que se descarta) y solo se conserva el agregado en fuentes/bdns/bdns_agregados.json.

Cuatro días de 2025 (03/11, 01/12, 18/12 y 19/12) tienen 6.461.534 concesiones en total; no se pueden leer por la
paginación de la API, así que solo se contaron (por ministerio e instrumento) y su importe es desconocido (REGISTRO B30).

Lo concedido no es lo obligado: la BDNS registra concesiones (fecha de concesión), no obligaciones del presupuesto, y
mezcla instrumentos que no son gasto (garantías, ventajas fiscales) o se mueven por otro capítulo (préstamos). La
comparación con los capítulos 4 y 7 del Estado es solo una referencia de cobertura, no una conciliación.

Entradas: fuentes/bdns/bdns_agregados.json, powerbi/dim_ministerio.csv, datos/ficha_capitulos.csv, datos/ficha_resumen.csv
Salidas:  datos/bdns_ministerio.csv, datos/bdns_resumen.csv, datos/controles_bdns.csv, preguntas.md (marcas
          <!-- tabla:bdns_… -->)
Uso: python scripts/27_bdns.py   (ejecutar después del 18, que aporta f, m, p, corto, leer, escribir)
"""
import importlib.util
import json
import re
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datos"
DOC = RAIZ / "preguntas.md"
ANIOS = [2022, 2023, 2024, 2025]
ULTIMO = ANIOS[-1]
TODOS = "22 ministerios"
# Recuentos que devuelve la propia API para tipoAdministracion=C (REGISTRO A39), contrastados con lo leído día a día.
RECUENTO_API = {2022: 281165, 2023: 365226, 2024: 358685, 2025: 13514744}
DIAS = {2022: 365, 2023: 365, 2024: 366, 2025: 365}
SOLO_RECUENTO_2025 = 6461534

INSTR = {
    "SUBVENCIÓN Y ENTREGA DINERARIA SIN CONTRAPRESTACIÓN": "Subvención y entrega dineraria",
    "PRÉSTAMO": "Préstamo",
    "GARANTÍA": "Garantía",
    "VENTAJA FISCAL": "Ventaja fiscal",
    "OTROS INSTRUMENTOS DE AYUDA": "Otros instrumentos de ayuda",
    "APORTACIÓN DE FINANCIACIÓN RIESGO": "Aportación de financiación de riesgo",
}
DIRECTA = {"Subvención y entrega dineraria", "Otros instrumentos de ayuda", "Aportación de financiación de riesgo"}

spec = importlib.util.spec_from_file_location("s18", Path(__file__).with_name("18_catastrofes.py"))
s18 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s18)
f, m, p, corto, leer, escribir = s18.f, s18.m, s18.p, s18.corto, s18.leer, s18.escribir


def n_(x):
    return f"{int(x):,}".replace(",", ".")


def main():
    d = json.loads((RAIZ / "fuentes" / "bdns" / "bdns_agregados.json").read_text(encoding="utf-8"))
    dim = {r["ministerio"].upper(): r["ministerio"] for r in leer(RAIZ / "powerbi" / "dim_ministerio.csv")
           if r["es_ministerio"] == "sí"}
    ctrl = []

    def control(que, a, b, tol=0, nota=""):
        ctrl.append(dict(control=que, valor_a=a, valor_b=b, diferencia=a - b, tolerancia=tol,
                         correcto="sí" if abs(a - b) <= tol else "NO", nota=nota))

    # --- agregado normalizado: la API trae dos grafías del mismo instrumento («y» y «Y»)
    acum = defaultdict(lambda: [0, 0.0, 0])
    for k, (n, imp, sin) in d["agg"].items():
        a, nom, ins = k.split("|")
        a = int(a)
        mi = dim.get(nom.upper())
        ins_n = INSTR.get(ins.upper())
        control(f"{a} · {corto(nom.title())} · {ins[:20]} · ministerio e instrumento reconocidos",
                int(mi is not None and ins_n is not None), 1)
        v = acum[(a, mi, ins_n)]
        v[0] += n
        v[1] += imp
        v[2] += sin
    filas = []
    for (a, mi, ins), (n, imp, sin) in sorted(acum.items(), key=lambda x: (x[0][0], x[0][1], x[0][2])):
        filas.append(dict(anio=a, ministerio_actual=mi, instrumento=ins, concesiones=n, importe=round(imp, 2),
                          concesiones_sin_importe=sin, importe_completo="sí" if sin == 0 else "no",
                          fuente="BDNS, API SNPSAP (infosubvenciones.es), concesiones del Estado por fecha de concesión; "
                                 "agregado propio sin beneficiarios"))
    escribir(DATOS / "bdns_ministerio.csv", filas,
             ["anio", "ministerio_actual", "instrumento", "concesiones", "importe", "concesiones_sin_importe",
              "importe_completo", "fuente"])

    # --- controles de lectura
    for a in ANIOS:
        n_agg = sum(x["concesiones"] for x in filas if x["anio"] == a)
        c = d["ctl"][f"{a}|lectura"]
        so = d["ctl"].get(f"{a}|solo-recuento", {"dias": 0, "total": 0, "vistos": 0, "unicos": 0, "ok": 0})
        control(f"{a} · concesiones agregadas = recuento de la API", n_agg, RECUENTO_API[a], 0)
        control(f"{a} · concesiones leídas + solo contadas = recuento de la API", c["total"] + so["total"], RECUENTO_API[a], 0)
        control(f"{a} · registros leídos = registros únicos (sin repetidos)", c["vistos"], c["unicos"], 0)
        control(f"{a} · días controlados = días del año", c["dias"] + so["dias"], DIAS[a], 0)
        control(f"{a} · días con lectura correcta = días leídos", c["ok"] + so["ok"], c["dias"] + so["dias"], 0)
    sin_total = sum(x["concesiones_sin_importe"] for x in filas if x["anio"] == ULTIMO)
    control("2025 · concesiones de los 4 días solo contados = 6.461.534 (recuento de la API por día)",
            d["ctl"]["2025|solo-recuento"]["total"], SOLO_RECUENTO_2025, 0)
    control("2025 · concesiones sin importe en el agregado = concesiones de los 4 días solo contados", sin_total, SOLO_RECUENTO_2025, 0,
            "todas las concesiones sin importe vienen de esos cuatro días; en los días leídos no falta ningún importe")
    control("años con concesiones del Estado antes de 2022 = 0 (REGISTRO A39)", min(int(k.split("|")[0]) for k in d["agg"]), 2022, 0)
    sin_leidas = 0

    # --- resumen por ministerio y año
    cap = defaultdict(float)
    for r in leer(DATOS / "ficha_capitulos.csv"):
        if r["ambito"] == "Estado" and r["capitulo"] in ("4", "7"):
            cap[(r["ministerio_actual"], int(r["anio"]))] += f(r["obligaciones"])
    cont = {(r["ministerio_actual"], int(r["anio"])): r["continuidad_estado"] for r in leer(DATOS / "ficha_resumen.csv")}
    agr = defaultdict(lambda: defaultdict(float))
    for x in filas:
        for mi in (x["ministerio_actual"], TODOS):
            g = agr[(mi, x["anio"])]
            g["concesiones"] += x["concesiones"]
            g["sin_importe"] += x["concesiones_sin_importe"]
            g["importe_total"] += x["importe"]
            if x["instrumento"] in DIRECTA:
                g["directa_n"] += x["concesiones"]
                g["directa"] += x["importe"]
                g["directa_sin"] += x["concesiones_sin_importe"]
            elif x["instrumento"] == "Préstamo":
                g["prestamo"] += x["importe"]
            elif x["instrumento"] == "Garantía":
                g["garantia"] += x["importe"]
            elif x["instrumento"] == "Ventaja fiscal":
                g["ventaja"] += x["importe"]
    resumen = []
    for (mi, a), g in sorted(agr.items(), key=lambda x: (x[0][1], x[0][0] == TODOS, x[0][0])):
        c47 = cap.get((mi, a)) if mi != TODOS else sum(cap.get((q, a), 0) for q in {k[0] for k in cap})
        cn = cont.get((mi, a), "") if mi != TODOS else ""
        ok_cmp = a <= 2024 and (mi == TODOS or cn == "directa") and c47
        resumen.append(dict(
            anio=a, ministerio_actual=mi, continuidad=cn, concesiones=int(g["concesiones"]),
            concesiones_sin_importe=int(g["sin_importe"]), subvenciones_y_ayudas_directas=round(g["directa"], 2),
            concesiones_ayudas_directas=int(g["directa_n"]), prestamos=round(g["prestamo"], 2),
            garantias=round(g["garantia"], 2), ventajas_fiscales=round(g["ventaja"], 2),
            importe_total_leido=round(g["importe_total"], 2),
            obligaciones_cap4_cap7_estado=round(c47, 2) if c47 else "",
            pct_ayudas_directas_sobre_cap4_cap7=round(100 * g["directa"] / c47, 2) if ok_cmp else "",
            importe_completo="sí" if g["sin_importe"] == 0 else "no",
            fuente="BDNS (API SNPSAP); obligaciones: IGAE, liquidación del Presupuesto del Estado (capítulos 4 y 7, Estado)"))
    escribir(DATOS / "bdns_resumen.csv", resumen,
             ["anio", "ministerio_actual", "continuidad", "concesiones", "concesiones_sin_importe",
              "subvenciones_y_ayudas_directas", "concesiones_ayudas_directas", "prestamos", "garantias",
              "ventajas_fiscales", "importe_total_leido", "obligaciones_cap4_cap7_estado",
              "pct_ayudas_directas_sobre_cap4_cap7", "importe_completo", "fuente"])
    R = {(r["ministerio_actual"], r["anio"]): r for r in resumen}
    for a in ANIOS:
        s = sum(r["importe_total_leido"] for r in resumen if r["anio"] == a and r["ministerio_actual"] != TODOS)
        control(f"{a} · suma de ministerios = total (importe leído)", s, R[(TODOS, a)]["importe_total_leido"], 1)
        s2 = sum(r["subvenciones_y_ayudas_directas"] + r["prestamos"] + r["garantias"] + r["ventajas_fiscales"]
                 for r in resumen if r["anio"] == a and r["ministerio_actual"] == TODOS)
        otros = sum(x["importe"] for x in filas if x["anio"] == a) - s2
        control(f"{a} · importe por instrumento cubre el total (sin instrumentos no agrupados)", otros, 0, 1)
    escribir(DATOS / "controles_bdns.csv", ctrl, ["control", "valor_a", "valor_b", "diferencia", "tolerancia", "correcto", "nota"])

    # --- tablas
    pcs = lambda x: "—" if x in (None, "") else f"{float(x):.1f}".replace(".", ",")
    T = {}
    t = ["| Año | Concesiones | De ellas, sin importe conocido | Subvenciones y ayudas directas, M€ | Préstamos, M€ | Garantías, M€ | Ventajas fiscales, M€ |",
         "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for a in ANIOS:
        g = R[(TODOS, a)]
        t.append(f"| {a}{' †' if g['concesiones_sin_importe'] else ''} | {n_(g['concesiones'])} | {n_(g['concesiones_sin_importe'])} | "
                 f"{m(g['subvenciones_y_ayudas_directas'])} | {m(g['prestamos'])} | {m(g['garantias'])} | {m(g['ventajas_fiscales'])} |")
    T["bdns_total"] = "\n".join(t)

    mins = sorted({r["ministerio_actual"] for r in resumen if r["ministerio_actual"] != TODOS},
                  key=lambda mi: -sum(R[(mi, a)]["subvenciones_y_ayudas_directas"] for a in ANIOS if (mi, a) in R))
    t = ["| Ministerio actual | 2022 | 2023 | 2024 | 2025 † | Concesiones 2025 | De ellas, sin importe (†) |",
         "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for mi in mins + [TODOS]:
        b = "**" if mi == TODOS else ""
        c = [m(R[(mi, a)]["subvenciones_y_ayudas_directas"]) if (mi, a) in R else "—" for a in ANIOS]
        g25 = R.get((mi, ULTIMO))
        t.append(f"| {b}{corto(mi)}{b} | " + " | ".join(c) + f" | {n_(g25['concesiones'])} | {n_(g25['concesiones_sin_importe'])} |")
    T["bdns_ministerio"] = "\n".join(t)

    t = ["| Ministerio actual | 2022 | 2023 | 2024 | Concesiones 2024 (todos los instrumentos) |", "| --- | ---: | ---: | ---: | ---: |"]
    for mi in sorted(mins, key=lambda mi: -(R[(mi, 2024)]["pct_ayudas_directas_sobre_cap4_cap7"] or 0)
                     if R[(mi, 2024)]["pct_ayudas_directas_sobre_cap4_cap7"] != "" else 1e9):
        c = [pcs(R[(mi, a)]["pct_ayudas_directas_sobre_cap4_cap7"]) if (mi, a) in R else "—" for a in (2022, 2023, 2024)]
        t.append(f"| {corto(mi)} | " + " | ".join(c) + f" | {n_(R[(mi, 2024)]['concesiones']) if (mi, 2024) in R else '—'} |")
    g = R[(TODOS, 2024)]
    t.append("| **Total (22 ministerios)** | " + " | ".join(pcs(R[(TODOS, a)]["pct_ayudas_directas_sobre_cap4_cap7"]) for a in (2022, 2023, 2024))
             + f" | {n_(g['concesiones'])} |")
    T["bdns_vs_cap47"] = "\n".join(t)

    texto = DOC.read_text(encoding="utf-8")
    hechas = 0
    for nombre, tabla in T.items():
        texto, n = re.subn(rf"<!-- tabla:{nombre} -->.*?<!-- /tabla -->",
                           lambda _: f"<!-- tabla:{nombre} -->\n{tabla}\n<!-- /tabla -->", texto, flags=re.S)
        hechas += n
    DOC.write_text(texto, encoding="utf-8")
    malos = [c for c in ctrl if c["correcto"] != "sí"]
    print(f"{len(filas)} filas; {len(resumen)} filas de resumen; {len(ctrl)} controles, {len(malos)} incorrectos; "
          f"preguntas.md: {hechas} de {len(T)} marcas; sin importe leídas: {sin_leidas}")
    for c in malos:
        print("  CONTROL INCORRECTO:", c["control"], c["valor_a"], c["valor_b"])
    for nombre, tabla in T.items():
        print(f"\n[{nombre}]\n{tabla}")


if __name__ == "__main__":
    main()
