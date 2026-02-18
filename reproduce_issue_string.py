import sys
import unittest
from unittest.mock import MagicMock, patch

# Mock pymssql before importing analytics_tools
sys.modules["pymssql"] = MagicMock()
sys.modules["database"] = MagicMock()

from analytics_tools import draft_email_tool

# Mock logger
import logging
logging.basicConfig(level=logging.DEBUG)

class TestEmailStringInput(unittest.TestCase):
    @patch("analytics_tools.smtplib.SMTP")
    def test_send_with_string_input(self, mock_smtp):
        # Setup mock
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        
        # Test case: sending TO A STRING instead of a list
        # This simulates what happens if the LLM passes "foo@bar.com" instead of ["foo@bar.com"]
        recipient_str = "test@example.com"
        print(f"\n--- Testing send with STRING input: '{recipient_str}' ---")
        
        # Call the tool with string instead of list
        # type hint says list[str], but python doesn't enforce it
        try:
            result = draft_email_tool(
                to_usernames=recipient_str, # Passing string!
                subject="Test Subject",
                body_markdown="Test Body"
            )
            print(f"Result: {result}")
        except Exception as e:
            print(f"Exception caught: {e}")
        
        # Verify if SMTP was called
        if mock_server.send_message.called:
            msg = mock_server.send_message.call_args[0][0]
            print(f"SMTP send_message called!")
            print(f"To: {msg['To']}")
        else:
            print("SMTP send_message was NOT called!")

if __name__ == "__main__":
    unittest.main()
