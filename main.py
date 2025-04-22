import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Salut! Trimite-mi o poză cu bonul sau factura și mă ocup de restul 🤖")

# primire poze (bonuri)
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.first_name
    photo = update.message.photo[-1]  # cea mai mare calitate
    file = await photo.get_file()
    
    # Creează folder temporar dacă nu există
    os.makedirs("temp", exist_ok=True)

    file_path = f"temp/{photo.file_unique_id}.jpg"
    await file.download_to_drive(file_path)

    await update.message.reply_text(f"Mulțumesc, {user}! Bonul a fost primit ✅\nÎl trimit acum spre procesare 🔄")

    # Aici poți trimite fișierul la OCRBot sau salvezi în Drive

# fallback pt text
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Trimite-mi o poză cu un bon sau o factură 📷")

def main():
    token = os.getenv("TELEGRAM_TOKEN")
    print("DEBUG TOKEN:", token)  # Poți șterge după testare

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.run_polling()

if __name__ == '__main__':
    main()
