"""Piper auf dem Server: Sätze, die von den Einstellungen abhängen (Leitstelle mit Rufname), auf Zuruf vertonen.

Die Stimme (ca. 60 MB) wird beim ersten Gebrauch von Hugging Face geladen und unter PIPER_DIR abgelegt (im Docker-Volume
/models). Erzeugte Clips landen in audio/cache/ und werden wiederverwendet. Fehlt Piper oder geht etwas schief, gibt es
keinen Clip – das Frontend spricht dann mit der Browserstimme.
"""
from __future__ import annotations

import logging
import os
import threading
import urllib.request
import wave
from io import BytesIO
from pathlib import Path

from . import speech

log = logging.getLogger(__name__)
PIPER_DIR = Path(os.environ.get("PIPER_DIR") or (Path(os.environ.get("HF_HOME", Path.home() / ".cache")) / "piper"))
CACHE_DIR = speech.AUDIO_DIR / "cache"
VOICES_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main"

_lock = threading.Lock()
_voices: dict[str, object] = {}


def enabled() -> bool:
    if os.environ.get("PIPER", "1") == "0":
        return False
    try:
        import piper  # noqa: F401
        return True
    except ImportError:
        return False


def _model_path(model: str) -> Path:
    """de_DE-kerstin-medium → …/de/de_DE/kerstin/medium/de_DE-kerstin-medium.onnx (wird bei Bedarf geladen)."""
    path = PIPER_DIR / f"{model}.onnx"
    if path.exists() and path.with_suffix(".onnx.json").exists():
        return path
    lang, name, quality = model.split("-", 2)
    base = f"{VOICES_URL}/{lang.split('_')[0]}/{lang}/{name}/{quality}/{model}"
    PIPER_DIR.mkdir(parents=True, exist_ok=True)
    for suffix in (".onnx.json", ".onnx"):
        tmp = PIPER_DIR / f".{model}{suffix}.part"
        log.info("Lade Piper-Stimme %s%s", model, suffix)
        with urllib.request.urlopen(f"{base}{suffix}", timeout=60) as r, open(tmp, "wb") as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
        tmp.rename(PIPER_DIR / f"{model}{suffix}")
    return path


def _voice(model: str):
    if model not in _voices:
        from piper import PiperVoice
        _voices[model] = PiperVoice.load(_model_path(model))
    return _voices[model]


def preload(model: str) -> None:
    with _lock:
        _voice(model)


def funk(pcm, sr: int):
    """Digitalfunk, leicht: Telefonband (ca. 280–3500 Hz), sanfte Kompression, kurze Verzögerung – kein Rauschen."""
    import numpy as np

    x = pcm.astype(np.float32) / 32768
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / sr)
    lo, hi, s = 280.0, 3480.0, 0.2
    band = 1 / (1 + (lo / np.maximum(f, 1)) ** 4) / (1 + (f / hi) ** 8) * (1 + 0.35 * s * np.exp(-((f - 1800) / 700) ** 2))
    x = np.fft.irfft(spec * band, len(x))
    x /= np.abs(x).max() + 1e-9
    k = 1 + 1.5 * s
    x = np.tanh(k * x) / np.tanh(k)
    gap = np.zeros(int(0.12 * sr), np.float32)
    return (np.clip(np.concatenate([gap, x * 0.8, gap]), -1, 1) * 32767).astype("<i2")


def _mp3(pcm, sr: int) -> bytes:
    import lameenc
    enc = lameenc.Encoder()
    enc.set_bit_rate(48); enc.set_in_sample_rate(sr); enc.set_channels(1); enc.set_quality(2)
    return enc.encode(pcm.tobytes()) + enc.flush()


def render(clip: speech.Clip) -> Path:
    """Clip erzeugen (oder aus dem Cache) und den Pfad zurückgeben."""
    path = CACHE_DIR / f"{clip.id}.mp3"
    if path.exists():
        return path
    import numpy as np

    with _lock:  # Piper ist nicht threadsicher; ein Satz dauert ~0,2 s
        if path.exists():
            return path
        voice = _voice(clip.voice.model)
        buf = BytesIO()
        with wave.open(buf, "wb") as w:
            voice.synthesize_wav(clip.text, w)
        buf.seek(0)
        with wave.open(buf, "rb") as w:
            sr = w.getframerate()
            pcm = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
        if clip.voice.filter.startswith("funk"):
            pcm = funk(pcm, sr)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".part")
        tmp.write_bytes(_mp3(pcm, sr))
        tmp.rename(path)
    return path
