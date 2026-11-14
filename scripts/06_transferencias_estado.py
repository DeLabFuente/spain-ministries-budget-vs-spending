"""Transferencias del Estado a sus organismos, por destinatario (vol. I de la liquidación, «Ejecución art. 41/43/71/73»).

Sirve para no contar dos veces el gasto de un ministerio y el de sus organismos: lo que la sección transfiere a un
organismo es obligación del Estado y vuelve a ser gasto del organismo.
Artículos: 41 y 71 (a organismos autónomos), 43 y 73 (a otras entidades del sector público administrativo estatal
con presupuesto limitativo: agencias y otros organismos). Corrientes (4x) y de capital (7x).
Las líneas que agrupan a varios organismos («Confederaciones Hidrográficas», «Aportación del Estado a MUFACE, ISFAS
y MUGEJU», «Mecanismo de Recuperación y Resiliencia», «Otros») se dejan con su nombre; las de un solo ministerio
se asignan a él.

Entrada: fuentes/igae/_texto/estado_AAAA.txt (script 01), datos/organismos_ministerio_actual.csv (script 05)
Salidas: datos/transferencias_estado_organismos.csv (Estado -> organismos)
         datos/transferencias_organismos_al_estado.csv (organismos -> Estado, ingresos del Estado por concepto)
         datos/aportacion_estado_mutualismo.csv (sección 09 -> MUFACE, ISFAS y MUGEJU, como empleador)
"""
import csv
from collections import defaultdict
import importlib.util
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datos"


def cargar(nombre, fichero):
    spec = importlib.util.spec_from_file_location(nombre, RAIZ / "scripts" / fichero)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


liq = cargar("liq", "01_leer_liquidacion.py")
org = cargar("org", "05_organismos_ministerio.py")

NUM = liq.NUM
# Destinatarios que agrupan organismos de un mismo ministerio actual, o que no se pueden asignar
GRUPOS = {
    "CONFEDERACIONES HIDROGRAFICAS": "Ministerio para la Transición Ecológica y el Reto Demográfico",
    "MANCOMUNIDAD CANALES TAIBILLA": "Ministerio para la Transición Ecológica y el Reto Demográfico",
}
# Destinatarios abreviados: patrón -> palabras del nombre del organismo (organismo_id) o ministerio directo
RECEPTORES = [
    # La fuente publica en el art. 41 una sola línea para el INTA y el INVIED («INTA, Instituto Vivienda, Infraestruc.
    # y Equip. Defensa.» en 2017-2022, «INTA e INVIED» en 2024). Según los anexos de 2020-2024, el 99,9 % o más es del
    # INTA; en 2017-2019 (sin anexo) se supone igual. Ver REGISTRO.md.
    (r"^INTA\b", "TECNICA AEROESPACIAL"),
    (r"\bCNMC\b", "COMISION NACIONAL MERCADOS COMPETENCIA"),
    # El Fondo del Servicio Postal Universal lo recibe la CNMC (anexo: «A la CNMC para el Fondo de financiación del
    # Servicio Postal Universal», sección 17)
    (r"(?i)servicio postal universal", "COMISION NACIONAL MERCADOS COMPETENCIA"),
    # Desde 2023 la línea de la Agencia Tributaria se llama «A la A.E.A.T. por gastos y servicios varios»; sin esta
    # regla, la palabra «varios» la dejaba sin asignar
    (r"A\.E\.A\.T\.|Administración Tributaria", "ADMINISTRACION TRIBUTARIA"),
    (r"CIEMAT", "CENTRO INVESTIGACIONES ENERGETICAS"),
    (r"Seguridad e Higiene en el Trabajo|Seguridad y Salud en el Trabajo", "SEGURIDAD SALUD TRABAJO"),
    (r"(?i)miner[íi]a del carb[óo]n", "MINERIA CARBON"),
    (r"Instituto de la Mujer", "INSTITUTO MUJERES"),
    (r"\bSPEE\b|\bSEPE\b", "SERVICIO PUBLICO EMPLEO ESTATAL"),
    (r"\bICAA\b", "CINEMATOGRAFIA ARTES AUDIOVISUALES"),
    (r"\bINAEM\b", "ARTES ESCENICAS MUSICA"),
    (r"Salud Carlos III", "SALUD CARLOS III"),
    (r"\bFEGA\b", "FONDO GARANTIA AGRARIA"),
    (r"(?i)vivienda.*defensa", "VIVIENDA INFRAESTRUCTURA DEFENSA"),
    (r"(?i)medicamentos", "MEDICAMENTOS PRODUCTOS SANITARIOS"),
    # la antigua Agencia de Protección de la Salud en el Deporte es hoy la Comisión Antidopaje (no la de Protección de Datos)
    (r"(?i)protecci[óo]n de la salud en el deporte|antidopaje", "LUCHA ANTIDOPAJE DEPORTE"),
]
DIRECTOS = {}
# Destinatarios que no están en la liquidación de organismos (vol. II): no se restan del gasto de ningún ministerio.
# El Centro Nacional de Inteligencia no es un organismo del vol. II; sin esta regla se emparejaba con el Museo Reina Sofía.
SIN_ASIGNAR = ("MECANISMO RECUPERACION", "OTROS", "MUFACE", "RESTO", "VARIOS", "INTELIGENCIA")
SIN_ASIGNAR_RX = [r"\bCNI\b"]  # se comprueba con el texto original (en el normalizado «CNI» está dentro de «TECNICA»)
# Abreviaturas de los anexos por aplicación (descripciones de los conceptos del Mecanismo de Recuperación)
ALIAS_ANEXO = [
    (r"\bCSIC\b", "CONSEJO SUPERIOR INVESTIGACIONES CIENTIFICAS"),
    (r"\bAEI\b", "AGENCIA ESTATAL INVESTIGACION"),
    (r"\bOEITSS\b", "INSPECCION TRABAJO SEGURIDAD SOCIAL"),
    (r"\bAEMET\b", "AGENCIA ESTATAL METEOROLOGIA"),
    (r"\bI\.T\.J\.|Transición Justa", "TRANSICION JUSTA"),
    (r"(?i)Parques Nac", "PARQUES NACIONALES"),
    (r"(?i)Patrimonio Na(l|cional)\b", "PATRIMONIO NACIONAL"),
    (r"\bINSST\b", "SEGURIDAD SALUD TRABAJO"),
    (r"\bINJUVE\b", "INSTITUTO JUVENTUD"),
    (r"\bFOGASA\b", "FONDO GARANTIA SALARIAL"),
    (r"\bINVIED\b", "VIVIENDA INFRAESTRUCTURA DEFENSA"),
    (r"(?i)^Transferencias (corrientes|de capital)\. A Muface", "MUTUALIDAD GENERAL FUNCIONARIOS CIVILES"),
    (r"\bI?SCIII\b", "SALUD CARLOS III"),  # «SCIII»: así en la fuente (anexo), por ISCIII
    (r"(?i)Mutualidad de Funcionarios Civiles", "MUTUALIDAD GENERAL FUNCIONARIOS CIVILES"),
]


def preparar(tabla):
    global POR_ANIO, TODOS
    POR_ANIO, TODOS = {}, {}
    for r in tabla:
        POR_ANIO.setdefault(r["anio"], {})[org.normal(r["organismo_id"])] = r
    TODOS = {org.normal(r["organismo_id"]): r for r in tabla}


SIN = set()


def asignar(receptor, anio):
    """(ministerio actual, organismo_id, método) de un destinatario u origen escrito como en las tablas del vol. I.
    El método dice si la asignación es literal (nombre parecido) o una regla nuestra (alias, grupo, sin asignar)."""
    por_anio, todos, sin = POR_ANIO, TODOS, SIN
    n = org.normal(receptor)
    ministerio, organismo_id, metodo = "", "", ""
    grupo = next((g for g in GRUPOS if all(w in n for w in g.split())), None)
    patron = next((k for rx, k in RECEPTORES + ALIAS_ANEXO if re.search(rx, receptor)), None)
    if any(re.search(rx, receptor) for rx in SIN_ASIGNAR_RX):
        ministerio, metodo = "(sin asignar)", "sin asignar: no es un organismo del vol. II"
    elif patron:
        r = next((todos[c] for c in todos if all(w in c for w in patron.split())), None)
        if r is None:
            sin.add((anio, receptor + " [alias sin organismo]"))
            ministerio, metodo = "(sin asignar)", "regla escrita sin organismo"
        else:
            ministerio, organismo_id = r["ministerio_actual"], r["organismo_id"]
            metodo = f"regla escrita: {patron.lower()}"
    elif receptor in DIRECTOS:
        ministerio, organismo_id, metodo = DIRECTOS[receptor], receptor, "asignación directa"
    elif grupo:
        ministerio, organismo_id, metodo = GRUPOS[grupo], receptor, "grupo de organismos del mismo ministerio"
    elif any(w in n for w in SIN_ASIGNAR):
        ministerio, metodo = "(sin asignar)", "sin asignar: agrupa varios o no es un organismo del vol. II"
    else:
        cands = sorted(((org.parecido_org(n, c), c) for c in list(por_anio.get(anio, {})) + list(todos)),
                       reverse=True)
        if cands and cands[0][0] >= 0.66:
            r = por_anio.get(anio, {}).get(cands[0][1]) or todos[cands[0][1]]
            ministerio, organismo_id = r["ministerio_actual"], r["organismo_id"]
            metodo = "nombre igual" if cands[0][0] >= 0.999 else f"nombre parecido ({cands[0][0]:.2f})"
        else:
            sin.add((anio, receptor))
            ministerio, metodo = "(sin asignar)", "sin emparejar"
    return ministerio, organismo_id, metodo


def main():
    tabla = list(csv.DictReader(open(DATOS / "organismos_ministerio_actual.csv", encoding="utf-8"), delimiter=";"))
    preparar(tabla)
    filas, sin = [], SIN
    for txt in sorted((RAIZ / "fuentes" / "igae" / "_texto").glob("estado_*.txt")):
        anio = re.search(r"(\d{4})", txt.name).group(1)
        pags = txt.read_text(encoding="utf-8").split("\f")
        for i, p in enumerate(pags, 1):
            m = re.search(r"EJECUCIÓN ART\.?\s*(41|43|71|73)\b", p[:2500])
            if not m:
                continue
            art = m.group(1)
            for linea in p.splitlines():
                mm = re.match(r"^\s{2,}(\S.*?)\s{2,}(" + NUM + r")\s+(" + NUM + r")\s+(" + NUM + r")\s+(" + NUM + r")", linea)
                if not mm or "TOTALES" in mm.group(1).upper():
                    continue
                receptor = " ".join(mm.group(1).split())
                if not re.search(r"[a-záéíóú]", receptor) and not receptor.isupper():
                    continue
                d, o, _, pg = (liq.num(x) for x in mm.groups()[1:])
                ministerio, organismo_id, metodo = asignar(receptor, anio)
                filas.append(dict(anio=anio, articulo=art, capitulo=art[0], receptor=receptor,
                                  organismo_id=organismo_id, ministerio_actual=ministerio, metodo_asignacion=metodo,
                                  creditos_definitivos=d * 1000, obligaciones=o * 1000, pagos=pg * 1000,
                                  fuente=f"IGAE, Liquidación {anio} vol. I, ejecución art. {art}, p. {i} (miles de euros)"))
    filas = repartir_inta_invied(filas)
    filas = repartir_mecanismo(filas)
    for s in sorted(sin):
        print("sin emparejar:", s)
    # control: la suma de cada artículo debe coincidir con su fila TOTALES (se comprueba al leer el total)
    with open(DATOS / "transferencias_estado_organismos.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        campos = ["anio", "articulo", "capitulo", "receptor", "organismo_id", "ministerio_actual", "metodo_asignacion",
                  "creditos_definitivos", "obligaciones", "pagos", "fuente"]
        w.writerow(campos)
        for r in filas:
            w.writerow([liq.fmt(r[k]) if isinstance(r[k], float) else r[k] for k in campos])
    print(f"{len(filas)} líneas de transferencia; sin emparejar: {len(sin)}")
    al_estado()
    mutualismo()


def repartir_inta_invied(filas):
    """La línea conjunta del INTA y el INVIED (art. 41) se reparte entre los dos en proporción a sus derechos
    reconocidos por transferencias corrientes (capítulo 4 de sus ingresos) del mismo año. Es una estimación: la fuente
    no da el desglose. Contraste: en 2017-2019 la línea coincide con la suma de los dos (±1,3 M€); desde 2020 el INVIED
    no tiene ingresos del capítulo 4 y los anexos confirman que la línea es del INTA."""
    ing = {}
    for r in csv.DictReader(open(DATOS / "organismos_ingresos.csv", encoding="utf-8"), delimiter=";"):
        if r["capitulo"] == "4":
            ing[(r["anio"], r["organismo_id"])] = float(r["derechos_reconocidos"].replace(",", ".") or 0)
    inta = next(o for o in TODOS.values() if "AEROESPACIAL" in o["organismo_id"])["organismo_id"]
    invied = next(o for o in TODOS.values() if "VIVIENDA, INFRAESTRUCTURA" in o["organismo_id"])["organismo_id"]
    out = []
    for r in filas:
        if r["articulo"] != "41" or not re.match(r"^INTA\b", r["receptor"]):
            out.append(r)
            continue
        a, b = ing.get((r["anio"], inta), 0.0), ing.get((r["anio"], invied), 0.0)
        for oid, peso in ((inta, a / (a + b) if a + b else 1.0), (invied, b / (a + b) if a + b else 0.0)):
            if peso <= 0:
                continue
            x = dict(r, organismo_id=oid, creditos_definitivos=r["creditos_definitivos"] * peso,
                     obligaciones=r["obligaciones"] * peso, pagos=r["pagos"] * peso,
                     metodo_asignacion=f"línea conjunta INTA e INVIED: {100 * peso:.1f} % estimado por sus ingresos "
                                       f"corrientes (la fuente no da el desglose)")
            out.append(x)
    return out


def repartir_mecanismo(filas):
    """La fuente publica las transferencias del Mecanismo de Recuperación a organismos en una línea por artículo
    («Mecanismo de Recuperación y Resiliencia»), sin destinatario. Los anexos por aplicación (servicio «SS50», conceptos
    41, 43, 71 y 73) sí dicen a quién van, y su suma coincide al euro con esa línea. Se reparte la línea con ellos.
    Solo se guarda el organismo, no la descripción de la aplicación (intermedio privado)."""
    ap = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0, set()]))  # (año, art) -> organismo -> [def, obl, págs]
    sin_org = defaultdict(float)
    with open(RAIZ / "fuentes" / "igae" / "_intermedios" / "liquidacion_aplicaciones.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh, delimiter=";"):
            if r["servicio"][-2:] != "50" or r["economica"][:2] not in ("41", "43", "71", "73"):
                continue
            desc = re.split(r"(?i)[.,\s-]*(mecanismo de recuperaci|\bMRR\b)", r["descripcion"])[0]
            mi, oid, _ = asignar(desc, r["anio"])
            x = ap[(r["anio"], r["economica"][:2])][(mi, oid)]
            x[0] += float(r["creditos_definitivos"].replace(",", ".") or 0)
            x[1] += float(r["obligaciones"].replace(",", ".") or 0)
            x[2].add(r["pagina"])
    out = []
    for r in filas:
        if r["receptor"] != "Mecanismo de Recuperación y Resiliencia" or (r["anio"], r["articulo"]) not in ap:
            out.append(r)
            continue
        partes = ap[(r["anio"], r["articulo"])]
        tot_o = sum(v[1] for v in partes.values())
        if abs(tot_o - r["obligaciones"]) > 5000:  # la línea va en miles de euros redondeados; si no cuadra, se deja
            print("Mecanismo sin cuadrar:", r["anio"], r["articulo"], tot_o, r["obligaciones"])
            out.append(r)
            continue
        for (mi, oid), (d, o, pags) in sorted(partes.items(), key=lambda z: -z[1][1]):
            out.append(dict(r, organismo_id=oid, ministerio_actual=mi, creditos_definitivos=d, obligaciones=o,
                            pagos=None,
                            metodo_asignacion="línea del Mecanismo de Recuperación repartida con los anexos por aplicación "
                                              "(servicio SS50)" + ("" if oid else "; destinatario sin organismo en el vol. II"),
                            fuente=r["fuente"] + f"; reparto: anexos I y II, pp. {', '.join(sorted(pags, key=int))}"))
    return out


def al_estado():
    """Lo que los organismos transfieren al Estado (ingresos del Estado, artículos 41, 43, 71 y 73 por concepto).
    Ejemplo: la Jefatura de Tráfico entrega al Tesoro parte de su excedente. Es gasto del organismo (capítulo 4 o 7)
    que vuelve al Estado y no es gasto en sus funciones: se resta del gasto agregado del ministerio."""
    filas = []
    for txt in sorted((RAIZ / "fuentes" / "igae" / "_texto").glob("estado_*.txt")):
        anio = re.search(r"(\d{4})", txt.name).group(1)
        pags = txt.read_text(encoding="utf-8").split("\f")
        fin = next(i for i, p in enumerate(pags) if "MODIFICACIONES DE CRÉDITO POR SECCIONES" in p[:2500])
        vistos = {}
        for i, p in enumerate(pags[:fin], 1):
            if "CONCEPTOS" not in p[:2500].upper():
                continue
            for linea in p.splitlines():
                mm = re.match(r"^\s*((?:41|43|71|73)\d{1,3})\.\s+(.*?)\s{2,}(" + NUM + r")\s+(" + NUM + r")\s+(" + NUM + r")",
                              linea)
                if mm:
                    vistos[mm.group(1)] = (" ".join(mm.group(2).split()), liq.num(mm.group(4)), liq.num(mm.group(5)), i)
        hojas = [c for c in vistos if not any(o != c and o.startswith(c) for o in vistos)]   # el detalle más fino
        for c in sorted(hojas):
            nombre, dr, rec, pg = vistos[c]
            ministerio, organismo_id, metodo = asignar(nombre, anio)
            filas.append(dict(anio=anio, concepto=c, articulo=c[:2], origen=nombre, organismo_id=organismo_id,
                              ministerio_actual=ministerio, metodo_asignacion=metodo, derechos_reconocidos=dr * 1000, recaudacion=rec * 1000,
                              fuente=f"IGAE, Liquidación {anio} vol. I, ingresos por conceptos, p. {pg} (miles de euros)"))
    with open(DATOS / "transferencias_organismos_al_estado.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        campos = ["anio", "concepto", "articulo", "origen", "organismo_id", "ministerio_actual", "metodo_asignacion",
                  "derechos_reconocidos", "recaudacion", "fuente"]
        w.writerow(campos)
        for r in filas:
            w.writerow([liq.fmt(r[k]) if isinstance(r[k], float) else r[k] for k in campos])
    print(f"{len(filas)} conceptos de ingresos del Estado desde organismos")


def mutualismo():
    """Aportación del Estado como empleador a MUFACE, ISFAS y MUGEJU (sección 09, económicas 16001-16003, 2020-).
    Aparece en sus ingresos como cotizaciones (capítulo 1): no es dinero de los mutualistas."""
    mutuas = {"16001": "MUTUALIDAD GENERAL DE FUNCIONARIOS CIVILES DEL ESTADO",
              "16002": "INSTITUTO SOCIAL DE LAS FUERZAS ARMADAS", "16003": "MUTUALIDAD GENERAL JUDICIAL"}
    filas = []
    with open(RAIZ / "fuentes" / "igae" / "_intermedios" / "liquidacion_aplicaciones.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh, delimiter=";"):
            if r["seccion"] == "09" and r["economica"] in mutuas:
                filas.append(dict(anio=r["anio"], organismo_id=mutuas[r["economica"]], economica=r["economica"],
                                  obligaciones=float(r["obligaciones"].replace(",", ".")),
                                  fuente=f"IGAE, Liquidación {r['anio']} vol. I, anexo I, sección 09, aplicación "
                                         f"{r['servicio']} {r['programa']} {r['economica']} (euros)"))
    with open(DATOS / "aportacion_estado_mutualismo.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        campos = ["anio", "organismo_id", "economica", "obligaciones", "fuente"]
        w.writerow(campos)
        for r in filas:
            w.writerow([liq.fmt(r[k]) if isinstance(r[k], float) else r[k] for k in campos])
    print(f"{len(filas)} aportaciones del Estado al mutualismo")


if __name__ == "__main__":
    main()
