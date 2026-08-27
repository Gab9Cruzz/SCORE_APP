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
-- Fase 3 — Eng Review).
--
-- DISCIPLINA reemplaza a TORNEO.Disciplina (antes texto libre). Tipo
-- distingue disciplinas de equipo (Fútbol: sin modalidad) de individuales
-- (Tenis, Pádel: requieren MODALIDAD en el torneo — ver TORNEO abajo y
-- fn_validar_torneo_modalidad en 06_triggers.sql).
-- MODALIDAD.Tamano_Equipo fija cuántos jugadores admite un "equipo" en esa
-- modalidad (1 = individual, 2 = dobles/pádel) — EC-6 del plan bloquea el
-- exceso en el service layer (P2), no acá.
-- ------------------------------------------------------------
CREATE TABLE DISCIPLINA (
    ID SERIAL PRIMARY KEY,
    Nombre VARCHAR(50) NOT NULL,
    Tipo VARCHAR(20) NOT NULL,
    Estado VARCHAR(20) DEFAULT 'Activo'
);

CREATE TABLE MODALIDAD (
    ID SERIAL PRIMARY KEY,
    Disciplina_ID INT NOT NULL,
    Nombre VARCHAR(30) NOT NULL,
    Tamano_Equipo INT NOT NULL,
    Estado VARCHAR(20) DEFAULT 'Activo'
);

CREATE TABLE TORNEO (
    ID SERIAL PRIMARY KEY,
    Nombre VARCHAR(100) NOT NULL,
    Disciplina_ID INT NOT NULL,
    -- NULL si DISCIPLINA.Tipo='Equipo', obligatorio si Tipo='Individual'.
    -- No se puede expresar con un CHECK simple (cruza tablas) — lo valida
    -- fn_validar_torneo_modalidad en 06_triggers.sql.
    Modalidad_ID INT,
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

CREATE TABLE INSCRIPCIONES_TORNEO (
    ID SERIAL PRIMARY KEY,
    Torneo_ID INT NOT NULL,
    Equipo_ID INT NOT NULL,
    Fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Fecha_Registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Fecha_Modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Estado VARCHAR(20) DEFAULT 'Inscrito'
);

-- Membresía de un perfil de disciplina en el roster de un equipo para UN
-- torneo puntual. INSCRIPCIONES_TORNEO ya modela "equipo-en-este-torneo"
-- (Torneo_ID + Equipo_ID, único por par) — es el ancla del roster, por eso
-- JUGADOR_EQUIPO no repite Torneo_ID/Equipo_ID, los hereda de ahí. La
-- exclusividad "un jugador, un equipo, por torneo" la impone el trigger
-- fn_validar_exclusividad_torneo (06_triggers.sql), no un UNIQUE plano,
-- porque Torneo_ID no vive directamente en esta tabla.
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
