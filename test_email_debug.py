
import os
import logging
from dotenv import load_dotenv
import pandas as pd
import sys

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("TestEmail")

# Load env vars
load_dotenv()

# Add current dir to path
sys.path.append(os.getcwd())

from analytics_tools import mail_tool, draft_email_tool, SENDER_EMAIL

print(f"SMTP User: {os.getenv('SMTP_USER')}")
print(f"Sender Email: {SENDER_EMAIL}")

try:
    # Try calling mail_tool. We pass a username that resolves to an email.
    # In `analytics_tools.py`, `_emails_for_usernames` calls `database.py` -> `run_query`.
    # Let's see if we can trigger it.
    
    # Assuming 'Admin' or 'admin' exists in UserProfile.
    print("Testing draft_email_tool...")
    
    # Create a dummy HTML file for attachment testing
    dummy_html = "public/demo/test_chart_debug.html"
    os.makedirs("public/demo", exist_ok=True)
    with open(dummy_html, "w") as f:
        f.write("<html><body><h1>Test Chart</h1></body></html>")
    
    print(f"Created dummy attachment: {dummy_html}")

    result = draft_email_tool(
        to_usernames=["admin"], 
        subject="DEBUG: Draft Email Tool Test", 
        body_markdown="This is a test email sent via **draft_email_tool** with an HTML attachment.",
        attachments=[dummy_html]
    )
    
    print(f"Result: {result}")

except Exception as e:
    print(f"CRITICAL ERROR: {e}")
    import traceback
    traceback.print_exc()
