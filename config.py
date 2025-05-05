#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Configuration variables for the Anonymous Telegram Chat Bot
"""

import os
from datetime import datetime, timedelta

# List of admin user IDs who can broadcast messages and access admin dashboard
# You can add your Telegram user ID here
ADMIN_IDS = [int(id) for id in os.environ.get("ADMIN_IDS", "").split(",") if id]

# Admin privileges configuration (Adjustable per admin)
ADMIN_PRIVILEGES = {
    "broadcast": True,       # Allow sending broadcasts
    "user_mgmt": True,       # Allow user management (ban/unban)
    "system_mgmt": True,     # Allow changing system settings
    "stats_view": True,      # Allow viewing statistics 
    "logs_view": True        # Allow viewing system logs
}

# Bot version and system info for admin dashboard
BOT_VERSION = "1.1.0"
BOT_STARTED_AT = datetime.now()

# Banned users list - user_ids of banned users
BANNED_USERS = set()

# System configurations (changeable by admins)
SYSTEM_CONFIG = {
    "connection_timeout": 45,    # Seconds to wait for a connection
    "max_group_size": 10,        # Maximum users in a group
    "reveal_timeout": 300,       # Timeout for identity reveal requests (seconds)
    "banned_words": [],          # List of banned words/phrases
    "maintenance_mode": False    # If True, only admins can use the bot
}

# Statistics tracking for admin dashboard
STATISTICS = {
    "total_messages": 0,          # Total messages sent through the bot
    "connections_made": 0,        # Total successful connections
    "active_users_today": 0,      # Users active today
    "unique_users": 0,            # Total unique users who used the bot
    "groups_created": 0,          # Total group chats created
    "last_reset": datetime.now(), # When stats were last reset
}

# Audit log for admin actions
ADMIN_LOGS = []
