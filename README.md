# iei-itv

Proyecto iei-itv para la asignatura IEI (etsinf) de la Universitat Politècnica de València.
Este proyecto es una aplicación backend (API) para extraer, procesar y consultar datos de ITV de diferentes comunidades autónomas (Cataluña, Comunidad Valenciana, Galicia).

## Prerrequisitos

Necesitarás tener instalado:

* **Python 3.10** o superior.
* **Git** para clonar el repositorio.

## Instalación y uso

### 1. Clonar repositorio

```bash
git clone https://github.com/HyCrisXXI/iei-itv.git
cd iei-itv
```

### 2. Activar el entorno virtual

* **En Windows (PowerShell):**
    ```powershell
    .\.venv\Scripts\Activate.ps1
    ```
* **En macOS / Linux:**
    ```bash
    source .venv/bin/activate
    ```

### 3. Instalar dependencias del proyecto (lista de la compra)

```bash
pip install -r requirements.txt
```
## Estructura

La estructura principal del proyecto sigue un diseño modular:
```text
iei-itv/
├── src/                          # Directorio principal del código fuente
│   ├── api/                      # Endpoints de la API (FastAPI/Flask)
│   │   ├── __init__.py
│   │   └── api_routes.py
│   ├── config/                   # Módulos de configuración
│   │   ├── __init__.py
│   │   └── settings.py
│   ├── core/                     # Lógica central de base de datos
│   │   ├── __init__.py
│   │   ├── database.py
│   │   └── models.py
│   ├── extractors/               # Scripts de extracción de datos
│   │   ├── __init__.py
│   │   ├── extractor_cat.py
│   │   ├── extractor_cv.py
│   │   └── extractor_gal.py
│   └── wrappers/                 # Wrappers para normalizar a .json
│   └── services/                 # Lógica de negocio
│       ├── __init__.py
│       ├── load_service.py
│       └── search_service.py
├── tests/                        # Pruebas
├── .env                          # (Ignorado por Git) Credenciales de la DB
├── .env.example                  # Plantilla para las variables de entorno
├── .gitignore                    # Archivos y carpetas a ignorar por Git
├── main.py                       # Punto de entrada de la aplicación
└── requirements.txt              # Dependencias de Python
