import telebot
import requests
import json
import os
import time
from datetime import datetime

# ===== CONFIG =====
BOT_TOKEN = "8061338623:AAHdAHGLw6JuXp9EumdoJx-CT2vRyxT_Su4"
OWNER_ID = 7509216546
LOG_GROUP_ID = -1002888873802

API_KEY = "snipervision"
API_URL = "https://www.mazid-gmr-like-v4.freefireofficial.in/like"

USAGE_FILE = "usage.json"
APPROVED_FILE = "approved_groups.json"
PROCESSED_FILE = "processed.json"
API_COUNT_FILE = "api_count.json"

bot = telebot.TeleBot(BOT_TOKEN)

# ===== Helper Functions =====
def load_json(filename):
    if os.path.exists(filename):
        with open(filename, "r") as f:
            return json.load(f)
    return {}

def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)

def reset_all_usage():
    save_json(USAGE_FILE, {})
    save_json(PROCESSED_FILE, {})

def is_uid_processed(uid):
    data = load_json(PROCESSED_FILE)
    today = datetime.now().strftime('%Y-%m-%d')
    return uid in data and data[uid] == today

def record_uid(uid):
    data = load_json(PROCESSED_FILE)
    today = datetime.now().strftime('%Y-%m-%d')
    data[uid] = today
    save_json(PROCESSED_FILE, data)

def is_group_approved(group_id):
    groups = load_json(APPROVED_FILE)
    return str(group_id) in groups

def approve_group(group_id, limit):
    groups = load_json(APPROVED_FILE)
    groups[str(group_id)] = {"limit": limit, "used": 0}
    save_json(APPROVED_FILE, groups)

def can_group_use(group_id):
    groups = load_json(APPROVED_FILE)
    if str(group_id) not in groups:
        return False
    group = groups[str(group_id)]
    return group.get("used", 0) < group.get("limit", 0)

def record_group_use(group_id):
    groups = load_json(APPROVED_FILE)
    if str(group_id) in groups:
        groups[str(group_id)]["used"] += 1
        save_json(APPROVED_FILE, groups)

def can_use(user_id):
    if user_id == OWNER_ID:
        return True
    usage = load_json(USAGE_FILE)
    today = datetime.now().strftime('%Y-%m-%d')
    if str(user_id) not in usage or usage[str(user_id)].get("date") != today:
        usage[str(user_id)] = {"used": 0, "date": today}
        save_json(USAGE_FILE, usage)
    return usage[str(user_id)].get("used", 0) < 1

def record_use(user_id):
    if user_id == OWNER_ID:
        return
    usage = load_json(USAGE_FILE)
    usage[str(user_id)]["used"] += 1
    save_json(USAGE_FILE, usage)

def get_api_count():
    data = load_json(API_COUNT_FILE)
    today = datetime.now().strftime('%Y-%m-%d')
    if data.get("date") != today:
        data = {"date": today, "count": 0}
        save_json(API_COUNT_FILE, data)
    return data.get("count", 0)

def increase_api_count():
    data = load_json(API_COUNT_FILE)
    today = datetime.now().strftime('%Y-%m-%d')
    if data.get("date") != today:
        data = {"date": today, "count": 0}
    data["count"] += 1
    save_json(API_COUNT_FILE, data)
    return data["count"]

# ===== Commands =====
@bot.message_handler(commands=["start"])
def handle_start(message):
    bot.reply_to(message, "👋 Welcome! Use /like <region> <uid> in approved groups.")

@bot.message_handler(commands=["reload"])
def handle_reload(message):
    if message.from_user.id == OWNER_ID:
        reset_all_usage()
        bot.reply_to(message, "♻️ All daily limits reset successfully!")
    else:
        bot.reply_to(message, "❌ Only owner can use this command.")

@bot.message_handler(commands=["approve"])
def handle_approve(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "❌ Only owner can use this command.")
        return

    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Usage: /approve <limit>")
        return

    try:
        limit = int(args[1])
    except:
        bot.reply_to(message, "Limit must be a number.")
        return

    chat_id = message.chat.id
    approve_group(chat_id, limit)
    bot.reply_to(message, f"✅ Group approved with daily limit: {limit}")

@bot.message_handler(commands=["like"])
def handle_like(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if message.chat.type == "private":
        bot.reply_to(message, "❌ This command only works in groups.")
        return

    if not is_group_approved(chat_id):
        bot.reply_to(message, "⛔ This group is not approved. Ask the bot owner.")
        bot.send_message(OWNER_ID, f"🆕 Bot added to new group:\n{message.chat.title} ({chat_id})")
        return

    if not can_group_use(chat_id):
        bot.reply_to(message, "⛔ Group usage limit reached.")
        return

    if not can_use(user_id):
        bot.reply_to(message, "⛔ You already used your daily like. Try again tomorrow.")
        return

    args = message.text.split()
    if len(args) < 3:
        bot.reply_to(message, "❌ Usage: /like <region> <uid>\nExample: /like IND 12345678")
        return

    region, uid = args[1], args[2]
    if not uid.isdigit():
        bot.reply_to(message, "❌ Invalid UID, only numbers allowed.")
        return

    if is_uid_processed(uid):
        bot.reply_to(message, "⚠️ This UID already processed today.")
        return

    # First instant reply
    processing_msg = bot.reply_to(message, "⏳ Like Request processing...")
    time.sleep(5)

    # ===== Call API First to Check UID =====
    try:
        url = f"{API_URL}?key={API_KEY}&uid={uid}&server_name={region}"
        response = requests.get(url, timeout=15)
        data = response.json()

        # Check if UID is valid and likes can be sent
        if data.get("status") != 1 or data.get("LikesGivenByAPI", 0) == 0:
            bot.edit_message_text(
                chat_id=processing_msg.chat.id,
                message_id=processing_msg.message_id,
                text="❌ Invalid or inactive UID. No likes sent."
            )
            return

        name = data.get("PlayerNickname", "Unknown")
        level = data.get("Level", "N/A")
        likes_before = data.get("LikesbeforeCommand", 0)
        likes_after = data.get("LikesafterCommand", 0)
        likes_added = data.get("LikesGivenByAPI", likes_after - likes_before)

    except Exception as e:
        bot.edit_message_text(
            chat_id=processing_msg.chat.id,
            message_id=processing_msg.message_id,
            text=f"❌ Failed to send likes. Error: {e}"
        )
        return

    record_uid(uid)
    record_group_use(chat_id)
    record_use(user_id)
    count = increase_api_count()

    msg = f"""
✅ Request Processed Successfully
🆔 UID: {uid}
👤 Name: {name}
🏅 Level: {level}
📈 Likes Before: {likes_before}
📈 Likes After: {likes_after}
➕ Likes Added: {likes_added}
⏰ Processed At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🔢 API Used Today: {count}
"""
    bot.edit_message_text(
        chat_id=processing_msg.chat.id,
        message_id=processing_msg.message_id,
        text=msg
    )
    log = f"📥 Like Request\n🆔 {uid}\n👤 {name}\n🌍 {region}\n➕ {likes_added} likes"
    bot.send_message(LOG_GROUP_ID, log)

# ===== Auto Reconnect =====
print("✅ Bot is running...")
while True:
    try:
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
    except Exception as e:
        print(f"⚠️ Polling error: {e}")
        time.sleep(5)
        print("♻️ Reconnecting...")
