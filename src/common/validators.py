# src/common/validators.py
"""
Módulo centralizado de validadores para integración de datos.
Contiene funciones de validación y limpieza reutilizables por todos los extractores.
"""
from typing import Callable, List
import re


def is_valid_time(h: int, m: int) -> bool:
    """Verifica si hora:minuto es válido (0-23:0-59)."""
    return 0 <= h <= 23 and 0 <= m <= 59


def is_valid_horario(horario: str | None) -> bool:
    """
    Verifica si un string de horario contiene horas válidas.
    Busca patrones H:MM o HH:MM y valida cada uno.
    """
    if not horario:
        return False
    times = re.findall(r'(\d{1,2}):(\d{2})', horario)
    if not times:
        return False
    return all(is_valid_time(int(h), int(m)) for h, m in times)


def is_valid_email(email: str | None) -> bool:
    """
    Verifica si un email tiene usuario y dominio.
    Devuelve False para emails incompletos como "itv@".
    """
    if not email or "@" not in email:
        return False
    parts = email.split("@", 1)
    return len(parts) == 2 and len(parts[0]) > 0 and len(parts[1]) > 0


def clean_invalid_email(email: str | None) -> str | None:
    """
    Limpia un email inválido a None.
    Si el email es válido, lo devuelve sin cambios.
    """
    if is_valid_email(email):
        return email
    return None


def choose_best_value(val1, val2, validator=None):
    """
    Elige el mejor valor entre dos, opcionalmente usando un validador.
    
    Estrategia:
    1. Si hay validador, prefiere el valor válido
    2. Si ambos válidos o sin validador, prefiere el no vacío
    3. Si ambos tienen valor, prefiere el más largo (más completo)
    """
    if validator:
        v1_valid = validator(val1)
        v2_valid = validator(val2)
        if v1_valid and not v2_valid:
            return val1
        if v2_valid and not v1_valid:
            return val2
    # Si ambos válidos o ninguno tiene validador, preferir el no vacío/más largo
    if not val1:
        return val2
    if not val2:
        return val1
    # Ambos tienen valor, preferir el más largo (más completo)
    return val1 if len(str(val1)) >= len(str(val2)) else val2


def merge_duplicate_records(
    data_list: list,
    key_field: str,
    field_validators: dict | None = None,
    on_merge: Callable[[str, List[dict]], None] | None = None,
) -> list:
    """
    Fusiona registros duplicados por un campo clave.
    Combina campos tomando el mejor valor de cada uno.
    
    Args:
        data_list: Lista de diccionarios a fusionar
        key_field: Nombre del campo clave para identificar duplicados
        field_validators: Dict {campo: función_validadora} para campos específicos
    
    Returns:
        Lista de registros fusionados
    """
    from collections import defaultdict
    
    if field_validators is None:
        field_validators = {}
    
    groups = defaultdict(list)
    for record in data_list:
        key = str(record.get(key_field, "")).strip()
        if key:
            groups[key].append(record)
        else:
            # Sin clave, no se puede agrupar
            groups[f"_unnamed_{id(record)}"].append(record)
    
    merged_list = []
    for key, records in groups.items():
        if len(records) == 1:
            merged_list.append(records[0])
            continue
		
        if on_merge:
            try:
                on_merge(key, records)
            except Exception:
                pass

        # Fusionar múltiples registros
        base = records[0].copy()
        print(f"   [*] Fusionando {len(records)} registros duplicados para '{key_field}'={key}")
        
        for other in records[1:]:
            for field in other.keys():
                validator = field_validators.get(field)
                base[field] = choose_best_value(
                    base.get(field), 
                    other.get(field), 
                    validator
                )
        
        merged_list.append(base)
    
    return merged_list
