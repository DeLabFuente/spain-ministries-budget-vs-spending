"""Tablas para Power BI (modelo en estrella) a partir de datos/ y de la línea base de contratación.

Salidas (powerbi/), CSV con `;`, coma decimal y UTF-8, como el resto del proyecto:
  dim_ministerio.csv         22 ministerios (+ «AGE · ministerio sin identificar», solo en contratación). Clave:
                             ministerio_id = código de su sección en 2024 (99 para el sin identificar). Nivel A/B/C de
                             contratación con el intervalo del estudio de viabilidad y perfil de gasto en 2024.
  dim_anio.csv               2017-2026: presupuesto aprobado o prorrogado, tipo de dato y qué hay cada año; con el calendario
                             de prórroga y de Gobiernos en funciones (días del año, días con presupuesto prorrogado, días con
                             el Gobierno en funciones; salen de datos/calendario_*.csv, script 17).
  dim_gobierno.csv           los cuatro Gobiernos del periodo: fechas, días en funciones y días con presupuesto prorrogado.
  dim_capitulo.csv           capítulos 1-9 con su nombre y su tipo (corriente, capital, financiero).
  fact_ministerio_anio.csv   ministerio × año: Estado (iniciales, cada tipo de modificación, definitivos, obligaciones,
                             pagos), organismos, transferencias, gasto agregado y Mecanismo de Recuperación.
  fact_capitulo.csv          ministerio × año × ámbito (Estado / Organismos) × capítulo: definitivos y obligaciones.
  fact_programa.csv          ministerio × año × programa del Estado (2020-2024): iniciales, definitivos, obligaciones.
  fact_mrr_programa.csv      ministerio × año × programa × capítulo del Mecanismo (2021-2025).
  fact_ingresos_organismos.csv  ministerio × año × organismo × origen del ingreso.
  fact_contratacion_mes.csv  ministerio × año × mes × procedimiento × tipo de contrato: sumas de la línea base (solo AGE).

Uso: python scripts/12_powerbi.py (después de 07, 09, 10 y 11).
"""
import csv
import re
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datos"
SALIDA = RAIZ / "powerbi"
LB = RAIZ / "fuentes" / "contratacion" / "linea_base_cierre.csv"
NIVELES = RAIZ / "fuentes" / "contratacion" / "niveles_estudio_viabilidad.csv"
SIN_ID = "AGE · ministerio sin identificar"
CAPITULOS = {1: ("Gastos de personal", "corriente"), 2: ("Gastos corrientes en bienes y servicios", "corriente"),
             3: ("Gastos financieros", "corriente"), 4: ("Transferencias corrientes", "corriente"),
             5: ("Fondo de contingencia y otros imprevistos", "corriente"), 6: ("Inversiones reales", "capital"),
             7: ("Transferencias de capital", "capital"), 8: ("Activos financieros", "financiero"),
             9: ("Pasivos financieros", "financiero")}


def leer(p, enc="utf-8"):
    with open(p, encoding=enc) as fh:
        return list(csv.DictReader(fh, delimiter=";"))


def f(x):
    return float(x.replace(",", ".")) if x not in ("", None) else None


def fmt(x):
    if x is None:
        return ""
    if isinstance(x, float):
        x = round(x, 4)
        return str(int(x)) if x.is_integer() else f"{x}".replace(".", ",")
    return x


def escribir(nombre, filas, campos):
    SALIDA.mkdir(exist_ok=True)
    with open(SALIDA / nombre, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(campos)
        for r in filas:
            w.writerow([fmt(r.get(k)) for k in campos])
    print(f"{nombre}: {len(filas)} filas")


def corto(mi):
    return re.sub(r"^Ministerio (de la |del |de |para la )", "", mi)


def main():
    sma = leer(DATOS / "secciones_ministerio_actual.csv")
    res = leer(DATOS / "ficha_resumen.csv")
    comp = {(r["ministerio_actual"], r["anio"]): r for r in leer(DATOS / "comparativa_ministerios.csv")}
    niv = {r["ministerio_actual"]: r for r in leer(NIVELES)}

    # --- dim_ministerio
    ids = {r["ministerio_actual"]: int(r["codigo_seccion"]) for r in sma if r["anio"] == "2024" and r["tipo"] == "Ministerio"}
    assert len(ids) == 22, len(ids)
    dim_m = []
    for mi, i in sorted(ids.items(), key=lambda z: z[1]):
        c = comp[(mi, "2024")]
        cuotas = {"personal": f(c["pct_cap1_personal"]) or 0, "transferencias": f(c["pct_cap4_7_transferencias"]) or 0,
                  "inversiones": f(c["pct_cap6_inversiones"]) or 0, "financiero": f(c["pct_cap8_9_financieros"]) or 0,
                  "bienes y servicios": f(c["pct_cap2_bienes_servicios"]) or 0}
        perfil = max(cuotas, key=cuotas.get)
        nv = niv[mi]
        dim_m.append(dict(ministerio_id=i, ministerio=mi, ministerio_corto=corto(mi), es_ministerio="sí",
                          seccion_2024=f"{i:02d}", perfil_gasto_2024=perfil, perfil_pct_2024=cuotas[perfil],
                          nivel_contratacion=nv["nivel"], estudio_dif_pp=f(nv["dif_frente_age_sin_el_pp"]),
                          estudio_ic95_inferior=f(nv["ic95_inferior_pp"]), estudio_ic95_superior=f(nv["ic95_superior_pp"]),
                          estudio_distinto_tras_correccion=nv["distinto_tras_correccion"],
                          estudio_dif_oferta_unica_pp=f(nv["dif_oferta_unica_pp"]),
                          estudio_oferta_unica_distinta=nv["oferta_unica_distinta_tras_correccion"]))
    dim_m.append(dict(ministerio_id=99, ministerio=SIN_ID, ministerio_corto="Ministerio sin identificar (AGE)",
                      es_ministerio="no", seccion_2024=""))
    ids[SIN_ID] = 99
    escribir("dim_ministerio.csv", dim_m, list(dim_m[0].keys()))

    # --- dim_anio
    pres = {r["anio"]: r["presupuesto"] for r in res}
    dato = {r["anio"]: r["dato"] for r in res}
    con_org = {r["anio"] for r in res if r["organismos_obligaciones"]}

    # calendario de prórroga y de Gobiernos en funciones (datos/calendario_*.csv, script 17)
    def d_(x):
        return date.fromisoformat(x) if x else None

    def dmy(d):
        return d.strftime("%d/%m/%Y")

    def solape(a1, a2, b1, b2):
        """Días (ambos extremos incluidos) comunes a [a1, a2] y [b1, b2]."""
        i, j = max(a1, b1), min(a2, b2)
        return (j - i).days + 1 if j >= i else 0

    cal_p = {int(r["anio"]): r for r in leer(DATOS / "calendario_presupuestos.csv")}
    gob = leer(DATOS / "calendario_gobiernos.csv")
    tramos = leer(DATOS / "calendario_tramos.csv")
    corte = d_(cal_p[2026]["fecha_corte"])
    prorr = [(d_(t["desde"]), d_(t["hasta"])) for t in tramos if t["situacion"] == "prorrogado"]
    funciones = [(d_(g["cese_en_funciones_el"]), d_(g["hasta"])) for g in gob if g["cese_en_funciones_el"]]
    cal = {}
    for a in range(2017, 2027):
        i, j = date(a, 1, 1), min(date(a, 12, 31), corte)
        x = cal_p[a]
        propio = {"prorrogado todo el año": "Prorrogado todo el año",
                  "presupuesto propio todo el año": "Presupuesto propio todo el año"}.get(x["situacion"])
        if propio is None:
            e = d_(x["entrada_en_vigor_ley_del_anio"])
            propio = f"Prorrogado hasta el {dmy(e - timedelta(days=1))} y presupuesto propio desde el {dmy(e)}"  # sin «;»: dim_anio se lee con QuoteStyle.None
        d_prorr = sum(solape(i, j, *t) for t in prorr)
        d_func = sum(solape(i, j, *t) for t in funciones)
        d_ambos = sum(solape(max(i, f1), min(j, f2), *t) for f1, f2 in funciones for t in prorr
                      if solape(i, j, f1, f2) and solape(max(i, f1), min(j, f2), *t))
        assert (j - i).days + 1 == int(x["dias_anio"]), (a, (j - i).days + 1, x["dias_anio"])
        assert d_prorr == int(x["dias_prorrogado"]), (a, d_prorr, x["dias_prorrogado"])
        cal[a] = dict(dias_anio=int(x["dias_anio"]), dias_prorrogado=d_prorr,
                      dias_presupuesto_propio=int(x["dias_anio"]) - d_prorr,
                      pct_prorrogado=round(100 * d_prorr / int(x["dias_anio"]), 1),
                      dias_en_funciones=d_func, dias_en_funciones_y_prorrogado=d_ambos,
                      situacion_presupuesto=propio)
    # control cruzado con la tabla de Gobiernos (script 17): mismos días en funciones y en funciones con prórroga
    assert sum(c["dias_en_funciones"] for c in cal.values()) == sum(int(g["dias_en_funciones"]) for g in gob)
    assert sum(c["dias_en_funciones_y_prorrogado"] for c in cal.values()) == \
        sum(int(g["dias_en_funciones_con_presupuesto_prorrogado"]) for g in gob)

    dim_a = []
    for a in range(2017, 2027):
        s = str(a)
        dim_a.append(dict(anio=a, presupuesto=pres.get(s, "prorrogado" if a == 2026 else ""),
                          dato_estado=dato.get(s, "sin datos (año en curso)"),
                          hay_organismos="sí" if s in con_org else "no",
                          hay_mecanismo="sí" if 2021 <= a <= 2025 else "no",
                          contratacion="incompleto (hasta 23/10/2026)" if a == 2026 else "completo",
                          comparable_22="sí" if a in (2024, 2025) else "no", **cal[a]))
    escribir("dim_anio.csv", dim_a, list(dim_a[0].keys()))

    # --- dim_gobierno
    dim_g = []
    for n, g in enumerate(gob, 1):
        en_curso = g["en_curso"] == "sí"
        dim_g.append(dict(orden=n, gobierno=g["gobierno"], presidente_real_decreto=g["real_decreto_presidente"],
                          nombrado_el=dmy(d_(g["nombrado_el"])),
                          en_funciones_desde=dmy(d_(g["cese_en_funciones_el"])) if g["cese_en_funciones_el"] else "",
                          hasta=dmy(d_(g["hasta"])) + (" (en curso, corte)" if en_curso else ""),
                          motivo_del_fin=g["motivo_del_fin"] or "sigue en el cargo",
                          dias_mandato=int(g["dias_mandato"]), dias_en_funciones=int(g["dias_en_funciones"]),
                          dias_presupuesto_prorrogado=int(g["dias_presupuesto_prorrogado"]),
                          pct_prorrogado=f(g["pct_prorrogado"]),
                          dias_en_funciones_con_presupuesto_prorrogado=int(g["dias_en_funciones_con_presupuesto_prorrogado"]),
                          leyes_pge_publicadas_en_el_mandato=g["leyes_pge_publicadas_en_el_mandato"]))
    escribir("dim_gobierno.csv", dim_g, list(dim_g[0].keys()))

    # --- dim_capitulo
    escribir("dim_capitulo.csv", [dict(capitulo=k, capitulo_nombre=f"{k}. {v[0]}", tipo=v[1]) for k, v in CAPITULOS.items()],
             ["capitulo", "capitulo_nombre", "tipo"])

    # --- fact_ministerio_anio
    mrr = defaultdict(lambda: defaultdict(float))
    for r in leer(DATOS / "mrr_secciones.csv"):
        for k in ("creditos_iniciales", "creditos_definitivos", "obligaciones", "pagos"):
            mrr[(r["ministerio_actual"], r["anio"])][k] += f(r[k]) or 0
    hechos = []
    for r in res:
        k = (r["ministerio_actual"], r["anio"])
        x = dict(ministerio_id=ids[r["ministerio_actual"]], anio=int(r["anio"]), continuidad=r["continuidad_estado"])
        for c in ("creditos_iniciales", "creditos_extraordinarios_suplementos", "ampliaciones", "transferencias",
                  "incorporacion_remanentes", "generaciones_ingresos", "bajas_otras_modificaciones", "modificaciones_netas",
                  "creditos_definitivos", "obligaciones", "pagos"):
            x[f"estado_{c}"] = f(r[f"estado_{c}"])
        for c in ("organismos_obligaciones", "transferencias_restadas", "transferencias_de_otros_ministerios",
                  "transferencias_de_sus_organismos_al_estado", "gasto_agregado_sin_doble_computo"):
            x[c] = f(r[c])
        if k in mrr:
            m = mrr[k]
            x.update(mrr_creditos_iniciales=m["creditos_iniciales"], mrr_creditos_definitivos=m["creditos_definitivos"],
                     mrr_obligaciones=m["obligaciones"], mrr_pagos=m["pagos"] if r["anio"] == "2025" else None)
        hechos.append(x)
    campos = ["ministerio_id", "anio", "continuidad"] + [c for c in hechos[0] if c.startswith("estado_")] + \
             ["organismos_obligaciones", "transferencias_restadas", "transferencias_de_otros_ministerios",
              "transferencias_de_sus_organismos_al_estado", "gasto_agregado_sin_doble_computo",
              "mrr_creditos_iniciales", "mrr_creditos_definitivos", "mrr_obligaciones", "mrr_pagos"]
    escribir("fact_ministerio_anio.csv", hechos, campos)

    # --- fact_capitulo: Estado (liquidación por sección y capítulo) y organismos (vol. II)
    sec_min = {(r["anio"], r["codigo_seccion"]): r["ministerio_actual"] for r in sma if r["tipo"] == "Ministerio"}
    cap = defaultdict(lambda: [0.0, 0.0])
    for r in leer(DATOS / "liquidacion_seccion_capitulo.csv"):
        mi = sec_min.get((r["anio"], r["codigo_seccion"]))
        if mi:
            x = cap[(ids[mi], int(r["anio"]), "Estado", int(r["capitulo"]))]
            x[0] += f(r["creditos_definitivos"]) or 0
            x[1] += f(r["obligaciones"]) or 0
    for r in leer(DATOS / "organismos_gastos.csv"):
        if r["organismo"] and r["capitulo"] != "0" and r["ministerio_actual"] in ids:
            x = cap[(ids[r["ministerio_actual"]], int(r["anio"]), "Organismos", int(r["capitulo"]))]
            x[0] += f(r["creditos_definitivos"]) or 0
            x[1] += f(r["obligaciones"]) or 0
    filas = [dict(ministerio_id=m, anio=a, ambito=amb, capitulo=c, creditos_definitivos=v[0], obligaciones=v[1])
             for (m, a, amb, c), v in sorted(cap.items()) if v[0] or v[1]]
    escribir("fact_capitulo.csv", filas, ["ministerio_id", "anio", "ambito", "capitulo", "creditos_definitivos", "obligaciones"])

    # --- fact_programa
    filas = [dict(ministerio_id=ids[r["ministerio_actual"]], anio=int(r["anio"]), programa=r["programa"],
                  programa_nombre=r["programa_nombre"], creditos_iniciales=f(r["creditos_iniciales"]),
                  creditos_definitivos=f(r["creditos_definitivos"]), obligaciones=f(r["obligaciones"]))
             for r in leer(DATOS / "ficha_programas.csv")]
    escribir("fact_programa.csv", filas, list(filas[0].keys()))

    # --- fact_mrr_programa
    sec_min_mrr = {(r["anio"], r["codigo_seccion"]): r["ministerio_actual"] for r in leer(DATOS / "mrr_secciones.csv")}
    filas = []
    for r in leer(DATOS / "mrr_programa_capitulo.csv"):
        mi = sec_min_mrr[(r["anio"], r["codigo_seccion"])]
        filas.append(dict(ministerio_id=ids[mi], anio=int(r["anio"]), codigo_seccion=r["codigo_seccion"], programa=r["programa"],
                          programa_nombre=r["programa_nombre"], capitulo=int(r["capitulo"]),
                          creditos_iniciales=f(r["creditos_iniciales"]), creditos_definitivos=f(r["creditos_definitivos"]),
                          obligaciones=f(r["obligaciones"]), pagos=f(r["pagos"])))
    escribir("fact_mrr_programa.csv", filas, list(filas[0].keys()))

    # --- fact_ingresos_organismos
    filas = []
    for r in leer(DATOS / "ficha_ingresos_organismos.csv"):
        o = r["origen"]
        grupo = ("Propios" if o.startswith("propios") else "Transferencias del Estado" if "del Estado" in o
                 else "Transferencias de otros" if "de otros" in o else "Financieros")
        filas.append(dict(ministerio_id=ids[r["ministerio_actual"]], anio=int(r["anio"]), organismo=r["organismo"],
                          origen=o, origen_grupo=grupo, derechos_reconocidos=f(r["derechos_reconocidos"])))
    escribir("fact_ingresos_organismos.csv", filas, list(filas[0].keys()))

    # --- fact_contratacion_mes (solo AGE)
    sumas = ["n_adjudicaciones", "importe_con_iva_eur", "n_programa_especial", "importe_programa_especial_eur",
             "n_menor_importe_atipico", "importe_menor_atipico_eur", "n_ordinario", "importe_ordinario_eur", "n_con_ofertas",
             "n_oferta_unica", "n_negociado_sin_publicidad", "n_urgente_o_emergencia", "n_con_baja", "suma_baja"]
    filas = []
    for r in leer(LB, enc="utf-8-sig"):
        if r["bloque"] not in ("Defensa", "Resto de la AGE"):
            continue
        x = dict(ministerio_id=ids[r["grupo"]], anio=int(r["anio"]), mes=int(r["mes"]), fecha_mes=r["fecha_mes"],
                 nov_dic="sí" if r["periodo"] == "Nov-dic" else "no",
                 procedimiento="contrato menor" if r["es_contrato_menor"] == "Sí" else "licitación",
                 tipo_contrato=r["tipo_contrato"])
        for c in sumas:
            x[c] = f(r[c])
        filas.append(x)
    escribir("fact_contratacion_mes.csv", filas, list(filas[0].keys()))


if __name__ == "__main__":
    main()
