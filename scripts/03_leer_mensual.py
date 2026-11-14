"""Lector de la Estadística mensual de ejecución del Presupuesto (IGAE), mes de diciembre: último año sin liquidación.

Entrada: fuentes/igae/mensual/mensual_12-AA.pdf (p. ej. mensual_12-25.pdf para 2025)
Salida:  datos/mensual_secciones.csv, con las mismas columnas que datos/liquidacion_secciones.csv
         (miles de euros de la IGAE convertidos a euros) y la marca «provisional».
Tablas: «Modificaciones de crédito. Por secciones» y «Estado de ejecución. Secciones» (dos páginas: definitivos y
obligaciones; pagos). La mensual no publica los créditos iniciales: se obtienen como definitivos menos el total de
modificaciones. Los códigos de sección salen de los nombres abreviados de la última liquidación leída (misma
estructura de ministerios).
Uso: python scripts/03_leer_mensual.py
"""
import csv
import importlib.util
import re
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MENSUAL = RAIZ / "fuentes" / "igae" / "mensual"
TXT = RAIZ / "fuentes" / "igae" / "_texto"
DATOS = RAIZ / "datos"

spec = importlib.util.spec_from_file_location("liq", RAIZ / "scripts" / "01_leer_liquidacion.py")
liq = importlib.util.module_from_spec(spec)
spec.loader.exec_module(liq)


def paginas(pdf):
    txt = TXT / (pdf.stem + ".txt")
    if not txt.exists() or txt.stat().st_mtime < pdf.stat().st_mtime:
        subprocess.run(["pdftotext", "-layout", str(pdf), str(txt)], check=True)
    return txt.read_text(encoding="utf-8").split("\f")


def tabla(pags, titulo, n_min, exigir=None):
    out = []
    for i, p in enumerate(pags, 1):
        cab = "\n".join(p.splitlines()[:16])
        if titulo in cab and (exigir is None or exigir in cab):
            out += [(n, v, i) for n, v in liq.filas_tabla(p, n_min) if n != "TOTALES"]
    return out


def main():
    with open(DATOS / "liquidacion_secciones.csv", encoding="utf-8") as fh:
        liq_sec = list(csv.DictReader(fh, delimiter=";"))
    ultimo = max(int(r["anio"]) for r in liq_sec)
    codigo = {r["seccion_abreviada"]: r["codigo_seccion"] for r in liq_sec if int(r["anio"]) == ultimo}
    largo = {r["codigo_seccion"]: r["seccion"] for r in liq_sec if int(r["anio"]) == ultimo}
    filas = []
    for pdf in sorted(MENSUAL.glob("mensual_12-*.pdf")):
        anio = 2000 + int(re.search(r"12-(\d\d)", pdf.name).group(1))
        if anio <= ultimo:
            continue                                   # ya hay liquidación de ese año
        pags = paginas(pdf)
        mods = tabla(pags, "MODIFICACIONES DE CRÉDITO. POR SECCIONES", 10)
        ejec = tabla(pags, "ESTADO DE EJECUCIÓN. SECCIONES", 10, exigir="GASTOS COMPROMETIDOS")
        pagos = tabla(pags, "ESTADO DE EJECUCIÓN. SECCIONES", 10, exigir="PAGOS REALIZADOS")
        assert len(mods) == len(ejec) == len(pagos), (len(mods), len(ejec), len(pagos))
        for (n1, m, p1), (n2, e, p2), (n3, pg, p3) in zip(mods, ejec, pagos):
            assert n1 == n2 == n3, (n1, n2, n3)
            c = codigo[n1]
            ext, sup, amp, tpos, tneg, inc, gen, bajas, otras, total = m[:10]
            definitivos, obligaciones, pag = e[0], e[6], pg[0]
            assert abs(ext + sup + amp + tpos + tneg + inc + gen + bajas + otras - total) <= 10, (n1, m)
            filas.append(dict(
                anio=anio, codigo_seccion=c, seccion=largo[c], seccion_abreviada=n1, hay_anexo="no",
                creditos_iniciales=(definitivos - total) * 1000,
                creditos_extraordinarios_suplementos=(ext + sup) * 1000, ampliaciones=amp * 1000,
                transferencias=(tpos + tneg) * 1000, incorporacion_remanentes=inc * 1000,
                generaciones_ingresos=gen * 1000, bajas_otras_modificaciones=(bajas + otras) * 1000,
                creditos_definitivos=definitivos * 1000, obligaciones=obligaciones * 1000, pagos=pag * 1000,
                fuente=f"IGAE, Estadística mensual de ejecución, diciembre de {anio} (provisional), pp. {p1}, {p2} y "
                       f"{p3} (miles de euros); iniciales = definitivos - total de modificaciones",
                # control: la columna «2024» de la mensual debe coincidir con la liquidación de 2024
                _def_prev=e[1] * 1000, _obl_prev=e[7] * 1000, _pag_prev=pg[1] * 1000))
        prev = {r["codigo_seccion"]: r for r in liq_sec if int(r["anio"]) == anio - 1}
        dif = max(max(abs(r["_def_prev"] - float(prev[r["codigo_seccion"]]["creditos_definitivos"].replace(",", "."))),
                      abs(r["_obl_prev"] - float(prev[r["codigo_seccion"]]["obligaciones"].replace(",", "."))),
                      abs(r["_pag_prev"] - float(prev[r["codigo_seccion"]]["pagos"].replace(",", "."))))
                  for r in filas if r["anio"] == anio and r["codigo_seccion"] in prev)
        print(f"{anio}: {sum(r['anio'] == anio for r in filas)} secciones; columna {anio - 1} de la mensual frente a "
              f"la liquidación de {anio - 1}: diferencia máxima {dif:,.0f} €")
    campos = ["anio", "codigo_seccion", "seccion", "seccion_abreviada", "hay_anexo"] + liq.MODS + \
             ["obligaciones", "pagos", "fuente"]
    liq.escribir("mensual_secciones.csv", filas, campos)


if __name__ == "__main__":
    main()
