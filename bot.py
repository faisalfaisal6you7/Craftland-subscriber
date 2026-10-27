import os
import json
import time
import logging
import asyncio
from datetime import datetime, date
from main import start_bot_subscription
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ContextTypes, filters
)

# ---------- CONFIGURATION ----------
BOT_TOKEN = os.getenv("BOT_TOKEN", "8648143907:AAFSTH0b04O1Fa3rbYK_1EOL5n6E63v9LA0").strip()
OWNER_ID = int(os.getenv("OWNER_ID", "7414148694"))
INITIAL_ADMINS = [8625129539]

CHANNEL_1 = "https://t.me/faisalfreeapi"
CHANNEL_2 = "https://t.me/dailyfreelike"

# Data Files
USERS_FILE = "users_db.json"
REDEEM_FILE = "redeem_db.json"
ADMINS_FILE = "admins_db.json"
MAPS_FILE = "allowed_maps.json"
UIDS_FILE = "allowed_uids.json"
LOGS_FILE = "bot_logs.txt"

# Region Details Data
REGION_DETAILS = {
    "BD": ("BANGLADESH", "🇧🇩"),
    "IND": ("INDIA", "🇮🇳"),
    "ID": ("INDONESIA", "🇮🇩"),
    "BR": ("BRAZIL", "🇧🇷"),
    "ME": ("MIDDLE EAST", "🇦🇪"),
    "VN": ("VIETNAM", "🇻🇳"),
    "TH": ("THAILAND", "🇹🇭"),
    "CIS": ("RUSSIA / CIS", "🇷🇺"),
    "PK": ("PAKISTAN", "🇵🇰"),
    "SG": ("SINGAPORE", "🇸🇬"),
    "SAC": ("SOUTH AMERICA", "🇲🇽"),
    "TW": ("TAIWAN", "🇹🇼")
}

# Concurrency & Thread Locks
WORKER_SEMAPHORE = asyncio.Semaphore(5)
DB_LOCK = asyncio.Lock()

# ---------- SYSTEM LOGGING FUNCTION ----------
def log_activity(user_id: int, username: str, action: str):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{now}] User ID: {user_id} (@{username}) -> {action}\n"
    try:
        with open(LOGS_FILE, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception as e:
        logging.error(f"Log writing failed: {e}")

# ---------- DATABASE HANDLERS ----------
def load_data(file_path, default):
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Error loading {file_path}: {e}")
            return default
    return default

def _sync_save_data(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

async def save_data_async(file_path, data):
    async with DB_LOCK:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _sync_save_data, file_path, data)

users_db = load_data(USERS_FILE, {})
redeem_db = load_data(REDEEM_FILE, {})
admins_list = load_data(ADMINS_FILE, INITIAL_ADMINS)
allowed_maps = load_data(MAPS_FILE, [])
allowed_uids = load_data(UIDS_FILE, [])

def is_owner(user_id: int) -> bool:
    return int(user_id) == OWNER_ID

def is_admin(user_id: int) -> bool:
    return int(user_id) in admins_list or int(user_id) == OWNER_ID

def get_user_data(user_id, referrer_id=None):
    str_id = str(user_id)
    int_id = int(user_id)
    admin_flag = is_admin(int_id)
    
    if str_id not in users_db:
        users_db[str_id] = {
            "credits": 0,
            "is_vip": admin_flag,
            "is_banned": False,
            "state": None,
            "selected_region": "BD",
            "target_uid": None,
            "last_sub_time": 0,
            "referred_by": referrer_id,
            "referral_count": 0,
            "subs_today": 0,
            "last_sub_date": str(datetime.now().date())
        }
        
        if referrer_id and str(referrer_id) in users_db and str(referrer_id) != str_id:
            users_db[str(referrer_id)]["credits"] += 3
            users_db[str(referrer_id)]["referral_count"] += 1
            log_activity(referrer_id, "System", f"Referral bonus given for referring {user_id}")
            
        asyncio.create_task(save_data_async(USERS_FILE, users_db))

    if admin_flag and not users_db[str_id].get("is_vip"):
        users_db[str_id]["is_vip"] = True
        asyncio.create_task(save_data_async(USERS_FILE, users_db))

    today_str = str(datetime.now().date())
    if users_db[str_id].get("last_sub_date") != today_str:
        users_db[str_id]["subs_today"] = 0
        users_db[str_id]["last_sub_date"] = today_str
        asyncio.create_task(save_data_async(USERS_FILE, users_db))

    return users_db[str_id]

# ---------- REGION KEYBOARD HELPER ----------
def get_region_keyboard(prefix="region"):
    keyboard = []
    row = []
    for code, (name, flag) in REGION_DETAILS.items():
        btn_text = f"{flag} {name}"
        row.append(InlineKeyboardButton(btn_text, callback_data=f"{prefix}_{code}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)

# ---------- FORCE JOIN CHECKER ----------
async def check_force_join(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if is_admin(user_id):
        return True
    try:
        member1 = await context.bot.get_chat_member(chat_id=f"@{CHANNEL_1.lstrip('@')}", user_id=user_id)
        member2 = await context.bot.get_chat_member(chat_id=f"@{CHANNEL_2.lstrip('@')}", user_id=user_id)
        
        valid_status = ["creator", "administrator", "member"]
        if member1.status in valid_status and member2.status in valid_status:
            return True
    except Exception as e:
        logging.warning(f"Force join check failed for {user_id}: {e}")
    return False

async def send_join_request(update: Update):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Channel 1", url=f"https://t.me/{CHANNEL_1.lstrip('@')}")],
        [InlineKeyboardButton("💬 Channel 2", url=f"https://t.me/{CHANNEL_2.lstrip('@')}")]
    ])
    await update.message.reply_text(
        "⚠️ **বট ব্যবহার করতে আপনাকে আমাদের চ্যানেলে জয়েন করতে হবে!**\n\n"
        "নিচের দুটি চ্যানেলে জয়েন হয়ে ডায়ালগ বক্সে `/start` লিখে পাঠান:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

# ---------- MAIN MENU ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "NoUsername"
    
    referrer_id = None
    if context.args:
        try:
            referrer_id = int(context.args[0])
        except ValueError:
            pass

    log_activity(user_id, username, "Used /start command")

    u_data = get_user_data(user_id, referrer_id)
    if u_data.get("is_banned"):
        await update.message.reply_text("❌ আপনি এই বট থেকে ব্যান হয়ে আছেন!")
        return

    if not await check_force_join(user_id, context):
        await send_join_request(update)
        return

    await send_main_menu(update, user_id)

async def send_main_menu(update: Update, user_id: int):
    keyboard = [
        ["🚀 Send Subscriber", "💰 My Balance"],
        ["👤 My Profile", "🌐 Language / Region"],
        ["🔗 Refer & Earn", "🎟️ Redeem Code"],
        ["👨‍💻 Admin Info", "🔄 Refresh Chat"]
    ]
    
    if is_admin(user_id):
        admin_row = ["👑 Admin Commands"]
        if is_owner(user_id):
            admin_row.append("📜 Logs")
        keyboard.append(admin_row)

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "👋 **AGS ULTIMATE SUBSCRIBER BOT-এ স্বাগতম!**\n\n"
        "নিচের মেনু থেকে আপনার কাঙ্ক্ষিত অপশন সিলেক্ট করুন:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# ---------- WORKER PROCESSOR WITH LIVE PROGRESS ----------
async def process_subscriber_task(context, chat_id, region, target_uid, map_code, total_subs):
    status_msg = await context.bot.send_message(
        chat_id=chat_id, 
        text="⏳ **Hold Zone!** বট বর্তমানে প্রসেস করছে। লাইনে অপেক্ষা করুন...", 
        parse_mode="Markdown"
    )
    
    async with WORKER_SEMAPHORE:
        country_name, flag = REGION_DETAILS.get(region, ("BANGLADESH", "🇧🇩"))
        await status_msg.edit_text(
            f"⚙️ **কাজ শুরু হয়েছে!**\n"
            f"🌍 Region: {flag} `{country_name}`\n"
            f"👤 UID: `{target_uid}`\n"
            f"🎯 Target Subs: `{total_subs}`\n"
            f"📊 Progress: `0/{total_subs} (0%)`",
            parse_mode="Markdown"
        )
        
        sent_count = 0
        step = max(5, total_subs // 5)
        
        while sent_count < total_subs:
            batch = min(step, total_subs - sent_count)
            added = await asyncio.to_thread(start_bot_subscription, map_code, batch)
            
            if added is None or added == 0:
                break
                
            sent_count += added
            percent = int((sent_count / total_subs) * 100)
            
            try:
                await status_msg.edit_text(
                    f"🚀 **সাবস্ক্রাইবার পাঠানো হচ্ছে...**\n\n"
                    f"🌍 **Region:** {flag} `{region}` | 👤 **UID:** `{target_uid}`\n"
                    f"📊 **Progress:** `{sent_count}/{total_subs}` (`{percent}%`)\n"
                    f"🎯 **Target:** `{total_subs}`",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
            
            await asyncio.sleep(2)

        await status_msg.edit_text(
            f"🎉 **কাজ সফলভাবে সম্পন্ন হয়েছে!**\n\n"
            f"🌍 **Region:** {flag} `{country_name}`\n"
            f"👤 **UID:** `{target_uid}`\n"
            f"🗺️ **Map:** `{map_code}`\n"
            f"✅ **মোট পাঠানো হয়েছে:** `{sent_count}/{total_subs}`",
            parse_mode="Markdown"
        )

# ---------- CALLBACK QUERY HANDLER ----------
async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_data = get_user_data(user_id)
    data = query.data

    if data.startswith("lang_"):
        region_code = data.split("_")[1]
        country_name, flag = REGION_DETAILS.get(region_code, ("Unknown", "🏳️"))
        user_data["selected_region"] = region_code
        await save_data_async(USERS_FILE, users_db)
        
        await query.edit_message_text(
            f"✅ **Language / Region Updated!**\n\nSelected: {flag} **{country_name} ({region_code})**",
            parse_mode="Markdown"
        )

    elif data.startswith("subregion_"):
        region_code = data.split("_")[1]
        country_name, flag = REGION_DETAILS.get(region_code, ("Unknown", "🏳️"))
        user_data["temp_region"] = region_code
        user_data["state"] = "AWAITING_GAME_UID"
        await save_data_async(USERS_FILE, users_db)

        await query.edit_message_text(
            f"Selected Region: {flag} **{country_name} ({region_code})**\n\n"
            f"👤 **Step 2:** এবার আপনার **Game UID** দিন:\nExample: `5527680566`",
            parse_mode="Markdown"
        )

# ---------- ADMIN COMMANDS ----------
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    msg = (
        "👑 **ADMIN COMMAND LIST** 👑\n\n"
        "• `/send_subscribers <MAP> <COUNT>` - কাস্টম সাবস্ক্রাইবার পাঠান\n"
        "• `/attention_all <MSG>` - ব্রডকাস্ট মেসেজ পাঠান\n"
        "• `/add_admin <USER_ID>` - এডমিন যুক্ত করুন\n"
        "• `/remove_admin <USER_ID>` - এডমিন রিমুভ করুন\n"
        "• `/add_vip <USER_ID>` - VIP এক্সেস দিন\n"
        "• `/remove_vip <USER_ID>` - VIP রিমুভ করুন\n"
        "• `/add_map <MAP_CODE>` - মেপ যুক্ত করুন\n"
        "• `/remove_map <MAP_CODE>` - মেপ মুছুন\n"
        "• `/add_uid <UID>` - ইউআইডি যুক্ত করুন\n"
        "• `/remove_uid <UID>` - ইউআইডি মুছুন\n"
        "• `/ban_user <USER_ID>` - ইউজার ব্যান করুন\n"
        "• `/unban_user <USER_ID>` - আনব্যান করুন\n"
        "• `/add_redeem <CODE> <CREDIT> <LIMIT> [YYYY-MM-DD]` - মেয়াদসহ রিডিম কোড বানান\n"
        "• `/show_redeems` - সব কোড দেখুন\n"
        "• `/remove_redeem <CODE>` - কোড মুছুন\n"
        "• `/logs` - সিস্টেম লগ দেখুন"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def send_subscribers_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u_data = get_user_data(user_id)

    if not (is_admin(user_id) or u_data.get("is_vip")):
        await update.message.reply_text("❌ এই কমান্ডটি শুধু VIP এবং Admin-দের জন্য প্রযোজ্য!")
        return

    if len(context.args) < 2:
        await update.message.reply_text("⚠️ **ব্যবহার:** `/send_subscribers <MAP_CODE> <COUNT>`", parse_mode="Markdown")
        return

    map_code = context.args[0].replace("#", "")
    try:
        sub_count = int(context.args[1])
        if sub_count <= 0: raise ValueError
    except ValueError:
        await update.message.reply_text("❌ সাবস্ক্রাইবার সংখ্যা সঠিক হতে হবে!")
        return

    log_activity(user_id, update.effective_user.username or "NoUsername", f"Admin/VIP Send Subs: Map={map_code}, Count={sub_count}")
    await update.message.reply_text(f"✅ **অনুরোধ গ্রহণ করা হয়েছে!**\nMap: `{map_code}`\nCount: `{sub_count}`", parse_mode="Markdown")
    asyncio.create_task(process_subscriber_task(context, update.effective_chat.id, "BD", "N/A", map_code, sub_count))

async def attention_all_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text("⚠️ **ব্যবহার:** `/attention_all <আপনার বার্তা>`", parse_mode="Markdown")
        return

    msg_text = " ".join(context.args)
    broadcast_msg = f"📢 **BROADCAST ANNOUNCEMENT** 📢\n\n{msg_text}"
    
    count = 0
    await update.message.reply_text("🚀 ব্রডকাস্ট মেসেজ পাঠানো শুরু হয়েছে...")
    for uid in list(users_db.keys()):
        try:
            await context.bot.send_message(chat_id=int(uid), text=broadcast_msg, parse_mode="Markdown")
            count += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass

    await update.message.reply_text(f"✅ **ব্রডকাস্ট সম্পন্ন!**\nমোট `{count}` জন ইউজারের কাছে পাঠানো হয়েছে।", parse_mode="Markdown")

async def add_admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text("⚠️ **ব্যবহার:** `/add_admin <USER_ID>`", parse_mode="Markdown")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ইউজার আইডি সংখ্যা হতে হবে!")
        return

    if target_id not in admins_list:
        admins_list.append(target_id)
        await save_data_async(ADMINS_FILE, admins_list)
        u_data = get_user_data(target_id)
        u_data["is_vip"] = True
        await save_data_async(USERS_FILE, users_db)
        await update.message.reply_text(f"✅ User ID `{target_id}` কে Admin করা হয়েছে।", parse_mode="Markdown")
    else:
        await update.message.reply_text("⚠️ ইনি ইতিমধ্যে এডমিন আছেন!")

async def remove_admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text("⚠️ **ব্যবহার:** `/remove_admin <USER_ID>`", parse_mode="Markdown")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ইউজার আইডি সংখ্যা হতে হবে!")
        return

    if target_id in admins_list:
        admins_list.remove(target_id)
        await save_data_async(ADMINS_FILE, admins_list)
        await update.message.reply_text(f"✅ User ID `{target_id}` কে Admin তালিকা থেকে রিমুভ করা হয়েছে।", parse_mode="Markdown")
    else:
        await update.message.reply_text("⚠️ ইউজারটি এডমিন তালিকায় নেই!")

async def add_vip_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text("⚠️ **ব্যবহার:** `/add_vip <USER_ID>`", parse_mode="Markdown")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ইউজার আইডি সংখ্যা হতে হবে!")
        return

    u_data = get_user_data(target_id)
    u_data["is_vip"] = True
    await save_data_async(USERS_FILE, users_db)
    await update.message.reply_text(f"✅ User ID `{target_id}` কে VIP দেওয়া হয়েছে।", parse_mode="Markdown")

async def remove_vip_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text("⚠️ **ব্যবহার:** `/remove_vip <USER_ID>`", parse_mode="Markdown")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ইউজার আইডি সংখ্যা হতে হবে!")
        return

    u_data = get_user_data(target_id)
    u_data["is_vip"] = False
    await save_data_async(USERS_FILE, users_db)
    await update.message.reply_text(f"✅ User ID `{target_id}` এর VIP সুবিধা রিমুভ করা হয়েছে।", parse_mode="Markdown")

async def add_map_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text("⚠️ **ব্যবহার:** `/add_map <MAP_CODE>`", parse_mode="Markdown")
        return

    map_code = context.args[0].replace("#", "").strip()
    if map_code not in allowed_maps:
        allowed_maps.append(map_code)
        await save_data_async(MAPS_FILE, allowed_maps)
        await update.message.reply_text(f"✅ Map Code `{map_code}` যুক্ত করা হয়েছে।", parse_mode="Markdown")
    else:
        await update.message.reply_text("⚠️ Map Code টি আগেই যুক্ত করা আছে!")

async def remove_map_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text("⚠️ **ব্যবহার:** `/remove_map <MAP_CODE>`", parse_mode="Markdown")
        return

    map_code = context.args[0].replace("#", "").strip()
    if map_code in allowed_maps:
        allowed_maps.remove(map_code)
        await save_data_async(MAPS_FILE, allowed_maps)
        await update.message.reply_text(f"✅ Map Code `{map_code}` রিমুভ করা হয়েছে।", parse_mode="Markdown")
    else:
        await update.message.reply_text("⚠️ Map Code টি তালিকায় নেই!")

async def add_uid_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text("⚠️ **ব্যবহার:** `/add_uid <UID>`", parse_mode="Markdown")
        return

    uid = context.args[0].strip()
    if uid not in allowed_uids:
        allowed_uids.append(uid)
        await save_data_async(UIDS_FILE, allowed_uids)
        await update.message.reply_text(f"✅ UID `{uid}` যুক্ত করা হয়েছে।", parse_mode="Markdown")
    else:
        await update.message.reply_text("⚠️ UID টি আগেই যুক্ত করা আছে!")

async def remove_uid_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text("⚠️ **ব্যবহার:** `/remove_uid <UID>`", parse_mode="Markdown")
        return

    uid = context.args[0].strip()
    if uid in allowed_uids:
        allowed_uids.remove(uid)
        await save_data_async(UIDS_FILE, allowed_uids)
        await update.message.reply_text(f"✅ UID `{uid}` রিমুভ করা হয়েছে।", parse_mode="Markdown")
    else:
        await update.message.reply_text("⚠️ UID টি তালিকায় নেই!")

async def ban_user_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text("⚠️ **ব্যবহার:** `/ban_user <USER_ID>`", parse_mode="Markdown")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ইউজার আইডি সংখ্যা হতে হবে!")
        return

    u_data = get_user_data(target_id)
    u_data["is_banned"] = True
    await save_data_async(USERS_FILE, users_db)
    await update.message.reply_text(f"🚫 User ID `{target_id}` কে ব্যান করা হয়েছে।", parse_mode="Markdown")

async def unban_user_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text("⚠️ **ব্যবহার:** `/unban_user <USER_ID>`", parse_mode="Markdown")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ইউজার আইডি সংখ্যা হতে হবে!")
        return

    u_data = get_user_data(target_id)
    u_data["is_banned"] = False
    await save_data_async(USERS_FILE, users_db)
    await update.message.reply_text(f"✅ User ID `{target_id}` কে আনব্যান করা হয়েছে।", parse_mode="Markdown")

async def add_redeem_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if len(context.args) not in (3, 4):
        await update.message.reply_text(
            "⚠️ **ব্যবহার:** `/add_redeem <CODE> <CREDIT> <LIMIT> [YYYY-MM-DD]`\n\n"
            "উদাহরণ: `/add_redeem RAHIM100 10 50 2026-12-31`\n"
            "মেয়াদ না দিতে চাইলে: `/add_redeem RAHIM100 10 50`\n"
            "তারিখটি শেষ দিনসহ কার্যকর থাকবে।",
            parse_mode="Markdown"
        )
        return

    code = context.args[0].strip().upper()
    try:
        credit = int(context.args[1])
        limit = int(context.args[2])
        if credit <= 0 or limit <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ ক্রেডিট এবং লিমিট ১ বা তার বেশি পূর্ণসংখ্যা হতে হবে!")
        return

    expires_at = None
    if len(context.args) == 4:
        try:
            expires_at = date.fromisoformat(context.args[3]).isoformat()
        except ValueError:
            await update.message.reply_text(
                "❌ তারিখের ফরম্যাট ভুল। `YYYY-MM-DD` ব্যবহার করুন।\n"
                "উদাহরণ: `2026-12-31`",
                parse_mode="Markdown"
            )
            return
        if date.fromisoformat(expires_at) < date.today():
            await update.message.reply_text("❌ অতীতের তারিখ দিয়ে Redeem Code তৈরি করা যাবে না।")
            return

    # Prevent accidentally replacing an existing code and resetting its usage count.
    if code in redeem_db:
        await update.message.reply_text(
            f"⚠️ `{code}` কোডটি আগে থেকেই আছে। আগের ব্যবহারকারীদের রেকর্ড রিসেট না করতে নতুন নাম ব্যবহার করুন।",
            parse_mode="Markdown"
        )
        return

    redeem_db[code] = {"credit": credit, "limit": limit, "used_by": []}
    if expires_at:
        redeem_db[code]["expires_at"] = expires_at
    await save_data_async(REDEEM_FILE, redeem_db)
    expiry_text = expires_at if expires_at else "কোনো মেয়াদ নেই"
    await update.message.reply_text(
        f"✅ **Redeem Code তৈরি হয়েছে!**\nCode: `{code}`\nCredit: `{credit}`\n"
        f"Limit: `{limit}`\nমেয়াদ শেষ: `{expiry_text}`",
        parse_mode="Markdown"
    )

async def show_redeems_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not redeem_db:
        await update.message.reply_text("📜 কোনো রিডিম কোড নেই।")
        return

    today = date.today()
    msg = "🎟️ **সব রিডিম কোডের তালিকা:**\n\n"
    for code, info in redeem_db.items():
        used = len(info.get("used_by", []))
        limit = info.get("limit", 0)
        expires_at = info.get("expires_at")
        if expires_at:
            try:
                expired = date.fromisoformat(expires_at) < today
                expiry_status = f"{expires_at} {'(মেয়াদ শেষ)' if expired else ''}"
            except ValueError:
                expiry_status = f"{expires_at} (তারিখ ভুল)"
        else:
            expiry_status = "মেয়াদ নেই"
        msg += (f"• Code: `{code}` | Credit: `{info.get('credit', 0)}` | "
                f"Used: `{used}/{limit}` | Expiry: `{expiry_status}`\n")
    await update.message.reply_text(msg, parse_mode="Markdown")

async def remove_redeem_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text("⚠️ **ব্যবহার:** `/remove_redeem <CODE>`", parse_mode="Markdown")
        return

    code = context.args[0].strip().upper()
    if code in redeem_db:
        del redeem_db[code]
        await save_data_async(REDEEM_FILE, redeem_db)
        await update.message.reply_text(f"✅ Redeem Code `{code}` মুছে ফেলা হয়েছে।", parse_mode="Markdown")
    else:
        await update.message.reply_text("⚠️ রিডিম কোডটি পাওয়া যায়নি!")

async def logs_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id): return
    if not os.path.exists(LOGS_FILE):
        await update.message.reply_text("📜 কোনো লগ এখনো তৈরি হয়নি।")
        return

    with open(LOGS_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    last_logs = "".join(lines[-30:])
    await update.message.reply_text(f"🔍 **SYSTEM AUDIT LOGS:**\n\n```\n{last_logs}\n```", parse_mode="Markdown")

# ---------- MESSAGE HANDLER ----------
async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "NoUsername"
    user_data = get_user_data(user_id)

    if user_data.get("is_banned"):
        await update.message.reply_text("❌ আপনি ব্যান হয়ে আছেন!")
        return

    if not await check_force_join(user_id, context):
        await send_join_request(update)
        return

    text = update.message.text

    if text == "👑 Admin Commands" and is_admin(user_id):
        await help_cmd(update, context)
        return

    if text == "📜 Logs" and is_owner(user_id):
        await logs_cmd(update, context)
        return

    if text in ["🔄 Refresh Chat", "▶️ Start Again"]:
        user_data["state"] = None
        await save_data_async(USERS_FILE, users_db)
        await send_main_menu(update, user_id)
        return

    elif text == "🌐 Language / Region":
        await update.message.reply_text(
            "🌐 **Choose your default Region / Language:**",
            reply_markup=get_region_keyboard(prefix="lang"),
            parse_mode="Markdown"
        )

    elif text == "💰 My Balance":
        vip_status = "👑 VIP User (Unlimited)" if user_data.get("is_vip") else f"{user_data['credits']} Credit"
        await update.message.reply_text(f"💳 **ব্যালেন্স স্ট্যাটাস:** {vip_status}", parse_mode="Markdown")

    elif text == "👤 My Profile":
        if is_owner(user_id):
            role_title = "👑 Owner (VIP)"
        elif is_admin(user_id):
            role_title = "🛡️ Admin (VIP)"
        elif user_data.get("is_vip"):
            role_title = "👑 VIP User"
        else:
            role_title = "👤 Normal User"

        c_code = user_data.get("selected_region", "BD")
        country_name, flag = REGION_DETAILS.get(c_code, ("BANGLADESH", "🇧🇩"))

        msg = (
            f"👤 **USER PROFILE STATUS**\n\n"
            f"🆔 **User ID:** `{user_id}`\n"
            f"⭐ **Account Role:** {role_title}\n"
            f"🌍 **Selected Region:** {flag} {country_name} (`{c_code}`)\n"
            f"💳 **Available Credits:** `{user_data['credits']}`\n"
            f"🚀 **Subs Taken Today:** `{user_data.get('subs_today', 0)}`\n"
            f"👥 **Total Referrals:** `{user_data.get('referral_count', 0)}`"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

    elif text == "🔗 Refer & Earn":
        bot_username = (await context.bot.get_me()).username
        ref_link = f"https://t.me/{bot_username}?start={user_id}"
        msg = (
            f"🎉 **রেফার করে ক্রেডিট আয় করুন!**\n\n"
            f"আপনার রেফারেল লিংকটি বন্ধুদের পাঠালে তারা জয়েন করলে আপনি পাবেন **৩ ক্রেডিট** পার রেফার!\n\n"
            f"🔗 **আপনার লিংক:**\n`{ref_link}`"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

    elif text == "👨‍💻 Admin Info":
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("💬 Contact Admin", url="https://t.me/ags_owner_atif")]])
        await update.message.reply_text("👤 **যোগাযোগ:**", reply_markup=keyboard)

    elif text == "🎟️ Redeem Code":
        user_data["state"] = "AWAITING_REDEEM_CODE"
        await save_data_async(USERS_FILE, users_db)
        await update.message.reply_text("🎟️ **আপনার রিডিম কোডটি পাঠান:**")

    elif text == "🚀 Send Subscriber":
        if not user_data.get("is_vip"):
            current_time = time.time()
            last_time = user_data.get("last_sub_time", 0)
            cooldown = 180

            if current_time - last_time < cooldown:
                remaining = int(cooldown - (current_time - last_time))
                await update.message.reply_text(f"⏳ **অপেক্ষা করুন!**\n\nআবার সাবস্ক্রাইবার নিতে **{remaining} সেকেন্ড** পর চেষ্টা করুন।", parse_mode="Markdown")
                return

            if user_data["credits"] < 1:
                await update.message.reply_text("❌ আপনার পর্যাপ্ত ক্রেডিট নেই!")
                return

        # Step 1: Show Region Choice
        await update.message.reply_text(
            "🌍 **Step 1:** সাবস্ক্রাইবার পাঠানোর জন্য **Region** সিলেক্ট করুন:",
            reply_markup=get_region_keyboard(prefix="subregion"),
            parse_mode="Markdown"
        )

    else:
        state = user_data.get("state")

        if state == "AWAITING_REDEEM_CODE":
            code = text.strip().upper()
            user_data["state"] = None
            await save_data_async(USERS_FILE, users_db)

            if code not in redeem_db:
                await update.message.reply_text("❌ ইনভ্যালিড রিডিম কোড!")
                return
            c_info = redeem_db[code]
            expires_at = c_info.get("expires_at")
            if expires_at:
                try:
                    if date.today() > date.fromisoformat(expires_at):
                        await update.message.reply_text("⌛ এই Redeem Code-এর মেয়াদ শেষ হয়ে গেছে!")
                        return
                except ValueError:
                    logging.error("Invalid expires_at date for redeem code %s", code)
                    await update.message.reply_text("❌ এই Redeem Code-এর মেয়াদের তথ্য ভুল। অ্যাডমিনের সঙ্গে যোগাযোগ করুন।")
                    return
            if user_id in c_info.get("used_by", []):
                await update.message.reply_text("⚠️ কোডটি আগে ব্যবহার করেছেন!")
                return
            if len(c_info.get("used_by", [])) >= c_info.get("limit", 0):
                await update.message.reply_text("❌ কোডের সীমা শেষ!")
                return

            user_data["credits"] += c_info["credit"]
            c_info.setdefault("used_by", []).append(user_id)
            await save_data_async(USERS_FILE, users_db)
            await save_data_async(REDEEM_FILE, redeem_db)
            log_activity(user_id, username, f"Redeemed Code {code} (+{c_info['credit']} Credits)")
            await update.message.reply_text(f"🎉 **{c_info['credit']} Credit** যুক্ত হয়েছে!")

        elif state == "AWAITING_GAME_UID":
            user_data["target_uid"] = text.strip()
            user_data["state"] = "AWAITING_MAP_CODE"
            await save_data_async(USERS_FILE, users_db)
            await update.message.reply_text("🗺️ **Step 3:** এবার আপনার **Map Code** দিন:\nExample: `#GSO82DNSKKO29NF`", parse_mode="Markdown")

        elif state == "AWAITING_MAP_CODE":
            map_code = text.strip().replace("#", "")
            target_uid = user_data.get("target_uid", "N/A")
            region = user_data.get("temp_region", user_data.get("selected_region", "BD"))
            
            if user_data.get("is_vip"):
                sub_count = 100
            else:
                used_credits = min(user_data["credits"], 2)
                sub_count = used_credits * 50
                user_data["credits"] -= used_credits

            user_data["subs_today"] = user_data.get("subs_today", 0) + sub_count
            user_data["last_sub_time"] = time.time()
            user_data["state"] = None
            await save_data_async(USERS_FILE, users_db)

            log_activity(user_id, username, f"Sent Subs Request: Region={region}, UID={target_uid}, Map={map_code}, Subs={sub_count}")
            asyncio.create_task(process_subscriber_task(context, update.effective_chat.id, region, target_uid, map_code, sub_count))

# ---------- BOT INITIALIZATION & RUNNER ----------
def build_application():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("logs", logs_cmd))
    app.add_handler(CommandHandler("send_subscribers", send_subscribers_cmd))
    app.add_handler(CommandHandler("attention_all", attention_all_cmd))
    app.add_handler(CommandHandler("add_admin", add_admin_cmd))
    app.add_handler(CommandHandler("remove_admin", remove_admin_cmd))
    app.add_handler(CommandHandler("add_vip", add_vip_cmd))
    app.add_handler(CommandHandler("remove_vip", remove_vip_cmd))
    app.add_handler(CommandHandler("add_map", add_map_cmd))
    app.add_handler(CommandHandler("remove_map", remove_map_cmd))
    app.add_handler(CommandHandler("add_uid", add_uid_cmd))
    app.add_handler(CommandHandler("remove_uid", remove_uid_cmd))
    app.add_handler(CommandHandler("ban_user", ban_user_cmd))
    app.add_handler(CommandHandler("unban_user", unban_user_cmd))
    app.add_handler(CommandHandler("add_redeem", add_redeem_cmd))
    app.add_handler(CommandHandler("show_redeems", show_redeems_cmd))
    app.add_handler(CommandHandler("remove_redeem", remove_redeem_cmd))

    # Callbacks
    app.add_handler(CallbackQueryHandler(handle_callback_query))

    # General Messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_messages))

    return app

if __name__ == "__main__":
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN environment variable is missing. Set your Telegram bot token before starting the bot.")
    app = build_application()
    print("⚡ OPTIMIZED BOT WITH REGIONS IS RUNNING!")
    app.run_polling(drop_pending_updates=True)