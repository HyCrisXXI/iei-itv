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


### 2. Crear y activar el entorno virtual

Si no existe la carpeta `.venv`, créala con:

* **En Windows:**
    ```powershell
    python -m venv .venv
    ```
* **En macOS / Linux:**
    ```bash
    python3 -m venv .venv
    ```

Luego, activa el entorno virtual:

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

## Cómo ejecutar la API y los extractores

### Lanzar la API REST (FastAPI)

En una terminal (desde la raiz del proyecto), ejecuta:

```bash
uvicorn src.api.main:app --reload
```

Esto arrancará el servidor en http://127.0.0.1:8000. Puedes ver la documentación interactiva en http://127.0.0.1:8000/docs

### Ejecutar los extractores

En otra terminal (con la API ya arrancada), ejecuta el extractor que desees. Por ejemplo, para Galicia:

```bash
python src/extractors/extractor_gal.py
```

## Estructura

La estructura principal del proyecto sigue un diseño modular:
```text
iei-itv/
├── data/                    # (csv, xml, json originales)
├── src/
│   ├── api/                 # Puntos de entrada (API de Carga y Búsqueda)
│   │   ├── routes/
│   │   │   ├── load.py      # API de Carga (Recibe manual y redirige a Extractors)
│   │   │   └── search.py    # API de Búsqueda (Solo lectura desde DB)
│   │   └── main.py          # APIs de los wrappers
│   │
│   ├── common/              # Funciones comunes para los extractors
│   │
│   ├── database/            # Almacén de Datos (Single Source of Truth)
│   │   ├── models.py        # Definición de tablas/documentos
│   │   ├── session.py       # Conexión a la DB
│   │   └── config.py        # Variables de entorno y configuración global
│   │
│   ├── wrappers/            # Capa de abstracción
│   │   ├── wrapper_gal.py
│   │   ├── wrapper_cat.py
│   │   └── wrapper_cv.py
│   │
│   └── extractors/          # Capa de normalización de datos
│       ├── gal_extractor.py
│       ├── cat_extractor.py
│       └── cv_extractor.py
│
├── main.py                  # Punto de entrada de la aplicación
├── .env.example             # Plantilla para las variables de entorno
├── .gitignore               # Archivos y carpetas a ignorar por Git
└── requirements.txt         # Dependencias de Python
