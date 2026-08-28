import pytest

"""Pruebas del modelo de anotaciones."""

from easypdf.model import Annotation, AnnotationStore, Kind


def test_normalized_rect_ordena_las_esquinas():
    ann = Annotation(kind=Kind.RECT, page=0, rect=(200, 300, 100, 150))
    assert ann.normalized_rect() == (100, 150, 200, 300)


def test_bounds_de_linea_y_dibujo():
    linea = Annotation(kind=Kind.LINE, page=0, p1=(10, 90), p2=(80, 20))
    assert linea.bounds() == (10, 20, 80, 90)
    dibujo = Annotation(kind=Kind.INK, page=0, strokes=[[(5, 5), (30, 40)], [(60, 10)]])
    assert dibujo.bounds() == (5, 5, 60, 40)


def test_translate_mueve_todas_las_geometrias():
    ann = Annotation(
        kind=Kind.INK, page=0, rect=(0, 0, 10, 10), p1=(1, 1), p2=(2, 2),
        strokes=[[(3, 3), (4, 4)]],
    )
    ann.translate(5, -2)
    assert ann.rect == (5, -2, 15, 8)
    assert ann.p1 == (6, -1) and ann.p2 == (7, 0)
    assert ann.strokes == [[(8, 1), (9, 2)]]


def test_copy_no_comparte_los_trazos():
    ann = Annotation(kind=Kind.INK, page=0, strokes=[[(1, 1), (2, 2)]])
    clon = ann.copy()
    clon.strokes[0].append((3, 3))
    assert ann.strokes == [[(1, 1), (2, 2)]]
    assert clon.id == ann.id


def test_is_empty_descarta_lo_diminuto():
    assert Annotation(kind=Kind.RECT, page=0, rect=(10, 10, 11, 11)).is_empty()
    assert not Annotation(kind=Kind.RECT, page=0, rect=(10, 10, 60, 40)).is_empty()
    assert Annotation(kind=Kind.LINE, page=0, p1=(1, 1), p2=(1, 1)).is_empty()
    assert Annotation(kind=Kind.INK, page=0, strokes=[[(1, 1)]]).is_empty()


def test_store_agrega_y_elimina():
    store = AnnotationStore()
    primera = store.add(Annotation(kind=Kind.RECT, page=0))
    segunda = store.add(Annotation(kind=Kind.TEXT, page=1))
    assert len(store) == 2
    assert store.for_page(1) == [segunda]
    assert store.pages_used() == [0, 1]
    assert store.remove(primera) == 0
    assert len(store) == 1
    store.clear()
    assert len(store) == 0


def test_kind_tiene_etiqueta_en_espanol():
    assert Kind.RECT.label == "Cuadro"
    assert Kind.INK.label == "Dibujo"


def test_tabla_reparte_las_celdas():
    tabla = Annotation(kind=Kind.TABLE, page=0, rect=(10, 20, 110, 80), rows=2, cols=4)
    celdas = tabla.cell_rects()
    assert len(celdas) == 8
    assert celdas[0] == (10, 20, 35, 50)
    assert celdas[-1] == (85, 50, 110, 80)
    # el borde mas las separaciones interiores
    assert len(tabla.grid_lines()) == (2 + 1) + (4 + 1)


def test_tabla_ajusta_los_textos_al_numero_de_celdas():
    tabla = Annotation(kind=Kind.TABLE, page=0, rows=2, cols=2, cells=["a", "b", "c", "d", "e"])
    assert tabla.normalized_cells() == ["a", "b", "c", "d"]
    tabla.cells = ["a"]
    assert tabla.normalized_cells() == ["a", "", "", ""]


def test_la_punta_de_flecha_crece_con_el_grosor_pero_no_pasa_de_la_linea():
    from easypdf.model import arrow_head

    base_fina, punta, izquierda, derecha = arrow_head((0, 0), (100, 0), 1.0)
    largo_fino = punta[0] - base_fina[0]
    base_gruesa, punta, _, _ = arrow_head((0, 0), (100, 0), 6.0)
    assert (punta[0] - base_gruesa[0]) > largo_fino
    assert abs(izquierda[1] - derecha[1]) == pytest.approx(largo_fino, rel=0.05)
    # en una linea muy corta la punta no puede ser mas larga que la linea
    base_corta, punta_corta, _, _ = arrow_head((0, 0), (6, 0), 6.0)
    assert base_corta[0] >= 0.0


# --------------------------------------------------------------------------
# Giro de pagina
# --------------------------------------------------------------------------

def test_rotate_point_lleva_las_esquinas_a_su_sitio():
    from easypdf.model import rotate_point

    ancho, alto = 600.0, 800.0
    # Girando 90 grados en horario, la esquina superior izquierda pasa a ser
    # la superior derecha de una pagina que ahora mide 800x600.
    assert rotate_point((0.0, 0.0), 90, ancho, alto) == (800.0, 0.0)
    assert rotate_point((600.0, 0.0), 90, ancho, alto) == (800.0, 600.0)
    assert rotate_point((0.0, 0.0), 180, ancho, alto) == (600.0, 800.0)
    assert rotate_point((0.0, 0.0), 270, ancho, alto) == (0.0, 600.0)
    assert rotate_point((10.0, 20.0), 0, ancho, alto) == (10.0, 20.0)


def test_cuatro_giros_de_90_devuelven_el_punto_al_origen():
    from easypdf.model import rotate_point

    punto, ancho, alto = (123.0, 456.0), 600.0, 800.0
    for _ in range(4):
        punto = rotate_point(punto, 90, ancho, alto)
        ancho, alto = alto, ancho          # la pagina cambia de orientacion
    assert punto == (123.0, 456.0)
    assert (ancho, alto) == (600.0, 800.0)


def test_rotate_annotation_gira_rectangulo_linea_y_trazos():
    from easypdf.model import rotate_annotation

    ann = Annotation(
        kind=Kind.INK, page=0, rect=(50.0, 100.0, 150.0, 200.0),
        p1=(10.0, 20.0), p2=(30.0, 40.0), strokes=[[(0.0, 0.0), (10.0, 10.0)]],
    )
    rotate_annotation(ann, 90, 600.0, 800.0)
    assert ann.rect == (600.0, 50.0, 700.0, 150.0)
    assert ann.p1 == (780.0, 10.0)
    assert ann.p2 == (760.0, 30.0)
    assert ann.strokes == [[(800.0, 0.0), (790.0, 10.0)]]


def test_rotate_annotation_no_toca_nada_si_el_giro_es_cero():
    from easypdf.model import rotate_annotation

    ann = Annotation(kind=Kind.RECT, page=0, rect=(1.0, 2.0, 3.0, 4.0))
    rotate_annotation(ann, 0, 600.0, 800.0)
    assert ann.rect == (1.0, 2.0, 3.0, 4.0)


# --------------------------------------------------------------------------
# Goma
# --------------------------------------------------------------------------

def test_la_goma_parte_el_trazo_en_dos():
    from easypdf.model import erase_strokes

    trazo = [[(0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (30.0, 0.0), (40.0, 0.0)]]
    assert erase_strokes(trazo, (20.0, 0.0), 6.0) == [
        [(0.0, 0.0), (10.0, 0.0)],
        [(30.0, 0.0), (40.0, 0.0)],
    ]


def test_la_goma_en_un_extremo_solo_acorta():
    from easypdf.model import erase_strokes

    trazo = [[(0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (30.0, 0.0)]]
    assert erase_strokes(trazo, (0.0, 0.0), 6.0) == [[(10.0, 0.0), (20.0, 0.0), (30.0, 0.0)]]


def test_una_goma_que_lo_cubre_todo_no_deja_nada():
    from easypdf.model import erase_strokes

    trazo = [[(0.0, 0.0), (10.0, 0.0), (20.0, 0.0)]]
    assert erase_strokes(trazo, (10.0, 0.0), 100.0) == []


def test_la_goma_lejos_no_toca_el_trazo():
    from easypdf.model import erase_strokes

    trazo = [[(0.0, 0.0), (10.0, 0.0), (20.0, 0.0)]]
    assert erase_strokes(trazo, (500.0, 500.0), 6.0) == trazo


def test_los_restos_de_un_solo_punto_se_descartan():
    """Un tramo de un punto no se dibuja, asi que no se conserva."""
    from easypdf.model import erase_strokes

    trazo = [[(0.0, 0.0), (10.0, 0.0), (20.0, 0.0)]]
    # se borra el punto del medio: a cada lado queda uno solo
    assert erase_strokes(trazo, (10.0, 0.0), 6.0) == []


def test_el_circulo_de_la_goma_detecta_lo_que_toca():
    from easypdf.model import circle_touches_rect

    caja = (0.0, 0.0, 10.0, 10.0)
    assert circle_touches_rect((5.0, 5.0), 2.0, caja)      # dentro
    assert circle_touches_rect((12.0, 5.0), 3.0, caja)     # roza el borde
    assert not circle_touches_rect((50.0, 50.0), 3.0, caja)
    # da igual como venga dado el rectangulo
    assert circle_touches_rect((5.0, 5.0), 1.0, (10.0, 10.0, 0.0, 0.0))
