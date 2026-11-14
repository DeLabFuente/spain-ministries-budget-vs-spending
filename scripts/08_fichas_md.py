"""Tablas en Markdown de las fichas (se insertan en fichas/*.md entre las marcas <!-- tabla:… --> y <!-- /tabla -->).

Así las cifras de los textos salen siempre de los CSV de datos/ y no se copian a mano.
Uso: python scripts/08_fichas_md.py
"""
import csv
import re
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datos"
FICHAS = RAIZ / "fichas"
MIN = {"defensa": "Ministerio de Defensa", "interior": "Ministerio del Interior",
       "agricultura": "Ministerio de Agricultura, Pesca y Alimentación", "hacienda": "Ministerio de Hacienda",
       "transportes": "Ministerio de Transportes y Movilidad Sostenible",
       "transicion_ecologica": "Ministerio para la Transición Ecológica y el Reto Demográfico",
       "ciencia": "Ministerio de Ciencia, Innovación y Universidades",
       "trabajo": "Ministerio de Trabajo y Economía Social",
       "inclusion": "Ministerio de Inclusión, Seguridad Social y Migraciones",
       "cultura": "Ministerio de Cultura",
       "presidencia_justicia": "Ministerio de la Presidencia, Justicia y Relaciones con las Cortes",
       "asuntos_exteriores": "Ministerio de Asuntos Exteriores, Unión Europea y Cooperación",
       "economia": "Ministerio de Economía, Comercio y Empresa", "sanidad": "Ministerio de Sanidad",
       "industria": "Ministerio de Industria y Turismo",
       "educacion": "Ministerio de Educación, Formación Profesional y Deportes",
       "politica_territorial": "Ministerio de Política Territorial y Memoria Democrática",
       "igualdad": "Ministerio de Igualdad",
       "transformacion_digital": "Ministerio para la Transformación Digital y de la Función Pública",
       "juventud_infancia": "Ministerio de Juventud e Infancia",
       "vivienda": "Ministerio de Vivienda y Agenda Urbana",
       "derechos_sociales": "Ministerio de Derechos Sociales, Consumo y Agenda 2030"}


def leer(n):
    with open(DATOS / n, encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter=";"))


def f(x):
    return float(x.replace(",", ".")) if x not in ("", None) else None


def m(x, dec=0):
    """euros -> millones con punto de miles y coma decimal"""
    if x is None:
        return "—"
    s = f"{x / 1e6:,.{dec}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def p(x):
    return "—" if x is None else f"{x:.1f}".replace(".", ",")


def dias_prorrogados():
    """Días de cada año con presupuesto prorrogado (datos/calendario_presupuestos.csv, script 17)."""
    try:
        return {r["anio"]: int(r["dias_prorrogado"]) for r in leer("calendario_presupuestos.csv")}
    except FileNotFoundError:
        return {}


def tabla_presupuesto(res, mi):
    filas = [r for r in res if r["ministerio_actual"] == mi]
    dp = dias_prorrogados()
    nota = False
    out = ["| Año | Presupuesto | Iniciales | Modificaciones | Definitivos | Obligaciones | % s/ definitivos | Pagos |",
           "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for r in filas:
        anio = r["anio"] + (" (prov.)" if r["dato"].startswith("provisional") else "") + \
            (" (*)" if r["continuidad_estado"] == "reconstruido" else "")
        pres = r["presupuesto"]
        if pres == "aprobado" and dp.get(r["anio"], 0) > 0:
            pres = f"aprobado ({dp[r['anio']]} d prorrog.)"
            nota = True
        out.append(f"| {anio} | {pres} | {m(f(r['estado_creditos_iniciales']))} | "
                   f"{m(f(r['estado_modificaciones_netas']))} | {m(f(r['estado_creditos_definitivos']))} | "
                   f"{m(f(r['estado_obligaciones']))} | {p(f(r['estado_pct_obligaciones_sobre_definitivos']))} | "
                   f"{m(f(r['estado_pagos']))} |")
    if nota:
        out.append("\n*«d prorrog.»: días del año en que rigió el presupuesto prorrogado del ejercicio anterior, hasta que entró en "
                   "vigor la ley del año. Calendario en [`comparativa.md`](../comparativa.md) y `datos/calendario_presupuestos.csv`.*")
    return "\n".join(out)


def tabla_modificaciones(res, mi):
    filas = [r for r in res if r["ministerio_actual"] == mi and r["estado_creditos_iniciales"]]
    out = ["| Año | Créd. extraord. y suplementos | Ampliaciones | Transferencias | Remanentes | Generaciones | Bajas y otras | Total |",
           "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for r in filas:
        anio = r["anio"] + (" (prov.)" if r["dato"].startswith("provisional") else "")
        out.append(f"| {anio} | " + " | ".join(m(f(r[f"estado_{c}"])) for c in (
            "creditos_extraordinarios_suplementos", "ampliaciones", "transferencias", "incorporacion_remanentes",
            "generaciones_ingresos", "bajas_otras_modificaciones", "modificaciones_netas")) + " |")
    return "\n".join(out)


def tabla_agregado(res, mi):
    filas = [r for r in res if r["ministerio_actual"] == mi and r["organismos_obligaciones"]]
    if filas and not any(f(r["organismos_obligaciones"]) for r in filas):
        return "*Este ministerio no tiene organismos con presupuesto propio: su gasto es el de la sección del Estado.*"
    out = ["| Año | Estado: obligaciones | Organismos: obligaciones | − Transferencias del Estado a sus organismos | "
           "− Devuelto al Estado por sus organismos | Gasto agregado |",
           "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for r in filas:
        out.append(f"| {r['anio']} | {m(f(r['estado_obligaciones']))} | {m(f(r['organismos_obligaciones']))} | "
                   f"{m(f(r['transferencias_restadas']))} | {m(f(r['transferencias_de_sus_organismos_al_estado']))} | "
                   f"{m(f(r['gasto_agregado_sin_doble_computo']))} |")
    return "\n".join(out)


def tabla_capitulos(cap, mi, anios=("2017", "2021", "2023", "2024")):
    caps = sorted({int(r["capitulo"]) for r in cap if r["ministerio_actual"] == mi})
    nom = {int(r["capitulo"]): r["capitulo_nombre"] for r in cap if r["capitulo_nombre"]}
    con_datos = sorted({r["anio"] for r in cap if r["ministerio_actual"] == mi and f(r["obligaciones"])})
    if con_datos and anios[0] not in con_datos:  # ministerio sin datos en el primer año: empezar en el suyo
        anios = (con_datos[0],) + tuple(a for a in anios[1:] if a != con_datos[0])
    out = []
    for amb in ("Estado", "Organismos"):
        tot = {a: sum(f(r["obligaciones"]) for r in cap if r["ministerio_actual"] == mi and r["anio"] == a and r["ambito"] == amb)
               for a in anios}
        anios_ok = [a for a in anios if tot[a]]
        if not anios_ok:
            continue
        out.append(f"**{amb}** (obligaciones, % del total del año)\n")
        out.append("| Capítulo | " + " | ".join(anios_ok) + " |")
        out.append("| --- | " + " | ".join("---:" for _ in anios_ok) + " |")
        for c in caps:
            v = {a: sum(f(r["obligaciones"]) for r in cap if r["ministerio_actual"] == mi and r["anio"] == a
                        and r["ambito"] == amb and int(r["capitulo"]) == c) for a in anios_ok}
            if all(100 * v[a] / tot[a] < 0.5 for a in anios_ok):
                continue
            out.append(f"| {c}. {nom.get(c, '')} | " + " | ".join(p(100 * v[a] / tot[a]) for a in anios_ok) + " |")
        out.append("| Total (M€) | " + " | ".join(m(tot[a]) for a in anios_ok) + " |\n")
    return "\n".join(out)


def tabla_ingresos(ing, mi, anios=("2017", "2020", "2024")):
    orgs = sorted({r["organismo"] for r in ing if r["ministerio_actual"] == mi})
    if not orgs:
        return "*Sin organismos, no hay ingresos propios que mostrar.*"
    out = ["| Organismo | Año | Derechos reconocidos (M€) | Propios | Transf. del Estado | Transf. de otros (UE, SS, CCAA…) | Financieros |",
           "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for o in orgs:
        for a in anios:
            rr = [r for r in ing if r["ministerio_actual"] == mi and r["organismo"] == o and r["anio"] == a]
            if not rr:
                continue
            tot = sum(f(r["derechos_reconocidos"]) for r in rr)
            g = defaultdict(float)
            for r in rr:
                k = ("propios" if r["origen"].startswith("propios") else "estado" if "del Estado" in r["origen"]
                     else "otros" if "de otros" in r["origen"] else "fin")
                g[k] += f(r["derechos_reconocidos"])
            out.append(f"| {o.title()[:60]} | {a} | {m(tot)} | " + " | ".join(
                p(100 * g[k] / tot) + " %" if tot else "—" for k in ("propios", "estado", "otros", "fin")) + " |")
    return "\n".join(out)


def tabla_programas(prog, mi, anio="2024", n=8):
    rr = sorted([r for r in prog if r["ministerio_actual"] == mi and r["anio"] == anio],
                key=lambda r: -f(r["obligaciones"]))
    tot = sum(f(r["obligaciones"]) for r in rr)
    out = [f"| Programa ({anio}) | Iniciales | Definitivos | Obligaciones | % del total |", "| --- | ---: | ---: | ---: | ---: |"]
    for r in rr[:n]:
        out.append(f"| {r['programa']} {r['programa_nombre'][:55]} | {m(f(r['creditos_iniciales']))} | "
                   f"{m(f(r['creditos_definitivos']))} | {m(f(r['obligaciones']))} | {p(100 * f(r['obligaciones']) / tot)} |")
    return "\n".join(out)


def tabla_contratacion(con, mi):
    fil = {(r["anio"], r["procedimiento"]): r for r in con if r["ministerio_actual"] == mi}
    anios = sorted({a for a, _ in fil if a != "2026"})
    out = ["| Año | Adjudicaciones | Importe (M€) | De ello, programas especiales | Importe ordinario | "
           "Nov-dic, % del ordinario (resto AGE) | Oferta única, % (resto AGE) | Negociado sin publicidad, % (resto AGE) | "
           "Contratos menores: número | Menores: M€ |",
           "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for a in anios:
        r = fil.get((a, "licitación"))
        mn = fil.get((a, "contrato menor"))
        if not r:
            continue
        nmen = f"{int(f(mn['adjudicaciones'])):,}".replace(",", ".") if mn else "—"
        nadj = f"{int(f(r['adjudicaciones'])):,}".replace(",", ".")
        out.append(f"| {a} | {nadj} | {m(f(r['importe_total']))} | "
                   f"{m(f(r['programas_especiales_importe']))} | {m(f(r['importe_ordinario']))} | "
                   f"{p(f(r['pct_importe_ordinario_nov_dic']))} ({p(f(r['resto_age_pct_importe_ordinario_nov_dic']))}) | "
                   f"{p(f(r['pct_oferta_unica']))} ({p(f(r['resto_age_pct_oferta_unica']))}) | "
                   f"{p(f(r['pct_negociado_sin_publicidad']))} ({p(f(r['resto_age_pct_negociado_sin_publicidad']))}) | "
                   f"{nmen} | {m(f(mn['importe_ordinario'])) if mn else '—'} |")
    return "\n".join(out)


def tabla_mrr(mrr, mprog, res, mi, n=6):
    """Mecanismo de Recuperación: por año (Estado) y programas con más obligaciones en 2021-2025."""
    agg = defaultdict(lambda: defaultdict(float))
    secs = set()
    for r in mrr:
        if r["ministerio_actual"] != mi:
            continue
        secs.add((r["anio"], r["codigo_seccion"]))
        for k in ("creditos_iniciales", "creditos_definitivos", "obligaciones", "pagos"):
            agg[r["anio"]][k] += f(r[k]) or 0
        agg[r["anio"]]["prov"] = r["dato"].startswith("provisional")
    obl_est = {r["anio"]: f(r["estado_obligaciones"]) for r in res if r["ministerio_actual"] == mi}
    out = ["| Año | Iniciales | Definitivos | Obligaciones | % s/ definitivos | % de las obligaciones del Estado del ministerio | Pagos |",
           "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for a in sorted(agg):
        x = agg[a]
        d, o = x["creditos_definitivos"], x["obligaciones"]
        out.append(f"| {a}{' (prov.)' if x['prov'] else ''} | {m(x['creditos_iniciales'])} | {m(d)} | {m(o)} | "
                   f"{p(100 * o / d) if d else '—'} | {p(100 * o / obl_est[a]) if obl_est.get(a) else '—'} | "
                   f"{m(x['pagos']) if x['prov'] else '—'} |")
    tot_d = sum(x["creditos_definitivos"] for x in agg.values())
    tot_o = sum(x["obligaciones"] for x in agg.values())
    out.append(f"| 2021-2025 | | {m(tot_d)} | {m(tot_o)} | {p(100 * tot_o / tot_d) if tot_d else '—'} | | |")
    out += ["", "*La fila «2021-2025» suma las obligaciones de cada año (eso es exacto) y los créditos definitivos de cada año. "
            "El crédito que un año no se reconoce puede incorporarse al siguiente como remanente y volver a contar en sus "
            "definitivos, de modo que el porcentaje de esa fila puede quedar por debajo de la ejecución real y no es la tasa "
            "del conjunto. La suma de definitivos de los programas, más abajo, tiene la misma limitación.*"]
    pr = defaultdict(lambda: [0.0, 0.0, ""])
    for r in mprog:
        if (r["anio"], r["codigo_seccion"]) not in secs:
            continue
        k = r["programa"]
        pr[k][0] += f(r["creditos_definitivos"]) or 0
        pr[k][1] += f(r["obligaciones"]) or 0
        pr[k][2] = pr[k][2] or r["programa_nombre"]
    out += ["", "| Programa del Mecanismo (2021-2025) | Definitivos | Obligaciones | % del Mecanismo del ministerio |",
            "| --- | ---: | ---: | ---: |"]
    for k, (d, o, nom) in sorted(pr.items(), key=lambda z: -z[1][1])[:n]:
        out.append(f"| {k} {nom[:60]} | {m(d)} | {m(o)} | {p(100 * o / tot_o) if tot_o else '—'} |")
    return "\n".join(out)


def main():
    res, cap, ing, prog = leer("ficha_resumen.csv"), leer("ficha_capitulos.csv"), leer("ficha_ingresos_organismos.csv"), \
        leer("ficha_programas.csv")
    con = leer("contratacion_ministerio.csv")
    mrr, mprog = leer("mrr_secciones.csv"), leer("mrr_programa_capitulo.csv")
    for clave, mi in MIN.items():
        ruta = FICHAS / f"{clave}.md"
        if not ruta.exists():
            continue
        texto = ruta.read_text(encoding="utf-8")
        tablas = {"presupuesto": tabla_presupuesto(res, mi), "modificaciones": tabla_modificaciones(res, mi),
                  "agregado": tabla_agregado(res, mi), "capitulos": tabla_capitulos(cap, mi),
                  "ingresos": tabla_ingresos(ing, mi), "programas": tabla_programas(prog, mi),
                  "contratacion": tabla_contratacion(con, mi), "mrr": tabla_mrr(mrr, mprog, res, mi)}
        for nombre, t in tablas.items():
            texto = re.sub(rf"<!-- tabla:{nombre} -->.*?<!-- /tabla -->",
                           f"<!-- tabla:{nombre} -->\n{t}\n<!-- /tabla -->", texto, flags=re.S)
        ruta.write_text(texto, encoding="utf-8")
        print("actualizada", ruta.name)


if __name__ == "__main__":
    main()
