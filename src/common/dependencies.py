# src/api/dependencies.py
import requests

def get_api_data(src) -> dict:
    url = "http://127.0.0.1:8000/" + src
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