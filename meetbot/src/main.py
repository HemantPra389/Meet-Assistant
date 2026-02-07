"""
Entry point for the Google Meet Bot.
"""
import argparse
import sys
import os

# Ensure the project root is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.bot import MeetBot
from src.config import DEFAULT_AUTH_DIR
from src.logger import setup_logger

logger = setup_logger("main")

def main():
    print(">>> MAIN STARTED <<<", flush=True)

    parser = argparse.ArgumentParser(description="Google Meet Bot")
    parser.add_argument("--meeting-url", help="URL of the Google Meet")
    parser.add_argument("--auth-dir", default=DEFAULT_AUTH_DIR, help="Directory for browser profile (cookies/cache)")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")
    parser.add_argument(
        "--signin",
        action="store_true",
        help="Manually sign in to Google and save session (one-time setup)"
    )

    args = parser.parse_args()
    
    if not args.signin and not args.meeting_url:
        parser.error("--meeting-url is required unless --signin is used")

    logger.info("Initializing MeetBot...")
    
    # Force headful mode for manual sign-in so user can see via VNC
    is_headless = args.headless
    if args.signin:
        logger.info("Manual sign-in requested: Forcing NON-HEADLESS mode.")
        is_headless = False

    bot = MeetBot(args.meeting_url, args.auth_dir, is_headless)

    if args.signin:
        bot.start(bootstrap_signin=True)
    else:
        bot.start()


if __name__ == "__main__":
    main()
