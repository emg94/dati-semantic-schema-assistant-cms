from schema_assistant.agent.static_answers import find_static_answer


def test_catalog_identity_answer_for_greeting() -> None:
    result = find_static_answer("Ciao, chi sei?")

    assert result is not None
    assert result.reason == "identity_catalog"
    assert "assistente del catalogo" in result.answer


def test_developer_identity_answer_has_priority() -> None:
    result = find_static_answer("Ciao, chi ti ha sviluppato?")

    assert result is not None
    assert result.reason == "identity_developer"
    assert "DXC Technology" in result.answer


def test_greeting_with_domain_question_is_not_static() -> None:
    result = find_static_answer("Ciao, mostrami le ontologie pubblicate da INPS")

    assert result is None
