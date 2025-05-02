import os
import json
import logging
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler
)
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.service_account import Credentials as DriveCredentials
import openai

# Config logger
logging.basicConfig(level=logging.INFO)

# Stările conversației
SELECT_FIRMA, GET_EMITENT, GET_SUM, GET_DATE, GET_CATEGORY, PROCESS_CHOICE = range(6)

# Dicționar temporar per utilizator
user_data = {}

# Sheets și foldere per firmă
FIRMA_FIX = "Costel Financial Broker SRL"
SHEET_NAME = "bonuri_costel_financial"
DRIVE_FOLDER_ID = "1nJYF876VwK9Fa1E2hBheqMIOEu8JY7Jw"

# Sheets

def get_gspread_client():
    keyfile_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    keyfile_dict = json.loads(keyfile_json)
    credentials = Credentials.from_service_account_info(keyfile_dict, scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ])
    return gspread.authorize(credentials)

# Drive

def get_drive_service():
    keyfile_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    creds_dict = json.loads(keyfile_json)
    creds = DriveCredentials.from_service_account_info(creds_dict, scopes=[
        "https://www.googleapis.com/auth/drive"
    ])
    return build("drive", "v3", credentials=creds)

# Comenzi

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Salut! Trimite-mi o poză cu bonul și alegi ce vrei să fac 📸")
    return ConversationHandler.END

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    photo = update.message.photo[-1]
    file = await photo.get_file()
    os.makedirs("temp", exist_ok=True)
    file_path = f"temp/{photo.file_unique_id}.jpg"
    await file.download_to_drive(file_path)

    user_data[user_id] = {"photo_path": file_path}

    reply_keyboard = [["Adaugă ca bon"], ["Analizează cu AI"]]
    await update.message.reply_text(
        "📸 Ce vrei să fac cu această poză?",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
    )
    return PROCESS_CHOICE

async def process_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    choice = update.message.text.lower()

    if "adaugă" in choice:
        user_data[user_id]["firma"] = FIRMA_FIX
        await update.message.reply_text("1️⃣ Cine a emis bonul?", reply_markup=ReplyKeyboardRemove())
        return GET_EMITENT

    elif "analizează" in choice:
        photo_path = user_data[user_id]["photo_path"]
        await update.message.reply_text("🔍 Analizez poza, te rog așteaptă...")
        await update.message.reply_text("✅ Am analizat poza (exemplu). Poți pune întrebări despre ea sau orice altceva!")
        del user_data[user_id]
        return ConversationHandler.END

    else:
        await update.message.reply_text("Te rog alege o opțiune validă: Adaugă ca bon sau Analizează cu AI.")
        return PROCESS_CHOICE

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
    photo_path = data["photo_path"]

    try:
        drive_service = get_drive_service()
        sheet_client = get_gspread_client()
        sheet = sheet_client.open(SHEET_NAME).worksheet("Bonuri")
    except Exception as e:
        await update.message.reply_text(f"❌ Eroare la inițializare Drive/Sheets:\n{e}")
        return ConversationHandler.END

    try:
        date_obj = datetime.strptime(data["data"], "%d.%m.%Y")
        folder_luna = date_obj.strftime("%B_%Y").capitalize()

        def create_or_get_folder(service, name, parent_id):
            query = f"mimeType='application/vnd.google-apps.folder' and name='{name}' and '{parent_id}' in parents and trashed=false"
            results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
            files = results.get("files", [])
            if files:
                return files[0]["id"]
            file_metadata = {
                "name": name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [parent_id]
            }
            file = service.files().create(body=file_metadata, fields="id").execute()
            return file.get("id")

        folder_bonuri = create_or_get_folder(drive_service, "Bonuri", DRIVE_FOLDER_ID)
        folder_luna_id = create_or_get_folder(drive_service, folder_luna, folder_bonuri)

        file_metadata = {
            "name": f"bon_{datetime.now().strftime('%H%M%S')}.jpg",
            "parents": [folder_luna_id]
        }
        media = MediaFileUpload(photo_path, mimetype="image/jpeg")
        file = drive_service.files().create(body=file_metadata, media_body=media, fields="id").execute()

        file_id = file.get("id")
        drive_service.permissions().create(
            fileId=file_id,
            body={"type": "anyone", "role": "reader"},
            fields="id"
        ).execute()
        file_url = f"https://drive.google.com/file/d/{file_id}/view"

    except Exception as e:
        await update.message.reply_text(f"❌ Eroare la salvarea pozei în Google Drive:\n{e}")
        return ConversationHandler.END

    try:
        sheet.append_row([
            data["data"],
            data["emitent"],
            data["suma"],
            data["categorie"],
            file_url
        ])
        await update.message.reply_text(f"✅ Bonul a fost salvat în Google Sheet și poza în Drive 📁")
    except Exception as e:
        await update.message.reply_text(f"❌ Eroare la scrierea în sheet:\n{e}")

    del user_data[user_id]
    return ConversationHandler.END

async def handle_general_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    await update.message.reply_text("💬 Procesăm întrebarea ta cu AI, așteaptă...")
    try:
        openai.api_key = os.getenv("OPENAI_API_KEY")
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ești un asistent contabil care oferă răspunsuri clare și precise."},
                {"role": "user", "content": user_message}
            ]
        )
        answer = response.choices[0].message.content
        await update.message.reply_text(answer)
    except Exception as e:
        await update.message.reply_text(f"❌ Eroare la comunicarea cu ChatGPT:\n{e}")

# Main

def main():
    app = ApplicationBuilder().token(os.getenv("TELEGRAM_TOKEN")).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.PHOTO, handle_photo)],
        states={
            PROCESS_CHOICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_choice)],
            GET_EMITENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_emitent)],
            GET_SUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_sum)],
            GET_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_date)],
            GET_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_category)],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_general_text))

    app.run_polling()

if __name__ == "__main__":
    main()

