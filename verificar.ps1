# Verificación completa del proyecto — lo que hay que ver en verde antes
# de dar por terminado un cambio.
#
# Uso:  .\verificar.ps1
#
# Corre, en orden y frenando en el primer fallo:
#   1. Tests de backend (pytest) — reconstruye torneos_mvp_test desde
#      /database, así que también valida que el esquema SQL sea coherente.
#      Incluye tests/test_scripts_sql.py, que corre los scripts de demo y
#      catálogo contra una base recién creada (ese es el que atrapa "un
#      cambio de esquema rompió el seed" — pasó de verdad).
#   2. Lint del frontend (oxlint).
#   3. Typecheck (tsc) — sin emitir, solo verificar.
#   4. Tests de frontend (vitest).
#   5. Build de producción (vite).
#
# El backend va primero aunque sea el paso más lento (~80s): es el que
# toca la base y el que detecta los problemas de fondo. Enterarse ahí es
# mejor que después de tres pasos verdes y rápidos que no probaban nada
# de eso.
#
# NO necesita el servidor corriendo. SÍ necesita PostgreSQL levantado
# (pytest crea y destruye sus propias bases; nunca toca torneos_mvp).

$ErrorActionPreference = "Stop"
$raiz = $PSScriptRoot
$fallos = @()

function Paso {
    param([string]$Nombre, [string]$Directorio, [scriptblock]$Comando)

    Write-Host ""
    Write-Host "=== $Nombre ===" -ForegroundColor Cyan
    Push-Location (Join-Path $raiz $Directorio)
    try {
        & $Comando
        if ($LASTEXITCODE -ne 0) {
            $script:fallos += $Nombre
            Write-Host "FALLO: $Nombre" -ForegroundColor Red
        }
    } finally {
        Pop-Location
    }
}

Paso "Backend — pytest" "backend" { python -m pytest -q }
if ($fallos.Count -eq 0) { Paso "Frontend — lint" "frontend" { npx oxlint } }
if ($fallos.Count -eq 0) { Paso "Frontend — typecheck" "frontend" { npx tsc -b --noEmit } }
if ($fallos.Count -eq 0) { Paso "Frontend — tests" "frontend" { npx vitest run } }
if ($fallos.Count -eq 0) { Paso "Frontend — build" "frontend" { npx vite build } }

Write-Host ""
if ($fallos.Count -eq 0) {
    Write-Host "TODO VERDE" -ForegroundColor Green
    exit 0
} else {
    Write-Host ("FALLARON: " + ($fallos -join ", ")) -ForegroundColor Red
    exit 1
}
