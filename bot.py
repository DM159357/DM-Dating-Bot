from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)

import sqlite3
import os
import time
import random

# ================= TOKEN =================
TOKEN = os.getenv("BOT_TOKEN")

# ================= DATABASE =================
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY,
    name TEXT,
    age INTEGER,
    gender TEXT,
    country TEXT,
    rating REAL DEFAULT 0,
    likes INTEGER DEFAULT 0,
    dislikes INTEGER DEFAULT 0
)
""")
conn.commit()

# ================= GLOBAL =================
waiting_users = []
active_chats = {}
user_step = {}
user_temp = {}
last_message = {}

# ================= SPAM =================
def check_spam(user):
    if user in last_message:
        if time.time() - last_message[user] < 1:
            return False
    last_message[user] = time.time()
    return True

# ================= CHECK REGISTER =================
def is_registered(user):
    data = cursor.execute(
        "SELECT * FROM users WHERE user_id=?",
        (user,)
    ).fetchone()
    return data is not None

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.chat_id

    if is_registered(user):
        await update.message.reply_text(
            "👋 Welcome Back!\n\n"
            "Use /chat to find partner ❤️\n"
            "/profile to view your profile"
        )
    else:
        user_step[user] = "name"
        await update.message.reply_text("👤 Enter Name:")

# ================= PROFILE =================
async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.chat_id

    data = cursor.execute(
        "SELECT name, age, gender, country, rating FROM users WHERE user_id=?",
        (user,)
    ).fetchone()

    if data:
        await update.message.reply_text(
            f"👤 Name: {data[0]}\n"
            f"📅 Age: {data[1]}\n"
            f"⚧ Gender: {data[2]}\n"
            f"🌍 Country: {data[3]}\n"
            f"⭐ Rating: {round(data[4],2)}"
        )
    else:
        await update.message.reply_text("❌ No profile found")

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
        await update.message.reply_text("📅 Age?")

    elif step == "age":
        try:
            age = int(text)
            if age < 18:
                await update.message.reply_text("❌ 18+ only")
                return
            user_temp[user]["age"] = age
        except:
            await update.message.reply_text("❌ Valid age")
            return

        user_step[user] = "gender"
        await update.message.reply_text("⚧ Gender?")

    elif step == "gender":
        if text.lower() not in ["male", "female"]:
            await update.message.reply_text("❌ male/female only")
            return

        user_temp[user]["gender"] = text.lower()
        user_step[user] = "country"
        await update.message.reply_text("🌍 Country?")

    elif step == "country":
        user_temp[user]["country"] = text

        data = user_temp[user]

        cursor.execute("""
        INSERT OR REPLACE INTO users
        (user_id, name, age, gender, country)
        VALUES (?, ?, ?, ?, ?)
        """, (user, data["name"], data["age"], data["gender"], data["country"]))

        conn.commit()

        del user_step[user]

        await update.message.reply_text("✅ Registered!\nUse /chat")

# ================= CHAT =================
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.chat_id

    if not is_registered(user):
        await update.message.reply_text("❌ Register first")
        return

    user_gender = cursor.execute(
        "SELECT gender FROM users WHERE user_id=?",
        (user,)
    ).fetchone()[0]

    random.shuffle(waiting_users)

    for partner in waiting_users:
        partner_gender = cursor.execute(
            "SELECT gender FROM users WHERE user_id=?",
            (partner,)
        ).fetchone()[0]

        if partner_gender != user_gender:

            waiting_users.remove(partner)

            active_chats[user] = partner
            active_chats[partner] = user

            p = cursor.execute(
                "SELECT age, country, rating FROM users WHERE user_id=?",
                (partner,)
            ).fetchone()

            u = cursor.execute(
                "SELECT age, country, rating FROM users WHERE user_id=?",
                (user,)
            ).fetchone()

            await context.bot.send_message(
                user,
                f"❤️ Connected!\nAge:{p[0]}\nCountry:{p[1]}\n⭐Rating:{round(p[2],2)}"
            )

            await context.bot.send_message(
                partner,
                f"❤️ Connected!\nAge:{u[0]}\nCountry:{u[1]}\n⭐Rating:{round(u[2],2)}"
            )

            return

    waiting_users.append(user)
    await update.message.reply_text("⏳ Waiting...")

# ================= SKIP =================
async def skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.chat_id

    if user in active_chats:
        partner = active_chats[user]

        del active_chats[user]
        del active_chats[partner]

        waiting_users.append(partner)

        await update.message.reply_text("⏭ Skipped")
        await context.bot.send_message(partner, "⏭ Partner skipped")

# ================= STOP + RATING =================
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.chat_id

    if user in active_chats:
        partner = active_chats[user]

        del active_chats[user]
        del active_chats[partner]

        cursor.execute(
            "UPDATE users SET dislikes = dislikes + 1 WHERE user_id=?",
            (partner,)
        )

        cursor.execute("""
        UPDATE users
        SET rating = likes * 1.0 / (likes + dislikes + 1)
        """)

        conn.commit()

        await update.message.reply_text("❌ Chat ended")
        await context.bot.send_message(partner, "❌ Chat ended")

# ================= RELAY =================
async def relay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.chat_id

    if not check_spam(user):
        return

    if user in active_chats:
        partner = active_chats[user]

        await context.bot.copy_message(
            chat_id=partner,
            from_chat_id=user,
            message_id=update.message.message_id
        )

# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("chat", chat))
    app.add_handler(CommandHandler("skip", skip))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("profile", profile))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_profile))
    app.add_handler(MessageHandler(filters.ALL, relay))

    print("🚀 Next Level Bot Running")
    app.run_polling()

if __name__ == "__main__":
    main()
