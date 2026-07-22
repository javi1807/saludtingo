from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.db.models import Case, When, Value, IntegerField, Count, Q
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import Receta, InventarioFarmacia, BotiquinSatelite
from urgencias.models import CargoFacturacion


def dashboard_farmacia(request):
    """Dashboard principal para despacho de recetas pendientes con KPIs."""
    # Ordenar por prioridad: EMERGENCIA primero, luego URGENTE, luego RUTINA
    recetas_pendientes = Receta.objects.filter(
        estado='PENDIENTE'
    ).annotate(
        prioridad_order=Case(
            When(prioridad='EMERGENCIA', then=Value(1)),
            When(prioridad='URGENTE', then=Value(2)),
            When(prioridad='RUTINA', then=Value(3)),
            default=Value(4),
            output_field=IntegerField(),
        )
    ).order_by('prioridad_order', '-fecha_emision').prefetch_related(
        'detalles__medicamento__inventario',
        'admision__paciente'
    )

    # KPIs
    hoy = timezone.now().date()
    despachos_hoy = Receta.objects.filter(
        estado='DESPACHADA',
        fecha_despacho__date=hoy
    ).count()
    
    stock_critico_count = InventarioFarmacia.objects.filter(
        stock_fisico__lt=20
    ).count()
    
    alertas_botiquin = BotiquinSatelite.objects.filter(
        cantidad_fisica__lt=0
    ).count()

    context = {
        'recetas': recetas_pendientes,
        'active_page': 'despacho',
        'kpis': {
            'pendientes': recetas_pendientes.count(),
            'despachos_hoy': despachos_hoy,
            'stock_critico': stock_critico_count,
            'alertas_botiquin': alertas_botiquin,
        }
    }
    return render(request, 'farmacia/dashboard.html', context)


def despachar_receta(request, receta_id):
    receta = get_object_or_404(Receta, id=receta_id)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                if receta.estado != 'PENDIENTE':
                    raise ValueError("Esta receta ya no está pendiente.")
                
                for detalle in receta.detalles.all():
                    medicamento = detalle.medicamento
                    inventario = InventarioFarmacia.objects.select_for_update().get(
                        medicamento=medicamento
                    )
                    if inventario.stock_fisico < detalle.cantidad:
                        return JsonResponse({
                            'success': False,
                            'message': f'Stock físico insuficiente de {medicamento.nombre}'
                        }, status=400)
                    
                    inventario.stock_fisico -= detalle.cantidad
                    inventario.stock_comprometido -= detalle.cantidad
                    if inventario.stock_comprometido < 0:
                        inventario.stock_comprometido = 0
                    inventario.save()
                    
                    # Generar CargoFacturacion
                    if hasattr(receta, 'admision'):
                        cuenta = receta.admision.cuenta_facturacion
                        CargoFacturacion.objects.create(
                            cuenta=cuenta,
                            medicamento=medicamento,
                            cantidad=detalle.cantidad,
                            precio_aplicado=medicamento.precio_unitario
                        )
                        cuenta.recalcular_total()
                
                receta.estado = 'DESPACHADA'
                receta.fecha_despacho = timezone.now()
                receta.farmaceutico_despacho = request.user.username if request.user.is_authenticated else 'Farmacéutico'
                receta.save()
                
                messages.success(request, f"Receta #{receta.id} despachada con éxito.")
                
        except ValueError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, "Ocurrió un error al despachar la receta.")
            
        return redirect('farmacia:dashboard')


@require_POST
def cancelar_receta_api(request, receta_id):
    """
    Cancela una receta PENDIENTE y devuelve el stock comprometido al inventario.
    Debilidad 7: Sin esto, el stock comprometido nunca se liberaría.
    """
    receta = get_object_or_404(Receta, id=receta_id)
    
    try:
        with transaction.atomic():
            if receta.estado != 'PENDIENTE':
                return JsonResponse({
                    'success': False,
                    'message': f'Solo se pueden cancelar recetas pendientes. Estado actual: {receta.get_estado_display()}'
                }, status=400)
            
            # Devolver stock comprometido
            for detalle in receta.detalles.all():
                inventario = InventarioFarmacia.objects.select_for_update().get(
                    medicamento=detalle.medicamento
                )
                inventario.stock_comprometido -= detalle.cantidad
                if inventario.stock_comprometido < 0:
                    inventario.stock_comprometido = 0
                inventario.save()
            
            receta.estado = 'CANCELADA'
            receta.farmaceutico_despacho = request.user.username if request.user.is_authenticated else 'Sistema'
            receta.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Receta #{receta.id} cancelada. Stock comprometido devuelto al inventario.'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error al cancelar: {str(e)}'
        }, status=500)


def inventario_farmacia(request):
    """Vista del Control de Inventario para Farmacia."""
    inventario_qs = InventarioFarmacia.objects.select_related('medicamento').all().order_by('medicamento__nombre')
    
    # Top 8 lowest available stock for chart
    top_criticos = sorted(list(inventario_qs), key=lambda x: x.stock_disponible)[:8]
    chart_data = []
    for inv in top_criticos:
        chart_data.append({
            'nombre': inv.medicamento.nombre[:15] + ('...' if len(inv.medicamento.nombre) > 15 else ''),
            'stock': inv.stock_disponible,
            'critical': inv.stock_disponible <= 20
        })
    
    # Botiquines satélites con stock negativo (alertas de reposición)
    botiquines_alerta = BotiquinSatelite.objects.filter(
        cantidad_fisica__lt=0
    ).select_related('medicamento').order_by('cantidad_fisica')
    
    # Datos históricos (últimos 6 meses)
    from datetime import date
    import calendar
    
    historical_chart_data = []
    today = date.today()
    for i in range(5, -1, -1):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        mes_str = f"{calendar.month_abbr[m]} {y}"
        count = Receta.objects.filter(
            estado__in=['DESPACHADA', 'ADMINISTRADO_BOTIQUIN'],
            fecha_emision__year=y,
            fecha_emision__month=m
        ).count()
        historical_chart_data.append({
            'mes': mes_str,
            'count': count
        })
    
    context = {
        'inventario': inventario_qs,
        'chart_data': chart_data,
        'historical_chart_data': historical_chart_data,
        'botiquines_alerta': botiquines_alerta,
        'active_page': 'inventario'
    }
    return render(request, 'farmacia/inventario.html', context)


from django.core.paginator import Paginator

def historial_recetas(request):
    """Vista de Auditoría de recetas despachadas y canceladas."""
    recetas_list = Receta.objects.filter(
        estado__in=['DESPACHADA', 'CANCELADA', 'ADMINISTRADO_BOTIQUIN']
    ).order_by('-fecha_emision').prefetch_related('detalles__medicamento', 'admision__paciente')
    
    paginator = Paginator(recetas_list, 50) # 50 recetas por página
    page_number = request.GET.get('page')
    recetas = paginator.get_page(page_number)
    
    context = {
        'recetas': recetas,
        'active_page': 'historial'
    }
    return render(request, 'farmacia/historial.html', context)


@require_POST
def reponer_stock_api(request):
    """API para reponer stock de un medicamento."""
    medicamento_id = request.POST.get('medicamento_id')
    cantidad_str = request.POST.get('cantidad')
    
    if not medicamento_id or not cantidad_str:
        return JsonResponse({'success': False, 'message': 'Datos incompletos.'})
        
    try:
        cantidad = int(cantidad_str)
        if cantidad <= 0:
            return JsonResponse({'success': False, 'message': 'La cantidad debe ser mayor a 0.'})
            
        with transaction.atomic():
            inventario = InventarioFarmacia.objects.select_for_update().get(medicamento_id=medicamento_id)
            inventario.stock_fisico += cantidad
            inventario.save()
            
        return JsonResponse({'success': True, 'message': f'Se agregaron {cantidad} unidades correctamente.'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

@require_POST
def reponer_botiquin_api(request):
    """API para reponer stock de un botiquín desde el inventario principal."""
    botiquin_id = request.POST.get('botiquin_id')
    cantidad = int(request.POST.get('cantidad', 0))
    
    if not botiquin_id or cantidad <= 0:
        return JsonResponse({'success': False, 'message': 'Datos inválidos.'})
        
    try:
        with transaction.atomic():
            botiquin = BotiquinSatelite.objects.select_for_update().get(id=botiquin_id)
            inventario = InventarioFarmacia.objects.select_for_update().get(medicamento=botiquin.medicamento)
            
            if inventario.stock_disponible < cantidad:
                return JsonResponse({'success': False, 'message': 'Stock insuficiente en la farmacia principal.'})
                
            inventario.stock_fisico -= cantidad
            inventario.save()
            
            botiquin.cantidad_fisica += cantidad
            botiquin.save()
            
        return JsonResponse({'success': True, 'message': f'Botiquín reabastecido (+{cantidad} uds).'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})
