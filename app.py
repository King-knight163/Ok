from flask import Flask
import threading
from main import main  # This will import your Telegram bot main() function

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is Running!", 200

def run_flask():
    app.run(host='0.0.0.0', port=8000)

if __name__ == "__main__":
    # Start Flask app in background thread to keep service alive
    threading.Thread(target=run_flask).start()

    # Start your actual Telegram bot
    main()