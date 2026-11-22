import os
import requests

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"].strip()
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"].strip()
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"].strip()

def flatten_text(data):
    """Safely flattens nested lists returned by Sefaria into a single string."""
    if isinstance(data, str):
        return data
    if isinstance(data, list):
        return "\n".join(filter(None, (flatten_text(item) for item in data)))
    return ""

def generate_with_fallback(api_key, prompt):
    """Tries available Gemini models in priority order, skipping any with 0 quota or 404."""
    resp = requests.get(
        f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
        timeout=20
    )
    resp.raise_for_status()
    available = [
        m["name"] for m in resp.json().get("models", [])
        if "generateContent" in m.get("supportedGenerationMethods", [])
    ]

    # Try stable/standard Flash & Pro models before preview/experimental ones
    preferred = [
        "models/gemini-3.8-flash",
        "models/gemini-3.5-flash",
        "models/gemini-3.0-flash",
        "models/gemini-2.5-flash-lite",
        "models/gemini-2.5-pro",
    ]
    candidates = [m for m in preferred if m in available] + [
        m for m in available if m not in preferred and "omni" not in m and "image" not in m and "tts" not in m
    ]

    errors = []
    for model_name in candidates:
        print(f"Trying {model_name}...")
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={api_key}",
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=30
        )
        if r.ok:
            print(f"Succeeded with {model_name}")
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        errors.append(f"{model_name} -> {r.status_code}")

    raise RuntimeError(f"All models failed. Tried: {errors}")

# 1. Fetch today's Daf Yomi reference from Sefaria
cal = requests.get("https://www.sefaria.org/api/calendars", timeout=20).json()
daf_item = next(item for item in cal["calendar_items"] if item["title"]["en"] == "Daf Yomi")
ref = daf_item["ref"]

# 2. Fetch the text (Aramaic/Hebrew + English)
text_data = requests.get(f"https://www.sefaria.org/api/texts/{ref}?context=0", timeout=20).json()
he_text = flatten_text(text_data.get("he", []))
en_text = flatten_text(text_data.get("text", []))

# 3. Summarize one sugya via Gemini Free Tier
prompt = f"""
You are a Talmudic scholar. Based ONLY on the text below from {ref}, select ONE central, self-contained sugya (issue) and summarize it concisely (under 250 words).
Do not use Markdown underscores or nested asterisks that break Telegram formatting.

Format strictly as:
📖 Source: {ref}
❓ The Issue (השאלה): [1-2 sentences]
⚖️ The Positions (המחלוקת): [Core arguments]
✅ The Resolution (המסקנה): [How it is resolved or if Teiku]
💡 Takeaway: [1 sentence]

Hebrew/Aramaic Text:
{he_text[:12000]}

English Text:
{en_text[:12000]}
"""

summary = generate_with_fallback(GEMINI_API_KEY, prompt)

# 4. Send to Telegram
tg_resp = requests.post(
    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
    json={"chat_id": TELEGRAM_CHAT_ID, "text": summary},
    timeout=20
)
if not tg_resp.ok:
    raise RuntimeError(f"Telegram API error {tg_resp.status_code}: {tg_resp.text}")

print(f"Successfully sent summary for {ref}")
