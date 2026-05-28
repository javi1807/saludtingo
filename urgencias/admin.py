from django.contrib import admin
from .models import Paciente, Recurso, Admision, Insumo, CuentaFacturacion, CargoFacturacion

@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    list_display = ('documento_identidad', 'apellido', 'nombre', 'historia_clinica_num', 'fecha_nacimiento')
    search_fields = ('documento_identidad', 'nombre', 'apellido')

@admin.register(Recurso)
class RecursoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'tipo', 'estado', 'descripcion')
    list_filter = ('tipo', 'estado')
    search_fields = ('codigo',)

@admin.register(Admision)
class AdmisionAdmin(admin.ModelAdmin):
    list_display = ('id', 'paciente', 'triage_nivel', 'recurso_asignado', 'estado', 'fecha_ingreso')
    list_filter = ('triage_nivel', 'estado')
    search_fields = ('paciente__nombre', 'paciente__apellido', 'paciente__documento_identidad')

@admin.register(Insumo)
class InsumoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'stock', 'precio_unitario')
    search_fields = ('codigo', 'nombre')

@admin.register(CuentaFacturacion)
class CuentaFacturacionAdmin(admin.ModelAdmin):
    list_display = ('id', 'admision', 'total_cargado')

@admin.register(CargoFacturacion)
class CargoFacturacionAdmin(admin.ModelAdmin):
    list_display = ('id', 'cuenta', 'insumo', 'cantidad', 'precio_aplicado', 'fecha_cargo')
