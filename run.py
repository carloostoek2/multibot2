#!/usr/bin/env python3
"""Entry point script for the Telegram bot."""
import asyncio
import sys

from bot.main import main


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user. Goodbye!")
        sys.exit(0)
