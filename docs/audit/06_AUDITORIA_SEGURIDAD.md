# 06 — Auditoría de seguridad

Fase VI, con OWASP Top 10 (2021) y OWASP API Security Top 10 (2023) como referencia.

> **Método.** Revisión de código y configuración. No se hizo explotación ni pruebas dinámicas: la API no pudo levantarse y no se atacó ningún servicio. "Confirmado (estático)" significa que la debilidad se lee directamente en el código citado; conviene reproducirla con una prueba automatizada antes de corregirla (así está planteado en cada tarea).

## 1. Lo que está bien resuelto

Antes de los hallazgos, lo que no hay que tocar:

| Control | Cómo está implementado |
|---|---|
| Contraseñas | bcrypt con sal por contraseña, truncado explícito a 72 bytes, verificación que no lanza ante un hash corrupto (`core/security.py:29-41`) |
| Estado fresco en cada petición | El usuario se relee de la base en cada llamada: una baja, un cambio de rol o una licencia revocada surten efecto de inmediato aunque el token siga vigente (`api/deps.py:23-70`) |
| Autorización centralizada | Dependencias de rol y de acceso a torneo; el árbitro limitado a su partido en el servicio |
| Escalada de privilegios | La escritura de usuarios exige `AdminGeneral` literal; el comentario del router explica el fallo real que lo motivó (`api/routes/usuarios.py:19-32`) |
| Auto-bloqueo | Un administrador no puede cambiar su rol, desactivarse ni revocarse la licencia |
| Datos personales | Cédula y correo ausentes para anónimos mediante esquemas de salida distintos (`schemas/jugador.py:40-57`) |
| Enumeración de torneos | Torneo no publicado responde 404, igual que uno inexistente |
| Inyección SQL | Todas las consultas son ORM o `text()` con parámetros. La única interpolación (`SET LOCAL lock_timeout`) usa un entero de configuración (`services/evento_partido.py:240`) |
| XSS | Sin `dangerouslySetInnerHTML`; React escapa todo. Los logos se neutralizan si no son `https://`, en el esquema y otra vez en la vista SQL |
| CSRF | No aplica: el token viaja en la cabecera `Authorization`, no en una cookie |
| Secreto del JWT | Obligatorio, sin valor por defecto en el código ni en el compose |
| Trazabilidad | Bitácora de accesos (éxitos y fallos con motivo) y auditoría de cambios atómica con cada escritura |
| Contenedor | La API corre con un usuario sin privilegios (`backend/Dockerfile:13-16`); `.dockerignore` excluye `.env` |
| Secretos en el repositorio | Ninguno versionado; `.env` ignorado. Verificado con `git ls-files` y una búsqueda de patrones |

## 2. Hallazgos

### SEC-01 — El límite de intentos de login se puede eludir

- **OWASP:** A07 Fallos de identificación y autenticación · API2 Autenticación rota.
- **Tipo:** Confirmado (estático). **Severidad:** Alto.
- **Ubicación:** `backend/app/services/usuario.py:136-152`, `backend/app/repositories/acceso.py:87-108`, `backend/app/repositories/usuario.py:11-14`, `backend/app/core/http.py:24-27`.
- **Descripción:** el contador de fallos se indexa por el par (nombre de usuario, IP). Dos componentes de esa clave los controla el atacante:
  1. **Nombre de usuario sin normalizar.** El contador compara el texto exacto que llegó (`Acceso.username == username`), pero la cuenta se busca con `strip().lower()`. `admin`, `Admin`, `ADMIN` y `admin ` apuntan a la misma cuenta y tienen contadores separados. Solo con mayúsculas y minúsculas, un nombre de cinco letras ofrece 32 variantes.
  2. **IP tomada de `X-Forwarded-For`.** Se usa el primer valor de la cabecera sin comprobar que venga de un proxy de confianza. Enviando una IP distinta en cada petición, el contador nunca llega a 5. Las propias pruebas eligen su IP así (`backend/tests/test_rate_limiting_login.py:19`).
- **Impacto:** fuerza bruta ilimitada contra cualquier cuenta. Combinado con `SEC-02`, la cuenta más expuesta es la del administrador.
- **Recomendación:** normalizar el nombre antes de contar y de registrar; aceptar `X-Forwarded-For` solo desde proxies configurados; añadir un tope por cuenta con retardo creciente. `TASK-004`.

### SEC-02 — Credenciales y secretos por defecto

- **OWASP:** A05 Configuración de seguridad incorrecta · API8.
- **Tipo:** Confirmado (estático). **Severidad:** Alto (Crítico si se despliega sin cambiarlos).
- **Ubicación:** `backend/app/core/config.py:20-21` (`admin` / `admin1234`), `infrastructure/docker-compose.yml:22` (`POSTGRES_PASSWORD: 1234`), `:25` (puerto 5432 publicado), `:51` (`ADMIN_PASSWORD` con valor por defecto), `backend/.env.example` (`JWT_SECRET_KEY=change-me-please-do-not-use-in-production`).
- **Descripción:** si la tabla de usuarios está vacía, la API crea un `AdminGeneral` con la contraseña por defecto. Nada obliga a cambiarla. La base queda accesible desde la red del anfitrión con usuario `postgres` y clave `1234`. Un secreto de JWT copiado del ejemplo sería aceptado: no hay validación de longitud ni de valores conocidos.
- **Impacto:** control total de la aplicación y de la base con credenciales públicas.
- **Recomendación:** en modo producción, negarse a arrancar si la contraseña del administrador o el secreto son los de ejemplo o demasiado cortos; no publicar el puerto de la base; obligar a cambiar la contraseña inicial. `TASK-005`, `TASK-050`.

### SEC-03 — Sesión: token en `localStorage`, sin revocación

- **OWASP:** A07 · API2.
- **Tipo:** Confirmado (estático). **Severidad:** Medio.
- **Ubicación:** `frontend/src/api/client.ts:6-14`, `frontend/src/auth/AuthContext.tsx:85-89`, `backend/app/core/security.py:44-47`.
- **Descripción:** el JWT (120 minutos) vive en `localStorage`, legible por cualquier script de la página. No hay cabeceras de seguridad (CSP, `X-Content-Type-Options`, `Referrer-Policy`), ni renovación, ni forma de invalidar un token: cerrar sesión solo lo borra del navegador y cambiar la contraseña no lo anula (decisión registrada en `TODOS.md`).
- **Mitigación presente:** el usuario se relee en cada petición, así que desactivar la cuenta o revocar la licencia corta el acceso al instante.
- **Recomendación:** CSP estricta servida por el proxy; marca de "tokens válidos desde" por usuario que se actualice al cambiar la contraseña o al cerrar sesión en todos los dispositivos. `TASK-033`, `TASK-049`.

### SEC-04 — Los catálogos globales no están acotados por torneo

- **OWASP:** A01 Control de acceso roto · API1 (autorización a nivel de objeto) y API5 (a nivel de función).
- **Tipo:** Confirmado (estático). **Severidad:** Medio (Alto si conviven organizaciones distintas).
- **Ubicación y alcance:** cualquier cuenta `TorneoAdmin`, tenga los torneos que tenga asignados, puede:

  | Acción | Ruta | Consecuencia |
  |---|---|---|
  | Renombrar o **archivar** cualquier grupo de torneos | `api/routes/torneo_grupos.py:39-50`, `schemas/torneo_grupo.py:29-43` | Archivar oculta todas sus ediciones y bloquea la operación de sus partidos |
  | Editar o dar de baja cualquier equipo | `api/routes/equipos.py:46-60` | Cambiar nombre o escudo, o desactivar un equipo que juega en torneos ajenos |
  | Editar o dar de baja cualquier jugador; suspender perfiles | `api/routes/jugadores.py:84-98`, `api/routes/perfiles.py:34-57` | Alterar cédula o nombre; suspender a un rival |
  | Crear, renombrar o dar de baja tipos de evento | `api/routes/eventos.py:27-41` | Ver `FUN-14`: marcadores a cero en todo el sistema |
  | Activar o desactivar disciplinas y modalidades | `api/routes/disciplinas.py:70-78`, `api/routes/modalidades.py:29-37` | Impedir crear torneos nuevos de un deporte |

- **Contexto:** el diseño trata estos recursos como catálogos compartidos, y `TODOS.md` ya anota que los listados no se filtran por asignación (prioridad P3). El riesgo depende del modelo de negocio: con un solo organizador es bajo; con licencias vendidas a organizadores distintos, es un fallo de aislamiento.
- **Recomendación:** tipos de evento, disciplinas y modalidades solo para `AdminGeneral`; grupos de torneo con la misma comprobación de acceso que sus ediciones; equipos y jugadores editables solo por quien administra algún torneo donde participan. `TASK-013`.

### SEC-05 — Exposición de datos personales

- **OWASP:** A01 · API3 (autorización a nivel de propiedad).
- **Tipo:** Confirmado (estático). **Severidad:** Medio.
- **Ubicación:** `backend/app/repositories/jugador.py:28-29`, `backend/app/api/routes/jugadores.py:39-81`.
- **Descripción:**
  1. **Búsqueda pública por cédula.** `GET /jugadores?q=` no exige sesión y busca en nombre **o cédula**. La respuesta anónima no incluye la cédula, pero permite confirmar a quién pertenece un número (se busca la cédula, se obtiene el nombre) y admite coincidencias parciales.
  2. **Proyección completa para cualquier cuenta.** Basta estar autenticado, con cualquier rol, para recibir cédula y correo. El rol `Publico`, definido como "solo lectura, igual que un visitante", y el `Arbitro` los ven.
- **Recomendación:** buscar por cédula solo para roles de gestión; devolver cédula y correo solo a `TorneoAdmin` y `AdminGeneral`. `TASK-014`.

### SEC-06 — Los errores exponen detalles internos y ocultan fallos reales

- **OWASP:** A05 · A09 Fallos de registro y monitorización · API8.
- **Tipo:** Confirmado (estático). **Severidad:** Medio.
- **Ubicación:** `backend/app/exceptions/handlers.py:21-39,108-117`.
- **Descripción:** cualquier error del controlador de base de datos se devuelve como 400 con la primera línea del mensaje de PostgreSQL; los de integridad, como 409 con el nombre de la tabla y de la restricción. Esto incluye caídas de conexión, tiempos de espera y errores de sintaxis. Nada se registra en el servidor. Además, la sustitución por un mensaje amable solo reconoce el texto en inglés (`duplicate key value violates unique constraint`); con PostgreSQL en español el mensaje crudo pasa tal cual.
- **Impacto:** fuga moderada de estructura interna y, sobre todo, incidentes invisibles: un fallo de la base parece un error del usuario.
- **Recomendación:** clasificar por SQLSTATE, responder 500 genérico con identificador de correlación para lo inesperado y registrar el detalle. `TASK-015`.

### SEC-07 — Sub-recursos de torneos no publicados visibles sin sesión

- **OWASP:** A01 · API1.
- **Tipo:** Confirmado (estático), en parte decisión documentada. **Severidad:** Bajo.
- **Ubicación:** `api/routes/partidos.py:154-156,263-281,354-357`, `api/routes/eventos_partido.py:32-43`, `api/routes/inscripciones.py:31-61`, `api/routes/plantillas.py:36-66`, `api/routes/traspasos.py:33-57`, `api/routes/grupos.py:21-24`, `api/routes/torneo_grupos.py:12-36`.
- **Descripción:** el detalle, el listado, las estadísticas y la llave de un torneo respetan `publicado`. Sus partidos por ID, cronómetro, convocatorias, eventos, inscripciones, plantillas y traspasos no. `GET /torneo-grupos` lista sin sesión todas las ediciones, con su marca `publicado`. El plan del portal decidió dejar pública "la superficie de partido" (C17); el resto no parece una decisión.
- **Impacto:** un torneo en borrador se puede reconstruir recorriendo identificadores.
- **Recomendación:** aplicar la misma comprobación de visibilidad resolviendo el torneo desde cada recurso. `TASK-014`.

### SEC-08 — Caché pública sin límite y sin limitación de peticiones

- **OWASP:** API4 Consumo de recursos sin restricción.
- **Tipo:** Confirmado (estático). **Severidad:** Medio.
- **Ubicación:** `backend/app/services/feed.py:22-23,64-68,92`; ausencia de limitación de peticiones fuera del login.
- **Descripción:** ver `BE-08`. Además, los endpoints públicos más costosos (cronómetro cada 5 s, estadísticas sobre vistas, `GET /partidos` con consultas N+1) no tienen ningún freno.
- **Recomendación:** caché acotada y limitación de peticiones en el proxy inverso. `TASK-030`, `TASK-049`.

### SEC-09 — El árbitro puede modificar más de lo que su rol necesita

- **OWASP:** API3.
- **Tipo:** Confirmado (estático). **Severidad:** Bajo.
- **Ubicación:** `backend/app/schemas/partido.py:50-96`, `backend/app/services/partido.py:95-111`.
- **Descripción:** en su partido, un árbitro puede cambiar `arbitro_id` (cederlo a otra cuenta), `fecha_partido`, `fase`, `grupo`, `ganador_corrido_id` y los campos de desempate. `arbitro_id` no se valida contra el rol de la cuenta destino.
- **Recomendación:** esquema de edición propio para el árbitro. `TASK-021`.

### Hallazgos menores e informativos

| ID | OWASP | Tipo | Severidad | Hallazgo | Evidencia | Tarea |
|---|---|---|---|---|---|---|
| SEC-10 | A05 | Confirmado (estático) | Bajo | CORS `*` por defecto en código y compose. Con token en cabecera el impacto es limitado, pero cualquier sitio puede leer la API pública | `core/config.py:45`, `docker-compose.yml:53` | `TASK-050` |
| SEC-11 | A04 | Confirmado (estático) | Bajo | Entradas sin límites de longitud ni de tamaño de lista; `skip`/`limit` negativos llegan a la base; `foto_url` sin exigir `https://` | `BE-07` | `TASK-029` |
| SEC-12 | A06 | Confirmado (ejecutado) / No verificable | Medio | `npm audit`: 8 vulnerabilidades (6 altas, 2 moderadas) en `vite`, `vitest`, `@vitest/mocker`, `undici`, `js-yaml`, `brace-expansion`, `source-map-js` y `@redocly/openapi-core`. Todas pertenecen a la cadena de desarrollo y pruebas, no al código que llega al navegador (dependencias de ejecución: `react`, `react-dom`, `react-router-dom`, `@tanstack/react-query`, `openapi-fetch`). **Backend no verificable**: `pip-audit` no está instalado y no se instaló nada | salida de `npm audit`; `frontend/package.json` | `TASK-056` |
| SEC-13 | A07 | Riesgo potencial | Bajo | Enumeración de usuarios por tiempo de respuesta: bcrypt solo se calcula si la cuenta existe | `services/usuario.py:154-156` | `TASK-004` |
| SEC-14 | A07 | Confirmado (estático) | Bajo | Política de contraseñas mínima: 8 caracteres, sin lista de contraseñas comunes; sin cambio propio (`FUN-13`) | `schemas/usuario.py:27-32` | `TASK-033` |
| SEC-15 | A09 | Confirmado (estático) | Bajo | Bitácoras: IP falsificable (advertido en el código); purga a los 30 días que solo corre al arrancar; datos personales en claro dentro del JSON de auditoría | `core/http.py:13-16`, `main.py:46-103`, `core/auditoria.py:58` | `TASK-050`, `TASK-053` |
| SEC-16 | A05 | Informativo | — | Documentación interactiva de la API (`/docs`, `/openapi.json`) pública | `main.py:116-121` | `TASK-050` |
| SEC-17 | A05 | Confirmado (estático) | Bajo | La imagen incluye dependencias de prueba, no fija la imagen base por resumen y no define `HEALTHCHECK` | `backend/Dockerfile`, `requirements.txt` | `TASK-049` |
| SEC-18 | A02 | Riesgo potencial | Medio | Sin TLS: la API se sirve en HTTP en el puerto 8000 y el frontend apunta a `http://127.0.0.1:8000`. Token y contraseñas viajarían en claro si se expone así | `docker-compose.yml`, `frontend/.env.example` | `TASK-049` |

## 3. Cobertura frente a OWASP

### OWASP Top 10 (2021)

| Categoría | Estado | Referencias |
|---|---|---|
| A01 Control de acceso roto | Hallazgos medios | `SEC-04`, `SEC-05`, `SEC-07`, `SEC-09` |
| A02 Fallos criptográficos | Correcto en reposo (bcrypt); pendiente en tránsito | `SEC-18` |
| A03 Inyección | Sin hallazgos | — |
| A04 Diseño inseguro | Menor | `SEC-11` |
| A05 Configuración incorrecta | Hallazgo alto | `SEC-02`, `SEC-06`, `SEC-10`, `SEC-16`, `SEC-17` |
| A06 Componentes vulnerables | Solo herramientas de desarrollo; backend sin verificar | `SEC-12` |
| A07 Identificación y autenticación | Hallazgo alto | `SEC-01`, `SEC-03`, `SEC-13`, `SEC-14` |
| A08 Integridad de software y datos | No verificable: no hay CI ni firma de artefactos | `OPS-03` |
| A09 Registro y monitorización | Insuficiente | `SEC-06`, `SEC-15`, `OPS-06` |
| A10 SSRF | No aplica: el servidor no hace peticiones salientes | — |

### OWASP API Security Top 10 (2023)

| Categoría | Estado | Referencias |
|---|---|---|
| API1 Autorización a nivel de objeto | Parcial | `SEC-04`, `SEC-07` |
| API2 Autenticación | Parcial | `SEC-01`, `SEC-03` |
| API3 Autorización a nivel de propiedad | Parcial | `SEC-05`, `SEC-09`, `FUN-04` |
| API4 Consumo de recursos | Parcial | `SEC-08`, `SEC-11`, `BE-01` |
| API5 Autorización a nivel de función | Parcial | `SEC-04` |
| API6 Flujos de negocio sensibles | Sin hallazgos relevantes | — |
| API7 SSRF | No aplica | — |
| API8 Configuración | Hallazgo alto | `SEC-02`, `SEC-10`, `SEC-16` |
| API9 Inventario | Correcto: una sola versión, OpenAPI completo | — |
| API10 Consumo inseguro de APIs | No aplica | — |

## 4. Lo que no se pudo verificar

| Aspecto | Motivo | Cómo verificarlo |
|---|---|---|
| Explotación real de `SEC-01`, `SEC-04`, `SEC-05`, `SEC-07` | API no levantada | Pruebas de autorización del backlog (`TASK-048`) |
| Vulnerabilidades de dependencias de Python | `pip-audit` no instalado | Ejecutarlo en CI (`TASK-056`) |
| Cabeceras de seguridad efectivas | No hay despliegue | Tras `TASK-049` |
| Permisos del usuario de base de datos | Sin acceso a una base | Revisión al crear el entorno de producción |
| Contenido de los `.env` locales | No se abrieron: contienen secretos del propietario | — |

## 5. Prioridad recomendada

1. `SEC-01` y `SEC-02`: antes de exponer la aplicación a Internet.
2. `SEC-18`, `SEC-03`, `SEC-08`: se resuelven juntas al poner un proxy inverso con TLS delante.
3. `SEC-04`, `SEC-05`, `SEC-07`: antes de admitir a un segundo organizador.
4. `SEC-06`: junto con la observabilidad.
5. El resto, en el ciclo de calidad.
