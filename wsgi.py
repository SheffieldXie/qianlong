"""
WSGI entry point for Render.com deployment
"""
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5048))
    app.run(host="0.0.0.0", port=port, debug=False)
