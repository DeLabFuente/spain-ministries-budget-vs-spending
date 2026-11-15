"""Pregunta 12 · ¿Qué parte de lo que el Estado transfiere a las comunidades autónomas se reconoce en diciembre? (2025)

Transferencias del Estado a las comunidades autónomas = artículo 45 (transferencias corrientes) y artículo 75
(transferencias de capital) de la clasificación económica. Se leen de los anexos por aplicación (anexo I «PGE» y
anexo II «no PGE») de las doce ediciones de 2025 de las Estadísticas de ejecución del Presupuesto de la IGAE
(art. 135 LGP), con el lector del script 01: cada edición da las obligaciones reconocidas netas acumuladas del
año hasta ese mes, línea a línea. De ahí salen, por ministerio actual, el calendario mensual de estas
transferencias y las líneas que se reconocen de golpe al final del año.

Qué mide: el momento en que se reconoce la obligación (no el pago ni la llegada a la comunidad). Solo el Estado
(no lo que reciben las comunidades a través de organismos o de la Seguridad Social) y solo 2025, que es
provisional. 2024 solo sale a nivel del Estado en conjunto (las tablas de los artículos 45 y 75 traen la cifra
del mismo mes de 2024; los anexos por aplicación de las ediciones de 2025 no).

Las secciones no ministeriales (sobre todo la 38, sistemas de financiación de entes territoriales) llevan la
mayor parte del artículo 45 y quedan fuera de los 22 ministerios: se muestran aparte para que cuadre con el Estado.

Entradas:
  fuentes/igae/mensual/mensual_01-25.pdf … mensual_12-25.pdf (texto en fuentes/igae/_texto/, con pdftotext -layout;
      la variable de entorno IGAE_TEXTO cambia la carpeta del texto)
  fuentes/igae/_intermedios/liquidacion_aplicaciones.csv (script 01; aplicaciones 2020-2024 para la serie anual)
  datos/secciones_ministerio_actual.csv, datos/mensual_ministerio_mes.csv, datos/mensual_resumen.csv
Salidas:  datos/transferencias_ccaa_anual.csv (2020-2025 por ministerio), datos/transferencias_ccaa_mes.csv, datos/transferencias_ccaa_resumen.csv, datos/transferencias_ccaa_lineas.csv,
          datos/transferencias_ccaa_estado.csv, datos/controles_transferencias_ccaa.csv,
          preguntas.md (marcas <!-- tabla:transf_… -->)
Uso: python scripts/31_transferencias_ccaa.py   (ejecutar después del 18 y del 28)
"""
import importlib.util
import os
import re
import subprocess
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datos"
DOC = RAIZ / "preguntas.md"
PDFS = RAIZ / "fuentes" / "igae" / "mensual"
TXT = Path(os.environ.get("IGAE_TEXTO", RAIZ / "fuentes" / "igae" / "_texto"))
MESES = list(range(1, 13))
NOMBRE_MES = ["", "ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
TODOS = "22 ministerios"
ARTS = ("45", "75")

spec18 = importlib.util.spec_from_file_location("s18", Path(__file__).with_name("18_catastrofes.py"))
s18 = importlib.util.module_from_spec(spec18)
spec18.loader.exec_module(s18)
f, m, p, corto, leer, escribir = s18.f, s18.m, s18.p, s18.corto, s18.leer, s18.escribir
s01 = s18.lector_01()


def num(s):
    s = s.strip()
    if s in ("-", ""):
        return 0
    return int(s.replace(".", "")) if re.fullmatch(r"-?[\d.]+", s) else None


def paginas(mes):
    t = TXT / f"mensual_{mes:02d}-25.txt"
    if not t.exists():
        TXT.mkdir(parents=True, exist_ok=True)
        subprocess.run(["pdftotext", "-layout", str(PDFS / f"mensual_{mes:02d}-25.pdf"), str(t)], check=True,
                       stderr=subprocess.DEVNULL)
    return t.read_text(encoding="utf-8").split("\f")


def totales_articulo(pags, art):
    """TOTALES de la tabla «Ejecución art. 45 / 75» (Estado, miles de euros): (2025, 2024) obligaciones y créditos."""
    out = None
    for i, pg in enumerate(pags, 1):
        cab = "\n".join(pg.splitlines()[:8]).upper()
        if f"EJECUCIÓN ART. {art}:" not in cab or "HASTA EL" not in cab:
            continue
        for linea in pg.split("\n"):
            toks = [x for x in re.split(r"\s{2,}", linea.strip()) if x]
            if toks and toks[0] == "TOTALES" and len(toks) >= 7:
                vals = [num(x) for x in toks[1:7]]
                out = dict(cred25=vals[0] * 1000, obl25=vals[1] * 1000, cred24=vals[3] * 1000, obl24=vals[4] * 1000, pagina=i)
    return out


def main():
    ma = {r["codigo_seccion"]: r for r in leer(DATOS / "secciones_ministerio_actual.csv") if r["anio"] == "2025"}
    ctrl = []

    def control(que, a, b, tol=0, nota=""):
        ctrl.append(dict(control=que, valor_a=a, valor_b=b, diferencia=a - b, tolerancia=tol,
                         correcto="sí" if abs(a - b) <= tol else "NO", nota=nota))

    # ---- lectura: línea × mes (obligaciones acumuladas) -------------------------------------------------------
    lineas = defaultdict(dict)       # (anexo, servicio, programa, economica) -> {mes: (obl, creditos def.)}
    desc = {}
    pagina = {}
    estado = {}
    for mes in MESES:
        pags = paginas(mes)
        apps, resumen, _ = s01.leer_anexo(pags, 2025)
        n = 0
        for a in apps:
            if a["economica"][:2] not in ARTS:
                continue
            k = (a["anexo"], a["servicio"], a["programa_completo"], a["economica"])
            if mes in lineas[k]:                          # la misma aplicación leída dos veces: se suma
                o, c = lineas[k][mes]
                lineas[k][mes] = (o + a["obligaciones"], c + a["creditos_definitivos"])
            else:
                lineas[k][mes] = (a["obligaciones"], a["creditos_definitivos"])
            desc[k] = re.sub(r"\s+", " ", a["descripcion"]).strip()
            if (k[1], k[2], k[3]) == ("3104", "231G", "451"):      # REGISTRO A38: la descripción no parece corresponder al programa
                desc[k] = "[descripción no publicada; REGISTRO A38]"
            pagina[(k, mes)] = a["pagina"]
            n += 1
        for art in ARTS:
            t = totales_articulo(pags, art)
            estado[(art, mes)] = t
            s_ob = sum(lineas[k][mes][0] for k in lineas if k[3][:2] == art and mes in lineas[k])
            control(f"{NOMBRE_MES[mes]} 2025 · art. {art} · tabla TOTALES encontrada", int(t is not None), 1)
            if t:
                control(f"{NOMBRE_MES[mes]} 2025 · art. {art} · suma de las aplicaciones de los anexos = TOTALES de la tabla del artículo",
                        s_ob, t["obl25"], 5000, "la tabla da miles de euros y su TOTALES suma importes ya redondeados: hasta 5.000 € de diferencia")
        control(f"{NOMBRE_MES[mes]} 2025 · aplicaciones de los artículos 45 y 75 leídas (> 300)", int(n > 300), 1)

    # ---- sección -> grupo (ministerio actual o sección no ministerial) ---------------------------------------
    def grupo(srv):
        r = ma.get(srv[:2])
        return (r["ministerio_actual"], r["tipo"]) if r else (f"Sección {srv[:2]} (sin equivalencia)", "Sección no ministerial")

    # acumulado por grupo × artículo × mes
    acum = defaultdict(float)
    cred = defaultdict(float)
    grupos = {}
    for k, v in lineas.items():
        g, tipo = grupo(k[1])
        grupos[g] = tipo
        art = k[3][:2]
        for mes in MESES:
            o, c = v.get(mes, (None, None))
            if o is None:
                # una línea sin fila en el mes cuenta como 0 antes de su primera aparición y, si ya apareció, como el mes anterior
                prev = [mm for mm in MESES if mm < mes and mm in v]
                o, c = (v[prev[-1]] if prev else (0.0, 0.0))
            for a_ in (art, "45+75"):
                acum[(g, a_, mes)] += o
                cred[(g, a_, mes)] += c
                if tipo == "Ministerio":
                    acum[(TODOS, a_, mes)] += o
                    cred[(TODOS, a_, mes)] += c
    mins = sorted(g for g, t in grupos.items() if t == "Ministerio")
    nomin = sorted(g for g, t in grupos.items() if t != "Ministerio")
    orden_g = mins + [TODOS] + nomin
    for mes in MESES:
        for art in ARTS:
            tot = sum(acum[(g, art, mes)] for g in grupos)
            control(f"{NOMBRE_MES[mes]} 2025 · art. {art} · ministerios + secciones no ministeriales = suma de las aplicaciones", tot,
                    sum(lineas[k][mes][0] for k in lineas if k[3][:2] == art and mes in lineas[k]), 2000,
                    "las líneas sin fila en un mes se llevan del mes anterior; la diferencia son líneas que desaparecen de la edición")

    # ---- CSV por mes -----------------------------------------------------------------------------------------
    fuente = "IGAE, Estadísticas de ejecución del Presupuesto (art. 135 LGP), ediciones de enero a diciembre de 2025, anexos I y II (euros)"
    out = []
    for g in orden_g:
        tipo = "Ministerio" if g in mins or g == TODOS else grupos[g]
        for art in ("45", "75", "45+75"):
            fin = acum[(g, art, 12)]
            ant = 0.0
            for mes in MESES:
                o = acum[(g, art, mes)]
                out.append(dict(anio=2025, mes=mes, grupo=g, tipo=tipo, articulo=art, obligaciones_acumuladas=o,
                                obligaciones_del_mes=o - ant, creditos_definitivos=cred[(g, art, mes)],
                                pct_del_anio=round(100 * o / fin, 2) if fin else "", dato="provisional", fuente=fuente))
                ant = o
    escribir(DATOS / "transferencias_ccaa_mes.csv", out,
             ["anio", "mes", "grupo", "tipo", "articulo", "obligaciones_acumuladas", "obligaciones_del_mes",
              "creditos_definitivos", "pct_del_anio", "dato", "fuente"])

    # ---- Estado en conjunto, 2024 y 2025 (tablas de los artículos) -------------------------------------------
    est = []
    for art in ARTS:
        for mes in MESES:
            t = estado[(art, mes)]
            est.append(dict(articulo=art, mes=mes, obligaciones_2025=t["obl25"], creditos_2025=t["cred25"],
                            obligaciones_2024=t["obl24"], creditos_2024=t["cred24"], pagina=t["pagina"]))
    escribir(DATOS / "transferencias_ccaa_estado.csv", est,
             ["articulo", "mes", "obligaciones_2025", "creditos_2025", "obligaciones_2024", "creditos_2024", "pagina"])
    E = {(r["articulo"], r["mes"]): r for r in est}
    for art in ARTS:
        prev = [0, 0]
        for mes in MESES:
            for k, anio in ((0, 2025), (1, 2024)):
                o = E[(art, mes)][f"obligaciones_{anio}"]
                control(f"{anio} · art. {art} · {NOMBRE_MES[mes]} · acumulado no baja respecto al mes anterior (tolerancia 1 M€)",
                        min(o - prev[k], 0), 0, 1e6)
                prev[k] = o

    # ---- por línea -------------------------------------------------------------------------------------------
    def serie(v):
        s, ult = [], 0.0
        for mes in MESES:
            if mes in v:
                ult = v[mes][0]
            s.append(ult)
        return s

    lin = []
    for k, v in lineas.items():
        s = serie(v)
        g, tipo = grupo(k[1])
        primer = next((mes for mes, o in zip(MESES, s) if o > 0), None)
        lin.append(dict(anio=2025, grupo=g, tipo=tipo, anexo=k[0], servicio=k[1], programa=k[2], economica=k[3],
                        articulo=k[3][:2], descripcion=desc[k], creditos_definitivos_dic=v[max(v)][1],
                        obligaciones_nov=s[10], obligaciones_dic=s[11], aumento_dic=s[11] - s[10],
                        pct_en_dic=round(100 * (s[11] - s[10]) / s[11], 2) if s[11] > 0 else "",
                        primer_mes_con_obligaciones=primer if primer else "", solo_dic="sí" if s[10] <= 0 < s[11] else "no",
                        pagina_dic=pagina.get((k, 12), "")))
    lin.sort(key=lambda r: -r["aumento_dic"])
    escribir(DATOS / "transferencias_ccaa_lineas.csv", lin,
             ["anio", "grupo", "tipo", "anexo", "servicio", "programa", "economica", "articulo", "descripcion",
              "creditos_definitivos_dic", "obligaciones_nov", "obligaciones_dic", "aumento_dic", "pct_en_dic",
              "primer_mes_con_obligaciones", "solo_dic", "pagina_dic"])
    L = {g: [r for r in lin if r["grupo"] == g or (g == TODOS and r["tipo"] == "Ministerio")] for g in orden_g}
    control("líneas: suma de obligaciones de diciembre = suma de los grupos (45+75)", sum(r["obligaciones_dic"] for r in lin),
            sum(acum[(g, "45+75", 12)] for g in grupos), 2000)

    # ---- resumen por grupo -----------------------------------------------------------------------------------
    gasto = {}
    for r in leer(DATOS / "mensual_ministerio_mes.csv"):
        if r["anio"] == "2025" and r["mes"] == "12":
            gasto[r["ministerio_actual"]] = f(r["obligaciones_acumuladas"])
    gdic = {r["ministerio_actual"]: f(r["pct_dic_2025"]) for r in leer(DATOS / "mensual_resumen.csv")}
    gnd = {r["ministerio_actual"]: f(r["pct_nov_dic_2025"]) for r in leer(DATOS / "mensual_resumen.csv")}

    def pc(g, art, hasta):
        fin = acum[(g, art, 12)]
        return 100 * acum[(g, art, hasta)] / fin if fin else None

    res = []
    for g in orden_g:
        fin = acum[(g, "45+75", 12)]
        r = dict(grupo=g, tipo="Ministerio" if g in mins or g == TODOS else grupos[g],
                 art45_2025=acum[(g, "45", 12)], art75_2025=acum[(g, "75", 12)], transferencias_2025=fin,
                 gasto_total_2025=gasto.get(g, ""),
                 pct_del_gasto=round(100 * fin / gasto[g], 2) if gasto.get(g) else "",
                 lineas_con_obligaciones=sum(1 for x in L[g] if x["obligaciones_dic"] > 0))
        for mes in (6, 9, 10, 11):
            v = pc(g, "45+75", mes)
            r[f"pct_hasta_{NOMBRE_MES[mes]}"] = round(v, 2) if v is not None else ""
        r["pct_nov_dic"] = round(100 - pc(g, "45+75", 10), 2) if fin else ""
        r["pct_dic"] = round(100 - pc(g, "45+75", 11), 2) if fin else ""
        r["pct_dic_art45"] = round(100 - pc(g, "45", 11), 2) if acum[(g, "45", 12)] else ""
        r["pct_dic_art75"] = round(100 - pc(g, "75", 11), 2) if acum[(g, "75", 12)] else ""
        r["pct_dic_gasto_total"] = gdic.get(g, "")
        r["pct_nov_dic_gasto_total"] = gnd.get(g, "")
        solo = sum(x["obligaciones_dic"] for x in L[g] if x["solo_dic"] == "sí")
        r["pct_lineas_solo_dic"] = round(100 * solo / fin, 2) if fin else ""
        res.append(r)
    escribir(DATOS / "transferencias_ccaa_resumen.csv", res,
             ["grupo", "tipo", "art45_2025", "art75_2025", "transferencias_2025", "gasto_total_2025", "pct_del_gasto",
              "lineas_con_obligaciones", "pct_hasta_jun", "pct_hasta_sep", "pct_hasta_oct", "pct_hasta_nov", "pct_nov_dic",
              "pct_dic", "pct_dic_art45", "pct_dic_art75", "pct_dic_gasto_total", "pct_nov_dic_gasto_total", "pct_lineas_solo_dic"])
    R = {r["grupo"]: r for r in res}
    control("22 ministerios · gasto total de diciembre de 2025 = suma de los ministerios de datos/mensual_ministerio_mes.csv",
            gasto[TODOS], sum(v for g, v in gasto.items() if g != TODOS), 1000)
    for g in mins:
        if gasto.get(g):
            control(f"{corto(g)} · transferencias a CCAA no superan el gasto total del ministerio", min(gasto[g] - acum[(g, '45+75', 12)], 0), 0)

    # ---- serie anual 2020-2025 (liquidación 2020-2024: anexos por aplicación; 2025: la mensual de diciembre) ---
    maa = {(int(r["anio"]), r["codigo_seccion"]): r for r in leer(DATOS / "secciones_ministerio_actual.csv")}
    anual = defaultdict(float)
    for r in leer(s18.APLIC):
        art = r["economica"][:2]
        if art not in ARTS:
            continue
        x = maa.get((int(r["anio"]), r["seccion"]))
        g = x["ministerio_actual"] if x else f"Sección {r['seccion']} (sin equivalencia)"
        tipo = x["tipo"] if x else "Sección no ministerial"
        anual[(int(r["anio"]), g, art)] += f(r["obligaciones"])
        if tipo == "Ministerio":
            anual[(int(r["anio"]), TODOS, art)] += f(r["obligaciones"])
        anual[(int(r["anio"]), "Estado", art)] += f(r["obligaciones"])
    for g in orden_g + ["Estado"]:
        for art in ARTS:
            anual[(2025, g, art)] = acum[(g, art, 12)] if g != "Estado" else sum(acum[(h, art, 12)] for h in grupos)
    gasto_anio = defaultdict(float)
    for (anio, cod), r in maa.items():
        if r["tipo"] == "Ministerio":
            gasto_anio[(anio, r["ministerio_actual"])] += f(r["obligaciones"])
            gasto_anio[(anio, TODOS)] += f(r["obligaciones"])
    ANIOS = list(range(2020, 2026))
    cambios = {(anio, r["ministerio_actual"]) for (anio, cod), r in maa.items() if r["tipo"] == "Ministerio" and r["continuidad"] != "directa"}
    gr_anual = sorted({k[1] for k in anual if k[1] != "Estado"}, key=lambda g: (g not in mins and g != TODOS, g))
    out_a = []
    for anio in ANIOS:
        for g in gr_anual + ["Estado"]:
            a45, a75 = anual.get((anio, g, "45"), 0.0), anual.get((anio, g, "75"), 0.0)
            gt = gasto_anio.get((anio, g))
            out_a.append(dict(anio=anio, grupo=g, tipo="Ministerio" if (g in mins or g == TODOS) else ("Estado" if g == "Estado" else "Sección no ministerial"),
                              art45=a45, art75=a75, transferencias=a45 + a75, gasto_total=gt if gt else "",
                              pct_del_gasto=round(100 * (a45 + a75) / gt, 2) if gt else "",
                              dato="provisional (mensual de diciembre)" if anio == 2025 else "definitivo (liquidación)"))
    escribir(DATOS / "transferencias_ccaa_anual.csv", out_a,
             ["anio", "grupo", "tipo", "art45", "art75", "transferencias", "gasto_total", "pct_del_gasto", "dato"])
    for art in ARTS:
        control(f"2024 · art. {art} · suma de las aplicaciones de la liquidación = TOTALES (comparativo de 2024) de la tabla de la mensual de diciembre",
                anual[(2024, "Estado", art)], estado[(art, 12)]["obl24"], 10000, "liquidación de 2024 (euros) frente al comparativo publicado en la edición de 2025 (miles redondeados); diferencia de menos de 8.000 €")
    for g in gr_anual:
        control(f"2025 · {corto(g)} · serie anual = obligaciones de diciembre del calendario (45+75)",
                anual[(2025, g, "45")] + anual[(2025, g, "75")], acum[(g, "45+75", 12)] if g in grupos or g == TODOS else 0.0, 1)

    # ---- tablas ----------------------------------------------------------------------------------------------
    pcs = lambda x: "—" if x in (None, "") else f"{float(x):.1f}".replace(".", ",")
    T = {}

    t = ["| Mes (acumulado al fin del mes) | Art. 45 · 2025, M€ | % del año 2025 | % del año 2024 | Art. 75 · 2025, M€ | % del año 2025 | % del año 2024 |",
         "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for mes in MESES:
        c = []
        for art in ARTS:
            e, e12 = E[(art, mes)], E[(art, 12)]
            c += [m(e["obligaciones_2025"]), p(e["obligaciones_2025"], e12["obligaciones_2025"]), p(e["obligaciones_2024"], e12["obligaciones_2024"])]
        t.append(f"| {NOMBRE_MES[mes].capitalize()} | " + " | ".join(c) + " |")
    T["transf_estado"] = "\n".join(t)

    t = ["| Quién lo reconoce (2025) | Art. 45, M€ | Art. 75, M€ | Total, M€ | Hasta septiembre, % | Noviembre-diciembre, % | Solo diciembre, % |",
         "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for g in [TODOS] + nomin:
        r = R[g]
        if r["transferencias_2025"] == 0:
            continue
        b = "**" if g == TODOS else ""
        t.append(f"| {b}{g}{b} | {m(r['art45_2025'])} | {m(r['art75_2025'])} | {m(r['transferencias_2025'])} | "
                 f"{pcs(r['pct_hasta_sep'])} | {pcs(r['pct_nov_dic'])} | {pcs(r['pct_dic'])} |")
    tot45 = sum(R[g]["art45_2025"] for g in [TODOS] + nomin)
    tot75 = sum(R[g]["art75_2025"] for g in [TODOS] + nomin)
    sep = sum(acum[(g, "45+75", 9)] for g in [TODOS] + nomin)
    oct_ = sum(acum[(g, "45+75", 10)] for g in [TODOS] + nomin)
    nov = sum(acum[(g, "45+75", 11)] for g in [TODOS] + nomin)
    t.append(f"| **Estado (artículos 45 y 75)** | {m(tot45)} | {m(tot75)} | {m(tot45 + tot75)} | {p(sep, tot45 + tot75)} | "
             f"{p(tot45 + tot75 - oct_, tot45 + tot75)} | {p(tot45 + tot75 - nov, tot45 + tot75)} |")
    T["transf_perimetro"] = "\n".join(t)

    orden = sorted([g for g in mins if R[g]["transferencias_2025"] > 0], key=lambda g: -(R[g]["transferencias_2025"]))
    t = ["| Ministerio actual | Transferencias a CCAA 2025, M€ | % de su gasto | Hasta septiembre, % | Noviembre-diciembre, % | Solo diciembre, % | Solo diciembre, su gasto total, % | Líneas que aparecen en diciembre, % |",
         "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for g in orden + [TODOS]:
        r = R[g]
        b = "**" if g == TODOS else ""
        t.append(f"| {b}{corto(g) if g != TODOS else g}{b} | {m(r['transferencias_2025'])} | {pcs(r['pct_del_gasto'])} | "
                 f"{pcs(r['pct_hasta_sep'])} | {pcs(r['pct_nov_dic'])} | {pcs(r['pct_dic'])} | {pcs(r['pct_dic_gasto_total'])} | "
                 f"{pcs(r['pct_lineas_solo_dic'])} |")
    T["transf_ministerio"] = "\n".join(t)

    top = [r for r in lin if r["tipo"] == "Ministerio"][:12]
    t = ["| Ministerio | Línea (programa · económica) | Descripción en la IGAE | Reconocido en diciembre, M€ | % de la línea en diciembre |",
         "| --- | --- | --- | ---: | ---: |"]
    for r in top:
        t.append(f"| {corto(r['grupo'])} | {r['programa']} · {r['economica']} | {r['descripcion'][:90]} | {m(r['aumento_dic'])} | {pcs(r['pct_en_dic'])} |")
    T["transf_lineas"] = "\n".join(t)

    A = {(r["anio"], r["grupo"]): r for r in out_a}
    ordm = sorted([g for g in mins if any(A[(a, g)]["transferencias"] > 0 for a in ANIOS)], key=lambda g: -A[(2024, g)]["transferencias"])
    t = ["| Ministerio actual | " + " | ".join(f"{a}, M€" for a in ANIOS) + " | % de su gasto 2024 | % de su gasto 2025 |",
         "| --- |" + " ---: |" * (len(ANIOS) + 2)]
    for g in ordm + [TODOS]:
        b = "**" if g == TODOS else ""
        t.append(f"| {b}{corto(g) if g != TODOS else g}{b} | " + " | ".join(m(A[(a, g)]["transferencias"]) + ("*" if (a, g) in cambios and A[(a, g)]["transferencias"] else "") for a in ANIOS)
                 + f" | {pcs(A[(2024, g)]['pct_del_gasto'])} | {pcs(A[(2025, g)]['pct_del_gasto'])} |")
    for g, nom in (("Sistemas de financiación de entes territoriales", None), ("Estado", "**Estado (artículos 45 y 75)**")):
        if (2024, g) in A:
            t.append(f"| {nom or g} | " + " | ".join(m(A[(a, g)]["transferencias"]) for a in ANIOS) + " | | |")
    T["transf_anual"] = "\n".join(t)

    texto_doc = DOC.read_text(encoding="utf-8")
    hechas = 0
    for nombre, tabla in T.items():
        texto_doc, n = re.subn(rf"<!-- tabla:{nombre} -->.*?<!-- /tabla -->",
                               lambda _: f"<!-- tabla:{nombre} -->\n{tabla}\n<!-- /tabla -->", texto_doc, flags=re.S)
        hechas += n
    DOC.write_text(texto_doc, encoding="utf-8")
    escribir(DATOS / "controles_transferencias_ccaa.csv", ctrl, ["control", "valor_a", "valor_b", "diferencia", "tolerancia", "correcto", "nota"])
    malos = [c for c in ctrl if c["correcto"] != "sí"]
    print(f"{len(lin)} líneas; {len(out)} filas por mes; {len(ctrl)} controles, {len(malos)} incorrectos; "
          f"preguntas.md: {hechas} de {len(T)} marcas")
    for c in malos[:40]:
        print("  CONTROL INCORRECTO:", c["control"], c["valor_a"], c["valor_b"])
    for nombre, tabla in T.items():
        print(f"\n[{nombre}]\n{tabla}")


if __name__ == "__main__":
    main()
