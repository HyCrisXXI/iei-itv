import sys
from pathlib import Path
from sqlalchemy.orm import Session
from database.models import TipoEstacion, Provincia, Localidad, Estacion
from database.session import get_db

def _map_tipo_enum(tipo: str | TipoEstacion) -> TipoEstacion:
    if isinstance(tipo, TipoEstacion):
        return tipo
        
    if not tipo:
        return TipoEstacion.Otros
    t = str(tipo).strip().lower()
    if 'fija' in t:
        return TipoEstacion.Estacion_fija
    if 'mov' in t or 'móvil' in t:
        return TipoEstacion.Estacion_movil
    return TipoEstacion.Otros

def _safe_int(value) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None

def save_stations(stations_data: list[dict], source_tag: str) -> dict:
    """
    Guarda estaciones en la BD.
    Asume que los datos en stations_data ya han sido validados previamente.
    Campos esperados:
      - nombre
      - p_nombre (Provincia) - opcional si no es fija, pero recomendado
      - p_cod (Codigo Provincia) - opcional
      - l_nombre (Localidad) - opcional
      - tipo
      - direccion, codigo_postal, latitud, longitud, horario, contacto, url
    """
    stats = {
        "processed": 0,
        "inserted": 0,
        "duplicates": 0,
        "errors": []
    }

    with next(get_db()) as session:
        prov_cache = {}
        loc_cache = {}
        est_cache = {}

        for data in stations_data:
            stats["processed"] += 1
            
            nombre = data.get("nombre")
            # Verificación de seguridad para evitar errores al comprometer la base de datos
            if not nombre:
                stats["errors"].append("Nombre vacío")
                continue

            p_nombre = data.get("p_nombre")
            l_nombre = data.get("l_nombre")
            p_cod = _safe_int(data.get("p_cod"))

            # --- PROVINCIA ---
            prov = None
            if p_nombre:
                p_norm = p_nombre.strip().lower() # Normalización para cache
                if p_norm in prov_cache:
                    prov = prov_cache[p_norm]
                else:
                    # Intentar buscar
                    query = session.query(Provincia)
                    if p_cod:
                        prov = query.filter_by(codigo=p_cod).first()
                    if not prov:
                        prov = query.filter(Provincia.nombre.ilike(p_nombre)).first()
                    
                    if not prov:
                        # Crear
                        prov_final_name = p_nombre.strip().capitalize()
                        prov = Provincia(nombre=prov_final_name, codigo=p_cod)
                        session.add(prov)
                        session.flush()
                    
                    prov_cache[p_norm] = prov

            # --- LOCALIDAD ---
            loc = None
            if l_nombre and prov:
                l_norm = l_nombre.strip().lower()
                loc_key = (l_norm, prov.codigo)
                if loc_key in loc_cache:
                    loc = loc_cache[loc_key]
                else:
                    loc = session.query(Localidad).filter(
                        Localidad.nombre.ilike(l_nombre), 
                        Localidad.codigo_provincia == prov.codigo
                    ).first()
                    
                    if not loc:
                        loc_final_name = l_nombre.strip().capitalize() # Normalización simple
                        loc = Localidad(nombre=loc_final_name, codigo_provincia=prov.codigo)
                        session.add(loc)
                        session.flush()
                    loc_cache[loc_key] = loc

            # --- ESTACION ---
            loc_cod = loc.codigo if loc else None
            est_key = (nombre, loc_cod)
            
            if est_key in est_cache:
                stats["duplicates"] += 1
                continue
            
            # Check DB
            query_est = session.query(Estacion).filter_by(nombre=nombre)
            if loc_cod is not None:
                query_est = query_est.filter_by(codigo_localidad=loc_cod)
            else:
                query_est = query_est.filter(Estacion.codigo_localidad.is_(None))
                
            est = query_est.first()
            if est:
                est_cache[est_key] = est
                stats["duplicates"] += 1
                continue

            estacion = Estacion(
                nombre=nombre,
                tipo=_map_tipo_enum(data.get("tipo")),
                codigo_localidad=loc_cod,
                origen_datos=source_tag,
                direccion=data.get("direccion"),
                codigo_postal=_safe_int(data.get("codigo_postal")),
                latitud=data.get("latitud"),
                longitud=data.get("longitud"),
                horario=data.get("horario"),
                contacto=data.get("contacto"),
                url=data.get("url")
            )
            session.add(estacion)
            est_cache[est_key] = estacion
            stats["inserted"] += 1

        session.commit()
    return stats
