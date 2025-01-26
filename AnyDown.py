import os
import logging
import tempfile
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
import yt_dlp

# Load environment variables
load_dotenv()
TOKEN = os.getenv("TOKEN")

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# YT-DLP configuration (updated for Facebook)
ydl_opts = {
    'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
    'outtmpl': '%(title)s.%(ext)s',
    'quiet': True,
    'no_warnings': True,
    'merge_output_format': 'mp4',
    'cookiefile': 'cookies.txt',  # Important for Facebook/Instagram
    'extractor_args': {
        'facebook': {
            'credentials': {
                'email': os.getenv('FB_EMAIL'),
                'password': os.getenv('FB_PASSWORD')
            }
        }
    }
}

SUPPORTED_DOMAINS = [
    'youtube.com',
    'youtu.be',
    'facebook.com',
    'fb.watch',  # Facebook watch links
    'instagram.com',
    'twitter.com',
    'x.com'
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message"""
    welcome_text = """
    🎥 Video Download Bot
    
    Send me a link from:
    - YouTube
    - Instagram
    - Twitter/X
    
    I'll download and send you the video!
    """
    await update.message.reply_text(welcome_text)

def is_supported_url(url: str) -> bool:
    """Improved URL validation"""
    try:
        return any(domain in url.lower() for domain in SUPPORTED_DOMAINS)
    except:
        return False

async def download_and_send_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming links and send videos"""
    message = update.message
    url = message.text
    
    if not is_supported_url(url):
        await message.reply_text("❌ Unsupported platform. Send links from YouTube/Facebook/Instagram/Twitter only.")
        return
    
    processing_msg = None
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Initialize downloader
            ydl = yt_dlp.YoutubeDL({
                **ydl_opts,
                'outtmpl': os.path.join(tmp_dir, '%(title)s.%(ext)s')
            })
            
            # Get video info
            await message.reply_chat_action(action="typing")
            info = ydl.extract_info(url, download=False)
            
            # Send processing message
            processing_msg = await message.reply_text(
                f"⏳ Downloading: {info.get('title', 'video')}\n"
                f"⏱ Duration: {info.get('duration', 0)//60} minutes"
            )
            
            # Download video
            ydl.download([url])
            
            # Get downloaded file path
            downloaded_files = [f for f in os.listdir(tmp_dir) if f.endswith('.mp4')]
            if not downloaded_files:
                raise Exception("No video file found after download")
            
            downloaded_path = os.path.join(tmp_dir, downloaded_files[0])
            
            # Send video
            await message.reply_chat_action(action="upload_video")
            if os.path.getsize(downloaded_path) < 2000 * 1024 * 1024:  # 2000MB limit
                with open(downloaded_path, 'rb') as video_file:
                    await message.reply_video(
                        video=video_file,
                        caption=f"✅ {info.get('title', 'Downloaded Video')}",
                        supports_streaming=True,
                        read_timeout=60,
                        write_timeout=60
                    )
            else:
                with open(downloaded_path, 'rb') as doc_file:
                    await message.reply_document(
                        document=doc_file,
                        caption="📁 File too large for streaming, sent as document"
                    )
            
            if processing_msg:
                await processing_msg.delete()
                
    except yt_dlp.utils.DownloadError as e:
        error_msg = f"❌ Download failed: {str(e)}"
        logger.error(error_msg)
        await message.reply_text("⚠️ Couldn't download this video. It might be private or age-restricted.")
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        await message.reply_text("❌ An unexpected error occurred. Please try again later.")
        
        if processing_msg:
            try:
                await processing_msg.delete()
            except:
                pass

def main():
    """Start the bot"""
    application = Application.builder().token(TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_and_send_video))

    # Start polling
    application.run_polling()

if __name__ == "__main__":
    main()