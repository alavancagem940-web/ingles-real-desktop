from audio_engine import (
    FALLBACK_VOICE,
    PRIMARY_VOICE,
    SPEECH_PITCH,
    SPEECH_RATE,
    pick_preferred_voice,
)


def test_voice_is_jenny_with_ana_fallback() -> None:
    assert PRIMARY_VOICE == "en-US-JennyNeural"
    assert FALLBACK_VOICE == "en-US-AnaNeural"
    assert "pt-BR" not in PRIMARY_VOICE
    assert "Francisca" not in PRIMARY_VOICE


def test_listening_training_prosody() -> None:
    assert SPEECH_RATE == "-10%"
    assert SPEECH_PITCH == "-5Hz"


def test_pick_preferred_voice_never_leaves_en_us() -> None:
    catalog = [
        {"ShortName": "pt-BR-FranciscaNeural", "Locale": "pt-BR", "Gender": "Female"},
        {"ShortName": "en-US-JennyNeural", "Locale": "en-US", "Gender": "Female"},
        {"ShortName": "en-US-AnaNeural", "Locale": "en-US", "Gender": "Female"},
    ]
    assert pick_preferred_voice(catalog) == "en-US-JennyNeural"
    assert pick_preferred_voice([]) == "en-US-JennyNeural"
    assert pick_preferred_voice([{"ShortName": "en-US-AnaNeural"}]) == "en-US-AnaNeural"


def test_engine_uses_edge_tts_and_pygame() -> None:
    source = open("audio_engine.py", encoding="utf-8").read()
    assert "import edge_tts" in source
    assert "import pygame" in source
    assert "pygame.mixer" in source
    assert "import pyttsx3" not in source
    assert "import playsound" not in source
    assert "which(\"aplay\")" not in source
    assert '["aplay"' not in source
    assert "aplay -q" not in source
