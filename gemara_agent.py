import os
import random
import requests

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"].strip()
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"].strip()
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"].strip()

# Curated Talmudic pages rich in philosophy, social ethics, and interpersonal law (בין אדם לחברו)
PHILOSOPHICAL_SOCIAL_LAW_REFS = [
    "Sanhedrin 37a",     # Creation of a single human being: saving one life = saving a world; human equality
    "Bava Metzia 62a",   # "חייך קודמים" - social & ethical dilemma of survival and shared responsibility
    "Bava Metzia 83a",   # Labor law, employer/worker ethics, and moral accountability beyond strict law
    "Bava Kamma 30a",    # Interpersonal damages, public space ethics, and "לפנים משורת הדין"
    "Bava Batra 21a",    # Competition, livelihood, community norms, and neighborly/social obligations
    "Shabbat 31a",       # Hillel's golden rule: "מה דעלך סני לחברך לא תעביד" - core interpersonal ethic
    "Gittin 59b",        # Peace, social harmony, and interpersonal conduct ("דרכי שלום")
]


def flatten_text(data):
    """Flattens nested lists returned by Sefaria into plain text."""
    if isinstance(data, str):
        return data
    if isinstance(data, list):
        return " ".join(filter(None, (flatten_text(item) for item in data)))
    return ""


def get_philosophical_social_law_passage():
    """Fetches a Talmudic page focused on philosophy, society, or interpersonal law from Sefaria."""
    ref = random.choice(PHILOSOPHICAL_SOCIAL_LAW_REFS)
    url = f"https://www.sefaria.org/{ref.replace(' ', '_')}"

    text_data = requests.get(
        f"https://www.sefaria.org/api/texts/{ref}?context=0", timeout=10
    ).json()
    he_raw = flatten_text(text_data.get("he") or [])
    en_raw = flatten_text(text_data.get("text") or [])
    excerpt = " ".join((he_raw or en_raw).split())[:1000]
    he_ref = text_data.get("heRef") or ref
    return ref, he_ref, url, excerpt


def summarize_in_hebrew(ref, he_ref, excerpt):
    """Summarizes a philosophical, social, or interpersonal law sugya in structured Hebrew."""
    prompt = f"""אתה פרשן תלמודי. בהתבסס אך ורק על הקטע המצורף מתוך {ref} ({he_ref}), בחר סוגיה מרכזית אחת העוסקת בפילוסופיה, בחברה או במשפט שבין אדם לחברו, וסכם אותה בעברית ברורה ותמציתית (עד 180 מילים).
הימנע מקווים תחתונים (_) ומכוכביות כפולות (**).

הצג בדיוק במבנה הבא:
📖 מקור: {he_ref} ({ref})
🧠 הסוגיה (פילוסופיה / חברה / בין אדם לחברו): [משפט אחד ברור]
❓ השאלה המרכזית: [1-2 משפטים]
⚖️ העמדות והמחלוקת: [עיקרי הדעות והנימוקים]
✅ המסקנה / ההכרעה: [כיצד הסוגיה מוכרעת או נותרת בתיקו]
💡 נקודה למחשבה: [משפט אחד]

קטע מתוך הגמרא:
{excerpt}
"""
    r = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent?key={GEMINI_API_KEY}",
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=15,
    )
    if not r.ok:
        raise RuntimeError(f"Gemini {r.status_code}: {r.text[:200]}")

    text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    if not text:
        raise RuntimeError("תגובה ריקה מ-Gemini")
    return text


def build_hebrew_fallback(ref, he_ref, url, excerpt):
    """Fallback message in Hebrew when Gemini hits quota/rate limits or times out."""
    return (
        f"📖 מקור: {he_ref} ({ref})\n"
        f"🔗 קישור לספריא: {url}\n"
        f"ℹ️ קטע ישיר (ללא עיבוד AI עקב מגבלת מכסה/זמן):\n\n"
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


ref, he_ref, url, excerpt = get_philosophical_social_law_passage()

try:
    message = summarize_in_hebrew(ref, he_ref, excerpt)
    print(f"Sent Hebrew summary for {ref}")
except Exception as err:
    print(f"Gemini skipped ({err}); using Hebrew direct fallback.")
    message = build_hebrew_fallback(ref, he_ref, url, excerpt)

send_telegram(message)
print(f"Delivered Hebrew message for {ref} to Telegram.")
