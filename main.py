from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext
import os, subprocess, time, json, zipfile, requests
from datetime import datetime, timedelta, timezone as dt_timezone
from apscheduler.schedulers.background import BackgroundScheduler
from pytz import timezone
from flask import Flask
import threading

BOT_TOKEN = "7659870883:AAGiG3ActkFCD2LmQ8l1b63_CJrPs-c7Ld0"
ADMIN_ID = 7107162691

BASE_DIR = "projects"
LOG_DIR = "logs"
PREMIUM_FILE = "premium.json"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
KOYEB_LINK_BASE = "https://your-app.koyeb.app"  # Customize your Koyeb subdomain

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

def run_command(uid, command, display_name, update, context):
    logpath = os.path.join(LOG_DIR, f"{uid}_{display_name}.txt")
    with open(logpath, "w") as logfile:
        subprocess.Popen(command, shell=True, stdout=logfile, stderr=logfile)

    user_projects.setdefault(uid, [])
    if display_name not in user_projects[uid]:
        user_projects[uid].append(display_name)

    if not is_premium(uid):
        scheduler.add_job(
            lambda: stop_command(uid, display_name, context.bot),
            'date',
            run_date=datetime.now(dt_timezone.utc) + timedelta(minutes=10),
            id=f"{uid}_{display_name}",
            replace_existing=True
        )

    link_button = [InlineKeyboardButton("🌐 Open Link", url=KOYEB_LINK_BASE)]
    control_buttons = [
        [InlineKeyboardButton("🛑 Stop", callback_data=f"terminate_{display_name}")],
        [InlineKeyboardButton("🔁 Restart", callback_data=f"restart_{display_name}")],
        [InlineKeyboardButton("📜 Log", callback_data=f"log_{display_name}")]
    ]
    update.effective_message.reply_text(
        f"✅ Project <b>{display_name}</b> started and hosted.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([link_button] + control_buttons)
    )

def stop_command(uid, display_name, bot):
    if display_name in user_projects.get(uid, []):
        user_projects[uid].remove(display_name)
        bot.send_message(chat_id=uid, text=f"💤 Project <b>{display_name}</b> auto-terminated.", parse_mode="HTML")

def start(update: Update, context: CallbackContext):
    user = update.effective_user
    uid = user.id
    name = user.first_name
    image = "https://files.catbox.moe/efem5j.jpg"
    keyboard = [
        [InlineKeyboardButton("🐍 Host Python File", callback_data="host_py")],
        [InlineKeyboardButton("📁 My Projects", callback_data="my_projects")],
        [InlineKeyboardButton("🗜 Deploy ZIP File", callback_data="deploy_zip")],
        [InlineKeyboardButton("🧬 Deploy GitHub URL", callback_data="deploy_github")]
    ]
    caption = f"""👋 Hello <b>{name}</b>,

💐 Welcome to ⛥ PLAY-Z PYTHON HOSTING BOT ⛥
🔷 Host your Python codes easily
⏱️ 10-min Auto Sleep for Free Plan

<em>© Powered by PLAY-Z HACKING</em>"""
    context.bot.send_photo(chat_id=uid, photo=image, caption=caption, parse_mode="HTML",
                           reply_markup=InlineKeyboardMarkup(keyboard))

def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    data = query.data
    uid = query.from_user.id

    if data == "host_py":
        query.message.reply_text("📁 Send a .py file to run.")
    elif data == "deploy_zip":
        query.message.reply_text("🗜 Send a .zip file.")
    elif data == "deploy_github":
        query.message.reply_text("📎 Send a GitHub repo link.")
    elif data == "my_projects":
        files = user_projects.get(uid, [])
        if not files:
            return query.message.reply_text("❌ No active projects.")
        buttons = [[InlineKeyboardButton(f"❌ {f}", callback_data=f"terminate_{f}")] for f in files]
        query.message.reply_text("📁 Active projects:", reply_markup=InlineKeyboardMarkup(buttons))
    elif data.startswith("terminate_"):
        filename = data.split("terminate_")[1]
        stop_command(uid, filename, context.bot)
        query.message.reply_text(f"✅ Project <b>{filename}</b> terminated.", parse_mode="HTML")
    elif data.startswith("log_"):
        filename = data.split("log_")[1]
        logpath = os.path.join(LOG_DIR, f"{uid}_{filename}.txt")
        if os.path.exists(logpath):
            with open(logpath, "rb") as f:
                context.bot.send_document(chat_id=uid, document=f, filename=f"{filename}.log")
        else:
            query.message.reply_text("❌ Log not found.")
    elif data.startswith("restart_"):
        filename = data.split("restart_")[1]
        path = os.path.join(BASE_DIR, f"{uid}_{filename}")
        if os.path.exists(path):
            run_command(uid, f"python3 '{path}'", filename, update, context)
        else:
            query.message.reply_text("❌ File not found.")

def handle_file(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    file = update.message.document

    if not file.file_name.endswith(".py"):
        return update.message.reply_text("❌ Send a valid .py file.")
    if file.file_size > MAX_FILE_SIZE:
        return update.message.reply_text("❌ File too large. Max 50MB allowed.")

    filename = f"{uid}_{file.file_name}"
    path = os.path.join(BASE_DIR, filename)
    file.get_file().download(path)

    run_command(uid, f"python3 '{path}'", file.file_name, update, context)

def handle_zip_file(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    file = update.message.document

    if not is_premium(uid):
        return update.message.reply_text("❌ ZIP is for premium users.")
    if not file.file_name.endswith(".zip"):
        return update.message.reply_text("❌ Not a zip file.")
    if file.file_size > MAX_FILE_SIZE:
        return update.message.reply_text("❌ File too large.")

    zip_path = os.path.join(BASE_DIR, f"{uid}_{file.file_name}")
    file.get_file().download(zip_path)
    extract_path = os.path.join(BASE_DIR, f"{uid}_{int(time.time())}")
    os.makedirs(extract_path, exist_ok=True)

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_path)
    os.remove(zip_path)

    for root, _, files in os.walk(extract_path):
        for f in files:
            if f.endswith(".py"):
                full_path = os.path.join(root, f)
                run_command(uid, f"python3 '{full_path}'", f, update, context)
                return update.message.reply_text("✅ Project deployed.")
    update.message.reply_text("❌ No .py file found.")

def handle_github_link(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    text = update.message.text.strip()
    if not is_premium(uid):
        return update.message.reply_text("❌ GitHub deploy is for premium users.")
    if not text.startswith("https://github.com/"):
        return update.message.reply_text("❌ Invalid GitHub URL.")

    url = text.rstrip("/")
    zip_url = url + "/archive/refs/heads/main.zip"
    r = requests.get(zip_url)
    if r.status_code != 200:
        zip_url = url + "/archive/refs/heads/master.zip"
        r = requests.get(zip_url)
        if r.status_code != 200:
            return update.message.reply_text("❌ Could not download repo.")

    zip_path = os.path.join(BASE_DIR, f"{uid}_repo.zip")
    with open(zip_path, "wb") as f:
        f.write(r.content)

    extract_path = os.path.join(BASE_DIR, f"{uid}_{int(time.time())}")
    os.makedirs(extract_path, exist_ok=True)

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_path)
    os.remove(zip_path)

    for root, _, files in os.walk(extract_path):
        for f in files:
            if f.endswith(".py"):
                full_path = os.path.join(root, f)
                run_command(uid, f"python3 '{full_path}'", f, update, context)
                return update.message.reply_text("✅ GitHub Project deployed.")
    update.message.reply_text("❌ No .py found in repo.")

def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(button_handler))
    dp.add_handler(MessageHandler(Filters.document.mime_type("text/x-python"), handle_file))
    dp.add_handler(MessageHandler(Filters.document.mime_type("application/zip"), handle_zip_file))
    dp.add_handler(MessageHandler(Filters.text & (~Filters.command), handle_github_link))
    updater.start_polling()
    updater.idle()

# Run Flask server for Koyeb
app = Flask(__name__)
@app.route('/')
def home(): return "Bot is Running!"

def run_flask():
    app.run(host='0.0.0.0', port=8000)

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    main()