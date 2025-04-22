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

    photo_link = "poza_locala"  # sau ""

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
