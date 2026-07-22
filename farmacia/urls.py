from django.urls import path
from django.contrib.auth.decorators import login_required, user_passes_test
from medsalud_project.auth_views import is_farmacia_staff
from . import views

farmacia_required = user_passes_test(is_farmacia_staff, login_url='/login/')

def protect(view_func):
    return login_required(farmacia_required(view_func))

app_name = 'farmacia'

urlpatterns = [
    path('dashboard/', protect(views.dashboard_farmacia), name='dashboard'),
    path('terminal/', protect(views.terminal_farmacia), name='terminal'),
    path('api/receta/<int:receta_id>/', protect(views.api_obtener_receta), name='api_obtener_receta'),
    path('inventario/', protect(views.inventario_farmacia), name='inventario'),
    path('historial/', protect(views.historial_recetas), name='historial'),
    path('despachar/<int:receta_id>/', protect(views.despachar_receta), name='despachar_receta'),
    path('cancelar/<int:receta_id>/', protect(views.cancelar_receta_api), name='cancelar_receta'),
    path('api/reponer/', protect(views.reponer_stock_api), name='reponer_stock_api'),
    path('api/reponer_botiquin/', protect(views.reponer_botiquin_api), name='reponer_botiquin_api'),
]
