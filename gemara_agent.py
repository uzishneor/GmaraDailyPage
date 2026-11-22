import os
import requests

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"].strip()
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"].strip()
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"].strip()


def flatten_text(data):
    """Flattens nested lists returned by Sefaria into plain text."""
    if isinstance(data, str):
        return data
    if isinstance(data, list):
        return " ".join(filter(None, (flatten_text(item) for item in data)))
    return ""


def get_daf_yomi():
    """Fetches today's Daf Yomi reference, Sefaria URL, and a short excerpt."""
    cal = requests.get("https://www.sefaria.org/api/calendars", timeout=10).json()
    daf_item = next(
        item for item in cal["calendar_items"] if item["title"]["en"] == "Daf Yomi"
    )
    ref = daf_item["ref"]
    url = f"https://www.sefaria.org/{ref.replace(' ', '_')}"

    text_data = requests.get(
        f"https://www.sefaria.org/api/texts/{ref}?context=0", timeout=10
    ).json()
    raw_text = flatten_text(text_data.get("text") or text_data.get("he") or [])
    excerpt = " ".join(raw_text.split())[:800]
    return ref, url, excerpt


def summarize_with_gemini(ref, excerpt):
    """Attempts a concise structured summary via Gemini; raises on failure."""
    prompt = f"""Summarize ONE sugya from {ref} in under 150 words. Avoid underscores and nested asterisks.

📖 Source: {ref}
❓ The Issue (השאלה):
⚖️ The Positions (המחלוקת):
✅ The Resolution (המסקנה):
💡 Takeaway:

Excerpt:
{excerpt}
"""
    r = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}",
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=15,
    )
    if not r.ok:
        raise RuntimeError(f"Gemini {r.status_code}: {r.text[:200]}")

    text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    if not text:
        raise RuntimeError("Empty response from Gemini")
    return text


def build_direct_fallback(ref, url, excerpt):
    """Fallback message when Gemini hits quota/rate limits or times out."""
    return (
        f"📖 Source: {ref}\n"
        f"🔗 Sefaria: {url}\n"
        f"ℹ️ Direct excerpt (Gemini unavailable/quota limit):\n\n"
        f"{excerpt}..."
    )


def send_telegram(message):
    tg = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": message},
        timeout=10,
    )
    if not tg.ok:
        raise RuntimeError(f"Telegram {tg.status_code}: {tg.text[:200]}")


ref, url, excerpt = get_daf_yomi()

try:
    message = summarize_with_gemini(ref, excerpt)
    print(f"Sent Gemini summary for {ref}")
except Exception as err:
    print(f"Gemini skipped ({err}); using direct Sefaria fallback.")
    message = build_direct_fallback(ref, url, excerpt)

send_telegram(message)
print(f"Delivered message for {ref} to Telegram.")
