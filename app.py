from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from database import get_connection
import bcrypt
from flask_apscheduler import APScheduler
from datetime import datetime, timedelta


# Inicializar el planificador
scheduler = APScheduler()


#### CORREOS PARA EL CATERING ###############
#############################################
CORREO_CATERING = "alejandro.bernal@unicasa.com.ve" 
CORREO_SOPORTE_IT = "alejandro.bernal@unicasa.com.ve"


#### NOTIFICACIONES EN EL SISTEMA VINCULADO CON EL CORREO #####
###############################################################
def registrar_en_pizarra(mensaje, tipo_alerta):
    try:
        # 1. Sacamos el ID usando el nombre exacto que encontraste
        id_usuario = session.get('usuario_id')

        if not id_usuario:
            print("⚠️ No hay sesión activa. No se grabará la notificación en SQL.")
            return # Salimos de la función sin dar error 500

        conn = get_connection()
        cursor = conn.cursor()

        # 2. Insertamos usando UsuarioID (que es como se llama tu columna en SQL)
        query = """
            INSERT INTO Notificaciones (UsuarioID, Mensaje, Tipo, Leido, FechaCreacion)
            VALUES (?, ?, ?, 0, GETDATE())
        """
        
        cursor.execute(query, (id_usuario, mensaje, tipo_alerta))
        conn.commit()
        conn.close()
        print(f"✅ Notificación registrada para el usuario {id_usuario}")

    except Exception as e:
        print(f"❌ Error crítico en registrar_en_pizarra: {e}")



## CERAR REUNIONES VENCIDAS ####

def cerrar_reuniones_vencidas():
    with app.app_context():
        conn = get_connection()
        cursor = conn.cursor()
        ahora = datetime.now()
        
        try:
            # 1. Buscamos las que ya terminaron y siguen abiertas (Estado 0)
            cursor.execute("""
                SELECT ID_Reserva, Titulo_Evento, ID_Organizador 
                FROM Reservas 
                WHERE Estado_Reserva = 0 AND Hora_Fin < ?
            """, (ahora,))
            
            vencidas = cursor.fetchall()
            
            for row in vencidas:
                id_reserva, titulo, id_organizador = row
                
                # 2. Ponemos la reunión en GRIS (Estado 1)
                cursor.execute("UPDATE Reservas SET Estado_Reserva = 1 WHERE ID_Reserva = ?", (id_reserva,))
                
                # 3. Insertamos la notificación con TUS COLUMNAS REALES
                mensaje = f"Sistema: La reunión '{titulo}' ha finalizado automáticamente."
                cursor.execute("""
                    INSERT INTO Notificaciones (UsuarioID, Mensaje, Tipo, Leido, FechaCreacion)
                    VALUES (?, ?, ?, 0, ?)
                """, (id_organizador, mensaje, 'Sistema', ahora))
                
                print(f"✅ AUTO-CIERRE: '{titulo}' finalizada y notificación creada.")
            
            conn.commit()
        except Exception as e:
            print(f"❌ Error en Vigilante: {e}")
        finally:
            conn.close()



#VERIFICAR RECORDATORIOOOOOOOSSSSSS ###########
###############################################
def verificar_recordatorios():
    # Usamos el contexto de la app para que Flask pueda usar la base de datos
    with app.app_context():
        conn = get_connection()
        cursor = conn.cursor()
        
        ahora = datetime.now()
        margen_30min = ahora + timedelta(minutes=30)

        # 1. Buscamos reservas (AÑADIMOS r.Hora_Fin a la consulta)
        query = """
            SELECT r.ID_Reserva, r.Titulo_Evento, r.Hora_Inicio, s.NombreSala, 
                   u.Nombre + ' ' + u.Apellido as Organizador, u.Email,
                   r.Hora_Fin  -- <-- Agregamos esta columna (índice 6)
            FROM Reservas r
            LEFT JOIN Salas s ON r.ID_Sala = s.ID_Sala
            JOIN Usuarios u ON r.ID_Organizador = u.UsuarioID
            WHERE r.Hora_Inicio <= ? 
              AND r.Hora_Inicio > ?
              AND r.Alerta_Enviada = 0
              AND r.Estado_Reserva < 2
        """
        cursor.execute(query, (margen_30min, ahora))
        proximas = cursor.fetchall()

        for res in proximas:
            id_res = res[0]
            
            # Formateamos la hora de fin usando el nuevo campo res[6]
            datos_mail = {
                'titulo': res[1],
                'inicio': res[2].strftime('%I:%M %p'),
                'fin': res[6].strftime('%I:%M %p') if res[6] else "---", # <-- Ahora sí tomará la hora real
                'sala': res[3] or "🌐 Reunión Virtual",
                'organizador': res[4]
            }
            correo_org = res[5]

            # 2. Buscamos a los invitados en tu tabla específica
            cursor.execute("""
                SELECT u.Email 
                FROM Invitados_Internos ii
                JOIN Usuarios u ON ii.UsuarioID = u.UsuarioID
                WHERE ii.ID_Reserva = ?
            """, (id_res,))
            lista_invitados = [row[0] for row in cursor.fetchall() if row[0]]

            # 3. Disparamos la notificación masiva (Naranja / Recordatorio)
            asunto_alerta = f"⏳ RECORDATORIO: {datos_mail['titulo']} inicia en poco tiempo."
            
            # Usamos tipo="recordatorio" (asegúrate de que esté en tu config con color naranja)
            enviar_correo_masivo(correo_org, lista_invitados, asunto_alerta, datos_mail, tipo="recordatorio")

            # 4. Marcamos la reserva para que no vuelva a enviar el correo en 5 min
            cursor.execute("UPDATE Reservas SET Alerta_Enviada = 1 WHERE ID_Reserva = ?", (id_res,))
            print(f"⏰ Recordatorio enviado para la reunión: {datos_mail['titulo']}")
        
        conn.commit()
        conn.close()





app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = 'unicasa_clave_secreta_2026'

# --- 1. RUTA INICIAL ---
@app.route('/')
def index():
    return render_template('login.html')

# --- 2. PROCESO DE AUTENTICACIÓN ---
@app.route('/auth', methods=['POST'])
def login():
    email = request.form.get('email') 
    password_candidata = request.form.get('password')

    conn = get_connection()
    if conn:
        cursor = conn.cursor()
        # Traemos EsAdmin (asegúrate de haber corrido el ALTER TABLE en SQL) [cite: 2026-02-09]
        cursor.execute("SELECT UsuarioID, Nombre, PasswordHash, CargoID, EsAdmin FROM Usuarios WHERE Email = ?", (email,))
        usuario = cursor.fetchone()
        conn.close()

        # Si el usuario existe y la clave coincide
        if usuario and bcrypt.checkpw(password_candidata.encode('utf-8'), usuario[2].encode('utf-8')):
            session['usuario_id'] = usuario[0]
            session['nombre'] = usuario[1]
            session['cargo_id'] = usuario[3] 
            
            # Manejo de nulos para EsAdmin [cite: 2026-02-09]
            es_admin_valor = usuario[4] if usuario[4] is not None else 0
            session['es_admin'] = bool(es_admin_valor) 
            
            # Nota: usamos session['nombre'] para la bienvenida
            return render_template('animacion_bienvenida.html', nombre=session['nombre'])
        
        else:
            # Credenciales incorrectas
            return render_template('login.html', error_login=True)
    
    # Error de conexión a base de datos
    return render_template('login.html', error_login=True)


    # REGISTRO GENERAL

# --- 2. MOSTRAR REGISTRO (Carga los datos de SQL) ---
@app.route('/pantalla_registro')
def ir_a_registro():
    conn = get_connection()
    if conn:
        cursor = conn.cursor()
        # Traemos los datos para los selectores del HTML
        cursor.execute("SELECT DeptoID, NombreDepto FROM Departamentos")
        deps = [{"id": r[0], "nombre": r[1]} for r in cursor.fetchall()]
        
        cursor.execute("SELECT SedeID, NombreSede FROM Sedes")
        sds = [{"id": r[0], "nombre": r[1]} for r in cursor.fetchall()]
        
        cursor.execute("SELECT CargoID, NombreCargo FROM Cargos")
        cgs = [{"id": r[0], "nombre": r[1]} for r in cursor.fetchall()]
        conn.close()
        
        return render_template('register.html', departamentos=deps, sedes=sds, cargos=cgs)
    return "Error: No se pudo conectar a la base de datos de Unicasa."

# --- 3. PROCESAR REGISTRO (Guarda en SQL) ---
@app.route('/registrar', methods=['POST'])
def registrar_usuario():
    data = request.form
    
    if data['password'] != data['confirm_password']:
        return "Las contraseñas no coinciden."

    pw_encriptada = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    conn = get_connection()
    if conn:
        cursor = conn.cursor()
        try:
            query = """INSERT INTO Usuarios (Cedula, Nombre, Apellido, Email, PasswordHash, SedeID, DeptoID, CargoID) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)"""
            cursor.execute(query, (
                data['cedula'], data['nombre'], data['apellido'], 
                data['email'], pw_encriptada, 
                data['id_sede'], data['id_departamento'], data['id_cargo']
            ))
            conn.commit()
            return redirect(url_for('index'))
        except Exception as e:
            return f"Error al guardar: {e}"
        finally:
            conn.close()
    return "Error de conexión."

#Dashboard ACTIVO
@app.route('/dashboard')
def dashboard():
    if 'usuario_id' not in session:
        return redirect(url_for('index'))

    usuario_id = session['usuario_id']
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Usamos LEFT JOIN para que si falta el cargo, no se rompa nada
        query = """
            SELECT u.Nombre, u.Apellido, 
                   ISNULL(c.NombreCargo, 'Personal'), 
                   ISNULL(d.NombreDepto, 'Unicasa'), 
                   u.FotoPerfil
            FROM Usuarios u
            LEFT JOIN Cargos c ON u.CargoID = c.CargoID
            LEFT JOIN Departamentos d ON u.DeptoID = d.DeptoID
            WHERE u.UsuarioID = ?
        """
        cursor.execute(query, (usuario_id,))
        res = cursor.fetchone()

        if res:
            user_data = {
                "nombre_completo": f"{res[0]} {res[1]}",
                "nombre_pila": res[0], # Solo el nombre para compatibilidad
                "cargo": res[2],
                "departamento": res[3],
                "foto": res[4] if res[4] and res[4] != 'default.png' else None
            }
        
            # ENVIAMOS AMBOS: 'usuario' para el sidebar y 'nombre' para el resto del HTML
            return render_template('dashboard.html', 
                                   usuario=user_data, 
                                   nombre=user_data["nombre_pila"])

    except Exception as e:
        print(f"Error en dashboard: {e}")
        return redirect(url_for('index'))
    finally:
        conn.close()


#PERFIL    
@app.route('/perfil')
def perfil():
    if 'usuario_id' not in session:
        return redirect(url_for('index'))

    conn = get_connection()
    cursor = conn.cursor()
    
    # Query para traer datos del usuario + nombre de Sede y Depto
    query = """
        SELECT u.Nombre, u.Apellido, u.Cedula, u.Email, u.Telefono, 
               s.NombreSede, d.NombreDepto, u.FotoPerfil
        FROM Usuarios u
        JOIN Sedes s ON u.SedeID = s.SedeID
        JOIN Departamentos d ON u.DeptoID = d.DeptoID
        WHERE u.UsuarioID = ?
    """
    
    try:
        cursor.execute(query, (session['usuario_id'],))
        res = cursor.fetchone()
        
        if not res:
            return "Usuario no encontrado", 404

        # Creamos el objeto 'usuario' ajustado para el nuevo HTML
        user_data = {
            "nombre": res[0],
            "apellido": res[1],
            "cedula": res[2],
            "correo": res[3],
            "telefono": res[4] if res[4] else "",
            "nombre_sede": res[5],
            "nombre_departamento": res[6],
            # Si en SQL es 'default.png' o None, mandamos None para activar el avatar de iniciales
            "foto_perfil": res[7] if res[7] and res[7] != 'default.png' else None
        }

        return render_template('perfil.html', usuario=user_data)

    except Exception as e:
        print(f"Error al cargar perfil: {e}")
        return "Error interno del servidor", 500
    finally:
        conn.close()



# GUARDAR CAMBIOS:
@app.route('/actualizar_perfil', methods=['POST'])
def actualizar_perfil():
    # 1. Obtenemos los datos del formulario
    nombre = request.form.get('nombre')
    apellido = request.form.get('apellido')
    nuevo_correo = request.form.get('correo')
    nueva_cedula = request.form.get('cedula')
    nuevo_telefono = request.form.get('telefono')
    nueva_pass = request.form.get('password')

    conn = get_connection()
    cursor = conn.cursor()

    try:
        if nueva_pass:
            pw_hash = bcrypt.hashpw(nueva_pass.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            # Nombres de columnas según tu imagen de SQL
            query = """
                UPDATE Usuarios 
                SET Nombre=?, Apellido=?, Email=?, Cedula=?, Telefono=?, PasswordHash=? 
                WHERE UsuarioID=?
            """
            cursor.execute(query, (nombre, apellido, nuevo_correo, nueva_cedula, nuevo_telefono, pw_hash, session['usuario_id']))
        else:
            query = """
                UPDATE Usuarios 
                SET Nombre=?, Apellido=?, Email=?, Cedula=?, Telefono=? 
                WHERE UsuarioID=?
            """
            cursor.execute(query, (nombre, apellido, nuevo_correo, nueva_cedula, nuevo_telefono, session['usuario_id']))
        
        conn.commit()
        session['usuario_nombre'] = nombre 

    except Exception as e:
        print(f"Error al actualizar: {e}")
    finally:
        conn.close()

    return redirect(url_for('perfil', actualizado='true'))



# --- OBTENER PERSONAL ---
@app.route('/api/obtener_personal')
def obtener_personal():
    if 'usuario_id' not in session:
        return jsonify({"error": "No autorizado"}), 401

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # 1. Traer Empleados (Usuarios)
        cursor.execute("SELECT UsuarioID, Nombre, Apellido FROM Usuarios")
        empleados = [{"id_usuario": row[0], "nombre": row[1], "apellido": row[2]} for row in cursor.fetchall()]

        # 2. Traer Roles/Cargos 
        cursor.execute("SELECT CargoID, NombreCargo FROM Cargos")
        cargos = [{"id_cargo": row[0], "nombre_cargo": row[1]} for row in cursor.fetchall()]

        # 3. Traer Departamentos (NOMBRES REALES: DeptoID y NombreDepto)
        # Aquí estaba el error: SQL Server no encontraba "id" ni "nombre"
        cursor.execute("SELECT DeptoID, NombreDepto FROM departamentos")
        departamentos = [{"id": row[0], "nombre": row[1]} for row in cursor.fetchall()]

        conn.close()

        # Enviamos los datos. El JS seguirá recibiendo "id" y "nombre" 
        # para que no tengas que cambiar tu HTML.
        return jsonify({
            "empleados": empleados,
            "cargos": cargos,
            "departamentos": departamentos 
        })

    except Exception as e:
        if conn: conn.close()
        # Esto imprimirá el error exacto en tu terminal de VS Code
        print(f"Error en obtener_personal: {e}")
        return jsonify({"error": str(e)}), 500


# ==========================================
# RUTA: GUARDAR EVENTOS CON NOTIFICACIONES
# ==========================================
@app.route('/api/guardar_evento', methods=['POST'])
def guardar_evento():
    data = request.json
    
    titulo = data.get('titulo', 'Sin Título')
    # Recibimos las cadenas completas desde JS (ej: '2026-03-09T08:00')
    inicio_raw = data.get('fecha_inicio_completa')
    fin_raw = data.get('fecha_fin_completa')
    
    descripcion = data.get('descripcion', '')
    tipo = data.get('tipo_asignacion') 
    id_asignado = data.get('id_asignado') 
    id_depto_filtro = data.get('id_departamento_filtro')
    color_elegido = data.get('color', '#800020') 
    
    # Procesamos las fechas para que SQL Server las entienda bien (YYYY-MM-DD HH:MM:SS)
    # Reemplazamos la 'T' del input datetime-local por un espacio
    inicio_sql = inicio_raw.replace('T', ' ') + ":00"
    fin_sql = fin_raw.replace('T', ' ') + ":00"

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # 1. DATOS DE SESIÓN
        creador_id = int(session.get('usuario_id', 1)) 
        nombre_creador = session.get('nombre', 'Un administrador')
        
        # 2. INSERTAR EVENTO PRINCIPAL
        query_insert = """
            INSERT INTO Eventos (Titulo, Descripcion, FechaInicio, FechaFin, Color, CreadoPor, TipoAsignacion)
            OUTPUT INSERTED.EventoID
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        # Usamos inicio_sql y fin_sql que ya traen sus fechas independientes
        cursor.execute(query_insert, (titulo, descripcion, inicio_sql, fin_sql, color_elegido, creador_id, tipo))
        
        fila = cursor.fetchone()
        if not fila:
            raise Exception("No se pudo obtener el EventoID generado")
        evento_id = int(fila[0])

        mensaje_notif = f"El usuario {nombre_creador} te agregó a '{titulo}'."
        usuarios_finales = []

        lista_ids = id_asignado if isinstance(id_asignado, list) else [id_asignado]

        # --- EXPANSIÓN DE DESTINATARIOS ---
        if tipo == 'persona':
            usuarios_finales = [int(x) for x in lista_ids if x]

        elif tipo == 'cargo':
            for cargo_id in lista_ids:
                if id_depto_filtro == 'todos':
                    cursor.execute("SELECT UsuarioID FROM usuarios WHERE CargoID = ?", (cargo_id,))
                else:
                    cursor.execute("SELECT UsuarioID FROM usuarios WHERE CargoID = ? AND DeptoID = ?", (cargo_id, id_depto_filtro))
                usuarios_finales.extend([int(row[0]) for row in cursor.fetchall()])

        elif tipo == 'departamento':
            for depto_id in lista_ids:
                cursor.execute("SELECT UsuarioID FROM usuarios WHERE DeptoID = ?", (depto_id,))
                usuarios_finales.extend([int(row[0]) for row in cursor.fetchall()])

       # 3. ELIMINAR DUPLICADOS Y PROCESAR INVITADOS/NOTIFICACIONES
        usuarios_finales = list(set(usuarios_finales))

        for uid in usuarios_finales:
            # 3.1. Insertar Invitado en la tabla de eventos
            cursor.execute("INSERT INTO Eventos_Invitados (EventoID, UsuarioID) VALUES (?, ?)", (evento_id, uid))
            
            # 3.2. LÓGICA DE MENSAJE DINÁMICO
            if int(uid) == int(creador_id):
                mensaje_final = f"Has creado la tarea '{titulo}', revísala en tu panel de tareas."
            else:
                mensaje_final = f"El usuario {nombre_creador} te agregó a la tarea '{titulo}', revísala en tu panel de tareas."
            
            # 3.3. Insertar Notificación (Formato original ultra-seguro)
            # Asegúrate que 'Tipo' no exceda el largo de la columna en SQL
            cursor.execute("""
                INSERT INTO notificaciones (UsuarioID, Mensaje, Tipo, Leido, FechaCreacion)
                VALUES (?, ?, 'Asignacion', 0, GETDATE())
            """, (uid, mensaje_final))

        print(f"📢 Notificaciones generadas para {len(usuarios_finales)} usuarios.")

        # 4. LOG DE AUDITORÍA
        detalle_log = f"Creó la tarea: {titulo} (ID: {evento_id}) asignada a {len(usuarios_finales)} usuarios."
        cursor.execute("""
            INSERT INTO Logs_Auditoria (UsuarioID, Accion, Detalle)
            VALUES (?, 'CREACION', ?)
        """, (creador_id, detalle_log))

        conn.commit()
        return jsonify({"status": "success", "evento_id": evento_id, "afectados": len(usuarios_finales)})

    except Exception as e:
        if conn: conn.rollback()
        print(f"Error en SQL Guardar: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if conn: conn.close()

# ==========================================
# RUTA: OBTENER EVENTOS (CALENDARIO)
# ==========================================
@app.route('/api/eventos')
def obtener_eventos():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # 1. Consulta principal (Usando UsuarioID y Nombre/Apellido con mayúscula)
        query = """
            SELECT 
                r.ID_Reserva, s.NombreSala, r.Titulo_Evento, 
                r.Hora_Inicio, r.Hora_Fin, s.ColorHex,
                r.Descripcion, r.Materiales_Requeridos, r.ID_Sala, r.ID_Organizador,
                s.Capacidad, s.Ubicacion, s.Dimensiones, s.Equipamiento,
                u.Nombre + ' ' + u.Apellido as OrganizadorNombre
            FROM Reservas r
            JOIN Salas s ON r.ID_Sala = s.ID_Sala
            LEFT JOIN Usuarios u ON r.ID_Organizador = u.UsuarioID
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        
        reuniones = []
        for row in rows:
            id_reserva = row[0]
            
          # 2. BUSCAR INVITADOS INTERNOS
            cursor.execute("""
                SELECT u.Nombre, u.Apellido, u.Cedula 
                FROM Usuarios u
                JOIN invitados_internos ii ON u.UsuarioID = ii.id_usuario
                WHERE ii.id_reserva = ?
            """, (id_reserva,))
            
            internos = []
            filas = cursor.fetchall()
            for r in filas:
                # Armamos el objeto con nombres ULTRA simples: 'n' y 'c'
                invitado = {
                    'n': f"{r[0]} {r[1]}".strip(), # n de nombre
                    'c': str(r[2]).strip() if r[2] else "S/C" # c de cedula
                }
                print(f"ENVIANDO A JS -> {invitado}") # Mira esto en tu terminal
                internos.append(invitado)

            # 3. BUSCAR INVITADOS EXTERNOS
            cursor.execute("""
                SELECT Nombre, Empresa, Cedula 
                FROM Invitados_Externos 
                WHERE ID_Reserva = ?
            """, (id_reserva,))
            externos = [{'nombre': r[0], 'empresa': r[1], 'cedula': r[2]} for r in cursor.fetchall()]
            
            reuniones.append({
                'id': id_reserva,
                'title': f"✔ {row[2]}",
                'start': row[3].isoformat(),
                'end': row[4].isoformat() if row[4] else None,
                'color': row[5] if row[5] else '#6b0f1a',
                'extendedProps': {
                    'nombre_sala': row[1],
                    'descripcion': row[6],
                    'materiales': row[7],
                    'id_sala': row[8],
                    'id_organizador': row[9],
                    'Capacidad': row[10],
                    'Ubicacion': row[11],
                    'Dimensiones': row[12],
                    'Equipamiento': row[13],
                    'organizador': row[14] or 'No asignado',
                    'invitados_internos': internos,
                    'invitados': externos
                }
            })
            
        return jsonify(reuniones)
    except Exception as e:
        print(f"Error en calendario: {e}")
        return jsonify([])
    finally:
        conn.close()






# ==========================================
# RUTA: ELIMINAR EVENTOS
# ==========================================
@app.route('/api/eliminar_evento/<int:id>', methods=['DELETE'])
def eliminar_evento(id):
    if 'usuario_id' not in session:
        return jsonify({"status": "error", "message": "Sesión no iniciada"}), 401

    usuario_actual = session.get('usuario_id')
    es_jefe = (session.get('cargo_id') == 5)
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT CreadoPor, Titulo FROM Eventos WHERE EventoID = ?", (id,))
        resultado = cursor.fetchone()
        
        if not resultado:
            return jsonify({"status": "error", "message": "La tarea no existe"}), 404
            
        creador_id = resultado[0]
        nombre_tarea = resultado[1]

        # Solo el creador o el jefe pueden borrar
        if creador_id == usuario_actual or es_jefe:
            # Avisar a invitados antes de borrar
            cursor.execute("""
                INSERT INTO notificaciones (UsuarioID, Mensaje, Tipo, Leido, FechaCreacion)
                SELECT UsuarioID, 'La tarea "' + ? + '" fue eliminada.', 'Alerta', 0, GETDATE()
                FROM Eventos_Invitados WHERE EventoID = ?
            """, (nombre_tarea, id))
            
            cursor.execute("DELETE FROM Eventos_Invitados WHERE EventoID = ?", (id,))
            cursor.execute("DELETE FROM Eventos WHERE EventoID = ?", (id,))
            
            cursor.execute("""
                INSERT INTO Logs_Auditoria (UsuarioID, Accion, Detalle)
                VALUES (?, 'BORRADO', ?)
            """, (usuario_actual, f"Eliminó la tarea: {nombre_tarea} (ID: {id})"))
            
            conn.commit()
            return jsonify({"status": "success", "message": "Eliminado correctamente"})
        
        return jsonify({"status": "error", "message": "No tienes permiso"}), 403

    except Exception as e:
        print(f"Error al eliminar: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


# TAREAS/EVENTOS/PLANIFICACIONES
@app.route('/api/tareas_detalladas')
def tareas_detalladas():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Lógica corregida: 
    # Si TipoAsignacion es 'cargo' o 'departamento', muestra el nombre del grupo.
    # Si es 'persona', lista todos los nombres de los invitados.
    query = """
        SELECT 
           e.EventoID, 
            e.Titulo, 
            CAST(e.Descripcion AS NVARCHAR(MAX)) as Descripcion, 
            FORMAT(e.FechaInicio, 'dd/MM/yyyy hh:mm tt') as Inicio,
            FORMAT(e.FechaFin, 'dd/MM/yyyy hh:mm tt') as Fin,
            e.completado,
            ISNULL(STUFF((
                SELECT DISTINCT ', ' + 
                    CASE 
                        WHEN e.TipoAsignacion = 'cargo' THEN c.NombreCargo
                        WHEN e.TipoAsignacion = 'departamento' THEN d.NombreDepto
                        ELSE u.Nombre + ' ' + u.Apellido
                    END
                FROM Eventos_Invitados ei
                INNER JOIN usuarios u ON ei.UsuarioID = u.UsuarioID 
                LEFT JOIN cargos c ON u.CargoID = c.CargoID
                LEFT JOIN departamentos d ON u.DeptoID = d.DeptoID
                WHERE ei.EventoID = e.EventoID
                FOR XML PATH(''), TYPE).value('.', 'NVARCHAR(MAX)'), 1, 2, ''), 'Sin asignar') as AsignadoA
        FROM Eventos e
        WHERE e.archivado = 0
        GROUP BY 
            e.EventoID, 
            e.Titulo, 
            CAST(e.Descripcion AS NVARCHAR(MAX)), 
            e.FechaInicio, 
            e.FechaFin,     -- <--- 2. CLAVE: Agregado al GROUP BY para evitar el error 8120
            e.completado,
            e.TipoAsignacion
        ORDER BY e.completado ASC, e.FechaInicio DESC
    """
    
    try:
        cursor.execute(query)
        columnas = [column[0] for column in cursor.description]
        resultado = [dict(zip(columnas, row)) for row in cursor.fetchall()]
        return jsonify(resultado)
    except Exception as e:
        print(f"Error en visualización dinámica (tareas_detalladas): {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()



###### DASH BOARD TAREAS COSAS #####
####################################
@app.route('/api/dashboard_tareas')
def dashboard_tareas():
    if 'usuario_id' not in session:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        usuario_id = session['usuario_id']

        # 1. Obtener conteos para Gráficos (Torta de Estados)
        cursor.execute("""
            SELECT Estado_Tarea, COUNT(*) 
            FROM Eventos 
            WHERE archivado = 0 
            GROUP BY Estado_Tarea
        """)
        stats_estados = {row[0]: row[1] for row in cursor.fetchall()}

        # 2. Obtener conteos para Gráficos (Torta de Prioridades)
        cursor.execute("""
            SELECT Prioridad, COUNT(*) 
            FROM Eventos 
            WHERE archivado = 0 
            GROUP BY Prioridad
        """)
        stats_prioridades = {row[0]: row[1] for row in cursor.fetchall()}

        # 3. Obtener lista de tareas para el Cronograma (Gantt)
        cursor.execute("""
            SELECT Titulo, FechaInicio, FechaFin, Prioridad, Progreso, EventoID, Descripcion
            FROM Eventos 
            WHERE archivado = 0
            ORDER BY FechaInicio ASC
        """)
        
        tareas_gantt = []
        for r in cursor.fetchall():
            # Asignamos colores según prioridad para el gráfico
            color = "#6b0f1a" if r[3] == 1 else ("#ffc107" if r[3] == 2 else "#28a745")
            
            tareas_gantt.append({
                'id': r[5],
                'name': r[0],
                'start': r[1].strftime('%Y-%m-%d') if r[1] else '2024-01-01',
                'end': r[2].strftime('%Y-%m-%d') if r[2] else '2024-01-01',     
                'progress': r[4] or 0,
                'description': r[6], # <-- Agregamos esto
                'color': color
            })

        conn.close()

        return jsonify({
            'stats_estados': stats_estados,
            'stats_prioridades': stats_prioridades,
            'tareas': tareas_gantt
        })

    except Exception as e:
        print(f"Error en dashboard_tareas: {e}")
        return jsonify({'error': str(e)}), 500




# NOTIFICACIONES
@app.route('/api/notificar_inicio_reunion', methods=['POST'])
def api_notificar_inicio_reunion():
    datos = request.json
    titulo = datos.get('titulo')
    # Llamamos a tu función para que lo meta al SQL
    registrar_en_pizarra(f"La reunión '{titulo}' ha comenzado ahora.", "REUNIÓN")
    return jsonify({"status": "success"})

@app.route('/api/obtener_notificaciones')
def api_notificaciones():
    try:
        id_usuario = session.get('usuario_id')
        conn = get_connection()
        cursor = conn.cursor()
        
        # AGREGAMOS: NotificacionID y Leido (muy importante)
        query = """
            SELECT NotificacionID, Mensaje, Tipo, FechaCreacion, Leido 
            FROM Notificaciones 
            WHERE UsuarioID = ? 
            ORDER BY FechaCreacion DESC
        """
        cursor.execute(query, (id_usuario,))
        
        columnas = [column[0] for column in cursor.description]
        notas = []
        for row in cursor.fetchall():
            d = dict(zip(columnas, row))
            if d['FechaCreacion']:
                d['FechaCreacion'] = d['FechaCreacion'].strftime('%d/%m/%Y %I:%M %p')
            notas.append(d)
            
        conn.close()
        return jsonify(notas)
    except Exception as e:
        print(f"Error en API: {e}")
        return jsonify([])

# --- 2. MARCAR UNA COMO LEÍDA ---
@app.route('/api/marcar_leida_individual/<int:id>', methods=['POST'])
def marcar_leida_individual(id):
    if 'usuario_id' in session:
        conn = get_connection()
        cursor = conn.cursor()
        # Nombre real: NotificacionID y UsuarioID
        cursor.execute("UPDATE notificaciones SET Leido = 1 WHERE NotificacionID = ? AND UsuarioID = ?", 
                       (id, session['usuario_id']))
        conn.commit()
        conn.close()
        return jsonify({"status": "ok"})
    return jsonify({"status": "error"}), 401

# --- 2. MARCAR COMO LEÍDAS ---
@app.route('/api/marcar_leidas', methods=['POST'])
def marcar_leidas():
    if 'usuario_id' in session:
        try:
            conn = get_connection()
            cursor = conn.cursor()
            # Ajustado a tus nombres: Leido, UsuarioID
            cursor.execute("UPDATE notificaciones SET Leido = 1 WHERE UsuarioID = ?", (session['usuario_id'],))
            conn.commit()
            conn.close()
            return jsonify({"status": "ok"})
        except Exception as e:
            print(f"Error en marcar_leidas: {e}")
            return jsonify({"status": "error"}), 500
            
    return jsonify({"status": "error"}), 401


# SONIDO Y CONTAR NOTIFICACIONES: 
#################################
@app.route('/api/contar_notificaciones')
def contar_notificaciones():
    if 'usuario_id' not in session:
        return jsonify({'total': 0, 'ultima_id': None})
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        usuario_id = session['usuario_id']

        # 1. Contamos las no leídas
        cursor.execute("SELECT COUNT(*) FROM Notificaciones WHERE UsuarioID = ? AND Leido = 0", 
                       (usuario_id,))
        total = cursor.fetchone()[0]

        # 2. Obtenemos la última (AJUSTA EL NOMBRE DE LA COLUMNA ID SI ES NECESARIO)
        # Probaremos con 'NotificacionID' o puedes usar '*' si no estás seguro
        cursor.execute("""
            SELECT TOP 1 Tipo, Mensaje 
            FROM Notificaciones 
            WHERE UsuarioID = ? 
            ORDER BY FechaCreacion DESC
        """, (usuario_id,))
        
        ultima = cursor.fetchone()
        
        # Para evitar el error de columna ID, usaremos la Fecha como identificador único si no sabemos el nombre del ID
        # o puedes poner el nombre real de tu columna ID aquí:
        ultima_id = str(ultima[0]) + str(ultima[1]) if ultima else None 

        conn.close()

        return jsonify({
            'total': total,
            'ultima_id': ultima_id, # Usamos una combinación única para identificarla
            'ultima_tipo': ultima[0] if ultima else None,
            'ultima_mensaje': ultima[1] if ultima else None
        })

    except Exception as e:
        print(f"Error al contar: {e}")
        return jsonify({'total': 0, 'ultima_id': None})


# ESTADISTICAS
from flask import jsonify
@app.route('/api/estadisticas-dashboard')
def obtener_estadisticas():
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # 1. TOP SALAS
        query_salas = """
            SELECT S.NombreSala, COUNT(R.ID_Reserva) as Total
            FROM dbo.Reservas R
            JOIN dbo.Salas S ON R.ID_Sala = S.ID_Sala
            GROUP BY S.NombreSala
            ORDER BY Total DESC
        """
        cursor.execute(query_salas)
        res_salas = cursor.fetchall()

        # 2. TOP USUARIOS
        query_usuarios = """
            SELECT U.Nombre, COUNT(R.ID_Reserva) as Total
            FROM dbo.Reservas R
            JOIN dbo.Usuarios U ON R.ID_Organizador = U.UsuarioID
            GROUP BY U.Nombre
            ORDER BY Total DESC
        """
        cursor.execute(query_usuarios)
        res_usuarios = cursor.fetchall()

        # 3. USO POR DÍA DE LA SEMANA
        query_semana = """
            SELECT DATEPART(dw, Hora_Inicio) as Dia, COUNT(*) as Total
            FROM dbo.Reservas
            GROUP BY DATEPART(dw, Hora_Inicio)
            ORDER BY Dia
        """
        cursor.execute(query_semana)
        res_semana = cursor.fetchall()

        # 4. RANKING POR DEPARTAMENTO
        query_deptos = """
            SELECT D.NombreDepto, COUNT(R.ID_Reserva) as Total
            FROM dbo.Reservas R
            JOIN dbo.Usuarios U ON R.ID_Organizador = U.UsuarioID
            JOIN dbo.Departamentos D ON U.DeptoID = D.DeptoID
            GROUP BY D.NombreDepto
            ORDER BY Total DESC
        """
        cursor.execute(query_deptos)
        res_deptos = cursor.fetchall()

       # --- NUEVO: 5. ACTIVIDAD POR HORA (Rango forzado 6 AM - 7 PM) ---
        query_horas = """
            SELECT DATEPART(hour, Hora_Inicio) as Hora, COUNT(*) as Total
            FROM dbo.Reservas
            WHERE DATEPART(hour, Hora_Inicio) BETWEEN 6 AND 19
            GROUP BY DATEPART(hour, Hora_Inicio)
        """
        cursor.execute(query_horas)
        # Convertimos el resultado en un diccionario para fácil búsqueda {hora: total}
        datos_db = {int(fila[0]): fila[1] for fila in cursor.fetchall()}

        cursor.close()
        conn.close()

        # Generamos el rango completo manualmente de 6 a 19 (7 PM)
        labels_horas = []
        data_horas = []
        
        for h in range(6, 20):  # El rango va de 6 hasta 19 (7 PM)
            # Lógica para AM/PM
            if h < 12:
                formato = f"{h} am"
            elif h == 12:
                formato = "12 pm"
            else:
                formato = f"{h - 12} pm" # Convierte 13 en 1 pm, 14 en 2 pm, etc.
            
            labels_horas.append(formato)
            # Si la hora h existe en los datos de la BD, usamos su total; si no, ponemos 0
            data_horas.append(datos_db.get(h, 0))

        return jsonify({
            "salas": {
                "labels": [fila[0] for fila in res_salas],
                "data": [fila[1] for fila in res_salas]
            },
            "usuarios": {
                "labels": [fila[0] for fila in res_usuarios],
                "data": [fila[1] for fila in res_usuarios]
            },
            "semana": [fila[1] for fila in res_semana],
            "departamentos": {
                "labels": [fila[0] for fila in res_deptos],
                "data": [fila[1] for fila in res_deptos]
            },
            "actividad_horas": {
                "labels": labels_horas,
                "data": data_horas
            }
        })

    except Exception as e:
        print(f"Error en estadísticas: {e}")
        return jsonify({"error": str(e)}), 500

## COMPLETAR TRAEA $$
@app.route('/api/completar_tarea/<int:id>', methods=['POST'])
def completar_tarea(id):
    data = request.get_json()
    pin_ingresado = data.get('pin') 
    usuario_actual = session.get('usuario_id')

    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # 1. CAMBIO CLAVE: Buscamos en 'validaciones_pin' usando un JOIN
        # Buscamos el código que NO haya sido usado aún (usado = 0)
        cursor.execute("""
            SELECT v.codigo_pin, e.titulo 
            FROM validaciones_pin v
            JOIN Eventos e ON v.EventoID = e.EventoID
            WHERE v.EventoID = ? AND v.usado = 0
        """, (id,))
        
        tarea = cursor.fetchone()
        
        if not tarea:
            return jsonify({"status": "error", "message": "Tarea no encontrada o PIN ya utilizado"}), 404
            
        pin_real = str(tarea[0])
        nombre_tarea = tarea[1]

        # 2. VALIDACIÓN
        if str(pin_ingresado) != pin_real:
            return jsonify({"status": "error", "message": "PIN incorrecto"}), 403

        # 3. Si el PIN es correcto:
        # Marcamos el PIN como usado para que no se repita
        cursor.execute("UPDATE validaciones_pin SET usado = 1 WHERE EventoID = ?", (id,))
        
        # Marcamos la tarea como completada
        cursor.execute("UPDATE Eventos SET completado = 1 WHERE EventoID = ?", (id,))
        
        # Insertamos la notificación (usando CONCAT para evitar errores de tipos en SQL)
        mensaje = f"✅ Tarea completada con éxito: {nombre_tarea}"
        cursor.execute("""
            INSERT INTO notificaciones (UsuarioID, Mensaje, Tipo, Leido, FechaCreacion)
            SELECT UsuarioID, ?, 'Exito', 0, GETDATE()
            FROM Eventos_Invitados WHERE EventoID = ?
        """, (mensaje, id))

        conn.commit()
        return jsonify({"status": "success", "message": "¡PIN Correcto! Tarea finalizada."})

    except Exception as e:
        print(f"Error con PIN: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


# GENERAR PIN
import random

@app.route('/api/generar_pin/<int:evento_id>', methods=['POST'])
def generar_pin(evento_id):
    # Verificamos que el usuario esté logueado y sea Jefe (Cargo 5)
    if 'usuario_id' in session and session.get('cargo_id') == 5:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Generamos un PIN de 4 dígitos al azar
        pin_nuevo = str(random.randint(1000, 9999))
        
        try:
            # 1. Marcamos pines anteriores como usados. 
            # Cambiado 'id_evento' por 'EventoID'
            cursor.execute("UPDATE validaciones_pin SET usado = 1 WHERE EventoID = ?", (evento_id,))
            
            # 2. Insertamos el nuevo PIN. 
            # Cambiado 'id_evento' por 'EventoID'
            cursor.execute("""
                INSERT INTO validaciones_pin (EventoID, id_jefe, codigo_pin, usado)
                VALUES (?, ?, ?, 0)
            """, (evento_id, session['usuario_id'], pin_nuevo))
            
            conn.commit()
            return jsonify({"status": "success", "pin": pin_nuevo})
            
        except Exception as e:
            # Imprimimos el error en la consola de VS Code para que lo veas
            print(f"Error en base de datos: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
            
        finally:
            conn.close()
    
    return jsonify({"status": "error", "message": "Acceso denegado. Se requiere nivel Jefe."}), 403



from datetime import datetime

@app.route('/api/validar_completar', methods=['POST'])
def validar_completar():
    data = request.get_json()
    evento_id = data.get('evento_id')
    pin_cliente = data.get('pin')
    usuario_actual = session.get('usuario_id') 

    if not usuario_actual:
        return jsonify({"status": "error", "message": "Sesión no iniciada"}), 401

    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # 1. Buscamos PIN y datos de la tarea (Tu JOIN está perfecto)
        cursor.execute("""
            SELECT v.codigo_pin, e.titulo, e.FechaFin, u.Nombre, e.CreadoPor
            FROM validaciones_pin v
            JOIN Eventos e ON v.EventoID = e.EventoID
            JOIN Usuarios u ON e.CreadoPor = u.UsuarioID
            WHERE v.EventoID = ? AND v.usado = 0
        """, (evento_id,))
        
        resultado = cursor.fetchone()

        if not resultado:
            return jsonify({"status": "error", "message": "Tarea no encontrada o ya finalizada."}), 404

        pin_real = str(resultado[0])
        nombre_tarea = resultado[1]
        fecha_fin = resultado[2]
        nombre_responsable = resultado[3]
        id_responsable = resultado[4]

        # --- BLOQUEO POR EXPIRACIÓN ---
        if fecha_fin and fecha_fin < datetime.now():
            cursor.execute("""
                INSERT INTO Logs_Auditoria (UsuarioID, Accion, Detalle)
                VALUES (?, 'FALLO_EXPIRACION', ?)
            """, (usuario_actual, f"Intento de completar tarea EXPIRADA: {nombre_tarea}. Responsable: {nombre_responsable}"))
            
            conn.commit()
            return jsonify({
                "status": "error", 
                "message": f"Lo sentimos, esta tarea expiró el {fecha_fin.strftime('%d/%m %H:%M')}."
            }), 403

        # 2. VALIDACIÓN DEL PIN
        if pin_real == str(pin_cliente):
            # Quemamos el PIN y completamos tarea
            cursor.execute("UPDATE validaciones_pin SET usado = 1 WHERE EventoID = ?", (evento_id,))
            cursor.execute("UPDATE Eventos SET completado = 1 WHERE EventoID = ?", (evento_id,))
            
            # LOG DE AUDITORÍA
            cursor.execute("""
                INSERT INTO Logs_Auditoria (UsuarioID, Accion, Detalle)
                VALUES (?, 'COMPLETADO', ?)
            """, (usuario_actual, f"Finalizó la tarea: {nombre_tarea} (ID: {evento_id})"))

            # NOTIFICAR A INVITADOS (Usando parámetros ? para evitar errores de comillas)
            mensaje_invitados = f"¡Tarea completada! '{nombre_tarea}' ha sido finalizada."
            cursor.execute("""
                INSERT INTO notificaciones (UsuarioID, Mensaje, Tipo, Leido, FechaCreacion)
                SELECT UsuarioID, ?, 'Exito', 0, GETDATE()
                FROM Eventos_Invitados 
                WHERE EventoID = ?
            """, (mensaje_invitados, evento_id))

            # NOTIFICAR AL USUARIO QUE HIZO LA ACCIÓN
            mensaje_propio = f"✅ Has completado la tarea: '{nombre_tarea}'"
            cursor.execute("""
                IF NOT EXISTS (SELECT 1 FROM Eventos_Invitados WHERE EventoID = ? AND UsuarioID = ?)
                BEGIN
                    INSERT INTO notificaciones (UsuarioID, Mensaje, Tipo, Leido, FechaCreacion)
                    VALUES (?, ?, 'Exito', 0, GETDATE())
                END
            """, (evento_id, usuario_actual, usuario_actual, mensaje_propio))
            
            conn.commit()
            return jsonify({"status": "success"})
        else:
            return jsonify({"status": "error", "message": "PIN incorrecto"}), 400
            
    except Exception as e:
        print(f"Error en validación: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


## ARCHIVAR TAREAS EVENTOS ##
@app.route('/api/archivar_evento/<int:id>', methods=['POST'])
def archivar_evento(id):
    # Verificamos sesión y permisos de Admin
    usuario_actual = session.get('usuario_id')
    es_admin = session.get('es_admin') # Asumiendo que guardas esto en session

    if not usuario_actual or not es_admin:
        return jsonify({"status": "error", "message": "No tienes permisos de administrador"}), 403

    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # 1. Verificamos que la tarea ya esté completada (que tenga el PIN puesto)
        cursor.execute("SELECT titulo, completado FROM Eventos WHERE EventoID = ?", (id,))
        tarea = cursor.fetchone()
        
        if not tarea:
            return jsonify({"status": "error", "message": "Tarea no encontrada"}), 404
            
        if tarea[1] == 0:
            return jsonify({"status": "error", "message": "La tarea debe estar completada con PIN antes de archivarse"}), 400

        nombre_tarea = tarea[0]

        # 2. Marcamos como archivado
        cursor.execute("UPDATE Eventos SET archivado = 1 WHERE EventoID = ?", (id,))
        
        # 3. Registramos la acción final en la Auditoría
        cursor.execute("""
            INSERT INTO Logs_Auditoria (UsuarioID, Accion, Detalle)
            VALUES (?, 'ARCHIVADO_FINAL', ?)
        """, (usuario_actual, f"El administrador archivó la reunión: {nombre_tarea} (ID: {id})"))

        conn.commit()
        return jsonify({"status": "success", "message": "Reunión archivada correctamente"})

    except Exception as e:
        print(f"Error al archivar: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


# OBTENER LOGS / REGISTROS DE Todo (SOLO JEFES)
@app.route('/api/obtener_logs')
def obtener_logs():
    if session.get('cargo_id') != 5: # Solo el Jefe (ID 5) puede ver esto
        return jsonify({"status": "error", "message": "Acceso denegado"}), 403

    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Unimos Logs con Usuarios para ver el nombre de quien hizo la acción
        cursor.execute("""
            SELECT L.LogID, U.Nombre, L.Accion, L.Detalle, 
                   FORMAT(L.Fecha, 'dd/MM/yyyy HH:mm') as FechaFormateada
            FROM Logs_Auditoria L
            JOIN Usuarios U ON L.UsuarioID = U.UsuarioID
            ORDER BY L.Fecha DESC
        """)
        
        logs = []
        for row in cursor.fetchall():
            logs.append({
                "id": row[0],
                "usuario": row[1],
                "accion": row[2],
                "detalle": row[3],
                "fecha": row[4]
            })
        return jsonify(logs)
    finally:
        conn.close()



# IMPORTAR EXCEL PARA LOS JEFES
import csv
from io import StringIO
from flask import Response, jsonify, session

@app.route('/api/exportar_auditoria')
def exportar_auditoria():
    # Solo el Jefe (Cargo 5) puede descargar esto
    if session.get('cargo_id') != 5:
        return jsonify({"status": "error", "message": "No autorizado"}), 403

    # Capturamos el filtro de tiempo (si no viene nada, descarga 'todo')
    rango = request.args.get('rango', 'todo')
    
    # Definimos cuántos días restar para el filtro de SQL
    filtros_sql = {
        "dia": 0,
        "semana": 7,
        "quincena": 15,
        "mes": 30
    }

    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Consulta base
        query = """
            SELECT 
                L.Fecha, 
                U.UsuarioID,
                (U.Nombre + ' ' + ISNULL(U.Apellido, '')) as Responsable, 
                L.Accion, 
                L.Detalle
            FROM Logs_Auditoria L
            JOIN Usuarios U ON L.UsuarioID = U.UsuarioID
        """
        
        params = []
        # Aplicamos el filtro de fecha si el rango existe en nuestro diccionario
        if rango in filtros_sql:
            # Filtra desde las 00:00 del día calculado hasta hoy
            query += " WHERE L.Fecha >= DATEADD(day, -?, CAST(GETDATE() AS DATE))"
            params.append(filtros_sql[rango])
        
        query += " ORDER BY L.Fecha DESC"
        
        cursor.execute(query, params)
        
        si = StringIO()
        # Delimitador ';' para que Excel en español separe las columnas automáticamente
        cw = csv.writer(si, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        
        cw.writerow(['Fecha/Hora', 'ID Usu.', 'Responsable', 'Acción', 'Detalle'])
        
        for row in cursor.fetchall():
            cw.writerow([row[0], row[1], row[2], row[3], row[4]])

        # El BOM (\ufeff) asegura que los acentos y la 'ñ' se vean bien
        contenido_final = "\ufeff" + si.getvalue()
        
        return Response(
            contenido_final,
            mimetype="text/csv",
            headers={"Content-disposition": f"attachment; filename=Registro_Tareas_{rango}.csv"}
        )
    except Exception as e:
        print(f"Error exportando: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


#DEPARTAMENTOS
@app.route('/api/departamentos')
def get_departamentos():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Usamos los nombres reales que vimos en tu captura de SQL
        cursor.execute("SELECT DeptoID, NombreDepto FROM departamentos")
        columnas = [column[0] for column in cursor.description]
        resultado = [dict(zip(columnas, row)) for row in cursor.fetchall()]
        return jsonify(resultado)
    except Exception as e:
        print(f"Error en departamentos: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()




# FOTO DE PERFIL: 

import os
from werkzeug.utils import secure_filename

# Configuración de carpetas
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg',}

@app.route('/subir_foto', methods=['POST'])
def subir_foto():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    if 'foto' not in request.files:
        return "No se seleccionó ninguna imagen", 400
    
    file = request.files['foto']
    if file.filename == '':
        return "Nombre de archivo vacío", 400

    if file:
        # 1. Asegurar nombre de archivo y guardar físicamente
        filename = secure_filename(f"user_{session['usuario_id']}_{file.filename}")
        file.save(os.path.join(UPLOAD_FOLDER, filename))

        # 2. Actualizar la base de datos SQL
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE Usuarios 
                SET FotoPerfil = ? 
                WHERE UsuarioID = ?
            """, (filename, session['usuario_id']))
            conn.commit()
        except Exception as e:
            print(f"Error al guardar en DB: {e}")
        finally:
            conn.close()

        return redirect(url_for('perfil')) # Redirige de vuelta al perfil




# RESERVAS
# --------

from flask import jsonify, request, session

# 1. RUTA PARA OBTENER LAS SALAS (Con toda la información técnica)
@app.route('/api/get_salas')
def get_salas():
    conn = get_connection()
    cursor = conn.cursor()
    # Modificamos el SELECT para traer Capacidad, Ubicacion, Dimensiones y Equipamiento
    query = """
        SELECT ID_Sala, NombreSala, Estado_Sala, 
               Capacidad, Ubicacion, Dimensiones, Equipamiento 
        FROM Salas
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()

    # Mapeamos los datos para que el Frontend los reciba completos
    salas = [{
        "id": r[0], 
        "nombre": r[1], 
        "estado": r[2],
        "Capacidad": r[3],
        "Ubicacion": r[4] or "No especificada",
        "Dimensiones": r[5] or "N/A",
        "Equipamiento": r[6] or "Básico"
    } for r in rows]

    return jsonify(salas)



# RESERVAS GET RESERVAS PARA LA RESERVAS
###########################################
@app.route('/api/get_reservas')
def get_reservas():
    conn = get_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT r.ID_Reserva, r.Titulo_Evento, r.Hora_Inicio, r.Hora_Fin, 
               s.ColorHex, u.Nombre, u.Apellido, r.Descripcion, r.Materiales_Requeridos,
               r.Estado_Reserva, s.NombreSala, s.ID_Sala, r.tipo_reunion, r.plataforma, 
               r.link_reunion, r.check_in, r.req_cafe, r.req_agua, r.req_it,
               r.ID_Organizador  -- <--- AGREGAMOS ESTO (Es el r[19])
        FROM Reservas r
        LEFT JOIN Salas s ON r.ID_Sala = s.ID_Sala
        JOIN Usuarios u ON r.ID_Organizador = u.UsuarioID
        WHERE r.Estado_Reserva < 2
    """
    cursor.execute(query)
    rows = cursor.fetchall()

    eventos = []
    for r in rows:
        id_reserva = r[0] 
        estado = r[9] if r[9] is not None else 0 
        tipo_reunion = r[12] if r[12] else 'Presencial'
        check_in_realizado = r[15]
        
        # --- INVITADOS EXTERNOS (Lo mantenemos igual) ---
        cursor.execute("SELECT NombreInvitado, EmpresaInvitado, CedulaInvitado FROM Invitados WHERE ID_Reserva = ?", (id_reserva,))
        filas_invitados = cursor.fetchall()
        lista_invitados = [
            {'nombre': i[0], 'empresa': i[1], 'cedula': i[2]} 
            for i in filas_invitados
        ]

       # --- CORREGIDO: INVITADOS INTERNOS (UNICASAs) ---
        cursor.execute("""
            SELECT u.Nombre + ' ' + u.Apellido, u.Cedula 
            FROM Invitados_Internos ii
            JOIN Usuarios u ON ii.UsuarioID = u.UsuarioID
            WHERE ii.ID_Reserva = ?
        """, (id_reserva,))
        
        # Ahora guardamos un objeto con nombre y cedula para cada uno
        lista_internos = [
            {'nombre': row[0], 'cedula': row[1] if row[1] else "N/A"} 
            for row in cursor.fetchall()
        ]
        # ---------------------------------------------

        color_base = r[4] if r[4] else "#02ace4" 
        
        # --- NUEVO: LÓGICA DE COLORES E ICONOS PARA 'MIXTA' ---
        if tipo_reunion == 'Virtual':
            color_final = "#0bb8e8" # Celeste
        elif tipo_reunion == 'Mixta':
            color_final = "#6f42c1" # Morado (Sugerido para distinguir Mixta)
        else:
            color_final = color_base

        if estado == 1:
            color_final = '#808080'
            
        titulo_final = r[1]
        
        # Añadimos iconos según modalidad
        if estado == 1:
            titulo_final = f"✔ {titulo_final}"
        elif tipo_reunion == 'Mixta':
            titulo_final = f"🏢🌐 {titulo_final}" 
        elif tipo_reunion == 'Virtual':
            titulo_final = f"💻 {titulo_final}"
        elif tipo_reunion == 'Presencial' and check_in_realizado == 1:
            titulo_final = f"📍 REUNIÓN COMENZADA: {titulo_final}"
        # -------------------------------------------------------

        nombre_completo = f"{r[5]} {r[6]}"

        eventos.append({
            'id': id_reserva,
            'title': titulo_final,
            'start': r[2].isoformat(),
            'end': r[3].isoformat(),
            'backgroundColor': color_final,
            'borderColor': color_final,
            'extendedProps': {
                'organizador': f"{r[5]} {r[6]}",
                'descripcion': r[7],
                'materiales': r[8],
                'estado': r[9] if r[9] is not None else 0,
                'nombre_sala': r[10] if r[10] else '🌐 Reunión Virtual', 
                'id_sala': r[11],
                'tipo_reunion': r[12] if r[12] else 'Presencial',
                'plataforma': r[13],
                'link_reunion': r[14],
                'check_in': r[15],
                'invitados': lista_invitados,
                'invitados_internos': lista_internos,
                'req_cafe': r[16],
                'req_agua': r[17],
                'req_it': r[18],
                'ID_Organizador': r[19], 
            }
        })
    
    conn.close() 
    return jsonify(eventos)


# 3. RUTA PARA GUARDAR UNA NUEVA RESERVA (CON INVITADOS)
########################################################
@app.route('/api/guardar_reserva', methods=['POST'])
def guardar_reserva():
    datos = request.json
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # 1. PREPARACIÓN DE DATOS Y VALIDACIÓN DE CHOQUE CON BUFFER
        tipo_reunion = datos.get('tipo_reunion', 'Presencial')
        id_sala = datos.get('id_sala') if datos.get('id_sala') else None

        if (tipo_reunion == 'Presencial' or tipo_reunion == 'Mixta') and id_sala:
            query_verificar = """
                SELECT COUNT(*) 
                FROM Reservas 
                WHERE ID_Sala = ? 
                  AND Estado_Reserva < 2
                  AND (
                      ? < DATEADD(hour, 1, Hora_Fin) 
                      AND ? > DATEADD(hour, -1, Hora_Inicio)
                  )
            """
            cursor.execute(query_verificar, (id_sala, datos['inicio'], datos['fin']))
            existe_choque = cursor.fetchone()[0]

            if existe_choque > 0:
                return jsonify({
                    'status': 'error', 
                    'message': 'Conflicto: La sala física ya está ocupada o requiere tiempo de limpieza.'
                }), 409

        # 2. INSERT DE LA RESERVA (USANDO OUTPUT PARA CAPTURAR EL ID DE FORMA SEGURA)
        query_insert = """
            INSERT INTO Reservas (
                ID_Sala, Titulo_Evento, Hora_Inicio, Hora_Fin, 
                Es_Recurrente, ID_Organizador, Descripcion, 
                Materiales_Requeridos, req_cafe, req_agua, req_it, 
                tipo_reunion, plataforma, link_reunion, check_in
            ) 
            OUTPUT INSERTED.ID_Reserva
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        """
        
        cursor.execute(query_insert, (
            id_sala,
            datos['titulo'], 
            datos['inicio'], 
            datos['fin'], 
            datos['recurrente'],
            datos['id_organizador'],
            datos['descripcion'],
            datos['materiales'],
            datos.get('req_cafe', 0),
            datos.get('req_agua', 0),
            datos.get('req_it', 0),
            tipo_reunion,
            datos.get('plataforma', None),
            datos.get('link_reunion', None)
        ))
        
        fila_id = cursor.fetchone()
        if fila_id:
            id_nueva_reserva = fila_id[0]
        else:
            raise Exception("No se pudo obtener el ID de la nueva reserva.")

        # 3. INSERT DE INVITADOS EXTERNOS
        lista_invitados = datos.get('invitados', [])
        if lista_invitados:
            query_invitados = """
                INSERT INTO Invitados (ID_Reserva, NombreInvitado, EmpresaInvitado, CedulaInvitado) 
                VALUES (?, ?, ?, ?)
            """
            for inv in lista_invitados:
                nombre = inv.get('nombre')
                if nombre and nombre.strip():
                    cursor.execute(query_invitados, (
                        id_nueva_reserva, 
                        nombre, 
                        inv.get('empresa'), 
                        inv.get('cedula')
                    ))

        # --- NUEVO: INSERT DE INVITADOS INTERNOS (TRABAJADORES UNICASA) ---
        invitados_internos = datos.get('invitados_internos', []) # Lista de IDs de usuarios
        for mimbro_id in invitados_internos:
            cursor.execute("""
                INSERT INTO Invitados_Internos (ID_Reserva, UsuarioID) 
                VALUES (?, ?)
            """, (id_nueva_reserva, mimbro_id))
        # -----------------------------------------------------------------

        conn.commit()

       # --- LÓGICA DE NOTIFICACIONES OPTIMIZADA ---
        try:
            # 1. Obtener nombres y correos base
            cursor.execute("SELECT Nombre, Apellido, Email FROM Usuarios WHERE UsuarioID = ?", (datos['id_organizador'],))
            user_row = cursor.fetchone()
            nombre_org = f"{user_row[0]} {user_row[1]}" if user_row else "Organizador"
            correo_org = user_row[2] if user_row else None

            # 2. Identificar el tipo y la sala
            tipo_reunion = datos.get('tipo_reunion', 'Presencial') # <--- CAPTURAMOS EL TIPO
            nombre_sala = "🌐 Reunión Virtual"
            
            if id_sala:
                cursor.execute("SELECT NombreSala FROM Salas WHERE ID_Sala = ?", (id_sala,))
                sala_row = cursor.fetchone()
                if sala_row: nombre_sala = sala_row[0]

            # 3. Armar el diccionario con el nuevo campo 'tipo'

            fecha_inicio = datetime.strptime(datos['inicio'].replace('T', ' '), '%Y-%m-%d %H:%M').strftime('%d/%m/%Y %I:%M %p')
            fecha_fin = datetime.strptime(datos['fin'].replace('T', ' '), '%Y-%m-%d %H:%M').strftime('%d/%m/%Y %I:%M %p')

            datos_mail = {
                'titulo': datos['titulo'],
                'inicio': fecha_inicio,
                'fin': fecha_fin,
                'sala': nombre_sala,
                'organizador': nombre_org,
                'tipo': tipo_reunion,
                'req_cafe': datos.get('req_cafe'),
                'req_agua': datos.get('req_agua'),
                'req_it': datos.get('req_it'),
                'descripcion': datos.get('descripcion', '')
            }

            # 2. NOTIFICACIÓN AL ORGANIZADOR (Individual - Vinotinto)
            if correo_org:
                enviar_correo_notificacion(correo_org, f"Reserva Confirmada: {datos['titulo']}", datos_mail, tipo="creacion")

            # 3. NOTIFICACIÓN MASIVA A INVITADOS (Un solo envío - Azul)
            emails_invitados = []
            for mimbro_id in invitados_internos:
                cursor.execute("SELECT Email FROM Usuarios WHERE UsuarioID = ?", (mimbro_id,))
                row_inv = cursor.fetchone()
                if row_inv and row_inv[0]:
                    emails_invitados.append(row_inv[0])

            if emails_invitados:
                asunto_inv = f"Invitación a reunión: {datos['titulo']}"
                # USAMOS LA MASIVA AQUÍ
                enviar_correo_masivo(correo_org, emails_invitados, asunto_inv, datos_mail, tipo="invitacion")

            # 4. AVISO A ADMINS (Individual o Masivo si son varios)
            admins = ["alejandro.bernal@unicasa.com.ve"]
            for admin_mail in admins:
                if admin_mail != correo_org:
                    enviar_correo_notificacion(admin_mail, f"REPORTE ADMIN: {nombre_org} agendó sala", datos_mail, tipo="creacion")

                # === NUEVO: AVISOS DE CATERING E IT (Agregado sin borrar nada) ===
                
                # Preparamos lista de servicios para el cuerpo del mail
                servicios_pedidos = []
                if datos.get('req_cafe'): servicios_pedidos.append("☕ Café")
                if datos.get('req_agua'): servicios_pedidos.append("💧 Agua")

                # Si pidió café o agua, enviamos a Catering
                if servicios_pedidos:
                    datos_catering = datos_mail.copy()
                    datos_catering['servicios'] = " y ".join(servicios_pedidos)
                    enviar_correo_notificacion(CORREO_CATERING, f"🍴 SOLICITUD CATERING: {nombre_sala}", datos_catering, tipo="catering")

                # Si pidió soporte IT
                if datos.get('req_it'):
                    enviar_correo_notificacion(CORREO_SOPORTE_IT, f"🖥️ SOPORTE IT REQUERIDO: {nombre_sala}", datos_mail, tipo="it")
                
                # ================================================================

        except Exception as e_mail:
            print(f"Error enviando notificaciones: {e_mail}")
        registrar_en_pizarra(f"Nueva reserva: {datos['titulo']} creada por {nombre_org}, revísala en tu calendario para ver más detalles" , "RESERVA CREADA")
        return jsonify({'status': 'success', 'id_reserva': id_nueva_reserva})

    except Exception as e:
        print(f"Error al guardar reserva: {e}")
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        conn.close()




# PARA ELIMINAR RESERVA: 
########################
@app.route('/api/eliminar_reserva/<int:id_reserva>', methods=['DELETE'])
def eliminar_reserva(id_reserva):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # 1. CAPTURAR DATOS DE LA RESERVA (Añadimos los campos de servicios)
        query_info = """
            SELECT r.Titulo_Evento, r.Hora_Inicio, r.Hora_Fin, s.NombreSala, 
                   u.Nombre + ' ' + u.Apellido as Organizador, u.Email,
                   r.req_cafe, r.req_agua, r.req_it
            FROM Reservas r
            LEFT JOIN Salas s ON r.ID_Sala = s.ID_Sala
            JOIN Usuarios u ON r.ID_Organizador = u.UsuarioID
            WHERE r.ID_Reserva = ?
        """
        cursor.execute(query_info, (id_reserva,))
        reserva = cursor.fetchone()
        
        if not reserva:
            return jsonify({'status': 'error', 'message': 'Reserva no encontrada'}), 404

        # Preparamos los datos para el correo
        datos_mail = {
            'titulo': reserva[0],
            'inicio': reserva[1].strftime('%d/%m/%Y %I:%M %p') if reserva[1] else "N/A",
            'fin': reserva[2].strftime('%d/%m/%Y %I:%M %p') if reserva[2] else "N/A",
            'sala': reserva[3] or "🌐 Reunión Virtual",
            'organizador': reserva[4]
        }
        correo_org = reserva[5]
        
        # Capturamos los requerimientos antes de borrar
        v_req_cafe = reserva[6]
        v_req_agua = reserva[7]
        v_req_it   = reserva[8]

        # 2. CAPTURAR CORREOS DE INVITADOS
        query_invitados = """
            SELECT u.Email 
            FROM Invitados_Internos ii
            JOIN Usuarios u ON ii.UsuarioID = u.UsuarioID
            WHERE ii.ID_Reserva = ?
        """
        cursor.execute(query_invitados, (id_reserva,))
        lista_invitados = [row[0] for row in cursor.fetchall() if row[0]]

        # 3. BORRAR DE LAS TABLAS
        registrar_en_pizarra(f"Se eliminó la reserva {reserva[0]}, creada por {reserva[4]} del calendario", "RESERVA ELIMINADA")
        cursor.execute("DELETE FROM Invitados_Internos WHERE ID_Reserva = ?", (id_reserva,))
        cursor.execute("DELETE FROM Reservas WHERE ID_Reserva = ?", (id_reserva,))
        conn.commit()

        # 4. NOTIFICACIONES
        asunto_canc = f"❌ CANCELADA: {datos_mail['titulo']}"
        
        # Notificar a invitados y organizador
        enviar_correo_masivo(correo_org, lista_invitados, asunto_canc, datos_mail, tipo="cancelacion")
        
        # Notificar a Admin
        admins = ["alejandro.bernal@unicasa.com.ve"]
        for admin_mail in admins:
            if admin_mail != correo_org:
                enviar_correo_notificacion(admin_mail, f"REPORTE ADMIN: Sala Liberada - {datos_mail['titulo']}", datos_mail, tipo="cancelacion")

        # === NUEVO: AVISO DE CANCELACIÓN A CATERING E IT ===
        
        # Lógica para Catering
        if v_req_cafe or v_req_agua:
            asunto_cat_canc = f"❌ CANCELACIÓN DE SERVICIO: {datos_mail['sala']}"
            # Usamos tipo 'cancelacion' para que el banner sea Vinotinto/Rojo
            enviar_correo_notificacion(CORREO_CATERING, asunto_cat_canc, datos_mail, tipo="cancelacion")

        # Lógica para IT
        if v_req_it:
            asunto_it_canc = f"❌ CANCELACIÓN DE SOPORTE: {datos_mail['sala']}"
            enviar_correo_notificacion(CORREO_SOPORTE_IT, asunto_it_canc, datos_mail, tipo="cancelacion")
        
        # ==================================================

        return jsonify({'status': 'success', 'message': 'Reserva eliminada y todos notificados'})

    except Exception as e:
        print(f"Error al eliminar: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        conn.close()


# RUTA PARA SOLICITAR QUE SE COMPLETO UNA RESERVA Y LUEGO UN ADMIN/JEFE LA ARCHIVE SI ES CORRECTO: 
# ######
@app.route('/api/completar_reserva/<int:id_reserva>', methods=['POST'])
def completar_reserva(id_reserva):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # 1. CAPTURAR DATOS ANTES DE MARCAR COMO COMPLETADA
        query_info = """
            SELECT r.Titulo_Evento, r.Hora_Inicio, r.Hora_Fin, s.NombreSala, 
                   u.Nombre + ' ' + u.Apellido as Organizador, u.Email
            FROM Reservas r
            LEFT JOIN Salas s ON r.ID_Sala = s.ID_Sala
            JOIN Usuarios u ON r.ID_Organizador = u.UsuarioID
            WHERE r.ID_Reserva = ?
        """
        cursor.execute(query_info, (id_reserva,))
        reserva = cursor.fetchone()
        
        if not reserva:
            return jsonify({'status': 'error', 'message': 'Reserva no encontrada'}), 404

        # Preparamos los datos para el correo elegante
        datos_mail = {
            'titulo': reserva[0],
            'inicio': reserva[1].strftime('%I:%M %p') if reserva[1] else "N/A",
            'fin': datetime.now().strftime('%I:%M %p'), # Marcamos la hora real de cierre
            'sala': reserva[3] or "🌐 Reunión Virtual",
            'organizador': reserva[4]
        }
        correo_org = reserva[5]

        # 2. ACTUALIZAR ESTADO (Tu lógica original)
        cursor.execute("UPDATE Reservas SET Estado_Reserva = 1 WHERE ID_Reserva = ?", (id_reserva,))
        conn.commit()

        # 3. ENVIAR NOTIFICACIONES (Color Verde)
        asunto_comp = f"FINALIZADA: {datos_mail['titulo']}"
        registrar_en_pizarra(
            f"Se ha completado la reserva {datos_mail['titulo']} organizada por {datos_mail['organizador']}. La ha sido sala liberada.", 
            "RESERVA COMPLETADA"
        )
        
        # Notificación al Organizador
        enviar_correo_notificacion(correo_org, asunto_comp, datos_mail, tipo="completada")
        
        # Notificación al Administrador (Alejandro Bernal)
        admin_mail = "alejandro.bernal@unicasa.com.ve"
        if admin_mail != correo_org:
            asunto_admin = f"REPORTE ADMIN: Sala Liberada - {datos_mail['sala']}"
            enviar_correo_notificacion(admin_mail, asunto_admin, datos_mail, tipo="completada")

        return jsonify({'status': 'success', 'message': 'Reunión completada y notificada'})
        
    except Exception as e:
        print(f"Error al completar reserva: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        conn.close()
        

# RUTA PARA QUE EL ADMIN APRUEBE LA RESERVA
##############
@app.route('/api/aprobar_reserva/<int:id_reserva>', methods=['POST'])
def aprobar_reserva(id_reserva):
    # 1. BLOQUE DE SEGURIDAD: Solo si el bit EsAdmin es 1 en SQL
    if not session.get('es_admin'):
        return jsonify({'status': 'error', 'message': 'Acceso denegado: Se requiere perfil administrador.'}), 403

    # Capturamos quién está aprobando (usamos 'nombre' porque así lo definiste en tu login)
    admin_nombre = session.get('nombre', 'Administrador')
    
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # 1. Obtener datos antes de archivar
        cursor.execute("SELECT Titulo_Evento, ID_Organizador FROM Reservas WHERE ID_Reserva = ?", (id_reserva,))
        reserva = cursor.fetchone()
        
        if reserva:
            titulo, usuario_id = reserva
            
            # 2. Marcar como Archivada (Estado 2) en SQL [cite: 2026-02-09]
            cursor.execute("UPDATE Reservas SET Estado_Reserva = 2 WHERE ID_Reserva = ?", (id_reserva,))
            
            # 3. INSERT EN LOGS_AUDITORIA para el historial interno
            query_log = """
                INSERT INTO Logs_Auditoria (UsuarioID, Accion, Detalle)
                VALUES (?, ?, ?)
            """
            cursor.execute(query_log, (session['usuario_id'], 'RESERVA_APROBADA', f'Se aprobó y archivó la reunión: {titulo}'))
            
            # 4. NOTIFICACIÓN PARA TODOS LOS ADMINES EN LA PIZARRA
            mensaje_pizarra = f"La reserva '{titulo}' fue revisada, aprobada y archivada por el {admin_nombre}."
            registrar_en_pizarra(mensaje_pizarra, "RESERVA APROBADA")
            
            conn.commit()
            return jsonify({'status': 'success'})
        
        return jsonify({'status': 'error', 'message': 'No se encontró la reserva'}), 404

    except Exception as e:
        print(f"Error en aprobación: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        conn.close()

############# ACTUALIZAR LAS RESERVAS PARA CUANDO SE EDITE ##############
########################################################################
@app.route('/api/update_reserva/<int:id_reserva>', methods=['POST'])
def update_reserva(id_reserva):
    datos = request.json
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # === NUEVO: CAPTURAR DATOS ACTUALES (ANTES DE EDITAR) ===
        cursor.execute("""
            SELECT r.Titulo_Evento, r.Hora_Inicio, r.Hora_Fin, s.NombreSala 
            FROM Reservas r
            LEFT JOIN Salas s ON r.ID_Sala = s.ID_Sala
            WHERE r.ID_Reserva = ?
        """, (id_reserva,))
        v = cursor.fetchone()
        
        datos_viejos = {
            'titulo': v[0] if v else "N/A",
            'inicio': v[1].strftime('%d/%m/%Y %I:%M %p') if v and v[1] else "N/A",
            'fin': v[2].strftime('%d/%m/%Y %I:%M %p') if v and v[2] else "N/A",
            'sala': v[3] or "🌐 Virtual"
        }

        # 1. VALIDACIÓN DE CHOQUE (Tu lógica original)
        query_verificar = """
            SELECT COUNT(*) FROM Reservas 
            WHERE ID_Sala = ? 
              AND ID_Reserva <> ?
              AND Estado_Reserva < 2
              AND (? < Hora_Fin AND ? > Hora_Inicio)
        """
        cursor.execute(query_verificar, (datos['id_sala'], id_reserva, datos['inicio'], datos['fin']))
        if cursor.fetchone()[0] > 0:
            return jsonify({'status': 'error', 'message': 'El nuevo horario choca con otra reserva.'}), 409

        # 2. ACTUALIZACIÓN (Mantenemos tus cambios de ID_Organizador)
        query_update = """
            UPDATE Reservas 
            SET ID_Sala = ?, 
                ID_Organizador = ?, 
                Titulo_Evento = ?, 
                Hora_Inicio = ?, 
                Hora_Fin = ?, 
                Descripcion = ?, 
                Materiales_Requeridos = ?, 
                Es_Recurrente = ?,
                tipo_reunion = ?,
                plataforma = ?,
                link_reunion = ?,
                req_cafe = ?,
                req_agua = ?,
                req_it = ?
            WHERE ID_Reserva = ?
        """
        cursor.execute(query_update, (
            datos['id_sala'], 
            datos['id_organizador'], 
            datos['titulo'], 
            datos['inicio'], 
            datos['fin'],
            datos['descripcion'], 
            datos['materiales'], 
            datos['recurrente'],
            datos.get('tipo_reunion', 'Presencial'),
            datos.get('plataforma', ''),
            datos.get('link_reunion', ''),
            1 if datos.get('req_cafe') else 0,
            1 if datos.get('req_agua') else 0,
            1 if datos.get('req_it') else 0,
            id_reserva
        ))
        
        cursor.execute("DELETE FROM Invitados_Internos WHERE ID_Reserva = ?", (id_reserva,))
        
        # Obtenemos la lista de IDs del objeto JSON
        invitados_nuevos = datos.get('invitados_internos', [])
        for inv_id in invitados_nuevos:
            cursor.execute("""
                INSERT INTO Invitados_Internos (ID_Reserva, UsuarioID) 
                VALUES (?, ?)
            """, (id_reserva, inv_id))

        conn.commit()

        # --- INICIO LÓGICA DE NOTIFICACIÓN DE EDICIÓN ---
        try:
            # 1. Obtener nombres, sala y SERVICIOS (Agregamos req_cafe, req_agua, req_it)
            cursor.execute("""
                SELECT u.Nombre + ' ' + u.Apellido, s.NombreSala, u.Email,
                       r.req_cafe, r.req_agua, r.req_it, r.tipo_reunion
                FROM Reservas r
                JOIN Usuarios u ON r.ID_Organizador = u.UsuarioID
                LEFT JOIN Salas s ON r.ID_Sala = s.ID_Sala
                WHERE r.ID_Reserva = ?
            """, (id_reserva,))
            info = cursor.fetchone()
            
            nombre_org = info[0] if info else "Organizador"
            nombre_sala = info[1] or "🌐 Reunión Virtual"
            correo_org = info[2] if info else None
            
            # Capturamos los requerimientos de la DB
            v_req_cafe = info[3]
            v_req_agua = info[4]
            v_req_it   = info[5]
            tipo_reunion = info[6]
            
            
            
            fecha_inicio = datetime.strptime(datos['inicio'].replace('T', ' '), '%Y-%m-%d %H:%M').strftime('%d/%m/%Y %I:%M %p')
            fecha_fin = datetime.strptime(datos['fin'].replace('T', ' '), '%Y-%m-%d %H:%M').strftime('%d/%m/%Y %I:%M %p')

            datos_mail = {
                'titulo': datos['titulo'],
                'inicio': fecha_inicio, 
                'fin': fecha_fin,
                'sala': nombre_sala,
                'organizador': nombre_org,
                'tipo': tipo_reunion,
                'viejos': datos_viejos
            }
            # 2. Obtener lista de Invitados Internos
            cursor.execute("""
                SELECT u.Email 
                FROM Invitados_Internos ii
                JOIN Usuarios u ON ii.UsuarioID = u.UsuarioID
                WHERE ii.ID_Reserva = ?
            """, (id_reserva,))
            lista_invitados = [row[0] for row in cursor.fetchall() if row[0]]

            # 3. Enviar Notificación Masiva (Color NARANJA)
            asunto_mod = f"⚠️ RESERVA MODIFICADA: {datos['titulo']}"
            if correo_org:
                enviar_correo_masivo(correo_org, lista_invitados, asunto_mod, datos_mail, tipo="pospuesta")

            # 4. Notificar al Administrador
            admin_mail = "alejandro.bernal@unicasa.com.ve"
            if admin_mail != correo_org:
                enviar_correo_notificacion(admin_mail, f"REPORTE ADMIN: Reserva Modificada - {datos['titulo']}", datos_mail, tipo="pospuesta")

            # === NUEVO: AVISO A CATERING E IT POR REPROGRAMACIÓN ===
            
            # Lógica para Catering
            servicios_pedidos = []
            if v_req_cafe: servicios_pedidos.append("☕ Café")
            if v_req_agua: servicios_pedidos.append("💧 Agua")

            if servicios_pedidos:
                datos_cat = datos_mail.copy()
                datos_cat['servicios'] = " y ".join(servicios_pedidos)
                asunto_cat = f"⏳ RESERVA EDITADA - CATERING: {datos['titulo']}"
                # Enviamos con tipo 'catering' para que use el color dorado y muestre el pedido
                enviar_correo_notificacion(CORREO_CATERING, asunto_cat, datos_cat, tipo="catering")

            # Lógica para IT
            if v_req_it:
                asunto_it = f"⏳ RESERVA EDITADA - SOPORTE IT: {datos['titulo']}"
                enviar_correo_notificacion(CORREO_SOPORTE_IT, asunto_it, datos_mail, tipo="it")

            # ======================================================
        
        except Exception as e_mail:
            print(f"Error enviando notificación de update: {e_mail}")
        registrar_en_pizarra(f"Se editó la reunión: {datos['titulo']} de el organizador {nombre_org}, revisa en tu calendario los nuevos detalles.", "RESERVA EDITADA")
        return jsonify({'status': 'success'})

    except Exception as e:
        print(f"Error en update: {str(e)}") 
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        conn.close()


#################################################
######### CHECK IN CONFIRMAR ASISTENCIA #########
#################################################
@app.route('/api/checkin/<int:id_reserva>', methods=['POST'])
def checkin_reserva(id_reserva):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE Reservas SET check_in = 1 WHERE ID_Reserva = ?", (id_reserva,))
        conn.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        conn.close()


def generar_ics(datos):
    # Formateamos las fechas al estilo que entiende el calendario (YYYYMMDDTHHMMSS)
    # Quitamos guiones, puntos y espacios
    inicio_ics = datos['inicio'].replace('-', '').replace(':', '').replace(' ', 'T').split('T')
    # Ajuste simple de formato
    formato_inicio = f"{inicio_ics[0]}T{inicio_ics[1]}00"
    
    fin_ics = datos['fin'].replace('-', '').replace(':', '').replace(' ', 'T').split('T')
    formato_fin = f"{fin_ics[0]}T{fin_ics[1]}00"

    ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Unicasa//Sistema de Reservas//ES
BEGIN:VEVENT
SUMMARY:{datos['titulo']}
DTSTART:{formato_inicio}
DTEND:{formato_fin}
LOCATION:{datos['sala']}
DESCRIPTION:Reserva gestionada por {datos['organizador']}.
END:VEVENT
END:VCALENDAR"""
    return ics_content

###### FUNCIÓN PARA EL CORREO INDIVIDUAL O SUAVE ##############
############################################
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage # Importante para el logo
import os
def enviar_correo_notificacion(destinatario, asunto, datos_reserva, tipo="creacion"):
    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    sender_email = "fabianbernal044@gmail.com"
    sender_password = "qhro yjcl cpcz tqqv"

    # --- CONFIGURACIÓN DINÁMICA SEGÚN EL TIPO ---
    config = {
        "creacion": {"titulo": "❗ NUEVA RESERVA ❗", "color": "#9c1c3f", "mensaje": "ha registrado exitosamente"},
        "invitacion": {"titulo": "↹ INVITACIÓN A REUNIÓN ↹", "color": "#9c1c3f", "mensaje": "te ha invitado a participar en"},
        "cancelacion": {"titulo": "❌ RESERVA CANCELADA ❌", "color": "#9c1c3f", "mensaje": "ha cancelado la siguiente"},
        "pospuesta": {"titulo": "⚠️ RESERVA MODIFICADA ⚠️", "color": "#9c1c3f", "mensaje": "ha modificado la reserva, verifica los detalles"},
        "completada": {"titulo": "✔️ REUNIÓN COMPLETADA ✔️", "color": "#9c1c3f", "mensaje": "se ha completado la reunión exitosamente"},
        "recordatorio": {"titulo": "✉ PRÓXIMA REUNIÓN ✉", "color": "#9c1c3f", "mensaje": "le recuerda que está por iniciar la reunión de"},
        "catering": {"titulo": "⛾ SOLICITUD DE CATERING ⛾", "color": "#9c1c3f", "mensaje": "ha solicitado servicios para"},
        "it": {"titulo": "🖥️ SOPORTE TÉCNICO IT 🖥️", "color": "#9c1c3f", "mensaje": "requiere apoyo técnico para"}
    }
    
    
    # Si el tipo no existe, usamos creación por defecto
    c = config.get(tipo, config["creacion"])

    seccion_comparativa = ""
    if tipo in ["pospuesta", "catering", "it"] and 'viejos' in datos_reserva:
        v = datos_reserva['viejos']
        seccion_comparativa = f"""
        <div style="margin-top: 20px; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden;">
            <table width="100%" cellpadding="10" style="border-collapse: collapse; font-size: 14px;">
                <tr style="background-color: #f8f9fa; text-align: center;">
                    <th style="border-bottom: 1px solid #eee;">Campo</th>
                    <th style="border-bottom: 1px solid #eee; color: #c0392b;">Antes</th>
                    <th style="border-bottom: 1px solid #eee; color: #27ae60;">Ahora</th>
                </tr>
                <tr>
                    <td style="border-bottom: 1px solid #eee;"><strong>Inicio</strong></td>
                    <td style="border-bottom: 1px solid #eee; color: #7f8c8d;">{v['inicio']}</td>
                    <td style="border-bottom: 1px solid #eee; font-weight: bold;">{datos_reserva['inicio']}</td>
                </tr>
                <tr>
                    <td style="border-bottom: 1px solid #eee;"><strong>Ubicación</strong></td>
                    <td style="border-bottom: 1px solid #eee; color: #7f8c8d;">{v['sala']}</td>
                    <td style="border-bottom: 1px solid #eee; font-weight: bold;">{datos_reserva['sala']}</td>
                </tr>
            </table>
        </div>
        <p style="font-size: 12px; color: #7f8c8d; text-align: center;">* Se resaltan los cambios realizados para su referencia.</p>
        """
    # --- Lógica para mostrar el campo extra de servicios (Café/Agua) ---
    fila_extra = ""
    if tipo == "catering":
        servicios = datos_reserva.get('servicios', 'Café / Agua')
        fila_extra = f"<tr><td><strong>📋 Pedido:</strong></td><td style='color: #d4a017; font-weight: bold;'>{servicios}</td></tr>"
    elif tipo == "it":
        fila_extra = f"<tr><td><strong>🛠️ Requerimiento:</strong></td><td style='color: #117a8b; font-weight: bold;'>Soporte IT</td></tr>"

    try:
        msg = MIMEMultipart('related')
        msg['From'] = f"Sistema de Reservas Unicasa <{sender_email}>"
        msg['To'] = destinatario
        msg['Subject'] = asunto

        # HTML Evolucionado: Usamos las variables dinámicas {c['color']}, {c['titulo']}, etc.
        html = f"""
        <html>
        <body style="margin: 0; padding: 0; background-color: #f4f4f4; font-family: Arial, sans-serif;">
            <table width="100%" border="0" cellspacing="0" cellpadding="0" style="padding: 20px;">
                <tr>
                    <td align="center">
                        <table width="550" border="0" cellspacing="0" cellpadding="0" style="background-color: #ffffff; border-radius: 12px; overflow: hidden; border: 1px solid #e0e0e0;">
                            <tr>
                                <td align="center" style="background-color: {c['color']}; padding: 30px;">
                                    <img src="cid:logo_unicasa" alt="Unicasa" width="160">
                                </td>
                            </tr>

                            <tr>
                                <td style="padding: 40px; color: #1a1a1a;">
                                    <h1 style="color: {c['color']}; font-size: 26px; text-align: center; margin: 0;">{c['titulo']}</h1>
                                    <p style="font-size: 20px; line-height: 1.6; text-align: center;">
                                        El usuario <strong style="color: {c['color']};">{datos_reserva['organizador']}</strong> {c['mensaje']} la reserva:
                                    </p>
                                    
                                    <div style="background-color: #f9f9f9; border-left: 5px solid {c['color']}; padding: 20px; margin: 20px 0;">
                                        <h3 style="margin: 0 0 10px 0;">{datos_reserva['titulo']}</h3>
                                        <table width="100%" style="font-size: 18px;">
                                            <tr><td><strong>📅 Inicio:</strong></td><td>{datos_reserva['inicio']}</td></tr>
                                            <tr><td><strong>🏁 Fin:</strong></td><td>{datos_reserva['fin']}</td></tr>
                                            <tr><td><strong>📍  Sala:</strong></td><td>{datos_reserva['sala']}</td></tr>
                                            <tr><td><strong>🎥 Modalidad:</strong></td><td>{datos_reserva.get('tipo', 'Presencial')}</td></tr>
                                            {fila_extra}
                                        </table>
                                    </div>

                                    {seccion_comparativa}<div align="center" style="margin-top: 25px;">
                                        <a href="http://127.0.0.1:5000/dashboard" style="background-color: {c['color']}; color: white; padding: 12px 25px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">VER CALENDARIO</a>
                                    </div>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(html, 'html'))

        # 2. Adjuntar la imagen (Tu bloque de código mejorado)
        ruta_logo = os.path.join(os.path.dirname(__file__), "static", "img", "logo_unicasa.png")
        
        if os.path.exists(ruta_logo):
            with open(ruta_logo, 'rb') as f:
                img = MIMEImage(f.read())
                img.add_header('Content-ID', '<logo_unicasa>') # Mantén los < >
                img.add_header('Content-Disposition', 'inline', filename="logo_unicasa.png")
                msg.attach(img)
            print("✅ Logo cargado y adjuntado.")
        else:
            # Si sale este mensaje en tu consola, es que el archivo no está en esa carpeta
            print(f"❌ ERROR: No se encontró el logo en: {ruta_logo}")
        
        # --- GENERAR Y ADJUNTAR ARCHIVO .ICS ---
        from email.mime.base import MIMEBase
        from email import encoders

        ics_text = generar_ics(datos_reserva)
        part = MIMEBase('text', 'calendar', method='REQUEST', name='invitacion.ics')
        part.set_payload(ics_text)
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment; filename="invitacion.ics"')
        msg.attach(part)

        # Conexión y envío
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, destinatario, msg.as_string())
        server.quit()
        
        print(f"Correo elegante enviado a {destinatario}")
        return True
    except Exception as e:
        print(f"Error al enviar correo: {e}")
        return False
    

## AHORA notificaciones de forma MASIVAMENTE A VARIOS ####
def enviar_correo_masivo(organizador_mail, lista_bcc, asunto, datos_reserva, tipo="creacion"):
    smtp_server = "smtp.gmail.com"
    smtp_port = 465  # Puerto SSL directo para evitar errores de conexión
    sender_email = "fabianbernal044@gmail.com"
    sender_password = "qhro yjcl cpcz tqqv"

    # Diccionario de configuración para los colores y mensajes
    config = {
        "creacion": {"titulo": "❗ NUEVA RESERVA ❗", "color": "#9c1c3f", "mensaje": "ha registrado exitosamente"},
        "invitacion": {"titulo": "↹ INVITACIÓN A REUNIÓN ↹", "color": "#9c1c3f", "mensaje": "te ha invitado a participar en"},
        "cancelacion": {"titulo": "❌ RESERVA CANCELADA ❌", "color": "#9c1c3f", "mensaje": "ha cancelado la siguiente"},
        "pospuesta": {"titulo": "⚠️ RESERVA MODIFICADA ⚠️", "color": "#9c1c3f", "mensaje": "ha modificado la reserva, verifica los detalles"},
        "completada": {"titulo": "✔️ REUNIÓN COMPLETADA ✔️", "color": "#9c1c3f", "mensaje": "se ha completado la reunión exitosamente"},
        "recordatorio": {"titulo": "✉ PRÓXIMA REUNIÓN ✉", "color": "#9c1c3f", "mensaje": "le recuerda que está por iniciar la reunión de"},
        "catering": {"titulo": "⛾ SOLICITUD DE CATERING ⛾", "color": "#9c1c3f", "mensaje": "ha solicitado servicios para"},
        "it": {"titulo": "🖥️ SOPORTE TÉCNICO IT 🖥️", "color": "#9c1c3f", "mensaje": "requiere apoyo técnico para"}
    }
    
    
    c = config.get(tipo, config["creacion"])

    seccion_comparativa = ""
    if tipo == "pospuesta" and 'viejos' in datos_reserva:
        v = datos_reserva['viejos']
        seccion_comparativa = f"""
        <div style="margin-top: 20px; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden;">
            <table width="100%" cellpadding="10" style="border-collapse: collapse; font-size: 14px;">
                <tr style="background-color: #f8f9fa; text-align: center;">
                    <th style="border-bottom: 1px solid #eee;">Campo</th>
                    <th style="border-bottom: 1px solid #eee; color: #c0392b;">Antes</th>
                    <th style="border-bottom: 1px solid #eee; color: #27ae60;">Ahora</th>
                </tr>
                <tr>
                    <td style="border-bottom: 1px solid #eee;"><strong>Inicio</strong></td>
                    <td style="border-bottom: 1px solid #eee; color: #7f8c8d;">{v['inicio']}</td>
                    <td style="border-bottom: 1px solid #eee; font-weight: bold;">{datos_reserva['inicio']}</td>
                </tr>
                <tr>
                    <td style="border-bottom: 1px solid #eee;"><strong>Ubicación</strong></td>
                    <td style="border-bottom: 1px solid #eee; color: #7f8c8d;">{v['sala']}</td>
                    <td style="border-bottom: 1px solid #eee; font-weight: bold;">{datos_reserva['sala']}</td>
                </tr>
            </table>
        </div>
        <p style="font-size: 12px; color: #7f8c8d; text-align: center;">* Se resaltan los cambios realizados para su referencia.</p>
        """

    fila_extra = ""
    if tipo == "catering":
        servicios = datos_reserva.get('servicios', 'Café / Agua')
        fila_extra = f"<tr><td><strong>📋 Pedido:</strong></td><td style='color: #d4a017; font-weight: bold;'>{servicios}</td></tr>{seccion_comparativa}"
    elif tipo == "it":
        fila_extra = f"<tr><td><strong>🛠️ Requerimiento:</strong></td><td style='color: #117a8b; font-weight: bold;'>Apoyo Audiovisual</td></tr>{seccion_comparativa}"

    try:
        msg = MIMEMultipart('related')
        msg['From'] = f"Sistema de Reservas Unicasa <{sender_email}>"
        msg['To'] = organizador_mail  # El organizador es el destinatario visible
        
        # Agregamos a todos los invitados en BCC (Copia Oculta)
        if lista_bcc and len(lista_bcc) > 0:
            msg['Bcc'] = ", ".join(lista_bcc)
            
        msg['Subject'] = asunto

        html = f"""
        <html>
        <body style="margin: 0; padding: 0; background-color: #f4f4f4; font-family: Arial, sans-serif;">
            <table width="100%" border="0" cellspacing="0" cellpadding="0" style="padding: 20px;">
                <tr>
                    <td align="center">
                        <table width="550" border="0" cellspacing="0" cellpadding="0" style="background-color: #ffffff; border-radius: 12px; overflow: hidden; border: 1px solid #e0e0e0; box-shadow: 0 10px 25px rgba(0,0,0,0.1);">
                            <tr>
                                <td align="center" style="background-color: {c['color']}; padding: 30px;">
                                    <img src="cid:logo_unicasa" alt="Unicasa" width="160">
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 40px; color: #1a1a1a;">
                                    <h1 style="color: {c['color']}; font-size: 26px; text-align: center; margin: 0;">{c['titulo']}</h1>
                                    <p style="font-size: 20px; line-height: 1.6; text-align: center;">
                                        El usuario <strong style="color: {c['color']};">{datos_reserva['organizador']}</strong> {c['mensaje']} la reserva:
                                    </p>
                                    <div style="background-color: #f9f9f9; border-left: 5px solid {c['color']}; padding: 20px; margin: 20px 0;">
                                        <h3 style="margin: 0 0 10px 0;">{datos_reserva['titulo']}</h3>
                                        <table width="100%" style="font-size: 18px;">
                                            <tr><td><strong>📅 Inicio:</strong></td><td>{datos_reserva['inicio']}</td></tr>
                                            <tr><td><strong>🏁 Fin:</strong></td><td>{datos_reserva['fin']}</td></tr>
                                            <tr><td><strong>📍  Sala:</strong></td><td>{datos_reserva['sala']}</td></tr>
                                            <tr><td><strong>🎥 Modalidad:</strong></td><td>{datos_reserva.get('tipo', 'Presencial')}</td></tr>
                                            {fila_extra}
                                        </table>
                                    </div>
                                    
                                    {seccion_comparativa} <div align="center" style="margin-top: 25px;">
                                        <a href="http://127.0.0.1:5000/dashboard" style="background-color: {c['color']}; color: white; padding: 12px 25px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">VER CALENDARIO</a>
                                    </div>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """
        msg.attach(MIMEText(html, 'html'))

        # Adjuntar Logo (Tu código que ya funciona)
        ruta_logo = os.path.join(os.path.dirname(__file__), "static", "img", "logo_unicasa.png")
        if os.path.exists(ruta_logo):
            with open(ruta_logo, 'rb') as f:
                img = MIMEImage(f.read())
                img.add_header('Content-ID', '<logo_unicasa>')
                msg.attach(img)

        # Usamos SMTP_SSL para mayor estabilidad
        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        server.login(sender_email, sender_password)
         # --- GENERAR Y ADJUNTAR ARCHIVO .ICS ---
        from email.mime.base import MIMEBase
        from email import encoders

        ics_text = generar_ics(datos_reserva)
        part = MIMEBase('text', 'calendar', method='REQUEST', name='invitacion.ics')
        part.set_payload(ics_text)
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment; filename="invitacion.ics"')
        msg.attach(part)
        # Lista total para el servidor SMTP (To + Bcc)
        destinatarios_reales = [organizador_mail] + (lista_bcc if lista_bcc else [])
        server.sendmail(sender_email, destinatarios_reales, msg.as_string())
        server.quit()
        
        print(f"✅ Envío masivo exitoso a {len(destinatarios_reales)} personas.")
        return True
    except Exception as e:
        print(f"❌ Error en envío masivo: {e}")
        return False




############## BUSCAR USUARIOS PARA INVITARLOS (USUARIOS UNICASA) ########
##########################################################################
@app.route('/api/buscar_usuarios')
def buscar_usuarios():
    query = request.args.get('q', '')
    conn = get_connection()
    cursor = conn.cursor()
    # Buscamos por nombre o apellido
    cursor.execute("""
        SELECT UsuarioID, Nombre, Apellido 
        FROM Usuarios 
        WHERE Nombre LIKE ? OR Apellido LIKE ?
    """, (f'%{query}%', f'%{query}%'))
    
    usuarios = [{'UsuarioID': row[0], 'Nombre': row[1], 'Apellido': row[2]} for row in cursor.fetchall()]
    conn.close()
    return jsonify(usuarios)


##### DETALLE SALA ##############
#################################
@app.route('/api/get_sala_detalle/<int:id_sala>')
def get_sala_detalle(id_sala):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Buscamos los datos técnicos que quieres mostrar
        # Verifica que los nombres de columna (Ubicacion, Capacidad, Equipamiento) 
        # sean exactamente iguales a los de tu tabla 'Salas'
        query = "SELECT Ubicacion, Capacidad, Equipamiento FROM Salas WHERE ID_Sala = ?"
        cursor.execute(query, (id_sala,))
        row = cursor.fetchone()
        
        if row:
            return jsonify({
                "ubicacion": row[0],
                "capacidad": row[1],
                "equipamiento": row[2]
            }), 200
        else:
            return jsonify({"error": "Sala no encontrada"}), 404
            
    except Exception as e:
        print(f"Error al obtener detalle de sala: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

## HGORA ##
from datetime import datetime
import pytz

def obtener_hora_caracas():
    # Definimos la zona horaria de Venezuela
    tz_caracas = pytz.timezone('America/Caracas')
    # Obtenemos la hora actual en esa zona
    return datetime.now(tz_caracas)

# Ejemplo de uso al guardar en SQL:
# nueva_reserva.fecha_creacion = obtener_hora_caracas()

import pytz
from datetime import datetime

# Definimos Caracas una sola vez para todo el sistema
TZ_CARACAS = pytz.timezone('America/Caracas')


### INDICADORES ###
###################
from datetime import date

@app.route('/api/indicadores_rapidos')
def indicadores_rapidos():
    uid = session.get('usuario_id')
    hoy = date.today()
    
    if not uid:
        return jsonify({"tareas": 0, "reservas": 0, "notificaciones": 0})
    
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # 1. TAREAS/EVENTOS
        cursor.execute("""
            SELECT COUNT(DISTINCT E.EventoID) 
            FROM dbo.Eventos E
            LEFT JOIN dbo.Eventos_Invitados EI ON E.EventoID = EI.EventoID
            WHERE (E.CreadoPor = ? OR EI.UsuarioID = ?)
            AND E.archivado = 0 AND E.completado = 0
        """, (uid, uid))
        t = cursor.fetchone()[0]
        
        # 2. RESERVAS: DIAGNÓSTICO
        # Primero, vamos a imprimir en la consola qué hay en la base de datos para hoy
        cursor.execute("SELECT ID_Reserva, Hora_Inicio, Estado_Reserva FROM dbo.Reservas WHERE CAST(Hora_Inicio AS DATE) = ?", (hoy,))
        debug_res = cursor.fetchall()
        print(f">>> BUSCANDO PARA FECHA: {hoy}")
        print(f">>> RESERVAS ENCONTRADAS EN BD: {debug_res}")

        # Consulta real (Súper flexible para que salga algo)
        cursor.execute("""
            SELECT COUNT(DISTINCT R.ID_Reserva) 
            FROM dbo.Reservas R
            LEFT JOIN dbo.Invitados_Internos II ON R.ID_Reserva = II.ID_Reserva
            WHERE (R.ID_Organizador = ? OR II.UsuarioID = ?)
            AND CAST(R.Hora_Inicio AS DATE) = ?
        """, (uid, uid, hoy))
        r = cursor.fetchone()[0]
        
        # 3. AVISOS
        cursor.execute("SELECT COUNT(*) FROM notificaciones WHERE UsuarioID = ? AND Leido = 0", (uid,))
        n = cursor.fetchone()[0]
        
        print(f">>> RESULTADO FINAL -> Tareas: {t}, Reservas: {r}, Avisos: {n}")
        
        return jsonify({"tareas": t, "reservas": r, "notificaciones": n})
    except Exception as e:
        print(f"!!! ERROR CRÍTICO: {e}")
        return jsonify({"tareas": 0, "reservas": 0, "notificaciones": 0})
    finally:
        conn.close()






# CERRAR SESIÓN
@app.route('/logout')
def logout():
    session.clear() # Limpia la sesión del usuario de Unicasa
    return redirect(url_for('index')) # Lo manda de vuelta al Login
    

# ENCENDER EL SERVIDOR (ESTO ES LO QUE HACE QUE CARGUE) ---
if __name__ == '__main__':
    # TRABAJO 1: Recordatorios (cada 5 min)
    scheduler.add_job(id='JobRecordatorios', func=verificar_recordatorios, trigger='interval', minutes=5)
    
    # TRABAJO 2: Cierre Automático (cada 1 min)
    scheduler.add_job(id='JobVigilante', func=cerrar_reuniones_vencidas, trigger='interval', seconds=2)
    
    scheduler.init_app(app)
    scheduler.start()
    
    app.run(debug=True, port=5000)
