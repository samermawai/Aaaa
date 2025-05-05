#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Main entry point for the Anonymous Telegram Chat Bot
"""

import logging
import os
from bot import start_bot
from app import app  # Import Flask app for web server

if __name__ == '__main__':
    # Set up logging
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    logger = logging.getLogger(__name__)
    
    # Get token from environment variable
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("No token provided! Please set the TELEGRAM_BOT_TOKEN environment variable.")
        exit(1)
    
    # Start the bot
    start_bot(token)
