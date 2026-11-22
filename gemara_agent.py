import os
import random
import requests

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"].strip()
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"].strip()
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"].strip()

# Philosophical, social, and interpersonal law (בין אדם לחברו) passages
PHILOSOPHICAL_SOCIAL_LAW_REFS = [
    "Sanhedrin 37a",     # ערך האדם היחיד, שוויון בני אדם ואחריות לחיי אדם
    "Bava Metzia 62a",   # דילמה חברתית ומוסרית של הישרדות ואחריות משותפת
    "Bava Metzia 83a",   # יחסי עבודה, אחריות מעסיק ועובד וחובת מוסר מעבר לחוק היבש
    "Bava Kamma 30a",    # נזקים במרחב הציבורי, יחסים בין אנשים והתנהגות מעבר לשורת הדין
    "Bava Batra 21a",    # תחרות כלכלית, פרנסה, אחריות קהילתית וזכויות שכנים
    "Shabbat 31a",       # הכלל המוסרי שבין אדם לחברו ותמצית היחס לזולת
    "Gittin 59b",        # שמירה על שלום, הרמוניה חברתית והתנהלות בין אנשים
]


def flatten_text(data):
    """Flattens nested lists returned by Sefaria into plain text."""
    if isinstance(data, str):
        return data
    if isinstance(data, list):
        return " ".join(filter(None, (flatten_text(item) for item in data)))
    return ""


def get_passage_context():
    """Fetches a passage from Sefaria to give Gemini the underlying idea."""
    ref = random.choice(PHILOSOPHICAL_SOCIAL_LAW_REFS)
    url = f"https://www.sefaria.org/{ref.replace(' ', '_')}"

    text_data = requests.get(
        f"https://www.sefaria.org/api/texts/{ref}?context=0", timeout=10
    ).json()
    he_raw = flatten_text(text_data.get("he") or [])
    en_raw = flatten_text(text_data.get("text") or [])
    context_text = " ".join((en_raw or he_raw).split())[:1000]
    he_ref = text_data.get("heRef") or ref
    return ref, he_ref, url, context_text


def pick_gemini_models(api_key):
    """Finds available text generation models on the key, skipping preview/media models."""
    try:
        resp = requests.get(
            f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
            timeout=10,
        )
        if not resp.ok:
            return ["models/gemini-2.5-flash"]
        models = resp.json().get("models", [])
        blocked = ("omni", "image", "tts", "audio", "live", "embedding", "veo", "imagen", "preview", "exp")
        found = [
            m["name"]
            for m in models
            if "generateContent" in m.get("supportedGenerationMethods", [])
            and "gemini" in m.get("name", "").lower()
            and not any(bad in m.get("name", "").lower() for bad in blocked)
        ]
        found.sort(key=lambda n: (0 if "flash" in n.lower() else 1, n), reverse=True)
        return found or ["models/gemini-2.5-flash"]
    except Exception:
        return ["models/gemini-2.5-flash"]


def explain_simply_in_hebrew(ref, he_ref, context_text):
    """Asks Gemini for a complete plain-Hebrew explanation: case, problem & discussion, and resolution."""
    prompt = f"""אתה מסביר סוגיות מהתלמוד בעברית פשוטה, טבעית וברורה (כמו הסבר לחבר).
הנושא: פילוסופיה, חברה, מוסר או משפט שבין אדם לחברו.

כללים חשובים:
1. אל תצטט ואל תשתמש במילות המקור מהגמרא או בארמית — נסח הכל מחדש במילים שלך כהסבר ברור.
2. הימנע מקווים תחתונים (_) ומכוכביות כפולות (**).
3. השלם תמיד את כל שלושת החלקים עד הסוף במשפטים שלמים ומלאים, בלי להיחתך באמצע:

📖 מקור: {he_ref} ({ref})

🧩 המקרה בפשטות:
[תאר ב-2-3 משפטים פשוטים מה הסיטואציה שקורה במציאות]

⚖️ הבעיה והדיון:
[הסבר ב-3-4 משפטים מה הדילמה או ההתנגשות בין הצדדים, ומה הנימוקים המרכזיים שעולים בדיון]

✅ המסקנה וההכרעה:
[הסבר ב-2-3 משפטים איך הסוגיה מוכרעת או מתיישבת, ומה הרעיון המרכזי לחיים ולחברה]

רקע לעיון (אל תצטט ממנו מילה במילה):
{context_text}
"""
    last_error = "לא התקבלה תשובה"
    for model_name in pick_gemini_models(GEMINI_API_KEY):
        try:
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={GEMINI_API_KEY}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.45, "maxOutputTokens": 1400},
                },
                timeout=20,
            )
            if r.ok:
                data = r.json()
                parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                text = "\n".join(p.get("text", "") for p in parts if "text" in p).strip()
                if text:
                    print(f"Generated explanation using {model_name}")
                    return text
            last_error = f"{model_name} ({r.status_code}): {r.text[:160]}"
        except Exception as e:
            last_error = f"{model_name}: {e}"

    raise RuntimeError(last_error)


def build_hebrew_fallback(ref, he_ref, url, err):
    """Clean Hebrew fallback if Gemini has no available free quota right now."""
    return (
        f"📖 מקור: {he_ref} ({ref})\n\n"
        f"🧩 המקרה בפשטות:\n"
        f"הדף עוסק בסוגיה חברתית, מוסרית או בדינים שבין אדם לחברו.\n\n"
        f"⚖️ הבעיה והדיון:\n"
        f"כרגע לא הופק עיבוד מלא מ-Gemini ({err}).\n\n"
        f"✅ המסקנה וההכרעה:\n"
        f"ניתן לקרוא את המקור בספריא: {url}"
    )


def send_telegram(message):
    tg = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": message},
        timeout=10,
    )
    if not tg.ok:
        raise RuntimeError(f"Telegram {tg.status_code}: {tg.text[:200]}")


ref, he_ref, url, context_text = get_passage_context()

try:
    message = explain_simply_in_hebrew(ref, he_ref, context_text)
except Exception as err:
    print(f"Gemini fallback triggered: {err}")
    message = build_hebrew_fallback(ref, he_ref, url, err)

send_telegram(message)
print(f"Delivered message for {ref} to Telegram.")
