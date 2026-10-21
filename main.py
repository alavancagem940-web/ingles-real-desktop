#!/usr/bin/env python3
"""Inglês Real — tutor desktop de inglês americano (não é o TrilhaPy)."""

from __future__ import annotations

import sys
import traceback


def _fail_without_deps() -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox
    except Exception:
        print(
            "Instale python3-tk e as dependências: pip install -r requirements.txt",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(
        "Inglês Real",
        "Não foi possível iniciar a interface.\n\n"
        "Crie um ambiente virtual e instale as dependências:\n"
        "python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt\n\n"
        "Depois rode: python main.py",
    )


def main() -> None:
    try:
        import customtkinter  # noqa: F401
    except ImportError:
        _fail_without_deps()
        return

    from audio_engine import default_engine
    from database import ProgressStore
    from ui import InglesRealApp

    audio = default_engine()
    store = ProgressStore()
    app = InglesRealApp(store, audio)

    def on_close() -> None:
        try:
            audio.shutdown()
        except Exception:
            pass
        app.destroy()

    app.protocol("WM_DELETE_WINDOW", on_close)
    try:
        app.mainloop()
    except Exception:
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
