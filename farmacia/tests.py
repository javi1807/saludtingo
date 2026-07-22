import json
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, Group
from farmacia.models import Medicamento, InventarioFarmacia, Receta, DetalleReceta
from urgencias.models import Paciente, Admision, CuentaFacturacion


class FarmaciaIntegrationTests(TestCase):
    def setUp(self):
        self.client = Client()
        
        # Create user with proper group permissions
        self.user = User.objects.create_user(username='testfarma', password='testpass')
        farmacia_group, _ = Group.objects.get_or_create(name='Farmacia_Staff')
        urgencias_group, _ = Group.objects.get_or_create(name='Urgencias_Staff')
        self.user.groups.add(farmacia_group, urgencias_group)
        self.client.login(username='testfarma', password='testpass')
        
        # Crear Paciente y Admision
        self.paciente = Paciente.objects.create(
            documento_identidad='123456',
            nombre='Test',
            apellido='Paciente',
            fecha_nacimiento='1990-01-01'
        )
        self.admision = Admision.objects.create(
            paciente=self.paciente,
            triage_nivel='VERDE',
            motivo_consulta='Dolor leve'
        )
        self.cuenta = CuentaFacturacion.objects.create(admision=self.admision)
        
        # Crear Medicamento e Inventario con nueva arquitectura
        self.med = Medicamento.objects.create(
            codigo='MED01',
            nombre='Paracetamol',
            principio_activo='Paracetamol',
            concentracion='500mg',
            precio_unitario=Decimal('10.50')
        )
        self.inventario = InventarioFarmacia.objects.create(
            medicamento=self.med,
            stock_fisico=50,
            stock_comprometido=0
        )

    def test_stock_disponible_property(self):
        """Verifica que la propiedad stock_disponible calcule correctamente."""
        self.assertEqual(self.inventario.stock_disponible, 50)
        self.inventario.stock_comprometido = 10
        self.inventario.save()
        self.inventario.refresh_from_db()
        self.assertEqual(self.inventario.stock_disponible, 40)

    def test_generar_receta_compromete_stock(self):
        """Al generar receta desde urgencias, el stock comprometido debe aumentar."""
        url = reverse('generar_receta_api')
        payload = {
            'admision_id': self.admision.id,
            'medicamentos': json.dumps([{'id': self.med.id, 'cantidad': 2}])
        }
        
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 200)
        
        # Validar receta creada
        self.assertEqual(Receta.objects.count(), 1)
        receta = Receta.objects.first()
        self.assertEqual(receta.estado, 'PENDIENTE')
        self.assertEqual(receta.detalles.count(), 1)
        
        # Validar stock comprometido
        self.inventario.refresh_from_db()
        self.assertEqual(self.inventario.stock_fisico, 50)  # Físico no cambia
        self.assertEqual(self.inventario.stock_comprometido, 2)  # Comprometido sube
        self.assertEqual(self.inventario.stock_disponible, 48)  # Disponible baja

    def test_despachar_receta_descuenta_fisico_y_comprometido(self):
        """Al despachar, se reduce stock_fisico Y stock_comprometido."""
        # Simular que ya se comprometió stock (como haría generar_receta_api)
        self.inventario.stock_comprometido = 3
        self.inventario.save()
        
        receta = Receta.objects.create(admision=self.admision, estado='PENDIENTE')
        DetalleReceta.objects.create(receta=receta, medicamento=self.med, cantidad=3)
        
        url = reverse('farmacia:despachar_receta', args=[receta.id])
        response = self.client.post(url)
        
        # Verificar redirección
        self.assertEqual(response.status_code, 302)
        
        # Verificar estado
        receta.refresh_from_db()
        self.assertEqual(receta.estado, 'DESPACHADA')
        self.assertIsNotNone(receta.fecha_despacho)
        
        # Verificar stock (partida doble)
        self.inventario.refresh_from_db()
        self.assertEqual(self.inventario.stock_fisico, 47)  # 50 - 3
        self.assertEqual(self.inventario.stock_comprometido, 0)  # 3 - 3
        
        # Verificar cargos
        self.cuenta.refresh_from_db()
        self.assertEqual(self.cuenta.cargos.count(), 1)
        self.assertEqual(self.cuenta.total_cargado, Decimal('31.50'))

    def test_cancelar_receta_devuelve_stock_comprometido(self):
        """Al cancelar una receta pendiente, se devuelve el stock comprometido."""
        # Simular prescripción que comprometió stock
        self.inventario.stock_comprometido = 5
        self.inventario.save()
        
        receta = Receta.objects.create(admision=self.admision, estado='PENDIENTE')
        DetalleReceta.objects.create(receta=receta, medicamento=self.med, cantidad=5)
        
        url = reverse('farmacia:cancelar_receta', args=[receta.id])
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, 200)
        
        receta.refresh_from_db()
        self.assertEqual(receta.estado, 'CANCELADA')
        
        # Stock comprometido devuelto
        self.inventario.refresh_from_db()
        self.assertEqual(self.inventario.stock_fisico, 50)  # Sin cambio
        self.assertEqual(self.inventario.stock_comprometido, 0)  # Devuelto

    def test_no_cancelar_receta_ya_despachada(self):
        """No se debe poder cancelar una receta ya despachada."""
        receta = Receta.objects.create(admision=self.admision, estado='DESPACHADA')
        
        url = reverse('farmacia:cancelar_receta', args=[receta.id])
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, 400)

    def test_receta_rechazada_si_stock_insuficiente(self):
        """Si no hay stock disponible, la receta debe ser rechazada."""
        # Agotar stock
        self.inventario.stock_fisico = 1
        self.inventario.save()
        
        url = reverse('generar_receta_api')
        payload = {
            'admision_id': self.admision.id,
            'medicamentos': json.dumps([{'id': self.med.id, 'cantidad': 5}])
        }
        
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 400)
        
        # No se creó receta
        self.assertEqual(Receta.objects.count(), 0)
