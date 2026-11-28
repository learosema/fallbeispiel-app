# Natürliche Stimmen

Die App liest Antworten mit vorab vertonten Clips vor. Fehlt ein Clip, spricht die Browserstimme. In den
Einstellungen lässt sich das mit „Natürliche Stimmen“ abschalten.

| Rolle | Stimme | Wann erzeugt |
| --- | --- | --- |
| Patient, Umstehende | Qwen3-TTS, pro Fall (`voices:` in `content/scenarios/*.yaml`) | vorab |
| Kollege, Befund, Rettungsdienst | Qwen3-TTS (`content/voices.yaml`) | vorab |
| Leitstelle | Piper Kerstin mit Funkfilter, kennt Rufname und Leitstelle aus den Einstellungen | auf dem Server, beim ersten Abruf |
| AED | Piper Thorsten, Gerätestimme | auf dem Server, beim ersten Abruf |

Gesprochen wird die **Sprechfassung**: Qwen liest Buchstaben-Abkürzungen englisch, deshalb wird ausgeschrieben, was man
in dem Moment sagen würde („RR 140/85“ → „Blutdruck 140 zu 85“, „GCS 15“ → „Glasgow 15“). Die Regeln stehen in
`content/voices.yaml`. Im Chat bleibt der Text unverändert.

## Ablauf

Die Clips heißen nach einem Hash aus Stimme und gesprochenem Text (`backend/speech.py`). Ändert sich ein Text, braucht
nur dieser Satz einen neuen Clip.

1. **Casting** (CPU geht, ca. 1,5 min pro Stimme): `make voices-cast` entwirft pro Stimme einen Referenzclip nach
   `audio/voices/`. Anhören. Passt eine nicht, die Beschreibung ändern (neuer Schlüssel) oder neu würfeln:
   `python tools/tts/cast.py --redo <schlüssel>`.
2. **Vertonen** (GPU): `tools/tts/vertonen.ipynb` in Colab öffnen und ausführen, `clips.zip` nach `audio/clips/`
   entpacken. Ohne GPU geht es auch lokal, nur sehr langsam: `python tools/tts/render.py`.
   Clips mit unplausibler Länge (verschluckter Text, Stottern) erzeugt `render.py` bis zu zweimal neu; was danach
   noch auffällt, steht in `audio/clips/suspect.txt` – diese gezielt anhören.
3. **Aufräumen und committen**: `make audio-status` zeigt, was fehlt; `python tools/tts/render.py --prune` löscht
   Clips, die kein Text mehr braucht. Dann `audio/` committen.

Nach Textänderungen reicht es, Schritt 2 erneut laufen zu lassen. Es werden nur die fehlenden Clips erzeugt.

## Umgebung

Die Werkzeuge brauchen eigene Pakete (`requirements.txt`, Python 3.12), die App selbst nicht:

```sh
uv venv -p 3.12 .venv-tts
uv pip install -p .venv-tts --index-strategy unsafe-best-match \
  --extra-index-url https://download.pytorch.org/whl/cpu torch -r tools/tts/requirements.txt
```

Die Modelle (ca. 4 GB je Modell) landen im Hugging-Face-Cache (`~/.cache/huggingface`).
