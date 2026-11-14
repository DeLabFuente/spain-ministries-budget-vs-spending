"""Pregunta 3 · ¿En cuántas líneas se concentra el gasto de cada ministerio? (2020-2025)

Unidad: la aplicación presupuestaria del Estado (año, sección, servicio, programa y económica), sumando los anexos I y
II y las líneas repetidas de una misma aplicación (p. ej. las territorializadas por provincia). Se ordenan las
aplicaciones de cada ministerio actual por sus obligaciones y se mide:
  pct_primera, pct_cinco_primeras   peso de la aplicación mayor y de las cinco mayores
  n50, n80, n95                     cuántas aplicaciones hacen falta para llegar al 50 %, el 80 % y el 95 %
y, de la aplicación mayor, su programa, su capítulo y a quién va según su clasificación económica (la del script 18),
sin su descripción (puede nombrar beneficiarios).

Solo el Estado: las transferencias a los organismos del ministerio son una línea más (programa 000X), y lo que el
organismo hace con el dinero no se ve. Los 22 solo se comparan en 2024 y 2025 (provisional); las series usan los
años con continuidad directa (REGISTRO B24).

Entradas: las del script 18 (aplicaciones 2020-2024 del script 01 y anexos de la mensual de 2025);
  datos/secciones_ministerio_actual.csv, datos/ficha_resumen.csv (continuidad)
Salidas:
  datos/concentracion_ministerio.csv   ministerio × año, más la fila «22 ministerios» de cada año
  datos/controles_concentracion.csv    cuadres
  preguntas.md                       tablas entre las marcas <!-- tabla:concentracion_… --> y <!-- /tabla -->
Uso: python scripts/21_concentracion.py
"""
import importlib.util
import re
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datos"
DOC = RAIZ / "preguntas.md"
ANIO_MENSUAL = 2025
ANIOS = list(range(2020, ANIO_MENSUAL + 1))
TODOS = "22 ministerios"
TOL_SECCION = 15000   # las tablas por secciones van en miles de euros

spec = importlib.util.spec_from_file_location("s18", Path(__file__).with_name("18_catastrofes.py"))
s18 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s18)
f, m, p, corto, leer, escribir = s18.f, s18.m, s18.p, s18.corto, s18.leer, s18.escribir


def medir(apl):
    """apl: lista de (obligaciones, clave). Devuelve las medidas de concentración."""
    pos = sorted((x for x in apl if x[0] > 0), key=lambda x: -x[0])
    total = sum(x[0] for x in pos)
    v = dict(aplicaciones_con_obligaciones=len(pos), obligaciones_positivas=total,
             pct_primera=100 * pos[0][0] / total, pct_cinco_primeras=100 * sum(x[0] for x in pos[:5]) / total)
    acum, hitos = 0.0, {"n50": 0.5, "n80": 0.8, "n95": 0.95}
    for i, (o, _) in enumerate(pos, 1):
        acum += o
        for k, q in hitos.items():
            if k not in v and acum >= q * total - 0.005:
                v[k] = i
    _, _, sec, _, prog, eco = pos[0][1]
    v.update(primera_obligaciones=pos[0][0], primera_programa=prog, primera_capitulo=eco[0],
             primera_destino=("Transferencia interna (programa 000X)" if prog == "000X" else s18.destino(eco)))
    return v


def main():
    apps, _, _ = s18.aplicaciones()
    apps = [r for r in apps if r["anio"] in ANIOS]
    sec = {(int(r["anio"]), r["codigo_seccion"]): r for r in leer(DATOS / "secciones_ministerio_actual.csv")}
    cont = {(r["ministerio_actual"], int(r["anio"])): r["continuidad_estado"] for r in leer(DATOS / "ficha_resumen.csv")}

    por_apl = defaultdict(float)     # (ministerio, año, sección, servicio, programa, económica) -> obligaciones
    por_sec = defaultdict(float)
    for r in apps:
        info = sec[(r["anio"], r["seccion"])]
        por_sec[(r["anio"], r["seccion"])] += r["obligaciones"]
        if info["tipo"] == "Ministerio":
            por_apl[(info["ministerio_actual"], r["anio"], r["seccion"], r["servicio"], r["programa"],
                     r["economica"])] += r["obligaciones"]

    ctrl = []

    def control(que, a, b, tol, nota=""):
        ctrl.append(dict(control=que, valor_a=a, valor_b=b, diferencia=a - b, tolerancia=tol,
                         correcto="sí" if abs(a - b) <= tol else "NO", nota=nota))

    grupos = defaultdict(list)
    for k, o in por_apl.items():
        grupos[(k[0], k[1])].append((o, k))
        grupos[(TODOS, k[1])].append((o, k))
    filas = []
    for (mi, a), apl in sorted(grupos.items(), key=lambda x: (x[0][1], x[0][0] == TODOS, x[0][0])):
        v = medir(apl)
        neto = sum(o for o, _ in apl)
        v.update(anio=a, dato="provisional (mensual de diciembre)" if a == ANIO_MENSUAL else "definitivo (liquidación)",
                 ministerio_actual=mi, continuidad=cont.get((mi, a), "") if mi != TODOS else "", obligaciones=neto,
                 fuente=("IGAE, Liquidación del Presupuesto del Estado %d, vol. I, anexos por aplicación" % a
                         if a < ANIO_MENSUAL else
                         "IGAE, Estadística mensual de ejecución, diciembre de 2025 (provisional), anexos por aplicación"))
        filas.append(v)
        control(f"{a} · {corto(mi)} · obligaciones positivas = obligaciones netas (no hay aplicaciones negativas)",
                v["obligaciones_positivas"], neto, 0.05)
        if mi != TODOS:
            tabla = sum(f(r["obligaciones"]) for (aa, c), r in sec.items() if aa == a and r["ministerio_actual"] == mi
                        and r["tipo"] == "Ministerio")
            n_sec = sum(1 for (aa, c), r in sec.items() if aa == a and r["ministerio_actual"] == mi and r["tipo"] == "Ministerio")
            control(f"{a} · {corto(mi)} · obligaciones de sus aplicaciones = tabla por secciones", neto, tabla,
                    TOL_SECCION * n_sec, "la tabla va en miles de euros")
    for a in ANIOS:
        control(f"{a} · {TODOS}: obligaciones = suma de los ministerios",
                next(v["obligaciones"] for v in filas if v["anio"] == a and v["ministerio_actual"] == TODOS),
                sum(v["obligaciones"] for v in filas if v["anio"] == a and v["ministerio_actual"] != TODOS), 0.05)
    escribir(DATOS / "concentracion_ministerio.csv", filas,
             ["anio", "dato", "ministerio_actual", "continuidad", "aplicaciones_con_obligaciones", "obligaciones",
              "pct_primera", "pct_cinco_primeras", "n50", "n80", "n95", "primera_obligaciones", "primera_programa",
              "primera_capitulo", "primera_destino", "fuente"])
    escribir(DATOS / "controles_concentracion.csv", ctrl,
             ["control", "valor_a", "valor_b", "diferencia", "tolerancia", "correcto", "nota"])
    F = {(v["ministerio_actual"], v["anio"]): v for v in filas}
    mins = sorted({v["ministerio_actual"] for v in filas if v["ministerio_actual"] != TODOS and (v["ministerio_actual"], ANIO_MENSUAL) in F})
    pc = lambda x: f"{x:.1f}".replace(".", ",")
    ent = lambda n: f"{n:,}".replace(",", ".")

    T = {}
    a1, a2 = ANIO_MENSUAL - 1, ANIO_MENSUAL
    t = [f"| Ministerio actual | Aplicaciones {a2} | Primera línea {a1}, % | 50 % en… | 80 % en… | Primera línea {a2}, % | "
         f"Cinco primeras, % | 50 % en… | 80 % en… | A quién va la primera línea de {a2} |",
         "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
    for mi in sorted(mins, key=lambda n: -F[(n, a2)]["pct_primera"]) + [TODOS]:
        x, y = F[(mi, a1)], F[(mi, a2)]
        b = "**" if mi == TODOS else ""
        t.append(f"| {b}{corto(mi)}{b} | {ent(y['aplicaciones_con_obligaciones'])} | {pc(x['pct_primera'])} | {x['n50']} | "
                 f"{x['n80']} | {b}{pc(y['pct_primera'])}{b} | {pc(y['pct_cinco_primeras'])} | {y['n50']} | {y['n80']} | "
                 f"{y['primera_destino']} |")
    T["concentracion_2024_2025"] = "\n".join(t)

    col = lambda a: str(a) if a < ANIO_MENSUAL else f"{a} (prov.)"
    t = ["| Ministerio actual | " + " | ".join(col(a) for a in ANIOS) + " |", "| --- | " + " | ".join("---:" for _ in ANIOS) + " |"]
    for mi in sorted(mins, key=lambda n: -F[(n, a2)]["pct_primera"]):
        c = [pc(F[(mi, a)]["pct_primera"]) if (mi, a) in F and F[(mi, a)]["continuidad"] == "directa" else "—" for a in ANIOS]
        t.append(f"| {corto(mi)} | " + " | ".join(c) + " |")
    T["concentracion_serie"] = "\n".join(t)

    t = ["| 22 ministerios | " + " | ".join(col(a) for a in ANIOS) + " |", "| --- | " + " | ".join("---:" for _ in ANIOS) + " |"]
    for et, fn in (("Obligaciones (M€)", lambda v: m(v["obligaciones"])),
                   ("Aplicaciones con obligaciones", lambda v: ent(v["aplicaciones_con_obligaciones"])),
                   ("Primera línea, %", lambda v: pc(v["pct_primera"])),
                   ("Cinco primeras, %", lambda v: pc(v["pct_cinco_primeras"])),
                   ("50 % en…", lambda v: str(v["n50"])), ("80 % en…", lambda v: str(v["n80"])),
                   ("95 % en…", lambda v: str(v["n95"]))):
        t.append(f"| {et} | " + " | ".join(fn(F[(TODOS, a)]) for a in ANIOS) + " |")
    T["concentracion_total"] = "\n".join(t)

    texto = DOC.read_text(encoding="utf-8")
    hechas = 0
    for nombre, tabla in T.items():
        texto, n = re.subn(rf"<!-- tabla:{nombre} -->.*?<!-- /tabla -->",
                           lambda _: f"<!-- tabla:{nombre} -->\n{tabla}\n<!-- /tabla -->", texto, flags=re.S)
        hechas += n
    DOC.write_text(texto, encoding="utf-8")

    malos = [c for c in ctrl if c["correcto"] != "sí"]
    print(f"{len(por_apl)} aplicaciones; {len(filas)} filas en concentracion_ministerio.csv; {len(ctrl)} controles, "
          f"{len(malos)} incorrectos; preguntas.md: {hechas} de {len(T)} marcas")
    for c in malos:
        print("  CONTROL INCORRECTO:", c["control"], c["valor_a"], c["valor_b"])
    for nombre, tabla in T.items():
        print(f"\n[{nombre}]\n{tabla}")


if __name__ == "__main__":
    main()
