#!/usr/bin/env python3
"""
Telegram Video Downloader Bot
================================
LEGAL DISCLAIMER: This bot is for downloading content you own or have permission to use.
Users must comply with all applicable laws and platform Terms of Service.

Requirements (requirements.txt):
python-telegram-bot==20.7
yt-dlp==2023.12.30
aiohttp==3.9.1
python-dotenv==1.0.0

Environment Variables Required:
- BOT_TOKEN: Your Telegram Bot Token from @BotFather
- ADMIN_ID: Your Telegram User ID (get from @userinfobot)
- WEBHOOK_URL: Your Render.com app URL (for production)
- PORT: Port number (Render provides this automatically)
"""

import os
import sys
import logging
import asyncio
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Set
from pathlib import Path

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

# Download library
import yt_dlp

# For async operations
import aiohttp

# Environment variables
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log')
    ]
)
logger = logging.getLogger(__name__)

# ==================== CONFIGURATION ====================

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))
WEBHOOK_URL = os.getenv('WEBHOOK_URL', '')
PORT = int(os.getenv('PORT', '8443'))

# File paths
AUTHORIZED_USERS_FILE = 'authorized_users.json'
STATS_FILE = 'stats.json'
DOWNLOADS_DIR = 'downloads'

# Telegram file size limit (50MB)
TELEGRAM_FILE_SIZE_LIMIT = 50 * 1024 * 1024

# Create downloads directory
Path(DOWNLOADS_DIR).mkdir(exist_ok=True)

# ==================== TERMS OF SERVICE ====================

TERMS_OF_SERVICE = """
📋 **TERMS OF SERVICE**

By using this bot, you acknowledge and agree:

✅ **Authorized Use Only:**
- You will ONLY download content you own or have explicit permission to download
- You will use downloaded content for personal/authorized editing purposes only

⚖️ **Legal Compliance:**
- You are solely responsible for complying with all applicable copyright laws
- You are responsible for complying with platform Terms of Service
- Downloading content from platforms may violate their ToS

🚫 **Prohibited Activities:**
- Downloading copyrighted content without permission
- Redistributing downloaded content without authorization
- Commercial use of downloaded content without proper rights

⚠️ **Liability Disclaimer:**
- This bot is provided "AS IS" for educational purposes
- The bot operator is not liable for any misuse
- Users assume all legal responsibility for their actions

📝 **Account Approval:**
- Access requires manual approval by the administrator
- Access may be revoked at any time for violations

**By using this bot, you accept these terms.**

Type /start to continue or /help for usage instructions.
"""

WELCOME_MESSAGE = """
🎬 **Video Downloader Bot**

Welcome! This bot helps you download videos from various platforms.

⚠️ **IMPORTANT:** Only download content you own or have permission to use!

📱 **Supported Platforms:**
YouTube, Instagram, Twitter/X, Facebook, TikTok, Reddit, Vimeo, Dailymotion, LinkedIn, Pinterest, and more!

🎯 **How to use:**
1. Send me a video URL
2. Select your preferred quality
3. Receive your video!

📊 **Features:**
• Multiple quality options (480p - 4K)
• Audio-only downloads
• File size preview
• Fast processing

Type /help for detailed instructions.

**Please read our Terms of Service before using.**
"""

HELP_MESSAGE = """
📖 **Help & Usage Guide**

**Basic Usage:**
1️⃣ Send any video URL from supported platforms
2️⃣ Wait for quality options to appear
3️⃣ Click on your preferred quality
4️⃣ Receive your video!

**Supported Platforms:**
• YouTube (videos, playlists, shorts)
• Instagram (reels, posts, IGTV, stories)
• Twitter/X (videos, GIFs)
• TikTok (videos)
• Facebook (public videos)
• Reddit (videos)
• Vimeo
• Dailymotion
• LinkedIn (videos)
• Pinterest (video pins)
• And many more!

**Available Commands:**
/start - Start the bot and see welcome message
/help - Show this help message
/terms - View Terms of Service
/stats - View your download statistics

**Admin Commands:**
/adduser <user_id> - Authorize a new user
/removeuser <user_id> - Remove user authorization
/listusers - List all authorized users
/broadcast <message> - Send message to all users
/globalstats - View global usage statistics

**Quality Options:**
The bot automatically detects available qualities:
• 4K (2160p) - If available
• 2K (1440p) - If available
• 1080p (Full HD)
• 720p (HD)
• 480p (SD)
• 360p (Low)
• Audio Only (MP3)

**File Size Limits:**
• Telegram allows files up to 50MB for bots
• Larger files will be compressed or upload will fail
• Consider using lower quality for long videos

**Tips:**
💡 Use audio-only for music videos to save size
💡 720p is a good balance between quality and file size
💡 Check file size before downloading

**Privacy & Legal:**
• We don't store your videos
• Files are deleted after sending
• You're responsible for legal compliance
• Read /terms for full legal disclaimer

**Need Help?**
Contact: @YourSupportUsername
"""

# ==================== DATA MANAGEMENT ====================

class DataManager:
    """Manages authorized users and statistics"""
    
    def __init__(self):
        self.authorized_users: Set[int] = self.load_authorized_users()
        self.stats: Dict = self.load_stats()
    
    def load_authorized_users(self) -> Set[int]:
        """Load authorized users from file"""
        try:
            if os.path.exists(AUTHORIZED_USERS_FILE):
                with open(AUTHORIZED_USERS_FILE, 'r') as f:
                    data = json.load(f)
                    return set(data.get('users', []))
            return {ADMIN_ID} if ADMIN_ID else set()
        except Exception as e:
            logger.error(f"Error loading authorized users: {e}")
            return {ADMIN_ID} if ADMIN_ID else set()
    
    def save_authorized_users(self):
        """Save authorized users to file"""
        try:
            with open(AUTHORIZED_USERS_FILE, 'w') as f:
                json.dump({'users': list(self.authorized_users)}, f)
        except Exception as e:
            logger.error(f"Error saving authorized users: {e}")
    
    def load_stats(self) -> Dict:
        """Load statistics from file"""
        try:
            if os.path.exists(STATS_FILE):
                with open(STATS_FILE, 'r') as f:
                    return json.load(f)
            return {
                'total_downloads': 0,
                'user_downloads': {},
                'platform_stats': {},
                'start_date': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error loading stats: {e}")
            return {'total_downloads': 0, 'user_downloads': {}, 'platform_stats': {}}
    
    def save_stats(self):
        """Save statistics to file"""
        try:
            with open(STATS_FILE, 'w') as f:
                json.dump(self.stats, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving stats: {e}")
    
    def add_user(self, user_id: int) -> bool:
        """Add a user to authorized list"""
        self.authorized_users.add(user_id)
        self.save_authorized_users()
        return True
    
    def remove_user(self, user_id: int) -> bool:
        """Remove a user from authorized list"""
        if user_id in self.authorized_users:
            self.authorized_users.remove(user_id)
            self.save_authorized_users()
            return True
        return False
    
    def is_authorized(self, user_id: int) -> bool:
        """Check if user is authorized"""
        return user_id in self.authorized_users
    
    def record_download(self, user_id: int, platform: str):
        """Record a download in statistics"""
        self.stats['total_downloads'] = self.stats.get('total_downloads', 0) + 1
        
        # User stats
        user_stats = self.stats.get('user_downloads', {})
        user_stats[str(user_id)] = user_stats.get(str(user_id), 0) + 1
        self.stats['user_downloads'] = user_stats
        
        # Platform stats
        platform_stats = self.stats.get('platform_stats', {})
        platform_stats[platform] = platform_stats.get(platform, 0) + 1
        self.stats['platform_stats'] = platform_stats
        
        self.save_stats()

# Initialize data manager
data_manager = DataManager()

# ==================== VIDEO DOWNLOADER ====================

class VideoDownloader:
    """Handles video downloading from various platforms"""
    
    def __init__(self):
        self.temp_dir = DOWNLOADS_DIR
    
    async def get_video_info(self, url: str) -> Optional[Dict]:
        """Extract video information without downloading"""
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
        
        try:
            loop = asyncio.get_event_loop()
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False))
                return info
        except Exception as e:
            logger.error(f"Error extracting video info: {e}")
            return None
    
    def format_bytes(self, bytes: Optional[int]) -> str:
        """Format bytes to human readable format"""
        if bytes is None:
            return "Unknown"
        
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes < 1024.0:
                return f"{bytes:.1f} {unit}"
            bytes /= 1024.0
        return f"{bytes:.1f} TB"
    
    def get_platform_name(self, url: str) -> str:
        """Detect platform from URL"""
        url_lower = url.lower()
        
        if 'youtube.com' in url_lower or 'youtu.be' in url_lower:
            return 'YouTube'
        elif 'instagram.com' in url_lower:
            return 'Instagram'
        elif 'twitter.com' in url_lower or 'x.com' in url_lower:
            return 'Twitter/X'
        elif 'tiktok.com' in url_lower:
            return 'TikTok'
        elif 'facebook.com' in url_lower or 'fb.watch' in url_lower:
            return 'Facebook'
        elif 'reddit.com' in url_lower:
            return 'Reddit'
        elif 'vimeo.com' in url_lower:
            return 'Vimeo'
        elif 'dailymotion.com' in url_lower:
            return 'Dailymotion'
        elif 'linkedin.com' in url_lower:
            return 'LinkedIn'
        elif 'pinterest.com' in url_lower:
            return 'Pinterest'
        else:
            return 'Unknown'
    
    async def get_formats(self, url: str) -> Optional[List[Dict]]:
        """Get available formats for a video"""
        info = await self.get_video_info(url)
        
        if not info:
            return None
        
        formats = []
        seen_qualities = set()
        
        # Get video formats
        if 'formats' in info:
            for f in info['formats']:
                # Skip formats without video
                if f.get('vcodec') == 'none':
                    continue
                
                height = f.get('height', 0)
                filesize = f.get('filesize') or f.get('filesize_approx', 0)
                ext = f.get('ext', 'mp4')
                format_id = f.get('format_id', '')
                
                if height and height not in seen_qualities:
                    seen_qualities.add(height)
                    
                    quality_label = self.get_quality_label(height)
                    
                    formats.append({
                        'format_id': format_id,
                        'quality': quality_label,
                        'height': height,
                        'filesize': filesize,
                        'ext': ext,
                        'type': 'video'
                    })
        
        # Add audio-only option
        formats.append({
            'format_id': 'bestaudio',
            'quality': 'Audio Only',
            'height': 0,
            'filesize': 0,
            'ext': 'mp3',
            'type': 'audio'
        })
        
        # Sort by height (quality)
        formats.sort(key=lambda x: x['height'], reverse=True)
        
        # Add video info
        for fmt in formats:
            fmt['title'] = info.get('title', 'video')
            fmt['duration'] = info.get('duration', 0)
            fmt['platform'] = self.get_platform_name(url)
        
        return formats
    
    def get_quality_label(self, height: int) -> str:
        """Convert height to quality label"""
        if height >= 2160:
            return '4K (2160p)'
        elif height >= 1440:
            return '2K (1440p)'
        elif height >= 1080:
            return '1080p (Full HD)'
        elif height >= 720:
            return '720p (HD)'
        elif height >= 480:
            return '480p (SD)'
        elif height >= 360:
            return '360p'
        else:
            return f'{height}p'
    
    async def download_video(self, url: str, format_id: str, progress_callback=None) -> Optional[str]:
        """Download video with specified format"""
        
        output_template = os.path.join(self.temp_dir, f'%(title)s_%(id)s.%(ext)s')
        
        ydl_opts = {
            'format': format_id if format_id != 'bestaudio' else 'bestaudio/best',
            'outtmpl': output_template,
            'quiet': True,
            'no_warnings': True,
        }
        
        # If audio only, extract audio
        if format_id == 'bestaudio':
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        
        try:
            loop = asyncio.get_event_loop()
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=True))
                
                # Get the downloaded file path
                if format_id == 'bestaudio':
                    filename = ydl.prepare_filename(info).rsplit('.', 1)[0] + '.mp3'
                else:
                    filename = ydl.prepare_filename(info)
                
                if os.path.exists(filename):
                    return filename
                else:
                    logger.error(f"Downloaded file not found: {filename}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error downloading video: {e}")
            return None
    
    def cleanup_file(self, filepath: str):
        """Delete downloaded file"""
        try:
            if filepath and os.path.exists(filepath):
                os.remove(filepath)
                logger.info(f"Cleaned up file: {filepath}")
        except Exception as e:
            logger.error(f"Error cleaning up file: {e}")

# Initialize downloader
downloader = VideoDownloader()

# ==================== TELEGRAM HANDLERS ====================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    user_id = user.id
    
    logger.info(f"User {user_id} ({user.username}) started the bot")
    
    # Check if user is authorized
    if not data_manager.is_authorized(user_id):
        await update.message.reply_text(
            f"⚠️ **Access Denied**\n\n"
            f"Your account is not authorized to use this bot.\n\n"
            f"**Your User ID:** `{user_id}`\n\n"
            f"Please contact the administrator to request access.\n\n"
            f"You must provide proof of content ownership/permission before access is granted.",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Notify admin of new user
        if ADMIN_ID:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"🔔 **New User Request**\n\n"
                     f"User: {user.mention_markdown()}\n"
                     f"ID: `{user_id}`\n"
                     f"Username: @{user.username}\n\n"
                     f"Use /adduser {user_id} to authorize.",
                parse_mode=ParseMode.MARKDOWN
            )
        return
    
    # Send welcome message with terms
    await update.message.reply_text(
        WELCOME_MESSAGE + "\n\n" + TERMS_OF_SERVICE,
        parse_mode=ParseMode.MARKDOWN
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    await update.message.reply_text(HELP_MESSAGE, parse_mode=ParseMode.MARKDOWN)

async def terms_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /terms command"""
    await update.message.reply_text(TERMS_OF_SERVICE, parse_mode=ParseMode.MARKDOWN)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command - show user's download statistics"""
    user_id = update.effective_user.id
    
    if not data_manager.is_authorized(user_id):
        await update.message.reply_text("⚠️ You are not authorized to use this bot.")
        return
    
    user_downloads = data_manager.stats.get('user_downloads', {}).get(str(user_id), 0)
    
    stats_text = f"📊 **Your Statistics**\n\n" \
                 f"Total Downloads: {user_downloads}\n\n" \
                 f"Thank you for using our service!"
    
    await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)

async def adduser_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /adduser command - Admin only"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("⚠️ This command is only available to administrators.")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /adduser <user_id>")
        return
    
    try:
        new_user_id = int(context.args[0])
        data_manager.add_user(new_user_id)
        
        await update.message.reply_text(f"✅ User {new_user_id} has been authorized!")
        
        # Notify the new user
        try:
            await context.bot.send_message(
                chat_id=new_user_id,
                text="🎉 **Access Granted!**\n\n"
                     "Your account has been authorized to use this bot.\n\n"
                     "Type /start to begin or /help for usage instructions.\n\n"
                     "Remember: Only download content you own or have permission to use!",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.warning(f"Could not notify user {new_user_id}: {e}")
            
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID. Please provide a numeric ID.")

async def removeuser_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /removeuser command - Admin only"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("⚠️ This command is only available to administrators.")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /removeuser <user_id>")
        return
    
    try:
        remove_user_id = int(context.args[0])
        
        if remove_user_id == ADMIN_ID:
            await update.message.reply_text("❌ Cannot remove the admin!")
            return
        
        if data_manager.remove_user(remove_user_id):
            await update.message.reply_text(f"✅ User {remove_user_id} has been removed from authorized users.")
        else:
            await update.message.reply_text(f"❌ User {remove_user_id} was not in the authorized list.")
            
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID. Please provide a numeric ID.")

async def listusers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /listusers command - Admin only"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("⚠️ This command is only available to administrators.")
        return
    
    users = data_manager.authorized_users
    
    if not users:
        await update.message.reply_text("📝 No authorized users yet.")
        return
    
    user_list = "\n".join([f"• `{uid}`" for uid in users])
    
    await update.message.reply_text(
        f"📝 **Authorized Users ({len(users)})**\n\n{user_list}",
        parse_mode=ParseMode.MARKDOWN
    )

async def globalstats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /globalstats command - Admin only"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("⚠️ This command is only available to administrators.")
        return
    
    stats = data_manager.stats
    total_downloads = stats.get('total_downloads', 0)
    total_users = len(data_manager.authorized_users)
    
    platform_stats = stats.get('platform_stats', {})
    platform_text = "\n".join([f"• {platform}: {count}" for platform, count in platform_stats.items()])
    
    if not platform_text:
        platform_text = "No downloads yet"
    
    stats_text = f"📊 **Global Statistics**\n\n" \
                 f"Total Downloads: {total_downloads}\n" \
                 f"Authorized Users: {total_users}\n\n" \
                 f"**Downloads by Platform:**\n{platform_text}"
    
    await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /broadcast command - Admin only"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("⚠️ This command is only available to administrators.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return
    
    message = " ".join(context.args)
    
    sent_count = 0
    failed_count = 0
    
    for uid in data_manager.authorized_users:
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=f"📢 **Broadcast Message**\n\n{message}",
                parse_mode=ParseMode.MARKDOWN
            )
            sent_count += 1
            await asyncio.sleep(0.1)  # Avoid rate limits
        except Exception as e:
            logger.error(f"Failed to send broadcast to {uid}: {e}")
            failed_count += 1
    
    await update.message.reply_text(
        f"✅ Broadcast complete!\n\n"
        f"Sent: {sent_count}\n"
        f"Failed: {failed_count}"
    )

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle video URL messages"""
    user_id = update.effective_user.id
    
    # Check authorization
    if not data_manager.is_authorized(user_id):
        await update.message.reply_text(
            "⚠️ You are not authorized to use this bot.\n\n"
            f"Your User ID: `{user_id}`\n\n"
            "Please contact the administrator for access.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    url = update.message.text.strip()
    
    # Basic URL validation
    if not url.startswith(('http://', 'https://')):
        await update.message.reply_text(
            "❌ Please send a valid URL starting with http:// or https://\n\n"
            "Type /help for usage instructions."
        )
        return
    
    # Send processing message
    processing_msg = await update.message.reply_text(
        "🔍 Analyzing video...\n\nPlease wait...",
        parse_mode=ParseMode.MARKDOWN
    )
    
    try:
        # Get available formats
        formats = await downloader.get_formats(url)
        
        if not formats:
            await processing_msg.edit_text(
                "❌ **Error**\n\n"
                "Could not extract video information. Please check:\n\n"
                "• URL is correct and accessible\n"
                "• Video is public (not private)\n"
                "• Platform is supported\n\n"
                "Type /help to see supported platforms.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Get video info
        video_title = formats[0].get('title', 'Video')
        platform = formats[0].get('platform', 'Unknown')
        
        # Create inline keyboard with quality options
        keyboard = []
        
        for fmt in formats:
            quality = fmt['quality']
            filesize = downloader.format_bytes(fmt['filesize'])
            
            button_text = f"{quality} - {filesize}"
            callback_data = f"dl_{fmt['format_id']}_{hash(url) % 10000}"
            
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        
        # Store URL in context for callback
        if 'user_data' not in context.bot_data:
            context.bot_data['user_data'] = {}
        
        if user_id not in context.bot_data['user_data']:
            context.bot_data['user_data'][user_id] = {}
        
        context.bot_data['user_data'][user_id]['url'] = url
        context.bot_data['user_data'][user_id]['platform'] = platform
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await processing_msg.edit_text(
            f"✅ **Video Found!**\n\n"
            f"📹 **Title:** {video_title[:100]}\n"
            f"🌐 **Platform:** {platform}\n\n"
            f"📊 **Select Quality:**",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Error handling URL: {e}")
        await processing_msg.edit_text(
            f"❌ **Error**\n\n"
            f"An error occurred while processing your request.\n\n"
            f"Error: {str(e)[:100]}\n\n"
            f"Please try again or contact support.",
            parse_mode=ParseMode.MARKDOWN
        )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks for quality selection"""
    query = update.callback_query
    user_id = query.from_user.id
    
    await query.answer()
    
    # Check authorization
    if not data_manager.is_authorized(user_id):
        await query.message.edit_text("⚠️ You are not authorized to use this bot.")
        return
    
    # Parse callback data
    callback_data = query.data
    
    if not callback_data.startswith('dl_'):
        return
    
    parts = callback_data.split('_')
    format_id = parts[1]
    
    # Get stored URL
    try:
        url = context.bot_data['user_data'][user_id]['url']
        platform = context.bot_data['user_data'][user_id]['platform']
    except (KeyError, TypeError):
        await query.message.edit_text(
            "❌ Session expired. Please send the URL again."
        )
        return
    
    # Update message
    await query.message.edit_text(
        "⬇️ **Downloading...**\n\n"
        "Please wait, this may take a few moments...",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Send typing action
    await context.bot.send_chat_action(chat_id=user_id, action=ChatAction.UPLOAD_VIDEO)
    
    try:
        # Download video
        filepath = await downloader.download_video(url, format_id)
        
        if not filepath:
            await query.message.edit_text(
                "❌ **Download Failed**\n\n"
                "Could not download the video. Please try:\n"
                "• Different quality option\n"
                "• Checking if the video is still available\n"
                "• Sending the URL again",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Check file size
        file_size = os.path.getsize(filepath)
        
        if file_size > TELEGRAM_FILE_SIZE_LIMIT:
            await query.message.edit_text(
                f"❌ **File Too Large**\n\n"
                f"File size: {downloader.format_bytes(file_size)}\n"
                f"Telegram limit: {downloader.format_bytes(TELEGRAM_FILE_SIZE_LIMIT)}\n\n"
                f"Please try a lower quality option.",
                parse_mode=ParseMode.MARKDOWN
            )
            downloader.cleanup_file(filepath)
            return
        
        # Send file
        await query.message.edit_text(
            "📤 **Uploading...**\n\nSending your file...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Determine file type
        is_audio = filepath.endswith('.mp3')
        
        if is_audio:
            with open(filepath, 'rb') as audio_file:
                await context.bot.send_audio(
                    chat_id=user_id,
                    audio=audio_file,
                    caption=f"🎵 Downloaded from {platform}",
                )
        else:
            with open(filepath, 'rb') as video_file:
                await context.bot.send_video(
                    chat_id=user_id,
                    video=video_file,
                    caption=f"🎬 Downloaded from {platform}",
                    supports_streaming=True
                )
        
        # Update statistics
        data_manager.record_download(user_id, platform)
        
        # Delete the download message
        await query.message.delete()
        
        # Send success message
        await context.bot.send_message(
            chat_id=user_id,
            text="✅ **Download Complete!**\n\n"
                 "Send another URL to download more videos!",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Cleanup file
        downloader.cleanup_file(filepath)
        
        logger.info(f"User {user_id} downloaded from {platform}")
        
    except Exception as e:
        logger.error(f"Error in download process: {e}")
        await query.message.edit_text(
            f"❌ **Error**\n\n"
            f"An error occurred during download.\n\n"
            f"Please try again or contact support.",
            parse_mode=ParseMode.MARKDOWN
        )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Update {update} caused error {context.error}")
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ An unexpected error occurred. Please try again later."
        )

# ==================== BOT INITIALIZATION ====================

async def post_init(application: Application):
    """Post initialization setup"""
    # Set bot commands
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("help", "Show help message"),
        BotCommand("terms", "View Terms of Service"),
        BotCommand("stats", "View your statistics"),
    ]
    
    await application.bot.set_my_commands(commands)
    
    logger.info("Bot initialized successfully")

def main():
    """Main function to run the bot"""
    
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not found in environment variables!")
        sys.exit(1)
    
    if not ADMIN_ID:
        logger.warning("ADMIN_ID not set! Bot will have limited functionality.")
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("terms", terms_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("adduser", adduser_command))
    application.add_handler(CommandHandler("removeuser", removeuser_command))
    application.add_handler(CommandHandler("listusers", listusers_command))
    application.add_handler(CommandHandler("globalstats", globalstats_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    
    # URL handler (any message that looks like a URL)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Regex(r'https?://'),
        handle_url
    ))
    
    # Callback query handler
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Error handler
    application.add_error_handler(error_handler)
    
    # Run bot
    if WEBHOOK_URL:
        # Production mode with webhook
        logger.info(f"Starting bot in webhook mode: {WEBHOOK_URL}")
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=BOT_TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}"
        )
    else:
        # Development mode with polling
        logger.info("Starting bot in polling mode")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
