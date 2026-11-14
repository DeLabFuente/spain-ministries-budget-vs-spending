"""Datos de las fichas por ministerio actual: presupuestado frente a gastado, con qué se paga y en qué se gasta.

Mismo modelo para los 22 ministerios; las fichas de la fase 2 son Defensa, Interior y Agricultura.

Entradas (datos/): secciones_ministerio_actual.csv, liquidacion_seccion_capitulo.csv, liquidacion_grupo_programas_seccion.csv,
liquidacion_programa_capitulo.csv, organismos_gastos.csv, organismos_ingresos.csv, transferencias_estado_organismos.csv
Salidas (datos/):
  ficha_resumen.csv     ministerio × año: Estado (iniciales → modificaciones → definitivos → obligaciones → pagos),
                        organismos (definitivos, obligaciones, pagos), transferencias del Estado a sus organismos y
                        gasto agregado sin doble cómputo
  ficha_capitulos.csv   ministerio × año × ámbito (Estado / organismos) × capítulo: obligaciones
  ficha_ingresos_organismos.csv  ministerio × año × organismo × origen: derechos reconocidos
  ficha_programas.csv   ministerio × año × programa (Estado, 2020-): iniciales, definitivos, obligaciones

Perímetro y reglas:
- Estado: las secciones cuyo ministerio actual es ese ministerio (equivalencias_secciones). Si la sección se partió
  («con cambios»), la fila lo dice en `continuidad_estado`.
- Agricultura 2017-2018 se reconstruye: estaba en la sección 23 con medio ambiente. Se toman sus grupos de programas
  (41x: desarrollo rural, estructuras agrarias, pesca, industria agroalimentaria, seguros agrarios) más las
  transferencias del Estado a los organismos de Agricultura (que en la sección iban en «transferencias internas»).
  Sin créditos iniciales ni modificaciones (la tabla por grupos no los trae).
- Organismos: los adscritos hoy al ministerio (organismos_ministerio_actual), aunque antes dependieran de otro.
- Gasto agregado = obligaciones del Estado + obligaciones de los organismos − lo que sus organismos devuelven al
  Estado (ingresos del Estado, art. 41/43/71/73; p. ej., el excedente de Tráfico) − transferencias del Estado a esos
  organismos (artículos 41, 43, 71 y 73), vengan de la sección que vengan. Cada euro se cuenta una sola vez, en el
  ministerio que lo presupuesta y lo paga: si el organismo recibe dinero de la sección de otro ministerio (p. ej., la
  CNMC, adscrita a Economía, recibe de Transición Ecológica los costes del sistema eléctrico), ese gasto se cuenta en
  el que paga y se resta en el que recibe. Así la suma de los 22 no tiene doble cómputo. La columna
  `transferencias_de_otros_ministerios` dice cuánto es (lo que pasa de lo transferido por sus secciones, grupo
  «Transferencias internas») y `aviso_doble_computo` lo señala. Las del Mecanismo de Recuperación a organismos van en
  una línea conjunta sin destinatario y no se restan.
"""
import csv
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datos"
APA = "Ministerio de Agricultura, Pesca y Alimentación"
# Organismo que cambia de nombre antes en la liquidación de organismos que en la del Estado: en 2020 el Estado
# todavía transfiere al «Instituto para la Reestructuración de la Minería del Carbón», que en la de organismos ya es el
# Instituto para la Transición Justa (REGISTRO C14). Solo se usa si el nombre original no existe ese año.
ALIAS_TRANSFERENCIAS = {"INST. REESTRUC. MINERÍA DEL CARBÓN Y DESAR. ALTER. COMAR. MIN., O.A.": "INSTITUTO PARA LA TRANSICIÓN JUSTA"}
GRUPOS_AGRICULTURA = ("41",)       # 411-416 en 2017-2018 (en 2019 la IGAE deja de publicar el código del grupo)


def leer(nombre):
    with open(DATOS / nombre, encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter=";"))


def f(x):
    return float(x.replace(",", ".")) if x not in ("", None) else 0.0


def fmt(x):
    if x is None:
        return ""
    if isinstance(x, float):
        return str(int(round(x))) if x.is_integer() else f"{x:.2f}".replace(".", ",")
    return x


def escribir(nombre, filas, campos):
    with open(DATOS / nombre, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(campos)
        for r in filas:
            w.writerow([fmt(r.get(k)) for k in campos])


ORIGEN_INGRESO = {1: "propios: cotizaciones e impuestos", 2: "propios: cotizaciones e impuestos",
                  3: "propios: tasas, precios públicos y otros", 5: "propios: patrimoniales", 6: "propios: enajenaciones",
                  4: "transferencias corrientes", 7: "transferencias de capital", 8: "financieros: activos (incl. remanente)",
                  9: "financieros: pasivos (préstamos)"}


def main():
    sec = [r for r in leer("secciones_ministerio_actual.csv") if r["tipo"] == "Ministerio"]
    sec_cap = leer("liquidacion_seccion_capitulo.csv")
    grupos = leer("liquidacion_grupo_programas_seccion.csv")
    progs = leer("liquidacion_programa_capitulo.csv")
    og = leer("organismos_gastos.csv")
    oi = leer("organismos_ingresos.csv")
    tr = leer("transferencias_estado_organismos.csv")
    tre = leer("transferencias_organismos_al_estado.csv")
    mut = leer("aportacion_estado_mutualismo.csv")

    ministerio_de = {(r["anio"], r["codigo_seccion"]): r["ministerio_actual"] for r in sec}
    cont_de = {(r["anio"], r["codigo_seccion"]): r["continuidad"] for r in sec}
    anios = sorted({r["anio"] for r in sec})
    ministerios = sorted({r["ministerio_actual"] for r in sec})

    # --- Estado
    E = defaultdict(lambda: defaultdict(float))
    meta = defaultdict(lambda: {"secciones": set(), "continuidad": set(), "presupuesto": "", "dato": ""})
    campos_e = ["creditos_iniciales", "creditos_extraordinarios_suplementos", "ampliaciones", "transferencias",
                "incorporacion_remanentes", "generaciones_ingresos", "bajas_otras_modificaciones",
                "creditos_definitivos", "obligaciones", "pagos"]
    for r in sec:
        k = (r["ministerio_actual"], r["anio"])
        for c in campos_e:
            E[k][c] += f(r[c])
        meta[k]["secciones"].add(f"{r['codigo_seccion']} {r['seccion']}")
        meta[k]["continuidad"].add(r["continuidad"])
        meta[k]["presupuesto"], meta[k]["dato"] = r["presupuesto"], r["dato"]

    # --- Transferencias del Estado a organismos, por ministerio del organismo
    T = defaultdict(float)
    for r in tr:
        if r["ministerio_actual"] and not r["ministerio_actual"].startswith("("):
            T[(r["ministerio_actual"], r["anio"])] += f(r["obligaciones"])

    # Lo que sus organismos devuelven al Estado (p. ej., excedente de Tráfico al Tesoro): sale del gasto agregado
    TE = defaultdict(float)
    for r in tre:
        if r["ministerio_actual"] and not r["ministerio_actual"].startswith("("):
            TE[(r["ministerio_actual"], r["anio"])] += f(r["derechos_reconocidos"])

    # Lo que cada sección transfiere a organismos (grupo de programas «Transferencias internas»): lo que lo pasa
    # llega de secciones de otros ministerios
    TI = defaultdict(float)
    for g in grupos:
        if g["grupo_programas"] == "000" or g["grupo_nombre"].lower().startswith("transferencias internas"):
            mm = ministerio_de.get((g["anio"], g["codigo_seccion"]))
            if mm:
                TI[(mm, g["anio"])] += f(g["obligaciones"])

    # --- Agricultura 2017-2018: reconstrucción desde la sección 23
    reconstruido = {}
    for anio in ("2017", "2018"):
        g = [x for x in grupos if x["anio"] == anio and x["codigo_seccion"] == "23"
             and x["grupo_programas"].startswith(GRUPOS_AGRICULTURA)]
        if g:
            t = [x for x in tr if x["anio"] == anio and x["ministerio_actual"] == APA]
            reconstruido[(APA, anio)] = {c: sum(f(x[c]) for x in g) + sum(f(x[c]) for x in t)
                                         for c in ("creditos_definitivos", "obligaciones", "pagos")}

    # --- Organismos
    O = defaultdict(lambda: defaultdict(float))
    n_org = defaultdict(set)
    for r in og:
        if r["organismo"] and r["capitulo"] == "0":
            k = (r["ministerio_actual"], r["anio"])
            for c in ("creditos_iniciales", "creditos_definitivos", "obligaciones", "pagos"):
                O[k][c] += f(r[c])
            n_org[k].add(r["organismo_id"])

    resumen = []
    for m in ministerios:
        for a in anios:
            k = (m, a)
            if k not in E and k not in reconstruido:
                continue
            fila = dict(ministerio_actual=m, anio=int(a), presupuesto=meta[k]["presupuesto"], dato=meta[k]["dato"])
            if k in reconstruido:
                fila.update({f"estado_{c}": None for c in campos_e})
                fila.update({f"estado_{c}": v for c, v in reconstruido[k].items()})
                fila["perimetro_estado"] = "reconstruido: grupos de programas 41x de la sección 23 + transferencias a sus organismos"
                fila["continuidad_estado"] = "reconstruido"
                fila["presupuesto"] = "aprobado"
                fila["dato"] = "definitivo (liquidación)"
            else:
                fila.update({f"estado_{c}": E[k][c] for c in campos_e})
                fila["estado_modificaciones_netas"] = E[k]["creditos_definitivos"] - E[k]["creditos_iniciales"]
                fila["perimetro_estado"] = " + ".join(sorted(meta[k]["secciones"]))
                fila["continuidad_estado"] = "con cambios" if "con cambios" in meta[k]["continuidad"] else "directa"
            ok = O.get(k)
            if ok and a <= max(r["anio"] for r in og):
                fila.update(organismos_numero=len(n_org[k]), organismos_creditos_iniciales=ok["creditos_iniciales"] or None,
                            organismos_creditos_definitivos=ok["creditos_definitivos"],
                            organismos_obligaciones=ok["obligaciones"], organismos_pagos=ok["pagos"])
            elif a <= max(r["anio"] for r in og):
                fila.update(organismos_numero=0, organismos_obligaciones=0.0)
            hay_org = a <= max(r["anio"] for r in og)
            fila["transferencias_estado_a_sus_organismos"] = T.get(k, 0.0) if hay_org else None
            fila["transferencias_internas_de_sus_secciones"] = TI.get(k, 0.0) if hay_org and k not in reconstruido else None
            if hay_org:
                fila["transferencias_restadas"] = T.get(k, 0.0)
                otros = 0.0 if k in reconstruido else max(0.0, T.get(k, 0.0) - TI.get(k, 0.0))
                fila["transferencias_de_otros_ministerios"] = otros
                if otros > 1e6:
                    fila["aviso_doble_computo"] = (f"Al menos {otros / 1e6:,.1f} M€ de las transferencias a sus organismos salen de "
                                                   "secciones de otros ministerios (cota inferior: se calcula restando el grupo "
                                                   "«Transferencias internas» de sus secciones, que puede ir a organismos de otros "
                                                   "ministerios; REGISTRO B19): se cuentan en el que paga y aquí se restan"
                                                   ).replace(",", "X").replace(".", ",").replace("X", ".")
            if hay_org:
                fila["transferencias_de_sus_organismos_al_estado"] = TE.get(k, 0.0)
            if fila.get("organismos_obligaciones") is not None and fila.get("estado_obligaciones") is not None:
                fila["gasto_agregado_sin_doble_computo"] = (fila["estado_obligaciones"] + fila["organismos_obligaciones"]
                                                            - fila["transferencias_restadas"]
                                                            - fila["transferencias_de_sus_organismos_al_estado"])
            de, ob = fila.get("estado_creditos_definitivos"), fila.get("estado_obligaciones")
            fila["estado_pct_obligaciones_sobre_definitivos"] = 100 * ob / de if de else None
            ini = fila.get("estado_creditos_iniciales")
            fila["estado_pct_obligaciones_sobre_iniciales"] = 100 * ob / ini if ini else None
            resumen.append(fila)
    campos = ["ministerio_actual", "anio", "presupuesto", "dato", "continuidad_estado", "perimetro_estado"] + \
             [f"estado_{c}" for c in campos_e[:7]] + ["estado_modificaciones_netas"] + \
             [f"estado_{c}" for c in campos_e[7:]] + \
             ["estado_pct_obligaciones_sobre_iniciales", "estado_pct_obligaciones_sobre_definitivos",
              "organismos_numero", "organismos_creditos_iniciales", "organismos_creditos_definitivos",
              "organismos_obligaciones", "organismos_pagos", "transferencias_estado_a_sus_organismos",
              "transferencias_internas_de_sus_secciones", "transferencias_de_otros_ministerios", "transferencias_restadas",
              "transferencias_de_sus_organismos_al_estado", "gasto_agregado_sin_doble_computo",
              "aviso_doble_computo"]
    escribir("ficha_resumen.csv", resumen, campos)

    # --- En qué se gasta: capítulos (Estado y organismos)
    caps = defaultdict(float)
    nombre_cap = {}
    for r in sec_cap:
        m = ministerio_de.get((r["anio"], r["codigo_seccion"]))
        if m:
            caps[(m, r["anio"], "Estado", int(r["capitulo"]))] += f(r["obligaciones"])
            nombre_cap[int(r["capitulo"])] = r["capitulo_nombre"]
    for r in og:
        if r["organismo"] and r["capitulo"] != "0":
            caps[(r["ministerio_actual"], r["anio"], "Organismos", int(r["capitulo"]))] += f(r["obligaciones"])
    filas = [dict(ministerio_actual=k[0], anio=int(k[1]), ambito=k[2], capitulo=k[3], capitulo_nombre=nombre_cap.get(k[3], ""),
                  obligaciones=v, aviso="sección con cambios de competencias" if k[2] == "Estado" and any(
                      cont_de.get((k[1], c)) == "con cambios" for (a, c), mm in ministerio_de.items()
                      if a == k[1] and mm == k[0]) else "")
             for k, v in sorted(caps.items())]
    escribir("ficha_capitulos.csv", filas, ["ministerio_actual", "anio", "ambito", "capitulo", "capitulo_nombre",
                                             "obligaciones", "aviso"])

    # --- Con qué se paga: ingresos de los organismos por origen, con lo que transfiere el Estado aparte
    ing = defaultdict(float)
    tr_org = defaultdict(float)
    ids_anio = {(r["anio"], r["organismo_id"]) for r in oi}
    for r in tr:
        oid = r["organismo_id"]
        if (r["anio"], oid) not in ids_anio and oid in ALIAS_TRANSFERENCIAS:   # REGISTRO C14
            oid = ALIAS_TRANSFERENCIAS[oid]
        tr_org[(r["anio"], oid, r["capitulo"])] += f(r["obligaciones"])
    aporta = defaultdict(float)
    for r in mut:
        aporta[(r["anio"], r["organismo_id"])] += f(r["obligaciones"])
    for r in oi:
        if not r["organismo"] or r["capitulo"] == "0":
            continue
        cap = int(r["capitulo"])
        k = (r["ministerio_actual"], r["anio"], r["organismo_id"])
        dr = f(r["derechos_reconocidos"])
        if cap == 1 and (r["anio"], r["organismo_id"]) in aporta:
            a = min(aporta[(r["anio"], r["organismo_id"])], dr)
            ing[k + ("del Estado como empleador (sección 09, cotizaciones)",)] += a
            ing[k + ("propios: cuotas de los mutualistas",)] += dr - a
            continue
        if cap in (4, 7):
            del_estado = tr_org.get((r["anio"], r["organismo_id"], str(cap)), 0.0)
            ing[k + (f"{ORIGEN_INGRESO[cap]}: del Estado (art. {cap}1/{cap}3)",)] += min(del_estado, dr)
            ing[k + (f"{ORIGEN_INGRESO[cap]}: de otros (UE, Seguridad Social, CCAA…)",)] += dr - min(del_estado, dr)
        else:
            ing[k + (ORIGEN_INGRESO[cap],)] += dr
    filas = [dict(ministerio_actual=k[0], anio=int(k[1]), organismo=k[2], origen=k[3], derechos_reconocidos=v)
             for k, v in sorted(ing.items()) if v]
    escribir("ficha_ingresos_organismos.csv", filas, ["ministerio_actual", "anio", "organismo", "origen",
                                                       "derechos_reconocidos"])

    # --- Programas del Estado (2020-)
    pg = defaultdict(lambda: [0.0, 0.0, 0.0])
    nom = {}
    for r in progs:
        m = ministerio_de.get((r["anio"], r["codigo_seccion"]))
        if m:
            x = pg[(m, r["anio"], r["programa"])]
            x[0] += f(r["creditos_iniciales"]); x[1] += f(r["creditos_definitivos"]); x[2] += f(r["obligaciones"])
            nom[(r["anio"], r["programa"])] = r["programa_nombre"]
    filas = [dict(ministerio_actual=k[0], anio=int(k[1]), programa=k[2], programa_nombre=nom.get((k[1], k[2]), ""),
                  creditos_iniciales=v[0], creditos_definitivos=v[1], obligaciones=v[2]) for k, v in sorted(pg.items())]
    escribir("ficha_programas.csv", filas, ["ministerio_actual", "anio", "programa", "programa_nombre",
                                             "creditos_iniciales", "creditos_definitivos", "obligaciones"])
    print(f"{len(resumen)} filas ministerio-año; {len(caps)} capítulo; {len(ing)} ingresos; {len(pg)} programas")


if __name__ == "__main__":
    main()
