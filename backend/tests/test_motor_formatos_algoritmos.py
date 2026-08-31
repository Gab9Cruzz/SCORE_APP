"""Los 2 algoritmos puros del motor de formatos, probados como funciones
—sin DB ni HTTP— porque no tienen ningún efecto lateral (motor-formatos-
plantillas-navegacion-plan.md, requerimiento #4)."""
from app.services.motor_formatos import MotorFormatosService, algoritmo_fixture_liga


def test_fixture_liga_par_cada_equipo_juega_una_vez_por_jornada():
    partidos = algoritmo_fixture_liga([1, 2, 3, 4], ida_vuelta=False)
    assert len(partidos) == 6  # C(4,2)
    jornadas = {j for (_, _, j) in partidos}
    assert jornadas == {1, 2, 3}
    for j in jornadas:
        equipos_de_la_jornada = [e for (l, v, jj) in partidos if jj == j for e in (l, v)]
        assert len(equipos_de_la_jornada) == len(set(equipos_de_la_jornada))


def test_fixture_liga_impar_un_equipo_descansa_por_jornada():
    partidos = algoritmo_fixture_liga([1, 2, 3], ida_vuelta=False)
    assert len(partidos) == 3  # 3 jornadas, 1 partido cada una
    for j in {1, 2, 3}:
        de_la_jornada = [p for p in partidos if p[2] == j]
        assert len(de_la_jornada) == 1


def test_fixture_liga_ida_vuelta_invierte_local_visitante():
    ida = algoritmo_fixture_liga([1, 2, 3, 4], ida_vuelta=False)
    con_vuelta = algoritmo_fixture_liga([1, 2, 3, 4], ida_vuelta=True)
    assert len(con_vuelta) == len(ida) * 2
    vueltas = con_vuelta[len(ida) :]
    assert {(v, l) for (l, v, _) in ida} == {(l, v) for (l, v, _) in vueltas}


def test_cruzar_grupos_top2_cruza_1ro_con_2do_del_otro_grupo():
    # EC-50: 1°A-2°B, 1°B-2°A.
    servicio = MotorFormatosService.__new__(MotorFormatosService)  # sin __init__: el método no toca self.session
    cruce = servicio._cruzar_grupos({"A": [10, 11], "B": [20, 21]})
    assert cruce == [10, 21, 20, 11]


def test_cruzar_grupos_4_grupos_empareja_de_a_pares():
    servicio = MotorFormatosService.__new__(MotorFormatosService)
    cruce = servicio._cruzar_grupos({"A": [1, 2], "B": [3, 4], "C": [5, 6], "D": [7, 8]})
    # A-B primero (1-4, 3-2), después C-D (5-8, 7-6).
    assert cruce == [1, 4, 3, 2, 5, 8, 7, 6]


def test_cruzar_grupos_numero_impar_deja_el_ultimo_sin_pareja():
    servicio = MotorFormatosService.__new__(MotorFormatosService)
    cruce = servicio._cruzar_grupos({"A": [1, 2], "B": [3, 4], "C": [5, 6]})
    assert cruce[:4] == [1, 4, 3, 2]
    assert cruce[4:] == [5, 6]  # C sin pareja de cruce, entra en orden de tabla
