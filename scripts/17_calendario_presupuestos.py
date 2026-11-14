"""Fase 5 · Calendario de presupuestos prorrogados (días y Gobiernos).

Mide, solo con fechas del BOE, cuánto tiempo se ha vivido con un presupuesto prorrogado (art. 134.4 de la
Constitución) y qué parte de cada mandato de Gobierno ha caído en esa situación. Es descriptivo: no dice por qué se
prorrogó un presupuesto ni evalúa a ningún Gobierno.

Medida A · por año natural: días con presupuesto prorrogado.
Medida B · por Gobierno: días de mandato, días en funciones, días con presupuesto prorrogado y leyes de
presupuestos publicadas durante el mandato.

Convenios (los mismos en los CSV y en comparativa.md):
- Días contados con los dos extremos incluidos. Ventana: del 1/01/2017 a la fecha de corte.
- «Gobierno» = desde la fecha del Real Decreto que nombra al Presidente hasta el día anterior al siguiente
  nombramiento. Los ministros se nombran 4-5 días después y la toma de posesión es posterior al Real Decreto, así que
  los límites tienen una imprecisión de unos pocos días; las fechas de los ministros van en el CSV.
- «En funciones» = desde la fecha del Real Decreto de cese tras las elecciones (el día siguiente a votar) hasta el día
  anterior al nombramiento del siguiente Presidente. Tras una moción de censura el Real Decreto de cese no dice
  «en funciones» y no se cuenta.
- 2026 no es un ejercicio cerrado: se cuenta hasta la fecha de corte.

Salidas (datos/):
  calendario_tramos.csv       tramos de presupuesto vigente (propio o prorrogado) con su fuente
  calendario_presupuestos.csv Medida A: años naturales
  calendario_gobiernos.csv    Medida B: Gobiernos
  calendario_fuentes.csv      cada fecha usada, con la norma y su referencia en el BOE
  comparativa.md              tablas entre las marcas <!-- tabla:calendario_… --> y <!-- /tabla -->

Uso: python scripts/17_calendario_presupuestos.py [AAAA-MM-DD]   (fecha de corte; por defecto, la de abajo)
"""
import csv
import re
import sys
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datos"
DOC = RAIZ / "comparativa.md"

CORTE = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date(2026, 11, 10)
INICIO = date(2017, 1, 1)
BOE = "https://www.boe.es/diario_boe/txt.php?id="

d = date.fromisoformat

# ---------------------------------------------------------------------------------------------------------------
# 1. Fuentes: cada fecha usada, con su norma. id = referencia del BOE ("" si no se ha podido comprobar el enlace).
# ---------------------------------------------------------------------------------------------------------------
FUENTES = [
    # (clave, fecha del hecho, hecho, norma, id BOE, fecha de publicación en el BOE)
    ("rd414_2016", "2016-10-30", "Nombramiento del Presidente del Gobierno", "Real Decreto 414/2016, de 30 de octubre", "BOE-A-2016-9962", "2016-10-31"),
    ("rd417_2016", "2016-11-03", "Nombramiento de los ministros", "Real Decreto 417/2016, de 3 de noviembre", "BOE-A-2016-10169", "2016-11-04"),
    ("eic36_2017", "2017-01-24", "Prórroga del presupuesto de 2016 (Ley 48/2015) durante 2017", "Orden EIC/36/2017, de 24 de enero", "BOE-A-2017-815", "2017-01-26"),
    ("ley3_2017", "2017-06-27", "Ley de Presupuestos Generales del Estado para 2017 (en vigor el 29/06/2017)", "Ley 3/2017, de 27 de junio", "BOE-A-2017-7387", "2017-06-28"),
    ("eic1300_2017", "2017-12-27", "Prórroga del presupuesto de 2017 durante 2018", "Orden EIC/1300/2017, de 27 de diciembre", "BOE-A-2017-15723", "2017-12-29"),
    ("rd353_2018", "2018-06-01", "Cese del Presidente del Gobierno tras la moción de censura", "Real Decreto 353/2018, de 1 de junio", "BOE-A-2018-7402", "2018-06-02"),
    ("rd354_2018", "2018-06-01", "Nombramiento del Presidente del Gobierno", "Real Decreto 354/2018, de 1 de junio", "BOE-A-2018-7400", "2018-06-02"),
    ("rd357_2018", "2018-06-06", "Nombramiento de los ministros", "Real Decreto 357/2018, de 6 de junio", "BOE-A-2018-7577", "2018-06-07"),
    ("ley6_2018", "2018-07-03", "Ley de Presupuestos Generales del Estado para 2018 (en vigor el 05/07/2018)", "Ley 6/2018, de 3 de julio", "BOE-A-2018-9268", "2018-07-04"),
    ("rdl28_2018", "2018-12-28", "Se mantiene en 2019 parte del contenido de la Ley 6/2018 mientras no se apruebe la ley de 2019", "Real Decreto-ley 28/2018, de 28 de diciembre", "BOE-A-2018-17992", ""),
    ("rd129_2019", "2019-03-04", "Disolución de las Cortes y elecciones del 28/04/2019", "Real Decreto 129/2019, de 4 de marzo", "BOE-A-2019-3109", "2019-03-05"),
    ("rd336_2019", "2019-04-29", "Cese del Presidente del Gobierno, que continúa en funciones", "Real Decreto 336/2019, de 29 de abril", "BOE-A-2019-6355", ""),
    ("rd337_2019", "2019-04-29", "Cese de los miembros del Gobierno, que continúan en funciones", "Real Decreto 337/2019, de 29 de abril", "BOE-A-2019-6356", ""),
    ("rd551_2019", "2019-09-24", "Disolución de las Cortes y elecciones del 10/11/2019", "Real Decreto 551/2019, de 24 de septiembre", "BOE-A-2019-13558", "2019-09-24"),
    ("rd1_2020", "2020-01-07", "Nombramiento del Presidente del Gobierno", "Real Decreto 1/2020, de 7 de enero", "BOE-A-2020-231", "2020-01-08"),
    ("rd8_2020", "2020-01-12", "Nombramiento de los ministros", "Real Decreto 8/2020, de 12 de enero", "BOE-A-2020-416", "2020-01-13"),
    ("etd9_2020", "2020-01-16", "Prórroga del presupuesto de 2018 durante 2020 (ya prorrogado en 2019)", "Orden ETD/9/2020, de 16 de enero", "BOE-A-2020-679", "2020-01-17"),
    ("ley11_2020", "2020-12-30", "Ley de Presupuestos Generales del Estado para 2021 (en vigor el 01/01/2021)", "Ley 11/2020, de 30 de diciembre", "BOE-A-2020-17339", "2020-12-31"),
    ("ley22_2021", "2021-12-28", "Ley de Presupuestos Generales del Estado para 2022 (en vigor el 01/01/2022)", "Ley 22/2021, de 28 de diciembre", "BOE-A-2021-21653", "2021-12-29"),
    ("ley31_2022", "2022-12-23", "Ley de Presupuestos Generales del Estado para 2023 (en vigor el 01/01/2023)", "Ley 31/2022, de 23 de diciembre", "BOE-A-2022-22128", "2022-12-24"),
    ("rd694_2023", "2023-07-24", "Cese del Presidente del Gobierno, que continúa en funciones", "Real Decreto 694/2023, de 24 de julio", "BOE-A-2023-17073", "2023-07-25"),
    ("rd695_2023", "2023-07-24", "Cese de los miembros del Gobierno, que continúan en funciones", "Real Decreto 695/2023, de 24 de julio", "BOE-A-2023-17074", "2023-07-25"),
    ("rd828_2023", "2023-11-16", "Nombramiento del Presidente del Gobierno", "Real Decreto 828/2023, de 16 de noviembre", "BOE-A-2023-23302", "2023-11-17"),
    ("rd835_2023", "2023-11-20", "Nombramiento de los ministros", "Real Decreto 835/2023, de 20 de noviembre", "BOE-A-2023-23543", "2023-11-21"),
    ("rdl8_2023", "2023-12-27", "Prórroga automática del presupuesto de 2023 durante 2024 (art. 134.4 CE)", "Real Decreto-ley 8/2023, de 27 de diciembre", "BOE-A-2023-26452", "2023-12-28"),
    ("ecm2_2026", "2026-01-09", "Prórroga del presupuesto de 2023 en 2024, 2025 y 2026", "Orden ECM/2/2026, de 9 de enero", "BOE-A-2026-678", "2026-01-13"),
    ("ecm941_2026", "2026-09-08", "Última referencia a la prórroga automática del presupuesto de 2023", "Orden ECM/941/2026, de 8 de septiembre", "BOE-A-2026-18896", "2026-09-09"),
    ("rd806_2026", "2026-10-05", "Disolución de las Cortes y convocatoria de elecciones para el 29/11/2026", "Real Decreto 806/2026, de 5 de octubre", "BOE-A-2026-20742", "2026-10-06"),
]
FUENTE = {k: (hecho, norma, i, pub) for k, _, hecho, norma, i, pub in FUENTES}


def ref(clave):
    """'Norma (BOE-A-…)' para las columnas de fuente."""
    _, norma, i, pub = FUENTE[clave]
    if i:
        return f"{norma} ({i})"
    return f"{norma} (BOE de {fmt(d(pub))}; sin enlace comprobado)" if pub else f"{norma} (sin enlace comprobado)"


# ---------------------------------------------------------------------------------------------------------------
# 2. Presupuesto vigente: tramos contiguos desde el 1/01/2017. 'propio' = ley aprobada para ese ejercicio;
#    'prorrogado' = presupuesto del ejercicio anterior (art. 134.4 CE).
# ---------------------------------------------------------------------------------------------------------------
# (desde, hasta o None si sigue abierto, situación, presupuesto que rige, ley, entrada en vigor de la ley, fuentes)
TRAMOS = [
    ("2017-01-01", "2017-06-28", "prorrogado", "2016", "Ley 48/2015, de 29 de octubre", "", ["eic36_2017"]),
    ("2017-06-29", "2017-12-31", "propio", "2017", "Ley 3/2017, de 27 de junio", "2017-06-29", ["ley3_2017"]),
    ("2018-01-01", "2018-07-04", "prorrogado", "2017", "Ley 3/2017, de 27 de junio", "", ["eic1300_2017"]),
    ("2018-07-05", "2018-12-31", "propio", "2018", "Ley 6/2018, de 3 de julio", "2018-07-05", ["ley6_2018"]),
    ("2019-01-01", "2020-12-31", "prorrogado", "2018", "Ley 6/2018, de 3 de julio", "", ["rdl28_2018", "etd9_2020"]),
    ("2021-01-01", "2021-12-31", "propio", "2021", "Ley 11/2020, de 30 de diciembre", "2021-01-01", ["ley11_2020"]),
    ("2022-01-01", "2022-12-31", "propio", "2022", "Ley 22/2021, de 28 de diciembre", "2022-01-01", ["ley22_2021"]),
    ("2023-01-01", "2023-12-31", "propio", "2023", "Ley 31/2022, de 23 de diciembre", "2023-01-01", ["ley31_2022"]),
    ("2024-01-01", None, "prorrogado", "2023", "Ley 31/2022, de 23 de diciembre", "", ["rdl8_2023", "ecm2_2026", "ecm941_2026"]),
]

# Leyes de presupuestos publicadas en el periodo: (ley, ejercicio, fecha de publicación en el BOE)
LEYES = [("Ley 3/2017", 2017, "2017-06-28"), ("Ley 6/2018", 2018, "2018-07-04"), ("Ley 11/2020", 2021, "2020-12-31"),
         ("Ley 22/2021", 2022, "2021-12-29"), ("Ley 31/2022", 2023, "2022-12-24")]

# ---------------------------------------------------------------------------------------------------------------
# 3. Gobiernos: desde el Real Decreto que nombra al Presidente. cese_funciones = Real Decreto de cese tras elecciones.
# ---------------------------------------------------------------------------------------------------------------
GOBIERNOS = [
    # (nombrado, fin de la etiqueta, ministros, cese_funciones o None, motivo del fin, fuentes)
    ("2016-10-30", "2016-11-03", None, "moción de censura (cese 01/06/2018, sin «en funciones»)", ["rd414_2016", "rd417_2016", "rd353_2018"]),
    ("2018-06-01", "2018-06-06", "2019-04-29", "nombramiento de un nuevo Presidente tras las elecciones del 28/04/2019 y del 10/11/2019", ["rd354_2018", "rd357_2018", "rd336_2019", "rd337_2019", "rd129_2019", "rd551_2019"]),
    ("2020-01-07", "2020-01-12", "2023-07-24", "nombramiento de un nuevo Presidente tras las elecciones del 23/07/2023", ["rd1_2020", "rd8_2020", "rd694_2023", "rd695_2023"]),
    ("2023-11-16", "2023-11-20", None, "", ["rd828_2023", "rd835_2023", "rd806_2026"]),
]


def fmt(x):
    return x.strftime("%d/%m/%Y")


def n(x):
    return f"{x:,}".replace(",", ".")


def pct(a, b):
    return f"{100 * a / b:.1f}".replace(".", ",") if b else ""


def dias(a, b):
    """Días de a a b, ambos incluidos (0 si no hay solape)."""
    return max(0, (b - a).days + 1)


def solape(a1, b1, a2, b2):
    return dias(max(a1, a2), min(b1, b2))


# ---------------------------------------------------------------------------------------------------------------
# Tramos con fechas y comprobaciones
# ---------------------------------------------------------------------------------------------------------------
tramos = []
for desde, hasta, sit, base, ley, vigor, fte in TRAMOS:
    a = d(desde)
    b = d(hasta) if hasta else CORTE
    tramos.append(dict(desde=a, hasta=b, abierto=hasta is None, situacion=sit, base=base, ley=ley,
                       vigor=d(vigor) if vigor else None, fuentes=fte))

assert tramos[0]["desde"] == INICIO
for t0, t1 in zip(tramos, tramos[1:]):
    assert t1["desde"] == t0["hasta"] + timedelta(days=1), f"hueco o solape entre {t0['hasta']} y {t1['desde']}"
assert tramos[-1]["hasta"] == CORTE and tramos[-1]["abierto"]
for t in tramos:
    if t["situacion"] == "propio":
        assert t["vigor"] == t["desde"], "un tramo propio empieza el día de entrada en vigor de su ley"
        assert int(t["base"]) == t["desde"].year, "la ley es la del año"
    else:
        assert int(t["base"]) < t["desde"].year, "el presupuesto prorrogado es de un año anterior"
# cada ley publicada sale en un tramo propio cuya entrada en vigor es posterior o igual a su publicación (días de diferencia)
for ley, ej, pub in LEYES:
    propios = [t for t in tramos if t["situacion"] == "propio" and t["ley"].startswith(ley)]
    assert len(propios) == 1 and d(pub) <= propios[0]["vigor"] <= d(pub) + timedelta(days=10), ley


def sit_en(dia):
    for t in tramos:
        if t["desde"] <= dia <= t["hasta"]:
            return t["situacion"]
    raise ValueError(dia)


# ---------------------------------------------------------------------------------------------------------------
# Medida A · años naturales
# ---------------------------------------------------------------------------------------------------------------
def leer(nombre):
    with open(DATOS / nombre, encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter=";"))


etiqueta_ficha = {}
try:
    for r in leer("ficha_resumen.csv"):
        etiqueta_ficha[int(r["anio"])] = r["presupuesto"]
except FileNotFoundError:
    pass

anios = []
for y in range(2017, CORTE.year + 1):
    a, b = date(y, 1, 1), min(date(y, 12, 31), CORTE)
    dprorr = sum(solape(a, b, t["desde"], t["hasta"]) for t in tramos if t["situacion"] == "prorrogado")
    dprop = sum(solape(a, b, t["desde"], t["hasta"]) for t in tramos if t["situacion"] == "propio")
    dy = dias(a, b)
    assert dprorr + dprop == dy
    leyes = [t for t in tramos if t["situacion"] == "propio" and t["desde"] <= b and t["hasta"] >= a]
    if dprorr == dy:
        sit = "prorrogado todo el año"
    elif dprorr == 0:
        sit = "presupuesto propio todo el año"
    else:
        sit = "prorrogado hasta la entrada en vigor de la ley del año"
    et = etiqueta_ficha.get(y, "")
    # la etiqueta binaria de ficha_resumen debe ser coherente con los días
    if et == "prorrogado":
        assert dprorr == dy, f"{y}: etiqueta prorrogado pero {dprorr}/{dy} días"
    if et == "aprobado":
        assert dprop > 0, f"{y}: etiqueta aprobado pero sin días con ley propia"
    anios.append(dict(anio=y, dias_anio=dy, dias_prorrogado=dprorr, dias_ley_propia=dprop,
                      situacion=sit, cerrado=y < CORTE.year or CORTE == date(y, 12, 31), etiqueta_ficha=et,
                      entrada_ley=min((t["vigor"] for t in leyes if t["vigor"]), default=None) if dprop else None))

total_dias = dias(INICIO, CORTE)
total_prorr = sum(a["dias_prorrogado"] for a in anios)
assert total_dias == sum(a["dias_anio"] for a in anios)
rachas = [(t["desde"], t["hasta"], dias(t["desde"], t["hasta"])) for t in tramos if t["situacion"] == "prorrogado"]
assert sum(r[2] for r in rachas) == total_prorr
# comprobaciones fijas con los valores a mano del BOE (independientes de las constantes de arriba)
asert = {2017: 179, 2018: 185, 2019: 365, 2020: 366, 2021: 0, 2022: 0, 2023: 0, 2024: 366, 2025: 365}
for a in anios:
    if a["anio"] in asert:
        assert a["dias_prorrogado"] == asert[a["anio"]], (a["anio"], a["dias_prorrogado"])
if CORTE == date(2026, 11, 10):
    assert anios[-1]["dias_prorrogado"] == 314 and rachas[-1][2] == 1045

# ---------------------------------------------------------------------------------------------------------------
# Medida B · Gobiernos
# ---------------------------------------------------------------------------------------------------------------
gob = []
for i, (nom, minis, cese, motivo, fte) in enumerate(GOBIERNOS):
    ini = d(nom)
    fin = d(GOBIERNOS[i + 1][0]) - timedelta(days=1) if i + 1 < len(GOBIERNOS) else CORTE
    a, b = max(ini, INICIO), fin
    f_ini = d(cese) if cese else None
    dm_total = dias(ini, fin)
    dm = dias(a, b)
    dfun = dias(f_ini, fin) if f_ini else 0
    dpr = sum(solape(a, b, t["desde"], t["hasta"]) for t in tramos if t["situacion"] == "prorrogado")
    dfpr = sum(solape(f_ini, fin, t["desde"], t["hasta"]) for t in tramos if t["situacion"] == "prorrogado") if f_ini else 0
    leyes = [(ley, ej, pub) for ley, ej, pub in LEYES if ini <= d(pub) <= fin]
    # días desde el nombramiento hasta la publicación de cada ley, y a la inversa
    gob.append(dict(
        etiqueta=f"Gobierno nombrado el {fmt(ini)}", rd=FUENTE[fte[0]][1].split(",")[0].replace("Real Decreto ", "RD "),
        nombrado=ini, ministros=d(minis), cese=f_ini, fin=fin, abierto=i + 1 == len(GOBIERNOS), motivo=motivo,
        dias_mandato=dm_total, dias_ventana=dm, dias_funciones=dfun, dias_prorrogado=dpr, dias_funciones_prorrogado=dfpr,
        leyes=leyes, fuentes=fte))
assert sum(g["dias_ventana"] for g in gob) == total_dias, "los Gobiernos cubren toda la ventana sin huecos"
assert sum(g["dias_prorrogado"] for g in gob) == total_prorr
if CORTE == date(2026, 11, 10):
    g1, g2, g3, g4 = gob
    assert (g1.get("dias_funciones"), g2["dias_funciones"], g3["dias_funciones"], g4["dias_funciones"]) == (0, 253, 115, 0)
    assert g2["dias_funciones_prorrogado"] == 253 and g3["dias_funciones_prorrogado"] == 0
    assert g4["dias_prorrogado"] == 1045 and g3["dias_prorrogado"] == 360

ultima = max(LEYES, key=lambda x: x[2])
dias_desde_ultima_ley = (CORTE - d(ultima[2])).days

# ---------------------------------------------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------------------------------------------
def csvfile(nombre, cab, filas):
    with open(DATOS / nombre, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter=";", lineterminator="\n")
        w.writerow(cab)
        for f in filas:
            w.writerow([str(x).replace(".", ",") if isinstance(x, float) else x for x in f])


csvfile("calendario_tramos.csv",
        ["desde", "hasta", "abierto", "dias", "situacion", "presupuesto_que_rige", "ley", "entrada_en_vigor_ley", "fuente"],
        [(t["desde"], t["hasta"], "sí" if t["abierto"] else "no", dias(t["desde"], t["hasta"]), t["situacion"],
          t["base"], t["ley"], t["vigor"] or "", " | ".join(ref(k) for k in t["fuentes"])) for t in tramos])

csvfile("calendario_presupuestos.csv",
        ["anio", "ejercicio_cerrado", "fecha_corte", "dias_anio", "dias_prorrogado", "pct_prorrogado", "dias_con_ley_propia",
         "situacion", "entrada_en_vigor_ley_del_anio", "etiqueta_en_fichas"],
        [(a["anio"], "sí" if a["cerrado"] else "no", CORTE if not a["cerrado"] else "", a["dias_anio"], a["dias_prorrogado"],
          pct(a["dias_prorrogado"], a["dias_anio"]), a["dias_ley_propia"], a["situacion"], a["entrada_ley"] or "",
          a["etiqueta_ficha"]) for a in anios])

csvfile("calendario_gobiernos.csv",
        ["gobierno", "real_decreto_presidente", "nombrado_el", "ministros_nombrados_el", "cese_en_funciones_el", "hasta",
         "en_curso", "motivo_del_fin", "dias_mandato", "dias_en_ventana_2017_corte", "dias_en_funciones",
         "dias_presupuesto_prorrogado", "pct_prorrogado", "dias_en_funciones_con_presupuesto_prorrogado",
         "leyes_pge_publicadas_en_el_mandato", "fuentes"],
        [(g["etiqueta"], g["rd"], g["nombrado"], g["ministros"], g["cese"] or "", g["fin"], "sí" if g["abierto"] else "no",
          g["motivo"], g["dias_mandato"], g["dias_ventana"], g["dias_funciones"], g["dias_prorrogado"],
          pct(g["dias_prorrogado"], g["dias_ventana"]), g["dias_funciones_prorrogado"],
          "; ".join(f"{l} (BOE {fmt(d(p))})" for l, _, p in g["leyes"]) or "ninguna",
          " | ".join(ref(k) for k in g["fuentes"])) for g in gob])

csvfile("calendario_fuentes.csv", ["fecha", "hecho", "norma", "referencia_boe", "publicado_en_el_boe", "enlace"],
        [(f, h, nm, i, pub, BOE + i if i else "") for _, f, h, nm, i, pub in sorted(FUENTES, key=lambda x: x[1])])

# ---------------------------------------------------------------------------------------------------------------
# Tablas de comparativa.md
# ---------------------------------------------------------------------------------------------------------------
def tabla_tramos():
    o = ["| Desde | Hasta | Días | Situación | Presupuesto que rige | Fuente |", "| --- | --- | ---: | --- | --- | --- |"]
    for t in tramos:
        hasta = f"{fmt(t['hasta'])} (corte)" if t["abierto"] else fmt(t["hasta"])
        sit = "**prorrogado**" if t["situacion"] == "prorrogado" else "ley del año"
        o.append(f"| {fmt(t['desde'])} | {hasta} | {n(dias(t['desde'], t['hasta']))} | {sit} | {t['ley']} (ejercicio {t['base']}) | "
                 + "; ".join(FUENTE[k][1].split(",")[0] for k in t["fuentes"]) + " |")
    return "\n".join(o)


def tabla_anios():
    o = ["| Año | Días del año | Días con presupuesto prorrogado | % del año | Presupuesto del año en vigor desde |",
         "| --- | ---: | ---: | ---: | --- |"]
    for a in anios:
        nota = "" if a["cerrado"] else " (hasta el corte)"
        ley = fmt(a["entrada_ley"]) if a["entrada_ley"] else ("—" if a["dias_prorrogado"] else "")
        o.append(f"| {a['anio']}{' (*)' if not a['cerrado'] else ''} | {n(a['dias_anio'])}{nota} | {n(a['dias_prorrogado'])} | "
                 f"{pct(a['dias_prorrogado'], a['dias_anio'])} | {ley} |")
    o.append(f"| **Total {INICIO.year}–{CORTE.year}** | **{n(total_dias)}** | **{n(total_prorr)}** | **{pct(total_prorr, total_dias)}** | |")
    return "\n".join(o)


def tabla_gobiernos():
    o = ["| Gobierno | Días en la ventana | En funciones | Con presupuesto prorrogado | % prorrogado | De ellos, en funciones y con presupuesto prorrogado | Leyes de presupuestos publicadas |",
         "| --- | ---: | ---: | ---: | ---: | ---: | --- |"]
    for g in gob:
        leyes = "; ".join(f"{l} ({fmt(d(p))})" for l, _, p in g["leyes"]) or "ninguna"
        etq = f"Nombrado el {fmt(g['nombrado'])} ({g['rd']})" + (" · en curso" if g["abierto"] else "")
        o.append(f"| {etq} | {n(g['dias_ventana'])} | {n(g['dias_funciones'])} | {n(g['dias_prorrogado'])} | "
                 f"{pct(g['dias_prorrogado'], g['dias_ventana'])} | {n(g['dias_funciones_prorrogado'])} | {leyes} |")
    return "\n".join(o)


def texto():
    ultimo, pen = rachas[-1], rachas[-2]
    g4 = gob[-1]
    return "\n".join([
        f"- Del {fmt(INICIO)} al {fmt(CORTE)} ({n(total_dias)} días) el presupuesto en vigor fue uno prorrogado durante "
        f"**{n(total_prorr)} días ({pct(total_prorr, total_dias)} %)**.",
        f"- Racha más larga: del {fmt(ultimo[0])} al {fmt(ultimo[1])}, **{n(ultimo[2])} días seguidos** con el presupuesto de "
        f"2023 prorrogado (2024, 2025 y lo que va de 2026). Sigue abierta. La anterior fue del {fmt(pen[0])} al {fmt(pen[1])} "
        f"({n(pen[2])} días, con el de 2018).",
        f"- {anios[0]['anio']} y {anios[1]['anio']} figuran como «aprobado» en las demás tablas porque la ley del año llegó antes "
        f"del 31 de diciembre, pero empezaron prorrogados: {n(anios[0]['dias_prorrogado'])} y {n(anios[1]['dias_prorrogado'])} días.",
        f"- La última ley de presupuestos publicada es la {ultima[0]} (BOE del {fmt(d(ultima[2]))}); a la fecha de corte han "
        f"pasado {n(dias_desde_ultima_ley)} días desde su publicación.",
        f"- El Real Decreto 806/2026 (BOE del 06/10/2026) disolvió las Cortes y convocó elecciones para el 29/11/2026. "
        f"El Gobierno nombrado el {fmt(g4['nombrado'])} no está en funciones a {fmt(CORTE)}: en 2019 y 2023 el cese tras las "
        f"elecciones se declaró al día siguiente de votar.",
    ])


def inyectar(texto_md, nombre, contenido):
    patron = rf"<!-- tabla:{nombre} -->.*?<!-- /tabla -->"
    nuevo, k = re.subn(patron, lambda _: f"<!-- tabla:{nombre} -->\n{contenido}\n<!-- /tabla -->", texto_md, flags=re.S)
    return nuevo, k


if DOC.exists():
    md = DOC.read_text(encoding="utf-8")
    marcas = 0
    for nombre, contenido in (("calendario_texto", texto()), ("calendario_tramos", tabla_tramos()),
                              ("calendario_anios", tabla_anios()), ("calendario_gobiernos", tabla_gobiernos())):
        md, k = inyectar(md, nombre, contenido)
        marcas += k
    DOC.write_text(md, encoding="utf-8")
    print(f"comparativa.md: {marcas} de 4 marcas actualizadas")

print(f"corte {CORTE}: {total_dias} días, {total_prorr} prorrogados ({pct(total_prorr, total_dias)} %)")
for a in anios:
    print(a["anio"], a["dias_prorrogado"], "/", a["dias_anio"], a["situacion"], "| ficha:", a["etiqueta_ficha"])
for g in gob:
    print(g["etiqueta"], "| ventana", g["dias_ventana"], "| en funciones", g["dias_funciones"], "| prorrogado", g["dias_prorrogado"],
          "| func+prorr", g["dias_funciones_prorrogado"], "|", [l for l, _, _ in g["leyes"]])
