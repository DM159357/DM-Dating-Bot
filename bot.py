# ================== IMPORTS ===============
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

import sqlite3
import time
import os

# ================== TOKEN ==================
TOKEN = os.getenv("BOT_TOKEN")

# ================== DATABASE ==================
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

# ================== GLOBAL ==================
waiting_users = []
active_chats = {}
user_step = {}
user_data_temp = {}
last_message = {}

# ================== SPAM CHECK ==================
def check_spam(user):
    if user in last_message:
        if time.time() - last_message[user] < 1:
            return False
    last_message[user] = time.time()
    return True

# ================== START ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.chat_id

    data = cursor.execute(
        "SELECT * FROM users WHERE user_id=?",
        (user,)
    ).fetchone()

    if data:
        await update.message.reply_text(
            "👫 Partner Matched 👫\n"
            "Welcome DM Dating Bot ❤️\n\n"
            "Use /chat - Find partner\n"
            "/skip - Change partner\n"
            "/stop - End chat"
        )
    else:
        user_step[user] = "name"
        await update.message.reply_text("Enter your name:")

# ================== PROFILE HANDLER ==================
async def handle_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.chat_id
    text = update.message.text

    if user not in user_step:
        return

    step = user_step[user]

    if step == "name":
        user_data_temp[user] = {"name": text}
        user_step[user] = "age"
        await update.message.reply_text("Enter your age:")

    elif step == "age":
        try:
            age = int(text)
            if age < 18:
                await update.message.reply_text("Age must be 18+")
                return
            user_data_temp[user]["age"] = age
        except:
            await update.message.reply_text("Enter valid age:")
            return

        user_step[user] = "gender"
        await update.message.reply_text("Enter gender (male/female):")

    elif step == "gender":
        if text.lower() not in ["male", "female"]:
            await update.message.reply_text("Enter male or female only")
            return

        user_data_temp[user]["gender"] = text.lower()
        user_step[user] = "country"
        await update.message.reply_text("Enter your country:")

    elif step == "country":
        user_data_temp[user]["country"] = text
        data = user_data_temp[user]

        cursor.execute("""
        INSERT OR REPLACE INTO users
        (user_id, name, age, gender, country)
        VALUES (?, ?, ?, ?, ?)
        """, (user, data["name"], data["age"], data["gender"], data["country"]))

        conn.commit()

        del user_step[user]

        await update.message.reply_text("Registration Complete ✅\nUse /chat")

# ================== CHAT ==================
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.chat_id

    user_data = cursor.execute(
        "SELECT gender FROM users WHERE user_id=?",
        (user,)
    ).fetchone()

    if not user_data:
        await update.message.reply_text("First register using /start")
        return

    gender = user_data[0]

    for waiting_user in waiting_users:
        partner_data = cursor.execute(
            "SELECT gender FROM users WHERE user_id=?",
            (waiting_user,)
        ).fetchone()

        if partner_data and partner_data[0] != gender:
            waiting_users.remove(waiting_user)

            active_chats[user] = waiting_user
            active_chats[waiting_user] = user

            await context.bot.send_message(user, "Connected ❤️")
            await context.bot.send_message(waiting_user, "Connected ❤️")
            return

    waiting_users.append(user)
    await update.message.reply_text("Waiting for partner...")

# ================== STOP ==================
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.chat_id

    if user in active_chats:
        partner = active_chats[user]

        del active_chats[user]
        del active_chats[partner]

        await context.bot.send_message(partner, "Chat ended")

    await update.message.reply_text("Chat stopped")

# ================== RELAY ==================
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

# ================== MAIN ==================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("chat", chat))
    app.add_handler(CommandHandler("stop", stop))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_profile))
    app.add_handler(MessageHandler(filters.ALL, relay))

    print("Bot Running 🚀")
    app.run_polling()

# ================== RUN ==================
if __name__ == "__main__":
    main()
