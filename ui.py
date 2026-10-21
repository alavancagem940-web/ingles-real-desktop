"""Portuguese CustomTkinter UI for Inglês Real. Listen button on every phrase."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import customtkinter as ctk

from audio_engine import PRIMARY_VOICE, AudioEngine, SilentAudioEngine
from database import LEVEL_LABELS, XP_PER_CORRECT, ProgressError, ProgressStore
from lessons import (
    PLACEMENT,
    TRACKS,
    Exercise,
    Lesson,
    Track,
    challenge_pass_threshold,
    lesson_by_id,
    track_by_id,
    validate_curriculum,
)

LISTEN_LABEL = "Ouvir Pronúncia Nativa"
THEORY_CARD_TITLE = "Explicação Teórica Prática"

NAVY = "#0B1F33"
SKY = "#2F80ED"
SKY_HOVER = "#1B6AD6"
GREEN = "#2F9E44"
GREEN_HOVER = "#237A34"
GREEN_SOFT = "#143D22"
RED = "#E03131"
RED_HOVER = "#C92A2A"
RED_SOFT = "#3D1111"
GOLD = "#F0B429"
LOCKED = "#7B8C9A"
SURFACE = "#13283C"


def normalize_fill(text: str) -> str:
    return " ".join((text or "").strip().lower().replace("'", "'").split())


def answers_match(expected: str, given: str) -> bool:
    exp = normalize_fill(expected)
    got = normalize_fill(given)
    if got == exp:
        return True
    aliases = {
        "going to": {"gonna", "going to"},
        "want to": {"wanna", "want to"},
        "got to": {"gotta", "got to", "have to"},
        "what are you": {"what are you", "whatcha", "what are you doing"},
    }
    for key, options in aliases.items():
        if exp == key and got in options:
            return True
    return False


@dataclass
class Session:
    track: Track
    lesson: Lesson
    index: int = 0
    on_theory: bool = True
    selected: Any = None
    checked: bool = False
    last_correct: bool | None = None
    correct_count: int = 0
    fill_value: str = ""


class InglesRealApp(ctk.CTk):
    def __init__(self, store: ProgressStore, audio: AudioEngine | SilentAudioEngine) -> None:
        super().__init__()
        self.store = store
        self.audio = audio
        self.session: Session | None = None
        self._placement_index = 0
        self._placement_correct = 0
        self._screen = 0
        self._boot_token = -1
        self._choice_buttons: list[ctk.CTkButton] = []
        self._feedback_bar: ctk.CTkFrame | None = None
        self._progress_bar: ctk.CTkProgressBar | None = None
        self._xp_label: ctk.CTkLabel | None = None
        self._level_label: ctk.CTkLabel | None = None
        self._fill_entry: ctk.CTkEntry | None = None
        self.exercise_host: ctk.CTkFrame | None = None

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.title("Inglês Real — inglês da vida nos EUA")
        self.geometry("1080x880")
        self.minsize(880, 700)
        self.configure(fg_color=("#F4F7FB", NAVY))

        self.header = ctk.CTkFrame(self, height=68, corner_radius=0, fg_color=("#FFFFFF", "#0A1A2B"))
        self.header.pack(fill="x")
        self.header.pack_propagate(False)
        ctk.CTkLabel(
            self.header,
            text="Inglês Real",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=SKY,
        ).pack(side="left", padx=20)
        self._level_label = ctk.CTkLabel(self.header, text="", font=ctk.CTkFont(size=14), text_color=LOCKED)
        self._level_label.pack(side="right", padx=(0, 18))
        self._xp_label = ctk.CTkLabel(self.header, text="0 XP", font=ctk.CTkFont(size=16, weight="bold"), text_color=GOLD)
        self._xp_label.pack(side="right", padx=8)

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=20, pady=16)
        self.after(80, self._boot)

    def _listen_button(self, parent: Any, english: str, width: int = 220) -> ctk.CTkButton:
        return ctk.CTkButton(
            parent,
            text=LISTEN_LABEL,
            width=width,
            height=36,
            fg_color=SKY,
            hover_color=SKY_HOVER,
            command=lambda t=english: self.audio.speak(t),
        )

    def _token(self) -> int:
        self._screen += 1
        self.audio.stop()
        for child in self.body.winfo_children():
            child.destroy()
        self._choice_buttons = []
        self._feedback_bar = None
        self._progress_bar = None
        self._fill_entry = None
        self.exercise_host = None
        return self._screen

    def _refresh_chrome(self) -> None:
        if self._xp_label is not None:
            self._xp_label.configure(text=f"{self.store.xp} XP")
        if self._level_label is not None:
            self._level_label.configure(text=self.store.level_label())

    def _boot(self) -> None:
        self.show_loading()
        self.after(120, self._finish_boot)

    def _finish_boot(self) -> None:
        if self._screen != self._boot_token:
            return
        try:
            validate_curriculum()
            self.store.load()
            self.audio.wait_ready(8.0)
        except ProgressError as exc:
            self.show_error(str(exc), allow_reset=True)
            return
        except Exception as exc:
            self.show_error(f"Falha ao iniciar: {exc}", allow_reset=False)
            return
        if self._screen != self._boot_token:
            return
        if not self.store.placement_completed:
            self.show_placement()
            return
        pos = self.store.position or {}
        if pos.get("screen") == "placement":
            self.show_placement(int(pos.get("step_index") or 0))
            return
        if pos.get("track_id") and pos.get("lesson_id"):
            self._resume_from_position(pos)
            return
        self.show_home()

    def _resume_from_position(self, pos: dict[str, Any]) -> None:
        track = track_by_id(str(pos.get("track_id")))
        lesson = lesson_by_id(str(pos.get("lesson_id")))
        if track is None or lesson is None:
            self.show_home()
            return
        step = int(pos.get("step_index") or 0)
        self.session = Session(track=track, lesson=lesson, index=max(0, step - 1), on_theory=step <= 0)
        if step <= 0:
            self.show_theory()
        else:
            self.session.on_theory = False
            self.session.index = min(step - 1, len(lesson.exercises) - 1)
            self._show_lesson_shell()
            self._render_exercise()

    def show_loading(self) -> None:
        self._boot_token = self._token()
        self._refresh_chrome()
        card = ctk.CTkFrame(self.body, fg_color=SURFACE)
        card.pack(expand=True, fill="both")
        ctk.CTkLabel(card, text="Carregando o Inglês Real…", font=ctk.CTkFont(size=26, weight="bold")).pack(pady=(80, 8))
        ctk.CTkLabel(
            card,
            text="Preparando o teste de nivelamento, o currículo e a voz Jenny (en-US).",
            font=ctk.CTkFont(size=15),
            text_color=LOCKED,
        ).pack()
        bar = ctk.CTkProgressBar(card, width=280, progress_color=SKY)
        bar.pack(pady=24)
        bar.configure(mode="indeterminate")
        bar.start()

    def show_error(self, message: str, allow_reset: bool) -> None:
        self._token()
        self._refresh_chrome()
        card = ctk.CTkFrame(self.body, fg_color=SURFACE)
        card.pack(expand=True, fill="both", padx=40, pady=40)
        ctk.CTkLabel(card, text="Algo deu errado", font=ctk.CTkFont(size=26, weight="bold"), text_color=RED).pack(
            pady=(40, 8)
        )
        ctk.CTkLabel(card, text=message, wraplength=640, font=ctk.CTkFont(size=15)).pack(pady=8, padx=24)
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(pady=20)
        ctk.CTkButton(row, text="Tentar de novo", fg_color=SKY, hover_color=SKY_HOVER, command=self._boot).pack(
            side="left", padx=8
        )
        if allow_reset:
            ctk.CTkButton(
                row,
                text="Restaurar progresso",
                fg_color=RED,
                hover_color=RED_HOVER,
                command=self._reset_progress,
            ).pack(side="left", padx=8)

    def _reset_progress(self) -> None:
        self.store.xp = 0
        self.store.placement_completed = False
        self.store.placement_result = None
        self.store.placement_score = 0
        self.store.unlocked_tracks = []
        self.store.completed_lessons = []
        self.store.completed_modules = []
        self.store.answers = {}
        self.store.position = {}
        self.store.save()
        self.show_placement()

    def show_home(self) -> None:
        self.session = None
        self._token()
        self._refresh_chrome()
        self.store.set_position(screen="home")
        scroll = ctk.CTkScrollableFrame(self.body, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        ctk.CTkLabel(scroll, text="Inglês da vida real (EUA)", font=ctk.CTkFont(size=26, weight="bold")).pack(
            anchor="w"
        )
        subtitle = (
            "Nível {level} · os módulos desse patamar já estão abertos. "
            "Feche o app quando quiser: o progresso fica em user_progress.json."
        ).format(level=self.store.level_label())
        ctk.CTkLabel(scroll, text=subtitle, font=ctk.CTkFont(size=14), text_color=LOCKED, wraplength=900).pack(
            anchor="w", pady=(0, 6)
        )
        voice = self.audio.voice or PRIMARY_VOICE
        ctk.CTkLabel(
            scroll,
            text=f"Pronúncia nativa: {voice} · {self.audio.status}",
            font=ctk.CTkFont(size=12),
            text_color=LOCKED,
        ).pack(anchor="w", pady=(0, 10))

        actions = ctk.CTkFrame(scroll, fg_color="transparent")
        actions.pack(fill="x", pady=(0, 12))
        target = self.store.continue_target()
        if target and target.get("lesson_id"):
            ctk.CTkButton(
                actions,
                text="Continuar de onde parei",
                fg_color=SKY,
                hover_color=SKY_HOVER,
                command=lambda: self._resume_from_position(target),
            ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            actions,
            text="Refazer teste de nivelamento",
            fg_color="transparent",
            border_width=1,
            command=self._confirm_retake,
        ).pack(side="left")

        for track in TRACKS:
            self._render_track_card(scroll, track)

    def _confirm_retake(self) -> None:
        self.store.retake_keeps_xp()
        self.show_placement()

    def _render_track_card(self, parent: Any, track: Track) -> None:
        unlocked = self.store.is_track_unlocked(track.id)
        card = ctk.CTkFrame(parent, fg_color=SURFACE)
        card.pack(fill="x", pady=8)
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=16, pady=(14, 6))
        title = track.title if unlocked else f"{track.title}  ·  bloqueado"
        ctk.CTkLabel(head, text=title, font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")
        done = sum(1 for lesson in track.lessons if self.store.is_lesson_complete(lesson.id))
        ctk.CTkLabel(
            head,
            text=f"{done}/{len(track.lessons)} lições",
            text_color=LOCKED,
            font=ctk.CTkFont(size=13),
        ).pack(side="right")
        ctk.CTkLabel(
            card,
            text=track.subtitle if unlocked else "Conclua o teste de nivelamento ou o desafio do módulo anterior.",
            wraplength=860,
            justify="left",
            text_color=LOCKED,
            font=ctk.CTkFont(size=13),
        ).pack(anchor="w", padx=16, pady=(0, 8))
        if not unlocked:
            return
        for lesson in track.lessons:
            self._render_lesson_row(card, track, lesson)

    def _render_lesson_row(self, parent: Any, track: Track, lesson: Lesson) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=4)
        open_ok = self.store.is_lesson_unlocked(track.id, lesson.id)
        done = self.store.is_lesson_complete(lesson.id)
        if done:
            badge = "concluída"
            color = GREEN
        elif open_ok:
            badge = "desafio" if lesson.kind == "challenge" else "aberta"
            color = GOLD if lesson.kind == "challenge" else SKY
        else:
            badge = "bloqueada"
            color = LOCKED
        ctk.CTkLabel(row, text=lesson.title, font=ctk.CTkFont(size=15, weight="bold")).pack(side="left")
        ctk.CTkLabel(row, text=badge, text_color=color, font=ctk.CTkFont(size=12)).pack(side="left", padx=10)
        if open_ok:
            ctk.CTkButton(
                row,
                text="Abrir",
                width=90,
                fg_color=SKY,
                hover_color=SKY_HOVER,
                command=lambda t=track, u=lesson: self.start_lesson(t, u),
            ).pack(side="right", pady=6)

    def start_lesson(self, track: Track, lesson: Lesson, step: int = 0) -> None:
        self.session = Session(track=track, lesson=lesson, index=max(0, step), on_theory=step <= 0)
        if step <= 0:
            self.show_theory()
        else:
            self.session.on_theory = False
            self._show_lesson_shell()
            self._render_exercise()

    def show_theory(self) -> None:
        assert self.session is not None
        self._token()
        self._refresh_chrome()
        session = self.session
        self.store.set_position(
            screen="theory",
            track_id=session.track.id,
            lesson_id=session.lesson.id,
            step_index=0,
        )
        theory = session.lesson.theory
        scroll = ctk.CTkScrollableFrame(self.body, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        top = ctk.CTkFrame(scroll, fg_color="transparent")
        top.pack(fill="x")
        ctk.CTkButton(top, text="← Trilha", width=90, fg_color="transparent", border_width=1, command=self.show_home).pack(
            side="left"
        )
        ctk.CTkLabel(top, text=session.lesson.title, font=ctk.CTkFont(size=20, weight="bold")).pack(side="left", padx=12)

        card = ctk.CTkFrame(scroll, fg_color=SURFACE)
        card.pack(fill="x", pady=12)
        ctk.CTkLabel(card, text=THEORY_CARD_TITLE, font=ctk.CTkFont(size=22, weight="bold"), text_color=SKY).pack(
            anchor="w", padx=18, pady=(16, 2)
        )
        ctk.CTkLabel(card, text=theory.subtitle, font=ctk.CTkFont(size=15), text_color=LOCKED, wraplength=880).pack(
            anchor="w", padx=18, pady=(0, 8)
        )
        listen_row = ctk.CTkFrame(card, fg_color="transparent")
        listen_row.pack(anchor="w", padx=18, pady=(0, 10))
        self._listen_button(listen_row, theory.visible_english()).pack(side="left")

        self._theory_section(card, "1. Conceito", theory.conceito)
        self._theory_section(card, "2. Cultura", theory.cultura)
        ctk.CTkLabel(card, text="3. Exemplos", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=18, pady=(8, 4))
        for example in theory.exemplos:
            box = ctk.CTkFrame(card, fg_color=("#E8EEF6", "#0F2438"))
            box.pack(fill="x", padx=18, pady=6)
            ctk.CTkLabel(
                box,
                text=example.en,
                font=ctk.CTkFont(size=16, weight="bold"),
                wraplength=820,
                justify="left",
                anchor="w",
            ).pack(anchor="w", padx=12, pady=(10, 2))
            ctk.CTkLabel(
                box,
                text=example.pt,
                font=ctk.CTkFont(size=14),
                text_color=LOCKED,
                wraplength=820,
                justify="left",
                anchor="w",
            ).pack(anchor="w", padx=12, pady=(0, 6))
            self._listen_button(box, example.en).pack(anchor="w", padx=12, pady=(0, 10))

        ctk.CTkButton(
            scroll,
            text="Ir para os exercícios",
            fg_color=GREEN,
            hover_color=GREEN_HOVER,
            height=44,
            command=self._begin_exercises,
        ).pack(anchor="e", pady=16)

        token = self._screen
        spoken = theory.visible_english()
        self.after(160, lambda t=token, s=spoken: self._speak_if_current(t, s))

    def _theory_section(self, parent: Any, title: str, body: str) -> None:
        ctk.CTkLabel(parent, text=title, font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=18, pady=(8, 2))
        ctk.CTkLabel(parent, text=body, wraplength=880, justify="left", anchor="w", font=ctk.CTkFont(size=14)).pack(
            anchor="w", padx=18, pady=(0, 6)
        )

    def _begin_exercises(self) -> None:
        if not self.session:
            return
        self.session.on_theory = False
        self.session.index = 0
        self._show_lesson_shell()
        self._render_exercise()

    def _show_lesson_shell(self) -> None:
        assert self.session is not None
        self._token()
        self._refresh_chrome()
        session = self.session
        top = ctk.CTkFrame(self.body, fg_color="transparent")
        top.pack(fill="x")
        ctk.CTkButton(top, text="← Trilha", width=90, fg_color="transparent", border_width=1, command=self.show_home).pack(
            side="left"
        )
        ctk.CTkLabel(top, text=session.lesson.title, font=ctk.CTkFont(size=18, weight="bold")).pack(side="left", padx=12)
        self._progress_bar = ctk.CTkProgressBar(self.body, progress_color=SKY)
        self._progress_bar.pack(fill="x", pady=(10, 8))
        self.exercise_host = ctk.CTkScrollableFrame(self.body, fg_color=SURFACE)
        self.exercise_host.pack(fill="both", expand=True)

    def _update_lesson_progress(self) -> None:
        if not self.session or not self._progress_bar:
            return
        total = len(self.session.lesson.exercises)
        done = self.session.index
        if self.session.checked and self.session.last_correct:
            done += 1
        self._progress_bar.set(min(1.0, done / max(1, total)))

    def _render_exercise(self) -> None:
        assert self.session is not None
        if self.exercise_host is None:
            self._show_lesson_shell()
        host = self.exercise_host
        assert host is not None
        for child in host.winfo_children():
            child.destroy()
        self._choice_buttons = []
        self._feedback_bar = None
        self._fill_entry = None
        session = self.session
        session.checked = False
        session.last_correct = None
        session.selected = None
        self._placement_locked = False
        exercise = session.lesson.exercises[session.index]
        self.store.set_position(
            screen="exercise",
            track_id=session.track.id,
            lesson_id=session.lesson.id,
            step_index=session.index + 1,
        )
        self._refresh_chrome()
        self._update_lesson_progress()
        self._paint_exercise(host, exercise, f"Pergunta {session.index + 1} de {len(session.lesson.exercises)}")
        token = self._screen
        self.after(140, lambda t=token, s=exercise.listen_en: self._speak_if_current(t, s))

    def _paint_exercise(self, host: Any, exercise: Exercise, caption: str, on_verify: Callable[[], None] | None = None) -> None:
        qrow = ctk.CTkFrame(host, fg_color="transparent")
        qrow.pack(fill="x", pady=(8, 4), padx=12)
        ctk.CTkLabel(qrow, text=caption, font=ctk.CTkFont(size=13), text_color=LOCKED).pack(side="left")
        self._listen_button(qrow, exercise.listen_en).pack(side="right")

        ctk.CTkLabel(
            host,
            text=exercise.prompt_pt,
            font=ctk.CTkFont(size=20, weight="bold"),
            wraplength=860,
            justify="left",
            anchor="w",
        ).pack(fill="x", pady=(8, 8), padx=12)

        phrase = ctk.CTkFrame(host, fg_color=("#E8EEF6", "#0F2438"))
        phrase.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkLabel(
            phrase,
            text=exercise.listen_en,
            font=ctk.CTkFont(size=16, weight="bold"),
            wraplength=820,
            justify="left",
            anchor="w",
        ).pack(anchor="w", padx=12, pady=(10, 6))
        self._listen_button(phrase, exercise.listen_en).pack(anchor="w", padx=12, pady=(0, 10))

        if exercise.kind == "fill":
            ctk.CTkLabel(host, text="Digite a resposta em inglês.", text_color=LOCKED, font=ctk.CTkFont(size=13)).pack(
                anchor="w", padx=12
            )
            self._fill_entry = ctk.CTkEntry(host, height=44, placeholder_text="Sua resposta")
            self._fill_entry.pack(fill="x", pady=8, padx=12)
            self._fill_entry.bind("<Return>", lambda _e: (on_verify or self._on_verify)())
        else:
            for idx, choice in enumerate(exercise.choices):
                row = ctk.CTkFrame(host, fg_color="transparent")
                row.pack(fill="x", padx=12, pady=4)
                spoken = None
                if idx < len(exercise.choice_en):
                    spoken = exercise.choice_en[idx]
                btn = ctk.CTkButton(
                    row,
                    text=choice,
                    anchor="w",
                    height=46,
                    fg_color=("#E9EEF0", "#1B2A31"),
                    text_color=("#102012", "#F4F7F8"),
                    hover_color=("#D5DEE3", "#243840"),
                    command=lambda c=choice, s=spoken: self._select_choice(c, s),
                )
                btn.pack(side="left", fill="x", expand=True)
                self._choice_buttons.append(btn)
                if spoken:
                    self._listen_button(row, spoken, width=200).pack(side="right", padx=(8, 0))

        action = ctk.CTkFrame(host, fg_color="transparent")
        action.pack(fill="x", pady=16, padx=12)
        ctk.CTkButton(
            action,
            text="Verificar",
            fg_color=GREEN,
            hover_color=GREEN_HOVER,
            height=42,
            command=on_verify or self._on_verify,
        ).pack(side="right")
        self._verify_btn = action.winfo_children()[-1]

    def _looks_english_choice(self, text: str) -> bool:
        if any(ch in text for ch in "áéíóúãõâêôçÁÉÍÓÚ"):
            return False
        return any(ch.isalpha() for ch in text) and text.isascii()

    def _select_choice(self, choice: str, spoken: str | None) -> None:
        if self.session and self.session.checked:
            return
        if getattr(self, "_placement_locked", False):
            return
        if self.session:
            self.session.selected = choice
        else:
            self._placement_selected = choice
        if spoken:
            self.audio.speak(spoken)
        for btn in self._choice_buttons:
            if btn.cget("text") == choice:
                btn.configure(border_width=2, border_color=SKY, fg_color=("#D9F0FF", "#1A3340"))
            else:
                btn.configure(border_width=0, fg_color=("#E9EEF0", "#1B2A31"))

    def _speak_if_current(self, token: int, text: str) -> None:
        if token != self._screen:
            return
        self.audio.speak(text)

    def _current_submission(self, exercise: Exercise) -> Any:
        if exercise.kind == "fill":
            return self._fill_entry.get() if self._fill_entry is not None else ""
        if self.session:
            return self.session.selected
        return getattr(self, "_placement_selected", None)

    def _is_correct(self, exercise: Exercise, submission: Any) -> bool:
        if exercise.kind == "fill":
            return answers_match(exercise.answer, str(submission or ""))
        return submission == exercise.answer

    def _on_verify(self) -> None:
        if not self.session or self.session.checked:
            return
        exercise = self.session.lesson.exercises[self.session.index]
        submission = self._current_submission(exercise)
        if exercise.kind != "fill" and not submission:
            self._flash_message("Escolha uma alternativa para verificar.")
            return
        if exercise.kind == "fill" and not str(submission).strip():
            self._flash_message("Digite uma resposta antes de verificar.")
            return
        correct = self._is_correct(exercise, submission)
        self.session.checked = True
        self.session.last_correct = correct
        if correct:
            self.session.correct_count += 1
            self.store.add_xp(XP_PER_CORRECT)
        self.store.record_answer(
            exercise.id,
            {"correct": correct, "submission": submission, "lesson": self.session.lesson.id},
        )
        self._refresh_chrome()
        self._update_lesson_progress()
        self._paint_result(exercise, correct, submission)
        explain = exercise.explain_correct if correct else exercise.explain_wrong
        self._show_feedback(correct, explain, on_continue=self._on_continue, on_retry=self._retry_exercise)

    def _paint_result(self, exercise: Exercise, correct: bool, submission: Any) -> None:
        color = GREEN if correct else RED
        if exercise.kind != "fill":
            for btn in self._choice_buttons:
                text = btn.cget("text")
                if correct and text == exercise.answer:
                    btn.configure(fg_color=GREEN, border_color=GREEN, border_width=2, text_color="white")
                elif (not correct) and text == submission:
                    btn.configure(fg_color=RED, border_color=RED, border_width=2, text_color="white")
                btn.configure(state="disabled")
        elif self._fill_entry is not None:
            self._fill_entry.configure(border_color=color, state="disabled")
        try:
            self._verify_btn.configure(state="disabled")
        except Exception:
            pass

    def _show_feedback(self, correct: bool, message: str, on_continue: Callable[[], None], on_retry: Callable[[], None]) -> None:
        host = self.exercise_host
        if host is None:
            return
        if self._feedback_bar is not None:
            self._feedback_bar.destroy()
        bg = GREEN_SOFT if correct else RED_SOFT
        fg = GREEN if correct else RED
        title = "Correto!  +10 XP" if correct else "Incorreto"
        bar = ctk.CTkFrame(host, fg_color=bg)
        bar.pack(fill="x", pady=(8, 12), padx=12)
        ctk.CTkLabel(bar, text=title, font=ctk.CTkFont(size=16, weight="bold"), text_color=fg).pack(
            anchor="w", padx=12, pady=(10, 2)
        )
        ctk.CTkLabel(bar, text=message, wraplength=820, justify="left", anchor="w").pack(anchor="w", padx=12, pady=(0, 8))
        actions = ctk.CTkFrame(bar, fg_color="transparent")
        actions.pack(anchor="e", padx=12, pady=(0, 12))
        if correct:
            ctk.CTkButton(actions, text="Continuar", fg_color=fg, hover_color=GREEN_HOVER, command=on_continue).pack(
                side="right"
            )
        else:
            ctk.CTkButton(actions, text="Avançar", fg_color=fg, hover_color=RED_HOVER, command=on_continue).pack(
                side="right", padx=(8, 0)
            )
            ctk.CTkButton(
                actions,
                text="Tentar de novo",
                fg_color="transparent",
                border_width=1,
                border_color=fg,
                text_color=fg,
                command=on_retry,
            ).pack(side="right")
        self._feedback_bar = bar

    def _retry_exercise(self) -> None:
        if self.session:
            self._render_exercise()

    def _flash_message(self, text: str) -> None:
        host = self.exercise_host
        if host is None:
            return
        if self._feedback_bar is not None:
            self._feedback_bar.destroy()
        bar = ctk.CTkFrame(host, fg_color=("#FFF4CC", "#3D3411"))
        bar.pack(fill="x", pady=8, padx=12)
        ctk.CTkLabel(bar, text=text, font=ctk.CTkFont(size=14)).pack(padx=12, pady=10)
        self._feedback_bar = bar

    def _on_continue(self) -> None:
        if not self.session or not self.session.checked:
            return
        self.session.index += 1
        if self.session.index >= len(self.session.lesson.exercises):
            self._finish_lesson()
            return
        self._render_exercise()

    def _finish_lesson(self) -> None:
        assert self.session is not None
        session = self.session
        total = len(session.lesson.exercises)
        needed = challenge_pass_threshold(total)
        passed = session.correct_count >= needed
        self.audio.stop()
        self._token()
        self._refresh_chrome()
        card = ctk.CTkFrame(self.body, fg_color=SURFACE)
        card.pack(expand=True, fill="both", padx=24, pady=24)
        if session.lesson.kind == "challenge" and not passed:
            title = "Ainda não passou"
            body = (
                f"Você acertou {session.correct_count} de {total}. "
                f"É preciso acertar pelo menos {needed} para concluir o módulo. "
                "Pode tentar de novo quando quiser — sem vidas, sem bloqueio."
            )
            color = RED
        else:
            self.store.mark_lesson_complete(session.lesson.id, session.lesson.xp_bonus)
            title = "Desafio concluído" if session.lesson.kind == "challenge" else "Lição concluída"
            extra = ""
            if session.lesson.kind == "challenge":
                extra = " O próximo módulo da trilha está liberado."
            body = (
                f"Você acertou {session.correct_count} de {total}. "
                f"+{session.lesson.xp_bonus} XP de bônus.{extra}"
            )
            color = GREEN
        self._refresh_chrome()
        ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=28, weight="bold"), text_color=color).pack(pady=(40, 10))
        ctk.CTkLabel(card, text=body, wraplength=640, font=ctk.CTkFont(size=16)).pack(padx=24, pady=8)
        ctk.CTkButton(card, text="Voltar à trilha", fg_color=SKY, hover_color=SKY_HOVER, command=self.show_home).pack(
            pady=22
        )
        self.store.set_position(screen="home")
        self.session = None

    def show_placement(self, start_at: int = 0) -> None:
        self.session = None
        self._placement_index = start_at
        self._placement_correct = 0
        self._placement_locked = False
        self._placement_selected = None
        self._token()
        self._refresh_chrome()
        self.store.set_position(screen="placement", step_index=start_at)
        intro = ctk.CTkFrame(self.body, fg_color="transparent")
        intro.pack(fill="x")
        ctk.CTkLabel(intro, text="Teste de nivelamento", font=ctk.CTkFont(size=24, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(
            intro,
            text="Perguntas progressivas (fácil → difícil). O resultado destrava Básico, Intermediário ou tudo até Fluência. "
            "Refazer depois não apaga o XP.",
            wraplength=900,
            justify="left",
            text_color=LOCKED,
        ).pack(anchor="w", pady=(0, 8))
        self._progress_bar = ctk.CTkProgressBar(self.body, progress_color=SKY)
        self._progress_bar.pack(fill="x", pady=(4, 8))
        self.exercise_host = ctk.CTkScrollableFrame(self.body, fg_color=SURFACE)
        self.exercise_host.pack(fill="both", expand=True)
        self._render_placement_item()

    def _render_placement_item(self) -> None:
        host = self.exercise_host
        assert host is not None
        for child in host.winfo_children():
            child.destroy()
        self._choice_buttons = []
        self._feedback_bar = None
        self._fill_entry = None
        self._placement_locked = False
        self._placement_selected = None
        exercise = PLACEMENT[self._placement_index]
        self.store.set_position(screen="placement", step_index=self._placement_index)
        if self._progress_bar:
            self._progress_bar.set(self._placement_index / max(1, len(PLACEMENT)))
        self._paint_exercise(
            host,
            exercise,
            f"Nivelamento {self._placement_index + 1} de {len(PLACEMENT)}",
            on_verify=self._on_placement_verify,
        )
        token = self._screen
        self.after(140, lambda t=token, s=exercise.listen_en: self._speak_if_current(t, s))

    def _on_placement_verify(self) -> None:
        if self._placement_locked:
            return
        exercise = PLACEMENT[self._placement_index]
        submission = self._current_submission(exercise)
        if not submission:
            self._flash_message("Escolha uma alternativa para verificar.")
            return
        correct = self._is_correct(exercise, submission)
        self._placement_locked = True
        if correct:
            self._placement_correct += 1
            self.store.add_xp(XP_PER_CORRECT)
        self.store.record_answer(exercise.id, {"correct": correct, "submission": submission, "lesson": "placement"})
        self._refresh_chrome()
        self._paint_result(exercise, correct, submission)
        explain = exercise.explain_correct if correct else exercise.explain_wrong
        self._show_feedback(correct, explain, on_continue=self._placement_next, on_retry=self._render_placement_item)

    def _placement_next(self) -> None:
        self._placement_index += 1
        if self._placement_index >= len(PLACEMENT):
            self._finish_placement()
            return
        self._render_placement_item()

    def _finish_placement(self) -> None:
        level = self.store.apply_placement(self._placement_correct, len(PLACEMENT))
        label = LEVEL_LABELS[level]
        self._token()
        self._refresh_chrome()
        card = ctk.CTkFrame(self.body, fg_color=SURFACE)
        card.pack(expand=True, fill="both", padx=24, pady=24)
        ctk.CTkLabel(card, text=f"Você está no nível {label}", font=ctk.CTkFont(size=28, weight="bold"), text_color=SKY).pack(
            pady=(48, 10)
        )
        unlocked = ", ".join(
            track.title for track in TRACKS if self.store.is_track_unlocked(track.id)
        )
        ctk.CTkLabel(
            card,
            text=(
                f"Acertos no teste: {self._placement_correct} de {len(PLACEMENT)}. "
                f"Módulos liberados: {unlocked}. "
                "Quem já sabe não recomeça do zero. Você pode refazer o teste depois, sem perder XP."
            ),
            wraplength=640,
            font=ctk.CTkFont(size=16),
        ).pack(padx=24, pady=8)
        ctk.CTkButton(card, text="Ir para a trilha", fg_color=SKY, hover_color=SKY_HOVER, command=self.show_home).pack(
            pady=22
        )
