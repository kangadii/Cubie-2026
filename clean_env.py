
content = """DB_NAME=TCube360DevDB
DB_PASSWORD=TCube@2025
DB_PORT=1433
DB_SERVER=160.153.178.38
DB_USER=sa
FROM_ADDR=kangadi.tcube@gmail.com
GOOGLE_API_KEY=AIzaSyBIK3nQybwWxxEo0OFY9xTYFD2C2Zr9S3E
SMTP_HOST=smtp.gmail.com
SMTP_PASS=katoaqvddlwxeozm
SMTP_PORT=587
SMTP_USER=kangadi.tcube@gmail.com
GEMINI_MODEL=gemini-2.5-flash
"""

with open(".env", "w", encoding="utf-8") as f:
    f.write(content)
print("Updated .env with gemini-2.5-flash model.")
