import os
import json
import io
import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler
)
import gspread
from google.oauth2.service_account import Credentials

# Config logger
logging.basicConfig(level=logging.INFO)

# Definim stările conversației
SELECT_FIRMA, GET_EMITENT, GET_SUM, GET_DATE, GET_CATEGORY = range(5)

# Dicționar temporar de stocare a datelor
user_data = {}

# Define firmele și sheets-urile lor
FIRME = {
    "Costel Financial Broker SRL": "bonuri_costel_financial",
    "Like Arrows SRL": "bonuri_like_arrows"
}

def get_gspread_client():
    keyfile_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    keyfile_dict = json.loads(keyfile_json)
    credentials = Credentials.from_service_account_info(keyfile_dict, scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ])
    return gspread.authorize(credentials)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Salut! Trimite-mi o poză cu bonul sau factura și începem înregistrarea 📸"
    )
    return ConversationHandler.END

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    photo = update.message.photo[-1]
    file = await photo.get_file()
    os.makedirs("temp", exist_ok=True)
    file_path = f"temp/{photo.file_unique_id}.jpg"
    await file.download_to_drive(file_path)

    user_data[user_id] = {
        "photo_path": file_path
    }

    reply_keyboard = [[f] for f in FIRME.keys()]
    await update.message.reply_text(
        "Pentru ce firmă este acest bon?",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
    )
    return SELECT_FIRMA

async def select_firma(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    firma = update.message.text
    if firma not in FIRME:
        await update.message.reply_text("Te rog alege o firmă validă.")
        return SELECT_FIRMA

    user_data[user_id]["firma"] = firma
    await update.message.reply_text("1️⃣ Cine a emis bonul?", reply_markup=ReplyKeyboardRemove())
    return GET_EMITENT

async def get_emitent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data[user_id]["emitent"] = update.message.text
    await update.message.reply_text("2️⃣ Ce sumă apare pe bon?")
    return GET_SUM

async def get_sum(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data[user_id]["suma"] = update.message.text
    await update.message.reply_text("3️⃣ Ce dată apare pe bon? (ex: 22.04.2025)")
    return GET_DATE

async def get_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data[user_id]["data"] = update.message.text
    await update.message.reply_text("4️⃣ Ce tip de cheltuială este? (ex: alimentație, transport, birou)")
    return GET_CATEGORY

async def get_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data[user_id]["categorie"] = update.message.text

    data = user_data[user_id]
    sheet_name = FIRME[data["firma"]]

    try:
        client = get_gspread_client()
        sheet = client.open(sheet_name).worksheet("Bonuri")
        await update.message.reply_text("📄 Acces la Google Sheet OK ✅")
    except Exception as e:
        await update.message.reply_text(f"❌ Eroare la accesarea Google Sheet:\n{e}")
        print("EROARE ACCES SHEET:", e)
        return ConversationHandler.END

    photo_link = "poza_locala"  # în viitor: link Google Drive

    try:
        sheet.append_row([
            data["data"],
            data["emitent"],
            data["suma"],
            data["categorie"],
            photo_link
        ])
        await update.message.reply_text(f"✅ Bonul a fost salvat în *{data['firma']}*. Mulțumim!")
    except Exception as e:
        await update.message.reply_text(f"❌ Eroare la salvarea în sheet:\n{e}")
        print("EROARE SCRIERE SHEET:", e)

    del user_data[user_id]
    return ConversationHandler.END

def main():
    app = ApplicationBuilder().token(os.getenv("TELEGRAM_TOKEN")).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.PHOTO, handle_photo)],
        states={
            SELECT_FIRMA: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_firma)],
            GET_EMITENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_emitent)],
            GET_SUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_sum)],
            GET_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_date)],
            GET_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_category)],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)

    app.run_polling()

if __name__ == "__main__":
    main()

