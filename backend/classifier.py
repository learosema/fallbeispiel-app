"""Intent-Erkennung: Regex-Muster (präzise) plus Satz-Embeddings (für Umschreibungen).

Spracheingaben kommen oft ohne Satzzeichen an („hallo wir sind vom drk was ist passiert“).
Deshalb wird jede Äußerung in Teilsätze und kurze Wortfenster zerlegt; jedes Stück wird
einzeln mit den Beispielsätzen der Intents verglichen.
"""
from __future__ import annotations

import os
import re
import threading
from dataclasses import dataclass

from .content import Intent, intents

MODEL_ID = os.environ.get("INTENT_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
# Mindest-Ähnlichkeit für ganze Teilsätze bzw. für kurze Wortfenster (strenger, weil fehleranfälliger)
CLAUSE_THRESHOLD = float(os.environ.get("INTENT_THRESHOLD", "0.72"))
# Wortfenster sind standardmäßig aus (> 1): kurze Fenster erzeugten zu viele Fehltreffer.
WINDOW_THRESHOLD = float(os.environ.get("INTENT_WINDOW_THRESHOLD", "1.01"))
USE_EMBEDDINGS = os.environ.get("INTENT_EMBEDDINGS", "1") != "0"

_SPLIT = re.compile(r"[.,;:!?\n]+|\s(?:und|dann|danach|außerdem|sowie|anschließend|jetzt|so)\s", re.I)


@dataclass(frozen=True)
class Hit:
    intent: str
    pos: int          # Zeichenposition in der Äußerung (für die Reihenfolge)
    score: float
    source: str       # "regex" | "embedding" | "funk" | "implied"


def normalize(text: str) -> str:
    t = text.lower().replace("ß", "ss")
    t = re.sub(r"[„“”\"'`´]", "", t)
    return re.sub(r"\s+", " ", t).strip()


def _compile(pattern: str) -> re.Pattern:
    # Muster werden auf normalisierten Text angewendet – also auch dort ß → ss
    return re.compile(pattern.lower().replace("ß", "ss"), re.I)


class _Embedder:
    def __init__(self) -> None:
        import torch
        from transformers import AutoModel, AutoTokenizer

        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(MODEL_ID)
        self.model = AutoModel.from_pretrained(MODEL_ID).eval()
        self.cache: dict[str, "torch.Tensor"] = {}
        self.lock = threading.Lock()

    def embed(self, texts: list[str]):
        torch = self.torch
        missing = [t for t in dict.fromkeys(texts) if t not in self.cache]
        if missing:
            with self.lock, torch.inference_mode():
                for i in range(0, len(missing), 64):
                    batch = missing[i:i + 64]
                    enc = self.tok(batch, padding=True, truncation=True, max_length=64, return_tensors="pt")
                    out = self.model(**enc).last_hidden_state
                    mask = enc["attention_mask"].unsqueeze(-1).float()
                    vec = (out * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
                    vec = torch.nn.functional.normalize(vec, dim=-1)
                    for t, v in zip(batch, vec):
                        self.cache[t] = v
            if len(self.cache) > 50_000:
                self.cache.clear()
        return torch.stack([self.cache[t] for t in texts])


class IntentClassifier:
    def __init__(self, catalogue: dict[str, Intent] | None = None, use_embeddings: bool = USE_EMBEDDINGS) -> None:
        self.intents = catalogue or intents()
        self.patterns = {iid: [_compile(p) for p in i.patterns] for iid, i in self.intents.items()}
        self.embedder = None
        if use_embeddings:
            self.embedder = _Embedder()
            self.example_intents: list[str] = []
            examples: list[str] = []
            for iid, i in self.intents.items():
                for ex in i.examples:
                    examples.append(normalize(ex))
                    self.example_intents.append(iid)
            self.example_matrix = self.embedder.embed(examples) if examples else None

    # ---- Regex ----
    def _regex_hits(self, text: str) -> list[Hit]:
        hits = []
        for iid, pats in self.patterns.items():
            positions = [m.start() for p in pats for m in [p.search(text)] if m]
            if positions:
                hits.append(Hit(iid, min(positions), 1.0, "regex"))
        return hits

    # ---- Embeddings ----
    def _clauses(self, text: str) -> list[tuple[int, str]]:
        out, last = [], 0
        for m in _SPLIT.finditer(text):
            if m.start() > last:
                out.append((last, text[last:m.start()]))
            last = m.end()
        out.append((last, text[last:]))
        return [(p + len(c) - len(c.lstrip()), c.strip()) for p, c in out if c.strip()]

    def _embedding_hits(self, text: str, covered: list[tuple[int, int]]) -> list[Hit]:
        if self.embedder is None or self.example_matrix is None:
            return []
        spans: list[tuple[int, str, float]] = []
        for pos, clause in self._clauses(text):
            end = pos + len(clause)
            # Teilsätze, in denen schon ein Regex-Muster gegriffen hat, nicht noch einmal raten
            if any(a < end and pos < b for a, b in covered):
                continue
            spans.append((pos, clause, CLAUSE_THRESHOLD))
            words = [(m.start() + pos, m.group()) for m in re.finditer(r"\S+", clause)]
            if len(words) > 4 and WINDOW_THRESHOLD <= 1:
                for n in (3, 4, 5, 6):
                    for k in range(0, len(words) - n + 1):
                        spans.append((words[k][0], " ".join(w for _, w in words[k:k + n]), WINDOW_THRESHOLD))
        if not spans:
            return []
        vecs = self.embedder.embed([s for _, s, _ in spans])
        sims = vecs @ self.example_matrix.T
        best: dict[str, Hit] = {}
        for (pos, _, thr), row in zip(spans, sims):
            score, idx = float(row.max()), int(row.argmax())
            if score < thr:
                continue
            iid = self.example_intents[idx]
            if iid not in best or pos < best[iid].pos:
                best[iid] = Hit(iid, pos, score, "embedding")
        return list(best.values())

    def classify(self, raw: str) -> list[Hit]:
        text = normalize(raw)
        hits = self._regex_hits(text)
        covered = []
        for p in (pp for pats in self.patterns.values() for pp in pats):
            covered += [(m.start(), m.end()) for m in p.finditer(text)]
        hits += [h for h in self._embedding_hits(text, covered) if h.intent not in {x.intent for x in hits}]
        return resolve(hits, self.intents)


def resolve(hits: list[Hit], catalogue: dict[str, Intent]) -> list[Hit]:
    """overrides/implies anwenden und nach Position sortieren."""
    exclusive = [h for h in hits if catalogue[h.intent].exclusive]
    if exclusive:
        hits = exclusive
    present = {h.intent for h in hits}
    dropped = {o for h in hits for o in catalogue[h.intent].overrides}
    out = [h for h in hits if h.intent not in dropped]
    for h in list(out):
        for imp in catalogue[h.intent].implies:
            if imp not in present:
                out.append(Hit(imp, h.pos, h.score, "implied"))
                present.add(imp)
    return sorted(out, key=lambda h: (h.pos, h.source == "implied"))


_instance: IntentClassifier | None = None
_lock = threading.Lock()


def get() -> IntentClassifier:
    global _instance
    with _lock:
        if _instance is None:
            _instance = IntentClassifier()
        return _instance
