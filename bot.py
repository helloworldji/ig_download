#!/usr/bin/env python3
"""
Telegram Video Downloader Bot - Real APIs Version
==================================================
Uses actual working APIs from various services
"""

import os
import sys
import logging
import asyncio
import json
import time
import re
from pathlib import Path
from typing import Optional
from aiohttp import web
import aiohttp

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.constants import ParseMode

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

# ==================== STATE ====================

authorized_users = {ADMIN_ID}
stats = {'total': 0, 'users': {}, 'platforms': {}}

# ==================== WEB SERVER ====================

async def health(request):
    return web.Response(text="Bot Running OK")

async def run_web_server():
    app = web.Application()
    app.router.add_get('/', health)
    app.router.add_get('/health', health)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    logger.info(f"✅ Web server on port {PORT}")
    
    while True:
        await asyncio.sleep(3600)

# ==================== DOWNLOAD HELPERS ====================

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
    elif 'facebook.com' in url or 'fb.watch' in url:
        return 'Facebook'
    elif 'pinterest.com' in url:
        return 'Pinterest'
    elif 'reddit.com' in url:
        return 'Reddit'
    return 'Other'

def cleanup(filepath: str):
    try:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
    except:
        pass

# ==================== API DOWNLOADERS ====================

async def download_from_api(url: str, quality: str = "720") -> Optional[str]:
    """Download using multiple API services"""
    
    platform = get_platform(url)
    
    # Try API 1: AllInOne Downloader (works for most platforms)
    result = await try_allinone_api(url, quality)
    if result:
        return result
    
    # Try API 2: SnapSave (good for Instagram/TikTok/Facebook)
    result = await try_snapsave_api(url, quality)
    if result:
        return result
    
    # Try API 3: SSSTik (TikTok specialist)
    if platform == 'TikTok':
        result = await try_ssstik_api(url)
        if result:
            return result
    
    # Try API 4: Y2Mate (YouTube specialist)
    if platform == 'YouTube':
        result = await try_y2mate_api(url, quality)
        if result:
            return result
    
    # Try API 5: SaveTweetVid (Twitter/X specialist)
    if platform == 'Twitter':
        result = await try_twitter_api(url)
        if result:
            return result
    
    logger.error("All APIs failed")
    return None

# ==================== API 1: AllInOne ====================

async def try_allinone_api(url: str, quality: str) -> Optional[str]:
    """All-in-one downloader API"""
    try:
        api_url = "https://api.allorigins.win/raw?url=" + url
        
        # This is a CORS proxy that helps fetch videos
        async with aiohttp.ClientSession() as session:
            # First, use a free video downloader API
            api_endpoint = "https://www.downloadvideosfrom.com/wp-json/aio-dl/video-data/"
            
            async with session.post(
                api_endpoint,
                json={"url": url},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get('medias') and len(data['medias']) > 0:
                        # Get video URL
                        video_url = data['medias'][0].get('url')
                        
                        if video_url:
                            # Download the file
                            filepath = await download_file(video_url)
                            if filepath:
                                logger.info("✅ AllInOne API success")
                                return filepath
                
    except Exception as e:
        logger.warning(f"AllInOne API failed: {e}")
    
    return None

# ==================== API 2: SnapSave ====================

async def try_snapsave_api(url: str, quality: str) -> Optional[str]:
    """SnapSave API - works for Instagram, Facebook, TikTok"""
    try:
        async with aiohttp.ClientSession() as session:
            # SnapSave uses a simple POST endpoint
            api_url = "https://snapsave.app/action.php"
            
            data = {
                "url": url,
                "lang": "en"
            }
            
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            async with session.post(
                api_url,
                data=data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                
                if response.status == 200:
                    html = await response.text()
                    
                    # Extract download URL from HTML
                    match = re.search(r'href="(https://[^"]+\.mp4[^"]*)"', html)
                    
                    if match:
                        video_url = match.group(1)
                        filepath = await download_file(video_url)
                        if filepath:
                            logger.info("✅ SnapSave API success")
                            return filepath
                
    except Exception as e:
        logger.warning(f"SnapSave API failed: {e}")
    
    return None

# ==================== API 3: SSSTik ====================

async def try_ssstik_api(url: str) -> Optional[str]:
    """SSSTik API - TikTok specialist"""
    try:
        async with aiohttp.ClientSession() as session:
            api_url = "https://ssstik.io/abc?url=dl"
            
            data = {
                "id": url,
                "locale": "en",
                "tt": "RFBiZ3Bi"
            }
            
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            async with session.post(
                api_url,
                data=data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                
                if response.status == 200:
                    html = await response.text()
                    
                    # Extract download URL
                    match = re.search(r'<a[^>]*href="([^"]+)"[^>]*>Download', html)
                    
                    if match:
                        video_url = match.group(1)
                        filepath = await download_file(video_url)
                        if filepath:
                            logger.info("✅ SSSTik API success")
                            return filepath
                
    except Exception as e:
        logger.warning(f"SSSTik API failed: {e}")
    
    return None

# ==================== API 4: Y2Mate ====================

async def try_y2mate_api(url: str, quality: str) -> Optional[str]:
    """Y2Mate API - YouTube specialist"""
    try:
        async with aiohttp.ClientSession() as session:
            # Y2Mate uses a two-step process
            api_url = "https://www.y2mate.com/mates/analyzeV2/ajax"
            
            data = {
                "k_query": url,
                "k_page": "home",
                "hl": "en",
                "q_auto": 0
            }
            
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            async with session.post(
                api_url,
                data=data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                
                if response.status == 200:
                    result = await response.json()
                    
                    if result.get('status') == 'ok':
                        # Extract video ID and quality
                        links = result.get('links', {}).get('mp4', {})
                        
                        # Try to get requested quality or best available
                        quality_key = next((k for k in links.keys() if quality in k), None)
                        
                        if quality_key:
                            video_data = links[quality_key]
                            k_value = video_data.get('k')
                            
                            if k_value:
                                # Get download link
                                convert_url = "https://www.y2mate.com/mates/convertV2/index"
                                
                                convert_data = {
                                    "vid": result.get('vid'),
                                    "k": k_value
                                }
                                
                                async with session.post(
                                    convert_url,
                                    data=convert_data,
                                    headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=30)
                                ) as convert_response:
                                    
                                    if convert_response.status == 200:
                                        convert_result = await convert_response.json()
                                        
                                        if convert_result.get('status') == 'ok':
                                            download_url = convert_result.get('dlink')
                                            
                                            if download_url:
                                                filepath = await download_file(download_url)
                                                if filepath:
                                                    logger.info("✅ Y2Mate API success")
                                                    return filepath
                
    except Exception as e:
        logger.warning(f"Y2Mate API failed: {e}")
    
    return None

# ==================== API 5: Twitter ====================

async def try_twitter_api(url: str) -> Optional[str]:
    """SaveTweetVid API - Twitter/X specialist"""
    try:
        async with aiohttp.ClientSession() as session:
            api_url = "https://twitsave.com/info"
            
            data = {
                "url": url
            }
            
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            async with session.post(
                api_url,
                data=data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                
                if response.status == 200:
                    html = await response.text()
                    
                    # Extract download URL
                    match = re.search(r'<a[^>]*href="([^"]+)"[^>]*download[^>]*>', html)
                    
                    if match:
                        video_url = match.group(1)
                        filepath = await download_file(video_url)
                        if filepath:
                            logger.info("✅ Twitter API success")
                            return filepath
                
    except Exception as e:
        logger.warning(f"Twitter API failed: {e}")
    
    return None

# ==================== FILE DOWNLOADER ====================

async def download_file(url: str, is_audio: bool = False) -> Optional[str]:
    """Download file from direct URL"""
    try:
        ext = 'mp3' if is_audio else 'mp4'
        filename = f"{int(time.time())}.{ext}"
        filepath = os.path.join(DOWNLOADS_DIR, filename)
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.google.com/'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=300)
            ) as response:
                
                if response.status == 200:
                    with open(filepath, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)
                    
                    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                        size = os.path.getsize(filepath)
                        logger.info(f"Downloaded: {format_bytes(size)}")
                        return filepath
                
    except Exception as e:
        logger.error(f"File download error: {e}")
    
    return None

# ==================== TELEGRAM HANDLERS ====================

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if user.id not in authorized_users:
        await update.message.reply_text(
            f"⚠️ Not authorized\n\n"
            f"ID: `{user.id}`\n"
            f"Contact admin for access",
            parse_mode=ParseMode.MARKDOWN
        )
        
        try:
            await context.bot.send_message(
                ADMIN_ID,
                f"🔔 New user:\n"
                f"{user.full_name}\n"
                f"ID: `{user.id}`\n"
                f"@{user.username or 'None'}\n\n"
                f"/adduser {user.id}",
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            pass
        return
    
    await update.message.reply_text(
        f"👋 Welcome {user.first_name}!\n\n"
        f"🎬 **Supported Platforms:**\n"
        f"• YouTube\n"
        f"• Instagram\n"
        f"• TikTok\n"
        f"• Twitter/X\n"
        f"• Facebook\n"
        f"• Pinterest\n"
        f"• Reddit\n\n"
        f"Just send me any video URL!",
        parse_mode=ParseMode.MARKDOWN
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 **How to Use**\n\n"
        "1. Send video URL\n"
        "2. Select quality\n"
        "3. Get your video!\n\n"
        "**Commands:**\n"
        "/start - Start\n"
        "/help - Help\n"
        "/stats - Stats",
        parse_mode=ParseMode.MARKDOWN
    )

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in authorized_users:
        return
    
    user_downloads = stats['users'].get(str(update.effective_user.id), 0)
    await update.message.reply_text(
        f"📊 Your downloads: **{user_downloads}**",
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
            await context.bot.send_message(new_id, "🎉 Access granted!\n\n/start to begin")
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
        f"📝 **Users ({len(authorized_users)}):**\n\n{users}",
        parse_mode=ParseMode.MARKDOWN
    )

async def globalstats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    total = stats.get('total', 0)
    platforms = stats.get('platforms', {})
    platform_text = "\n".join([f"• {p}: {c}" for p, c in platforms.items()])
    
    await update.message.reply_text(
        f"📊 **Global Stats**\n\n"
        f"Total: {total}\n"
        f"Users: {len(authorized_users)}\n\n"
        f"**Platforms:**\n{platform_text or 'None'}",
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
            [InlineKeyboardButton("720p (Recommended)", callback_data=f"dl_720_{hash(url) % 9999}")],
            [InlineKeyboardButton("480p (Smaller)", callback_data=f"dl_480_{hash(url) % 9999}")],
            [InlineKeyboardButton("360p (Fastest)", callback_data=f"dl_360_{hash(url) % 9999}")],
        ]
        
        if 'user_data' not in context.bot_data:
            context.bot_data['user_data'] = {}
        if user_id not in context.bot_data['user_data']:
            context.bot_data['user_data'][user_id] = {}
        
        context.bot_data['user_data'][user_id]['url'] = url
        context.bot_data['user_data'][user_id]['platform'] = platform
        
        await msg.edit_text(
            f"✅ **Ready**\n\n"
            f"Platform: {platform}\n\n"
            f"Select quality:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"URL error: {e}")
        await msg.edit_text("❌ Error processing URL")

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
            f"⬇️ **Downloading...**\n\n"
            f"Platform: {platform}\n"
            f"Quality: {quality}\n\n"
            f"This may take a minute...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Download using APIs
        filepath = await download_from_api(url, quality)
        
        if not filepath:
            await query.message.edit_text(
                "❌ **Download Failed**\n\n"
                "Possible reasons:\n"
                "• Video is private/deleted\n"
                "• Platform blocking downloads\n"
                "• URL is invalid\n\n"
                "Try:\n"
                "• Different video\n"
                "• Different platform\n"
                "• Checking if video is public",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        size = os.path.getsize(filepath)
        
        if size > TELEGRAM_FILE_LIMIT:
            await query.message.edit_text(
                f"❌ **File Too Large**\n\n"
                f"Size: {format_bytes(size)}\n"
                f"Limit: 50 MB\n\n"
                f"Try lower quality",
                parse_mode=ParseMode.MARKDOWN
            )
            cleanup(filepath)
            return
        
        await query.message.edit_text(
            f"📤 **Uploading...**\n\n"
            f"Size: {format_bytes(size)}",
            parse_mode=ParseMode.MARKDOWN
        )
        
        with open(filepath, 'rb') as f:
            await context.bot.send_video(
                user_id, f,
                caption=f"🎬 {platform} | {quality}",
                supports_streaming=True,
                read_timeout=60,
                write_timeout=60
            )
        
        # Update stats
        stats['total'] = stats.get('total', 0) + 1
        users = stats.get('users', {})
        users[str(user_id)] = users.get(str(user_id), 0) + 1
        stats['users'] = users
        platforms = stats.get('platforms', {})
        platforms[platform] = platforms.get(platform, 0) + 1
        stats['platforms'] = platforms
        
        await query.message.delete()
        await context.bot.send_message(
            user_id,
            "✅ **Done!**\n\nSend another URL to download more videos.",
            parse_mode=ParseMode.MARKDOWN
        )
        
        cleanup(filepath)
        
        logger.info(f"✅ Sent to {user_id}: {platform} ({quality})")
        
    except Exception as e:
        logger.error(f"Callback error: {e}")
        try:
            await query.message.edit_text(
                "❌ **Error**\n\n"
                "Something went wrong. Please try again.",
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            pass

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")

# ==================== MAIN ====================

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
        logger.info(f"✅ Users: {len(authorized_users)}")
        
        # Start web server
        asyncio.create_task(run_web_server())
        
    except Exception as e:
        logger.error(f"Init error: {e}")

def main():
    logger.info("🚀 Starting Video Downloader Bot...")
    
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
        
        logger.info("✅ Bot is running!")
        app.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
