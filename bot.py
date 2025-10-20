#!/usr/bin/env python3
"""
Telegram Video Downloader Bot - API-Based Version
==================================================
Uses Cobalt API to bypass all platform restrictions

REQUIREMENTS:
python-telegram-bot==21.5
aiohttp==3.10.11
"""

import os
import re  # Add this with other imports at the top
import sys
import logging
import asyncio
import json
import time
import re
from datetime import datetime
from typing import Dict, List, Optional, Set
from pathlib import Path
from urllib.parse import urlparse

# Telegram imports
from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup,
    BotCommand
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from telegram.constants import ParseMode, ChatAction
from telegram.error import TelegramError

# For async HTTP requests
import aiohttp

# ==================== CONFIGURATION ====================

# Bot Configuration
BOT_TOKEN = "8367293218:AAF7VsjU0jkzoU8DLd1kX75Kr73hXrKiq94"
ADMIN_ID = 8175884349
WEBHOOK_URL = ""  # Leave empty for polling mode

PORT = int(os.getenv('PORT', '10000'))

# File paths
AUTHORIZED_USERS_FILE = 'authorized_users.json'
STATS_FILE = 'stats.json'
DOWNLOADS_DIR = 'downloads'

# Telegram file size limit
TELEGRAM_FILE_SIZE_LIMIT = 50 * 1024 * 1024

# Create downloads directory
Path(DOWNLOADS_DIR).mkdir(exist_ok=True)

# ==================== LOGGING ====================

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ==================== MESSAGES ====================

WELCOME_MESSAGE = """
🎬 **Welcome to Video Downloader Bot!**

I can download videos from:
• YouTube
• Instagram 
• TikTok
• Twitter/X
• Facebook
• Reddit
• Pinterest
• Vimeo
• And many more!

**How to use:**
1. Send me a video URL
2. Choose quality
3. Get your video!

Type /help for more info.
"""

HELP_MESSAGE = """
📖 **How to Use**

**Download Videos:**
1. Send any video URL
2. Select quality (1080p, 720p, 480p, etc.)
3. Receive your video!

**Commands:**
/start - Start the bot
/help - Show this help
/stats - Your statistics
/platforms - Supported platforms

**Admin Commands:**
/adduser <id> - Add user
/removeuser <id> - Remove user
/listusers - List users
/globalstats - Global stats

**Supported Platforms:**
YouTube, Instagram, TikTok, Twitter, Facebook, Reddit, Vimeo, Pinterest, Streamable, SoundCloud, and more!

**Tips:**
• Use lower quality for long videos
• Audio only option for music
• 50MB Telegram file limit

Enjoy! 🚀
"""

# ==================== DATA MANAGER ====================

class DataManager:
    def __init__(self):
        self.authorized_users: Set[int] = self.load_authorized_users()
        self.stats: Dict = self.load_stats()
    
    def load_authorized_users(self) -> Set[int]:
        try:
            if os.path.exists(AUTHORIZED_USERS_FILE):
                with open(AUTHORIZED_USERS_FILE, 'r') as f:
                    data = json.load(f)
                    users = set(data.get('users', []))
                    users.add(ADMIN_ID)
                    return users
            return {ADMIN_ID}
        except Exception as e:
            logger.error(f"Error loading users: {e}")
            return {ADMIN_ID}
    
    def save_authorized_users(self):
        try:
            with open(AUTHORIZED_USERS_FILE, 'w') as f:
                json.dump({'users': list(self.authorized_users)}, f)
        except Exception as e:
            logger.error(f"Error saving users: {e}")
    
    def load_stats(self) -> Dict:
        try:
            if os.path.exists(STATS_FILE):
                with open(STATS_FILE, 'r') as f:
                    return json.load(f)
            return {
                'total_downloads': 0,
                'user_downloads': {},
                'platform_stats': {},
            }
        except Exception:
            return {'total_downloads': 0, 'user_downloads': {}, 'platform_stats': {}}
    
    def save_stats(self):
        try:
            with open(STATS_FILE, 'w') as f:
                json.dump(self.stats, f)
        except Exception as e:
            logger.error(f"Error saving stats: {e}")
    
    def add_user(self, user_id: int):
        self.authorized_users.add(user_id)
        self.save_authorized_users()
    
    def remove_user(self, user_id: int):
        if user_id != ADMIN_ID and user_id in self.authorized_users:
            self.authorized_users.remove(user_id)
            self.save_authorized_users()
    
    def is_authorized(self, user_id: int) -> bool:
        return user_id in self.authorized_users
    
    def record_download(self, user_id: int, platform: str, quality: str):
        self.stats['total_downloads'] = self.stats.get('total_downloads', 0) + 1
        
        user_stats = self.stats.get('user_downloads', {})
        user_stats[str(user_id)] = user_stats.get(str(user_id), 0) + 1
        self.stats['user_downloads'] = user_stats
        
        platform_stats = self.stats.get('platform_stats', {})
        platform_stats[platform] = platform_stats.get(platform, 0) + 1
        self.stats['platform_stats'] = platform_stats
        
        self.save_stats()

data_manager = DataManager()

# ==================== VIDEO DOWNLOADER (API-BASED) ====================

class VideoDownloader:
    """Downloads videos using multiple APIs with fallbacks"""
    
    def __init__(self):
        self.temp_dir = DOWNLOADS_DIR
    
    def get_platform(self, url: str) -> str:
        """Detect platform from URL"""
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
        elif 'pinterest.com' in url:
            return 'Pinterest'
        elif 'vimeo.com' in url:
            return 'Vimeo'
        
        return 'Unknown'
    
    def format_bytes(self, size: int) -> str:
        """Format bytes to readable size"""
        if not size:
            return "Unknown"
        
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
    
    async def download_with_api1(self, url: str, quality: str = "720") -> Optional[str]:
        """Try API 1: social-download-all-in-one"""
        
        try:
            api_url = "https://social-download-all-in-one.p.rapidapi.com/v1/social/autolink"
            
            headers = {
                "content-type": "application/json",
            }
            
            payload = {"url": url}
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    api_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        
                        # Extract download URL
                        if 'medias' in data and len(data['medias']) > 0:
                            media = data['medias'][0]
                            download_url = media.get('url')
                            if download_url:
                                logger.info("API1 success")
                                return download_url
                        
        except Exception as e:
            logger.error(f"API1 failed: {e}")
        
        return None
    
    async def download_with_api2(self, url: str, quality: str = "720") -> Optional[str]:
        """Try API 2: SaveFrom.net"""
        
        try:
            # SaveFrom API endpoint
            api_url = f"https://api.savefrom.net/info?url={url}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    api_url,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    if response.status == 200:
                        text = await response.text()
                        
                        # Parse response (JSON-like format)
                        import json
                        try:
                            # Extract JSON from callback
                            if '(' in text:
                                json_str = text.split('(', 1)[1].rsplit(')', 1)[0]
                                data = json.loads(json_str)
                                
                                if 'url' in data and len(data['url']) > 0:
                                    video = data['url'][0]
                                    download_url = video.get('url')
                                    if download_url:
                                        logger.info("API2 success")
                                        return download_url
                        except:
                            pass
                        
        except Exception as e:
            logger.error(f"API2 failed: {e}")
        
        return None
    
    async def download_with_api3(self, url: str, quality: str = "720") -> Optional[str]:
        """Try API 3: DownloadGram (Instagram specific)"""
        
        if 'instagram.com' not in url.lower():
            return None
        
        try:
            api_url = "https://downloadgram.org/reel-downloader.php"
            
            payload = {
                "url": url,
                "submit": ""
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    api_url,
                    data=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    if response.status == 200:
                        text = await response.text()
                        
                        # Extract download link from HTML
                        import re
                        matches = re.findall(r'href="(https://[^"]+\.mp4[^"]*)"', text)
                        
                        if matches:
                            logger.info("API3 success")
                            return matches[0]
                        
        except Exception as e:
            logger.error(f"API3 failed: {e}")
        
        return None
    
    async def download_with_cobalt_fixed(self, url: str, quality: str = "720") -> Optional[str]:
        """Try Cobalt API with fixed format"""
        
        try:
            # Use the new Cobalt API v9 format
            api_url = "https://api.cobalt.tools/api/json"
            
            is_audio = quality == "audio"
            
            # Simplified payload
            payload = {
                "url": url,
                "vQuality": "max" if quality == "max" else quality,
                "filenamePattern": "classic",
                "isAudioOnly": is_audio,
                "aFormat": "mp3" if is_audio else "best",
                "isAudioMuted": False,
                "dubLang": False
            }
            
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    api_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        
                        status = data.get('status')
                        
                        if status == 'stream' or status == 'redirect':
                            download_url = data.get('url')
                            if download_url:
                                logger.info("Cobalt API success")
                                return download_url
                        
                        elif status == 'picker':
                            picker = data.get('picker', [])
                            if picker:
                                logger.info("Cobalt picker success")
                                return picker[0].get('url')
                    
                    else:
                        error_text = await response.text()
                        logger.warning(f"Cobalt returned {response.status}: {error_text[:200]}")
                        
        except Exception as e:
            logger.error(f"Cobalt failed: {e}")
        
        return None
    
    async def get_download_url(self, url: str, quality: str = "720") -> Optional[str]:
        """Try all APIs in sequence"""
        
        logger.info(f"Attempting download for: {url}")
        
        # Try Cobalt first (most reliable when it works)
        download_url = await self.download_with_cobalt_fixed(url, quality)
        if download_url:
            return download_url
        
        # Try API 1
        download_url = await self.download_with_api1(url, quality)
        if download_url:
            return download_url
        
        # Try API 2
        download_url = await self.download_with_api2(url, quality)
        if download_url:
            return download_url
        
        # Try API 3 (Instagram specific)
        download_url = await self.download_with_api3(url, quality)
        if download_url:
            return download_url
        
        logger.error("All APIs failed")
        return None
    
    async def download_file(self, download_url: str, is_audio: bool = False) -> Optional[str]:
        """Download file from direct URL"""
        
        ext = 'mp3' if is_audio else 'mp4'
        filename = f"{int(time.time())}.{ext}"
        filepath = os.path.join(self.temp_dir, filename)
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    download_url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=300)
                ) as response:
                    
                    if response.status != 200:
                        logger.error(f"Download failed: HTTP {response.status}")
                        return None
                    
                    # Download file in chunks
                    with open(filepath, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)
                    
                    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                        logger.info(f"Downloaded: {filepath} ({self.format_bytes(os.path.getsize(filepath))})")
                        return filepath
                    
                    return None
                    
        except Exception as e:
            logger.error(f"Download error: {e}")
            if os.path.exists(filepath):
                os.remove(filepath)
            return None
    
    async def download_video(self, url: str, quality: str = "720") -> Optional[str]:
        """Main download function"""
        
        try:
            # Get download URL from APIs
            download_url = await self.get_download_url(url, quality)
            
            if not download_url:
                logger.error("Failed to get download URL from any API")
                return None
            
            logger.info(f"Got download URL: {download_url[:100]}")
            
            # Download the file
            is_audio = quality == "audio"
            filepath = await self.download_file(download_url, is_audio)
            
            return filepath
            
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return None
    
    def cleanup(self, filepath: str):
        """Delete file"""
        try:
            if filepath and os.path.exists(filepath):
                os.remove(filepath)
                logger.info(f"Cleaned: {filepath}")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
    
    def cleanup_old_files(self):
        """Clean old files"""
        try:
            now = time.time()
            for filename in os.listdir(self.temp_dir):
                filepath = os.path.join(self.temp_dir, filename)
                if os.path.isfile(filepath):
                    age = now - os.path.getmtime(filepath)
                    if age > 3600:  # 1 hour
                        os.remove(filepath)
                        logger.info(f"Cleaned old: {filename}")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
# ==================== COMMAND HANDLERS ====================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start"""
    user = update.effective_user
    
    if not data_manager.is_authorized(user.id):
        await update.message.reply_text(
            f"⚠️ **Access Denied**\n\n"
            f"Your ID: `{user.id}`\n"
            f"Username: @{user.username or 'None'}\n\n"
            f"Contact admin for access.",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Notify admin
        try:
            await context.bot.send_message(
                ADMIN_ID,
                f"🔔 New user request\n\n"
                f"Name: {user.full_name}\n"
                f"Username: @{user.username or 'None'}\n"
                f"ID: `{user.id}`\n\n"
                f"Authorize: `/adduser {user.id}`",
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            pass
        return
    
    await update.message.reply_text(
        f"👋 Hello {user.first_name}!\n\n" + WELCOME_MESSAGE,
        parse_mode=ParseMode.MARKDOWN
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help"""
    await update.message.reply_text(HELP_MESSAGE, parse_mode=ParseMode.MARKDOWN)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats"""
    if not data_manager.is_authorized(update.effective_user.id):
        return
    
    user_id = update.effective_user.id
    downloads = data_manager.stats.get('user_downloads', {}).get(str(user_id), 0)
    
    await update.message.reply_text(
        f"📊 **Your Stats**\n\n"
        f"Downloads: {downloads}\n\n"
        f"Thank you! 🙏",
        parse_mode=ParseMode.MARKDOWN
    )

async def platforms_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /platforms"""
    platforms = """
🌐 **Supported Platforms**

✅ YouTube
✅ Instagram  
✅ TikTok
✅ Twitter/X
✅ Facebook
✅ Reddit
✅ Pinterest
✅ Vimeo
✅ Streamable
✅ SoundCloud
✅ Dailymotion
✅ Twitch

And many more!

Just send any video URL!
"""
    await update.message.reply_text(platforms, parse_mode=ParseMode.MARKDOWN)

async def adduser_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /adduser"""
    if update.effective_user.id != ADMIN_ID:
        return
    
    if not context.args:
        await update.message.reply_text("Usage: `/adduser <user_id>`", parse_mode=ParseMode.MARKDOWN)
        return
    
    try:
        new_user_id = int(context.args[0])
        data_manager.add_user(new_user_id)
        
        await update.message.reply_text(f"✅ Added user `{new_user_id}`", parse_mode=ParseMode.MARKDOWN)
        
        try:
            await context.bot.send_message(
                new_user_id,
                "🎉 Access granted! Send /start to begin.",
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            pass
            
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID")

async def removeuser_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /removeuser"""
    if update.effective_user.id != ADMIN_ID:
        return
    
    if not context.args:
        await update.message.reply_text("Usage: `/removeuser <user_id>`", parse_mode=ParseMode.MARKDOWN)
        return
    
    try:
        user_id = int(context.args[0])
        data_manager.remove_user(user_id)
        await update.message.reply_text(f"✅ Removed user `{user_id}`", parse_mode=ParseMode.MARKDOWN)
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID")

async def listusers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /listusers"""
    if update.effective_user.id != ADMIN_ID:
        return
    
    users = sorted(data_manager.authorized_users)
    user_list = "\n".join([f"`{uid}`" for uid in users])
    
    await update.message.reply_text(
        f"📝 **Authorized Users ({len(users)})**\n\n{user_list}",
        parse_mode=ParseMode.MARKDOWN
    )

async def globalstats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /globalstats"""
    if update.effective_user.id != ADMIN_ID:
        return
    
    stats = data_manager.stats
    total = stats.get('total_downloads', 0)
    users = len(data_manager.authorized_users)
    
    platform_stats = stats.get('platform_stats', {})
    platform_text = "\n".join([f"• {p}: {c}" for p, c in sorted(platform_stats.items(), key=lambda x: x[1], reverse=True)[:10]])
    
    await update.message.reply_text(
        f"📊 **Global Stats**\n\n"
        f"Total Downloads: {total}\n"
        f"Users: {users}\n\n"
        f"**Top Platforms:**\n{platform_text or 'None'}",
        parse_mode=ParseMode.MARKDOWN
    )

# ==================== URL HANDLER ====================

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle video URLs"""
    user_id = update.effective_user.id
    
    if not data_manager.is_authorized(user_id):
        await update.message.reply_text("⚠️ Not authorized")
        return
    
    url = update.message.text.strip()
    
    # Validate URL
    if not url.startswith(('http://', 'https://')):
        await update.message.reply_text("❌ Invalid URL")
        return
    
    msg = await update.message.reply_text("🔍 Processing...")
    
    try:
        platform = downloader.get_platform(url)
        
        # Quality options
        qualities = [
            ('1080p (Full HD)', '1080'),
            ('720p (HD)', '720'),
            ('480p (SD)', '480'),
            ('360p', '360'),
            ('🎵 Audio Only', 'audio'),
        ]
        
        # Create buttons
        keyboard = []
        for label, value in qualities:
            callback_data = f"dl_{value}_{abs(hash(url)) % 10000}"
            keyboard.append([InlineKeyboardButton(label, callback_data=callback_data)])
        
        # Store URL
        if 'user_data' not in context.bot_data:
            context.bot_data['user_data'] = {}
        if user_id not in context.bot_data['user_data']:
            context.bot_data['user_data'][user_id] = {}
        
        context.bot_data['user_data'][user_id]['url'] = url
        context.bot_data['user_data'][user_id]['platform'] = platform
        
        await msg.edit_text(
            f"✅ **Video Found**\n\n"
            f"Platform: {platform}\n\n"
            f"Select quality:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Error: {e}")
        await msg.edit_text("❌ Error processing URL")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle quality selection"""
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
            f"⬇️ **Downloading**\n\n"
            f"Quality: {quality}\n"
            f"Platform: {platform}\n\n"
            f"Please wait...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Download
        filepath = await downloader.download_video(url, quality)
        
        if not filepath:
            await query.message.edit_text(
                "❌ **Download Failed**\n\n"
                "Possible reasons:\n"
                "• Video is private\n"
                "• Platform blocking\n"
                "• Invalid URL\n\n"
                "Try another video or quality."
            )
            return
        
        # Check size
        size = os.path.getsize(filepath)
        
        if size > TELEGRAM_FILE_SIZE_LIMIT:
            await query.message.edit_text(
                f"❌ **File too large**\n\n"
                f"Size: {downloader.format_bytes(size)}\n"
                f"Limit: 50 MB\n\n"
                f"Try lower quality."
            )
            downloader.cleanup(filepath)
            return
        
        await query.message.edit_text(f"📤 Uploading... ({downloader.format_bytes(size)})")
        
        # Send file
        is_audio = quality == 'audio'
        
        with open(filepath, 'rb') as f:
            if is_audio:
                await context.bot.send_audio(
                    user_id,
                    f,
                    caption=f"🎵 {platform} | Audio",
                    read_timeout=60,
                    write_timeout=60
                )
            else:
                await context.bot.send_video(
                    user_id,
                    f,
                    caption=f"🎬 {platform} | {quality}",
                    supports_streaming=True,
                    read_timeout=60,
                    write_timeout=60
                )
        
        # Record stats
        data_manager.record_download(user_id, platform, quality)
        
        await query.message.delete()
        await context.bot.send_message(user_id, "✅ Done! Send another URL.")
        
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
    """Global error handler"""
    logger.error(f"Error: {context.error}")

# ==================== MAIN ====================

async def post_init(application: Application):
    """Post init"""
    try:
        commands = [
            BotCommand("start", "Start bot"),
            BotCommand("help", "Show help"),
            BotCommand("stats", "Your stats"),
            BotCommand("platforms", "Supported platforms"),
        ]
        await application.bot.set_my_commands(commands)
        
        bot = await application.bot.get_me()
        logger.info(f"Bot started: @{bot.username}")
        logger.info(f"Admin: {ADMIN_ID}")
        logger.info(f"Users: {len(data_manager.authorized_users)}")
        
        downloader.cleanup_old_files()
    except Exception as e:
        logger.error(f"Init error: {e}")

def main():
    """Main function"""
    
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
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("stats", stats_command))
        app.add_handler(CommandHandler("platforms", platforms_command))
        app.add_handler(CommandHandler("adduser", adduser_command))
        app.add_handler(CommandHandler("removeuser", removeuser_command))
        app.add_handler(CommandHandler("listusers", listusers_command))
        app.add_handler(CommandHandler("globalstats", globalstats_command))
        
        app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.Regex(r'https?://'),
            handle_url
        ))
        
        app.add_handler(CallbackQueryHandler(button_callback))
        app.add_error_handler(error_handler)
        
        # Run
        logger.info("✅ Starting polling mode")
        app.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
