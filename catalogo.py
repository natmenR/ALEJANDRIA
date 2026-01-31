"""
Routes de Catálogo de Reportes
Muestra todos los reportes con próxima ejecución calculada
"""

from flask import Blueprint, render_template, request, flash, redirect
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import get_connection
from datetime import datetime

catalogos_bp = Blueprint('catalogos', __name__)

@catalogos_bp.route('/catalogos')
def index():
    """
    Catálogo de reportes con próxima ejecución y estado calculados
    """
    
    try:
        # Parámetros de búsqueda/filtro
        filtro_busqueda = request.args.get('q', '').strip()
        filtro_estado = request.args.get('estado', '')
        filtro_criticidad = request.args.get('criticidad', '')
        
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Query principal usando la vista optimizada
        query = """
            SELECT 
                r.id_reporte,
                r.codigo_interno,
                r.nombre,
                r.proposito,
                r.descripcion,
                r.criticidad,
                r.audiencia,
                r.formato_entrega,
                r.formato_reporte,
                r.ruta_entrega,
                r.estado,
                r.estado_entrega,
                r.proxima_ejecucion,
                r.ultima_entrega,
                r.created_at,
                
                t.nombre as tipo_nombre,
                t.prefijo_codigo,
                c.nombre as categoria_nombre,
                a1.nombre as area_reportante_nombre,
                a2.nombre as area_ejecutora_nombre,
                a3.nombre as area_receptora_nombre,
                
                s.frecuencia,
                s.reglas_json,
                
                ca.horas_antes_alerta,
                
                -- Cálculo de horas hasta vencimiento
                TIMESTAMPDIFF(HOUR, NOW(), r.proxima_ejecucion) as horas_hasta_vencimiento,
                
                -- Estado calculado
                CASE 
                    WHEN r.proxima_ejecucion IS NULL THEN 'SIN_PROGRAMAR'
                    WHEN NOW() > r.proxima_ejecucion THEN 'RETRASADO'
                    WHEN TIMESTAMPDIFF(HOUR, NOW(), r.proxima_ejecucion) <= COALESCE(ca.horas_antes_alerta, 24) THEN 'PROXIMO_VENCER'
                    ELSE 'EN_TIEMPO'
                END as estado_calculado
                
            FROM reporte r
            LEFT JOIN tipo_reporte t ON r.tipo_id = t.id_tipo
            LEFT JOIN categoria_reporte c ON r.categoria_id = c.id_categoria
            LEFT JOIN area a1 ON r.area_reportante_id = a1.id_area
            LEFT JOIN area a2 ON r.area_ejecutora_id = a2.id_area
            LEFT JOIN area a3 ON r.area_receptora_id = a3.id_area
            LEFT JOIN reporte_schedule s ON r.id_reporte = s.reporte_id
            LEFT JOIN config_alertas ca ON s.frecuencia = ca.frecuencia
            WHERE 1=1
        """
        
        params = []
        
        # Filtro de búsqueda
        if filtro_busqueda:
            query += " AND (r.nombre LIKE %s OR r.codigo_interno LIKE %s OR t.nombre LIKE %s)"
            busqueda_param = f"%{filtro_busqueda}%"
            params.extend([busqueda_param, busqueda_param, busqueda_param])
        
        # Filtro de estado
        if filtro_estado:
            query += " AND r.estado = %s"
            params.append(filtro_estado)
        
        # Filtro de criticidad
        if filtro_criticidad:
            query += " AND r.criticidad = %s"
            params.append(filtro_criticidad)
        
        # Ordenar por estado y próxima ejecución
        query += """ 
            ORDER BY 
                CASE r.estado_entrega
                    WHEN 'RETRASADO' THEN 1
                    WHEN 'PROXIMO_VENCER' THEN 2
                    WHEN 'EN_TIEMPO' THEN 3
                    WHEN 'ENTREGADO' THEN 4
                    ELSE 5
                END,
                r.proxima_ejecucion ASC,
                r.created_at DESC
        """
        
        print(f"📋 Ejecutando query de catálogo...")
        print(f"   Búsqueda: {filtro_busqueda or 'ninguna'}")
        print(f"   Estado: {filtro_estado or 'todos'}")
        print(f"   Criticidad: {filtro_criticidad or 'todas'}")
        
        cursor.execute(query, params)
        reportes = cursor.fetchall()
        
        print(f"✓ Encontrados {len(reportes)} reportes")
        
        # Procesar cada reporte
        for reporte in reportes:
            # Verificar recursos
            cursor.execute("""
                SELECT r.tipo, r.url, r.nombre 
                FROM reporte_recurso rr
                JOIN recurso r ON rr.recurso_id = r.id_recurso
                WHERE rr.reporte_id = %s
            """, (reporte['id_reporte'],))
            recursos = cursor.fetchall()
            
            reporte['tiene_gitlab'] = any(rec['tipo'] == 'GITLAB' for rec in recursos)
            reporte['tiene_pdf'] = any(rec['tipo'] == 'PDF' for rec in recursos)
            reporte['gitlab_url'] = next((rec['url'] for rec in recursos if rec['tipo'] == 'GITLAB'), None)
            
            # Formatear próxima ejecución
            if reporte['proxima_ejecucion']:
                reporte['proxima_ejecucion_formatted'] = reporte['proxima_ejecucion'].strftime('%d/%m/%Y %H:%M')
                
                # Calcular tiempo restante en formato legible
                horas = reporte['horas_hasta_vencimiento']
                if horas is not None:
                    if horas < 0:
                        dias_retraso = abs(horas) // 24
                        horas_retraso = abs(horas) % 24
                        if dias_retraso > 0:
                            reporte['tiempo_restante'] = f"{int(dias_retraso)}d {int(horas_retraso)}h de retraso"
                        else:
                            reporte['tiempo_restante'] = f"{int(abs(horas))}h de retraso"
                    elif horas < 24:
                        reporte['tiempo_restante'] = f"{int(horas)}h restantes"
                    else:
                        dias = horas // 24
                        horas_restantes = int(horas % 24)
                        reporte['tiempo_restante'] = f"{int(dias)}d {horas_restantes}h"
                else:
                    reporte['tiempo_restante'] = 'N/A'
            else:
                reporte['proxima_ejecucion_formatted'] = 'No programado'
                reporte['tiempo_restante'] = 'N/A'
            
            # Formatear última entrega
            if reporte['ultima_entrega']:
                reporte['ultima_entrega_formatted'] = reporte['ultima_entrega'].strftime('%d/%m/%Y %H:%M')
            else:
                reporte['ultima_entrega_formatted'] = 'Nunca'
            
            # Badge de estado
            estado_badges = {
                'RETRASADO': {'color': 'red', 'icon': 'exclamation-triangle', 'text': 'Retrasado'},
                'PROXIMO_VENCER': {'color': 'yellow', 'icon': 'clock', 'text': 'Próximo a vencer'},
                'EN_TIEMPO': {'color': 'green', 'icon': 'check-circle', 'text': 'En tiempo'},
                'ENTREGADO': {'color': 'blue', 'icon': 'check-double', 'text': 'Entregado'},
                'SIN_PROGRAMAR': {'color': 'gray', 'icon': 'calendar-times', 'text': 'Sin programar'}
            }
            
            estado_calc = reporte.get('estado_calculado', 'SIN_PROGRAMAR')
            reporte['badge_estado'] = estado_badges.get(estado_calc, estado_badges['SIN_PROGRAMAR'])
            
            # Badge de criticidad
            criticidad_badges = {
                'CRITICA': {'color': 'red', 'text': 'Crítica'},
                'ALTA': {'color': 'orange', 'text': 'Alta'},
                'MEDIA': {'color': 'yellow', 'text': 'Media'},
                'BAJA': {'color': 'green', 'text': 'Baja'}
            }
            reporte['badge_criticidad'] = criticidad_badges.get(reporte['criticidad'], criticidad_badges['MEDIA'])
        
        # Obtener filtros disponibles para los dropdowns
        cursor.execute("SELECT DISTINCT estado FROM reporte ORDER BY estado")
        estados_disponibles = [row['estado'] for row in cursor.fetchall()]
        
        criticidades_disponibles = ['CRITICA', 'ALTA', 'MEDIA', 'BAJA']
        
        cursor.close()
        conn.close()
        
        print(f"✅ Catálogo cargado exitosamente con {len(reportes)} reportes")
        
        return render_template(
            'catalogos.html',
            reportes=reportes,
            estados_disponibles=estados_disponibles,
            criticidades_disponibles=criticidades_disponibles,
            filtro_busqueda=filtro_busqueda,
            filtro_estado=filtro_estado,
            filtro_criticidad=filtro_criticidad
        )
        
    except Exception as e:
        print(f"❌ ERROR en catálogo: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        
        flash(f"❌ Error al cargar catálogo: {str(e)}", "error")
        return render_template('catalogos.html', reportes=[], estados_disponibles=[], criticidades_disponibles=[])


@catalogos_bp.route('/reporte/<int:reporte_id>')
def ver_detalle(reporte_id):
    """Vista de detalle de un reporte"""
    
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Obtener reporte completo
        cursor.execute("""
            SELECT 
                r.*,
                t.nombre as tipo_nombre,
                c.nombre as categoria_nombre,
                a1.nombre as area_reportante_nombre,
                a2.nombre as area_ejecutora_nombre,
                a3.nombre as area_receptora_nombre,
                s.frecuencia,
                s.reglas_json,
                u.nombre as creado_por_nombre
            FROM reporte r
            LEFT JOIN tipo_reporte t ON r.tipo_id = t.id_tipo
            LEFT JOIN categoria_reporte c ON r.categoria_id = c.id_categoria
            LEFT JOIN area a1 ON r.area_reportante_id = a1.id_area
            LEFT JOIN area a2 ON r.area_ejecutora_id = a2.id_area
            LEFT JOIN area a3 ON r.area_receptora_id = a3.id_area
            LEFT JOIN reporte_schedule s ON r.id_reporte = s.reporte_id
            LEFT JOIN usuario u ON r.creado_por = u.id_usuario
            WHERE r.id_reporte = %s
        """, (reporte_id,))
        
        reporte = cursor.fetchone()
        
        if not reporte:
            flash("❌ Reporte no encontrado", "error")
            return redirect('/catalogos')
        
        # Obtener historial de entregas
        cursor.execute("""
            SELECT 
                h.*,
                u.nombre as creado_por_nombre
            FROM historial_entregas h
            LEFT JOIN usuario u ON h.creado_por = u.id_usuario
            WHERE h.reporte_id = %s
            ORDER BY h.created_at DESC
            LIMIT 10
        """, (reporte_id,))
        
        historial = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return render_template('reporte_detalle.html', reporte=reporte, historial=historial)
        
    except Exception as e:
        print(f"❌ ERROR al ver detalle: {str(e)}")
        flash(f"❌ Error: {str(e)}", "error")
        return redirect('/catalogos')
