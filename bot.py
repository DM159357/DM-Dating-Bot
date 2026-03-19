# ================== IMPORTS ==================

import os
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import sqlite3
import time

# ================== TOKEN ==================
TOKEN = os.getenv("")

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

# ================== GLOBAL VARIABLES ==================
waiting_users = []
active_chats = {}
user_step = {}
user_data_temp = {}
last_message = {}

# ================== SPAM PROTECTION ==================
def check_spam(user):
    if user in last_message:
        if time.time() - last_message[user] < 1:
            return False
    last_message[user] = time.time()
    return True

# ================== START ==================
def start(update, context):
    user = update.message.chat_id

    data = cursor.execute(
        "SELECT * FROM users WHERE user_id=?",
        (user,)
    ).fetchone()

    if data:
        update.message.reply_text(
           
            "👫Patner Matched👫\n" 
            "Welcome DM Dating Bot ❤️\nUse /chat - Find partner" 
            "/skip - Change partner\n" 
            "/stop - End chat"
        )
    else:
        user_step[user] = "name"
        update.message.reply_text("Enter your name:")

# ================== PROFILE HANDLER ==================
def handle_profile(update, context):
    user = update.message.chat_id
    text = update.message.text

    if user not in user_step:
        return

    step = user_step[user]

    if step == "name":
        user_data_temp[user] = {"name": text}
        user_step[user] = "age"
        update.message.reply_text("Enter your age:")

    elif step == "age":
        try:
            age = int(text)
            if age < 18:
                update.message.reply_text("Age must be 18+")
                return
            user_data_temp[user]["age"] = age
        except:
            update.message.reply_text("Enter valid age:")
            return

        user_step[user] = "gender"
        update.message.reply_text("Enter gender (male/female):")

    elif step == "gender":
        if text.lower() not in ["male", "female"]:
            update.message.reply_text("Enter male or female only")
            return

        user_data_temp[user]["gender"] = text.lower()
        user_step[user] = "country"
        update.message.reply_text("Enter your country:")

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

        update.message.reply_text(
            "Registration Complete ✅\nUse /chat"
        )

    elif step == "feedback":
        partner = user_data_temp[user]["partner"]

        if text.lower() == "yes":
            cursor.execute(
                "UPDATE users SET likes = likes + 1 WHERE user_id=?",
                (partner,)
            )
        else:
            cursor.execute(
                "UPDATE users SET dislikes = dislikes + 1 WHERE user_id=?",
                (partner,)
            )

        # Update rating
        cursor.execute("""
        UPDATE users
        SET rating = (likes * 1.0) / (likes + dislikes + 1)
        """)

        conn.commit()

        del user_step[user]

        update.message.reply_text("Thanks for feedback ❤️")

# ================== CHAT ==================
def chat(update, context):
    user = update.message.chat_id

    # check registration
    user_data = cursor.execute(
        "SELECT gender FROM users WHERE user_id=?",
        (user,)
    ).fetchone()

    if not user_data:
        update.message.reply_text("First register using /start")
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

            # partner info
            partner_info = cursor.execute(
                "SELECT age, country, rating FROM users WHERE user_id=?",
                (waiting_user,)
            ).fetchone()

            user_info = cursor.execute(
                "SELECT age, country, rating FROM users WHERE user_id=?",
                (user,)
            ).fetchone()

            context.bot.send_message(
                user,
                f"Connected ❤️\nPartner Info:\n"
                f"Age: {partner_info[0]}\n"
                f"Country: {partner_info[1]}\n"
                f"Rating: {round(partner_info[2],2)}"
            )

            context.bot.send_message(
                waiting_user,
                f"Connected ❤️\nPartner Info:\n"
                f"Age: {user_info[0]}\n"
                f"Country: {user_info[1]}\n"
                f"Rating: {round(user_info[2],2)}"
            )

            return

    waiting_users.append(user)
    update.message.reply_text("Waiting for partner...")

# ================== SKIP ==================
def skip(update, context):
    user = update.message.chat_id

    if user in active_chats:
        partner = active_chats[user]

        del active_chats[user]
        del active_chats[partner]

        context.bot.send_message(partner, "Partner skipped")

        chat(update, context)

# ================== STOP ==================
def stop(update, context):
    user = update.message.chat_id

    if user in active_chats:
        partner = active_chats[user]

        del active_chats[user]
        del active_chats[partner]

        context.bot.send_message(partner, "Chat ended")

        user_step[user] = "feedback"
        user_data_temp[user] = {"partner": partner}

        update.message.reply_text("Did you like partner? (yes/no)")

# ================== RELAY ==================
def relay(update, context):
    user = update.message.chat_id

    if not check_spam(user):
        return

    if user in active_chats:
        partner = active_chats[user]

        context.bot.copy_message(
            chat_id=partner,
            from_chat_id=user,
            message_id=update.message.message_id
        )
    else:
        update.message.reply_text("Use /chat to start")

# ================== PROFILE ==================
def profile(update, context):
    user = update.message.chat_id

    data = cursor.execute(
        "SELECT name, age, gender, country, rating FROM users WHERE user_id=?",
        (user,)
    ).fetchone()

    if data:
        update.message.reply_text(
            f"Name: {data[0]}\n"
            f"Age: {data[1]}\n"
            f"Gender: {data[2]}\n"
            f"Country: {data[3]}\n"
            f"Rating: {round(data[4],2)}"
        )
    else:
        update.message.reply_text("No profile found")

# ================== MAIN ==================
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("chat", chat))
    dp.add_handler(CommandHandler("skip", skip))
    dp.add_handler(CommandHandler("stop", stop))
    dp.add_handler(CommandHandler("profile", profile))

    dp.add_handler(MessageHandler(Filters.text, handle_profile))
    dp.add_handler(MessageHandler(Filters.all, relay))

    updater.start_polling()
    print("Bot Running 🚀")
    updater.idle()

# ================== RUN ==================
main()
