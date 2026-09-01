import pytest

"""Tests of the annotation model."""

from easypdf.model import Annotation, AnnotationStore, Kind


def test_normalized_rect_orders_the_corners():
    ann = Annotation(kind=Kind.RECT, page=0, rect=(200, 300, 100, 150))
    assert ann.normalized_rect() == (100, 150, 200, 300)


def test_bounds_of_line_and_drawing():
    line = Annotation(kind=Kind.LINE, page=0, p1=(10, 90), p2=(80, 20))
    assert line.bounds() == (10, 20, 80, 90)
    dibujo = Annotation(kind=Kind.INK, page=0, strokes=[[(5, 5), (30, 40)], [(60, 10)]])
    assert dibujo.bounds() == (5, 5, 60, 40)


def test_translate_moves_every_geometry():
    ann = Annotation(
        kind=Kind.INK, page=0, rect=(0, 0, 10, 10), p1=(1, 1), p2=(2, 2),
        strokes=[[(3, 3), (4, 4)]],
    )
    ann.translate(5, -2)
    assert ann.rect == (5, -2, 15, 8)
    assert ann.p1 == (6, -1) and ann.p2 == (7, 0)
    assert ann.strokes == [[(8, 1), (9, 2)]]


def test_copy_does_not_share_the_strokes():
    ann = Annotation(kind=Kind.INK, page=0, strokes=[[(1, 1), (2, 2)]])
    clon = ann.copy()
    clon.strokes[0].append((3, 3))
    assert ann.strokes == [[(1, 1), (2, 2)]]
    assert clon.id == ann.id


def test_is_empty_discards_the_tiny():
    assert Annotation(kind=Kind.RECT, page=0, rect=(10, 10, 11, 11)).is_empty()
    assert not Annotation(kind=Kind.RECT, page=0, rect=(10, 10, 60, 40)).is_empty()
    assert Annotation(kind=Kind.LINE, page=0, p1=(1, 1), p2=(1, 1)).is_empty()
    assert Annotation(kind=Kind.INK, page=0, strokes=[[(1, 1)]]).is_empty()


def test_store_adds_and_removes():
    store = AnnotationStore()
    first_tick = store.add(Annotation(kind=Kind.RECT, page=0))
    segunda = store.add(Annotation(kind=Kind.TEXT, page=1))
    assert len(store) == 2
    assert store.for_page(1) == [segunda]
    assert store.pages_used() == [0, 1]
    assert store.remove(first_tick) == 0
    assert len(store) == 1
    store.clear()
    assert len(store) == 0


def test_every_kind_has_a_readable_label():
    assert Kind.RECT.label == "Box"
    assert Kind.INK.label == "Drawing"


def test_a_table_lays_out_its_cells():
    table = Annotation(kind=Kind.TABLE, page=0, rect=(10, 20, 110, 80), rows=2, cols=4)
    cells = table.cell_rects()
    assert len(cells) == 8
    assert cells[0] == (10, 20, 35, 50)
    assert cells[-1] == (85, 50, 110, 80)
    # the border plus the inner dividers
    assert len(table.grid_lines()) == (2 + 1) + (4 + 1)


def test_a_table_fits_the_texts_to_the_cell_count():
    table = Annotation(kind=Kind.TABLE, page=0, rows=2, cols=2, cells=["a", "b", "c", "d", "e"])
    assert table.normalized_cells() == ["a", "b", "c", "d"]
    table.cells = ["a"]
    assert table.normalized_cells() == ["a", "", "", ""]


def test_the_arrow_head_grows_with_width_but_never_exceeds_the_line():
    from easypdf.model import arrow_head

    thin_base, tip, left, right = arrow_head((0, 0), (100, 0), 1.0)
    thin_length = tip[0] - thin_base[0]
    thick_base, tip, _, _ = arrow_head((0, 0), (100, 0), 6.0)
    assert (tip[0] - thick_base[0]) > thin_length
    assert abs(left[1] - right[1]) == pytest.approx(thin_length, rel=0.05)
    # on a very short line the head cannot be longer than the line itself
    short_base, _short_tip, _, _ = arrow_head((0, 0), (6, 0), 6.0)
    assert short_base[0] >= 0.0


# --------------------------------------------------------------------------
# Page rotation
# --------------------------------------------------------------------------

def test_rotate_point_takes_the_corners_where_they_belong():
    from easypdf.model import rotate_point

    width, height = 600.0, 800.0
    # Turning 90 degrees clockwise, the top left corner becomes the top right
    # of a page that now measures 800x600.
    assert rotate_point((0.0, 0.0), 90, width, height) == (800.0, 0.0)
    assert rotate_point((600.0, 0.0), 90, width, height) == (800.0, 600.0)
    assert rotate_point((0.0, 0.0), 180, width, height) == (600.0, 800.0)
    assert rotate_point((0.0, 0.0), 270, width, height) == (0.0, 600.0)
    assert rotate_point((10.0, 20.0), 0, width, height) == (10.0, 20.0)


def test_four_ninety_degree_turns_return_the_point_home():
    from easypdf.model import rotate_point

    point, width, height = (123.0, 456.0), 600.0, 800.0
    for _ in range(4):
        point = rotate_point(point, 90, width, height)
        width, height = height, width          # the page changes orientation
    assert point == (123.0, 456.0)
    assert (width, height) == (600.0, 800.0)


def test_rotate_annotation_turns_rect_line_and_strokes():
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


def test_rotate_annotation_does_nothing_at_zero():
    from easypdf.model import rotate_annotation

    ann = Annotation(kind=Kind.RECT, page=0, rect=(1.0, 2.0, 3.0, 4.0))
    rotate_annotation(ann, 0, 600.0, 800.0)
    assert ann.rect == (1.0, 2.0, 3.0, 4.0)


# --------------------------------------------------------------------------
# Snapping to guides
# --------------------------------------------------------------------------

def test_snap_offset_sticks_to_the_nearest_guide():
    from easypdf.model import snap_offset

    # the left edge is 2 away from the guide at 100
    assert snap_offset([98.0, 148.0, 198.0], [0.0, 100.0, 300.0], 6.0) == (2.0, 100.0)


def test_snap_offset_does_nothing_when_far_away():
    from easypdf.model import snap_offset

    assert snap_offset([80.0], [100.0], 6.0) == (0.0, None)


def test_snap_offset_picks_the_closest_guide_of_several():
    from easypdf.model import snap_offset

    # 97 is 3 from 100 and 3 from 94: on a tie the first one wins
    delta, guide = snap_offset([97.0], [100.0, 94.0], 6.0)
    assert guide == 100.0 and delta == 3.0
    # and if one is clearly nearer, that one wins
    assert snap_offset([97.0], [100.0, 96.0], 6.0) == (-1.0, 96.0)


def test_snap_offset_leaves_what_is_already_aligned():
    from easypdf.model import snap_offset

    assert snap_offset([100.0], [100.0], 6.0) == (0.0, 100.0)


def test_moving_an_annotation_drags_everything_it_is_made_of():
    """The rectangle is not enough: lines live in their ends and ink in its strokes."""
    from easypdf.model import move_annotation

    ann = Annotation(
        kind=Kind.LINE, page=0, rect=(10.0, 20.0, 110.0, 120.0),
        p1=(10.0, 20.0), p2=(110.0, 120.0),
        strokes=[[(0.0, 0.0), (5.0, 5.0)]],
    )
    move_annotation(ann, 7.0, -3.0)
    assert ann.rect == (17.0, 17.0, 117.0, 117.0)
    assert ann.p1 == (17.0, 17.0)
    assert ann.p2 == (117.0, 117.0)
    assert ann.strokes == [[(7.0, -3.0), (12.0, 2.0)]]


def test_moving_by_zero_touches_nothing():
    from easypdf.model import move_annotation

    ann = Annotation(kind=Kind.RECT, page=0, rect=(1.0, 2.0, 3.0, 4.0))
    move_annotation(ann, 0.0, 0.0)
    assert ann.rect == (1.0, 2.0, 3.0, 4.0)
