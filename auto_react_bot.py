"""
ری‌اکشن خودکار روی هر پست جدیدِ کانالِ خودت.

توکن‌ها در این فایل نیستند! آن‌ها را در فایل جدا «bot_tokens.txt»
(کنار همین اسکریپت) می‌گذاری، هر توکن در یک خط. این‌طوری راز در
اسکریپت ذخیره نمی‌شود.

پیش‌نیاز:
  - همه‌ی ربات‌ها ادمین کانال باشند.
  - pip install requests
  - فایل bot_tokens.txt با توکن‌های تازه (revoke‌شده) ساخته باشی.
  - این اسکریپت باید روشن بماند (کامپیوتر همیشه‌روشن یا VPS).
"""

import os
import random
import time
import requests

# ───────────── تنظیمات ─────────────

# نام فایلی که توکن‌ها در آن‌اند (هر توکن یک خط؛ خط خالی و خطِ # نادیده گرفته می‌شود)
TOKENS_FILE = "bot_tokens.txt"

# یوزرنیم کانال بدون @ (روی host می‌توانی با متغیر محیطی CHANNEL_USERNAME عوضش کنی)
CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME", "testbotaii")

# ایموجی‌ها همراه وزن: عدد بزرگ‌تر یعنی احتمال انتخاب بیشتر.
# فقط ایموجی‌های فعالِ کانالت را بگذار. وزن‌ها واقعی‌تر نشانش می‌دهند.
EMOJI_WEIGHTS = {
    "👍": 5,
    "❤️": 4,
    "🔥": 3,
    "👎": 2,
    "💔": 2,
}

# بازه‌ی تأخیر بین ری‌اکشن‌ها (ثانیه) — کوتاه نگهش می‌داریم تا اجرای cron سریع تمام شود
DELAY_MIN = 1
DELAY_MAX = 6

# چند تا از ربات‌ها روی هر پست ری‌اکشن بزنند (تصادفی بین این دو عدد)
REACT_MIN = 9
REACT_MAX = 99  # عملاً یعنی «تا جایی که ربات داری»

# ───────────────────────────────────

API = "https://api.telegram.org/bot"


def load_tokens(path):
    """توکن‌ها را اول از متغیر محیطی BOT_TOKENS می‌خواند (برای host امن)،
    و اگر نبود از فایل. توکن‌ها را می‌توان با خط جدید، کاما یا فاصله جدا کرد."""
    # ۱) اول متغیر محیطی (روی host به‌صورت secret تنظیمش می‌کنی)
    env_value = os.environ.get("BOT_TOKENS")
    if env_value:
        raw = env_value.replace(",", "\n").replace(" ", "\n")
        tokens = [t.strip() for t in raw.splitlines() if t.strip()]
        if tokens:
            return tokens

    # ۲) در غیر این صورت از فایل (برای اجرای محلی)
    if not os.path.exists(path):
        raise SystemExit(
            f"نه متغیر محیطی BOT_TOKENS ست شده و نه فایل «{path}» هست. "
            f"یکی را فراهم کن."
        )
    tokens = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                tokens.append(line)
    if not tokens:
        raise SystemExit(f"فایل «{path}» خالی است.")
    return tokens


def pick_emoji():
    emojis = list(EMOJI_WEIGHTS.keys())
    weights = list(EMOJI_WEIGHTS.values())
    return random.choices(emojis, weights=weights, k=1)[0]


def send_reaction(token, chat_id, message_id, emoji):
    url = f"{API}{token}/setMessageReaction"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "reaction": [{"type": "emoji", "emoji": emoji}],
    }
    try:
        return requests.post(url, json=payload, timeout=15).json()
    except requests.RequestException as e:
        return {"ok": False, "error": str(e)}


def react_all(tokens, chat_id, message_id):
    count = random.randint(REACT_MIN, min(REACT_MAX, len(tokens)))
    chosen = random.sample(tokens, count)
    print(f"  → {count} ربات روی پست {message_id} ری‌اکشن می‌زنند")

    for i, token in enumerate(chosen, start=1):
        emoji = pick_emoji()
        result = send_reaction(token, chat_id, message_id, emoji)
        bot_id = token.split(":")[0]
        if result.get("ok"):
            print(f"    [{i}/{count}] ربات {bot_id} ← {emoji} ✓")
        else:
            print(f"    [{i}/{count}] ربات {bot_id} ناموفق: "
                  f"{result.get('description') or result.get('error')}")
        if i < count:
            time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))


def drain_backlog(listener_token):
    """آپدیت‌های قدیمیِ توی صف را بدون ری‌اکشن رد می‌کند و آخرین offset را
    برمی‌گرداند، تا حلقه‌ی اصلی فقط از پست‌های واقعاً جدید شروع کند."""
    offset = None
    skipped = 0
    while True:
        params = {"timeout": 0, "allowed_updates": ["channel_post"]}
        if offset is not None:
            params["offset"] = offset
        try:
            resp = requests.get(f"{API}{listener_token}/getUpdates",
                                params=params, timeout=20).json()
        except requests.RequestException:
            break
        updates = resp.get("result", [])
        if not updates:
            break
        for u in updates:
            offset = u["update_id"] + 1
            skipped += 1
    if skipped:
        print(f"{skipped} آپدیت قدیمی رد شد (روی آن‌ها ری‌اکشن زده نمی‌شود).")
    return offset


def main():
    tokens = load_tokens(TOKENS_FILE)
    listener_token = tokens[0]
    print(f"{len(tokens)} ربات بارگذاری شد. در حال رد کردن پست‌های قدیمی...")

    offset = drain_backlog(listener_token)
    print("آماده شد؛ از این به بعد فقط روی پست‌های جدید ری‌اکشن می‌زند. (Ctrl+C برای توقف)")
    seen = set()

    while True:
        try:
            params = {"timeout": 30, "allowed_updates": ["channel_post"]}
            if offset is not None:
                params["offset"] = offset
            resp = requests.get(f"{API}{listener_token}/getUpdates",
                                params=params, timeout=40).json()
        except requests.RequestException as e:
            print(f"خطای شبکه: {e} — تلاش دوباره تا چند ثانیه")
            time.sleep(5)
            continue

        for update in resp.get("result", []):
            offset = update["update_id"] + 1
            post = update.get("channel_post")
            if not post:
                continue
            chat = post.get("chat", {})
            if chat.get("username", "").lower() != CHANNEL_USERNAME.lower():
                continue
            msg_id = post["message_id"]
            if msg_id in seen:
                continue
            seen.add(msg_id)

            print(f"پست جدید شناسایی شد: {msg_id}")
            time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
            react_all(tokens, chat["id"], msg_id)


def run_once():
    """یک‌بار اجرا می‌شود (مناسب cron / GitHub Actions با RUN_ONCE=1).
    اول پست‌های جدید را می‌گیرد و فوراً «تأیید» می‌کند (تا اگر اجرا نیمه‌کاره
    کنسل شد، پست‌ها تلنبار نشوند)، و تازه بعد ری‌اکشن می‌زند."""
    tokens = load_tokens(TOKENS_FILE)
    listener = tokens[0]
    try:
        resp = requests.get(
            f"{API}{listener}/getUpdates",
            params={"timeout": 0, "allowed_updates": ["channel_post"]},
            timeout=30,
        ).json()
    except requests.RequestException as e:
        raise SystemExit(f"خطای شبکه: {e}")

    updates = resp.get("result", [])

    # ۱) ابتدا فهرست پست‌های مربوط به کانال را جمع کن و آخرین offset را پیدا کن
    targets = []
    last_offset = None
    for u in updates:
        last_offset = u["update_id"] + 1
        post = u.get("channel_post")
        if not post:
            continue
        chat = post.get("chat", {})
        if chat.get("username", "").lower() != CHANNEL_USERNAME.lower():
            continue
        targets.append((chat["id"], post["message_id"]))

    # ۲) فوراً تأیید کن (قبل از بخش کند) تا کنسل‌شدنِ اجرا باعث تکرار نشود
    if last_offset is not None:
        try:
            requests.get(f"{API}{listener}/getUpdates",
                         params={"offset": last_offset, "timeout": 0}, timeout=15)
        except requests.RequestException:
            pass

    # ۳) حالا بخش کند: ری‌اکشن‌زدن با تأخیر
    for chat_id, msg_id in targets:
        print(f"پست جدید: {msg_id}")
        react_all(tokens, chat_id, msg_id)

    print(f"اجرای یک‌باره تمام شد. روی {len(targets)} پست ری‌اکشن زده شد.")


if __name__ == "__main__":
    if os.environ.get("RUN_ONCE") == "1":
        run_once()       # حالت cron / GitHub Actions
    else:
        main()           # حالت گوش‌دادنِ همیشگی (VPS/کامپیوتر)
