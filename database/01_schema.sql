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
    Estado VARCHAR(20) DEFAULT 'Activo'
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
CREATE TABLE TORNEO_GRUPO (
    ID SERIAL PRIMARY KEY,
    Nombre VARCHAR(100) NOT NULL,
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
    Estado VARCHAR(20) DEFAULT 'Activo'
);

CREATE TABLE EQUIPOS (
    ID SERIAL PRIMARY KEY,
    Nombre VARCHAR(100) NOT NULL,
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
    Estado VARCHAR(20) DEFAULT 'Activo'
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

CREATE TABLE PARTIDOS (
    ID SERIAL PRIMARY KEY,
    Torneo_ID INT NOT NULL,
    EQUIPOS_ID_LOCAL INT NOT NULL,
    EQUIPOS_ID_VISITANTE INT NOT NULL,
    Fecha_Partido TIMESTAMP NOT NULL,
    -- Ubicación del partido en el calendario del torneo.
    -- Sin estas tres columnas no hay jornadas, fase de grupos ni eliminatorias.
    Jornada INT,
    Fase VARCHAR(30) DEFAULT 'Regular',
    Grupo VARCHAR(10),
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
