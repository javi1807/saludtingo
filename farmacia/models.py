from django.db import models
from urgencias.models import Admision

class Medicamento(models.Model):
    codigo = models.CharField(max_length=20, unique=True, db_index=True, verbose_name="Código")
    nombre = models.CharField(max_length=150, verbose_name="Nombre Comercial")
    principio_activo = models.CharField(max_length=150, verbose_name="Principio Activo")
    concentracion = models.CharField(max_length=50, verbose_name="Concentración")
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio Unitario")

    def __str__(self):
        return f"{self.nombre} ({self.principio_activo} - {self.concentracion})"


class InventarioFarmacia(models.Model):
    medicamento = models.OneToOneField(Medicamento, on_delete=models.CASCADE, related_name="inventario")
    stock_fisico = models.IntegerField(default=0, verbose_name="Stock Físico (Estantes)")
    stock_comprometido = models.IntegerField(default=0, verbose_name="Stock Comprometido (En Recetas)")

    @property
    def stock_disponible(self):
        return self.stock_fisico - self.stock_comprometido

    def __str__(self):
        return f"{self.medicamento.nombre} - Físico: {self.stock_fisico} | Disponible: {self.stock_disponible}"

class BotiquinSatelite(models.Model):
    medicamento = models.ForeignKey(Medicamento, on_delete=models.CASCADE, related_name="botiquines")
    ubicacion = models.CharField(max_length=100, verbose_name="Ubicación (Ej. Carro Paro Box 3)")
    cantidad_fisica = models.IntegerField(default=0, verbose_name="Cantidad Físico en Botiquín")
    
    def __str__(self):
        return f"{self.ubicacion} - {self.medicamento.nombre}: {self.cantidad_fisica} uds."


class Receta(models.Model):
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('DESPACHADA', 'Despachada'),
        ('CANCELADA', 'Cancelada'),
        ('ADMINISTRADO_BOTIQUIN', 'Administrado de Botiquín (Retroactivo)'),
    ]
    PRIORIDAD_CHOICES = [
        ('RUTINA', 'Rutina'),
        ('URGENTE', 'Urgente'),
        ('EMERGENCIA', 'Emergencia / STAT'),
    ]

    admision = models.ForeignKey(Admision, on_delete=models.CASCADE, related_name='recetas')
    estado = models.CharField(max_length=30, choices=ESTADO_CHOICES, default='PENDIENTE')
    prioridad = models.CharField(max_length=20, choices=PRIORIDAD_CHOICES, default='RUTINA')
    fecha_emision = models.DateTimeField(auto_now_add=True)
    fecha_despacho = models.DateTimeField(null=True, blank=True)
    medico = models.CharField(max_length=100, blank=True, null=True, verbose_name="Médico Prescriptor")
    farmaceutico_despacho = models.CharField(max_length=100, blank=True, null=True, verbose_name="Farmacéutico que Despachó")

    def __str__(self):
        return f"Receta #{self.id} - Admisión {self.admision.id} ({self.estado})"


class DetalleReceta(models.Model):
    receta = models.ForeignKey(Receta, on_delete=models.CASCADE, related_name="detalles")
    medicamento = models.ForeignKey(Medicamento, on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField()
    indicaciones = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.cantidad} x {self.medicamento.nombre} (Receta #{self.receta.id})"
