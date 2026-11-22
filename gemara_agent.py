import os
import requests

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

def flatten_text(data):
    """Safely flattens nested lists returned by Sefaria into a single string."""
    if isinstance(data, str):
        return data
    if isinstance(data, list):
        return "\n".join(filter(None, (flatten_text(item) for item in data)))
    return ""

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

gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
gemini_resp = requests.post(
    gemini_url,
    json={"contents": [{"parts": [{"text": prompt}]}]},
    timeout=30
)
gemini_resp.raise_for_status()
summary = gemini_resp.json()["candidates"][0]["content"]["parts"][0]["text"]

# 4. Send to Telegram
tg_resp = requests.post(
    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
    json={"chat_id": TELEGRAM_CHAT_ID, "text": summary},
    timeout=20
)
tg_resp.raise_for_status()
print(f"Successfully sent summary for {ref}")
