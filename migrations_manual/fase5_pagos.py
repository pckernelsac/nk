"""
Migracion Fase 5: Sistema de Pagos Ampliado
Crea tablas para tipos de pago, conceptos, obligaciones y pagos generales
Actualiza ConfiguracionPension para manejar series separadas

Ejecutar: python migrations_manual/fase5_pagos.py
"""

import sys
import os

# Agregar el directorio raiz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import db, TipoPago, ConceptoPagoCiclo, ConfiguracionPension

def ejecutar_migracion():
    """Ejecuta la migracion para crear tablas de pagos"""

    print("=" * 60)
    print("MIGRACION FASE 5: Sistema de Pagos Ampliado")
    print("=" * 60)
    print()

    with app.app_context():
        try:
            # Primero actualizar ConfiguracionPension
            print("Actualizando tabla configuracion_pension...")

            # Agregar columnas para pagos generales
            try:
                db.session.execute(db.text(
                    "ALTER TABLE configuracion_pension ADD COLUMN serie_recibo_general VARCHAR(10) DEFAULT '002'"
                ))
                print("[OK] Columna serie_recibo_general agregada")
            except Exception as e:
                if 'duplicate column' in str(e).lower() or 'already exists' in str(e).lower():
                    print("[INFO] Columna serie_recibo_general ya existe")
                else:
                    raise

            try:
                db.session.execute(db.text(
                    "ALTER TABLE configuracion_pension ADD COLUMN numero_correlativo_general INTEGER DEFAULT 1"
                ))
                print("[OK] Columna numero_correlativo_general agregada")
            except Exception as e:
                if 'duplicate column' in str(e).lower() or 'already exists' in str(e).lower():
                    print("[INFO] Columna numero_correlativo_general ya existe")
                else:
                    raise

            db.session.commit()
            print()

            # Crear nuevas tablas
            print("Creando tablas de pagos...")

            db.create_all()

            print("[OK] Tabla tipos_pago creada")
            print("[OK] Tabla conceptos_pago_ciclo creada")
            print("[OK] Tabla obligaciones_pago_estudiante creada")
            print("[OK] Tabla pagos_generales creada")
            print()

            # Crear tipos de pago de ejemplo
            print("Creando tipos de pago de ejemplo...")

            tipos_ejemplo = [
                {'nombre': 'Carnet Estudiantil', 'codigo': 'CARNET', 'categoria': 'Escolar'},
                {'nombre': 'Compendio', 'codigo': 'COMPENDIO', 'categoria': 'Escolar'},
                {'nombre': 'Uniforme', 'codigo': 'UNIFORME', 'categoria': 'Escolar'},
                {'nombre': 'Seguro Escolar', 'codigo': 'SEGURO', 'categoria': 'Administrativo'},
                {'nombre': 'Matricula', 'codigo': 'MATRICULA', 'categoria': 'Administrativo'},
            ]

            for tipo_data in tipos_ejemplo:
                # Verificar si ya existe
                existe = TipoPago.query.filter_by(codigo=tipo_data['codigo']).first()

                if not existe:
                    tipo = TipoPago(
                        nombre=tipo_data['nombre'],
                        codigo=tipo_data['codigo'],
                        categoria=tipo_data.get('categoria'),
                        activo=True,
                        usuario_registro='admin'
                    )
                    db.session.add(tipo)
                    print(f"  [OK] Creado: {tipo.nombre}")

            # Crear conceptos de ejemplo para 2025
            print()
            print("Creando conceptos de ejemplo para 2025...")

            # Obtener los tipos creados
            carnet = TipoPago.query.filter_by(codigo='CARNET').first()
            compendio = TipoPago.query.filter_by(codigo='COMPENDIO').first()

            conceptos_ejemplo = []

            if carnet:
                conceptos_ejemplo.append({
                    'tipo_pago_id': carnet.id,
                    'tipo_pago_nombre': carnet.nombre,
                    'anio_escolar': '2025',
                    'monto': 30.00,
                    'permite_cuotas': False,
                    'numero_cuotas_max': 1
                })

            if compendio:
                conceptos_ejemplo.append({
                    'tipo_pago_id': compendio.id,
                    'tipo_pago_nombre': compendio.nombre,
                    'anio_escolar': '2025',
                    'monto': 100.00,
                    'permite_cuotas': True,
                    'numero_cuotas_max': 2
                })

            for concepto_data in conceptos_ejemplo:
                # Verificar si ya existe
                existe = ConceptoPagoCiclo.query.filter_by(
                    tipo_pago_id=concepto_data['tipo_pago_id'],
                    anio_escolar=concepto_data['anio_escolar']
                ).first()

                if not existe:
                    concepto = ConceptoPagoCiclo(
                        tipo_pago_id=concepto_data['tipo_pago_id'],
                        tipo_pago_nombre=concepto_data['tipo_pago_nombre'],
                        anio_escolar=concepto_data['anio_escolar'],
                        monto=concepto_data['monto'],
                        permite_cuotas=concepto_data['permite_cuotas'],
                        numero_cuotas_max=concepto_data['numero_cuotas_max'],
                        activo=True,
                        usuario_registro='admin'
                    )
                    db.session.add(concepto)
                    print(f"  [OK] Creado: {concepto.tipo_pago_nombre} - S/{concepto.monto}")

            db.session.commit()

            print()
            print("=" * 60)
            print("MIGRACION COMPLETADA")
            print("=" * 60)
            print()
            print("Tablas creadas:")
            print("  - tipos_pago (con 5 tipos de ejemplo)")
            print("  - conceptos_pago_ciclo (con 2 conceptos para 2025)")
            print("  - obligaciones_pago_estudiante")
            print("  - pagos_generales")
            print()
            print("Configuracion actualizada:")
            print("  - Serie para pagos generales: 002")
            print("  - Numero correlativo inicial: 1")
            print()
            print("Proximos pasos:")
            print("1. Acceder a /pagos/tipos para ver tipos de pago")
            print("2. Acceder a /pagos/conceptos para ver conceptos")
            print("3. Asignar obligaciones en /pagos/obligaciones/asignar")
            print("4. Registrar pagos en /pagos/registrar")
            print("5. Ver estado de cuenta en /pagos/estado_cuenta/<estudiante_id>")
            print()

        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()

if __name__ == '__main__':
    ejecutar_migracion()
