from django.urls import path
from django.contrib.auth.decorators import login_required, user_passes_test
from medsalud_project.auth_views import is_urgencias_staff
from . import views

urgencias_required = user_passes_test(is_urgencias_staff, login_url='/login/')

def protect(view_func):
    return login_required(urgencias_required(view_func))

urlpatterns = [
    path('', protect(views.dashboard), name='dashboard'),
    path('medica/', protect(views.consola_medica), name='consola_medica'),
    path('admision/', protect(views.admision), name='admision'),
    path('limpieza/', protect(views.limpieza), name='limpieza'),
    path('analiticas/', protect(views.analiticas), name='analiticas'),

    # API de estado del sistema (polling ligero)
    path('api/status/', protect(views.status_api), name='status_api'),
    path('api/trasladar/', protect(views.trasladar_paciente_api), name='trasladar_paciente_api'),

    # APIs transaccionales de pacientes
    path('api/paciente/registrar/', protect(views.registrar_paciente_api), name='registrar_paciente_api'),
    path('api/paciente/shock-trauma/', protect(views.registrar_shock_trauma_api), name='registrar_shock_trauma_api'),
    path('api/paciente/regularizar/', protect(views.regularizar_paciente_nn_api), name='regularizar_paciente_nn_api'),

    # APIs transaccionales de recursos (flujo clínico)
    path('api/recurso/asignar/', protect(views.asignar_recurso_api), name='asignar_recurso_api'),
    path('api/recurso/pre-alta/', protect(views.ordenar_pre_alta_api), name='ordenar_pre_alta_api'),
    path('api/recurso/confirmar-salida/', protect(views.confirmar_salida_api), name='confirmar_salida_api'),
    path('api/recurso/limpieza-completada/', protect(views.registrar_limpieza_api), name='registrar_limpieza_api'),
    path('api/recurso/liberar/', protect(views.liberar_recurso_api), name='liberar_recurso_api'),

    # API de facturación
    path('api/facturacion/cargo/', protect(views.aplicar_cargos_api), name='aplicar_cargos_api'),
    path('api/farmacia/receta/', protect(views.generar_receta_api), name='generar_receta_api'),
    path('api/farmacia/botiquin/', protect(views.administrar_botiquin_api), name='administrar_botiquin_api'),
]
