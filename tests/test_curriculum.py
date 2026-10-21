from lessons import (
    PLACEMENT,
    TRACK_ORDER,
    TRACKS,
    all_examples,
    all_exercises,
    challenge_pass_threshold,
    validate_curriculum,
)
from ui import LISTEN_LABEL, THEORY_CARD_TITLE


def test_tracks_cover_all_levels() -> None:
    assert TRACK_ORDER == ("basico", "intermediario", "avancado", "fluencia")
    assert [track.id for track in TRACKS] == list(TRACK_ORDER)
    for track in TRACKS:
        assert track.lessons
        assert any(lesson.kind == "challenge" for lesson in track.lessons)


def test_curriculum_is_valid_and_extensive() -> None:
    validate_curriculum()
    exercises = all_exercises()
    examples = all_examples()
    assert len(exercises) >= 120
    assert len(examples) >= 80
    assert len(PLACEMENT) >= 10


def test_every_item_has_english_for_tts() -> None:
    for exercise in all_exercises():
        assert exercise.listen_en.strip(), exercise.id
    for example in all_examples():
        assert example.en.strip()
        assert example.pt.strip()


def test_listen_button_label_and_theory_card() -> None:
    assert LISTEN_LABEL == "Ouvir Pronúncia Nativa"
    assert THEORY_CARD_TITLE == "Explicação Teórica Prática"
    ui_src = open("ui.py", encoding="utf-8").read()
    assert 'LISTEN_LABEL = "Ouvir Pronúncia Nativa"' in ui_src
    assert "text=LISTEN_LABEL" in ui_src
    assert ui_src.count("self._listen_button(") >= 4


def test_real_us_english_markers() -> None:
    blob = " ".join(item.listen_en.lower() for item in all_exercises())
    for token in ("gonna", "wanna", "gotta", "whatcha", "figure it out", "no cap"):
        assert token in blob, token


def test_challenge_threshold() -> None:
    assert challenge_pass_threshold(6) == 4
    assert challenge_pass_threshold(1) == 1
