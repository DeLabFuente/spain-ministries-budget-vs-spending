"""Pregunta 1 · ¿Se ejecuta mejor el crédito que se crea durante el año que el del presupuesto? (2020-2025)

Compara, en todas las secciones del Estado, la parte reconocida (obligaciones / crédito definitivo) de cuatro
grupos de líneas presupuestarias (aplicaciones):
  presupuesto, sin cambio   anexo I «PGE», crédito definitivo = crédito inicial
  presupuesto, reducidas    anexo I, crédito definitivo < inicial
  presupuesto, ampliadas    anexo I, crédito definitivo > inicial
  nuevas                    anexo II «no PGE»: no existían en el presupuesto aprobado o prorrogado
y deja aparte las líneas «sin crédito propio» (anexo I, sin crédito inicial ni definitivo, con obligaciones).

Ajuste (REGISTRO B22): cuando la misma aplicación (año, sección, servicio, programa y económica) sale en el
anexo I sin crédito y con obligaciones y en el anexo II con crédito (REGISTRO A29), las obligaciones del anexo I
se cuentan en el grupo «nuevas», junto a su crédito.

El Mecanismo de Recuperación y Resiliencia (servicio SS50, desde 2021) se da por separado: en 2024 y 2025, con
el presupuesto prorrogado, casi todo su crédito está en líneas del anexo II aunque no sea dinero nuevo.

Entradas:
  las del script 18 (aplicaciones 2020-2024 del script 01 y anexos por aplicación de la mensual de 2025) y su
  clasificación de catástrofes (función `clasificar`)
  datos/secciones_ministerio_actual.csv   sección y año -> ministerio actual; control por sección
  datos/mrr_secciones.csv                 control de la marca del Mecanismo

Salidas (separador ';', decimales con coma, UTF-8, importes en euros):
  datos/credito_nuevo_ministerio.csv   año × sección × Mecanismo × grupo × capítulo × catástrofe
  datos/credito_nuevo_resumen.csv      año × Mecanismo × grupo, 22 ministerios (con y sin capítulo 8)
  datos/credito_nuevo_tramos.csv       líneas nuevas de los 22 ministerios por tramo de ejecución
  datos/controles_credito_nuevo.csv    cuadres
  preguntas.md                       tablas entre las marcas <!-- tabla:credito_nuevo_… --> y <!-- /tabla -->
Uso: python scripts/19_credito_nuevo.py
"""
import csv
import importlib.util
import re
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datos"
DOC = RAIZ / "preguntas.md"
ANIO_MENSUAL = 2025
ANIOS = list(range(2020, ANIO_MENSUAL + 1))
TOL_SECCION = 15000   # las tablas por secciones van en miles de euros

G_IGUAL, G_BAJA, G_ALTA, G_NUEVA, G_SIN = ("presupuesto, sin cambio", "presupuesto, reducidas",
                                           "presupuesto, ampliadas", "nuevas (anexo II)", "sin crédito propio")
GRUPOS = [G_IGUAL, G_BAJA, G_ALTA, G_NUEVA, G_SIN]
ETIQUETA = {G_IGUAL: "Líneas del presupuesto, sin cambio", G_BAJA: "Líneas del presupuesto, reducidas",
            G_ALTA: "Líneas del presupuesto, ampliadas", G_NUEVA: "Líneas nuevas (anexo II)",
            G_SIN: "Líneas sin crédito propio"}
TRAMOS = ["0 %", "más de 0 y menos de 50 %", "de 50 a menos de 99 %", "99 % o más"]
C3 = ("creditos_iniciales", "creditos_definitivos", "obligaciones")


def modulo(nombre):
    spec = importlib.util.spec_from_file_location(nombre.split("_")[0], Path(__file__).with_name(nombre))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


s18 = modulo("18_catastrofes.py")
f, fmt, m, p, corto, leer, escribir = s18.f, s18.fmt, s18.m, s18.p, s18.corto, s18.leer, s18.escribir


def es_mrr(r):
    return r["anio"] >= 2021 and r["servicio"][-2:] == "50" and r["servicio"][:2] == r["seccion"]


def tramo(dfn, obl):
    q = obl / dfn
    return TRAMOS[0] if obl == 0 else TRAMOS[1] if q < 0.5 else TRAMOS[2] if q < 0.99 else TRAMOS[3]


def main():
    apps, _, _ = s18.aplicaciones()
    apps = [r for r in apps if r["anio"] in ANIOS]
    sec = {(int(r["anio"]), r["codigo_seccion"]): r for r in leer(DATOS / "secciones_ministerio_actual.csv")}

    # ---------- grupo de cada línea
    clave = lambda r: (r["anio"], r["seccion"], r["servicio"], r["programa"], r["economica"])
    con_credito_ii = {clave(r) for r in apps if r["anexo"] == "II no PGE" and r["creditos_definitivos"] > 0}
    for r in apps:
        info = sec[(r["anio"], r["seccion"])]
        r["ministerio_actual"], r["tipo_seccion"] = info["ministerio_actual"], info["tipo"]
        r["mecanismo"] = "sí" if es_mrr(r) else "no"
        r["capitulo"] = r["economica"][0]
        ini, dfn = round(r["creditos_iniciales"], 2), round(r["creditos_definitivos"], 2)
        r["emparejada"] = False
        if r["anexo"] == "II no PGE":
            r["grupo"] = G_NUEVA
        elif ini == 0 and dfn == 0:
            r["emparejada"] = clave(r) in con_credito_ii
            r["grupo"] = G_NUEVA if r["emparejada"] else G_SIN
        else:
            r["grupo"] = G_IGUAL if dfn == ini else G_BAJA if dfn < ini else G_ALTA
        c = s18.clasificar(r) if r["grupo"] == G_NUEVA and r["mecanismo"] == "no" else None
        r["catastrofe"] = s18.SUCESOS[c[0]] if c else ""

    # ---------- controles
    ctrl = []

    def control(que, a, b, tol, nota=""):
        ctrl.append(dict(control=que, valor_a=a, valor_b=b, diferencia=a - b, tolerancia=tol,
                         correcto="sí" if abs(a - b) <= tol else "NO", nota=nota))

    por_sec = defaultdict(lambda: [0.0, 0.0, 0.0])
    por_mrr = defaultdict(lambda: [0.0, 0.0, 0.0])
    for r in apps:
        for i, k in enumerate(C3):
            por_sec[(r["anio"], r["seccion"])][i] += r[k]
            if r["mecanismo"] == "sí":
                por_mrr[(r["anio"], r["seccion"])][i] += r[k]
    for (a, c), info in sorted(sec.items()):
        if a in ANIOS:
            for i, k in enumerate(C3):
                control(f"{a} · sección {c} · {k}: aplicaciones (anexos I y II) = tabla por secciones",
                        por_sec[(a, c)][i], f(info[k]), TOL_SECCION, "la tabla va en miles de euros")
    vistos = set()
    for r in leer(DATOS / "mrr_secciones.csv"):
        a, c = int(r["anio"]), r["codigo_seccion"]
        vistos.add((a, c))
        for i, k in enumerate(C3):
            control(f"{a} · sección {c} · Mecanismo · {k}: aplicaciones del servicio {c}50 = mrr_secciones.csv",
                    por_mrr[(a, c)][i], f(r[k]), 1000 if a == ANIO_MENSUAL else 0.05,
                    "2025: el capítulo del Mecanismo de la mensual va en miles de euros" if a == ANIO_MENSUAL else "")
    control("Mecanismo: secciones y años con servicio SS50 = secciones y años de mrr_secciones.csv",
            len(set(por_mrr)), len(vistos), 0)

    # ---------- agregado publicable
    ag = defaultdict(lambda: dict(lineas=0, creditos_iniciales=0.0, creditos_definitivos=0.0, obligaciones=0.0))
    for r in apps:
        k = (r["anio"], r["dato"], r["seccion"], r["ministerio_actual"], r["tipo_seccion"], r["mecanismo"],
             GRUPOS.index(r["grupo"]), r["capitulo"], r["catastrofe"])
        ag[k]["lineas"] += 1
        for c in C3:
            ag[k][c] += r[c]
    filas = [dict(anio=k[0], dato=k[1], codigo_seccion=k[2], ministerio_actual=k[3], tipo_seccion=k[4],
                  mecanismo=k[5], grupo=GRUPOS[k[6]], capitulo=k[7], catastrofe=k[8], **ag[k],
                  fuente=("IGAE, Liquidación del Presupuesto del Estado %d, vol. I, anexos por aplicación" % k[0]
                          if k[0] < ANIO_MENSUAL else
                          "IGAE, Estadística mensual de ejecución, diciembre de 2025 (provisional), anexos por aplicación"))
             for k in sorted(ag)]
    escribir(DATOS / "credito_nuevo_ministerio.csv", filas,
             ["anio", "dato", "codigo_seccion", "ministerio_actual", "tipo_seccion", "mecanismo", "grupo", "capitulo",
              "catastrofe", "lineas", *C3, "fuente"])

    # ---------- resumen de los 22 ministerios
    mins = [r for r in filas if r["tipo_seccion"] == "Ministerio"]

    def suma(cond, campo):
        return sum(r[campo] for r in mins if cond(r))

    res = []
    for a in ANIOS:
        for mec in ("no", "sí"):
            for g in GRUPOS:
                c = lambda r: r["anio"] == a and r["mecanismo"] == mec and r["grupo"] == g
                c8 = lambda r: c(r) and r["capitulo"] != "8"
                if not any(c(r) for r in mins):
                    continue
                v = dict(anio=a, mecanismo=mec, grupo=g, lineas=suma(c, "lineas"),
                         **{k: suma(c, k) for k in C3},
                         creditos_definitivos_sin_cap8=suma(c8, "creditos_definitivos"),
                         obligaciones_sin_cap8=suma(c8, "obligaciones"))
                v["pct_obligaciones_sobre_definitivos"] = (round(100 * v["obligaciones"] / v["creditos_definitivos"], 1)
                                                           if v["creditos_definitivos"] > 0 else None)
                v["pct_sin_cap8"] = (round(100 * v["obligaciones_sin_cap8"] / v["creditos_definitivos_sin_cap8"], 1)
                                     if v["creditos_definitivos_sin_cap8"] > 0 else None)
                res.append(v)
    escribir(DATOS / "credito_nuevo_resumen.csv", res,
             ["anio", "mecanismo", "grupo", "lineas", *C3, "pct_obligaciones_sobre_definitivos",
              "creditos_definitivos_sin_cap8", "obligaciones_sin_cap8", "pct_sin_cap8"])
    R = {(v["anio"], v["mecanismo"], v["grupo"]): v for v in res}

    # ---------- líneas nuevas por tramo de ejecución (por aplicación: une las emparejadas con su crédito)
    nuevas = defaultdict(lambda: [0.0, 0.0])
    for r in apps:
        if r["grupo"] == G_NUEVA and r["tipo_seccion"] == "Ministerio":
            k = (r["mecanismo"],) + clave(r)
            nuevas[k][0] += r["creditos_definitivos"]
            nuevas[k][1] += r["obligaciones"]
    tr = defaultdict(lambda: dict(aplicaciones=0, creditos_definitivos=0.0, obligaciones=0.0))
    fuera = defaultdict(lambda: dict(aplicaciones=0, creditos_definitivos=0.0, obligaciones=0.0))
    for (mec, a, *_), (dfn, obl) in nuevas.items():
        dfn, obl = round(dfn, 2), round(obl, 2)   # al céntimo: hay aplicaciones con líneas que se anulan (A37)
        dest = tr[(a, mec, tramo(dfn, obl))] if dfn > 0 else fuera[(a, mec)]
        dest["aplicaciones"] += 1
        dest["creditos_definitivos"] += dfn
        dest["obligaciones"] += obl
    ftr = [dict(anio=a, mecanismo=mec, tramo=t, **tr[(a, mec, t)])
           for a in ANIOS for mec in ("no", "sí") for t in TRAMOS if (a, mec, t) in tr]
    ftr += [dict(anio=a, mecanismo=mec, tramo="sin crédito o con crédito negativo", **v)
            for (a, mec), v in sorted(fuera.items())]
    escribir(DATOS / "credito_nuevo_tramos.csv", ftr,
             ["anio", "mecanismo", "tramo", "aplicaciones", "creditos_definitivos", "obligaciones"])

    # cuadres internos
    for a in ANIOS:
        for i, k in enumerate(C3):
            control(f"{a} · todas las secciones · {k}: agregado por grupo = suma de aplicaciones",
                    sum(r[k] for r in filas if r["anio"] == a), sum(v[i] for (aa, c), v in por_sec.items() if aa == a), 0.05)
        control(f"{a} · 22 ministerios · crédito de líneas nuevas: por tramos = resumen",
                sum(r["creditos_definitivos"] for r in ftr if r["anio"] == a),
                sum(R[(a, mec, G_NUEVA)]["creditos_definitivos"] for mec in ("no", "sí") if (a, mec, G_NUEVA) in R), 0.05)
    escribir(DATOS / "controles_credito_nuevo.csv", ctrl,
             ["control", "valor_a", "valor_b", "diferencia", "tolerancia", "correcto", "nota"])

    # ---------- medidas del ajuste y de sus límites (para el texto)
    emp = defaultdict(float)
    for r in apps:
        if r["emparejada"] and r["tipo_seccion"] == "Ministerio":
            emp[(r["anio"], r["mecanismo"])] += r["obligaciones"]
    exceso = defaultdict(float)   # líneas nuevas que reconocen más que su crédito (crédito de otra línea)
    for (mec, a, *_), (dfn, obl) in nuevas.items():
        if obl > max(dfn, 0) + 0.005:
            exceso[(a, mec)] += obl - max(dfn, 0)

    # cota: obligaciones «sin crédito propio» que podrían ser de líneas nuevas (mismo programa, crédito nuevo sin usar)
    prog = defaultdict(lambda: [0.0, 0.0])
    for r in apps:
        if r["tipo_seccion"] == "Ministerio" and r["grupo"] == G_SIN:
            prog[(r["anio"], r["mecanismo"], r["seccion"], r["servicio"], r["programa"])][0] += r["obligaciones"]
    for (mec, a, se, sv, pr, _), (dfn, obl) in nuevas.items():
        prog[(a, mec, se, sv, pr)][1] += max(dfn - obl, 0.0)
    cota = defaultdict(float)
    for (a, mec, *_), (o, libre) in prog.items():
        cota[(a, mec)] += min(o, libre)

    # ---------- tablas de preguntas.md
    T = {}
    col = lambda a: str(a) if a < ANIO_MENSUAL else f"{a} (prov.)"

    def pct_grupo(mec, g, anios, sin8=False):
        d, o = ("creditos_definitivos_sin_cap8", "obligaciones_sin_cap8") if sin8 else ("creditos_definitivos",
                                                                                         "obligaciones")
        vs = [R.get((a, mec, g)) for a in anios]
        celdas = [p(v[o], v[d]) if v and v[d] > 0 else "—" for v in vs]
        tot = p(sum(v[o] for v in vs if v), sum(v[d] for v in vs if v))
        return celdas, tot

    # 1. tamaño
    t = ["| | " + " | ".join(col(a) for a in ANIOS) + " |", "| --- | " + " | ".join("---:" for _ in ANIOS) + " |"]
    tot_dfn = {a: sum(v["creditos_definitivos"] for (aa, mec, g), v in R.items() if aa == a) for a in ANIOS}
    nue = {a: R[(a, "no", G_NUEVA)]["creditos_definitivos"] for a in ANIOS}
    cat = {a: suma(lambda r: r["anio"] == a and r["catastrofe"] != "", "creditos_definitivos") for a in ANIOS}
    nue_mrr = {a: R[(a, "sí", G_NUEVA)]["creditos_definitivos"] if (a, "sí", G_NUEVA) in R else None for a in ANIOS}
    alta = {a: sum(R[(a, mec, G_ALTA)]["creditos_definitivos"] - R[(a, mec, G_ALTA)]["creditos_iniciales"]
                   for mec in ("no", "sí") if (a, mec, G_ALTA) in R) for a in ANIOS}
    baja = {a: sum(R[(a, mec, G_BAJA)]["creditos_iniciales"] - R[(a, mec, G_BAJA)]["creditos_definitivos"]
                   for mec in ("no", "sí") if (a, mec, G_BAJA) in R) for a in ANIOS}
    t.append("| Crédito definitivo de los 22 ministerios | " + " | ".join(m(tot_dfn[a]) for a in ANIOS) + " |")
    t.append("| En líneas nuevas, sin el Mecanismo | " + " | ".join(m(nue[a]) for a in ANIOS) + " |")
    t.append("| … en % del crédito definitivo | " + " | ".join(p(nue[a], tot_dfn[a]) for a in ANIOS) + " |")
    t.append("| … de ellas, respuesta a catástrofes (apartado 7) | " + " | ".join(m(cat[a]) for a in ANIOS) + " |")
    t.append("| En líneas nuevas del Mecanismo | " + " | ".join(m(nue_mrr[a]) for a in ANIOS) + " |")
    t.append("| Aumento de las líneas del presupuesto ampliadas | " + " | ".join(m(alta[a]) for a in ANIOS) + " |")
    t.append("| Recorte de las líneas del presupuesto reducidas | " + " | ".join(m(baja[a]) for a in ANIOS) + " |")
    T["credito_nuevo_tamano"] = "\n".join(t)

    # 2 y 3. ejecución sin el Mecanismo, con y sin capítulo 8
    for nombre, sin8 in (("credito_nuevo_ejecucion", False), ("credito_nuevo_sin8", True)):
        t = ["| Grupo de líneas | " + " | ".join(col(a) for a in ANIOS) + " | 2020-2025 |",
             "| --- | " + " | ".join("---:" for _ in ANIOS) + " | ---: |"]
        for g in GRUPOS[:4]:
            celdas, tot = pct_grupo("no", g, ANIOS, sin8)
            t.append(f"| {ETIQUETA[g]} | " + " | ".join(celdas) + f" | **{tot}** |")
        if not sin8:
            sc = [R[(a, "no", G_SIN)]["obligaciones"] if (a, "no", G_SIN) in R else 0.0 for a in ANIOS]
            t.append(f"| *{ETIQUETA[G_SIN]} (obligaciones, M€)* | " + " | ".join(m(x) for x in sc) + f" | *{m(sum(sc))}* |")
        T[nombre] = "\n".join(t)

    # 4. Mecanismo
    am = [a for a in ANIOS if a >= 2021]
    t = ["| Grupo de líneas | " + " | ".join(col(a) for a in am) + " |", "| --- | " + " | ".join("---:" for _ in am) + " |"]
    for g in GRUPOS[:4]:
        c = []
        for a in am:
            v = R.get((a, "sí", g))
            c.append("—" if not v or v["creditos_definitivos"] <= 0
                     else f"{m(v['creditos_definitivos'])} · {p(v['obligaciones'], v['creditos_definitivos'])} %")
        t.append(f"| {ETIQUETA[g]} | " + " | ".join(c) + " |")
    sc = [R[(a, "sí", G_SIN)]["obligaciones"] if (a, "sí", G_SIN) in R else 0.0 for a in am]
    t.append(f"| *{ETIQUETA[G_SIN]} (obligaciones, M€)* | " + " | ".join(m(x) for x in sc) + " |")
    T["credito_nuevo_mrr"] = "\n".join(t)

    # 5. líneas nuevas sin el Mecanismo: catástrofes y resto
    t = ["| Líneas nuevas, sin el Mecanismo | " + " | ".join(col(a) for a in ANIOS) + " | 2020-2025, % |",
         "| --- | " + " | ".join("---:" for _ in ANIOS) + " | ---: |"]
    for et, cond in (("Respuesta a catástrofes (apartado 7)", lambda r: r["catastrofe"] != ""),
                     ("Resto", lambda r: r["catastrofe"] == "")):
        c, td, to = [], 0.0, 0.0
        for a in ANIOS:
            cc = lambda r: r["anio"] == a and r["mecanismo"] == "no" and r["grupo"] == G_NUEVA and cond(r)
            d, o = suma(cc, "creditos_definitivos"), suma(cc, "obligaciones")
            td, to = td + d, to + o
            c.append("—" if d <= 0 else f"{m(d)} · {p(o, d)} %")
        t.append(f"| {et} | " + " | ".join(c) + f" | **{p(to, td)}** |")
    T["credito_nuevo_catastrofes"] = "\n".join(t)

    # 6. tramos (sin el Mecanismo)
    t = ["| Parte reconocida de la línea nueva | " + " | ".join(col(a) for a in ANIOS) + " | 2020-2025 | Aplicaciones |",
         "| --- | " + " | ".join("---:" for _ in ANIOS) + " | ---: | ---: |"]
    td = {a: sum(tr[(a, "no", x)]["creditos_definitivos"] for x in TRAMOS if (a, "no", x) in tr) for a in ANIOS}
    for x in TRAMOS:
        v = [tr[(a, "no", x)]["creditos_definitivos"] if (a, "no", x) in tr else 0.0 for a in ANIOS]
        n = sum(tr[(a, "no", x)]["aplicaciones"] for a in ANIOS if (a, "no", x) in tr)
        t.append(f"| {x} | " + " | ".join(p(v[i], td[a]) for i, a in enumerate(ANIOS))
                 + f" | **{p(sum(v), sum(td.values()))}** | " + f"{n:,}".replace(",", ".") + " |")
    T["credito_nuevo_tramos"] = "\n".join(t)

    # 7. por ministerio (sin el Mecanismo, 2020-2025)
    mi = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))
    for r in mins:
        if r["mecanismo"] == "no":
            mi[r["ministerio_actual"]][r["grupo"]][0] += r["creditos_definitivos"]
            mi[r["ministerio_actual"]][r["grupo"]][1] += r["obligaciones"]
    t = ["| Ministerio actual | Crédito en líneas nuevas | % de su crédito | Reconocido: líneas nuevas, % | "
         "ampliadas, % | sin cambio, % | reducidas, % |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for nombre in sorted(mi, key=lambda n: -mi[n][G_NUEVA][0]):
        v = mi[nombre]
        tot = sum(x[0] for x in v.values())
        pg = lambda g: p(v[g][1], v[g][0]) if v[g][0] > 0 else "—"
        t.append(f"| {corto(nombre)} | {m(v[G_NUEVA][0])} | {p(v[G_NUEVA][0], tot)} | {pg(G_NUEVA)} | {pg(G_ALTA)} | "
                 f"{pg(G_IGUAL)} | {pg(G_BAJA)} |")
    T["credito_nuevo_ministerio"] = "\n".join(t)

    texto = DOC.read_text(encoding="utf-8")
    hechas = 0
    for nombre, tabla in T.items():
        texto, n = re.subn(rf"<!-- tabla:{nombre} -->.*?<!-- /tabla -->",
                           lambda _: f"<!-- tabla:{nombre} -->\n{tabla}\n<!-- /tabla -->", texto, flags=re.S)
        hechas += n
    DOC.write_text(texto, encoding="utf-8")

    malos = [c for c in ctrl if c["correcto"] != "sí"]
    print(f"{len(apps)} líneas; {len(filas)} filas en credito_nuevo_ministerio.csv; {len(ctrl)} controles, "
          f"{len(malos)} incorrectos; preguntas.md: {hechas} de {len(T)} marcas")
    for c in malos:
        print("  CONTROL INCORRECTO:", c["control"], c["valor_a"], c["valor_b"])
    print("  Obligaciones del anexo I contadas con su crédito del anexo II (M€), 22 ministerios:",
          ", ".join(f"{a} {'Mec.' if mec == 'sí' else 'resto'}: {m(v, 1)}" for (a, mec), v in sorted(emp.items())))
    print("  Líneas nuevas que reconocen más que su crédito (exceso, M€):",
          ", ".join(f"{a} {'Mec.' if mec == 'sí' else 'resto'}: {m(v, 1)}" for (a, mec), v in sorted(exceso.items())))
    print("  Cota de obligaciones «sin crédito propio» que podrían ser de líneas nuevas (M€):",
          ", ".join(f"{a} {'Mec.' if mec == 'sí' else 'resto'}: {m(v, 1)}" for (a, mec), v in sorted(cota.items()) if v))
    for nombre, tabla in T.items():
        print(f"\n[{nombre}]\n{tabla}")


if __name__ == "__main__":
    main()
