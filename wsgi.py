#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
WSGI entry point for the Flask web app
"""

from app import app

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)