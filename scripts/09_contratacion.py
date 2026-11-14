"""Contratación por ministerio actual, desde la línea base del proyecto «Gasto de fin de ejercicio en la contratación
de Defensa» (fichero linea_base_cierre.csv, copiado sin cambios en fuentes/contratacion/).

Reglas heredadas (las mismas para todos los órganos de la PLACSP):
- Licitaciones adjudicadas (sindicación 643) y contratos menores (sindicación 1143, desde 2018), con IVA.
- Fuera: establecimiento de acuerdos marco y sistemas dinámicos (su importe es un techo, no un gasto) y anuladas.
- «Programa especial»: expediente con adjudicaciones de 100 M€ o más en un año (euros de 2025); el «importe
  ordinario» es el resto. Contratos menores de más de 60.500 € con IVA: error de importe, fuera del ordinario.
- Ministerio: el actual del órgano por su jerarquía en la plataforma (organismos autónomos y agencias dentro;
  ADIF, Renfe, Aena, Correos y demás sociedades, fuera). En Defensa, la serie llamada «sección 14» en el proyecto
  anterior ya incluye el INTA, el INVIED y el ISFAS (la plataforma los cuelga de la Secretaría de Estado y de la
  Subsecretaría); fuera quedan las sociedades ISDEFE y SAES, los consorcios y el Centro Universitario de la Defensa de
  Madrid (31 registros), como las sociedades y consorcios de los demás ministerios.
- 2026 llega hasta el 23/10/2026: incompleto.

Salidas (datos/):
  contratacion_ministerio.csv  ministerio × año × tipo de procedimiento (licitación / menor): adjudicaciones,
      importe, programas especiales, importe ordinario, peso de noviembre-diciembre, oferta única, negociado sin
      publicidad, urgencia o emergencia y baja media; y lo mismo para «resto de la AGE» (la AGE sin ese ministerio).
  contratacion_tipo.csv        ministerio × año × tipo de contrato (suministros, servicios, obras, otros):
      importe ordinario de licitaciones y su peso.
"""
import csv
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
FUENTE = RAIZ / "fuentes" / "contratacion" / "linea_base_cierre.csv"
DATOS = RAIZ / "datos"
SUMABLES = ["n_adjudicaciones", "importe_con_iva_eur", "n_programa_especial", "importe_programa_especial_eur",
            "n_ordinario", "importe_ordinario_eur", "n_con_ofertas", "n_oferta_unica", "n_negociado_sin_publicidad",
            "n_urgente_o_emergencia", "n_con_baja", "suma_baja"]


def f(x):
    return float(x.replace(",", ".")) if x not in ("", None) else 0.0


def fmt(x):
    if x is None:
        return ""
    if isinstance(x, float):
        return str(int(round(x))) if x.is_integer() else f"{x:.4f}".rstrip("0").replace(".", ",")
    return x


def indicadores(t, nd):
    """t: sumas del año; nd: sumas de noviembre-diciembre."""
    d = dict(adjudicaciones=t["n_adjudicaciones"], importe_total=t["importe_con_iva_eur"],
             programas_especiales_n=t["n_programa_especial"], programas_especiales_importe=t["importe_programa_especial_eur"],
             importe_ordinario=t["importe_ordinario_eur"])
    d["pct_importe_ordinario_nov_dic"] = 100 * nd["importe_ordinario_eur"] / t["importe_ordinario_eur"] if t["importe_ordinario_eur"] else None
    d["pct_adjudicaciones_nov_dic"] = 100 * nd["n_adjudicaciones"] / t["n_adjudicaciones"] if t["n_adjudicaciones"] else None
    d["pct_oferta_unica"] = 100 * t["n_oferta_unica"] / t["n_con_ofertas"] if t["n_con_ofertas"] else None
    d["pct_negociado_sin_publicidad"] = 100 * t["n_negociado_sin_publicidad"] / t["n_adjudicaciones"] if t["n_adjudicaciones"] else None
    d["pct_urgente_o_emergencia"] = 100 * t["n_urgente_o_emergencia"] / t["n_adjudicaciones"] if t["n_adjudicaciones"] else None
    d["baja_media_pct"] = t["suma_baja"] / t["n_con_baja"] if t["n_con_baja"] else None
    return d


def main():
    with open(FUENTE, encoding="utf-8-sig") as fh:
        filas = [r for r in csv.DictReader(fh, delimiter=";") if r["bloque"] in ("Defensa", "Resto de la AGE")]
    tot = defaultdict(lambda: defaultdict(float))       # (grupo, año, menor, periodo) -> sumas
    tipo = defaultdict(float)
    for r in filas:
        for per in (r["periodo"], "año"):
            x = tot[(r["grupo"], int(r["anio"]), r["es_contrato_menor"], per)]
            for c in SUMABLES:
                x[c] += f(r[c])
        if r["es_contrato_menor"] == "No":
            tipo[(r["grupo"], int(r["anio"]), r["tipo_contrato"])] += f(r["importe_ordinario_eur"])
    grupos = sorted({k[0] for k in tot if k[0].startswith("Ministerio")})
    anios = sorted({k[1] for k in tot})
    out = []
    for g in grupos:
        for a in anios:
            for menor, nombre in (("No", "licitación"), ("Sí", "contrato menor")):
                t = tot.get((g, a, menor, "año"))
                if not t or not t["n_adjudicaciones"]:
                    continue
                nd = tot.get((g, a, menor, "Nov-dic"), defaultdict(float))
                fila = dict(ministerio_actual=g, anio=a, procedimiento=nombre,
                            completo="no (hasta 23/10/2026)" if a == 2026 else "sí", **indicadores(t, nd))
                # resto de la AGE: todos los ministerios menos este (incluye «ministerio sin identificar»)
                rt, rnd = defaultdict(float), defaultdict(float)
                for (gg, aa, mm, per), x in tot.items():
                    if gg == g or aa != a or mm != menor or per not in ("año", "Nov-dic"):
                        continue
                    destino = rt if per == "año" else rnd
                    for c in SUMABLES:
                        destino[c] += x[c]
                ri = indicadores(rt, rnd)
                for k in ("pct_importe_ordinario_nov_dic", "pct_adjudicaciones_nov_dic", "pct_oferta_unica",
                          "pct_negociado_sin_publicidad", "pct_urgente_o_emergencia", "baja_media_pct"):
                    fila[f"resto_age_{k}"] = ri[k]
                fila["fuente"] = ("PLACSP, línea base del proyecto «Gasto de fin de ejercicio en la contratación de Defensa» "
                                  "(linea_base_cierre.csv)")
                out.append(fila)
    campos = ["ministerio_actual", "anio", "procedimiento", "completo", "adjudicaciones", "importe_total",
              "programas_especiales_n", "programas_especiales_importe", "importe_ordinario",
              "pct_importe_ordinario_nov_dic", "pct_adjudicaciones_nov_dic", "pct_oferta_unica",
              "pct_negociado_sin_publicidad", "pct_urgente_o_emergencia", "baja_media_pct",
              "resto_age_pct_importe_ordinario_nov_dic", "resto_age_pct_adjudicaciones_nov_dic",
              "resto_age_pct_oferta_unica", "resto_age_pct_negociado_sin_publicidad",
              "resto_age_pct_urgente_o_emergencia", "resto_age_baja_media_pct", "fuente"]
    with open(DATOS / "contratacion_ministerio.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(campos)
        for r in out:
            w.writerow([fmt(r.get(k)) for k in campos])
    filas_t = []
    for g in grupos:
        for a in anios:
            total = sum(v for (gg, aa, _), v in tipo.items() if gg == g and aa == a)
            for t in ("Suministros", "Servicios", "Obras", "Otros"):
                v = tipo.get((g, a, t), 0.0)
                if total:
                    filas_t.append(dict(ministerio_actual=g, anio=a, tipo_contrato=t, importe_ordinario=v,
                                        pct=100 * v / total))
    with open(DATOS / "contratacion_tipo.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["ministerio_actual", "anio", "tipo_contrato", "importe_ordinario", "pct"])
        for r in filas_t:
            w.writerow([fmt(r[k]) for k in ("ministerio_actual", "anio", "tipo_contrato", "importe_ordinario", "pct")])
    print(f"{len(out)} filas ministerio-año-procedimiento; {len(filas_t)} filas por tipo")


if __name__ == "__main__":
    main()
