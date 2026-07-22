from django.contrib import admin
from .models import Medicamento, InventarioFarmacia, Receta, DetalleReceta, BotiquinSatelite


class DetalleRecetaInline(admin.TabularInline):
    model = DetalleReceta
    extra = 0
    readonly_fields = ('medicamento', 'cantidad', 'indicaciones')


@admin.register(Medicamento)
class MedicamentoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'principio_activo', 'concentracion', 'precio_unitario')
    search_fields = ('codigo', 'nombre', 'principio_activo')
    list_filter = ('concentracion',)


@admin.register(InventarioFarmacia)
class InventarioFarmaciaAdmin(admin.ModelAdmin):
    list_display = ('medicamento', 'stock_fisico', 'stock_comprometido', 'get_stock_disponible')
    search_fields = ('medicamento__nombre', 'medicamento__codigo')
    list_filter = ('stock_fisico',)

    @admin.display(description='Stock Disponible')
    def get_stock_disponible(self, obj):
        return obj.stock_disponible


@admin.register(Receta)
class RecetaAdmin(admin.ModelAdmin):
    list_display = ('id', 'admision', 'estado', 'prioridad', 'medico', 'farmaceutico_despacho', 'fecha_emision', 'fecha_despacho')
    list_filter = ('estado', 'prioridad')
    search_fields = ('admision__paciente__nombre', 'admision__paciente__apellido', 'medico')
    inlines = [DetalleRecetaInline]
    readonly_fields = ('fecha_emision',)


@admin.register(BotiquinSatelite)
class BotiquinSateliteAdmin(admin.ModelAdmin):
    list_display = ('ubicacion', 'medicamento', 'cantidad_fisica')
    search_fields = ('ubicacion', 'medicamento__nombre')
    list_filter = ('ubicacion',)
