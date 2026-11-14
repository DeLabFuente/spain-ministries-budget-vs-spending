"""Pregunta 9 · ¿Qué ministerios gastan más y cuáles menos si se descuenta la inflación? (2017-2025)

Obligaciones reconocidas del Estado en las secciones ministeriales, por ministerio actual y año, en euros corrientes y
en euros constantes de 2025. Deflactor principal: el del gasto en consumo final de las Administraciones Públicas (INE);
como contraste, IPC y deflactor del PIB. Los factores salen de powerbi/deflactor.csv (script 14; factor = índice de 2025
dividido entre el índice del año). Se separa el Mecanismo de Recuperación y Resiliencia (datos/mrr_secciones.csv), que
está dentro de las obligaciones de la sección y se mueve por calendario europeo, no por el gasto ordinario (REGISTRO B28).

Solo se compara un ministerio entre dos años cuando los dos tienen continuidad directa. 2025 es provisional
(estadística mensual de diciembre). Es una medida de cuánto crecen las obligaciones, no de si se gasta mejor o peor.

Entradas: datos/secciones_ministerio_actual.csv, datos/mrr_secciones.csv, datos/ficha_resumen.csv,
          datos/sobre_inicial_ministerio.csv (control), powerbi/deflactor.csv
Salidas:  datos/euros_constantes_ministerio.csv, datos/euros_constantes_resumen.csv, datos/controles_euros_constantes.csv,
          preguntas.md (marcas <!-- tabla:euros_constantes_… -->)
Uso: python scripts/26_euros_constantes.py
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
VENTANAS = [(2019, 2025), (2021, 2025), (2024, 2025)]
FACT = [("aapp", "factor_aapp"), ("ipc", "factor_2025"), ("pib", "factor_pib")]

spec = importlib.util.spec_from_file_location("s18", Path(__file__).with_name("18_catastrofes.py"))
s18 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s18)
f, m, p, corto, leer, escribir = s18.f, s18.m, s18.p, s18.corto, s18.leer, s18.escribir


def main():
    fac = {int(r["anio"]): {k: f(r[c]) for k, c in FACT} for r in leer(RAIZ / "powerbi" / "deflactor.csv")}
    res = {(r["ministerio_actual"], int(r["anio"])): r for r in leer(DATOS / "ficha_resumen.csv")}
    ob = defaultdict(float)
    for r in leer(DATOS / "secciones_ministerio_actual.csv"):
        if r["tipo"] == "Ministerio":
            for mi in (r["ministerio_actual"], TODOS):
                ob[(mi, int(r["anio"]))] += f(r["obligaciones"])
    mrr = defaultdict(float)
    for r in leer(DATOS / "mrr_secciones.csv"):
        for mi in (r["ministerio_actual"], TODOS):
            mrr[(mi, int(r["anio"]))] += f(r["obligaciones"])

    ctrl = []

    def control(que, a, b, tol, nota=""):
        ctrl.append(dict(control=que, valor_a=a, valor_b=b, diferencia=a - b, tolerancia=tol,
                         correcto="sí" if abs(a - b) <= tol else "NO", nota=nota))

    filas, F = [], {}
    for (mi, a), v in sorted(ob.items(), key=lambda x: (x[0][1], x[0][0] == TODOS, x[0][0])):
        cont = res[(mi, a)]["continuidad_estado"] if (mi, a) in res else ""
        sin = v - mrr.get((mi, a), 0.0)
        x = dict(anio=a, ministerio_actual=mi, continuidad=cont, comparable="sí" if mi == TODOS or cont == "directa" else "no",
                 obligaciones_corrientes=v, mecanismo=mrr.get((mi, a), 0.0), obligaciones_sin_mecanismo=sin,
                 factor_aapp=fac[a]["aapp"], factor_ipc=fac[a]["ipc"], factor_pib=fac[a]["pib"],
                 const_aapp=v * fac[a]["aapp"], const_ipc=v * fac[a]["ipc"], const_pib=v * fac[a]["pib"],
                 const_aapp_sin_mecanismo=sin * fac[a]["aapp"],
                 dato="provisional (mensual de diciembre)" if a == ULTIMO else "definitivo (liquidación)",
                 fuente="IGAE, liquidación del Presupuesto del Estado, vol. I; 2025: estadística mensual de diciembre, "
                        "provisional; deflactores: INE (powerbi/deflactor.csv, script 14)")
        filas.append(x)
        F[(mi, a)] = x
        control(f"{a} · {corto(mi)} · constantes = corrientes × factor (AAPP)", x["const_aapp"], v * fac[a]["aapp"], 0.01)
    for a in ANIOS:
        suma = sum(x["obligaciones_corrientes"] for x in filas if x["anio"] == a and x["ministerio_actual"] != TODOS)
        control(f"{a} · suma de ministerios = 22 ministerios", suma, F[(TODOS, a)]["obligaciones_corrientes"], 1)
        control(f"{a} · obligaciones 22 = sobre_inicial_ministerio.csv",
                F[(TODOS, a)]["obligaciones_corrientes"],
                f(next(r for r in leer(DATOS / "sobre_inicial_ministerio.csv")
                       if int(r["anio"]) == a and r["ministerio_actual"] == TODOS)["obligaciones"]), 1)
    control("factor de 2025 = 1 (AAPP, IPC, PIB)", sum(fac[2025].values()), 3.0, 1e-9)
    escribir(DATOS / "euros_constantes_ministerio.csv", filas,
             ["anio", "ministerio_actual", "continuidad", "comparable", "dato", "obligaciones_corrientes", "mecanismo",
              "obligaciones_sin_mecanismo", "factor_aapp", "factor_ipc", "factor_pib", "const_aapp", "const_ipc",
              "const_pib", "const_aapp_sin_mecanismo", "fuente"])

    mins = sorted({mi for (mi, a) in F if mi != TODOS and (mi, ULTIMO) in F})

    def var(mi, a0, a1, campo):
        x0, x1 = F.get((mi, a0)), F.get((mi, a1))
        if not x0 or not x1 or x0["comparable"] != "sí" or x1["comparable"] != "sí" or not x0[campo]:
            return None
        return 100 * (x1[campo] / x0[campo] - 1)

    resumen = []
    for mi in mins + [TODOS]:
        v = dict(ministerio_actual=mi)
        for a0, a1 in VENTANAS:
            t = f"{a0}_{a1}"
            for nombre, campo in [("nominal", "obligaciones_corrientes"), ("real_aapp", "const_aapp"), ("real_ipc", "const_ipc"),
                                  ("real_pib", "const_pib"), ("real_aapp_sin_mecanismo", "const_aapp_sin_mecanismo")]:
                r = var(mi, a0, a1, campo)
                v[f"pct_{nombre}_{t}"] = None if r is None else round(r, 2)
        resumen.append(v)
    campos = ["ministerio_actual"] + [f"pct_{n}_{a0}_{a1}" for a0, a1 in VENTANAS
                                     for n in ("nominal", "real_aapp", "real_ipc", "real_pib", "real_aapp_sin_mecanismo")]
    escribir(DATOS / "euros_constantes_resumen.csv", resumen, campos)
    R = {v["ministerio_actual"]: v for v in resumen}
    for v in resumen:
        for a0, a1 in VENTANAS:
            t = f"{a0}_{a1}"
            if v[f"pct_nominal_{t}"] is not None:
                n, r = v[f"pct_nominal_{t}"], v[f"pct_real_aapp_{t}"]
                # el real debe cuadrar con nominal y factores: (1+n)·fac1/fac0 − 1
                esp = 100 * ((1 + n / 100) * fac[a1]["aapp"] / fac[a0]["aapp"] - 1)
                control(f"{corto(v['ministerio_actual'])} · {a0}-{a1} · real (AAPP) cuadra con nominal y factores", r, esp, 0.02)
    escribir(DATOS / "controles_euros_constantes.csv", ctrl,
             ["control", "valor_a", "valor_b", "diferencia", "tolerancia", "correcto", "nota"])

    pc = lambda x: "—" if x is None else (("+" if x >= 0 else "−") + f"{abs(x):.1f}".replace(".", ","))
    T = {}
    t = ["| Año | Corrientes, M€ | Constantes de 2025 (AAPP), M€ | Constantes (IPC), M€ | Constantes (PIB), M€ | Sin Mecanismo, corrientes, M€ | Sin Mecanismo, constantes (AAPP), M€ |",
         "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for a in ANIOS:
        x = F[(TODOS, a)]
        t.append(f"| {a}{' (prov.)' if a == ULTIMO else ''} | {m(x['obligaciones_corrientes'])} | {m(x['const_aapp'])} | "
                 f"{m(x['const_ipc'])} | {m(x['const_pib'])} | {m(x['obligaciones_sin_mecanismo'])} | {m(x['const_aapp_sin_mecanismo'])} |")
    t.append("| **Variación 2019-2025, %** | " + " | ".join(
        f"**{pc(var(TODOS, 2019, 2025, c))}**" for c in ("obligaciones_corrientes", "const_aapp", "const_ipc", "const_pib",
                                                        "obligaciones_sin_mecanismo", "const_aapp_sin_mecanismo")) + " |")
    T["euros_constantes_total"] = "\n".join(t)

    def clave(mi):
        r = R[mi]["pct_real_aapp_2021_2025"]
        r2 = R[mi]["pct_real_aapp_2024_2025"]
        return (r is None, -(r if r is not None else 0), r2 is None, -(r2 if r2 is not None else 0))
    orden = sorted(mins, key=clave)
    t = ["| Ministerio actual | 2019-2025 nominal | 2019-2025 real | 2021-2025 nominal | 2021-2025 real | 2024-2025 nominal | 2024-2025 real |",
         "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for mi in orden + [TODOS]:
        b = "**" if mi == TODOS else ""
        c = []
        for a0, a1 in VENTANAS:
            c += [pc(R[mi][f"pct_nominal_{a0}_{a1}"]), pc(R[mi][f"pct_real_aapp_{a0}_{a1}"])]
        t.append(f"| {b}{corto(mi)}{b} | " + " | ".join(c) + " |")
    T["euros_constantes_ministerio"] = "\n".join(t)

    t = ["| Ministerio actual | Real 2021-2025 con Mecanismo | Real 2021-2025 sin Mecanismo | Real 2024-2025 con Mecanismo | Real 2024-2025 sin Mecanismo | Mecanismo en 2025, M€ |",
         "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for mi in orden + [TODOS]:
        b = "**" if mi == TODOS else ""
        t.append(f"| {b}{corto(mi)}{b} | {pc(R[mi]['pct_real_aapp_2021_2025'])} | {pc(R[mi]['pct_real_aapp_sin_mecanismo_2021_2025'] if 'pct_real_aapp_sin_mecanismo_2021_2025' in R[mi] else None)} | "
                 f"{pc(R[mi]['pct_real_aapp_2024_2025'])} | {pc(R[mi]['pct_real_aapp_sin_mecanismo_2024_2025'])} | {m(F[(mi, 2025)]['mecanismo'])} |")
    T["euros_constantes_mecanismo"] = "\n".join(t)

    texto = DOC.read_text(encoding="utf-8")
    hechas = 0
    for nombre, tabla in T.items():
        texto, n = re.subn(rf"<!-- tabla:{nombre} -->.*?<!-- /tabla -->",
                           lambda _: f"<!-- tabla:{nombre} -->\n{tabla}\n<!-- /tabla -->", texto, flags=re.S)
        hechas += n
    DOC.write_text(texto, encoding="utf-8")
    malos = [c for c in ctrl if c["correcto"] != "sí"]
    print(f"{len(filas)} filas; {len(ctrl)} controles, {len(malos)} incorrectos; preguntas.md: {hechas} de {len(T)} marcas")
    for c in malos:
        print("  CONTROL INCORRECTO:", c["control"], c["valor_a"], c["valor_b"])
    for nombre, tabla in T.items():
        print(f"\n[{nombre}]\n{tabla}")


if __name__ == "__main__":
    main()
