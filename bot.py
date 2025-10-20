#!/usr/bin/env python3
"""
Telegram Video Downloader Bot - Production Version
===================================================
Complete rewrite with web server for Render.com
Uses yt-dlp with optimal configuration
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

# Web server
from aiohttp import web

# Telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.constants import ParseMode, ChatAction
from telegram.error import TelegramError

# Video downloader
import yt_dlp

# ==================== CONFIGURATION ====================

BOT_TOKEN = "8367293218:AAF7VsjU0jkzoU8DLd1kX75Kr73hXrKiq94"
ADMIN_ID = 8175884349
PORT = int(os.getenv('PORT', '10000'))

AUTHORIZED_USERS_FILE = 'users.json'
STATS_FILE = 'stats.json'
DOWNLOADS_DIR = 'downloads'
TELEGRAM_FILE_LIMIT = 50 * 1024 * 1024  # 50MB

Path(DOWNLOADS_DIR).mkdir(exist_ok=True)

# ==================== LOGGING ====================

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)
logging.getLogger('httpx').setLevel(logging.WARNING)

# ==================== WEB SERVER (for Render health checks) ====================

async def health_check(request):
    """Health check endpoint for Render"""
    return web.Response(text="Bot is running!")

async def start_web_server():
    """Start web server for Render health checks"""
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    logger.info(f"✅ Web server started on port {PORT}")

# ==================== DATA MANAGER ====================

class DataManager:
    def __init__(self):
        self.authorized_users: Set[int] = self.load_users()
        self.stats: Dict = self.load_stats()
    
    def load_users(self) -> Set[int]:
        try:
            if os.path.exists(AUTHORIZED_USERS_FILE):
                with open(AUTHORIZED_USERS_FILE) as f:
                    data = json.load(f)
                    users = set(data.get('users', []))
                    users.add(ADMIN_ID)
                    return users
        except Exception as e:
            logger.error(f"Load users error: {e}")
        return {ADMIN_ID}
    
    def save_users(self):
        try:
            with open(AUTHORIZED_USERS_FILE, 'w') as f:
                json.dump({'users': list(self.authorized_users)}, f)
        except Exception as e:
            logger.error(f"Save users error: {e}")
    
    def load_stats(self) -> Dict:
        try:
            if os.path.exists(STATS_FILE):
                with open(STATS_FILE) as f:
                    return json.load(f)
        except:
            pass
        return {'total': 0, 'users': {}, 'platforms': {}}
    
    def save_stats(self):
        try:
            with open(STATS_FILE, 'w') as f:
                json.dump(self.stats, f)
        except Exception as e:
            logger.error(f"Save stats error: {e}")
    
    def add_user(self, user_id: int):
        self.authorized_users.add(user_id)
        self.save_users()
    
    def remove_user(self, user_id: int):
        if user_id != ADMIN_ID:
            self.authorized_users.discard(user_id)
            self.save_users()
    
    def is_authorized(self, user_id: int) -> bool:
        return user_id in self.authorized_users
    
    def record_download(self, user_id: int, platform: str):
        self.stats['total'] = self.stats.get('total', 0) + 1
        
        users = self.stats.get('users', {})
        users[str(user_id)] = users.get(str(user_id), 0) + 1
        self.stats['users'] = users
        
        platforms = self.stats.get('platforms', {})
        platforms[platform] = platforms.get(platform, 0) + 1
        self.stats['platforms'] = platforms
        
        self.save_stats()

data_manager = DataManager()

# ==================== VIDEO DOWNLOADER ====================

class VideoDownloader:
    def __init__(self):
        self.temp_dir = DOWNLOADS_DIR
    
    def get_platform(self, url: str) -> str:
        url_lower = url.lower()
        platforms = {
            'youtube.com': 'YouTube', 'youtu.be': 'YouTube',
            'instagram.com': 'Instagram',
            'tiktok.com': 'TikTok',
            'twitter.com': 'Twitter', 'x.com': 'Twitter',
            'facebook.com': 'Facebook',
            'reddit.com': 'Reddit',
            'vimeo.com': 'Vimeo',
            'pinterest.com': 'Pinterest',
        }
        
        for key, platform in platforms.items():
            if key in url_lower:
                return platform
        return 'Other'
    
    def format_bytes(self, size: int) -> str:
        if not size:
            return "Unknown"
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
    
    def get_ydl_opts(self, quality: str = "720", audio_only: bool = False):
        """Get yt-dlp options with anti-detection"""
        
        opts = {
            'quiet': True,
            'no_warnings': True,
            'format': 'bestaudio/best' if audio_only else f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]/best',
            'outtmpl': os.path.join(self.temp_dir, f'{int(time.time())}_%(id)s.%(ext)s'),
            'merge_output_format': 'mp4',
            'socket_timeout': 30,
            'retries': 10,
            'fragment_retries': 10,
            'http_chunk_size': 10485760,
            
            # Anti-bot detection
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'referer': 'https://www.google.com/',
            
            # Extractor args for different platforms
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                    'player_skip': ['webpage'],
                },
                'instagram': {
                    'api_mode': 'browser',
                }
            },
            
            # Cookies and headers
            'cookiesfrombrowser': None,
            'nocheckcertificate': True,
            'age_limit': None,
        }
        
        if audio_only:
            opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
            opts['format'] = 'bestaudio/best'
        
        return opts
    
    async def download(self, url: str, quality: str = "720") -> Optional[str]:
        """Download video"""
        try:
            is_audio = quality == "audio"
            opts = self.get_ydl_opts(quality, is_audio)
            
            loop = asyncio.get_event_loop()
            
            def download_sync():
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    
                    # Get filename
                    if is_audio:
                        filename = ydl.prepare_filename(info)
                        filename = filename.rsplit('.', 1)[0] + '.mp3'
                    else:
                        filename = ydl.prepare_filename(info)
                    
                    return filename
            
            filepath = await loop.run_in_executor(None, download_sync)
            
            if filepath and os.path.exists(filepath):
                size = os.path.getsize(filepath)
                logger.info(f"Downloaded: {filepath} ({self.format_bytes(size)})")
                return filepath
            
            return None
            
        except Exception as e:
            logger.error(f"Download error: {e}")
            return None
    
    def cleanup(self, filepath: str):
        try:
            if filepath and os.path.exists(filepath):
                os.remove(filepath)
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
    
    def cleanup_old_files(self):
        try:
            now = time.time()
            for filename in os.listdir(self.temp_dir):
                filepath = os.path.join(self.temp_dir, filename)
                if os.path.isfile(filepath):
                    if now - os.path.getmtime(filepath) > 3600:
                        os.remove(filepath)
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

downloader = VideoDownloader()

# ==================== TELEGRAM HANDLERS ====================

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not data_manager.is_authorized(user.id):
        await update.message.reply_text(
            f"⚠️ Access Denied\n\n"
            f"Your ID: `{user.id}`\n"
            f"Username: @{user.username or 'None'}\n\n"
            f"Contact admin for access.",
            parse_mode=ParseMode.MARKDOWN
        )
        
        try:
            await context.bot.send_message(
                ADMIN_ID,
                f"🔔 New user:\n"
                f"Name: {user.full_name}\n"
                f"ID: `{user.id}`\n"
                f"Username: @{user.username or 'None'}\n\n"
                f"Authorize: `/adduser {user.id}`",
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            pass
        return
    
    await update.message.reply_text(
        f"👋 Welcome {user.first_name}!\n\n"
        f"🎬 Send me any video URL from:\n"
        f"• YouTube\n"
        f"• Instagram\n"
        f"• TikTok\n"
        f"• Twitter\n"
        f"• Facebook\n"
        f"• And more!\n\n"
        f"I'll send you the video!\n\n"
        f"Type /help for more info."
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 **How to Use**\n\n"
        "1. Send me a video URL\n"
        "2. Select quality\n"
        "3. Get your video!\n\n"
        "**Commands:**\n"
        "/start - Start bot\n"
        "/help - This message\n"
        "/stats - Your stats\n\n"
        "**Admin:**\n"
        "/adduser <id>\n"
        "/removeuser <id>\n"
        "/listusers\n"
        "/globalstats",
        parse_mode=ParseMode.MARKDOWN
    )

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not data_manager.is_authorized(update.effective_user.id):
        return
    
    user_id = str(update.effective_user.id)
    downloads = data_manager.stats.get('users', {}).get(user_id, 0)
    
    await update.message.reply_text(
        f"📊 **Your Stats**\n\n"
        f"Downloads: {downloads}",
        parse_mode=ParseMode.MARKDOWN
    )

async def adduser_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /adduser <user_id>")
        return
    
    try:
        new_user_id = int(context.args[0])
        data_manager.add_user(new_user_id)
        await update.message.reply_text(f"✅ Added user {new_user_id}")
        
        try:
            await context.bot.send_message(
                new_user_id,
                "🎉 Access granted!\nSend /start to begin."
            )
        except:
            pass
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID")

async def removeuser_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /removeuser <user_id>")
        return
    
    try:
        user_id = int(context.args[0])
        data_manager.remove_user(user_id)
        await update.message.reply_text(f"✅ Removed user {user_id}")
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID")

async def listusers_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    users = sorted(data_manager.authorized_users)
    user_list = "\n".join([f"`{uid}`" for uid in users])
    
    await update.message.reply_text(
        f"📝 **Users ({len(users)})**\n\n{user_list}",
        parse_mode=ParseMode.MARKDOWN
    )

async def globalstats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    stats = data_manager.stats
    total = stats.get('total', 0)
    users = len(data_manager.authorized_users)
    
    platforms = stats.get('platforms', {})
    platform_text = "\n".join([
        f"• {p}: {c}" 
        for p, c in sorted(platforms.items(), key=lambda x: x[1], reverse=True)[:5]
    ])
    
    await update.message.reply_text(
        f"📊 **Global Stats**\n\n"
        f"Downloads: {total}\n"
        f"Users: {users}\n\n"
        f"**Platforms:**\n{platform_text or 'None'}",
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not data_manager.is_authorized(user_id):
        await update.message.reply_text("⚠️ Not authorized")
        return
    
    url = update.message.text.strip()
    
    if not url.startswith(('http://', 'https://')):
        await update.message.reply_text("❌ Invalid URL")
        return
    
    msg = await update.message.reply_text("🔍 Processing...")
    
    try:
        platform = downloader.get_platform(url)
        
        # Quality buttons
        keyboard = [
            [InlineKeyboardButton("1080p", callback_data=f"dl_1080_{hash(url) % 10000}")],
            [InlineKeyboardButton("720p (Recommended)", callback_data=f"dl_720_{hash(url) % 10000}")],
            [InlineKeyboardButton("480p", callback_data=f"dl_480_{hash(url) % 10000}")],
            [InlineKeyboardButton("360p", callback_data=f"dl_360_{hash(url) % 10000}")],
            [InlineKeyboardButton("🎵 Audio Only", callback_data=f"dl_audio_{hash(url) % 10000}")],
        ]
        
        # Store URL
        if 'user_data' not in context.bot_data:
            context.bot_data['user_data'] = {}
        if user_id not in context.bot_data['user_data']:
            context.bot_data['user_data'][user_id] = {}
        
        context.bot_data['user_data'][user_id]['url'] = url
        context.bot_data['user_data'][user_id]['platform'] = platform
        
        await msg.edit_text(
            f"✅ **Ready to download**\n\n"
            f"Platform: {platform}\n\n"
            f"Select quality:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"URL handler error: {e}")
        await msg.edit_text("❌ Error processing URL")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    
    await query.answer()
    
    if not data_manager.is_authorized(user_id):
        return
    
    try:
        # Parse callback
        parts = query.data.split('_')
        quality = parts[1]
        
        # Get URL
        user_data = context.bot_data.get('user_data', {}).get(user_id, {})
        url = user_data.get('url')
        platform = user_data.get('platform', 'Unknown')
        
        if not url:
            await query.message.edit_text("❌ Session expired. Send URL again.")
            return
        
        await query.message.edit_text(
            f"⬇️ Downloading...\n\n"
            f"Quality: {quality}\n"
            f"Platform: {platform}\n\n"
            f"Please wait..."
        )
        
        # Download
        filepath = await downloader.download(url, quality)
        
        if not filepath:
            await query.message.edit_text(
                "❌ **Download failed**\n\n"
                "Reasons:\n"
                "• Video is private\n"
                "• Platform blocking\n"
                "• Invalid URL\n\n"
                "Try another video or quality."
            )
            return
        
        # Check size
        size = os.path.getsize(filepath)
        
        if size > TELEGRAM_FILE_LIMIT:
            await query.message.edit_text(
                f"❌ **File too large**\n\n"
                f"Size: {downloader.format_bytes(size)}\n"
                f"Limit: 50 MB\n\n"
                f"Try lower quality."
            )
            downloader.cleanup(filepath)
            return
        
        await query.message.edit_text(
            f"📤 Uploading...\n\n{downloader.format_bytes(size)}"
        )
        
        # Send file
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
        data_manager.record_download(user_id, platform)
        
        await query.message.delete()
        await context.bot.send_message(user_id, "✅ Done!\n\nSend another URL.")
        
        # Cleanup
        downloader.cleanup(filepath)
        
        logger.info(f"Sent to {user_id}: {platform} ({quality})")
        
    except Exception as e:
        logger.error(f"Callback error: {e}")
        try:
            await query.message.edit_text("❌ Error occurred")
        except:
            pass

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")

# ==================== BOT SETUP ====================

async def post_init(app: Application):
    try:
        commands = [
            BotCommand("start", "Start bot"),
            BotCommand("help", "Help"),
            BotCommand("stats", "Your stats"),
        ]
        await app.bot.set_my_commands(commands)
        
        bot = await app.bot.get_me()
        logger.info(f"✅ Bot: @{bot.username}")
        logger.info(f"✅ Admin: {ADMIN_ID}")
        logger.info(f"✅ Users: {len(data_manager.authorized_users)}")
        
        downloader.cleanup_old_files()
        
        # Start web server
        await start_web_server()
        
    except Exception as e:
        logger.error(f"Init error: {e}")

def main():
    logger.info("🚀 Starting bot...")
    
    try:
        app = (
            Application.builder()
            .token(BOT_TOKEN)
            .post_init(post_init)
            .read_timeout(30)
            .write_timeout(30)
            .build()
        )
        
        # Handlers
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
        
        # Run
        logger.info("✅ Running in polling mode with web server")
        app.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"Fatal: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
