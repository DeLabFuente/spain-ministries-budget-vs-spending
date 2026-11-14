# BDNS: agregados de las concesiones del Estado (2022-2025)

`bdns_agregados.json` contiene solo agregados, sin ningún registro individual y sin beneficiarios.

- `agg`: clave `año|ministerio (nombre de la BDNS)|instrumento (grafía de la BDNS)` → `[concesiones, importe en euros, concesiones sin importe]`.
- `ctl`: por año y modo de lectura (`lectura` = concesiones leídas una a una; `solo-recuento` = días gigantes de 2025 solo contados): días, concesiones totales según la API, vistas, únicas y días con lectura correcta.
- Origen: API pública de la BDNS (`https://www.infosubvenciones.es/bdnstrans/api/concesiones/busqueda`, `tipoAdministracion=C`), leída el 13-14/11/2026 día a día (1.461 días) desde el navegador integrado. Cuatro días de 2025 (03/11, 01/12, 18/12 y 19/12; 6.461.534 concesiones) solo se contaron por ministerio e instrumento.
- Se usa en `scripts/27_bdns.py`. Reglas y salvedades: `REGISTRO.md` (A39, A40, B30).
