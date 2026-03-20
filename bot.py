from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, CallbackQueryHandler
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
            "👫 Partner Matched 👫\n"
            "Welcome To DM Dating Bot ❤️\n"
            "/chat - Find partner\n"
            "/link - Share Profile Link\n"
            "/stop - End chat"
        )
    else:
        user_step[user] = "name"
        await update.message.reply_text("👤 Enter Name:")

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
        except:
            await update.message.reply_text("❌ Invalid age")
            return

        user_temp[user]["age"] = age
        user_step[user] = "gender"
        await update.message.reply_text("⚧ Gender?")

    elif step == "gender":
        user_temp[user]["gender"] = text
        user_step[user] = "country"
        await update.message.reply_text("🌍 Country?")

    elif step == "country":
        user_temp[user]["country"] = text

        d = user_temp[user]

        cursor.execute("""
        INSERT OR REPLACE INTO users
        (user_id, name, age, gender, country)
        VALUES (?, ?, ?, ?, ?)
        """, (user, d["name"], d["age"], d["gender"], d["country"]))

        conn.commit()

        del user_step[user]

        await update.message.reply_text("✅ Registered!\nUse /chat")

# ================= CHAT =================
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.chat_id

    if not is_registered(user):
        await update.message.reply_text("❌ Register first")
        return

    if user in active_chats:
        await update.message.reply_text("❌ Already in chat")
        return

    if waiting_users:
        partner = waiting_users.pop(0)

        active_chats[user] = partner
        active_chats[partner] = user

        # Profile info
        p = cursor.execute(
            "SELECT age, country, likes, dislikes FROM users WHERE user_id=?",
            (partner,)
        ).fetchone()

        u = cursor.execute(
            "SELECT age, country, likes, dislikes FROM users WHERE user_id=?",
            (user,)
        ).fetchone()

        msg = (
            "👫 Partner Matched 👫\n"
            "Welcome To DM Dating Bot ❤️\n"
            "/chat - Find partner\n"
            "/link - Share Profile Link\n"
            "/stop - End chat"
        )

        await context.bot.send_message(user, msg)
        await context.bot.send_message(partner, msg)

    else:
        waiting_users.append(user)
        await update.message.reply_text("⏳ Waiting...")

# ================= RELAY (TEXT) =================
async def relay_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.chat_id

    if not check_spam(user):
        return

    if user in active_chats:
        partner = active_chats[user]

        await context.bot.send_message(
            partner,
            f"👤 User:\n{update.message.text}"
        )

# ================= MEDIA WITH WATERMARK =================
async def relay_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.chat_id

    if user not in active_chats:
        return

    partner = active_chats[user]

    caption = f"📸 Sent by User ID: {user}"

    if update.message.photo:
        file = update.message.photo[-1].file_id
        await context.bot.send_photo(partner, file, caption=caption)

    elif update.message.video:
        file = update.message.video.file_id
        await context.bot.send_video(partner, file, caption=caption)

# ================= PROFILE LINK =================
async def link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.chat_id

    await update.message.reply_text(
        f"🔗 Profile Link:\nhttps://t.me/YOUR_BOT_USERNAME?start={user}"
    )

# ================= STOP + RATING =================
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.chat_id

    if user in active_chats:
        partner = active_chats[user]

        del active_chats[user]
        del active_chats[partner]

        keyboard = [
            [
                InlineKeyboardButton("👍 Like", callback_data=f"like_{partner}"),
                InlineKeyboardButton("👎 Dislike", callback_data=f"dislike_{partner}")
            ]
        ]

        await update.message.reply_text(
            "⭐ Rate Your Partner:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        await context.bot.send_message(partner, "❌ Chat Ended")

# ================= BUTTON HANDLER =================
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, partner = query.data.split("_")
    partner = int(partner)

    if action == "like":
        cursor.execute(
            "UPDATE users SET likes = likes + 1 WHERE user_id=?",
            (partner,)
        )
    else:
        cursor.execute(
            "UPDATE users SET dislikes = dislikes + 1 WHERE user_id=?",
            (partner,)
        )

    conn.commit()

    await query.edit_message_text("✅ Thanks for rating!")

# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("chat", chat))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("link", link))

    app.add_handler(CallbackQueryHandler(button))

    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO, relay_media))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_profile))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, relay_text))

    print("🚀 Bot Running...")
    app.run_polling()

if __name__ == "__main__":
    main()
