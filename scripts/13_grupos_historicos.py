"""Equivalencias año a año entre los 22 ministerios actuales y los ministerios de cada año.

Para cada año y cada ministerio actual dice en qué ministerio de entonces estaban sus
competencias, qué otros ministerios actuales incluía aquel ministerio y una nota. Los
ministerios actuales que en un año compartían ministerio forman un «grupo»; el informe
de Power BI suma el grupo entero cuando se elige cualquiera de sus miembros.

Entrada: datos/secciones_ministerio_actual.csv, datos/equivalencias_secciones.csv,
         powerbi/fact_ministerio_anio.csv, powerbi/dim_ministerio.csv
Salida:  powerbi/dim_grupo.csv

Decisiones (anotadas en REGISTRO.md, B15):
- Cuando un ministerio actual no existía, se asigna a la sección que tenía el grueso de
  sus competencias (tabla TITULAR). Transformación Digital y Función Pública va con la
  parte digital; la Función Pública queda en su sección de cada año y se avisa en la nota.
- Agricultura 2017-2018 está reconstruida a partir de la sección 23, que ya está entera en
  Transición Ecológica: dentro del grupo no se suma su parte del Estado (incluir_estado = 0),
  pero sí sus organismos y las transferencias a ellos.
"""
import csv
import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def leer(rel):
    with open(os.path.join(RAIZ, rel), encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter=";"))


# Ministerio actual (id) -> {año: código de la sección que tenía el grueso de sus competencias}
TITULAR = {
    21: {2017: "23", 2018: "23"},                       # Agricultura, en Agricultura y Medio Ambiente
    22: {2017: "25", 2018: "25"},                       # Política Territorial, en Presidencia y AA. TT.
    24: {2017: "18", 2018: "18"},                       # Cultura, en Educación, Cultura y Deporte
    25: {a: "17" for a in range(2017, 2024)},           # Vivienda, en Fomento / Transportes
    28: {2017: "27", 2018: "27"},                       # Ciencia, en Economía, Industria y Competitividad
    29: {a: "26" for a in range(2017, 2021)},           # Derechos Sociales, en Sanidad
    30: {2017: "26", 2018: "26", 2019: "25", 2020: "25"},  # Igualdad
    31: {**{a: "26" for a in range(2017, 2021)}, **{a: "29" for a in range(2021, 2024)}},  # Juventud e Infancia
    32: {a: "19" for a in range(2017, 2021)},           # Inclusión, SS y Migraciones, en Empleo / Trabajo
    33: {2017: "20", 2018: "20", **{a: "27" for a in range(2019, 2024)}},  # Transformación Digital
}
AVISO_EXTRA = {
    33: "La Función Pública, que hoy también es de este ministerio, estaba entonces en {fp} y no se incluye aquí.",
}
FUNCION_PUBLICA = {2017: "Hacienda y Función Pública", 2018: "Hacienda y Función Pública",
                   2019: "Política Territorial y Función Pública", 2020: "Política Territorial y Función Pública",
                   2021: "Política Territorial y Función Pública", 2022: "Hacienda y Función Pública",
                   2023: "Hacienda y Función Pública"}

NOMBRES = {
    "AGRICULT. Y PESCA, ALIM. Y MEDIO AMB.": "Agricultura y Pesca, Alimentación y Medio Ambiente",
    "PRESIDENCIA Y PARA LAS ADM. TERRIT.": "Presidencia y para las Administraciones Territoriales",
    "ASUNTOS EXT, U. E. Y COOPERACIÓN": "Asuntos Exteriores, Unión Europea y Cooperación",
    "TRABAJO, MIGRACIONES Y S.S.": "Trabajo, Migraciones y Seguridad Social",
    "POLÍTICA TERRITORIAL Y FUNCIÓN PÚB.": "Política Territorial y Función Pública",
    "PRESIDENCIA, REL., CORTES E IGUALDAD": "Presidencia, Relaciones con las Cortes e Igualdad",
}
MINUSCULAS = {"y", "e", "de", "del", "la", "las", "el", "para", "con", "los"}


def bonito(seccion):
    s = seccion.strip()
    if s in NOMBRES:
        return NOMBRES[s]
    for pref in ("MINISTERIO PARA LA ", "MINISTERIO DE LA ", "MINISTERIO DEL ", "MINISTERIO DE "):
        if s.startswith(pref):
            s = s[len(pref):]
            break
    palabras = []
    for i, p in enumerate(s.lower().split(" ")):
        palabras.append(p if (i > 0 and p in MINUSCULAS) else p[:1].upper() + p[1:])
    return " ".join(palabras)


def main():
    dim = leer("powerbi/dim_ministerio.csv")
    corto = {int(d["ministerio_id"]): d["ministerio_corto"] for d in dim if d["es_ministerio"] == "sí"}
    id_por_nombre = {d["ministerio"]: int(d["ministerio_id"]) for d in dim}
    fact = leer("powerbi/fact_ministerio_anio.csv")
    filas = {(int(f["anio"]), int(f["ministerio_id"])): f["continuidad"] for f in fact}
    secciones = [s for s in leer("datos/secciones_ministerio_actual.csv") if s["tipo"] == "Ministerio"]
    notas = {}
    for e in leer("datos/equivalencias_secciones.csv"):
        for a in range(int(e["anio_desde"]), int(e["anio_hasta"]) + 1):
            notas[(a, e["codigo_seccion"], e["seccion_igae"])] = e["nota"].strip()

    salida = []
    for anio in range(2017, 2026):
        sec = {s["codigo_seccion"]: s for s in secciones if int(s["anio"]) == anio}
        dueno = {c: id_por_nombre[s["ministerio_actual"]] for c, s in sec.items()}  # sección -> ministerio actual
        padre = {m: m for m in corto}

        def raiz(m):
            while padre[m] != m:
                m = padre[m]
            return m

        for m, por_anio in TITULAR.items():
            if anio in por_anio:
                c = por_anio[anio]
                assert c in sec, (anio, m, c)
                padre[raiz(m)] = raiz(dueno[c])
        for m in corto:
            assert (anio, m) in filas or anio in TITULAR.get(m, {}), f"{anio}: falta titular para {m}"
        grupos = {}
        for m in corto:
            grupos.setdefault(raiz(m), []).append(m)
        for miembros in grupos.values():
            miembros.sort()
            codigos = sorted(c for c, d in dueno.items() if d in miembros)
            nombres = [bonito(sec[c]["seccion"]) for c in codigos]
            nombre_grupo = " + ".join(nombres)
            gid = f"{anio}-{miembros[0]}"
            for m in miembros:
                otros = [corto[o] for o in miembros if o != m]
                otros_txt = ", ".join(otros[:-1]) + (" y " if len(otros) > 1 else "") + otros[-1] if otros else ""
                propio = (anio, m) in filas and filas[(anio, m)] != "reconstruido"
                if not propio:
                    c = TITULAR[m][anio]
                    rel = f"No existía como ministerio propio: sus competencias estaban en «{bonito(sec[c]['seccion'])}»"
                    rel += f", que también incluía lo que hoy es {otros_txt}." if otros else "."
                    existia = "no"
                elif len(miembros) == 1 and len(codigos) == 1 and filas[(anio, m)] == "directa":
                    rel = "Existía con el mismo perímetro que hoy."
                    existia = "sí"
                else:
                    existia = "sí"
                    if len(codigos) > 1:
                        rel = "Sus competencias estaban repartidas en " + " y ".join(f"«{n}»" for n in nombres)
                        rel += f", que también incluían lo que hoy es {otros_txt}" if otros else ""
                        rel += "; se muestran sumados."
                    else:
                        rel = f"Entonces era «{nombres[0]}»"
                        rel += f", que también incluía lo que hoy es {otros_txt}." if otros else ", con un perímetro distinto del actual."
                    nota = " ".join(n if n.endswith(".") else n + "." for n in
                                    sorted({notas.get((anio, c, sec[c]["seccion"]), "") for c in codigos} - {""}))
                    if nota:
                        rel += " " + nota
                if m in AVISO_EXTRA and anio in FUNCION_PUBLICA:
                    rel += " " + AVISO_EXTRA[m].format(fp=f"«{FUNCION_PUBLICA[anio]}»")
                salida.append({
                    "anio": anio, "ministerio_id": m, "grupo_id": gid,
                    "ministerio_entonces": nombre_grupo,
                    "secciones_entonces": ", ".join(codigos),
                    "compuesto_por": "; ".join(corto[o] for o in miembros),
                    "existia": existia,
                    "relacion": rel,
                    "incluir_estado": 0 if (anio, m) in filas and filas[(anio, m)] == "reconstruido" else 1,
                })

    campos = list(salida[0].keys())
    with open(os.path.join(RAIZ, "powerbi", "dim_grupo.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos, delimiter=";")
        w.writeheader()
        w.writerows(salida)
    print(f"dim_grupo.csv: {len(salida)} filas, {len({s['grupo_id'] for s in salida})} grupos")


if __name__ == "__main__":
    main()
