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

CREATE TABLE TORNEO (
    ID SERIAL PRIMARY KEY,
    Nombre VARCHAR(100) NOT NULL,
    Disciplina VARCHAR(50) NOT NULL,
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

CREATE TABLE JUGADORES (
    ID SERIAL PRIMARY KEY,
    Nombre VARCHAR(100) NOT NULL,
    Fecha_Registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Fecha_Modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Estado VARCHAR(20) DEFAULT 'Activo'
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

CREATE TABLE JUGADOR_EQUIPO (
    ID SERIAL PRIMARY KEY,
    JUGADOR_ID INT NOT NULL,
    EQUIPO_ID INT NOT NULL,
    Dorsal INT,
    Fecha_Inicio DATE NOT NULL,
    Fecha_Fin DATE,
    Fecha_Registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Fecha_Modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Estado VARCHAR(20) DEFAULT 'Activo'
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
