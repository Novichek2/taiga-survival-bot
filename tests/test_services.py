from app.services import calculate_score, level_for_score, load_questions


def test_score_bounds_and_progress():
    assert calculate_score(0, False) == 0
    assert calculate_score(95, True) == 100
    assert calculate_score(50, True) == 58
    assert calculate_score(50, False) == 45


def test_levels():
    assert level_for_score(0) == "Городской"
    assert level_for_score(50) == "Автономник"
    assert level_for_score(99) == "Инструктор"


def test_all_mvp_modules_have_content():
    for module in ("fire", "water", "navigation", "shelter", "first_aid", "winter"):
        questions = load_questions(module)
        assert questions
        for question in questions:
            assert question["id"]
            assert len(question["options"]) >= 2
            assert 0 <= question["answer"] < len(question["options"])
