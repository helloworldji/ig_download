#!/usr/bin/env python3
"""
Telegram Video Downloader Bot - Production Version
===================================================
"""

import os
import sys
import logging
import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Set
from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.constants import ParseMode
from telegram.error import TelegramError
import yt_dlp

# ==================== CONFIG ====================

BOT_TOKEN = "8367293218:AAF7VsjU0jkzoU8DLd1kX75Kr73hXrKiq94"
ADMIN_ID = 8175884349
PORT = int(os.getenv('PORT', '10000'))

DOWNLOADS_DIR = 'downloads'
TELEGRAM_FILE_LIMIT = 50 * 1024 * 1024

Path(DOWNLOADS_DIR).mkdir(exist_ok=True)

# ==================== LOGGING ====================

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
logging.getLogger('httpx').setLevel(logging.WARNING)

# ==================== GLOBALS ====================

authorized_users = {ADMIN_ID}
download_stats = {'total': 0, 'users': {}, 'platforms': {}}

# ==================== WEB SERVER ====================

async def health(request):
    return web.Response(text="OK")

async def run_web_server():
    """Run web server in background"""
    app = web.Application()
    app.router.add_get('/', health)
    app.router.add_get('/health', health)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    logger.info(f"✅ Web server running on port {PORT}")
    
    # Keep running
    while True:
        await asyncio.sleep(3600)

# ==================== DOWNLOADER ====================

def format_bytes(size: int) -> str:
    if not size:
        return "Unknown"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"

def get_platform(url: str) -> str:
    url = url.lower()
    if 'youtube.com' in url or 'youtu.be' in url:
        return 'YouTube'
    elif 'instagram.com' in url:
        return 'Instagram'
    elif 'tiktok.com' in url:
        return 'TikTok'
    elif 'twitter.com' in url or 'x.com' in url:
        return 'Twitter'
    elif 'facebook.com' in url:
        return 'Facebook'
    elif 'reddit.com' in url:
        return 'Reddit'
    return 'Other'

async def download_video(url: str, quality: str = "720") -> Optional[str]:
    """Download video using yt-dlp"""
    try:
        is_audio = quality == "audio"
        
        opts = {
            'quiet': True,
            'no_warnings': True,
            'outtmpl': os.path.join(DOWNLOADS_DIR, f'{int(time.time())}.%(ext)s'),
            'socket_timeout': 30,
            'retries': 10,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }
        
        if is_audio:
            opts['format'] = 'bestaudio/best'
            opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        else:
            opts['format'] = f'bestvideo[height<={quality}]+bestaudio/best'
            opts['merge_output_format'] = 'mp4'
        
        loop = asyncio.get_event_loop()
        
        def dl():
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                if is_audio:
                    filename = filename.rsplit('.', 1)[0] + '.mp3'
                return filename
        
        filepath = await loop.run_in_executor(None, dl)
        
        if filepath and os.path.exists(filepath):
            logger.info(f"Downloaded: {filepath}")
            return filepath
        
        return None
        
    except Exception as e:
        logger.error(f"Download error: {e}")
        return None

def cleanup_file(filepath: str):
    try:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
    except:
        pass

# ==================== HANDLERS ====================

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if user.id not in authorized_users:
        await update.message.reply_text(
            f"⚠️ Not authorized\n\n"
            f"Your ID: `{user.id}`\n\n"
            f"Contact admin.",
            parse_mode=ParseMode.MARKDOWN
        )
        
        try:
            await context.bot.send_message(
                ADMIN_ID,
                f"🔔 New user: {user.full_name}\n"
                f"ID: `{user.id}`\n"
                f"Username: @{user.username or 'None'}\n\n"
                f"Authorize: `/adduser {user.id}`",
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            pass
        return
    
    await update.message.reply_text(
        f"👋 Welcome!\n\n"
        f"Send me any video URL from:\n"
        f"• YouTube\n"
        f"• Instagram\n"
        f"• TikTok\n"
        f"• Twitter\n"
        f"• Facebook\n\n"
        f"I'll download it for you!"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 **Help**\n\n"
        "1. Send video URL\n"
        "2. Select quality\n"
        "3. Get video!\n\n"
        "Commands:\n"
        "/start /help /stats",
        parse_mode=ParseMode.MARKDOWN
    )

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in authorized_users:
        return
    
    user_downloads = download_stats['users'].get(str(update.effective_user.id), 0)
    await update.message.reply_text(
        f"📊 Your downloads: {user_downloads}",
        parse_mode=ParseMode.MARKDOWN
    )

async def adduser_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /adduser <user_id>")
        return
    
    try:
        new_id = int(context.args[0])
        authorized_users.add(new_id)
        await update.message.reply_text(f"✅ Added {new_id}")
        
        try:
            await context.bot.send_message(new_id, "🎉 Access granted! /start")
        except:
            pass
    except:
        await update.message.reply_text("❌ Invalid ID")

async def removeuser_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /removeuser <user_id>")
        return
    
    try:
        user_id = int(context.args[0])
        if user_id != ADMIN_ID:
            authorized_users.discard(user_id)
            await update.message.reply_text(f"✅ Removed {user_id}")
    except:
        await update.message.reply_text("❌ Invalid ID")

async def listusers_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    users = "\n".join([f"`{u}`" for u in sorted(authorized_users)])
    await update.message.reply_text(
        f"📝 Users ({len(authorized_users)}):\n\n{users}",
        parse_mode=ParseMode.MARKDOWN
    )

async def globalstats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    total = download_stats.get('total', 0)
    platforms = download_stats.get('platforms', {})
    platform_text = "\n".join([f"• {p}: {c}" for p, c in platforms.items()])
    
    await update.message.reply_text(
        f"📊 **Global Stats**\n\n"
        f"Total: {total}\n"
        f"Users: {len(authorized_users)}\n\n"
        f"{platform_text}",
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in authorized_users:
        return
    
    url = update.message.text.strip()
    
    if not url.startswith(('http://', 'https://')):
        return
    
    msg = await update.message.reply_text("🔍 Processing...")
    
    try:
        platform = get_platform(url)
        
        keyboard = [
            [InlineKeyboardButton("1080p", callback_data=f"dl_1080_{hash(url) % 9999}")],
            [InlineKeyboardButton("720p ⭐", callback_data=f"dl_720_{hash(url) % 9999}")],
            [InlineKeyboardButton("480p", callback_data=f"dl_480_{hash(url) % 9999}")],
            [InlineKeyboardButton("360p", callback_data=f"dl_360_{hash(url) % 9999}")],
            [InlineKeyboardButton("🎵 Audio", callback_data=f"dl_audio_{hash(url) % 9999}")],
        ]
        
        if 'user_data' not in context.bot_data:
            context.bot_data['user_data'] = {}
        if user_id not in context.bot_data['user_data']:
            context.bot_data['user_data'][user_id] = {}
        
        context.bot_data['user_data'][user_id]['url'] = url
        context.bot_data['user_data'][user_id]['platform'] = platform
        
        await msg.edit_text(
            f"✅ Ready\n\nPlatform: {platform}\n\nSelect quality:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logger.error(f"URL error: {e}")
        await msg.edit_text("❌ Error")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    
    await query.answer()
    
    if user_id not in authorized_users:
        return
    
    try:
        parts = query.data.split('_')
        quality = parts[1]
        
        user_data = context.bot_data.get('user_data', {}).get(user_id, {})
        url = user_data.get('url')
        platform = user_data.get('platform', 'Unknown')
        
        if not url:
            await query.message.edit_text("❌ Expired. Send URL again.")
            return
        
        await query.message.edit_text(
            f"⬇️ Downloading...\n\n"
            f"Quality: {quality}\n"
            f"Platform: {platform}\n\n"
            f"Please wait..."
        )
        
        filepath = await download_video(url, quality)
        
        if not filepath:
            await query.message.edit_text(
                "❌ Download failed\n\n"
                "Try:\n"
                "• Different quality\n"
                "• Different video\n"
                "• Check if video is public"
            )
            return
        
        size = os.path.getsize(filepath)
        
        if size > TELEGRAM_FILE_LIMIT:
            await query.message.edit_text(
                f"❌ Too large\n\n"
                f"Size: {format_bytes(size)}\n"
                f"Limit: 50 MB\n\n"
                f"Try lower quality"
            )
            cleanup_file(filepath)
            return
        
        await query.message.edit_text(f"📤 Uploading... ({format_bytes(size)})")
        
        is_audio = quality == 'audio'
        
        with open(filepath, 'rb') as f:
            if is_audio:
                await context.bot.send_audio(
                    user_id, f,
                    caption=f"🎵 {platform}",
                    read_timeout=60, write_timeout=60
                )
            else:
                await context.bot.send_video(
                    user_id, f,
                    caption=f"🎬 {platform} | {quality}",
                    supports_streaming=True,
                    read_timeout=60, write_timeout=60
                )
        
        # Stats
        download_stats['total'] = download_stats.get('total', 0) + 1
        users = download_stats.get('users', {})
        users[str(user_id)] = users.get(str(user_id), 0) + 1
        download_stats['users'] = users
        platforms = download_stats.get('platforms', {})
        platforms[platform] = platforms.get(platform, 0) + 1
        download_stats['platforms'] = platforms
        
        await query.message.delete()
        await context.bot.send_message(user_id, "✅ Done! Send another URL.")
        
        cleanup_file(filepath)
        
        logger.info(f"Sent to {user_id}: {platform} ({quality})")
        
    except Exception as e:
        logger.error(f"Callback error: {e}")
        try:
            await query.message.edit_text("❌ Error")
        except:
            pass

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")

# ==================== MAIN ====================

async def post_init(app: Application):
    try:
        commands = [
            BotCommand("start", "Start"),
            BotCommand("help", "Help"),
            BotCommand("stats", "Stats"),
        ]
        await app.bot.set_my_commands(commands)
        
        bot = await app.bot.get_me()
        logger.info(f"✅ Bot: @{bot.username}")
        logger.info(f"✅ Admin: {ADMIN_ID}")
        logger.info(f"✅ Users: {len(authorized_users)}")
        
        # Start web server in background
        asyncio.create_task(run_web_server())
        
    except Exception as e:
        logger.error(f"Init error: {e}")

def main():
    logger.info("🚀 Starting...")
    
    try:
        app = (
            Application.builder()
            .token(BOT_TOKEN)
            .post_init(post_init)
            .read_timeout(30)
            .write_timeout(30)
            .build()
        )
        
        app.add_handler(CommandHandler("start", start_cmd))
        app.add_handler(CommandHandler("help", help_cmd))
        app.add_handler(CommandHandler("stats", stats_cmd))
        app.add_handler(CommandHandler("adduser", adduser_cmd))
        app.add_handler(CommandHandler("removeuser", removeuser_cmd))
        app.add_handler(CommandHandler("listusers", listusers_cmd))
        app.add_handler(CommandHandler("globalstats", globalstats_cmd))
        
        app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.Regex(r'https?://'),
            handle_url
        ))
        
        app.add_handler(CallbackQueryHandler(button_callback))
        app.add_error_handler(error_handler)
        
        logger.info("✅ Running")
        app.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"Fatal: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
