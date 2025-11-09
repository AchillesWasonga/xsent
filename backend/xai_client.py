import os, requests, json, re
from typing import Literal, Tuple
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

XAI_KEY = os.getenv("XAI_KEY")
XAI_MODEL = os.getenv("XAI_MODEL", "grok-4-latest")
BASE_URL = "https://api.x.ai/v1/chat/completions"

if not XAI_KEY:
    raise RuntimeError("XAI_KEY missing in .env")

def classify_sentiment(text: str) -> Tuple[Literal[-1, 0, 1], float, str]:
    """
    Returns (label, score, rationale)
      label: -1 negative, 0 neutral, 1 positive
      score: float in [-1, 1]
      rationale: short explanation
    """
    system = (
        "You label sentiment. Reply ONLY in strict JSON with fields: "
        '{"label": -1|0|1, "score": -1..1, "rationale": "short reason"}'
    )
    user = f'Classify sentiment for this text:\n"""{text}"""'

    headers = {"Authorization": f"Bearer {XAI_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": XAI_MODEL,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "temperature": 0,
        "stream": False,
        "max_tokens": 64  # keep responses tiny for speed
    }
    r = requests.post(BASE_URL, json=payload, headers=headers, timeout=25)
    if r.status_code != 200:
        raise RuntimeError(f"xAI error {r.status_code}: {r.text}")

    content = r.json()["choices"][0]["message"]["content"]
    m = re.search(r"\{.*\}", content, re.S)
    data = json.loads(m.group(0)) if m else json.loads(content)
    label = int(data.get("label", 0))
    score = float(data.get("score", 0))
    rationale = str(data.get("rationale", ""))
    return label, score, rationale
