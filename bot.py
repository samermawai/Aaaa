#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Bot setup and configuration for the Anonymous Telegram Chat Bot
"""

import logging
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, CallbackQueryHandler
)
from handlers import (
    start, connect, disconnect, handle_message, 
    reveal_identity, handle_callback_query, 
    invite_command, broadcast_command,
    topic_command, group_command, mode_command, leave_command,
    handle_mood_reaction
)
# Import admin functionality
from admin import (
    admin_dashboard, admin_user_management, admin_broadcast_message,
    admin_system_config, admin_find_user, handle_admin_callback,
    ban_user, unban_user
)

logger = logging.getLogger(__name__)

def start_bot(token):
    """Start the bot with the given token"""
    # Create the Application
    application = Application.builder().token(token).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("connect", connect))
    application.add_handler(CommandHandler("disconnect", disconnect))
    application.add_handler(CommandHandler("reveal", reveal_identity))
    application.add_handler(CommandHandler("invite", invite_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    
    # Add new mode and group commands
    application.add_handler(CommandHandler("topic", topic_command))
    application.add_handler(CommandHandler("group", group_command))
    application.add_handler(CommandHandler("mode", mode_command))
    application.add_handler(CommandHandler("leave", leave_command))
    application.add_handler(CommandHandler("mood", handle_mood_reaction))
    
    # Add admin commands
    application.add_handler(CommandHandler("admin", admin_dashboard))
    application.add_handler(CommandHandler("admin_users", admin_user_management))
    application.add_handler(CommandHandler("admin_broadcast", admin_broadcast_message))
    application.add_handler(CommandHandler("admin_config", admin_system_config))
    application.add_handler(CommandHandler("admin_find_user", admin_find_user))
    
    # Add extended broadcast commands for different targeting with proper parameter assignment
    application.add_handler(CommandHandler("broadcast_all", 
                                          lambda u, c: admin_broadcast_message(update=u, context=c, target="all")))
    application.add_handler(CommandHandler("broadcast_active", 
                                          lambda u, c: admin_broadcast_message(update=u, context=c, target="active")))
    application.add_handler(CommandHandler("broadcast_waiting", 
                                          lambda u, c: admin_broadcast_message(update=u, context=c, target="waiting")))
    application.add_handler(CommandHandler("broadcast_groups", 
                                          lambda u, c: admin_broadcast_message(update=u, context=c, target="groups")))
    
    # Add configuration commands with proper parameter assignment
    application.add_handler(CommandHandler("set_timeout", 
                                          lambda u, c: admin_system_config(update=u, context=c, action="set_timeout")))
    application.add_handler(CommandHandler("set_group_size", 
                                          lambda u, c: admin_system_config(update=u, context=c, action="set_group_size")))
    application.add_handler(CommandHandler("add_banned_word", 
                                          lambda u, c: admin_system_config(update=u, context=c, action="add_banned_word")))
    application.add_handler(CommandHandler("remove_banned_word", 
                                          lambda u, c: admin_system_config(update=u, context=c, action="remove_banned_word")))
    
    # Add callback query handler for inline buttons with pattern matching
    # Admin callbacks start with "admin_" and will be handled by handle_admin_callback
    application.add_handler(CallbackQueryHandler(handle_admin_callback, pattern="^admin_"))
    
    # All other callbacks handled by the regular handler
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    
    # Add message handler for chat messages
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Log all errors
    application.add_error_handler(error_handler)
    
    # Set up job queue for timeout checks
    job_queue = application.job_queue
    job_queue.run_repeating(check_timeouts, interval=5, first=0)
    
    # Start the Bot
    logger.info("Starting bot...")
    application.run_polling()

def error_handler(update, context):
    """Log errors caused by updates"""
    logger.error(f"Update {update} caused error {context.error}")

async def check_timeouts(context):
    """Check for timeouts in the waiting_since dictionary"""
    from utils import check_waiting_timeouts
    await check_waiting_timeouts(context)
