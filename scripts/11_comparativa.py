"""Fase 3 · Comparativa común de los 22 ministerios.

Entradas (datos/): ficha_resumen.csv, ficha_capitulos.csv, mrr_secciones.csv, contratacion_ministerio.csv;
fuentes/contratacion/linea_base_cierre.csv (cuotas de noviembre-diciembre de todo el periodo) y
fuentes/contratacion/niveles_estudio_viabilidad.csv (niveles A/B/C, intervalos y corrección por comparaciones
múltiples del estudio de viabilidad del 30/10/2026, transcritos de su anexo).

Reglas:
- Los 22 solo son comparables a la vez en 2024 (liquidación) y 2025 (provisional, solo Estado): son los años en que
  todos tienen su estructura actual. Los dos se ejecutan con el mismo presupuesto, el de 2023 prorrogado.
- Las series de varios años solo usan los años con `continuidad = directa`. Los «con cambios» se marcan.
- Contratación: el periodo completo 2017-2025 (sin 2026, incompleto). Se concluye solo en el nivel A, o en el B si
  coinciden dos indicadores; el nivel C se muestra sin orden (reglas de lectura del estudio).

Salidas:
  datos/comparativa_ministerios.csv   ministerio × año: indicadores comunes (ejecución, modificaciones, composición,
                                      gasto agregado, Mecanismo de Recuperación, contratación)
  datos/comparativa_contratacion.csv  ministerio: cuota de noviembre-diciembre 2017-2025 frente a la AGE sin él,
                                      con el nivel y el intervalo del estudio
  comparativa.md                      tablas entre las marcas <!-- tabla:… --> y <!-- /tabla -->
  README.md                           tabla de los 22 ministerios entre las marcas <!-- tabla:ministerios --> y <!-- /tabla -->
"""
import csv
import re
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datos"
LB = RAIZ / "fuentes" / "contratacion" / "linea_base_cierre.csv"
NIVELES = RAIZ / "fuentes" / "contratacion" / "niveles_estudio_viabilidad.csv"
DOC = RAIZ / "comparativa.md"
LEEME = RAIZ / "README.md"
FICHAS = {"Ministerio de Defensa": "defensa", "Ministerio del Interior": "interior",
          "Ministerio de Agricultura, Pesca y Alimentación": "agricultura", "Ministerio de Hacienda": "hacienda",
          "Ministerio de Transportes y Movilidad Sostenible": "transportes",
          "Ministerio para la Transición Ecológica y el Reto Demográfico": "transicion_ecologica",
          "Ministerio de Ciencia, Innovación y Universidades": "ciencia",
          "Ministerio de Trabajo y Economía Social": "trabajo",
          "Ministerio de Inclusión, Seguridad Social y Migraciones": "inclusion",
          "Ministerio de Cultura": "cultura",
          "Ministerio de la Presidencia, Justicia y Relaciones con las Cortes": "presidencia_justicia",
          "Ministerio de Asuntos Exteriores, Unión Europea y Cooperación": "asuntos_exteriores",
          "Ministerio de Economía, Comercio y Empresa": "economia", "Ministerio de Sanidad": "sanidad",
          "Ministerio de Industria y Turismo": "industria",
          "Ministerio de Educación, Formación Profesional y Deportes": "educacion",
          "Ministerio de Política Territorial y Memoria Democrática": "politica_territorial",
          "Ministerio de Igualdad": "igualdad",
          "Ministerio para la Transformación Digital y de la Función Pública": "transformacion_digital",
          "Ministerio de Juventud e Infancia": "juventud_infancia",
          "Ministerio de Vivienda y Agenda Urbana": "vivienda",
          "Ministerio de Derechos Sociales, Consumo y Agenda 2030": "derechos_sociales"}
ULTIMO_LIQ = "2024"
MENSUAL = "2025"


def leer(p, sep=";", enc="utf-8"):
    with open(p, encoding=enc) as fh:
        return list(csv.DictReader(fh, delimiter=sep))


def f(x):
    return float(x.replace(",", ".")) if x not in ("", None) else None


def fmt(x):
    if x is None:
        return ""
    if isinstance(x, float):
        return str(int(round(x))) if abs(x - round(x)) < 1e-9 else f"{x:.4f}".rstrip("0").replace(".", ",")
    return x


def m(x, dec=0):
    if x is None:
        return "—"
    s = f"{x / 1e6:,.{dec}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def p(x, dec=1, signo=False):
    if x is None:
        return "—"
    s = f"{x:+.{dec}f}" if signo else f"{x:.{dec}f}"
    return s.replace(".", ",")


def corto(mi):
    return re.sub(r"^Ministerio (de la |del |de |para la )", "", mi)


def div(a, b):
    return 100 * a / b if a is not None and b else None


def main():
    res = leer(DATOS / "ficha_resumen.csv")
    cap = leer(DATOS / "ficha_capitulos.csv")
    mrr = leer(DATOS / "mrr_secciones.csv")
    con = leer(DATOS / "contratacion_ministerio.csv")
    niv = {r["ministerio_actual"]: r for r in leer(NIVELES)}
    ministerios = sorted({r["ministerio_actual"] for r in res}, key=corto)
    assert set(niv) == set(ministerios), set(niv) ^ set(ministerios)

    capit = defaultdict(float)
    for r in cap:
        if r["ambito"] == "Estado":
            capit[(r["ministerio_actual"], r["anio"], int(r["capitulo"]))] += f(r["obligaciones"]) or 0
    mrr_o = defaultdict(float)
    for r in mrr:
        mrr_o[(r["ministerio_actual"], r["anio"])] += f(r["obligaciones"]) or 0
    lic = {(r["ministerio_actual"], r["anio"]): r for r in con if r["procedimiento"] == "licitación"}

    # --- ministerio × año
    filas = []
    for r in res:
        mi, a = r["ministerio_actual"], r["anio"]
        ini, de, ob = f(r["estado_creditos_iniciales"]), f(r["estado_creditos_definitivos"]), f(r["estado_obligaciones"])
        tot_cap = sum(v for (mm, aa, _), v in capit.items() if mm == mi and aa == a)
        c = lambda *ks: sum(capit.get((mi, a, k), 0.0) for k in ks) if tot_cap else None
        fila = dict(
            ministerio_actual=mi, ministerio=corto(mi), anio=int(a), presupuesto=r["presupuesto"], dato=r["dato"],
            continuidad=r["continuidad_estado"], nivel_contratacion=niv[mi]["nivel"],
            estado_creditos_iniciales=ini, estado_creditos_definitivos=de, estado_obligaciones=ob,
            pct_obligaciones_sobre_iniciales=div(ob, ini), pct_obligaciones_sobre_definitivos=div(ob, de),
            pct_modificaciones_sobre_iniciales=div(f(r["estado_modificaciones_netas"]), ini))
        for k in ("creditos_extraordinarios_suplementos", "ampliaciones", "transferencias", "incorporacion_remanentes",
                  "generaciones_ingresos", "bajas_otras_modificaciones"):
            fila[f"pct_{k}_sobre_iniciales"] = div(f(r[f"estado_{k}"]), ini)
        fila.update(
            pct_cap1_personal=div(c(1), tot_cap), pct_cap2_bienes_servicios=div(c(2), tot_cap),
            pct_cap4_7_transferencias=div(c(4, 7), tot_cap), pct_cap6_inversiones=div(c(6), tot_cap),
            pct_cap8_9_financieros=div(c(8, 9), tot_cap),
            organismos_obligaciones=f(r["organismos_obligaciones"]),
            gasto_agregado_sin_doble_computo=f(r["gasto_agregado_sin_doble_computo"]),
            transferencias_de_otros_ministerios=f(r["transferencias_de_otros_ministerios"]),
            mrr_obligaciones=mrr_o.get((mi, a)) if int(a) >= 2021 else None,
            pct_mrr_sobre_obligaciones_estado=div(mrr_o.get((mi, a)), ob) if int(a) >= 2021 else None)
        li = lic.get((mi, a))
        fila.update(contratacion_importe_ordinario=f(li["importe_ordinario"]) if li else None,
                    contratacion_pct_nov_dic=f(li["pct_importe_ordinario_nov_dic"]) if li else None,
                    contratacion_resto_age_pct_nov_dic=f(li["resto_age_pct_importe_ordinario_nov_dic"]) if li else None)
        filas.append(fila)
    campos = list(filas[0].keys())
    with open(DATOS / "comparativa_ministerios.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(campos)
        for r in filas:
            w.writerow([fmt(r.get(k)) for k in campos])
    F = {(r["ministerio_actual"], str(r["anio"])): r for r in filas}

    # --- contratación 2017-2025 a partir de la línea base: cuota de noviembre-diciembre del importe ordinario
    s = defaultdict(lambda: [0.0, 0.0, 0.0])  # (grupo, año) -> ordinario, ordinario nov-dic, adjudicaciones ordinarias
    for r in leer(LB, enc="utf-8-sig"):
        if r["bloque"] not in ("Defensa", "Resto de la AGE") or r["es_contrato_menor"] != "No" or r["anio"] == "2026":
            continue
        x = s[(r["grupo"], r["anio"])]
        x[0] += f(r["importe_ordinario_eur"])
        x[1] += f(r["importe_ordinario_eur"]) if r["periodo"] == "Nov-dic" else 0
        x[2] += f(r["n_ordinario"])
    anios_c = sorted({a for _, a in s})
    fc = []
    for mi in ministerios:
        o = sum(s[(mi, a)][0] for a in anios_c)
        nd = sum(s[(mi, a)][1] for a in anios_c)
        n = sum(s[(mi, a)][2] for a in anios_c)
        ro = sum(v[0] for (g, a), v in s.items() if g != mi)
        rnd = sum(v[1] for (g, a), v in s.items() if g != mi)
        encima = sum(1 for a in anios_c if s[(mi, a)][0] and sum(v[0] for (g, aa), v in s.items() if aa == a and g != mi)
                     and s[(mi, a)][1] / s[(mi, a)][0] > sum(v[1] for (g, aa), v in s.items() if aa == a and g != mi)
                     / sum(v[0] for (g, aa), v in s.items() if aa == a and g != mi))
        nv = niv[mi]
        fc.append(dict(ministerio_actual=mi, ministerio=corto(mi), nivel=nv["nivel"], adjudicaciones_ordinarias=n,
                       importe_ordinario=o, pct_nov_dic=div(nd, o), resto_age_pct_nov_dic=div(rnd, ro),
                       dif_pp=div(nd, o) - div(rnd, ro), anios_por_encima=encima, anios=len(anios_c),
                       estudio_ic95=f"[{nv['ic95_inferior_pp']}; {nv['ic95_superior_pp']}]",
                       estudio_distinto_tras_correccion=nv["distinto_tras_correccion"],
                       estudio_dif_dentro_de_tipos_pp=f(nv["dif_dentro_de_tipos_pp"]),
                       estudio_dif_oferta_unica_pp=f(nv["dif_oferta_unica_pp"]),
                       estudio_oferta_unica_distinta=nv["oferta_unica_distinta_tras_correccion"],
                       fuente="línea base PLACSP 2017-2025 (importe ordinario de licitaciones); intervalos y corrección: "
                              "estudio de viabilidad del 30/10/2026"))
    campos = list(fc[0].keys())
    with open(DATOS / "comparativa_contratacion.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(campos)
        for r in fc:
            w.writerow([fmt(r.get(k)) for k in campos])

    # --- tablas de comparativa.md
    T = {}
    orden24 = sorted(ministerios, key=lambda mi: -(F[(mi, ULTIMO_LIQ)]["gasto_agregado_sin_doble_computo"] or 0))
    t = ["| Ministerio | Iniciales | Definitivos | Obligaciones | Oblig. / iniciales | Oblig. / definitivos | "
         "Organismos: obligaciones | Gasto agregado | Mecanismo de Recuperación, % de las obligaciones |",
         "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    tot = defaultdict(float)
    for mi in orden24:
        r = F[(mi, ULTIMO_LIQ)]
        t.append(f"| {r['ministerio']} | {m(r['estado_creditos_iniciales'])} | {m(r['estado_creditos_definitivos'])} | "
                 f"{m(r['estado_obligaciones'])} | {p(r['pct_obligaciones_sobre_iniciales'])} | "
                 f"{p(r['pct_obligaciones_sobre_definitivos'])} | {m(r['organismos_obligaciones'])} | "
                 f"{m(r['gasto_agregado_sin_doble_computo'])} | {p(r['pct_mrr_sobre_obligaciones_estado'])} |")
        for k in ("estado_creditos_iniciales", "estado_creditos_definitivos", "estado_obligaciones",
                  "organismos_obligaciones", "gasto_agregado_sin_doble_computo", "mrr_obligaciones"):
            tot[k] += r[k] or 0
    t.append(f"| **22 ministerios** | {m(tot['estado_creditos_iniciales'])} | {m(tot['estado_creditos_definitivos'])} | "
             f"{m(tot['estado_obligaciones'])} | {p(div(tot['estado_obligaciones'], tot['estado_creditos_iniciales']))} | "
             f"{p(div(tot['estado_obligaciones'], tot['estado_creditos_definitivos']))} | {m(tot['organismos_obligaciones'])} | "
             f"{m(tot['gasto_agregado_sin_doble_computo'])} | {p(div(tot['mrr_obligaciones'], tot['estado_obligaciones']))} |")
    T["tamano"] = "\n".join(t)

    orden25 = sorted(ministerios, key=lambda mi: -(F[(mi, MENSUAL)]["pct_obligaciones_sobre_iniciales"] or 0))
    t = ["| Ministerio | Oblig. / iniciales 2024 | Oblig. / iniciales 2025 (prov.) | Modificaciones netas 2025, % de iniciales | "
         "Ampliaciones | Transferencias | Créd. extraord. y suplementos | Remanentes y generaciones | Oblig. / definitivos 2025 |",
         "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for mi in orden25:
        r, r4 = F[(mi, MENSUAL)], F[(mi, ULTIMO_LIQ)]
        rg = None if r["pct_incorporacion_remanentes_sobre_iniciales"] is None else \
            r["pct_incorporacion_remanentes_sobre_iniciales"] + r["pct_generaciones_ingresos_sobre_iniciales"]
        t.append(f"| {r['ministerio']} | {p(r4['pct_obligaciones_sobre_iniciales'])} | {p(r['pct_obligaciones_sobre_iniciales'])} | "
                 f"{p(r['pct_modificaciones_sobre_iniciales'], signo=True)} | "
                 f"{p(r['pct_ampliaciones_sobre_iniciales'], signo=True)} | {p(r['pct_transferencias_sobre_iniciales'], signo=True)} | "
                 f"{p(r['pct_creditos_extraordinarios_suplementos_sobre_iniciales'], signo=True)} | {p(rg, signo=True)} | "
                 f"{p(r['pct_obligaciones_sobre_definitivos'])} |")
    T["prorroga"] = "\n".join(t)

    t = ["| Ministerio | Personal (1) | Bienes y servicios (2) | Transferencias (4 y 7) | Inversiones (6) | Financieros (8 y 9) |",
         "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for mi in sorted(ministerios, key=lambda mi: -(F[(mi, ULTIMO_LIQ)]["pct_cap4_7_transferencias"] or 0)):
        r = F[(mi, ULTIMO_LIQ)]
        t.append(f"| {r['ministerio']} | {p(r['pct_cap1_personal'])} | {p(r['pct_cap2_bienes_servicios'])} | "
                 f"{p(r['pct_cap4_7_transferencias'])} | {p(r['pct_cap6_inversiones'])} | {p(r['pct_cap8_9_financieros'])} |")
    T["composicion"] = "\n".join(t)

    anios = [str(a) for a in range(2017, 2026)]
    t = ["| Ministerio | " + " | ".join(anios) + " |", "| --- | " + " | ".join("---:" for _ in anios) + " |"]
    for mi in ministerios:
        cel = []
        for a in anios:
            r = F.get((mi, a))
            if not r or r["pct_obligaciones_sobre_definitivos"] is None:
                cel.append("·")
            else:
                cel.append(p(r["pct_obligaciones_sobre_definitivos"]) + ("" if r["continuidad"] == "directa" else "*"))
        t.append(f"| {corto(mi)} | " + " | ".join(cel) + " |")
    T["serie"] = "\n".join(t)

    t = ["| Ministerio | Obligaciones 2021-2025 | % ejecutado (oblig. / definitivos) | Peso en sus obligaciones, 2024 | Peso, 2025 (prov.) |",
         "| --- | ---: | ---: | ---: | ---: |"]
    dm = defaultdict(lambda: [0.0, 0.0])
    for r in mrr:
        dm[r["ministerio_actual"]][0] += f(r["creditos_definitivos"]) or 0
        dm[r["ministerio_actual"]][1] += f(r["obligaciones"]) or 0
    for mi in sorted(dm, key=lambda k: -dm[k][1]):
        t.append(f"| {corto(mi)} | {m(dm[mi][1])} | {p(div(dm[mi][1], dm[mi][0]))} | "
                 f"{p(F[(mi, ULTIMO_LIQ)]['pct_mrr_sobre_obligaciones_estado'])} | {p(F[(mi, MENSUAL)]['pct_mrr_sobre_obligaciones_estado'])} |")
    t.append(f"| **Total** | {m(sum(v[1] for v in dm.values()))} | {p(div(sum(v[1] for v in dm.values()), sum(v[0] for v in dm.values())))} | | |")
    T["mrr"] = "\n".join(t)

    t = ["| Nivel | Ministerio | Adjudicaciones ordinarias | Importe ordinario (M€) | Nov-dic, % | AGE sin él, % | Diferencia (pp) | "
         "IC 95 % del estudio | Distinto tras corregir | Años por encima (de 9) | Oferta única, dif. (pp) |",
         "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- | ---: | ---: |"]
    for nivel in ("A", "B", "C"):
        grupo = [r for r in fc if r["nivel"] == nivel]
        grupo.sort(key=(lambda r: -r["dif_pp"]) if nivel != "C" else (lambda r: r["ministerio"]))
        for r in grupo:
            ou = p(r["estudio_dif_oferta_unica_pp"], signo=True) + ("*" if r["estudio_oferta_unica_distinta"] == "sí" else "")
            n_adj = f"{int(r['adjudicaciones_ordinarias']):,}".replace(",", ".")
            dif = p(r["dif_pp"], signo=True) if nivel != "C" else "(no concluyente)"
            t.append(f"| {nivel} | {r['ministerio']} | {n_adj} | {m(r['importe_ordinario'])} | {p(r['pct_nov_dic'])} | "
                     f"{p(r['resto_age_pct_nov_dic'])} | {dif} | {r['estudio_ic95']} | "
                     f"{r['estudio_distinto_tras_correccion']} | {r['anios_por_encima']} | {ou} |")
    T["contratacion"] = "\n".join(t)

    # Lo que no se gasta (definitivos − obligaciones) de los 22, con el capítulo 8 y el Mecanismo (se solapan)
    sm = {(r["anio"], r["codigo_seccion"]): r["ministerio_actual"] for r in leer(DATOS / "secciones_ministerio_actual.csv")
          if r["tipo"] == "Ministerio"}
    ne = defaultdict(lambda: defaultdict(float))
    for r in leer(DATOS / "liquidacion_seccion_capitulo.csv"):
        mi = sm.get((r["anio"], r["codigo_seccion"]))
        if mi:
            d = (f(r["creditos_definitivos"]) or 0) - (f(r["obligaciones"]) or 0)
            ne[r["anio"]]["total"] += d
            ne[r["anio"]][("min", mi)] += d
            if r["capitulo"] == "8":
                ne[r["anio"]]["cap8"] += d
    for r in mrr:
        if r["anio"] in ne:
            ne[r["anio"]]["mrr"] += (f(r["creditos_definitivos"]) or 0) - (f(r["obligaciones"]) or 0)
    t = ["| Año | Créditos definitivos sin gastar (22 ministerios) | De ello, capítulo 8 | % | De ello, Mecanismo de Recuperación | % | Ministerio con más | Su importe |",
         "| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: |"]
    for a in sorted(ne):
        x = ne[a]
        top = max((k for k in x if isinstance(k, tuple)), key=lambda k: x[k])
        t.append(f"| {a} | {m(x['total'])} | {m(x['cap8'])} | {p(div(x['cap8'], x['total']), 0)} | "
                 f"{m(x['mrr']) if int(a) >= 2021 else '—'} | {p(div(x['mrr'], x['total']), 0) if int(a) >= 2021 else '—'} | "
                 f"{corto(top[1])} | {m(x[top])} |")
    T["sin_gastar"] = "\n".join(t)

    # --- tabla de los 22 ministerios del README (un ministerio por fila, con enlace a su ficha)
    assert set(FICHAS) == set(ministerios), set(FICHAS) ^ set(ministerios)
    t = ["| Ministerio (ficha) | Obligaciones del Estado 2024 | 2025 (prov.) | Oblig. / iniciales 2024, % | "
         "Gasto de sus organismos 2024 | Gasto agregado 2024 | Contratación ordinaria 2024 | "
         "Mecanismo de Recuperación, obligaciones 2021-2025 | Contratación: nivel |",
         "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :---: |"]
    for mi in orden24:
        assert (RAIZ / "fichas" / f"{FICHAS[mi]}.md").exists(), FICHAS[mi]
        r, r25 = F[(mi, ULTIMO_LIQ)], F[(mi, MENSUAL)]
        t.append(f"| [{corto(mi)}](fichas/{FICHAS[mi]}.md) | {m(r['estado_obligaciones'])} | {m(r25['estado_obligaciones'])} | "
                 f"{p(r['pct_obligaciones_sobre_iniciales'])} | {m(r['organismos_obligaciones'])} | "
                 f"{m(r['gasto_agregado_sin_doble_computo'])} | {m(r['contratacion_importe_ordinario'])} | "
                 f"{m(dm[mi][1])} | {r['nivel_contratacion']} |")
    suma = lambda k, a=ULTIMO_LIQ: sum(F[(mi, a)][k] or 0 for mi in ministerios)
    t.append(f"| **22 ministerios** | {m(suma('estado_obligaciones'))} | {m(suma('estado_obligaciones', MENSUAL))} | "
             f"{p(div(suma('estado_obligaciones'), suma('estado_creditos_iniciales')))} | {m(suma('organismos_obligaciones'))} | "
             f"{m(suma('gasto_agregado_sin_doble_computo'))} | {m(suma('contratacion_importe_ordinario'))} | "
             f"{m(sum(v[1] for v in dm.values()))} | |")
    leeme = LEEME.read_text(encoding="utf-8")
    leeme, n = re.subn(r"<!-- tabla:ministerios -->.*?<!-- /tabla -->",
                       "<!-- tabla:ministerios -->\n" + "\n".join(t) + "\n<!-- /tabla -->", leeme, flags=re.S)
    assert n == 1, "README.md: falta la marca tabla:ministerios"
    LEEME.write_text(leeme, encoding="utf-8")

    texto = DOC.read_text(encoding="utf-8")
    for nombre, tabla in T.items():
        texto, n = re.subn(rf"<!-- tabla:{nombre} -->.*?<!-- /tabla -->", f"<!-- tabla:{nombre} -->\n{tabla}\n<!-- /tabla -->",
                           texto, flags=re.S)
        assert n == 1, nombre
    DOC.write_text(texto, encoding="utf-8")
    print(f"{len(filas)} filas ministerio-año; {len(fc)} ministerios en contratación; comparativa.md y README.md actualizados")
    for r in fc:
        print(f"  {r['nivel']} {r['ministerio'][:40]:40} {p(r['pct_nov_dic'])} vs {p(r['resto_age_pct_nov_dic'])} "
              f"({p(r['dif_pp'], signo=True)}) estudio {niv[r['ministerio_actual']]['cuota_nov_dic_pct']} "
              f"({niv[r['ministerio_actual']]['dif_frente_age_sin_el_pp']})")


if __name__ == "__main__":
    main()
