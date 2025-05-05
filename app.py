#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Web frontend for the Anonymous Telegram Chat Bot
"""

import os
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "ANONYM0US_CH4T_B0T")

# Configure SQLite database
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///bot_stats.db"
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize the app with the extension
db.init_app(app)

@app.route('/')
def index():
    """Render the homepage with bot information"""
    return render_template('index.html')

@app.route('/features')
def features():
    """Render the features page"""
    return render_template('features.html')

@app.route('/help')
def help():
    """Render the help page"""
    return render_template('help.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)