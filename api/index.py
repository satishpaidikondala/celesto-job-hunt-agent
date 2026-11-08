"""
Vercel Serverless Function entry point for Celesto Run Ledger & Job Hunt Desk API.
Exposes the FastAPI application directly to Vercel's Python runtime.
"""
import os
import sys

# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from app.main import app

