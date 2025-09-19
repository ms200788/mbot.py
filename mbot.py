import os
import sqlite3
import uuid
from flask import Flask
from threading import Thread
from telegram import Update, ParseMode
from telegram.ext import (
    Updater, CommandHandler, MessageHandler, Filters, CallbackContext,
    ConversationHandler
)

TOKEN = os.getenv("TELEGRAM_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
DB_PATH = os.getenv("DB_PATH", "mbot.db")
WEBHOOK_PORT = int(os.getenv("PORT", "10000"))  # For Render

# Conversation states
UPLOAD, PROTECT, TIMER = range(3)

# Flask app for healthcheck
app = Flask(__name__)
@app.route('/health')
def health():
    return "ok", 200

def run_flask():
    app.run(host="0.0.0.0", port=WEBHOOK_PORT)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
    c.execute("CREATE TABLE IF NOT EXISTS messages (name TEXT PRIMARY KEY, content TEXT)")
    c.execute("""CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        owner_id INTEGER,
        protect INTEGER,
        timer INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        file_type TEXT,
        file_id TEXT,
        caption TEXT
    )""")
    conn.commit()
    conn.close()

def add_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def set_message(name, content):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO messages (name, content) VALUES (?,?)", (name, content))
    conn.commit()
    conn.close()

def get_message(name, default):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT content FROM messages WHERE name=?", (name,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else default

def is_owner(user_id):
    return user_id == OWNER_ID

def start(update: Update, context: CallbackContext):
    add_user(update.effective_user.id)
    args = context.args
    if args:
        session_id = args[0]
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT protect, timer FROM sessions WHERE session_id=?", (session_id,))
        session = c.fetchone()
        c.execute("SELECT file_type, file_id, caption FROM files WHERE session_id=?", (session_id,))
        files = c.fetchall()
        conn.close()
        if not session or not files:
            update.message.reply_text("Invalid or expired link.")
            return
        protect, timer = session
        user_is_owner = update.effective_user.id == OWNER_ID
        sent_msgs = []
        for file_type, file_id, caption in files:
            kwargs = {"caption": caption, "parse_mode": ParseMode.MARKDOWN}
            if file_type in ['photo', 'video', 'document']:
                if protect and not user_is_owner:
                    kwargs["protect_content"] = True
                if file_type == 'photo':
                    msg = update.message.reply_photo(file_id, **kwargs)
                elif file_type == 'video':
                    msg = update.message.reply_video(file_id, **kwargs)
                elif file_type == 'document':
                    msg = update.message.reply_document(file_id, **kwargs)
                sent_msgs.append(msg)
            else:
                msg = update.message.reply_text(caption or "[Text]")
                sent_msgs.append(msg)
        # Auto-delete logic
        if timer and timer > 0 and not user_is_owner:
            for msg in sent_msgs:
                context.job_queue.run_once(
                    lambda ctx: ctx.bot.delete_message(msg.chat_id, msg.message_id),
                    timer * 60
                )
        update.message.reply_text("Files sent. You can use this link again to get files.")
    else:
        msg = get_message("start", "Welcome to Mbot! Use /help for info.")
        update.message.reply_text(msg)

def help_cmd(update: Update, context: CallbackContext):
    msg = get_message("help", "Available commands: /start, /help")
    update.message.reply_text(msg)

def setmessage(update: Update, context: CallbackContext):
    if not is_owner(update.effective_user.id):
        update.message.reply_text("Only the owner can use this command.")
        return
    if len(context.args) < 2:
        update.message.reply_text("Usage: /setmessage <start|help> <your message>")
        return
    name = context.args[0].lower()
    if name not in ["start", "help"]:
        update.message.reply_text("Only 'start' or 'help' can be set.")
        return
    content = " ".join(context.args[1:])
    set_message(name, content)
    update.message.reply_text(f"{name.title()} message updated.")

def upload_start(update: Update, context: CallbackContext):
    if not is_owner(update.effective_user.id):
        update.message.reply_text("Only the owner can upload.")
        return ConversationHandler.END
    context.user_data['files'] = []
    update.message.reply_text(
        "Send files (any type). You can send multiple files. Send /d when done."
    )
    return UPLOAD

def upload_files(update: Update, context: CallbackContext):
    if update.message.text == '/d':
        update.message.reply_text("Protect content? (on/off)")
        return PROTECT
    files = context.user_data.get('files', [])
    if update.message.photo:
        files.append(('photo', update.message.photo[-1].file_id, update.message.caption))
    elif update.message.video:
        files.append(('video', update.message.video.file_id, update.message.caption))
    elif update.message.document:
        files.append(('document', update.message.document.file_id, update.message.caption))
    elif update.message.text:
        files.append(('text', None, update.message.text))
    context.user_data['files'] = files
    update.message.reply_text("File received. Continue or send /d to finish.")
    return UPLOAD

def upload_protect(update: Update, context: CallbackContext):
    protect = update.message.text.lower()
    context.user_data['protect'] = 1 if protect == 'on' else 0
    update.message.reply_text("Auto-delete timer? (0 for never, or minutes up to 10080 for 7 days)")
    return TIMER

def upload_timer(update: Update, context: CallbackContext):
    try:
        timer = int(update.message.text)
        if not (0 <= timer <= 10080):
            raise ValueError
    except ValueError:
        update.message.reply_text("Invalid. Enter minutes: 0 to 10080.")
        return TIMER
    context.user_data['timer'] = timer
    # Save session and files
    session_id = str(uuid.uuid4())[:8]
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO sessions (session_id, owner_id, protect, timer) VALUES (?, ?, ?, ?)",
              (session_id, OWNER_ID, context.user_data['protect'], timer))
    for ftype, fid, caption in context.user_data['files']:
        c.execute("INSERT INTO files (session_id, file_type, file_id, caption) VALUES (?, ?, ?, ?)",
                  (session_id, ftype, fid, caption))
    conn.commit()
    conn.close()
    bot_username = context.bot.get_me().username
    deep_link = f"https://t.me/{bot_username}?start={session_id}"
    update.message.reply_text(f"Upload complete!\nDeep link: {deep_link}")
    return ConversationHandler.END

def cancel(update: Update, context: CallbackContext):
    update.message.reply_text("Upload cancelled.")
    return ConversationHandler.END

def broadcast(update: Update, context: CallbackContext):
    if not is_owner(update.effective_user.id):
        update.message.reply_text("Only the owner can broadcast.")
        return
    if not context.args:
        update.message.reply_text("Usage: /broadcast <message>")
        return
    message = " ".join(context.args)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    user_ids = [row[0] for row in c.execute("SELECT user_id FROM users")]
    conn.close()
    for uid in user_ids:
        try:
            context.bot.send_message(chat_id=uid, text=message)
        except Exception:
            pass
    update.message.reply_text("Broadcast sent.")

def main():
    init_db()
    Thread(target=run_flask).start()  # Start healthcheck server
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('upload', upload_start)],
        states={
            UPLOAD: [MessageHandler(Filters.all, upload_files)],
            PROTECT: [MessageHandler(Filters.text, upload_protect)],
            TIMER: [MessageHandler(Filters.text, upload_timer)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    dp.add_handler(conv_handler)
    dp.add_handler(CommandHandler('start', start, pass_args=True))
    dp.add_handler(CommandHandler('help', help_cmd))
    dp.add_handler(CommandHandler('setmessage', setmessage, pass_args=True))
    dp.add_handler(CommandHandler('broadcast', broadcast, pass_args=True))
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
