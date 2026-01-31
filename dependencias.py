# ============================================================================
# DEPENDENCIAS.PY - Route para Visualización de Trazabilidad Jerárquica
# ============================================================================
# Sistema de navegación multinivel de dependencias de reportes
# Permite visualizar: padres -> padres de padres -> ... -> reporte foco -> hijos -> hijos de hijos -> ...

from flask import Blueprint, render_template, jsonify, request
from db import get_connection
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

dependencias_bp = Blueprint('dependencias', __name__)

# ============================================================================
# RUTA PRINCIPAL - RENDERIZA LA VISTA
# ============================================================================

@dependencias_bp.route('/dependencias')

def index():
    """Renderiza la página principal de dependencias"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Obtener lista de reportes para el selector
        cursor.execute("""
            SELECT id_reporte, codigo_interno, nombre, descripcion, audiencia
            FROM reporte
            WHERE estado = 'Aprobado'
            ORDER BY codigo_interno
        """)
        
        reportes = []
        for row in cursor.fetchall():
            reportes.append({
                'id': row[0],
                'codigo_interno': row[1],
                'nombre': row[2],
                'descripcion': row[3],
                'audiencia': row[4]
            })
        
        cursor.close()
        conn.close()
        
        return render_template('dependencias.html', reportes=reportes)
        
    except Exception as e:
        logger.error(f"Error al cargar página de dependencias: {str(e)}")
        return render_template('error.html', mensaje="Error al cargar trazabilidad"), 500


# ============================================================================
# API - OBTENER ÁRBOL COMPLETO DE DEPENDENCIAS
# ============================================================================

@dependencias_bp.route('/api/dependencias/arbol/<int:id_reporte>')
def obtener_arbol_dependencias(id_reporte):
    """
    Obtiene el árbol completo de dependencias para un reporte focal
    
    Retorna:
    {
        "foco": {...},
        "niveles_upstream": [[nivel1], [nivel2], ...],  # Padres, abuelos, etc.
        "niveles_downstream": [[nivel1], [nivel2], ...]  # Hijos, nietos, etc.
    }
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # 1. Obtener información del reporte focal
        foco = obtener_info_reporte(cursor, id_reporte)
        
        if not foco:
            return jsonify({"error": "Reporte no encontrado"}), 404
        
        # 2. Construir niveles hacia arriba (upstream - dependencias)
        niveles_upstream = construir_niveles_upstream(cursor, id_reporte)
        
        # 3. Construir niveles hacia abajo (downstream - afectaciones)
        niveles_downstream = construir_niveles_downstream(cursor, id_reporte)
        
        cursor.close()
        conn.close()
        
        resultado = {
            "foco": foco,
            "niveles_upstream": niveles_upstream,
            "niveles_downstream": niveles_downstream,
            "total_upstream": sum(len(nivel) for nivel in niveles_upstream),
            "total_downstream": sum(len(nivel) for nivel in niveles_downstream)
        }
        
        logger.info(f"Árbol generado para reporte {id_reporte}: {len(niveles_upstream)} niveles upstream, {len(niveles_downstream)} niveles downstream")
        
        return jsonify(resultado)
        
    except Exception as e:
        logger.error(f"Error al obtener árbol de dependencias: {str(e)}")
        return jsonify({"error": str(e)}), 500


# ============================================================================
# FUNCIONES AUXILIARES - CONSTRUCCIÓN DE NIVELES
# ============================================================================

def obtener_info_reporte(cursor, id_reporte):
    """Obtiene información completa de un reporte"""
    cursor.execute("""
        SELECT 
            r.id_reporte,
            r.codigo_interno,
            r.nombre,
            r.descripcion,
            r.audiencia,
            r.estado,
            tr.nombre as tipo_reporte,
            rs.frecuencia as frecuencia,
            r.receptor_externo,
            (SELECT COUNT(*) FROM reporte_dependencia WHERE reporte_dependiente_id = r.id_reporte) as num_dependencias,
            (SELECT COUNT(*) FROM reporte_dependencia WHERE reporte_origen_id = r.id_reporte) as num_afectaciones
        FROM reporte r
        LEFT JOIN tipo_reporte tr ON r.tipo_id= tr.id_tipo
        LEFT JOIN reporte_schedule rs ON r.id_reporte = rs.reporte_id
        WHERE r.id_reporte = %s
    """, (id_reporte,))
    
    row = cursor.fetchone()
    if not row:
        return None
    
    return {
        'id': row[0],
        'codigo_interno': row[1],
        'nombre': row[2],
        'descripcion': row[3],
        'audiencia': row[4],
        'estado': row[5],
        'tipo': row[6],
        'frecuencia': row[7],
        'receptor_externo': row[8],
        'num_dependencias': row[9],
        'num_afectaciones': row[10]
    }


def construir_niveles_upstream(cursor, id_reporte_inicial, max_niveles=10):
    """
    Construye niveles upstream (dependencias) recursivamente
    
    Nivel 0: Dependencias directas (padres)
    Nivel 1: Dependencias de las dependencias (abuelos)
    Nivel N: ...hasta que no haya más padres
    """
    niveles = []
    ids_procesados = {id_reporte_inicial}  # Evitar ciclos
    ids_nivel_actual = {id_reporte_inicial}
    
    for nivel in range(max_niveles):
        if not ids_nivel_actual:
            break
        
        # Obtener padres del nivel actual
        padres = obtener_padres_directos(cursor, ids_nivel_actual, ids_procesados)
        
        if not padres:
            break
        
        niveles.append(padres)
        
        # Preparar siguiente nivel
        ids_procesados.update(p['id'] for p in padres)
        ids_nivel_actual = {p['id'] for p in padres}
    
    # Invertir para que el nivel más lejano esté primero (visual)
    return list(reversed(niveles))


def construir_niveles_downstream(cursor, id_reporte_inicial, max_niveles=10):
    """
    Construye niveles downstream (afectaciones) recursivamente
    
    Nivel 0: Afectaciones directas (hijos)
    Nivel 1: Afectaciones de las afectaciones (nietos)
    Nivel N: ...hasta que no haya más hijos
    """
    niveles = []
    ids_procesados = {id_reporte_inicial}  # Evitar ciclos
    ids_nivel_actual = {id_reporte_inicial}
    
    for nivel in range(max_niveles):
        if not ids_nivel_actual:
            break
        
        # Obtener hijos del nivel actual
        hijos = obtener_hijos_directos(cursor, ids_nivel_actual, ids_procesados)
        
        if not hijos:
            break
        
        niveles.append(hijos)
        
        # Preparar siguiente nivel
        ids_procesados.update(h['id'] for h in hijos)
        ids_nivel_actual = {h['id'] for h in hijos}
    
    return niveles


def obtener_padres_directos(cursor, ids_hijos, ids_excluir):
    """Obtiene todos los padres directos de un conjunto de reportes"""
    if not ids_hijos:
        return []
    
    placeholders = ','.join(['%s'] * len(ids_hijos))
    
    query = f"""
        SELECT DISTINCT
            r.id_reporte,
            r.codigo_interno,
            r.nombre,
            r.descripcion,
            r.audiencia,
            r.estado,
            tr.nombre as tipo,
            dr.tipo_dependencia,
            dr.criticidad
        FROM reporte_dependencia dr
        INNER JOIN reporte r ON dr.reporte_origen_id  = r.id_reporte
        LEFT JOIN tipo_reporte tr ON r.tipo_id = tr.id_tipo
        WHERE dr.reporte_dependiente_id IN ({placeholders})
        AND r.id_reporte NOT IN ({','.join(['%s'] * len(ids_excluir))})
        AND r.estado = 'Aprobado'
        ORDER BY dr.criticidad DESC, r.codigo_interno
    """
    
    params = list(ids_hijos) + list(ids_excluir)
    cursor.execute(query, params)
    
    padres = []
    for row in cursor.fetchall():
        padres.append({
            'id': row[0],
            'codigo_interno': row[1],
            'nombre': row[2],
            'descripcion': row[3],
            'audiencia': row[4],
            'estado': row[5],
            'tipo': row[6],
            'tipo_dependencia': row[7],
            'criticidad': row[8]
        })
    
    return padres


def obtener_hijos_directos(cursor, ids_padres, ids_excluir):
    """Obtiene todos los hijos directos de un conjunto de reportes"""
    if not ids_padres:
        return []
    
    placeholders = ','.join(['%s'] * len(ids_padres))
    
    query = f"""
        SELECT DISTINCT
            r.id_reporte,
            r.codigo_interno,
            r.nombre,
            r.descripcion,
            r.audiencia,
            r.estado,
            tr.nombre as tipo,
            dr.tipo_dependencia,
            dr.criticidad
        FROM reporte_dependencia dr
        INNER JOIN reporte r ON dr.reporte_dependiente_id= r.id_reporte
        LEFT JOIN tipo_reporte tr ON r.tipo_id= tr.id_tipo
        WHERE dr.reporte_origen_id  IN ({placeholders})
        AND r.id_reporte NOT IN ({','.join(['%s'] * len(ids_excluir))})
        AND r.estado = 'Aprobado'
        ORDER BY dr.criticidad DESC, r.codigo_interno
    """
    
    params = list(ids_padres) + list(ids_excluir)
    cursor.execute(query, params)
    
    hijos = []
    for row in cursor.fetchall():
        hijos.append({
            'id': row[0],
            'codigo_interno': row[1],
            'nombre': row[2],
            'descripcion': row[3],
            'audiencia': row[4],
            'estado': row[5],
            'tipo': row[6],
            'tipo_dependencia': row[7],
            'criticidad': row[8]
        })
    
    return hijos


# ============================================================================
# API - BÚSQUEDA Y FILTROS
# ============================================================================

@dependencias_bp.route('/api/dependencias/buscar')
def buscar_reportes():
    """Busca reportes por código o nombre para cambiar el foco"""
    try:
        termino = request.args.get('q', '').strip()
        
        if len(termino) < 2:
            return jsonify([])
        
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                id_reporte,
                codigo_interno,
                nombre,
                descripcion,
                audiencia
            FROM reporte
            WHERE estado = 'Aprobado'
            AND (
                LOWER(codigo_interno) LIKE LOWER(%s)
                OR LOWER(nombre) LIKE LOWER(%s)
            )
            ORDER BY codigo_interno
            LIMIT 20
        """, (f'%{termino}%', f'%{termino}%'))
        
        resultados = []
        for row in cursor.fetchall():
            resultados.append({
                'id': row[0],
                'codigo_interno': row[1],
                'nombre': row[2],
                'descripcion': row[3],
                'audiencia': row[4],
                'label': f"{row[1]} - {row[2]}"
            })
        
        cursor.close()
        conn.close()
        
        return jsonify(resultados)
        
    except Exception as e:
        logger.error(f"Error en búsqueda: {str(e)}")
        return jsonify({"error": str(e)}), 500


# ============================================================================
# API - CREAR DEPENDENCIA
# ============================================================================

@dependencias_bp.route('/api/dependencias/crear', methods=['POST'])
def crear_dependencia():
    """
    Crea una nueva dependencia entre dos reportes
    
    Body JSON:
    {
        "reporte_origen_id ": int,
        "reporte_dependiente_id": int,
        "tipo_dependencia": "DATOS|CALCULO|CONSOLIDACION|VALIDACION",
        "criticidad": "BAJA|MEDIA|ALTA",
        "observaciones": str (opcional)
    }
    """
    try:
        data = request.get_json()
        
        # Validaciones
        if not data:
            return jsonify({"error": "No se recibieron datos"}), 400
        
        id_padre = data.get('reporte_origen_id') or data.get('id_reporte_padre')
        id_hijo = data.get('reporte_dependiente_id') or data.get('id_reporte_hijo')

        tipo_dep = data.get('tipo_dependencia')
        criticidad = data.get('criticidad')
        observaciones = data.get('observaciones', '').strip() or None
        
        # Validar campos obligatorios
        if not all([id_padre, id_hijo, tipo_dep, criticidad]):
            return jsonify({"error": "Faltan campos obligatorios"}), 400
        
        # Validar que no sea el mismo reporte
        if id_padre == id_hijo:
            return jsonify({"error": "Un reporte no puede depender de sí mismo"}), 400
        
        # Validar tipos
        tipos_validos = ['DATOS', 'CALCULO', 'CONSOLIDACION', 'VALIDACION']
        if tipo_dep not in tipos_validos:
            return jsonify({"error": f"Tipo de dependencia inválido. Debe ser: {', '.join(tipos_validos)}"}), 400
        
        criticidades_validas = ['BAJA', 'MEDIA', 'ALTA']
        if criticidad not in criticidades_validas:
            return jsonify({"error": f"Criticidad inválida. Debe ser: {', '.join(criticidades_validas)}"}), 400
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Verificar que ambos reportes existen y están activos
        cursor.execute("""
            SELECT id_reporte, codigo_interno, nombre, estado 
            FROM reporte 
            WHERE id_reporte IN (%s, %s)
        """, (id_padre, id_hijo))
        
        reportes = cursor.fetchall()
        
        if len(reportes) != 2:
            cursor.close()
            conn.close()
            return jsonify({"error": "Uno o ambos reportes no existen"}), 404
        
        # Verificar que están activos
        for r in reportes:
            if r[3] != 'Aprobado':
                cursor.close()
                conn.close()
                return jsonify({"error": f"El reporte {r[1]} no está aprobado"}), 400
        
        # Verificar si ya existe esta dependencia
        cursor.execute("""
            SELECT id_dependencia 
            FROM reporte_dependencia
            WHERE reporte_origen_id  = %s AND reporte_dependiente_id= %s
        """, (id_padre, id_hijo))
        
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({"error": "Esta dependencia ya existe"}), 409
        
        # Crear la dependencia
        usuario_actual = 1  # temporal hasta login real

        cursor.execute("""
            INSERT INTO reporte_dependencia
            (reporte_origen_id, reporte_dependiente_id, tipo_dependencia, criticidad, observaciones, creado_por)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (id_padre, id_hijo, tipo_dep, criticidad, observaciones, usuario_actual))


        
        id_dependencia = cursor.lastrowid
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"Dependencia creada: ID {id_dependencia} - Padre: {id_padre} → Hijo: {id_hijo}")
        
        return jsonify({
            "success": True,
            "id_dependencia": id_dependencia,
            "mensaje": "Dependencia creada exitosamente"
        }), 201
        
    except Exception as e:
        logger.error(f"Error al crear dependencia: {str(e)}")
        return jsonify({"error": f"Error interno: {str(e)}"}), 500
