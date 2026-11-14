"""Pregunta 6 · ¿Cuánto de lo reconocido queda sin pagar al cierre del año? (2017-2025)

Por ministerio actual y año: pendiente de pago = obligaciones reconocidas − pagos realizados, del presupuesto
corriente del Estado, al 31 de diciembre. Y por capítulo (2017-2024), para ver qué tipo de gasto se queda sin pagar.

No es deuda vencida ni retraso: lo pendiente se paga en el año siguiente como obligaciones de presupuestos cerrados,
que no están en los datos del proyecto. Por ministerio, las series solo usan los años con continuidad directa; los 22
se comparan en 2024 y 2025 (provisional) (REGISTRO B26).

Entradas (datos/): secciones_ministerio_actual.csv, liquidacion_seccion_capitulo.csv, ficha_resumen.csv
Salidas:
  datos/pendiente_pago_ministerio.csv   ministerio × año, más la fila «22 ministerios»
  datos/pendiente_pago_capitulo.csv     ministerio × año × capítulo (2017-2024), más «22 ministerios»
  datos/controles_pendiente_pago.csv    cuadres
  preguntas.md                        tablas entre las marcas <!-- tabla:pendiente_pago_… --> y <!-- /tabla -->
Uso: python scripts/23_pendiente_pago.py
"""
import importlib.util
import re
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datos"
DOC = RAIZ / "preguntas.md"
ANIOS = list(range(2017, 2026))
ULTIMO = ANIOS[-1]
TODOS = "22 ministerios"
CAPS = {"1": "Personal", "2": "Bienes y servicios", "3": "Gastos financieros", "4": "Transferencias corrientes",
        "5": "Fondo de contingencia", "6": "Inversiones reales", "7": "Transferencias de capital",
        "8": "Activos financieros", "9": "Pasivos financieros"}

spec = importlib.util.spec_from_file_location("s18", Path(__file__).with_name("18_catastrofes.py"))
s18 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s18)
f, m, p, corto, leer, escribir = s18.f, s18.m, s18.p, s18.corto, s18.leer, s18.escribir


def main():
    sec = {(int(r["anio"]), r["codigo_seccion"]): r for r in leer(DATOS / "secciones_ministerio_actual.csv")}
    res = {(r["ministerio_actual"], int(r["anio"])): r for r in leer(DATOS / "ficha_resumen.csv")}
    ag = defaultdict(lambda: [0.0, 0.0])
    for (a, c), r in sec.items():
        if r["tipo"] == "Ministerio":
            for mi in (r["ministerio_actual"], TODOS):
                ag[(mi, a)][0] += f(r["obligaciones"])
                ag[(mi, a)][1] += f(r["pagos"])
    cap = defaultdict(lambda: [0.0, 0.0])
    for r in leer(DATOS / "liquidacion_seccion_capitulo.csv"):
        info = sec[(int(r["anio"]), r["codigo_seccion"])]
        if info["tipo"] == "Ministerio":
            for mi in (info["ministerio_actual"], TODOS):
                cap[(mi, int(r["anio"]), r["capitulo"])][0] += f(r["obligaciones"])
                cap[(mi, int(r["anio"]), r["capitulo"])][1] += f(r["pagos"])

    ctrl = []

    def control(que, a, b, tol, nota=""):
        ctrl.append(dict(control=que, valor_a=a, valor_b=b, diferencia=a - b, tolerancia=tol,
                         correcto="sí" if abs(a - b) <= tol else "NO", nota=nota))

    filas = []
    for (mi, a), (o, pg) in sorted(ag.items(), key=lambda x: (x[0][1], x[0][0] == TODOS, x[0][0])):
        cont = res[(mi, a)]["continuidad_estado"] if (mi, a) in res else ""
        filas.append(dict(anio=a, dato="provisional (mensual de diciembre)" if a == ULTIMO else "definitivo (liquidación)",
                          ministerio_actual=mi, continuidad=cont, obligaciones=o, pagos=pg, pendiente_de_pago=o - pg,
                          pct_pendiente=round(100 * (o - pg) / o, 2) if o else None,
                          fuente="IGAE, liquidación del Presupuesto del Estado, vol. I; 2025: estadística mensual de "
                                 "diciembre, provisional (datos/secciones_ministerio_actual.csv)"))
        if mi != TODOS and (mi, a) in res and cont != "reconstruido":
            control(f"{a} · {corto(mi)} · obligaciones = ficha_resumen.csv", o, f(res[(mi, a)]["estado_obligaciones"]), 1)
            control(f"{a} · {corto(mi)} · pagos = ficha_resumen.csv", pg, f(res[(mi, a)]["estado_pagos"]), 1)
        if a < ULTIMO:
            for i, k in enumerate(("obligaciones", "pagos")):
                control(f"{a} · {corto(mi)} · {k}: suma de capítulos = sección",
                        sum(v[i] for (m2, a2, _), v in cap.items() if m2 == mi and a2 == a), (o, pg)[i], 1)
    escribir(DATOS / "pendiente_pago_ministerio.csv", filas,
             ["anio", "dato", "ministerio_actual", "continuidad", "obligaciones", "pagos", "pendiente_de_pago",
              "pct_pendiente", "fuente"])
    fcap = [dict(anio=a, ministerio_actual=mi, capitulo=c, capitulo_nombre=CAPS[c], obligaciones=o, pagos=pg,
                 pendiente_de_pago=o - pg, pct_pendiente=round(100 * (o - pg) / o, 2) if o else None)
            for (mi, a, c), (o, pg) in sorted(cap.items(), key=lambda x: (x[0][1], x[0][0] == TODOS, x[0][0], x[0][2]))]
    escribir(DATOS / "pendiente_pago_capitulo.csv", fcap,
             ["anio", "ministerio_actual", "capitulo", "capitulo_nombre", "obligaciones", "pagos", "pendiente_de_pago",
              "pct_pendiente"])
    escribir(DATOS / "controles_pendiente_pago.csv", ctrl,
             ["control", "valor_a", "valor_b", "diferencia", "tolerancia", "correcto", "nota"])
    F = {(x["ministerio_actual"], x["anio"]): x for x in filas}
    mins = sorted({x["ministerio_actual"] for x in filas if x["ministerio_actual"] != TODOS and (x["ministerio_actual"], ULTIMO) in F})
    col = lambda a: str(a) if a < ULTIMO else f"{a} (prov.)"
    pc = lambda x: "—" if x is None else f"{x:.1f}".replace(".", ",")
    pct = lambda x: 100 * x["pendiente_de_pago"] / x["obligaciones"]

    T = {}
    t = ["| Secciones ministeriales | " + " | ".join(col(a) for a in ANIOS) + " |", "| --- | " + " | ".join("---:" for _ in ANIOS) + " |"]
    t.append("| Obligaciones reconocidas | " + " | ".join(m(F[(TODOS, a)]["obligaciones"]) for a in ANIOS) + " |")
    t.append("| Pendiente de pago al cierre | " + " | ".join(m(F[(TODOS, a)]["pendiente_de_pago"]) for a in ANIOS) + " |")
    t.append("| **… en % de lo reconocido** | " + " | ".join(f"**{pc(pct(F[(TODOS, a)]))}**" for a in ANIOS) + " |")
    T["pendiente_pago_serie"] = "\n".join(t)

    ac = [a for a in ANIOS if a < ULTIMO]
    grupos = [("Transferencias de capital (capítulo 7)", ["7"]), ("Activos financieros (capítulo 8)", ["8"]),
              ("Transferencias corrientes (capítulo 4)", ["4"]), ("Inversiones reales (capítulo 6)", ["6"]),
              ("Bienes y servicios (capítulo 2)", ["2"]), ("Personal y resto (capítulos 1, 3, 5 y 9)", ["1", "3", "5", "9"])]
    t = ["| Pendiente de pago, por capítulo | " + " | ".join(str(a) for a in ac) + f" | % de lo reconocido en {ac[-1]} |",
         "| --- | " + " | ".join("---:" for _ in ac) + " | ---: |"]
    for et, cs in grupos:
        v = {a: [sum(cap[(TODOS, a, c)][i] for c in cs if (TODOS, a, c) in cap) for i in (0, 1)] for a in ac}
        t.append(f"| {et} | " + " | ".join(m(v[a][0] - v[a][1]) for a in ac) + f" | {p(v[ac[-1]][0] - v[ac[-1]][1], v[ac[-1]][0])} |")
    T["pendiente_pago_capitulo"] = "\n".join(t)

    a1 = ULTIMO - 1
    t = [f"| Ministerio actual | Pendiente {a1} | % de lo reconocido | Capítulo que más deja pendiente en {a1} | "
         f"Pendiente {ULTIMO} | % de lo reconocido |", "| --- | ---: | ---: | --- | ---: | ---: |"]
    for mi in sorted(mins, key=lambda n: -pct(F[(n, a1)])) + [TODOS]:
        x, y, b = F[(mi, a1)], F[(mi, ULTIMO)], "**" if mi == TODOS else ""
        pend = {c: cap[(mi, a1, c)][0] - cap[(mi, a1, c)][1] for c in CAPS if (mi, a1, c) in cap}
        c1 = max(pend, key=pend.get)
        t.append(f"| {b}{corto(mi)}{b} | {m(x['pendiente_de_pago'])} | {b}{pc(pct(x))}{b} | "
                 f"{CAPS[c1]} ({p(pend[c1], x['pendiente_de_pago'], 0)} %) | {m(y['pendiente_de_pago'])} | {pc(pct(y))} |")
    T["pendiente_pago_2024_2025"] = "\n".join(t)

    t = ["| Ministerio actual | " + " | ".join(col(a) for a in ANIOS) + " |", "| --- | " + " | ".join("---:" for _ in ANIOS) + " |"]
    for mi in sorted(mins, key=lambda n: -pct(F[(n, a1)])):
        c = [pc(pct(F[(mi, a)])) if (mi, a) in F and F[(mi, a)]["continuidad"] == "directa" else "—" for a in ANIOS]
        t.append(f"| {corto(mi)} | " + " | ".join(c) + " |")
    T["pendiente_pago_ministerio_serie"] = "\n".join(t)

    texto = DOC.read_text(encoding="utf-8")
    hechas = 0
    for nombre, tabla in T.items():
        texto, n = re.subn(rf"<!-- tabla:{nombre} -->.*?<!-- /tabla -->",
                           lambda _: f"<!-- tabla:{nombre} -->\n{tabla}\n<!-- /tabla -->", texto, flags=re.S)
        hechas += n
    DOC.write_text(texto, encoding="utf-8")

    malos = [c for c in ctrl if c["correcto"] != "sí"]
    print(f"{len(filas)} filas en pendiente_pago_ministerio.csv; {len(fcap)} en pendiente_pago_capitulo.csv; "
          f"{len(ctrl)} controles, {len(malos)} incorrectos; preguntas.md: {hechas} de {len(T)} marcas")
    for c in malos:
        print("  CONTROL INCORRECTO:", c["control"], c["valor_a"], c["valor_b"])
    for nombre, tabla in T.items():
        print(f"\n[{nombre}]\n{tabla}")


if __name__ == "__main__":
    main()
