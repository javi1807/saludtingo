import time
import threading
from django.test import TransactionTestCase, Client
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError, connection, OperationalError
from django.contrib.auth.models import User, Group
from urgencias.models import Paciente, Recurso, Admision, Insumo, CuentaFacturacion, CargoFacturacion

class UrgenciasConcurrencyTests(TransactionTestCase):
    
    def setUp(self):
        # Reiniciar/Limpiar antes de cada test
        Paciente.objects.all().delete()
        Recurso.objects.all().delete()
        Insumo.objects.all().delete()
        
        # Create authenticated user for protected views
        self.user = User.objects.create_user(username='testmedico', password='testpass')
        urgencias_group, _ = Group.objects.get_or_create(name='Urgencias_Staff')
        self.user.groups.add(urgencias_group)
        
        # Cama de prueba
        self.cama = Recurso.objects.create(codigo="CAMA-TEST", tipo="CAMA", estado="DISPONIBLE", descripcion="Cama Test Concurrencia")
        
        # Insumo de prueba (stock inicial = 2)
        self.insumo = Insumo.objects.create(codigo="INS-TEST", nombre="Suero de Prueba", stock=2, precio_unitario=10.00)

    def test_concurrent_patient_registration_zero_collision(self):
        """
        Prueba que dos hilos intentando registrar el mismo DNI simultáneamente
        no dupliquen el registro del paciente y que ambos creen una admisión atómicamente.
        Utiliza reintentos para manejar el bloqueo completo de base de datos de SQLite.
        """
        dni = "99999999-Z"
        nombre = "Concurrente"
        
        exceptions = []
        
        def register_worker(suffix, delay):
            retries = 5
            while retries > 0:
                connection.close() # Forzar conexión fresca por hilo
                try:
                    with transaction.atomic():
                        try:
                            # Bloquear fila
                            paciente = Paciente.objects.select_for_update().get(documento_identidad=dni)
                            paciente.nombre = nombre
                            paciente.apellido = f"Ap-{suffix}"
                            time.sleep(delay)
                            paciente.save()
                        except Paciente.DoesNotExist:
                            # Si no existe, simulamos un delay para provocar la colisión de inserción
                            time.sleep(delay)
                            try:
                                paciente = Paciente.objects.create(
                                    documento_identidad=dni,
                                    nombre=nombre,
                                    apellido=f"Ap-{suffix}",
                                    fecha_nacimiento="1980-01-01"
                                )
                            except IntegrityError:
                                # Capturar colisión y resolver
                                paciente = Paciente.objects.select_for_update().get(documento_identidad=dni)
                                paciente.nombre = nombre
                                paciente.apellido = f"Ap-{suffix}-Resuelto"
                                paciente.save()
                        
                        # Crear admisión
                        adm = Admision.objects.create(
                            paciente=paciente,
                            motivo_consulta=f"Motivo-{suffix}",
                            triage_nivel='AMARILLO',
                            estado='EN_ESPERA'
                        )
                        CuentaFacturacion.objects.create(admision=adm)
                        
                        # Si llegamos aquí con éxito, salimos del ciclo de reintentos
                        break
                except OperationalError as oe:
                    if "lock" in str(oe).lower() and retries > 1:
                        retries -= 1
                        time.sleep(0.3) # Esperar a que el otro hilo libere el bloqueo de SQLite
                        continue
                    exceptions.append(oe)
                    break
                except Exception as e:
                    exceptions.append(e)
                    break
                finally:
                    connection.close()

        # Lanzar 2 hilos paralelos
        # Hilo 1 tarda 0.2s, Hilo 2 tarda 0.1s.
        t1 = threading.Thread(target=register_worker, args=("A", 0.2))
        t2 = threading.Thread(target=register_worker, args=("B", 0.1))
        
        t1.start()
        t2.start()
        
        t1.join()
        t2.join()
        
        # Validar que no hay excepciones catastróficas no manejadas
        self.assertEqual(len(exceptions), 0, f"Excepciones detectadas: {exceptions}")
        
        # El paciente debe existir exactamente una vez
        pacientes = Paciente.objects.filter(documento_identidad=dni)
        self.assertEqual(pacientes.count(), 1)
        
        # Deben haberse creado dos admisiones (una por cada llamada/hilo exitoso)
        admisiones = Admision.objects.filter(paciente__documento_identidad=dni)
        self.assertEqual(admisiones.count(), 2)

    def test_concurrent_bed_assignment_exclusive_lock(self):
        """
        Prueba que si dos pacientes intentan asignar la misma cama disponible
        en paralelo, solo uno de ellos lo consiga y el otro obtenga una excepción
        de validación o bloqueo, impidiendo la doble ocupación.
        """
        p1 = Paciente.objects.create(documento_identidad="PX-1", nombre="PX1", apellido="LN1", fecha_nacimiento="1990-01-01")
        p2 = Paciente.objects.create(documento_identidad="PX-2", nombre="PX2", apellido="LN2", fecha_nacimiento="1991-01-01")
        
        adm1 = Admision.objects.create(paciente=p1, motivo_consulta="Adm1", estado="EN_ESPERA")
        adm2 = Admision.objects.create(paciente=p2, motivo_consulta="Adm2", estado="EN_ESPERA")
        
        successes = []
        failures = []

        def assign_worker(adm_id, delay):
            connection.close()
            try:
                with transaction.atomic():
                    # 1. select_for_update para bloqueo pesimista
                    recurso = Recurso.objects.select_for_update().get(codigo="CAMA-TEST")
                    
                    time.sleep(delay) # Mantener bloqueo
                    
                    if recurso.estado != 'DISPONIBLE':
                        raise ValidationError("Cama ocupada")
                        
                    recurso.estado = 'OCUPADO'
                    recurso.save()
                    
                    adm = Admision.objects.select_for_update().get(id=adm_id)
                    adm.recurso_asignado = recurso
                    adm.estado = 'ADMITIDO'
                    adm.save()
                    
                    successes.append(adm_id)
            except (ValidationError, Exception) as e:
                failures.append(e)
            finally:
                connection.close()

        # Hilo A bloquea primero (delay=0.3s)
        # Hilo B intenta 0.05s después, debe bloquearse esperando y luego fallar
        t1 = threading.Thread(target=assign_worker, args=(adm1.id, 0.3))
        t2 = threading.Thread(target=assign_worker, args=(adm2.id, 0.05))
        
        t1.start()
        time.sleep(0.05)
        t2.start()
        
        t1.join()
        t2.join()

        # Validaciones de consistencia
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(failures), 1)
        
        # Verificar estado final de la cama
        self.cama.refresh_from_db()
        self.assertEqual(self.cama.estado, 'OCUPADO')
        
        # Solo una admisión debe tener el recurso asignado
        admisiones_con_cama = Admision.objects.filter(recurso_asignado=self.cama)
        self.assertEqual(admisiones_con_cama.count(), 1)

    def test_concurrent_inventory_billing_atomicity(self):
        """
        Prueba la atomicidad de cargos: dos hilos retiran del inventario en paralelo.
        Con un stock de 2:
        - Hilo A retira 2 unidades (exitoso, reduce stock a 0).
        - Hilo B retira 1 unidad (falla por stock insuficiente).
        La cuenta de B no debe registrar cargos parciales, y el stock final debe ser exactamente 0 (no negativo).
        """
        p1 = Paciente.objects.create(documento_identidad="PX-3", nombre="PX3", apellido="LN3", fecha_nacimiento="1990-01-01")
        p2 = Paciente.objects.create(documento_identidad="PX-4", nombre="PX4", apellido="LN4", fecha_nacimiento="1991-01-01")
        
        adm1 = Admision.objects.create(paciente=p1, motivo_consulta="Adm3", estado="EN_ESPERA")
        adm2 = Admision.objects.create(paciente=p2, motivo_consulta="Adm4", estado="EN_ESPERA")
        
        cta1 = CuentaFacturacion.objects.create(admision=adm1)
        cta2 = CuentaFacturacion.objects.create(admision=adm2)
        
        successes = []
        failures = []

        def billing_worker(cuenta_id, qty, delay):
            connection.close()
            try:
                with transaction.atomic():
                    # Bloquear insumo
                    ins = Insumo.objects.select_for_update().get(codigo="INS-TEST")
                    
                    time.sleep(delay)
                    
                    if ins.stock < qty:
                        raise ValidationError("Stock insuficiente")
                        
                    ins.stock -= qty
                    ins.save()
                    
                    cta = CuentaFacturacion.objects.select_for_update().get(id=cuenta_id)
                    CargoFacturacion.objects.create(
                        cuenta=cta,
                        insumo=ins,
                        cantidad=qty,
                        precio_aplicado=ins.precio_unitario
                    )
                    cta.recalcular_total()
                    successes.append(cuenta_id)
            except (ValidationError, Exception) as e:
                failures.append(e)
            finally:
                connection.close()

        # Hilo A pide 2 (delay=0.3s) - Entra primero y consume todo
        # Hilo B pide 1 (delay=0.05s) - Entra después, espera bloqueo, y falla por stock=0
        t1 = threading.Thread(target=billing_worker, args=(cta1.id, 2, 0.3))
        t2 = threading.Thread(target=billing_worker, args=(cta2.id, 1, 0.05))
        
        t1.start()
        time.sleep(0.05)
        t2.start()
        
        t1.join()
        t2.join()

        # Verificar
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(failures), 1)
        
        self.insumo.refresh_from_db()
        self.assertEqual(self.insumo.stock, 0)
        
        cta1.refresh_from_db()
        cta2.refresh_from_db()
        
        self.assertEqual(cta1.total_cargado, 20.00) # 2 x 10.00
        self.assertEqual(cta2.total_cargado, 0.00)  # falló y se revirtió
        
        self.assertEqual(cta1.cargos.count(), 1)
        self.assertEqual(cta2.cargos.count(), 0)

    def test_bpmn_recurso_lifecycle(self):
        """
        Prueba el ciclo de vida completo de un recurso alineado con Bizagi BPMN:
        1. Cama disponible: DISPONIBLE.
        2. Paciente ingresado y asignado: DISPONIBLE -> OCUPADO.
        3. Médico ordena pre-alta: OCUPADO -> PRE_ALTA.
        4. Enfermería confirma salida física del paciente: PRE_ALTA -> LIMPIEZA.
        5. Personal de limpieza registra término: LIMPIEZA -> DISPONIBLE.
        """
        p = Paciente.objects.create(documento_identidad="PX-BPMN", nombre="Pac", apellido="BPMN", fecha_nacimiento="1990-01-01")
        adm = Admision.objects.create(paciente=p, motivo_consulta="Ingreso regular", estado="EN_ESPERA")
        
        self.assertEqual(self.cama.estado, 'DISPONIBLE')
        
        # 1. Asignar cama
        client = Client()
        client.login(username='testmedico', password='testpass')
        response = client.post('/api/recurso/asignar/', {
            'admision_id': adm.id,
            'recurso_id': self.cama.id
        })
        self.assertEqual(response.status_code, 200)
        self.cama.refresh_from_db()
        adm.refresh_from_db()
        self.assertEqual(self.cama.estado, 'OCUPADO')
        self.assertEqual(adm.estado, 'ADMITIDO')
        
        # 2. Emitir Pre-Alta
        response = client.post('/api/recurso/pre-alta/', {
            'admision_id': adm.id
        })
        self.assertEqual(response.status_code, 200)
        self.cama.refresh_from_db()
        self.assertEqual(self.cama.estado, 'PRE_ALTA')
        
        # 3. Confirmar Salida Física
        response = client.post('/api/recurso/confirmar-salida/', {
            'admision_id': adm.id
        })
        self.assertEqual(response.status_code, 200)
        self.cama.refresh_from_db()
        adm.refresh_from_db()
        self.assertEqual(self.cama.estado, 'LIMPIEZA')
        self.assertEqual(adm.estado, 'ALTA')
        self.assertIsNone(adm.recurso_asignado)
        
        # 4. Registrar limpieza completada
        response = client.post('/api/recurso/limpieza-completada/', {
            'recurso_id': self.cama.id
        })
        self.assertEqual(response.status_code, 200)
        self.cama.refresh_from_db()
        self.assertEqual(self.cama.estado, 'DISPONIBLE')

    def test_regularize_paciente_nn_nuevo_dni(self):
        """
        Prueba la regularización de un paciente NN con un DNI nuevo.
        Debería actualizar los campos del registro NN original.
        """
        client = Client()
        client.login(username='testmedico', password='testpass')
        
        # 1. Crear un bypass de shock trauma (crea paciente NN y bloquea cama)
        response = client.post('/api/paciente/shock-trauma/')
        self.assertEqual(response.status_code, 200)
        
        # Obtener la admisión NN creada
        admision_nn = Admision.objects.filter(paciente__documento_identidad__startswith="NN-").latest('id')
        paciente_nn_id = admision_nn.paciente.id
        nn_dni = admision_nn.paciente.documento_identidad
        
        # 2. Intentar regularizar con un DNI nuevo
        nuevo_dni = "88888888-A"
        response = client.post('/api/paciente/regularizar/', {
            'admision_id': admision_nn.id,
            'documento_identidad': nuevo_dni,
            'nombre': 'Carlos',
            'apellido': 'García',
            'fecha_nacimiento': '1985-05-15'
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        
        # Verificar que los datos del paciente original se hayan actualizado
        paciente = Paciente.objects.get(id=paciente_nn_id)
        self.assertEqual(paciente.documento_identidad, nuevo_dni)
        self.assertEqual(paciente.nombre, 'Carlos')
        self.assertEqual(paciente.apellido, 'García')
        self.assertEqual(paciente.historia_clinica_num, f"HC-{nuevo_dni}")
        
        # Verificar que el DNI viejo NN ya no exista
        self.assertFalse(Paciente.objects.filter(documento_identidad=nn_dni).exists())

    def test_regularize_paciente_nn_dni_existente(self):
        """
        Prueba la regularización de un paciente NN con un DNI que ya existe en la base de datos.
        Debería reasociar la admisión al paciente existente, actualizar sus datos demográficos
        y eliminar el paciente NN temporal.
        """
        client = Client()
        client.login(username='testmedico', password='testpass')
        
        # 1. Crear paciente con DNI existente
        dni_existente = "77777777-B"
        paciente_existente = Paciente.objects.create(
            documento_identidad=dni_existente,
            nombre="Ana",
            apellido="López",
            fecha_nacimiento="1992-08-20"
        )
        
        # 2. Crear un bypass de shock trauma (crea paciente NN)
        response = client.post('/api/paciente/shock-trauma/')
        self.assertEqual(response.status_code, 200)
        
        # Obtener la admisión NN creada
        admision_nn = Admision.objects.filter(paciente__documento_identidad__startswith="NN-").latest('id')
        nn_dni = admision_nn.paciente.documento_identidad
        
        # 3. Intentar regularizar con el DNI existente (cambiando el nombre a Ana María)
        response = client.post('/api/paciente/regularizar/', {
            'admision_id': admision_nn.id,
            'documento_identidad': dni_existente,
            'nombre': 'Ana María',
            'apellido': 'López',
            'fecha_nacimiento': '1992-08-20'
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        
        # Verificar que la admisión ahora apunta al paciente existente
        admision_nn.refresh_from_db()
        self.assertEqual(admision_nn.paciente.id, paciente_existente.id)
        
        # Verificar que el paciente existente actualizó sus datos
        paciente_existente.refresh_from_db()
        self.assertEqual(paciente_existente.nombre, 'Ana María')
        
        # Verificar que el paciente NN temporal fue borrado para no contaminar la base de datos
        self.assertFalse(Paciente.objects.filter(documento_identidad=nn_dni).exists())

    def test_page_views_resolve_ok(self):
        """
        Prueba que las cinco páginas de la aplicación se enrutan y renderizan correctamente.
        """
        client = Client()
        client.login(username='testmedico', password='testpass')
        
        pages = ['/', '/medica/', '/admision/', '/limpieza/', '/analiticas/']
        for page in pages:
            response = client.get(page)
            self.assertEqual(response.status_code, 200, f"Error rendering page {page}")


