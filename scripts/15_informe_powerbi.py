"""Genera el modelo semántico y las 15 páginas del informe de Power BI (formato PBIP/PBIR).

Lee el proyecto tal como está en powerbi/ y reescribe, sin tocar nada más:
- SemanticModel/definition/tables/_Medidas.tmdl: formatos y carpetas de las medidas; las medidas de
  presupuesto pasan por dim_grupo (cada año, el ministerio de entonces; REGISTRO B15) y por el
  selector Euros (corrientes o constantes de 2025 con IPC, deflactor del PIB o del consumo
  público; REGISTRO B16); añade las medidas nuevas (equivalencias, cascada, valor del dinero).
- tablas Pasos y Euros (calculadas), dim_grupo (lee powerbi/dim_grupo.csv), dim_gobierno (lee
  powerbi/dim_gobierno.csv) y dim_anio (le une powerbi/deflactor.csv y las columnas de calendario de
  prórroga si aún no las tiene).
- relationships.tmdl: los hechos de presupuesto se relacionan con dim_ministerio a través de
  dim_grupo, no directamente.
- model.tmdl: referencias a las tablas nuevas.
- Report/definition: tema propio (StaticResources/RegisteredResources/), report.json, y las 15 páginas
  (page.json y visual.json de cada objeto) con banda de título, navegador de páginas y franja de filtros.

Es idempotente: se puede ejecutar las veces que haga falta sobre el mismo proyecto.

Antes: scripts 12 (CSV del modelo, incl. calendario), 13 (dim_grupo.csv), 14 (deflactor.csv) y 30 (CSV de los
apartados 7 a 13, 16 y 17: tablas fact_catastrofe… fact_mensual, páginas 9 a 14).
Después: cerrar Power BI Desktop si estaba abierto, abrir presupuesto_al_gasto.pbip y pulsar
«Actualizar» (las tablas calculadas y dim_grupo solo se cargan al actualizar). Guardar.

Uso: python scripts/15_informe_powerbi.py [carpeta_de_salida]
     (por defecto escribe en powerbi/; con una carpeta distinta deja powerbi/ intacto y escribe
     allí solo los archivos generados, útil para comparar).
"""
import json, os, re, sys, uuid, shutil, hashlib

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(RAIZ, "powerbi") + "/"
OUT = (os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(RAIZ, "powerbi")) + "/"
SM = "presupuesto_al_gasto.SemanticModel/definition/"
RP = "presupuesto_al_gasto.Report/definition/"

def w(rel, text, crlf=False):
    p = OUT + rel
    os.makedirs(os.path.dirname(p), exist_ok=True)
    if crlf:
        text = text.replace("\r\n", "\n").replace("\n", "\r\n")
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(text)

def gid(seed):
    return hashlib.md5(seed.encode()).hexdigest()[:20]

# ------------------------------------------------------------------ modelo: medidas
MEUR = r'#,0\ €'
PCT = r'0.0\ %;-0.0\ %;0.0\ %'
fmt = {}
folders = {}
for m in ["Iniciales", "Créditos extraordinarios y suplementos", "Ampliaciones", "Transferencias de crédito",
          "Remanentes", "Generaciones", "Bajas y otras", "Modificaciones", "Definitivos", "Obligaciones",
          "Pagos", "Sin gastar"]:
    fmt[m] = MEUR; folders[m] = "1 Presupuesto"
for m in ["% obligaciones sobre iniciales", "% ejecución", "% modificaciones sobre iniciales", "% pagado"]:
    fmt[m] = PCT; folders[m] = "1 Presupuesto"
folders["Continuidad"] = "1 Presupuesto"
for m in ["Organismos: obligaciones", "Transferencias del Estado restadas", "De ellas, de otros ministerios",
          "Devuelto al Estado por sus organismos", "Gasto agregado"]:
    fmt[m] = MEUR; folders[m] = "2 Organismos y gasto agregado"
for m in ["MRR definitivos", "MRR obligaciones"]:
    fmt[m] = MEUR; folders[m] = "3 Mecanismo de Recuperación"
for m in ["MRR % ejecutado", "MRR peso en las obligaciones"]:
    fmt[m] = PCT; folders[m] = "3 Mecanismo de Recuperación"
for m in ["Obligaciones por capítulo", "Definitivos por capítulo", "Sin gastar por capítulo"]:
    fmt[m] = MEUR; folders[m] = "4 Capítulos"
fmt["% del año"] = PCT; folders["% del año"] = "4 Capítulos"
for m in ["Importe ordinario", "Importe ordinario nov-dic", "Programas especiales", "Contratos menores: importe"]:
    fmt[m] = MEUR; folders[m] = "5 Contratación"
for m in ["Cuota nov-dic", "Cuota nov-dic AGE sin él", "Oferta única %", "Negociado sin publicidad %"]:
    fmt[m] = PCT; folders[m] = "5 Contratación"
for m in ["Adjudicaciones", "Contratos menores"]:
    fmt[m] = "#,0"; folders[m] = "5 Contratación"
for m in ["Baja media %", "Diferencia nov-dic (pp)", "Estudio: diferencia (pp)", "Estudio: IC 95 % inferior",
          "Estudio: IC 95 % superior"]:
    fmt[m] = "0.0"; folders[m] = "5 Contratación"

txt = open(SRC + SM + "tables/_Medidas.tmdl", encoding="utf-8").read().replace("\r\n", "\n")
lines = txt.split("\n")
out, cur, seen = [], None, set()
for ln in lines:
    mm = re.match(r"^\tmeasure (.+?) =", ln)
    if mm:
        name = mm.group(1)
        if name.startswith("'"):
            name = name[1:-1].replace("''", "'")
        cur = name; seen.add(name)
        out.append(ln); continue
    if re.match(r"^\t(column|partition|annotation) ", ln):
        cur = None
    if cur is not None:
        if ln.startswith("\t\tformatString:") or ln.startswith("\t\tdisplayFolder:") \
                or ln.startswith("\t\tannotation PBI_FormatHint"):
            continue
        if ln.startswith("\t\tlineageTag:"):
            if cur in fmt:
                out.append("\t\tformatString: " + fmt[cur])
            if cur in folders:
                out.append("\t\tdisplayFolder: " + folders[cur])
            out.append(ln); continue
    out.append(ln)
missing = set(fmt) - seen
assert not missing, missing
txt = "\n".join(out)
txt = re.sub(r"\n{3,}", "\n\n", txt)

def bloques(txt):
    ls = txt.split("\n")
    res = []
    i = 0
    while i < len(ls):
        m = re.match(r"^\tmeasure (.+?) =", ls[i])
        if m:
            name = m.group(1)
            if name.startswith("'"):
                name = name[1:-1].replace("''", "'")
            j = i + 1
            while j < len(ls) and not re.match(r"^\t[^\t]", ls[j]):
                j += 1
            res.append((name, i, j))
            i = j
        else:
            i += 1
    return ls, res

def quitar_medida(txt, name):
    ls, bl = bloques(txt)
    for n, i, j in bl:
        if n == name:
            return "\n".join(ls[:i] + ls[j:])
    return txt

def poner_expr(txt, name, expr):
    ls, bl = bloques(txt)
    for n, i, j in bl:
        if n != name:
            continue
        head = re.match(r"^(\tmeasure .+?) =", ls[i]).group(1) + " = ```"
        k = i + 1
        while k < len(ls) and ls[k].startswith("\t\t\t"):   # cuerpo de la expresión (3 tabuladores), con o sin ```
            k += 1
        nuevo = [head] + ["\t\t\t" + e for e in expr.split("\n")] + ["\t\t\t```"]
        return "\n".join(ls[:i] + nuevo + ls[k:])
    raise KeyError(name)

def pares(nombre="_pares", estado=True, extra=""):
    cond = ",\n        dim_grupo[incluir_estado] = 1" if estado else ""
    if extra:
        cond = ",\n        " + extra
    return (f"VAR {nombre} =\n    CALCULATETABLE (\n        SUMMARIZE ( dim_grupo, dim_grupo[anio], dim_grupo[ministerio_id] ),\n"
            f"        REMOVEFILTERS ( dim_ministerio ), REMOVEFILTERS ( dim_grupo ),\n"
            f"        TREATAS ( _grupos, dim_grupo[anio], dim_grupo[grupo_id] ){cond}\n    )")

GR = "VAR _k = SELECTEDVALUE ( Euros[orden], 1 )\nVAR _grupos = SUMMARIZE ( dim_grupo, dim_grupo[anio], dim_grupo[grupo_id] )"

def S(t, c):
    return (f"SUMX ( {t}, {t}[{c}] * SWITCH ( _k, 2, RELATED ( dim_anio[factor_2025] ), "
            f"3, RELATED ( dim_anio[factor_pib] ), 4, RELATED ( dim_anio[factor_aapp] ), 1 ) )")

def redir(tabla, columna, estado=True):
    return (GR + "\n" + pares(estado=estado) +
            f"\nRETURN\n    CALCULATE ( {S(tabla, columna)}, TREATAS ( _pares, {tabla}[anio], {tabla}[ministerio_id] ) )")

ESTADO = {"Iniciales": "estado_creditos_iniciales",
          "Créditos extraordinarios y suplementos": "estado_creditos_extraordinarios_suplementos",
          "Ampliaciones": "estado_ampliaciones", "Transferencias de crédito": "estado_transferencias",
          "Remanentes": "estado_incorporacion_remanentes", "Generaciones": "estado_generaciones_ingresos",
          "Bajas y otras": "estado_bajas_otras_modificaciones", "Modificaciones": "estado_modificaciones_netas",
          "Definitivos": "estado_creditos_definitivos", "Obligaciones": "estado_obligaciones", "Pagos": "estado_pagos",
          "MRR definitivos": "mrr_creditos_definitivos", "MRR obligaciones": "mrr_obligaciones"}
ORG = {"Organismos: obligaciones": "organismos_obligaciones",
       "Transferencias del Estado restadas": "transferencias_restadas",
       "De ellas, de otros ministerios": "transferencias_de_otros_ministerios",
       "Devuelto al Estado por sus organismos": "transferencias_de_sus_organismos_al_estado"}
for n, c in ESTADO.items():
    txt = poner_expr(txt, n, redir("fact_ministerio_anio", c, True))
for n, c in ORG.items():
    txt = poner_expr(txt, n, redir("fact_ministerio_anio", c, False))
txt = poner_expr(txt, "Gasto agregado", GR + "\n" + pares(estado=False) + "\n" +
    pares("_excluidos", extra="dim_grupo[incluir_estado] = 0") +
    "\nRETURN\n    CALCULATE ( " + S("fact_ministerio_anio", "gasto_agregado_sin_doble_computo") + ", TREATAS ( _pares, fact_ministerio_anio[anio], fact_ministerio_anio[ministerio_id] ) )"
    "\n        - CALCULATE ( " + S("fact_ministerio_anio", "estado_obligaciones") + ", TREATAS ( _excluidos, fact_ministerio_anio[anio], fact_ministerio_anio[ministerio_id] ) )")
for n, c in [("Obligaciones por capítulo", "obligaciones"), ("Definitivos por capítulo", "creditos_definitivos")]:
    txt = poner_expr(txt, n, GR + "\n" + pares("_pares_estado") + "\n" + pares(estado=False) +
        f"\nRETURN\n    CALCULATE ( {S('fact_capitulo', c)}, TREATAS ( _pares_estado, fact_capitulo[anio], fact_capitulo[ministerio_id] ), KEEPFILTERS ( fact_capitulo[ambito] = \"Estado\" ) )"
        f"\n        + CALCULATE ( {S('fact_capitulo', c)}, TREATAS ( _pares, fact_capitulo[anio], fact_capitulo[ministerio_id] ), KEEPFILTERS ( fact_capitulo[ambito] <> \"Estado\" ) )")
txt = poner_expr(txt, "Continuidad", "SELECTEDVALUE ( dim_grupo[existia] )")

def bloque_nuevo(nombre, expr, formato=None, carpeta=None):
    q = "'" + nombre.replace("'", "''") + "'"
    out = f"\tmeasure {q} = ```\n" + "\n".join("\t\t\t" + e for e in expr.split("\n")) + "\n\t\t\t```\n"
    if formato:
        out += f"\t\tformatString: {formato}\n"
    if carpeta:
        out += f"\t\tdisplayFolder: {carpeta}\n"
    out += f"\t\tlineageTag: {uuid.uuid5(uuid.NAMESPACE_DNS, 'm.' + nombre)}\n\n"
    return out

extra_medidas = (
    bloque_nuevo("Organismos: derechos reconocidos", redir("fact_ingresos_organismos", "derechos_reconocidos", False), MEUR, "2 Organismos y gasto agregado")
    + bloque_nuevo("MRR programa: definitivos", redir("fact_mrr_programa", "creditos_definitivos", True), MEUR, "3 Mecanismo de Recuperación")
    + bloque_nuevo("MRR programa: obligaciones", redir("fact_mrr_programa", "obligaciones", True), MEUR, "3 Mecanismo de Recuperación")
    + bloque_nuevo("Ministerio de entonces", "SELECTEDVALUE ( dim_grupo[ministerio_entonces] )", None, "0 Equivalencias")
    + bloque_nuevo("Incluye", "SELECTEDVALUE ( dim_grupo[compuesto_por] )", None, "0 Equivalencias")
    + bloque_nuevo("Nivel de contratación",
        "SWITCH ( SELECTEDVALUE ( dim_ministerio[nivel_contratacion] ),\n    \"A\", \"A · concluyente\",\n    \"B\", \"B · solo si coinciden dos indicadores\",\n    \"C\", \"C · no concluyente\"\n)", None, "0 Equivalencias")
    + bloque_nuevo("Perfil de gasto",
        "VAR _p = SELECTEDVALUE ( dim_ministerio[perfil_gasto_2024] )\nVAR _x = SELECTEDVALUE ( dim_ministerio[perfil_pct_2024] )\nRETURN\n    IF ( NOT ISBLANK ( _p ), UPPER ( LEFT ( _p, 1 ) ) & MID ( _p, 2, 100 ) & \" (\" & FORMAT ( _x / 100, \"0 %\" ) & \" del gasto)\" )", None, "0 Equivalencias")
    + bloque_nuevo("Factor IPC", "MAX ( dim_anio[factor_2025] )", "0.000", "7 Valor del dinero")
    + bloque_nuevo("Factor deflactor del PIB", "MAX ( dim_anio[factor_pib] )", "0.000", "7 Valor del dinero")
    + bloque_nuevo("Factor deflactor del consumo público", "MAX ( dim_anio[factor_aapp] )", "0.000", "7 Valor del dinero")
    + bloque_nuevo("Días del año", "SUM ( dim_anio[dias_anio] )", "#,0", "8 Calendario")
    + bloque_nuevo("Días con presupuesto prorrogado", "SUM ( dim_anio[dias_prorrogado] )", "#,0", "8 Calendario")
    + bloque_nuevo("Días con presupuesto propio", "SUM ( dim_anio[dias_presupuesto_propio] )", "#,0", "8 Calendario")
    + bloque_nuevo("% del tiempo con presupuesto prorrogado", "DIVIDE ( [Días con presupuesto prorrogado], [Días del año] )", PCT, "8 Calendario")
    + bloque_nuevo("Días con el Gobierno en funciones", "SUM ( dim_anio[dias_en_funciones] )", "#,0", "8 Calendario")
    + bloque_nuevo("Días en funciones y con presupuesto prorrogado", "SUM ( dim_anio[dias_en_funciones_y_prorrogado] )", "#,0", "8 Calendario")
    + "".join(bloque_nuevo(f"Obligaciones: {et}", f"CALCULATE ( [Obligaciones], REMOVEFILTERS ( Euros ), Euros[orden] = {k} )", MEUR, "7 Valor del dinero")
              for k, et in [(1, "euros corrientes"), (2, "€ de 2025 (IPC)"), (3, "€ de 2025 (deflactor del PIB)"),
                            (4, "€ de 2025 (deflactor del consumo público)")]))
for et in ["euros corrientes", "€ de 2025 (IPC)", "€ de 2025 (deflactor del PIB)", "€ de 2025 (deflactor del consumo público)"]:
    fmt["Obligaciones: " + et] = MEUR
for n in ["Organismos: derechos reconocidos", "MRR programa: definitivos", "MRR programa: obligaciones"]:
    fmt[n] = MEUR

TIPO_TMDL = {"int": ("int64", "\n\t\tformatString: 0"), "dbl": ("double", ""), "txt": ("string", "")}
TIPO_M = {"int": "Int64.Type", "dbl": "type number", "txt": "type text"}
# ---- apartados 7 a 13, 16 y 17: tablas propias (script 30) y sus medidas. Todo en euros corrientes y por ministerio
# actual: no pasan por dim_grupo ni por el selector «Euros»; se relacionan solo con dim_anio.
NUEVAS_TABLAS = ["fact_catastrofe", "fact_catastrofe_destino", "fact_credito_nuevo", "fact_contratacion_gasto",
                 "fact_concentracion", "fact_ejecucion", "fact_bdns", "fact_bdns_instrumento", "fact_mensual"]
INT_COLS = {"anio", "mes", "lineas", "aplicaciones_con_obligaciones", "n50", "n80", "n95", "primera_capitulo",
            "adjudicaciones", "concesiones", "concesiones_sin_importe", "concesiones_ayudas_directas"}
TEXT_COLS = {"suceso_nombre", "medida", "dato", "ministerio", "tipo_seccion", "destino", "mecanismo", "grupo",
             "continuidad", "nivel_contratacion", "composicion", "presupuesto", "comparable", "primera_programa",
             "primera_destino", "instrumento", "importe_completo"}


def leer_cabecera_y_valores(t):
    import csv
    with open(SRC + t + ".csv", encoding="utf-8", newline="") as f:
        filas = list(csv.reader(f, delimiter=";"))
    return filas[0], filas[1:]


COLS_NUEVAS = {}
for t in NUEVAS_TABLAS:
    cab, filas = leer_cabecera_y_valores(t)
    tipos = []
    for i, n in enumerate(cab):
        vals = [r[i] for r in filas if r[i] != ""]
        if n in TEXT_COLS:
            tipos.append((n, "txt"))
        elif n in INT_COLS:
            assert all(re.fullmatch(r"-?\d+", v) for v in vals), (t, n)
            tipos.append((n, "int"))
        else:
            assert all(re.fullmatch(r"-?\d+(,\d+)?", v) for v in vals), (t, n)
            tipos.append((n, "dbl"))
    COLS_NUEVAS[t] = tipos
    cols_tmdl = ""
    for n, tp in tipos:
        cols_tmdl += (f"\tcolumn {n}\n\t\tdataType: {TIPO_TMDL[tp][0]}{TIPO_TMDL[tp][1]}\n" + ("\t\tisHidden\n" if n == "anio" else "") +
                      f"\t\tlineageTag: {uuid.uuid5(uuid.NAMESPACE_DNS, t + '.' + n)}\n\t\tsummarizeBy: none\n"
                      f"\t\tsourceColumn: {n}\n\n\t\tannotation SummarizationSetBy = Automatic\n\n")
    tipos_m = ", ".join('{"%s", %s}' % (n, TIPO_M[tp]) for n, tp in tipos)
    w(SM + f"tables/{t}.tmdl",
      f"table {t}\n\tlineageTag: {uuid.uuid5(uuid.NAMESPACE_DNS, t)}\n\n" + cols_tmdl +
      f"\tpartition {t} = m\n\t\tmode: import\n\t\tsource =\n\t\t\t\tlet\n"
      f"\t\t\t\t    Origen = Csv.Document(File.Contents(RutaProyecto & \"powerbi\\{t}.csv\"), [Delimiter = \";\", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),\n"
      "\t\t\t\t    Encabezados = Table.PromoteHeaders(Origen, [PromoteAllScalars = true]),\n"
      f"\t\t\t\t    Tipos = Table.TransformColumnTypes(Encabezados, {{{tipos_m}}}, \"es-ES\")\n"
      "\t\t\t\tin\n\t\t\t\t    Tipos\n\n"
      "\tannotation PBI_NavigationStepName = Navegación\n\n\tannotation PBI_ResultType = Table\n\n", crlf=True)


def SUMA(t, c):
    return f"SUM ( {t}[{c}] )"


def MEDIA(t, c):
    return f"AVERAGE ( {t}[{c}] )"


C9, C10, C11, C12, C13, C14 = ("9 Catástrofes", "10 Crédito nuevo y remanentes", "11 Inicial, reconocido y pagado",
                               "12 Contratación frente a gasto y concentración", "13 Subvenciones (BDNS)", "14 Calendario mensual")
E = "fact_ejecucion"
CG = "fact_contratacion_gasto"
MEDIDAS_NUEVAS = [
    # 9. catástrofes
    ("Catástrofes: definitivos", SUMA("fact_catastrofe", "creditos_definitivos"), MEUR, C9),
    ("Catástrofes: obligaciones", SUMA("fact_catastrofe", "obligaciones"), MEUR, C9),
    ("Catástrofes: % reconocido", "DIVIDE ( [Catástrofes: obligaciones], [Catástrofes: definitivos] )", PCT, C9),
    ("Catástrofes por destino: obligaciones", SUMA("fact_catastrofe_destino", "obligaciones"), MEUR, C9),
    # 10. crédito nuevo y remanentes
    ("Crédito nuevo: definitivos", SUMA("fact_credito_nuevo", "creditos_definitivos"), MEUR, C10),
    ("Crédito nuevo: obligaciones", SUMA("fact_credito_nuevo", "obligaciones"), MEUR, C10),
    ("Crédito nuevo: % reconocido", "DIVIDE ( [Crédito nuevo: obligaciones], [Crédito nuevo: definitivos] )", PCT, C10),
    ("Crédito nuevo: % reconocido sin capítulo 8",
     "DIVIDE ( " + SUMA("fact_credito_nuevo", "obligaciones_sin_cap8") + ", " + SUMA("fact_credito_nuevo", "creditos_definitivos_sin_cap8") + " )", PCT, C10),
    ("Remanentes: sin reconocer", SUMA(E, "sin_reconocer"), MEUR, C10),
    ("Remanentes: incorporado al año siguiente", SUMA(E, "incorporacion_anio_siguiente"), MEUR, C10),
    ("Remanentes: sin incorporar", SUMA(E, "sin_incorporar"), MEUR, C10),
    ("Remanentes: % sin reconocer", f"DIVIDE ( [Remanentes: sin reconocer], {SUMA(E, 'creditos_definitivos')} )", PCT, C10),
    ("Remanentes: % incorporado", "DIVIDE ( [Remanentes: incorporado al año siguiente], [Remanentes: sin reconocer] )", PCT, C10),
    # 11. inicial, reconocido y pagado (apartados 11, 12 y 13)
    ("Ejecución: créditos iniciales", SUMA(E, "creditos_iniciales"), MEUR, C11),
    ("Ejecución: créd. extraordinarios y suplementos", SUMA(E, "creditos_extraordinarios_suplementos"), MEUR, C11),
    ("Ejecución: ampliaciones", SUMA(E, "ampliaciones"), MEUR, C11),
    ("Ejecución: transferencias de crédito", SUMA(E, "transferencias"), MEUR, C11),
    ("Ejecución: incorporación de remanentes", SUMA(E, "incorporacion_remanentes"), MEUR, C11),
    ("Ejecución: generaciones", SUMA(E, "generaciones_ingresos"), MEUR, C11),
    ("Ejecución: bajas y otras", SUMA(E, "bajas_otras_modificaciones"), MEUR, C11),
    ("Ejecución: definitivos", SUMA(E, "creditos_definitivos"), MEUR, C11),
    ("Ejecución: obligaciones", SUMA(E, "obligaciones"), MEUR, C11),
    ("Ejecución: pagos", SUMA(E, "pagos"), MEUR, C11),
    ("Ejecución: pendiente de pago", SUMA(E, "pendiente_de_pago"), MEUR, C11),
    ("Ejecución: % pendiente de pago", "DIVIDE ( [Ejecución: pendiente de pago], [Ejecución: obligaciones] )", PCT, C11),
    ("Ejecución: % obligaciones sobre iniciales (años comparables)",
     f"CALCULATE ( DIVIDE ( {SUMA(E, 'obligaciones')}, {SUMA(E, 'creditos_iniciales')} ), {E}[comparable] = \"sí\" )", PCT, C11),
    # 12. contratación frente a gasto y concentración (apartados 9 y 10)
    ("Contratación y gasto: gasto agregado", SUMA(CG, "gasto_agregado"), MEUR, C12),
    ("Contratación y gasto: personal", SUMA(CG, "personal"), MEUR, C12),
    ("Contratación y gasto: compras e inversiones", SUMA(CG, "compras_inversiones"), MEUR, C12),
    ("Contratación y gasto: préstamos y aportaciones", SUMA(CG, "prestamos_aportaciones"), MEUR, C12),
    ("Contratación y gasto: transferencias y resto", SUMA(CG, "transferencias_y_resto"), MEUR, C12),
    ("Contratación y gasto: licitaciones ordinarias", SUMA(CG, "licitaciones_ordinario"), MEUR, C12),
    ("Contratación y gasto: contratos menores", SUMA(CG, "menores_ordinario"), MEUR, C12),
    ("Contratación y gasto: adjudicado ordinario", SUMA(CG, "contratacion_ordinaria"), MEUR, C12),
    ("Contratación y gasto: programas especiales", SUMA(CG, "programas_especiales"), MEUR, C12),
    ("Contratación y gasto: adjudicado total", SUMA(CG, "adjudicado_total"), MEUR, C12),
    ("Contratación y gasto: % adjudicado ordinario sobre el gasto",
     "DIVIDE ( [Contratación y gasto: adjudicado ordinario], [Contratación y gasto: gasto agregado] )", PCT, C12),
    ("Contratación y gasto: % adjudicado total sobre compras e inversiones",
     f"CALCULATE ( DIVIDE ( {SUMA(CG, 'adjudicado_total')}, {SUMA(CG, 'compras_inversiones')} ), {CG}[composicion] = \"sí\" )", PCT, C12),
    ("Concentración: peso de la primera línea, %", MEDIA("fact_concentracion", "pct_primera"), "0.0", C12),
    ("Concentración: peso de las cinco primeras líneas, %", MEDIA("fact_concentracion", "pct_cinco_primeras"), "0.0", C12),
    ("Concentración: líneas para el 50 %", MEDIA("fact_concentracion", "n50"), "0.0", C12),
    ("Concentración: líneas para el 80 %", MEDIA("fact_concentracion", "n80"), "0.0", C12),
    ("Concentración: líneas para el 95 %", MEDIA("fact_concentracion", "n95"), "0.0", C12),
    # 13. BDNS (apartado 16)
    ("BDNS: concesiones", SUMA("fact_bdns", "concesiones"), "#,0", C13),
    ("BDNS: sin importe conocido", SUMA("fact_bdns", "concesiones_sin_importe"), "#,0", C13),
    ("BDNS: subvenciones y ayudas directas", SUMA("fact_bdns", "subvenciones_y_ayudas_directas"), MEUR, C13),
    ("BDNS: préstamos", SUMA("fact_bdns", "prestamos"), MEUR, C13),
    ("BDNS: garantías", SUMA("fact_bdns", "garantias"), MEUR, C13),
    ("BDNS: ventajas fiscales", SUMA("fact_bdns", "ventajas_fiscales"), MEUR, C13),
    ("BDNS: obligaciones de los capítulos 4 y 7 del Estado", SUMA("fact_bdns", "obligaciones_cap4_cap7_estado"), MEUR, C13),
    ("BDNS: ayudas directas sobre los capítulos 4 y 7",
     "DIVIDE ( [BDNS: subvenciones y ayudas directas], [BDNS: obligaciones de los capítulos 4 y 7 del Estado] )", PCT, C13),
    ("BDNS por instrumento: importe", SUMA("fact_bdns_instrumento", "importe"), MEUR, C13),
    ("BDNS por instrumento: concesiones", SUMA("fact_bdns_instrumento", "concesiones"), "#,0", C13),
    # 14. calendario mensual (apartado 17)
    ("Mensual: obligaciones acumuladas", SUMA("fact_mensual", "obligaciones_acumuladas"), MEUR, C14),
    ("Mensual: obligaciones del mes", SUMA("fact_mensual", "obligaciones_del_mes"), MEUR, C14),
    ("Mensual: pagos acumulados", SUMA("fact_mensual", "pagos_acumulados"), MEUR, C14),
    ("Mensual: % acumulado del año",
     "DIVIDE ( " + SUMA("fact_mensual", "obligaciones_acumuladas") + ", CALCULATE ( " + SUMA("fact_mensual", "obligaciones_acumuladas")
     + ", REMOVEFILTERS ( fact_mensual[mes] ), fact_mensual[mes] = 12 ) )", PCT, C14),
    ("Mensual: % pagado", "DIVIDE ( [Mensual: pagos acumulados], [Mensual: obligaciones acumuladas] )", PCT, C14),
]
for n, ex, fo, ca in MEDIDAS_NUEVAS:
    fmt[n] = fo
    extra_medidas += bloque_nuevo(n, ex, fo, ca)

nuevas = f"""\tmeasure 'MRR sin gastar' = [MRR definitivos] - [MRR obligaciones]
\t\tformatString: {MEUR}
\t\tdisplayFolder: 3 Mecanismo de Recuperación
\t\tlineageTag: {uuid.uuid5(uuid.NAMESPACE_DNS, 'mrrsg')}

\tmeasure 'Importe del paso' = ```
\t\t\tSWITCH (
\t\t\t    SELECTEDVALUE ( Pasos[paso] ),
\t\t\t    "Créditos iniciales", [Iniciales],
\t\t\t    "Créd. extraordinarios y suplementos", [Créditos extraordinarios y suplementos],
\t\t\t    "Ampliaciones", [Ampliaciones],
\t\t\t    "Transferencias de crédito", [Transferencias de crédito],
\t\t\t    "Remanentes", [Remanentes],
\t\t\t    "Generaciones", [Generaciones],
\t\t\t    "Bajas y otras", [Bajas y otras],
\t\t\t    "Sin gastar", - [Sin gastar]
\t\t\t)
\t\t\t```
\t\tformatString: {MEUR}
\t\tdisplayFolder: 6 Cascada
\t\tlineageTag: {uuid.uuid5(uuid.NAMESPACE_DNS, 'impaso')}

"""
# idempotencia: se quitan las medidas que este script añade (si ya estaban) y se vuelven a poner
for n in re.findall(r"^\tmeasure '((?:[^']|'')+)' =", nuevas + extra_medidas, flags=re.M):
    txt = quitar_medida(txt, n.replace("''", "'"))
txt = re.sub(r"\n{3,}", "\n\n", txt)
assert "\tcolumn Columna1" in txt
txt = txt.replace("\tcolumn Columna1", nuevas + extra_medidas + "\tcolumn Columna1", 1)
w(SM + "tables/_Medidas.tmdl", txt, crlf=True)

pasos = f"""table Pasos
\tlineageTag: {uuid.uuid5(uuid.NAMESPACE_DNS, 'pasos')}

\tcolumn orden
\t\tdataType: int64
\t\tformatString: 0
\t\tlineageTag: {uuid.uuid5(uuid.NAMESPACE_DNS, 'pasos.orden')}
\t\tsummarizeBy: none
\t\tisNameInferred
\t\tsourceColumn: [orden]

\t\tannotation SummarizationSetBy = Automatic

\tcolumn paso
\t\tdataType: string
\t\tlineageTag: {uuid.uuid5(uuid.NAMESPACE_DNS, 'pasos.paso')}
\t\tsummarizeBy: none
\t\tisNameInferred
\t\tsourceColumn: [paso]
\t\tsortByColumn: orden

\t\tannotation SummarizationSetBy = Automatic

\tpartition Pasos = calculated
\t\tmode: import
\t\tsource = ```
\t\t\t\tDATATABLE (
\t\t\t\t    "orden", INTEGER, "paso", STRING,
\t\t\t\t    {{
\t\t\t\t        {{ 1, "Créditos iniciales" }}, {{ 2, "Créd. extraordinarios y suplementos" }}, {{ 3, "Ampliaciones" }},
\t\t\t\t        {{ 4, "Transferencias de crédito" }}, {{ 5, "Remanentes" }}, {{ 6, "Generaciones" }}, {{ 7, "Bajas y otras" }},
\t\t\t\t        {{ 8, "Sin gastar" }}
\t\t\t\t    }}
\t\t\t\t)
\t\t\t\t```

\tannotation PBI_Id = {uuid.uuid5(uuid.NAMESPACE_DNS, 'pasos.id').hex}

"""
w(SM + "tables/Pasos.tmdl", pasos, crlf=True)

euros = f"""table Euros
\tlineageTag: {uuid.uuid5(uuid.NAMESPACE_DNS, 'euros')}

\tcolumn euros
\t\tdataType: string
\t\tlineageTag: {uuid.uuid5(uuid.NAMESPACE_DNS, 'euros.euros')}
\t\tsummarizeBy: none
\t\tisNameInferred
\t\tsourceColumn: [euros]
\t\tsortByColumn: orden

\t\tannotation SummarizationSetBy = Automatic

\tcolumn orden
\t\tdataType: int64
\t\tformatString: 0
\t\tisHidden
\t\tlineageTag: {uuid.uuid5(uuid.NAMESPACE_DNS, 'euros.orden')}
\t\tsummarizeBy: none
\t\tisNameInferred
\t\tsourceColumn: [orden]

\t\tannotation SummarizationSetBy = Automatic

\tpartition Euros = calculated
\t\tmode: import
\t\tsource = ```
\t\t\t\tDATATABLE ( "euros", STRING, "orden", INTEGER, {{ {{ "Corrientes", 1 }}, {{ "Constantes de 2025 (IPC)", 2 }}, {{ "Constantes de 2025 (deflactor del PIB)", 3 }}, {{ "Constantes de 2025 (deflactor del consumo público)", 4 }} }} )
\t\t\t\t```

"""
w(SM + "tables/Euros.tmdl", euros, crlf=True)

da = open(SRC + SM + "tables/dim_anio.tmdl", encoding="utf-8").read().replace("\r\n", "\n")
if "factor_aapp" not in da:
    cols_extra = ""
    for n in ["ipc_media_base2021", "factor_2025", "deflactor_pib_2020", "factor_pib", "deflactor_aapp_2020", "factor_aapp"]:
        cols_extra += (f"\tcolumn {n}\n\t\tdataType: double\n\t\tlineageTag: {uuid.uuid5(uuid.NAMESPACE_DNS, 'dim_anio.' + n)}\n"
                       f"\t\tsummarizeBy: none\n\t\tsourceColumn: {n}\n\n\t\tannotation SummarizationSetBy = Automatic\n\n")
    da = da.replace("\tpartition dim_anio = m", cols_extra + "\tpartition dim_anio = m", 1)
    viejo = "\t\t\t\tin\n\t\t\t\t    Tipos\n"
    assert viejo in da
    nuevo = ("\t\t\t\t    Defl = Table.PromoteHeaders(Csv.Document(File.Contents(RutaProyecto & \"powerbi\\deflactor.csv\"), [Delimiter = \";\", Encoding = 65001, QuoteStyle = QuoteStyle.None]), [PromoteAllScalars = true]),\n"
             "\t\t\t\t    DeflTipos = Table.TransformColumnTypes(Table.SelectColumns(Defl, {\"anio\", \"ipc_media_base2021\", \"factor_2025\", \"deflactor_pib_2020\", \"factor_pib\", \"deflactor_aapp_2020\", \"factor_aapp\"}), {{\"anio\", Int64.Type}, {\"ipc_media_base2021\", type number}, {\"factor_2025\", type number}, {\"deflactor_pib_2020\", type number}, {\"factor_pib\", type number}, {\"deflactor_aapp_2020\", type number}, {\"factor_aapp\", type number}}, \"es-ES\"),\n"
             "\t\t\t\t    Unido = Table.NestedJoin(Tipos, {\"anio\"}, DeflTipos, {\"anio\"}, \"d\", JoinKind.LeftOuter),\n"
             "\t\t\t\t    Resultado = Table.ExpandTableColumn(Unido, \"d\", {\"ipc_media_base2021\", \"factor_2025\", \"deflactor_pib_2020\", \"factor_pib\", \"deflactor_aapp_2020\", \"factor_aapp\"})\n"
             "\t\t\t\tin\n\t\t\t\t    Resultado\n")
    da = da.replace("\t\t\t\t    }, \"es-ES\")\n" + viejo, "\t\t\t\t    }, \"es-ES\"),\n" + nuevo, 1)
    assert "Resultado" in da
# calendario de prórroga y de Gobiernos en funciones (script 12): columnas de dim_anio
CAL = [("dias_anio", "int"), ("dias_prorrogado", "int"), ("dias_presupuesto_propio", "int"), ("pct_prorrogado", "dbl"),
       ("dias_en_funciones", "int"), ("dias_en_funciones_y_prorrogado", "int"), ("situacion_presupuesto", "txt")]
TIPO_TMDL = {"int": ("int64", "\n\t\tformatString: 0"), "dbl": ("double", ""), "txt": ("string", "")}
TIPO_M = {"int": "Int64.Type", "dbl": "type number", "txt": "type text"}
if "dias_prorrogado" not in da:
    cols_cal = ""
    for n, t in CAL:
        cols_cal += (f"\tcolumn {n}\n\t\tdataType: {TIPO_TMDL[t][0]}{TIPO_TMDL[t][1]}\n" + ("\t\tisHidden\n" if n == "pct_prorrogado" else "") +
                     f"\t\tlineageTag: {uuid.uuid5(uuid.NAMESPACE_DNS, 'dim_anio.' + n)}\n"
                     f"\t\tsummarizeBy: none\n\t\tsourceColumn: {n}\n\n\t\tannotation SummarizationSetBy = Automatic\n\n")
    da = da.replace("\tpartition dim_anio = m", cols_cal + "\tpartition dim_anio = m", 1)
    viejo = '{"comparable_22", type text}\n'
    assert viejo in da
    da = da.replace(viejo, '{"comparable_22", type text},\n\t\t\t\t        ' +
                    ", ".join('{"%s", %s}' % (n, TIPO_M[t]) for n, t in CAL) + "\n", 1)
    assert "dias_en_funciones_y_prorrogado" in da
w(SM + "tables/dim_anio.tmdl", da, crlf=True)

def columna(n, tipo, oculta=False):
    t = {"int": ("int64", "Int64.Type", "\n\t\tformatString: 0"), "txt": ("string", "type text", "")}[tipo]
    return (f"\tcolumn {n}\n\t\tdataType: {t[0]}{t[2]}\n" + ("\t\tisHidden\n" if oculta else "") +
            f"\t\tlineageTag: {uuid.uuid5(uuid.NAMESPACE_DNS, 'dim_grupo.' + n)}\n\t\tsummarizeBy: none\n"
            f"\t\tsourceColumn: {n}\n\n\t\tannotation SummarizationSetBy = Automatic\n\n")
COLS_G = [("anio", "int", False), ("ministerio_id", "int", True), ("grupo_id", "txt", True),
          ("ministerio_entonces", "txt", False), ("secciones_entonces", "txt", False), ("compuesto_por", "txt", False),
          ("existia", "txt", False), ("relacion", "txt", False), ("incluir_estado", "int", True)]
tipos_m = ", ".join('{"%s", %s}' % (n, "Int64.Type" if t == "int" else "type text") for n, t, _ in COLS_G)
dimg = (f"table dim_grupo\n\tlineageTag: {uuid.uuid5(uuid.NAMESPACE_DNS, 'dim_grupo')}\n\n" +
        "".join(columna(*c) for c in COLS_G) +
        "\tpartition dim_grupo = m\n\t\tmode: import\n\t\tsource =\n"
        "\t\t\t\tlet\n"
        "\t\t\t\t    Origen = Csv.Document(File.Contents(RutaProyecto & \"powerbi\\dim_grupo.csv\"), [Delimiter = \";\", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),\n"
        "\t\t\t\t    Encabezados = Table.PromoteHeaders(Origen, [PromoteAllScalars = true]),\n"
        f"\t\t\t\t    Tipos = Table.TransformColumnTypes(Encabezados, {{{tipos_m}}}, \"es-ES\")\n"
        "\t\t\t\tin\n\t\t\t\t    Tipos\n\n"
        "\tannotation PBI_NavigationStepName = Navegación\n\n\tannotation PBI_ResultType = Table\n\n")
w(SM + "tables/dim_grupo.tmdl", dimg, crlf=True)

GOB = [("orden", "int"), ("gobierno", "txt"), ("presidente_real_decreto", "txt"), ("nombrado_el", "txt"),
       ("en_funciones_desde", "txt"), ("hasta", "txt"), ("motivo_del_fin", "txt"), ("dias_mandato", "int"),
       ("dias_en_funciones", "int"), ("dias_presupuesto_prorrogado", "int"), ("pct_prorrogado", "dbl"),
       ("dias_en_funciones_con_presupuesto_prorrogado", "int"), ("leyes_pge_publicadas_en_el_mandato", "txt")]
fmt_g = {"pct_prorrogado": "\n\t\tformatString: 0.0"}
ORDENADAS = ("gobierno", "presidente_real_decreto", "nombrado_el", "en_funciones_desde", "hasta")  # fechas en texto: se ordenan por «orden»
cols_g = "".join(
    f"\tcolumn {n}\n\t\tdataType: {TIPO_TMDL[t][0]}{TIPO_TMDL[t][1] or fmt_g.get(n, '')}\n"
    f"\t\tlineageTag: {uuid.uuid5(uuid.NAMESPACE_DNS, 'dim_gobierno.' + n)}\n\t\tsummarizeBy: none\n"
    f"\t\tsourceColumn: {n}\n" + ("\t\tsortByColumn: orden\n" if n in ORDENADAS else "") +
    "\n\t\tannotation SummarizationSetBy = Automatic\n\n" for n, t in GOB)
tipos_g = ", ".join('{"%s", %s}' % (n, TIPO_M[t]) for n, t in GOB)
dimgob = (f"table dim_gobierno\n\tlineageTag: {uuid.uuid5(uuid.NAMESPACE_DNS, 'dim_gobierno')}\n\n" + cols_g +
          "\tpartition dim_gobierno = m\n\t\tmode: import\n\t\tsource =\n"
          "\t\t\t\tlet\n"
          "\t\t\t\t    Origen = Csv.Document(File.Contents(RutaProyecto & \"powerbi\\dim_gobierno.csv\"), [Delimiter = \";\", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),\n"
          "\t\t\t\t    Encabezados = Table.PromoteHeaders(Origen, [PromoteAllScalars = true]),\n"
          f"\t\t\t\t    Tipos = Table.TransformColumnTypes(Encabezados, {{{tipos_g}}}, \"es-ES\")\n"
          "\t\t\t\tin\n\t\t\t\t    Tipos\n\n"
          "\tannotation PBI_NavigationStepName = Navegación\n\n\tannotation PBI_ResultType = Table\n\n")
w(SM + "tables/dim_gobierno.tmdl", dimgob, crlf=True)

rels = open(SRC + SM + "relationships.tmdl", encoding="utf-8").read().replace("\r\n", "\n")
partes = [b for b in rels.split("\n\n") if b.strip()]
QUITAR = {f"fromColumn: {t}.ministerio_id" for t in
          ["fact_ministerio_anio", "fact_capitulo", "fact_programa", "fact_mrr_programa", "fact_ingresos_organismos"]}
partes = [b for b in partes if not any(q in b for q in QUITAR) and "dim_grupo" not in b]
partes = [b for b in partes if not any(f"fromColumn: {t}." in b for t in NUEVAS_TABLAS)]
for t in NUEVAS_TABLAS:
    partes.append(f"relationship {uuid.uuid5(uuid.NAMESPACE_DNS, 'rel.' + t + '.anio')}\n\tfromColumn: {t}.anio\n\ttoColumn: dim_anio.anio")
for a, b in [("dim_grupo.ministerio_id", "dim_ministerio.ministerio_id"), ("dim_grupo.anio", "dim_anio.anio")]:
    partes.append(f"relationship {uuid.uuid5(uuid.NAMESPACE_DNS, 'rel.' + a)}\n\tfromColumn: {a}\n\ttoColumn: {b}")
w(SM + "relationships.tmdl", "\n\n".join(partes) + "\n\n", crlf=True)

model = open(SRC + SM + "model.tmdl", encoding="utf-8").read()
if "ref table Euros" not in model:
    model = model.replace("ref table Pasos", "ref table Pasos\nref table Euros", 1)
if "ref table dim_grupo" not in model:
    model = model.replace("ref table dim_anio", "ref table dim_anio\nref table dim_grupo", 1)
    model = model.replace('"fact_contratacion_mes",', '"fact_contratacion_mes","dim_grupo",', 1)
if "ref table dim_gobierno" not in model:
    model = model.replace("ref table dim_grupo", "ref table dim_grupo\nref table dim_gobierno", 1)
    model = model.replace('"dim_grupo",', '"dim_grupo","dim_gobierno",', 1)
if f"ref table {NUEVAS_TABLAS[0]}" not in model:
    model = model.replace("ref table dim_gobierno", "ref table dim_gobierno\n" + "\n".join("ref table " + t for t in NUEVAS_TABLAS), 1)
    model = model.replace('"dim_gobierno",', '"dim_gobierno",' + ",".join('"%s"' % t for t in NUEVAS_TABLAS) + ",", 1)
if "ref table Pasos" not in model:
    model = model.replace("ref table _Medidas", "ref table _Medidas\nref table Pasos")
w(SM + "model.tmdl", model, crlf=True)

# ------------------------------------------------------------------ informe
VC = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.14.0/schema.json"
PG = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"

# Identidad visual. Paleta categórica de 8 tonos validada con el validador de paletas de la habilidad dataviz
# (tramo de luminosidad OKLCH 0,43-0,77, croma >= 0,10, separación para daltonismo >= 8, contraste >= 3:1 sobre blanco);
# el noveno tono (gris) es neutro y solo lo usa el capítulo 9.
NAVY = "#14233B"      # banda de título
INK = "#1F2933"       # texto principal
INK2 = "#52606D"      # texto secundario
INK3 = "#7B8794"      # texto terciario / noveno color
LINEA = "#D5DBE3"     # bordes de los paneles
REJILLA = "#E6EAF0"   # rejilla de los gráficos
FONDO = "#EEF1F5"     # fondo de página
BLANCO = "#FFFFFF"
ACENTO = "#BC7C0E"    # pestaña activa
PALETA = ["#2B5C9E", "#BC7C0E", "#0E9585", "#B5453F", "#7456A6", "#789A1F", "#CC5C94", "#4B94DA", INK3]
BANDA_H = 112
TOP = 200             # donde empieza el contenido bajo la banda y la franja de filtros
LIMITE = 1060         # donde acaba en las páginas de 1080 de alto


def lit(v):
    return {"expr": {"Literal": {"Value": v}}}


def solid(c):
    return {"solid": {"color": lit(f"'{c}'")}}


def col(t, c, nombre=None):
    d = {"field": {"Column": {"Expression": {"SourceRef": {"Entity": t}}, "Property": c}},
         "queryRef": f"{t}.{c}", "nativeQueryRef": c}
    if nombre:
        d["displayName"] = nombre
    return d


def mea(m, nombre=None):
    d = {"field": {"Measure": {"Expression": {"SourceRef": {"Entity": "_Medidas"}}, "Property": m}},
         "queryRef": f"_Medidas.{m}", "nativeQueryRef": m}
    if nombre:
        d["displayName"] = nombre
    return d


def agg(t, c, alias):
    return {"field": {"Aggregation": {"Expression": {"Column": {"Expression": {"SourceRef": {"Entity": t}},
                                                                  "Property": c}}, "Function": 0}},
            "queryRef": f"Sum({t}.{c})", "nativeQueryRef": alias}


def fld(p):
    return p["field"]


def flt(name, t, c, values, kind="int"):
    vals = [[{"Literal": {"Value": (f"{v}L" if kind == "int" else "'" + v + "'")}}] for v in values]
    return {"name": name, "field": {"Column": {"Expression": {"SourceRef": {"Entity": t}}, "Property": c}},
            "type": "Categorical",
            "filter": {"Version": 2, "From": [{"Name": "x", "Entity": t, "Type": 0}],
                       "Where": [{"Condition": {"In": {"Expressions": [
                           {"Column": {"Expression": {"SourceRef": {"Source": "x"}}, "Property": c}}],
                           "Values": vals}}}]}}


def title(text):
    return {"title": [{"properties": {"show": lit("true"), "text": lit("'" + text.replace("'", "''") + "'")}}]}


pages = []


def page(pid, name, filters=None):
    p = {"id": pid, "name": name, "filters": filters or [], "visuals": []}
    pages.append(p)
    return p


def add(p, vid, x, y, wd, ht, visual, filters=None):
    v = {"$schema": VC, "name": vid, "position": {"x": x, "y": y, "z": len(p["visuals"]) * 1000,
                                                   "height": ht, "width": wd, "tabOrder": len(p["visuals"]) * 1000},
         "visual": visual}
    if filters:
        v["filterConfig"] = {"filters": filters}
    p["visuals"].append(v)


def es_importe(proj):
    f = proj["field"]
    if "Measure" in f:
        return fmt.get(f["Measure"]["Property"]) == MEUR or f["Measure"]["Property"] in ("MRR sin gastar", "Importe del paso")
    return "Aggregation" in f


MILLONES = {"labelDisplayUnits": lit("1000000D"), "labelPrecision": lit("0L")}


def chart(vtype, roles, ttl, sort=None, objects=None, etiquetas=False, colores=None):
    """colores: {medida: '#hex'} fija el color de cada serie (el color sigue a la entidad, no a su posición)."""
    v = {"visualType": vtype, "query": {"queryState": {r: {"projections": ps} for r, ps in roles.items()}},
         "visualContainerObjects": title(ttl), "drillFilterOtherVisuals": True}
    if sort:
        v["query"]["sortDefinition"] = {"sort": [{"field": fld(s[0]), "direction": s[1]} for s in sort],
                                        "isDefaultSort": False}
    objects = dict(objects or {})
    importe = any(es_importe(p) for ps in roles.values() for p in ps)
    if vtype in ("tableEx", "pivotTable"):
        cf = [{"properties": dict(MILLONES), "selector": {"metadata": p["queryRef"]}}
              for ps in roles.values() for p in ps if es_importe(p)]
        if cf:
            objects["columnFormatting"] = cf
    if vtype == "card" and importe:
        objects["labels"] = [{"properties": dict(MILLONES)}]
    if vtype in ("clusteredBarChart", "barChart", "columnChart", "clusteredColumnChart", "lineChart", "waterfallChart") \
            and importe:
        objects["valueAxis"] = [{"properties": {"labelDisplayUnits": lit("1000000D")}}]
    if etiquetas and vtype in ("clusteredBarChart", "barChart", "columnChart", "clusteredColumnChart"):
        props = {"show": lit("true"), "fontSize": lit("10D"), "color": solid(INK)}
        if importe:
            props.update(MILLONES)
        objects["labels"] = [{"properties": props}]
    if colores:
        objects["dataPoint"] = [{"properties": {"fill": solid(c)}, "selector": {"metadata": f"_Medidas.{m}"}}
                                for m, c in colores.items()]
    if objects:
        v["objects"] = objects
    return v


# ---- contenedores de texto: banda, franja de filtros y paneles
def cont_texto(fondo, borde, izq, arr, der, aba):
    c = {"background": [{"properties": {"show": lit("true" if fondo else "false"), "color": solid(fondo or BLANCO),
                                        "transparency": lit("0D")}}],
         "border": [{"properties": {"show": lit("true" if borde else "false"), "color": solid(borde or LINEA),
                                    "radius": lit("4D"), "width": lit("1D")}}],
         "padding": [{"properties": {"left": lit(f"{izq}D"), "top": lit(f"{arr}D"), "right": lit(f"{der}D"),
                                     "bottom": lit(f"{aba}D")}}]}
    return c


def textbox(paras, cont=None):
    ps = []
    for item in paras:
        text, size, bold = item[:3]
        color = item[3] if len(item) > 3 else INK
        style = {"fontSize": f"{size}pt", "fontFamily": "Segoe UI", "color": color}
        if bold:
            style["fontWeight"] = "bold"
        ps.append({"textRuns": [{"value": text, "textStyle": style}]})
    v = {"visualType": "textbox", "objects": {"general": [{"properties": {"paragraphs": ps}}]},
         "drillFilterOtherVisuals": True}
    if cont:
        v["visualContainerObjects"] = cont
    return v


def panel_texto(paras):
    return textbox(paras, cont_texto(BLANCO, LINEA, 24, 20, 24, 20))


AVISO = "Análisis de la ejecución presupuestaria con datos públicos; no es una auditoría. Una diferencia no es una irregularidad."


def navegador():
    return {"visualType": "pageNavigator",
            "visualContainerObjects": {"stylePreset": [{"properties": {"name": lit("'Tab'")}}]},
            "drillFilterOtherVisuals": True}


def chrome(p, key, band_id, titulo, extra=None, ancho_texto=1860):
    """Banda de título con el navegador de páginas y, debajo, la franja con la explicación de la página.
    ancho_texto: ancho que queda para el texto de la franja (el resto lo ocupan los selectores)."""
    add(p, band_id, 0, 0, 1920, BANDA_H,
        textbox([(titulo, 22, True, BLANCO), (AVISO, 11, False, "#B9C6DA")], cont_texto(NAVY, None, 30, 10, 30, 0)))
    add(p, gid(key + "nav"), 24, 66, 1872, 40, navegador())
    if extra:
        add(p, gid(key + "strip"), 30, 124, 1860, 60,
            textbox([(extra, 12, False, INK2)], cont_texto(BLANCO, LINEA, 16, 9, 1860 - ancho_texto + 16, 6)))


MIN = col("dim_ministerio", "ministerio_corto")
ENT = col("dim_grupo", "ministerio_entonces")
ANIO = col("dim_anio", "anio")


def card(m, ttl, texto=False):
    """Tarjeta con el valor grande; si el valor es un texto (no un número), con letra más pequeña."""
    v = chart("card", {"Values": [mea(m)]}, ttl)
    v.setdefault("objects", {})["categoryLabels"] = [{"properties": {"show": lit("false")}}]
    if texto:
        v["objects"]["labels"] = [{"properties": {"fontSize": lit("16D")}}]
    return v


def selector(entity, column, default_literal, ttl):
    return {"visualType": "slicer",
        "query": {"queryState": {"Values": {"projections": [col(entity, column)]}}},
        "objects": {"data": [{"properties": {"mode": lit("'Dropdown'")}}],
                    "selection": [{"properties": {"singleSelect": lit("true")}}],
                    "header": [{"properties": {"show": lit("false")}}],
                    "items": [{"properties": {"textSize": lit("12D")}}],
                    "general": [{"properties": {"filter": {"filter": {
                        "Version": 2, "From": [{"Name": "d", "Entity": entity, "Type": 0}],
                        "Where": [{"Condition": {"In": {"Expressions": [
                            {"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": column}}],
                            "Values": [[{"Literal": {"Value": default_literal}}]]}}}]}}}}]},
        "visualContainerObjects": {"title": [{"properties": {"show": lit("true"), "text": lit("'" + ttl + "'"),
                                                              "fontSize": lit("11D"), "bold": lit("false"),
                                                              "fontColor": solid(INK2)}}]},
        "drillFilterOtherVisuals": True}


def filtro_euros(p, key, x, wd=270):
    add(p, gid(key), x, 128, wd, 54, selector("Euros", "euros", "'Corrientes'", "Euros"))


# 1. Los 22 ministerios
p = page("d4f103d2e87081231347", "1. Los 22")
chrome(p, "pg1", "dcfae3178753c191d214", "Los 22 ministerios",
       "Elige el año a la derecha (por defecto 2024). Cada fila es un ministerio tal como existía ese año; la columna «Incluye» dice a qué ministerios actuales equivale. 2025 es provisional y sin organismos.",
       ancho_texto=1284)
filtro_euros(p, "p1eu", 1330)
add(p, gid("p1sl"), 1620, 128, 270, 54, selector("dim_anio", "anio", "2024L", "Año"))
for i, (m, t) in enumerate([("Iniciales", "Créditos iniciales"), ("Definitivos", "Créditos definitivos"),
                            ("Obligaciones", "Obligaciones reconocidas"), ("Gasto agregado", "Gasto agregado (Estado + organismos)")]):
    add(p, gid(f"p1c{i}"), 30 + i * 470, TOP, 450, 120, card(m, t))
add(p, gid("p1mat"), 30, 340, 1160, LIMITE - 340, chart("pivotTable",
    {"Rows": [ENT], "Values": [mea("Incluye"), mea("Iniciales"), mea("Definitivos"), mea("Obligaciones"),
                               mea("% ejecución"), mea("Gasto agregado"), mea("MRR peso en las obligaciones")]},
    "Presupuesto y gasto por ministerio (los de ese año)", sort=[(mea("Gasto agregado"), "Descending")]))
add(p, gid("p1bar"), 1210, 340, 680, LIMITE - 340, chart("clusteredBarChart",
    {"Category": [ENT], "Y": [mea("Gasto agregado")]}, "Gasto agregado sin doble cómputo",
    sort=[(mea("Gasto agregado"), "Descending")], etiquetas=True))

# 2. Ficha de un ministerio
p = page(gid("pg2"), "2. Ficha")
p["height"] = 1580
p["display"] = "FitToWidth"
chrome(p, "pg2", gid("p2h"), "Ficha de un ministerio",
       "Elige el ministerio a la derecha (en blanco, todos). Si un año no existía como hoy, se ve el ministerio de entonces: la tabla del final explica cuál. Cascada y organismos: 2024. Contratación: perímetro actual.",
       ancho_texto=984)
filtro_euros(p, "p2eu", 1030, 280)
add(p, gid("p2sl"), 1330, 128, 560, 54, selector("dim_ministerio", "ministerio_corto", "'Defensa'", "Ministerio"))
add(p, gid("p2info"), 30, TOP, 400, 120, card("Nivel de contratación", "Nivel de la comparación de contratación", texto=True))
add(p, gid("p2perf"), 450, TOP, 400, 120, card("Perfil de gasto", "Perfil de gasto (2024)", texto=True))
add(p, gid("p2est"), 870, TOP, 300, 120, card("Estudio: diferencia (pp)", "Nov-dic frente al resto de la AGE (pp)"))
add(p, gid("p2mrr1"), 1190, TOP, 340, 120, card("MRR obligaciones", "Mecanismo: obligaciones 2021-2025"))
add(p, gid("p2mrr2"), 1550, TOP, 340, 120, card("MRR % ejecutado", "Mecanismo: % ejecutado"))
add(p, gid("p2wf"), 30, 340, 920, 380, chart("waterfallChart",
    {"Category": [col("Pasos", "paso")], "Y": [mea("Importe del paso")]},
    "Del presupuesto inicial a las obligaciones (total = obligaciones)",
    sort=[(col("Pasos", "paso"), "Ascending")]),
    filters=[flt("f2wf", "dim_anio", "anio", [2024])])
add(p, gid("p2lin"), 970, 340, 920, 380, chart("lineChart",
    {"Category": [ANIO], "Y": [mea("Obligaciones"), mea("Definitivos")]},
    "Créditos definitivos y obligaciones por año (cada año, el ministerio de entonces)"))
add(p, gid("p2cap"), 30, 740, 620, 360, chart("columnChart",
    {"Category": [ANIO], "Y": [mea("Obligaciones por capítulo")], "Series": [col("dim_capitulo", "capitulo_nombre")]},
    "Obligaciones del Estado por capítulo"),
    filters=[flt("f2amb", "fact_capitulo", "ambito", ["Estado"], "str")])
add(p, gid("p2org"), 670, 740, 600, 360, chart("tableEx",
    {"Values": [col("fact_ingresos_organismos", "organismo"), col("fact_ingresos_organismos", "origen_grupo"),
                mea("Organismos: derechos reconocidos")]},
    "Ingresos de sus organismos (derechos reconocidos, €)"),
    filters=[flt("f2org", "dim_anio", "anio", [2024])])
add(p, gid("p2con"), 1290, 740, 600, 360, chart("lineChart",
    {"Category": [ANIO], "Y": [mea("Cuota nov-dic"), mea("Cuota nov-dic AGE sin él")]},
    "Contratación en noviembre-diciembre frente al resto de la AGE (perímetro actual)"),
    filters=[flt("f2con", "dim_anio", "contratacion", ["completo"], "str")])
add(p, gid("p2eq"), 30, 1120, 1860, 420, chart("tableEx",
    {"Values": [col("dim_grupo", "anio"), col("dim_grupo", "ministerio_entonces"), col("dim_grupo", "relacion")]},
    "Qué ministerio se ve cada año",
    sort=[(col("dim_grupo", "anio"), "Ascending")],
    objects={"total": [{"properties": {"totals": lit("false")}}],
             "values": [{"properties": {"wordWrap": lit("true"), "fontSize": lit("11D")}}],
             "columnHeaders": [{"properties": {"fontSize": lit("11D")}}]}))

# 3. Calendario de prórroga (nueva)
p = page(gid("pgcal"), "3. Calendario")
chrome(p, "pgcal", gid("pgcalh"), "Calendario de prórroga",
       "Cuántos días de cada año se vivió con presupuesto propio o prorrogado (art. 134.4 de la Constitución) y cuántos con el Gobierno en funciones. Se cuentan los días con ambos extremos incluidos; 2026 llega hasta el 10/11/2026. Fechas y normas: BOE, en datos/calendario_fuentes.csv (script 17).")
for i, (m, t) in enumerate([("Días con presupuesto prorrogado", "Días con presupuesto prorrogado (2017 a 10/11/2026)"),
                            ("% del tiempo con presupuesto prorrogado", "Parte del periodo con presupuesto prorrogado"),
                            ("Días con el Gobierno en funciones", "Días con el Gobierno en funciones"),
                            ("Días en funciones y con presupuesto prorrogado", "Días en funciones y con presupuesto prorrogado a la vez")]):
    add(p, gid(f"pgcalc{i}"), 30 + i * 470, TOP, 450, 120, card(m, t))
add(p, gid("pgcal1"), 30, 340, 930, 380, chart("columnChart",
    {"Category": [ANIO], "Y": [mea("Días con presupuesto propio"), mea("Días con presupuesto prorrogado")]},
    "Días de cada año según el presupuesto que rige",
    colores={"Días con presupuesto propio": PALETA[0], "Días con presupuesto prorrogado": PALETA[1]}))
add(p, gid("pgcal2"), 980, 340, 910, 380, chart("clusteredColumnChart",
    {"Category": [ANIO], "Y": [mea("Días con el Gobierno en funciones"), mea("Días en funciones y con presupuesto prorrogado")]},
    "Días con el Gobierno en funciones, por año", etiquetas=True,
    colores={"Días con el Gobierno en funciones": PALETA[2], "Días en funciones y con presupuesto prorrogado": PALETA[1]}))
add(p, gid("pgcal3"), 30, 740, 930, LIMITE - 740, chart("tableEx",
    {"Values": [ANIO, col("dim_anio", "situacion_presupuesto", "Presupuesto que rige"),
                mea("Días con presupuesto prorrogado", "Días prorrogado"),
                mea("% del tiempo con presupuesto prorrogado", "% del año prorrogado"),
                mea("Días con el Gobierno en funciones", "Días en funciones")]},
    "Año a año", sort=[(ANIO, "Ascending")],
    objects={"values": [{"properties": {"wordWrap": lit("true"), "fontSize": lit("11D")}}],
             "columnHeaders": [{"properties": {"fontSize": lit("11D")}}]}))
add(p, gid("pgcal4"), 980, 740, 910, LIMITE - 740, chart("tableEx",
    {"Values": [col("dim_gobierno", "presidente_real_decreto", "Nombramiento"), col("dim_gobierno", "nombrado_el", "Desde"),
                col("dim_gobierno", "hasta", "Hasta"), col("dim_gobierno", "dias_mandato", "Días de mandato"),
                col("dim_gobierno", "dias_en_funciones", "En funciones"),
                col("dim_gobierno", "dias_presupuesto_prorrogado", "Con presupuesto prorrogado"),
                col("dim_gobierno", "leyes_pge_publicadas_en_el_mandato", "Leyes de presupuestos publicadas")]},
    "Los cuatro Gobiernos del periodo", sort=[(col("dim_gobierno", "presidente_real_decreto"), "Ascending")],
    objects={"total": [{"properties": {"totals": lit("false")}}],
             "values": [{"properties": {"wordWrap": lit("true"), "fontSize": lit("11D")}}],
             "columnHeaders": [{"properties": {"fontSize": lit("11D")}}]}))

# 4. Presupuesto prorrogado
p = page(gid("pg3"), "4. Prorrogado", [flt("f3anio", "dim_anio", "anio", [2024, 2025])])
chrome(p, "pg3", gid("p3h"), "Presupuesto prorrogado: 2024 y 2025",
       "Los dos años se ejecutan con el presupuesto de 2023 prorrogado. 2025 sale de la mensual de diciembre (provisional).",
       ancho_texto=1530)
filtro_euros(p, "p3heu", 1580, 310)
add(p, gid("p3bar"), 30, TOP, 930, LIMITE - TOP, chart("clusteredBarChart",
    {"Category": [ENT], "Series": [ANIO], "Y": [mea("% obligaciones sobre iniciales")]},
    "Obligaciones sobre créditos iniciales", sort=[(mea("% obligaciones sobre iniciales"), "Descending")]))
add(p, gid("p3mod"), 980, TOP, 910, LIMITE - TOP, chart("barChart",
    {"Category": [ENT], "Y": [mea("Créditos extraordinarios y suplementos"), mea("Ampliaciones"),
                              mea("Transferencias de crédito"), mea("Remanentes"), mea("Generaciones"),
                              mea("Bajas y otras")]},
    "Modificaciones de crédito en 2025, por tipo"),
    filters=[flt("f3mod", "dim_anio", "anio", [2025])])

# 5. Lo que no se gasta
p = page(gid("pg4"), "5. Sin gastar", [flt("f4anio", "dim_anio", "anio", list(range(2017, 2025)))])
chrome(p, "pg4", gid("p4h"), "Lo que no se gasta",
       "Créditos definitivos menos obligaciones, 2017-2024 (la mensual de 2025 no da capítulos). El capítulo 8 son activos financieros.",
       ancho_texto=1530)
filtro_euros(p, "p4heu", 1580, 310)
add(p, gid("p4cap"), 30, TOP, 1180, 440, chart("columnChart",
    {"Category": [ANIO], "Y": [mea("Sin gastar por capítulo")], "Series": [col("dim_capitulo", "capitulo_nombre")]},
    "Crédito sin gastar del Estado, por capítulo"),
    filters=[flt("f4amb", "fact_capitulo", "ambito", ["Estado"], "str")])
add(p, gid("p4mrr"), 30, 660, 1180, LIMITE - 660, chart("lineChart",
    {"Category": [ANIO], "Y": [mea("MRR sin gastar"), mea("Sin gastar")]},
    "Sin gastar: total del Estado y parte del Mecanismo de Recuperación"))
add(p, gid("p4rk"), 1230, TOP, 660, LIMITE - TOP, chart("clusteredBarChart",
    {"Category": [ENT], "Y": [mea("Sin gastar")]}, "Sin gastar por ministerio de cada año (suma de los años filtrados)",
    sort=[(mea("Sin gastar"), "Descending")], etiquetas=True))

# 6. Mecanismo de Recuperación
p = page(gid("pg5"), "6. Mecanismo", [flt("f5anio", "dim_anio", "anio", list(range(2021, 2026)))])
chrome(p, "pg5", gid("p5h"), "Mecanismo de Recuperación y Resiliencia, 2021-2025",
       "Servicio 50 de cada sección. 2025, provisional. Haz clic en un ministerio para filtrar la tabla de programas.",
       ancho_texto=1530)
filtro_euros(p, "p5heu", 1580, 310)
add(p, gid("p5ob"), 30, TOP, 600, LIMITE - TOP, chart("clusteredBarChart",
    {"Category": [ENT], "Y": [mea("MRR obligaciones")]}, "Obligaciones del Mecanismo",
    sort=[(mea("MRR obligaciones"), "Descending")], etiquetas=True))
add(p, gid("p5ej"), 650, TOP, 560, LIMITE - TOP, chart("clusteredBarChart",
    {"Category": [ENT], "Y": [mea("MRR % ejecutado"), mea("MRR peso en las obligaciones")]},
    "% ejecutado y peso en las obligaciones del ministerio",
    sort=[(mea("MRR % ejecutado"), "Descending")]))
add(p, gid("p5tb"), 1230, TOP, 660, LIMITE - TOP, chart("tableEx",
    {"Values": [col("fact_mrr_programa", "programa"), col("fact_mrr_programa", "programa_nombre"),
                mea("MRR programa: definitivos"), mea("MRR programa: obligaciones")]},
    "Programas del Mecanismo"))

# 7. Contratación al cierre
p = page(gid("pg6"), "7. Cierre", [flt("f6c", "dim_anio", "contratacion", ["completo"], "str")])
chrome(p, "pg6", gid("p6h"), "Contratación al cierre del ejercicio (2017-2025)",
       "Diferencia en puntos entre la cuota de noviembre-diciembre del ministerio y la del resto de la AGE. Solo se concluye en el nivel A, o en el B si coinciden dos indicadores. El nivel C va aparte y sin orden.")
add(p, gid("p6dif"), 30, TOP, 900, 560, chart("clusteredBarChart",
    {"Category": [MIN], "Y": [mea("Diferencia nov-dic (pp)")]},
    "Diferencia nov-dic (pp), niveles A y B", sort=[(mea("Diferencia nov-dic (pp)"), "Descending")], etiquetas=True),
    filters=[flt("f6ab", "dim_ministerio", "nivel_contratacion", ["A", "B"], "str")])
add(p, gid("p6ic"), 950, TOP, 940, 560, chart("tableEx",
    {"Values": [MIN, col("dim_ministerio", "nivel_contratacion"), mea("Diferencia nov-dic (pp)"),
                mea("Estudio: diferencia (pp)"), mea("Estudio: IC 95 % inferior"), mea("Estudio: IC 95 % superior")]},
    "Contraste con el estudio de viabilidad (intervalo de confianza del 95 %)",
    objects={"total": [{"properties": {"totals": lit("false")}}]}),
    filters=[flt("f6ab2", "dim_ministerio", "nivel_contratacion", ["A", "B"], "str")])
add(p, gid("p6c"), 30, 780, 600, LIMITE - 780, chart("tableEx",
    {"Values": [MIN, mea("Adjudicaciones"), mea("Importe ordinario")]},
    "Nivel C (no concluyente): sin diferencia, en orden alfabético", sort=[(MIN, "Ascending")]),
    filters=[flt("f6c2", "dim_ministerio", "nivel_contratacion", ["C"], "str")])
add(p, gid("p6mes"), 650, 780, 1240, LIMITE - 780, chart("clusteredColumnChart",
    {"Category": [col("fact_contratacion_mes", "mes")], "Y": [mea("Importe ordinario")]},
    "Importe ordinario adjudicado por mes (licitaciones)"))

# 8. Valor del dinero
p = page(gid("pg8"), "8. Valor del dinero")
chrome(p, "pg8", gid("p8h"), "Valor del dinero: euros corrientes y constantes de 2025",
       "Las mismas obligaciones medidas de cuatro formas. Elige un ministerio a la derecha (en blanco, todos).",
       ancho_texto=1304)
add(p, gid("p8sl"), 1350, 128, 540, 54, selector("dim_ministerio", "ministerio_corto", "'Defensa'", "Ministerio"))
add(p, gid("p8ob"), 30, TOP, 1180, 500, chart("lineChart",
    {"Category": [ANIO], "Y": [mea("Obligaciones: euros corrientes"), mea("Obligaciones: € de 2025 (IPC)"),
                               mea("Obligaciones: € de 2025 (deflactor del PIB)"),
                               mea("Obligaciones: € de 2025 (deflactor del consumo público)")]},
    "Obligaciones reconocidas por año, en euros corrientes y en euros de 2025"),
    filters=[flt("f8ob", "dim_anio", "anio", list(range(2017, 2026)))])
add(p, gid("p8fac"), 1230, TOP, 660, 500, chart("lineChart",
    {"Category": [ANIO], "Y": [mea("Factor IPC"), mea("Factor deflactor del PIB"), mea("Factor deflactor del consumo público")]},
    "Por cuánto se multiplica un euro de cada año para pasarlo a euros de 2025"),
    filters=[flt("f8fa", "dim_anio", "anio", list(range(2017, 2026)))])
add(p, gid("p8tb"), 30, 720, 900, LIMITE - 720, chart("tableEx",
    {"Values": [ANIO, mea("Factor IPC"), mea("Factor deflactor del PIB"), mea("Factor deflactor del consumo público")]},
    "Factores (100 € del año = factor × 100 € de 2025)", sort=[(ANIO, "Ascending")],
    objects={"total": [{"properties": {"totals": lit("false")}}]}),
    filters=[flt("f8tb", "dim_anio", "anio", list(range(2017, 2026)))])
add(p, gid("p8tx"), 950, 720, 940, LIMITE - 720, panel_texto([
    ("Qué mide cada uno", 16, True, NAVY),
    ("IPC: lo que vale hoy ese dinero para un ciudadano (precios de consumo de los hogares). Es el más conocido.", 12, False),
    ("Deflactor del PIB: los precios de toda la economía.", 12, False),
    ("Deflactor del consumo público: los precios de lo que compran las Administraciones (sobre todo sueldos públicos, bienes y servicios). Es el que mejor dice si el gasto público crece en términos reales.", 12, False),
    ("Fuentes: INE, IPC (tabla 70172 y tasas medias de 2024 y 2025) y Contabilidad Nacional Anual, Revisión Estadística 2024 (pib95_25.xlsx, 18/09/2026). Script 14.", 11, False, INK2),
]))

# 9. Catástrofes (apartado 7)
def lista_anios(p, key, x, wd=270, defecto=None):
    add(p, gid(key), x, 128, wd, 54, selector("dim_anio", "anio", f"{defecto}L", "Año"))


CAT = "fact_catastrofe"
p = page(gid("pgcat"), "9. Catástrofes")
chrome(p, "pgcat", gid("pgcath"), "Respuesta a las catástrofes, 2020-2025",
       "Líneas del Estado que una regla escrita liga a cinco sucesos: covid-19, crisis de la energía, DANA de 2024, La Palma y Filomena. Es una cota inferior, solo del Estado (apartado 7). Euros corrientes; 2025, provisional.")
for i, (m, t) in enumerate([("Catástrofes: definitivos", "Créditos definitivos"), ("Catástrofes: obligaciones", "Obligaciones reconocidas"),
                            ("Catástrofes: % reconocido", "Parte reconocida")]):
    add(p, gid(f"pgcatc{i}"), 30 + i * 315, TOP, 300, 110, card(m, t))
add(p, gid("pgcatan"), 30, 330, 930, 340, chart("columnChart",
    {"Category": [ANIO], "Series": [col(CAT, "suceso_nombre")], "Y": [mea("Catástrofes: obligaciones")]},
    "Obligaciones reconocidas por año y suceso"))
add(p, gid("pgcatde"), 30, 690, 930, LIMITE - 690, chart("pivotTable",
    {"Rows": [col("fact_catastrofe_destino", "destino")], "Columns": [col("fact_catastrofe_destino", "suceso_nombre")],
     "Values": [mea("Catástrofes por destino: obligaciones")]},
    "A quién va: obligaciones por tipo de destino y suceso (sumados los años)"))
add(p, gid("pgcatmi"), 980, TOP, 910, 460, chart("barChart",
    {"Category": [col(CAT, "ministerio")], "Series": [col(CAT, "suceso_nombre")], "Y": [mea("Catástrofes: obligaciones")]},
    "En qué ministerio se abre el crédito: obligaciones por sección", sort=[(mea("Catástrofes: obligaciones"), "Descending")]))
add(p, gid("pgcatme"), 980, 680, 910, LIMITE - 680, chart("barChart",
    {"Category": [col(CAT, "medida")], "Y": [mea("Catástrofes: obligaciones")]},
    "Por medida (solo covid y crisis de la energía tienen desglose)", sort=[(mea("Catástrofes: obligaciones"), "Descending")], etiquetas=True))

# 10. Crédito nuevo y remanentes (apartados 8 y 11)
CN = "fact_credito_nuevo"
p = page(gid("pgcre"), "10. Crédito nuevo")
chrome(p, "pgcre", gid("pgcreh"), "Crédito del presupuesto y crédito creado durante el año; remanentes",
       "Arriba, 2020-2025: líneas del presupuesto (sin cambio, ampliadas, reducidas) frente a líneas nuevas del anexo II (apartado 8). Abajo, 2017-2024: crédito que no se reconoce y lo que se incorpora al año siguiente (apartado 11). Euros corrientes.")
add(p, gid("pgcrecol"), 30, TOP, 930, 420, chart("columnChart",
    {"Category": [ANIO], "Series": [col(CN, "grupo")], "Y": [mea("Crédito nuevo: definitivos")]},
    "Crédito definitivo por grupo de líneas"))
add(p, gid("pgcrelin"), 980, TOP, 910, 420, chart("lineChart",
    {"Category": [ANIO], "Series": [col(CN, "grupo")], "Y": [mea("Crédito nuevo: % reconocido sin capítulo 8")]},
    "Parte reconocida por grupo, sin el Mecanismo de Recuperación y sin capítulo 8"),
    filters=[flt("fcremec", CN, "mecanismo", ["Resto del presupuesto"], "str")])
add(p, gid("pgrem"), 30, 640, 930, LIMITE - 640, chart("clusteredColumnChart",
    {"Category": [ANIO], "Y": [mea("Remanentes: sin reconocer"), mea("Remanentes: incorporado al año siguiente")]},
    "Los 22 ministerios: crédito sin reconocer y crédito incorporado al año siguiente"),
    filters=[flt("fremanio", "dim_anio", "anio", list(range(2017, 2025)))])
add(p, gid("pgremt"), 980, 640, 910, LIMITE - 640, chart("tableEx",
    {"Values": [col("fact_ejecucion", "ministerio"), mea("Remanentes: sin reconocer"), mea("Remanentes: % sin reconocer"),
                mea("Remanentes: incorporado al año siguiente"), mea("Remanentes: sin incorporar")]},
    "Por ministerio en 2024: crédito sin reconocer y qué se incorpora en 2025", sort=[(mea("Remanentes: sin reconocer"), "Descending")]),
    filters=[flt("fremt", "dim_anio", "anio", [2024])])

# 11. Inicial, reconocido y pagado (apartados 11, 12 y 13)
p = page(gid("pgeje"), "11. Inicial y pagado")
chrome(p, "pgeje", gid("pgejeh"), "Del crédito inicial al reconocido y al pagado",
       "Obligaciones sobre créditos iniciales (solo años comparables, apartado 13) y obligaciones sin pagar el 31 de diciembre (apartado 12). Sin pagar no es deuda vencida. Estado, secciones ministeriales, euros corrientes. 2025, provisional.",
       ancho_texto=1560)
lista_anios(p, "pgejesl", 1620, 270, 2024)
add(p, gid("pgejea"), 30, TOP, 930, 400, chart("clusteredBarChart",
    {"Category": [col("fact_ejecucion", "ministerio")], "Y": [mea("Ejecución: % obligaciones sobre iniciales (años comparables)")]},
    "Obligaciones sobre créditos iniciales", sort=[(mea("Ejecución: % obligaciones sobre iniciales (años comparables)"), "Descending")], etiquetas=True))
add(p, gid("pgejeb"), 980, TOP, 910, 400, chart("clusteredBarChart",
    {"Category": [col("fact_ejecucion", "ministerio")], "Y": [mea("Ejecución: % pendiente de pago")]},
    "Obligaciones sin pagar al cierre, % de las obligaciones", sort=[(mea("Ejecución: % pendiente de pago"), "Descending")], etiquetas=True))
add(p, gid("pgejet"), 30, 620, 1860, LIMITE - 620, chart("tableEx",
    {"Values": [col("fact_ejecucion", "ministerio"), mea("Ejecución: créditos iniciales"),
                mea("Ejecución: créd. extraordinarios y suplementos"), mea("Ejecución: ampliaciones"),
                mea("Ejecución: transferencias de crédito"), mea("Ejecución: incorporación de remanentes"),
                mea("Ejecución: generaciones"), mea("Ejecución: bajas y otras"), mea("Ejecución: definitivos"),
                mea("Ejecución: obligaciones"), mea("Ejecución: pagos"), mea("Ejecución: pendiente de pago")]},
    "Del inicial al definitivo, por tipo de modificación, y de las obligaciones a los pagos",
    sort=[(mea("Ejecución: obligaciones"), "Descending")]))

# 12. Contratación frente a gasto y concentración (apartados 9 y 10)
p = page(gid("pgcon"), "12. Contratación y gasto")
chrome(p, "pgcon", gid("pgconh"), "Contratación frente a gasto y concentración del gasto",
       "Qué parte del gasto agregado pasa por contratos (lo adjudicado no es lo gastado y el perímetro no coincide: apartado 9) y en cuántas líneas se concentra el gasto del Estado (apartado 10). Euros corrientes; la concentración empieza en 2020.",
       ancho_texto=1560)
lista_anios(p, "pgconsl", 1620, 270, 2024)
add(p, gid("pgcon1"), 30, TOP, 930, 420, chart("hundredPercentStackedBarChart",
    {"Category": [col(CG, "ministerio")], "Y": [mea("Contratación y gasto: personal"), mea("Contratación y gasto: compras e inversiones"),
                                              mea("Contratación y gasto: préstamos y aportaciones"), mea("Contratación y gasto: transferencias y resto")]},
    "De qué se compone el gasto agregado"))
add(p, gid("pgcon2"), 980, TOP, 910, 420, chart("clusteredBarChart",
    {"Category": [col(CG, "ministerio")], "Y": [mea("Contratación y gasto: % adjudicado ordinario sobre el gasto")]},
    "Adjudicado ordinario, % del gasto agregado", sort=[(mea("Contratación y gasto: % adjudicado ordinario sobre el gasto"), "Descending")], etiquetas=True))
add(p, gid("pgcon3"), 30, 640, 930, LIMITE - 640, chart("tableEx",
    {"Values": [col(CG, "ministerio"), col(CG, "nivel_contratacion"), mea("Contratación y gasto: gasto agregado"),
                mea("Contratación y gasto: compras e inversiones"), mea("Contratación y gasto: adjudicado ordinario"),
                mea("Contratación y gasto: programas especiales"),
                mea("Contratación y gasto: % adjudicado total sobre compras e inversiones")]},
    "Gasto, compras e inversiones y lo adjudicado en la Plataforma de Contratación", sort=[(mea("Contratación y gasto: gasto agregado"), "Descending")]))
add(p, gid("pgcon4"), 980, 640, 910, LIMITE - 640, chart("tableEx",
    {"Values": [col("fact_concentracion", "ministerio"), col("fact_concentracion", "aplicaciones_con_obligaciones"),
                col("fact_concentracion", "pct_primera"), col("fact_concentracion", "pct_cinco_primeras"),
                col("fact_concentracion", "n50"), col("fact_concentracion", "n80"), col("fact_concentracion", "n95")]},
    "Concentración: líneas con obligaciones, peso de la primera y de las cinco primeras (%) y líneas hasta el 50, 80 y 95 %",
    sort=[(col("fact_concentracion", "pct_primera"), "Descending")]))

# 13. Subvenciones (apartado 16)
BD = "fact_bdns"
p = page(gid("pgbd"), "13. Subvenciones")
chrome(p, "pgbd", gid("pgbdh"), "Subvenciones y ayudas concedidas según la BDNS, 2022-2025",
       "Concesiones del Estado por fecha de concesión, sumadas por ministerio, año e instrumento; no son obligaciones del presupuesto (apartado 16). Los préstamos, las garantías y las ventajas fiscales no son gasto. Sin beneficiarios: solo agregados. Euros corrientes.")
add(p, gid("pgbd1"), 30, TOP, 930, 400, chart("columnChart",
    {"Category": [ANIO], "Series": [col("fact_bdns_instrumento", "instrumento")], "Y": [mea("BDNS por instrumento: importe")]},
    "Importe concedido por año e instrumento"))
add(p, gid("pgbd2"), 980, TOP, 910, 400, chart("columnChart",
    {"Category": [ANIO], "Y": [mea("BDNS: concesiones")]}, "Número de concesiones por año", etiquetas=True))
add(p, gid("pgbd3"), 30, 620, 930, LIMITE - 620, chart("clusteredBarChart",
    {"Category": [col(BD, "ministerio")], "Y": [mea("BDNS: subvenciones y ayudas directas")]},
    "Subvenciones y ayudas directas concedidas en 2024, por ministerio",
    sort=[(mea("BDNS: subvenciones y ayudas directas"), "Descending")], etiquetas=True),
    filters=[flt("fbd24a", "dim_anio", "anio", [2024])])
add(p, gid("pgbd4"), 980, 620, 910, LIMITE - 620, chart("tableEx",
    {"Values": [col(BD, "ministerio"), mea("BDNS: concesiones"), mea("BDNS: subvenciones y ayudas directas"),
                mea("BDNS: ayudas directas sobre los capítulos 4 y 7"), mea("BDNS: préstamos"), mea("BDNS: garantías"),
                mea("BDNS: ventajas fiscales")]},
    "Por ministerio en 2024: concesiones, ayudas directas y otros instrumentos",
    sort=[(mea("BDNS: subvenciones y ayudas directas"), "Descending")]),
    filters=[flt("fbd24b", "dim_anio", "anio", [2024])])

# 14. Calendario mensual (apartado 17)
FM = "fact_mensual"
p = page(gid("pgmes"), "14. Calendario mensual")
chrome(p, "pgmes", gid("pgmesh"), "Calendario de ejecución mes a mes, 2024 y 2025",
       "Obligaciones reconocidas acumuladas de las secciones ministeriales del Estado, según las doce ediciones de 2025 de la estadística mensual de la IGAE (apartado 17). 2024 es el comparativo publicado en 2025; 2025, provisional. Euros corrientes.")
add(p, gid("pgmes1"), 30, TOP, 930, 400, chart("lineChart",
    {"Category": [col(FM, "mes")], "Series": [ANIO], "Y": [mea("Mensual: % acumulado del año")]},
    "Los 22 ministerios: obligaciones acumuladas, % del total de diciembre"))
add(p, gid("pgmes2"), 980, TOP, 910, 400, chart("clusteredColumnChart",
    {"Category": [col(FM, "mes")], "Series": [ANIO], "Y": [mea("Mensual: obligaciones del mes")]},
    "Los 22 ministerios: obligaciones reconocidas en cada mes"))
add(p, gid("pgmes3"), 30, 620, 1860, LIMITE - 620, chart("pivotTable",
    {"Rows": [col(FM, "ministerio")], "Columns": [col(FM, "mes")], "Values": [mea("Mensual: % acumulado del año")]},
    "2025: obligaciones acumuladas de cada ministerio hasta cada mes, % de su total del año"),
    filters=[flt("fmes25", "dim_anio", "anio", [2025])])

# 15. Método y registro
p = page(gid("pg7"), "15. Método y registro")
p["height"] = 1240
chrome(p, "pg7", gid("p7h"), "Método y registro")
add(p, gid("p7t"), 30, 128, 1860, 1220 - 128, panel_texto([
    ("Perímetro", 20, True, NAVY),
    ("Estado: liquidación de la IGAE 2017-2024 y mensual de diciembre de 2025 (provisional). Organismos: liquidación de organismos 2017-2024. Contratación: línea base de la Plataforma de Contratación del Sector Público, solo la Administración General del Estado; sociedades, fundaciones y consorcios quedan fuera.", 15, False),
    ("Doble cómputo", 20, True, NAVY),
    ("El gasto agregado suma Estado y organismos y resta todas las transferencias del Estado a los organismos del ministerio, vengan de la sección que vengan. El gasto se cuenta en el ministerio que paga, así que la suma de los 22 no cuenta nada dos veces.", 15, False),
    ("Años comparables", 20, True, NAVY),
    ("Cada año se muestran los ministerios que existían entonces. Al elegir un ministerio actual en un año en que no existía, o en que compartía ministerio con otros, se ve el ministerio de entonces completo (tabla dim_grupo, script 13 y REGISTRO B15). Cuando no existía, se toma el ministerio que tenía el grueso de sus competencias; la Función Pública de Transformación Digital queda en su ministerio de cada año. La contratación usa siempre el perímetro actual de los órganos. 2024 y 2025 son los dos años con los 22 ministerios actuales y el mismo presupuesto prorrogado. 2017-2019 no tienen detalle por aplicación.", 15, False),
    ("Presupuesto prorrogado y Gobierno en funciones", 20, True, NAVY),
    ("La página 3 cuenta los días de cada año con presupuesto prorrogado y con el Gobierno en funciones, con ambos extremos incluidos y, en 2026, hasta el 10/11/2026. Las fechas salen de las normas del BOE que recoge datos/calendario_fuentes.csv (script 17). En 2017 el presupuesto estuvo prorrogado hasta el 28/06 y en 2018 hasta el 04/07; esos dos años aparecen como «aprobado» en el resto del informe. En 2019 y 2020 estuvo prorrogado todo el año, y también en 2024, 2025 y 2026. Es un calendario: no mide cuánto gasto cambia por estar en prórroga o en funciones.", 15, False),
    ("Euros corrientes y constantes", 20, True, NAVY),
    ("Con el selector «Euros» los importes del presupuesto y de los organismos se pasan a euros de 2025 con uno de tres índices del INE: el IPC (100 M€ de 2017 = 124,7 M€ de 2025), el deflactor del PIB (125,7) o el deflactor del consumo final de las Administraciones Públicas (120,9). La página 8 los compara. Los porcentajes no cambian dentro de un mismo año. La contratación se queda en euros corrientes, porque se compara por cuotas. Script 14 y REGISTRO B16.", 15, False),
    ("Páginas 9 a 14", 20, True, NAVY),
    ("Recogen los apartados 7 a 13, 16 y 17 de preguntas.md con tablas propias (script 30). Van siempre en euros corrientes, no pasan por el selector «Euros» y usan el ministerio actual, como el texto de esos apartados. Las cifras salen de los CSV de datos/ y se comprueban en datos/controles_powerbi_apartados.csv.", 15, False),
    ("Avisos", 20, True, NAVY),
    ("2025 es provisional. 2026 está incompleto en contratación (hasta el 23/10). Una diferencia no es una irregularidad. Las anomalías de la fuente y todos nuestros ajustes están anotados en REGISTRO.md; las fuentes, en datos/LEEME.md.", 15, False),
]))

# ---------------------------------------------------------------- tema propio
def sc(c):
    return {"solid": {"color": c}}


def estilo_tabla(extra=None):
    cab = {"fontSize": 11, "fontColor": sc(NAVY), "backColor": sc("#E8EDF4"), "bold": True}
    val = {"fontSize": 11, "fontColor": sc(INK), "backColorPrimary": sc(BLANCO), "backColorSecondary": sc(BLANCO)}
    tot = {"fontSize": 11, "fontColor": sc(NAVY), "backColor": sc("#F4F6F9"), "bold": True}
    d = {"columnHeaders": [cab], "values": [val], "total": [tot],
         "grid": [{"rowPadding": 4, "gridVertical": False, "gridHorizontal": True, "gridHorizontalColor": sc("#E3E8EE"),
                   "gridHorizontalWeight": 1, "outlineColor": sc(LINEA)}]}
    d.update(extra or {})
    return d


def estilo_pivote():
    d = estilo_tabla()
    d["rowHeaders"] = [{"fontSize": 11, "fontColor": sc(INK), "backColor": sc(BLANCO)}]
    for k in ("rowTotal", "columnTotal", "subTotals"):
        d[k] = [{"fontSize": 11, "fontColor": sc(NAVY), "backColor": sc("#F4F6F9"), "bold": True}]
    return d


def estilo_navegador(pestana):
    luz, claro = "#C5D0E0", "#FFFFFF"
    d = {"background": [{"show": False}], "visualHeader": [{"show": False}], "title": [{"show": False}],
         "padding": [{"left": 0, "top": 0, "right": 0, "bottom": 0}], "border": [{"show": False}],
         "dropShadow": [{"show": False}],
         "text": [{"$id": "default", "fontSize": 9.5, "fontColor": sc(luz), "leftMargin": 3, "rightMargin": 3,
                   "topMargin": 6, "bottomMargin": 8},
                  {"$id": "hover", "fontColor": sc(claro)}, {"$id": "press", "fontColor": sc(claro)},
                  {"$id": "selected", "fontSize": 9.5, "fontColor": sc(claro), "bold": True, "leftMargin": 3,
                   "rightMargin": 3, "topMargin": 6, "bottomMargin": 8}],
         "shape": [{"$id": "default", "tileShape": "rectangle", "roundEdge": 4}],
         "layout": [{"orientation": 2, "cellPadding": 4}]}
    if pestana:
        d["outline"] = [{"show": False}]
        d["fill"] = [{"show": True}, {"$id": "default", "transparency": 100},
                     {"$id": "hover", "fillColor": sc("#1F3354"), "transparency": 0},
                     {"$id": "press", "fillColor": sc("#2A426B"), "transparency": 0},
                     {"$id": "selected", "transparency": 100}]
        d["accentBar"] = [{"show": False},
                          {"$id": "hover", "show": True, "position": "Bottom", "weight": 2, "color": sc("#5A6F91")},
                          {"$id": "press", "show": True, "position": "Bottom", "weight": 2, "color": sc("#8FA3C2")},
                          {"$id": "selected", "show": True, "position": "Bottom", "weight": 3, "color": sc(ACENTO)}]
    else:
        d["outline"] = [{"$id": k, "transparency": 100} for k in ("default", "hover", "press", "selected")]
        d["fill"] = [{"$id": "default", "transparency": 100},
                     {"$id": "hover", "fillColor": sc("#1F3354"), "transparency": 0},
                     {"$id": "press", "fillColor": sc("#2A426B"), "transparency": 0},
                     {"$id": "selected", "fillColor": sc("#2A426B"), "transparency": 0}]
    return {"*": d} if not pestana else d


TEMA = {
    "name": "Del presupuesto al gasto",
    "dataColors": PALETA,
    "foreground": INK, "foregroundNeutralSecondary": INK2, "foregroundNeutralTertiary": INK3,
    "background": BLANCO, "backgroundLight": FONDO, "backgroundNeutral": "#E4E9F0",
    "tableAccent": PALETA[0], "shapeStroke": LINEA,
    "good": PALETA[2], "neutral": PALETA[1], "bad": PALETA[3],
    "maximum": PALETA[0], "center": "#C9D3E0", "minimum": "#EAF0F8",
    "textClasses": {
        "callout": {"fontSize": 26, "fontFace": "Segoe UI Semibold", "color": NAVY},
        "title": {"fontSize": 13, "fontFace": "Segoe UI Semibold", "color": INK},
        "header": {"fontSize": 12, "fontFace": "Segoe UI Semibold", "color": INK},
        "label": {"fontSize": 11, "fontFace": "Segoe UI", "color": INK2}},
    "visualStyles": {
        "*": {"*": {
            "title": [{"show": True, "fontSize": 13, "fontColor": sc(INK), "alignment": "left", "bold": True,
                       "fontFamily": "Segoe UI Semibold", "titleWrap": True}],
            "subTitle": [{"show": False}],
            "background": [{"show": True, "color": sc(BLANCO), "transparency": 0}],
            "border": [{"show": True, "width": 1, "radius": 4, "color": sc(LINEA)}],
            "dropShadow": [{"show": False}],
            "padding": [{"left": 16, "top": 12, "right": 16, "bottom": 14}],
            "categoryAxis": [{"fontSize": 11, "labelColor": sc(INK2), "showAxisTitle": False, "gridlineColor": sc(REJILLA)}],
            "valueAxis": [{"fontSize": 11, "labelColor": sc(INK2), "showAxisTitle": False, "gridlineStyle": "solid",
                           "gridlineColor": sc(REJILLA)}],
            "legend": [{"show": True, "position": "Bottom", "showTitle": False, "fontSize": 11, "labelColor": sc(INK2)}],
            "lineStyles": [{"strokeWidth": 2.5}]}},
        "lineChart": {"*": {"lineStyles": [{"lineChartType": "linear", "strokeWidth": 2.5, "showMarker": True,
                                            "showMarkerByDefault": True, "markerShape": "circle", "markerSize": 6}]}},
        "card": {"*": {
            "title": [{"show": True, "fontSize": 12, "fontColor": sc(INK2), "bold": False, "alignment": "left",
                       "fontFamily": "Segoe UI"}],
            "labels": [{"fontSize": 28, "color": sc(NAVY), "fontFamily": "Segoe UI Semibold"}],
            "categoryLabels": [{"show": False}],
            "padding": [{"left": 16, "top": 10, "right": 16, "bottom": 10}]}},
        "tableEx": {"*": {"stylePreset": [{"name": "None"}], **estilo_tabla()}, "None": estilo_tabla()},
        "pivotTable": {"*": {"stylePreset": [{"name": "None"}], **estilo_pivote()}, "None": estilo_pivote()},
        "waterfallChart": {"*": {"sentimentColors": [{"increaseFill": sc(PALETA[2]), "decreaseFill": sc(PALETA[3]),
                                                       "otherFill": sc(INK3), "totalFill": sc(PALETA[0])}]}},
        "slicer": {"*": {"dropdown": [{"borderColor": sc("#BFC8D4"), "borderRadius": 3}],
                         "items": [{"padding": 6, "fontColor": sc(INK)}]}},
        "pageNavigator": {**estilo_navegador(False), "Tab": estilo_navegador(True)},
        "page": {"*": {"background": [{"color": sc(FONDO), "transparency": 0}],
                       "outspace": [{"color": sc("#DDE2EA")}]}}}}
TEMA_ARCHIVO = "PresupuestoAlGasto.json"
RR = "presupuesto_al_gasto.Report/StaticResources/RegisteredResources/"
w(RR + TEMA_ARCHIVO, json.dumps(TEMA, ensure_ascii=False, indent=2))

rep = json.load(open(SRC + RP + "report.json", encoding="utf-8"))
tc = rep["themeCollection"]
tc["customTheme"] = {"name": TEMA_ARCHIVO, "reportVersionAtImport": dict(tc["baseTheme"]["reportVersionAtImport"]),
                     "type": "RegisteredResources"}
rep["resourcePackages"] = [rp for rp in rep["resourcePackages"] if rp["name"] != "RegisteredResources"] + [
    {"name": "RegisteredResources", "type": "RegisteredResources",
     "items": [{"name": TEMA_ARCHIVO, "path": TEMA_ARCHIVO, "type": "CustomTheme"}]}]
w(RP + "report.json", json.dumps(rep, ensure_ascii=False, indent=2))

# ---------------------------------------------------------------- escribir páginas
order = []
for p in pages:
    order.append(p["id"])
    vis = OUT + RP + f"pages/{p['id']}/visuals"
    if os.path.isdir(vis):
        shutil.rmtree(vis)
    pj = {"$schema": PG, "name": p["id"], "displayName": p["name"], "displayOption": p.get("display", "FitToPage"),
          "height": p.get("height", 1080), "width": 1920,
          "objects": {"background": [{"properties": {"color": solid(FONDO), "transparency": lit("0D")}}],
                      "outspace": [{"properties": {"color": solid("#DDE2EA")}}]}}
    if p["filters"]:
        pj["filterConfig"] = {"filters": p["filters"]}
    w(RP + f"pages/{p['id']}/page.json", json.dumps(pj, ensure_ascii=False, indent=2))
    for v in p["visuals"]:
        w(RP + f"pages/{p['id']}/visuals/{v['name']}/visual.json", json.dumps(v, ensure_ascii=False, indent=2))
pj = json.load(open(SRC + RP + "pages/pages.json", encoding="utf-8"))
pj["pageOrder"] = order
pj["activePageName"] = order[0]
w(RP + "pages/pages.json", json.dumps(pj, ensure_ascii=False, indent=2))

print(f"{len(pages)} páginas, {sum(len(p['visuals']) for p in pages)} objetos visuales; escrito en {OUT}")
