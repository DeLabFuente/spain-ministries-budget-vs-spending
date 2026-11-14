"""Valida el informe de Power BI generado por el script 15 contra los esquemas oficiales de Microsoft.

Comprueba cada visual.json (esquema visualContainer), page.json (page), pages.json (pagesMetadata), report.json (report) y
el tema propio (esquema de temas de informe). También comprueba que cada objeto visual está dentro de la página, que no se
solapan los gráficos y que los selectores caen en la franja de filtros.

Los esquemas no vienen con el proyecto; se clonan (solo lectura):
  git clone --depth 1 --filter=blob:none --sparse https://github.com/microsoft/json-schemas  &&  git -C json-schemas sparse-checkout set fabric/item/report
  git clone --depth 1 --filter=blob:none --sparse https://github.com/microsoft/powerbi-desktop-samples  &&  git -C powerbi-desktop-samples sparse-checkout set "Report Theme JSON Schema"

Uso: python scripts/15b_validar_informe.py <carpeta powerbi/ o la de salida del script 15> <carpeta json-schemas> <carpeta powerbi-desktop-samples>
Necesita jsonschema >= 4.18 (pip install jsonschema referencing).

Limitaciones: (1) el repositorio de esquemas puede ir por detrás de Power BI Desktop (aquí, visualContainer 2.13.0 frente a la
2.14.0 que declaran los archivos), así que el campo $schema se ignora en la comprobación; (2) los esquemas de los objetos de cada
visual (`objects`) y del tema comprueban tipos y valores, no los nombres de las propiedades: un nombre mal escrito se ignora sin avisar.
"""
import glob, json, os, re, sys
from jsonschema import Draft7Validator, Draft202012Validator
from referencing import Registry, Resource
import referencing.jsonschema

if len(sys.argv) != 4:
    sys.exit(__doc__)
RAIZ, ESQ, TEMAS = (os.path.abspath(a) for a in sys.argv[1:4])
BASE = "https://developer.microsoft.com/json-schemas/fabric/"
D = os.path.join(ESQ, "fabric", "item", "report", "definition") + os.sep


def carga(uri):
    p = os.path.join(ESQ, "fabric", uri[len(BASE):]) if uri.startswith(BASE) else uri
    return Resource.from_contents(json.load(open(p, encoding="utf-8")), default_specification=referencing.jsonschema.DRAFT7)


REG = Registry(retrieve=carga)


def errores(esq_rel, inst):
    sch = json.load(open(D + esq_rel, encoding="utf-8"))
    cls = Draft7Validator if "draft-07" in sch.get("$schema", "") else Draft202012Validator
    inst = json.loads(json.dumps(inst))
    if "$schema" in inst and "$schema" in sch.get("properties", {}):
        inst["$schema"] = sch["properties"]["$schema"].get("const", inst["$schema"])
    return sorted(cls(sch, registry=REG).iter_errors(inst), key=lambda e: list(e.path))


def ver(carpeta):
    v = sorted((x for x in os.listdir(D + carpeta) if x[0].isdigit()), key=lambda s: [int(n) for n in s.split(".")])
    return v[-1]


R = os.path.join(RAIZ, "presupuesto_al_gasto.Report", "definition") + os.sep
n = mal = 0


def prueba(esq, ruta):
    global n, mal
    n += 1
    e = errores(esq, json.load(open(ruta, encoding="utf-8")))
    if e:
        mal += 1
        print("ERROR", os.path.relpath(ruta, RAIZ))
        for x in e[:4]:
            print("   ", list(x.path), x.message[:200])


vc, pg, pm, rp = (f"{c}/{ver(c)}/schema.json" for c in ("visualContainer", "page", "pagesMetadata", "report"))
for f in glob.glob(R + "pages/*/visuals/*/visual.json"):
    prueba(vc, f)
for f in glob.glob(R + "pages/*/page.json"):
    prueba(pg, f)
prueba(pm, R + "pages/pages.json")
prueba(rp, R + "report.json")
print(f"esquemas usados: {vc}, {pg}, {pm}, {rp}")

# tema propio
tema_esq = sorted(glob.glob(os.path.join(TEMAS, "Report Theme JSON Schema", "reportThemeSchema-*.json")),
                  key=lambda s: [int(x) for x in re.findall(r"\d+", os.path.basename(s))])[-1]
sch = json.load(open(tema_esq, encoding="utf-8"))
cls = Draft7Validator if "draft-07" in sch.get("$schema", "") else Draft202012Validator
for f in glob.glob(os.path.join(RAIZ, "presupuesto_al_gasto.Report", "StaticResources", "RegisteredResources", "*.json")):
    n += 1
    e = list(cls(sch).iter_errors(json.load(open(f, encoding="utf-8"))))
    if e:
        mal += 1
        print("ERROR tema", os.path.basename(f))
        for x in e[:4]:
            print("   ", list(x.path), x.message[:200])
print(f"tema: {os.path.basename(tema_esq)}")

# geometría
for pj in sorted(glob.glob(R + "pages/*/page.json")):
    page = json.load(open(pj, encoding="utf-8"))
    vs = []
    for f in glob.glob(os.path.dirname(pj) + "/visuals/*/visual.json"):
        j = json.load(open(f, encoding="utf-8"))
        p = j["position"]
        vs.append((j["name"], j["visual"]["visualType"], p["x"], p["y"], p["width"], p["height"]))
    for v in vs:
        _, t, x, y, w, h = v
        if x < 0 or y < 0 or x + w > page["width"] or y + h > page["height"]:
            mal += 1; print("FUERA DE LA PÁGINA", page["displayName"], v)
        if t == "slicer" and not (124 <= y and y + h <= 184):
            mal += 1; print("SELECTOR FUERA DE LA FRANJA", page["displayName"], v)
    graf = [v for v in vs if v[1] not in ("textbox", "pageNavigator", "slicer")]
    for i, a in enumerate(graf):
        for b in graf[i + 1:]:
            if a[2] < b[2] + b[4] and b[2] < a[2] + a[4] and a[3] < b[3] + b[5] and b[3] < a[3] + a[5]:
                mal += 1; print("SOLAPE", page["displayName"], a, b)
print(f"{n} archivos de esquema comprobados; {mal} problemas")
sys.exit(1 if mal else 0)
