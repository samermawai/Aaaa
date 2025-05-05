#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Admin functionality for the Anonymous Telegram Chat Bot
"""

import os
import logging
import asyncio
import platform
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set, Union, Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import (
    ADMIN_IDS, ADMIN_PRIVILEGES, BOT_VERSION, BOT_STARTED_AT, 
    BANNED_USERS, SYSTEM_CONFIG, STATISTICS, ADMIN_LOGS
)
from utils import (
    ALL_USERS, ACTIVE_CONNECTIONS, WAITING_USERS, WAITING_BY_TOPIC,
    GROUP_CHATS, USER_PREFERENCES, ChatMode
)

logger = logging.getLogger(__name__)

# Admin utility functions
def is_admin(user_id: int) -> bool:
    """Check if a user is an admin"""
    return user_id in ADMIN_IDS

def has_privilege(user_id: int, privilege: str) -> bool:
    """Check if an admin has a specific privilege"""
    if not is_admin(user_id):
        return False
    return ADMIN_PRIVILEGES.get(privilege, False)

def log_admin_action(admin_id: int, action: str, details: str = "") -> None:
    """Log an admin action to the audit log"""
    ADMIN_LOGS.append({
        "admin_id": admin_id,
        "action": action,
        "details": details,
        "timestamp": datetime.now()
    })
    logger.info(f"Admin {admin_id} performed action: {action} - {details}")

async def update_statistics() -> None:
    """Update usage statistics for the admin dashboard"""
    # Update active users today
    today = datetime.now().date()
    active_today = set()
    
    for user_id, user in ALL_USERS.items():
        # In a real implementation, you'd track when users were last active
        # Here we're just using all users as a placeholder
        active_today.add(user_id)
    
    STATISTICS["active_users_today"] = len(active_today)
    STATISTICS["unique_users"] = len(ALL_USERS)
    
    # Other stats would be updated during normal operations

def get_system_status() -> Dict[str, Any]:
    """Get system status information for admin dashboard"""
    now = datetime.now()
    uptime = now - BOT_STARTED_AT
    uptime_str = str(uptime).split('.')[0]  # Remove microseconds
    
    return {
        "version": BOT_VERSION,
        "uptime": uptime_str,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "connections": len(ACTIVE_CONNECTIONS) // 2,  # Divide by 2 as each connection is counted twice
        "waiting_users": len(WAITING_USERS) + sum(len(users) for users in WAITING_BY_TOPIC.values()),
        "total_users": len(ALL_USERS),
        "active_groups": len(GROUP_CHATS),
        "maintenance_mode": SYSTEM_CONFIG["maintenance_mode"],
        "banned_users": len(BANNED_USERS)
    }

async def toggle_maintenance_mode(admin_id: int, enable: bool) -> None:
    """Enable or disable maintenance mode"""
    SYSTEM_CONFIG["maintenance_mode"] = enable
    
    # Log the action
    action = "enable_maintenance" if enable else "disable_maintenance"
    log_admin_action(admin_id, action)
    
    # If enabling maintenance, disconnect all non-admin users
    if enable:
        for user_id in list(ACTIVE_CONNECTIONS.keys()):
            if user_id not in ADMIN_IDS:
                partner_id = ACTIVE_CONNECTIONS.get(user_id)
                if partner_id and partner_id not in ADMIN_IDS:
                    # Both users are non-admins, disconnect them
                    if user_id in ACTIVE_CONNECTIONS:
                        del ACTIVE_CONNECTIONS[user_id]
                    if partner_id in ACTIVE_CONNECTIONS:
                        del ACTIVE_CONNECTIONS[partner_id]

async def ban_user(admin_id: int, target_user_id: int, reason: str = "") -> bool:
    """Ban a user from using the bot"""
    # Check if user exists
    if target_user_id not in ALL_USERS:
        return False
    
    # Add to banned list
    BANNED_USERS.add(target_user_id)
    
    # Log the action
    log_admin_action(admin_id, "ban_user", f"User ID: {target_user_id}, Reason: {reason}")
    
    # Disconnect the user if they're in a conversation
    if target_user_id in ACTIVE_CONNECTIONS:
        partner_id = ACTIVE_CONNECTIONS[target_user_id]
        
        # Remove from active connections
        if target_user_id in ACTIVE_CONNECTIONS:
            del ACTIVE_CONNECTIONS[target_user_id]
        if partner_id in ACTIVE_CONNECTIONS:
            del ACTIVE_CONNECTIONS[partner_id]
    
    # Remove from any waiting lists
    if target_user_id in WAITING_USERS:
        WAITING_USERS.remove(target_user_id)
    
    for topic, users in WAITING_BY_TOPIC.items():
        if target_user_id in users:
            users.remove(target_user_id)
    
    # Remove from any groups
    for group_id, group in list(GROUP_CHATS.items()):
        if target_user_id in group.members:
            group.members.remove(target_user_id)
            # If the group is now empty, delete it
            if not group.members:
                del GROUP_CHATS[group_id]
    
    return True

async def unban_user(admin_id: int, target_user_id: int) -> bool:
    """Unban a user"""
    if target_user_id in BANNED_USERS:
        BANNED_USERS.remove(target_user_id)
        log_admin_action(admin_id, "unban_user", f"User ID: {target_user_id}")
        return True
    return False

async def get_user_info(user_id: int) -> Dict[str, Any]:
    """Get detailed information about a user"""
    user = ALL_USERS.get(user_id)
    if not user:
        return {"error": "User not found"}
    
    prefs = USER_PREFERENCES.get(user_id, {})
    mode = prefs.get('mode', ChatMode.ONE_ON_ONE)
    
    is_connected = user_id in ACTIVE_CONNECTIONS
    is_waiting = (user_id in WAITING_USERS or 
                 any(user_id in users for users in WAITING_BY_TOPIC.values()))
    
    in_group = False
    group_info = None
    if prefs.get('group_id') in GROUP_CHATS:
        in_group = True
        group = GROUP_CHATS[prefs['group_id']]
        group_info = {
            "id": group.id,
            "name": group.name,
            "members": len(group.members),
            "is_creator": group.creator_id == user_id
        }
    
    return {
        "id": user_id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "is_banned": user_id in BANNED_USERS,
        "chat_mode": mode.value if mode else "unknown",
        "topic": prefs.get('topic'),
        "is_connected": is_connected,
        "is_waiting": is_waiting,
        "in_group": in_group,
        "group_info": group_info,
        "is_admin": is_admin(user_id)
    }

# Admin command handlers
async def admin_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display the admin dashboard"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Check if user is an admin
    if not is_admin(user_id):
        await context.bot.send_message(
            chat_id=chat_id,
            text="⚠️ You don't have permission to access the admin dashboard."
        )
        return
    
    # Update statistics
    await update_statistics()
    
    # Get system status
    status = get_system_status()
    
    # Create fancy dashboard message with statistics
    dashboard_text = (
        f"🛠️ *ADMIN DASHBOARD*\n\n"
        f"🤖 *Bot Status*\n"
        f"Version: {status['version']}\n"
        f"Uptime: {status['uptime']}\n"
        f"Platform: {status['platform']}\n"
        f"Python: {status['python']}\n\n"
        
        f"👥 *Users and Connections*\n"
        f"Total Users: {status['total_users']}\n"
        f"Active Connections: {status['connections']}\n"
        f"Waiting Users: {status['waiting_users']}\n"
        f"Active Groups: {status['active_groups']}\n"
        f"Banned Users: {status['banned_users']}\n\n"
        
        f"📊 *Statistics*\n"
        f"Messages Today: {STATISTICS['total_messages']}\n"
        f"Connections Made: {STATISTICS['connections_made']}\n"
        f"Active Today: {STATISTICS['active_users_today']}\n"
        f"Groups Created: {STATISTICS['groups_created']}\n\n"
        
        f"⚙️ *System Configuration*\n"
        f"Maintenance Mode: {'✅ ON' if status['maintenance_mode'] else '❌ OFF'}\n"
        f"Connection Timeout: {SYSTEM_CONFIG['connection_timeout']}s\n"
        f"Max Group Size: {SYSTEM_CONFIG['max_group_size']}\n"
        f"Banned Words: {len(SYSTEM_CONFIG['banned_words'])}\n"
    )
    
    # Create admin action buttons
    keyboard = [
        [
            InlineKeyboardButton("👤 User Management", callback_data="admin_users"),
            InlineKeyboardButton("📊 Statistics", callback_data="admin_stats")
        ],
        [
            InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
            InlineKeyboardButton("⚙️ System Config", callback_data="admin_config")
        ]
    ]
    
    # Add maintenance mode toggle button
    if status['maintenance_mode']:
        keyboard.append([InlineKeyboardButton("🟢 Disable Maintenance Mode", callback_data="admin_maint_off")])
    else:
        keyboard.append([InlineKeyboardButton("🔴 Enable Maintenance Mode", callback_data="admin_maint_on")])
    
    # Add system logs button
    keyboard.append([InlineKeyboardButton("📜 View Logs", callback_data="admin_logs")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send the dashboard
    await context.bot.send_message(
        chat_id=chat_id,
        text=dashboard_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    # Log admin dashboard access
    log_admin_action(user_id, "access_dashboard")

async def admin_user_management(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display user management interface"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Check if user is an admin with user management privileges
    if not is_admin(user_id) or not has_privilege(user_id, "user_mgmt"):
        await context.bot.send_message(
            chat_id=chat_id,
            text="⚠️ You don't have permission to manage users."
        )
        return
    
    # Create user management interface
    # Show total users and options to search, ban/unban
    user_count = len(ALL_USERS)
    banned_count = len(BANNED_USERS)
    
    management_text = (
        f"👤 *USER MANAGEMENT*\n\n"
        f"Total users: {user_count}\n"
        f"Banned users: {banned_count}\n\n"
        f"Use the buttons below to manage users or search for a specific user with:\n"
        f"`/admin_find_user <user_id or username>`"
    )
    
    # Create action buttons
    keyboard = [
        [
            InlineKeyboardButton("🔍 Search User", callback_data="admin_search_user"),
            InlineKeyboardButton("🚫 View Banned", callback_data="admin_view_banned")
        ],
        [
            InlineKeyboardButton("👥 Active Users", callback_data="admin_active_users"),
            InlineKeyboardButton("👥 Waiting Users", callback_data="admin_waiting_users")
        ],
        [InlineKeyboardButton("↩️ Back to Dashboard", callback_data="admin_dashboard")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send the management interface
    await context.bot.send_message(
        chat_id=chat_id,
        text=management_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    # Log admin user management access
    log_admin_action(user_id, "access_user_management")

async def admin_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE, target: str = None) -> None:
    """Enhanced broadcast messaging with targeting options"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Check if user is an admin with broadcast privileges
    if not is_admin(user_id) or not has_privilege(user_id, "broadcast"):
        await context.bot.send_message(
            chat_id=chat_id,
            text="⚠️ You don't have permission to broadcast messages."
        )
        return
        
    # If a specific target is specified (from command handler), handle the broadcast now
    if target:
        # Get the message
        if not context.args:
            await context.bot.send_message(
                chat_id=chat_id, 
                text=f"⚠️ Please provide a message to broadcast: /broadcast_{target} <message>"
            )
            return
            
        # Get the message
        message = ' '.join(context.args)
        
        # Different targeting options
        if target == "all":
            # Broadcast to all users
            target_users = list(ALL_USERS.keys())
            target_name = "all users"
        elif target == "active":
            # Only users in active connections
            target_users = list(ACTIVE_CONNECTIONS.keys())
            target_name = "active users"
        elif target == "waiting":
            # Only users waiting for a match
            target_users = WAITING_USERS + [
                user_id for topic_users in WAITING_BY_TOPIC.values() for user_id in topic_users
            ]
            target_name = "waiting users"
        elif target == "groups":
            # Only users in group chats
            target_users = []
            for group in GROUP_CHATS.values():
                target_users.extend(list(group.members))
            target_name = "group members"
        else:
            # Default to all users
            target_users = list(ALL_USERS.keys())
            target_name = "all users"
        
        # Remove duplicates
        target_users = list(set(target_users))
        
        # Broadcast
        await send_broadcast(update, context, message, target_users, target_name)
        return
    
    # Show broadcast options
    broadcast_text = (
        f"📢 *BROADCAST MESSAGE*\n\n"
        f"Select your target audience:\n\n"
        f"• All Users: Message all users of the bot\n"
        f"• Active Users: Only users in active conversations\n"
        f"• Waiting Users: Only users waiting for connections\n"
        f"• Group Members: Only users in group chats\n\n"
        f"To send a broadcast, use one of these commands:\n"
        f"`/broadcast_all <message>` - Send to all users\n"
        f"`/broadcast_active <message>` - Send to active users\n"
        f"`/broadcast_waiting <message>` - Send to waiting users\n"
        f"`/broadcast_groups <message>` - Send to group chat members"
    )
    
    # Create buttons for different broadcast options
    keyboard = [
        [
            InlineKeyboardButton("👥 All Users", callback_data="admin_broadcast_all"),
            InlineKeyboardButton("💬 Active Users", callback_data="admin_broadcast_active")
        ],
        [
            InlineKeyboardButton("⏳ Waiting Users", callback_data="admin_broadcast_waiting"),
            InlineKeyboardButton("👪 Group Members", callback_data="admin_broadcast_groups")
        ],
        [InlineKeyboardButton("↩️ Back to Dashboard", callback_data="admin_dashboard")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send the broadcast interface
    await context.bot.send_message(
        chat_id=chat_id,
        text=broadcast_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    # Log admin broadcast access
    log_admin_action(user_id, "access_broadcast_interface")

async def send_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE, message: str, target_users: List[int], target_name: str) -> None:
    """Helper function to send a broadcast message to a list of users"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Check if the message is valid
    if not message or len(message.strip()) == 0:
        await context.bot.send_message(
            chat_id=chat_id,
            text="⚠️ Cannot send empty message."
        )
        return
    
    # Format the broadcast message with header
    broadcast_message = (
        f"📢 *ADMIN BROADCAST*\n\n"
        f"{message}"
    )
    
    # Count successful deliveries
    sent_count = 0
    
    # Send to all targeted users - with progress updates for large broadcasts
    total_users = len(target_users)
    progress_message = await context.bot.send_message(
        chat_id=chat_id,
        text=f"🔄 Sending broadcast to {total_users} {target_name}... (0%)"
    )
    
    for idx, target_id in enumerate(target_users):
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=broadcast_message,
                parse_mode='Markdown'
            )
            sent_count += 1
            
            # Update progress for large broadcasts (every 5% or 20 users)
            if total_users > 20 and (idx + 1) % max(1, total_users // 20) == 0:
                progress = (idx + 1) / total_users * 100
                await progress_message.edit_text(
                    f"🔄 Sending broadcast to {total_users} {target_name}... ({progress:.1f}%)"
                )
                
        except Exception as e:
            logger.error(f"Failed to send broadcast to user {target_id}: {e}")
    
    # Update with final result
    await progress_message.edit_text(
        f"✅ Broadcast sent to {sent_count}/{total_users} {target_name}."
    )
    
    # Log the broadcast
    log_admin_action(user_id, "broadcast", f"Sent to {sent_count} {target_name}: {message[:50]}...")

async def admin_system_config(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str = None) -> None:
    """Interface for changing system configuration"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Check if user is an admin with system management privileges
    if not is_admin(user_id) or not has_privilege(user_id, "system_mgmt"):
        await context.bot.send_message(
            chat_id=chat_id,
            text="⚠️ You don't have permission to modify system configuration."
        )
        return
    
    # Handle specific configuration actions if provided
    if action:
        if not context.args:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ Please provide a value for the {action} setting."
            )
            return
            
        value = context.args[0]
        
        if action == "set_timeout":
            try:
                timeout = int(value)
                if timeout < 5 or timeout > 300:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text="⚠️ Timeout must be between 5 and 300 seconds."
                    )
                    return
                    
                SYSTEM_CONFIG["connection_timeout"] = timeout
                log_admin_action(user_id, "change_config", f"Set timeout to {timeout}s")
                
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"✅ Connection timeout set to {timeout} seconds."
                )
                
            except ValueError:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="⚠️ Timeout must be a number."
                )
                
        elif action == "set_group_size":
            try:
                size = int(value)
                if size < 2 or size > 50:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text="⚠️ Group size must be between 2 and 50 members."
                    )
                    return
                    
                SYSTEM_CONFIG["max_group_size"] = size
                log_admin_action(user_id, "change_config", f"Set max group size to {size}")
                
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"✅ Maximum group size set to {size} members."
                )
                
            except ValueError:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="⚠️ Group size must be a number."
                )
                
        elif action == "add_banned_word":
            word = value.lower()
            if word in SYSTEM_CONFIG["banned_words"]:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"⚠️ '{word}' is already in the banned words list."
                )
                return
                
            SYSTEM_CONFIG["banned_words"].append(word)
            log_admin_action(user_id, "change_config", f"Added banned word: {word}")
            
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"✅ Added '{word}' to banned words list."
            )
            
        elif action == "remove_banned_word":
            word = value.lower()
            if word not in SYSTEM_CONFIG["banned_words"]:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"⚠️ '{word}' is not in the banned words list."
                )
                return
                
            SYSTEM_CONFIG["banned_words"].remove(word)
            log_admin_action(user_id, "change_config", f"Removed banned word: {word}")
            
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"✅ Removed '{word}' from banned words list."
            )
            
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ Unknown configuration action: {action}"
            )
            
        return
    
    # Show current configuration
    config_text = (
        f"⚙️ *SYSTEM CONFIGURATION*\n\n"
        f"• Connection Timeout: {SYSTEM_CONFIG['connection_timeout']}s\n"
        f"• Max Group Size: {SYSTEM_CONFIG['max_group_size']} users\n"
        f"• Reveal Timeout: {SYSTEM_CONFIG['reveal_timeout']}s\n"
        f"• Banned Words: {len(SYSTEM_CONFIG['banned_words'])}\n"
        f"• Maintenance Mode: {'✅ ON' if SYSTEM_CONFIG['maintenance_mode'] else '❌ OFF'}\n\n"
        
        f"To change configuration, use these commands:\n"
        f"`/set_timeout <seconds>` - Set connection timeout\n"
        f"`/set_group_size <number>` - Set max group size\n"
        f"`/set_reveal_timeout <seconds>` - Set identity reveal timeout\n"
        f"`/add_banned_word <word>` - Add a banned word\n"
        f"`/remove_banned_word <word>` - Remove a banned word"
    )
    
    # Create buttons for common configuration changes
    keyboard = [
        [
            InlineKeyboardButton("⏱️ Set Timeout: 30s", callback_data="admin_set_timeout_30"),
            InlineKeyboardButton("⏱️ Set Timeout: 60s", callback_data="admin_set_timeout_60")
        ],
        [
            InlineKeyboardButton("👥 Group Size: 5", callback_data="admin_set_group_5"),
            InlineKeyboardButton("👥 Group Size: 10", callback_data="admin_set_group_10")
        ],
        [
            InlineKeyboardButton("📜 Manage Banned Words", callback_data="admin_banned_words"),
        ],
        [InlineKeyboardButton("↩️ Back to Dashboard", callback_data="admin_dashboard")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send the configuration interface
    await context.bot.send_message(
        chat_id=chat_id,
        text=config_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    # Log admin config access
    log_admin_action(user_id, "access_system_config")

async def admin_find_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Search for and display user information"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Check if user is an admin with user management privileges
    if not is_admin(user_id) or not has_privilege(user_id, "user_mgmt"):
        await context.bot.send_message(
            chat_id=chat_id,
            text="⚠️ You don't have permission to view user information."
        )
        return
    
    # Check if there's a search term
    if not context.args:
        await context.bot.send_message(
            chat_id=chat_id,
            text="⚠️ Please provide a user ID or username to search for: /admin_find_user <user_id or username>"
        )
        return
    
    # Get the search term
    search_term = context.args[0]
    target_user_id = None
    
    # Try to parse as user ID
    try:
        target_user_id = int(search_term)
        if target_user_id not in ALL_USERS:
            target_user_id = None
    except ValueError:
        # Search by username
        for uid, user in ALL_USERS.items():
            if user.username and user.username.lower() == search_term.lower().lstrip('@'):
                target_user_id = uid
                break
    
    if not target_user_id:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ User not found: {search_term}"
        )
        return
    
    # Get detailed user info
    user_info = await get_user_info(target_user_id)
    
    # Format user information
    info_text = (
        f"👤 *USER INFORMATION*\n\n"
        f"*User ID:* `{user_info['id']}`\n"
        f"*Name:* {user_info['first_name']} {user_info['last_name'] or ''}\n"
        f"*Username:* @{user_info['username'] or 'None'}\n\n"
        
        f"*Status:*\n"
        f"• Banned: {'✅ Yes' if user_info['is_banned'] else '❌ No'}\n"
        f"• Admin: {'✅ Yes' if user_info['is_admin'] else '❌ No'}\n"
        f"• Connected: {'✅ Yes' if user_info['is_connected'] else '❌ No'}\n"
        f"• Waiting: {'✅ Yes' if user_info['is_waiting'] else '❌ No'}\n"
        f"• In Group: {'✅ Yes' if user_info['in_group'] else '❌ No'}\n\n"
        
        f"*Preferences:*\n"
        f"• Chat Mode: {user_info['chat_mode']}\n"
    )
    
    if user_info['topic']:
        info_text += f"• Topic: {user_info['topic']}\n"
    
    if user_info['in_group'] and user_info['group_info']:
        info_text += (
            f"\n*Group Information:*\n"
            f"• Group ID: {user_info['group_info']['id']}\n"
            f"• Group Name: {user_info['group_info']['name']}\n"
            f"• Members: {user_info['group_info']['members']}\n"
            f"• Creator: {'✅ Yes' if user_info['group_info']['is_creator'] else '❌ No'}\n"
        )
    
    # Create action buttons
    keyboard = []
    
    # Ban/unban button
    if user_info['is_banned']:
        keyboard.append([InlineKeyboardButton("✅ Unban User", callback_data=f"admin_unban_{target_user_id}")])
    else:
        keyboard.append([InlineKeyboardButton("🚫 Ban User", callback_data=f"admin_ban_{target_user_id}")])
    
    # Disconnect button (if connected)
    if user_info['is_connected']:
        keyboard.append([InlineKeyboardButton("❌ Disconnect User", callback_data=f"admin_disconnect_{target_user_id}")])
    
    # Remove from waiting list (if waiting)
    if user_info['is_waiting']:
        keyboard.append([InlineKeyboardButton("⏹️ Remove from Waiting", callback_data=f"admin_remove_waiting_{target_user_id}")])
    
    # Remove from group (if in group)
    if user_info['in_group']:
        keyboard.append([InlineKeyboardButton("👋 Remove from Group", callback_data=f"admin_remove_group_{target_user_id}")])
    
    # Back button
    keyboard.append([InlineKeyboardButton("↩️ Back to User Management", callback_data="admin_users")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send the user information
    await context.bot.send_message(
        chat_id=chat_id,
        text=info_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    # Log admin user search
    log_admin_action(user_id, "search_user", f"Searched for: {search_term}")

# Helper function for admin actions via callback queries
async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin dashboard callback queries"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    # Check if user is an admin
    if not is_admin(user_id):
        await query.edit_message_text(
            text="⚠️ You don't have permission to access admin features."
        )
        return
    
    # Handle different admin callbacks
    if data == "admin_dashboard":
        await admin_dashboard(update, context)
    
    elif data == "admin_users":
        await admin_user_management(update, context)
    
    elif data == "admin_broadcast":
        await admin_broadcast_message(update, context)
    
    elif data == "admin_config":
        await admin_system_config(update, context)
    
    elif data == "admin_maint_on":
        await toggle_maintenance_mode(user_id, True)
        await query.edit_message_text(
            text="✅ Maintenance mode enabled. Only admins can use the bot now.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("↩️ Back to Dashboard", callback_data="admin_dashboard")
            ]])
        )
    
    elif data == "admin_maint_off":
        await toggle_maintenance_mode(user_id, False)
        await query.edit_message_text(
            text="✅ Maintenance mode disabled. All users can use the bot now.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("↩️ Back to Dashboard", callback_data="admin_dashboard")
            ]])
        )
    
    # Handle ban/unban callbacks
    elif data.startswith("admin_ban_"):
        target_id = int(data.split("_")[2])
        success = await ban_user(user_id, target_id)
        
        if success:
            await query.edit_message_text(
                text=f"✅ User {target_id} has been banned successfully.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("↩️ Back to User Management", callback_data="admin_users")
                ]])
            )
        else:
            await query.edit_message_text(
                text=f"❌ Failed to ban user {target_id}. User might not exist.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("↩️ Back to User Management", callback_data="admin_users")
                ]])
            )
    
    elif data.startswith("admin_unban_"):
        target_id = int(data.split("_")[2])
        success = await unban_user(user_id, target_id)
        
        if success:
            await query.edit_message_text(
                text=f"✅ User {target_id} has been unbanned successfully.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("↩️ Back to User Management", callback_data="admin_users")
                ]])
            )
        else:
            await query.edit_message_text(
                text=f"❌ User {target_id} was not banned or does not exist.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("↩️ Back to User Management", callback_data="admin_users")
                ]])
            )
    
    # Handle system config changes
    elif data.startswith("admin_set_timeout_"):
        timeout = int(data.split("_")[3])
        SYSTEM_CONFIG["connection_timeout"] = timeout
        log_admin_action(user_id, "change_config", f"Set timeout to {timeout}s")
        
        await query.edit_message_text(
            text=f"✅ Connection timeout set to {timeout} seconds.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("↩️ Back to System Config", callback_data="admin_config")
            ]])
        )
    
    elif data.startswith("admin_set_group_"):
        size = int(data.split("_")[3])
        SYSTEM_CONFIG["max_group_size"] = size
        log_admin_action(user_id, "change_config", f"Set max group size to {size}")
        
        await query.edit_message_text(
            text=f"✅ Maximum group size set to {size} members.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("↩️ Back to System Config", callback_data="admin_config")
            ]])
        )
    
    # Handle other admin callbacks...
    else:
        await query.edit_message_text(
            text="⚠️ Unknown admin action.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("↩️ Back to Dashboard", callback_data="admin_dashboard")
            ]])
        )