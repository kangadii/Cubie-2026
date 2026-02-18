"""Quick SMTP connectivity test for CubieHelp email feature."""
import os
import smtplib
import ssl
from dotenv import load_dotenv

load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
FROM_ADDR = os.getenv("FROM_ADDR", SMTP_USER)

print("=== SMTP Configuration ===")
print(f"Host: {SMTP_HOST}")
print(f"Port: {SMTP_PORT}")
print(f"User: {SMTP_USER}")
print(f"Pass: {'*' * len(SMTP_PASS) if SMTP_PASS else 'NOT SET'}")
print(f"From: {FROM_ADDR}")
print()

if not all([SMTP_HOST, SMTP_USER, SMTP_PASS]):
    print("ERROR: Missing SMTP configuration!")
    exit(1)

print("=== Testing SMTP Connection ===")
context = ssl.create_default_context()
try:
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        print(f"✓ Connected to {SMTP_HOST}:{SMTP_PORT}")
        server.starttls(context=context)
        print("✓ TLS started successfully")
        server.login(SMTP_USER, SMTP_PASS)
        print("✓ Login successful!")
        print()
        print("=== SMTP TEST PASSED ===")
        print("Email credentials are valid and connection works.")
except smtplib.SMTPAuthenticationError as e:
    print(f"✗ Authentication failed: {e}")
    print("  Check your SMTP_USER and SMTP_PASS (App Password for Gmail)")
except smtplib.SMTPConnectError as e:
    print(f"✗ Connection failed: {e}")
except Exception as e:
    print(f"✗ Error: {e}")
