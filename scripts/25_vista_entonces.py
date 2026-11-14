"""Pregunta 8 · ¿Cambian las conclusiones según se asignen los cambios de competencias? (2017-2025)

Se repiten dos análisis (pregunta 7, obligaciones sobre créditos iniciales, y pregunta 9, crecimiento en euros constantes)
con la otra vista: en lugar de «ministerio actual» (solo se comparan los años con continuidad directa), el «ministerio de
entonces»: cada año se suman las secciones del ministerio que tenía las competencias de cada ministerio actual, según
powerbi/dim_grupo.csv (script 13). Esa serie existe los nueve años, pero cambia de perímetro cuando cambian las
competencias: es la historia del ministerio que tenía cada tarea, no la de una tarea con perímetro fijo (REGISTRO B29).

Varios ministerios actuales comparten ministerio de entonces en un año (por ejemplo cuatro compartían Sanidad en 2017-2018):
en ese año sus cifras son iguales. Agricultura 2017-2018 no suma Estado en el grupo (REGISTRO B15) y no se mide.

Entradas: powerbi/dim_grupo.csv, powerbi/dim_ministerio.csv, powerbi/deflactor.csv, datos/secciones_ministerio_actual.csv,
          datos/sobre_inicial_ministerio.csv y _resumen.csv, datos/euros_constantes_resumen.csv
Salidas:  datos/vista_entonces_ministerio.csv, datos/vista_entonces_resumen.csv, datos/controles_vista_entonces.csv,
          preguntas.md (marcas <!-- tabla:vista_entonces_… -->)
Uso: python scripts/25_vista_entonces.py
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
MIN_ANIOS = 5
VENT = [(2017, 2025), (2019, 2025), (2021, 2025)]

spec = importlib.util.spec_from_file_location("s18", Path(__file__).with_name("18_catastrofes.py"))
s18 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s18)
f, m, p, corto, leer, escribir = s18.f, s18.m, s18.p, s18.corto, s18.leer, s18.escribir


def main():
    grupos = leer(RAIZ / "powerbi" / "dim_grupo.csv")
    nombre = {r["ministerio_id"]: r["ministerio"] for r in leer(RAIZ / "powerbi" / "dim_ministerio.csv")}
    fac = {int(r["anio"]): f(r["factor_aapp"]) for r in leer(RAIZ / "powerbi" / "deflactor.csv")}
    sec = {(int(r["anio"]), r["codigo_seccion"]): r for r in leer(DATOS / "secciones_ministerio_actual.csv")}
    prorroga = {a: r["presupuesto"] for (a, _), r in sec.items() if r["tipo"] == "Ministerio" for a in [a]}
    si = {(r["ministerio_actual"], int(r["anio"])): r for r in leer(DATOS / "sobre_inicial_ministerio.csv")}
    sir = {r["ministerio_actual"]: r for r in leer(DATOS / "sobre_inicial_resumen.csv")}
    ecr = {r["ministerio_actual"]: r for r in leer(DATOS / "euros_constantes_resumen.csv")}

    ctrl = []

    def control(que, a, b, tol, nota=""):
        ctrl.append(dict(control=que, valor_a=a, valor_b=b, diferencia=a - b, tolerancia=tol,
                         correcto="sí" if abs(a - b) <= tol else "NO", nota=nota))

    filas, F = [], {}
    for r in grupos:
        a, mi = int(r["anio"]), nombre[r["ministerio_id"]]
        cods = [c.strip() for c in r["secciones_entonces"].split(",")]
        ini = obl = 0.0
        if r["incluir_estado"] == "1":
            for c in cods:
                x = sec[(a, c)]
                ini += f(x["creditos_iniciales"])
                obl += f(x["obligaciones"])
        x = dict(anio=a, ministerio_actual=mi, grupo_id=r["grupo_id"], ministerio_entonces=r["ministerio_entonces"],
                 secciones_entonces=r["secciones_entonces"], incluye_estado=r["incluir_estado"],
                 presupuesto=prorroga[a], creditos_iniciales=ini, obligaciones=obl,
                 pct_obligaciones_sobre_iniciales=round(100 * obl / ini, 2) if ini else None,
                 obligaciones_constantes_2025=obl * fac[a], factor_aapp=fac[a],
                 fuente="IGAE, liquidación del Presupuesto del Estado, vol. I; 2025: estadística mensual de diciembre, "
                        "provisional; grupos: powerbi/dim_grupo.csv (script 13)")
        filas.append(x)
        F[(mi, a)] = x
        s = si.get((mi, a))
        # donde el ministerio de entonces es el mismo que el actual (misma sección, continuidad directa), las dos vistas coinciden
        if s and s["comparable"] == "sí" and r["incluir_estado"] == "1" and r["existia"] == "sí" and len(cods) == 1:
            control(f"{a} · {corto(mi)} · vista de entonces = vista actual (créditos iniciales)", ini, f(s["creditos_iniciales"]), 1)
            control(f"{a} · {corto(mi)} · vista de entonces = vista actual (obligaciones)", obl, f(s["obligaciones"]), 1)
    escribir(DATOS / "vista_entonces_ministerio.csv", filas,
             ["anio", "ministerio_actual", "grupo_id", "ministerio_entonces", "secciones_entonces", "incluye_estado", "presupuesto",
              "creditos_iniciales", "obligaciones", "pct_obligaciones_sobre_iniciales", "factor_aapp",
              "obligaciones_constantes_2025", "fuente"])
    # cada ministerio de entonces cuenta una sola vez: la suma de grupos distintos = las 22 secciones ministeriales
    for a in ANIOS:
        por_grupo = {}
        for x in filas:
            if x["anio"] == a:
                por_grupo[x["grupo_id"]] = max(por_grupo.get(x["grupo_id"], 0.0), x["obligaciones"])
        tot = sum(por_grupo.values())
        ref = f(si[("22 ministerios", a)]["obligaciones"])
        control(f"{a} · suma de ministerios de entonces (sin repetir) = 22 ministerios", tot, ref, 1,
                "en 2017-2018 Agricultura comparte grupo con Transición Ecológica y su Estado no se suma dos veces")

    mins = sorted({x["ministerio_actual"] for x in filas})
    resumen = []
    for mi in mins:
        xs = [F[(mi, a)] for a in ANIOS if F[(mi, a)]["creditos_iniciales"]]
        rs = [100 * x["obligaciones"] / x["creditos_iniciales"] for x in xs]
        v = dict(ministerio_actual=mi, anios_entonces=len(xs), anios_por_encima_de_100_entonces=sum(1 for r in rs if r > 100),
                 pct_minimo_entonces=round(min(rs), 2), pct_maximo_entonces=round(max(rs), 2),
                 pct_acumulado_entonces=round(100 * sum(x["obligaciones"] for x in xs) / sum(x["creditos_iniciales"] for x in xs), 2),
                 sistematico_entonces=("sí" if len(xs) >= MIN_ANIOS and all(r > 100 for r in rs)
                                       else "no" if len(xs) >= MIN_ANIOS else f"menos de {MIN_ANIOS} años"))
        s = sir[mi]
        v.update(anios_actual=int(s["anios_comparables"]), anios_por_encima_de_100_actual=int(s["anios_por_encima_de_100"]),
                 pct_acumulado_actual=f(s["pct_acumulado"]), sistematico_actual=s["sistematico"])
        for a0, a1 in VENT:
            o0, o1 = F[(mi, a0)], F[(mi, a1)]
            ok = o0["incluye_estado"] == "1" and o0["obligaciones"]
            v[f"pct_real_entonces_{a0}_{a1}"] = round(100 * (o1["obligaciones_constantes_2025"] / o0["obligaciones_constantes_2025"] - 1), 2) if ok else None
            v[f"pct_nominal_entonces_{a0}_{a1}"] = round(100 * (o1["obligaciones"] / o0["obligaciones"] - 1), 2) if ok else None
            if a0 > 2017:
                v[f"pct_real_actual_{a0}_{a1}"] = f(ecr[mi][f"pct_real_aapp_{a0}_{a1}"]) if ecr[mi][f"pct_real_aapp_{a0}_{a1}"] != "" else None
        resumen.append(v)
    campos = ["ministerio_actual", "anios_entonces", "anios_por_encima_de_100_entonces", "pct_minimo_entonces", "pct_maximo_entonces",
              "pct_acumulado_entonces", "sistematico_entonces", "anios_actual", "anios_por_encima_de_100_actual",
              "pct_acumulado_actual", "sistematico_actual"]
    campos += [f"pct_{t}_{k}_{a0}_{a1}" for a0, a1 in VENT for t in ("nominal", "real") for k in ("entonces", "actual")
               if not (t == "nominal" and k == "actual") and not (a0 == 2017 and k == "actual")]
    escribir(DATOS / "vista_entonces_resumen.csv", resumen, campos)
    for v in resumen:
        for a0, a1 in VENT[1:]:
            n, r = v[f"pct_nominal_entonces_{a0}_{a1}"], v[f"pct_real_entonces_{a0}_{a1}"]
            if n is not None:
                esp = 100 * ((1 + n / 100) * fac[a1] / fac[a0] - 1)
                control(f"{corto(v['ministerio_actual'])} · {a0}-{a1} · real cuadra con nominal y factores", r, esp, 0.02)
    escribir(DATOS / "controles_vista_entonces.csv", ctrl,
             ["control", "valor_a", "valor_b", "diferencia", "tolerancia", "correcto", "nota"])
    R = {v["ministerio_actual"]: v for v in resumen}

    pc = lambda x: f"{x:.1f}".replace(".", ",")
    sg = lambda x: "—" if x is None else ("+" if x >= 0 else "−") + f"{abs(x):.1f}".replace(".", ",")
    col = lambda a: (str(a) if a < ULTIMO else f"{a} (prov.)") + (" P" if prorroga[a] != "aprobado" else "")
    orden = sorted(mins, key=lambda n: (-R[n]["anios_por_encima_de_100_entonces"], -R[n]["pct_acumulado_entonces"]))
    T = {}
    t = ["| Ministerio actual | " + " | ".join(col(a) for a in ANIOS) + " | Años > 100 %: de entonces | actual |",
         "| --- | " + " | ".join("---:" for _ in ANIOS) + " | ---: | ---: |"]
    for mi in orden:
        c = [pc(F[(mi, a)]["pct_obligaciones_sobre_iniciales"]) if F[(mi, a)]["pct_obligaciones_sobre_iniciales"] is not None else "—" for a in ANIOS]
        v = R[mi]
        t.append(f"| {corto(mi)} | " + " | ".join(c) + f" | {v['anios_por_encima_de_100_entonces']} de {v['anios_entonces']} | "
                 f"{v['anios_por_encima_de_100_actual']} de {v['anios_actual']} |")
    T["vista_entonces_sobre_inicial"] = "\n".join(t)

    orden2 = sorted(mins, key=lambda n: (R[n]["pct_real_entonces_2021_2025"] is None, -(R[n]["pct_real_entonces_2021_2025"] or 0)))
    t = ["| Ministerio actual | 2017-2025 de entonces | 2019-2025 de entonces | 2019-2025 actual | 2021-2025 de entonces | 2021-2025 actual |",
         "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for mi in orden2:
        v = R[mi]
        t.append(f"| {corto(mi)} | {sg(v['pct_real_entonces_2017_2025'])} | {sg(v['pct_real_entonces_2019_2025'])} | "
                 f"{sg(v['pct_real_actual_2019_2025'])} | {sg(v['pct_real_entonces_2021_2025'])} | {sg(v['pct_real_actual_2021_2025'])} |")
    T["vista_entonces_real"] = "\n".join(t)

    texto = DOC.read_text(encoding="utf-8")
    hechas = 0
    for nombre_t, tabla in T.items():
        texto, n = re.subn(rf"<!-- tabla:{nombre_t} -->.*?<!-- /tabla -->",
                           lambda _: f"<!-- tabla:{nombre_t} -->\n{tabla}\n<!-- /tabla -->", texto, flags=re.S)
        hechas += n
    DOC.write_text(texto, encoding="utf-8")
    malos = [c for c in ctrl if c["correcto"] != "sí"]
    print(f"{len(filas)} filas; {len(ctrl)} controles, {len(malos)} incorrectos; preguntas.md: {hechas} de {len(T)} marcas")
    for c in malos:
        print("  CONTROL INCORRECTO:", c["control"], c["valor_a"], c["valor_b"], c["nota"])
    for nombre_t, tabla in T.items():
        print(f"\n[{nombre_t}]\n{tabla}")
    print("\nSISTEMÁTICO:", [(corto(v["ministerio_actual"]), v["sistematico_entonces"], v["sistematico_actual"]) for v in resumen
                           if v["sistematico_entonces"] == "sí" or v["sistematico_actual"] == "sí"])


if __name__ == "__main__":
    main()
