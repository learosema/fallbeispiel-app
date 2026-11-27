"""Casting: entwirft pro Stimme einen Referenzclip mit Qwen3-TTS VoiceDesign → audio/voices/<key>.wav (+ .txt).

Die Referenz prägt Klang und Stimmung aller Sätze, die render.py später von ihr klont. Erst anhören, dann vertonen.

  python tools/tts/cast.py                 # alle fehlenden Stimmen
  python tools/tts/cast.py --redo KEY ...  # einzelne Stimmen neu würfeln (z. B. weil sie nicht passen)
  python tools/tts/cast.py --list          # nur anzeigen, was es gibt / was fehlt

Läuft auf CPU (ca. 1 min pro Stimme) oder GPU. Abhängigkeiten: tools/tts/requirements.txt
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend import speech  # noqa: E402

DESIGN_MODEL = "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--redo", nargs="*", default=[], help="Schlüssel, die neu gecastet werden sollen")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--takes", type=int, default=1,
                    help="mehrere Takes pro Stimme: Take 1 = <key>.wav, weitere <key>~2.wav … (zum Aussuchen; "
                         "den gewählten dann nach <key>.wav kopieren und die übrigen löschen)")
    ap.add_argument("--device", default=None, help="cuda:0 | cpu (Standard: cuda, wenn vorhanden)")
    args = ap.parse_args()

    voices = [v for v in speech.voices_in_use(speech.collect()) if v.engine == "qwen"]
    speech.VOICES_DIR.mkdir(parents=True, exist_ok=True)
    todo = [v for v in voices if v.key in args.redo or not (speech.VOICES_DIR / f"{v.key}.wav").exists()]
    if args.list:
        for v in voices:
            print(("fehlt " if v in todo else "ok    ") + v.key)
        return
    if not todo:
        print("Alle Stimmen gecastet.")
        return

    import soundfile as sf
    import torch
    from qwen_tts import Qwen3TTSModel

    device = args.device or ("cuda:0" if torch.cuda.is_available() else "cpu")
    dtype = torch.bfloat16 if device.startswith("cuda") else torch.float32
    model = Qwen3TTSModel.from_pretrained(DESIGN_MODEL, device_map=device, dtype=dtype)
    for n, v in enumerate(todo, 1):
        text = speech.reference_text(v)
        for take in range(1, args.takes + 1):
            name = v.key if take == 1 else f"{v.key}~{take}"
            t = time.time()
            wavs, sr = model.generate_voice_design(text=text, language="German", instruct=v.design)
            sf.write(speech.VOICES_DIR / f"{name}.wav", wavs[0], sr, subtype="PCM_16")
            (speech.VOICES_DIR / f"{name}.txt").write_text(text + "\n", encoding="utf-8")
            meta = {"role": v.role, "scenario": v.scenario, "design": v.design}
            if args.takes > 1:
                meta["label"] = f"Take {take}"
            (speech.VOICES_DIR / f"{name}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            print(f"[{n}/{len(todo)}] {name}  {len(wavs[0]) / sr:.1f} s Audio in {time.time() - t:.0f} s", flush=True)


if __name__ == "__main__":
    main()
