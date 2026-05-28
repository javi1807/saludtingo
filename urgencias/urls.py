from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('medica/', views.consola_medica, name='consola_medica'),
    path('admision/', views.admision, name='admision'),
    path('limpieza/', views.limpieza, name='limpieza'),
    path('analiticas/', views.analiticas, name='analiticas'),

    # API de estado del sistema (polling ligero)
    path('api/status/', views.status_api, name='status_api'),

    # APIs transaccionales de pacientes
    path('api/paciente/registrar/', views.registrar_paciente_api, name='registrar_paciente_api'),
    path('api/paciente/shock-trauma/', views.registrar_shock_trauma_api, name='registrar_shock_trauma_api'),
    path('api/paciente/regularizar/', views.regularizar_paciente_nn_api, name='regularizar_paciente_nn_api'),

    # APIs transaccionales de recursos (flujo clínico)
    path('api/recurso/asignar/', views.asignar_recurso_api, name='asignar_recurso_api'),
    path('api/recurso/pre-alta/', views.ordenar_pre_alta_api, name='ordenar_pre_alta_api'),
    path('api/recurso/confirmar-salida/', views.confirmar_salida_api, name='confirmar_salida_api'),
    path('api/recurso/limpieza-completada/', views.registrar_limpieza_api, name='registrar_limpieza_api'),
    path('api/recurso/liberar/', views.liberar_recurso_api, name='liberar_recurso_api'),

    # API de facturación
    path('api/facturacion/cargo/', views.aplicar_cargos_api, name='aplicar_cargos_api'),
]
