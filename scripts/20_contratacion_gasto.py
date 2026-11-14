"""Pregunta 2 · ¿Qué parte del gasto pasa por contratación pública y qué parte va en transferencias y préstamos?

Dos medidas por ministerio actual y año (2017-2024, los años con Estado y organismos):
  1. Composición del gasto agregado sin doble cómputo (script 07), por capítulos:
       personal                  capítulo 1 del Estado y de sus organismos
       compras e inversiones     capítulos 2 y 6: lo que, como mucho, se paga con contratos
       préstamos y aportaciones  capítulo 8
       transferencias y resto    por diferencia: gasto agregado − los tres anteriores (capítulos 4 y 7 sin las
                                 transferencias entre el Estado y sus organismos, más los capítulos 3, 5 y 9)
  2. Lo adjudicado en la Plataforma de Contratación del Sector Público (script 09): licitaciones ordinarias,
     contratos menores y programas especiales, con IVA, frente al gasto agregado y frente a compras e inversiones.
     «Adjudicado total» = ordinario + programas especiales (sin los contratos menores de importe atípico).

Lo adjudicado no es lo gastado: un contrato cuenta entero el año en que se adjudica y se paga durante varios. Y el
perímetro no es el mismo: la contratación de un ministerio incluye órganos que no están en su presupuesto (entidades
gestoras de la Seguridad Social, autoridades portuarias, compras centralizadas de Hacienda para toda la AGE). Por
eso la ratio es un orden de magnitud, no una cuenta (REGISTRO B23).

Los 22 solo son comparables a la vez en 2024. Las series por ministerio solo usan los años con continuidad directa;
de los 22 juntos solo se da la serie de compras e inversiones y de lo adjudicado, desde 2019 (en 2017-2018 el Estado
de Agricultura está reconstruido y no tiene capítulos; el gasto agregado de los 22 no se puede sumar antes de 2024).

Entradas (datos/): ficha_resumen.csv, ficha_capitulos.csv, contratacion_ministerio.csv;
  fuentes/contratacion/niveles_estudio_viabilidad.csv (niveles A/B/C)
Salidas:
  datos/contratacion_gasto.csv            ministerio × año
  datos/controles_contratacion_gasto.csv  cuadres
  preguntas.md                          tablas entre las marcas <!-- tabla:contratacion_gasto_… --> y <!-- /tabla -->
Uso: python scripts/20_contratacion_gasto.py
"""
import csv
import re
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datos"
NIVELES = RAIZ / "fuentes" / "contratacion" / "niveles_estudio_viabilidad.csv"
DOC = RAIZ / "preguntas.md"
ANIOS = list(range(2017, 2025))
ANIO_22 = 2024                    # único año con liquidación en que los 22 tienen su forma actual
SERIE = list(range(2019, 2025))   # años en que se pueden sumar los 22
ACUM = list(range(2021, 2025))    # acumulado de los ministerios con continuidad directa en los cuatro años
PARTES = ["personal", "compras_inversiones", "prestamos_aportaciones", "transferencias_y_resto"]


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


def main():
    res = {(r["ministerio_actual"], int(r["anio"])): r for r in leer(DATOS / "ficha_resumen.csv")}
    cap = defaultdict(lambda: defaultdict(float))        # (ministerio, año) -> capítulo -> obligaciones
    amb = defaultdict(lambda: defaultdict(float))        # (ministerio, año) -> ámbito -> obligaciones
    for r in leer(DATOS / "ficha_capitulos.csv"):
        k = (r["ministerio_actual"], int(r["anio"]))
        cap[k][r["capitulo"]] += f(r["obligaciones"])
        amb[k][r["ambito"]] += f(r["obligaciones"])
    con = defaultdict(lambda: defaultdict(float))
    for r in leer(DATOS / "contratacion_ministerio.csv"):
        k = (r["ministerio_actual"], int(r["anio"]))
        pr = "licitaciones" if r["procedimiento"] == "licitación" else "menores"
        con[k][pr + "_ordinario"] += f(r["importe_ordinario"])
        con[k]["programas_especiales"] += f(r["programas_especiales_importe"])
        con[k]["adjudicaciones"] += f(r["adjudicaciones"])
    nivel = {r["ministerio_actual"]: r["nivel"] for r in leer(NIVELES)}

    ctrl = []

    def control(que, a, b, tol, nota=""):
        ctrl.append(dict(control=que, valor_a=a, valor_b=b, diferencia=a - b, tolerancia=tol,
                         correcto="sí" if abs(a - b) <= tol else "NO", nota=nota))

    filas = []
    for (mi, a), r in sorted(res.items()):
        if a not in ANIOS or r["gasto_agregado_sin_doble_computo"] == "":
            continue
        k = (mi, a)
        gasto = f(r["gasto_agregado_sin_doble_computo"])
        estado, org = f(r["estado_obligaciones"]), f(r["organismos_obligaciones"])
        reconstruido = r["continuidad_estado"] == "reconstruido"
        if not reconstruido:
            control(f"{a} · {corto(mi)} · Estado: suma de capítulos = obligaciones de la ficha", amb[k]["Estado"], estado, 1)
        control(f"{a} · {corto(mi)} · organismos: suma de capítulos = obligaciones de la ficha", amb[k]["Organismos"], org, 1)
        control(f"{a} · {corto(mi)} · gasto agregado = Estado + organismos − transferencias restadas − devuelto al Estado",
                estado + org - f(r["transferencias_restadas"]) - f(r["transferencias_de_sus_organismos_al_estado"]),
                gasto, 1)
        c = cap[k]
        v = dict(ministerio_actual=mi, anio=a, continuidad=r["continuidad_estado"], nivel_contratacion=nivel[mi],
                 gasto_agregado=gasto, personal=c["1"], compras_inversiones=c["2"] + c["6"],
                 prestamos_aportaciones=c["8"])
        v["transferencias_y_resto"] = gasto - v["personal"] - v["compras_inversiones"] - v["prestamos_aportaciones"]
        # Agricultura 2017-2018: el Estado está reconstruido y no tiene capítulos; la composición no se da
        v["composicion"] = "no (Estado reconstruido, sin capítulos)" if reconstruido else "sí"
        for x in PARTES:
            v["pct_" + x] = round(100 * v[x] / gasto, 2) if gasto and not reconstruido else None
        cc = con.get(k, {})
        v.update(licitaciones_ordinario=cc.get("licitaciones_ordinario", 0.0), menores_ordinario=cc.get("menores_ordinario", 0.0),
                 programas_especiales=cc.get("programas_especiales", 0.0), adjudicaciones=cc.get("adjudicaciones", 0.0))
        v["contratacion_ordinaria"] = v["licitaciones_ordinario"] + v["menores_ordinario"]
        # sin los contratos menores de importe atípico (más de 60.500 € con IVA), que el script 09 trata como errores
        v["adjudicado_total"] = v["contratacion_ordinaria"] + v["programas_especiales"]
        v["pct_ordinaria_sobre_gasto"] = round(100 * v["contratacion_ordinaria"] / gasto, 2) if gasto else None
        v["pct_adjudicado_sobre_compras_inversiones"] = (round(100 * v["adjudicado_total"] / v["compras_inversiones"], 1)
                                                         if v["compras_inversiones"] and not reconstruido else None)
        v["fuente"] = ("IGAE, liquidación del Estado y de sus organismos (datos/ficha_*.csv); PLACSP, línea base del "
                       "proyecto de Defensa (datos/contratacion_ministerio.csv)")
        filas.append(v)
    escribir(DATOS / "contratacion_gasto.csv", filas,
             ["ministerio_actual", "anio", "continuidad", "nivel_contratacion", "gasto_agregado", "composicion", *PARTES,
              *["pct_" + x for x in PARTES], "adjudicaciones", "licitaciones_ordinario", "menores_ordinario",
              "contratacion_ordinaria", "programas_especiales", "adjudicado_total", "pct_ordinaria_sobre_gasto",
              "pct_adjudicado_sobre_compras_inversiones", "fuente"])
    F = {(v["ministerio_actual"], v["anio"]): v for v in filas}
    mins = sorted({v["ministerio_actual"] for v in filas})

    # el año de los 22: la suma de las licitaciones ordinarias es la de la tabla del README (script 11)
    cm = {(r["ministerio_actual"], int(r["anio"])): r for r in leer(DATOS / "comparativa_ministerios.csv")}
    for mi in mins:
        if (mi, ANIO_22) in cm:
            control(f"{ANIO_22} · {corto(mi)} · licitaciones ordinarias = comparativa_ministerios.csv",
                    F[(mi, ANIO_22)]["licitaciones_ordinario"], f(cm[(mi, ANIO_22)]["contratacion_importe_ordinario"]), 1)
            control(f"{ANIO_22} · {corto(mi)} · gasto agregado = comparativa_ministerios.csv",
                    F[(mi, ANIO_22)]["gasto_agregado"], f(cm[(mi, ANIO_22)]["gasto_agregado_sin_doble_computo"]), 1)
    for v in filas:
        if v["composicion"] == "sí":
            control(f"{v['anio']} · {corto(v['ministerio_actual'])} · transferencias y resto no negativo",
                    min(v["transferencias_y_resto"], 0.0), 0.0, 1)
    def tot(a, campo):
        return sum(F[(mi, a)][campo] for mi in mins if (mi, a) in F)

    # ---------- tablas
    T = {}
    t = ["| Ministerio actual | Gasto agregado | Personal, % | Compras e inversiones, % | Préstamos y aportaciones, % | "
         "Transferencias y resto, % | Licitaciones ordinarias | Contratos menores | Adjudicado ordinario, % del gasto | "
         "Programas especiales | Adjudicado total / compras e inversiones, % | Nivel |",
         "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :---: |"]
    for mi in sorted(mins, key=lambda n: -F[(n, ANIO_22)]["gasto_agregado"]):
        v = F[(mi, ANIO_22)]
        t.append(f"| {corto(mi)} | {m(v['gasto_agregado'])} | " + " | ".join(p(v[x], v["gasto_agregado"]) for x in PARTES)
                 + f" | {m(v['licitaciones_ordinario'])} | {m(v['menores_ordinario'])} | "
                 f"{p(v['contratacion_ordinaria'], v['gasto_agregado'])} | {m(v['programas_especiales'])} | "
                 f"{p(v['adjudicado_total'], v['compras_inversiones'], 0)} | {v['nivel_contratacion']} |")
    g = tot(ANIO_22, "gasto_agregado")
    t.append(f"| **22 ministerios** | **{m(g)}** | " + " | ".join(f"**{p(tot(ANIO_22, x), g)}**" for x in PARTES)
             + f" | **{m(tot(ANIO_22, 'licitaciones_ordinario'))}** | **{m(tot(ANIO_22, 'menores_ordinario'))}** | "
             f"**{p(tot(ANIO_22, 'contratacion_ordinaria'), g)}** | **{m(tot(ANIO_22, 'programas_especiales'))}** | "
             f"**{p(tot(ANIO_22, 'adjudicado_total'), tot(ANIO_22, 'compras_inversiones'), 0)}** | |")
    T["contratacion_gasto_2024"] = "\n".join(t)

    # serie de los 22 juntos: solo compras e inversiones y contratación. El gasto agregado de los 22 no se suma antes
    # de 2024: los organismos de los ministerios que aún no existían (p. ej. MUFACE) no están en ficha_resumen.csv
    todos = sorted({mi for (mi, a) in cap})
    c26 = {a: sum(cap[(mi, a)]["2"] + cap[(mi, a)]["6"] for mi in todos if (mi, a) in cap) for a in SERIE}
    adj = {a: {x: sum(con[(mi, a)][x] for mi in todos if (mi, a) in con)
               for x in ("licitaciones_ordinario", "menores_ordinario", "programas_especiales")}
           for a in SERIE}
    control(f"{ANIO_22} · compras e inversiones de los 22: suma de ficha_capitulos.csv = suma de las filas del año",
            c26[ANIO_22], tot(ANIO_22, "compras_inversiones"), 1)
    t = ["| 22 ministerios | " + " | ".join(str(a) for a in SERIE) + " |", "| --- | " + " | ".join("---:" for _ in SERIE) + " |"]
    filas_serie = [("Compras e inversiones (capítulos 2 y 6, Estado y organismos)", lambda a: m(c26[a])),
                   ("Licitaciones ordinarias", lambda a: m(adj[a]["licitaciones_ordinario"])),
                   ("Contratos menores", lambda a: m(adj[a]["menores_ordinario"])),
                   ("Programas especiales", lambda a: m(adj[a]["programas_especiales"])),
                   ("Adjudicado ordinario / compras e inversiones, %",
                    lambda a: p(adj[a]["licitaciones_ordinario"] + adj[a]["menores_ordinario"], c26[a], 0)),
                   ("Adjudicado total / compras e inversiones, %", lambda a: p(sum(adj[a].values()), c26[a], 0))]
    for et, fn in filas_serie:
        t.append(f"| {et} | " + " | ".join(fn(a) for a in SERIE) + " |")
    T["contratacion_gasto_serie"] = "\n".join(t)

    t = ["| Ministerio actual | " + " | ".join(str(a) for a in SERIE) + " |", "| --- | " + " | ".join("---:" for _ in SERIE) + " |"]
    for mi in sorted(mins, key=lambda n: -F[(n, ANIO_22)]["gasto_agregado"]):
        c = [p(F[(mi, a)]["contratacion_ordinaria"], F[(mi, a)]["gasto_agregado"])
             if (mi, a) in F and F[(mi, a)]["continuidad"] == "directa" else "—" for a in SERIE]
        t.append(f"| {corto(mi)} | " + " | ".join(c) + " |")
    T["contratacion_gasto_ministerio_serie"] = "\n".join(t)

    estables = [mi for mi in mins if all((mi, a) in F and F[(mi, a)]["continuidad"] == "directa" for a in ACUM)]
    t = [f"| Ministerio actual | Compras e inversiones {ACUM[0]}-{ACUM[-1]} | Adjudicado ordinario | Programas especiales | "
         "Adjudicado total / compras e inversiones, % |", "| --- | ---: | ---: | ---: | ---: |"]
    s = lambda mi, campo: sum(F[(mi, a)][campo] for a in ACUM)
    for mi in sorted(estables, key=lambda n: -s(n, "compras_inversiones")):
        t.append(f"| {corto(mi)} | {m(s(mi, 'compras_inversiones'))} | {m(s(mi, 'contratacion_ordinaria'))} | "
                 f"{m(s(mi, 'programas_especiales'))} | {p(s(mi, 'adjudicado_total'), s(mi, 'compras_inversiones'), 0)} |")
    T["contratacion_gasto_acumulado"] = "\n".join(t)

    escribir(DATOS / "controles_contratacion_gasto.csv", ctrl,
             ["control", "valor_a", "valor_b", "diferencia", "tolerancia", "correcto", "nota"])

    texto = DOC.read_text(encoding="utf-8")
    hechas = 0
    for nombre, tabla in T.items():
        texto, n = re.subn(rf"<!-- tabla:{nombre} -->.*?<!-- /tabla -->",
                           lambda _: f"<!-- tabla:{nombre} -->\n{tabla}\n<!-- /tabla -->", texto, flags=re.S)
        hechas += n
    DOC.write_text(texto, encoding="utf-8")

    malos = [c for c in ctrl if c["correcto"] != "sí"]
    print(f"{len(filas)} filas en contratacion_gasto.csv; {len(ctrl)} controles, {len(malos)} incorrectos; "
          f"preguntas.md: {hechas} de {len(T)} marcas")
    for c in malos:
        print("  CONTROL INCORRECTO:", c["control"], c["valor_a"], c["valor_b"])
    for nombre, tabla in T.items():
        print(f"\n[{nombre}]\n{tabla}")


if __name__ == "__main__":
    main()
