#!/usr/bin/env python3
import os, sys, logging, asyncio, time
from pathlib import Path
from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode
import yt_dlp

# CONFIG
BOT_TOKEN = "8367293218:AAF7VsjU0jkzoU8DLd1kX75Kr73hXrKiq94"
ADMIN_ID = 8175884349
PORT = int(os.getenv('PORT', '10000'))
DOWNLOADS_DIR = 'downloads'
Path(DOWNLOADS_DIR).mkdir(exist_ok=True)

# LOGGING
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger('httpx').setLevel(logging.WARNING)

# STATE
users = {ADMIN_ID}
stats = {'total': 0}

# WEB SERVER
async def health(request):
    return web.Response(text="OK")

async def run_web():
    app = web.Application()
    app.router.add_get('/', health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    logger.info(f"✅ Web on {PORT}")
    while True:
        await asyncio.sleep(3600)

# DOWNLOAD
async def download(url: str, quality: str = "720") -> str:
    try:
        opts = {
            'quiet': True,
            'no_warnings': True,
            'outtmpl': f'{DOWNLOADS_DIR}/{int(time.time())}.%(ext)s',
            'format': f'best[height<={quality}]/best' if quality != "audio" else 'bestaudio',
            'merge_output_format': 'mp4',
            'retries': 20,
            'socket_timeout': 30,
        }
        
        if quality == "audio":
            opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}]
        
        loop = asyncio.get_event_loop()
        
        def dl():
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                if quality == "audio":
                    filename = filename.rsplit('.', 1)[0] + '.mp3'
                return filename
        
        filepath = await loop.run_in_executor(None, dl)
        
        if filepath and os.path.exists(filepath):
            return filepath
        return None
    except Exception as e:
        logger.error(f"Download error: {e}")
        return None

# HANDLERS
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in users:
        await update.message.reply_text(f"⚠️ Not authorized\nID: {user.id}\nContact admin")
        try:
            await context.bot.send_message(ADMIN_ID, f"New user: {user.full_name} (ID: {user.id})\nAuthorize: /adduser {user.id}")
        except: pass
        return
    await update.message.reply_text(f"👋 Welcome!\n\n🎬 Send video URL from:\n• YouTube\n• Instagram\n• TikTok\n• Twitter\n• Facebook\n\nI'll download it!")

async def adduser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args:
        await update.message.reply_text("Usage: /adduser <id>")
        return
    try:
        new_id = int(context.args[0])
        users.add(new_id)
        await update.message.reply_text(f"✅ Added {new_id}")
        try:
            await context.bot.send_message(new_id, "🎉 Access granted! /start")
        except: pass
    except:
        await update.message.reply_text("❌ Invalid")

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in users: return
    url = update.message.text.strip()
    if not url.startswith('http'): return
    
    msg = await update.message.reply_text("🔍 Processing...")
    
    keyboard = [
        [InlineKeyboardButton("720p", callback_data=f"dl_720_{hash(url) % 9999}")],
        [InlineKeyboardButton("480p", callback_data=f"dl_480_{hash(url) % 9999}")],
        [InlineKeyboardButton("360p", callback_data=f"dl_360_{hash(url) % 9999}")],
        [InlineKeyboardButton("🎵 Audio", callback_data=f"dl_audio_{hash(url) % 9999}")],
    ]
    
    if 'user_data' not in context.bot_data:
        context.bot_data['user_data'] = {}
    context.bot_data['user_data'][update.effective_user.id] = {'url': url}
    
    await msg.edit_text("✅ Select quality:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id not in users: return
    
    quality = query.data.split('_')[1]
    url = context.bot_data.get('user_data', {}).get(query.from_user.id, {}).get('url')
    
    if not url:
        await query.message.edit_text("❌ Expired. Send URL again.")
        return
    
    await query.message.edit_text(f"⬇️ Downloading {quality}...\n\nPlease wait 1-2 minutes...")
    
    filepath = await download(url, quality)
    
    if not filepath:
        await query.message.edit_text("❌ Failed. Try different video/quality.")
        return
    
    size = os.path.getsize(filepath)
    if size > 50 * 1024 * 1024:
        await query.message.edit_text(f"❌ Too large ({size//1024//1024}MB). Try lower quality.")
        os.remove(filepath)
        return
    
    await query.message.edit_text("📤 Uploading...")
    
    is_audio = quality == 'audio'
    with open(filepath, 'rb') as f:
        if is_audio:
            await context.bot.send_audio(query.from_user.id, f, caption="🎵 Audio", read_timeout=60, write_timeout=60)
        else:
            await context.bot.send_video(query.from_user.id, f, caption=f"🎬 {quality}", read_timeout=60, write_timeout=60)
    
    stats['total'] += 1
    await query.message.delete()
    await context.bot.send_message(query.from_user.id, "✅ Done! Send another URL.")
    os.remove(filepath)

# MAIN
async def post_init(app: Application):
    bot = await app.bot.get_me()
    logger.info(f"✅ Bot: @{bot.username}")
    asyncio.create_task(run_web())

def main():
    logger.info("🚀 Starting...")
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("adduser", adduser))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Regex(r'https?://'), handle_url))
    app.add_handler(CallbackQueryHandler(button))
    logger.info("✅ Running")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
