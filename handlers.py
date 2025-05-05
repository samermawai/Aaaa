#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Command and message handlers for the Anonymous Telegram Chat Bot
"""

import logging
import time
import asyncio
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils import (
    get_user_data, find_partner, disconnect_users, get_user_preference, set_user_preference,
    create_group_chat, add_to_group, leave_group, generate_group_id,
    WAITING_USERS, ACTIVE_CONNECTIONS, WAITING_SINCE, WAITING_BY_TOPIC,
    ALL_USERS, REVEAL_REQUESTS, GROUP_CHATS, AVAILABLE_TOPICS,
    ChatMode, check_user_access
)
from config import ADMIN_IDS

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send an interactive welcome sequence when the command /start is issued."""
    from config import SYSTEM_CONFIG, BANNED_USERS
    from admin import is_admin
    
    user = update.effective_user
    chat_id = update.effective_chat.id
    ALL_USERS[user.id] = user
    
    # Check if user is banned - special handling to allow displaying ban message
    if user.id in BANNED_USERS and not is_admin(user.id):
        await context.bot.send_message(
            chat_id=chat_id,
            text="⛔ *You have been banned from using this bot.*\n\nIf you think this is a mistake, please contact the administrator.",
            parse_mode='Markdown'
        )
        return
        
    # Check for maintenance mode - allow admins and show informative message
    if SYSTEM_CONFIG["maintenance_mode"] and not is_admin(user.id):
        await context.bot.send_message(
            chat_id=chat_id,
            text="🛠️ *Bot Maintenance Mode*\n\nThe bot is currently under maintenance and temporarily unavailable.\n\nPlease try again later.",
            parse_mode='Markdown'
        )
        return
    
    # Send animated welcome message sequence
    intro_message = await context.bot.send_message(
        chat_id=chat_id, 
        text="👋 *Connecting...*",
        parse_mode='Markdown'
    )
    
    # First animation - simulate loading
    for i in range(3):
        await asyncio.sleep(0.7)
        loading_text = "⚡ *Initializing Anonymous Chat* " + "." * (i + 1)
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=intro_message.message_id,
            text=loading_text,
            parse_mode='Markdown'
        )
    
    # Welcome reveal animation
    await asyncio.sleep(0.7)
    welcome_title = "✨ *Welcome to Anonymous Chat!* ✨"
    await context.bot.edit_message_text(
        chat_id=chat_id,
        message_id=intro_message.message_id,
        text=welcome_title,
        parse_mode='Markdown'
    )
    
    # Privacy message with typing animation
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    await asyncio.sleep(1.5)
    privacy_message = await context.bot.send_message(
        chat_id=chat_id,
        text="🔒 *Your Privacy Matters*\n\nAll conversations are completely anonymous unless both parties agree to reveal identities.",
        parse_mode='Markdown'
    )
    
    # Features introduction with typing animation
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    await asyncio.sleep(2)
    
    # Animated features reveal
    features_message = await context.bot.send_message(
        chat_id=chat_id,
        text="🚀 *Discovering Features...*",
        parse_mode='Markdown'
    )
    
    # Features animation sequence
    feature_steps = [
        "💫 *Chat Modes*\n\n✓ One-on-One Random Matching",
        "💫 *Chat Modes*\n\n✓ One-on-One Random Matching\n✓ Topic-Based Conversations",
        "💫 *Chat Modes*\n\n✓ One-on-One Random Matching\n✓ Topic-Based Conversations\n✓ Anonymous Group Chats"
    ]
    
    for step in feature_steps:
        await asyncio.sleep(0.8)
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=features_message.message_id,
            text=step,
            parse_mode='Markdown'
        )
    
    # Command hints with typing animation
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    await asyncio.sleep(1.5)
    
    commands_text = (
        "📚 *Available Commands*\n\n"
        "• /connect - 🔍 Find someone to chat with\n"
        "• /disconnect - 👋 End current conversation\n"
        "• /reveal - 🎭 Request to reveal identities\n"
        "• /mood - 💫 Send emoji reactions\n"
        "• /topic - 📋 Browse chat topics\n"
        "• /group - 👥 Manage group chats\n"
        "• /mode - 🔀 Switch chat modes"
    )
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=commands_text,
        parse_mode='Markdown'
    )
    
    # Final call to action with animated button appearance
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    await asyncio.sleep(1)
    
    action_text = "🎮 *Ready to begin?* Choose your preferred chat mode:"
    
    # Create attractive mode selection buttons
    keyboard = [
        [InlineKeyboardButton("✨ One-on-One Chat", callback_data="mode_one_on_one")],
        [InlineKeyboardButton("🔍 Topic-Based Chat", callback_data="mode_topic")],
        [InlineKeyboardButton("👥 Group Chat", callback_data="mode_group")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send the final message with mode buttons
    await context.bot.send_message(
        chat_id=chat_id,
        text=action_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def connect(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Connect the user with a random chat partner based on their chat mode preference."""
    from config import STATISTICS, SYSTEM_CONFIG, BANNED_USERS
    from admin import is_admin
    
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Add user to ALL_USERS dictionary for broadcasts
    ALL_USERS[user_id] = update.effective_user
    
    # Check if user is banned
    if user_id in BANNED_USERS and not is_admin(user_id):
        await context.bot.send_message(
            chat_id=chat_id,
            text="⛔ *You have been banned from using this bot.*\n\nIf you think this is a mistake, please contact the administrator.",
            parse_mode='Markdown'
        )
        return
        
    # Check for maintenance mode - only admins can use the bot when in maintenance
    if SYSTEM_CONFIG["maintenance_mode"] and not is_admin(user_id):
        await context.bot.send_message(
            chat_id=chat_id,
            text="🛠️ *Bot Maintenance Mode*\n\nThe bot is currently under maintenance and temporarily unavailable.\n\nPlease try again later.",
            parse_mode='Markdown'
        )
        return
    
    # Get user preferences
    user_prefs = get_user_preference(user_id)
    chat_mode = user_prefs['mode']
    
    # Check if user is already in a chat
    if user_id in ACTIVE_CONNECTIONS:
        await context.bot.send_message(
            chat_id=chat_id, 
            text="⚠️ You are already in a conversation! Use /disconnect first."
        )
        return
    
    # Check if user is in a group chat
    if chat_mode == ChatMode.GROUP and user_prefs['group_id'] in GROUP_CHATS:
        group_id = user_prefs['group_id']
        group_name = GROUP_CHATS[group_id].name
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"ℹ️ You're already in group chat '{group_name}'. Use /leave to exit."
        )
        return
    
    # Check if user is already waiting in any list
    if user_id in WAITING_USERS:
        await context.bot.send_message(
            chat_id=chat_id, 
            text="⏳ You are already looking for a partner. Please wait..."
        )
        return
    
    # Handle different chat modes with animated looking process
    search_message = None
    topic = None
    
    if chat_mode == ChatMode.ONE_ON_ONE:
        # Animated searching process for one-on-one
        search_message = await context.bot.send_message(
            chat_id=chat_id, 
            text="🔍 *Initiating random partner search*...",
            parse_mode='Markdown'
        )
        
        # Animate the search process
        search_animations = [
            "🔍 *Scanning for available users*...",
            "🔍 *Looking for your perfect match*...",
            "🔍 *Searching the anonymous network*..."
        ]
        
        for animation in search_animations:
            await asyncio.sleep(0.8)
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=search_message.message_id,
                text=animation,
                parse_mode='Markdown'
            )
            
    elif chat_mode == ChatMode.TOPIC:
        topic = user_prefs['topic']
        if not topic or topic not in AVAILABLE_TOPICS:
            # User hasn't selected a topic, show topic selection
            await topic_command(update, context)
            return
        
        # Animated searching process for topic-based
        search_message = await context.bot.send_message(
            chat_id=chat_id, 
            text=f"🔍 *Initiating topic-based search*: '{topic}'",
            parse_mode='Markdown'
        )
        
        # Animate the search process with topic-specific text
        search_animations = [
            f"🔍 *Looking for {topic} enthusiasts*...",
            f"🔍 *Searching for users interested in {topic}*...",
            f"🔍 *Finding your {topic} match*..."
        ]
        
        for animation in search_animations:
            await asyncio.sleep(0.8)
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=search_message.message_id,
                text=animation,
                parse_mode='Markdown'
            )
            
    elif chat_mode == ChatMode.GROUP:
        # Redirect to group command
        await group_command(update, context)
        return
    
    # Try to find a partner based on selected mode and topic
    partner_id = find_partner(user_id)
    
    if partner_id:
        # Partner found, connect them with animation
        ACTIVE_CONNECTIONS[user_id] = partner_id
        ACTIVE_CONNECTIONS[partner_id] = user_id
        
        # Remove both from appropriate waiting lists
        if chat_mode == ChatMode.ONE_ON_ONE:
            if user_id in WAITING_USERS:
                WAITING_USERS.remove(user_id)
            if partner_id in WAITING_USERS:
                WAITING_USERS.remove(partner_id)
        elif chat_mode == ChatMode.TOPIC and topic in AVAILABLE_TOPICS:
            if user_id in WAITING_BY_TOPIC[topic]:
                WAITING_BY_TOPIC[topic].remove(user_id)
            
            # Get partner's preferences
            partner_prefs = get_user_preference(partner_id)
            if partner_prefs['mode'] == ChatMode.TOPIC and partner_prefs['topic'] in AVAILABLE_TOPICS:
                partner_topic = partner_prefs['topic']
                if partner_id in WAITING_BY_TOPIC[partner_topic]:
                    WAITING_BY_TOPIC[partner_topic].remove(partner_id)
            
        # Remove from timing list
        if user_id in WAITING_SINCE:
            del WAITING_SINCE[user_id]
        if partner_id in WAITING_SINCE:
            del WAITING_SINCE[partner_id]
        
        # Animate the connection process
        if search_message:
            connection_steps = [
                "✨ *Match Found!* Establishing connection...",
                "🔐 *Securing anonymous channel*...",
                "🎉 *Connection established!* Ready to chat!"
            ]
            
            for step in connection_steps:
                await asyncio.sleep(0.7)
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=search_message.message_id,
                    text=step,
                    parse_mode='Markdown'
                )
        
        # Send instructional message after animation completes
        await asyncio.sleep(0.8)
        
        # Customize connection message based on mode
        if chat_mode == ChatMode.ONE_ON_ONE:
            message = "✅ *Connected!*\n\nYou can now chat anonymously. Your messages will be delivered instantly, without revealing your identity.\n\nUse /disconnect when you want to end the conversation."
        elif chat_mode == ChatMode.TOPIC:
            message = f"✅ *Connected with {topic} enthusiast!*\n\nYou can now chat anonymously about your shared interest in {topic}.\n\nUse /disconnect when you want to end the conversation."
        else:
            message = "✅ *Connected!*\n\nYou can now chat anonymously. Your messages will be delivered instantly, without revealing your identity.\n\nUse /disconnect when you want to end the conversation."
        
        # Create tips keyboard
        tips_keyboard = [
            [InlineKeyboardButton("💡 Chat Tips", callback_data="show_tips")],
            [InlineKeyboardButton("🎭 Reveal Identity", callback_data="request_reveal")]
        ]
        tips_markup = InlineKeyboardMarkup(tips_keyboard)
        
        # Notify user with enhanced message and buttons
        await context.bot.send_message(
            chat_id=chat_id, 
            text=message,
            reply_markup=tips_markup,
            parse_mode='Markdown'
        )
        
        # Get partner's chat mode for customized message
        partner_prefs = get_user_preference(partner_id)
        
        # Animate connection for partner
        partner_search_message = await context.bot.send_message(
            chat_id=partner_id,
            text="✨ *Someone is connecting with you*...",
            parse_mode='Markdown'
        )
        
        # Brief animation for partner
        partner_steps = [
            "🔐 *Securing anonymous channel*...",
            "🎉 *Connection established!* Ready to chat!"
        ]
        
        for step in partner_steps:
            await asyncio.sleep(0.7)
            await context.bot.edit_message_text(
                chat_id=partner_id,
                message_id=partner_search_message.message_id,
                text=step,
                parse_mode='Markdown'
            )
        
        # Customize partner message based on their preferences
        if partner_prefs['mode'] == ChatMode.TOPIC and partner_prefs['topic']:
            partner_topic_name = partner_prefs['topic']
            partner_message = f"✅ *Connected with {partner_topic_name} enthusiast!*\n\nYou can now chat anonymously about your shared interest in {partner_topic_name}.\n\nUse /disconnect when you want to end the conversation."
        else:
            partner_message = "✅ *Connected!*\n\nYou can now chat anonymously. Your messages will be delivered instantly, without revealing your identity.\n\nUse /disconnect when you want to end the conversation."
        
        # Send partner message with same tip buttons
        await context.bot.send_message(
            chat_id=partner_id, 
            text=partner_message,
            reply_markup=tips_markup,
            parse_mode='Markdown'
        )
    else:
        # No partner found, animate waiting state
        if search_message:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=search_message.message_id,
                text="⏳ *Waiting for matching user*...\n\nYou'll be notified as soon as someone connects.",
                parse_mode='Markdown'
            )
        
        # Add to appropriate waiting list
        if chat_mode == ChatMode.ONE_ON_ONE:
            WAITING_USERS.append(user_id)
        elif chat_mode == ChatMode.TOPIC and topic in AVAILABLE_TOPICS:
            WAITING_BY_TOPIC[topic].append(user_id)
        
        # Add timestamp for timeout handling
        WAITING_SINCE[user_id] = time.time()
        
        # Store context for use in timeout function
        context.user_data['user_id'] = user_id
        context.user_data['chat_id'] = chat_id
        
        # Create cancel button
        cancel_keyboard = [[InlineKeyboardButton("❌ Cancel Search", callback_data="cancel_search")]]
        cancel_markup = InlineKeyboardMarkup(cancel_keyboard)
        
        # Send additional waiting message with cancel option
        await context.bot.send_message(
            chat_id=chat_id,
            text="💫 *You've been added to the waiting queue*\n\nRelax and wait for a match. You can cancel anytime using the button below or by typing /disconnect.",
            reply_markup=cancel_markup,
            parse_mode='Markdown'
        )

async def disconnect(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Disconnect from the current chat partner with animated transitions."""
    from config import SYSTEM_CONFIG, BANNED_USERS
    from admin import is_admin
    
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Add user to ALL_USERS dictionary for broadcasts
    ALL_USERS[user_id] = update.effective_user
    
    # Check if user is banned
    if user_id in BANNED_USERS and not is_admin(user_id):
        await context.bot.send_message(
            chat_id=chat_id,
            text="⛔ *You have been banned from using this bot.*\n\nIf you think this is a mistake, please contact the administrator.",
            parse_mode='Markdown'
        )
        return
        
    # Check for maintenance mode - only admins can use the bot when in maintenance
    if SYSTEM_CONFIG["maintenance_mode"] and not is_admin(user_id):
        await context.bot.send_message(
            chat_id=chat_id,
            text="🛠️ *Bot Maintenance Mode*\n\nThe bot is currently under maintenance and temporarily unavailable.\n\nPlease try again later.",
            parse_mode='Markdown'
        )
        return
    
    # Start with animated message
    disconnect_message = await context.bot.send_message(
        chat_id=chat_id,
        text="🔄 *Processing disconnect request*...",
        parse_mode='Markdown'
    )
    
    if user_id in ACTIVE_CONNECTIONS:
        partner_id = ACTIVE_CONNECTIONS[user_id]
        
        # Animated disconnection sequence
        disconnect_steps = [
            "🔄 *Closing communication channel*...",
            "🔄 *Clearing chat data*...",
            "🔄 *Terminating anonymous connection*..."
        ]
        
        for step in disconnect_steps:
            await asyncio.sleep(0.7)
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=disconnect_message.message_id,
                text=step,
                parse_mode='Markdown'
            )
        
        # Disconnect both users
        disconnect_users(user_id, partner_id)
        
        # Final disconnection message with animation
        await asyncio.sleep(0.7)
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=disconnect_message.message_id,
            text="✅ *Connection terminated successfully*\n\nYou have been disconnected from your chat partner.",
            parse_mode='Markdown'
        )
        
        # Add quick options to find a new partner
        options_keyboard = [
            [InlineKeyboardButton("🔄 Find New Partner", callback_data="connect_now")],
            [InlineKeyboardButton("⚙️ Change Chat Mode", callback_data="change_mode")]
        ]
        options_markup = InlineKeyboardMarkup(options_keyboard)
        
        await context.bot.send_message(
            chat_id=chat_id,
            text="👋 *Chat ended*\n\nWould you like to find someone new to talk to?",
            reply_markup=options_markup,
            parse_mode='Markdown'
        )
        
        # Notify partner with animation
        partner_notification = await context.bot.send_message(
            chat_id=partner_id,
            text="⚠️ *Connection status changing*...",
            parse_mode='Markdown'
        )
        
        await asyncio.sleep(0.8)
        await context.bot.edit_message_text(
            chat_id=partner_id,
            message_id=partner_notification.message_id,
            text="👋 *Your partner has disconnected*\n\nThis conversation has ended.",
            parse_mode='Markdown'
        )
        
        # Give partner options too
        await context.bot.send_message(
            chat_id=partner_id,
            text="💬 *Ready for a new conversation?*",
            reply_markup=options_markup,
            parse_mode='Markdown'
        )
    
    elif user_id in WAITING_USERS:
        # User is in waiting list - animated cancellation
        cancel_steps = [
            "🔄 *Checking queue status*...",
            "🔄 *Removing from waiting list*...",
            "🔄 *Cancelling search request*..."
        ]
        
        for step in cancel_steps:
            await asyncio.sleep(0.7)
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=disconnect_message.message_id,
                text=step,
                parse_mode='Markdown'
            )
        
        # Remove user from waiting list
        WAITING_USERS.remove(user_id)
        if user_id in WAITING_SINCE:
            del WAITING_SINCE[user_id]
        
        # Final cancellation message
        await asyncio.sleep(0.7)
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=disconnect_message.message_id,
            text="✅ *Search cancelled*\n\nYou've been removed from the waiting queue.",
            parse_mode='Markdown'
        )
        
        # Offer options
        options_keyboard = [
            [InlineKeyboardButton("🔄 Try Again", callback_data="try_again")],
            [InlineKeyboardButton("🔀 Change Chat Mode", callback_data="change_mode")]
        ]
        options_markup = InlineKeyboardMarkup(options_keyboard)
        
        await context.bot.send_message(
            chat_id=chat_id,
            text="💭 *What would you like to do next?*",
            reply_markup=options_markup,
            parse_mode='Markdown'
        )
    
    # Check for topic-based waiting
    elif any(user_id in waiting_list for waiting_list in WAITING_BY_TOPIC.values()):
        # Find which topic the user was waiting for
        user_topic = None
        for topic, waiting_list in WAITING_BY_TOPIC.items():
            if user_id in waiting_list:
                user_topic = topic
                waiting_list.remove(user_id)
                break
        
        # Animated cancellation for topic-based waiting
        topic_cancel_steps = [
            "🔄 *Checking topic queue*...",
            f"🔄 *Removing from {user_topic} waiting list*..." if user_topic else "🔄 *Removing from topic waiting list*...",
            "🔄 *Cancelling topic-based search*..."
        ]
        
        for step in topic_cancel_steps:
            await asyncio.sleep(0.7)
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=disconnect_message.message_id,
                text=step,
                parse_mode='Markdown'
            )
        
        # Remove from waiting time tracker
        if user_id in WAITING_SINCE:
            del WAITING_SINCE[user_id]
            
        # Final topic cancellation message
        topic_text = f" for topic '{user_topic}'" if user_topic else ""
        await asyncio.sleep(0.7)
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=disconnect_message.message_id,
            text=f"✅ *Topic search cancelled*\n\nYou've been removed from the waiting queue{topic_text}.",
            parse_mode='Markdown'
        )
        
        # Offer topic-specific options
        topic_options = [
            [InlineKeyboardButton("🔄 Try Same Topic", callback_data="connect_now")],
            [InlineKeyboardButton("📋 Choose Different Topic", callback_data="mode_topic")],
            [InlineKeyboardButton("🔀 Change Chat Mode", callback_data="change_mode")]
        ]
        topic_markup = InlineKeyboardMarkup(topic_options)
        
        await context.bot.send_message(
            chat_id=chat_id,
            text="🔍 *Topic Search Cancelled*\n\nWhat would you like to do next?",
            reply_markup=topic_markup,
            parse_mode='Markdown'
        )
    
    else:
        # Not in any conversation or waiting list
        await asyncio.sleep(0.7)
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=disconnect_message.message_id,
            text="ℹ️ *No active connections*\n\nYou're not currently in any conversation or waiting list.",
            parse_mode='Markdown'
        )
        
        # Offer general options
        general_options = [
            [InlineKeyboardButton("🔍 Find Someone to Chat With", callback_data="connect_now")],
            [InlineKeyboardButton("⚙️ Chat Settings", callback_data="change_mode")]
        ]
        general_markup = InlineKeyboardMarkup(general_options)
        
        await context.bot.send_message(
            chat_id=chat_id,
            text="💬 *Ready to start?*\n\nYou can find someone to chat with or adjust your settings first.",
            reply_markup=general_markup,
            parse_mode='Markdown'
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Forward messages between chat partners or to group chat members with content moderation."""
    from config import SYSTEM_CONFIG, BANNED_USERS, STATISTICS
    from admin import is_admin
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    message_text = update.message.text
    
    # Check if user is banned
    if user_id in BANNED_USERS and not is_admin(user_id):
        await context.bot.send_message(
            chat_id=chat_id,
            text="⛔ *You have been banned from using this bot.*\n\nIf you think this is a mistake, please contact the administrator.",
            parse_mode='Markdown'
        )
        return
        
    # Check for maintenance mode - only admins can use the bot when in maintenance
    if SYSTEM_CONFIG["maintenance_mode"] and not is_admin(user_id):
        await context.bot.send_message(
            chat_id=chat_id,
            text="🛠️ *Bot Maintenance Mode*\n\nThe bot is currently under maintenance and temporarily unavailable.\n\nPlease try again later.",
            parse_mode='Markdown'
        )
        return
        
    # Content moderation - check for banned words
    if SYSTEM_CONFIG["banned_words"] and not is_admin(user_id):
        message_lower = message_text.lower()
        for banned_word in SYSTEM_CONFIG["banned_words"]:
            if banned_word in message_lower:
                # Notify user of policy violation
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="⚠️ *Message Not Sent*\n\nYour message contains prohibited content and was not delivered.\n\nPlease review our content policy and try again with appropriate language.",
                    parse_mode='Markdown'
                )
                return
                
    # Update message statistics
    STATISTICS["total_messages"] += 1
    
    # Get user preferences
    user_prefs = get_user_preference(user_id)
    
    # Check for mood reaction command
    if message_text.startswith('/mood'):
        await handle_mood_reaction(update, context)
        return
    
    # One-on-one chat mode
    if user_id in ACTIVE_CONNECTIONS:
        partner_id = ACTIVE_CONNECTIONS[user_id]
        
        # Add reaction buttons to messages
        mood_keyboard = [
            [
                InlineKeyboardButton("❤️", callback_data="mood_heart"),
                InlineKeyboardButton("😂", callback_data="mood_laugh"),
                InlineKeyboardButton("😮", callback_data="mood_wow"),
                InlineKeyboardButton("😢", callback_data="mood_sad"),
                InlineKeyboardButton("😡", callback_data="mood_angry")
            ]
        ]
        mood_markup = InlineKeyboardMarkup(mood_keyboard)
        
        # Forward the message to the partner with reaction buttons
        await context.bot.send_message(
            chat_id=partner_id, 
            text=f"👤 Anonymous: {message_text}",
            reply_markup=mood_markup
        )
        
        # Send animated delivery confirmation
        delivery_confirm = await context.bot.send_message(
            chat_id=chat_id,
            text="🔄 *Sending message*...",
            parse_mode='Markdown'
        )
        
        await asyncio.sleep(0.5)
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=delivery_confirm.message_id,
            text="✓ *Message delivered*",
            parse_mode='Markdown'
        )
        return
    
    # Group chat mode
    if user_prefs['mode'] == ChatMode.GROUP and user_prefs['group_id'] in GROUP_CHATS:
        group_id = user_prefs['group_id']
        group = GROUP_CHATS[group_id]
        
        # Get user number in group (for anonymous identification)
        member_list = list(group.members)
        user_number = member_list.index(user_id) + 1 if user_id in member_list else 0
        
        # Add mood reaction buttons to group messages
        group_mood_keyboard = [
            [
                InlineKeyboardButton("👍", callback_data=f"group_mood_like_{group_id}_{user_number}"),
                InlineKeyboardButton("❤️", callback_data=f"group_mood_heart_{group_id}_{user_number}"),
                InlineKeyboardButton("😂", callback_data=f"group_mood_laugh_{group_id}_{user_number}"),
                InlineKeyboardButton("😮", callback_data=f"group_mood_wow_{group_id}_{user_number}"),
                InlineKeyboardButton("👏", callback_data=f"group_mood_clap_{group_id}_{user_number}")
            ]
        ]
        group_mood_markup = InlineKeyboardMarkup(group_mood_keyboard)
        
        # Forward message to all other group members with reaction buttons
        for member_id in group.members:
            if member_id != user_id:  # Don't send to the sender
                try:
                    await context.bot.send_message(
                        chat_id=member_id,
                        text=f"👥 Group Member #{user_number}: {message_text}",
                        reply_markup=group_mood_markup
                    )
                except Exception as e:
                    logger.error(f"Error sending message to group member {member_id}: {e}")
        
        # Send enhanced delivery confirmation to the sender
        delivery_confirm = await context.bot.send_message(
            chat_id=chat_id,
            text="🔄 *Delivering message to group*...",
            parse_mode='Markdown'
        )
        
        await asyncio.sleep(0.7)
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=delivery_confirm.message_id,
            text="✅ *Message delivered*\n\nYour message has been sent to the group successfully.",
            parse_mode='Markdown'
        )
        return
    
    # User is not in any conversation
    await context.bot.send_message(
        chat_id=chat_id, 
        text="ℹ️ You're not in an active conversation. Use /connect to find a partner or /group to join a group chat."
    )

async def reveal_identity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Request to reveal identities with the chat partner using animated sequences."""
    from config import SYSTEM_CONFIG, BANNED_USERS
    from admin import is_admin
    
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Add user to ALL_USERS dictionary for broadcasts
    ALL_USERS[user_id] = update.effective_user
    
    # Check if user is banned
    if user_id in BANNED_USERS and not is_admin(user_id):
        await context.bot.send_message(
            chat_id=chat_id,
            text="⛔ *You have been banned from using this bot.*\n\nIf you think this is a mistake, please contact the administrator.",
            parse_mode='Markdown'
        )
        return
        
    # Check for maintenance mode - only admins can use the bot when in maintenance
    if SYSTEM_CONFIG["maintenance_mode"] and not is_admin(user_id):
        await context.bot.send_message(
            chat_id=chat_id,
            text="🛠️ *Bot Maintenance Mode*\n\nThe bot is currently under maintenance and temporarily unavailable.\n\nPlease try again later.",
            parse_mode='Markdown'
        )
        return
    
    # Check if user is in an active conversation
    if user_id not in ACTIVE_CONNECTIONS:
        # Animated error message
        error_message = await context.bot.send_message(
            chat_id=chat_id, 
            text="🔍 *Checking connection status*...",
            parse_mode='Markdown'
        )
        
        await asyncio.sleep(0.8)
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=error_message.message_id,
            text="❌ *No active connection found*\n\nYou need to be in an active conversation to reveal identities.",
            parse_mode='Markdown'
        )
        
        # Add connect button
        connect_keyboard = [[InlineKeyboardButton("🔄 Find a Partner", callback_data="connect_now")]]
        connect_markup = InlineKeyboardMarkup(connect_keyboard)
        
        await asyncio.sleep(0.8)
        await context.bot.send_message(
            chat_id=chat_id,
            text="ℹ️ Use the button below to find a chat partner first:",
            reply_markup=connect_markup
        )
        return
    
    partner_id = ACTIVE_CONNECTIONS[user_id]
    
    # Check if there's already a pending request from this user
    if user_id in REVEAL_REQUESTS:
        # Animated pending message
        pending_message = await context.bot.send_message(
            chat_id=chat_id, 
            text="🔍 *Checking reveal request status*...",
            parse_mode='Markdown'
        )
        
        await asyncio.sleep(0.8)
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=pending_message.message_id,
            text="⏳ *Request already pending*\n\nYou've already sent a reveal request to your partner. Please wait for their response.",
            parse_mode='Markdown'
        )
        return
    
    # Create new reveal request with animation
    request_animation = await context.bot.send_message(
        chat_id=chat_id, 
        text="🔒 *Preparing identity reveal request*...",
        parse_mode='Markdown'
    )
    
    # Animated request steps
    request_steps = [
        "📝 *Creating reveal request*...",
        "🔐 *Setting privacy options*...",
        "📤 *Sending request to partner*..."
    ]
    
    for step in request_steps:
        await asyncio.sleep(0.8)
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=request_animation.message_id,
            text=step,
            parse_mode='Markdown'
        )
    
    # Create new reveal request in data structure
    REVEAL_REQUESTS[user_id] = {
        'partner_id': partner_id,
        'status': 'pending'
    }
    
    # Create enhanced inline keyboard for partner to respond
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes, Reveal My Identity", callback_data=f"reveal_yes_{user_id}"),
            InlineKeyboardButton("❌ No, Stay Anonymous", callback_data=f"reveal_no_{user_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send confirmation to user
    await context.bot.edit_message_text(
        chat_id=chat_id,
        message_id=request_animation.message_id,
        text="🎭 *Identity Reveal Request Sent!*\n\nWaiting for your partner's response...\n\nThey will decide whether to share their real identity with you.",
        parse_mode='Markdown'
    )
    
    # Send animated request to partner
    partner_notice = await context.bot.send_message(
        chat_id=partner_id, 
        text="💌 *New Request Received*...",
        parse_mode='Markdown'
    )
    
    await asyncio.sleep(1)
    await context.bot.edit_message_text(
        chat_id=partner_id,
        message_id=partner_notice.message_id,
        text="🎭 *Identity Reveal Request*\n\nYour chat partner would like to reveal identities.\n\nIf you accept, both of you will be able to see each other's name and username (if available).\n\nDo you want to reveal your identity?",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    # Add info about what happens with the data
    await context.bot.send_chat_action(chat_id=partner_id, action="typing")
    await asyncio.sleep(1)
    
    await context.bot.send_message(
        chat_id=partner_id,
        text="ℹ️ *Privacy Note*: Only your name and username will be shared. No other personal information is collected or revealed by this bot.",
        parse_mode='Markdown'
    )

async def handle_mood_reaction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /mood command to express emotions during chat"""
    from config import SYSTEM_CONFIG, BANNED_USERS
    from admin import is_admin
    
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    message_text = update.message.text.strip()
    
    # Add user to ALL_USERS dictionary for broadcasts
    ALL_USERS[user_id] = update.effective_user
    
    # Check if user is banned
    if user_id in BANNED_USERS and not is_admin(user_id):
        await context.bot.send_message(
            chat_id=chat_id,
            text="⛔ *You have been banned from using this bot.*\n\nIf you think this is a mistake, please contact the administrator.",
            parse_mode='Markdown'
        )
        return
        
    # Check for maintenance mode - only admins can use the bot when in maintenance
    if SYSTEM_CONFIG["maintenance_mode"] and not is_admin(user_id):
        await context.bot.send_message(
            chat_id=chat_id,
            text="🛠️ *Bot Maintenance Mode*\n\nThe bot is currently under maintenance and temporarily unavailable.\n\nPlease try again later.",
            parse_mode='Markdown'
        )
        return
    
    # Check if user is in active conversation
    if user_id not in ACTIVE_CONNECTIONS:
        await context.bot.send_message(
            chat_id=chat_id,
            text="❌ You need to be in an active conversation to send mood reactions."
        )
        return
    
    partner_id = ACTIVE_CONNECTIONS[user_id]
    
    # Parse command for specific mood or show mood selection menu
    mood = None
    if len(message_text) > 5:  # Extract mood if provided (format: /mood happy)
        mood = message_text[6:].lower().strip()
    
    # Mood dictionary with corresponding emojis
    mood_emojis = {
        "happy": "😊", "laugh": "😂", "love": "❤️", "wow": "😮", 
        "sad": "😢", "angry": "😡", "thumbsup": "👍", "fire": "🔥",
        "clap": "👏", "thinking": "🤔", "cool": "😎", "party": "🎉"
    }
    
    # If no specific mood or invalid mood, show mood selection menu
    if not mood or mood not in mood_emojis:
        # Create animated mood selection interface
        mood_message = await context.bot.send_message(
            chat_id=chat_id,
            text="💭 *Loading mood selector*...",
            parse_mode='Markdown'
        )
        
        await asyncio.sleep(0.8)
        
        # Build attractive emoji grid for mood selection
        keyboard = []
        mood_rows = [list(mood_emojis.items())[i:i+4] for i in range(0, len(mood_emojis), 4)]
        
        for row in mood_rows:
            keyboard_row = []
            for mood_name, emoji in row:
                keyboard_row.append(InlineKeyboardButton(
                    f"{emoji}", callback_data=f"select_mood_{mood_name}"
                ))
            keyboard.append(keyboard_row)
        
        # Add cancel button
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_mood")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Show final mood selection interface
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=mood_message.message_id,
            text="💭 *Express Your Emotion*\n\nChoose a reaction to send to your chat partner:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return
    
    # Send the selected mood directly if specified in command
    emoji = mood_emojis.get(mood, "👍")  # Default to thumbs up if not found
    
    # Animated mood sending sequence
    mood_message = await context.bot.send_message(
        chat_id=chat_id,
        text=f"💭 *Sending {emoji} reaction*...",
        parse_mode='Markdown'
    )
    
    await asyncio.sleep(0.7)
    await context.bot.edit_message_text(
        chat_id=chat_id,
        message_id=mood_message.message_id,
        text=f"✅ *Reaction sent*\n\nYou sent: {emoji}",
        parse_mode='Markdown'
    )
    
    # Send to partner with animation
    partner_message = await context.bot.send_message(
        chat_id=partner_id,
        text="💭 *Incoming reaction*...",
        parse_mode='Markdown'
    )
    
    await asyncio.sleep(0.8)
    
    # Display animated effect based on the mood type
    display_text = f"💭 Your chat partner sent a reaction: {emoji}"
    
    # Create enhanced display for certain reactions
    if mood in ["love", "fire", "party"]:
        # Create more decorative display for expressive reactions
        decorations = {
            "love": "❤️ 💕 ❤️ 💕 ❤️",
            "fire": "🔥 🔥 🔥 🔥 🔥",
            "party": "🎉 🎊 🎉 🎊 🎉"
        }
        display_text = f"💫 *Reaction Received!*\n\n{decorations.get(mood)}\n\nYour chat partner reacted with {emoji}\n{decorations.get(mood)}"
    
    await context.bot.edit_message_text(
        chat_id=partner_id,
        message_id=partner_message.message_id,
        text=display_text,
        parse_mode='Markdown'
    )
    
    # Show mood reaction help message to first-time recipients
    if 'shown_mood_help' not in context.user_data:
        context.user_data['shown_mood_help'] = True
        
        # Send helpful tip about mood reactions after a short delay
        await asyncio.sleep(1.5)
        
        help_keyboard = [[InlineKeyboardButton("😊 Try Mood Reactions", callback_data="try_mood")]]
        help_markup = InlineKeyboardMarkup(help_keyboard)
        
        await context.bot.send_message(
            chat_id=partner_id,
            text="💡 *Mood Reaction Tip*\n\nYou can also express emotions in your conversations!\n\n• Use the /mood command to see reaction options\n• Type /mood [type] to send specific reactions (e.g., /mood happy)\n• Click reaction buttons under messages in chat",
            reply_markup=help_markup,
            parse_mode='Markdown'
        )

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback queries from inline buttons."""
    from config import SYSTEM_CONFIG, BANNED_USERS
    from admin import is_admin
    
    query = update.callback_query
    await query.answer()  # Answer the callback query
    
    data = query.data
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Add user to ALL_USERS dictionary for broadcasts
    ALL_USERS[user_id] = update.effective_user
    
    # Check if user is banned - except for certain system callbacks
    if user_id in BANNED_USERS and not is_admin(user_id) and not data.startswith("system_"):
        await context.bot.send_message(
            chat_id=chat_id,
            text="⛔ *You have been banned from using this bot.*\n\nIf you think this is a mistake, please contact the administrator.",
            parse_mode='Markdown'
        )
        return
        
    # Check for maintenance mode - except for admin-related callbacks
    if SYSTEM_CONFIG["maintenance_mode"] and not is_admin(user_id) and not data.startswith("admin_"):
        await context.bot.send_message(
            chat_id=chat_id,
            text="🛠️ *Bot Maintenance Mode*\n\nThe bot is currently under maintenance and temporarily unavailable.\n\nPlease try again later.",
            parse_mode='Markdown'
        )
        return
    
    if data.startswith("reveal_"):
        # Identity reveal response with animation
        _, response, requester_id = data.split("_")
        requester_id = int(requester_id)
        chat_id = update.effective_chat.id
        
        if response == "yes":
            # User agreed to reveal - with animation
            await query.edit_message_text(
                text="✨ *Processing your response*...",
                parse_mode='Markdown'
            )
            
            if requester_id in REVEAL_REQUESTS and REVEAL_REQUESTS[requester_id]['partner_id'] == user_id:
                # Get user data
                requester = ALL_USERS.get(requester_id)
                responder = ALL_USERS.get(user_id)
                
                if requester and responder:
                    # Animated reveal sequence
                    reveal_steps = [
                        "🔐 *Preparing secure identity exchange*...",
                        "🔄 *Validating request*...",
                        "✅ *Request verified*\n\nProcessing identities..."
                    ]
                    
                    # Show animation to both users
                    requester_message = await context.bot.send_message(
                        chat_id=requester_id,
                        text="💌 *Identity reveal in progress*...",
                        parse_mode='Markdown'
                    )
                    
                    responder_message = await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=query.message.message_id,
                        text="💌 *Identity reveal in progress*...",
                        parse_mode='Markdown'
                    )
                    
                    # Show animation steps
                    for step in reveal_steps:
                        await asyncio.sleep(0.8)
                        # Update requester's message
                        await context.bot.edit_message_text(
                            chat_id=requester_id,
                            message_id=requester_message.message_id,
                            text=step,
                            parse_mode='Markdown'
                        )
                        
                        # Update responder's message
                        await context.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=responder_message.message_id,
                            text=step,
                            parse_mode='Markdown'
                        )
                    
                    # Build beautiful profile cards with emojis and formatting
                    requester_username = f"\n*Username:* @{requester.username}" if requester.username else ""
                    responder_username = f"\n*Username:* @{responder.username}" if responder.username else ""
                    
                    requester_card = (
                        f"🎭 *Identity Revealed!*\n\n"
                        f"You're chatting with:\n\n"
                        f"👤 *Name:* {responder.first_name} {responder.last_name if responder.last_name else ''}"
                        f"{responder_username}"
                    )
                    
                    responder_card = (
                        f"🎭 *Identity Revealed!*\n\n"
                        f"You're chatting with:\n\n"
                        f"👤 *Name:* {requester.first_name} {requester.last_name if requester.last_name else ''}"
                        f"{requester_username}"
                    )
                    
                    # Add dramatic pause
                    await asyncio.sleep(1.2)
                    
                    # Send final reveal messages with sparkle animation
                    final_requester = await context.bot.edit_message_text(
                        chat_id=requester_id,
                        message_id=requester_message.message_id,
                        text="✨✨✨ *Revealing identity* ✨✨✨",
                        parse_mode='Markdown'
                    )
                    
                    final_responder = await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=responder_message.message_id,
                        text="✨✨✨ *Revealing identity* ✨✨✨",
                        parse_mode='Markdown'
                    )
                    
                    await asyncio.sleep(1)
                    
                    # Create continue chat buttons
                    continue_keyboard = [[InlineKeyboardButton("💬 Continue Chat", callback_data="continue_chat")]]
                    continue_markup = InlineKeyboardMarkup(continue_keyboard)
                    
                    # Send identity cards
                    await context.bot.send_message(
                        chat_id=requester_id,
                        text=requester_card,
                        parse_mode='Markdown',
                        reply_markup=continue_markup
                    )
                    
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=responder_card,
                        parse_mode='Markdown',
                        reply_markup=continue_markup
                    )
                    
                    # Clear the request
                    del REVEAL_REQUESTS[requester_id]
                    
                    # Add success confirmation
                    await context.bot.edit_message_text(
                        chat_id=requester_id,
                        message_id=final_requester.message_id,
                        text="✅ *Identity exchange complete!*\n\nYou can now chat knowing who you're talking to.",
                        parse_mode='Markdown'
                    )
                    
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=final_responder.message_id,
                        text="✅ *Identity exchange complete!*\n\nYou can now chat knowing who you're talking to.",
                        parse_mode='Markdown'
                    )
                else:
                    # Error getting user data
                    await query.edit_message_text(
                        text="❌ *Error retrieving user information*\n\nWe couldn't access the profile information needed for identity reveal.",
                        parse_mode='Markdown'
                    )
            else:
                # No matching request
                await query.edit_message_text(
                    text="❓ The identity reveal request is no longer valid. It may have been canceled or expired.",
                    parse_mode='Markdown'
                )
        else:
            # User declined to reveal - with animation
            decline_animation = await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=query.message.message_id,
                text="🔒 *Processing your decision*...",
                parse_mode='Markdown'
            )
            
            await asyncio.sleep(0.8)
            
            if requester_id in REVEAL_REQUESTS:
                # Animated decline sequence
                requester_notification = await context.bot.send_message(
                    chat_id=requester_id, 
                    text="⏳ *Waiting for response*...",
                    parse_mode='Markdown'
                )
                
                await asyncio.sleep(0.8)
                await context.bot.edit_message_text(
                    chat_id=requester_id,
                    message_id=requester_notification.message_id,
                    text="❌ *Request Declined*\n\nYour chat partner has chosen to remain anonymous.",
                    parse_mode='Markdown'
                )
                
                # Add suggestion for requester
                suggest_keyboard = [[InlineKeyboardButton("🔄 Continue Anonymously", callback_data="continue_chat")]]
                suggest_markup = InlineKeyboardMarkup(suggest_keyboard)
                
                await context.bot.send_message(
                    chat_id=requester_id,
                    text="💬 *Privacy Respected*\n\nYour chat can continue anonymously. Everyone has different privacy preferences.",
                    reply_markup=suggest_markup,
                    parse_mode='Markdown'
                )
                
                # Clear the request
                del REVEAL_REQUESTS[requester_id]
            
            # Update the button message with confirmation
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=decline_animation.message_id,
                text="🔒 *Privacy Maintained*\n\nYou declined to reveal identities. Your anonymity has been preserved.",
                parse_mode='Markdown'
            )
    
    elif data.startswith("mode_"):
        # Mode selection handler
        mode = data.split("_", 1)[1]
        
        if mode == "one_on_one":
            # Set to one-on-one mode
            set_user_preference(user_id, mode=ChatMode.ONE_ON_ONE, topic=None, group_id=None)
            await query.edit_message_text(
                text="✅ Mode set to 1️⃣ One-on-One Chat.\n\nUse /connect to find a random partner."
            )
        
        elif mode == "topic":
            # Set to topic-based mode and show topic selection
            set_user_preference(user_id, mode=ChatMode.TOPIC)
            
            # Show topic selection menu
            topic_keyboard = []
            for i in range(0, len(AVAILABLE_TOPICS), 2):
                row = []
                row.append(InlineKeyboardButton(AVAILABLE_TOPICS[i].capitalize(), callback_data=f"topic_{AVAILABLE_TOPICS[i]}"))
                if i + 1 < len(AVAILABLE_TOPICS):
                    row.append(InlineKeyboardButton(AVAILABLE_TOPICS[i+1].capitalize(), callback_data=f"topic_{AVAILABLE_TOPICS[i+1]}"))
                topic_keyboard.append(row)
            
            reply_markup = InlineKeyboardMarkup(topic_keyboard)
            
            await query.edit_message_text(
                text="📋 Mode set to Topic-Based Chat.\n\nPlease select a topic you're interested in:",
                reply_markup=reply_markup
            )
        
        elif mode == "group":
            # Set to group mode and show group options
            set_user_preference(user_id, mode=ChatMode.GROUP)
            
            # Show group options
            group_keyboard = [
                [InlineKeyboardButton("➕ Create New Group", callback_data="group_create")],
                [InlineKeyboardButton("🔍 Browse Public Groups", callback_data="group_browse")]
            ]
            reply_markup = InlineKeyboardMarkup(group_keyboard)
            
            await query.edit_message_text(
                text="👥 Mode set to Group Chat.\n\nWould you like to create a new group or browse existing ones?",
                reply_markup=reply_markup
            )
    
    elif data.startswith("topic_"):
        # Topic selection handler
        topic = data.split("_", 1)[1]
        
        if topic in AVAILABLE_TOPICS:
            # Set the selected topic
            set_user_preference(user_id, mode=ChatMode.TOPIC, topic=topic)
            
            # Create connect button
            keyboard = [[InlineKeyboardButton("🔍 Find Partner", callback_data="connect_now")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text=f"✅ Topic set to: '{topic.capitalize()}'\n\nClick the button below to find someone interested in this topic!",
                reply_markup=reply_markup
            )
    
    elif data.startswith("group_"):
        # Group actions handler
        action = data.split("_", 1)[1]
        
        if action == "create":
            # Store the command in user_data to expect group name in next message
            context.user_data['expect_group_name'] = True
            
            await query.edit_message_text(
                text="👥 *Creating a New Group*\n\nPlease send a name for your group (e.g., 'Tech Chat', 'Music Lovers'):",
                parse_mode='Markdown'
            )
        
        elif action == "browse":
            # List available groups
            if not GROUP_CHATS:
                await query.edit_message_text(
                    text="❌ No active group chats available. You can create one yourself!"
                )
                return
            
            # Create buttons for each available group
            group_keyboard = []
            for group_id, group in GROUP_CHATS.items():
                if not group.is_full():
                    group_keyboard.append([
                        InlineKeyboardButton(
                            f"{group.name} ({len(group.members)}/{group.max_size})",
                            callback_data=f"join_group_{group_id}"
                        )
                    ])
            
            if not group_keyboard:
                await query.edit_message_text(
                    text="❌ All groups are currently full. Please try again later or create your own group."
                )
                return
            
            reply_markup = InlineKeyboardMarkup(group_keyboard)
            
            await query.edit_message_text(
                text="📋 Available Group Chats:\nSelect a group to join:",
                reply_markup=reply_markup
            )
    
    elif data.startswith("join_group_"):
        # Join group handler
        group_id = data.split("_", 2)[2]
        
        if group_id in GROUP_CHATS and not GROUP_CHATS[group_id].is_full():
            # Add user to group
            result = add_to_group(user_id, group_id)
            
            if result:
                group_name = GROUP_CHATS[group_id].name
                group_size = len(GROUP_CHATS[group_id].members)
                max_size = GROUP_CHATS[group_id].max_size
                
                # Notify user
                await query.edit_message_text(
                    text=f"✅ You've joined the group: '{group_name}'\n\nMembers: {group_size}/{max_size}\n\nStart typing to send messages to the group!"
                )
                
                # Notify other group members
                for member_id in GROUP_CHATS[group_id].members:
                    if member_id != user_id:
                        try:
                            await context.bot.send_message(
                                chat_id=member_id,
                                text=f"👋 A new member has joined the group '{group_name}'!\nMembers: {group_size}/{max_size}"
                            )
                        except Exception as e:
                            logger.error(f"Error notifying group member {member_id}: {e}")
            else:
                await query.edit_message_text(
                    text="❌ Failed to join the group. It might be full now."
                )
        else:
            await query.edit_message_text(
                text="❌ This group no longer exists or is full."
            )
    
    elif data == "connect_now":
        # User wants to connect immediately
        await connect(update, context)
    
    elif data == "try_again":
        # User wants to try connecting again
        await connect(update, context)
        
    elif data == "change_mode":
        # User wants to change chat mode
        await mode_command(update, context)
        
    elif data == "cancel_search":
        # User wants to cancel the ongoing search
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        # Remove user from waiting lists
        if user_id in WAITING_USERS:
            WAITING_USERS.remove(user_id)
        
        # Check if in topic waiting list
        user_prefs = get_user_preference(user_id)
        if user_prefs['mode'] == ChatMode.TOPIC and user_prefs['topic'] in AVAILABLE_TOPICS:
            topic = user_prefs['topic']
            if user_id in WAITING_BY_TOPIC[topic]:
                WAITING_BY_TOPIC[topic].remove(user_id)
        
        # Remove from waiting timestamp tracking
        if user_id in WAITING_SINCE:
            del WAITING_SINCE[user_id]
        
        # Animate the cancellation
        cancel_animation = await context.bot.send_message(
            chat_id=chat_id,
            text="🛑 *Cancelling search*...",
            parse_mode='Markdown'
        )
        
        await asyncio.sleep(0.8)
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=cancel_animation.message_id,
            text="✅ *Search cancelled*\n\nYou have been removed from the waiting queue.",
            parse_mode='Markdown'
        )
        
        # Show options to try again or change mode
        options_keyboard = [
            [InlineKeyboardButton("🔄 Try Again", callback_data="try_again")],
            [InlineKeyboardButton("🔀 Change Chat Mode", callback_data="change_mode")]
        ]
        options_markup = InlineKeyboardMarkup(options_keyboard)
        
    elif data == "continue_chat":
        # User clicked "Continue Chat" button after identity reveal or other interactions
        chat_id = update.effective_chat.id
        
        # Show a nice confirmation animation
        await query.edit_message_text(
            text="💬 *Continuing your conversation*...",
            parse_mode='Markdown'
        )
        
        await asyncio.sleep(0.8)
        
        # Check if user is in active conversation
        if user_id in ACTIVE_CONNECTIONS:
            partner_id = ACTIVE_CONNECTIONS[user_id]
            
            # Show some chat tips with animation
            chat_tips = [
                "💡 *Chat Tip*: You can still use all commands while chatting.",
                "💡 *Chat Tip*: Send photos, stickers or voice messages as usual.",
                "💡 *Chat Tip*: Use /disconnect if you want to end this conversation."
            ]
            
            # Choose a random tip
            tip = random.choice(chat_tips)
            
            # Send encouraging message to continue the conversation
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"✅ *Chat Active*\n\nYou're still connected with your partner. Just type to send messages!\n\n{tip}",
                parse_mode='Markdown'
            )
        else:
            # User is not in an active chat
            # Create options to find a new partner
            connect_keyboard = [
                [InlineKeyboardButton("🔄 Find New Partner", callback_data="connect_now")],
                [InlineKeyboardButton("⚙️ Change Chat Mode", callback_data="change_mode")]
            ]
            connect_markup = InlineKeyboardMarkup(connect_keyboard)
            
            await context.bot.send_message(
                chat_id=chat_id,
                text="❓ *No Active Chat*\n\nYou're not currently connected to anyone. Would you like to find a new chat partner?",
                reply_markup=connect_markup,
                parse_mode='Markdown'
            )
        
        await asyncio.sleep(0.7)
        # Create options keyboard
        next_options = [
            [InlineKeyboardButton("🔄 Try Again", callback_data="try_again")],
            [InlineKeyboardButton("🔀 Change Chat Mode", callback_data="change_mode")]
        ]
        next_options_markup = InlineKeyboardMarkup(next_options)
        
        await context.bot.send_message(
            chat_id=chat_id,
            text="🎮 *What would you like to do next?*",
            reply_markup=next_options_markup,
            parse_mode='Markdown'
        )
        
    elif data == "show_tips":
        # Show chat tips in an animated sequence
        chat_id = update.effective_chat.id
        
        # Create initial tips message
        tips_message = await context.bot.send_message(
            chat_id=chat_id,
            text="💡 *Loading chat tips*...",
            parse_mode='Markdown'
        )
        
        # Tips animation sequence
        tips_content = [
            "💡 *Chat Tips*\n\n1️⃣ Remember to be respectful",
            "💡 *Chat Tips*\n\n1️⃣ Remember to be respectful\n2️⃣ Your messages are anonymous",
            "💡 *Chat Tips*\n\n1️⃣ Remember to be respectful\n2️⃣ Your messages are anonymous\n3️⃣ Use /reveal to request identity exchange",
            "💡 *Chat Tips*\n\n1️⃣ Remember to be respectful\n2️⃣ Your messages are anonymous\n3️⃣ Use /reveal to request identity exchange\n4️⃣ Use /mood to send emoji reactions",
            "💡 *Chat Tips*\n\n1️⃣ Remember to be respectful\n2️⃣ Your messages are anonymous\n3️⃣ Use /reveal to request identity exchange\n4️⃣ Use /mood to send emoji reactions\n5️⃣ Use /disconnect to end the conversation"
        ]
        
        for content in tips_content:
            await asyncio.sleep(0.7)
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=tips_message.message_id,
                text=content,
                parse_mode='Markdown'
            )
            
        # Add a close button
        close_keyboard = [[InlineKeyboardButton("✅ Got it", callback_data="close_tips")]]
        close_markup = InlineKeyboardMarkup(close_keyboard)
        
        await context.bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=tips_message.message_id,
            reply_markup=close_markup
        )
        
    elif data == "close_tips":
        # Close the tips message
        await query.edit_message_text(
            text="✅ *Tips closed*\n\nEnjoy your anonymous conversation!",
            parse_mode='Markdown'
        )
        
    elif data == "request_reveal":
        # Shortcut for reveal identity command
        await reveal_identity(update, context)
        
    # Handle mood reaction button clicks
    elif data.startswith("mood_"):
        mood_type = data.split("_")[1]
        
        # Check if user is in active conversation
        if user_id in ACTIVE_CONNECTIONS:
            partner_id = ACTIVE_CONNECTIONS[user_id]
            
            # Process mood reaction
            mood_emoji_map = {
                "heart": "❤️", "laugh": "😂", "wow": "😮", "sad": "😢", "angry": "😡"
            }
            emoji = mood_emoji_map.get(mood_type, "👍")
            
            # Show sender acknowledgment
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"✅ You reacted with {emoji}"
            )
            
            # Show fancy animation to recipient
            reaction_message = await context.bot.send_message(
                chat_id=partner_id,
                text="💫 *Receiving reaction*...",
                parse_mode='Markdown'
            )
            
            await asyncio.sleep(0.7)
            
            # Different displays for different reactions
            if mood_type == "heart":
                display = f"❤️ *Someone liked your message* ❤️\n\nYour chat partner reacted with {emoji}"
            elif mood_type == "laugh":
                display = f"😂 *Someone found your message funny* 😂\n\nYour chat partner reacted with {emoji}"
            elif mood_type == "wow":
                display = f"😮 *Someone was surprised by your message* 😮\n\nYour chat partner reacted with {emoji}"
            elif mood_type == "sad":
                display = f"😢 *Someone felt sad about your message* 😢\n\nYour chat partner reacted with {emoji}"
            elif mood_type == "angry":
                display = f"😡 *Someone reacted strongly to your message* 😡\n\nYour chat partner reacted with {emoji}"
            else:
                display = f"👍 *Someone reacted to your message*\n\nYour chat partner reacted with {emoji}"
            
            await context.bot.edit_message_text(
                chat_id=partner_id,
                message_id=reaction_message.message_id,
                text=display,
                parse_mode='Markdown'
            )
    
    # Handle mood selection from mood menu
    elif data.startswith("select_mood_"):
        mood_name = data.split("_")[2]
        
        # Check if user is in active conversation
        if user_id in ACTIVE_CONNECTIONS:
            partner_id = ACTIVE_CONNECTIONS[user_id]
            
            # Get mood emoji mapping
            mood_emojis = {
                "happy": "😊", "laugh": "😂", "love": "❤️", "wow": "😮", 
                "sad": "😢", "angry": "😡", "thumbsup": "👍", "fire": "🔥",
                "clap": "👏", "thinking": "🤔", "cool": "😎", "party": "🎉"
            }
            emoji = mood_emojis.get(mood_name, "👍")
            
            # Acknowledge selection
            await query.edit_message_text(
                text=f"✅ *Mood selected*: {emoji}\n\nSending your reaction...",
                parse_mode='Markdown'
            )
            
            # Send animated reaction to partner
            partner_message = await context.bot.send_message(
                chat_id=partner_id,
                text="💭 *Incoming reaction*...",
                parse_mode='Markdown'
            )
            
            await asyncio.sleep(0.8)
            
            # Display animated effect based on the mood type
            display_text = f"💭 Your chat partner sent a reaction: {emoji}"
            
            # Create enhanced display for certain reactions
            if mood_name in ["love", "fire", "party"]:
                # Create more decorative display for expressive reactions
                decorations = {
                    "love": "❤️ 💕 ❤️ 💕 ❤️",
                    "fire": "🔥 🔥 🔥 🔥 🔥",
                    "party": "🎉 🎊 🎉 🎊 🎉"
                }
                display_text = f"💫 *Reaction Received!*\n\n{decorations.get(mood_name)}\n\nYour chat partner reacted with {emoji}\n{decorations.get(mood_name)}"
            
            await context.bot.edit_message_text(
                chat_id=partner_id,
                message_id=partner_message.message_id,
                text=display_text,
                parse_mode='Markdown'
            )
            
            # Confirm delivery to sender
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"✅ *Reaction delivered*\n\nYou sent: {emoji}",
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text(
                text="❌ You're not in an active conversation. Find a chat partner first to send reactions.",
                parse_mode='Markdown'
            )
    
    elif data == "cancel_mood":
        # Cancel mood selection
        await query.edit_message_text(
            text="🚫 *Mood selection cancelled*\n\nNo reaction was sent.",
            parse_mode='Markdown'
        )
        
    elif data == "try_mood":
        # User clicked the "Try Mood Reactions" button
        # Show animated mood selection interface
        await query.edit_message_text(
            text="💭 *Opening mood selector*...",
            parse_mode='Markdown'
        )
        
        await asyncio.sleep(0.8)
        
        # Get the list of available moods
        mood_emojis = {
            "happy": "😊", "laugh": "😂", "love": "❤️", "wow": "😮", 
            "sad": "😢", "angry": "😡", "thumbsup": "👍", "fire": "🔥",
            "clap": "👏", "thinking": "🤔", "cool": "😎", "party": "🎉"
        }
        
        # Build attractive emoji grid for mood selection
        keyboard = []
        mood_rows = [list(mood_emojis.items())[i:i+4] for i in range(0, len(mood_emojis), 4)]
        
        for row in mood_rows:
            keyboard_row = []
            for mood_name, emoji in row:
                keyboard_row.append(InlineKeyboardButton(
                    f"{emoji}", callback_data=f"select_mood_{mood_name}"
                ))
            keyboard.append(keyboard_row)
        
        # Add cancel button
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_mood")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Show final mood selection interface
        await query.edit_message_text(
            text="💭 *Express Your Emotion*\n\nChoose a reaction to send to your chat partner:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    # Handle group chat mood reactions
    elif data.startswith("group_mood_"):
        # Parse the mood, group ID, and sender number
        try:
            _, mood_type, group_id, user_number = data.split("_")
            user_number = int(user_number)
            
            # Get user preferences
            user_prefs = get_user_preference(user_id)
            
            # Check if user is in the same group
            if user_prefs['mode'] == ChatMode.GROUP and user_prefs['group_id'] == group_id and group_id in GROUP_CHATS:
                group = GROUP_CHATS[group_id]
                
                # Get emoji based on mood type
                mood_emoji_map = {
                    "like": "👍", "heart": "❤️", "laugh": "😂", "wow": "😮", "clap": "👏"
                }
                emoji = mood_emoji_map.get(mood_type, "👍")
                
                # Get reactor's number in the group for identification
                member_list = list(group.members)
                reactor_number = member_list.index(user_id) + 1 if user_id in member_list else 0
                
                # Acknowledge the reaction
                await query.edit_message_text(
                    text=f"{query.message.text}\n\n{emoji} Reacted by Member #{reactor_number}",
                )
                
                # Notify all other group members about the reaction
                for member_id in group.members:
                    if member_id != user_id:  # Don't send to the reactor
                        try:
                            await context.bot.send_message(
                                chat_id=member_id,
                                text=f"💫 *Group Reaction*\n\nMember #{reactor_number} reacted with {emoji} to a message from Member #{user_number}",
                                parse_mode='Markdown'
                            )
                        except Exception as e:
                            logger.error(f"Error sending reaction notification to group member {member_id}: {e}")
                
                # If the message was from a specific user, notify them specially
                if user_number > 0 and user_number <= len(member_list):
                    original_sender_id = member_list[user_number - 1]
                    if original_sender_id != user_id:  # Don't send to self
                        try:
                            # Create an animated special notification for the message author
                            reaction_message = await context.bot.send_message(
                                chat_id=original_sender_id,
                                text="💫 *Someone is reacting to your message*...",
                                parse_mode='Markdown'
                            )
                            
                            await asyncio.sleep(0.8)
                            
                            # Customize notification based on reaction type
                            notification_text = f"💫 *Group Member #{reactor_number} reacted to your message*\n\nThey sent: {emoji}"
                            
                            # Enhanced notification for certain reaction types
                            if mood_type == "heart":
                                notification_text = f"❤️ *Someone liked your message in the group*\n\nGroup Member #{reactor_number} reacted with {emoji}"
                            elif mood_type == "clap":
                                notification_text = f"👏 *Your message received applause*\n\nGroup Member #{reactor_number} is clapping for your message {emoji}"
                            elif mood_type == "laugh":
                                notification_text = f"😂 *Your message made someone laugh*\n\nGroup Member #{reactor_number} found your message funny {emoji}"
                            
                            await context.bot.edit_message_text(
                                chat_id=original_sender_id,
                                message_id=reaction_message.message_id,
                                text=notification_text,
                                parse_mode='Markdown'
                            )
                        except Exception as e:
                            logger.error(f"Error sending special reaction to original sender {original_sender_id}: {e}")
            else:
                # User is not in the group anymore
                await query.edit_message_text(
                    text=f"{query.message.text}\n\n❌ You're no longer in this group chat."
                )
        except Exception as e:
            logger.error(f"Error handling group mood reaction: {e}")
            await query.edit_message_text(
                text=f"{query.message.text}\n\n❌ Error processing reaction."
            )

async def invite_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate an invite link for a group or channel."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Check if the bot is an admin in the chat
    try:
        bot_member = await context.bot.get_chat_member(chat_id, context.bot.id)
        if bot_member.status not in ['administrator', 'creator']:
            await context.bot.send_message(
                chat_id=chat_id, 
                text="⚠️ I need to be an admin in this group/channel to create invite links!"
            )
            return
        
        # Generate the invite link
        invite_link = await context.bot.create_chat_invite_link(chat_id)
        
        await context.bot.send_message(
            chat_id=chat_id, 
            text=f"🔗 Here's your invite link: {invite_link.invite_link}"
        )
    except Exception as e:
        logger.error(f"Error creating invite link: {e}")
        await context.bot.send_message(
            chat_id=chat_id, 
            text="❌ Error creating invite link. Make sure I'm an admin with the right permissions."
        )

async def topic_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display available topics for topic-based chat with animations"""
    from config import SYSTEM_CONFIG, BANNED_USERS
    from admin import is_admin
    
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Add user to ALL_USERS dictionary for broadcasts
    ALL_USERS[user_id] = update.effective_user
    
    # Check if user is banned
    if user_id in BANNED_USERS and not is_admin(user_id):
        await context.bot.send_message(
            chat_id=chat_id,
            text="⛔ *You have been banned from using this bot.*\n\nIf you think this is a mistake, please contact the administrator.",
            parse_mode='Markdown'
        )
        return
        
    # Check for maintenance mode - only admins can use the bot when in maintenance
    if SYSTEM_CONFIG["maintenance_mode"] and not is_admin(user_id):
        await context.bot.send_message(
            chat_id=chat_id,
            text="🛠️ *Bot Maintenance Mode*\n\nThe bot is currently under maintenance and temporarily unavailable.\n\nPlease try again later.",
            parse_mode='Markdown'
        )
        return
    
    # Set user preference to topic mode
    set_user_preference(user_id, mode=ChatMode.TOPIC)
    
    # Initial loading animation
    topic_intro = await context.bot.send_message(
        chat_id=chat_id,
        text="📋 *Loading topic categories*...",
        parse_mode='Markdown'
    )
    
    # Topic category intro animation
    topic_intro_steps = [
        "📋 *Topic-Based Matching*\n\nFind users with similar interests...",
        "📋 *Topic-Based Matching*\n\nChoose a conversation topic to match with like-minded people",
        "📋 *Topic-Based Matching*\n\nOur algorithm will connect you with users interested in the same subject"
    ]
    
    for step in topic_intro_steps:
        await asyncio.sleep(0.8)
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=topic_intro.message_id,
            text=step,
            parse_mode='Markdown'
        )
    
    # Add emoji icons for each topic to make them more visually appealing
    topic_emojis = {
        "arts": "🎨", "books": "📚", "movies": "🎬", "music": "🎵", 
        "sports": "⚽", "technology": "💻", "gaming": "🎮", "travel": "✈️",
        "food": "🍕", "science": "🔬", "languages": "🗣️", "pets": "🐾", 
        "other": "🔍"
    }
    
    # Send typing indicator before showing topics
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    await asyncio.sleep(1)
    
    # Create topic selection buttons with emojis
    topic_keyboard = []
    for i in range(0, len(AVAILABLE_TOPICS), 2):
        row = []
        topic1 = AVAILABLE_TOPICS[i]
        emoji1 = topic_emojis.get(topic1, "")
        button_text1 = f"{emoji1} {topic1.capitalize()}"
        row.append(InlineKeyboardButton(button_text1, callback_data=f"topic_{topic1}"))
        
        if i + 1 < len(AVAILABLE_TOPICS):
            topic2 = AVAILABLE_TOPICS[i+1]
            emoji2 = topic_emojis.get(topic2, "")
            button_text2 = f"{emoji2} {topic2.capitalize()}"
            row.append(InlineKeyboardButton(button_text2, callback_data=f"topic_{topic2}"))
        
        topic_keyboard.append(row)
    
    # Add a back button
    topic_keyboard.append([InlineKeyboardButton("↩️ Back to Chat Modes", callback_data="change_mode")])
    
    reply_markup = InlineKeyboardMarkup(topic_keyboard)
    
    # Final message with topic selection
    await context.bot.send_message(
        chat_id=chat_id,
        text="🌟 *Select a Topic*\n\nChoose a conversation topic to find your perfect chat partner:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    # Add helper text about what happens next
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    await asyncio.sleep(1)
    
    await context.bot.send_message(
        chat_id=chat_id,
        text="ℹ️ *What happens next?*\n\nAfter selecting a topic, use /connect to start searching for a partner interested in the same topic.",
        parse_mode='Markdown'
    )

async def group_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manage group chats with animations - create or join existing groups"""
    from config import SYSTEM_CONFIG, BANNED_USERS
    from admin import is_admin
    
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Add user to ALL_USERS dictionary for broadcasts
    ALL_USERS[user_id] = update.effective_user
    
    # Check if user is banned
    if user_id in BANNED_USERS and not is_admin(user_id):
        await context.bot.send_message(
            chat_id=chat_id,
            text="⛔ *You have been banned from using this bot.*\n\nIf you think this is a mistake, please contact the administrator.",
            parse_mode='Markdown'
        )
        return
        
    # Check for maintenance mode - only admins can use the bot when in maintenance
    if SYSTEM_CONFIG["maintenance_mode"] and not is_admin(user_id):
        await context.bot.send_message(
            chat_id=chat_id,
            text="🛠️ *Bot Maintenance Mode*\n\nThe bot is currently under maintenance and temporarily unavailable.\n\nPlease try again later.",
            parse_mode='Markdown'
        )
        return
    
    # Set user preference to group mode
    set_user_preference(user_id, mode=ChatMode.GROUP)
    
    # Initial loading animation
    group_intro = await context.bot.send_message(
        chat_id=chat_id,
        text="👥 *Loading group chat options*...",
        parse_mode='Markdown'
    )
    
    # Check if user is already in a group
    user_prefs = get_user_preference(user_id)
    
    if user_prefs['group_id'] in GROUP_CHATS:
        group = GROUP_CHATS[user_prefs['group_id']]
        
        # Animate group info loading
        group_info_steps = [
            f"👥 *Group Chat: {group.name}*\n\nChecking member status...",
            f"👥 *Group Chat: {group.name}*\n\nLoading group information...",
            f"👥 *Group Chat: {group.name}*\n\nRetrieving membership details..."
        ]
        
        for step in group_info_steps:
            await asyncio.sleep(0.8)
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=group_intro.message_id,
                text=step,
                parse_mode='Markdown'
            )
        
        # Create group management buttons
        keyboard = [
            [InlineKeyboardButton("❌ Leave Group", callback_data=f"leave_group_{user_prefs['group_id']}")],
            [InlineKeyboardButton("👥 View Members", callback_data=f"view_members_{user_prefs['group_id']}")],
            [InlineKeyboardButton("💬 Send Message", callback_data=f"group_message_{user_prefs['group_id']}")]
        ]
        
        # Add admin options if user is the creator
        if group.creator_id == user_id:
            keyboard.append([InlineKeyboardButton("👑 Group Admin Panel", callback_data=f"manage_group_{user_prefs['group_id']}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Show final group info with animated typing indicator
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        await asyncio.sleep(1)
        
        # Get emoji for member count visualization
        member_emoji = "👤" * min(len(group.members), 5)  # Maximum 5 icons
        
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=group_intro.message_id,
            text=f"👥 *Group Chat: {group.name}*\n\n"
                 f"You're currently in this group chat with {len(group.members)} members.\n"
                 f"{member_emoji}\n\n"
                 f"Select an option below to manage your group experience:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        # Animate group options for new users
        group_option_steps = [
            "👥 *Group Chat Mode*\n\nExploring group options...",
            "👥 *Group Chat Mode*\n\nYou're not in any group yet. Loading choices...",
            "👥 *Group Chat Mode*\n\nYou can create a new group or join an existing one."
        ]
        
        for step in group_option_steps:
            await asyncio.sleep(0.8)
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=group_intro.message_id,
                text=step,
                parse_mode='Markdown'
            )
        
        # Show typing indicator before displaying buttons
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        await asyncio.sleep(1)
        
        # Show group options with enhanced buttons
        group_keyboard = [
            [InlineKeyboardButton("✨ Create New Group", callback_data="group_create")],
            [InlineKeyboardButton("🔍 Browse Public Groups", callback_data="group_browse")],
            [InlineKeyboardButton("↩️ Back to Chat Modes", callback_data="change_mode")]
        ]
        reply_markup = InlineKeyboardMarkup(group_keyboard)
        
        # Send final options menu
        await context.bot.send_message(
            chat_id=chat_id,
            text="👥 *Anonymous Group Chat*\n\n"
                 "Start or join a group conversation with multiple anonymous users.\n\n"
                 "• Create a new group with a custom name\n"
                 "• Browse and join existing public groups\n"
                 "• Chat anonymously with multiple people at once",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        # Add a hint about group chats with typing animation
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        await asyncio.sleep(1.2)
        
        await context.bot.send_message(
            chat_id=chat_id,
            text="💡 *Group Chat Tip*\n\n"
                 "In group chats, all members remain anonymous. You'll be identified by a number (e.g., Member #1) "
                 "to maintain privacy while chatting with multiple people.",
            parse_mode='Markdown'
        )

async def mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Switch between different chat modes with animated interface"""
    from config import SYSTEM_CONFIG, BANNED_USERS
    from admin import is_admin
    
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Add user to ALL_USERS dictionary for broadcasts
    ALL_USERS[user_id] = update.effective_user
    
    # Check if user is banned
    if user_id in BANNED_USERS and not is_admin(user_id):
        await context.bot.send_message(
            chat_id=chat_id,
            text="⛔ *You have been banned from using this bot.*\n\nIf you think this is a mistake, please contact the administrator.",
            parse_mode='Markdown'
        )
        return
        
    # Check for maintenance mode - only admins can use the bot when in maintenance
    if SYSTEM_CONFIG["maintenance_mode"] and not is_admin(user_id):
        await context.bot.send_message(
            chat_id=chat_id,
            text="🛠️ *Bot Maintenance Mode*\n\nThe bot is currently under maintenance and temporarily unavailable.\n\nPlease try again later.",
            parse_mode='Markdown'
        )
        return
    
    # Get current mode for reference
    user_prefs = get_user_preference(user_id)
    current_mode = user_prefs['mode']
    
    # Initial loading animation
    mode_intro = await context.bot.send_message(
        chat_id=chat_id,
        text="🔀 *Loading chat modes*...",
        parse_mode='Markdown'
    )
    
    # Mode selection animation
    mode_steps = [
        "🔀 *Chat Modes*\n\nDiscovering available options...",
        "🔀 *Chat Modes*\n\nPreparing personalized recommendations...",
        "🔀 *Chat Modes*\n\nSelect the perfect way to connect:"
    ]
    
    for step in mode_steps:
        await asyncio.sleep(0.8)
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=mode_intro.message_id,
            text=step,
            parse_mode='Markdown'
        )
    
    # Detailed mode descriptions with visual indicators
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    await asyncio.sleep(1)
    
    # Create enhanced mode cards with descriptive text
    one_on_one_desc = "✨ Random matching with any available user\n💬 Private one-to-one conversations\n🔒 Complete anonymity"
    topic_desc = "🔍 Find partners with shared interests\n📚 13 topic categories to choose from\n🎯 More meaningful conversations"
    group_desc = "👥 Multi-user anonymous chats\n✏️ Create or join existing groups\n🌐 Community-style interaction"
    
    # Highlight current mode
    current_indicator = "✅ "
    one_on_one_prefix = current_indicator if current_mode == ChatMode.ONE_ON_ONE else ""
    topic_prefix = current_indicator if current_mode == ChatMode.TOPIC else ""
    group_prefix = current_indicator if current_mode == ChatMode.GROUP else ""
    
    # Create enhanced mode selection buttons with visual appeal
    keyboard = [
        [InlineKeyboardButton(f"{one_on_one_prefix}1️⃣ One-on-One Chat", callback_data="mode_one_on_one")],
        [InlineKeyboardButton(f"{topic_prefix}📋 Topic-Based Chat", callback_data="mode_topic")],
        [InlineKeyboardButton(f"{group_prefix}👥 Group Chat", callback_data="mode_group")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send the mode selection message
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"🔀 *Chat Modes*\n\n"
             f"*1️⃣ One-on-One Chat*\n{one_on_one_desc}\n\n"
             f"*📋 Topic-Based Chat*\n{topic_desc}\n\n"
             f"*👥 Group Chat*\n{group_desc}\n\n"
             f"Select your preferred mode below:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    # Add quick connect button as follow-up
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    await asyncio.sleep(1)
    
    # Quick connect buttons
    connect_keyboard = [[InlineKeyboardButton("🚀 Connect Now", callback_data="connect_now")]]
    connect_markup = InlineKeyboardMarkup(connect_keyboard)
    
    await context.bot.send_message(
        chat_id=chat_id,
        text="💡 *Pro Tip*: After selecting a mode, click 'Connect Now' or use /connect to find a chat partner immediately.",
        reply_markup=connect_markup,
        parse_mode='Markdown'
    )

async def leave_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Leave a group chat"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    user_prefs = get_user_preference(user_id)
    
    if user_prefs['mode'] == ChatMode.GROUP and user_prefs['group_id'] in GROUP_CHATS:
        group_id = user_prefs['group_id']
        group_name = GROUP_CHATS[group_id].name
        
        # Leave the group
        result = leave_group(user_id, group_id)
        
        if result == "deleted":
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"👋 You have left the group '{group_name}'. As you were the last member, the group has been deleted."
            )
        elif result == "transferred":
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"👋 You have left the group '{group_name}'. As you were the creator, admin privileges have been transferred to another member."
            )
            
            # Notify the new creator
            new_creator_id = GROUP_CHATS[group_id].creator_id
            await context.bot.send_message(
                chat_id=new_creator_id,
                text=f"👑 You are now the admin of the group '{group_name}'!"
            )
        elif result == "left":
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"👋 You have left the group '{group_name}'."
            )
            
            # Notify remaining members
            for member_id in GROUP_CHATS[group_id].members:
                try:
                    await context.bot.send_message(
                        chat_id=member_id,
                        text=f"ℹ️ A member has left the group '{group_name}'."
                    )
                except Exception as e:
                    logger.error(f"Error notifying group member {member_id}: {e}")
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ Error leaving the group."
            )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text="ℹ️ You're not currently in any group chat."
        )

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Broadcast a message to all users (admin only)."""
    user_id = update.effective_user.id
    
    # Check if user is an admin
    if user_id not in ADMIN_IDS:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text="⚠️ You don't have permission to use this command."
        )
        return
    
    # Check if there's a message to broadcast
    if not context.args:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text="⚠️ Please provide a message to broadcast: /broadcast <message>"
        )
        return
    
    # Get the message
    message = ' '.join(context.args)
    
    # Broadcast to all users
    success_count = 0
    fail_count = 0
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text="📣 Broadcasting message to all users..."
    )
    
    for user_id in ALL_USERS:
        try:
            await context.bot.send_message(
                chat_id=user_id, 
                text=f"📣 *Broadcast message from the bot admin:*\n\n{message}",
                parse_mode='Markdown'
            )
            success_count += 1
        except Exception:
            fail_count += 1
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text=f"📊 Broadcast complete!\nSuccessful: {success_count}\nFailed: {fail_count}"
    )
