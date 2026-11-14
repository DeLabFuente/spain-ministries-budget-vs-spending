"""Asigna cada organismo (vol. II de la liquidación) a su ministerio actual.

Regla: un organismo va al ministerio al que está adscrito en el último año en que aparece (así el FEGA de 2017,
adscrito entonces a Agricultura y Medio Ambiente, va a Agricultura, y las confederaciones hidrográficas a Transición
Ecológica). Si ya no existe, va al ministerio actual de la sección a la que estaba adscrito (equivalencias_secciones).
Los nombres de un mismo organismo cambian entre años (abreviaturas, «O.A.»): se emparejan normalizando el nombre.

Entrada: datos/organismos_gastos.csv, datos/organismos_ingresos.csv, datos/secciones_ministerio_actual.csv
Salida:  datos/organismos_ministerio_actual.csv (una fila por organismo y año) y, con la columna de ministerio actual
         añadida, datos/organismos_gastos.csv y datos/organismos_ingresos.csv (se reescriben).
"""
import csv
import difflib
import re
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datos"

ABREV = {"INST.": "INSTITUTO", "INFRAESTR.": "INFRAESTRUCTURAS", "EQUIPAM.": "EQUIPAMIENTO", "EQUIP.": "EQUIPAMIENTO",
         "SERV.": "SERVICIO", "NAL.": "NACIONAL", "ADMON.": "ADMINISTRACION", "GRAL.": "GENERAL", "CTRO.": "CENTRO",
         "ORG.": "ORGANISMO", "AUT.": "AUTONOMO", "Y EQUIP.": "Y EQUIPAMIENTO", "SOC.": "SOCIALES", "F.": "FORMACION",
         "PÚBL.": "PUBLICA", "PUBL.": "PUBLICA", "TRANSF.": "TRANSFORMACION", "REL.": "RELACIONES", "DEMOCR.": "DEMOCRATICA",
         "ECONÓM.": "ECONOMICOS", "TRANSFORM.": "TRANSFORMACION", "EXT.": "EXTERIORES", "U. E.": "UNION EUROPEA",
         "RETO DEMOGR.": "RETO DEMOGRAFICO", "URB.": "URBANA", "ESP.": "ESPAÑOL", "INVEST.": "INVESTIGACIONES", "TECNOLÓG.": "TECNOLOGICAS",
         "AG.": "AGENCIA"}
# Mismo organismo con otro nombre (nombre antiguo -> nombre actual), comprobado con sus normas de creación
ALIAS = {"INSTITUTO DE LA MUJER Y PARA LA IGUALDAD DE OPORTUNIDADES": "INSTITUTO DE LAS MUJERES",
         "AGENCIA ESPAÑOLA DE PROTECCIÓN DE LA SALUD EN EL DEPORTE":
             "A.E. COMISIÓN ESPAÑOLA PARA LUCHA ANTIDOPAJE EN EL DEPORTE"}
VACIAS = {"DE", "DEL", "LA", "LAS", "LOS", "EL", "Y", "E", "PARA", "O", "A", "OA", "M", "MINISTERIO", "MO", "P"}
# palabras que no distinguen un organismo de otro (para emparejar nombres entre años)
GENERICAS = {"ORGANISMO", "AUTONOMO", "AGENCIA", "ESTATAL", "AE", "MP", "OAMP", "ENTIDAD", "PUBLICA"}


def normal(s):
    s = s.upper()
    for k, v in ABREV.items():
        s = s.replace(k, v)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"\bO\.\s*A\.?", " ", s)
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    return " ".join(w for w in s.split() if w not in VACIAS)


def parecido_org(a, b):
    """Proporción de palabras distintivas del nombre más corto que están en el otro (singular/plural igual)."""
    f = lambda s: {w.rstrip("S") for w in s.split() if w not in GENERICAS}
    ta, tb = f(a), f(b)
    comunes = len(ta & tb)
    if ta == tb:
        return 1.0
    return comunes / max(1, min(len(ta), len(tb))) if comunes >= 2 and min(len(ta), len(tb)) >= 2 else 0.0


def parecido(a, b):
    ta, tb = set(a.split()), set(b.split())
    jac = len(ta & tb) / max(1, len(ta | tb))
    return max(jac, difflib.SequenceMatcher(None, a, b).ratio())


def leer(nombre):
    with open(DATOS / nombre, encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter=";"))


def escribir(nombre, filas, campos):
    with open(DATOS / nombre, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(campos)
        for r in filas:
            w.writerow([r.get(k, "") for k in campos])


def main():
    sec = leer("secciones_ministerio_actual.csv")
    abrev = {(r["anio"], r["codigo_seccion"]): r for r in sec}
    nombres_sec = {}
    for r in leer("liquidacion_secciones.csv"):
        nombres_sec.setdefault(r["anio"], []).append((r["codigo_seccion"], normal(r["seccion"])))
        nombres_sec[r["anio"]].append((r["codigo_seccion"], normal(r["seccion_abreviada"])))

    gastos = leer("organismos_gastos.csv")
    ingresos = leer("organismos_ingresos.csv")

    # 1) departamento -> código de sección del mismo año
    depto_codigo, revisar = {}, []
    for anio, depto in sorted({(r["anio"], r["departamento"]) for r in gastos + ingresos}):
        if depto == "TOTAL GENERAL":
            continue
        n = normal(depto)
        cand = sorted(((parecido(n, s), c) for c, s in nombres_sec[anio]), reverse=True)
        score, codigo = cand[0]
        depto_codigo[(anio, depto)] = codigo
        if score < 0.75:
            revisar.append((anio, depto, codigo, round(score, 2)))
    for x in revisar:
        print("revisar departamento:", x)

    # 2) organismo -> identificador estable (nombre normalizado del año más reciente en que aparece)
    orgs = sorted({(r["anio"], r["tipo_entidad"], r["departamento"], r["organismo"]) for r in gastos if r["organismo"]},
                  key=lambda x: -int(x[0]))
    canon = {}          # normalizado -> (nombre más reciente, año, depto)
    ident = {}
    dudosos = []
    alias = {normal(k): normal(v) for k, v in ALIAS.items()}
    for anio, tipo, depto, org in orgs:
        n = normal(org)
        n = alias.get(n, n)
        if n not in canon:
            hit = next((c for c in canon if c == n or alias.get(c) == n), None)
            n = hit or n
        if n in canon:
            ident[(anio, depto, org)] = n
            continue
        cand = sorted(((parecido_org(n, c), c) for c in canon), reverse=True)
        if cand and cand[0][0] >= 0.85:
            ident[(anio, depto, org)] = cand[0][1]
            if cand[0][0] < 1:
                dudosos.append((org, canon[cand[0][1]][0], round(cand[0][0], 2)))
        else:
            canon[n] = (org, anio, depto)
            ident[(anio, depto, org)] = n
    for d in sorted(set(dudosos)):
        print("emparejado (comprobar):", d)

    # 3) ministerio actual: el de su adscripción en el último año en que aparece
    ultimo = {}
    for (anio, depto, org), n in ident.items():
        if n not in ultimo or int(anio) > int(ultimo[n][0]):
            ultimo[n] = (anio, depto)
    def ministerio(anio, depto, org):
        n = ident[(anio, depto, org)]
        a, d = ultimo[n]
        return abrev[(a, depto_codigo[(a, d)])]["ministerio_actual"]

    tabla = []
    for anio, tipo, depto, org in sorted(orgs, key=lambda x: (x[0], x[2], x[3])):
        n = ident[(anio, depto, org)]
        tabla.append(dict(anio=anio, tipo_entidad=tipo, departamento=depto,
                          codigo_seccion_departamento=depto_codigo[(anio, depto)], organismo=org,
                          organismo_id=canon[n][0], ministerio_actual=ministerio(anio, depto, org)))
    escribir("organismos_ministerio_actual.csv", tabla, ["anio", "tipo_entidad", "departamento",
             "codigo_seccion_departamento", "organismo", "organismo_id", "ministerio_actual"])

    for filas, nombre in ((gastos, "organismos_gastos.csv"), (ingresos, "organismos_ingresos.csv")):
        campos = [k for k in filas[0].keys() if k not in ("ministerio_actual", "organismo_id", "codigo_seccion_departamento")]
        for r in filas:
            if r["departamento"] == "TOTAL GENERAL":
                r.update(ministerio_actual="", organismo_id="", codigo_seccion_departamento="")
                continue
            r["codigo_seccion_departamento"] = depto_codigo[(r["anio"], r["departamento"])]
            if r["organismo"]:
                r["organismo_id"] = canon[ident[(r["anio"], r["departamento"], r["organismo"])]][0]
                r["ministerio_actual"] = ministerio(r["anio"], r["departamento"], r["organismo"])
            else:      # total del departamento: ministerio de la sección de ese año
                r["organismo_id"] = ""
                r["ministerio_actual"] = abrev[(r["anio"], r["codigo_seccion_departamento"])]["ministerio_actual"]
        i = campos.index("organismo") + 1
        escribir(nombre, filas, campos[:i] + ["organismo_id", "codigo_seccion_departamento", "ministerio_actual"] + campos[i:])
    print(f"{len(canon)} organismos distintos en {len({r['anio'] for r in tabla})} años")


if __name__ == "__main__":
    main()
