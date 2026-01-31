"""
Routes de Reportes - VERSIÓN FINAL
Manejo completo de CRUD con dependencias preliminares simplificadas
SOLO relación DEPENDE_DE (el reporte nuevo siempre es el HIJO)
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
import json, os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import get_connection
from services.reporte_service import ReporteService

reportes_bp = Blueprint('reportes', __name__)

UPLOAD_FOLDER = "uploads/reportes"

@reportes_bp.route('/crear_reporte', methods=['GET', 'POST'])
def crear_reporte():
    """Crear un nuevo reporte con código auto-generado"""
    
    if request.method == 'POST':
        print("="*50)
        print("📝 CREANDO NUEVO REPORTE CON DEPENDENCIAS")
        print("="*50)
        
        conn = None
        codigo_generado = None
        
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)

            # ============================================
            # 1. OBTENER Y VALIDAR DATOS DEL FORMULARIO
            # ============================================
            nombre = request.form.get("nombre")
            descripcion = request.form.get("descripcion")
            consideraciones = request.form.get("consideraciones")  # ← NUEVO
            proposito = request.form.get("proposito")
            tipo_id = request.form.get("tipo_id")
            
            if not nombre or not tipo_id:
                raise ValueError("El nombre y tipo de reporte son obligatorios")

            # ============================================
            # 2. GENERAR CÓDIGO INTERNO AUTOMÁTICO
            # ============================================
            try:
                codigo_generado = ReporteService.generar_codigo_interno(int(tipo_id))
                print(f"✓ Código generado: {codigo_generado}")
            except Exception as e:
                raise ValueError(f"Error al generar código: {str(e)}")

            # ============================================
            # 3. RECOPILAR RESTO DE DATOS
            # ============================================
            categoria_id = request.form.get("categoria_id") or None
            area_reportante = request.form.get("area_reportante_id")
            area_ejecutora = request.form.get("area_ejecutora_id")
            area_receptora = request.form.get("area_receptora_id") or None

            if not area_reportante or not area_ejecutora:
                raise ValueError("Las áreas reportante y ejecutora son obligatorias")

            audiencia = request.form.get("audiencia", "interna").upper()
            receptor_externo = request.form.get("receptor_externo") or None
            criticidad = request.form.get("criticidad") or "MEDIA"
            formato_entrega = request.form.get("formato_entrega") or "CORREO"
            formato_reporte = request.form.get("formato_reporte") or "PDF"
            ruta_entrega = request.form.get("ruta_entrega")
            creado_por = session.get("user_id", 1)

            print(f"📋 Datos del reporte:")
            print(f"   Código: {codigo_generado}")
            print(f"   Nombre: {nombre}")
            print(f"   Consideraciones: {'Sí' if consideraciones else 'No'}")

            # ============================================
            # 4. INSERTAR REPORTE EN BASE DE DATOS
            # ============================================
            cursor.execute("""
                INSERT INTO reporte (
                    codigo_interno, nombre, proposito, descripcion, consideraciones,
                    tipo_id, categoria_id,
                    area_reportante_id, area_ejecutora_id, area_receptora_id,
                    audiencia, receptor_externo,
                    criticidad, formato_entrega, formato_reporte,
                    ruta_entrega, creado_por, estado
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                codigo_generado, nombre, proposito, descripcion, consideraciones,
                tipo_id, categoria_id,
                area_reportante, area_ejecutora, area_receptora,
                audiencia, receptor_externo,
                criticidad, formato_entrega, formato_reporte,
                ruta_entrega, creado_por, 'Por Validar'
            ))

            reporte_id = cursor.lastrowid
            print(f"✓ Reporte insertado con ID: {reporte_id}")

            # ============================================
            # 4.5 CREAR DEPENDENCIAS PRELIMINARES (NO VALIDADAS)
            # SIMPLIFICADO: Solo DEPENDE_DE (el nuevo siempre es HIJO)
            # ============================================
            dependencias_creadas = 0
            
            # Obtener dependencias del formulario (JSON)
            dependencias_json = request.form.get("dependencias", "[]")
            
            try:
                dependencias = json.loads(dependencias_json)
            except:
                dependencias = []
            
            print(f"📊 Dependencias a crear: {len(dependencias)}")
            
            # Crear dependencias donde el nuevo reporte es DEPENDIENTE
            for dep in dependencias:
                try:
                    cursor.execute("""
                        INSERT INTO reporte_dependencia (
                            reporte_origen_id,
                            reporte_dependiente_id,
                            tipo_dependencia,
                            criticidad,
                            observaciones,
                            validada,
                            creado_por
                        ) VALUES (%s, %s, %s, %s, %s, FALSE, %s)
                    """, (
                        dep.get('id_reporte'),           # El seleccionado es ORIGEN
                        reporte_id,                       # El nuevo es DEPENDIENTE (hijo)
                        dep.get('tipo_dependencia', 'DATOS'),
                        dep.get('criticidad', 'MEDIA'),
                        dep.get('observaciones'),
                        creado_por
                    ))
                    dependencias_creadas += 1
                    print(f"   ✓ Dependencia creada: {dep.get('codigo')} → {codigo_generado}")
                except Exception as e:
                    print(f"   ⚠️  Error al crear dependencia: {e}")
            
            print(f"✓ Total dependencias preliminares creadas: {dependencias_creadas}")

            # ============================================
            # 5. CONFIGURAR SCHEDULE Y CALCULAR PRÓXIMA EJECUCIÓN
            # ============================================
            frecuencia_form = request.form.get("frecuencia")
            reglas_json = request.form.get("reglas_json")

            map_frecuencia = {
                "diaria": "DIARIA",
                "semanal": "SEMANAL",
                "mensual": "MENSUAL",
                "anual": "ANUAL",
                "semestral": "SEMESTRAL",
                "cuatrimestral": "TRIMESTRAL",
                "trimestral": "TRIMESTRAL"
            }

            frecuencia = map_frecuencia.get(frecuencia_form, "ADHOC")
            
            cursor.execute("""
                INSERT INTO reporte_schedule (
                    reporte_id, frecuencia, reglas_json
                ) VALUES ( %s, %s, %s)
            """, (reporte_id, frecuencia, reglas_json))
            
            print(f"✓ Schedule configurado: {frecuencia}")

            # Calcular próxima ejecución
            try:
                proxima_ejecucion = ReporteService.calcular_proxima_ejecucion(
                    frecuencia, reglas_json
                )
                
                if proxima_ejecucion:
                    estado_entrega = ReporteService.calcular_estado_entrega(
                        proxima_ejecucion, frecuencia
                    )
                    
                    cursor.execute("""
                        UPDATE reporte 
                        SET proxima_ejecucion = %s,
                            estado_entrega = %s
                        WHERE id_reporte = %s
                    """, (proxima_ejecucion, estado_entrega, reporte_id))
                    
                    print(f"✓ Próxima ejecución: {proxima_ejecucion}")
            except Exception as e:
                print(f"⚠️  Advertencia al calcular ejecución: {e}")

            # ============================================
            # 6. PROCESAR RECURSOS (GITLAB Y PDF)
            # ============================================
            gitlab_url = request.form.get("gitlab_url")
            if gitlab_url:
                cursor.execute("""
                    INSERT INTO recurso (tipo, nombre, url, creado_por)
                    VALUES ('GITLAB', %s, %s, %s)
                """, ("Repositorio GitLab", gitlab_url, creado_por))
                recurso_id = cursor.lastrowid
                
                cursor.execute("""
                    INSERT INTO reporte_recurso (reporte_id, recurso_id)
                    VALUES (%s, %s)
                """, (reporte_id, recurso_id))
                print(f"✓ GitLab vinculado")

            # Subir PDF
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            archivo_pdf = request.files.get("pdf_formato")
            
            if archivo_pdf and archivo_pdf.filename:
                filename = archivo_pdf.filename
                ruta_archivo = os.path.join(UPLOAD_FOLDER, filename)
                archivo_pdf.save(ruta_archivo)
                size_bytes = os.path.getsize(ruta_archivo)
                
                cursor.execute("""
                    INSERT INTO recurso (tipo, nombre, ruta_servidor, size_bytes, creado_por)
                    VALUES ('PDF', %s, %s, %s, %s)
                """, (filename, ruta_archivo, size_bytes, creado_por))
                recurso_id = cursor.lastrowid
                
                cursor.execute("""
                    INSERT INTO reporte_recurso (reporte_id, recurso_id)
                    VALUES (%s, %s)
                """, (reporte_id, recurso_id))
                print(f"✓ PDF guardado")

            # ============================================
            # 7. REGISTRAR EN BITÁCORA
            # ============================================
            ReporteService.registrar_log(
                'REPORTE', reporte_id, 'CREAR',
                f"Reporte {codigo_generado} creado: {nombre} (con {dependencias_creadas} dependencias preliminares)",
                creado_por,
                {
                    'codigo': codigo_generado,
                    'tipo_id': tipo_id,
                    'frecuencia': frecuencia,
                    'dependencias_preliminares': dependencias_creadas
                }
            )

            # ============================================
            # 8. COMMIT Y MENSAJE DE ÉXITO
            # ============================================
            conn.commit()
            print("="*50)
            print(f"✅ REPORTE {codigo_generado} CREADO EXITOSAMENTE")
            print(f"✅ Dependencias preliminares: {dependencias_creadas}")
            print("="*50)
            
            cursor.close()
            conn.close()

            mensaje_exito = f"✅ Tu reporte {codigo_generado} se ha creado exitosamente"
            if dependencias_creadas > 0:
                mensaje_exito += f" con {dependencias_creadas} dependencia(s). Se validarán al aprobar el reporte."
            
            flash(mensaje_exito, "success")
            return redirect('/catalogos')
            
        except ValueError as ve:
            print(f"❌ Error de validación: {str(ve)}")
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            flash(f"❌ Error: {str(ve)}", "error")
            return redirect('/crear_reporte')
            
        except Exception as e:
            print(f"❌ ERROR CRÍTICO: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            
            flash(f"❌ No se pudo crear el reporte: {str(e)}", "error")
            return redirect('/crear_reporte')
    
    # ============================================
    # GET - CARGAR FORMULARIO CON CATÁLOGOS
    # ============================================
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT id_tipo, nombre FROM tipo_reporte ORDER BY nombre")
    tipos = cursor.fetchall()

    cursor.execute("SELECT id_categoria, nombre FROM categoria_reporte ORDER BY nombre")
    categorias = cursor.fetchall()

    cursor.execute("SELECT id_area, nombre FROM area ORDER BY nombre")
    areas = cursor.fetchall()

    # Obtener reportes APROBADOS para dependencias
    cursor.execute("""
        SELECT id_reporte, codigo_interno, nombre 
        FROM reporte 
        WHERE estado = 'Aprobado'
        ORDER BY codigo_interno
    """)
    reportes_activos = cursor.fetchall()

    # Obtener ENUMs
    cursor.execute("SHOW COLUMNS FROM reporte LIKE 'criticidad'")
    criticidad_raw = cursor.fetchone()
    criticidad_e = []
    if criticidad_raw:
        enum_str = criticidad_raw["Type"]
        criticidad_e = enum_str.replace("enum(", "").replace(")", "").replace("'", "").split(",")

    cursor.execute("SHOW COLUMNS FROM reporte LIKE 'formato_entrega'")
    formato_raw = cursor.fetchone()
    formato_e = []
    if formato_raw:
        enum_str = formato_raw["Type"]
        formato_e = enum_str.replace("enum(", "").replace(")", "").replace("'", "").split(",")

    cursor.execute("SHOW COLUMNS FROM reporte LIKE 'formato_reporte'")
    formato_raw = cursor.fetchone()
    formato_er = []
    if formato_raw:
        enum_str = formato_raw["Type"]
        formato_er = enum_str.replace("enum(", "").replace(")", "").replace("'", "").split(",")

    cursor.close()
    conn.close()

    return render_template(
        'crear_reporte.html',
        tipos=tipos,
        categorias=categorias,
        areas=areas,
        reportes_activos=reportes_activos,
        criticidad_e=criticidad_e,
        formato_e=formato_e,
        formato_er=formato_er
    )


@reportes_bp.route('/reporte/<int:reporte_id>/marcar_entregado', methods=['POST'])
def marcar_entregado(reporte_id):
    """Marca un reporte como entregado y recalcula próxima ejecución"""
    try:
        usuario_id = session.get("user_id", 1)
        
        if ReporteService.marcar_entregado(reporte_id, usuario_id):
            return jsonify({
                'success': True,
                'message': 'Reporte marcado como entregado correctamente'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Error al marcar reporte como entregado'
            }), 500
            
    except Exception as e:
        print(f"❌ ERROR al marcar entregado: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@reportes_bp.route('/api/reportes/<int:id_reporte>/aprobar', methods=['POST'])
def aprobar_reporte(id_reporte):
    """Aprueba un reporte y valida sus dependencias automáticamente vía trigger"""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT codigo_interno, estado 
            FROM reporte 
            WHERE id_reporte = %s
        """, (id_reporte,))
        
        result = cursor.fetchone()
        if not result:
            cursor.close()
            conn.close()
            return jsonify({"error": "Reporte no encontrado"}), 404
        
        codigo = result['codigo_interno']
        estado_actual = result['estado']
        
        if estado_actual == 'Aprobado':
            cursor.close()
            conn.close()
            return jsonify({"error": "El reporte ya está aprobado"}), 400
        
        # Contar dependencias no validadas
        cursor.execute("""
            SELECT COUNT(*) as total
            FROM reporte_dependencia 
            WHERE (reporte_origen_id = %s OR reporte_dependiente_id = %s)
            AND validada = FALSE
        """, (id_reporte, id_reporte))
        
        dependencias_pendientes = cursor.fetchone()['total']
        
        # Aprobar reporte (el trigger validará las dependencias)
        usuario = session.get("user_id", 1)
        cursor.execute("""
            UPDATE reporte 
            SET estado = 'Aprobado',
                modificado_por = %s
            WHERE id_reporte = %s
        """, (usuario, id_reporte))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"✓ Reporte {codigo} aprobado. {dependencias_pendientes} dependencias validadas")
        
        return jsonify({
            "success": True,
            "mensaje": f"Reporte aprobado exitosamente",
            "dependencias_validadas": dependencias_pendientes
        }), 200
        
    except Exception as e:
        print(f"❌ Error al aprobar reporte: {str(e)}")
        
        if conn:
            conn.rollback()
            cursor.close()
            conn.close()
        
        return jsonify({"error": f"Error interno: {str(e)}"}), 500
