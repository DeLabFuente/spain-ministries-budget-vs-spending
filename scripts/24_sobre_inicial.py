"""Pregunta 7 · ¿Qué ministerios gastan sistemáticamente más de lo presupuestado inicialmente? (2017-2025)

Por ministerio actual y año: obligaciones reconocidas sobre créditos iniciales del Estado, y de dónde sale el crédito
que se añade (modificaciones por tipo, en % del crédito inicial). El crédito inicial es el del presupuesto aprobado
o, en los años de prórroga (2019, 2020, 2024 y 2025), el prorrogado.

«Sistemáticamente» = por encima del 100 % en todos los años comparables (los de continuidad directa), con cinco o
más años comparables. Con menos años no se concluye (REGISTRO B27). Agricultura 2017-2018 no tiene créditos
iniciales (Estado reconstruido).

Entradas (datos/): secciones_ministerio_actual.csv, ficha_resumen.csv (continuidad y control)
Salidas:
  datos/sobre_inicial_ministerio.csv   ministerio × año, más la fila «22 ministerios»
  datos/sobre_inicial_resumen.csv      ministerio: años comparables, años por encima del 100 %, mínimo, máximo y
                                       modificaciones acumuladas por tipo en los años comparables
  datos/controles_sobre_inicial.csv    cuadres
  preguntas.md                       tablas entre las marcas <!-- tabla:sobre_inicial_… --> y <!-- /tabla -->
Uso: python scripts/24_sobre_inicial.py
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
MIN_ANIOS = 5
MODS = [("creditos_extraordinarios_suplementos", "Créd. extraord. y suplementos"), ("ampliaciones", "Ampliaciones"),
        ("transferencias", "Transferencias"), ("incorporacion_remanentes", "Remanentes"),
        ("generaciones_ingresos", "Generaciones"), ("bajas_otras_modificaciones", "Bajas y otras")]
CAMPOS = ["creditos_iniciales", *[k for k, _ in MODS], "creditos_definitivos", "obligaciones"]

spec = importlib.util.spec_from_file_location("s18", Path(__file__).with_name("18_catastrofes.py"))
s18 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s18)
f, m, p, corto, leer, escribir = s18.f, s18.m, s18.p, s18.corto, s18.leer, s18.escribir


def main():
    res = {(r["ministerio_actual"], int(r["anio"])): r for r in leer(DATOS / "ficha_resumen.csv")}
    ag = defaultdict(lambda: defaultdict(float))
    n_sec = defaultdict(int)
    prorroga = {}
    for r in leer(DATOS / "secciones_ministerio_actual.csv"):
        if r["tipo"] != "Ministerio":
            continue
        prorroga[int(r["anio"])] = r["presupuesto"]
        for mi in (r["ministerio_actual"], TODOS):
            n_sec[(mi, int(r["anio"]))] += 1
            for c in CAMPOS:
                ag[(mi, int(r["anio"]))][c] += f(r[c])

    ctrl = []

    def control(que, a, b, tol, nota=""):
        ctrl.append(dict(control=que, valor_a=a, valor_b=b, diferencia=a - b, tolerancia=tol,
                         correcto="sí" if abs(a - b) <= tol else "NO", nota=nota))

    filas = []
    for (mi, a), v in sorted(ag.items(), key=lambda x: (x[0][1], x[0][0] == TODOS, x[0][0])):
        cont = res[(mi, a)]["continuidad_estado"] if (mi, a) in res else ""
        fila = dict(anio=a, presupuesto=prorroga[a],
                    dato="provisional (mensual de diciembre)" if a == ULTIMO else "definitivo (liquidación)",
                    ministerio_actual=mi, continuidad=cont, **{c: v[c] for c in CAMPOS},
                    pct_obligaciones_sobre_iniciales=round(100 * v["obligaciones"] / v["creditos_iniciales"], 2),
                    comparable="sí" if mi == TODOS or cont == "directa" else "no",
                    fuente="IGAE, liquidación del Presupuesto del Estado, vol. I; 2025: estadística mensual de "
                           "diciembre, provisional (datos/secciones_ministerio_actual.csv)")
        filas.append(fila)
        control(f"{a} · {corto(mi)} · iniciales + modificaciones = definitivos",
                v["creditos_iniciales"] + sum(v[k] for k, _ in MODS), v["creditos_definitivos"], 20000 * n_sec[(mi, a)],
                "cada columna viene redondeada a miles de euros")
        if mi != TODOS and (mi, a) in res and cont != "reconstruido":
            control(f"{a} · {corto(mi)} · créditos iniciales = ficha_resumen.csv", v["creditos_iniciales"],
                    f(res[(mi, a)]["estado_creditos_iniciales"]), 1)
            control(f"{a} · {corto(mi)} · obligaciones = ficha_resumen.csv", v["obligaciones"],
                    f(res[(mi, a)]["estado_obligaciones"]), 1)
    escribir(DATOS / "sobre_inicial_ministerio.csv", filas,
             ["anio", "presupuesto", "dato", "ministerio_actual", "continuidad", "comparable", *CAMPOS,
              "pct_obligaciones_sobre_iniciales", "fuente"])
    F = {(x["ministerio_actual"], x["anio"]): x for x in filas}
    mins = sorted({x["ministerio_actual"] for x in filas if x["ministerio_actual"] != TODOS and (x["ministerio_actual"], ULTIMO) in F})
    ratio = lambda x: 100 * x["obligaciones"] / x["creditos_iniciales"]

    resumen = []
    for mi in mins + [TODOS]:
        xs = [F[(mi, a)] for a in ANIOS if (mi, a) in F and F[(mi, a)]["comparable"] == "sí"]
        ini = sum(x["creditos_iniciales"] for x in xs)
        rs = [ratio(x) for x in xs]
        v = dict(ministerio_actual=mi, anios_comparables=len(xs), primer_anio=xs[0]["anio"], ultimo_anio=xs[-1]["anio"],
                 anios_por_encima_de_100=sum(1 for r in rs if r > 100), pct_minimo=round(min(rs), 2), pct_maximo=round(max(rs), 2),
                 pct_acumulado=round(100 * sum(x["obligaciones"] for x in xs) / ini, 2),
                 sistematico=("sí" if len(xs) >= MIN_ANIOS and all(r > 100 for r in rs)
                              else "no" if len(xs) >= MIN_ANIOS else f"menos de {MIN_ANIOS} años comparables"))
        for k, _ in MODS:
            v["pct_" + k] = round(100 * sum(x[k] for x in xs) / ini, 2)
        v["_ini"], v["_xs"] = ini, xs
        resumen.append(v)
    escribir(DATOS / "sobre_inicial_resumen.csv", resumen,
             ["ministerio_actual", "anios_comparables", "primer_anio", "ultimo_anio", "anios_por_encima_de_100", "pct_minimo",
              "pct_maximo", "pct_acumulado", "sistematico", *["pct_" + k for k, _ in MODS]])
    escribir(DATOS / "controles_sobre_inicial.csv", ctrl,
             ["control", "valor_a", "valor_b", "diferencia", "tolerancia", "correcto", "nota"])
    R = {v["ministerio_actual"]: v for v in resumen}
    pc = lambda x: f"{x:.1f}".replace(".", ",")
    sg = lambda x: ("+" if x >= 0 else "−") + f"{abs(x):.1f}".replace(".", ",")

    T = {}
    col = lambda a: (str(a) if a < ULTIMO else f"{a} (prov.)") + (" P" if prorroga[a] != "aprobado" else "")
    orden = sorted(mins, key=lambda n: (-R[n]["anios_por_encima_de_100"] / R[n]["anios_comparables"], -R[n]["anios_comparables"],
                                        -R[n]["pct_acumulado"]))
    t = ["| Ministerio actual | " + " | ".join(col(a) for a in ANIOS) + " | Años por encima del 100 % |",
         "| --- | " + " | ".join("---:" for _ in ANIOS) + " | ---: |"]
    for mi in orden + [TODOS]:
        b = "**" if mi == TODOS else ""
        c = [pc(ratio(F[(mi, a)])) if (mi, a) in F and F[(mi, a)]["comparable"] == "sí" else "—" for a in ANIOS]
        t.append(f"| {b}{corto(mi)}{b} | " + " | ".join(c) + f" | {R[mi]['anios_por_encima_de_100']} de {R[mi]['anios_comparables']} |")
    T["sobre_inicial_serie"] = "\n".join(t)

    largos = [mi for mi in orden if R[mi]["anios_comparables"] >= MIN_ANIOS]
    t = ["| Ministerio actual | Años comparables | Obligaciones / iniciales, % | " + " | ".join(et for _, et in MODS) + " | Sin reconocer |",
         "| --- | --- | ---: | " + " | ".join("---:" for _ in MODS) + " | ---: |"]
    for mi in largos + [TODOS]:
        v, b = R[mi], "**" if mi == TODOS else ""
        sin = 100 * sum(x["creditos_definitivos"] - x["obligaciones"] for x in v["_xs"]) / v["_ini"]
        t.append(f"| {b}{corto(mi)}{b} | {v['anios_comparables']} ({v['primer_anio']}-{v['ultimo_anio']}) | {b}{pc(v['pct_acumulado'])}{b} | "
                 + " | ".join(sg(v["pct_" + k]) for k, _ in MODS) + f" | {sg(-sin)} |")
    T["sobre_inicial_origen"] = "\n".join(t)

    texto = DOC.read_text(encoding="utf-8")
    hechas = 0
    for nombre, tabla in T.items():
        texto, n = re.subn(rf"<!-- tabla:{nombre} -->.*?<!-- /tabla -->",
                           lambda _: f"<!-- tabla:{nombre} -->\n{tabla}\n<!-- /tabla -->", texto, flags=re.S)
        hechas += n
    DOC.write_text(texto, encoding="utf-8")

    malos = [c for c in ctrl if c["correcto"] != "sí"]
    print(f"{len(filas)} filas en sobre_inicial_ministerio.csv; {len(ctrl)} controles, {len(malos)} incorrectos; "
          f"preguntas.md: {hechas} de {len(T)} marcas")
    for c in malos:
        print("  CONTROL INCORRECTO:", c["control"], c["valor_a"], c["valor_b"])
    for nombre, tabla in T.items():
        print(f"\n[{nombre}]\n{tabla}")


if __name__ == "__main__":
    main()
