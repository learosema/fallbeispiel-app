"""Vertonung: klont alle Sätze von den Referenzstimmen (audio/voices/) mit Qwen3-TTS Base → audio/clips/<id>.mp3.

Fortsetzbar: Was schon da ist, wird übersprungen. Ohne Referenzclip (cast.py) wird eine Stimme ausgelassen.

  python tools/tts/render.py --status        # wie viele Clips fehlen, pro Stimme
  python tools/tts/render.py                 # alles Fehlende vertonen (GPU empfohlen: ca. 1450 Clips)
  python tools/tts/render.py --voice KEY     # nur eine Stimme (z. B. nach neuem Casting)
  python tools/tts/render.py --prune         # Clips löschen, die kein Text mehr braucht

Abhängigkeiten: tools/tts/requirements.txt
"""
from __future__ import annotations

import argparse
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend import speech  # noqa: E402

BASE_MODEL = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
TARGET_RMS_DB = -20.0   # alle Stimmen gleich laut
PEAK = 0.95
# Plausible Sprechgeschwindigkeit (Zeichen pro Sekunde). Deutlich schneller = Modell hat vermutlich Text verschluckt,
# deutlich langsamer = Stottern/Endlosschleife. Solche Clips werden bis zu RETRIES-mal neu erzeugt, sonst gemeldet.
CPS_MIN, CPS_MAX, RETRIES = 4.0, 22.0, 2
SUSPECT = "suspect.txt"  # Liste der Clips, die auch nach den Wiederholungen auffällig waren (in audio/clips/)


def plausible(text: str, seconds: float) -> bool:
    if len(text) < 12:  # „Ja.“, „Hm.“: zu kurz für eine Aussage
        return 0.2 < seconds < 4
    return CPS_MIN <= len(text) / max(seconds, 0.01) <= CPS_MAX


def trim(audio, sr: int):
    """Stille am Anfang/Ende kürzen (bis auf 80 ms)."""
    import numpy as np

    x = np.asarray(audio, dtype=np.float32)
    if x.ndim > 1:
        x = x.mean(axis=1)
    loud = np.flatnonzero(np.abs(x) > 0.01)
    if loud.size:
        pad = int(0.08 * sr)
        x = x[max(0, loud[0] - pad): loud[-1] + pad]
    return x


def spoken_seconds(audio, sr: int) -> float:
    """Länge so, wie sie später im Clip steht (ohne Stille) – darauf bezieht sich die Plausibilitätsprüfung."""
    return len(trim(audio, sr)) / sr


def to_mp3(audio, sr: int) -> bytes:
    import lameenc
    import numpy as np

    x = trim(audio, sr)  # dann Lautheit angleichen
    rms = float(np.sqrt(np.mean(x ** 2))) or 1e-6
    x = x * min(10 ** (TARGET_RMS_DB / 20) / rms, PEAK / (float(np.abs(x).max()) or 1e-6))
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    enc = lameenc.Encoder()
    enc.set_bit_rate(48); enc.set_in_sample_rate(sr); enc.set_channels(1); enc.set_quality(2)
    return enc.encode(pcm.tobytes()) + enc.flush()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--prune", action="store_true")
    ap.add_argument("--voice", nargs="*", default=[])
    ap.add_argument("--batch", type=int, default=None, help="Sätze pro Durchlauf (GPU: 8, CPU: 1)")
    ap.add_argument("--limit", type=int, default=0, help="höchstens so viele Clips (zum Testen)")
    ap.add_argument("--device", default=None)
    args = ap.parse_args()

    clips = speech.collect()
    speech.CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    have = {p.stem for p in speech.CLIPS_DIR.glob("*.mp3")}

    if args.prune:
        wanted = {c.id for c in clips}
        old = sorted(have - wanted)
        for cid in old:
            (speech.CLIPS_DIR / f"{cid}.mp3").unlink()
        print(f"{len(old)} veraltete Clips gelöscht, {len(have & wanted)} bleiben.")
        return

    todo: dict[str, list[speech.Clip]] = defaultdict(list)
    for c in clips:
        if c.id not in have and (not args.voice or c.voice.key in args.voice):
            todo[c.voice.key].append(c)
    no_ref = [k for k in todo if not (speech.VOICES_DIR / f"{k}.wav").exists()]

    if args.status:
        total = len(clips)
        print(f"{total - sum(map(len, todo.values()))}/{total} Clips vorhanden")
        for k, cs in sorted(todo.items(), key=lambda kv: -len(kv[1])):
            print(f"  {len(cs):4d} fehlen  {k}" + ("  (noch kein Casting)" if k in no_ref else ""))
        return
    for k in no_ref:
        print(f"überspringe {k}: kein Referenzclip – erst tools/tts/cast.py", file=sys.stderr)
        del todo[k]
    if not todo:
        print("Nichts zu tun.")
        return

    import torch
    from qwen_tts import Qwen3TTSModel

    device = args.device or ("cuda:0" if torch.cuda.is_available() else "cpu")
    gpu = device.startswith("cuda")
    batch = args.batch or (8 if gpu else 1)
    # bfloat16 erst ab Ampere (A100, L4); die T4 in Colab kann nur float16
    dtype = (torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16) if gpu else torch.float32
    model = Qwen3TTSModel.from_pretrained(BASE_MODEL, device_map=device, dtype=dtype)
    print(f"Modell auf {device} ({dtype}), {batch} Sätze pro Durchlauf", flush=True)

    done, total, t0 = 0, sum(map(len, todo.values())), time.time()
    if args.limit:
        total = min(total, args.limit)
    for key, cs in todo.items():
        ref = speech.VOICES_DIR / f"{key}.wav"
        ref_text = (speech.VOICES_DIR / f"{key}.txt").read_text(encoding="utf-8").strip()
        prompt = model.create_voice_clone_prompt(ref_audio=str(ref), ref_text=ref_text)
        for i in range(0, len(cs), batch):
            if args.limit and done >= args.limit:
                break
            part = cs[i: i + batch]
            wavs, sr = model.generate_voice_clone(text=[c.text for c in part], language=["German"] * len(part),
                                                  voice_clone_prompt=prompt * len(part))
            wavs = list(wavs)
            for n, c in enumerate(part):
                tries = 0
                while not plausible(c.text, spoken_seconds(wavs[n], sr)) and tries < RETRIES:
                    tries += 1
                    again, _ = model.generate_voice_clone(text=[c.text], language=["German"], voice_clone_prompt=prompt)
                    wavs[n] = again[0]
                if not plausible(c.text, spoken_seconds(wavs[n], sr)):
                    with open(speech.CLIPS_DIR / SUSPECT, "a", encoding="utf-8") as f:
                        f.write(f"{c.id}\t{key}\t{spoken_seconds(wavs[n], sr):.1f}s\t{c.text}\n")
                    print(f"  auffällig: {c.id} ({spoken_seconds(wavs[n], sr):.1f} s) {c.text[:60]}", flush=True)
            for c, w in zip(part, wavs):
                tmp = speech.CLIPS_DIR / f".{c.id}.tmp"
                tmp.write_bytes(to_mp3(w, sr))
                tmp.rename(speech.CLIPS_DIR / f"{c.id}.mp3")  # erst fertig, dann sichtbar – Abbruch hinterlässt nichts Halbes
            done += len(part)
            rate = (time.time() - t0) / done
            print(f"[{done}/{total}] {key}  ~{rate * (total - done) / 60:.0f} min übrig", flush=True)
    print("fertig.")


if __name__ == "__main__":
    main()
