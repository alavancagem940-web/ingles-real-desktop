"""Local persistence for Inglês Real: user_progress.json (not a remote database)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lessons import TRACKS, TRACK_ORDER, lesson_by_id, track_by_id

XP_PER_CORRECT = 10
PLACEMENT_INICIANTE_MAX = 4
PLACEMENT_INTERMEDIARIO_MAX = 8

LEVEL_LABELS = {
    "iniciante": "Iniciante",
    "intermediario": "Intermediário",
    "avancado": "Avançado",
}


def default_progress_path() -> Path:
    override = os.environ.get("INGLES_REAL_PROGRESS")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent / "user_progress.json"


def level_from_score(correct: int) -> str:
    if correct <= PLACEMENT_INICIANTE_MAX:
        return "iniciante"
    if correct <= PLACEMENT_INTERMEDIARIO_MAX:
        return "intermediario"
    return "avancado"


def tracks_for_level(level: str) -> list[str]:
    if level == "avancado":
        return list(TRACK_ORDER)
    if level == "intermediario":
        return ["basico", "intermediario"]
    return ["basico"]


@dataclass
class ProgressStore:
    path: Path = field(default_factory=default_progress_path)
    xp: int = 0
    placement_completed: bool = False
    placement_result: str | None = None
    placement_score: int = 0
    unlocked_tracks: list[str] = field(default_factory=list)
    completed_lessons: list[str] = field(default_factory=list)
    completed_modules: list[str] = field(default_factory=list)
    answers: dict[str, Any] = field(default_factory=dict)
    position: dict[str, Any] = field(default_factory=dict)

    def load(self) -> None:
        if not self.path.exists():
            self.save()
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProgressError(f"Não foi possível ler o progresso salvo: {exc}") from exc
        self.xp = int(data.get("xp", 0))
        self.placement_completed = bool(data.get("placement_completed", False))
        self.placement_result = data.get("placement_result") or data.get("level")
        self.placement_score = int(data.get("placement_score", 0))
        self.unlocked_tracks = list(data.get("unlocked_tracks", []))
        self.completed_lessons = list(data.get("completed_lessons", []))
        self.completed_modules = list(data.get("completed_modules", []))
        self.answers = dict(data.get("answers", {}))
        self.position = dict(data.get("position", {}))

    def save(self) -> None:
        payload: dict[str, Any] = {
            "xp": self.xp,
            "placement_completed": self.placement_completed,
            "placement_result": self.placement_result,
            "placement_score": self.placement_score,
            "unlocked_tracks": self.unlocked_tracks,
            "completed_lessons": self.completed_lessons,
            "completed_modules": self.completed_modules,
            "answers": self.answers,
            "position": self.position,
            "level": self.placement_result,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def apply_placement(self, score: int, total: int) -> str:
        level = level_from_score(score)
        self.placement_completed = True
        self.placement_result = level
        self.placement_score = score
        unlocked = set(self.unlocked_tracks) | set(tracks_for_level(level))
        self.unlocked_tracks = [tid for tid in TRACK_ORDER if tid in unlocked]
        self.position = {"screen": "home"}
        self.save()
        return level

    def retake_keeps_xp(self) -> None:
        """Placement can be redone; XP, answers and completed lessons stay."""
        self.placement_completed = False
        self.position = {"screen": "placement", "step_index": 0}
        self.save()

    def add_xp(self, amount: int) -> None:
        self.xp += max(0, amount)
        self.save()

    def record_answer(self, exercise_id: str, payload: dict[str, Any]) -> None:
        self.answers[exercise_id] = payload
        self.save()

    def set_position(self, **kwargs: Any) -> None:
        self.position = dict(kwargs)
        self.save()

    def mark_lesson_complete(self, lesson_id: str, bonus_xp: int) -> None:
        if lesson_id not in self.completed_lessons:
            self.completed_lessons.append(lesson_id)
        lesson = lesson_by_id(lesson_id)
        if lesson and lesson.kind == "challenge":
            track = None
            for item in TRACKS:
                if any(unit.id == lesson_id for unit in item.lessons):
                    track = item
                    break
            if track and track.id not in self.completed_modules:
                self.completed_modules.append(track.id)
            if track:
                self._unlock_next_track(track.id)
        self.add_xp(bonus_xp)

    def _unlock_next_track(self, track_id: str) -> None:
        if track_id not in TRACK_ORDER:
            return
        index = TRACK_ORDER.index(track_id)
        if index + 1 < len(TRACK_ORDER):
            nxt = TRACK_ORDER[index + 1]
            if nxt not in self.unlocked_tracks:
                self.unlocked_tracks.append(nxt)

    def is_track_unlocked(self, track_id: str) -> bool:
        return track_id in self.unlocked_tracks

    def is_lesson_unlocked(self, track_id: str, lesson_id: str) -> bool:
        if not self.is_track_unlocked(track_id):
            return False
        track = track_by_id(track_id)
        if track is None:
            return False
        previous: list[str] = []
        for lesson in track.lessons:
            if lesson.id == lesson_id:
                return all(item in self.completed_lessons for item in previous)
            previous.append(lesson.id)
        return False

    def is_lesson_complete(self, lesson_id: str) -> bool:
        return lesson_id in self.completed_lessons

    def is_empty(self) -> bool:
        return not self.placement_completed and self.xp == 0 and not self.completed_lessons

    def continue_target(self) -> dict[str, Any] | None:
        pos = self.position or {}
        if pos.get("track_id") and pos.get("lesson_id"):
            return pos
        for track in TRACKS:
            if not self.is_track_unlocked(track.id):
                continue
            for lesson in track.lessons:
                if self.is_lesson_unlocked(track.id, lesson.id) and lesson.id not in self.completed_lessons:
                    return {"screen": "theory", "track_id": track.id, "lesson_id": lesson.id, "step_index": 0}
        return None

    def level_label(self) -> str:
        if not self.placement_result:
            return "Sem nível"
        return LEVEL_LABELS.get(self.placement_result, self.placement_result)


class ProgressError(Exception):
    pass
