"""Tests of the interface texts."""

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
    previous = language()
    yield
    set_language(previous)


def test_both_languages_have_the_same_keys():
    claves = {codigo: set(textos) for codigo, textos in TEXTS.items()}
    reference = claves[DEFAULT_LANGUAGE]
    for codigo, propias in claves.items():
        assert propias == reference, f"faltan textos en {codigo}: {reference ^ propias}"


def test_there_are_no_empty_texts():
    for code, texts in TEXTS.items():
        empty = [key for key, value in texts.items() if not value.strip()]
        assert not empty, f"{code} has empty texts: {empty}"


def test_the_format_fields_match_across_languages():
    """If a text carries {name}, the translation has to carry it too."""
    import string

    def fields(text):
        return {c for _, c, _, _ in string.Formatter().parse(text) if c}

    for key, text in TEXTS[DEFAULT_LANGUAGE].items():
        for code, texts in TEXTS.items():
            assert fields(texts[key]) == fields(text), f"{key} in {code}"


def test_it_translates_and_switches_language():
    set_language("en")
    assert tr("save") == "&Save"
    set_language("es")
    assert tr("save") == "&Guardar"
    assert language() == "es"


def test_it_fills_in_the_fields():
    set_language("en")
    assert tr("status_of", total=7) == "of 7"
    assert "3 x 4" in tr("hint_table", rows=3, cols=4)


def test_an_unknown_key_does_not_break_it():
    assert tr("clave-que-no-existe") == "clave-que-no-existe"


def test_system_language():
    assert system_language("es_ES") == "es"
    assert system_language("en-GB") == "en"
    assert system_language("fr_FR") == DEFAULT_LANGUAGE   # sin traducir: ingles
    assert system_language("") == DEFAULT_LANGUAGE


def test_an_unknown_language_falls_back_to_the_default():
    assert set_language("klingon") == DEFAULT_LANGUAGE
    assert set(LANGUAGES) == set(TEXTS)
