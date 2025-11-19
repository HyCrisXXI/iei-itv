# src/extractors/extractor_cat.py
import sys
import json
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from wrappers.wrapper_cat import xmltojson

def coordsToDecimal(coordString: str) -> str | None:
    if(coordString.length == 0):
        return None
    conv = coordString.toDouble()/1000000
    return str(conv)


def codigoProvincia(codigoLocalidad):
    if(codigoLocalidad.length == 5):
        return codigoLocalidad.substring(0,2)
    else: return "0" + codigoLocalidad.substring(0,1)

def transform_itv_record(record: dict) -> dict:
    KEY_MAPPING = {
        "denominaci": "nombre",
        "fija": "tipo",
        "adre_a": "direccion",
        "cp": "codigo_postal",
        "long": "longitud",
        "lat": "latitud",
        "horari": "horario",
        "correu_electrònic": "contacto",
        "codi_municipi": "codigo_localidad",
        "municipi": "nombre_localidad",
        "codi_postal": "codigo_provincia",
        "serveis_territorials": "nombre_provincia",
    }
    
    transformed = {} # Claves estandarizadas
    for old_key, new_key in KEY_MAPPING.items():
        if old_key in record:
            transformed[new_key] = record[old_key]
    
    # Elimina clave original
    lat_string = transformed.pop("lat", None)
    long_string = transformed.pop("long", None)
    
    if lat_string: 
        lat = coordsToDecimal(lat_string)

    if long_string:        
        long = coordsToDecimal(long_string)
    
    transformed["lat"] = lat
    transformed["long"] = long

    cod_postal_string = transformed.pop("cod_postal", None)
    transformed["p_cod"] = cod_postal_string[:2] if cod_postal_string else None
    
    return transformed

if __name__ == "__main__":
    data_list = xmltojson()
    transformed_data = [transform_itv_record(record) for record in data_list]
    out_path = Path(__file__).resolve().parent / "cat.json"
    with out_path.open("w", encoding="utf-8") as jsonfile:
        json.dump(data_list, jsonfile, indent=4, ensure_ascii=False) # minify: indent=None, separators=(",", ":")
