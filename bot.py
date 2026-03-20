import os
import time
import sqlite3

from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)

# ================= CONFIG =================
TOKEN = os.getenv("BOT_TOKEN")
BOT_USERNAME = "dmdating_bot"

# ================= DATABASE =================
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY,
    name TEXT,
    age INTEGER,
    gender TEXT,
    country TEXT
)
""")
conn.commit()

# ================= GLOBAL =================
waiting_users = []
active_chats = {}
user_step = {}
user_temp = {}
last_message = {}

# ================= SPAM CONTROL =================
def check_spam(user):
    now = time.time()
    if user in last_message and now - last_message[user] < 0.5:
        return False
    last_message[user] = now
    return True

# ================= REGISTER CHECK =================
def is_registered(user):
    return cursor.execute(
        "SELECT 1 FROM users WHERE user_id=?",
        (user,)
    ).fetchone() is not None

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.chat_id
    args = context.args

    # 🔗 Profile view
    if args:
        target = int(args[0])

        data = cursor.execute(
            "SELECT name, age, gender, country FROM users WHERE user_id=?",
            (target,)
        ).fetchone()

        if data:
            await update.message.reply_text(
                f"👤 PROFILE\n\n"
                f"Name: {data[0]}\n"
                f"Age: {data[1]}\n"
                f"Gender: {data[2]}\n"
                f"Country: {data[3]}\n"
                f"\n🔗 Chat: https://t.me/{BOT_USERNAME}?start={target}"
            )
        else:
            await update.message.reply_text("❌ Profile not found")

        return

    if not is_registered(user):
        user_step[user] = "name"
        await update.message.reply_text("👤 Enter Name:")
    else:
        await update.message.reply_text(
            "👫 Welcome To DM Dating Bot ❤️\n\n"
            "/chat - Find partner\n"
            "/link - Share Profile Link\n"
            "/stop - End chat\n"
        )

# ================= LINK =================
async def link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.chat_id

    link = f"https://t.me/{BOT_USERNAME}?start={user}"

    await update.message.reply_text(
        f"🔗 Your Profile Link:\n{link}\n\n"
        "👉 Share this to connect with others"
    )

# ================= CHAT =================
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.chat_id

    if not is_registered(user):
        await update.message.reply_text("❌ Register first")
        return

    if user in active_chats:
        await update.message.reply_text("⚠️ You are already in chat")
        return

    for partner in waiting_users:
        if partner != user:
            waiting_users.remove(partner)

            active_chats[user] = partner
            active_chats[partner] = user

            await context.bot.send_message(user, "👫 Connected!")
            await context.bot.send_message(partner, "👫 Connected!")

            return

    waiting_users.append(user)
    await update.message.reply_text("⏳ Searching partner...")

# ================= STOP =================
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.chat_id

    if user in active_chats:
        partner = active_chats[user]

        del active_chats[user]
        del active_chats[partner]

        await update.message.reply_text("❌ Chat Ended")
        await context.bot.send_message(partner, "❌ Chat Ended")

# ================= MESSAGE RELAY =================
async def relay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.chat_id

    if not check_spam(user):
        return

    if user not in active_chats:
        return

    partner = active_chats[user]

    try:
        # 🔥 Forward ALL types (text, image, video, etc.)
        await context.bot.copy_message(
            chat_id=partner,
            from_chat_id=user,
            message_id=update.message.message_id
        )
    except Exception as e:
        print("Relay Error:", e)

# ================= REGISTRATION =================
async def handle_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.chat_id
    text = update.message.text

    if user not in user_step:
        return

    step = user_step[user]

    if step == "name":
        user_temp[user] = {"name": text}
        user_step[user] = "age"
        await update.message.reply_text("Enter Age:")

    elif step == "age":
        user_temp[user]["age"] = int(text)
        user_step[user] = "gender"
        await update.message.reply_text("Gender:")

    elif step == "gender":
        user_temp[user]["gender"] = text
        user_step[user] = "country"
        await update.message.reply_text("Country:")

    elif step == "country":
        user_temp[user]["country"] = text

        d = user_temp[user]

        cursor.execute("""
        INSERT OR REPLACE INTO users VALUES (?, ?, ?, ?, ?)
        """, (user, d["name"], d["age"], d["gender"], d["country"]))

        conn.commit()

        del user_step[user]

        await update.message.reply_text("✅ Registered! Now use /chat")

# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("chat", chat))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("link", link))

    # ⚠️ Order important
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_profile))
    app.add_handler(MessageHandler(filters.ALL, relay))

    print("🚀 Bot Running...")
    app.run_polling()

if __name__ == "__main__":
    main()
