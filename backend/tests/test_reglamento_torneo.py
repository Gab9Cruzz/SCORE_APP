"""Motor de reglamento de torneo genérico (TODOS.md — decisión tomada
2026-09-17). Unit tests puros de `ReglamentoTorneo`: no tocan la DB, solo
instancian `Torneo` en memoria — el objetivo es la resolución de los
fallbacks (`None` con significado), no la persistencia, que ya cubren los
tests de integración existentes (test_minimo_para_iniciar.py,
test_tope_titulares.py, test_desempate_penales.py, etc.) sin cambios.
"""

from app.models.torneo import Torneo
from app.services.reglamento_torneo import ReglamentoTorneo, validar_maximo_titulares, validar_minimo_para_iniciar


def _torneo(**overrides) -> Torneo:
    base = dict(
        minimo_jugadores_para_iniciar=None,
        maximo_titulares_permitido=None,
        permite_cambios_ilimitados=False,
        maximo_cambios_por_equipo=None,
        metodo_desempate_eliminatoria="Manual",
        formato_eliminatoria="Unico",
        permite_walkover_grupos=False,
        cupo_maximo_inscripciones=None,
    )
    base.update(overrides)
    return Torneo(**base)


def test_minimo_titulares_usa_el_valor_del_torneo_si_esta_seteado():
    reglamento = ReglamentoTorneo.desde(_torneo(minimo_jugadores_para_iniciar=3))
    assert reglamento.minimo_titulares(tamano_equipo_modalidad=11) == 3


def test_minimo_titulares_cae_al_tamano_de_la_modalidad_si_es_null():
    reglamento = ReglamentoTorneo.desde(_torneo(minimo_jugadores_para_iniciar=None))
    assert reglamento.minimo_titulares(tamano_equipo_modalidad=11) == 11


def test_maximo_titulares_usa_el_valor_del_torneo_si_esta_seteado():
    reglamento = ReglamentoTorneo.desde(_torneo(maximo_titulares_permitido=7))
    assert reglamento.maximo_titulares(tamano_equipo_modalidad=11) == 7


def test_maximo_titulares_cae_al_tamano_de_la_modalidad_si_es_null():
    reglamento = ReglamentoTorneo.desde(_torneo(maximo_titulares_permitido=None))
    assert reglamento.maximo_titulares(tamano_equipo_modalidad=11) == 11


def test_resolver_desempate_aplicable_devuelve_el_metodo_del_torneo():
    reglamento = ReglamentoTorneo.desde(_torneo(metodo_desempate_eliminatoria="Penales_Directo"))
    assert reglamento.resolver_desempate_aplicable(ronda_nombre="Cuartos de Final") == "Penales_Directo"


def test_validar_minimo_para_iniciar_null_no_hace_nada():
    validar_minimo_para_iniciar(None, modalidad_tamano_equipo=11, modalidad_nombre="Fútbol 11")


def test_validar_minimo_para_iniciar_rechaza_por_encima_del_tamano_de_equipo():
    try:
        validar_minimo_para_iniciar(12, modalidad_tamano_equipo=11, modalidad_nombre="Fútbol 11")
    except Exception as exc:
        assert "11" in str(exc)
    else:
        raise AssertionError("Debía rechazar un mínimo mayor al tamaño del equipo.")


def test_validar_maximo_titulares_rechaza_por_encima_del_tamano_de_equipo():
    try:
        validar_maximo_titulares(12, modalidad_tamano_equipo=11, modalidad_nombre="Fútbol 11")
    except Exception as exc:
        assert "11" in str(exc)
    else:
        raise AssertionError("Debía rechazar un máximo mayor al tamaño del equipo.")
