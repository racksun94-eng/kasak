import os
import asyncio
import requests
from flask import Flask
from threading import Thread
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    KeyboardButtonRequestUsers,
    KeyboardButtonRequestChat,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set!")

ADMIN_ID = 8300271033

BASE_URL = "https://api.subhxcosmo.in/api?key=RACKSUN&type=tg&term="
NUMBER_API_URL = "http://node-production-1649.up.railway.app/api/num-india?key=NUMBER&num={number}"
AADHAR_API_URL = "https://ayush-multi-api.vercel.app/api/adhar?term={aadhar}"
TG_TO_NUM_API = "https://anon-tg-info.vercel.app/tg2num/userid?key=temp224&q={user_id}"
CHANNEL_USERNAME = "@racksun19"
CHANNEL_LINK = "https://t.me/racksun19"

USERS_FILE = "users.txt"
known_users = set()


def load_users():
    global known_users
    if not os.path.exists(USERS_FILE):
        return
    f = open(USERS_FILE, "r")
    for line in f:
        line = line.strip()
        if line.isdigit():
            known_users.add(int(line))
    f.close()


def track_user(user_id):
    if not user_id:
        return
    if user_id in known_users:
        return
    known_users.add(user_id)
    f = open(USERS_FILE, "a")
    f.write(str(user_id) + "\n")
    f.close()


def clean_address(addr):
    if not addr:
        return "N/A"
    if "!" in addr:
        parts = []
        for p in addr.split("!"):
            p = p.strip()
            if p and p != ".":
                parts.append(p)
        if parts:
            return ", ".join(parts)
        return "N/A"
    cleaned = " ".join(addr.split())
    if cleaned:
        return cleaned
    return "N/A"


async def delete_searching(context, chat_id, msg_id):
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
    except Exception:
        pass


flask_app = Flask(__name__)


@flask_app.route("/")
def home():
    return "Bot is Alive!"


def run_flask():
    port = int(os.environ.get("PORT", 8000))
    flask_app.run(host="0.0.0.0", port=port)


def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()


async def is_member(user_id, context):
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
    except Exception:
        return False
    if member.status == "member":
        return True
    if member.status == "administrator":
        return True
    if member.status == "creator":
        return True
    return False


async def send_join_message(update, context):
    user = update.message.from_user
    first_name = user.first_name or "User"
    join_button = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK)],
        [InlineKeyboardButton("✅ I have Joined", callback_data="check_joined")]
    ])
    text = "⚠️ *Hello " + first_name + "!*\n\nJoin our channel to use this bot.\nAfter joining, click *I have Joined* button."
    sent = await update.message.reply_text(text, reply_markup=join_button, parse_mode="Markdown")
    context.user_data["join_msg_id"] = sent.message_id


async def delete_join_message(context, chat_id):
    msg_id = context.user_data.get("join_msg_id")
    if not msg_id:
        return
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
    except Exception:
        pass
    context.user_data.pop("join_msg_id", None)
    await context.bot.send_message(
        chat_id=chat_id,
        text="✅ *You have successfully joined our channel!*\n\nYou can now use the bot freely. Send /start to begin.",
        parse_mode="Markdown"
    )


async def check_joined_callback(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    track_user(user_id)
    member_ok = await is_member(user_id, context)
    if not member_ok:
        await query.answer("❌ You have not joined yet! Please join first.", show_alert=True)
        return
    await query.message.delete()
    context.user_data.pop("join_msg_id", None)
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="✅ *You have successfully joined our channel!*\n\nYou can now use the bot freely. Send /start to begin.",
        parse_mode="Markdown"
    )


def main_menu_markup():
    btn_user = KeyboardButton(text="User", request_users=KeyboardButtonRequestUsers(request_id=1, max_quantity=1))
    btn_group = KeyboardButton(text="Group", request_chat=KeyboardButtonRequestChat(request_id=2, chat_is_channel=False))
    btn_channel = KeyboardButton(text="Channel", request_chat=KeyboardButtonRequestChat(request_id=3, chat_is_channel=True))
    return ReplyKeyboardMarkup([[btn_user, btn_group, btn_channel]], resize_keyboard=True)


async def show_main_menu(update, context, header=None):
    user_id = update.message.from_user.id
    parts = []
    if header:
        parts.append(header + "\n\n")
    parts.append("*Welcome To @racksunbot*\n\n")
    parts.append("*Your ID :* `" + str(user_id) + "`\n\n")
    parts.append("Send me a Telegram username or number to look up.\n")
    parts.append("Example: @username or 1234567890\n\n")
    parts.append("Or use the buttons below to get User/Group/Channel ID:")
    welcome_msg = "".join(parts)
    await update.message.reply_text(welcome_msg, reply_markup=main_menu_markup(), parse_mode="Markdown")


async def start(update, context):
    user_id = update.message.from_user.id
    track_user(user_id)
    chat_id = update.message.chat_id
    if not await is_member(user_id, context):
        await send_join_message(update, context)
        return
    await delete_join_message(context, chat_id)
    context.user_data.clear()
    await show_main_menu(update, context)


async def back_command(update, context):
    user_id = update.message.from_user.id
    track_user(user_id)
    chat_id = update.message.chat_id
    if not await is_member(user_id, context):
        await send_join_message(update, context)
        return
    await delete_join_message(context, chat_id)
    await show_main_menu(update, context, header="🔙 *Back to main menu.*")


async def cancel_command(update, context):
    user_id = update.message.from_user.id
    track_user(user_id)
    chat_id = update.message.chat_id
    if not await is_member(user_id, context):
        await send_join_message(update, context)
        return
    await delete_join_message(context, chat_id)
    context.user_data.clear()
    await show_main_menu(update, context, header="❌ *Cancelled.*")


async def settings_command(update, context):
    user_id = update.message.from_user.id
    track_user(user_id)
    chat_id = update.message.chat_id
    if not await is_member(user_id, context):
        await send_join_message(update, context)
        return
    await delete_join_message(context, chat_id)
    settings_text = (
        "⚙️ *Settings*\n\n"
        "*What this bot can do:*\n\n"
        "📱 *Username / UID Lookup*\n"
        "Send any @username or numeric ID to get details instantly\n\n"
        "📞 *Phone Number Lookup*\n"
        "Use `/num <number>` to fetch available information\n\n"
        "🪪 *Aadhar Lookup*\n"
        "Use `/aadhar <12-digit number>` to fetch info\n\n"
        "👥 *User / Group / Channel ID*\n"
        "Use the buttons below to get IDs easily\n\n"
        "📝 *Report Issue*\n"
        "Use `/report <message>` to report any bot issue to admin\n\n"
        "⚡ *Fast and Automatic*\n"
        "No extra commands needed for basic lookups\n\n"
        "❓ *Help Guide*\n"
        "Use /help to see full instructions\n\n"
        "—\n\n"
        "_Thanks for using this bot._"
    )
    await update.message.reply_text(settings_text, parse_mode="Markdown")


async def help_command(update, context):
    user_id = update.message.from_user.id
    track_user(user_id)
    chat_id = update.message.chat_id
    if not await is_member(user_id, context):
        await send_join_message(update, context)
        return
    await delete_join_message(context, chat_id)
    help_text = (
        "🤖 *Welcome to @racksunbot Help*\n\n"
        "Here is how to use this bot:\n\n"
        "📱 *Telegram Username / UID Lookup*\n"
        "  Just send the username or UID directly in chat.\n"
        "  No command needed.\n\n"
        "  Examples:\n"
        "   • `@username`\n"
        "   • `1234567890`\n\n"
        "📞 *Phone Number Lookup*\n"
        "  Use the /num command followed by the number.\n\n"
        "  Example:\n"
        "   • `/num 9876543210`\n\n"
        "🪪 *Aadhar Lookup*\n"
        "  Use the /aadhar command followed by 12-digit Aadhar.\n\n"
        "  Example:\n"
        "   • `/aadhar 652507323571`\n\n"
        "📝 *Report an Issue*\n"
        "  Use the /report command followed by your message.\n"
        "  Your report will be sent directly to the admin.\n\n"
        "  Example:\n"
        "   • `/report Bot is not responding properly`\n\n"
        "📋 *Available Commands*\n"
        "  /start    — Start the bot\n"
        "  /num      — Phone number lookup\n"
        "  /aadhar   — Aadhar lookup\n"
        "  /report   — Report an issue to admin\n"
        "  /settings — Show bot features\n"
        "  /back     — Back to main menu\n"
        "  /cancel   — Cancel current action\n"
        "  /help     — Show this help message"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def stats_command(update, context):
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID:
        return
    msg = "📊 *Bot Stats*\n\n*Total Users:* `" + str(len(known_users)) + "`"
    await update.message.reply_text(msg, parse_mode="Markdown")


async def report_command(update, context):
    user_id = update.message.from_user.id
    track_user(user_id)
    chat_id = update.message.chat_id
    if not await is_member(user_id, context):
        await send_join_message(update, context)
        return
    await delete_join_message(context, chat_id)
    if not context.args:
        usage = (
            "📝 *Report an Issue*\n\n"
            "*Usage:* `/report <your message>`\n\n"
            "*Example:*\n"
            "`/report Bot is not responding to username lookup`\n\n"
            "_Your message will be sent directly to the admin._"
        )
        await update.message.reply_text(usage, parse_mode="Markdown")
        return
    user = update.message.from_user
    report_text = " ".join(context.args)
    username = "@" + user.username if user.username else "N/A"
    full_name = user.first_name or ""
    if user.last_name:
        full_name = full_name + " " + user.last_name
    if not full_name.strip():
        full_name = "Unknown"
    admin_msg = (
        "🚨 *New Report Received*\n\n"
        "*From:* " + full_name + "\n"
        "*Username:* " + username + "\n"
        "*User ID:* `" + str(user.id) + "`\n\n"
        "*Message:*\n" + report_text
    )
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg, parse_mode="Markdown")
        await update.message.reply_text(
            "✅ *Report Sent Successfully!*\n\nYour message has been delivered to the admin. You will receive a response soon.",
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(
            "❌ *Failed to send report.*\nPlease try again after some time.",
            parse_mode="Markdown"
        )
        print("Report send error:", str(e))


async def reply_command(update, context):
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID:
        return
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "*Usage:* `/reply <user_id> <your message>`\n\n"
            "*Example:*\n"
            "`/reply 1234567890 Thanks, we have fixed the issue!`",
            parse_mode="Markdown"
        )
        return
    target_id = context.args[0]
    if not target_id.isdigit():
        await update.message.reply_text("❌ *Invalid User ID!*\nPlease enter a valid numeric User ID.", parse_mode="Markdown")
        return
    message = " ".join(context.args[1:])
    reply_text = "💬 *Reply from Admin*\n\n" + message
    try:
        await context.bot.send_message(chat_id=int(target_id), text=reply_text, parse_mode="Markdown")
        await update.message.reply_text(
            "✅ *Reply sent successfully!*\n\n"
            "*Sent to User ID:* `" + target_id + "`\n"
            "*Message:* " + message,
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(
            "❌ *Failed to send reply.*\n\n"
            "User may have blocked the bot or ID is wrong.\n"
            "*Error:* " + str(e),
            parse_mode="Markdown"
        )


async def num_lookup(update, context):
    user_id = update.message.from_user.id
    track_user(user_id)
    chat_id = update.message.chat_id
    if not await is_member(user_id, context):
        await send_join_message(update, context)
        return
    await delete_join_message(context, chat_id)
    if not context.args:
        await update.message.reply_text("*Usage:* `/num 9876543210`", parse_mode="Markdown")
        return
    number = context.args[0].replace("+", "").replace(" ", "").replace("-", "")
    searching = await update.message.reply_text("🔍 Searching...")
    try:
        url = NUMBER_API_URL.format(number=number)
        res = await asyncio.to_thread(requests.get, url, timeout=20)
        data = res.json()
    except Exception as e:
        await delete_searching(context, chat_id, searching.message_id)
        await update.message.reply_text("❌ *Error connecting to API.*\n`" + str(e) + "`", parse_mode="Markdown")
        return
    try:
        inner = data.get("data", {})
        if not inner:
            inner = data
        results = inner.get("results", [])
        total = inner.get("total", len(results))
        if not results:
            await delete_searching(context, chat_id, searching.message_id)
            await update.message.reply_text(
                "*Data Not Found!*\n\nNo information found for this number.",
                parse_mode="Markdown"
            )
            return
        header = "*Number:* `" + number + "`\n*Total Records:* `" + str(total) + "`\n"
        blocks = [header]
        i = 0
        for entry in results:
            i = i + 1
            block = (
                "\n*Record " + str(i) + "*\n"
                "*Name:* `" + str(entry.get("name") or "N/A") + "`\n"
                "*Father:* `" + str(entry.get("father_name") or "N/A") + "`\n"
                "*Mobile:* `" + str(entry.get("mobile") or "N/A") + "`\n"
                "*Alternate:* `" + str(entry.get("alternate") or "N/A") + "`\n"
                "*Aadhar:* `" + str(entry.get("aadhar") or "N/A") + "`\n"
                "*Email:* `" + str(entry.get("email") or "N/A") + "`\n"
                "*Circle:* `" + str(entry.get("circle") or "N/A") + "`\n"
                "*Truecaller:* `" + str(entry.get("truecaller_name") or "N/A") + "`\n"
                "*Address:* `" + clean_address(entry.get("address")) + "`"
            )
            blocks.append(block)
        text = "\n".join(blocks)
        await delete_searching(context, chat_id, searching.message_id)
        chunk = ""
        for line in text.split("\n"):
            if len(chunk) + len(line) + 1 > 3800:
                await update.message.reply_text(chunk, parse_mode="Markdown")
                chunk = line + "\n"
            else:
                chunk = chunk + line + "\n"
        if chunk.strip():
            await update.message.reply_text(chunk, parse_mode="Markdown")
    except Exception as e:
        await delete_searching(context, chat_id, searching.message_id)
        await update.message.reply_text("❌ *Failed to parse response.*\n`" + str(e) + "`", parse_mode="Markdown")


async def aadhar_lookup(update, context):
    user_id = update.message.from_user.id
    track_user(user_id)
    chat_id = update.message.chat_id
    if not await is_member(user_id, context):
        await send_join_message(update, context)
        return
    await delete_join_message(context, chat_id)
    if not context.args:
        await update.message.reply_text("*Usage:* `/aadhar 652507323571`", parse_mode="Markdown")
        return
    aadhar = context.args[0].replace(" ", "").replace("-", "")
    searching = await update.message.reply_text("🔍 Searching...")
    try:
        url = AADHAR_API_URL.format(aadhar=aadhar)
        res = await asyncio.to_thread(requests.get, url, timeout=20)
        data = res.json()
    except Exception as e:
        await delete_searching(context, chat_id, searching.message_id)
        await update.message.reply_text("❌ *Error connecting to API.*\n`" + str(e) + "`", parse_mode="Markdown")
        return
    entries = []
    if isinstance(data, dict):
        for k in data:
            v = data[k]
            if k.isdigit() and isinstance(v, dict):
                entries.append(v)
    if not entries:
        await delete_searching(context, chat_id, searching.message_id)
        await update.message.reply_text("*Data Not Found!*\n\nNo information found for this Aadhar.", parse_mode="Markdown")
        return
    header = "*Aadhar:* `" + aadhar + "`\n*Total Records:* `" + str(len(entries)) + "`\n"
    blocks = [header]
    i = 0
    for entry in entries:
        i = i + 1
        block = (
            "\n*Record " + str(i) + "*\n"
            "*Name:* `" + str(entry.get("name") or "N/A") + "`\n"
            "*Father:* `" + str(entry.get("fname") or "N/A") + "`\n"
            "*Mobile:* `" + str(entry.get("mobile") or "N/A") + "`\n"
            "*Alt Mobile:* `" + str(entry.get("alt") or "N/A") + "`\n"
            "*Email:* `" + str(entry.get("email") or "N/A") + "`\n"
            "*Circle:* `" + str(entry.get("circle") or "N/A") + "`\n"
            "*Address:* `" + clean_address(entry.get("address")) + "`"
        )
        blocks.append(block)
    text = "\n".join(blocks)
    await delete_searching(context, chat_id, searching.message_id)
    chunk = ""
    for line in text.split("\n"):
        if len(chunk) + len(line) + 1 > 3800:
            await update.message.reply_text(chunk, parse_mode="Markdown")
            chunk = line + "\n"
        else:
            chunk = chunk + line + "\n"
    if chunk.strip():
        await update.message.reply_text(chunk, parse_mode="Markdown")


async def handle_users_shared(update, context):
    user_id = update.message.from_user.id
    track_user(user_id)
    chat_id = update.message.chat_id
    if not await is_member(user_id, context):
        await send_join_message(update, context)
        return
    await delete_join_message(context, chat_id)
    if update.message.users_shared:
        for user in update.message.users_shared.users:
            await update.message.reply_text("*User ID:* `" + str(user.user_id) + "`", parse_mode="Markdown")


async def handle_chat_shared(update, context):
    user_id = update.message.from_user.id
    track_user(user_id)
    chat_id = update.message.chat_id
    if not await is_member(user_id, context):
        await send_join_message(update, context)
        return
    await delete_join_message(context, chat_id)
    if update.message.chat_shared:
        await update.message.reply_text("*Chat ID:* `" + str(update.message.chat_shared.chat_id) + "`", parse_mode="Markdown")


async def fetch_tg_number(user_id_str, update):
    try:
        tg_url = TG_TO_NUM_API.format(user_id=user_id_str)
        tg_res = await asyncio.to_thread(requests.get, tg_url, timeout=20)
        tg_data = tg_res.json()
        response = tg_data.get("response", {})
             response = tg_data.get("response", {})
        success = response.get("parameters", {}).get("success", False)
        results = response.get("data", [])
        if not success or not results:
            return
        blocks = ["*Linked Phone Number*\n"]
        i = 0
        for entry in results:
            i = i + 1
            country_code = str(entry.get("country_code") or "")
            mobile = str(entry.get("mobile_number") or "N/A")
            block = (
                "\n*Record " + str(i) + "*\n"
                "*Telegram ID:* `" + str(entry.get("tg_id") or "N/A") + "`\n"
                "*Country:* `" + str(entry.get("country") or "N/A") + "`\n"
                "*Country Code:* `" + str(country_code) + "`\n"
                "*Mobile Number:* `" + country_code + mobile + "`"
            )
            blocks.append(block)
        tg_text = "\n".join(blocks)
        await update.message.reply_text(tg_text, parse_mode="Markdown")
    except Exception as e:
        print("TG Number lookup error:", str(e))


async def lookup(update, context):
    user_id = update.message.from_user.id
    track_user(user_id)
    chat_id = update.message.chat_id
    if not await is_member(user_id, context):
        await send_join_message(update, context)
        return
    await delete_join_message(context, chat_id)
    user_input = update.message.text.strip()
    is_username = user_input.startswith("@") and len(user_input) > 1
    digits_only = user_input.lstrip("+")
    is_number = digits_only.isdigit() and len(digits_only) >= 7
    if not is_username and not is_number:
        return
    searching = await update.message.reply_text("🔍 Searching...")
    try:
        url = BASE_URL + user_input
        res = await asyncio.to_thread(requests.get, url, timeout=15)
        data = res.json()
    except Exception as e:
        await delete_searching(context, chat_id, searching.message_id)
        await update.message.reply_text("❌ *Error connecting to API.*\n`" + str(e) + "`", parse_mode="Markdown")
        return
    if "result" in data:
        result = data["result"]
    else:
        result = data
    not_found = False
    text = ""
    extracted_id = None
    if isinstance(result, dict):
        if not result.get("success", True):
            not_found = True
        else:
            fields = {}
            for k in result:
                v = result[k]
                if k != "success" and k != "msg":
                    fields[k] = v
            if not fields:
                not_found = True
            else:
                for id_key in ["id", "user_id", "tg_id", "telegram_id", "userid"]:
                    if id_key in fields and str(fields[id_key]).isdigit():
                        extracted_id = str(fields[id_key])
                        break
                lines = ["*Result:*\n"]
                for key in fields:
                    value = fields[key]
                    label = key.replace("_", " ").title()
                    lines.append("*" + label + ":* `" + str(value) + "`")
                text = "\n".join(lines)
    elif not result:
        not_found = True
    else:
        text = "*Result:*\n`" + str(result) + "`"
    if not_found:
        text = "*Data Not Found!*\n\nNo information found for this username."
    await delete_searching(context, chat_id, searching.message_id)
    await update.message.reply_text(text, parse_mode="Markdown")
    if is_number:
        await fetch_tg_number(digits_only, update)
    elif is_username and extracted_id:
        await fetch_tg_number(extracted_id, update)


if __name__ == "__main__":
    load_users()
    keep_alive()
    print("Flask Server Started!")
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("num", num_lookup))
    app.add_handler(CommandHandler("aadhar", aadhar_lookup))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CommandHandler("back", back_command))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("report", report_command))
    app.add_handler(CommandHandler("reply", reply_command))
    app.add_handler(CallbackQueryHandler(check_joined_callback, pattern="check_joined"))
    app.add_handler(MessageHandler(filters.StatusUpdate.USERS_SHARED, handle_users_shared))
    app.add_handler(MessageHandler(filters.StatusUpdate.CHAT_SHARED, handle_chat_shared))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lookup))
    print("Bot is Online!")
    app.run_polling()
