"""Pruebas de los textos de la interfaz."""

import pytest

from easypdf.i18n import (
    DEFAULT_LANGUAGE,
    LANGUAGES,
    TEXTS,
    language,
    set_language,
    system_language,
    tr,
)


@pytest.fixture(autouse=True)
def idioma_limpio():
    anterior = language()
    yield
    set_language(anterior)


def test_los_dos_idiomas_tienen_las_mismas_claves():
    claves = {codigo: set(textos) for codigo, textos in TEXTS.items()}
    referencia = claves[DEFAULT_LANGUAGE]
    for codigo, propias in claves.items():
        assert propias == referencia, f"faltan textos en {codigo}: {referencia ^ propias}"


def test_no_hay_textos_vacios():
    for codigo, textos in TEXTS.items():
        vacios = [clave for clave, valor in textos.items() if not valor.strip()]
        assert not vacios, f"{codigo} tiene textos vacios: {vacios}"


def test_los_campos_de_cada_texto_coinciden_entre_idiomas():
    """Si un texto lleva {name}, la traduccion tiene que llevarlo tambien."""
    import string

    def campos(texto):
        return {c for _, c, _, _ in string.Formatter().parse(texto) if c}

    for clave, texto in TEXTS[DEFAULT_LANGUAGE].items():
        for codigo, textos in TEXTS.items():
            assert campos(textos[clave]) == campos(texto), f"{clave} en {codigo}"


def test_traduce_y_cambia_de_idioma():
    set_language("en")
    assert tr("save") == "&Save"
    set_language("es")
    assert tr("save") == "&Guardar"
    assert language() == "es"


def test_rellena_los_campos():
    set_language("en")
    assert tr("status_of", total=7) == "of 7"
    assert "3 x 4" in tr("hint_table", rows=3, cols=4)


def test_una_clave_desconocida_no_rompe():
    assert tr("clave-que-no-existe") == "clave-que-no-existe"


def test_idioma_del_sistema():
    assert system_language("es_ES") == "es"
    assert system_language("en-GB") == "en"
    assert system_language("fr_FR") == DEFAULT_LANGUAGE   # sin traducir: ingles
    assert system_language("") == DEFAULT_LANGUAGE


def test_un_idioma_desconocido_cae_al_predeterminado():
    assert set_language("klingon") == DEFAULT_LANGUAGE
    assert set(LANGUAGES) == set(TEXTS)
