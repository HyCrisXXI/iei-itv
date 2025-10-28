# mydearmap

Proyecto para la asignatura IEI (etsinf) de la Universitat Politècnica de València.
Trata de obtener datos sobre ITVs de Cataluña, Galicia y Comunidad Valenciana de distintas fuentes y unificarlos.
Escribir pip install -r requirements.txt para tener todas las librerías (lista de la compra)
Comando importante antes de ejecutar cualquier clase .py: .\.venv\Scripts\Activate.ps1


## Estructura

iei_itv/
├── config/                  # Archivos de configuración (conexión DB, logging, etc.)
│   └── settings.py
├── core/                    # Componentes base y comunes
│   ├── database.py          # Lógica de conexión a la DB y gestión de sesiones
│   └── models.py            # Definición de la estructura de la DB (ORM)
├── extractors/              # Módulos para procesar datos de fuentes externas
│   ├── extractor_gal.py     # Lógica para CSV o XML (Fuente GAL)
│   ├── extractor_cat.py     # Lógica para XML (Fuente CAT)
│   └── extractor_cv.py      # Lógica para JSON (Fuente CV)
├── services/                # Lógica de negocio específica (APIs de carga/búsqueda)
│   ├── load_service.py      # Lógica de la API de carga (maneja la inserción de datos)
│   └── search_service.py    # Lógica de la API de búsqueda (maneja la consulta de datos)
├── api/                     # Implementación de los endpoints de la API (usando FastAPI o Flask)
│   └── api_routes.py        # Define los endpoints /carga y /busqueda
├── tests/                   # Pruebas unitarias e de integración
├── main.py                  # Punto de entrada de la aplicación
├── requirements.txt         # Dependencias del proyecto (psycopg2, ORM, framework web)
└── .env                     # Api keys del proyecto (supabase)