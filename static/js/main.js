if (Notification.permission !== "granted") {
    Notification.requestPermission();
}

let tareasData = []; // Esta será nuestra "maleta" global
// --- VARIABLES GLOBALES ---
let calendar;
let infoSeleccionada = null;
let cachePersonal = null;

document.addEventListener('DOMContentLoaded', function() {
    const calendarEl = document.getElementById('calendar');

   if (calendarEl) {
        calendar = new FullCalendar.Calendar(calendarEl, {
            initialView: 'timeGridWeek', 
            locale: 'es',
            selectable: true,
            editable: false,
            allDaySlot: false,
            dayMaxEvents: 3, // Limita a 3 eventos por día
            moreLinkContent: function(args) {
        return '+ Ver más'; // Personaliza el texto del botón
    },
            timeZone: 'local', // Fuerza al calendario a usar la hora de Venezuela
            nowIndicator: true,          // Muestra la línea del tiempo actual
            now: new Date(),             // Sincroniza con la hora exacta del navegador 
            eventDisplay: 'block',
            scrollTime: new Date().getHours() + ':00:00',
            height: 'auto',          
            allDayText: 'HORAS',
            eventStartEditable: false, 
            eventDurationEditable: false,
            slotDuration: '00:30:00',
            slotLabelInterval: '00:30:00',      
            snapDuration: '00:30:00',
            slotLabelFormat: {
            hour: 'numeric',
            minute: '2-digit',
            omitZeroMinute: false,
            meridiem: 'short', // Esto pone el AM/PM
            hour12: true       // Forzamos formato de 12 horas
},
            // --- INSERCIÓN AQUÍ: PERSONALIZACIÓN DE LAS ETIQUETAS DE HORA ---
        slotLabelContent: function(arg) {
            let hour = arg.date.getHours();
            let minute = arg.date.getMinutes();
            
            // Si es la media hora (:30)
            if (minute === 30) {
                return { 
                    html: `<div style="font-size: 1.1em; color: #424242; font-weight: normal; margin-top: -5px;">${arg.text}</div>` 
                };
            }
            
            // Si es la hora en punto (:00)
            return { 
                html: `<div style="font-weight: bold; color: #6b0f1a; font-size: 1.3em;">${arg.text}</div>` 
            };
        },
        // ---------------------------------------------------------------
            eventTimeFormat: {
            hour: 'numeric',
            minute: '2-digit',
            meridiem: 'short',
            hour12: true
    },      
            forceEventDuration: true,      
            displayEventEnd: true,
            headerToolbar: {
                left: 'prev,next today',
                center: 'title',
                right: 'dayGridMonth,timeGridWeek,timeGridDay'
            },
            // ESTO SE ACTIVA AL CARGAR LOS EVENTOS DEL SQL [cite: 2026-02-09]
    eventsSet: function() {
        actualizarProximaReunion();
    },
            
            // 1. EVENTO AL SELECCIONAR RANGO (Abrir para crear nueva)
            select: function(info) {
                infoSeleccionada = info;
                abrirModalReserva();
                
                // Autocompletar fechas en el modal
                if(document.getElementById('res_inicio')) {
                    const inicioStr = info.startStr.slice(0, 16);
                    const finStr = info.endStr.slice(0, 16);
                    document.getElementById('res_inicio').value = inicioStr;
                    document.getElementById('res_fin').value = finStr;
                }
            },

            // ESTO ES CLAVE:
    eventMouseEnter: function(info) {
        info.el.style.cursor = 'pointer'; // Para que el usuario sepa que es clickable
    },

    eventClick: function(info) {
        // Bloqueo total para que no se active el "select" del fondo
        info.jsEvent.preventDefault();
        info.jsEvent.stopPropagation();
        
        console.log("¡POR FIN TOCASTE EL EVENTO!"); // Revisa la consola F12 para ver si sale
        mostrarDetalleReserva(info.event);
    },
    eventDidMount: function(info) {
        // NUEVO: Prioridad máxima al estado finalizado (Gris)
    if (info.event.extendedProps.estado === 1) {
        info.el.style.backgroundColor = '#6c757d'; 
        info.el.style.borderColor = '#242424';
        info.el.style.boxShadow = "none"; // Quitamos cualquier brillo si ya terminó
        return; // Detenemos aquí para que no ejecute lo de abajo
    }
    const ahora = new Date();
    const inicioReserva = info.event.start;
    const diferencia = inicioReserva - ahora;

    // 2. Si la reunión es en las próximas 2 horas (y no ha pasado aún)
    if (diferencia > 0 && diferencia < 7200000) {
        // Aplicamos un estilo más fuerte para que resalte en la cuadrícula (semana/día)
        info.el.style.boxShadow = "0 0 15px 5px rgba(255, 193, 7, 0.6)"; 
        info.el.style.border = "2px solid #ffc107";
        info.el.style.zIndex = "100"; // Lo ponemos por encima de la franja gris
        
        // Opcional: una animación de pulso sutil para llamar la atención
        info.el.classList.add('evento-proximo-pulso');
    }
    
    // 3. Si la reunión ya está ocurriendo (ahora mismo)
    if (ahora >= inicioReserva && ahora <= info.event.end) {
        info.el.style.boxShadow = "0 0 15px 5px rgba(40, 167, 69, 0.5)"; // Brillo verde
        info.el.style.border = "2px solid #28a745";
    }
},

            events: '/api/get_reservas' 
        });
        
        calendar.render();
    }

    const btnManual = document.getElementById('btnCrearGeneral');
    if (btnManual) {
        btnManual.onclick = function() {
            infoSeleccionada = null;
            abrirSelector();
        };
    }

    // Vincular el envío del formulario correctamente
    const form = document.getElementById('formEvento');
    if (form) {
        form.onsubmit = guardarPlanificacionSQL;
    }
});

// --- FUNCIONES DE INTERFAZ ---

function abrirSelector() {
    const modal = document.getElementById('modalSelector');
    if (modal) modal.style.display = 'flex';
}

function cerrarSelector() {
    const modal = document.getElementById('modalSelector');
    if (modal) modal.style.display = 'none';
}

function cerrarModal() {
    const modales = ['modalReserva', 'modalEvento', 'modalDetalleReserva'];
    modales.forEach(m => {
        const el = document.getElementById(m);
        if (el) el.style.display = 'none';
    });

    // --- LÓGICA DE LIMPIEZA PARA EVITAR BUGS ---
    const form = document.getElementById('formReserva');
    const modalReserva = document.getElementById('modalReserva');

    if (form && modalReserva) {
        // 1. Limpiar todos los inputs (título, descripción, etc.)
        form.reset();

        // --- AGREGADO: Limpiar invitados Unicasa ---
        if (typeof limpiarInvitadosUnicasa === 'function') {
            limpiarInvitadosUnicasa();
        }

        // 2. Restaurar el título original por defecto
        const tituloModal = modalReserva.querySelector('h3');
        if (tituloModal) {
            tituloModal.innerHTML = '<i class="fas fa-calendar-plus"></i> Reservar Sala';
        }

        // 3. Restaurar el botón original
        const btnSubmit = form.querySelector('button[type="submit"]');
        if (btnSubmit) {
            btnSubmit.innerHTML = '<i class="fas fa-check"></i> Confirmar Reserva';
        }

        // 4. IMPORTANTE: Volver a poner la función de GUARDAR original
        form.onsubmit = function(e) {
            if (typeof guardarReservaSQL === 'function') {
                guardarReservaSQL(e);
            }
        };
    }
    
    // Limpiar la selección del calendario para que no queden fechas guardadas
    if (typeof infoSeleccionada !== 'undefined') {
        infoSeleccionada = null;
    }
}

function navegar(pantalla, elemento) {
    const cubo = document.getElementById('cubo-principal');
    const caras = document.querySelectorAll('.seccion-pantalla');

    // FORZAR REDIBUJO: Esto despierta a las caras que el navegador ocultó
    caras.forEach(s => {
        s.style.display = 'block';
        s.style.zIndex = "1";
        // Un micro-cambio de opacidad obliga al motor gráfico a renderizar de nuevo
        s.style.opacity = "0.99"; 
        setTimeout(() => { s.style.opacity = "1"; }, 10);
    });

    // ... resto de tu lógica de remover clases ...
    cubo.classList.remove('mostrar-calendario', 'mostrar-tareas', 'mostrar-notif', 'mostrar-estadisticas', 'mostrar-configuracion');

    if (pantalla === 'calendario') {
        cubo.classList.add('mostrar-calendario');
        setTimeout(() => { if(window.calendar) calendar.updateSize(); }, 800);
    }
    else if (pantalla === 'tareas') {
        cubo.classList.add('mostrar-tareas');
        
        // Esperamos 800ms a que el cubo gire para cargar todo lo visual
        setTimeout(() => {
            cargarPanelTareas();           // Carga tu tabla de siempre
            actualizarIndicadoresVisuales(); // Carga el nuevo Dashboard (Gantt y Gráficos)
        }, 800);
    } 
    else if (pantalla === 'notificaciones') {
        cubo.classList.add('mostrar-notif');
        mostrarNotificaciones();
    }
    else if (pantalla === 'estadisticas') {
        cubo.classList.add('mostrar-estadisticas');
        setTimeout(cargarGraficas, 800);
    }
    else if (pantalla === 'configuracion') {
        cubo.classList.add('mostrar-configuracion');
    }

    // 3. Estilo de la Sidebar
    document.querySelectorAll('.menu a').forEach(a => a.classList.remove('active'));
    if (elemento) elemento.classList.add('active');
}

// --- LÓGICA DEL MODAL ---

async function irAEventoPersonal() {
    cerrarSelector();
    const modal = document.getElementById('modalEvento');
    if (modal) {
        modal.style.display = 'flex';
        
        if (!cachePersonal) {
            try {
                const resp = await fetch('/api/obtener_personal');
                cachePersonal = await resp.json();
            } catch (e) { console.error("Error cargando personal:", e); }
        }
        
        actualizarListaDestinos(); 

        if (infoSeleccionada) {
            const formatDT = (date) => {
                const d = new Date(date);
                d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
                return d.toISOString().slice(0, 16);
            };
            
            document.getElementById('ev_inicio').value = formatDT(infoSeleccionada.start);
            let fechaFin = infoSeleccionada.end || new Date(infoSeleccionada.start.getTime() + 60*60000);
            document.getElementById('ev_fin').value = formatDT(fechaFin);
        }
    }
}

function actualizarListaDestinos() {
    const tipo = document.getElementById('ev_tipo_destino').value;
    const selectDestino = document.getElementById('ev_destino');
    if (!cachePersonal || !selectDestino) return;

    selectDestino.innerHTML = "";

    if (tipo === 'persona') {
        cachePersonal.empleados.forEach(emp => {
            selectDestino.innerHTML += `<option value="${emp.id_usuario}">${emp.nombre} ${emp.apellido}</option>`;
        });
    } else if (tipo === 'departamento') {
        cachePersonal.departamentos.forEach(dep => {
            selectDestino.innerHTML += `<option value="${dep.id}">${dep.nombre}</option>`;
        });
    } else if (tipo === 'cargo') {
        cachePersonal.cargos.forEach(car => {
            selectDestino.innerHTML += `<option value="${car.id_cargo}">${car.nombre_cargo}</option>`;
        });
    }
}

// --- CARGAR TAREAS EN PANEL ---
async function cargarPanelTareas() {
    const contenedor = document.getElementById('contenedor-lista-tareas');
    if (!contenedor) return;

    // Capturamos los datos de sesión desde tus inputs hidden
    const usuarioLogueado = {
        id: document.getElementById('sesion_usuario_id').value,
        esAdmin: document.getElementById('sesion_es_admin').value === 'True'
    };

    // Mensaje de carga inicial
    contenedor.innerHTML = '<div style="padding:20px; text-align:center;">Cargando tareas...</div>';

    try {
        const resp = await fetch('/api/tareas_detalladas');
        const tareas = await resp.json();

        tareasData = tareas;

        if (tareas.length === 0) {
            contenedor.innerHTML = '<div style="padding:40px; text-align:center; color: #666;">No hay tareas o planificaciones registradas.</div>';
            return;
        }

        let html = `
            <div class="tabla-scroll">
                <table class="tabla-tareas">
                    <thead>
                        <tr>
                            <th>Actividad / Breve Descripción</th>
                            <th>Fecha y Hora</th>
                            <th>Personal Asignado</th>
                            <th>Estado</th>
                            <th>Acciones</th>
                        </tr>
                    </thead>
                    <tbody>`;

        tareas.forEach(t => {
            const estadoClase = t.completado ? 'badge-verde' : 'badge-rojo';
            const estadoTexto = t.completado ? 'Completado' : 'Pendiente';

            // --- LÓGICA DE BOTONES DINÁMICA ---
            let botonesHtml = "";

            if (t.completado) {
                if (usuarioLogueado.esAdmin) {
                    // Si está completado y es Admin: Botón de Archivar
                    botonesHtml = `
                        <button onclick="archivarReunion(${t.EventoID})" class="btn-icon-archivar" title="Archivar Reunión">
                            <i class="fas fa-archive"></i> Archivar
                        </button>`;
                } else {
                    // Si está completado y es usuario normal: Texto de espera
                    botonesHtml = `<span class="status-espera" style="color: #f39c12; font-size: 0.85rem;"><i class="fas fa-clock"></i> Esperando revisión...</span>`;
                }
            } else {
                // Si no está completado: Tus 5 botones originales
                botonesHtml = `
                    <button onclick="verDetallesTarea(${t.EventoID})" class="btn-icon-ver" title="Ver + detalles">
                        <i class="fas fa-eye"></i>
                    </button>
                    <button onclick="abrirModalEditar(${t.EventoID})" class="btn-icon-editar" title="Editar">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button onclick="marcarTareaCompletada(${t.EventoID})" class="btn-icon-check" title="Completar">
                        <i class="fas fa-check-double"></i>
                    </button>
                    <button onclick="solicitarGenerarPin(${t.EventoID})" class="btn-icon-pin" title="Generar PIN de Seguridad">
                        <i class="fas fa-key"></i>
                    </button>
                    <button onclick="eliminarEventoLista(${t.EventoID})" class="btn-icon-borrar" title="Eliminar">
                        <i class="fas fa-trash-alt"></i>
                    </button>`;
            }

            html += `
    <tr>
        <td>
    <div class="tarea-info" style="max-width: 100%; padding-right: 10px;">
        <span class="tarea-titulo" style="font-weight: bold; display: block; color: #333;">${t.Titulo}</span>
        <p class="tarea-desc" style="font-size: 0.8rem; color: #666; margin: 5px 0 0 0; line-height: 1.2;">
            ${t.Descripcion || ''}
        </p>
    </div>
</td>
        <td style="width: 200px; padding: 10px;">
    <div class="rango-fechas" style="display: flex; flex-direction: column; gap: 5px;">
        <div style="font-size: 0.85rem; font-weight: 600; color: #333;">
            <i class="fas fa-calendar-alt" style="color: #2c3e50; margin-right: 4px;"></i>
            ${t.Inicio}
        </div>
        <div style="font-size: 0.8rem; color: #d11616; border-top: 1px solid #eee; padding-top: 3px;">
            <i class="fas fa-flag-checkered" style="margin-right: 4px;"></i>
            ${t.Fin}
        </div>
    </div>
</td>
        <td><div class="asignados-lista"><small>${t.AsignadoA}</small></div></td>
        <td><span class="badge-status ${estadoClase}">${estadoTexto}</span></td>
        <td>
            <div class="acciones-flex">
                ${botonesHtml}
            </div>
        </td>
    </tr>`;
        });

        html += `</tbody></table></div>`;
        contenedor.innerHTML = html;

    } catch (e) {
        console.error("Error al cargar panel de tareas:", e);
        contenedor.innerHTML = '<div style="padding:20px; color:red; text-align:center;">Error al conectar con el servidor.</div>';
    }
}


///// VER DETALLES DE LAS TAREAS/EVENTOS/PLANIFICACIONES ///
////////////////////////////////////////////////////////////
function verDetallesTarea(id) {
    // 1. Buscamos la tarea en los datos que ya cargó la tabla (asumiendo que guardas el resultado en una variable global 'tareasData')
    const tarea = tareasData.find(t => t.EventoID === id);

    if (tarea) {
        // 2. Llenamos los campos del modal
        document.getElementById('det_titulo_tarea').innerText = tarea.Titulo;
        document.getElementById('det_descripcion').innerText = tarea.Descripcion || "Sin descripción adicional.";
        document.getElementById('det_inicio').innerText = tarea.Inicio;
        document.getElementById('det_fin').innerText = tarea.Fin;
        document.getElementById('det_personal').innerText = tarea.AsignadoA;
        
        // Formato para el estado
        const estadoLabel = tarea.completado ? 
            '<span class="badge-completado">Completado</span>' : 
            '<span class="badge-pendiente">Pendiente</span>';
        document.getElementById('det_estado').innerHTML = estadoLabel;

        // 3. Mostramos el modal con una transición suave
        const modal = document.getElementById('modalDetalles');
        modal.style.display = 'flex';
        modal.classList.add('fade-in');
    }
}

function cerrarModalDetalles() {
    document.getElementById('modalDetalles').style.display = 'none';
}





// GUARDAR ----
//----------
async function guardarPlanificacionSQL(e) {
    if (e) e.preventDefault(); 

    // 1. Captura de datos
    const titulo = document.getElementById('ev_titulo').value;
    const inicio = document.getElementById('ev_inicio').value;
    const fin = document.getElementById('ev_fin').value || inicio; // Si no hay fin, usa el inicio
    const detalles = document.getElementById('ev_detalles').value;
    const tipoAsignacion = document.getElementById('ev_tipo_destino').value;
    
    const selectDestino = document.getElementById('ev_destino');
    const invitados = Array.from(selectDestino.selectedOptions).map(opt => opt.value);

    // 2. Validación de campos obligatorios
    if (!titulo || !inicio || invitados.length === 0) {
        Swal.fire({
            icon: 'warning',
            title: 'Campos incompletos',
            text: 'Por favor, completa los campos obligatorios antes de continuar.',
            confirmButtonColor: '#9c1c3f'
        });
        return;
    }

    // 2.1 Validación lógica: Que el fin no sea antes que el inicio
    if (new Date(fin) < new Date(inicio)) {
        Swal.fire({
            icon: 'error',
            title: 'Error en fechas',
            text: 'La fecha de finalización no puede ser anterior a la de inicio.',
            confirmButtonColor: '#9c1c3f'
        });
        return;
    }

    // 2.2 Preparación de objeto (Ahora enviamos las cadenas completas ISO)
    const datos = {
        titulo: titulo,
        fecha_inicio_completa: inicio, 
        fecha_fin_completa: fin,
        descripcion: detalles,
        tipo_asignacion: tipoAsignacion,
        id_asignado: invitados,
        id_departamento_filtro: 'todos',
    };

    try {
        // 3. Estado de CARGA
        Swal.fire({
            title: 'Guardando planificación...',
            html: 'Estamos registrando los datos en el sistema de Unicasa.',
            allowOutsideClick: false,
            didOpen: () => {
                Swal.showLoading();
            }
        });

        const respuesta = await fetch('/api/guardar_evento', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(datos)
        });

        const res = await respuesta.json();

        if (res.status === 'success') {
            // 4. ÉXITO
            await Swal.fire({
                icon: 'success',
                title: '¡Planificación guardada!',
                text: 'La tarea se guardó correctamente, verifícala en el Panel de Tareas.',
                confirmButtonColor: '#28a745',
                timer: 2000,
                showConfirmButton: false
            });

            // Acciones de limpieza
            cerrarModal(); 
            const form = document.getElementById('formEvento');
            if (form) form.reset();
            
            // Actualizamos el panel si existe
            if (typeof cargarPanelTareas === 'function') cargarPanelTareas();
            if (typeof calendar !== 'undefined') calendar.refetchEvents();

        } else {
            throw new Error(res.message || "Error al procesar en SQL");
        }

    } catch (error) {
        console.error("Error:", error);
        // 5. ERROR
        Swal.fire({
            icon: 'error',
            title: 'No se pudo guardar',
            text: error.message || 'Error de conexión con el servidor.',
            confirmButtonColor: '#9c1c3f'
        });
    }
}


// --- FUNCIÓN PARA ELIMINAR DESDE LA LISTA ---
async function eliminarEventoLista(id) {
    // 1. Sustituimos el confirm() aburrido por un Warning de SweetAlert
    const result = await Swal.fire({
        title: '¿Eliminar tarea?',
        text: "Esta acción borrará la tarea del SQL y no se puede deshacer.",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#d33', // Rojo para peligro
        cancelButtonColor: '#6c757d',
        confirmButtonText: '<i class="fas fa-trash"></i> Sí, eliminar',
        cancelButtonText: 'Cancelar',
        reverseButtons: true,
        backdrop: `rgba(0,0,0,0.4)`
    });

    // Si el usuario confirma
    if (result.isConfirmed) {
        try {
            // 2. ACTIVAMOS EL RELOJITO (Cargando...)
            Swal.fire({
                title: 'Borrando del sistema...',
                html: 'Espere un momento mientras actualizamos el SQL.',
                allowOutsideClick: false,
                didOpen: () => {
                    Swal.showLoading();
                }
            });

            const resp = await fetch(`/api/eliminar_evento/${id}`, {
                method: 'DELETE'
            });
            const res = await resp.json();

            if (res.status === 'success') {
                // 3. ÉXITO: El relojito se quita solo al mostrar este
                await Swal.fire({
                    icon: 'success',
                    title: '¡Tarea Eliminada!',
                    text: 'El registro ha sido borrado correctamente.',
                    confirmButtonColor: '#28a745',
                    timer: 1500,
                    showConfirmButton: false
                });

                // Sincronizamos todo
                if (typeof cargarPanelTareas === 'function') cargarPanelTareas();
                if (typeof calendar !== 'undefined') calendar.refetchEvents();

            } else {
                throw new Error(res.message || "No se pudo eliminar");
            }

        } catch (e) {
            console.error("Error al eliminar:", e);
            // 4. ERROR: Si algo falla en el puente al servidor
            Swal.fire({
                icon: 'error',
                title: 'Error de proceso',
                text: 'No pudimos conectar con el SQL para borrar esta tarea.',
                confirmButtonColor: '#9c1c3f'
            });
        }
    }
}

//////////////////////
// COMPLETAR TAREA ///
//////////////////////
async function marcarTareaCompletada(id) {
    // 1. Pedimos el PIN con un modal de entrada
    const { value: pinIngresado } = await Swal.fire({
        title: 'Validación de Seguridad',
        text: 'Por favor, ingresa el PIN de seguridad para finalizar esta tarea.',
        input: 'text',
        inputPlaceholder: 'Ingresa el PIN aquí...',
        showCancelButton: true,
        confirmButtonColor: '#28a745', // Verde Unicasa
        confirmButtonText: 'Validar y Completar',
        cancelButtonText: 'Cancelar',
        inputAttributes: {
            autocapitalize: 'off',
            autocorrect: 'off'
        },
        inputValidator: (value) => {
            if (!value) {
                return '¡Debes ingresar el PIN!';
            }
        }
    });

    // Si el usuario ingresó algo y no canceló
    if (pinIngresado) {
        try {
            // 2. Estado de carga (Relojito) mientras validamos en SQL
            Swal.fire({
                title: 'Verificando PIN...',
                html: 'Estamos validando tus credenciales en el sistema.',
                allowOutsideClick: false,
                didOpen: () => {
                    Swal.showLoading();
                }
            });

            const respuesta = await fetch(`/api/completar_tarea/${id}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ pin: pinIngresado })
            });

            const res = await respuesta.json();

            if (res.status === 'success') {
                // 3. ÉXITO
                await Swal.fire({
                    icon: 'success',
                    title: '¡Tarea Finalizada!',
                    text: res.message, // "¡PIN Correcto! Tarea finalizada."
                    confirmButtonColor: '#28a745',
                    timer: 2000,
                    showConfirmButton: false
                });

                // Actualizamos la lista y el calendario
                if (typeof cargarPanelTareas === 'function') cargarPanelTareas();
                if (typeof calendar !== 'undefined') calendar.refetchEvents();
                
                // Si tienes la campana de notificaciones, la actualizamos también
                if (typeof actualizarBadgeNotificaciones === 'function') {
                    actualizarBadgeNotificaciones();
                }

            } else {
                // 4. ERROR (PIN incorrecto o no encontrado)
                Swal.fire({
                    icon: 'error',
                    title: 'Validación fallida',
                    text: res.message, // "PIN incorrecto"
                    confirmButtonColor: '#9c1c3f'
                });
            }
        } catch (error) {
            console.error("Error al completar:", error);
            Swal.fire({
                icon: 'error',
                title: 'Error de conexión',
                text: 'No se pudo contactar con el servidor.',
                confirmButtonColor: '#9c1c3f'
            });
        }
    }
}

// GENERAR PIN //

async function solicitarGenerarPin(eventoId) {
    const result = await Swal.fire({
        title: '¿Generar nuevo PIN?',
        text: "Esto invalidará cualquier PIN anterior para esta tarea.",
        icon: 'info',
        showCancelButton: true,
        confirmButtonColor: '#9c1c3f',
        confirmButtonText: 'Sí, generar PIN',
        cancelButtonText: 'Cancelar'
    });

    if (result.isConfirmed) {
        try {
            Swal.fire({
                title: 'Generando...',
                didOpen: () => { Swal.showLoading(); }
            });

            const respuesta = await fetch(`/api/generar_pin/${eventoId}`, {
                method: 'POST'
            });

            const res = await respuesta.json();

            if (res.status === 'success') {
                // ÉXITO: Mostramos el PIN en grande para que el Jefe lo entregue
                await Swal.fire({
                    icon: 'success',
                    title: 'PIN Generado con Éxito',
                    html: `
                        <p>Entrega este código al responsable de la tarea:</p>
                        <div style="background: #eee; padding: 20px; border-radius: 10px; margin: 15px 0;">
                            <strong style="font-size: 2.5rem; color: #9c1c3f; letter-spacing: 10px;">${res.pin}</strong>
                        </div>
                        <p style="font-size: 0.8rem; color: #666;">Este PIN es único y expira cuando se complete la tarea.</p>
                    `,
                    confirmButtonColor: '#9c1c3f'
                });
            } else {
                // ERROR: Aquí saldrá "Acceso denegado" si no es Cargo 5
                Swal.fire({
                    icon: 'error',
                    title: 'Error de Autorización',
                    text: res.message,
                    confirmButtonColor: '#9c1c3f'
                });
            }
        } catch (error) {
            Swal.fire('Error', 'No se pudo conectar con el servidor', 'error');
        }
    }
}

///// ARCHIVAR TAREA ///
async function archivarReunion(id) {
    const result = await Swal.fire({
        title: '¿Archivar reunión?',
        text: "La reunión se marcará como finalizada oficialmente y desaparecerá de la lista activa.",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#2c3e50',
        confirmButtonText: 'Sí, archivar',
        cancelButtonText: 'Cancelar'
    });

    if (result.isConfirmed) {
        try {
            Swal.fire({ title: 'Archivando...', didOpen: () => Swal.showLoading() });

            const res = await fetch(`/api/archivar_evento/${id}`, { method: 'POST' });
            const data = await res.json();

            if (data.status === 'success') {
                Swal.fire('¡Archivado!', 'La reunión ha sido enviada al historial.', 'success');
                cargarPanelTareas(); // Recarga la lista
            }
        } catch (error) {
            Swal.fire('Error', 'No se pudo archivar la reunión.', 'error');
        }
    }
}



//////////////////////////////////////////////////
/////////////// --- RESERVAS --- /////////////////
/////////////// --- RESERVAS --- /////////////////
/////////////// --- RESERVAS --- /////////////////
/////////////// --- RESERVAS --- /////////////////
//////////////////////////////////////////////////


// RESERVAS
// -------------
async function abrirModalReserva() {
    cerrarSelector(); // Cerramos cualquier menú previo
    const modal = document.getElementById('modalReserva');
    const form = document.getElementById('formReserva');
    
    if (modal && form) {
        // 1. LIMPIEZA TOTAL: Borra lo que escribió el usuario antes
        form.reset();

        // 2. RESTAURAR TEXTO Y COMPORTAMIENTO:
        // Forzamos el título que quieres y el comportamiento de "Crear"
        modal.querySelector('h3').innerHTML = '<i class="fas fa-calendar-plus"></i> Reservar Sala';
        
        const btnSubmit = form.querySelector('button[type="submit"]');
        btnSubmit.innerHTML = '<i class="fas fa-check"></i> Confirmar Reserva';
        
        // REESTABLECER EL ENVÍO: Muy importante para que no intente editar
        form.onsubmit = function(e) {
            guardarReservaSQL(e);
        };

        // 3. CARGAR DATOS Y MOSTRAR
        cargarSalasSQL();
        modal.style.display = 'flex';
        
        // Autocompletar si se seleccionó en el calendario
        if (typeof infoSeleccionada !== 'undefined' && infoSeleccionada) {
            const formatDT = (date) => {
                const d = new Date(date);
                d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
                return d.toISOString().slice(0, 16);
            };
            document.getElementById('res_inicio').value = formatDT(infoSeleccionada.start);
            document.getElementById('res_fin').value = formatDT(infoSeleccionada.end || infoSeleccionada.start);
        }
    }
}

// ------------ GUARDAR RESERVA
// ------------------------------------
// --- GUARDAR RESERVA DE SALA ---
async function guardarReservaSQL(e) {
    if (e) e.preventDefault();

    const btnSubmit = e.target.querySelector('button[type="submit"]') || document.querySelector('.btn-primario');
    const originalContent = btnSubmit.innerHTML;

    const datos = {
        id_sala: document.getElementById('res_sala').value || null,
        id_organizador: document.getElementById('res_organizador').value,
        titulo: document.getElementById('res_titulo').value,
        descripcion: document.getElementById('res_descripcion').value,
        materiales: document.getElementById('res_materiales').value,
        inicio: document.getElementById('res_inicio').value.replace('T', ' '),
        fin: document.getElementById('res_fin').value.replace('T', ' '),
        recurrente: document.getElementById('res_recurrente').checked ? 1 : 0,
        req_cafe: document.getElementById('req_cafe').checked ? 1 : 0,
        req_agua: document.getElementById('req_agua').checked ? 1 : 0,
        req_it: document.getElementById('req_it').checked ? 1 : 0,
        tipo_reunion: document.getElementById('res_tipo_reunion').value,
        plataforma: document.getElementById('res_plataforma').value || null,
        link_reunion: document.getElementById('res_link').value || null,
        invitados: invitadosTemporales, // <--- Correcto: Esto manda el array de objetos
        invitados_internos: trabajadoresSeleccionados // <--- Los IDs de los compañeros
    };

    // --- VALIDACIÓN ---
    let errores = [];
    if (!datos.titulo) errores.push("título");
    if (!datos.inicio) errores.push("hora de inicio");
    if (!datos.fin) errores.push("hora de fin");
    if (!datos.id_organizador) errores.push("responsable");
    
    // Validación lógica de tiempo
    if (new Date(datos.inicio) >= new Date(datos.fin)) {
        errores.push("la hora de fin debe ser mayor a la de inicio");
    }

    if (datos.tipo_reunion === 'Presencial' && !datos.id_sala) {
        errores.push("seleccionar una sala");
    }
    if (datos.tipo_reunion === 'Virtual') {
        if (!datos.plataforma) errores.push("plataforma");
        if (!datos.link_reunion) errores.push("enlace de la reunión");
    }
    else if (datos.tipo_reunion === 'Mixta') {
        // Exige TODO: Sala + Plataforma + Link
        if (!datos.id_sala) errores.push("seleccionar una sala física");
        if (!datos.plataforma) errores.push("plataforma virtual");
        if (!datos.link_reunion) errores.push("enlace de la reunión");
    }

    if (errores.length > 0) {
        mostrarToast("Falta: " + errores.join(", "), "error");
        return;
    }

    try {
        btnSubmit.disabled = true;
        btnSubmit.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Verificando...';

        const respuesta = await fetch('/api/guardar_reserva', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(datos)
        });

        const res = await respuesta.json();

        if (res.success || res.status === 'success') {
            // --- CAMBIO A SWEETALERT ---
            Swal.fire({
                title: '¡Reserva Guardada!',
                text: 'El evento se ha registrado correctamente en el calendario.',
                icon: 'success',
                confirmButtonColor: '#28a745',
                confirmButtonText: 'Entendido'
            }).then((result) => {
                // --- LIMPIEZA Y CIERRE DESPUÉS DEL OK ---
                invitadosTemporales = [];
                const listaUL = document.getElementById('lista_invitados_previa');
                if(listaUL) listaUL.innerHTML = "";
                
                // Cierre seguro del modal
                if (typeof cerrarModal === "function") {
                    cerrarModal();
                } else {
                    const m = document.getElementById('modalReserva');
                    if(m) m.style.display = 'none';
                }

                // Reset de formulario
                const form = document.getElementById('formReserva');
                if(form) form.reset();
                
                if(typeof toggleCamposVirtuales === "function") toggleCamposVirtuales();
                
                const infoSala = document.getElementById('info-sala-detalle');
                if (infoSala) infoSala.style.display = 'none';

                // Actualizar calendario
                if (typeof calendar !== 'undefined' && calendar !== null) {
                    calendar.refetchEvents();
                }
            });

        } else {
            Swal.fire({
                title: 'No se pudo reservar',
                text: res.message || "Error desconocido",
                icon: 'warning',
                confirmButtonColor: '#d33'
            });
        }
    } catch (error) {
        console.error("Error:", error);
        mostrarToast("Fallo de conexión con el servidor", "error");
    } finally {
        btnSubmit.disabled = false;
        btnSubmit.innerHTML = originalContent;
    }
}



// ---- CARGAR SALAS
// ------
// Variable global para guardar la info completa de las salas
let salasCache = [];

async function cargarSalasSQL() {
    const select = document.getElementById('res_sala');
    if (!select) return;

    try {
        const resp = await fetch('/api/get_salas');
        const salas = await resp.json();
        
        // Guardamos los datos completos en el caché
        salasCache = salas;
        
        // Limpiamos y ponemos la opción por defecto
        select.innerHTML = '<option value="">-- Seleccione una sala --</option>';
        
        salas.forEach(s => {
            // AJUSTE CLAVE: Usamos los nombres exactos de tu SQL (ID_Sala, NombreSala, Estado)
            const idSala = s.ID_Sala || s.id; 
            const nombreSala = s.NombreSala || s.nombre;
            const estadoSala = s.Estado || s.estado || 'Disponible';

            const disabled = estadoSala !== 'Disponible' ? 'disabled' : '';
            
            // Creamos el elemento de forma más limpia
            const option = document.createElement('option');
            option.value = idSala;
            option.disabled = (estadoSala !== 'Disponible');
            option.textContent = `${nombreSala} (${estadoSala})`;
            
            select.appendChild(option);
        });

        // Evitar duplicar event listeners si la función se llama varias veces
        select.removeEventListener('change', actualizarDetallesSala);
        select.addEventListener('change', actualizarDetallesSala);

        // Retornamos true para que abrirModoEdicion sepa que ya puede marcar la sala
        return true;

    } catch (e) {
        console.error("Error al cargar salas:", e);
        return false;
    }
}

function actualizarDetallesSala() {
    const idSeleccionado = document.getElementById('res_sala').value;
    const panel = document.getElementById('info-sala-detalle');
    
    console.log("ID Seleccionado:", idSeleccionado); // Mira esto en la consola F12
    console.log("Contenido de salasCache:", typeof salasCache !== 'undefined' ? salasCache : "No existe");

    if (!idSeleccionado) {
        panel.style.display = 'none';
        return;
    }

    // Buscamos la sala (Aseguramos que el ID sea comparado correctamente)
    const sala = salasCache.find(s => s.id == idSeleccionado);

    if (sala) {
        panel.style.display = 'block';
        
        // Mapeo de variables: SQL (Mayúscula) o JS (Minúscula)
        const ubicacion = sala.Ubicacion || sala.ubicacion || 'No definida';
        const capacidad = sala.Capacidad || sala.capacidad || '0';
        const dimensiones = sala.Dimensiones || sala.dimensiones || 'N/A';
        const equiposRaw = sala.Equipamiento || sala.equipamiento || '';

        panel.innerHTML = `
            <div class="ficha-sala" style="background: #fdf2f2; border: 1px solid #6b0f1a; padding: 12px; border-radius: 8px; margin-top: 10px;">
                <div class="ficha-item" style="margin-bottom: 5px;">
                    <i class="fas fa-map-marker-alt" style="color: #6b0f1a;"></i> 
                    <span><strong>Ubicación:</strong> ${ubicacion}</span>
                </div>
                <div style="display: flex; justify-content: space-between; margin: 8px 0; border-top: 1px solid #eee; padding-top: 5px;">
                    <div>
                        <i class="fas fa-users" style="color: #6b0f1a;"></i> 
                        <span><strong>Capacidad:</strong> ${capacidad} pers.</span>
                    </div>
                    <div>
                        <i class="fas fa-expand-arrows-alt" style="color: #6b0f1a;"></i> 
                        <span><strong>Tamaño:</strong> ${dimensiones}</span>
                    </div>
                </div>
                <div class="ficha-equipos">
                    <strong>Equipamiento:</strong><br>
                    <div style="display: flex; flex-wrap: wrap; gap: 5px; margin-top: 5px;">
                        ${equiposRaw ? equiposRaw.split(',').map(tag => `<span style="background: #6b0f1a; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8em;">${tag.trim()}</span>`).join('') : 'Básico'}
                    </div>
                </div>
            </div>
        `;
    } else {
        console.error("No se encontró la sala con ID:", idSeleccionado, "en el caché.");
    }
}




// CARGAR EMPLEADO PARA LAS SALAS
//-------
async function cargarOrganizadoresReserva() {
    const select = document.getElementById('res_organizador');
    if (!select) return;

    // 1. CARGA DE DATOS (Usando el cachePersonal)
    if (!cachePersonal) {
        try {
            const resp = await fetch('/api/obtener_personal');
            cachePersonal = await resp.json();
        } catch (e) { 
            console.error("Error al cargar personal:", e); 
            return; 
        }
    }

    // 2. LIMPIEZA Y LLENADO
    select.innerHTML = '<option value="">-- Seleccione el responsable --</option>';
    
    // Usamos empleados porque es la propiedad que viene en tu JSON
    if (cachePersonal && cachePersonal.empleados) {
        cachePersonal.empleados.forEach(emp => {
            const opt = document.createElement('option');
            opt.value = emp.id_usuario; // Este ID debe coincidir con datos.id_organizador
            opt.textContent = `${emp.nombre} ${emp.apellido}`;
            select.appendChild(opt);
        });
    }

    // 3. EL PASO CLAVE: Retornamos algo para que el 'await' de afuera funcione
    return true; 
}
// Actualiza tu función de abrir para que cargue ambos
function abrirModalReserva() {
    cerrarSelector();
    document.getElementById('modalReserva').style.display = 'flex';
    cargarSalasSQL(); 
    cargarOrganizadoresReserva(); // <--- Nueva llamada
}






// MODAL PARA VER LO QUE SE ABRE (Actualizado con formato AM/PM)
function mostrarDetalleReserva(eventObj) {
    try {
        const p = eventObj.extendedProps;
        const idReserva = eventObj.id;
        const titulo = (eventObj.title || '').replace('✔ ', '');
 
        // Capturamos el ID desde el elemento oculto que pusimos en el HTML
const usuarioActualId = parseInt(document.getElementById('sesion_usuario_id').value) || 0;
const esAdmin = document.getElementById('sesion_es_admin').value === "True";

// El ID del dueño que ya sabemos que llega bien como 1
const idOrganizadorReserva = parseInt(p.ID_Organizador || 0, 10);

console.log("Validación Final -> Mi ID:", usuarioActualId, "| Dueño ID:", idOrganizadorReserva);

 // Inyectar en el HTML
        document.getElementById('det_titulo').innerText = titulo;
        document.getElementById('det_organizador').innerText = p.organizador || 'No asignado';

        // Formateo de fechas para el modal
        const opcionesHora = { hour: 'numeric', minute: '2-digit', hour12: true };
        const opcionesFecha = { day: '2-digit', month: '2-digit', year: 'numeric' };
        
        
        // --- NUEVA LÓGICA DE HORARIO COMPLETO ---
        let fechaTexto = 'Fecha no definida';

        if (eventObj.start) {
            const fechaBase = eventObj.start.toLocaleDateString('es-VE', opcionesFecha);
            const horaInicio = eventObj.start.toLocaleTimeString('es-VE', opcionesHora);
            
            // Si existe hora de fin, la formateamos; si no, ponemos un aviso
            const horaFin = eventObj.end ? 
                eventObj.end.toLocaleTimeString('es-VE', opcionesHora) : 
                'Indefinida';

            fechaTexto = `${fechaBase}, ${horaInicio} — ${horaFin}`;
        }
        
        document.getElementById('det_horario').innerText = fechaTexto;
        document.getElementById('det_descripcion').innerText = p.descripcion || 'Sin descripción';
        document.getElementById('det_materiales').innerText = p.materiales || 'Ninguno';

        // 1. Lógica de Servicios (Catering/IT)
        let htmlServicios = "";
        if (p.req_cafe == 1) htmlServicios += `<span title="Café" style="margin-right: 15px; color: #6b0f1a;"><i class="fas fa-coffee"></i> Café</span>`;
        if (p.req_agua == 1) htmlServicios += `<span title="Agua" style="margin-right: 15px; color: #0eb5fd;"><i class="fas fa-tint"></i> Agua</span>`;
        if (p.req_it == 1)   htmlServicios += `<span title="Soporte IT" style="color: #28a745;"><i class="fas fa-headset"></i> Soporte IT</span>`;
        
        const contenedorServicios = document.getElementById('det_servicios');
        if (contenedorServicios) {
            contenedorServicios.innerHTML = htmlServicios || "<small style='color:gray;'>Ningún servicio solicitado</small>";
        }

      // --- LÓGICA DE INVITADOS (DISEÑO UNIFORME) ---
const listaUL = document.getElementById('lista-invitados-detalle');
const seccionInv = document.getElementById('seccion-invitados');

if (listaUL && seccionInv) {
    const internos = p.invitados_internos || []; 
    const externos = p.invitados || [];          

    if (internos.length > 0 || externos.length > 0) {
        seccionInv.style.display = 'block';
        const itemStyle = 'border-bottom: 1px solid #eee; padding: 8px 0; font-size: 14px; display: flex; align-items: center;';

        const htmlInternos = (p.invitados_internos || []).map(int => `
    <li style="border-bottom: 1px solid #eee; padding: 8px 0; font-size: 14px; display: flex; align-items: center;">
        <i class="fas fa-id-badge" style="color: #6b0f1a; margin-right: 10px; width: 20px;"></i>
        <span>
            <strong>${int.nombre || 'Sin Nombre'}</strong> 
            <span style="color: #666;">(Interno - ${int.cedula || 'N/A'})</span>
        </span>
    </li>
`).join('');

        const htmlExternos = externos.map(inv => `
            <li style="${itemStyle}">
                <i class="fas fa-user-check" style="color: #28a745; margin-right: 10px; width: 20px; font-size: 1.1em;"></i>
                <span>
                    <strong>${inv.nombre}</strong> 
                    <span style="color: #666;">(${inv.empresa || 'Particular'} - ${inv.cedula || 'N/A'})</span>
                </span>
            </li>
        `).join('');

        listaUL.innerHTML = htmlInternos + htmlExternos;
        
        const tituloSeccion = seccionInv.querySelector('strong');
        if (tituloSeccion) {
            tituloSeccion.innerHTML = '<i class="fas fa-users"></i> Personas Invitadas:';
        }
    } else {
        seccionInv.style.display = 'none';
    }
}
        // ----------------------------------------

      // --- LÓGICA DE MODALIDAD ACTUALIZADA (VIRTUAL/PRESENCIAL/MIXTA) ---
const tipoReunion = p.tipo_reunion || 'Presencial';
const detTipo = document.getElementById('det_tipo_reunion');

// 1. Definimos el texto y el icono según la modalidad
if (tipoReunion === 'Mixta') {
    detTipo.innerHTML = '🏢🌐 <b>Reunión Mixta</b> (Presencial + Virtual)';
} else if (tipoReunion === 'Virtual') {
    detTipo.innerText = '🌐 Reunión Virtual';
} else {
    detTipo.innerText = '📍 Reunión Presencial';
}

// 2. Control del Link: Se muestra en 'Virtual' Y en 'Mixta'
const linkSeccion = document.getElementById('det_link_seccion');

if ((tipoReunion === 'Virtual' || tipoReunion === 'Mixta') && p.link_reunion) {
    linkSeccion.style.display = 'block';
    document.getElementById('det_plataforma').innerText = p.plataforma || 'Plataforma no especificada';
    
    const linkElement = document.getElementById('det_link_url');
    linkElement.href = p.link_reunion;
    linkElement.innerText = "Haga clic aquí para unirse a la reunión";
} else {
    linkSeccion.style.display = 'none';
}

// --- Inyectar Sala ---
document.getElementById('det_sala').innerHTML = `<strong>${p.nombre_sala || 'Sala'}</strong>`;

// Apuntamos al nuevo ID exclusivo del modal de detalles
const infoSalaVer = document.getElementById('info-sala-ver-detalle');

if (p.id_sala) {
    infoSalaVer.style.display = 'block'; 
    
    fetch(`/api/get_sala_detalle/${p.id_sala}`)
        .then(res => res.json())
        .then(sala => {
            if(!sala.error) {
                infoSalaVer.innerHTML = `
                    <div style="background-color: #f8f9fa; border-left: 5px solid #9c1c3f; padding: 12px; border-radius: 8px; margin-top: 10px; border: 1px solid #eee;">
                        <p style="margin: 0 0 5px 0; font-size: 13px; color: #333;"><strong>📍 Ubicación:</strong> ${sala.ubicacion}</p>
                        <p style="margin: 0 0 5px 0; font-size: 13px; color: #333;"><strong>👥 Capacidad:</strong> ${sala.capacidad} pers.</p>
                        <p style="margin: 0; font-size: 13px; color: #333;"><strong>🛠️ Equipamiento:</strong> ${sala.equipamiento}</p>
                    </div>
                `;
            }
        });
} else {
    infoSalaVer.style.display = 'none';
}

// (Tu código sigue igual)
const modal = document.getElementById('modalDetalleReserva');
modal.dataset.idReserva = idReserva;
        
        // --- NUEVA LÓGICA: BOTÓN CHECK-IN ---
        const btnCheckin = document.getElementById('btn_checkin');
        if (btnCheckin) {
            btnCheckin.dataset.idReserva = idReserva;
            // Mostrar solo si es Presencial, no tiene check_in y la reserva está activa (estado < 1)
            if (tipoReunion === 'Presencial' && !p.check_in && (p.estado || 0) < 1) {
                btnCheckin.style.display = 'inline-block';
            } else {
                btnCheckin.style.display = 'none';
            }
        }

        // --- PROTECCIÓN CONTRA NULLS EN EL JSON ---
        modal.dataset.reservaOriginal = JSON.stringify({
            id: idReserva,
            titulo: titulo,
            inicio: eventObj.start ? eventObj.start.toISOString() : null, 
            fin: eventObj.end ? eventObj.end.toISOString() : null,
            descripcion: p.descripcion || "",
            materiales: p.materiales || "",
            id_sala: p.id_sala, 
            id_organizador: p.id_organizador,
            recurrente: p.recurrente || 0,
            req_cafe: p.req_cafe || 0,
            req_agua: p.req_agua || 0,
            req_it: p.req_it || 0,
            tipo_reunion: tipoReunion,
            plataforma: p.plataforma,
            link_reunion: p.link_reunion,
            invitados: p.invitados, // Incluirlos en la copia de respaldo
            invitados_internos: p.invitados_internos // <--- Los IDs de los compañeros
        });

        // Lógica de botones
        const btnFinalizar = document.querySelector('.btn-completar-green');
        const btnAprobar = document.getElementById('btnAprobarAdmin');

        if (eventObj.title && eventObj.title.includes('✔')) {
            if(btnFinalizar) btnFinalizar.style.display = 'none';
            if(btnAprobar) btnAprobar.style.display = 'block';
        } else {
            if(btnFinalizar) btnFinalizar.style.display = 'block';
            if(btnAprobar) btnAprobar.style.display = 'none';
        }
       const controles = document.getElementById('controles_propietario');
const aviso = document.getElementById('msg_solo_lectura');

// La comparación mágica
if (esAdmin || (usuarioActualId > 0 && usuarioActualId === idOrganizadorReserva)) {
    if (controles) controles.style.display = 'block';
    if (aviso) aviso.style.display = 'none';
    console.log("✅ Acceso total concedido");
} else {
    if (controles) controles.style.display = 'none';
    if (aviso) aviso.style.display = 'block';
    console.log("❌ Acceso denegado: Eres el ID " + usuarioActualId + " y el dueño es el ID " + idOrganizadorReserva);
}
modal.style.display = 'flex';


    } catch (error) {
        console.error("Error en mostrarDetalleReserva:", error);
        alert("Hubo un error al cargar los detalles de la reserva. Revisa la consola (F12).");
    }
}

// COMENZAR O CONFIRMAR LA SALA/ASISTENCIA ////
//////////////////////////////////////////////
async function confirmarAsistencia() {
    const btn = document.getElementById('btn_checkin');
    const idReserva = btn.dataset.idReserva;
    
    // Alerta de confirmación antes de proceder
    const result = await Swal.fire({
        title: '¿Confirmar asistencia?',
        text: "Se registrará tu llegada a la sala ahora mismo.",
        icon: 'info',
        showCancelButton: true,
        confirmButtonColor: '#28a745', // Verde éxito
        cancelButtonColor: '#6c757d',
        confirmButtonText: '<i class="fas fa-user-check"></i> Sí, confirmar',
        cancelButtonText: 'Cancelar',
        reverseButtons: true,
        backdrop: `rgba(0,0,0,0.6)`
    });

    if (result.isConfirmed) {
        try {
            Swal.showLoading(); // Feedback de espera

            const respuesta = await fetch(`/api/checkin/${idReserva}`, { method: 'POST' });
            const res = await respuesta.json();
            
            if (res.status === 'success') {
                await Swal.fire({
                    icon: 'success',
                    title: '¡Asistencia confirmada!',
                    text: 'Se ha registrado tu ingreso correctamente.',
                    confirmButtonColor: '#28a745',
                    timer: 2000,
                    showConfirmButton: false
                });

                btn.style.display = 'none'; // Ocultamos el botón
                if (typeof calendar !== 'undefined') {
                    calendar.refetchEvents(); // Refrescamos calendario
                }
            } else {
                throw new Error(res.message);
            }
        } catch (error) {
            Swal.fire({
                icon: 'error',
                title: 'Error al confirmar',
                text: 'No se pudo registrar la asistencia.',
                confirmButtonColor: '#9c1c3f'
            });
        }
    }
}

// ELIMINAR RESERVA: 
////////////////////
async function eliminarReservaActual() {
    const idReserva = document.getElementById('modalDetalleReserva').dataset.idReserva;

    if (!idReserva) {
        Swal.fire({
            icon: 'error',
            title: 'Error',
            text: 'No se pudo identificar la reserva.',
            confirmButtonColor: '#9c1c3f'
        });
        return;
    }

    const result = await Swal.fire({
        title: '¿Estás seguro?',
        text: "Esta acción eliminará la reserva permanentemente.",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#d33', // Rojo para peligro
        cancelButtonColor: '#6c757d',
        confirmButtonText: '<i class="fas fa-trash-alt"></i> Sí, eliminar',
        cancelButtonText: 'Cancelar',
        reverseButtons: true
    });

    if (result.isConfirmed) {
        try {
            // 1. Mostramos el "relojito" de carga
            Swal.fire({
                title: 'Eliminando reserva...',
                html: 'Por favor, espera un momento.',
                allowOutsideClick: false,
                didOpen: () => {
                    Swal.showLoading(); // Aquí se activa el cargador animado
                }
            });

            const respuesta = await fetch(`/api/eliminar_reserva/${idReserva}`, {
                method: 'DELETE'
            });

            const res = await respuesta.json();

            if (res.status === 'success') {
                // 2. Éxito: El cargador se quita solo al abrir este nuevo Swal
                await Swal.fire({
                    icon: 'success',
                    title: '¡Eliminado!',
                    text: 'La reserva ha sido borrada del sistema.',
                    confirmButtonColor: '#9c1c3f',
                    timer: 2000,
                    showConfirmButton: false
                });

                cerrarModal(); 
                if (typeof calendar !== 'undefined') {
                    calendar.refetchEvents(); 
                }
            } else {
                throw new Error(res.message || "Error desconocido");
            }
        } catch (error) {
            console.error("Error:", error);
            Swal.fire({
                icon: 'error',
                title: 'No se pudo eliminar',
                text: error.message || 'Error de conexión con el servidor.',
                confirmButtonColor: '#9c1c3f'
            });
        }
    }
}





/// SOLICITAR QUE LA RESERVA TERMINO Y ADMIN LA ARCHIVE PARA TENER REGISTRO EN UN LOG DESPUÉS //
async function marcarCompletada() {
    const idReserva = document.getElementById('modalDetalleReserva').dataset.idReserva;

    if (!idReserva) {
        Swal.fire({
            icon: 'error',
            title: 'Error',
            text: 'No se pudo identificar la reserva.',
            confirmButtonColor: '#9c1c3f'
        });
        return;
    }

    const result = await Swal.fire({
        title: '¿Finalizar reunión?',
        text: "Se enviará una solicitud al administrador para marcarla como completada.",
        icon: 'question',
        showCancelButton: true,
        confirmButtonColor: '#28a745', // Verde Unicasa
        cancelButtonColor: '#6c757d',
        confirmButtonText: '<i class="fas fa-check-circle"></i> Sí, finalizar',
        cancelButtonText: 'Cancelar',
        reverseButtons: true,
        backdrop: `rgba(0,0,0,0.6)`
    });

    if (result.isConfirmed) {
        try {
            // 1. Mostramos el "relojito" de carga mientras el SQL se actualiza
            Swal.fire({
                title: 'Procesando solicitud...',
                html: 'Enviando aviso al administrador.',
                allowOutsideClick: false,
                didOpen: () => {
                    Swal.showLoading(); // Activa el cargador animado
                }
            });

            const respuesta = await fetch(`/api/completar_reserva/${idReserva}`, {
                method: 'POST'
            });

            const res = await respuesta.json();

            if (res.status === 'success') {
                // 2. Éxito: Se cierra el relojito y sale el check verde
                await Swal.fire({
                    icon: 'success',
                    title: '¡Solicitud Enviada!',
                    text: 'La reserva cambiará de color mientras el administrador la aprueba.',
                    confirmButtonColor: '#28a745',
                    timer: 3000,
                    showConfirmButton: false
                });

                cerrarModal();
                if (typeof calendar !== 'undefined') {
                    calendar.refetchEvents(); // Recarga para ver el nuevo estado/color
                }
            } else {
                throw new Error(res.message || 'No se pudo completar la acción.');
            }
        } catch (error) {
            console.error("Error:", error);
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: error.message || 'Hubo un problema al conectar con el servidor.',
                confirmButtonColor: '#9c1c3f'
            });
        }
    }
}





// APROBAR LA RESERVA Y METER AL LOG: 
///////////////////////////////
async function aprobarYLoguear() {
    const idReserva = document.getElementById('modalDetalleReserva').dataset.idReserva;

    // Alerta de confirmación administrativa
    const result = await Swal.fire({
        title: '¿Archivar reserva?',
        text: "Al confirmar, la reunión se registrará oficialmente en el historial y se liberará el espacio en el calendario.",
        icon: 'info',
        showCancelButton: true,
        confirmButtonColor: '#0056b3', // Azul para acciones de registro/archivo
        cancelButtonColor: '#6c757d',
        confirmButtonText: '<i class="fas fa-file-export"></i> Sí, archivar',
        cancelButtonText: 'Cancelar',
        reverseButtons: true,
        backdrop: `rgba(0,0,0,0.6)`
    });

    if (result.isConfirmed) {
        try {
            // Feedback visual de procesamiento
            Swal.showLoading();

            const respuesta = await fetch(`/api/aprobar_reserva/${idReserva}`, {
                method: 'POST'
            });

            const res = await respuesta.json();

            if (res.status === 'success') {
                await Swal.fire({
                    icon: 'success',
                    title: '¡Archivado con éxito!',
                    text: 'La reserva ha sido enviada al historial log.',
                    confirmButtonColor: '#0056b3',
                    timer: 2500,
                    showConfirmButton: false
                });

                cerrarModal();
                if (typeof calendar !== 'undefined') {
                    calendar.refetchEvents(); // El evento desaparecerá del calendario principal
                }
            } else {
                Swal.fire({
                    icon: 'error',
                    title: 'Error al archivar',
                    text: res.message,
                    confirmButtonColor: '#9c1c3f'
                });
            }
        } catch (error) {
            console.error("Error:", error);
            Swal.fire({
                icon: 'error',
                title: 'Fallo de conexión',
                text: 'No se pudo contactar con el servidor de Unicasa.',
                confirmButtonColor: '#9c1c3f'
            });
        }
    }
}



/////////////////////////////////////
///////////////////////////////// PANTALLA COMPLETA
function toggleCalendarioGrande() {
    const body = document.body;
    body.classList.toggle('calendar-maximized');

    // Cambiar texto del botón (usa el ID que le pusiste)
    const btn = document.getElementById('btnExpandir') || document.querySelector('.btn-secundario');
    if (body.classList.contains('calendar-maximized')) {
        btn.innerHTML = '<i class="fas fa-compress-arrows-alt"></i> Reducir';
    } else {
        btn.innerHTML = '<i class="fas fa-expand-arrows-alt"></i> Pantalla Completa';
    }

    // DISPARAR EL REAJUSTE
    // Esperamos un poco a que el CSS oculte el sidebar
    setTimeout(() => {
        if (typeof calendar !== 'undefined') {
            calendar.updateSize();
            // Disparar un evento de resize global por si acaso
            window.dispatchEvent(new Event('resize'));
        }
    }, 400); 
}

/// MOSTRAR LOS TOAST LINDOS 
///////////////////////////////
function mostrarToast(mensaje, tipo = 'success') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${tipo}`;
    
    const icono = tipo === 'success' ? 'fa-check-circle' : 'fa-exclamation-circle';
    
    toast.innerHTML = `
        <i class="fas ${icono}"></i>
        <span>${mensaje}</span>
    `;
    
    container.appendChild(toast);

    // Desvanecer y eliminar después de 3 segundos
    setTimeout(() => {
        toast.classList.add('toast-fade-out');
        setTimeout(() => toast.remove(), 500);
    }, 3000);
}


///////// EDITAR RESERVA /////////
///////////////////////////////////
async function abrirModoEdicion() {
    const modalDetalle = document.getElementById('modalDetalleReserva');
    if (!modalDetalle.dataset.reservaOriginal) return;
    
    // Parseamos los datos originales de la reserva
    const datos = JSON.parse(modalDetalle.dataset.reservaOriginal);
    const form = document.getElementById('formReserva');
    const modalForm = document.getElementById('modalReserva');

    // 1. CARGAR DATOS DE SQL Y ESPERAR (Sincronización Crítica)
    // Usamos await para asegurar que los <option> existan antes de asignar valores
    await cargarSalasSQL(); 
    if (typeof cargarOrganizadoresReserva === 'function') {
        await cargarOrganizadoresReserva(); 
    }

    // 2. RELLENAR CAMPOS DE TEXTO
    document.getElementById('res_titulo').value = datos.titulo || "";
    document.getElementById('res_descripcion').value = datos.descripcion || "";
    document.getElementById('res_materiales').value = datos.materiales || "";
    
    // Si tienes el checkbox de recurrente:
    const checkRecurrente = document.getElementById('res_recurrente');
    if (checkRecurrente) {
        checkRecurrente.checked = datos.recurrente == 1;
    }

    // 3. SELECCIÓN AUTOMÁTICA DE LOS SELECTS
    // --- Sala ---
    const selectSala = document.getElementById('res_sala');
    if (selectSala && datos.id_sala) {
        selectSala.value = String(datos.id_sala);
    }

    // --- Responsable (Blindado) ---
    const selectResp = document.getElementById('res_organizador');
    if (selectResp && datos.id_organizador) {
        const idBuscado = String(datos.id_organizador);
        
        // Intento 1: Asignación directa
        selectResp.value = idBuscado;
        
        // Intento 2: Búsqueda manual si la directa falla (doble igual para omitir tipo de dato)
        if (selectResp.value !== idBuscado) {
            Array.from(selectResp.options).forEach(opt => {
                if (opt.value == idBuscado) opt.selected = true;
            });
        }
        
        // Intento 3: Reintento de seguridad por latencia de renderizado
        setTimeout(() => {
            if (selectResp.value !== idBuscado) {
                selectResp.value = idBuscado;
            }
        }, 150); 
    }

    // 4. FORMATEAR FECHAS (Evita desfase horario)
    const formatParaInput = (fecha) => {
        if (!fecha) return "";
        const d = new Date(fecha);
        const pad = (n) => n.toString().padStart(2, '0');
        // Formato requerido por <input type="datetime-local">: YYYY-MM-DDTHH:mm
        return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
    };

    document.getElementById('res_inicio').value = formatParaInput(datos.inicio);
    document.getElementById('res_fin').value = formatParaInput(datos.fin);

    // 5. CONFIGURAR INTERFAZ Y EVENTOS
    modalForm.querySelector('h3').innerHTML = '<i class="fas fa-edit"></i> Editar Reserva';
    
    const btnSubmit = form.querySelector('button[type="submit"]');
    if (btnSubmit) {
        btnSubmit.innerHTML = '<i class="fas fa-save"></i> Guardar Cambios';
    }

    // Sobrescribimos el onsubmit para que use la ruta de actualización
    form.onsubmit = async function(e) {
        e.preventDefault();
        if (typeof actualizarReservaSQL === 'function') {
            await actualizarReservaSQL(e, datos.id);
        }
    };

    // 6. SWAP DE MODALES
    modalDetalle.style.display = 'none';
    modalForm.style.display = 'flex';
}

////// ACTUALIZAR RESERVA, LA QUE DISPARA EL GUARDAR CAMBIOS /////
//////////////////////////////////////////////////////////////////
async function actualizarReservaSQL(e, idReserva) {
    if (e) e.preventDefault();

    const btn = document.querySelector('#formReserva button[type="submit"]');
    const originalText = btn.innerHTML;

    // 1. CAPTURAMOS LOS DATOS (Igual que en guardarReservaSQL)
    const datos = {
        id_sala: document.getElementById('res_sala').value || null,
        id_organizador: document.getElementById('res_organizador').value,
        titulo: document.getElementById('res_titulo').value,
        descripcion: document.getElementById('res_descripcion').value,
        materiales: document.getElementById('res_materiales').value,
        inicio: document.getElementById('res_inicio').value.replace('T', ' '),
        fin: document.getElementById('res_fin').value.replace('T', ' '),
        recurrente: document.getElementById('res_recurrente').checked ? 1 : 0,
        req_cafe: document.getElementById('req_cafe').checked ? 1 : 0,
        req_agua: document.getElementById('req_agua').checked ? 1 : 0,
        req_it: document.getElementById('req_it').checked ? 1 : 0,
        // Ojo: Asegúrate que el ID sea 'res_tipo_reunion' como en tu guardar
        tipo_reunion: document.getElementById('res_tipo_reunion').value, 
        plataforma: document.getElementById('res_plataforma').value || null,
        link_reunion: document.getElementById('res_link').value || null,
        // Usamos las mismas variables globales que usas al guardar
        invitados: invitadosTemporales, 
        invitados_internos: trabajadoresSeleccionados 
    };

    // 2. VALIDACIÓN (Copiada de tu lógica de guardado)
    let errores = [];
    if (!datos.titulo) errores.push("título");
    if (!datos.inicio) errores.push("hora de inicio");
    if (!datos.fin) errores.push("hora de fin");
    if (!datos.id_organizador) errores.push("responsable");
    
    if (new Date(datos.inicio) >= new Date(datos.fin)) {
        errores.push("la hora de fin debe ser mayor a la de inicio");
    }

    if (datos.tipo_reunion === 'Presencial' && !datos.id_sala) {
        errores.push("seleccionar una sala");
    }
    if (datos.tipo_reunion === 'Virtual') {
        if (!datos.plataforma) errores.push("plataforma");
        if (!datos.link_reunion) errores.push("enlace de la reunión");
    }
    else if (datos.tipo_reunion === 'Mixta') {
        // Exige TODO: Sala + Plataforma + Link
        if (!datos.id_sala) errores.push("seleccionar una sala física");
        if (!datos.plataforma) errores.push("plataforma virtual");
        if (!datos.link_reunion) errores.push("enlace de la reunión");
    }

    if (errores.length > 0) {
        mostrarToast("Falta: " + errores.join(", "), "error");
        return;
    }

    // 3. ENVÍO AL SERVIDOR
    try {
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Actualizando...';

        const resp = await fetch(`/api/update_reserva/${idReserva}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(datos)
        });

        const res = await resp.json();

        if (res.status === 'success' || res.success) {
            mostrarToast("¡Reserva actualizada correctamente!", "success");
            
            // LIMPIEZA (Igual que al guardar)
            invitadosTemporales = []; 
            trabajadoresSeleccionados = []; // También limpiamos esta si la usas
            const listaUL = document.getElementById('lista_invitados_previa');
            if(listaUL) listaUL.innerHTML = ""; 

            cerrarModal();
            
            if (typeof calendar !== 'undefined') {
                calendar.refetchEvents(); 
            }
        } else {
            mostrarToast(res.message, "error");
        }
    } catch (error) {
        console.error("Error en la actualización:", error);
        mostrarToast("Error de conexión", "error");
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}


// NOTIS PERO EN EL RESUMEN HOY //
// Función para precargar datos sin cambiar de pantalla
function precargarQuickLook() {
    fetch('/api/obtener_notificaciones')
        .then(response => response.json())
        .then(data => {
            const contentQuickLook = document.getElementById('quick-look-content');
            if (contentQuickLook && data && data.length > 0) {
                contentQuickLook.innerHTML = data.slice(0, 3).map(n => `
                    <div class="quick-item">
                        <strong style="display:block; color:#ffa502;">${n.Tipo ? n.Tipo.toUpperCase() : 'AVISO'}</strong>
                        <p style="margin:2px 0; color:#eee; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${n.Mensaje}</p>
                    </div>
                `).join('');
            }
        });
}

// Ejecutar apenas cargue la página
window.addEventListener('load', precargarQuickLook);



///////////////////////////////////////////////////////
///////// TIPO DE REUNION DIGITAL O PRESENCIAL ///////////
function toggleCamposVirtuales() {
    const tipo = document.getElementById('res_tipo_reunion').value;
    const seccionVirtual = document.getElementById('seccion_virtual');
    const selectSala = document.getElementById('res_sala');
    const plataforma = document.getElementById('res_plataforma');
    const link = document.getElementById('res_link');

if (tipo === 'Virtual' || tipo === 'Mixta') {
        seccionVirtual.style.display = 'block';
        plataforma.setAttribute('required', 'true');
        link.setAttribute('required', 'true');

        if (tipo === 'Virtual') {
            // SOLO VIRTUAL: No usa sala física
            selectSala.value = ""; 
            selectSala.disabled = true;
            selectSala.removeAttribute('required');
        } else {
            // MIXTA: SÍ usa sala física y es obligatoria
            selectSala.disabled = false;
            selectSala.setAttribute('required', 'true');
        }
        
    } else {
        // PRESENCIAL: No hay link, solo sala física
        seccionVirtual.style.display = 'none';
        plataforma.removeAttribute('required');
        link.removeAttribute('required');

        selectSala.disabled = false;
        selectSala.setAttribute('required', 'true');
    }
}



///// INVITADOS EXTERNOS PARA REUNIONES /////
/////////////////////////////////////////////
let invitadosTemporales = [];

function agregarInvitadoLista() {
    const nom = document.getElementById('inv_nombre');
    const emp = document.getElementById('inv_empresa');
    const ced = document.getElementById('inv_cedula');
    
    if (nom.value.trim()) {
        // Guardamos el objeto completo
        invitadosTemporales.push({
            nombre: nom.value.trim(),
            empresa: emp.value.trim(),
            cedula: ced.value.trim()
        });
        
        actualizarVistaInvitados();
        
        // Limpiamos los 3 inputs
        nom.value = ""; emp.value = ""; ced.value = "";
    }
}

function actualizarVistaInvitados() {
    const listaUL = document.getElementById('lista_invitados_previa');
    listaUL.innerHTML = invitadosTemporales.map((inv, index) => 
        `<li style="background: #f4f4f4; margin-bottom: 5px; padding: 8px; border-radius: 4px; display: flex; justify-content: space-between; font-size: 0.85em;">
            <span><strong>${inv.nombre}</strong> - ${inv.empresa || 'S/E'} (${inv.cedula || 'S/C'})</span>
            <span onclick="eliminarInvitado(${index})" style="color: #6b0f1a; cursor: pointer; font-weight: bold;">&times;</span>
        </li>`
    ).join('');
}

function eliminarInvitado(index) {
    invitadosTemporales.splice(index, 1);
    actualizarVistaInvitados();
}


/////////////Este script hará tres cosas: buscar mientras escribes, agregar al trabajador a una lista y enviarlos al backend.//////////////////
///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
let trabajadoresSeleccionados = []; // Aquí guardaremos los IDs

// 1. Buscador en tiempo real
// Aseguramos que el código corra cuando el modal esté listo
// Usamos una función global para que no haya errores de carga
// 1. Buscador en tiempo real usando DELEGACIÓN (Para que funcione dentro de modales)
document.addEventListener('input', async function(e) {
    // Verificamos que el usuario esté escribiendo en el buscador de trabajadores
    if (e.target && e.target.id === 'busquedaTrabajador') {
        const inputBusqueda = e.target;
        const busqueda = inputBusqueda.value.trim();
        const lista = document.getElementById('listaSugerencias');
        
        console.log("Escribiendo en vivo:", busqueda);

        if (busqueda.length < 2) {
            lista.style.display = 'none';
            lista.innerHTML = '';
            return;
        }

        try {
            const response = await fetch(`/api/buscar_usuarios?q=${encodeURIComponent(busqueda)}`);
            const usuarios = await response.json();

            lista.innerHTML = '';

            if (usuarios.length > 0) {
                usuarios.forEach(u => {
                    const li = document.createElement('li');
                    li.style.padding = '12px';
                    li.style.background = 'white';
                    li.style.color = 'black';
                    li.style.borderBottom = '1px solid #ddd';
                    li.style.cursor = 'pointer';
                    li.style.display = 'block';
                    li.textContent = `${u.Nombre} ${u.Apellido}`;
                    
                    li.onclick = function() {
                        agregarTrabajador(u);
                        lista.style.display = 'none';
                        inputBusqueda.value = '';
                    };
                    lista.appendChild(li);
                });

                // FORZAR VISIBILIDAD
                lista.style.display = 'block';
                lista.style.zIndex = '99999';
                lista.style.position = 'absolute';
                lista.style.width = inputBusqueda.offsetWidth + 'px'; // Ajusta el ancho al del input
            } else {
                lista.style.display = 'none';
            }
        } catch (error) {
            console.error("Error al buscar:", error);
        }
    }
});

// 2. Función para agregar el "Chip" visual
///////////////////////////////////////////
function agregarTrabajador(usuario) {
    if (trabajadoresSeleccionados.includes(usuario.UsuarioID)) return;

    trabajadoresSeleccionados.push(usuario.UsuarioID);
    
    const container = document.getElementById('contenedorInternosSeleccionados');
    const chip = document.createElement('span');
    
    // Le agregamos un ID único al chip para borrarlo fácil
    chip.id = `chip-usuario-${usuario.UsuarioID}`;
    chip.className = 'badge bg-primary p-2 d-flex align-items-center';
    chip.style.margin = '2px';
    
    chip.innerHTML = `
        ${usuario.Nombre} ${usuario.Apellido}
        <i class="fas fa-times-circle ms-2 pointer" 
           style="cursor:pointer;" 
           onclick="removerTrabajador(${usuario.UsuarioID})"></i>
    `;
    container.appendChild(chip);
    
    // Limpiar buscador
    document.getElementById('busquedaTrabajador').value = '';
    document.getElementById('listaSugerencias').style.display = 'none';
}

// 3. Función para borrar (Ahora busca por ID de chip)
function removerTrabajador(id) {
    // 1. Lo quitamos del array
    trabajadoresSeleccionados = trabajadoresSeleccionados.filter(uId => uId !== id);
    
    // 2. Lo quitamos de la pantalla usando el ID que creamos arriba
    const chip = document.getElementById(`chip-usuario-${id}`);
    if (chip) {
        chip.remove();
    }
    
    console.log("Eliminado. Quedan:", trabajadoresSeleccionados);
}

/// LIMPIAR LOS INVITADOS////
function limpiarInvitadosUnicasa() {
    // 1. Vaciar el array de IDs
    trabajadoresSeleccionados = [];
    
    // 2. Limpiar el contenedor visual de chips
    const container = document.getElementById('contenedorInternosSeleccionados');
    if (container) container.innerHTML = '';
    
    // 3. Limpiar el input de búsqueda y la lista de sugerencias
    const input = document.getElementById('busquedaTrabajador');
    const lista = document.getElementById('listaSugerencias');
    if (input) input.value = '';
    if (lista) {
        lista.innerHTML = '';
        lista.style.display = 'none';
    }
    
    console.log("Buscador de invitados reiniciado");
}

//// NOTIFICACIONES EN EL SISTEMA //////
///////////////////////////////////////
function mostrarNotificaciones() {
    // 1. Ocultamos las otras pantallas
    document.getElementById('pantalla-calendario').style.display = 'none';
    document.getElementById('pantalla-tareas').style.display = 'none';
    
    // 2. Mostramos la sección de notificaciones
    const seccionNotif = document.getElementById('pantalla-notificaciones');
    const contenedorLista = document.getElementById('contenedor-notificaciones');
    const contentQuickLook = document.getElementById('quick-look-content');
    
    seccionNotif.style.display = 'block';
    
    // CORRECCIÓN AQUÍ: Usamos contenedorLista que es la que declaraste arriba
    contenedorLista.innerHTML = '<div style="text-align:center; padding:20px;"><i class="fas fa-spinner fa-spin"></i> Actualizando...</div>';

    // 3. Pedimos a Python los datos
    fetch('/api/obtener_notificaciones')
        .then(response => response.json())
        .then(data => {
            console.log("Datos recibidos de SQL:", data);

            // PASO 2: Llenar el Quick Look de la sidebar con las últimas 3
            if (contentQuickLook) {
                if (!data || data.length === 0) {
                    contentQuickLook.innerHTML = '<p style="padding:15px; font-size:0.7rem; color:rgba(255,255,255,0.4); text-align:center; margin:0;">No hay avisos recientes</p>';
                } else {
                    contentQuickLook.innerHTML = data.slice(0, 3).map(n => `
                        <div class="quick-item" style="padding: 10px; border-bottom: 1px solid rgba(255,255,255,0.05);">
                            <strong style="display:block; font-size:0.75rem; color:#ffa502;">${n.Tipo ? n.Tipo.toUpperCase() : 'AVISO'}</strong>
                            <p style="margin:2px 0; font-size:0.7rem; color:#eee; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${n.Mensaje}</p>
                        </div>
                    `).join('');
                }
            }
            
            if (!data || data.length === 0) {
                contenedorLista.innerHTML = '<p style="text-align:center; padding:20px;">No hay notificaciones.</p>';
                return;
            }

            let html = '';
            data.forEach(n => {
    const claseEstado = n.Leido ? 'leida' : 'nueva';
    
    // 1. LÓGICA DE HOY/AYER POR TEXTO (Sencilla y segura)
    let fechaMostrar = n.FechaCreacion; 
    try {
        // Obtenemos fechas de referencia
        const hoyStr = new Date().toISOString().split('T')[0]; // "YYYY-MM-DD"
        
        const ayerObj = new Date();
        ayerObj.setDate(ayerObj.getDate() - 1);
        const ayerStr = ayerObj.toISOString().split('T')[0];

        // n.FechaCreacion suele venir "YYYY-MM-DD HH:MM:SS"
        const partes = n.FechaCreacion.split(' ');
        const parteFecha = partes[0]; 
        const parteHora = partes[1] ? partes[1].substring(0, 5) : "";

        if (parteFecha === hoyStr) {
            fechaMostrar = `Hoy a las ${parteHora}`;
        } else if (parteFecha === ayerStr) {
            fechaMostrar = `Ayer a las ${parteHora}`;
        }
    } catch (e) {
        console.error("Error al procesar fecha:", e);
    }

    // 2. HTML CON DISEÑO VERTICAL (Sin la variable tieneEvento)
    html += `
    <div id="notif-${n.NotificacionID}" 
         class="card-notif ${n.Tipo} ${claseEstado}" 
         onclick="marcarUnaLeida(${n.NotificacionID}, ${n.Leido})">
        <div class="card-header-notif" style="display: flex; flex-direction: column; align-items: flex-start;">
            <div style="display: flex; justify-content: space-between; width: 100%; align-items: center;">
                <strong style="font-size: 0.9rem;">${n.Tipo ? n.Tipo.toUpperCase() : 'AVISO'}</strong>
                ${!n.Leido ? '<span class="punto-nuevo" style="color: #9c1c3f;">●</span>' : ''}
            </div>
            <small style="color: #888; margin-top: 2px; font-size: 0.75rem;">${fechaMostrar}</small>
        </div>
        <p style="margin-top: 10px; font-size: 0.9rem; color: #333;">${n.Mensaje}</p>
    </div>`;
});
            contenedorLista.innerHTML = html;
        })
        .catch(error => {
            console.error('Error:', error);
            contenedorLista.innerHTML = '<p style="color:red; text-align:center;">Error al cargar notificaciones.</p>';
        });
}

function formatearFechaNotif(fechaStr) {
    const fecha = new Date(fechaStr);
    const ahora = new Date();
    
    const esHoy = fecha.toDateString() === ahora.toDateString();
    
    const ayer = new Date();
    ayer.setDate(ahora.getDate() - 1);
    const esAyer = fecha.toDateString() === ayer.toDateString();

    const opcionesHora = { hour: '2-digit', minute: '2-digit' };
    const hora = fecha.toLocaleTimeString([], opcionesHora);

    if (esHoy) return `Hoy a las ${hora}`;
    if (esAyer) return `Ayer a las ${hora}`;
    
    // Si es más vieja, mostramos fecha normal
    return fecha.toLocaleDateString() + ' ' + hora;
}

// MARCAR LEÍDAS SISTEMA AUTOMÁTICO //
///////////////////////////////////////
function marcarTodoLeido() {
    Swal.fire({
        title: '¿Estás seguro?',
        text: "Todas tus notificaciones se marcarán como leídas",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#28a745', // Verde Unicasa
        cancelButtonColor: '#d33',
        confirmButtonText: 'Sí, marcar todas',
        cancelButtonText: 'Cancelar',
        // Esto hace que se vea bien sobre fondos oscuros o claros
        background: '#fff', 
        customClass: {
            popup: 'animated fadeInDown'
        }
    }).then((result) => {
        if (result.isConfirmed) {
            // Si el usuario confirma, hacemos el fetch
            fetch('/api/marcar_leidas', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.status === "ok") {
                        // Notificación de éxito
                        Swal.fire({
                            title: '¡Listo!',
                            text: 'Notificaciones actualizadas.',
                            icon: 'success',
                            timer: 1500,
                            showConfirmButton: false
                        });

                        // Refrescamos tu interfaz
                        mostrarNotificaciones();
                        actualizarBadgeNotificaciones(); 
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    Swal.fire('Error', 'No se pudo actualizar el SQL', 'error');
                });
        }
    });
}
function marcarUnaLeida(id, yaLeida) {
    if (yaLeida) return; // Si ya está leída, no hacemos nada

    fetch(`/api/marcar_leida_individual/${id}`, { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            if (data.status === "ok") {
                // Cambio visual inmediato sin recargar
                const tarjeta = document.getElementById(`notif-${id}`);
                tarjeta.classList.remove('nueva');
                tarjeta.classList.add('leida');
                actualizarBadgeNotificaciones();
                
                // Quitamos el punto rojo si existe
                const punto = tarjeta.querySelector('.punto-nuevo');
                if (punto) punto.remove();

                console.log(`Notificación ${id} marcada como leída.`);
            }
        })
        .catch(error => console.error('Error:', error));
}

/// SONIDO NOTIFICACIONES SISTEMA INTERNO //
////////////////////////////////////////////
let ultimoIdNotificacionVisto = null; // Cambiamos el contador por ID para mayor precisión
let totalNotificacionesActual = 0; 

function actualizarBadgeNotificaciones() {
    fetch('/api/contar_notificaciones')
        .then(response => response.json())
        .then(data => {
            const badge = document.querySelector('.nav-badge');
            const nuevoTotal = data.total;

            // 1. Lógica para detectar si hay UNA NOTIFICACIÓN NUEVA REAL (por ID)
            if (data.ultima_id && data.ultima_id !== ultimoIdNotificacionVisto) {
                
                // Si no es la primera vez que carga la página, procesamos la novedad
                if (ultimoIdNotificacionVisto !== null) {
                    
                    // A. Sonar el audio para CUALQUIER notificación nueva
                    reproducirSonido();

                    // B. SOLO si la nueva es de tipo 'Sistema', mostramos el Toast
                    if (data.ultima_tipo === 'Sistema') {
                        mostrarToastSistema(data.ultima_mensaje);

                    if (typeof calendar !== 'undefined') {
                                calendar.refetchEvents(); 
                    }    
                    }
                    
                }
                // Actualizamos el ID visto para no repetir el proceso con la misma notificación
                ultimoIdNotificacionVisto = data.ultima_id;
            }

            // 2. Actualización de UI del Badge (Lo que ya te funciona)
            if (nuevoTotal > 0) {
                badge.textContent = nuevoTotal;
                badge.style.display = 'inline-block';
            } else {
                badge.style.display = 'none';
            }

            totalNotificacionesActual = nuevoTotal;
        })
        .catch(error => console.error('Error al contar notificaciones:', error));
}

function mostrarToastSistema(mensaje) {
    const Toast = Swal.mixin({
        toast: true,
        position: 'top-end',
        showConfirmButton: false,
        timer: 8000,
        timerProgressBar: true,
        iconColor: '#6b0f1a', 
        didOpen: (toast) => {
            toast.style.cursor = 'pointer';
            
            toast.addEventListener('click', () => {
                // 1. Cerramos el Toast inmediatamente
                Swal.close();

                // 2. Buscamos el botón de la barra de navegación
                const btnNotif = document.getElementById('btn-nav-notificaciones');
                
                // 3. Ejecutamos tus funciones de navegación
                if (typeof navegar === "function") {
                    navegar('notificaciones', btnNotif);
                }
                if (typeof mostrarNotificaciones === "function") {
                    mostrarNotificaciones();
                }
            });

            toast.addEventListener('mouseenter', Swal.stopTimer);
            toast.addEventListener('mouseleave', Swal.resumeTimer);
        }
    });

    Toast.fire({
        icon: 'warning',
        title: 'Aviso del Sistema',
        text: mensaje,
        footer: '<div style="color: #6b0f1a; font-size: 0.8em; font-weight: bold; text-align: center; width: 100%;">Haz clic para ver detalles</div>'
    });
}


function reproducirSonido() {
    const sonido = document.getElementById('sonido-notificacion');
    if (sonido) {
        sonido.currentTime = 0; // Reinicia el audio si ya estaba sonando
        sonido.play().catch(e => console.warn("El navegador bloqueó el auto-play: ", e));
    }
}
// Ejecutar una vez al cargar la página
setInterval(actualizarBadgeNotificaciones, 2000);
document.addEventListener('DOMContentLoaded', actualizarBadgeNotificaciones);



// Función para cargar los contadores del Dashboard //
//////////////////////////////////////////////////////
function cargarIndicadores() {
    // IMPORTANTE: Mira que la ruta sea /api/indicadores_rapidos
    fetch('/api/indicadores_rapidos')
        .then(res => res.json())
        .then(data => {
            console.log("Indicadores recibidos:", data);
            document.getElementById('count-tareas').innerText = data.tareas;
            document.getElementById('count-reservas').innerText = data.reservas;
            document.getElementById('count-notif').innerText = data.notificaciones;
        })
        .catch(e => console.error("Error cargando indicadores:", e));
}

// Llamarla al cargar la página
document.addEventListener('DOMContentLoaded', cargarIndicadores);


// Ejecutar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
    cargarIndicadores();
    
    // OPCIONAL: Actualizar automáticamente cada 2 minutos para ver cambios en tiempo real
    setInterval(cargarIndicadores, 60000); 
});


////////////////////
/// ESTADISTICAS ///
////////////////////

// 1. Variables globales: añadimos estas dos para la flecha
let chartSalas, chartUsuarios, chartSemana;
let datosStats = null;      // <--- IMPORTANTE: Para guardar los datos del servidor
let modoActual = 'usuarios'; // <--- IMPORTANTE: Para saber en qué vista estamos

function cargarGraficas() {
    fetch('/api/estadisticas-dashboard')
        .then(response => response.json())
        .then(data => {
            datosStats = data; // <--- GUARDAMOS los datos para que toggleRanking los vea

            // --- 1. GRÁFICA DE SALAS (Barras Verticales) ---
            const ctxSalas = document.getElementById('chartSalas').getContext('2d');
            if (chartSalas) chartSalas.destroy();
            chartSalas = new Chart(ctxSalas, {
                type: 'bar',
                data: {
                    labels: data.salas.labels,
                    datasets: [{
                        label: 'Número de Reservas',
                        data: data.salas.data,
                        backgroundColor: 'rgba(156, 28, 63, 0.8)',
                        borderColor: '#9c1c3f',
                        borderWidth: 1
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });

            // --- 2. GRÁFICA DE USUARIOS (Dona/Pastel) ---
            const ctxUser = document.getElementById('chartUsuarios').getContext('2d');
            if (chartUsuarios) chartUsuarios.destroy();
            chartUsuarios = new Chart(ctxUser, {
                type: 'doughnut',
                data: {
                    labels: data.usuarios.labels,
                    datasets: [{
                        data: data.usuarios.data,
                        backgroundColor: ['#9c1c3f', '#d4a5b2', '#5c1025', '#e9ecef'],
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });

            // --- 3. GRÁFICA SEMANAL (Línea) ---
            const ctxSemana = document.getElementById('chartSemana').getContext('2d');
            if (chartSemana) chartSemana.destroy();
            chartSemana = new Chart(ctxSemana, {
                type: 'line',
                data: {
                    labels: ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'],
                    datasets: [{
                        label: 'Actividad de la Semana',
                        data: data.semana,
                        fill: true,
                        backgroundColor: 'rgba(156, 28, 63, 0.1)',
                        borderColor: '#9c1c3f',
                        tension: 0.4
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });
        })
        .catch(error => console.error('Error cargando estadísticas:', error));
}
//////////////////////////////
// ESTADISTICAS TAREAS ///////
//////////////////////////////
let chartPrioridadInstance = null;

function actualizarIndicadoresVisuales() {
    fetch('/api/dashboard_tareas')
        .then(res => res.json())
        .then(data => {
            // --- 1. ACTUALIZAR MINI-CARDS (KPIs) ---
            const totalTareas = data.tareas.length;
            const sumaProgreso = data.tareas.reduce((acc, t) => acc + (parseInt(t.progress) || 0), 0);
            const promedio = totalTareas > 0 ? Math.round(sumaProgreso / totalTareas) : 0;

            if(document.getElementById('total-progreso')) {
                document.getElementById('total-progreso').innerText = `${promedio}%`;
                document.getElementById('bar-total').style.width = `${promedio}%`;
            }

            const criticas = data.stats_prioridades[1] || 0;
            if(document.getElementById('tareas-criticas')) {
                document.getElementById('tareas-criticas').innerText = criticas;
            }

            // --- 2. DIBUJAR EL GANTT ---
            if(data.tareas && data.tareas.length > 0) {
                // VALIDACIÓN DE DATOS (Para matar el error de 'group' y '$bar')
                const tareasValidadas = data.tareas.map(t => ({
                    id: String(t.id),
                    name: t.name || "Sin título",
                    start: t.start, 
                    end: t.end,
                    progress: parseInt(t.progress) || 0,
                    description: t.description || "Sin descripción",
                    // Esto asigna colores: 1=Vinotinto, 2=Amarillo, 3=Verde
                    custom_class: 'bar-prioridad-' + (t.priority || 3) 
                }));

                // Limpieza total antes de redibujar
                const contenedor = document.getElementById('gantt-target');
                contenedor.innerHTML = '';
                
                const hoy = new Date();
const haceUnMes = new Date(hoy.getFullYear(), hoy.getMonth() - 1, hoy.getDate());
const dentroDeDosMeses = new Date(hoy.getFullYear(), hoy.getMonth() + 2, hoy.getDate());

const gantt = new Gantt("#gantt-target", tareasValidadas, {
    language: 'es',
    view_mode: 'Day', 
    column_width: 45,  // Ajustado para que los días no estén tan pegados ni tan lejos
    bar_height: 35,
    padding: 18,
    date_format: 'DD/MM/YYYY',
    // Esto asegura que siempre veas un margen razonable
    start_date: haceUnMes,
    end_date: dentroDeDosMeses,
                        custom_popup_html: function(task) {
                        // AQUÍ ESTÁ EL TRUCO: Formateamos las fechas antes del return
                        const fInicio = task.start.split('-').reverse().join('/');
                        const fFin = task.end.split('-').reverse().join('/');

                        return `
    <div class="gantt-popup-custom" id="contenedor-popup-gantt">
        <div class="gantt-popup-header d-flex justify-content-between align-items-center">
            <span style="font-size: 1.0rem; font-weight: bold;">
                <i class="fas fa-clipboard-list"></i> DETALLE TAREA
            </span>
            <i class="fas fa-times btn-close-gantt" 
               onclick="event.stopPropagation(); forzarCierrePopup();" 
               style="cursor:pointer; padding: 5px; font-size: 1.2rem;"></i>
        </div>
        <div class="gantt-popup-body">
            <h6 class="gantt-task-title" style="font-size: 1.0rem; font-weight: 800; margin-bottom: 10px;">
                ${task.name}
            </h6>
            <p class="gantt-task-desc" style="font-size: 0.85rem; line-height: 1.4;">
                ${task.description}
            </p>
            <div class="gantt-task-meta" style="margin-top: 15px;">
                <div style="font-size: 1rem; color: #555; margin-bottom: 8px;">
                    <i class="far fa-calendar-alt"></i> <strong>${fInicio}</strong> al <strong>${fFin}</strong>
                </div>
                <div class="progress-label" style="font-size: 0.9rem; margin-bottom: 4px;">
                    Progreso: ${task.progress}%
                </div>
                <div class="progress-mini" style="height: 10px;">
                    <div style="width: ${task.progress}%; height: 100%;"></div>
                </div>
            </div>
        </div>
    </div>`;
                    }
                });
            }
            // Después de const gantt = new Gantt(...)
function marcarDivisionMes() {
    const textosDias = document.querySelectorAll('.gantt .lower-text');
    textosDias.forEach(texto => {
        if (texto.textContent === '01') {
            const x = texto.getAttribute('x');
            const svg = document.querySelector('#gantt-target svg');
            
            // Creamos una línea roja vertical justo antes del día 01
            const linea = document.createElementNS("http://www.w3.org/2000/svg", "line");
            linea.setAttribute("x1", x - 20); // Ajustamos a la izquierda del 01
            linea.setAttribute("y1", "0");
            linea.setAttribute("x2", x - 20);
            linea.setAttribute("y2", "100%");
            linea.setAttribute("stroke", "#6b0f1a");
            linea.setAttribute("stroke-width", "3");
            linea.setAttribute("stroke-dasharray", "5,5"); // Línea punteada elegante
            
            svg.appendChild(linea);
        }
    });
}

// Ejecutamos la marca después de un breve delay para que el SVG esté listo
setTimeout(marcarDivisionMes, 500);

            // --- 3. GRÁFICO DE TORTA ---
            const canvas = document.getElementById('chartPrioridades');
            if (canvas) {
                const ctx = canvas.getContext('2d');
                if (chartPrioridadInstance) { chartPrioridadInstance.destroy(); }
                chartPrioridadInstance = new Chart(ctx, {
                    type: 'doughnut',
                    data: {
                        labels: ['Alta', 'Media', 'Baja'],
                        datasets: [{
                            data: [
                                data.stats_prioridades[1] || 0, 
                                data.stats_prioridades[2] || 0, 
                                data.stats_prioridades[3] || 0
                            ],
                            backgroundColor: ['#6b0f1a', '#ffc107', '#28a745'],
                            borderWidth: 2
                        }]
                    },
                    options: { responsive: true, maintainAspectRatio: false }
                });
            }
        })
        .catch(err => console.error("Error en Dashboard:", err));
}

// CERRAR POUP MINI MODAL DEL GANTT //
//////////////////////////////////////
function forzarCierrePopup() {
    console.log("Intentando cerrar popup...");

    // 1. Buscamos por la clase que usa Frappe por defecto
    const containers = document.querySelectorAll('.details-container');
    containers.forEach(el => {
        el.style.display = 'none';
        el.innerHTML = '';
    });

    // 2. Buscamos nuestro contenedor personalizado por ID
    const miPopup = document.getElementById('contenedor-popup-gantt');
    if (miPopup) {
        // Subimos hasta encontrar el contenedor que inyecta la librería
        let parent = miPopup.closest('.details-container');
        if (parent) {
            parent.style.display = 'none';
        } else {
            // Si no tiene ese padre, ocultamos el nuestro directamente
            miPopup.style.display = 'none';
        }
    }
}
//////////////////////////////
// RANKING DE DEPARTAMENTOS //
//////////////////////////////
function toggleRanking() {
    // Si todavía no han cargado los datos del servidor, no hacemos nada
    if (!datosStats) return; 

    const titulo = document.getElementById('titulo-ranking');
    const iconoFlecha = document.getElementById('icono-flecha');
    const botonFlecha = iconoFlecha.parentElement;

    if (modoActual === 'usuarios') {
        // Cambiamos a Departamentos (usando los datos guardados en datosStats)
        chartUsuarios.data.labels = datosStats.departamentos.labels;
        chartUsuarios.data.datasets[0].data = datosStats.departamentos.data;
        chartUsuarios.data.datasets[0].backgroundColor = ['#09783f', '#09381a', '#42a471', '#8cd29e'];
        
        titulo.innerHTML = '<i class="fas fa-building"></i> Ranking por Departamentos';
        titulo.style.color = '#006437'; // Título en verde
        botonFlecha.style.backgroundColor = '#006437'; // Fondo del botón verde
        iconoFlecha.classList.replace('fa-arrow-right', 'fa-arrow-left');
        modoActual = 'departamentos';


    } else {
        // Volvemos a Organizadores
        chartUsuarios.data.labels = datosStats.usuarios.labels;
        chartUsuarios.data.datasets[0].data = datosStats.usuarios.data;
        chartUsuarios.data.datasets[0].backgroundColor = ['#9c1c3f', '#5c1025', '#d4a5b2', '#e9ecef'];
        
        titulo.innerHTML = '<i class="fas fa-users"></i> Ranking de Organizadores';
        titulo.style.color = '#9c1c3f'; // Título en vinotinto
        botonFlecha.style.backgroundColor = '#9c1c3f'; // Fondo del botón vinotinto
        iconoFlecha.classList.replace('fa-arrow-left', 'fa-arrow-right');
        modoActual = 'usuarios';
    }
    chartUsuarios.update(); 
}
////////////////////////
// ACTIVIDAD POR HORA //
////////////////////////
let modoActividad = 'dias'; // 'dias' o 'horas'

function toggleActividad() {
    if (!datosStats) return;

    const titulo = document.getElementById('titulo-actividad');
    const icono = document.getElementById('icono-actividad');
    const btn = icono.parentElement;

    if (modoActividad === 'dias') {
        // CAMBIAR A HORAS (AZUL)
        modoActividad = 'horas';
        chartSemana.data.labels = datosStats.actividad_horas.labels;
        chartSemana.data.datasets[0].data = datosStats.actividad_horas.data;
        chartSemana.data.datasets[0].label = 'Reservas por Hora';
        
        // Cambiamos el color a azul
        chartSemana.data.datasets[0].borderColor = '#0056b3';
        chartSemana.data.datasets[0].backgroundColor = 'rgba(0, 86, 179, 0.1)';
        
        titulo.innerHTML = '<i class="fas fa-clock"></i> Actividad por Horas';
        titulo.style.color = '#0056b3';
        btn.style.backgroundColor = '#0056b3';
        icono.classList.replace('fa-clock', 'fa-calendar-day');
    } else {
        // VOLVER A DÍAS (VINOTINTO)
        modoActividad = 'dias';
        chartSemana.data.labels = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'];
        chartSemana.data.datasets[0].data = datosStats.semana;
        chartSemana.data.datasets[0].label = 'Reservas por Día';
        
        // Volvemos al Vinotinto de Unicasa
        chartSemana.data.datasets[0].borderColor = '#9c1c3f';
        chartSemana.data.datasets[0].backgroundColor = 'rgba(156, 28, 63, 0.1)';
        
        titulo.innerHTML = '<i class="fas fa-calendar-week"></i> Actividad por Días';
        titulo.style.color = '#9c1c3f';
        btn.style.backgroundColor = '#9c1c3f';
        icono.classList.replace('fa-calendar-day', 'fa-clock');
    }
    chartSemana.update();
}


/////////////////////////////////
// RELOJ PARA LA CONFIGURACIÓN //
/////////////////////////////////
function actualizarReloj() {
    const ahora = new Date();
    // Forzamos el formato de 12 horas con AM/PM como hicimos en las gráficas
    const opciones = { 
        timeZone: 'America/Caracas', 
        hour: '2-digit', 
        minute: '2-digit', 
        second: '2-digit', 
        hour12: true 
    };
    const horaCaracas = ahora.toLocaleTimeString('es-VE', opciones);
    document.getElementById('live-clock').innerHTML = `<i class="fas fa-clock"></i> ${horaCaracas}`;
}

// Actualizar cada segundo
setInterval(actualizarReloj, 1000);
actualizarReloj();

///////////////////////////////////////
// ALERTA DE GUARDADO PARA EL PERFIL //
///////////////////////////////////////
// Detectar si venimos de una actualización exitosa
const urlParams = new URLSearchParams(window.location.search);

if (urlParams.get('actualizado') === 'true') {
    Swal.fire({
        icon: 'success',
        title: '¡Perfil Actualizado!',
        text: 'Tus cambios se han guardado correctamente en el sistema.',
        confirmButtonColor: '#9c1c3f', // Tu vinotinto de Unicasa
        timer: 3000,
        showConfirmButton: false
    }).then(() => {
        // Limpia la URL para que no vuelva a salir si recargas la página
        window.history.replaceState({}, document.title, "/" + window.location.pathname.split("/")[1]);
    });
}

///////////////////////
/// PROXIMA REUNION ///
///////////////////////
function actualizarProximaReunion() {
    if (typeof calendar === 'undefined') return;

    const ahora = new Date();
    const eventos = calendar.getEvents();
    
    // Elementos del DOM
    const txtProgreso = document.getElementById('reunion-progreso');
    const txtProxima = document.getElementById('nombre-reunion');
    const txtTiempo = document.getElementById('tiempo-restante');

    // 1. BUSCAR REUNIONES EN PROGRESO
    const enProgreso = eventos.filter(e => ahora >= e.start && ahora <= e.end);
    
    if (enProgreso.length > 0) {
        txtProgreso.innerText = enProgreso.map(e => e.title).join(' / ');
        txtProgreso.style.color = "#28a745"; // Verde éxito
    } else {
        txtProgreso.innerText = "No hay ninguna en progreso";
        txtProgreso.style.color = "#999";
    }

    // 2. BUSCAR PRÓXIMAS REUNIONES
    const futuros = eventos
        .filter(e => e.start > ahora)
        .sort((a, b) => a.start - b.start);

    if (futuros.length > 0) {
        const proximaHoraInicio = futuros[0].start.getTime();
        const simultaneas = futuros.filter(e => e.start.getTime() === proximaHoraInicio);
        
        txtProxima.innerText = simultaneas.map(e => e.title).join(' / ');
        
        const mins = Math.round((proximaHoraInicio - ahora.getTime()) / 60000);
        if (mins < 60) {
            txtTiempo.innerText = `en ${mins} min`;
            txtTiempo.style.backgroundColor = mins <= 5 ? "#d32f2f" : "#ffc107";
        } else {
            const horas = Math.floor(mins / 60);
            txtTiempo.innerText = `en ${horas}h ${mins % 60}m`;
            txtTiempo.style.backgroundColor = "#6c757d";
        }
    } else {
        txtProxima.innerText = "No hay más reuniones hoy";
        txtTiempo.innerText = "";
    }
}

// Actualización automática cada minuto
setInterval(function() {
    actualizarProximaReunion();
}, 60000); 

// También la llamamos una vez al cargar la página por primera vez
document.addEventListener('DOMContentLoaded', function() {
    // Un pequeño retraso para asegurar que el calendario ya tiene los eventos
    setTimeout(actualizarProximaReunion, 1500); 
});


