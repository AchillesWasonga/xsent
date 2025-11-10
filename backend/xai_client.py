# backend/xai_client.py
"""
Minimal sentiment scorer used by the aggregator.
Returns a score in [-1.0, 1.0] and a label in {"pos","neu","neg"}.

You can later replace `score_text()` to call xAI/Grok with your XAI_KEY
and map the model output to this same schema.
"""

from __future__ import annotations
import re
from typing import Dict

# Tiny lexicons (expand as you like)
POS_WORDS = {
    "bull", "bullish", "mooning", "pump", "pumped", "green", "surge",
    "great", "good", "strong", "optimistic", "win", "beats", "beat",
    "rally", "rallies", "up", "buy", "buying", "🚀", "🔥", "❤️", "💚",
}
NEG_WORDS = {
    "bear", "bearish", "dump", "dumped", "red", "crash", "crashed",
    "bad", "poor", "weak", "sell", "selling", "down", "fell",
    "risk", "scared", "fear", "fud", "😭", "💔", "💥",
}
NEGATORS = {"not", "no", "never", "hardly", "barely", "scarcely", "isn't", "wasn't", "don't", "doesn't", "didn't", "can't", "won't"}

# Words + a wide emoji block
_word_re = re.compile(r"[A-Za-z0-9_]+|[\U0001F300-\U0001FAFF]")

def _tokens(text: str):
    return [t.lower() for t in _word_re.findall(text or "")]

def score_text(text: str) -> Dict[str, float | str]:
    """
    Heuristic scorer. Output:
      { "score": float in [-1,1], "label": "pos"|"neu"|"neg" }
    """
    toks = _tokens(text)
    if not toks:
        return {"score": 0.0, "label": "neu"}

    score = 0.0
    negate = False
    for t in toks:
        if t in NEGATORS:
            negate = True
            continue

        delta = 0.0
        if t in POS_WORDS:
            delta = 1.0
        elif t in NEG_WORDS:
            delta = -1.0

        if negate and delta != 0.0:
            delta = -delta
            negate = False

        score += delta

    # Exclamation emphasis
    exclam = text.count("!")
    if exclam:
        score *= min(1.0, 0.15 * exclam + 1.0)

    # Normalize to [-1, 1]
    if score > 0:
        norm = min(1.0, score / 6.0)
    elif score < 0:
        norm = max(-1.0, score / 6.0)
    else:
        norm = 0.0

    label = "neu"
    if norm > 0.05:
        label = "pos"
    elif norm < -0.05:
        label = "neg"

    return {"score": float(round(norm, 4)), "label": label}
