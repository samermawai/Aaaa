#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Utility functions and data structures for the Anonymous Telegram Chat Bot
"""

import asyncio
import logging
from typing import Callable, Any, Optional

import random
import time
import logging
import asyncio
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Union
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, User, Update
from telegram.ext import ContextTypes
from functools import wraps

logger = logging.getLogger(__name__)

# Define chat modes
class ChatMode(Enum):
    ONE_ON_ONE = "one_on_one"  # Default 1:1 anonymous chat
    GROUP = "group"            # Group chat with multiple participants
    TOPIC = "topic"            # Topic-based matching for 1:1 chats

# Topic categories for topic-based matching
AVAILABLE_TOPICS = [
    "arts", "books", "movies", "music", "sports", 
    "technology", "gaming", "travel", "food", 
    "science", "languages", "pets", "other"
]

@dataclass
class GroupChat:
    id: str
    creator_id: int
    members: Set[int]
    name: str
    max_size: int = 10
    
    def is_full(self) -> bool:
        return len(self.members) >= self.max_size

# Main data structures
# Store waiting users for 1:1 chats: [user_id]
WAITING_USERS = []

# Store users waiting by topic: topic -> [user_id]
WAITING_BY_TOPIC = {topic: [] for topic in AVAILABLE_TOPICS}

# Store active 1:1 connections: user_id -> partner_id
ACTIVE_CONNECTIONS = {}

# Store when a user started waiting: user_id -> timestamp
WAITING_SINCE = {}

# Store user modes and preferences: user_id -> {'mode': ChatMode, 'topic': str, 'group_id': str}
USER_PREFERENCES = {}

# Store active group chats: group_id -> GroupChat object
GROUP_CHATS = {}

# Store all users who have used the bot: user_id -> User
ALL_USERS = {}

# Store identity reveal requests: requester_id -> {'partner_id': id, 'status': 'pending/accepted/rejected'}
REVEAL_REQUESTS = {}

# Timeout in seconds
TIMEOUT_SECONDS = 45

def get_user_data(user_id):
    """Get user data from the ALL_USERS dictionary"""
    return ALL_USERS.get(user_id)

def get_user_preference(user_id):
    """Get user's chat preferences or set default if not exists"""
    if user_id not in USER_PREFERENCES:
        USER_PREFERENCES[user_id] = {
            'mode': ChatMode.ONE_ON_ONE,
            'topic': None,
            'group_id': None
        }
    return USER_PREFERENCES[user_id]

def set_user_preference(user_id, mode=None, topic=None, group_id=None):
    """Set user's chat preferences"""
    prefs = get_user_preference(user_id)
    if mode:
        prefs['mode'] = mode
    if topic is not None:  # Could be empty string
        prefs['topic'] = topic
    if group_id is not None:  # Could be empty string
        prefs['group_id'] = group_id
    USER_PREFERENCES[user_id] = prefs
    return prefs

def find_partner(user_id, mode=None, topic=None):
    """Find a random chat partner based on mode and topic"""
    # Get user's chat mode if not provided
    if mode is None:
        user_prefs = get_user_preference(user_id)
        mode = user_prefs['mode']
        topic = user_prefs['topic']
    
    # For one-on-one mode
    if mode == ChatMode.ONE_ON_ONE:
        # Copy the waiting list to avoid modification during iteration
        potential_partners = WAITING_USERS.copy()
        
        # Remove the user if they're in the waiting list
        if user_id in potential_partners:
            potential_partners.remove(user_id)
        
        # If no potential partners, return None
        if not potential_partners:
            return None
        
        # Select a random partner
        partner_id = random.choice(potential_partners)
        
        # Ensure user isn't connecting to themselves
        if partner_id == user_id:
            logger.warning(f"Attempted self-connection for user {user_id}")
            return None
        
        return partner_id
    
    # For topic-based mode
    elif mode == ChatMode.TOPIC and topic in AVAILABLE_TOPICS:
        # Copy the topic waiting list
        potential_partners = WAITING_BY_TOPIC[topic].copy()
        
        # Remove the user if they're in the waiting list
        if user_id in potential_partners:
            potential_partners.remove(user_id)
        
        # If no potential partners, return None
        if not potential_partners:
            return None
        
        # Select a random partner with the same topic interest
        partner_id = random.choice(potential_partners)
        
        # Safety check
        if partner_id == user_id:
            logger.warning(f"Attempted self-connection for user {user_id} in topic {topic}")
            return None
        
        return partner_id
    
    return None

def generate_group_id():
    """Generate a unique ID for a group chat"""
    return f"grp_{int(time.time())}_{random.randint(1000, 9999)}"

def create_group_chat(creator_id, name, max_size=10):
    """Create a new group chat"""
    group_id = generate_group_id()
    
    # Create group chat object
    group = GroupChat(
        id=group_id,
        creator_id=creator_id,
        members={creator_id},  # Add creator as first member
        name=name,
        max_size=max_size
    )
    
    # Add to active groups
    GROUP_CHATS[group_id] = group
    
    # Update creator's preferences
    set_user_preference(creator_id, mode=ChatMode.GROUP, group_id=group_id)
    
    return group

def add_to_group(user_id, group_id):
    """Add a user to a group chat"""
    if group_id in GROUP_CHATS and not GROUP_CHATS[group_id].is_full():
        # Add user to group members
        GROUP_CHATS[group_id].members.add(user_id)
        
        # Update user preferences
        set_user_preference(user_id, mode=ChatMode.GROUP, group_id=group_id)
        
        return True
    return False

def leave_group(user_id, group_id):
    """Remove a user from a group chat"""
    if group_id in GROUP_CHATS and user_id in GROUP_CHATS[group_id].members:
        # Remove from group
        GROUP_CHATS[group_id].members.remove(user_id)
        
        # Reset user preferences
        set_user_preference(user_id, mode=ChatMode.ONE_ON_ONE, group_id=None)
        
        # If group is empty, delete it
        if len(GROUP_CHATS[group_id].members) == 0:
            del GROUP_CHATS[group_id]
            return "deleted"
        
        # If creator left, assign new creator
        if user_id == GROUP_CHATS[group_id].creator_id and GROUP_CHATS[group_id].members:
            GROUP_CHATS[group_id].creator_id = next(iter(GROUP_CHATS[group_id].members))
            return "transferred"
        
        return "left"
    return False

def disconnect_users(user_id, partner_id):
    """Disconnect two users from a chat"""
    # Remove from active connections
    if user_id in ACTIVE_CONNECTIONS:
        del ACTIVE_CONNECTIONS[user_id]
    if partner_id in ACTIVE_CONNECTIONS:
        del ACTIVE_CONNECTIONS[partner_id]
    
    # Clean up any pending reveal requests
    if user_id in REVEAL_REQUESTS:
        del REVEAL_REQUESTS[user_id]
    if partner_id in REVEAL_REQUESTS:
        del REVEAL_REQUESTS[partner_id]
        
    # Reset user preferences to default
    set_user_preference(user_id, mode=ChatMode.ONE_ON_ONE, topic=None, group_id=None)
    set_user_preference(partner_id, mode=ChatMode.ONE_ON_ONE, topic=None, group_id=None)

async def check_waiting_timeouts(context):
    """Check for users who have been waiting too long in any waiting list"""
    current_time = time.time()
    timed_out_users = []
    
    # Find users who have timed out and users approaching timeout
    for user_id, start_time in list(WAITING_SINCE.items()):
        # First warning at 30 seconds
        if 30 < current_time - start_time < 35:
            try:
                # Send a gentle warning with animated typing indicator
                await context.bot.send_chat_action(chat_id=user_id, action="typing")
                await context.bot.send_message(
                    chat_id=user_id,
                    text="⏳ *Still searching for your match*...\n\nIt's taking a bit longer than usual. We'll keep looking!",
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Error sending timeout warning to user {user_id}: {e}")
        
        # Full timeout at 45 seconds
        elif current_time - start_time > TIMEOUT_SECONDS:
            timed_out_users.append(user_id)
    
    # Process timed out users with animation
    for user_id in timed_out_users:
        user_prefs = get_user_preference(user_id)
        
        # Remove from appropriate waiting structures
        if user_id in WAITING_USERS:
            WAITING_USERS.remove(user_id)
            
        # Check if user was waiting for topic-based chat
        if user_prefs['mode'] == ChatMode.TOPIC and user_prefs['topic'] in AVAILABLE_TOPICS:
            topic = user_prefs['topic']
            if user_id in WAITING_BY_TOPIC[topic]:
                WAITING_BY_TOPIC[topic].remove(user_id)
        
        # Remove from the timestamp tracking
        if user_id in WAITING_SINCE:
            del WAITING_SINCE[user_id]
        
        try:
            # Send animated timeout message
            timeout_message = await context.bot.send_message(
                chat_id=user_id,
                text="⏱️ *Search timeout in progress*...",
                parse_mode='Markdown'
            )
            
            # Animation sequence - customize based on mode
            if user_prefs['mode'] == ChatMode.ONE_ON_ONE:
                timeout_steps = [
                    "⏱️ *Search timeout*\n\nAnalyzing one-on-one connection attempts...",
                    "⏱️ *Search timeout*\n\nWe've searched everywhere, but couldn't find a one-on-one match right now.",
                    "⏱️ *Search timeout*\n\nNo users are available for one-on-one chat at the moment."
                ]
            elif user_prefs['mode'] == ChatMode.TOPIC:
                topic_name = user_prefs['topic'] or "Unknown"
                timeout_steps = [
                    f"⏱️ *Search timeout*\n\nAnalyzing '{topic_name}' topic connections...",
                    f"⏱️ *Search timeout*\n\nWe've searched, but couldn't find anyone interested in '{topic_name}' right now.",
                    f"⏱️ *Search timeout*\n\nNo users available for '{topic_name}' topic chat at the moment."
                ]
            else:
                timeout_steps = [
                    "⏱️ *Search timeout*\n\nAnalyzing connection attempts...",
                    "⏱️ *Search timeout*\n\nWe've looked everywhere, but couldn't find a match right now.",
                    "⏱️ *Search timeout*\n\nNo available users match your criteria at the moment."
                ]
            
            # Play animation
            for step in timeout_steps:
                await asyncio.sleep(0.8)
                try:
                    await context.bot.edit_message_text(
                        chat_id=user_id,
                        message_id=timeout_message.message_id,
                        text=step,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Error updating timeout animation for user {user_id}: {e}")
            
            # Add some helpful suggestions
            suggestions = [
                "💡 **Suggestions:**",
                "• Try at a different time when more users might be online",
                "• Consider changing to a different chat mode",
                "• If using topic-based chat, try a more popular topic"
            ]
            
            suggestion_text = timeout_steps[-1] + "\n\n" + "\n".join(suggestions)
            
            try:
                await context.bot.edit_message_text(
                    chat_id=user_id,
                    message_id=timeout_message.message_id,
                    text=suggestion_text,
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Error updating suggestions for user {user_id}: {e}")
            
            # Create retry buttons with visual enhancements
            keyboard = [
                [InlineKeyboardButton("🔄 Try Again", callback_data="try_again")],
                [InlineKeyboardButton("🔀 Change Chat Mode", callback_data="change_mode")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Send options as a separate message for better visibility
            await context.bot.send_message(
                chat_id=user_id,
                text="✨ *What would you like to do next?*",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error sending timeout message to {user_id}: {e}")

# Admin permission decorator
def check_user_access(func):
    """Decorator to check if user is banned or if maintenance mode is on"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        from config import SYSTEM_CONFIG, BANNED_USERS
        from admin import is_admin
        
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        # Always add users to the ALL_USERS dictionary for broadcasts
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
        
        # If user has access, proceed with the command
        return await func(update, context, *args, **kwargs)
    
    return wrapper
