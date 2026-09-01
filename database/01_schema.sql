-- ============================================================
-- 01_schema.sql
-- Definición de tablas (columnas y llaves primarias)
-- Sistema de Torneos - PostgreSQL
--
-- IMPORTANTE sobre mayúsculas: los identificadores se declaran SIN
-- comillas dobles, así que Postgres los pliega a minúsculas. La tabla
-- es "torneo" y la columna "fecha_modificacion". El código de la API y
-- las funciones PL/pgSQL deben usar minúsculas.
-- ============================================================

-- ------------------------------------------------------------
-- Catálogo de disciplinas y modalidades (docs/plans/equipos-jugadores-plan.md,
-- Fase 3 — Eng Review; catálogo unificado en
-- docs/plans/ediciones-catalogo-disciplinas-plan.md, Decisión A1).
--
-- DISCIPLINA reemplaza a TORNEO.Disciplina (antes texto libre). Ya NO
-- tiene columna Tipo: toda disciplina tiene 1+ filas en MODALIDAD siempre
-- (incluso Fútbol: "Fútbol 11", "Fútbol 5"...) y MODALIDAD.Tamano_Equipo
-- es la única fuente de verdad de cómo se inscribe (1 = individual, sin
-- Equipo; 2 = pareja, Equipo autonombrado; >2 = conjunto, Equipo con
-- nombre libre) — ver INSCRIPCIONES_TORNEO abajo y
-- fn_validar_torneo_modalidad en 06_triggers.sql. El Tipo binario
-- ('Equipo'/'Individual') que existía antes no alcanzaba para modelar una
-- disciplina con modalidades de tamaños distintos (ej. Voleibol Pista 6x6
-- vs Playa 2x2) — ver Decision Audit Trail #1 del plan de catálogo.
-- ------------------------------------------------------------
CREATE TABLE DISCIPLINA (
    ID SERIAL PRIMARY KEY,
    Nombre VARCHAR(50) NOT NULL,
    Estado VARCHAR(20) DEFAULT 'Activo',
    -- NULL = no seteado, ordena al final (NULLS LAST) — barra de
    -- navegación tipo SofaScore ordenada por popularidad, no alfabético
    -- (motor-formatos-plantillas-navegacion-plan.md, requerimiento #3).
    Orden_Popularidad INT
);

CREATE TABLE MODALIDAD (
    ID SERIAL PRIMARY KEY,
    Disciplina_ID INT NOT NULL,
    Nombre VARCHAR(30) NOT NULL,
    Tamano_Equipo INT NOT NULL,
    Estado VARCHAR(20) DEFAULT 'Activo'
);

-- Agrupa las ediciones de un mismo torneo a través del tiempo (ej. "Liga
-- Relámpago" agrupa su Edición 1, Edición 2, ...) — docs/plans/torneos-admin-plan.md,
-- Fase 1/3. El nombre mostrado de una edición se COMPONE en el momento
-- ("{Nombre} - Edición {Numero_Edicion}"), nunca se guarda concatenado en
-- TORNEO.Nombre: si el grupo se renombra después, todas sus ediciones
-- reflejan el nombre nuevo sin tener que tocar cada fila de TORNEO.
-- Estado (3B-7, docs/plans/cierre-backlog-todos-plan.md): baja LÓGICA
-- (nunca DELETE — mismo criterio que el resto del esquema), sin cascada.
-- 'Archivado' solo oculta el grupo de /torneo-grupos por default (los
-- selectores de la Pestaña Torneos) — sus TORNEO (ediciones) existentes
-- NO se tocan, siguen consultables/jugables tal cual estaban. Un grupo
-- archivado por error no arrastra nada al reactivarlo.
CREATE TABLE TORNEO_GRUPO (
    ID SERIAL PRIMARY KEY,
    Nombre VARCHAR(100) NOT NULL,
    Estado VARCHAR(20) NOT NULL DEFAULT 'Activo',
    Fecha_Registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Fecha_Modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE TORNEO (
    ID SERIAL PRIMARY KEY,
    Nombre VARCHAR(100) NOT NULL,
    Disciplina_ID INT NOT NULL,
    -- Siempre obligatorio (catálogo unificado — Decisión A1): toda
    -- disciplina tiene 1+ modalidades, así que todo torneo tiene una.
    -- Que la modalidad indicada pertenezca a la disciplina indicada no se
    -- puede expresar con un CHECK simple (cruza tablas) — lo valida
    -- fn_validar_torneo_modalidad en 06_triggers.sql.
    Modalidad_ID INT NOT NULL,
    -- Cada TORNEO es UNA edición de su TORNEO_GRUPO. Numero_Edicion es
    -- único por grupo (unique_edicion_por_grupo, 02_constraints.sql) — lo
    -- asigna el service layer como MAX(Numero_Edicion del grupo) + 1 al
    -- crear una edición nueva, nunca lo tipea el admin a mano.
    Torneo_Grupo_ID INT NOT NULL,
    Numero_Edicion INT NOT NULL DEFAULT 1,
    Fecha_Inicio DATE NOT NULL,
    Fecha_Fin DATE NOT NULL,
    Fecha_Registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Fecha_Modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Estado VARCHAR(20) DEFAULT 'Activo',
    -- Motor de Formatos (motor-formatos-plantillas-navegacion-plan.md,
    -- requerimiento #4). CHECK enum, no tabla catálogo — F1 en el plan,
    -- mismo patrón que Estado en 10+ tablas, 3 valores fijos.
    Formato VARCHAR(20) NOT NULL DEFAULT 'Liga',
    -- Solo relevante si Formato='Liga' — TorneoService valida que no venga
    -- en TRUE para otro formato (fn_validar_torneo_formato_parametros).
    Ida_Vuelta BOOLEAN NOT NULL DEFAULT FALSE,
    -- Solo Formato='Grupos_Playoffs'. NULL en cualquier otro formato.
    Equipos_Por_Grupo INT,
    Clasificados_Por_Grupo INT,
    -- Solo relevante si Formato IN ('Eliminacion','Grupos_Playoffs') y el
    -- bracket llega a tener una ronda de Semifinal (EC-58). Default TRUE:
    -- el usuario confirmó incluirlo (Decisiones confirmadas del plan).
    Incluye_Tercer_Lugar BOOLEAN NOT NULL DEFAULT TRUE
);

-- Disciplina_ID/Modalidad_ID son NOT NULL desde
-- equipos-disciplina-navegacion-plan.md (Decisiones #1/#2/#3): un equipo
-- pertenece a UNA disciplina, y esa es la que se compara contra la del
-- torneo al inscribirlo (InscripcionTorneoService.create). Modalidad_ID es
-- lo que la UI muestra como "Categoria" (Decision #2 = B1) — no hay
-- catalogo de categorias etarias, se reusa el eje que el sistema ya
-- modela y ya valida. Que la modalidad pertenezca a la disciplina lo
-- exige fn_validar_equipo_modalidad (06_triggers.sql), espejo exacto de
-- fn_validar_torneo_modalidad.
CREATE TABLE EQUIPOS (
    ID SERIAL PRIMARY KEY,
    Nombre VARCHAR(100) NOT NULL,
    Disciplina_ID INT NOT NULL,
    Modalidad_ID INT NOT NULL,
    Fecha_Registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Fecha_Modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Estado VARCHAR(20) DEFAULT 'Activo'
);

-- JUGADORES = identidad de la persona (única por Cedula). El perfil por
-- disciplina vive en JUGADOR_PERFIL_DISCIPLINA, abajo — una persona puede
-- jugar Fútbol y Tenis con dos perfiles distintos sobre la misma fila acá.
CREATE TABLE JUGADORES (
    ID SERIAL PRIMARY KEY,
    Nombre VARCHAR(100) NOT NULL,
    Cedula VARCHAR(20) NOT NULL,
    -- NO es UNIQUE a propósito: dos cédulas distintas pueden compartir un
    -- correo familiar. La identidad de la persona es la cédula.
    Correo_Electronico VARCHAR(150) NOT NULL,
    Fecha_Registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Fecha_Modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Estado VARCHAR(20) DEFAULT 'Activo',
    -- nullable a propósito: sin uploader en este plan, acepta una URL. El
    -- frontend cae a iniciales cuando es NULL (motor-formatos-plantillas-
    -- navegacion-plan.md, requerimiento #3 — grid de Plantillas).
    Foto_URL VARCHAR(500)
);

-- Perfil de un jugador dentro de una disciplina. Suspendido es una sanción
-- explícita — el estado Libre/Activo NO se guarda acá, se deriva de si hay
-- una JUGADOR_EQUIPO vigente (ver vw_estado_perfil_disciplina en
-- 04_views.sql y EC-10/EC-11 del plan): guardarlo como columna obliga a
-- recordar actualizarlo en cada agencia-libre y cada traspaso, y una
-- migración futura que toque JUGADOR_EQUIPO sin tocar esta columna la
-- deja desincronizada.
CREATE TABLE JUGADOR_PERFIL_DISCIPLINA (
    ID SERIAL PRIMARY KEY,
    Jugador_ID INT NOT NULL,
    Disciplina_ID INT NOT NULL,
    Suspendido BOOLEAN NOT NULL DEFAULT FALSE,
    Fecha_Registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Fecha_Modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Ancla de una inscripción a un torneo — de un Equipo (Tamano_Equipo>=2)
-- o de un Jugador directo (Tamano_Equipo=1), nunca los dos ni ninguno
-- (chk_inscripcion_exactamente_uno, 02_constraints.sql). Antes de
-- docs/plans/ediciones-catalogo-disciplinas-plan.md (Decisión B1) toda
-- inscripción exigía un Equipo_ID, incluso en disciplinas individuales
-- (se autocreaba un "equipo" fantasma con el nombre del jugador). Ahora
-- una disciplina individual referencia Jugador_Perfil_ID y no crea
-- ninguna fila en EQUIPOS.
CREATE TABLE INSCRIPCIONES_TORNEO (
    ID SERIAL PRIMARY KEY,
    Torneo_ID INT NOT NULL,
    Equipo_ID INT,
    Jugador_Perfil_ID INT,
    Fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Fecha_Registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Fecha_Modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Estado VARCHAR(20) DEFAULT 'Inscrito'
);

-- Membresía de un perfil de disciplina en el roster de un equipo (o, en
-- disciplinas individuales, en su propia inscripción-sin-Equipo) para UN
-- torneo puntual. INSCRIPCIONES_TORNEO ya modela "equipo (o jugador)-en-
-- este-torneo" — es el ancla del roster, por eso JUGADOR_EQUIPO no repite
-- Torneo_ID/Equipo_ID, los hereda de ahí. Una inscripción individual
-- también genera una fila acá (Dorsal=NULL) para que la exclusividad siga
-- funcionando sin reescribirse — ver Decisión B1 del plan de catálogo. La
-- exclusividad "un jugador, un equipo/inscripción, por torneo" la impone
-- el trigger fn_validar_exclusividad_torneo (06_triggers.sql), no un
-- UNIQUE plano, porque Torneo_ID no vive directamente en esta tabla.
CREATE TABLE JUGADOR_EQUIPO (
    ID SERIAL PRIMARY KEY,
    Jugador_Perfil_ID INT NOT NULL,
    Inscripcion_Torneo_ID INT NOT NULL,
    Dorsal INT,
    Fecha_Inicio DATE NOT NULL,
    Fecha_Fin DATE,
    Fecha_Registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Fecha_Modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- 'Traspasado' es distinto de 'Inactivo' genérico: deja en la propia
    -- fila el POR QUÉ terminó la membresía, sin tener que ir a buscarlo en
    -- TRASPASOS.
    Estado VARCHAR(20) DEFAULT 'Activo'
);

-- Trayectoria de traspasos, append-only. Nunca se edita ni se borra una
-- fila — corregir un traspaso mal hecho es un traspaso nuevo en sentido
-- inverso; el original solo se marca Estado='Anulado' como anotación
-- visual (EC-20 del plan), sigue existiendo en la trayectoria.
CREATE TABLE TRASPASOS (
    ID SERIAL PRIMARY KEY,
    Jugador_Perfil_ID INT NOT NULL,
    -- NULL = fichaje desde agencia libre, no un traspaso equipo-a-equipo.
    Inscripcion_Origen_ID INT,
    Inscripcion_Destino_ID INT NOT NULL,
    Dorsal_Nuevo INT,
    Realizado_Por INT NOT NULL,
    Motivo VARCHAR(200),
    Fecha_Traspaso TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Estado VARCHAR(20) DEFAULT 'Completado'
);

-- ------------------------------------------------------------
-- Plantilla Base de un equipo (gestion-avanzada-equipos-control-mesa-plan.md,
-- Decisión D1-C). Banco de candidatos de un equipo ANTES/independiente de
-- cualquier torneo — explícitamente NO autoritativo: no participa de
-- ninguna regla de elegibilidad (esa sigue siendo exclusivamente
-- JUGADOR_EQUIPO, torneo-scoped). Se copia a JUGADOR_EQUIPO recién al
-- inscribir el equipo a un torneo (InscripcionTorneoService), momento en
-- el que sí pasa por fn_validar_exclusividad_torneo como cualquier otra
-- fila. Evita reabrir la Alternativa A de D1 (roster permanente
-- autoritativo, ya rechazada en TODOS.md): acá no hay vigencia propia que
-- conciliar con la de JUGADOR_EQUIPO, solo candidatos.
CREATE TABLE EQUIPO_JUGADOR_BASE (
    ID SERIAL PRIMARY KEY,
    Equipo_ID INT NOT NULL,
    Jugador_Perfil_ID INT NOT NULL,
    -- No autoritativo: valor por defecto al copiar a JUGADOR_EQUIPO. La
    -- unicidad real de dorsal sigue viviendo en uq_dorsal_por_roster_vigente
    -- (torneo-scoped) — acá no se valida unicidad, sería una regla
    -- fantasma que no protege nada real.
    Dorsal_Sugerido INT,
    Fecha_Registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Fecha_Modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Baja lógica ("Quitar" en la UI) — nunca DELETE, mismo criterio que
    -- el resto del esquema.
    Estado VARCHAR(20) DEFAULT 'Activo'
);

-- ------------------------------------------------------------
-- Motor de Tiempos + Control de Mesa en vivo
-- (gestion-avanzada-equipos-control-mesa-plan.md, Fase 3).
-- ------------------------------------------------------------

-- Configuración del cronómetro de un torneo — 1:1 con TORNEO. Tabla
-- propia en vez de columnas en TORNEO (que ya tiene 6 columnas nullable
-- condicionadas a Formato — ver Decision Audit Trail #2 del plan): este
-- es un eje de configuración sin relación con el formato de competición.
CREATE TABLE CONFIGURACION_TIEMPO_TORNEO (
    ID SERIAL PRIMARY KEY,
    Torneo_ID INT NOT NULL,
    Tipo_Cronometro VARCHAR(20) NOT NULL,
    -- Requeridos si Tipo_Cronometro='Periodos', NULL si 'Corrido' — ver
    -- chk_config_tiempo_periodos en 02_constraints.sql.
    Cantidad_Periodos INT,
    Duracion_Periodo_Minutos INT,
    -- Informativo únicamente, incluso en 'Periodos': el cronómetro no lo
    -- cuenta activamente, el entretiempo termina cuando el árbitro
    -- presiona "Iniciar 2do Tiempo".
    Duracion_Descanso_Minutos INT,
    Fecha_Registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Fecha_Modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Hito auditable de un partido (inicio/fin de período, pausa/reanudación,
-- fin de partido) — vocabulario único para ambos tipos de cronómetro. A
-- diferencia de TRASPASOS (append-only), SÍ se permite UPDATE directo
-- sobre Minuto_Reloj/Timestamp_Real (corrección de un hito mal cargado):
-- queda capturado por el listener genérico de AUDITORIA
-- (backend/app/core/auditoria.py), no hace falta duplicar ese mecanismo
-- con un Fecha_Modificacion + trigger dedicado.
CREATE TABLE HITOS_PARTIDO (
    ID SERIAL PRIMARY KEY,
    Partido_ID INT NOT NULL,
    Tipo_Hito VARCHAR(20) NOT NULL,
    -- Solo para Inicio_Periodo/Fin_Periodo (1, 2, 3...). NULL en
    -- cualquier otro tipo — validado por fn_validar_hito_partido.
    Numero_Periodo INT,
    -- Momento real de reloj en que se presionó el botón — fuente de
    -- verdad para vw_duracion_partido.
    Timestamp_Real TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- El minuto "de juego" que mostraba el cronómetro en ese instante —
    -- redundante respecto a Timestamp_Real a propósito (tiempo agregado,
    -- pausas): es el número que un árbitro reconoce y quiere corregir sin
    -- razonar sobre timestamps.
    Minuto_Reloj INT,
    Registrado_Por INT NOT NULL,
    Fecha_Registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------
-- Motor de Formatos de Competición (motor-formatos-plantillas-navegacion-
-- plan.md, requerimiento #4). FASE formaliza lo que antes era
-- PARTIDOS.Fase/Grupo (texto libre). Liga/Eliminación → 1 FASE. Grupos +
-- Playoffs → 2 FASES (Orden 1 'Grupos', Orden 2 'Eliminacion', esta
-- última creada recién al "Generar Playoffs" — ver Decisión G1).
-- ------------------------------------------------------------
CREATE TABLE FASE (
    ID SERIAL PRIMARY KEY,
    Torneo_ID INT NOT NULL,
    Nombre VARCHAR(50) NOT NULL,
    Tipo VARCHAR(20) NOT NULL,
    Orden INT NOT NULL,
    Estado VARCHAR(20) NOT NULL DEFAULT 'Pendiente',
    Fecha_Registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Fecha_Modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Grupo dentro de una FASE Tipo='Grupos' ("A", "B", "C"...).
CREATE TABLE GRUPO (
    ID SERIAL PRIMARY KEY,
    Fase_ID INT NOT NULL,
    Nombre VARCHAR(10) NOT NULL,
    Fecha_Registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Resultado del sorteo de grupos: qué equipo (vía su inscripción a ESTE
-- torneo) cayó en qué grupo. Ancla en INSCRIPCIONES_TORNEO, no en
-- EQUIPOS directo — mismo criterio que JUGADOR_EQUIPO (reusa el ancla
-- "equipo-en-este-torneo" ya existente).
--
-- Orden_Manual (3A-12, docs/plans/cierre-backlog-todos-plan.md — EC-51 de
-- motor-formatos-plantillas-navegacion-plan.md, "enfrentamiento directo
-- primero; si persiste el empate, resolución manual del admin"): NULL por
-- default (orden automático de vw_tabla_posiciones sin tocar). Un admin
-- lo setea SOLO para desempatar — vw_tabla_posiciones lo usa como
-- desempate de ÚLTIMA instancia, DESPUÉS de PTS/DG/GF, así que nunca
-- puede promover a un equipo por encima de otro con más puntos.
CREATE TABLE GRUPO_EQUIPO (
    ID SERIAL PRIMARY KEY,
    Grupo_ID INT NOT NULL,
    Inscripcion_Torneo_ID INT NOT NULL,
    Orden_Manual INT,
    Fecha_Registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Auditoría append-only de cada sorteo (bracket o grupos), mismo patrón
-- que TRASPASOS: rehacer un sorteo no borra el anterior, lo marca
-- 'Rehecho' e inserta uno nuevo 'Completado' (EC-52).
CREATE TABLE SORTEOS (
    ID SERIAL PRIMARY KEY,
    Fase_ID INT NOT NULL,
    Realizado_Por INT NOT NULL,
    Semilla VARCHAR(50),
    Fecha_Sorteo TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Estado VARCHAR(20) NOT NULL DEFAULT 'Completado'
);

CREATE TABLE PARTIDOS (
    ID SERIAL PRIMARY KEY,
    Torneo_ID INT NOT NULL,
    -- Nullable: un partido de ronda 2+ de un bracket de Eliminación se
    -- crea ANTES de saber quién lo juega ("Ganador Partido 3 vs Ganador
    -- Partido 4") — nace con ambos NULL, el trigger de propagación del
    -- bracket los completa cuando el partido anterior termina (Decisión
    -- Eng #13 del plan).
    EQUIPOS_ID_LOCAL INT,
    EQUIPOS_ID_VISITANTE INT,
    Fecha_Partido TIMESTAMP NOT NULL,
    -- Ubicación del partido en el calendario del torneo.
    -- Sin estas tres columnas no hay jornadas, fase de grupos ni eliminatorias.
    Jornada INT,
    -- Fase/Grupo (texto libre) se mantienen por compatibilidad con el alta
    -- manual de partidos ya existente (POST /partidos, PartidosAdmin) —
    -- el motor de formatos nuevo escribe Fase_ID/Grupo_ID/Ronda_Nombre en
    -- su lugar (columnas de abajo) y esas dos son las que leen
    -- vw_tabla_posiciones/vw_resultados_partidos rescopadas. Convergerlas
    -- en una sola representación es trabajo de un plan aparte (ver
    -- TODOS.md) — acá conviven sin pisarse: un partido creado a mano
    -- sigue usando Fase (texto), uno generado por el motor usa Fase_ID.
    Fase VARCHAR(30) DEFAULT 'Regular',
    Grupo VARCHAR(10),
    -- Motor de Formatos — estructura real (Fase_ID reemplaza a Fase/Grupo
    -- texto para todo partido generado por el motor).
    Fase_ID INT,
    Grupo_ID INT,
    -- "Octavos de Final", "Semifinal", "Tercer Lugar"... — denormalizado,
    -- se calcula al sortear el bracket y se graba acá para no tener que
    -- recalcularlo con lógica escondida en el cliente cada vez que se
    -- muestra.
    Ronda_Nombre VARCHAR(30),
    -- Encadenamiento de bracket: a qué partido avanza el GANADOR de este.
    Partido_Siguiente_ID INT,
    Slot_Siguiente VARCHAR(10),
    -- Partido por el 3er/4to lugar (confirmado en el plan): a qué partido
    -- avanza el PERDEDOR — solo lo usan las 2 semifinales, encadenamiento
    -- paralelo e independiente del de arriba.
    Partido_Perdedor_Siguiente_ID INT,
    Slot_Perdedor_Siguiente VARCHAR(10),
    -- Desempate manual para un partido de Eliminación empatado en goles
    -- (penales/tiempo extra/decisión arbitral) — el sistema registra
    -- QUIÉN ganó, no CÓMO, mismo nivel de detalle que TRASPASOS.Motivo.
    Ganador_Desempate_ID INT,
    -- Ganador de un partido "Corrido" (Tenis/Pádel — sin marcador de
    -- goles en absoluto). Deliberadamente DISTINTA de Ganador_Desempate_ID:
    -- esa columna resuelve un empate de goles dentro de un bracket de
    -- Eliminación (fn_validar_partido_eliminacion_desempate, atado a
    -- FASE.Tipo); esta se valida contra CONFIGURACION_TIEMPO_TORNEO.Tipo_Cronometro
    -- (fn_validar_ganador_corrido, 06_triggers.sql) — significan cosas
    -- distintas, reusar la misma columna sería más corto pero engañoso.
    Ganador_Corrido_ID INT,
    -- Árbitro asignado a este partido. Nullable: un partido puede no tener
    -- árbitro asignado todavía. Sin esto, "el árbitro solo ve/carga SUS
    -- partidos asignados" (roles-3-modulos-plan.md, Fase 1) no es
    -- construible. Un solo árbitro por partido a propósito — ver D6 en
    -- ese plan.
    ARBITRO_ID INT,
    Fecha_Registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Fecha_Modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Estado VARCHAR(20) DEFAULT 'Programado'
);

CREATE TABLE EVENTOS (
    ID SERIAL PRIMARY KEY,
    Nombre VARCHAR(50) NOT NULL,
    Descripcion VARCHAR(200),
    Fecha_Registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Fecha_Modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Estado VARCHAR(20) DEFAULT 'Activo'
);

-- ------------------------------------------------------------
-- Autenticación
--
-- No tiene FK hacia el dominio de torneos: un usuario es quien opera el
-- sistema, no un participante. Si más adelante hace falta ligar un
-- usuario a un jugador o a un equipo, se agrega ahí la referencia.
--
-- Password_Hash guarda el HASH, nunca la contraseña. El nombre de la
-- columna lo deja explícito para que nadie escriba texto plano por
-- descuido. 255 caracteres cubren bcrypt (60), scrypt y argon2.
--
-- Username se guarda siempre en minúsculas (lo fuerza un CHECK en
-- 02_constraints.sql). Así "Gabo" y "gabo" no pueden ser dos cuentas
-- distintas, que es el error clásico de un login con UNIQUE simple.
-- ------------------------------------------------------------
CREATE TABLE USUARIOS (
    ID SERIAL PRIMARY KEY,
    Username VARCHAR(50) NOT NULL,
    Nombre VARCHAR(100) NOT NULL,
    Password_Hash VARCHAR(255) NOT NULL,
    Rol VARCHAR(20) NOT NULL DEFAULT 'Publico',
    Fecha_Registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Fecha_Modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Estado VARCHAR(20) DEFAULT 'Activo'
);

-- Bitacora de INTENTOS de inicio de sesion (exitosos y fallidos).
--
-- Append-only: una fila se escribe una vez y no se toca nunca mas. Por eso
-- es la unica tabla sin Fecha_Modificacion — una fecha de modificacion en
-- un registro de auditoria no seria un dato util, seria una senal de que
-- alguien lo edito.
--
-- Username se guarda TAL COMO SE TIPEO y es NOT NULL, mientras que
-- Usuario_ID es nullable: el caso mas interesante de auditar es justamente
-- el intento contra un usuario que no existe, donde no hay ID que
-- referenciar. Nunca se guarda la contrasena probada, ni siquiera hasheada.
--
-- La FK a USUARIOS va sin ON DELETE (NO ACTION), igual que
-- TRASPASOS.Realizado_Por: es un rastro de auditoria, no debe poder
-- desaparecer porque alguien borro la cuenta.
CREATE TABLE ACCESOS (
    ID SERIAL PRIMARY KEY,
    Usuario_ID INT,
    Username VARCHAR(50) NOT NULL,
    Exitoso BOOLEAN NOT NULL,
    -- NULL si Exitoso. Si no: 'credenciales' o 'inactivo' (chk_accesos_motivo)
    Motivo VARCHAR(30),
    -- 45 = largo maximo de una IPv6 en texto
    IP VARCHAR(45),
    User_Agent VARCHAR(255),
    Fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE EVENTOS_PARTIDO (
    ID SERIAL PRIMARY KEY,
    PARTIDOS_ID INT NOT NULL,
    JUGADOR_ID INT NOT NULL,
    -- EQUIPO_ID = el equipo AL QUE PERTENECIA el jugador en ese partido.
    -- Es obligatorio y no se deduce: deducirlo desde JUGADOR_EQUIPO hacía
    -- que un jugador con historial en ambos equipos contara su gol dos veces.
    -- Para 'Autogol' el gol se acredita al rival; eso lo resuelve la vista
    -- vw_goles_acreditados, no esta columna, que guarda el dato crudo.
    EQUIPO_ID INT NOT NULL,
    EVENTOS_ID INT NOT NULL,
    -- Solo para el evento 'Cambio': el jugador que ENTRA.
    -- JUGADOR_ID es entonces el que sale.
    JUGADOR_ID_ENTRA INT,
    MINUTO INT NOT NULL,
    Fecha_Registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Fecha_Modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Estado VARCHAR(20) DEFAULT 'Registrado'
);

-- Auditoria de cambios: alta, modificacion o baja logica de CUALQUIER
-- entidad del sistema (torneos, equipos, jugadores, partidos, usuarios...).
-- La llena sola un event listener de SQLAlchemy (backend/app/core/auditoria.py),
-- no un INSERT a mano por tabla — por eso Tabla es texto libre en vez de
-- 18 FKs, una por entidad posible.
--
-- Append-only, igual que ACCESOS: sin Fecha_Modificacion (ver el
-- comentario de esa tabla arriba, mismo razonamiento).
--
-- Datos_Anteriores/Datos_Nuevos son JSONB: el "antes" y el "despues" de
-- las columnas que cambiaron (para 'crear', solo Datos_Nuevos con el
-- estado inicial completo; para 'eliminar', solo Datos_Anteriores).
-- Password_Hash nunca aparece en texto plano ahi adentro, mismo criterio
-- que "nunca se guarda la contrasena probada" de ACCESOS.
--
-- La FK a USUARIOS va sin ON DELETE, igual que ACCESOS.Usuario_ID: es un
-- rastro de auditoria, no debe poder desaparecer porque se borro la cuenta
-- (y en este esquema ninguna cuenta se borra de verdad: es baja logica).
CREATE TABLE AUDITORIA (
    ID SERIAL PRIMARY KEY,
    Usuario_ID INT,
    Tabla VARCHAR(50) NOT NULL,
    Registro_ID INT NOT NULL,
    -- 'crear' | 'modificar' | 'eliminar' (chk_auditoria_accion)
    Accion VARCHAR(20) NOT NULL,
    Datos_Anteriores JSONB,
    Datos_Nuevos JSONB,
    -- 45 = largo maximo de una IPv6 en texto
    IP VARCHAR(45),
    User_Agent VARCHAR(255),
    Fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
