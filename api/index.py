"""Vercel serverless entry point — wraps the Flask app."""

import sys
import os

# Ensure the project root is on the path so `gui` and `core` can be imported.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from gui import app  # noqa: E402, F401
