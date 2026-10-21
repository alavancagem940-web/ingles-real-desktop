"""Neural American TTS for Inglês Real.

Synthesizes with `edge-tts` on a background thread and plays through
`pygame.mixer` (never pyttsx3, playsound, or aplay). Missing audio
devices do not crash the app.
"""

from __future__ import annotations

import asyncio
import os
import queue
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

PRIMARY_VOICE = "en-US-JennyNeural"
FALLBACK_VOICE = "en-US-AnaNeural"
PREFERRED_VOICES = (PRIMARY_VOICE, FALLBACK_VOICE)

# Listening-training: slightly slow, soft/velvety, not rushed or bright.
SPEECH_RATE = "-10%"
SPEECH_PITCH = "-5Hz"
SPEECH_VOLUME = "+0%"

_FORBIDDEN_VOICES = (
    "pt-BR-FranciscaNeural",
    "pt-BR-ThaliaNeural",
    "pt-BR-GiovannaNeural",
)


def pick_preferred_voice(voices: list[dict[str, Any]] | None = None) -> str:
    """Jenny, else Ana. Never another locale — even if the catalog lists it."""
    names = {str(item.get("ShortName", "")) for item in (voices or [])}
    if PRIMARY_VOICE in names or not names:
        return PRIMARY_VOICE
    if FALLBACK_VOICE in names:
        return FALLBACK_VOICE
    return PRIMARY_VOICE


def _clean(text: str) -> str:
    return " ".join((text or "").split())


class AudioEngine:
    def __init__(self) -> None:
        self.backend = "none"
        self.voice = PRIMARY_VOICE
        self.status = "iniciando"
        self.mixer_ok = False
        self.mixer_driver = ""
        self._queue: queue.Queue[str] = queue.Queue()
        self._ready = threading.Event()
        self._cancel = threading.Event()
        self._lock = threading.Lock()
        self._pending = ""
        self._speak_queued = False
        self._mixer_lock = threading.Lock()
        self._init_mixer_once()
        self._thread = threading.Thread(target=self._worker, name="ingles-tts", daemon=True)
        self._thread.start()

    def wait_ready(self, timeout: float = 8.0) -> bool:
        return self._ready.wait(timeout)

    def speak(self, text: str) -> None:
        """Queue English speech. Cancels the current utterance. Never blocks the UI."""
        cleaned = _clean(text)
        if not cleaned:
            return
        with self._lock:
            self._pending = cleaned
            self._cancel.set()
            self._stop_mixer()
            if not self._speak_queued:
                self._speak_queued = True
                self._queue.put("speak")

    def stop(self) -> None:
        with self._lock:
            self._pending = ""
            self._cancel.set()
            self._stop_mixer()
            self._queue.put("stop")

    def shutdown(self) -> None:
        self.stop()
        self._queue.put("quit")

    def _init_mixer_once(self) -> None:
        """Initialize pygame mixer a single time. Dummy driver if the device is missing."""
        try:
            import pygame
        except Exception:
            self.mixer_ok = False
            self.mixer_driver = "unavailable"
            self.status = "pygame ausente"
            return

        if pygame.mixer.get_init():
            self.mixer_ok = True
            self.mixer_driver = os.environ.get("SDL_AUDIODRIVER", "default")
            return

        drivers = []
        current = os.environ.get("SDL_AUDIODRIVER")
        if current:
            drivers.append(current)
        for name in ("pulse", "alsa", "pipewire", "dummy"):
            if name not in drivers:
                drivers.append(name)

        for driver in drivers:
            try:
                os.environ["SDL_AUDIODRIVER"] = driver
                try:
                    pygame.mixer.quit()
                except Exception:
                    pass
                pygame.mixer.pre_init(frequency=22050, size=-16, channels=1, buffer=1024)
                pygame.mixer.init()
                if pygame.mixer.get_init():
                    try:
                        pygame.mixer.music.set_volume(1.0)
                    except Exception:
                        pass
                    self.mixer_ok = driver != "dummy"
                    self.mixer_driver = driver
                    return
            except Exception:
                continue

        self.mixer_ok = False
        self.mixer_driver = "none"

    def _stop_mixer(self) -> None:
        try:
            import pygame

            if pygame.mixer.get_init():
                with self._mixer_lock:
                    try:
                        pygame.mixer.music.stop()
                    except Exception:
                        pass
                    try:
                        pygame.mixer.stop()
                    except Exception:
                        pass
        except Exception:
            pass

    def _set_status(self) -> None:
        if self.backend == "edge-tts" and self.voice:
            device = "pygame" if self.mixer_ok else f"pygame ({self.mixer_driver or 'sem dispositivo'})"
            self.status = f"{self.voice} · edge-tts · {device}"
        elif self.backend == "edge-tts":
            self.status = "edge-tts"
        else:
            self.status = "voz indisponível"

    def _worker(self) -> None:
        self.backend = self._detect_backend()
        if self.backend == "edge-tts":
            self.voice = self._resolve_neural_voice()
        self._set_status()
        self._ready.set()
        while True:
            cmd = self._queue.get()
            if cmd == "quit":
                self._stop_mixer()
                break
            if cmd == "stop":
                self._cancel.set()
                self._stop_mixer()
                continue
            if cmd != "speak":
                continue
            with self._lock:
                self._speak_queued = False
                text = self._pending
                self._cancel.clear()
            if not text:
                continue
            try:
                self._utter(text)
            except Exception:
                self.status = "falha ao falar; tente Ouvir Pronúncia Nativa de novo"

    def _detect_backend(self) -> str:
        try:
            import edge_tts  # noqa: F401

            return "edge-tts"
        except Exception:
            return "none"

    def _resolve_neural_voice(self) -> str:
        try:
            import edge_tts

            voices = asyncio.run(asyncio.wait_for(edge_tts.list_voices(), timeout=6))
            chosen = pick_preferred_voice(list(voices or []))
            if chosen in _FORBIDDEN_VOICES:
                return PRIMARY_VOICE
            return chosen
        except Exception:
            return PRIMARY_VOICE

    def _utter(self, text: str) -> None:
        if self._cancel.is_set():
            return
        if self.backend != "edge-tts":
            self.status = "edge-tts não instalado"
            return
        voices = []
        current = self.voice if self.voice in PREFERRED_VOICES else PRIMARY_VOICE
        voices.append(current)
        for candidate in PREFERRED_VOICES:
            if candidate not in voices:
                voices.append(candidate)

        handle = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        path = handle.name
        handle.close()
        try:
            for voice in voices:
                if self._cancel.is_set():
                    return
                if self._synthesize_edge(text, voice, path):
                    self.voice = voice
                    self.backend = "edge-tts"
                    self._set_status()
                    if self._cancel.is_set():
                        return
                    self._play_pygame(path)
                    return
            self.status = "falha no edge-tts (Jenny/Ana)"
        finally:
            try:
                Path(path).unlink(missing_ok=True)
            except OSError:
                pass

    def _synthesize_edge(self, text: str, voice: str, path: str) -> bool:
        if voice in _FORBIDDEN_VOICES:
            return False
        try:
            import edge_tts
        except Exception:
            return False

        async def _write() -> bool:
            communicate = edge_tts.Communicate(
                text,
                voice,
                rate=SPEECH_RATE,
                pitch=SPEECH_PITCH,
                volume=SPEECH_VOLUME,
            )
            with open(path, "wb") as out:
                async for chunk in communicate.stream():
                    if self._cancel.is_set():
                        return False
                    if chunk.get("type") == "audio":
                        out.write(chunk["data"])
            return Path(path).stat().st_size > 0

        for _attempt in range(2):
            if self._cancel.is_set():
                return False
            try:
                if asyncio.run(_write()):
                    return True
            except Exception:
                time.sleep(0.35)
        return False

    def _play_pygame(self, path: str) -> bool:
        """Loud playback through pygame.mixer.music. No aplay/playsound."""
        try:
            import pygame
        except Exception:
            return False
        if not pygame.mixer.get_init():
            self._init_mixer_once()
        if not pygame.mixer.get_init():
            return False
        try:
            with self._mixer_lock:
                pygame.mixer.music.stop()
                pygame.mixer.music.load(path)
                pygame.mixer.music.set_volume(1.0)
                pygame.mixer.music.play()
            while True:
                if self._cancel.is_set():
                    self._stop_mixer()
                    return True
                busy = False
                try:
                    busy = pygame.mixer.music.get_busy()
                except Exception:
                    break
                if not busy:
                    break
                time.sleep(0.05)
            return True
        except Exception:
            return False


class SilentAudioEngine:
    """Drop-in stand-in for tests and environments without a voice."""

    backend = "silent"
    voice = PRIMARY_VOICE
    status = "silencioso (teste)"
    mixer_ok = False
    mixer_driver = "silent"

    def wait_ready(self, timeout: float = 8.0) -> bool:
        return True

    def speak(self, text: str) -> None:
        return None

    def stop(self) -> None:
        return None

    def shutdown(self) -> None:
        return None


def default_engine() -> AudioEngine | SilentAudioEngine:
    if os.environ.get("INGLES_REAL_SILENT") == "1":
        return SilentAudioEngine()
    return AudioEngine()
