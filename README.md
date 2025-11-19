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
│   │   └── dependencies.py  # Autenticación, configuración de API
│   │
│   ├── wrappers/            # Capa de Abstracción y Normalización
│   │   ├── base.py          # Clase base/interfaz para los wrappers
│   │   ├── gal.py
│   │   ├── cat.py
│   │   └── cv.py            # Consume 'utils/geo.py' si es necesario
│   │
│   ├── extractors/          # Motor de Escritura y Orquestación
│   │   ├── manager.py       # Lógica para elegir el extractor correcto
│   │   ├── gal_extractor.py
│   │   ├── cat_extractor.py
│   │   └── cv_extractor.py
│   │
│   └── database/            # Almacén de Datos (Single Source of Truth)
│       ├── models.py        # Definición de tablas/documentos
│       ├── session.py       # Conexión a la DB
│       ├── repository.py    # Funciones CRUD (Create, Read, Update, Delete)
│       └── config.py        # Variables de entorno y configuración global
│
├── main.py                  # Punto de entrada de la aplicación
├── .env.example             # Plantilla para las variables de entorno
├── .gitignore               # Archivos y carpetas a ignorar por Git
└── requirements.txt         # Dependencias de Python
