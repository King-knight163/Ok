from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext
import os, subprocess, time, json, zipfile, requests
from datetime import datetime, timedelta, timezone as dt_timezone
from apscheduler.schedulers.background import BackgroundScheduler
from pytz import timezone

BOT_TOKEN = "7659870883:AAHIHWRgYVx7uvj5D5H_pe-t2nPKkPLBZxw"
ADMIN_ID = 7107162691

BASE_DIR = "projects"
LOG_DIR = "logs"
PREMIUM_FILE = "premium.json"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

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

def safe_session(uid, name):
    return f"{uid}{name.replace('.', '').replace('/', '_')}"

def auto_terminate(uid, filename, bot):
    session = safe_session(uid, filename)
    subprocess.call(f"tmux kill-session -t {session}", shell=True)
    if filename in user_projects.get(uid, []):
        user_projects[uid].remove(filename)
        bot.send_message(chat_id=uid, text=f"💤 Project <b>{filename}</b> auto-terminated.", parse_mode="HTML")

def run_command(uid, command, display_name, update, context):
    session = safe_session(uid, display_name)
    logpath = os.path.join(LOG_DIR, f"{session}.txt")

    subprocess.call(f"tmux kill-session -t {session}", shell=True)
    subprocess.call(f"tmux new-session -d -s {session} '{command} 2>&1 | tee {logpath}'", shell=True)

    user_projects.setdefault(uid, [])
    if display_name not in user_projects[uid]:
        user_projects[uid].append(display_name)

    if not is_premium(uid):
        scheduler.add_job(auto_terminate, 'date', run_date=datetime.now(dt_timezone.utc) + timedelta(minutes=10),
                          args=[uid, display_name, context.bot], id=f"{uid}_{display_name}", replace_existing=True)

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
    user = update.effective_user
    uid = user.id
    name = user.first_name
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
    context.bot.send_photo(chat_id=uid, photo=image, caption=caption, parse_mode="HTML",
                           reply_markup=InlineKeyboardMarkup(keyboard))

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
        files = user_projects.get(uid, [])
        if not files:
            return query.message.reply_text("❌ No active projects.")
        buttons = [[InlineKeyboardButton(f"❌ {f}", callback_data=f"terminate_{f}")] for f in files]
        query.message.reply_text("📁 Active projects:", reply_markup=InlineKeyboardMarkup(buttons))
    elif data == "terminate_one":
        files = user_projects.get(uid, [])
        if not files:
            return query.message.reply_text("❌ No active projects.")
        buttons = [[InlineKeyboardButton(f"🛠 Stop {f}", callback_data=f"terminate_{f}")] for f in files]
        query.message.reply_text("🛠 Select project to terminate:", reply_markup=InlineKeyboardMarkup(buttons))
    elif data == "terminate_all":
        if uid != ADMIN_ID:
            return query.answer("❌ Only admin can use this.")
        subprocess.call("tmux kill-server", shell=True)
        user_projects.clear()
        query.message.reply_text("🧨 All sessions terminated by admin.")
    elif data == "my_plan":
        now = datetime.now(timezone("Asia/Kolkata"))
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        expiry = premium_users.get(str(uid))
        project_count = len(user_projects.get(uid, []))

        if expiry:
            expiry_dt = datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S")
            days_left = (expiry_dt - datetime.utcnow()).days
            if datetime.utcnow() > expiry_dt:
                del premium_users[str(uid)]
                save_premium(premium_users)
                return query.message.reply_text("❌ Your premium plan has expired.", parse_mode="HTML")
            text = f"""<b>╔══════════════════════╗
🌟 PREMIUM PLAN ACTIVE
╚══════════════════════╝</b>
<b>👤 USER ID:</b> <code>{uid}</code>
<b>📅 EXPIRES ON:</b> <code>{expiry}</code>
<b>🕒 CURRENT TIME:</b> <code>{now_str}</code>
<b>⏳ DAYS LEFT:</b> <code>{days_left} day(s)</code>
<b>📂 ACTIVE PROJECTS:</b> <code>{project_count}</code>
<b>✨ YOUR PREMIUM BENEFITS:</b>
├ 🗂️ Unlimited .py Projects Hosting
├ 🚫 No Auto-Terminate
├ 🧠 Full Log Access Anytime
├ 🔄 Unlimited Restarts
├ 📂 ZIP & GitHub Hosting
└ ⚡ Fastest Execution Priority
<b>💡 NEED TO EXTEND?</b>
📩 Contact <a href="https://t.me/PLAYZ_HELP_BOT">PLAY-Z HELP BOT</a>
📎 Send Your ID: <code>{uid}</code>
<b>🔧 Powered by:</b> <a href="https://t.me/+CK4EXZbq7DRkZmE1">PLAY-Z HACKING</a>"""
        else:
            text = f"""<b>╔══════════════════╗
🆓 FREE PLAN ACTIVE
╚══════════════════╝</b>
<b>👤 USER ID:</b> <code>{uid}</code>
<b>🕒 CURRENT TIME:</b> <code>{now_str}</code>
<b>📂 ACTIVE PROJECTS:</b> <code>{project_count}/3</code>
<b>❌ FREE PLAN LIMITS:</b>
├ 📄 Max 3 .py Projects
├ ⏱️ Auto-Terminate in 10 min
├ 📂 No ZIP or GitHub Hosting
<b>💡 WANT TO UPGRADE?</b>
✨ Get Premium for:
✔ Unlimited Hosting
✔ Full Log Access
✔ ZIP + GitHub Support
<b>🔧 Powered by:</b> ©<b>PLAY-Z HACKING</b>"""
        query.message.reply_text(text, parse_mode="HTML", disable_web_page_preview=True)
    elif data.startswith("terminate_"):
        filename = data.split("terminate_")[1]
        session = safe_session(uid, filename)
        subprocess.call(f"tmux kill-session -t {session}", shell=True)
        if filename in user_projects.get(uid, []):
            user_projects[uid].remove(filename)
        query.message.reply_text(f"✅ Project <b>{filename}</b> terminated.", parse_mode="HTML")
    elif data.startswith("restart_"):
        filename = data.split("restart_")[1]
        path = os.path.join(BASE_DIR, filename)
        if os.path.exists(path):
            with open(path, "r") as f:
                cmd = f.read().strip()
            run_command(uid, cmd, filename, update, context)
        else:
            query.message.reply_text("❌ Command file missing.")
    elif data.startswith("log_"):
        filename = data.split("log_")[1]
        session = safe_session(uid, filename)
        logpath = os.path.join(LOG_DIR, f"{session}.txt")
        if os.path.exists(logpath):
            with open(logpath, "rb") as f:
                context.bot.send_document(chat_id=uid, document=f, filename=f"{filename}.txt")
        else:
            context.bot.send_message(chat_id=uid, text="❌ Log not found.")

def handle_file(update: Update, context: CallbackContext):
    file = update.message.document
    uid = update.effective_user.id

    if not file.file_name.endswith(".py"):
        return update.message.reply_text("❌ Send a valid .py file only.")
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
        return update.message.reply_text("❌ ZIP feature is for premium users.")
    if not file.file_name.endswith(".zip"):
        return update.message.reply_text("❌ Upload a valid .zip file.")
    if file.file_size > MAX_FILE_SIZE:
        return update.message.reply_text("❌ ZIP file too large. Max 50MB allowed.")

    zip_name = f"{uid}_{file.file_name}"
    zip_path = os.path.join(BASE_DIR, zip_name)
    file.get_file().download(zip_path)

    msg = update.message.reply_text("📦 Extracting ZIP...")
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            extract_path = os.path.join(BASE_DIR, f"{uid}_{int(time.time())}")
            os.makedirs(extract_path, exist_ok=True)
            zip_ref.extractall(extract_path)
            os.remove(zip_path)
            handle_extracted(uid, extract_path, msg, update, context)
    except:
        msg.edit_text("❌ Invalid ZIP file.")

def handle_github_link(update: Update, context: CallbackContext):
    url = update.message.text.strip()
    uid = update.effective_user.id

    if not is_premium(uid):
        return update.message.reply_text("❌ GitHub support is for premium users.")
    if not url.startswith("https://github.com/"):
        return update.message.reply_text("❌ Invalid GitHub URL.")

    base = url.rstrip("/")
    download_url = base + "/archive/refs/heads/main.zip"
    r = requests.head(download_url)
    if r.status_code != 200:
        download_url = base + "/archive/refs/heads/master.zip"
        r = requests.head(download_url)
        if r.status_code != 200:
            return update.message.reply_text("❌ Could not download repo.")

    size = int(r.headers.get("Content-Length", 0))
    if size > MAX_FILE_SIZE:
        return update.message.reply_text("❌ GitHub ZIP too large. Max 50MB allowed.")

    r = requests.get(download_url)
    zip_name = f"{uid}github{int(time.time())}.zip"
    zip_path = os.path.join(BASE_DIR, zip_name)
    with open(zip_path, "wb") as f:
        f.write(r.content)

    msg = update.message.reply_text("📦 Extracting GitHub ZIP...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        extract_path = os.path.join(BASE_DIR, f"{uid}_{int(time.time())}")
        os.makedirs(extract_path, exist_ok=True)
        zip_ref.extractall(extract_path)
        os.remove(zip_path)
        handle_extracted(uid, extract_path, msg, update, context)

def handle_extracted(uid, extract_path, msg, update, context):
    cmd_path = None
    for root, _, files in os.walk(extract_path):
        for f in files:
            if f == "cmd.txt":
                cmd_path = os.path.join(root, f)
                break

    if cmd_path:
        with open(cmd_path) as f:
            command = f.read().strip()
        run_command(uid, command, os.path.basename(cmd_path), update, context)
        msg.edit_text("✅ cmd.txt found and running project.")
    else:
        py_files = []
        for root, _, files in os.walk(extract_path):
            for f in files:
                if f.endswith(".py"):
                    full = os.path.join(root, f)
                    py_files.append(full)
        if not py_files:
            return msg.edit_text("❌ No .py or cmd.txt found.")
        file = py_files[0]
        run_command(uid, f"python3 '{file}'", os.path.basename(file), update, context)
        msg.edit_text("✅ No cmd.txt, running first .py file.")

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
    dp.add_handler(MessageHandler(Filters.document.mime_type("application/zip"), handle_zip_file))
    dp.add_handler(MessageHandler(Filters.document.mime_type("text/x-python"), handle_file))
    dp.add_handler(MessageHandler(Filters.text & (~Filters.command), handle_github_link))

    updater.start_polling()
    updater.idle()

# ... (baaki pura bot ka code same rahega)

from flask import Flask
import threading

# Flask app to keep Koyeb Web Service happy
app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running!", 200

def run_flask():
    app.run(host='0.0.0.0', port=8000)

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    main()