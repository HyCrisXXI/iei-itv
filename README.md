# iei-itv

Proyecto para la asignatura IEI (etsinf) de la Universitat Politècnica de València.
Trata de obtener datos sobre ITVs de Cataluña, Galicia y Comunidad Valenciana de distintas fuentes y unificarlos.

Prerequisitos: Python 3.10 o superior

# 1 Clonar repositorio
git clone https://github.com/HyCrisXXI/iei-itv.git
cd iei-itv

#  2 Activar el entorno virtual
#   En Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
#   En macOS / Linux:
source .venv/bin/activate

#  3 Instalar dependencias del proyecto (lista de la compra)
pip install -r requirements.txt

## Estructura

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
