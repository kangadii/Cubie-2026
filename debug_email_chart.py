
import asyncio
import os
from analytics_tools import draft_email_tool

# Ensure demo directory exists
os.makedirs("public/demo", exist_ok=True)

# Create a dummy HTML chart file
chart_path = "public/demo/debug_chart.html"
with open(chart_path, "w") as f:
    f.write("<html><body><h1>This is a debug chart</h1></body></html>")

# Create a dummy PNG chart file (optional, just to test different types)
png_path = "public/demo/debug_chart.png"
with open(png_path, "wb") as f:
    f.write(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82')

async def test_email_with_attachment():
    print(f"Testing email with attachment: {chart_path} and {png_path}")
    
    # Use a dummy email address (or user's if available in env, but let's stick to safe test)
    # The tool resolves usernames to emails, or takes raw emails.
    recipient = "logistiex@gmail.com" # Hardcoded for now based on previous context or just a placeholder
    # Actually, let's use the env var if possible or a safe test address
    
    subject = "DEBUG: Test Email with Chart Attachment"
    body = f"This is a test email with a chart attachment.\n\nChart: {chart_path}"
    
    # Simulating what the LLM might pass (paths relative to public or absolute?)
    # analytics_tools handles /static/ prefix mapping.
    attachments = [f"/static/demo/debug_chart.html", f"/static/demo/debug_chart.png"]
    
    result = draft_email_tool([recipient], subject, body, attachments)
    print(f"Result: {result}")

if __name__ == "__main__":
    asyncio.run(test_email_with_attachment())
