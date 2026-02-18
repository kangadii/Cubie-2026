
import smtplib
import ssl
import os
import logging
from email.message import EmailMessage
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
FROM_ADDR = os.getenv("FROM_ADDR", SMTP_USER)

# Logging setup
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("SMTPDebug")

def send_debug_email(to_email):
    print(f"DEBUG: Sending to {to_email} via {SMTP_HOST}:{SMTP_PORT}")
    print(f"DEBUG: User: {SMTP_USER}")
    
    msg = EmailMessage()
    msg["Subject"] = "Debug Email - SMTP Trace"
    msg["From"] = FROM_ADDR
    msg["To"] = to_email
    msg.set_content("This is a test email to debug SMTP interaction. It verifies if the server accepts the message.")

    context = ssl.create_default_context()
    
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.set_debuglevel(2)  # Level 2 for full SMTP conversation (timestamped)
            print("--- SMTP CONNECT ---")
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            print("--- SMTP LOGIN ---")
            server.login(SMTP_USER, SMTP_PASS)
            print("--- SMTP SEND ---")
            server.send_message(msg)
            print("--- SMTP SUCCESS ---")
            print("Email sent successfully!")
    except Exception as e:
        print(f"--- SMTP FAILED ---")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # recipient = "logistiex@gmail.com" # Default test
    # Allow override
    import sys
    recipient = sys.argv[1] if len(sys.argv) > 1 else "logistiex@gmail.com"
    send_debug_email(recipient)
