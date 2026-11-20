"""Minuto de partido calculado desde los hitos (services/minuto_partido.py).

Era el service con menos cobertura (36 %, docs/cobertura.md): solo lo
ejercían de pasada las pruebas de eventos. Es una función pura, así que se
prueba sin base, con hitos armados a mano.
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

from app.services.minuto_partido import calcular_minuto_actual

T0 = datetime(2026, 11, 20, 15, 0, 0)


def hito(tipo: str, minuto: float, periodo: int | None = None) -> SimpleNamespace:
    return SimpleNamespace(tipo_hito=tipo, timestamp_real=T0 + timedelta(minutes=minuto), numero_periodo=periodo)


def en(minuto: float) -> datetime:
    return T0 + timedelta(minutes=minuto)


PERIODOS = SimpleNamespace(tipo_cronometro="Periodos")
CORRIDO = SimpleNamespace(tipo_cronometro="Corrido")


def test_sin_inicio_de_partido_no_hay_minuto():
    assert calcular_minuto_actual([], PERIODOS, en(10)) is None
    assert calcular_minuto_actual([hito("Pausa", 1)], CORRIDO, en(10)) is None


def test_corrido_cuenta_desde_el_inicio_del_partido():
    hitos = [hito("Inicio_Partido", 0)]
    assert calcular_minuto_actual(hitos, CORRIDO, en(12.5)) == 12


def test_corrido_descuenta_las_pausas():
    hitos = [hito("Inicio_Partido", 0), hito("Pausa", 10), hito("Reanudacion", 15)]
    assert calcular_minuto_actual(hitos, CORRIDO, en(20)) == 15


def test_en_pausa_devuelve_el_ultimo_minuto_conocido():
    hitos = [hito("Inicio_Partido", 0), hito("Pausa", 10)]
    assert calcular_minuto_actual(hitos, CORRIDO, en(40)) == 10


def test_periodos_sin_periodo_abierto_es_minuto_cero():
    hitos = [hito("Inicio_Partido", 0)]
    assert calcular_minuto_actual(hitos, PERIODOS, en(5)) == 0


def test_periodos_acumula_el_primero_cerrado_y_el_segundo_abierto():
    hitos = [
        hito("Inicio_Partido", 0),
        hito("Inicio_Periodo", 0, 1),
        hito("Fin_Periodo", 45, 1),
        # Entretiempo de 15 minutos: no cuenta.
        hito("Inicio_Periodo", 60, 2),
    ]
    assert calcular_minuto_actual(hitos, PERIODOS, en(82)) == 67


def test_en_el_entretiempo_queda_el_minuto_del_cierre():
    hitos = [hito("Inicio_Partido", 0), hito("Inicio_Periodo", 0, 1), hito("Fin_Periodo", 45, 1)]
    assert calcular_minuto_actual(hitos, PERIODOS, en(52)) == 45


def test_periodos_descuenta_pausas_dentro_de_cada_periodo():
    hitos = [
        hito("Inicio_Partido", 0),
        hito("Inicio_Periodo", 0, 1),
        hito("Pausa", 20),
        hito("Reanudacion", 23),
        hito("Fin_Periodo", 48, 1),
        hito("Inicio_Periodo", 60, 2),
        hito("Pausa", 70),
    ]
    # 1er período: 48 - 3 de pausa = 45; 2do: 10 hasta la pausa.
    assert calcular_minuto_actual(hitos, PERIODOS, en(90)) == 55


def test_un_fin_de_periodo_sin_su_inicio_se_ignora():
    hitos = [hito("Inicio_Partido", 0), hito("Fin_Periodo", 30, 1)]
    assert calcular_minuto_actual(hitos, PERIODOS, en(40)) == 0


def test_una_reanudacion_sin_pausa_previa_no_duplica_tiempo():
    hitos = [hito("Inicio_Partido", 0), hito("Reanudacion", 5)]
    assert calcular_minuto_actual(hitos, CORRIDO, en(10)) == 10
