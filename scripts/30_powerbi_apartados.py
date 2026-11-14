"""Prepara las tablas de Power BI de los apartados 7 a 13, 16 y 17 de preguntas.md.

Lee los CSV de datos/ (ya verificados en sus scripts) y escribe en powerbi/ los CSV que carga el modelo,
con el ministerio con su nombre corto (el de dim_ministerio) y sin la columna de fuente. No calcula
cifras nuevas: solo une, renombra y descarta filas de total (22 ministerios), que el modelo vuelve a
sumar. Los apartados 14 (euros constantes) y 15 (ministerio de entonces) ya están en las páginas 1 a 8.

Salidas (powerbi/):
  fact_catastrofe.csv            apartado 7  (datos/catastrofes_ministerio.csv)
  fact_catastrofe_destino.csv    apartado 7  (datos/catastrofes_destino.csv)
  fact_credito_nuevo.csv         apartado 8  (datos/credito_nuevo_resumen.csv)
  fact_contratacion_gasto.csv    apartado 9  (datos/contratacion_gasto.csv)
  fact_concentracion.csv         apartado 10 (datos/concentracion_ministerio.csv)
  fact_ejecucion.csv             apartados 11, 12 y 13 (datos/sobre_inicial_ministerio.csv,
                                 remanentes_ministerio.csv y pendiente_pago_ministerio.csv, por año y ministerio)
  fact_bdns.csv                  apartado 16 (datos/bdns_resumen.csv)
  fact_bdns_instrumento.csv      apartado 16 (datos/bdns_ministerio.csv)
  fact_mensual.csv               apartado 17 (datos/mensual_ministerio_mes.csv)
y datos/controles_powerbi_apartados.csv (comprobaciones contra los CSV de origen).

Después: ejecutar 15_informe_powerbi.py (tablas, medidas y páginas del modelo).
Uso: python scripts/30_powerbi_apartados.py
"""
import csv, os, sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(RAIZ, "datos") + os.sep
P = os.path.join(RAIZ, "powerbi") + os.sep


def leer(ruta):
    with open(ruta, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def num(s):
    return float(s.replace(",", ".")) if s not in ("", None) else 0.0


def escribir(nombre, cols, filas):
    with open(P + nombre, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";", lineterminator="\r\n")
        w.writerow(cols)
        for r in filas:
            w.writerow([r[c] for c in cols])


CORTO = {r["ministerio"]: r["ministerio_corto"] for r in leer(P + "dim_ministerio.csv")}
controles = []


def control(nombre, valor, esperado, tol=0.5):
    ok = abs(valor - esperado) <= tol
    controles.append({"comprobacion": nombre, "valor": f"{valor:.2f}".replace(".", ","),
                      "esperado": f"{esperado:.2f}".replace(".", ","), "resultado": "OK" if ok else "FALLA"})
    if not ok:
        print("FALLA:", nombre, valor, esperado)


def ministerio(fila, campo="ministerio_actual"):
    n = fila[campo]
    return CORTO.get(n, n)


def sin_total(filas, campo="ministerio_actual"):
    """Quita las filas de total («22 ministerios»), que el modelo suma por su cuenta."""
    return [r for r in filas if not r[campo].startswith("22 ministerios")]


def convertir(filas, campo="ministerio_actual"):
    for r in filas:
        r["ministerio"] = ministerio(r, campo)
    return filas


# ---- 7. catástrofes
o = leer(D + "catastrofes_ministerio.csv")
for r in o:
    r["ministerio"] = ministerio(r)
    r["medida"] = r["medida"] or "Sin desglose por medida"
cols = ["suceso_nombre", "medida", "anio", "dato", "ministerio", "tipo_seccion", "lineas", "creditos_iniciales",
        "creditos_definitivos", "obligaciones"]
escribir("fact_catastrofe.csv", cols, o)
res = leer(D + "catastrofes_resumen.csv")
control("catástrofes: obligaciones por ministerio = resumen", sum(num(r["obligaciones"]) for r in o),
        sum(num(r["obligaciones"]) for r in res), 1)
control("catástrofes: definitivos por ministerio = resumen", sum(num(r["creditos_definitivos"]) for r in o),
        sum(num(r["creditos_definitivos"]) for r in res), 1)
d = leer(D + "catastrofes_destino.csv")
escribir("fact_catastrofe_destino.csv", ["suceso_nombre", "destino", "anio", "lineas", "creditos_definitivos", "obligaciones"], d)
control("catástrofes: obligaciones por destino = resumen", sum(num(r["obligaciones"]) for r in d),
        sum(num(r["obligaciones"]) for r in res), 1)

# ---- 8. crédito nuevo
o = leer(D + "credito_nuevo_resumen.csv")
for r in o:
    r["mecanismo"] = "Mecanismo de Recuperación" if r["mecanismo"] == "sí" else "Resto del presupuesto"
cols = ["anio", "mecanismo", "grupo", "lineas", "creditos_iniciales", "creditos_definitivos", "obligaciones",
        "creditos_definitivos_sin_cap8", "obligaciones_sin_cap8"]
escribir("fact_credito_nuevo.csv", cols, o)
control("crédito nuevo: filas", len(o), len(leer(D + "credito_nuevo_resumen.csv")), 0)
control("crédito nuevo: obligaciones", sum(num(r["obligaciones"]) for r in o),
        sum(num(r["obligaciones"]) for r in leer(D + "credito_nuevo_resumen.csv")), 1)

# ---- 9. contratación frente a gasto
o = convertir(sin_total(leer(D + "contratacion_gasto.csv")))
cols = ["ministerio", "anio", "continuidad", "nivel_contratacion", "composicion", "gasto_agregado", "personal",
        "compras_inversiones", "prestamos_aportaciones", "transferencias_y_resto", "pct_compras_inversiones",
        "adjudicaciones", "licitaciones_ordinario", "menores_ordinario", "contratacion_ordinaria",
        "programas_especiales", "adjudicado_total", "pct_ordinaria_sobre_gasto",
        "pct_adjudicado_sobre_compras_inversiones"]
escribir("fact_contratacion_gasto.csv", cols, o)
control("contratación-gasto: filas", len(o), len(leer(D + "contratacion_gasto.csv")), 0)
control("contratación-gasto: gasto agregado", sum(num(r["gasto_agregado"]) for r in o),
        sum(num(r["gasto_agregado"]) for r in leer(D + "contratacion_gasto.csv")), 1)

# ---- 10. concentración
o = convertir(sin_total(leer(D + "concentracion_ministerio.csv")))
cols = ["anio", "dato", "ministerio", "continuidad", "aplicaciones_con_obligaciones", "obligaciones", "pct_primera",
        "pct_cinco_primeras", "n50", "n80", "n95", "primera_obligaciones", "primera_programa", "primera_capitulo",
        "primera_destino"]
escribir("fact_concentracion.csv", cols, o)
control("concentración: obligaciones", sum(num(r["obligaciones"]) for r in o),
        sum(num(r["obligaciones"]) for r in sin_total(leer(D + "concentracion_ministerio.csv"))), 1)
control("concentración: obligaciones = total «22 ministerios» del origen", sum(num(r["obligaciones"]) for r in o),
        sum(num(r["obligaciones"]) for r in leer(D + "concentracion_ministerio.csv") if r["ministerio_actual"].startswith("22 ")), 1)

# ---- 11, 12 y 13: una fila por año y ministerio
si = convertir(sin_total(leer(D + "sobre_inicial_ministerio.csv")))
rm = {(r["anio"], r["ministerio_actual"]): r for r in sin_total(leer(D + "remanentes_ministerio.csv"))}
pp = {(r["anio"], r["ministerio_actual"]): r for r in sin_total(leer(D + "pendiente_pago_ministerio.csv"))}
assert set(rm) == {(r["anio"], r["ministerio_actual"]) for r in si} == set(pp), "claves distintas"
for r in si:
    k = (r["anio"], r["ministerio_actual"])
    a, b = rm[k], pp[k]
    assert num(a["creditos_definitivos"]) == num(r["creditos_definitivos"]), k
    assert num(a["obligaciones"]) == num(r["obligaciones"]) == num(b["obligaciones"]), k
    r["pagos"] = b["pagos"]
    r["pendiente_de_pago"] = b["pendiente_de_pago"]
    r["sin_reconocer"] = a["sin_reconocer"]
    r["mrr_sin_reconocer"] = a["mrr_sin_reconocer"]
    r["incorporacion_anio_siguiente"] = a["incorporacion_anio_siguiente"]
    r["sin_incorporar"] = a["sin_incorporar"]
cols = ["anio", "ministerio", "presupuesto", "dato", "continuidad", "comparable", "creditos_iniciales",
        "creditos_extraordinarios_suplementos", "ampliaciones", "transferencias", "incorporacion_remanentes",
        "generaciones_ingresos", "bajas_otras_modificaciones", "creditos_definitivos", "obligaciones", "pagos",
        "pendiente_de_pago", "sin_reconocer", "mrr_sin_reconocer", "incorporacion_anio_siguiente", "sin_incorporar"]
escribir("fact_ejecucion.csv", cols, si)
control("ejecución: filas", len(si), len(sin_total(leer(D + "sobre_inicial_ministerio.csv"))), 0)
control("ejecución: pendiente de pago", sum(num(r["pendiente_de_pago"]) for r in si),
        sum(num(r["pendiente_de_pago"]) for r in sin_total(leer(D + "pendiente_pago_ministerio.csv"))), 1)
control("ejecución: sin reconocer", sum(num(r["sin_reconocer"]) for r in si),
        sum(num(r["sin_reconocer"]) for r in sin_total(leer(D + "remanentes_ministerio.csv"))), 1)

# ---- 16. BDNS
o = convertir(sin_total(leer(D + "bdns_resumen.csv")))
cols = ["anio", "ministerio", "continuidad", "concesiones", "concesiones_sin_importe", "subvenciones_y_ayudas_directas",
        "concesiones_ayudas_directas", "prestamos", "garantias", "ventajas_fiscales", "importe_total_leido",
        "obligaciones_cap4_cap7_estado", "pct_ayudas_directas_sobre_cap4_cap7", "importe_completo"]
escribir("fact_bdns.csv", cols, o)
control("BDNS: concesiones", sum(num(r["concesiones"]) for r in o),
        sum(num(r["concesiones"]) for r in leer(D + "bdns_resumen.csv") if not r["ministerio_actual"].startswith("22 ")), 0)
o = convertir(sin_total(leer(D + "bdns_ministerio.csv")))
escribir("fact_bdns_instrumento.csv", ["anio", "ministerio", "instrumento", "concesiones", "importe",
                                       "concesiones_sin_importe", "importe_completo"], o)
control("BDNS por instrumento: importe", sum(num(r["importe"]) for r in o),
        sum(num(r["importe"]) for r in leer(D + "bdns_ministerio.csv") if not r["ministerio_actual"].startswith("22 ")), 1)

# ---- 17. calendario mensual
o = convertir(sin_total(leer(D + "mensual_ministerio_mes.csv")))
cols = ["anio", "mes", "ministerio", "dato", "obligaciones_acumuladas", "pagos_acumulados", "creditos_definitivos",
        "obligaciones_del_mes", "pct_del_anio", "pct_pagado"]
escribir("fact_mensual.csv", cols, o)
control("mensual: filas", len(o), 2 * 12 * 22, 0)
control("mensual: obligaciones del mes (suma de meses = acumulado de diciembre)",
        sum(num(r["obligaciones_del_mes"]) for r in o),
        sum(num(r["obligaciones_acumuladas"]) for r in o if r["mes"] == "12"), 5)

with open(D + "controles_powerbi_apartados.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["comprobacion", "valor", "esperado", "resultado"], delimiter=";", lineterminator="\r\n")
    w.writeheader()
    w.writerows(controles)
fallos = [c for c in controles if c["resultado"] != "OK"]
print(f"{len(controles)} comprobaciones, {len(fallos)} fallos")
sys.exit(1 if fallos else 0)
