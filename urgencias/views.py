import json
from decimal import Decimal
from datetime import date, timedelta
from django.shortcuts import render
from django.http import JsonResponse
from django.db import transaction, IntegrityError
from django.core.exceptions import ValidationError
from django.views.decorators.http import require_POST
from django.db.models import Prefetch, Sum, Case, When, Value, IntegerField
from django.utils import timezone

from .models import Paciente, Recurso, Admision, Insumo, CuentaFacturacion, CargoFacturacion
from .decorators import retry_on_db_lock
from farmacia.models import Medicamento, Receta, DetalleReceta, InventarioFarmacia, BotiquinSatelite

# --- VIEWS DE NAVEGACIÓN ---
def dashboard(request):
    """Renderiza el monitor de camas principal (Overview)."""
    active_admisiones_prefetch = Prefetch(
        'admisiones_activas',
        queryset=Admision.objects.exclude(estado='ALTA').select_related('paciente')
    )
    recursos = Recurso.objects.prefetch_related(active_admisiones_prefetch).all().order_by('tipo', 'codigo')
    
    admisiones_activas = Admision.objects.select_related(
        'paciente',
        'recurso_asignado',
        'cuenta_facturacion'
    ).exclude(estado='ALTA').order_by('-fecha_ingreso')
    
    stats = {
        'total_pacientes': Paciente.objects.count(),
        'admisiones_activas': admisiones_activas.count(),
        'camas_libres': RecursosCount(recursos, 'CAMA', 'DISPONIBLE'),
        'camas_ocupadas': RecursosCount(recursos, 'CAMA', 'OCUPADO'),
        'boxes_libres': RecursosCount(recursos, 'BOX', 'DISPONIBLE'),
        'boxes_ocupados': RecursosCount(recursos, 'BOX', 'OCUPADO'),
    }
    stats['recursos_limpieza'] = RecursosCount(recursos, None, 'LIMPIEZA')
    stats['total_recursos'] = len(recursos)

    context = {
        'recursos': recursos,
        'admisiones': admisiones_activas,
        'stats': stats,
        'active_page': 'dashboard',
    }
    return render(request, 'urgencias/dashboard.html', context)


def consola_medica(request):
    """Renderiza la consola médica con las admisiones y medicamentos."""
    active_admisiones_prefetch = Prefetch(
        'admisiones_activas',
        queryset=Admision.objects.exclude(estado='ALTA').select_related('paciente')
    )
    recursos = Recurso.objects.prefetch_related(active_admisiones_prefetch).all().order_by('tipo', 'codigo')
    
    admisiones_activas = Admision.objects.select_related(
        'paciente',
        'recurso_asignado',
        'cuenta_facturacion'
    ).exclude(estado='ALTA').annotate(
        triage_order=Case(
            When(triage_nivel='ROJO', then=Value(1)),
            When(triage_nivel='NARANJA', then=Value(2)),
            When(triage_nivel='AMARILLO', then=Value(3)),
            When(triage_nivel='VERDE', then=Value(4)),
            When(triage_nivel='AZUL', then=Value(5)),
            default=Value(6),
            output_field=IntegerField(),
        )
    ).order_by('triage_order', 'fecha_ingreso')
    
    pacientes = Paciente.objects.all().order_by('-id')[:20]
    insumos = Insumo.objects.all().order_by('codigo')
    medicamentos = Medicamento.objects.all().order_by('nombre')

    context = {
        'recursos': recursos,
        'admisiones': admisiones_activas,
        'pacientes': pacientes,
        'insumos': insumos,
        'medicamentos': medicamentos,
        'active_page': 'consola_medica',
    }
    return render(request, 'urgencias/consola_medica.html', context)


def admision(request):
    """Renderiza el formulario de admisiones y triaje."""
    active_admisiones_prefetch = Prefetch(
        'admisiones_activas',
        queryset=Admision.objects.exclude(estado='ALTA').select_related('paciente')
    )
    recursos = Recurso.objects.prefetch_related(active_admisiones_prefetch).all().order_by('tipo', 'codigo')
    
    admisiones_activas = Admision.objects.select_related(
        'paciente',
        'recurso_asignado',
        'cuenta_facturacion'
    ).exclude(estado='ALTA').order_by('-fecha_ingreso')

    camas_libres = RecursosCount(recursos, 'CAMA', 'DISPONIBLE')
    boxes_libres = RecursosCount(recursos, 'BOX', 'DISPONIBLE')

    context = {
        'recursos': recursos,
        'admisiones': admisiones_activas,
        'camas_libres': camas_libres,
        'boxes_libres': boxes_libres,
        'active_page': 'admision',
    }
    return render(request, 'urgencias/admision.html', context)


def limpieza(request):
    """Renderiza el monitor de desinfección y limpieza."""
    active_admisiones_prefetch = Prefetch(
        'admisiones_activas',
        queryset=Admision.objects.exclude(estado='ALTA').select_related('paciente')
    )
    recursos = Recurso.objects.prefetch_related(active_admisiones_prefetch).all().order_by('tipo', 'codigo')
    
    admisiones_activas = Admision.objects.select_related(
        'paciente',
        'recurso_asignado',
        'cuenta_facturacion'
    ).exclude(estado='ALTA').order_by('-fecha_ingreso')

    context = {
        'recursos': recursos,
        'admisiones': admisiones_activas,
        'active_page': 'limpieza',
    }
    return render(request, 'urgencias/limpieza.html', context)


def analiticas(request):
    """Renderiza la sección de reportes y analíticas gráficas."""
    active_admisiones_prefetch = Prefetch(
        'admisiones_activas',
        queryset=Admision.objects.exclude(estado='ALTA').select_related('paciente')
    )
    recursos = Recurso.objects.prefetch_related(active_admisiones_prefetch).all().order_by('tipo', 'codigo')
    
    admisiones_activas = Admision.objects.select_related(
        'paciente',
        'recurso_asignado',
        'cuenta_facturacion'
    ).exclude(estado='ALTA').order_by('-fecha_ingreso')
    
    insumos = Insumo.objects.all().order_by('codigo')

    stats = {
        'total_pacientes': Paciente.objects.count(),
        'admisiones_activas': admisiones_activas.count(),
        'camas_libres': RecursosCount(recursos, 'CAMA', 'DISPONIBLE'),
        'camas_ocupadas': RecursosCount(recursos, 'CAMA', 'OCUPADO'),
        'boxes_libres': RecursosCount(recursos, 'BOX', 'DISPONIBLE'),
        'boxes_ocupados': RecursosCount(recursos, 'BOX', 'OCUPADO'),
    }
    stats['recursos_limpieza'] = RecursosCount(recursos, None, 'LIMPIEZA')
    stats['total_recursos'] = len(recursos)

    charts = build_dashboard_charts(recursos, admisiones_activas, insumos)

    context = {
        'recursos': recursos,
        'admisiones': admisiones_activas,
        'stats': stats,
        'charts': charts,
        'active_page': 'analiticas',
    }
    return render(request, 'urgencias/analiticas.html', context)


def RecursosCount(recursos, tipo, estado):
    return len([r for r in recursos if (tipo is None or r.tipo == tipo) and r.estado == estado])


def percent(value, total):
    if not total:
        return 0
    return round((value / total) * 100)


def minutos_desde(dt):
    """Calcula los minutos transcurridos desde un datetime hasta ahora."""
    if not dt:
        return None
    delta = timezone.now() - dt
    return int(delta.total_seconds() // 60)


def status_api(request):
    """
    Endpoint GET ligero para polling de estado del sistema.
    Devuelve contadores de recursos y admisiones activas en JSON.
    """
    recursos = Recurso.objects.all()
    admisiones_activas = Admision.objects.exclude(estado='ALTA')

    # Contadores por tipo y estado
    camas = list(recursos.filter(tipo='CAMA'))
    boxes = list(recursos.filter(tipo='BOX'))
    quirofanos = list(recursos.filter(tipo='QUIROFANO'))

    # Alertas: pacientes críticos (ROJO/NARANJA) sin cama > 30 minutos
    alertas_criticas = []
    for adm in admisiones_activas.filter(
        triage_nivel__in=['ROJO', 'NARANJA'],
        recurso_asignado__isnull=True
    ).select_related('paciente'):
        minutos = minutos_desde(adm.fecha_ingreso)
        if minutos is not None and minutos >= 30:
            alertas_criticas.append({
                'admision_id': adm.id,
                'paciente': f"{adm.paciente.nombre} {adm.paciente.apellido}",
                'triage': adm.triage_nivel,
                'minutos_espera': minutos,
            })

    return JsonResponse({
        'timestamp': timezone.now().isoformat(),
        'stats': {
            'admisiones_activas': admisiones_activas.count(),
            'camas_libres': len([r for r in camas if r.estado == 'DISPONIBLE']),
            'camas_ocupadas': len([r for r in camas if r.estado == 'OCUPADO']),
            'camas_pre_alta': len([r for r in camas if r.estado == 'PRE_ALTA']),
            'camas_limpieza': len([r for r in camas if r.estado == 'LIMPIEZA']),
            'boxes_libres': len([r for r in boxes if r.estado == 'DISPONIBLE']),
            'boxes_ocupados': len([r for r in boxes if r.estado == 'OCUPADO']),
            'quirofanos_libres': len([r for r in quirofanos if r.estado == 'DISPONIBLE']),
            'total_recursos': recursos.count(),
        },
        'alertas_criticas': alertas_criticas,
    })


def build_dashboard_charts(recursos, admisiones_activas, insumos):
    """Agrupa datos reales para los gráficos del dashboard sin depender de mocks."""
    recursos_list = list(recursos)
    admisiones_list = list(admisiones_activas)
    insumos_list = list(insumos)

    estado_labels = dict(Recurso.ESTADO_CHOICES)
    tipo_labels = dict(Recurso.TIPO_CHOICES)
    triage_labels = dict(Admision.TRIAGE_CHOICES)
    admision_estado_labels = dict(Admision.ESTADO_CHOICES)

    total_recursos = len(recursos_list)
    recursos_por_estado = []
    for estado, label in Recurso.ESTADO_CHOICES:
        count = len([r for r in recursos_list if r.estado == estado])
        recursos_por_estado.append({
            'key': estado.lower(),
            'label': label,
            'count': count,
            'percent': percent(count, total_recursos),
        })

    ocupacion_por_tipo = []
    for tipo, label in Recurso.TIPO_CHOICES:
        items = [r for r in recursos_list if r.tipo == tipo]
        total = len(items)
        ocupados = len([r for r in items if r.estado in ['OCUPADO', 'PRE_ALTA']])
        disponibles = len([r for r in items if r.estado == 'DISPONIBLE'])
        bloqueados = total - ocupados - disponibles
        ocupacion_por_tipo.append({
            'key': tipo.lower(),
            'label': label,
            'total': total,
            'ocupados': ocupados,
            'disponibles': disponibles,
            'bloqueados': bloqueados,
            'percent': percent(ocupados, total),
        })

    total_admisiones = len(admisiones_list)
    triage_activo = []
    for triage, label in Admision.TRIAGE_CHOICES:
        count = len([a for a in admisiones_list if a.triage_nivel == triage])
        triage_activo.append({
            'key': triage.lower(),
            'label': label,
            'count': count,
            'percent': percent(count, total_admisiones),
        })

    admisiones_por_estado = []
    for estado, label in Admision.ESTADO_CHOICES:
        if estado == 'ALTA':
            continue
        count = len([a for a in admisiones_list if a.estado == estado])
        admisiones_por_estado.append({
            'key': estado.lower(),
            'label': label,
            'count': count,
            'percent': percent(count, total_admisiones),
        })

    pacientes_por_edad = []
    age_buckets = {'0-17': 0, '18-35': 0, '36-55': 0, '56-75': 0, '76+': 0}
    for paciente in Paciente.objects.exclude(fecha_nacimiento__isnull=True):
        if paciente.fecha_nacimiento:
            age = (date.today() - paciente.fecha_nacimiento).days // 365
            if age <= 17:
                age_buckets['0-17'] += 1
            elif age <= 35:
                age_buckets['18-35'] += 1
            elif age <= 55:
                age_buckets['36-55'] += 1
            elif age <= 75:
                age_buckets['56-75'] += 1
            else:
                age_buckets['76+'] += 1

    for key, label in [('0-17', '0-17 años'), ('18-35', '18-35 años'), ('36-55', '36-55 años'), ('56-75', '56-75 años'), ('76+', '76+ años')]:
        pacientes_por_edad.append({
            'key': key,
            'label': label,
            'count': age_buckets[key],
            'percent': percent(age_buckets[key], sum(age_buckets.values())),
        })

    ingresos_por_turno = []
    turno_counts = {'mañana': 0, 'tarde': 0, 'noche': 0}
    for adm in admisiones_list:
        if adm.fecha_ingreso:
            hour = adm.fecha_ingreso.hour
            if 6 <= hour <= 13:
                turno_counts['mañana'] += 1
            elif 14 <= hour <= 21:
                turno_counts['tarde'] += 1
            else:
                turno_counts['noche'] += 1

    for key, label in [('mañana', 'Mañana 06-13'), ('tarde', 'Tarde 14-21'), ('noche', 'Noche 22-05')]:
        ingresos_por_turno.append({
            'key': key,
            'label': label,
            'count': turno_counts[key],
            'percent': percent(turno_counts[key], total_admisiones),
        })

    ultima_semana = [(date.today() - timedelta(days=i)) for i in range(6, -1, -1)]
    admisiones_por_dia = {dia: 0 for dia in ultima_semana}
    
    # Obtener todas las admisiones (incluyendo las dadas de alta) para los últimos 7 días
    fecha_limite = timezone.now() - timedelta(days=7)
    admisiones_recientes = Admision.objects.filter(fecha_ingreso__gte=fecha_limite)
    
    for adm in admisiones_recientes:
        if adm.fecha_ingreso:
            fecha = adm.fecha_ingreso.date()
            if fecha in admisiones_por_dia:
                admisiones_por_dia[fecha] += 1

    max_dia = max(admisiones_por_dia.values(), default=0)
    admisiones_ultimos_siete = [
        {
            'label': dia.strftime('%d/%m'),
            'count': admisiones_por_dia[dia],
            'percent': percent(admisiones_por_dia[dia], max_dia),
        }
        for dia in ultima_semana
    ]

    facturacion_total = CuentaFacturacion.objects.aggregate(total=Sum('total_cargado'))['total'] or Decimal('0.00')
    cargos_total = CargoFacturacion.objects.aggregate(total=Sum('cantidad'))['total'] or 0

    return {
        'recursos_por_estado': recursos_por_estado,
        'ocupacion_por_tipo': ocupacion_por_tipo,
        'triage_activo': triage_activo,
        'admisiones_por_estado': admisiones_por_estado,
        'pacientes_por_edad': pacientes_por_edad,
        'ingresos_por_turno': ingresos_por_turno,
        'admisiones_ultimos_siete': admisiones_ultimos_siete,
        'facturacion_total': facturacion_total,
        'cargos_total': cargos_total,
        'estado_labels': estado_labels,
        'tipo_labels': tipo_labels,
        'triage_labels': triage_labels,
        'admision_estado_labels': admision_estado_labels,
    }


# --- APIS TRANSACCIONALES CORE ---

@require_POST
@retry_on_db_lock()
def registrar_paciente_api(request):
    """
    Registra o actualiza un paciente y crea una admisión de forma segura.
    Evita colisiones si hay solicitudes simultáneas del mismo paciente.
    """
    documento = request.POST.get('documento_identidad', '').strip()
    nombre = request.POST.get('nombre', '').strip()
    apellido = request.POST.get('apellido', '').strip()
    fecha_nacimiento = request.POST.get('fecha_nacimiento', '')
    motivo = request.POST.get('motivo_consulta', '').strip()
    triage = request.POST.get('triage_nivel', 'AMARILLO')

    if not (documento and nombre and apellido and fecha_nacimiento and motivo):
        return JsonResponse({'success': False, 'message': 'Todos los campos son obligatorios'}, status=400)

    try:
        # Iniciamos bloque atómico
        with transaction.atomic():
            # Intentamos crear o actualizar el paciente usando select_for_update para evitar colisiones concurrentes
            # En SQLite, select_for_update bloquea la tabla completa si no hay índices precisos, pero el DNI está indexado.
            # Capturamos excepciones de clave única por si dos hilos intentan hacer INSERT a la vez.
            try:
                # Intento de obtener el registro bloqueado
                paciente = Paciente.objects.select_for_update().get(documento_identidad=documento)
                # Si existe, actualizamos los datos
                paciente.nombre = nombre
                paciente.apellido = apellido
                paciente.fecha_nacimiento = fecha_nacimiento
                paciente.save()
                created = False
            except Paciente.DoesNotExist:
                # Si no existe, creamos uno nuevo
                try:
                    paciente = Paciente(
                        documento_identidad=documento,
                        nombre=nombre,
                        apellido=apellido,
                        fecha_nacimiento=fecha_nacimiento
                    )
                    paciente.save()
                    created = True
                except IntegrityError:
                    # En caso de colisión de clave única (otra solicitud lo insertó entre el get y el save),
                    # volvemos a obtener el registro bloqueado
                    paciente = Paciente.objects.select_for_update().get(documento_identidad=documento)
                    paciente.nombre = nombre
                    paciente.apellido = apellido
                    paciente.fecha_nacimiento = fecha_nacimiento
                    paciente.save()
                    created = False

            # Validar que no tenga ya una admisión activa en curso
            admision_activa = Admision.objects.filter(paciente=paciente).exclude(estado='ALTA').first()
            if admision_activa:
                raise ValidationError(f"El paciente ya cuenta con una admisión activa (ID #{admision_activa.id})")

            # Crear admisión — registrar timestamp de ingreso/triage
            admision = Admision.objects.create(
                paciente=paciente,
                motivo_consulta=motivo,
                triage_nivel=triage,
                estado='EN_ESPERA',
                fecha_triage=timezone.now()
            )

            # Crear cuenta de facturación inicial vacía
            CuentaFacturacion.objects.create(admision=admision)

        accion = "creado" if created else "actualizado"
        return JsonResponse({
            'success': True,
            'message': f"Paciente {accion} e ingresado a triage exitosamente. Admisión #{admision.id}",
            'data': {
                'admision_id': admision.id,
                'paciente_id': paciente.id,
                'historia_clinica': paciente.historia_clinica_num
            }
        })
    except ValidationError as e:
        return JsonResponse({'success': False, 'message': str(e.message if hasattr(e, 'message') else e)}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'message': f"Error interno: {str(e)}"}, status=500)


@require_POST
@retry_on_db_lock()
def asignar_recurso_api(request):
    """
    Asigna una cama o box de atención a una admisión activa.
    Usa control de concurrencia estricto (Pessimistic Locking) para evitar doble asignación.
    """
    admision_id = request.POST.get('admision_id')
    recurso_id = request.POST.get('recurso_id')

    if not (admision_id and recurso_id):
        return JsonResponse({'success': False, 'message': 'Faltan parámetros de admisión o recurso'}, status=400)

    try:
        with transaction.atomic():
            # 1. Bloquear y verificar el recurso
            recurso = Recurso.objects.select_for_update().get(id=recurso_id)
            
            if recurso.estado != 'DISPONIBLE':
                raise ValidationError(f"El recurso {recurso.codigo} no está disponible (Estado actual: {recurso.get_estado_display()})")

            # 2. Bloquear y obtener la admisión
            admision = Admision.objects.select_for_update().get(id=admision_id)
            if admision.estado == 'ALTA':
                raise ValidationError("No se puede asignar un recurso a una admisión que ya fue dada de alta")

            # 3. Si la admisión ya tenía un recurso asignado, liberarlo
            if admision.recurso_asignado:
                recurso_viejo = Recurso.objects.select_for_update().get(id=admision.recurso_asignado.id)
                recurso_viejo.estado = 'DISPONIBLE'
                recurso_viejo.save()

            # 4. Asignar recurso y actualizar estados — registrar timestamp
            recurso.estado = 'OCUPADO'
            recurso.save()

            admision.recurso_asignado = recurso
            admision.estado = 'ADMITIDO'
            admision.fecha_admision_cama = timezone.now()
            admision.save()

        return JsonResponse({
            'success': True,
            'message': f"Recurso {recurso.codigo} asignado con éxito a la Admisión #{admision.id}."
        })
    except Recurso.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Recurso no encontrado'}, status=404)
    except Admision.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Admisión no encontrada'}, status=404)
    except ValidationError as e:
        return JsonResponse({'success': False, 'message': str(e.message if hasattr(e, 'message') else e)}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'message': f"Error transaccional: {str(e)}"}, status=500)


@require_POST
@retry_on_db_lock()
def aplicar_cargos_api(request):
    """
    Registra la aplicación de un insumo médico, descontando el inventario
    y añadiendo el costo a la cuenta del paciente de manera atómica (ACID).
    """
    admision_id = request.POST.get('admision_id')
    insumo_id = request.POST.get('insumo_id')
    cantidad_str = request.POST.get('cantidad', '1')

    if not (admision_id and insumo_id):
        return JsonResponse({'success': False, 'message': 'Faltan parámetros indispensables'}, status=400)

    try:
        cantidad = int(cantidad_str)
        if cantidad <= 0:
            raise ValidationError("La cantidad debe ser mayor a cero")
    except ValueError:
        return JsonResponse({'success': False, 'message': 'Cantidad inválida'}, status=400)

    try:
        with transaction.atomic():
            # 1. Obtener y bloquear la cuenta de facturación
            cuenta = CuentaFacturacion.objects.select_for_update().get(admision_id=admision_id)

            # 2. Obtener y bloquear el insumo del inventario
            insumo = Insumo.objects.select_for_update().get(id=insumo_id)

            # 3. Validar stock disponible
            if insumo.stock < cantidad:
                raise ValidationError(
                    f"Stock insuficiente para {insumo.nombre}. Requerido: {cantidad}, Disponible: {insumo.stock}"
                )

            # 4. Descontar stock
            insumo.stock -= cantidad
            insumo.save()

            # 5. Crear el cargo de facturación
            CargoFacturacion.objects.create(
                cuenta=cuenta,
                insumo=insumo,
                cantidad=cantidad,
                precio_aplicado=insumo.precio_unitario
            )

            # 6. Recalcular el total cargado a la cuenta
            cuenta.recalcular_total()

        return JsonResponse({
            'success': True,
            'message': f"Se cargaron {cantidad} unidad(es) de {insumo.nombre} a la cuenta del paciente. Stock restante: {insumo.stock}."
        })
    except CuentaFacturacion.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'No existe una cuenta de facturación activa para esta admisión'}, status=404)
    except Insumo.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Insumo no encontrado'}, status=404)
    except ValidationError as e:
        return JsonResponse({'success': False, 'message': str(e.message if hasattr(e, 'message') else e)}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'message': f"Error transaccional: {str(e)}"}, status=500)


@require_POST
@retry_on_db_lock()
def liberar_recurso_api(request):
    """
    Libera un recurso asignado (alta médica) de manera atómica.
    """
    admision_id = request.POST.get('admision_id')

    if not admision_id:
        return JsonResponse({'success': False, 'message': 'ID de admisión requerido'}, status=400)

    try:
        with transaction.atomic():
            admision = Admision.objects.select_for_update().get(id=admision_id)
            
            recurso = admision.recurso_asignado
            if recurso:
                recurso = Recurso.objects.select_for_update().get(id=recurso.id)
                recurso.estado = 'DISPONIBLE'
                recurso.save()
                
                admision.recurso_asignado = None

            admision.estado = 'ALTA'
            admision.fecha_alta = timezone.now()
            admision.save()

        return JsonResponse({
            'success': True,
            'message': f"Alta médica procesada. Admisión #{admision.id} cerrada y recurso liberado."
        })
    except Admision.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Admisión no encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': f"Error al dar de alta: {str(e)}"}, status=500)


def registrar_shock_trauma_api(request):
    """
    Bypass Shock Trauma: Registra un paciente NN y le asigna una cama crítica disponible de manera inmediata y atómica.
    """
    import uuid
    nn_id = f"NN-{uuid.uuid4().hex[:8].upper()}"
    
    try:
        with transaction.atomic():
            # 1. Crear el paciente NN
            paciente = Paciente.objects.create(
                documento_identidad=nn_id,
                nombre="Paciente NN",
                apellido="Shock Trauma",
                fecha_nacimiento="2000-01-01"
            )
            
            # 2. Buscar y bloquear una cama crítica (preferencia CAMA de tipo CAMA)
            recurso = Recurso.objects.select_for_update().filter(tipo='CAMA', estado='DISPONIBLE').first()
            if not recurso:
                # Si no hay camas, buscar cualquier box disponible
                recurso = Recurso.objects.select_for_update().filter(tipo='BOX', estado='DISPONIBLE').first()
                
            if not recurso:
                raise ValidationError("No hay recursos críticos disponibles (camas/boxes) en este momento.")
                
            recurso.estado = 'OCUPADO'
            recurso.save()
            
            # 3. Crear admisión directa en estado ADMITIDO y triage ROJO
            admision = Admision.objects.create(
                paciente=paciente,
                motivo_consulta="INGRESO CRÍTICO - SHOCK TRAUMA BYPASS",
                triage_nivel='ROJO',
                recurso_asignado=recurso,
                estado='ADMITIDO'
            )
            
            # 4. Crear cuenta de facturación
            CuentaFacturacion.objects.create(admision=admision)
            
        return JsonResponse({
            'success': True,
            'message': f"Bypass Shock Trauma completado. Paciente registrado temporalmente como {paciente.nombre} ({paciente.documento_identidad}) y asignado a {recurso.codigo}."
        })
    except ValidationError as e:
        return JsonResponse({'success': False, 'message': str(e.message if hasattr(e, 'message') else e)}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'message': f"Error en Shock Trauma Bypass: {str(e)}"}, status=500)


@require_POST
@retry_on_db_lock()
def ordenar_pre_alta_api(request):
    """
    El médico de guardia da la orden de pre-alta. El recurso queda reservado (PRE_ALTA) pero no libre.
    """
    admision_id = request.POST.get('admision_id')
    if not admision_id:
        return JsonResponse({'success': False, 'message': 'ID de admisión requerido'}, status=400)
        
    try:
        with transaction.atomic():
            admision = Admision.objects.select_for_update().get(id=admision_id)
            if not admision.recurso_asignado:
                raise ValidationError("La admisión no cuenta con un recurso asignado.")
                
            recurso = Recurso.objects.select_for_update().get(id=admision.recurso_asignado.id)
            recurso.estado = 'PRE_ALTA'
            recurso.save()

            # Registrar timestamp de pre-alta en la admisión
            admision.fecha_pre_alta = timezone.now()
            admision.save()
            
        return JsonResponse({
            'success': True,
            'message': f"Orden de pre-alta registrada. El recurso {recurso.codigo} se encuentra reservado en preparación de salida."
        })
    except Admision.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Admisión no encontrada'}, status=404)
    except ValidationError as e:
        return JsonResponse({'success': False, 'message': str(e.message if hasattr(e, 'message') else e)}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'message': f"Error transaccional: {str(e)}"}, status=500)


@require_POST
@retry_on_db_lock()
def confirmar_salida_api(request):
    """
    El personal de admisión o enfermería confirma que el paciente abandonó físicamente la cama.
    El paciente es dado de alta (estado ALTA) y la cama pasa a estado LIMPIEZA.
    """
    admision_id = request.POST.get('admision_id')
    if not admision_id:
        return JsonResponse({'success': False, 'message': 'ID de admisión requerido'}, status=400)
        
    try:
        with transaction.atomic():
            admision = Admision.objects.select_for_update().get(id=admision_id)
            recurso_asignado = admision.recurso_asignado
            
            if recurso_asignado:
                recurso = Recurso.objects.select_for_update().get(id=recurso_asignado.id)
                recurso.estado = 'LIMPIEZA'
                recurso.save()
                
                # Desasociar del recurso
                admision.recurso_asignado = None
            
            admision.estado = 'ALTA'
            admision.fecha_alta = timezone.now()
            admision.save()
            
        return JsonResponse({
            'success': True,
            'message': f"Salida física confirmada. Paciente dado de alta. Cama {recurso.codigo if recurso_asignado else ''} enviada a desinfección."
        })
    except Admision.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Admisión no encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': f"Error transaccional: {str(e)}"}, status=500)


@require_POST
@retry_on_db_lock()
def registrar_limpieza_api(request):
    """
    El personal de limpieza registra que se ha desinfectado la cama.
    La cama vuelve a estar DISPONIBLE en SQL.
    """
    recurso_id = request.POST.get('recurso_id')
    if not recurso_id:
        return JsonResponse({'success': False, 'message': 'ID de recurso requerido'}, status=400)
        
    try:
        with transaction.atomic():
            recurso = Recurso.objects.select_for_update().get(id=recurso_id)
            if recurso.estado != 'LIMPIEZA':
                raise ValidationError(f"El recurso {recurso.codigo} no se encuentra en estado de limpieza (Estado actual: {recurso.get_estado_display()}).")
                
            recurso.estado = 'DISPONIBLE'
            recurso.save()
            
        return JsonResponse({
            'success': True,
            'message': f"Limpieza y desinfección de {recurso.codigo} completada. El recurso está disponible nuevamente."
        })
    except Recurso.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Recurso no encontrado'}, status=404)
    except ValidationError as e:
        return JsonResponse({'success': False, 'message': str(e.message if hasattr(e, 'message') else e)}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'message': f"Error transaccional: {str(e)}"}, status=500)


@require_POST
@retry_on_db_lock()
def regularizar_paciente_nn_api(request):
    """
    Regularizar Paciente NN: Toma una admisión de paciente NN y actualiza
    los datos con su documento real (DNI), nombre, apellido y fecha de nacimiento.
    Si el DNI ya existe en la base de datos, asocia la admisión al paciente existente y
    borra el NN temporal de forma atómica para evitar duplicados.
    """
    admision_id = request.POST.get('admision_id')
    nuevo_dni = request.POST.get('documento_identidad', '').strip()
    nuevo_nombre = request.POST.get('nombre', '').strip()
    nuevo_apellido = request.POST.get('apellido', '').strip()
    nueva_fecha_nacimiento = request.POST.get('fecha_nacimiento', '')

    if not (admision_id and nuevo_dni and nuevo_nombre and nuevo_apellido and nueva_fecha_nacimiento):
        return JsonResponse({'success': False, 'message': 'Todos los campos son obligatorios'}, status=400)

    try:
        with transaction.atomic():
            # 1. Obtener y bloquear la admisión
            admision = Admision.objects.select_for_update().get(id=admision_id)
            paciente_nn = Paciente.objects.select_for_update().get(id=admision.paciente.id)

            # 2. Validar que realmente sea un paciente NN
            if not paciente_nn.documento_identidad.startswith("NN-"):
                raise ValidationError("Esta admisión ya está asociada a un paciente regularizado.")

            # 3. Comprobar si el DNI de destino ya existe
            try:
                # Caso B: El DNI ya está registrado en el sistema
                paciente_existente = Paciente.objects.select_for_update().get(documento_identidad=nuevo_dni)
                
                # Actualizar datos demográficos del paciente existente
                paciente_existente.nombre = nuevo_nombre
                paciente_existente.apellido = nuevo_apellido
                paciente_existente.fecha_nacimiento = nueva_fecha_nacimiento
                paciente_existente.save()

                # Verificar si el paciente existente ya tiene admisiones activas (para evitar colisión de admisión doble)
                admision_activa = Admision.objects.filter(paciente=paciente_existente).exclude(estado='ALTA').exclude(id=admision.id).first()
                if admision_activa:
                    raise ValidationError(f"El paciente {nuevo_dni} ya tiene una admisión activa (ID #{admision_activa.id})")

                # Asignar la admisión al paciente existente
                admision.paciente = paciente_existente
                admision.save()

                # Eliminar el paciente NN temporal sobrante
                paciente_nn.delete()
                
                message = f"Admisión regularizada. DNI {nuevo_dni} existente detectado; se asoció el historial y se eliminó el registro NN temporal."
            except Paciente.DoesNotExist:
                # Caso A: El DNI es nuevo
                # Modificar el registro NN directamente
                paciente_nn.documento_identidad = nuevo_dni
                paciente_nn.nombre = nuevo_nombre
                paciente_nn.apellido = nuevo_apellido
                paciente_nn.fecha_nacimiento = nueva_fecha_nacimiento
                paciente_nn.historia_clinica_num = f"HC-{nuevo_dni}"
                paciente_nn.save()
                
                message = f"Paciente NN regularizado exitosamente con DNI {nuevo_dni} y número de historia clínica generado."

        return JsonResponse({'success': True, 'message': message})
    except Admision.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Admisión no encontrada'}, status=404)
    except Paciente.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Paciente asociado no encontrado'}, status=404)
    except ValidationError as e:
        return JsonResponse({'success': False, 'message': str(e.message if hasattr(e, 'message') else e)}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'message': f"Error al regularizar: {str(e)}"}, status=500)

@require_POST
@retry_on_db_lock()
def generar_receta_api(request):
    """
    Genera una receta médica desde urgencias hacia farmacia.
    No verifica stock, simplemente emite la orden.
    """
    admision_id = request.POST.get('admision_id')
    medicamentos_json = request.POST.get('medicamentos') # ej: '[{"id": 1, "cantidad": 2}, ...]'
    prioridad = request.POST.get('prioridad', 'RUTINA')
    
    if not (admision_id and medicamentos_json):
        return JsonResponse({'success': False, 'message': 'Faltan parámetros indispensables'}, status=400)
        
    try:
        medicamentos_data = json.loads(medicamentos_json)
        if not medicamentos_data:
            raise ValidationError("La receta no puede estar vacía.")
            
        with transaction.atomic():
            admision = Admision.objects.select_for_update().get(id=admision_id)
            
            # Crear la receta
            receta = Receta.objects.create(
                admision=admision,
                medico=request.user.username if request.user.is_authenticated else 'Médico Urgencias',
                prioridad=prioridad,
                estado='PENDIENTE'
            )
            
            for item in medicamentos_data:
                med_id = item.get('id')
                cantidad = int(item.get('cantidad', 0))
                
                if cantidad <= 0:
                    raise ValidationError("La cantidad debe ser mayor a cero.")
                    
                # Pessimistic Lock on Inventory
                try:
                    inventario = InventarioFarmacia.objects.select_for_update().get(medicamento_id=med_id)
                except InventarioFarmacia.DoesNotExist:
                    raise ValidationError(f"No hay registro de inventario para el medicamento ID {med_id}.")
                
                if inventario.stock_disponible < cantidad:
                    raise ValidationError(f"Stock insuficiente para {inventario.medicamento.nombre}. Físico: {inventario.stock_fisico}, Comprometido: {inventario.stock_comprometido}.")
                
                # Commit the stock allocation (Flujo 1)
                inventario.stock_comprometido += cantidad
                inventario.save()
                    
                medicamento = inventario.medicamento
                DetalleReceta.objects.create(
                    receta=receta,
                    medicamento=medicamento,
                    cantidad=cantidad
                )
                
        return JsonResponse({
            'success': True,
            'message': f"Receta #{receta.id} generada y enviada a farmacia exitosamente."
        })
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Formato de medicamentos inválido'}, status=400)
    except Admision.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Admisión no encontrada'}, status=404)
    except Medicamento.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Uno o más medicamentos no existen'}, status=404)
    except ValidationError as e:
        return JsonResponse({'success': False, 'message': str(e.message if hasattr(e, 'message') else e)}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'message': f"Error al generar receta: {str(e)}"}, status=500)

@require_POST
@retry_on_db_lock()
def administrar_botiquin_api(request):
    """
    Flujo 2: El 'Carro de Paro' (Dispensación Retroactiva).
    Enfermería ya administró el medicamento. Esto regulariza el stock local y notifica a Farmacia.
    """
    admision_id = request.POST.get('admision_id')
    medicamento_id = request.POST.get('medicamento_id')
    cantidad = int(request.POST.get('cantidad', 1))
    ubicacion = request.POST.get('ubicacion', 'Carro de Paro Urgencias')

    if not (admision_id and medicamento_id):
        return JsonResponse({'success': False, 'message': 'Faltan parámetros indispensables'}, status=400)

    try:
        with transaction.atomic():
            admision = Admision.objects.select_for_update().get(id=admision_id)
            medicamento = Medicamento.objects.get(id=medicamento_id)

            # Restar del Botiquín Satélite (o crearlo en negativo si no hay registro para que Farmacia sepa cuánto reponer)
            botiquin, _ = BotiquinSatelite.objects.select_for_update().get_or_create(
                medicamento=medicamento,
                ubicacion=ubicacion,
                defaults={'cantidad_fisica': 0}
            )
            botiquin.cantidad_fisica -= cantidad
            botiquin.save()

            # Registrar la receta retroactiva
            receta = Receta.objects.create(
                admision=admision,
                medico=request.user.username if request.user.is_authenticated else 'Enfermería',
                prioridad='EMERGENCIA',
                estado='ADMINISTRADO_BOTIQUIN',
                fecha_despacho=timezone.now()
            )

            DetalleReceta.objects.create(
                receta=receta,
                medicamento=medicamento,
                cantidad=cantidad,
                indicaciones=f"Uso de emergencia desde {ubicacion}"
            )

            # Generar el cargo directo a facturación
            cuenta = admision.cuenta_facturacion
            CargoFacturacion.objects.create(
                cuenta=cuenta,
                medicamento=medicamento,
                cantidad=cantidad,
                precio_aplicado=medicamento.precio_unitario
            )
            cuenta.recalcular_total()

        return JsonResponse({
            'success': True,
            'message': f"Administración de {medicamento.nombre} desde {ubicacion} registrada exitosamente."
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': f"Error al registrar botiquín: {str(e)}"}, status=500)


@require_POST
def trasladar_paciente_api(request):
    """API para trasladar a un paciente a un nuevo recurso (cama/box)."""
    admision_id = request.POST.get('admision_id')
    nuevo_recurso_id = request.POST.get('recurso_id')
    
    if not admision_id or not nuevo_recurso_id:
        return JsonResponse({'success': False, 'message': 'Datos incompletos'})
        
    try:
        with transaction.atomic():
            adm = Admision.objects.select_for_update().get(id=admision_id)
            nuevo_recurso = Recurso.objects.select_for_update().get(id=nuevo_recurso_id)
            recurso_anterior = adm.recurso_asignado
            
            if nuevo_recurso.estado != 'DISPONIBLE':
                return JsonResponse({'success': False, 'message': 'El nuevo recurso no está disponible'})
                
            if recurso_anterior:
                recurso_anterior.estado = 'LIMPIEZA'
                recurso_anterior.save()
                
            nuevo_recurso.estado = 'OCUPADO'
            nuevo_recurso.save()
            
            adm.recurso_asignado = nuevo_recurso
            # Si estaba en espera o triage, actualizar a ADMITIDO
            if adm.estado in ['EN_ESPERA', 'EN_TRIAJE']:
                adm.estado = 'ADMITIDO'
                if not adm.fecha_admision_cama:
                    adm.fecha_admision_cama = timezone.now()
            adm.save()
            
        return JsonResponse({'success': True, 'message': f'Paciente trasladado a {nuevo_recurso.codigo}'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})
