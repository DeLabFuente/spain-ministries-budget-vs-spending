"""Equivalencias de secciones y primer cuadro «presupuestado frente a gastado».

Entrada: datos/liquidacion_secciones.csv (scripts/01_leer_liquidacion.py) y, para el último año sin liquidación,
         datos/mensual_secciones.csv (scripts/03_leer_mensual.py, provisional)
Salidas (separador ';', decimales con coma, UTF-8, importes en euros):
  datos/equivalencias_secciones.csv  cada nombre de sección de cada año -> ministerio actual (RD 829/2023, 22 ministerios)
  datos/secciones_ministerio_actual.csv  liquidacion_secciones con el ministerio actual y la marca de continuidad
  datos/cuadro_defensa_interior_agricultura.csv  iniciales -> modificaciones -> definitivos -> obligaciones -> pagos

Regla (la misma que MINISTERIO_ACTUAL del proyecto de Defensa): cada sección se asigna al departamento actual que
heredó el grueso de sus competencias, que casi siempre conserva el mismo código de sección. Cuando una sección se
partió o se fusionó, la columna «continuidad» dice «con cambios» y la nota explica qué parte salió o entró y adónde.
Esas filas no se pueden comparar directamente con los años siguientes: el reparto se hará por grupos de programas
(datos/liquidacion_grupo_programas_seccion.csv) en la ficha de cada ministerio.
"""
import csv
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datos"

PJRC = "Ministerio de la Presidencia, Justicia y Relaciones con las Cortes"
HAC = "Ministerio de Hacienda"
INT = "Ministerio del Interior"
AAEE = "Ministerio de Asuntos Exteriores, Unión Europea y Cooperación"
DEF = "Ministerio de Defensa"
TMS = "Ministerio de Transportes y Movilidad Sostenible"
EFPD = "Ministerio de Educación, Formación Profesional y Deportes"
TES = "Ministerio de Trabajo y Economía Social"
IT = "Ministerio de Industria y Turismo"
APA = "Ministerio de Agricultura, Pesca y Alimentación"
PTMD = "Ministerio de Política Territorial y Memoria Democrática"
TERD = "Ministerio para la Transición Ecológica y el Reto Demográfico"
CUL = "Ministerio de Cultura"
VAU = "Ministerio de Vivienda y Agenda Urbana"
SAN = "Ministerio de Sanidad"
ECE = "Ministerio de Economía, Comercio y Empresa"
CIU = "Ministerio de Ciencia, Innovación y Universidades"
DSCA = "Ministerio de Derechos Sociales, Consumo y Agenda 2030"
IGU = "Ministerio de Igualdad"
JI = "Ministerio de Juventud e Infancia"
ISSM = "Ministerio de Inclusión, Seguridad Social y Migraciones"
TDFP = "Ministerio para la Transformación Digital y de la Función Pública"
MINISTERIOS_2026 = [PJRC, HAC, INT, AAEE, DEF, TMS, EFPD, TES, IT, APA, PTMD, TERD, CUL, VAU, SAN, ECE, CIU, DSCA,
                    IGU, JI, ISSM, TDFP]

OC, NM, MI = "Órgano constitucional", "Sección no ministerial", "Ministerio"
D, C = "directa", "con cambios"

# (código, nombre de la sección tal como lo publica la IGAE) -> (tipo, ministerio actual, continuidad, nota)
REGLAS = {
    # Órganos constitucionales y secciones no ministeriales: se arrastran con su propio nombre
    **{(c, n): (OC, m, D, "") for c, n, m in [
        ("01", "CASA DE SU MAJESTAD EL REY", "Casa de Su Majestad el Rey"), ("02", "CORTES GENERALES", "Cortes Generales"),
        ("03", "TRIBUNAL DE CUENTAS", "Tribunal de Cuentas"), ("04", "TRIBUNAL CONSTITUCIONAL", "Tribunal Constitucional"),
        ("05", "CONSEJO DE ESTADO", "Consejo de Estado"),
        ("08", "CONSEJO GENERAL DEL PODER JUDICIAL", "Consejo General del Poder Judicial")]},
    ("06", "DEUDA PÚBLICA"): (NM, "Deuda pública", D, ""),
    ("07", "CLASES PASIVAS"): (NM, "Clases pasivas", D, ""),
    ("09", "APORT. MUTUALISMO ADMINISTRATIVO"): (NM, "Aportaciones al mutualismo administrativo", D,
                                                 "Sección creada en 2018 (antes, dentro de otras secciones)."),
    ("09", "APORTACIONES AL MUTUALISMO ADMINISTRATIVO"): (NM, "Aportaciones al mutualismo administrativo", D, ""),
    ("10", "CONTRATACIÓN CENTRALIZADA"): (NM, "Contratación centralizada", D, "Sección creada en 2018."),
    ("31", "GASTOS DE DIVERSOS MINISTERIOS"): (NM, "Gastos de diversos ministerios", D,
                                               "Solo en 2017; desde 2018 su contenido se reparte en otras secciones."),
    **{(c, n): (NM, m, D, "") for c, n, m in [
        ("32", "OTRAS RELAC. FINANC. CON ENTES TERRIT.", "Otras relaciones financieras con entes territoriales"),
        ("32", "OTRAS RELACIONES FINANCIERAS CON ENTES TERRITORIALES", "Otras relaciones financieras con entes territoriales"),
        ("37", "OTRAS RELACIONES FINANCIERAS CON ENTES TERRITORIALES", "Otras relaciones financieras con entes territoriales"),
        ("33", "FONDOS DE COMPENSACIÓN INTERTERRIT.", "Fondos de compensación interterritorial"),
        ("33", "FONDOS DE COMPENSACIÓN INTERTERRITORIAL", "Fondos de compensación interterritorial"),
        ("36", "FONDOS DE COMPENSACIÓN INTERTERRITORIAL", "Fondos de compensación interterritorial"),
        ("34", "RELACIONES FINANCIERAS CON LA U.E.", "Relaciones financieras con la Unión Europea"),
        ("34", "RELACIONES FINANCIERAS CON LA U. E.", "Relaciones financieras con la Unión Europea"),
        ("34", "RELACIONES FINANCIERAS CON LA UNIÓN EUROPEA", "Relaciones financieras con la Unión Europea"),
        ("35", "FONDO DE CONTINGENCIA", "Fondo de contingencia"),
        ("36", "SISTEMAS DE FINANC. DE ENTES TERRIT.", "Sistemas de financiación de entes territoriales"),
        ("36", "SISTEMAS DE FINANCIACIÓN DE ENTES TERRITORIALES", "Sistemas de financiación de entes territoriales"),
        ("38", "SISTEMAS DE FINANCIACIÓN DE ENTES TERRITORIALES", "Sistemas de financiación de entes territoriales")]},

    # Ministerios
    ("12", "ASUNTOS EXTERIORES Y DE COOPERACIÓN"): (MI, AAEE, D, ""),
    ("12", "ASUNTOS EXT, U. E. Y COOPERACIÓN"): (MI, AAEE, D, ""),
    ("12", "MINISTERIO DE ASUNTOS EXTERIORES, UNIÓN EUROPEA Y COOPERACIÓN"): (MI, AAEE, D, ""),
    ("13", "JUSTICIA"): (MI, PJRC, C, "En 2024 se fusiona con Presidencia y Relaciones con las Cortes (antes sección 25)."),
    ("13", "MINISTERIO DE JUSTICIA"): (MI, PJRC, C, "En 2024 se fusiona con Presidencia y Relaciones con las Cortes (antes sección 25)."),
    ("13", "MINISTERIO DE LA PRESIDENCIA, JUSTICIA Y RELACIONES CON LAS CORTES"): (MI, PJRC, D, ""),
    ("14", "DEFENSA"): (MI, DEF, D, ""),
    ("14", "MINISTERIO DE DEFENSA"): (MI, DEF, D, ""),
    ("15", "HACIENDA Y FUNCIÓN PÚBLICA"): (MI, HAC, C, "Función Pública sale en 2018 a Política Territorial y Función Pública (22); hoy está en Transformación Digital y Función Pública (33)."),
    ("15", "HACIENDA"): (MI, HAC, D, ""),
    ("15", "MINISTERIO DE HACIENDA"): (MI, HAC, D, ""),
    ("15", "MINISTERIO DE HACIENDA Y FUNCIÓN PÚBLICA"): (MI, HAC, C, "Función Pública vuelve a Hacienda en 2022 (desde la 22) y sale en 2024 a Transformación Digital y Función Pública (33)."),
    ("16", "INTERIOR"): (MI, INT, D, ""),
    ("16", "MINISTERIO DEL INTERIOR"): (MI, INT, D, ""),
    ("17", "FOMENTO"): (MI, TMS, C, "Vivienda y agenda urbana (grupo 261 y planes de rehabilitación) salen en 2024 a Vivienda y Agenda Urbana (25)."),
    ("17", "MINISTERIO DE FOMENTO"): (MI, TMS, C, "Vivienda y agenda urbana salen en 2024 a Vivienda y Agenda Urbana (25)."),
    ("17", "MINISTERIO DE TRANSPORTES, MOVILIDAD Y AGENDA URBANA"): (MI, TMS, C, "Vivienda y agenda urbana salen en 2024 a Vivienda y Agenda Urbana (25)."),
    ("17", "MINISTERIO DE TRANSPORTES Y MOVILIDAD SOSTENIBLE"): (MI, TMS, D, ""),
    ("18", "EDUCACIÓN, CULTURA Y DEPORTE"): (MI, EFPD, C, "Cultura sale en 2018 a Cultura y Deporte (24) y deportes vuelve en 2024; las universidades pasan a Ciencia (28) en 2018."),
    ("18", "EDUCACIÓN Y FORMACIÓN PROFESIONAL"): (MI, EFPD, C, "Deportes se incorpora en 2024 desde Cultura y Deporte (24)."),
    ("18", "MINISTERIO DE EDUCACIÓN Y FORMACIÓN PROFESIONAL"): (MI, EFPD, C, "Deportes se incorpora en 2024 desde Cultura y Deporte (24)."),
    ("18", "MINISTERIO DE EDUCACIÓN, FORMACIÓN PROFESIONAL Y DEPORTES"): (MI, EFPD, D, ""),
    ("19", "EMPLEO Y SEGURIDAD SOCIAL"): (MI, TES, C, "Seguridad Social y migraciones salen en 2021 (en la liquidación) a Inclusión, Seguridad Social y Migraciones (32): era la mayor parte del gasto de la sección."),
    ("19", "TRABAJO, MIGRACIONES Y S.S."): (MI, TES, C, "Seguridad Social y migraciones salen en 2021 a Inclusión, Seguridad Social y Migraciones (32): era la mayor parte del gasto de la sección."),
    ("19", "MINISTERIO DE TRABAJO, MIGRACIONES Y SEGURIDAD SOCIAL"): (MI, TES, C, "Seguridad Social y migraciones salen en 2021 a Inclusión, Seguridad Social y Migraciones (32): era la mayor parte del gasto de la sección."),
    ("19", "MINISTERIO DE TRABAJO Y ECONOMÍA SOCIAL"): (MI, TES, D, ""),
    ("20", "ENERGÍA, TURISMO Y AGENDA DIGITAL"): (MI, IT, C, "Energía sale en 2018 a Transición Ecológica (23) y telecomunicaciones y agenda digital a Economía (27); hoy, en Transformación Digital y Función Pública (33). Industria llega desde Economía, Industria y Competitividad (27)."),
    ("20", "INDUSTRIA, COMERCIO Y TURISMO"): (MI, IT, C, "Comercio sale en 2024 a Economía, Comercio y Empresa (27)."),
    ("20", "MINISTERIO DE INDUSTRIA, COMERCIO Y TURISMO"): (MI, IT, C, "Comercio sale en 2024 a Economía, Comercio y Empresa (27)."),
    ("20", "MINISTERIO DE INDUSTRIA Y TURISMO"): (MI, IT, D, ""),
    ("21", "AGRICULTURA, PESCA Y ALIMENTACIÓN"): (MI, APA, D, ""),
    ("21", "MINISTERIO DE AGRICULTURA, PESCA Y ALIMENTACIÓN"): (MI, APA, D, ""),
    ("22", "POLÍTICA TERRITORIAL Y FUNCIÓN PÚB."): (MI, PTMD, C, "Función Pública sale en 2022 a Hacienda (15) y hoy está en Transformación Digital y Función Pública (33); memoria democrática llega en 2024 desde Presidencia (25)."),
    ("22", "MINISTERIO DE POLÍTICA TERRITORIAL Y FUNCIÓN PÚBLICA"): (MI, PTMD, C, "Función Pública sale en 2022 a Hacienda (15) y hoy está en Transformación Digital y Función Pública (33); memoria democrática llega en 2024 desde Presidencia (25)."),
    ("22", "MINISTERIO DE POLÍTICA TERRITORIAL"): (MI, PTMD, C, "Memoria democrática llega en 2024 desde Presidencia (25)."),
    ("22", "MINISTERIO DE POLÍTICA TERRITORIAL Y MEMORIA DEMOCRÁTICA"): (MI, PTMD, D, ""),
    ("23", "AGRICULT. Y PESCA, ALIM. Y MEDIO AMB."): (MI, TERD, C, "Agricultura, pesca y alimentación (grupos de programas 41x) salen en 2019 a la nueva sección 21. El grueso del gasto directo era medio ambiente y agua (grupos 45x), que sigue en la 23; ver la ficha de Agricultura."),
    ("23", "TRANSICIÓN ECOLÓGICA"): (MI, TERD, C, "Absorbe energía (desde 20) en 2018; reto demográfico se añade en 2020."),
    ("23", "MINISTERIO PARA LA TRANSICIÓN ECOLÓGICA"): (MI, TERD, C, "Reto demográfico se añade en 2020."),
    ("23", "MINISTERIO PARA LA TRANSICIÓN ECOLÓGICA Y EL RETO DEMOGRÁFICO"): (MI, TERD, D, ""),
    ("24", "CULTURA Y DEPORTE"): (MI, CUL, C, "Deportes sale en 2024 a Educación, Formación Profesional y Deportes (18)."),
    ("24", "MINISTERIO DE CULTURA Y DEPORTE"): (MI, CUL, C, "Deportes sale en 2024 a Educación, Formación Profesional y Deportes (18)."),
    ("24", "MINISTERIO DE CULTURA"): (MI, CUL, D, ""),
    ("25", "PRESIDENCIA Y PARA LAS ADM. TERRIT."): (MI, PJRC, C, "Administraciones territoriales salen en 2018 a Política Territorial (22). En 2024 Presidencia se fusiona con Justicia en la 13 y el código 25 pasa a Vivienda."),
    ("25", "PRESIDENCIA, REL., CORTES E IGUALDAD"): (MI, PJRC, C, "Igualdad sale en 2021 a Igualdad (30). En 2024 se fusiona con Justicia en la 13 y el código 25 pasa a Vivienda."),
    ("25", "MINISTERIO DE LA PRESIDENCIA, RELACIONES CON LAS CORTES E IGUALDAD"): (MI, PJRC, C, "Igualdad sale en 2021 a Igualdad (30). En 2024 se fusiona con Justicia en la 13 y el código 25 pasa a Vivienda."),
    ("25", "MINISTERIO DE LA PRESIDENCIA, RELACIONES CON LAS CORTES Y MEMORIA DEMOCRÁTICA"): (MI, PJRC, C, "Memoria democrática sale en 2024 a Política Territorial (22); el resto se fusiona con Justicia en la 13 y el código 25 pasa a Vivienda."),
    ("25", "MINISTERIO DE VIVIENDA Y AGENDA URBANA"): (MI, VAU, D, "Nueva en 2024, con la vivienda que estaba en Transportes (17). Mismo código que la antigua Presidencia: no son la misma serie."),
    ("26", "SANIDAD, SERVICIOS SOCIALES E IGUALDAD"): (MI, SAN, C, "Servicios sociales e igualdad salen en 2020-2021 a Derechos Sociales (29) e Igualdad (30); consumo, a Consumo (31) y hoy a Derechos Sociales, Consumo y Agenda 2030 (29). Buena parte del gasto de la sección era de servicios sociales (Imserso)."),
    ("26", "SANIDAD, CONSUMO Y BIENESTAR SOCIAL"): (MI, SAN, C, "Bienestar social sale en 2021 a Derechos Sociales (29) y consumo a Consumo (31)."),
    ("26", "MINISTERIO DE SANIDAD, CONSUMO Y BIENESTAR SOCIAL"): (MI, SAN, C, "Bienestar social sale en 2021 a Derechos Sociales (29) y consumo a Consumo (31)."),
    ("26", "MINISTERIO DE SANIDAD"): (MI, SAN, D, ""),
    ("27", "ECONOMÍA, INDUSTRIA Y COMPETITIVIDAD"): (MI, ECE, C, "Investigación (grupos 46x) sale en 2018 a Ciencia (28) e industria a Industria, Comercio y Turismo (20)."),
    ("27", "ECONOMÍA Y EMPRESA"): (MI, ECE, C, "En 2021 asume telecomunicaciones y transformación digital; en 2024 esa parte pasa a Transformación Digital y Función Pública (33) y llega comercio desde la 20."),
    ("27", "MINISTERIO DE ECONOMÍA Y EMPRESA"): (MI, ECE, C, "En 2021 asume telecomunicaciones y transformación digital; en 2024 esa parte pasa a Transformación Digital y Función Pública (33) y llega comercio desde la 20."),
    ("27", "MINISTERIO DE ASUNTOS ECONÓMICOS Y TRANSFORMACIÓN DIGITAL"): (MI, ECE, C, "En 2024 la parte digital (conectividad, ciberseguridad, digitalización; la mayor parte del gasto de 2023) pasa a Transformación Digital y Función Pública (33) y llega comercio desde la 20."),
    ("27", "MINISTERIO DE ECONOMÍA, COMERCIO Y EMPRESA"): (MI, ECE, D, ""),
    ("28", "CIENCIA, INNOVACIÓN Y UNIVERSIDADES"): (MI, CIU, C, "Universidades sale en 2021 a Universidades (33) y vuelve en 2024."),
    ("28", "MINISTERIO DE CIENCIA, INNOVACIÓN Y UNIVERSIDADES"): (MI, CIU, D, ""),
    ("28", "MINISTERIO DE CIENCIA E INNOVACIÓN"): (MI, CIU, C, "Universidades (33) se reincorpora en 2024."),
    ("29", "MINISTERIO DE DERECHOS SOCIALES Y AGENDA 2030"): (MI, DSCA, C, "Consumo (31) se incorpora en 2024; juventud e infancia salen a Juventud e Infancia (31)."),
    ("29", "MINISTERIO DE DERECHOS SOCIALES, CONSUMO Y AGENDA 2030"): (MI, DSCA, D, ""),
    ("30", "MINISTERIO DE IGUALDAD"): (MI, IGU, D, ""),
    ("31", "MINISTERIO DE CONSUMO"): (MI, DSCA, C, "En 2024 se integra en Derechos Sociales, Consumo y Agenda 2030 (29); el código 31 pasa a Juventud e Infancia."),
    ("31", "MINISTERIO DE JUVENTUD E INFANCIA"): (MI, JI, D, "Nueva en 2024. Mismo código que el antiguo Consumo: no son la misma serie."),
    ("32", "MINISTERIO DE INCLUSIÓN, SEGURIDAD SOCIAL Y MIGRACIONES"): (MI, ISSM, D, "Nueva en 2021 con la Seguridad Social y las migraciones que estaban en Trabajo (19)."),
    ("33", "MINISTERIO DE UNIVERSIDADES"): (MI, CIU, C, "En 2024 se integra en Ciencia, Innovación y Universidades (28); el código 33 pasa a Transformación Digital y Función Pública."),
    ("33", "MINISTERIO PARA LA TRANSFORMACIÓN DIGITAL Y DE LA FUNCIÓN PÚBLICA"): (MI, TDFP, D, "Nueva en 2024 con la parte digital de Asuntos Económicos (27) y la Función Pública de Hacienda (15). Mismo código que la antigua Universidades: no son la misma serie."),
}

# Presupuesto de cada año: aprobado o prorrogado (los créditos iniciales de un año prorrogado son los del
# presupuesto anterior, y la brecha entre iniciales y definitivos crece por diseño)
PRESUPUESTO = {2017: ("aprobado", "Ley 3/2017 (aprobada en junio; hasta entonces, prórroga de 2016)"),
               2018: ("aprobado", "Ley 6/2018 (aprobada en julio; hasta entonces, prórroga de 2017)"),
               2019: ("prorrogado", "prórroga del presupuesto de 2018"),
               2020: ("prorrogado", "prórroga del presupuesto de 2018"),
               2021: ("aprobado", "Ley 11/2020"), 2022: ("aprobado", "Ley 22/2021"), 2023: ("aprobado", "Ley 31/2022"),
               2024: ("prorrogado", "prórroga del presupuesto de 2023"),
               2025: ("prorrogado", "prórroga del presupuesto de 2023"),
               2026: ("prorrogado", "prórroga del presupuesto de 2023")}


def f(x):
    return float(x.replace(",", ".")) if x not in ("", None) else None


def fmt(x, dec=2):
    if x is None:
        return ""
    if isinstance(x, float):
        return str(int(round(x))) if x.is_integer() else f"{x:.{dec}f}".replace(".", ",")
    return x


def leer(nombre):
    with open(DATOS / nombre, encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter=";"))


def escribir(nombre, filas, campos):
    with open(DATOS / nombre, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(campos)
        for r in filas:
            w.writerow([fmt(r.get(k)) for k in campos])


def main():
    sec = leer("liquidacion_secciones.csv")
    for r in sec:
        r["dato"] = "definitivo (liquidación)"
    if (DATOS / "mensual_secciones.csv").exists():
        for r in leer("mensual_secciones.csv"):
            r["dato"] = "provisional (mensual de diciembre)"
            sec.append(r)
    faltan = sorted({(r["codigo_seccion"], r["seccion"]) for r in sec} - set(REGLAS))
    assert not faltan, f"secciones sin regla: {faltan}"
    usados = {m for (t, m, _, _) in REGLAS.values() if t == MI}
    assert usados <= set(MINISTERIOS_2026), usados - set(MINISTERIOS_2026)

    # 1) equivalencias: una fila por (código, nombre), con el tramo de años en que aparece
    tramos = {}
    for r in sec:
        k = (r["codigo_seccion"], r["seccion"])
        tramos.setdefault(k, []).append(int(r["anio"]))
    eq = []
    for (c, n), anios in sorted(tramos.items(), key=lambda kv: (kv[0][0], min(kv[1]))):
        tipo, actual, cont, nota = REGLAS[(c, n)]
        eq.append(dict(codigo_seccion=c, seccion_igae=n, anio_desde=min(anios), anio_hasta=max(anios), tipo=tipo,
                       ministerio_actual=actual, continuidad=cont, nota=nota))
    escribir("equivalencias_secciones.csv", eq, ["codigo_seccion", "seccion_igae", "anio_desde", "anio_hasta",
             "tipo", "ministerio_actual", "continuidad", "nota"])

    # 2) liquidación por sección con el ministerio actual
    numericos = ["creditos_iniciales", "creditos_extraordinarios_suplementos", "ampliaciones", "transferencias",
                 "incorporacion_remanentes", "generaciones_ingresos", "bajas_otras_modificaciones",
                 "creditos_definitivos", "obligaciones", "pagos"]
    filas = []
    for r in sec:
        tipo, actual, cont, nota = REGLAS[(r["codigo_seccion"], r["seccion"])]
        anio = int(r["anio"])
        x = {k: f(r[k]) for k in numericos}
        x.update(anio=anio, codigo_seccion=r["codigo_seccion"], seccion=r["seccion"], tipo=tipo,
                 ministerio_actual=actual, continuidad=cont, presupuesto=PRESUPUESTO[anio][0], dato=r["dato"],
                 modificaciones_netas=x["creditos_definitivos"] - x["creditos_iniciales"],
                 pct_obligaciones_sobre_definitivos=100 * x["obligaciones"] / x["creditos_definitivos"]
                 if x["creditos_definitivos"] else None,
                 pct_obligaciones_sobre_iniciales=100 * x["obligaciones"] / x["creditos_iniciales"]
                 if x["creditos_iniciales"] else None,
                 pct_pagos_sobre_obligaciones=100 * x["pagos"] / x["obligaciones"] if x["obligaciones"] else None,
                 fuente=r["fuente"])
        filas.append(x)
    campos = ["anio", "presupuesto", "dato", "codigo_seccion", "seccion", "tipo", "ministerio_actual", "continuidad"] \
        + numericos[:1] + numericos[1:7] + ["modificaciones_netas"] + numericos[7:] \
        + ["pct_obligaciones_sobre_iniciales", "pct_obligaciones_sobre_definitivos", "pct_pagos_sobre_obligaciones",
           "fuente"]
    escribir("secciones_ministerio_actual.csv", filas, campos)

    # 3) primer cuadro: Defensa, Interior y Agricultura (secciones con continuidad directa)
    cuadro = [x for x in filas if x["ministerio_actual"] in (DEF, INT, APA)]
    for x in cuadro:
        x["nota_presupuesto"] = PRESUPUESTO[x["anio"]][1]
    cuadro.sort(key=lambda x: (x["ministerio_actual"] != DEF, x["ministerio_actual"] != INT, x["anio"]))
    escribir("cuadro_defensa_interior_agricultura.csv", cuadro,
             ["ministerio_actual", "anio", "presupuesto", "nota_presupuesto", "dato", "codigo_seccion", "seccion",
              "continuidad"] + numericos[:7] + ["modificaciones_netas"] + numericos[7:]
             + ["pct_obligaciones_sobre_iniciales", "pct_obligaciones_sobre_definitivos",
                "pct_pagos_sobre_obligaciones", "fuente"])
    print(f"{len(eq)} equivalencias, {len(filas)} filas sección-año, {len(cuadro)} filas en el cuadro")
    for x in cuadro:
        print(f"  {x['ministerio_actual'][15:30]:15} {x['anio']} {x['presupuesto'][:5]:5} "
              f"ini {x['creditos_iniciales']/1e6:9,.0f}  def {x['creditos_definitivos']/1e6:9,.0f}  "
              f"obl {x['obligaciones']/1e6:9,.0f} ({x['pct_obligaciones_sobre_definitivos']:.1f} %)  "
              f"pag {x['pagos']/1e6:9,.0f}")


if __name__ == "__main__":
    main()
