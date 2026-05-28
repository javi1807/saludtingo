from django.apps import AppConfig
from django.db.backends.signals import connection_created
from django.dispatch import receiver

class UrgenciasConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "urgencias"

    def ready(self):
        # Asegura que las señales se registren correctamente al iniciar la aplicación
        pass

@receiver(connection_created)
def configure_sqlite(sender, connection, **kwargs):
    """
    Configura de forma óptima SQLite cada vez que se establece una conexión.
    Activa el modo WAL (Write-Ahead Logging) y el modo síncrono NORMAL
    para habilitar lectura y escritura concurrentes sin bloqueos duros.
    """
    if connection.vendor == 'sqlite':
        try:
            cursor = connection.cursor()
            cursor.execute('PRAGMA journal_mode=WAL;')
            cursor.execute('PRAGMA synchronous=NORMAL;')
            cursor.execute('PRAGMA cache_size=-64000;')  # Aumentar caché de lectura a 64MB
        except Exception:
            # Capturar posibles fallas en entornos de prueba iniciales
            pass
