"""Configuration module for the Telegram bot."""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Bot configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required. Please set it in your .env file.")
