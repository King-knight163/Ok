from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext
import os, subprocess, time, json, zipfile, requests, threading
from datetime import datetime, timedelta, timezone as dt_timezone
from apscheduler.schedulers.background import BackgroundScheduler
from pytz import timezone

BOT_TOKEN = "7694418942:AAExss6WeT5Q4EIZLWlidt4JVuLT8fIRS5s"
ADMIN_ID = 7107162691

BASE_DIR = "projects"
LOG_DIR = "logs"
PREMIUM_FILE = "premium.json"
MAX_FILE_SIZE = 50 * 1024 * 1024

os.makedirs(BASE_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

user_projects = {}
premium_users = {}

scheduler = BackgroundScheduler(timezone=timezone('Asia/Kolkata'))
scheduler.start()

def load_premium():
    if os.path.exists(PREMIUM_FILE):
        with open(PREMIUM_FILE, "r") as f:
            return json.load(f)
    return {}

def save_premium(data):
    with open(PREMIUM_FILE, "w") as f:
        json.dump(data, f)

premium_users = load_premium()

def is_premium(uid):
    expiry = premium_users.get(str(uid))
    if not expiry: return False
    expiry_dt = datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt_timezone.utc)
    if datetime.now(dt_timezone.utc) > expiry_dt:
        del premium_users[str(uid)]
        save_premium(premium_users)
        return False
    return True

def stop_project(uid, filename, bot=None):
    proc = user_projects.get(uid, {}).get(filename)
    if proc:
        proc.kill()
        user_projects[uid].pop(filename, None)
        if bot:
            bot.send_message(chat_id=uid, text=f"💤 Project <b>{filename}</b> auto-terminated.", parse_mode="HTML")

def run_command(uid, command, display_name, update, context):
    logpath = os.path.join(LOG_DIR, f"{uid}_{display_name}.txt")
    def execute():
        with open(logpath, "w") as log_file:
            proc = subprocess.Popen(command, shell=True, stdout=log_file, stderr=subprocess.STDOUT)
            user_projects.setdefault(uid, {})
            user_projects[uid][display_name] = proc

            if not is_premium(uid):
                scheduler.add_job(stop_project, 'date',
                    run_date=datetime.now(dt_timezone.utc) + timedelta(minutes=10),
                    args=[uid, display_name, context.bot]
                )
    threading.Thread(target=execute).start()

    update.effective_message.reply_text(
        f"✅ Project <b>{display_name}</b> started.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🛑 Stop", callback_data=f"terminate_{display_name}")],
            [InlineKeyboardButton("🔁 Restart", callback_data=f"restart_{display_name}")],
            [InlineKeyboardButton("📜 Log", callback_data=f"log_{display_name}")]
        ])
    )

def start(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    name = update.effective_user.first_name
    image = "https://files.catbox.moe/efem5j.jpg"
    keyboard = [
        [InlineKeyboardButton("🐍 Host Python File", callback_data="host_py")],
        [InlineKeyboardButton("📁 My Projects", callback_data="my_projects")],
        [InlineKeyboardButton("🛠 Terminal a Project", callback_data="terminate_one")],
        [InlineKeyboardButton("⛔ Terminate All", callback_data="terminate_all")],
        [InlineKeyboardButton("📜 My Plan", callback_data="my_plan")],
        [InlineKeyboardButton("🧬 Deploy GitHub URL", callback_data="deploy_github")],
        [InlineKeyboardButton("🗜 Deploy ZIP File", callback_data="deploy_zip")]
    ]
    caption = f"""👋 Hello <b>{name}</b>,

💐 Welcome to ⛥ PLAY-Z PYTHON HOSTING BOT ⛥
🔷 Host your Python codes easily
🚀 Deploy up to 3 .py files (unlimited for premium)
⏱️ 10-min Auto Sleep
📜 Smart Logs | 🧠 Auto Command

<em>© Powered by PLAY-Z HACKING</em>"""
    context.bot.send_photo(chat_id=uid, photo=image, caption=caption, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    uid = query.from_user.id
    data = query.data

    if data == "host_py":
        query.message.reply_text("📁 Send a .py file to run.")
    elif data == "deploy_github":
        query.message.reply_text("📎 Send a GitHub repo link.")
    elif data == "deploy_zip":
        query.message.reply_text("🗜 Send a .zip file.")
    elif data == "my_projects":
        files = user_projects.get(uid, {})
        if not files:
            return query.message.reply_text("❌ No active projects.")
        buttons = [[InlineKeyboardButton(f"❌ {f}", callback_data=f"terminate_{f}")] for f in files]
        query.message.reply_text("📁 Active projects:", reply_markup=InlineKeyboardMarkup(buttons))
    elif data == "terminate_one":
        files = user_projects.get(uid, {})
        if not files:
            return query.message.reply_text("❌ No active projects.")
        buttons = [[InlineKeyboardButton(f"🛠 Stop {f}", callback_data=f"terminate_{f}")] for f in files]
        query.message.reply_text("🛠 Select project to terminate:", reply_markup=InlineKeyboardMarkup(buttons))
    elif data == "terminate_all":
        if uid != ADMIN_ID:
            return query.answer("❌ Only admin can use this.")
        for uid_projects in user_projects.values():
            for proc in uid_projects.values():
                proc.kill()
        user_projects.clear()
        query.message.reply_text("🧨 All sessions terminated by admin.")
    elif data == "my_plan":
        now = datetime.now(timezone("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M:%S")
        expiry = premium_users.get(str(uid))
        project_count = len(user_projects.get(uid, {}))
        if expiry:
            text = f"""🌟 <b>PREMIUM PLAN ACTIVE</b>
<b>User ID:</b> <code>{uid}</code>
<b>Expires on:</b> <code>{expiry}</code>
<b>Projects:</b> <code>{project_count}</code>"""
        else:
            text = f"""🆓 <b>FREE PLAN</b>
<b>User ID:</b> <code>{uid}</code>
<b>Active Projects:</b> <code>{project_count}/3</code>"""
        query.message.reply_text(text, parse_mode="HTML")
    elif data.startswith("terminate_"):
        filename = data.split("terminate_")[1]
        stop_project(uid, filename, context.bot)
        query.message.reply_text(f"✅ Project <b>{filename}</b> terminated.", parse_mode="HTML")
    elif data.startswith("restart_"):
        filename = data.split("restart_")[1]
        path = os.path.join(BASE_DIR, filename)
        if os.path.exists(path):
            run_command(uid, f"python3 '{path}'", filename, update, context)
        else:
            query.message.reply_text("❌ File not found.")
    elif data.startswith("log_"):
        filename = data.split("log_")[1]
        logpath = os.path.join(LOG_DIR, f"{uid}_{filename}.txt")
        if os.path.exists(logpath):
            with open(logpath, "rb") as f:
                context.bot.send_document(chat_id=uid, document=f, filename=f"{filename}.log")
        else:
            context.bot.send_message(chat_id=uid, text="❌ Log not found.")

def handle_file(update: Update, context: CallbackContext):
    file = update.message.document
    uid = update.effective_user.id
    if not file.file_name.endswith(".py"):
        return update.message.reply_text("❌ Send a valid .py file only.")
    if file.file_size > MAX_FILE_SIZE:
        return update.message.reply_text("❌ File too large. Max 50MB allowed.")
    filename = file.file_name
    path = os.path.join(BASE_DIR, filename)
    file.get_file().download(path)
    run_command(uid, f"python3 '{path}'", filename, update, context)

def add_premium(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        return update.message.reply_text("❌ Only admin can use this.")
    try:
        uid = str(context.args[0])
        days = int(context.args[1])
        expiry = (datetime.now(dt_timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        premium_users[uid] = expiry
        save_premium(premium_users)
        update.message.reply_text(f"✅ Premium activated for {uid} ({days} days)")
    except:
        update.message.reply_text("❌ Usage: /add <user_id> <days>")

def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("add", add_premium, pass_args=True))
    dp.add_handler(CallbackQueryHandler(button_handler))
    dp.add_handler(MessageHandler(Filters.document.mime_type("text/x-python"), handle_file))
    updater.start_polling()
    updater.idle()

# Flask server to keep alive on Koyeb
app = Flask(__name__)
@app.route('/')
def index():
    return "Bot is running", 200

from flask import Flask
import threading

app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running", 200

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=8000)).start()
    main()  # Make sure `main()` function is defined above