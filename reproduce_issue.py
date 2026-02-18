import sys
import unittest
from unittest.mock import MagicMock, patch

# Mock pymssql before importing analytics_tools because we don't need real DB for this test
sys.modules["pymssql"] = MagicMock()
sys.modules["database"] = MagicMock()

# Now import the tool
from analytics_tools import draft_email_tool

# Mock logger to see output
import logging
logging.basicConfig(level=logging.DEBUG)

class TestEmailLogic(unittest.TestCase):
    @patch("analytics_tools.smtplib.SMTP")
    def test_send_to_arbitrary_email(self, mock_smtp):
        # Setup mock
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        
        # Test case: sending to a random email
        recipient = "random.user@example.com"
        print(f"\n--- Testing send to {recipient} ---")
        
        # Call the tool
        result = draft_email_tool(
            to_usernames=[recipient],
            subject="Test Subject",
            body_markdown="Test Body"
        )
        
        print(f"Result: {result}")
        
        # Verify SMTP interaction
        if mock_server.send_message.called:
            msg = mock_server.send_message.call_args[0][0]
            print(f"SMTP send_message called!")
            print(f"To: {msg['To']}")
            print(f"From: {msg['From']}")
            print(f"Subject: {msg['Subject']}")
            
            # Check if recipient matches
            self.assertIn(recipient, msg['To'])
        else:
            print("SMTP send_message was NOT called!")

    @patch("analytics_tools.smtplib.SMTP")
    def test_send_to_kangadi(self, mock_smtp):
        # Setup mock
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        
        # Test case: sending to the working email
        recipient = "kangadi@tcube360.com"
        print(f"\n--- Testing send to {recipient} ---")
        
        # Call the tool
        result = draft_email_tool(
            to_usernames=[recipient],
            subject="Test Subject",
            body_markdown="Test Body"
        )
        
        print(f"Result: {result}")
        
        if mock_server.send_message.called:
            msg = mock_server.send_message.call_args[0][0]
            print(f"SMTP send_message called!")
            print(f"To: {msg['To']}")
    
if __name__ == "__main__":
    unittest.main()
