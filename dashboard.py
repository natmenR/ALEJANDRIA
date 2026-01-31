from flask import Blueprint, render_template
from db import get_connection

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
def index():
    """Dashboard principal con estadísticas"""
    
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Estadísticas generales
    cursor.execute("""
        SELECT 
            COUNT(*) as total_reportes,
            SUM(CASE WHEN criticidad = 'ALTA' THEN 1 ELSE 0 END) as alta_criticidad,
            SUM(CASE WHEN criticidad = 'MEDIA' THEN 1 ELSE 0 END) as media_criticidad,
            SUM(CASE WHEN criticidad = 'BAJA' THEN 1 ELSE 0 END) as baja_criticidad
        FROM reporte
    """)
    stats = cursor.fetchone()
    
    # Últimos reportes creados - COLUMNA CORREGIDA
    cursor.execute("""
        SELECT 
            r.id_reporte,
            r.codigo_interno,
            r.nombre,
            r.created_at,
            t.nombre as tipo_nombre,
            r.criticidad
        FROM reporte r
        LEFT JOIN tipo_reporte t ON r.tipo_id = t.id_tipo
        ORDER BY r.created_at DESC
        LIMIT 5
    """)
    ultimos_reportes = cursor.fetchall()
    
    # Reportes por frecuencia
    cursor.execute("""
        SELECT 
            s.frecuencia,
            COUNT(s.reporte_id) as cantidad
        FROM reporte_schedule s
        GROUP BY s.frecuencia
        ORDER BY cantidad DESC
    """)
    reportes_por_frecuencia = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template(
        'dashboard.html',
        stats=stats,
        ultimos_reportes=ultimos_reportes,
        reportes_por_frecuencia=reportes_por_frecuencia
    )
