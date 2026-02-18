
import os
import logging
from analytics_tools import draft_email_tool, logger

# Configure logging to see output
logging.basicConfig(level=logging.DEBUG)
logger.setLevel(logging.DEBUG)

def test_zip_attachment():
    # Create a dummy HTML file
    dummy_file = "public/demo/test_chart.html"
    os.makedirs("public/demo", exist_ok=True)
    with open(dummy_file, "w") as f:
        f.write("<html><body><h1>Test Chart</h1><script>alert('test')</script></body></html>")
    
    recipient = ["logistiex@gmail.com"]
    subject = "Test Email with Zipped HTML Attachment"
    body = "This email should contain a zipped HTML attachment."
    
    print(f"Testing email with attachment: {dummy_file}")
    
    # This should trigger the zip logic
    result = draft_email_tool(recipient, subject, body, [dummy_file])
    
    print(f"Result: {result}")

if __name__ == "__main__":
    test_zip_attachment()
