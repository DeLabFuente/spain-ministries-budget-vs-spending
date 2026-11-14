"""Pregunta 4 · ¿Qué pasa con el crédito que no se gasta? Remanentes incorporados, crédito anulado y bajas (2017-2025)

Por sección del Estado y año, la liquidación da el crédito definitivo, las obligaciones y las modificaciones por tipo
(entre ellas la incorporación de remanentes y las bajas). Con eso se mide, para cada ministerio actual y año t:
  sin_reconocer                 crédito definitivo − obligaciones (el remanente de crédito del año)
  mrr_sin_reconocer             la parte que es del Mecanismo de Recuperación (servicio 50)
  incorporacion_anio_siguiente  la incorporación de remanentes del año t+1
  pct_incorporado               incorporacion_anio_siguiente / sin_reconocer
  sin_incorporar                sin_reconocer − incorporacion_anio_siguiente: lo que se anula al cierre
  bajas                         «bajas y otras modificaciones» del propio año (reducciones de crédito durante el año)

La fuente no dice de qué crédito sale cada remanente ni cuánto es del Mecanismo: se pone al lado el crédito del
Mecanismo sin reconocer el año anterior, sin atribuir. Por ministerio, el par de años t y t+1 solo es comparable si
el ministerio tiene continuidad directa los dos años (REGISTRO B25). 2025 es provisional y no tiene año siguiente.

Entradas (datos/): secciones_ministerio_actual.csv, mrr_secciones.csv, ficha_resumen.csv (continuidad y control)
Salidas:
  datos/remanentes_ministerio.csv   ministerio × año, más la fila «22 ministerios»
  datos/controles_remanentes.csv    cuadres
  preguntas.md                    tablas entre las marcas <!-- tabla:remanentes_… --> y <!-- /tabla -->
Uso: python scripts/22_remanentes.py
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
CAMPOS = ["creditos_iniciales", "incorporacion_remanentes", "bajas_otras_modificaciones", "creditos_definitivos", "obligaciones"]

spec = importlib.util.spec_from_file_location("s18", Path(__file__).with_name("18_catastrofes.py"))
s18 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s18)
f, m, p, corto, leer, escribir = s18.f, s18.m, s18.p, s18.corto, s18.leer, s18.escribir


def main():
    ag = defaultdict(lambda: defaultdict(float))
    for r in leer(DATOS / "secciones_ministerio_actual.csv"):
        if r["tipo"] != "Ministerio":
            continue
        for mi in (r["ministerio_actual"], TODOS):
            for c in CAMPOS:
                ag[(mi, int(r["anio"]))][c] += f(r[c])
    mrr = defaultdict(float)
    for r in leer(DATOS / "mrr_secciones.csv"):
        for mi in (r["ministerio_actual"], TODOS):
            mrr[(mi, int(r["anio"]))] += f(r["creditos_definitivos"]) - f(r["obligaciones"])
    res = {(r["ministerio_actual"], int(r["anio"])): r for r in leer(DATOS / "ficha_resumen.csv")}

    ctrl = []

    def control(que, a, b, tol, nota=""):
        ctrl.append(dict(control=que, valor_a=a, valor_b=b, diferencia=a - b, tolerancia=tol,
                         correcto="sí" if abs(a - b) <= tol else "NO", nota=nota))

    filas = []
    for (mi, a), v in sorted(ag.items(), key=lambda x: (x[0][1], x[0][0] == TODOS, x[0][0])):
        sig = ag.get((mi, a + 1))
        cont = res[(mi, a)]["continuidad_estado"] if (mi, a) in res else ""
        cont_sig = res[(mi, a + 1)]["continuidad_estado"] if (mi, a + 1) in res else ""
        fila = dict(anio=a, dato="provisional (mensual de diciembre)" if a == ULTIMO else "definitivo (liquidación)",
                    ministerio_actual=mi, continuidad=cont, creditos_definitivos=v["creditos_definitivos"],
                    obligaciones=v["obligaciones"], sin_reconocer=v["creditos_definitivos"] - v["obligaciones"],
                    mrr_sin_reconocer=mrr.get((mi, a)) if a >= 2021 else None,
                    incorporacion_remanentes=v["incorporacion_remanentes"], bajas=v["bajas_otras_modificaciones"])
        fila["pct_sin_reconocer"] = round(100 * fila["sin_reconocer"] / v["creditos_definitivos"], 2)
        if sig is not None:
            fila["incorporacion_anio_siguiente"] = sig["incorporacion_remanentes"]
            fila["pct_incorporado"] = (round(100 * sig["incorporacion_remanentes"] / fila["sin_reconocer"], 2)
                                       if fila["sin_reconocer"] > 0 else None)
            fila["sin_incorporar"] = fila["sin_reconocer"] - sig["incorporacion_remanentes"]
            fila["par_comparable"] = "sí" if mi == TODOS or (cont == "directa" and cont_sig == "directa") else "no"
        fila["fuente"] = ("IGAE, liquidación del Presupuesto del Estado, vol. I (modificaciones por sección); 2025: "
                          "estadística mensual de diciembre, provisional (datos/secciones_ministerio_actual.csv)")
        filas.append(fila)
        if mi != TODOS and (mi, a) in res and cont != "reconstruido":
            r = res[(mi, a)]
            control(f"{a} · {corto(mi)} · incorporación de remanentes = ficha_resumen.csv",
                    v["incorporacion_remanentes"], f(r["estado_incorporacion_remanentes"]), 1)
            control(f"{a} · {corto(mi)} · crédito sin reconocer = ficha_resumen.csv",
                    fila["sin_reconocer"], f(r["estado_creditos_definitivos"]) - f(r["estado_obligaciones"]), 1)
    for a in ANIOS:
        for c, k in (("incorporacion_remanentes", "incorporacion_remanentes"), ("sin_reconocer", "sin_reconocer")):
            control(f"{a} · {TODOS}: {c} = suma de los ministerios",
                    next(x[k] for x in filas if x["anio"] == a and x["ministerio_actual"] == TODOS),
                    sum(x[k] for x in filas if x["anio"] == a and x["ministerio_actual"] != TODOS), 1)
    escribir(DATOS / "remanentes_ministerio.csv", filas,
             ["anio", "dato", "ministerio_actual", "continuidad", "creditos_definitivos", "obligaciones", "sin_reconocer",
              "pct_sin_reconocer", "mrr_sin_reconocer", "incorporacion_remanentes", "bajas", "incorporacion_anio_siguiente",
              "pct_incorporado", "sin_incorporar", "par_comparable", "fuente"])
    escribir(DATOS / "controles_remanentes.csv", ctrl,
             ["control", "valor_a", "valor_b", "diferencia", "tolerancia", "correcto", "nota"])
    F = {(x["ministerio_actual"], x["anio"]): x for x in filas}
    mins = sorted({x["ministerio_actual"] for x in filas if x["ministerio_actual"] != TODOS and (x["ministerio_actual"], ULTIMO) in F})

    T = {}
    pares = ANIOS[:-1]
    t = ["| Secciones ministeriales | " + " | ".join(f"{a}→{str(a + 1)[2:]}" for a in pares) + " |",
         "| --- | " + " | ".join("---:" for _ in pares) + " |"]
    X = lambda a: F[(TODOS, a)]
    t.append("| Crédito sin reconocer el primer año | " + " | ".join(m(X(a)["sin_reconocer"]) for a in pares) + " |")
    t.append("| … en % del crédito definitivo | " + " | ".join(p(X(a)["sin_reconocer"], X(a)["creditos_definitivos"]) for a in pares) + " |")
    t.append("| … del que es del Mecanismo de Recuperación | " + " | ".join(m(X(a)["mrr_sin_reconocer"]) for a in pares) + " |")
    t.append("| Remanentes incorporados el segundo año | " + " | ".join(m(X(a)["incorporacion_anio_siguiente"]) for a in pares) + " |")
    t.append("| **… en % de lo no reconocido** | " + " | ".join(f"**{p(X(a)['incorporacion_anio_siguiente'], X(a)['sin_reconocer'])}**" for a in pares) + " |")
    t.append("| Sin incorporar (se anula) | " + " | ".join(m(X(a)["sin_incorporar"]) for a in pares) + " |")
    T["remanentes_serie"] = "\n".join(t)

    t = ["| Secciones ministeriales | " + " | ".join(str(a) if a < ULTIMO else f"{a} (prov.)" for a in ANIOS) + " |",
         "| --- | " + " | ".join("---:" for _ in ANIOS) + " |"]
    t.append("| Incorporación de remanentes | " + " | ".join(m(X(a)["incorporacion_remanentes"]) for a in ANIOS) + " |")
    t.append("| Bajas y otras modificaciones | " + " | ".join(m(X(a)["bajas"]) for a in ANIOS) + " |")
    T["remanentes_bajas"] = "\n".join(t)

    a1 = ULTIMO - 1
    t = [f"| Ministerio actual | Sin reconocer en {a1} | % de su crédito | … del Mecanismo | Incorporado en {ULTIMO} | "
         f"% de lo no reconocido | Sin incorporar | Bajas en {ULTIMO} |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for mi in sorted(mins, key=lambda n: -F[(n, a1)]["incorporacion_anio_siguiente"]) + [TODOS]:
        x, b = F[(mi, a1)], "**" if mi == TODOS else ""
        t.append(f"| {b}{corto(mi)}{b} | {m(x['sin_reconocer'])} | {p(x['sin_reconocer'], x['creditos_definitivos'])} | "
                 f"{m(x['mrr_sin_reconocer'])} | {b}{m(x['incorporacion_anio_siguiente'])}{b} | "
                 f"{p(x['incorporacion_anio_siguiente'], x['sin_reconocer'])} | {m(x['sin_incorporar'])} | {m(F[(mi, ULTIMO)]['bajas'])} |")
    T["remanentes_2024_2025"] = "\n".join(t)

    serie = [a for a in ANIOS if a >= 2021]
    t = ["| Ministerio actual | " + " | ".join(str(a) if a < ULTIMO else f"{a} (prov.)" for a in serie) + " |",
         "| --- | " + " | ".join("---:" for _ in serie) + " |"]
    for mi in sorted(mins, key=lambda n: -sum(F[(n, a)]["incorporacion_remanentes"] for a in serie if (n, a) in F)):
        c = []
        for a in serie:
            if (mi, a) not in F:
                c.append("—")
            else:
                c.append(m(F[(mi, a)]["incorporacion_remanentes"]) + ("" if F[(mi, a)]["continuidad"] == "directa" else " *"))
        t.append(f"| {corto(mi)} | " + " | ".join(c) + " |")
    T["remanentes_ministerio_serie"] = "\n".join(t)

    texto = DOC.read_text(encoding="utf-8")
    hechas = 0
    for nombre, tabla in T.items():
        texto, n = re.subn(rf"<!-- tabla:{nombre} -->.*?<!-- /tabla -->",
                           lambda _: f"<!-- tabla:{nombre} -->\n{tabla}\n<!-- /tabla -->", texto, flags=re.S)
        hechas += n
    DOC.write_text(texto, encoding="utf-8")

    malos = [c for c in ctrl if c["correcto"] != "sí"]
    print(f"{len(filas)} filas en remanentes_ministerio.csv; {len(ctrl)} controles, {len(malos)} incorrectos; "
          f"preguntas.md: {hechas} de {len(T)} marcas")
    for c in malos:
        print("  CONTROL INCORRECTO:", c["control"], c["valor_a"], c["valor_b"])
    for nombre, tabla in T.items():
        print(f"\n[{nombre}]\n{tabla}")


if __name__ == "__main__":
    main()
