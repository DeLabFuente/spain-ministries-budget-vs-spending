# Modelo de Power BI

El informe es un proyecto de Power BI en formato PBIP (`presupuesto_al_gasto.pbip`): el modelo y las páginas son archivos de texto en `presupuesto_al_gasto.SemanticModel/` y `presupuesto_al_gasto.Report/`. No hace falta montarlo a mano: lo generan los scripts.

## 1. Regenerar el informe

```
python scripts/12_powerbi.py          # CSV del modelo a partir de datos/
python scripts/13_grupos_historicos.py   # powerbi/dim_grupo.csv (qué ministerio había cada año)
python scripts/14_deflactor.py        # powerbi/deflactor.csv (IPC y deflactores del INE)
python scripts/30_powerbi_apartados.py  # CSV de los apartados 7 a 13, 16 y 17 (fact_catastrofe, fact_ejecucion…)
python scripts/15_informe_powerbi.py  # modelo semántico, tema y las 15 páginas
```

Después: cerrar Power BI Desktop si estaba abierto, abrir `presupuesto_al_gasto.pbip`, pulsar **Inicio → Actualizar** (las tablas calculadas y `dim_grupo` solo se cargan al actualizar) y guardar.

- El script 15 es idempotente: se puede ejecutar las veces que haga falta. Reescribe las medidas, las tablas `Pasos`, `Euros`, `dim_grupo`, `dim_gobierno` y `dim_anio`, las relaciones, el tema (`StaticResources/RegisteredResources/PresupuestoAlGasto.json`, registrado en `report.json`) y las 15 páginas, y escribe las nueve tablas `fact_*` de los apartados 7 a 13, 16 y 17; no toca el resto de tablas.
- **Los cambios del informe se hacen en el script 15**, no en Power BI Desktop: lo que se retoque a mano en una página se pierde al volver a ejecutarlo. Con `python scripts/15_informe_powerbi.py <carpeta>` escribe en otra carpeta y deja `powerbi/` intacto, para comparar.
- Requisitos ya guardados en el proyecto: configuración regional «Español (España)» (los CSV llevan coma decimal y punto y coma) y el parámetro `RutaProyecto` con la ruta de la carpeta del proyecto terminada en `\`. Si se mueve la carpeta, solo hay que cambiar el parámetro (Inicio → Transformar datos → Editar parámetros). **En la copia publicada en GitHub el parámetro viene con un marcador** (`C:\RUTA\A\LA\CARPETA\`): hay que sustituirlo por la ruta propia antes de actualizar.

## 2. Tablas

| Tabla | Grano | Qué tiene |
| --- | --- | --- |
| `dim_ministerio` | 1 fila por ministerio actual (22 + «sin identificar», id 99, solo para contratación) | Clave `ministerio_id` = código de su sección en 2024. Nombre corto, perfil de gasto en 2024, nivel A/B/C de contratación e intervalo del estudio de viabilidad |
| `dim_anio` | 2017-2026 | Presupuesto aprobado o prorrogado, tipo de dato, si hay organismos y Mecanismo, si la contratación está completa. Calendario (script 12, a partir de `datos/calendario_*.csv`): días del año, días con presupuesto prorrogado y propio, días con el Gobierno en funciones (y con el presupuesto prorrogado a la vez) y `situacion_presupuesto`, en texto. Une `deflactor.csv`: índices y factores para pasar a euros de 2025 (`factor_2025` del IPC, `factor_pib`, `factor_aapp`) |
| `dim_grupo` | año × ministerio actual (198 filas, 2017-2025) | El ministerio que existía ese año y que contiene al actual (`grupo_id`, `ministerio_entonces`, sus secciones), los ministerios actuales que lo forman (`compuesto_por`), si existía (`existia`), una nota (`relacion`) e `incluir_estado` (0 en Agricultura 2017-2018, ver abajo). Script 13, REGISTRO B15 |
| `dim_gobierno` | 4 filas, una por Gobierno del periodo | Presidente (real decreto), fechas de inicio, de cese en funciones y de fin, motivo, días de mandato, días en funciones, días con presupuesto prorrogado, días en funciones con presupuesto prorrogado y leyes de presupuestos publicadas en el mandato. Sin relaciones; las fechas son texto y se ordenan por `orden`. Script 12 (de `datos/calendario_gobiernos.csv`, script 17) |
| `dim_capitulo` | capítulos 1-9 | Nombre y tipo (corriente, capital, financiero) |
| `Euros` | 4 filas (tabla calculada) | Selector: corrientes, constantes de 2025 con IPC, con deflactor del PIB o con deflactor del consumo público. Sin relaciones |
| `Pasos` | 8 filas (tabla calculada) | Pasos de la cascada del presupuesto. Sin relaciones |
| `fact_ministerio_anio` | sección × año | Estado: iniciales, cada tipo de modificación, definitivos, obligaciones, pagos. Organismos, transferencias restadas, gasto agregado y Mecanismo de Recuperación |
| `fact_capitulo` | sección × año × ámbito × capítulo | Definitivos y obligaciones del Estado (2017-2024) y de los organismos |
| `fact_programa` | sección × año × programa | Programas del Estado, 2020-2024 |
| `fact_mrr_programa` | sección × año × programa × capítulo | Mecanismo de Recuperación 2021-2025 |
| `fact_ingresos_organismos` | sección × año × organismo × origen | Derechos reconocidos por origen (propios, del Estado, de otros, financieros) |
| `fact_catastrofe` | suceso × medida × año × sección | Apartado 7: créditos iniciales, definitivos y obligaciones de las líneas ligadas a cada suceso (script 18). Sin medida: «Sin desglose por medida» |
| `fact_catastrofe_destino` | suceso × destino × año | Apartado 7: obligaciones por tipo de destino (comunidades, empresas, familias…), sin beneficiarios concretos |
| `fact_credito_nuevo` | año × Mecanismo × grupo de líneas | Apartado 8: crédito y obligaciones de las líneas del presupuesto (sin cambio, ampliadas, reducidas), nuevas (anexo II) y sin crédito propio; con y sin capítulo 8 (script 19) |
| `fact_contratacion_gasto` | ministerio actual × año | Apartado 9: gasto agregado y su composición, adjudicado en la Plataforma, nivel de contratación (script 20) |
| `fact_concentracion` | ministerio actual × año | Apartado 10: líneas con obligaciones, peso de la primera y de las cinco primeras, líneas hasta el 50, 80 y 95 % (script 21) |
| `fact_ejecucion` | ministerio actual × año | Apartados 11, 12 y 13: iniciales, cada modificación, definitivos, obligaciones, pagos, pendiente de pago, crédito sin reconocer y su incorporación (scripts 22, 23 y 24) |
| `fact_bdns` | ministerio actual × año | Apartado 16: concesiones y importes por tipo de instrumento y obligaciones de los capítulos 4 y 7 (script 27) |
| `fact_bdns_instrumento` | ministerio actual × año × instrumento | Apartado 16: concesiones e importe de cada instrumento (script 27) |
| `fact_mensual` | ministerio actual × año × mes | Apartado 17: obligaciones y pagos acumulados de 2024 y 2025 (script 28) |
| `fact_contratacion_mes` | ministerio × año × mes × procedimiento × tipo de contrato | Sumas de la línea base de la PLACSP (solo la Administración General del Estado), siempre con el perímetro actual |

En las tablas de presupuesto, `ministerio_id` es la sección **de ese año** (por ejemplo, 23 en 2017 es Agricultura y Pesca, Alimentación y Medio Ambiente).

## 3. Relaciones

De uno a varios, filtro en una dirección:

- `dim_anio[anio]` → `anio` de las seis tablas de hechos y de `dim_grupo`.
- `dim_ministerio[ministerio_id]` → `dim_grupo[ministerio_id]` y `fact_contratacion_mes[ministerio_id]`.
- `dim_capitulo[capitulo]` → `fact_capitulo[capitulo]` y `fact_mrr_programa[capitulo]`.

Las cinco tablas de presupuesto **no** se relacionan con `dim_ministerio`: el ministerio les llega por las medidas, a través de `dim_grupo` (apartado 4).

Las nueve tablas de los apartados 7 a 13, 16 y 17 solo se relacionan con `dim_anio[anio]`. Llevan el ministerio actual como texto (`ministerio`, el nombre corto de `dim_ministerio`; los CSV se prepararon sin las filas de total «22 ministerios», que el modelo suma) y van en euros corrientes: no pasan por `dim_grupo` ni por el selector `Euros`.

## 4. Medidas

Todas en la tabla `_Medidas`, por carpetas. Formato de importes `#,0\ €` (los objetos visuales los muestran en millones con «Unidades de visualización»); porcentajes `0.0\ %`.

### Cómo se elige el ministerio de cada año

Al elegir un ministerio actual, cada año se suma **el ministerio que existía entonces y lo contenía, completo**. Si se elige Igualdad, en 2017 se ve Sanidad, Servicios Sociales e Igualdad; en 2019, Justicia + Presidencia, Relaciones con las Cortes e Igualdad, y desde 2021, Igualdad. Todas las medidas de presupuesto siguen este patrón:

```DAX
Obligaciones =
VAR _k = SELECTEDVALUE ( Euros[orden], 1 )
VAR _grupos = SUMMARIZE ( dim_grupo, dim_grupo[anio], dim_grupo[grupo_id] )
VAR _pares =
    CALCULATETABLE (
        SUMMARIZE ( dim_grupo, dim_grupo[anio], dim_grupo[ministerio_id] ),
        REMOVEFILTERS ( dim_ministerio ), REMOVEFILTERS ( dim_grupo ),
        TREATAS ( _grupos, dim_grupo[anio], dim_grupo[grupo_id] ),
        dim_grupo[incluir_estado] = 1
    )
RETURN
    CALCULATE (
        SUMX ( fact_ministerio_anio,
            fact_ministerio_anio[estado_obligaciones]
                * SWITCH ( _k, 2, RELATED ( dim_anio[factor_2025] ), 3, RELATED ( dim_anio[factor_pib] ),
                               4, RELATED ( dim_anio[factor_aapp] ), 1 ) ),
        TREATAS ( _pares, fact_ministerio_anio[anio], fact_ministerio_anio[ministerio_id] )
    )
```

1. `_grupos`: los grupos (ministerio de entonces) de los ministerios y años filtrados.
2. `_pares`: todos los pares año × sección que forman esos grupos, quitando el filtro de ministerio.
3. `TREATAS` aplica esos pares a la tabla de hechos; `SUMX` multiplica por el factor del selector `Euros` (1 si son euros corrientes).

**`incluir_estado`.** En 2017 y 2018 la Agricultura (id 21) está reconstruida a partir de la sección 23 (REGISTRO B2), que entonces era Agricultura y Pesca, Alimentación y Medio Ambiente. Como el grupo de esos años suma las dos, la parte del Estado de la 21 se contaría dos veces (REGISTRO C13). Por eso esas dos filas tienen `incluir_estado = 0`: las medidas del Estado las excluyen; las de organismos las incluyen, y `Gasto agregado` suma la 21 y le resta sus obligaciones del Estado.

Medidas que usan el patrón (con su columna):

| Carpeta | Medidas |
| --- | --- |
| 9 Catástrofes | `Catástrofes: definitivos`, `Catástrofes: obligaciones`, `Catástrofes: % reconocido`, `Catástrofes por destino: obligaciones` |
| 10 Crédito nuevo y remanentes | `Crédito nuevo: definitivos`, `…: obligaciones`, `…: % reconocido`, `…: % reconocido sin capítulo 8`; `Remanentes: sin reconocer`, `…: incorporado al año siguiente`, `…: sin incorporar`, `…: % sin reconocer`, `…: % incorporado` |
| 11 Inicial, reconocido y pagado | `Ejecución: créditos iniciales`, cada tipo de modificación, `definitivos`, `obligaciones`, `pagos`, `pendiente de pago`, `% pendiente de pago` y `% obligaciones sobre iniciales (años comparables)` (solo filas con `comparable = "sí"`, como el apartado 13) |
| 12 Contratación frente a gasto y concentración | `Contratación y gasto: …` (gasto agregado, composición, adjudicado ordinario y total, programas especiales, `% adjudicado ordinario sobre el gasto`, `% adjudicado total sobre compras e inversiones` solo con composición completa); `Concentración: …` (media de los porcentajes y de las líneas hasta el 50, 80 y 95 %: con un ministerio y un año es el valor del apartado 10) |
| 13 Subvenciones (BDNS) | `BDNS: …` (concesiones, importes por instrumento, `% ayudas directas sobre los capítulos 4 y 7`) y `BDNS por instrumento: …` |
| 14 Calendario mensual | `Mensual: obligaciones acumuladas`, `…del mes`, `pagos acumulados`, `% acumulado del año` (acumulado entre el de diciembre, para cualquier selección), `% pagado` |
| 1 Presupuesto | `Iniciales`, `Créditos extraordinarios y suplementos`, `Ampliaciones`, `Transferencias de crédito`, `Remanentes`, `Generaciones`, `Bajas y otras`, `Modificaciones`, `Definitivos`, `Obligaciones`, `Pagos` (columnas `estado_*`) |
| 2 Organismos y gasto agregado | `Organismos: obligaciones`, `Transferencias del Estado restadas`, `De ellas, de otros ministerios`, `Devuelto al Estado por sus organismos`, `Gasto agregado`, `Organismos: derechos reconocidos` (de `fact_ingresos_organismos`) |
| 3 Mecanismo de Recuperación | `MRR definitivos`, `MRR obligaciones`, `MRR programa: definitivos`, `MRR programa: obligaciones` (de `fact_mrr_programa`) |
| 4 Capítulos | `Obligaciones por capítulo`, `Definitivos por capítulo`: el ámbito Estado con `incluir_estado = 1` y los organismos con todos los pares |

Las demás se calculan a partir de esas y no repiten el patrón:

```DAX
Sin gastar = [Definitivos] - [Obligaciones]
% obligaciones sobre iniciales = DIVIDE ( [Obligaciones], [Iniciales] )
% ejecución = DIVIDE ( [Obligaciones], [Definitivos] )
% modificaciones sobre iniciales = DIVIDE ( [Modificaciones], [Iniciales] )
% pagado = DIVIDE ( [Pagos], [Obligaciones] )
Continuidad = SELECTEDVALUE ( dim_grupo[existia] )

MRR % ejecutado = DIVIDE ( [MRR obligaciones], [MRR definitivos] )
MRR peso en las obligaciones = DIVIDE ( [MRR obligaciones], [Obligaciones] )
MRR sin gastar = [MRR definitivos] - [MRR obligaciones]

Sin gastar por capítulo = [Definitivos por capítulo] - [Obligaciones por capítulo]
% del año = DIVIDE ( [Obligaciones por capítulo], CALCULATE ( [Obligaciones por capítulo], REMOVEFILTERS ( dim_capitulo ) ) )
```

Las de capítulos se usan con un filtro de objeto visual `fact_capitulo[ambito] = "Estado"` (u «Organismos») para no mezclar ámbitos.

### 0 Equivalencias (texto para tarjetas)

```DAX
Ministerio de entonces = SELECTEDVALUE ( dim_grupo[ministerio_entonces] )
Incluye = SELECTEDVALUE ( dim_grupo[compuesto_por] )
Nivel de contratación = SWITCH ( SELECTEDVALUE ( dim_ministerio[nivel_contratacion] ),
    "A", "A · concluyente", "B", "B · solo si coinciden dos indicadores", "C", "C · no concluyente" )
Perfil de gasto = «Perfil (xx % del gasto)» a partir de dim_ministerio[perfil_gasto_2024] y [perfil_pct_2024]
```

### 5 Contratación al cierre del ejercicio

No pasan por `dim_grupo` ni por `Euros`: la contratación se compara siempre con el perímetro actual de los órganos y por cuotas.

```DAX
Importe ordinario =
CALCULATE ( SUM ( fact_contratacion_mes[importe_ordinario_eur] ), fact_contratacion_mes[procedimiento] = "licitación" )

Importe ordinario nov-dic =
CALCULATE ( [Importe ordinario], fact_contratacion_mes[nov_dic] = "sí" )

Cuota nov-dic = DIVIDE ( [Importe ordinario nov-dic], [Importe ordinario] )

Cuota nov-dic AGE sin él =
VAR _sel = VALUES ( dim_ministerio[ministerio_id] )
VAR _resto = FILTER ( ALL ( dim_ministerio[ministerio_id] ), NOT dim_ministerio[ministerio_id] IN _sel )
RETURN
    DIVIDE (
        CALCULATE ( [Importe ordinario nov-dic], REMOVEFILTERS ( dim_ministerio ), _resto ),
        CALCULATE ( [Importe ordinario], REMOVEFILTERS ( dim_ministerio ), _resto )
    )

Diferencia nov-dic (pp) = ( [Cuota nov-dic] - [Cuota nov-dic AGE sin él] ) * 100

Adjudicaciones = CALCULATE ( SUM ( fact_contratacion_mes[n_adjudicaciones] ), fact_contratacion_mes[procedimiento] = "licitación" )
Programas especiales = CALCULATE ( SUM ( fact_contratacion_mes[importe_programa_especial_eur] ), fact_contratacion_mes[procedimiento] = "licitación" )
Oferta única % =
CALCULATE ( DIVIDE ( SUM ( fact_contratacion_mes[n_oferta_unica] ), SUM ( fact_contratacion_mes[n_con_ofertas] ) ), fact_contratacion_mes[procedimiento] = "licitación" )
Negociado sin publicidad % =
CALCULATE ( DIVIDE ( SUM ( fact_contratacion_mes[n_negociado_sin_publicidad] ), SUM ( fact_contratacion_mes[n_adjudicaciones] ) ), fact_contratacion_mes[procedimiento] = "licitación" )
Baja media % = CALCULATE ( DIVIDE ( SUM ( fact_contratacion_mes[suma_baja] ), SUM ( fact_contratacion_mes[n_con_baja] ) ), fact_contratacion_mes[procedimiento] = "licitación" ) * 100
Contratos menores = CALCULATE ( SUM ( fact_contratacion_mes[n_adjudicaciones] ), fact_contratacion_mes[procedimiento] = "contrato menor" )
Contratos menores: importe = CALCULATE ( SUM ( fact_contratacion_mes[importe_ordinario_eur] ), fact_contratacion_mes[procedimiento] = "contrato menor" )

Estudio: diferencia (pp) = SELECTEDVALUE ( dim_ministerio[estudio_dif_pp] )
Estudio: IC 95 % inferior = SELECTEDVALUE ( dim_ministerio[estudio_ic95_inferior] )
Estudio: IC 95 % superior = SELECTEDVALUE ( dim_ministerio[estudio_ic95_superior] )
```

- **2026 está incompleto** (hasta el 23/10): las páginas de contratación filtran `dim_anio[contratacion] = "completo"`.
- **«AGE sin él»** incluye a Defensa y a los órganos sin ministerio identificado (id 99), igual que la comparativa. Sin ningún ministerio filtrado devuelve vacío, porque no hay «resto».
- **Contraste:** con 2017-2025 y un solo ministerio, `Cuota nov-dic` y `Cuota nov-dic AGE sin él` dan lo mismo que `datos/comparativa_contratacion.csv` (diferencia menor de 0,0001 puntos).

### 6 Cascada

```DAX
Importe del paso =
SWITCH ( SELECTEDVALUE ( Pasos[paso] ),
    "Créditos iniciales", [Iniciales],
    "Créd. extraordinarios y suplementos", [Créditos extraordinarios y suplementos],
    "Ampliaciones", [Ampliaciones], "Transferencias de crédito", [Transferencias de crédito],
    "Remanentes", [Remanentes], "Generaciones", [Generaciones], "Bajas y otras", [Bajas y otras],
    "Sin gastar", - [Sin gastar] )
```

En el gráfico de cascada con `Pasos[paso]` (ordenado por `orden`), el total final son las obligaciones reconocidas.

### 7 Valor del dinero

El selector `Euros` cambia todas las medidas de presupuesto y organismos a la vez. Para comparar las cuatro formas en un mismo gráfico hay medidas fijas:

```DAX
Obligaciones: euros corrientes = CALCULATE ( [Obligaciones], REMOVEFILTERS ( Euros ), Euros[orden] = 1 )
Obligaciones: € de 2025 (IPC) = ... Euros[orden] = 2
Obligaciones: € de 2025 (deflactor del PIB) = ... Euros[orden] = 3
Obligaciones: € de 2025 (deflactor del consumo público) = ... Euros[orden] = 4

Factor IPC = MAX ( dim_anio[factor_2025] )
Factor deflactor del PIB = MAX ( dim_anio[factor_pib] )
Factor deflactor del consumo público = MAX ( dim_anio[factor_aapp] )
```

Factor = índice de 2025 / índice del año: 100 € de 2017 son 124,7 € de 2025 con el IPC, 125,7 con el deflactor del PIB y 120,9 con el del consumo público. Los porcentajes de un mismo año no cambian. Script 14, REGISTRO B16 y A20.

### 8 Calendario

Solo leen `dim_anio` (no pasan por `dim_grupo` ni por `Euros`). Los días se cuentan con ambos extremos incluidos y 2026 acaba en la fecha de corte (10/11/2026).

```DAX
Días del año = SUM ( dim_anio[dias_anio] )
Días con presupuesto prorrogado = SUM ( dim_anio[dias_prorrogado] )
Días con presupuesto propio = SUM ( dim_anio[dias_presupuesto_propio] )
% del tiempo con presupuesto prorrogado = DIVIDE ( [Días con presupuesto prorrogado], [Días del año] )
Días con el Gobierno en funciones = SUM ( dim_anio[dias_en_funciones] )
Días en funciones y con presupuesto prorrogado = SUM ( dim_anio[dias_en_funciones_y_prorrogado] )
```

Con todos los años: 2.140 días con presupuesto prorrogado de 3.601 (59,4 %), 368 con el Gobierno en funciones y 253 de ellos con el presupuesto prorrogado. El script 12 comprueba que los días de cada año cuadran con `datos/calendario_presupuestos.csv` y que los totales cuadran con `datos/calendario_gobiernos.csv`.

## 5. Páginas

Todas llevan una banda de título azul marino con el aviso «Análisis de la ejecución presupuestaria con datos públicos; no es una auditoría. Una diferencia no es una irregularidad» y, debajo, el navegador de páginas (pestañas). Las páginas con explicación llevan una franja blanca con el texto y, a la derecha, los selectores. Las páginas 1, 2, 4, 5 y 6 tienen el selector `Euros` (por defecto, corrientes).

**Navegar entre páginas en Power BI Desktop.** Las pestañas de la banda superior son el navegador de páginas nativo. En Desktop (modo edición) hay que pulsar **Ctrl + clic** para cambiar de página; en Power BI Service o en vista de lectura basta un clic.

| Página | Objetos visuales | Filtros |
| --- | --- | --- |
| 1. Los 22 | Selector de año (por defecto 2024). Tarjetas: iniciales, definitivos, obligaciones, gasto agregado. Matriz por ministerio de entonces con `Incluye`, importes, % ejecución, gasto agregado y peso del Mecanismo. Barras de gasto agregado, con el valor en cada barra | — |
| 2. Ficha | Selector de ministerio (por defecto Defensa; en blanco, todos). Tarjetas: nivel de contratación, perfil de gasto, diferencia del estudio, obligaciones y % ejecutado del Mecanismo. Cascada 2024. Líneas de definitivos y obligaciones por año. Columnas por capítulo (Estado). Ingresos de sus organismos 2024. Cuota nov-dic frente al resto de la AGE. Tabla «Qué ministerio se ve cada año» | Página larga (1580 px, ajustada al ancho) |
| 3. Calendario | Tarjetas: días con presupuesto prorrogado, parte del periodo, días con el Gobierno en funciones, días en funciones con presupuesto prorrogado. Columnas apiladas: días de cada año con presupuesto propio y prorrogado. Columnas: días en funciones por año. Tabla año a año y tabla de los cuatro Gobiernos | — (2017 a 10/11/2026) |
| 4. Prorrogado | Obligaciones sobre iniciales por ministerio, 2024 frente a 2025. Modificaciones de 2025 por tipo | 2024 y 2025 |
| 5. Sin gastar | Sin gastar por capítulo (Estado) por año. Sin gastar total y del Mecanismo. Ranking de ministerios | 2017-2024 (la mensual de 2025 no da capítulos) |
| 6. Mecanismo | Obligaciones del Mecanismo por ministerio; % ejecutado y peso. Tabla de programas | 2021-2025 |
| 7. Cierre | Diferencia nov-dic (pp), niveles A y B. Contraste con el estudio (IC 95 %). Nivel C aparte, en orden alfabético. Importe ordinario por mes | `contratacion = "completo"` |
| 8. Valor del dinero | Selector de ministerio. Obligaciones por año en las cuatro medidas. Factores por año (gráfico y tabla). Qué mide cada índice y fuentes | 2017-2025 |
| 9. Catástrofes | Tarjetas: definitivos, obligaciones, % reconocido. Columnas por año y suceso. Pivote destino × suceso. Barras por sección y por medida | — |
| 10. Crédito nuevo | Crédito definitivo por grupo de líneas. Parte reconocida por grupo (sin Mecanismo y sin capítulo 8). Remanentes: sin reconocer frente a incorporado, y tabla por ministerio en 2024 | `mecanismo = "Resto del presupuesto"` (gráfico de líneas); remanentes 2017-2024 |
| 11. Inicial y pagado | Selector de año (por defecto 2024). Obligaciones sobre iniciales y % sin pagar por ministerio. Tabla del inicial al definitivo por tipo de modificación y de las obligaciones a los pagos | — |
| 12. Contratación y gasto | Selector de año (por defecto 2024). Composición del gasto agregado (100 %), % adjudicado ordinario, tabla gasto-compras-adjudicado y tabla de concentración | — |
| 13. Subvenciones | Importe por año e instrumento, concesiones por año, ayudas directas y tabla por ministerio en 2024 | 2024 en los dos visuales por ministerio |
| 14. Calendario mensual | Obligaciones acumuladas (% de diciembre) y obligaciones de cada mes, 2024 y 2025; pivote ministerio × mes de 2025 | 2025 en el pivote |
| 15. Método y registro | Texto: perímetro, doble cómputo, años comparables, presupuesto prorrogado y Gobierno en funciones, euros corrientes y constantes, páginas 9 a 14, avisos (página más alta: 1.240 px) | — |

## 6. Aspecto

El tema propio (`PresupuestoAlGasto.json`, encima del tema base Fluent 2) fija la identidad visual: fondo de página gris azulado claro, paneles blancos con borde fino y esquinas de 4 px, sin sombras, títulos de 13 pt, tablas con cabecera gris azulada y líneas horizontales finas, líneas rectas con marcadores, tarjetas con el valor en azul marino.

La paleta categórica son ocho tonos, en este orden: azul `#2B5C9E`, ámbar `#BC7C0E`, verde azulado `#0E9585`, ladrillo `#B5453F`, violeta `#7456A6`, oliva `#789A1F`, rosa `#CC5C94` y azul claro `#4B94DA`; el noveno, gris `#7B8794`, solo lo usa el capítulo 9. Se validó con el validador de paletas de la habilidad `dataviz` sobre fondo blanco: luminosidad y croma dentro de banda, separación para daltonismo de al menos 9,8 entre tonos contiguos (≥ 8 es el objetivo), distancia con visión normal de al menos 18,9 (≥ 15) y contraste de al menos 3:1 con el blanco. Las series con significado fijo llevan color fijo (en el calendario: ámbar = prorrogado).

Qué se validó y qué no: `python scripts/15b_validar_informe.py` comprueba todos los `visual.json`, `page.json`, `pages.json` y `report.json` contra los esquemas oficiales de Microsoft (`visualContainer` 2.13.0, la última del repositorio de esquemas, aunque los archivos declaran la 2.14.0; `page` 2.1.0; `pagesMetadata` 1.1.0; `report` 3.3.0) y el tema contra el esquema de temas de informe (`reportThemeSchema-2.159`); también que nada se sale de la página, que los gráficos no se solapan y que los selectores caen en la franja de filtros. Esos esquemas comprueban tipos y valores, no los nombres de las propiedades de cada visual ni del tema: un nombre mal escrito se ignoraría sin avisar. La maquetación no se ha visto en Power BI Desktop: al abrir el informe hay que revisar que la banda, las pestañas y los selectores se ven como se espera.
