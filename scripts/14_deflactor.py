"""Factores para pasar euros corrientes a euros constantes de 2025.

Tres índices (importe en euros de 2025 = importe × factor; factor = índice de 2025 / índice del año):

1. IPC general (INE). Responde a «cuánto vale hoy ese dinero» para un ciudadano.
   - 2017-2023: INE, IPC base 2021, índice general nacional, media anual (tabla 70172,
     https://ine.es/jaxiT3/files/t/en/csv/70172.csv), con tres decimales.
   - 2024 y 2025: se encadenan las tasas de variación de la media anual publicadas por el INE
     (2,8 % y 2,7 %; nota de Funcas sobre el IPC de diciembre de 2025). Error máximo por
     redondeo: unas 5 centésimas de punto.
2. Deflactor implícito del PIB (INE). Precios de toda la economía.
3. Deflactor del gasto en consumo final de las Administraciones Públicas (INE). Precios de lo que
   compran las AAPP (sobre todo salarios públicos, bienes y servicios): el más adecuado para ver si
   el gasto público crece en términos reales.
   - 2 y 3: INE, Contabilidad Nacional Anual de España, Revisión Estadística 2024, fichero
     https://ine.es/daco/daco42/cne24/pib95_25.xlsx (publicado el 18/09/2026; 2024 provisional,
     2025 avance). Deflactor = precios corrientes (Tabla 1) / (precios corrientes de 2020 ×
     índice de volumen encadenado 2020 = 100 (Tabla 4) / 100) × 100.
   - Contraste con la nota de prensa CNA2025: deflactor del PIB 6,2 % en 2023 y 3,1 % en 2024,
     igual que aquí; para 2025 la nota da 2,9 % y la tabla da 3,0 % (REGISTRO A20).

Salida: powerbi/deflactor.csv
"""
import csv
import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANIOS = range(2017, 2026)

IPC_BASE_2021 = {2017: 95.046, 2018: 96.638, 2019: 97.314, 2020: 97.000, 2021: 100.000,
                 2022: 108.391, 2023: 112.219}
TASA_MEDIA_IPC = {2024: 2.8, 2025: 2.7}

# INE, pib95_25.xlsx. Millones de euros corrientes (Tabla 1) e índices de volumen encadenados,
# 2020 = 100 (Tabla 4).
PIB_CORRIENTE = {2017: 1170024, 2018: 1212276, 2019: 1253710, 2020: 1129214, 2021: 1235474,
                 2022: 1375863, 2023: 1496277, 2024: 1598588, 2025: 1690012}
PIB_VOLUMEN = {2017: 107.54799751127599, 2018: 110.12422477349401, 2019: 112.283966815727, 2020: 100.0,
               2021: 106.68314420473, 2022: 113.4792323308169, 2023: 116.15722948209525,
               2024: 120.4225003239479, 2025: 123.54389665835244}
AAPP_CORRIENTE = {2017: 215798, 2018: 223673, 2019: 234127, 2020: 245553, 2021: 259441,
                  2022: 275811, 2023: 293914, 2024: 308122, 2025: 324514}
AAPP_VOLUMEN = {2017: 92.591016576160698, 2018: 94.537677074432395, 2019: 96.606176140489893, 2020: 100.0,
                2021: 103.626915574234, 2022: 104.41857358768699, 2023: 108.89347683594924,
                2024: 112.44207173491533, 2025: 115.15019583622846}


def deflactor(corriente, volumen):
    return {a: corriente[a] / (corriente[2020] * volumen[a] / 100) * 100 for a in ANIOS}


def coma(x, d):
    return f"{x:.{d}f}".replace(".", ",")


def main():
    ipc = dict(IPC_BASE_2021)
    for anio in sorted(TASA_MEDIA_IPC):
        ipc[anio] = ipc[anio - 1] * (1 + TASA_MEDIA_IPC[anio] / 100)
    pib = deflactor(PIB_CORRIENTE, PIB_VOLUMEN)
    aapp = deflactor(AAPP_CORRIENTE, AAPP_VOLUMEN)
    with open(os.path.join(RAIZ, "powerbi", "deflactor.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["anio", "ipc_media_base2021", "factor_2025", "deflactor_pib_2020", "factor_pib",
                    "deflactor_aapp_2020", "factor_aapp", "fuente"])
        for a in ANIOS:
            fuente_ipc = ("IPC: INE tabla 70172 (base 2021)" if a in IPC_BASE_2021
                          else f"IPC: encadenado con la tasa media del INE ({coma(TASA_MEDIA_IPC[a], 1)} %)")
            w.writerow([a, coma(ipc[a], 3), coma(ipc[2025] / ipc[a], 6),
                        coma(pib[a], 3), coma(pib[2025] / pib[a], 6),
                        coma(aapp[a], 3), coma(aapp[2025] / aapp[a], 6),
                        fuente_ipc + "; deflactores: INE CNA, pib95_25.xlsx (18/09/2026)"])
            print(a, round(ipc[2025] / ipc[a], 4), round(pib[2025] / pib[a], 4), round(aapp[2025] / aapp[a], 4))


if __name__ == "__main__":
    main()
