from django.db import models
from django.core.exceptions import ValidationError

class Paciente(models.Model):
    documento_identidad = models.CharField(max_length=20, unique=True, db_index=True, verbose_name="Documento de Identidad")
    nombre = models.CharField(max_length=100, verbose_name="Nombre")
    apellido = models.CharField(max_length=100, verbose_name="Apellido")
    fecha_nacimiento = models.DateField(verbose_name="Fecha de Nacimiento")
    historia_clinica_num = models.CharField(max_length=30, unique=True, verbose_name="Número de Historia Clínica")
    alergias_conocidas = models.TextField(blank=True, null=True, help_text="Alergias a medicamentos u otros.")

    def save(self, *args, **kwargs):
        if not self.historia_clinica_num:
            # Generar número de historia clínica determinista basado en el documento de identidad
            self.historia_clinica_num = f"HC-{self.documento_identidad}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.apellido}, {self.nombre} ({self.documento_identidad})"


class Recurso(models.Model):
    TIPO_CHOICES = [
        ('CAMA', 'Cama'),
        ('BOX', 'Box de Atención'),
        ('QUIROFANO', 'Quirófano'),
    ]

    ESTADO_CHOICES = [
        ('DISPONIBLE', 'Disponible'),
        ('OCUPADO', 'Ocupado'),
        ('MANTENIMIENTO', 'En Mantenimiento'),
        ('PRE_ALTA', 'Pre-Alta'),
        ('LIMPIEZA', 'En Limpieza'),
    ]

    codigo = models.CharField(max_length=20, unique=True, db_index=True, verbose_name="Código de Recurso")
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='CAMA', verbose_name="Tipo de Recurso")
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='DISPONIBLE', verbose_name="Estado")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.codigo} ({self.get_estado_display()})"


class Admision(models.Model):
    TRIAGE_CHOICES = [
        ('ROJO', 'Rojo (Nivel 1 - Crítico)'),
        ('NARANJA', 'Naranja (Nivel 2 - Emergencia)'),
        ('AMARILLO', 'Amarillo (Nivel 3 - Urgencia)'),
        ('VERDE', 'Verde (Nivel 4 - Menor)'),
        ('AZUL', 'Azul (Nivel 5 - No Urgente)'),
    ]

    ESTADO_CHOICES = [
        ('EN_ESPERA', 'En Espera de Triage'),
        ('EN_TRIAJE', 'En Triaje / Evaluación'),
        ('ADMITIDO', 'Admitido con Recurso'),
        ('ALTA', 'Dado de Alta / Egreso'),
    ]

    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name="admisiones", verbose_name="Paciente")
    fecha_ingreso = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Ingreso")
    triage_nivel = models.CharField(max_length=20, choices=TRIAGE_CHOICES, default='AMARILLO', verbose_name="Nivel de Triage")
    motivo_consulta = models.TextField(verbose_name="Motivo de Consulta")
    recurso_asignado = models.ForeignKey(Recurso, on_delete=models.SET_NULL, null=True, blank=True, related_name="admisiones_activas", verbose_name="Recurso Asignado")
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='EN_ESPERA', verbose_name="Estado de la Admisión")

    # --- Timestamps de flujo clínico ---
    fecha_triage = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Evaluación Triage")
    fecha_admision_cama = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Asignación de Cama")
    fecha_pre_alta = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Orden de Pre-Alta")
    fecha_alta = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Alta Definitiva")
    notas_alta = models.TextField(blank=True, null=True, verbose_name="Notas de Egreso")

    def __str__(self):
        return f"Admisión #{self.id} - {self.paciente.apellido} ({self.get_estado_display()})"


class Insumo(models.Model):
    codigo = models.CharField(max_length=20, unique=True, db_index=True, verbose_name="Código de Insumo")
    nombre = models.CharField(max_length=100, verbose_name="Nombre de Insumo")
    stock = models.IntegerField(verbose_name="Stock Disponible")
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio Unitario")

    def __str__(self):
        return f"{self.nombre} ({self.codigo}) - Stock: {self.stock}"


class CuentaFacturacion(models.Model):
    admision = models.OneToOneField(Admision, on_delete=models.CASCADE, related_name="cuenta_facturacion", verbose_name="Admisión")
    total_cargado = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Total Cargado")

    def __str__(self):
        return f"Cuenta de Admisión #{self.admision.id} - Total: ${self.total_cargado}"

    def recalcular_total(self):
        total = self.cargos.aggregate(
            total=models.Sum(models.F('cantidad') * models.F('precio_aplicado'))
        )['total'] or 0.00
        self.total_cargado = total
        self.save()


class CargoFacturacion(models.Model):
    cuenta = models.ForeignKey(CuentaFacturacion, on_delete=models.CASCADE, related_name="cargos", verbose_name="Cuenta de Facturación")
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT, related_name="cargos_aplicados", verbose_name="Insumo", null=True, blank=True)
    medicamento = models.ForeignKey('farmacia.Medicamento', on_delete=models.PROTECT, related_name="cargos_aplicados", verbose_name="Medicamento", null=True, blank=True)
    cantidad = models.IntegerField(verbose_name="Cantidad")
    precio_aplicado = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio Aplicado")
    fecha_cargo = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Cargo")

    def __str__(self):
        item = self.insumo.nombre if self.insumo else (self.medicamento.nombre if self.medicamento else 'N/A')
        return f"Cargo: {self.cantidad} x {item} en Cuenta #{self.cuenta.id}"
