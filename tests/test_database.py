from database import ProgressStore, level_from_score, tracks_for_level
from lessons import PLACEMENT, validate_curriculum


def test_placement_bands() -> None:
    assert level_from_score(0) == "iniciante"
    assert level_from_score(4) == "iniciante"
    assert level_from_score(5) == "intermediario"
    assert level_from_score(8) == "intermediario"
    assert level_from_score(9) == "avancado"
    assert tracks_for_level("iniciante") == ["basico"]
    assert "fluencia" in tracks_for_level("avancado")


def test_progress_roundtrip(tmp_path) -> None:
    path = tmp_path / "user_progress.json"
    store = ProgressStore(path=path)
    store.load()
    store.xp = 40
    store.apply_placement(7, len(PLACEMENT))
    store.record_answer("b1e1", {"correct": True, "submission": "Nothing much, you?"})
    store.set_position(screen="exercise", track_id="basico", lesson_id="b1", step_index=2)
    store.mark_lesson_complete("b1", 25)

    other = ProgressStore(path=path)
    other.load()
    assert other.xp == 65
    assert other.placement_result == "intermediario"
    assert other.placement_completed is True
    assert "basico" in other.unlocked_tracks
    assert "intermediario" in other.unlocked_tracks
    assert "b1" in other.completed_lessons
    assert other.position["lesson_id"] == "b1"
    assert other.answers["b1e1"]["correct"] is True


def test_retake_keeps_xp(tmp_path) -> None:
    path = tmp_path / "user_progress.json"
    store = ProgressStore(path=path)
    store.apply_placement(11, len(PLACEMENT))
    store.xp = 200
    store.completed_lessons = ["b1"]
    store.save()
    store.retake_keeps_xp()
    assert store.xp == 200
    assert store.completed_lessons == ["b1"]
    assert store.placement_completed is False
    store.apply_placement(3, len(PLACEMENT))
    assert store.xp == 200
    assert "basico" in store.unlocked_tracks
    assert "fluencia" in store.unlocked_tracks


def test_validate_on_import() -> None:
    validate_curriculum()
