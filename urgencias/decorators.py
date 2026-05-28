import time
import random
import logging
from functools import wraps
from django.db import OperationalError

logger = logging.getLogger(__name__)

def retry_on_db_lock(max_retries=5, initial_backoff=0.05, backoff_factor=2.0):
    """
    Decorador para reintentar funciones o vistas que fallan debido a bloqueos de base de datos
    (ej. 'database is locked' en SQLite).
    Utiliza backoff exponencial con jitter (variación aleatoria) para desincronizar solicitudes concurrentes.
    """
    def decorator(func):
        @wraps(func)
        def _wrapped(*args, **kwargs):
            retries = 0
            backoff = initial_backoff
            
            while True:
                try:
                    return func(*args, **kwargs)
                except OperationalError as e:
                    # Verificar si es un error de bloqueo (ej. 'database is locked' o 'table is locked')
                    is_lock_error = "lock" in str(e).lower()
                    
                    if is_lock_error and retries < max_retries:
                        retries += 1
                        # Calcular tiempo de espera con variación aleatoria
                        jitter = random.uniform(0.5, 1.5)
                        sleep_time = backoff * jitter
                        
                        logger.warning(
                            f"[CONCURRENCIA] Bloqueo detectado en base de datos. "
                            f"Reintento {retries}/{max_retries} en {sleep_time:.3f}s. Detalle: {str(e)}"
                        )
                        
                        time.sleep(sleep_time)
                        backoff *= backoff_factor
                        continue
                    else:
                        # Si superamos los reintentos o no es un error de bloqueo, lanzar la excepción
                        raise e
        return _wrapped
    return decorator
