#!/usr/bin/env python3
"""
Telegram Video Downloader Bot - Complete Single File Version
=============================================================

REQUIREMENTS (requirements.txt):
--------------------------------
python-telegram-bot==20.7
yt-dlp==2023.12.30
aiohttp==3.9.1

DEPLOYMENT ON RENDER.COM:
------------------------
1. Create new Web Service
2. Connect GitHub repository
3. Build Command: pip install -r requirements.txt
4. Start Command: python bot.py
5. Add Environment Variable: PORT (Render provides this automatically)

That's it! The bot will start automatically.

LEGAL DISCLAIMER:
-----------------
This bot is for downloading content you own or have permission to use.
Users must comply with all applicable laws and platform Terms of Service.
"""

import os
import sys
import logging
import asyncio
import json
import time
import re
import shutil
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
from telegram.error import TelegramError, NetworkError, BadRequest

# Download library
import yt_dlp

# For async operations
import aiohttp

# ==================== CONFIGURATION ====================

# Bot Configuration (Hardcoded - Your Credentials)
BOT_TOKEN = "8367293218:AAF7VsjU0jkzoU8DLd1kX75Kr73hXrKiq94"
ADMIN_ID = 8175884349
WEBHOOK_URL = "https://telegram-download.onrender.com"

# Get PORT from environment (Render provides this) or use default
PORT = int(os.getenv('PORT', '10000'))

# File paths
AUTHORIZED_USERS_FILE = 'authorized_users.json'
STATS_FILE = 'stats.json'
DOWNLOADS_DIR = 'downloads'

# Telegram file size limit (50MB)
TELEGRAM_FILE_SIZE_LIMIT = 50 * 1024 * 1024

# Create downloads directory
Path(DOWNLOADS_DIR).mkdir(exist_ok=True)

# ==================== LOGGING SETUP ====================

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Reduce verbose logging from libraries
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('telegram').setLevel(logging.WARNING)
logging.getLogger('yt_dlp').setLevel(logging.WARNING)

# ==================== TERMS AND MESSAGES ====================

TERMS_OF_SERVICE = """
📋 **TERMS OF SERVICE**

By using this bot, you acknowledge and agree:

✅ **Authorized Use Only:**
• You will ONLY download content you own or have explicit permission to download
• You will use downloaded content for personal/authorized editing purposes only

⚖️ **Legal Compliance:**
• You are solely responsible for complying with all applicable copyright laws
• You are responsible for complying with platform Terms of Service
• Downloading content from platforms may violate their ToS

🚫 **Prohibited Activities:**
• Downloading copyrighted content without permission
• Redistributing downloaded content without authorization
• Commercial use of downloaded content without proper rights

⚠️ **Liability Disclaimer:**
• This bot is provided "AS IS" for educational purposes
• The bot operator is not liable for any misuse
• Users assume all legal responsibility for their actions

📝 **Account Approval:**
• Access requires manual approval by the administrator
• Access may be revoked at any time for violations

**By using this bot, you accept these terms.**
"""

WELCOME_MESSAGE = """
🎬 **Welcome to Video Downloader Bot!**

Hello! I can help you download videos from multiple platforms.

⚠️ **IMPORTANT:** Only download content you own or have permission to use!

🌐 **Supported Platforms:**
• YouTube (Videos, Shorts, Playlists)
• Instagram (Reels, Posts, Stories, IGTV)
• Twitter/X (Videos, GIFs)
• TikTok (Videos)
• Facebook (Public Videos)
• Reddit (Videos)
• Vimeo
• Dailymotion
• LinkedIn (Videos)
• Pinterest (Video Pins)
• Twitch (Clips, VODs)
• And 1000+ more sites!

📋 **Quick Start:**
1. Send me any video URL
2. Choose your preferred quality
3. Get your video instantly!

🎯 **Features:**
✓ Multiple quality options (480p - 4K)
✓ Audio-only downloads (MP3)
✓ File size preview
✓ Fast processing
✓ Progress tracking

Type /help for detailed instructions or just send a video URL to start!
"""

HELP_MESSAGE = """
📖 **Complete Usage Guide**

**🎯 How to Download Videos:**

1️⃣ **Send a Video URL**
   Just paste any video link from supported platforms

2️⃣ **Select Quality**
   Choose from available quality options:
   • 4K (2160p) - Ultra HD
   • 2K (1440p) - Quad HD
   • 1080p - Full HD
   • 720p - HD
   • 480p - SD
   • 360p - Low quality
   • Audio Only - MP3 format

3️⃣ **Download**
   The bot will download and send your video!

**🌐 Supported Platforms:**

📱 **Social Media:**
• Instagram - Reels, Posts, Stories, IGTV
• TikTok - All public videos
• Twitter/X - Videos and GIFs
• Facebook - Public videos
• LinkedIn - Video posts
• Pinterest - Video pins

🎥 **Video Platforms:**
• YouTube - Videos, Shorts, Live streams
• Vimeo - All public videos
• Dailymotion - Public videos
• Twitch - Clips and VODs
• Streamable - All videos

💬 **Forums & Others:**
• Reddit - Video posts
• Imgur - Video posts
• And 1000+ more sites!

**📋 Available Commands:**

**User Commands:**
/start - Start the bot
/help - Show this help message
/terms - View Terms of Service
/stats - Your download statistics
/platforms - List all supported platforms

**Admin Commands:**
/adduser <user_id> - Authorize a user
/removeuser <user_id> - Remove user access
/listusers - Show all authorized users
/globalstats - View global statistics
/broadcast <message> - Send message to all users
/cleanup - Clean old downloaded files

**💡 Pro Tips:**

🎵 **For Music Videos:**
   Use "Audio Only" option to save space and get MP3

📏 **For Long Videos:**
   Choose 480p or 720p to stay under Telegram's 50MB limit

⚡ **For Best Quality:**
   Select the highest available resolution (4K/1080p)

🔄 **If Download Fails:**
   • Try a different quality option
   • Make sure the video is public
   • Check if the URL is correct
   • Wait a moment and try again

**📊 File Size Guide:**

Approximate sizes for a 5-minute video:
• 4K: ~500MB+ (too large for Telegram)
• 1080p: ~150MB (may be too large)
• 720p: ~50-80MB (recommended)
• 480p: ~25-40MB (safe choice)
• Audio: ~5-10MB (smallest)

**🔒 Privacy & Security:**

✓ Videos are processed temporarily
✓ Files are deleted after sending
✓ We don't store your content
✓ Your privacy is protected

**⚖️ Legal Notice:**

This bot is for downloading content you own or have permission to use.
You are responsible for complying with all applicable laws and platform Terms of Service.

**❓ Need Help?**

If you encounter any issues:
• Check if the video is publicly accessible
• Try a different quality option
• Make sure your account is authorized
• Contact admin if problem persists

**Let's get started! Send me a video URL! 🚀**
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
                    users = set(data.get('users', []))
                    # Always include admin
                    users.add(ADMIN_ID)
                    return users
            return {ADMIN_ID}
        except Exception as e:
            logger.error(f"Error loading authorized users: {e}")
            return {ADMIN_ID}
    
    def save_authorized_users(self):
        """Save authorized users to file"""
        try:
            with open(AUTHORIZED_USERS_FILE, 'w') as f:
                json.dump({'users': list(self.authorized_users)}, f, indent=2)
            logger.info(f"Saved {len(self.authorized_users)} authorized users")
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
                'quality_stats': {},
                'start_date': datetime.now().isoformat(),
                'last_updated': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error loading stats: {e}")
            return {
                'total_downloads': 0,
                'user_downloads': {},
                'platform_stats': {},
                'quality_stats': {}
            }
    
    def save_stats(self):
        """Save statistics to file"""
        try:
            self.stats['last_updated'] = datetime.now().isoformat()
            with open(STATS_FILE, 'w') as f:
                json.dump(self.stats, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving stats: {e}")
    
    def add_user(self, user_id: int) -> bool:
        """Add a user to authorized list"""
        self.authorized_users.add(user_id)
        self.save_authorized_users()
        logger.info(f"Added user {user_id} to authorized list")
        return True
    
    def remove_user(self, user_id: int) -> bool:
        """Remove a user from authorized list"""
        if user_id == ADMIN_ID:
            return False  # Cannot remove admin
        if user_id in self.authorized_users:
            self.authorized_users.remove(user_id)
            self.save_authorized_users()
            logger.info(f"Removed user {user_id} from authorized list")
            return True
        return False
    
    def is_authorized(self, user_id: int) -> bool:
        """Check if user is authorized"""
        return user_id in self.authorized_users
    
    def record_download(self, user_id: int, platform: str, quality: str = 'unknown'):
        """Record a download in statistics"""
        # Total downloads
        self.stats['total_downloads'] = self.stats.get('total_downloads', 0) + 1
        
        # User stats
        user_stats = self.stats.get('user_downloads', {})
        user_stats[str(user_id)] = user_stats.get(str(user_id), 0) + 1
        self.stats['user_downloads'] = user_stats
        
        # Platform stats
        platform_stats = self.stats.get('platform_stats', {})
        platform_stats[platform] = platform_stats.get(platform, 0) + 1
        self.stats['platform_stats'] = platform_stats
        
        # Quality stats
        quality_stats = self.stats.get('quality_stats', {})
        quality_stats[quality] = quality_stats.get(quality, 0) + 1
        self.stats['quality_stats'] = quality_stats
        
        self.save_stats()
        logger.info(f"Recorded download: User {user_id}, Platform {platform}, Quality {quality}")

# Initialize data manager
data_manager = DataManager()

# ==================== VIDEO DOWNLOADER ====================

class VideoDownloader:
    """Handles video downloading from various platforms using yt-dlp"""
    
    def __init__(self):
        self.temp_dir = DOWNLOADS_DIR
        
        # Cookie file for authentication (if needed)
        self.cookies_file = None
    
    async def get_video_info(self, url: str) -> Optional[Dict]:
        """Extract video information without downloading"""
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'socket_timeout': 30,
            'retries': 3,
        }
        
        try:
            loop = asyncio.get_event_loop()
            
            def extract_info():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(url, download=False)
            
            info = await loop.run_in_executor(None, extract_info)
            return info
            
        except Exception as e:
            logger.error(f"Error extracting video info from {url}: {e}")
            return None
    
    def format_bytes(self, bytes_size: Optional[int]) -> str:
        """Format bytes to human readable format"""
        if bytes_size is None or bytes_size == 0:
            return "Unknown"
        
        bytes_float = float(bytes_size)
        
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_float < 1024.0:
                return f"{bytes_float:.1f} {unit}"
            bytes_float /= 1024.0
        return f"{bytes_float:.1f} TB"
    
    def format_duration(self, seconds: Optional[int]) -> str:
        """Format duration in seconds to human readable format"""
        if not seconds:
            return "Unknown"
        
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"
    
    def get_platform_name(self, url: str, info: Dict = None) -> str:
        """Detect platform from URL or info"""
        
        if info:
            extractor = info.get('extractor', '').lower()
            extractor_key = info.get('extractor_key', '').lower()
            
            # Map extractors to friendly names
            platform_map = {
                'youtube': 'YouTube',
                'instagram': 'Instagram',
                'twitter': 'Twitter/X',
                'tiktok': 'TikTok',
                'facebook': 'Facebook',
                'reddit': 'Reddit',
                'vimeo': 'Vimeo',
                'dailymotion': 'Dailymotion',
                'linkedin': 'LinkedIn',
                'pinterest': 'Pinterest',
                'twitch': 'Twitch',
                'streamable': 'Streamable',
            }
            
            for key, name in platform_map.items():
                if key in extractor or key in extractor_key:
                    return name
        
        # Fallback to URL parsing
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
        elif 'twitch.tv' in url_lower:
            return 'Twitch'
        
        return 'Unknown Platform'
    
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
        elif height >= 240:
            return '240p'
        else:
            return f'{height}p'
    
    async def get_formats(self, url: str) -> Optional[List[Dict]]:
        """Get available formats for a video"""
        
        info = await self.get_video_info(url)
        
        if not info:
            return None
        
        formats = []
        seen_qualities = set()
        
        # Get video+audio combined formats first (preferred)
        if 'formats' in info:
            for f in info['formats']:
                # Skip audio-only or video-only if combined formats exist
                vcodec = f.get('vcodec', 'none')
                acodec = f.get('acodec', 'none')
                
                # We want formats with both video and audio
                if vcodec != 'none' and acodec != 'none':
                    height = f.get('height', 0)
                    filesize = f.get('filesize') or f.get('filesize_approx', 0)
                    ext = f.get('ext', 'mp4')
                    format_id = f.get('format_id', '')
                    fps = f.get('fps', 0)
                    
                    if height and height >= 240:  # Minimum quality
                        quality_key = (height, fps)
                        if quality_key not in seen_qualities:
                            seen_qualities.add(quality_key)
                            
                            quality_label = self.get_quality_label(height)
                            if fps and fps > 30:
                                quality_label += f" ({fps}fps)"
                            
                            formats.append({
                                'format_id': format_id,
                                'quality': quality_label,
                                'height': height,
                                'filesize': filesize,
                                'ext': ext,
                                'type': 'video',
                                'fps': fps
                            })
        
        # If no combined formats, try video-only + audio combinations
        if len(formats) < 3:
            # Get best video-only formats
            video_formats = []
            if 'formats' in info:
                for f in info['formats']:
                    if f.get('vcodec', 'none') != 'none' and f.get('acodec', 'none') == 'none':
                        height = f.get('height', 0)
                        if height and height >= 240:
                            video_formats.append({
                                'height': height,
                                'format_id': f.get('format_id', ''),
                                'filesize': f.get('filesize') or f.get('filesize_approx', 0),
                                'ext': f.get('ext', 'mp4'),
                                'fps': f.get('fps', 0)
                            })
            
            # Add unique video formats
            for vf in video_formats:
                height = vf['height']
                quality_key = (height, vf['fps'])
                if quality_key not in seen_qualities:
                    seen_qualities.add(quality_key)
                    
                    quality_label = self.get_quality_label(height)
                    if vf['fps'] and vf['fps'] > 30:
                        quality_label += f" ({vf['fps']}fps)"
                    
                    # Use bestvideo[height=X]+bestaudio format
                    format_id = f"bestvideo[height={height}]+bestaudio/best[height={height}]"
                    
                    formats.append({
                        'format_id': format_id,
                        'quality': quality_label,
                        'height': height,
                        'filesize': vf['filesize'],
                        'ext': vf['ext'],
                        'type': 'video',
                        'fps': vf['fps']
                    })
        
        # Add default quality options if nothing found
        if not formats:
            formats.append({
                'format_id': 'best',
                'quality': 'Best Available',
                'height': 99999,
                'filesize': 0,
                'ext': 'mp4',
                'type': 'video',
                'fps': 0
            })
        
        # Add audio-only option
        formats.append({
            'format_id': 'bestaudio',
            'quality': '🎵 Audio Only (MP3)',
            'height': 0,
            'filesize': 0,
            'ext': 'mp3',
            'type': 'audio',
            'fps': 0
        })
        
        # Sort by height (quality) - highest first
        formats.sort(key=lambda x: (x['height'], x.get('fps', 0)), reverse=True)
        
        # Add video metadata to all formats
        platform = self.get_platform_name(url, info)
        title = info.get('title', 'Video')
        duration = info.get('duration', 0)
        
        for fmt in formats:
            fmt['title'] = title
            fmt['duration'] = duration
            fmt['platform'] = platform
            fmt['url'] = url
        
        return formats
    
    async def download_video(self, url: str, format_id: str, quality_label: str = 'unknown') -> Optional[str]:
        """Download video with specified format"""
        
        # Generate unique filename
        timestamp = int(time.time())
        output_template = os.path.join(self.temp_dir, f'video_{timestamp}_%(id)s.%(ext)s')
        
        ydl_opts = {
            'format': format_id,
            'outtmpl': output_template,
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': 30,
            'retries': 3,
            'fragment_retries': 3,
            'http_chunk_size': 10485760,  # 10MB chunks
        }
        
        # If audio only, extract and convert to MP3
        if format_id == 'bestaudio' or 'audio' in quality_label.lower():
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        
        # For video, merge formats if needed
        elif '+' in format_id or 'bestvideo' in format_id:
            ydl_opts['merge_output_format'] = 'mp4'
        
        try:
            loop = asyncio.get_event_loop()
            
            def download():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    
                    # Get the actual downloaded filename
                    if format_id == 'bestaudio' or 'audio' in quality_label.lower():
                        # For audio, the extension will be changed to mp3
                        base_filename = ydl.prepare_filename(info)
                        filename = base_filename.rsplit('.', 1)[0] + '.mp3'
                    else:
                        filename = ydl.prepare_filename(info)
                    
                    return filename
            
            filename = await loop.run_in_executor(None, download)
            
            # Verify file exists
            if filename and os.path.exists(filename):
                logger.info(f"Successfully downloaded: {filename} ({self.format_bytes(os.path.getsize(filename))})")
                return filename
            else:
                logger.error(f"Downloaded file not found: {filename}")
                return None
                
        except Exception as e:
            logger.error(f"Error downloading video from {url}: {e}")
            return None
    
    def cleanup_file(self, filepath: str):
        """Delete downloaded file"""
        try:
            if filepath and os.path.exists(filepath):
                os.remove(filepath)
                logger.info(f"Cleaned up file: {filepath}")
        except Exception as e:
            logger.error(f"Error cleaning up file {filepath}: {e}")
    
    def cleanup_old_files(self, max_age_hours: int = 1):
        """Clean up old downloaded files"""
        try:
            now = time.time()
            max_age_seconds = max_age_hours * 3600
            
            deleted_count = 0
            for filename in os.listdir(self.temp_dir):
                filepath = os.path.join(self.temp_dir, filename)
                
                if os.path.isfile(filepath):
                    file_age = now - os.path.getmtime(filepath)
                    
                    if file_age > max_age_seconds:
                        os.remove(filepath)
                        deleted_count += 1
                        logger.info(f"Deleted old file: {filename}")
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old files")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error cleaning up old files: {e}")
            return 0

# Initialize downloader
downloader = VideoDownloader()

# ==================== UTILITY FUNCTIONS ====================

def is_valid_url(url: str) -> bool:
    """Check if string is a valid URL"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False

def extract_user_id(text: str) -> Optional[int]:
    """Extract user ID from text"""
    try:
        # Try to find a number in the text
        numbers = re.findall(r'\d+', text)
        if numbers:
            return int(numbers[0])
    except Exception:
        pass
    return None

# ==================== TELEGRAM COMMAND HANDLERS ====================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    user_id = user.id
    
    logger.info(f"User {user_id} (@{user.username}) started the bot")
    
    # Check if user is authorized
    if not data_manager.is_authorized(user_id):
        await update.message.reply_text(
            f"⚠️ **Access Denied**\n\n"
            f"Your account is not authorized to use this bot.\n\n"
            f"**Your User ID:** `{user_id}`\n"
            f"**Username:** @{user.username or 'N/A'}\n\n"
            f"Please contact the administrator to request access.\n\n"
            f"📋 **Requirements for Access:**\n"
            f"• Proof of content ownership/permission\n"
            f"• Agreement to Terms of Service\n"
            f"• Valid reason for using the bot\n\n"
            f"The administrator will review your request.",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Notify admin of new user request
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"🔔 **New User Access Request**\n\n"
                     f"👤 **User Info:**\n"
                     f"• Name: {user.full_name}\n"
                     f"• Username: @{user.username or 'N/A'}\n"
                     f"• User ID: `{user_id}`\n"
                     f"• Language: {user.language_code or 'N/A'}\n\n"
                     f"**Action Required:**\n"
                     f"To authorize: `/adduser {user_id}`\n"
                     f"To ignore: Do nothing",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Could not notify admin about new user {user_id}: {e}")
        
        return
    
    # User is authorized - send welcome message
    welcome_text = f"👋 **Hello {user.first_name}!**\n\n" + WELCOME_MESSAGE
    
    await update.message.reply_text(
        welcome_text,
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Show terms after welcome
    await asyncio.sleep(1)
    await update.message.reply_text(
        TERMS_OF_SERVICE,
        parse_mode=ParseMode.MARKDOWN
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    await update.message.reply_text(
        HELP_MESSAGE,
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True
    )

async def terms_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /terms command"""
    await update.message.reply_text(
        TERMS_OF_SERVICE,
        parse_mode=ParseMode.MARKDOWN
    )

async def platforms_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /platforms command - show supported platforms"""
    
    platforms_text = """
🌐 **Supported Platforms (1000+ sites)**

**📱 Social Media:**
• Instagram (Reels, Posts, Stories, IGTV)
• TikTok (All public videos)
• Twitter/X (Videos, GIFs)
• Facebook (Public videos)
• LinkedIn (Video posts)
• Pinterest (Video pins)
• Snapchat (Public stories)

**🎥 Video Platforms:**
• YouTube (Videos, Shorts, Live)
• Vimeo (Public videos)
• Dailymotion (All videos)
• Twitch (Clips, VODs)
• Streamable
• Vidio
• Rumble

**💬 Forums & Communities:**
• Reddit (Video posts, v.redd.it)
• Imgur (Videos, GIFs)
• 9GAG (Videos)
• Tumblr (Videos)

**🎓 Educational:**
• Coursera (If authorized)
• Udemy (If authorized)
• Khan Academy

**📺 Streaming:**
• Twitch (Clips, VODs)
• DLive
• Trovo

**🎬 Entertainment:**
• SoundCloud (Audio)
• Mixcloud (Audio)
• Bandcamp (Audio/Video)
• Spotify (If authorized)

**🌏 Regional Platforms:**
• Bilibili (China)
• Niconico (Japan)
• VK (Russia)
• OK.ru (Russia)
• Youku (China)

**And 1000+ more websites!**

Just send any video URL and I'll try to download it! 🚀

**Not sure if a site is supported?**
Just try sending the URL - I'll let you know if it works!
"""
    
    await update.message.reply_text(
        platforms_text,
        parse_mode=ParseMode.MARKDOWN
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command - show user's download statistics"""
    user_id = update.effective_user.id
    
    if not data_manager.is_authorized(user_id):
        await update.message.reply_text("⚠️ You are not authorized to use this bot.")
        return
    
    user_downloads = data_manager.stats.get('user_downloads', {}).get(str(user_id), 0)
    total_downloads = data_manager.stats.get('total_downloads', 0)
    
    # Calculate user's percentage
    if total_downloads > 0:
        percentage = (user_downloads / total_downloads) * 100
    else:
        percentage = 0
    
    stats_text = (
        f"📊 **Your Download Statistics**\n\n"
        f"🎬 **Your Downloads:** {user_downloads}\n"
        f"🌐 **Total Downloads:** {total_downloads}\n"
        f"📈 **Your Share:** {percentage:.1f}%\n\n"
        f"Thank you for using our service! 🙏"
    )
    
    await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)

# ==================== ADMIN COMMANDS ====================

async def adduser_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /adduser command - Admin only"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("⚠️ This command is only available to administrators.")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text(
            "❌ **Invalid Usage**\n\n"
            "**Correct usage:** `/adduser <user_id>`\n\n"
            "**Example:** `/adduser 123456789`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    try:
        new_user_id = int(context.args[0])
        
        if data_manager.is_authorized(new_user_id):
            await update.message.reply_text(
                f"ℹ️ User `{new_user_id}` is already authorized!",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        data_manager.add_user(new_user_id)
        
        await update.message.reply_text(
            f"✅ **User Authorized!**\n\n"
            f"User ID: `{new_user_id}`\n\n"
            f"The user can now use the bot.",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Notify the new user
        try:
            await context.bot.send_message(
                chat_id=new_user_id,
                text="🎉 **Access Granted!**\n\n"
                     "Your account has been authorized to use the Video Downloader Bot!\n\n"
                     "🚀 **Get Started:**\n"
                     "• Type /start to see welcome message\n"
                     "• Type /help for usage instructions\n"
                     "• Send any video URL to start downloading\n\n"
                     "⚠️ **Remember:**\n"
                     "Only download content you own or have permission to use!\n\n"
                     "Enjoy! 🎬",
                parse_mode=ParseMode.MARKDOWN
            )
            logger.info(f"Notified user {new_user_id} about authorization")
        except Exception as e:
            logger.warning(f"Could not notify user {new_user_id}: {e}")
            await update.message.reply_text(
                f"⚠️ User authorized but could not send notification.\n"
                f"The user needs to start a chat with the bot first.",
                parse_mode=ParseMode.MARKDOWN
            )
            
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid user ID. Please provide a numeric ID.",
            parse_mode=ParseMode.MARKDOWN
        )

async def removeuser_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /removeuser command - Admin only"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("⚠️ This command is only available to administrators.")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text(
            "❌ **Invalid Usage**\n\n"
            "**Correct usage:** `/removeuser <user_id>`\n\n"
            "**Example:** `/removeuser 123456789`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    try:
        remove_user_id = int(context.args[0])
        
        if remove_user_id == ADMIN_ID:
            await update.message.reply_text(
                "❌ Cannot remove the administrator!",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        if data_manager.remove_user(remove_user_id):
            await update.message.reply_text(
                f"✅ **User Removed**\n\n"
                f"User ID: `{remove_user_id}`\n\n"
                f"This user can no longer use the bot.",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Try to notify the user
            try:
                await context.bot.send_message(
                    chat_id=remove_user_id,
                    text="⚠️ **Access Revoked**\n\n"
                         "Your access to the Video Downloader Bot has been removed.\n\n"
                         "If you believe this is an error, please contact the administrator.",
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception:
                pass  # User might have blocked the bot
                
        else:
            await update.message.reply_text(
                f"❌ User `{remove_user_id}` was not in the authorized list.",
                parse_mode=ParseMode.MARKDOWN
            )
            
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid user ID. Please provide a numeric ID.",
            parse_mode=ParseMode.MARKDOWN
        )

async def listusers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /listusers command - Admin only"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("⚠️ This command is only available to administrators.")
        return
    
    users = sorted(data_manager.authorized_users)
    
    if not users:
        await update.message.reply_text("📝 No authorized users yet.")
        return
    
    # Split into chunks if too many users
    chunk_size = 50
    user_chunks = [users[i:i + chunk_size] for i in range(0, len(users), chunk_size)]
    
    for idx, chunk in enumerate(user_chunks):
        user_list = "\n".join([
            f"{'👑' if uid == ADMIN_ID else '👤'} `{uid}`"
            for uid in chunk
        ])
        
        header = f"📝 **Authorized Users ({len(users)} total)**"
        if len(user_chunks) > 1:
            header += f" - Page {idx + 1}/{len(user_chunks)}"
        
        await update.message.reply_text(
            f"{header}\n\n{user_list}",
            parse_mode=ParseMode.MARKDOWN
        )
        
        if idx < len(user_chunks) - 1:
            await asyncio.sleep(0.5)  # Small delay between messages

async def globalstats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /globalstats command - Admin only"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("⚠️ This command is only available to administrators.")
        return
    
    stats = data_manager.stats
    total_downloads = stats.get('total_downloads', 0)
    total_users = len(data_manager.authorized_users)
    
    # Platform statistics
    platform_stats = stats.get('platform_stats', {})
    if platform_stats:
        sorted_platforms = sorted(platform_stats.items(), key=lambda x: x[1], reverse=True)
        platform_text = "\n".join([
            f"• {platform}: {count}"
            for platform, count in sorted_platforms[:10]
        ])
    else:
        platform_text = "No downloads yet"
    
    # Quality statistics
    quality_stats = stats.get('quality_stats', {})
    if quality_stats:
        sorted_qualities = sorted(quality_stats.items(), key=lambda x: x[1], reverse=True)
        quality_text = "\n".join([
            f"• {quality}: {count}"
            for quality, count in sorted_qualities[:5]
        ])
    else:
        quality_text = "No data"
    
    # Top users
    user_downloads = stats.get('user_downloads', {})
    if user_downloads:
        sorted_users = sorted(user_downloads.items(), key=lambda x: x[1], reverse=True)
        top_users_text = "\n".join([
            f"• User `{uid}`: {count} downloads"
            for uid, count in sorted_users[:5]
        ])
    else:
        top_users_text = "No downloads yet"
    
    # Start date
    start_date = stats.get('start_date', 'Unknown')
    if start_date != 'Unknown':
        try:
            start_dt = datetime.fromisoformat(start_date)
            days_running = (datetime.now() - start_dt).days
            start_date_str = start_dt.strftime('%Y-%m-%d')
        except:
            start_date_str = start_date
            days_running = 0
    else:
        start_date_str = 'Unknown'
        days_running = 0
    
    stats_text = (
        f"📊 **Global Bot Statistics**\n\n"
        f"📅 **Running Since:** {start_date_str}\n"
        f"⏱️ **Days Active:** {days_running}\n\n"
        f"🎬 **Total Downloads:** {total_downloads}\n"
        f"👥 **Authorized Users:** {total_users}\n"
        f"📈 **Avg per User:** {total_downloads / total_users if total_users > 0 else 0:.1f}\n\n"
        f"🌐 **Top Platforms:**\n{platform_text}\n\n"
        f"📊 **Popular Qualities:**\n{quality_text}\n\n"
        f"👑 **Top Users:**\n{top_users_text}"
    )
    
    await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /broadcast command - Admin only"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("⚠️ This command is only available to administrators.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ **Invalid Usage**\n\n"
            "**Correct usage:** `/broadcast <message>`\n\n"
            "**Example:** `/broadcast Important update: Bot will be down for maintenance`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    message = " ".join(context.args)
    
    # Confirm broadcast
    confirm_text = (
        f"📢 **Confirm Broadcast**\n\n"
        f"**Message:**\n{message}\n\n"
        f"**Recipients:** {len(data_manager.authorized_users)} users\n\n"
        f"Send /confirm to proceed or /cancel to abort."
    )
    
    await update.message.reply_text(confirm_text, parse_mode=ParseMode.MARKDOWN)
    
    # Store broadcast message in context
    context.user_data['pending_broadcast'] = message

async def confirm_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /confirm command for broadcast"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        return
    
    if 'pending_broadcast' not in context.user_data:
        await update.message.reply_text("❌ No pending broadcast to confirm.")
        return
    
    message = context.user_data['pending_broadcast']
    
    sent_count = 0
    failed_count = 0
    
    status_msg = await update.message.reply_text("📤 **Broadcasting...**\n\nPlease wait...")
    
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
    
    # Clear pending broadcast
    del context.user_data['pending_broadcast']
    
    await status_msg.edit_text(
        f"✅ **Broadcast Complete!**\n\n"
        f"📤 **Sent:** {sent_count}\n"
        f"❌ **Failed:** {failed_count}\n"
        f"📊 **Success Rate:** {sent_count / (sent_count + failed_count) * 100 if (sent_count + failed_count) > 0 else 0:.1f}%"
    )

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cancel command"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        return
    
    if 'pending_broadcast' in context.user_data:
        del context.user_data['pending_broadcast']
        await update.message.reply_text("✅ Broadcast cancelled.")
    else:
        await update.message.reply_text("❌ Nothing to cancel.")

async def cleanup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cleanup command - Admin only"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("⚠️ This command is only available to administrators.")
        return
    
    status_msg = await update.message.reply_text("🧹 Cleaning up old files...")
    
    deleted_count = downloader.cleanup_old_files(max_age_hours=1)
    
    await status_msg.edit_text(
        f"✅ **Cleanup Complete!**\n\n"
        f"🗑️ Deleted {deleted_count} old file(s)"
    )

# ==================== URL HANDLER ====================

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle video URL messages"""
    user_id = update.effective_user.id
    user = update.effective_user
    
    # Check authorization
    if not data_manager.is_authorized(user_id):
        await update.message.reply_text(
            f"⚠️ **Access Denied**\n\n"
            f"You are not authorized to use this bot.\n\n"
            f"**Your User ID:** `{user_id}`\n\n"
            f"Please contact the administrator for access.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    url = update.message.text.strip()
    
    # Validate URL
    if not is_valid_url(url):
        await update.message.reply_text(
            "❌ **Invalid URL**\n\n"
            "Please send a valid URL starting with http:// or https://\n\n"
            "Type /help for usage instructions.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Send processing message
    processing_msg = await update.message.reply_text(
        "🔍 **Analyzing video...**\n\n"
        "Please wait while I fetch video information...",
        parse_mode=ParseMode.MARKDOWN
    )
    
    try:
        # Send typing action
        await context.bot.send_chat_action(chat_id=user_id, action=ChatAction.TYPING)
        
        # Get available formats
        formats = await downloader.get_formats(url)
        
        if not formats:
            await processing_msg.edit_text(
                "❌ **Error Fetching Video**\n\n"
                "Could not extract video information. Please check:\n\n"
                "✓ URL is correct and accessible\n"
                "✓ Video is public (not private)\n"
                "✓ Platform is supported\n"
                "✓ Video still exists\n\n"
                "Type /help to see supported platforms or try another URL.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Get video info from first format
        video_title = formats[0].get('title', 'Video')[:100]
        platform = formats[0].get('platform', 'Unknown')
        duration = formats[0].get('duration', 0)
        
        # Create inline keyboard with quality options
        keyboard = []
        
        for fmt in formats:
            quality = fmt['quality']
            filesize = fmt['filesize']
            
            # Format button text
            if filesize and filesize > 0:
                size_str = downloader.format_bytes(filesize)
                button_text = f"{quality} ({size_str})"
                
                # Warn if file might be too large
                if filesize > TELEGRAM_FILE_SIZE_LIMIT:
                    button_text += " ⚠️"
            else:
                button_text = quality
            
            # Create unique callback data
            # Format: dl_<format_id>_<hash>
            callback_data = f"dl_{fmt['format_id']}_{abs(hash(url)) % 100000}"
            
            # Truncate if too long (Telegram limit is 64 bytes)
            if len(callback_data) > 64:
                callback_data = callback_data[:64]
            
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        
        # Store URL and format info in user context
        if 'user_data' not in context.bot_data:
            context.bot_data['user_data'] = {}
        
        if user_id not in context.bot_data['user_data']:
            context.bot_data['user_data'][user_id] = {}
        
        context.bot_data['user_data'][user_id]['url'] = url
        context.bot_data['user_data'][user_id]['platform'] = platform
        context.bot_data['user_data'][user_id]['formats'] = {
            f"dl_{fmt['format_id']}_{abs(hash(url)) % 100000}"[:64]: fmt
            for fmt in formats
        }
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Format duration
        duration_str = downloader.format_duration(duration) if duration else "Unknown"
        
        # Edit processing message with results
        await processing_msg.edit_text(
            f"✅ **Video Found!**\n\n"
            f"📹 **Title:** {video_title}\n"
            f"🌐 **Platform:** {platform}\n"
            f"⏱️ **Duration:** {duration_str}\n\n"
            f"📊 **Select Quality:**\n"
            f"_(⚠️ = May exceed Telegram's 50MB limit)_",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        logger.info(f"User {user_id} requested video from {platform}: {video_title[:50]}")
        
    except Exception as e:
        logger.error(f"Error handling URL {url}: {e}", exc_info=True)
        await processing_msg.edit_text(
            f"❌ **Error**\n\n"
            f"An error occurred while processing your request:\n\n"
            f"`{str(e)[:200]}`\n\n"
            f"Please try:\n"
            f"• Checking if the URL is correct\n"
            f"• Using a different URL\n"
            f"• Trying again later\n\n"
            f"If the problem persists, contact support.",
            parse_mode=ParseMode.MARKDOWN
        )

# ==================== CALLBACK QUERY HANDLER ====================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks for quality selection"""
    query = update.callback_query
    user_id = query.from_user.id
    
    await query.answer()
    
    # Check authorization
    if not data_manager.is_authorized(user_id):
        await query.message.edit_text("⚠️ You are not authorized to use this bot.")
        return
    
    callback_data = query.data
    
    if not callback_data.startswith('dl_'):
        return
    
    try:
        # Get stored data
        user_data = context.bot_data.get('user_data', {}).get(user_id, {})
        url = user_data.get('url')
        platform = user_data.get('platform', 'Unknown')
        formats = user_data.get('formats', {})
        
        if not url:
            await query.message.edit_text(
                "❌ **Session Expired**\n\n"
                "Please send the URL again to download.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Get format info
        format_info = formats.get(callback_data)
        
        if not format_info:
            await query.message.edit_text(
                "❌ **Error**\n\n"
                "Format information not found. Please try sending the URL again.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        format_id = format_info['format_id']
        quality_label = format_info['quality']
        
        # Update message to show downloading
        await query.message.edit_text(
            f"⬇️ **Downloading...**\n\n"
            f"📹 **Quality:** {quality_label}\n"
            f"🌐 **Platform:** {platform}\n\n"
            f"Please wait, this may take a few moments...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Send upload action
        await context.bot.send_chat_action(chat_id=user_id, action=ChatAction.UPLOAD_VIDEO)
        
        # Download the video
        filepath = await downloader.download_video(url, format_id, quality_label)
        
        if not filepath:
            await query.message.edit_text(
                "❌ **Download Failed**\n\n"
                "Could not download the video. Please try:\n\n"
                "• A different quality option\n"
                "• Checking if the video is still available\n"
                "• Sending the URL again\n"
                "• Using a different platform\n\n"
                "If the problem persists, the video may not be accessible.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Check file size
        file_size = os.path.getsize(filepath)
        
        if file_size > TELEGRAM_FILE_SIZE_LIMIT:
            await query.message.edit_text(
                f"❌ **File Too Large for Telegram**\n\n"
                f"📊 **File Size:** {downloader.format_bytes(file_size)}\n"
                f"📊 **Telegram Limit:** {downloader.format_bytes(TELEGRAM_FILE_SIZE_LIMIT)}\n\n"
                f"Please try:\n"
                f"• Selecting a lower quality (480p or 720p)\n"
                f"• Using audio-only option for music\n"
                f"• Trying a shorter video\n\n"
                f"Telegram bots cannot send files larger than 50MB.",
                parse_mode=ParseMode.MARKDOWN
            )
            downloader.cleanup_file(filepath)
            return
        
        # Update message to show uploading
        await query.message.edit_text(
            f"📤 **Uploading to Telegram...**\n\n"
            f"📊 **Size:** {downloader.format_bytes(file_size)}\n\n"
            f"Please wait...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Send the file
        is_audio = filepath.endswith('.mp3') or 'audio' in quality_label.lower()
        
        try:
            if is_audio:
                # Send as audio
                with open(filepath, 'rb') as audio_file:
                    await context.bot.send_audio(
                        chat_id=user_id,
                        audio=audio_file,
                        caption=f"🎵 **Downloaded from {platform}**\n\n"
                                f"Quality: {quality_label}\n"
                                f"Size: {downloader.format_bytes(file_size)}",
                        parse_mode=ParseMode.MARKDOWN,
                        read_timeout=60,
                        write_timeout=60
                    )
            else:
                # Send as video
                with open(filepath, 'rb') as video_file:
                    await context.bot.send_video(
                        chat_id=user_id,
                        video=video_file,
                        caption=f"🎬 **Downloaded from {platform}**\n\n"
                                f"Quality: {quality_label}\n"
                                f"Size: {downloader.format_bytes(file_size)}",
                        supports_streaming=True,
                        parse_mode=ParseMode.MARKDOWN,
                        read_timeout=60,
                        write_timeout=60
                    )
            
            # Record statistics
            data_manager.record_download(user_id, platform, quality_label)
            
            # Delete the status message
            await query.message.delete()
            
            # Send success message
            await context.bot.send_message(
                chat_id=user_id,
                text="✅ **Download Complete!**\n\n"
                     "Send another URL to download more videos!\n\n"
                     "Type /help for more information.",
                parse_mode=ParseMode.MARKDOWN
            )
            
            logger.info(f"Successfully sent video to user {user_id} from {platform} ({quality_label}, {downloader.format_bytes(file_size)})")
            
        except TelegramError as e:
            logger.error(f"Telegram error sending file: {e}")
            await query.message.edit_text(
                f"❌ **Upload Failed**\n\n"
                f"Could not upload the file to Telegram.\n\n"
                f"Error: {str(e)[:100]}\n\n"
                f"Please try:\n"
                f"• A lower quality option\n"
                f"• Trying again later\n"
                f"• Contacting support if problem persists",
                parse_mode=ParseMode.MARKDOWN
            )
        
        # Clean up the downloaded file
        downloader.cleanup_file(filepath)
        
    except Exception as e:
        logger.error(f"Error in download callback: {e}", exc_info=True)
        try:
            await query.message.edit_text(
                f"❌ **Error**\n\n"
                f"An unexpected error occurred during download.\n\n"
                f"Please try again or contact support if the problem persists.",
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            pass

# ==================== ERROR HANDLER ====================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Global error handler"""
    logger.error(f"Update {update} caused error: {context.error}", exc_info=context.error)
    
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "❌ **An unexpected error occurred.**\n\n"
                "Please try again later or contact support if the problem persists.",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception:
            pass  # Can't send error message

# ==================== BOT INITIALIZATION ====================

async def post_init(application: Application):
    """Post initialization setup"""
    try:
        # Set bot commands
        commands = [
            BotCommand("start", "Start the bot"),
            BotCommand("help", "Show help and usage guide"),
            BotCommand("platforms", "List supported platforms"),
            BotCommand("terms", "View Terms of Service"),
            BotCommand("stats", "View your download statistics"),
        ]
        
        await application.bot.set_my_commands(commands)
        
        # Get bot info
        bot_info = await application.bot.get_me()
        logger.info(f"Bot initialized: @{bot_info.username} (ID: {bot_info.id})")
        logger.info(f"Admin ID: {ADMIN_ID}")
        logger.info(f"Webhook URL: {WEBHOOK_URL}")
        logger.info(f"Authorized users: {len(data_manager.authorized_users)}")
        
        # Clean up old files on startup
        downloader.cleanup_old_files(max_age_hours=1)
        
    except Exception as e:
        logger.error(f"Error in post_init: {e}")

# ==================== MAIN FUNCTION ====================

def main():
    """Main function to run the bot"""
    
    # Validate configuration
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN not configured!")
        sys.exit(1)
    
    if not ADMIN_ID:
        logger.error("❌ ADMIN_ID not configured!")
        sys.exit(1)
    
    logger.info("🚀 Starting Telegram Video Downloader Bot...")
    logger.info(f"📡 Webhook Mode: {bool(WEBHOOK_URL)}")
    logger.info(f"🔌 Port: {PORT}")
    
    try:
        # Create application
        application = (
            Application.builder()
            .token(BOT_TOKEN)
            .post_init(post_init)
            .read_timeout(30)
            .write_timeout(30)
            .build()
        )
        
        # Add command handlers
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("terms", terms_command))
        application.add_handler(CommandHandler("platforms", platforms_command))
        application.add_handler(CommandHandler("stats", stats_command))
        
        # Admin commands
        application.add_handler(CommandHandler("adduser", adduser_command))
        application.add_handler(CommandHandler("removeuser", removeuser_command))
        application.add_handler(CommandHandler("listusers", listusers_command))
        application.add_handler(CommandHandler("globalstats", globalstats_command))
        application.add_handler(CommandHandler("broadcast", broadcast_command))
        application.add_handler(CommandHandler("confirm", confirm_command))
        application.add_handler(CommandHandler("cancel", cancel_command))
        application.add_handler(CommandHandler("cleanup", cleanup_command))
        
        # URL handler - matches any message with http/https
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.Regex(r'https?://'),
            handle_url
        ))
        
        # Callback query handler for button clicks
        application.add_handler(CallbackQueryHandler(button_callback))
        
        # Error handler
        application.add_error_handler(error_handler)
        
        # Run bot
        if WEBHOOK_URL:
            # Production mode with webhook (for Render.com)
            logger.info(f"🌐 Starting webhook mode on {WEBHOOK_URL}:{PORT}")
            
            application.run_webhook(
                listen="0.0.0.0",
                port=PORT,
                url_path=BOT_TOKEN,
                webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}",
                allowed_updates=Update.ALL_TYPES
            )
        else:
            # Development mode with polling
            logger.info("🔄 Starting polling mode (development)")
            application.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True
            )
            
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)

# ==================== ENTRY POINT ====================

if __name__ == '__main__':
    main()
