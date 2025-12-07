# src/api/dependencies.py
import requests

def get_api_data(source_tag: str) -> dict:
    url = "http://127.0.0.1:8000/" + source_tag
    try:
        # Recupera datos de la API
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        print("ERROR: No se pudo conectar a la API. ¿Está el servidor FastAPI arrancado en el puerto 8000?")
        exit(1)
    except requests.exceptions.Timeout:
        print("ERROR: La conexión a la API ha tardado demasiado. ¿Está el servidor FastAPI funcionando?")
        exit(1)
    except requests.exceptions.HTTPError as e:
        print(f"ERROR: La API devolvió un error HTTP: {e.response.status_code}")
        exit(1)

def save_transformed_to_json(transformed_list: list, source_tag: str):
    out_path = Path(__file__).resolve().parent / f"{source_tag}.json"
    with out_path.open("w", encoding="utf-8") as jsonfile:
        json.dump(transformed_list, jsonfile, indent=4, ensure_ascii=False)
