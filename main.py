import os
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

async def start(update, context):
    await update.message.reply_text("Salut! Sunt online!")

def main():
    token = os.getenv("TELEGRAM_TOKEN")
    print("🔍 TOKEN DEBUG:", token)  # <- linia importantă

    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.run_polling()

if __name__ == '__main__':
    main()
