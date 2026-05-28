from django.core.management.base import BaseCommand
from urgencias.models import Recurso, Insumo

class Command(BaseCommand):
    help = 'Seeds initial data for emergency resources (beds, boxes, ORs) and medical supplies (inventory).'

    def handle(self, *args, **options):
        self.stdout.write('Seeding initial emergency resources...')
        
        # 1. Seed Recursos
        recursos_data = [
            {'codigo': 'CAMA-101', 'tipo': 'CAMA', 'estado': 'DISPONIBLE', 'descripcion': 'Cama de Observación Adultos A'},
            {'codigo': 'CAMA-102', 'tipo': 'CAMA', 'estado': 'DISPONIBLE', 'descripcion': 'Cama de Observación Adultos B'},
            {'codigo': 'CAMA-103', 'tipo': 'CAMA', 'estado': 'DISPONIBLE', 'descripcion': 'Cama de Observación Adultos C'},
            {'codigo': 'CAMA-104', 'tipo': 'CAMA', 'estado': 'OCUPADO', 'descripcion': 'Cama Pediatría A'},
            {'codigo': 'CAMA-105', 'tipo': 'CAMA', 'estado': 'MANTENIMIENTO', 'descripcion': 'Cama de Reanimación (En mantenimiento técnico)'},
            {'codigo': 'BOX-01', 'tipo': 'BOX', 'estado': 'DISPONIBLE', 'descripcion': 'Box de Triage Principal'},
            {'codigo': 'BOX-02', 'tipo': 'BOX', 'estado': 'DISPONIBLE', 'descripcion': 'Box de Procedimientos Menores'},
            {'codigo': 'BOX-03', 'tipo': 'BOX', 'estado': 'OCUPADO', 'descripcion': 'Box de Especialidades Ginecología'},
            {'codigo': 'QUIROFANO-01', 'tipo': 'QUIROFANO', 'estado': 'DISPONIBLE', 'descripcion': 'Quirófano de Emergencias Generales'},
            {'codigo': 'QUIROFANO-02', 'tipo': 'QUIROFANO', 'estado': 'DISPONIBLE', 'descripcion': 'Quirófano de Emergencia Trauma'},
        ]

        created_recursos = 0
        for data in recursos_data:
            recurso, created = Recurso.objects.get_or_create(
                codigo=data['codigo'],
                defaults={
                    'tipo': data['tipo'],
                    'estado': data['estado'],
                    'descripcion': data['descripcion']
                }
            )
            if created:
                created_recursos += 1
            else:
                # Actualizar estado si ya existía para resetear a un estado conocido
                recurso.estado = data['estado']
                recurso.tipo = data['tipo']
                recurso.descripcion = data['descripcion']
                recurso.save()

        self.stdout.write(self.style.SUCCESS(f'Successfully seeded/reset {len(recursos_data)} resources (Beds/Boxes/ORs).'))

        # 2. Seed Insumos (Inventory)
        insumos_data = [
            {'codigo': 'INS-001', 'nombre': 'Jeringa Descartable 5ml', 'stock': 150, 'precio_unitario': 1.50},
            {'codigo': 'INS-002', 'nombre': 'Suero Fisiológico 500ml', 'stock': 80, 'precio_unitario': 8.90},
            {'codigo': 'INS-003', 'nombre': 'Paracetamol Endovenoso 1g', 'stock': 45, 'precio_unitario': 5.00},
            {'codigo': 'INS-004', 'nombre': 'Catéter Intravenoso 18G', 'stock': 120, 'precio_unitario': 3.25},
            {'codigo': 'INS-005', 'nombre': 'Ampolla de Adrenalina 1mg', 'stock': 12, 'precio_unitario': 15.00}, # Stock crítico
        ]

        created_insumos = 0
        for data in insumos_data:
            insumo, created = Insumo.objects.get_or_create(
                codigo=data['codigo'],
                defaults={
                    'nombre': data['nombre'],
                    'stock': data['stock'],
                    'precio_unitario': data['precio_unitario']
                }
            )
            if created:
                created_insumos += 1
            else:
                # Resetear stock y precios para pruebas repetibles
                insumo.stock = data['stock']
                insumo.precio_unitario = data['precio_unitario']
                insumo.nombre = data['nombre']
                insumo.save()

        self.stdout.write(self.style.SUCCESS(f'Successfully seeded/reset {len(insumos_data)} medical supply items.'))
        self.stdout.write(self.style.SUCCESS('Database seeding completed successfully!'))
