from __future__ import annotations

"""Utility functions exposed to the LLM for analytics queries.

This module keeps the database-execution logic in one place so that
main.py can import and register the functions when operating in
"analytics" mode.
"""

import re
from typing import Any, List, Dict
import logging

from uuid import uuid4
import os, io, base64
import plotly.express as px
import zipfile

# basic logging config (only once)
# logging.basicConfig(level=logging.INFO, format="[analytics_tools] %(levelname)s: %(message)s")
import logging
logger = logging.getLogger("CubieApp")

import pandas as pd

from database import run_query

# --- simple safety checker -------------------------------------------------
_READ_ONLY_PATTERN = re.compile(r"^\s*select\b", re.IGNORECASE)
_DISALLOWED_PATTERN = re.compile(r"\b(drop|delete|update|insert|alter|truncate)\b", re.IGNORECASE)


def _validate_sql(sql: str) -> None:
    """Raise ValueError if *sql* is not a safe, read-only SELECT statement."""
    if not _READ_ONLY_PATTERN.match(sql):
        raise ValueError("Only SELECT statements are permitted.")
    if _DISALLOWED_PATTERN.search(sql):
        raise ValueError("Dangerous keyword detected; query rejected.")


# --- tools -----------------------------------------------------------------

_MACROS: Dict[str, str] = {
    "{{CURRENT_YEAR}}": "YEAR(GETDATE())",
    "{{CURRENT_MONTH}}": "MONTH(GETDATE())",
}


def _expand_macros(sql: str) -> str:
    """Replace known macro tokens in the SQL with their T-SQL equivalent."""
    for token, replacement in _MACROS.items():
        sql = sql.replace(token, replacement)
    return sql


def _run_and_serialize(query: str) -> str:
    """Internal helper: run query and return JSON string."""
    
    # Auto-correct common LLM mistakes (LIMIT -> TOP)
    import re
    # Check for LIMIT at the end
    limit_match = re.search(r"LIMIT\s+(\d+)", query, re.IGNORECASE)
    if limit_match:
        limit_val = limit_match.group(1)
        # Remove LIMIT clause
        query = re.sub(r"LIMIT\s+\d+", "", query, flags=re.IGNORECASE).strip()
        # Insert TOP if not present
        if not re.search(r"SELECT\s+TOP", query, re.IGNORECASE):
            query = re.sub(r"SELECT\s+", f"SELECT TOP {limit_val} ", query, count=1, flags=re.IGNORECASE)
        logging.info("Auto-corrected SQL: %s", query)

    logging.info("SQL run: %s", query)
    
    # Debug: write SQL to file
    try:
        with open("sql_debug.log", "a") as f:
            f.write(f"SQL: {query}\n")
    except Exception:
        pass
        
    df = run_query(query)
    if df.empty:
        return '[{"notice":"no_rows"}]'
    return df.to_json(orient="records")  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Chart generation (Plotly)
# ---------------------------------------------------------------------------

def chart_tool(sql: str, chart_type: str, x: str, y: str, title: str | None = None, z: str | None = None) -> str:
    """Execute SQL, render a Plotly chart, save as interactive HTML, return embed code.

    Parameters
    ----------
    sql: read-only SELECT statement.
    chart_type: "line" | "bar" | "stacked_bar" | "pie" | "donut" | "area" | "scatter" | "heatmap" | "histogram".
    x, y: column names in result set to map to axes.
    title: optional chart title.
    z: optional z-axis column for 3D charts or heatmap values.
    """
    _validate_sql(sql)
    sql = _expand_macros(sql)

    df = run_query(sql)
    if df.empty:
        return '[{"notice":"no_rows"}]'

    # Enhanced color palette for professional look
    color_palette = ['#004aad', '#00a8e8', '#00d4aa', '#ffc107', '#ff6b6b', '#c44dff', '#36a2eb', '#ff9f40']
    
    if chart_type == "line":
        fig = px.line(df, x=x, y=y, title=title, markers=True)
        fig.update_traces(line=dict(width=3))
    elif chart_type == "bar":
        fig = px.bar(df, x=x, y=y, title=title, color_discrete_sequence=color_palette)
    elif chart_type == "stacked_bar":
        # Expect y to be a list of numeric columns for stacking
        y_cols = [col.strip() for col in y.split(',')]
        fig = px.bar(df, x=x, y=y_cols, title=title, color_discrete_sequence=color_palette)
        fig.update_layout(barmode='stack')
    elif chart_type == "grouped_bar":
        y_cols = [col.strip() for col in y.split(',')]
        fig = px.bar(df, x=x, y=y_cols, title=title, barmode='group', color_discrete_sequence=color_palette)
    elif chart_type == "pie":
        # For pie charts: x is labels (names), y is values
        fig = px.pie(df, names=x, values=y, title=title, color_discrete_sequence=color_palette)
        fig.update_traces(textposition='inside', textinfo='percent+label')
    elif chart_type == "donut":
        # Donut chart is a pie with a hole
        fig = px.pie(df, names=x, values=y, title=title, hole=0.4, color_discrete_sequence=color_palette)
        fig.update_traces(textposition='inside', textinfo='percent+label')
    elif chart_type == "area":
        fig = px.area(df, x=x, y=y, title=title, color_discrete_sequence=color_palette)
    elif chart_type == "scatter":
        fig = px.scatter(df, x=x, y=y, title=title, color_discrete_sequence=color_palette)
        fig.update_traces(marker=dict(size=10))
    elif chart_type == "histogram":
        fig = px.histogram(df, x=x, title=title, color_discrete_sequence=color_palette)
    elif chart_type == "heatmap":
        # If a z-column is provided use it, else count occurrences
        if z:
            fig = px.density_heatmap(df, x=x, y=y, z=z, color_continuous_scale="Blues")
        else:
            fig = px.density_heatmap(df, x=x, y=y, color_continuous_scale="Blues")
    elif chart_type == "treemap":
        # Treemap for hierarchical data
        fig = px.treemap(df, path=[x], values=y, title=title, color_discrete_sequence=color_palette)
    elif chart_type == "funnel":
        fig = px.funnel(df, x=y, y=x, title=title, color_discrete_sequence=color_palette)
    else:
        # Default to bar chart for unknown types
        logging.warning(f"Unknown chart_type '{chart_type}', defaulting to bar")
        fig = px.bar(df, x=x, y=y, title=title, color_discrete_sequence=color_palette)

    fig.update_layout(
        template="plotly_white",
        width=600,
        height=350,
        legend_title="",
        font=dict(family="Montserrat, sans-serif"),
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=False)
    )

    # Ensure output directory exists
    out_dir = "public/demo"
    os.makedirs(out_dir, exist_ok=True)
    
    # Generate unique name for HTML chart
    base_name = uuid4().hex
    html_fname = f"{base_name}.html"
    html_path = os.path.join(out_dir, html_fname)
    
    logging.info(f"Saving interactive chart to {html_path}")
    try:
        # Save as interactive HTML (for in-chat display) - this is fast and reliable
        fig.write_html(html_path, include_plotlyjs='cdn')
        logging.info("Chart HTML saved successfully.")
    except Exception as e:
        logging.error(f"Failed to save chart: {e}")
        import traceback
        logging.error(traceback.format_exc())
        raise ValueError(f"Chart generation failed: {e}")

    # Return Iframe to embed the interactive chart
    # Include the base_name so we can regenerate PNG when needed for email
    return (
        f'<iframe src="/static/demo/{html_fname}" style="width: 100%; height: 450px; border: none; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.05);"></iframe>'
        f'<div style="text-align: center; margin-top: 8px;">'
        f'<a href="/static/demo/{html_fname}" target="_blank" class="view-fullscreen-btn">View Full Screen ↗</a>'
        f'</div>'
        f'<!-- chart_html:/static/demo/{html_fname} -->'  # Reference for email conversion
    )


def sql_tool(sql: str) -> str:
    """Execute a single validated SELECT query and return JSON rows."""
    _validate_sql(sql)
    sql = _expand_macros(sql)
    return _run_and_serialize(sql)


def multi_sql_tool(queries: List[str]) -> List[str]:
    """Run multiple read-only queries and return list of JSON result strings."""
    results: List[str] = []
    # DEFENSIVE: Ensure queries is a list
    if not queries:
        return []
    if not isinstance(queries, list):
         # If single string passed by mistake
         if isinstance(queries, str):
             queries = [queries]
         else:
             return []

    for q in queries:
        _validate_sql(q)
        q = _expand_macros(q)
        results.append(_run_and_serialize(q))
    return results


def percentage_tool(numerator_sql: str, denominator_sql: str) -> str:
    """Compute percentage = SUM(numerator_result) / SUM(denominator_result) * 100.

    Each SQL should return a single row with a single numeric column.
    Returns a JSON string with keys numerator, denominator, percent.
    """
    import json

    # Run both queries
    num_json = sql_tool(numerator_sql)
    den_json = sql_tool(denominator_sql)

    num_val = float(pd.read_json(num_json).iloc[0, 0]) if num_json != "[]" else 0.0
    den_val = float(pd.read_json(den_json).iloc[0, 0]) if den_json != "[]" else 0.0
    percent = (num_val / den_val * 100.0) if den_val else None

    return json.dumps({
        "numerator": num_val,
        "denominator": den_val,
        "percent": percent,
    })

# ---------------------------------------------------------------------------
# Dispute management mutation + email helper
# ---------------------------------------------------------------------------
import smtplib, ssl, mimetypes, json
from email.message import EmailMessage
import pymssql
from database import DB_SERVER, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
FROM_ADDR = os.getenv("FROM_ADDR", SMTP_USER)

SENDER_DISPLAY_NAME = "Cubie-TCube360"
# Just use the display name for the From header if the SMTP server allows it, 
# or use the standard format but we'll try to rely on the display name being prominent.
# To "hide" it implies we want the recipient to see just the name.
SENDER_EMAIL = f"{SENDER_DISPLAY_NAME} <{FROM_ADDR}>" 
# Note: We can't truly "hide" the address from the protocol, but this format prioritizes the name display.

# AI-generated email disclaimer
AI_EMAIL_DISCLAIMER = """

---
⚠️ This e-mail is auto-generated using AI by Cubie Assistant.
Please verify any data or actions before making business decisions.
"""


def _execute_non_query(sql: str) -> None:
    """Execute an INSERT/UPDATE/DELETE statement."""
    conn = pymssql.connect(
        server=DB_SERVER,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        port=DB_PORT,
    )
    cursor = conn.cursor()
    cursor.execute(sql)
    conn.commit()
    conn.close()


def update_dispute_status(dispute_id: int, new_status: str | None, changed_by: str) -> str:
    """Set DisputeStatus to 'Open' or 'Closed'. If *new_status* is None, toggle it."""

    if not new_status:
        # fetch current status
        df = run_query(f"SELECT DisputeStatus FROM DisputeManagement WHERE DisputeID={int(dispute_id)}")
        if df.empty:
            raise ValueError("DisputeID not found")
        curr = str(df.iloc[0, 0]).strip().capitalize()
        status_norm = "Closed" if curr == "Open" else "Open"
    else:
        status_norm = new_status.strip().capitalize()

    if status_norm not in {"Open", "Closed"}:
        raise ValueError("new_status must be 'Open' or 'Closed'")

    safe_user = changed_by.replace("'", "''")
    query = (
        f"UPDATE DisputeManagement SET DisputeStatus='{status_norm}', "
        f"ChangedOn=GETDATE(), ChangedBy='{safe_user}' "
        f"WHERE DisputeID={int(dispute_id)};"
    )
    _execute_non_query(query)
    return status_norm.lower()


def add_audit_comment(dispute_id: int, comments: str, processor: str | None = None, assigned_to: str | None = None) -> str:
    """Insert a comment row into AuditTrail."""
    proc_val = (processor or "Cubie").replace("'", "''")
    comm_val = comments.replace("'", "''")
    assign_val = (assigned_to or "").replace("'", "''")
    query = (
        f"INSERT INTO AuditTrail (DisputeID, CreationDate, Processor, Comments, AssignedTo) "
        f"VALUES ({int(dispute_id)}, GETDATE(), '{proc_val}', '{comm_val}', '{assign_val}');"
    )
    _execute_non_query(query)
    return "inserted"


def _emails_for_usernames(usernames: list[str]) -> list[str]:
    """Resolve usernames *or* raw email addresses to email addresses."""
    # FIX: Handle case where LLM passes a string instead of a list
    # If usernames is a string, wrap it in a list
    if isinstance(usernames, str):
        logger.warning(f"_emails_for_usernames received string instead of list: '{usernames}'. Auto-wrapping.")
        usernames = [usernames]
    
    if not usernames:
        return []

    direct_emails = [u for u in usernames if "@" in u]
    lookup_users  = [u for u in usernames if "@" not in u]

    results: list[str] = direct_emails.copy()

    if lookup_users:
        quoted = ",".join(f"'{u.lower()}'" for u in lookup_users)
        sql = (
            "SELECT EmailId FROM UserProfile "
            f"WHERE LOWER(UserName) IN ({quoted})"
        )
        df = run_query(sql)
        if not df.empty:
            results.extend(df["EmailId"].dropna().tolist())

    # de-dup and return
    final_list = list({e.lower(): e for e in results}.values())
    logger.info(f"Resolved emails for {usernames}: {final_list}")
    return final_list


def clean_email_content(content: str) -> str:
    """Clean up email content by removing markdown formatting and unnecessary characters."""
    import re
    
    # Remove markdown bold formatting (**text** -> text)
    content = re.sub(r'\*\*(.*?)\*\*', r'\1', content)
    
    # Remove markdown italic formatting (*text* -> text)
    content = re.sub(r'\*(.*?)\*', r'\1', content)
    
    # Remove markdown headers (# Header -> Header)
    content = re.sub(r'^#+\s*', '', content, flags=re.MULTILINE)
    
    # Remove markdown list formatting (- item -> item)
    content = re.sub(r'^-\s*', '', content, flags=re.MULTILINE)
    
    # Remove markdown code blocks (```code``` -> code)
    content = re.sub(r'```.*?\n(.*?)\n```', r'\1', content, flags=re.DOTALL)
    
    # Remove markdown inline code (`code` -> code)
    content = re.sub(r'`(.*?)`', r'\1', content)
    
    # Clean up extra whitespace
    content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
    content = content.strip()
    
    return content


def _markdown_to_html(text: str) -> str:
    """Convert basic markdown to HTML for emails."""
    import re
    html = text
    # Bold **text**
    html = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', html)
    # Italic *text*
    html = re.sub(r'\*(.*?)\*', r'<i>\1</i>', html)
    
    # Process tables (basic support for | col | col | syntax)
    # This is a simple parser for standard markdown tables
    # It assumes tables are separated by newlines and have a header row, separator row, and data rows
    
    # regex for table row: starts and ends with |, contains |
    import re
    table_block_pattern = re.compile(r'((\|[^\n]+\|\n)+)', re.MULTILINE)
    
    def table_replacer(match):
        block = match.group(1).strip()
        rows = block.split('\n')
        if len(rows) < 2: return block # Not a valid table
        
        html_table = ['<table style="width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 14px;">']
        
        # Header
        header_row = rows[0].strip('|').split('|')
        html_table.append('<thead><tr>')
        for cell in header_row:
            html_table.append(f'<th style="background-color: #004aad; color: white; padding: 12px; text-align: left; border: 1px solid #ddd;">{cell.strip()}</th>')
        html_table.append('</tr></thead>')
        
        # Body (skip separator row 1)
        html_table.append('<tbody>')
        for row in rows[2:]:
            cells = row.strip('|').split('|')
            html_table.append('<tr>')
            for cell in cells:
                html_table.append(f'<td style="padding: 12px; border: 1px solid #ddd;">{cell.strip()}</td>')
            html_table.append('</tr>')
        html_table.append('</tbody></table>')
        return "".join(html_table)

    # Apply table replacement BEFORE processing lines
    # Note: parsing context-free markdown tables accurately is hard with regex, 
    # but this handles the standard output from the LLM well enough.
    # A robust approach would use a library like `markdown` or `commonmark` if available/allowed.
    # Since we saw `markdown` package is NOT installed (pip list showed minimal), we stick to manual simple parsing or use `re`.
    
    # Actually, a simpler line-by-line approach might be safer if regex is tricky.
    # Let's try to detect the table block in the manual line processor if possible, 
    # or just pre-process the text using the regex above which is decent for contiguous blocks.
    
    html = table_block_pattern.sub(table_replacer, html)

    # Process lines for lists and headers
    lines = []
    in_list = False
    
    # We need to rely on the pre-processed HTML for tables, so we should split by newline carefully
    # or just let the previous regex handle it and skip those lines?
    # The previous regex replaced the markdown table with <table>...</table> on a single line (mostly).
    # So the line processor below will see <table>...</table> as a line.
    
    for line in html.split('\n'):
        line = line.strip()
        if not line:
            continue
            
        if line.startswith('<table'):
            lines.append(line)
            continue
            
        if line.startswith('- '):
            if not in_list:
                lines.append('<ul>')
                in_list = True
            lines.append(f'<li>{line[2:]}</li>')
        else:
            if in_list:
                lines.append('</ul>')
                in_list = False
            
            if line.startswith('### '):
                lines.append(f'<h3 style="color: #004aad;">{line[4:]}</h3>')
            elif line.startswith('## '):
                lines.append(f'<h2 style="color: #004aad;">{line[3:]}</h2>')
            elif line.startswith('# '):
                lines.append(f'<h1 style="color: #004aad;">{line[2:]}</h1>')
            else:
                lines.append(f'<p style="margin-bottom: 10px;">{line}</p>')
                
    if in_list:
        lines.append('</ul>')
        
    return "\n".join(lines)

def _get_email_template(content_html: str, subject: str) -> str:
    """Wrap content in a professional corporate HTML template."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background-color: #f4f4f4; }}
            .container {{ max-width: 600px; margin: 20px auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .header {{ background: linear-gradient(135deg, #0061f2 0%, #00c6f9 100%); padding: 30px 40px; text-align: center; color: white; }}
            .header h1 {{ margin: 0; font-size: 24px; font-weight: 600; letter-spacing: 1px; }}
            .content {{ padding: 40px; }}
            .footer {{ background-color: #f9f9f9; padding: 20px 40px; text-align: center; font-size: 12px; color: #888; border-top: 1px solid #eee; }}
            
            /* Typography */
            h1, h2, h3 {{ color: #004aad; margin-top: 25px; }}
            h2 {{ font-size: 20px; border-bottom: 2px solid #eee; padding-bottom: 10px; }}
            p {{ margin-bottom: 15px; }}
            ul {{ padding-left: 20px; margin-bottom: 20px; }}
            li {{ margin-bottom: 8px; }}
            
            /* Tables */
            table {{ width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 14px; }}
            th {{ background-color: #004aad; color: white; padding: 12px; text-align: left; }}
            td {{ padding: 12px; border-bottom: 1px solid #ddd; }}
            tr:nth-child(even) {{ background-color: #f9f9f9; }}
            
            /* AI Disclaimer */
            .disclaimer {{ margin-top: 20px; padding: 15px; background-color: #eef2f5; border-left: 4px solid #004aad; font-size: 13px; color: #555; text-align: left; }}
            .signature {{ margin-top: 30px; font-weight: bold; color: #004aad; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>TCube 360 AI Assistant</h1>
            </div>
            <div class="content">
                {content_html}
            </div>
            <div class="footer">
                &copy; 2026 TCube 360. All rights reserved.<br>
                Automated message generated by Cubie.
            </div>
        </div>
    </body>
    </html>
    """


def draft_email_tool(to_usernames: list[str], subject: str, body_markdown: str, attachments: list[str] | None = None) -> str:
    """Send an email directly to the specified users (no approval flow).
    
    This function now sends emails immediately instead of creating a draft.
    All emails include an AI-generated disclaimer.
    """
    # Debug logging for input validation
    logger.debug(f"draft_email_tool called with to_usernames type={type(to_usernames)}, value={to_usernames}")
    
    # DEFENSIVE: Ensure to_usernames is a list
    if to_usernames is None:
        to_usernames = []
    elif isinstance(to_usernames, str):
        to_usernames = [to_usernames]
        
    recipients = _emails_for_usernames(to_usernames)
    if not recipients:
        logger.warning(f"No valid recipients found for input: {to_usernames}")
        return "Error: No valid recipients found. Please provide a valid email address."

    # Clean up the email content for plain text
    clean_body = clean_email_content(body_markdown)
    
    # Generate HTML content
    html_body = _markdown_to_html(body_markdown)
    
    # Add AI disclaimer using the new professional style
    disclaimer_html = '''
    <div class="disclaimer">
        <strong>⚠️ AI-Generated Content</strong><br>
        This email was generated by Cubie Assistant. Please verify all data before making business decisions.
    </div>
    '''
    
    if "auto-generated using AI" not in clean_body:
        clean_body += "\n\n---\n⚠️ This e-mail is auto-generated using AI by Cubie Assistant.\nPlease verify any data or actions before making business decisions."
        html_body += disclaimer_html
    
    # Fallback: If we have chart attachments, try to embed them visually in the HTML body too
    # REMOVED: broken iframe embedding logic that caused empty boxes.
    # The email will rely on the attachment and the summarized data table in the body.
    if attachments:
        html_body += '<p><i>(See attached zip file for interactive charts)</i></p>'
    
    # Add signature if not present
    # Build the email message
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = SENDER_EMAIL  # Shows as "Cubie-TCube360" in recipient's inbox
        msg["To"] = ", ".join(recipients)
        
        # Set plain text as fall back
        msg.set_content(clean_body)
        
        # Apply the professional template
        full_html = _get_email_template(html_body, subject)
        
        # Set HTML as the preferred version
        msg.add_alternative(full_html, subtype='html')

        if "TEST ATTACH" in subject.upper():
            # DEBUG: Force attach a known file to verify sending works
            test_file = "public/demo/test.txt"
            with open(test_file, "w") as f: f.write("This is a test attachment.")
            if not attachments: attachments = []
            attachments.append(test_file)
            logger.info("DEBUG: Forcing attachment of test.txt")

        # Infer attachment paths from body_markdown if none supplied
        if (not attachments or len(attachments) == 0) and "/static/demo/" in body_markdown:
            import re
            # Look for both .png and .html files
            paths = re.findall(r"/static/demo/\S+?\.(?:png|html)", body_markdown)
            attachments = list(set(paths))
            logger.debug(f"Auto-inferred attachments: {attachments}")

        # Handle attachments - attach files directly
        logger.debug(f"Processing attachments: {attachments}")
        attached_count = 0
        for path in attachments or []:
            print(f"DEBUG Email: Processing attachment path: {path}")
            fs_path = path
            if path.startswith("/static/"):
                fs_path = os.path.join("public", path[len("/static/"):])
            
            print(f"DEBUG Email: Final filesystem path: {fs_path}")
            
            # Attach the file directly
            try:
                if os.path.exists(fs_path):
                    print(f"DEBUG Email: File EXISTS at {fs_path}")
                    mime, _ = mimetypes.guess_type(fs_path)
                    if mime is None:
                        mime = "application/octet-stream"
                    
                    # Special handling for HTML files - ZIP them to avoid spam filters
                    if fs_path.endswith(".html"):
                        try:
                            zip_path = fs_path + ".zip"
                            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                                zf.write(fs_path, os.path.basename(fs_path))
                            
                            with open(zip_path, "rb") as fp:
                                msg.add_attachment(fp.read(), maintype="application", subtype="zip", filename=os.path.basename(path) + ".zip")
                            
                            # Clean up zip
                            try:
                                os.remove(zip_path)
                            except:
                                pass
                            
                            attached_count += 1
                            logger.info(f"Successfully attached (zipped): {os.path.basename(path)}")
                        except Exception as zip_err:
                            logger.error(f"Failed to zip/attach {fs_path}: {zip_err}")
                            # Fallback to attaching raw HTML if zip fails
                            with open(fs_path, "r", encoding="utf-8") as fp:
                                file_content = fp.read()
                                msg.add_attachment(file_content, subtype="html", filename=os.path.basename(path))
                    else:
                        main_sub = mime.split("/")
                        maintype, subtype = main_sub[0], main_sub[1]
                        with open(fs_path, "rb") as fp:
                            msg.add_attachment(fp.read(), maintype=maintype, subtype=subtype, filename=os.path.basename(path))
                    
                    attached_count += 1
                    logger.info(f"Successfully attached: {os.path.basename(path)}")
                    print(f"DEBUG Email: ATTACHED {os.path.basename(path)}")
                else:
                    print(f"DEBUG Email: File NOT FOUND at {fs_path}")
                    logger.warning(f"File not found, skipping: {fs_path}")
            except Exception as attach_err:
                logger.error(f"Failed to attach {fs_path}: {attach_err}")
                print(f"DEBUG Email: Failed to attach {fs_path}: {attach_err}")
                # Continue preventing attachment error from stopping email
        
        logger.debug(f"Total attachments added: {attached_count}")

        # Send the email immediately
        context = ssl.create_default_context()
        try:
            logger.info(f"Attempting to connect to SMTP server {SMTP_HOST}:{SMTP_PORT}")
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.set_debuglevel(1) # Enable debug output for SMTP
                server.starttls(context=context)
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)
                logger.info(f"Email sent successfully to {recipients}")
            return f"[OK] Email sent successfully to {', '.join(recipients)}!"
        except Exception as exc:
            logger.error(f"SMTP error: {exc}")
            return f"[ERROR] Error sending email: {exc}"
    except Exception as general_err:
        logger.error(f"CRITICAL: draft_email_tool failed: {general_err}")
        return f"[ERROR] Internal error preparing email: {general_err}"


def mail_tool(to_usernames: list[str], subject: str, body_markdown: str, attachments: list[str] | None = None) -> str:
    """Send an email via SMTP to given usernames (resolved to EmailId)."""
    # Debug logging for input validation
    logger.debug(f"mail_tool called with to_usernames type={type(to_usernames)}, value={to_usernames}")
    
    recipients = _emails_for_usernames(to_usernames)
    if not recipients:
        logger.warning(f"No valid recipients found for input: {to_usernames}")
        return "Error: No valid recipients found. Please provide a valid email address."

    logger.info(f"mail_tool called with recipients: {recipients}")
    logger.debug(f"SMTP_HOST: {SMTP_HOST}, SMTP_USER: {SMTP_USER}")
    
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL  # Shows as "Cubie-TCube360" in recipient's inbox
    msg["To"] = ", ".join(recipients)
    
    # Clean up the email content before sending
    clean_body = clean_email_content(body_markdown)
    
    # Generate HTML content
    html_body = _markdown_to_html(body_markdown)
    
    # Add AI disclaimer instead of just Cubie signature
    disclaimer_text = "\n\n---\n⚠️ This e-mail is auto-generated using AI by Cubie Assistant.\nPlease verify any data or actions before making business decisions."
    disclaimer_html = '<hr><p style="font-size: 0.8em; color: #666;">⚠️ This e-mail is auto-generated using AI by Cubie Assistant.<br>Please verify any data or actions before making business decisions.</p>'

    if "auto-generated using AI" not in clean_body:
        clean_body += disclaimer_text
        html_body += disclaimer_html
    elif not clean_body.rstrip().endswith("Cubie"):
        clean_body += "\n\n— Cubie"
        html_body += '<p>— Cubie</p>'
    
    msg.set_content(clean_body)
    msg.add_alternative(f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        {html_body}
      </body>
    </html>
    """, subtype='html')

    # Infer attachment paths from body_markdown if none supplied
    if (not attachments or len(attachments) == 0) and "/static/demo/" in body_markdown:
        import re
        # Look for both .png and .html files
        paths = re.findall(r"/static/demo/\S+?\.(?:png|html)", body_markdown)
        # Deduplicate paths
        attachments = list(set(paths))
    
    # Deduplicate explicit attachments if any
    if attachments:
        attachments = list(set(attachments))

    for path in attachments or []:
        # Map /static/xyz to filesystem path public/xyz for reading
        print(f"DEBUG MailTool: Processing attachment path: {path}")
        fs_path = path
        if path.startswith("/static/"):
            fs_path = os.path.join("public", path[len("/static/"):])
        
        print(f"DEBUG MailTool: fs_path: {fs_path}")
        if os.path.exists(fs_path):
            print(f"DEBUG MailTool: File exists!")
            mime, _ = mimetypes.guess_type(fs_path)
            if mime is None:
                mime = "application/octet-stream"

            try:
                # Special handling for HTML files - ZIP them
                if fs_path.endswith(".html"):
                    try:
                        zip_path = fs_path + ".zip"
                        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                            zf.write(fs_path, os.path.basename(fs_path))
                        
                        with open(zip_path, "rb") as fp:
                            msg.add_attachment(fp.read(), maintype="application", subtype="zip", filename=os.path.basename(path) + ".zip")
                        
                        try:
                            os.remove(zip_path)
                        except:
                            pass
                            
                        print(f"DEBUG MailTool: Attached (zipped) {path}")
                    except Exception as z_err:
                        print(f"DEBUG Zip Error: {z_err}")
                        # Fallback
                        with open(fs_path, "r", encoding="utf-8") as fp:
                            file_content = fp.read()
                            msg.add_attachment(file_content, subtype="html", filename=os.path.basename(path))
                else:
                    main_sub = mime.split("/")
                    maintype, subtype = main_sub[0], main_sub[1]
                    with open(fs_path, "rb") as fp:
                        msg.add_attachment(fp.read(), maintype=maintype, subtype=subtype, filename=os.path.basename(path))
                
                print(f"DEBUG MailTool: Attached {path}")
            except Exception as e:
                print(f"DEBUG MailTool: Error attaching: {e}")
                continue
        else:
            print(f"DEBUG MailTool: File DOES NOT EXIST")
    context = ssl.create_default_context()
    try:
        logger.info(f"Attempting to connect to SMTP server {SMTP_HOST}:{SMTP_PORT}")
        print(f"DEBUG: SMTP_USER: {SMTP_USER}, FROM_ADDR: {FROM_ADDR}")
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            print(f"DEBUG: Connected to SMTP server")
            server.starttls(context=context)
            print(f"DEBUG: Started TLS")
            server.login(SMTP_USER, SMTP_PASS)
            print(f"DEBUG: Logged in successfully")
            server.send_message(msg)
            print(f"DEBUG: Email sent successfully")
        return f"[OK] Email sent successfully to {', '.join(recipients)}!"
    except Exception as exc:
        print(f"DEBUG: SMTP error: {exc}")
        return f"[ERROR] Error sending email: {exc}"


def approve_email_tool() -> str:
    """Send the approved email draft."""
    global EMAIL_DRAFT
    print(f"DEBUG: approve_email_tool called, EMAIL_DRAFT: {EMAIL_DRAFT}")
    if not EMAIL_DRAFT:
        print("DEBUG: No EMAIL_DRAFT found")
        return "no_draft"
    
    print(f"DEBUG: Sending email with draft: {EMAIL_DRAFT}")
    # Send the email using the draft
    result = mail_tool(
        EMAIL_DRAFT["recipients"],
        EMAIL_DRAFT["subject"], 
        EMAIL_DRAFT["body"],
        EMAIL_DRAFT["attachments"]
    )
    
    # Clear the draft
    EMAIL_DRAFT = None
    print(f"DEBUG: Email sent, result: {result}")
    
    return result


# Global variable to store email draft
EMAIL_DRAFT = None


# ---------------------------------------------------------------------------
# Navigation Tool - Redirect users to TCube application screens
# ---------------------------------------------------------------------------

def navigate_tool(destination: str) -> str:
    """
    Navigate user to a specific TCube application screen (RateCube, AuditCube).
    
    Args:
        destination: The screen/page user wants to navigate to
                    (e.g., 'Rate Calculator', 'Rate Dashboard', 'Rate Maintenance')
        
    Returns:
        JSON with redirect URL and action, or error message with available options
    """
    import json
    
    # Load navigation routes from config file
    config_path = "navigation_routes.json"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except FileNotFoundError:
        return json.dumps({
            "action": "error",
            "message": "Navigation configuration not found. Please contact administrator."
        })
    except json.JSONDecodeError:
        return json.dumps({
            "action": "error", 
            "message": "Navigation configuration is invalid. Please contact administrator."
        })
    
    # Normalize destination for matching
    dest_lower = destination.lower().strip()
    
    # Try to find a matching route
    for route in config.get("routes", []):
        # Check if destination matches any keyword
        keywords = route.get("keywords", [])
        route_name = route.get("name", "").lower()
        route_id = route.get("id", "").lower()
        
        # Match against keywords, name, or id
        if any(kw.lower() in dest_lower or dest_lower in kw.lower() for kw in keywords):
            logging.info(f"Navigation match found: {route['name']} -> {route['url']}")
            return json.dumps({
                "action": "navigate",
                "url": route["url"],
                "name": route["name"],
                "description": route.get("description", ""),
                "message": f"Opening {route['name']}..."
            })
        
        # Also match on route name or id directly
        if dest_lower in route_name or route_name in dest_lower:
            logging.info(f"Navigation match found: {route['name']} -> {route['url']}")
            return json.dumps({
                "action": "navigate",
                "url": route["url"],
                "name": route["name"],
                "description": route.get("description", ""),
                "message": f"Opening {route['name']}..."
            })
        
        if dest_lower in route_id or route_id in dest_lower:
            logging.info(f"Navigation match found: {route['name']} -> {route['url']}")
            return json.dumps({
                "action": "navigate",
                "url": route["url"],
                "name": route["name"],
                "description": route.get("description", ""),
                "message": f"Opening {route['name']}..."
            })
    
    # No match found - return available options
    available = [r["name"] for r in config.get("routes", [])]
    logging.info(f"No navigation match for '{destination}'. Available: {available}")
    return json.dumps({
        "action": "not_found",
        "message": f"I couldn't find a page matching '{destination}'. Available screens: {', '.join(available)}",
        "available_routes": available
    })