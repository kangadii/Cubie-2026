import os
import json
import numpy as np
from google import genai
from google.genai import types
from google.api_core.exceptions import ResourceExhausted
import time
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Request
from dotenv import load_dotenv
from numpy.linalg import norm
from typing import List, Dict, Any
from uuid import uuid4

import json as json_lib  # for parsing function arguments safely
from datetime import datetime

# noqa: F401 – explicit re-export (chart tools)
import analytics_tools as _at

from analytics_tools import sql_tool, multi_sql_tool, percentage_tool, chart_tool, update_dispute_status, add_audit_comment, mail_tool, draft_email_tool, approve_email_tool, navigate_tool

from fastapi import HTTPException
from starlette.middleware.sessions import SessionMiddleware
import secrets

# Import authentication module
# Import authentication module
from auth import authenticate_user

# === Logging Configuration ===
import logging
from logging.handlers import RotatingFileHandler

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        RotatingFileHandler("logs/cubie.log", maxBytes=10*1024*1024, backupCount=5),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("CubieApp")

app = FastAPI()

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=200, 
        content={"reply": "⚠️ **System Error:** Something went wrong. I have logged the error for the developers to fix."}
    )


# === Simple session storage for email drafts ===
# In a real app, you'd use Redis, database, or proper session management
EMAIL_DRAFTS: Dict[str, Dict[str, Any]] = {}

# === Load environment variables ===
# === Load environment variables ===
load_dotenv(override=True)
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key or not api_key.strip():
    raise ValueError("GOOGLE_API_KEY not set or empty in your .env file")
api_key = api_key.strip()
genai_client = genai.Client(api_key=api_key)

# === Embedding and chat model ===
EMBED_MODEL = "models/gemini-embedding-001"
CHAT_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# === Load saved embeddings and documents ===
data = np.load("help_embeddings.npz", allow_pickle=True)
embeddings = data["embeddings"]
documents = data["documents"]

# Whitelist of valid help pages to prevent fabricated links
HELP_DOMAIN = "http://dev.tcube360.com/help/"
HELP_URL_WHITELIST: list[str] = []
try:
    for _fname in os.listdir("HelpContent"):
        if _fname.endswith(".html"):
            HELP_URL_WHITELIST.append(HELP_DOMAIN + _fname)
except FileNotFoundError:
    HELP_URL_WHITELIST = []

# === Load DB schema for analytics mode ===
try:
    with open("schema_prompt.txt", "r", encoding="utf-8") as _f:
        DB_SCHEMA = _f.read()
except FileNotFoundError:
    DB_SCHEMA = ""

# === Embedding helper ===
def get_embedding(text, model=EMBED_MODEL):
    result = genai_client.models.embed_content(
        model=model,
        contents=text,
        config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT")
    )
    return result.embeddings[0].values

# === Cosine similarity ===
def cosine_similarity(a, b):
    return np.dot(a, b) / (norm(a) * norm(b))

# === Boosting logic (optional) ===
BOOST_TERMS = ['kpi', 'dashboard', 'visualization', 'metrics', 'summary', 'trend', 'table', 'shipment']
CUBE_TERMS = ['rate cube', 'audit cube', 'admin cube', 'track cube']

def boost_score(score, doc, query):
    content = (doc.get('section_title', '') + ' ' + doc.get('content', '')).lower()
    query = query.lower()
    keyword_boost = sum(1 for term in BOOST_TERMS if term in content and term in query) * 0.02
    cube_boost = 0.05 if any(cube in query and cube in (doc.get('cube') or '').lower() for cube in CUBE_TERMS) else 0
    return score + keyword_boost + cube_boost

# === Semantic search for top matching docs ===
def search_documents(query, top_k=3):
    query_embedding = get_embedding(query)
    scored_docs = []
    # First pass: filter out 'under construction' docs
    for doc, emb in zip(documents, embeddings):
        section = doc.get('section_title', '').lower()
        content = doc.get('content', '').lower()
        if "under construction" in section or "under construction" in content:
            continue
        sim = cosine_similarity(query_embedding, emb)
        boosted = boost_score(sim, doc, query)
        scored_docs.append((boosted, doc))
    # If nothing left after filtering, fall back to all docs
    if not scored_docs:
        for doc, emb in zip(documents, embeddings):
            sim = cosine_similarity(query_embedding, emb)
            boosted = boost_score(sim, doc, query)
            scored_docs.append((boosted, doc))
    ranked = sorted(scored_docs, key=lambda x: x[0], reverse=True)
    return ranked[:top_k]

# === Format context for prompt ===
def build_context(docs):
    parts = []
    for doc in docs:
        section = doc["section_title"]
        content = doc.get("content", "")
        url = doc.get("source_url", "")
        parts.append(f"Section: {section}\nURL: {url}\nContent: {content}")
    return "\n\n".join(parts)

# === Intent Classification ===
# Keyword-based intent detection to correctly route queries before LLM processing

ANALYTICS_KEYWORDS = [
    'how many', 'count', 'total', 'sum', 'average', 'avg', 'percentage', '%',
    'shipments', 'shipment', 'disputes', 'dispute', 'carriers', 'carrier',
    'this month', 'last month', 'this year', 'last year', 'year to date', 'ytd',
    'top', 'bottom', 'ranking', 'compare', 'comparison', 'trend', 'trends',
    'data', 'statistics', 'stats', 'metrics', 'kpi', 'kpis',
    'delivery time', 'on time', 'late', 'delayed', 'overdue',
    'invoice', 'invoices', 'cost', 'costs', 'spend', 'spending', 'volume',
    'users', 'user count', 'active users', 'how much', 'what is the',
    'analysis', 'analyze', 'report', 'summary', 'breakdown',
    'which carrier', 'which carriers', 'performance', 'weight', 'packages'
]

VISUALIZATION_KEYWORDS = [
    'chart', 'graph', 'plot', 'visualization', 'visualize', 'visualise',
    'bar chart', 'line chart', 'pie chart', 'pie graph', 'heatmap', 'heat map',
    'scatter', 'scatter plot', 'area chart', 'histogram', 'donut', 'treemap',
    'show me a graph', 'show me a chart', 'create a chart', 'draw a', 'plot a',
    'visual representation', 'graphical', 'diagram'
]

EMAIL_KEYWORDS = [
    'email', 'e-mail', 'send this', 'send me', 'mail this', 'mail me',
    'send to', 'email this', 'forward', 'share via email', 'share this',
    'notify', 'send a report', 'email report', 'send summary'
]

NAVIGATION_KEYWORDS = [
    'go to', 'take me to', 'navigate to', 'open', 'redirect', 'show me the page',
    'rate calculator', 'rate dashboard', 'rate maintenance', 'audit dashboard',
    'go to page', 'open page', 'switch to', 'bring me to', 'check rates',
    'price lookup', 'shipping cost', 'track shipment', 'where is my shipment',
    'file a claim', 'claim status', 'report center', 'admin settings', 'configure app'
]

HELP_KEYWORDS = [
    'how do i', 'how to', 'what is', 'explain', 'help me', 'guide',
    'documentation', 'instructions', 'tutorial', 'steps to', 'process for',
    'can you explain', 'tell me about', 'describe', 'definition',
    'where can i find', 'how does', 'what does'
]

def classify_intent(query: str, explicit_mode: str = "auto", history: List[Dict[str, str]] = None) -> str:
    """
    Classify user query intent using Gemini 2.0 Flash for smart routing.
    Distinguishes between 'What is' (Help) and 'Take me to' (Navigation).
    
    Args:
        query: The user's message
        explicit_mode: Mode explicitly set by frontend ('auto', 'help', 'analytics')
        history: Recent conversation history context
    
    Returns:
        One of: 'analytics', 'visualization', 'email', 'navigation', 'help'
    """
    # 1. Fast path for explicit modes or obvious keywords to save latency
    q_lower = query.lower()
    
    # Email is always analytics/action
    if any(phrase in q_lower for phrase in ['send me', 'email this', 'email me', 'mail me']):
        return 'email'
        
    # If explicitly set, respect it unless it's a clear navigation/action
    if explicit_mode == 'analytics':
        # check for viz keywords
        if any(kw in q_lower for kw in VISUALIZATION_KEYWORDS):
            return 'visualization'
        return 'analytics'
        
    # 2. LLM Classification (Gemini 2.0 Flash)
    try:
        # Construct simplified history for context
        history_text = ""
        if history:
            # Take last 2 turns
            recent = history[-2:] if len(history) > 2 else history
            for msg in recent:
                role = "User" if msg.get("role") == "user" else "Assistant"
                history_text += f"{role}: {msg.get('content', '')}\n"
        
        system_instruction = (
            "You are the Intent Router for the Cubie App. Classify the user's latest query into exactly one category:\n"
            "- NAVIGATION: User EXPLICITLY wants to go to, open, or switch to a specific app screen/page. "
            "(e.g., 'take me to rate calculator', 'open dashboard', 'go to settings'). "
            "keywords: open, go to, launch, show me the page.\n"
            "- HELP: User asks for definitions, explanations, 'how to', or location of features. "
            "(e.g., 'what is rate calculator', 'how do i find settings', 'where is the dashboard?'). "
            "keywords: what is, how to, explain, guide.\n"
            "- ANALYTICS: User asks for data, specific numbers, statistics, reports, or charts. "
            "(e.g., 'show top shipments', 'how many disputes', 'analyze cost').\n"
            "- VISUALIZATION: User explicitly asks for a chart, graph, or visual. (e.g., 'graph trends').\n"
            "- CHAT: Greetings, general talk, or clarifications.\n\n"
            "CRITICAL DISTINCTION:\n"
            "- 'Open Rate Calculator' -> NAVIGATION\n"
            "- 'What is Rate Calculator?' -> HELP\n"
            "- 'Where is the Rate Calculator?' -> HELP (User needs guidance, not a redirect)\n"
            "- 'Take me to Rate Calculator' -> NAVIGATION\n\n"
            "Output ONLY the category name."
        )
        
        prompt = f"History:\n{history_text}\nUser Query: {query}\n\nCategory:"
        
        response = genai_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.0,
                max_output_tokens=10
            )
        )
        
        intent = response.text.strip().upper()
        logger.info(f"LLM Classification: {intent} for query: '{query}'")
        
        if "NAVIGATION" in intent:
            return "navigation"
        elif "HELP" in intent:
            return "help"
        elif "VISUALIZATION" in intent:
            return "visualization"
        elif "ANALYTICS" in intent:
            return "analytics"
        # Fallback for CHAT or others -> Help (which handles chat) or Analytics if data-heavy
        elif "CHAT" in intent:
             return "help" # Help mode handles chitchat well
             
        # If LLM gives something weird, fall back to keyword logic
        
    except Exception as e:
        logger.error(f"LLM Classification failed: {e}. Falling back to keywords.")
    
    # 3. Fallback Keyword Logic (Original Logic)
    
    # Check for help intent patterns first
    help_patterns = ['how to', 'how do i', 'steps to', 'steps for', 'guide', 'tutorial', 'explain', 'what is', 'where is', 'help with']
    if any(p in q_lower for p in help_patterns):
        return 'help'

    # Check for navigation intent
    strong_nav_terms = [
        'rate calculator', 'rate dashboard', 'rate maintenance', 'audit dashboard',
        'shipment tracking', 'dispute management', 'reports', 'admin', 'settings',
        'check rates', 'track package', 'file a claim'
    ]
    # In fallback, be stricter: require action verb + term for navigation
    nav_verbs = ['go', 'open', 'show', 'take', 'navigate', 'launch']
    if any(term in q_lower for term in strong_nav_terms) and any(verb in q_lower for verb in nav_verbs):
        return 'navigation'

    # Analytics fallback
    analytics_score = sum(1 for kw in ANALYTICS_KEYWORDS if kw in q_lower)
    if analytics_score > 0:
        return 'analytics'

    return 'help'

def should_ask_email_context(query: str, last_response: str) -> bool:
    """
    Determine if Cubie should ask for clarification about what to email.
    
    Returns True if the email request is ambiguous.
    """
    q_lower = query.lower()
    
    # Clear email targets
    has_clear_target = any(phrase in q_lower for phrase in [
        'this', 'these results', 'the above', 'the chart', 'the data',
        'the report', 'the summary', 'what we discussed'
    ])
    
    # If there's recent context (last_response is not empty), we have something to send
    if last_response and len(last_response) > 50:
        return False
    
    # Ambiguous if no context and no clear target
    if not has_clear_target and not last_response:
        return True
    
    return False

# === FastAPI Setup ===
# (app already created above)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add session middleware for authentication
# Generate a secure secret key (in production, store in .env)
SESSION_SECRET = os.getenv("SESSION_SECRET_KEY", secrets.token_hex(32))
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    max_age=1800,  # 30 minutes in seconds
    same_site="lax",
    https_only=False  # Set to True in production with HTTPS
)

# === Logging Middleware ===
from starlette.middleware.base import BaseHTTPMiddleware

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        # Log request
        logger.info(f"Incoming request: {request.method} {request.url.path}")
        
        try:
            response = await call_next(request)
            process_time = (time.time() - start_time) * 1000
            
            # Log response
            logger.info(f"Completed request: {request.method} {request.url.path} - Status: {response.status_code} - Time: {process_time:.2f}ms")
            return response
        except Exception as e:
            process_time = (time.time() - start_time) * 1000
            logger.error(f"Request failed: {request.method} {request.url.path} - Error: {e} - Time: {process_time:.2f}ms")
            raise

app.add_middleware(LoggingMiddleware)

# Mount static files
app.mount("/static", StaticFiles(directory="public"), name="static")
app.mount("/public", StaticFiles(directory="public"), name="public")

@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    """
    Root endpoint - shows login page or chat interface based on session.
    
    If user is not logged in: serve login.html
    If user is logged in: serve index.html (chat interface)
    """
    # Check if user has valid session
    if "user_id" not in request.session:
        # Not logged in - show login page
        with open("public/login.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    
    # Logged in - show chat interface
    with open("public/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/health")
async def health_check():
    """Health check endpoint to verify database and email connectivity."""
    try:
        # Test database connection
        from database import run_query
        test_result = run_query("SELECT 1 as test")
        db_status = "connected" if not test_result.empty and "error" not in test_result.columns else "failed"
        
        # Test email configuration
        from analytics_tools import SMTP_HOST, SMTP_USER, SMTP_PASS
        email_status = "configured" if SMTP_HOST and SMTP_USER and SMTP_PASS else "missing_config"
        
        return {
            "status": "healthy" if db_status == "connected" and email_status == "configured" else "unhealthy",
            "database": db_status,
            "email": email_status,
            "test_query_result": test_result.to_dict() if not test_result.empty else None
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.post("/api/login")
async def login(request: Request):
    """
    Login endpoint - authenticate user credentials.
    
    Request body:
        {
            "username": "TCube360",
            "password": "Cubie@2025"
        }
    
    Response:
        Success: {"success": True, "user": {...}}
        Failure: {"success": False, "error": "error message"}
    """
    try:
        body = await request.json()
        username = body.get("username")
        password = body.get("password")
        
        if not username or not password:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Username and password required"}
            )
        
        # Authenticate using auth module
        user = authenticate_user(username, password)
        
        if user:
            # Create session
            request.session["user_id"] = user["OID"]
            request.session["username"] = user["UserName"]
            request.session["email"] = user.get("EmailId", "")
            
            print(f"User logged in: {username} (OID: {user['OID']})")
            
            return JSONResponse({
                "success": True,
                "user": {
                    "username": user["UserName"],
                    "email": user.get("EmailId", "")
                }
            })
        else:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Invalid username or password"}
            )
            
    except Exception as e:
        print(f"Login error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "Server error during login"}
        )

@app.post("/api/logout")
async def logout(request: Request):
    """
    Logout endpoint - clear user session.
    
    Response:
        {"success": True}
    """
    username = request.session.get("username", "Unknown")
    request.session.clear()
    print(f"User logged out: {username}")
    return JSONResponse({"success": True})


# === In-memory conversation context (single user, for dev/testing) ===
conversation_history = [
    {"role": "system", "content": (
        "You are Cubie, a helpful and upbeat customer service assistant for Tcube.\n"
        "Your goal is to provide clear, concise, and friendly answers grounded in the help documentation.\n\n"
        "Instructions:\n"
        "- Always use a polite, friendly, and conversational tone.\n"
        "- If the user asks for humor (e.g., jokes), respond playfully.\n"
        "- When giving instructions, always use bullet points (-) or numbered lists (1., 2., ...) with spacing.\n"
        "- When referencing links:\n"
        "   • Use [descriptive link text](URL) instead of raw URLs.\n"
        "- Do not repeat greetings in each response.\n"
        "- If you don't know the answer, say so politely.\n"
        "- Responses must always be formatted using valid Markdown syntax.\n\n"
        "Help Context:\n{context}"
    )}
]

# Globals to retain last assistant reply and chart paths
LAST_BODY: str = ""
LAST_CHARTS: list[str] = []

@app.post("/api/approve-email")
async def approve_email(request: Request):
    """Direct endpoint for approving email drafts without going through AI."""
    try:
        body = await request.json()
        session_id = body.get("session_id", "default")
        
        print(f"DEBUG: Direct approval request for session_id: {session_id}")
        print(f"DEBUG: EMAIL_DRAFTS keys: {list(EMAIL_DRAFTS.keys())}")
        
        if session_id in EMAIL_DRAFTS:
            draft_data = EMAIL_DRAFTS[session_id]
            print(f"DEBUG: Found draft in session storage: {draft_data}")
            
            # Send the email using the draft
            from analytics_tools import mail_tool
            result = mail_tool(
                draft_data["recipients"],
                draft_data["subject"], 
                draft_data["body"],
                draft_data["attachments"]
            )
            print(f"DEBUG: Email sent, result: {result}")
            
            # Clear the draft from session storage
            del EMAIL_DRAFTS[session_id]
            
            if result == "sent":
                reply = "✅ Email has been sent successfully!"
            else:
                reply = f"❌ Error sending email: {result}"
        else:
            print(f"DEBUG: No draft found in session storage")
            reply = "❌ No email draft found to approve."
        
        return JSONResponse({"reply": reply})
        
    except Exception as e:
        import traceback
        print("Error during /api/approve-email request:")
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/query")
async def handle_query(request: Request):
    # ===== AUTHENTICATION CHECK =====
    # Require user to be logged in
    if False and "user_id" not in request.session:
        return JSONResponse(
            status_code=401,
            content={"error": "Not authenticated. Please log in."}
        )
    
    try:
        global LAST_BODY, LAST_CHARTS
        body = await request.json()
        query = body.get("question")
        mode = body.get("mode", "help")  # "help" or "analytics"
        prefs = body.get("prefs", {})
        conversation_history = body.get("history", [])  # Get conversation history from frontend
        if not query:
            return JSONResponse(status_code=400, content={"error": "Missing 'question' in request."})


        # --- placeholder for future prompt engineering / no hard-coded demos ---
        q_lower = query.lower()
        now = datetime.now()
        # (hard-coded demo removed)

        # --- Greeting shortcut ---
        greeting_keywords = ["hi", "hello", "hey", "good morning", "good afternoon", "good evening"]
        if query.strip().lower() in greeting_keywords:
            reply = "Hello! I'm Cubie, your personal supply chain assistant. How can I assist you today?"
            conversation_history.append({"role": "assistant", "content": reply})
            return JSONResponse({"reply": reply})
        # --- End greeting shortcut ---

        # === INTELLIGENT INTENT DETECTION ===
        # Initialize variables used across modes
        last_chart_snippet = None
        navigation_result = None
        top_docs = []  # Initialize to empty list to prevent UnboundLocalError/NoneTypeError

        # Classify the user's intent to ensure proper routing
        detected_intent = classify_intent(query, mode, conversation_history)
        logger.info(f"Query='{query[:50]}...', explicit_mode='{mode}', detected_intent='{detected_intent}'")
        
        # Override mode if intent detection suggests a different handler
        if detected_intent in ['analytics', 'visualization', 'email', 'navigation'] and mode == 'help':
            logger.info(f"Overriding mode from 'help' to 'analytics' based on detected intent: {detected_intent}")
            mode = 'analytics'  # Analytics mode handles all data-related queries including email
        
        # Check if user is asking to send email without clear context
        if detected_intent == 'email' and should_ask_email_context(query, LAST_BODY):
            reply = ("I'd be happy to send you an email! Could you please specify what information you'd like me to include? "
                    "For example:\n"
                    "- 'Email me the shipment summary from last month'\n"
                    "- 'Send me the top 5 carriers data'\n"
                    "- 'Email the chart we just created'\n\n"
                    "Or if you want me to send the last response, just say 'email me this' or 'send me the above'.")
            return JSONResponse({"reply": reply})

        # Build help context only in help mode
        # Build help context only in help mode
        if mode == "help":
            # RESTRUCTURED PROMPT: Less context, stricter rules at the END.
            # 1. Reduce context window to minimize noise
            # 1. Reduce context window to minimize noise
            try:
                top_docs = search_documents(query, top_k=3) or []
            except Exception as e:
                logger.error(f"Document search failed: {e}")
                top_docs = []
            
            context = build_context([doc for _, doc in top_docs])
            
            # 2. Enhanced System Prompt with 'Sandwich' technique
            system_prompt = (
                "You are Cubie, the TCube360 expert assistant.\n"
                "Your task is to answer the user's question based ONLY on the provided context.\n\n"
                "=== CONTEXT DOCUMENTS (DATA SOURCE) ===\n"
                f"{context}\n\n"
                "=== STRICT OUTPUT RULES (YOU MUST FOLLOW THESE) ===\n"
                "1. **IGNORE VERBOSITY**: The context documents are long. Your answer must be SHORT.\n"
                "2. **DIRECT ANSWER**: Start immediately with the answer. Do not say 'The Rate Calculator is a tool...'. Just say 'To calculate rates, do X, Y, Z.'\n"
                "3. **LENGTH LIMIT**: \n"
                "   - Simple questions: Max 2 sentences.\n"
                "   - Complex questions: Max 1 paragraph + 3 bullet points.\n"
                "4. **NO COMPREHENSIVE GUIDES**: Do not explain features the user didn't ask for.\n"
                "5. **MANDATORY FOLLOW-UP**: End with: 'Want to know more about [specific detail]?'\n"
                "6. **TONE**: Senior Engineer style. Direct. Efficient. No fluff."
            )
        else:
            context = ""
            system_prompt = ""  # Will be set in analytics block

        # --- Build dynamic system prompt based on mode ---
        if mode == "analytics":
            system_prompt = (
                "You are Cubie, a professional Supply Chain Assistant for TCube.\n"
                "Your goal is to help users analyze their supply chain data, visualize trends, and manage disputes.\n\n"
                "CORE BEHAVIOR:\n"
                "- **SWEET SPOT ANSWERS**: specific, direct, and concise. Do not lecture.\n"
                "- **ACT PROFESSIONALLY**: You are a domain expert. Do NOT mention being an 'AI', 'bot', 'backend' or 'code'.\n"
                "- **HIDE MACHINERY**: Never explain *how* you query data. Just do it.\n"
                "- **DIRECT ACTION**: If asked for a chart, generate it. If asked to email, send it.\n"
                "- **CONVERSATIONAL LOOP**: Always end with a relevant follow-up question/suggestion (e.g., 'Should I email this?', 'Want to break this down by carrier?').\n"
                "- **EMAIL CAPABILITIES**: You CAN send emails with attachments. If a user asks to email a chart:\n"
                "  1. ATTACH IT: Pass the chart's file path to the 'attachments' parameter.\n"
                "  2. **ALWAYS include a markdown table summary of the data in the email body.**\n"
                "  3. NEVER say 'I cannot save images'. You can.\n\n"
                f"{DB_SCHEMA}"
            )
            system_prompt += (
                "\n\n=== DATA FORMATTING RULES (CRITICAL) ===\n"
                "1. **DYNAMIC PRESENTATION**:\n"
                "   - **Tables**: Use Markdown tables for lists, comparisons, or multi-row data. (e.g., Top 5 Carriers).\n"
                "     CRITICAL SYNTAX: You MUST include the separator row |---|---| between headers and data rows.\n"
                "     DO NOT indent the table. Start at the beginning of the line.\n"
                "     Example:\n"
                "| Carrier | Shipments |\n"
                "|---|---|\n"
                "| FedEx | 1,234 |\n"
                "| UPS | 890 |\n"
                "   - **Plain Text**: Use natural language for single values or simple facts. (e.g., 'Total spend is $5,000').\n"
                "2. **PROFESSIONAL HEADERS**: Rename DB columns to human-readable headers in tables:\n"
                "   - 'TCCarrierCode' -> 'Carrier'\n"
                "   - 'shipment_count' -> 'Shipments'\n"
                "   - 'TotalCost' -> 'Total Cost ($)'\n"
                "3. **FORMATTING**:\n"
                "   - Format numbers with commas (e.g., 1,234).\n"
                "   - Format currency with $ (e.g., $1,234.50).\n"
                "   - Dates should be YYYY-MM-DD or 'Mon YYYY'.\n"
                "\n=== CORE RULES ===\n"
                "• If the JSON you receive is [{\"notice\":\"no_rows\"}], reply: 'No data available for that query.'\n"
                "• Never display raw SQL in your answer.\n"
                "• Column naming reminders: use RecipientCountry/RecipientCity/RecipientState for destination fields.\n"
                "• In DisputeManagement the carrier column is CarrierCode (not TCCarrierCode).\n"
                "• When the user asks for 'top' items default to TOP 3 unless specified otherwise.\n"
                "• DYNAMIC FLOW: Do NOT dump all information at once. Give the answer, then ask if the user wants more details.\n"
                "\n=== EMAIL HANDLING & CONFIRMATION ===\n"
                "• When user says 'send me email', 'email this', or similar:\n"
                "  1. YOU MUST ASK FOR CONFIRMATION FIRST. Do NOT send immediately.\n"
                "  2. Ask: 'I can send that to you. To be sure, what exactly would you like me to include?'\n"
                "  3. Offer options based on conversation context, e.g.:\n"
                "     - 'Should I send the shipment summary?'\n"
                "     - 'Do you want the bar chart of top carriers attached?'\n"
                "     - 'Or the data summary in the email body?'\n"
                "  4. **CRITICAL EMAIL RULE**: If the user provides an email address (e.g., 'bob@gmail.com' or 'user@company.com'),\n"
                "     YOU MUST USE THAT EMAIL ADDRESS EXACTLY.\n"
                "     DO NOT ignore the user's email.\n"
                "     DO NOT default to 'kangadi@tcube360.com' unless the user SPECIFICALLY asks for it.\n"
                "     This applies to ALL modes including visualization.\n"
                "  5. If user provides an email address but no content detail, still ask to confirm the content.\n"
                "  6. ONLY call `draft_email_tool` after the user explicitly confirms WHAT to send (e.g., 'send the chart' or 'yes, the summary').\n"
                "• When calling `draft_email_tool`:\n"
                "  - Use a professional, specific Subject line (e.g., 'Shipment Summary Report - Oct 2025').\n"
                "  - Ensure `body_markdown` is well-formatted.\n"
                "  - IF user wants a chart, you MUST pass its filepath in `attachments`.\n"
                "\n=== VISUALIZATION ===\n"
                "• Choose the RIGHT chart type based on data:\n"
                "  - 'pie' or 'donut': Distribution/percentage breakdown (e.g., shipments by carrier)\n"
                "  - 'bar': Comparing categories (e.g., top carriers by volume)\n"
                "  - 'line': Trends over time (e.g., monthly shipment count)\n"
                "  - 'area': Cumulative trends over time\n"
                "  - 'scatter': Correlation between two metrics\n"
                "  - 'heatmap': Two-dimensional comparison\n"
                "  - 'histogram': Distribution of a single metric\n"
                "• For pie/donut: x=category column (names), y=numeric column (values)\n"
                "• When chart_tool returns an HTML iframe, include it directly in your response\n"
                "\n=== NAVIGATION ===\n"
                "• When user wants to go to a page (e.g., 'take me to rate calculator'), use navigate_tool\n"
                "• navigate_tool returns a URL that the frontend will use to redirect\n"
                "• Include the navigation message in your response so the user knows what's happening\n"
            )
            functions_spec = [
                {
                    "name": "sql_tool",
                    "description": "Run a read-only SQL query and return JSON rows",
                    "parameters": {
                        "type": "object",
                        "properties": {"sql": {"type": "string"}},
                        "required": ["sql"]
                    },
                },
                {
                    "name": "multi_sql_tool",
                    "description": "Run multiple read-only SQL queries and return list of JSON result strings",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "queries": {
                                "type": "array",
                                "items": {"type": "string"}
                            }
                        },
                        "required": ["queries"]
                    },
                },
                {
                    "name": "percentage_tool",
                    "description": "Compute percentage using two SQL queries (numerator and denominator)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "numerator_sql": {"type": "string"},
                            "denominator_sql": {"type": "string"}
                        },
                        "required": ["numerator_sql", "denominator_sql"]
                    },
                },
                {
                    "name": "chart_tool",
                    "description": "Generate an interactive Plotly chart. Supported chart_type values: 'line', 'bar', 'stacked_bar', 'grouped_bar', 'pie', 'donut', 'area', 'scatter', 'histogram', 'heatmap', 'treemap', 'funnel'. For pie/donut: x=labels (category column), y=values (numeric column). For others: x=x-axis, y=y-axis. Always include a descriptive title.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "sql": {"type": "string", "description": "SQL query to fetch data for the chart"},
                            "chart_type": {"type": "string", "description": "One of: line, bar, stacked_bar, grouped_bar, pie, donut, area, scatter, histogram, heatmap, treemap, funnel"},
                            "x": {"type": "string", "description": "Column for x-axis (or 'names' for pie/donut)"},
                            "y": {"type": "string", "description": "Column for y-axis (or 'values' for pie/donut). For stacked bars, comma-separate column names."},
                            "title": {"type": "string", "description": "Chart title"},
                            "z": {"type": "string", "description": "Optional z-axis column for heatmaps"}
                        },
                        "required": ["sql", "chart_type", "x", "y"]
                    },
                },
                {
                    "name": "update_dispute_status",
                    "description": "Set a dispute's status to Open or Closed in DisputeManagement",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "dispute_id": {"type": "integer"},
                            "new_status": {"type": "string"},
                            "changed_by": {"type": "string"}
                        },
                        "required": ["dispute_id", "changed_by"]
                    },
                },
                {
                    "name": "add_audit_comment",
                    "description": "Insert a comment row into AuditTrail for a dispute",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "dispute_id": {"type": "integer"},
                            "comments": {"type": "string"},
                            "processor": {"type": "string"},
                            "assigned_to": {"type": "string"}
                        },
                        "required": ["dispute_id", "comments"]
                    },
                },
                {
                    "name": "draft_email_tool",
                    "description": "Send an email immediately to TCube users. No approval needed - email is sent right away. All emails include an AI-generated disclaimer.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "to_usernames": {"type": "array", "items": {"type": "string"}},
                            "subject": {"type": "string"},
                            "body_markdown": {"type": "string"},
                            "attachments": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["to_usernames", "subject", "body_markdown"]
                    },
                },
                {
                    "name": "navigate_tool",
                    "description": "Navigate user to a specific screen/page in TCube application (RateCube, AuditCube). Use when user wants to go to, open, or navigate to a specific menu, tab, dashboard, or screen. Examples: 'take me to rate calculator', 'open rate dashboard', 'go to rate maintenance'.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "destination": {
                                "type": "string",
                                "description": "The screen or page the user wants to navigate to (e.g., 'Rate Calculator', 'Rate Dashboard', 'Rate Maintenance')"
                            }
                        },
                        "required": ["destination"]
                    },
                },
            ]
        else:
            # default help-mode prompt (original)
            system_prompt = (
                "You are Cubie, a helpful and upbeat customer service assistant for Tcube.\\n"
                "Your goal is to provide detailed, relevant answers using the help documentation provided below.\\n\\n"
                "Instructions:\\n"
                "- UNDERSTAND what the user wants: analyze their question to identify the specific task, feature, or issue they're asking about.\\n"
                "- CURATE your response: select and present the most relevant help content that directly addresses their need.\\n"
                "- Include step-by-step instructions, screenshots references, menu paths, and specific details from the help docs when relevant.\\n"
                "- Do NOT just summarize - provide actionable, detailed guidance from the help content.\\n"
                "- Always use a polite, friendly, and conversational tone.\\n"
                "- If the user asks for humor (e.g., jokes), respond playfully.\\n"
                "- When giving instructions, always use bullet points (-) or numbered lists (1., 2., ...) with spacing.\\n"
                "- When referencing links:\\n"
                "   • Use [descriptive link text](URL) instead of raw URLs.\\n"
                "- Do not repeat greetings in each response.\\n"
                "- If you don't know the answer, say so politely.\\n"
                "- Responses must always be formatted using valid Markdown syntax.\\n\\n"
                "Help Context:"
            )
            functions_spec = None

        # Add user preferences to the system prompt
        if prefs.get("name"):
            system_prompt += f"\n\nThe user's preferred name is: {prefs['name']}. Greet them by this name in your first message only."
        if prefs.get("length"):
            system_prompt += f"\n\nRespond with {prefs['length']} length answers."
        if prefs.get("traits"):
            traits = prefs['traits']
            if 'cheerful' in traits:
                system_prompt += "\n\nBe cheerful, use exclamation points, and maintain an optimistic tone."
            if 'playful' in traits:
                system_prompt += "\n\nBe playful: use emojis and add a joke or light humor when appropriate."
            if 'neutral' in traits:
                system_prompt += "\n\nMaintain a neutral, balanced tone."
            if 'professional' in traits:
                system_prompt += "\n\nBe professional and businesslike."

        # Use conversation history from frontend, but ensure system prompt is updated
        conversation = [
            {"role": "system", "content": system_prompt}
        ]
        # Add previous conversation history from frontend
        conversation.extend(conversation_history)
        # Add current user message
        user_message = f"{query}\n\nHelp Context:\n{context}"
        conversation.append({"role": "user", "content": user_message})

        # Gemini uses different message format
        messages = conversation

        if mode == "analytics":
            # Check for email approval/rejection in analytics mode
            # Use raw 'query' instead of 'user_message' to avoid issues with appended Help Context
            query_lower = query.lower().strip()
            query_clean = "".join(c for c in query_lower if c.isalnum() or c.isspace())
            
            approval_tokens = {"approve", "approved", "yes", "send", "proceed", "sure", "ok", "okay", "confirm", "right", "go", "do", "please"}
            tokens = set(query_clean.split())
            
            # Fuzzy match for approval (e.g., "yes proceed", "go ahead", "send it")
            is_approved = (not tokens.isdisjoint(approval_tokens)) or ("go ahead" in query_clean) or ("send it" in query_clean)

            if is_approved:
                # User approved the email draft
                logger.info(f"User approved email in analytics mode, checking for draft...")
                session_id = "default"  # In a real app, you'd get this from the request
                logger.debug(f"Checking session storage for session_id: {session_id}")
                
                if session_id in EMAIL_DRAFTS:
                    draft_data = EMAIL_DRAFTS[session_id]
                    logger.info(f"Found draft in session storage: {draft_data.get('subject')}")
                    
                    # Send the email using the draft
                    from analytics_tools import mail_tool
                    result = mail_tool(
                        draft_data["recipients"],
                        draft_data["subject"], 
                        draft_data["body"],
                        draft_data["attachments"]
                    )
                    logger.info(f"Email sent, result: {result}")
                    
                    # Clear the draft from session storage
                    del EMAIL_DRAFTS[session_id]
                    
                    if "[OK]" in result or "successfully" in result.lower():
                        reply = "✅ Email has been sent successfully!"
                    else:
                        reply = f"❌ Error sending email: {result}"
                else:
                    logger.debug(f"No draft in session, passing '{user_message}' to LLM for potential tool call")
                    # Fall through to LLM (do not return)
            elif query_lower in ["reject", "rejected", "no", "cancel", "don't send"] or "don't" in query_lower:
                # User rejected the email draft - only intercept if there WAS a draft
                session_id = "default"
                if session_id in EMAIL_DRAFTS:
                    del EMAIL_DRAFTS[session_id]
                    logger.info(f"Cleared draft from session storage")
                    reply = "❌ Email draft has been cancelled."
                    return JSONResponse({"reply": reply})
                # Otherwise fall through to LLM
            
            last_chart_snippet: str | None = None  # store latest chart HTML/Markdown from chart_tool
            navigation_result: str | None = None  # store navigate_tool result for URL extraction
            
            # --- Build Gemini function declarations ---
            gemini_tools = None
            if functions_spec:
                func_declarations = []
                for spec in functions_spec:
                    # Convert OpenAI function spec to Gemini format
                    params = spec.get("parameters", {})
                    func_decl = types.FunctionDeclaration(
                        name=spec["name"],
                        description=spec.get("description", ""),
                        parameters=params
                    )
                    func_declarations.append(func_decl)
                gemini_tools = [types.Tool(function_declarations=func_declarations)]
            
            # Create Gemini model with system instruction
            # Fallback models list: 
            # 1. Primary (from env: gemini-2.5-flash) 
            # 2. Backup (gemini-2.0-flash) 
            # 3. Alias fallback (gemini-flash-latest)
            fallback_models = [CHAT_MODEL, "gemini-2.0-flash", "models/gemini-flash-latest"]
            
            # Helper to create model config
            def get_model_config():
                return types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    tools=gemini_tools,
                    temperature=0.3
                )
            
            # Build model config
            model_config = get_model_config()
            current_model_name = fallback_models[0]
            
            # Convert messages to Gemini format (skip system message, already in system_instruction)
            gemini_history = []
            for msg in messages:
                if msg["role"] == "system":
                    continue  # System instruction already set
                elif msg["role"] == "user":
                    gemini_history.append(types.Content(role="user", parts=[types.Part.from_text(text=msg["content"])]))
                elif msg["role"] == "assistant":
                    gemini_history.append(types.Content(role="model", parts=[types.Part.from_text(text=msg["content"])]))
            
            # Create chat session
            chat = genai_client.chats.create(
                model=current_model_name,
                config=model_config,
                history=gemini_history[:-1] if gemini_history else []
            )
            
            # --- Multi-step agent loop ---
            current_message = gemini_history[-1].parts[0].text if gemini_history else user_message
            while True:
                response = None
                last_error = None
                
                # --- Circuit Breaker / Fallback Loop ---
                for model_name in fallback_models:
                    try:
                        # If we switched models, recreate the chat session
                        if model_name != current_model_name or chat is None:
                            print(f"DEBUG: Switching/Initializing model: {model_name}")
                            current_model_name = model_name
                            chat = genai_client.chats.create(
                                model=current_model_name,
                                config=model_config,
                                history=gemini_history[:-1] if gemini_history else []
                            )
                        
                        # Check if 'current_message' is a function response (list of Parts)
                        is_func_response = isinstance(current_message, list) and len(current_message) > 0 and hasattr(current_message[0], 'function_response')
                        
                        if is_func_response and model_name != fallback_models[0]:
                             print("DEBUG: Fallback during function loop - restarting turn with last user message.")
                             final_user_msg = gemini_history[-1].parts[0].text if gemini_history else user_message
                             response = chat.send_message(final_user_msg)
                        else:
                            response = chat.send_message(current_message)
                        
                        # If successful, break the retry loop
                        break
                    except Exception as e:
                        print(f"WARNING: Model {model_name} failed: {e}")
                        last_error = e
                        # Force chat recreation on next loop to ensure clean slate
                        chat = None 
                        # Retry delay as requested by user
                        time.sleep(1.0)
                        continue
                
                if response is None:
                    # If all models failed, raise the last error to be caught by outer try/except
                    raise last_error or Exception("All models failed to generate content.")
                
                candidate = response.candidates[0]
                
                # Check for function calls
                fn_calls = []
                for part in candidate.content.parts:
                    if hasattr(part, 'function_call') and part.function_call:
                        fc = part.function_call
                        fn_calls.append({
                            "name": fc.name,
                            "arguments": dict(fc.args) if fc.args else {}
                        })
                
                if fn_calls:
                    print(f"DEBUG: Processing {len(fn_calls)} function calls")
                    
                    # Execute each function call
                    function_responses = []
                    for call in fn_calls:
                        print(f"DEBUG: Processing function call: {call['name']}")
                        args = call["arguments"]
                        
                        if call["name"] == "sql_tool":
                            result = sql_tool(args.get("sql") or "")
                        elif call["name"] == "multi_sql_tool":
                            # FIX: Handle None from args.get if "queries" is null
                            queries = args.get("queries") or []
                            result = json_lib.dumps(multi_sql_tool(queries))
                        elif call["name"] == "percentage_tool":
                            result = percentage_tool(args.get("numerator_sql") or "", args.get("denominator_sql") or "")
                        elif call["name"] == "chart_tool":
                            try:
                                result = chart_tool(
                                    args.get("sql") or "",
                                    args.get("chart_type", "line"),
                                    args.get("x") or "",
                                    args.get("y") or "",
                                    args.get("title") or "",
                                    args.get("z") or ""
                                )
                            except Exception as chart_exc:
                                result = f"Sorry, I couldn't generate that chart: {chart_exc}"
                            if ("<iframe" in result) or ("<img" in result) or ("![" in result):
                                last_chart_snippet = result
                                # Immediate update of LAST_CHARTS so it can be used in the same turn for emails
                                import re as _re
                                new_charts = _re.findall(r'/static/demo/\S+?\.html', result)
                                LAST_CHARTS = list(set(LAST_CHARTS + new_charts))
                                logger.debug(f"Immediate LAST_CHARTS update: {LAST_CHARTS}")
                        elif call["name"] == "update_dispute_status":
                            result = update_dispute_status(
                                args.get("dispute_id"),
                                args.get("new_status"),
                                args.get("changed_by", "agent"),
                            )
                        elif call["name"] == "add_audit_comment":
                            result = add_audit_comment(
                                args.get("dispute_id"),
                                args.get("comments", ""),
                                args.get("processor", "agent"),
                                args.get("assigned_to", ""),
                            )
                        elif call["name"] == "draft_email_tool":
                            to_users = args.get("to_usernames", [])
                            subject = args.get("subject", "Assistance Summary")
                            body_md = args.get("body_markdown", "") or LAST_BODY
                            
                            # Merge explicit attachments with auto-detected charts to prevent dropping real charts
                            arg_attach = args.get("attachments") or []
                            # FIX: Convert RepeatedComposite to list to avoid TypeError
                            attach = list(set(list(arg_attach) + LAST_CHARTS))
                            print(f"DEBUG EMAIL: LAST_CHARTS={LAST_CHARTS}")
                            print(f"DEBUG EMAIL: arg_attach={list(arg_attach)}")
                            print(f"DEBUG EMAIL: final attach={attach}")
                            import re as _re
                            if (not _re.search(r"\d", body_md or "")) and _re.search(r"\d", LAST_BODY or ""):
                                body_md = (body_md + "\n\nRecent results:\n" + LAST_BODY).strip()
                            result = draft_email_tool(to_users, subject, body_md, attach)
                            print(f"DEBUG EMAIL: draft_email_tool result: {result}")
                        elif call["name"] == "mail_tool":
                            to_users = args.get("to_usernames", [])
                            subject = args.get("subject", "Assistance Summary")
                            body_md = args.get("body_markdown", "") or LAST_BODY
                            arg_attach = args.get("attachments") or []
                            # FIX: Convert RepeatedComposite to list
                            attach = list(set(list(arg_attach) + LAST_CHARTS))
                            result = mail_tool(to_users, subject, body_md, attach)
                        elif call["name"] == "navigate_tool":
                            destination = args.get("destination", "")
                            result = navigate_tool(destination)
                            navigation_result = result  # Store for URL extraction later
                            print(f"DEBUG: navigate_tool result: {result}")
                        else:
                            result = "Unsupported function"
                        
                        # Build function response for Gemini
                        # Build function response for Gemini
                        function_responses.append(
                            types.Part.from_function_response(
                                name=call["name"],
                                response={"result": result}
                            )
                        )
                    
                    # Send function results back to continue the conversation
                    current_message = function_responses
                    continue
                
                # Otherwise, we have the final answer
                final_reply = candidate.content.parts[0].text if candidate.content.parts else "I couldn't generate a response."
                
                # Check if any function call was navigate_tool and extract the URL
                navigation_url = None
                if navigation_result:
                    # Parse the navigation result to extract the URL
                    # Parse the navigation result to extract the URL
                    # import json as json_lib  <-- REMOVED: Causes UnboundLocalError by shadowing global

                    try:
                        nav_data = json_lib.loads(navigation_result)
                        if nav_data.get("action") == "navigate" and nav_data.get("url"):
                            navigation_url = nav_data["url"]
                            logger.info(f"Detected navigation to {navigation_url}")
                    except Exception as e:
                        logger.error(f"Failed to parse navigation result: {e}")
                
                # If this was a navigation request, append a special marker with the URL
                if navigation_url:
                    # Append a hidden marker that frontend can detect
                    final_reply += f"\n\n<!-- NAVIGATE_TO:{navigation_url} -->"
                    logger.debug(f"Added navigation marker to reply")
                
                # Update globals for future email requests
                LAST_BODY = final_reply.strip()
                if last_chart_snippet:
                    import re
                    # Look for HTML chart references (will be converted to PNG at email time)
                    LAST_CHARTS = re.findall(r'/static/demo/\S+?\.html', last_chart_snippet)
                    # Also check for hidden chart_html comments
                    hidden_charts = re.findall(r'chart_html:(/static/demo/\S+?\.html)', last_chart_snippet)
                    LAST_CHARTS.extend(hidden_charts)
                    LAST_CHARTS = list(set(LAST_CHARTS))  # Remove duplicates
                    logger.debug(f"Found chart HTMLs for email: {LAST_CHARTS}")
                
                # Persistence Fix: Do NOT clear LAST_CHARTS here. 
                # We want to remember charts from previous turns for "email this" requests.
                # Just cap the list to avoid infinite growth
                if len(LAST_CHARTS) > 5:
                    LAST_CHARTS = LAST_CHARTS[-5:]
                # If model forgot to include the chart, prepend it
                # Check for <iframe>, <img>, and ![] to avoid duplicating the chart
                if last_chart_snippet and ("<iframe" not in final_reply and "<img" not in final_reply and "![" not in final_reply):
                    # Prepend the chart snippet so it appears before text
                    final_reply = f"{last_chart_snippet}\n\n{final_reply}"
                
                # Build response object
                response_data = {"reply": final_reply}
                if navigation_url:
                    response_data["navigation_url"] = navigation_url
                    logger.info(f"Returning navigation_url in JSON response: {navigation_url}")
                
                return JSONResponse(response_data)


        # ---------------- help mode (single step) ------------------

        # Check for email approval/rejection in help mode
        user_message_lower = user_message.lower().strip()
        if user_message_lower in ["approve", "approved", "yes", "send", "send it"]:
            # User approved the email draft
            print(f"DEBUG: User approved email, checking for draft...")
            session_id = "default"  # In a real app, you'd get this from the request
            print(f"DEBUG: Checking session storage for session_id: {session_id}")
            print(f"DEBUG: EMAIL_DRAFTS keys: {list(EMAIL_DRAFTS.keys())}")
            
            if session_id in EMAIL_DRAFTS:
                draft_data = EMAIL_DRAFTS[session_id]
                print(f"DEBUG: Found draft in session storage: {draft_data}")
                
                # Send the email using the draft
                from analytics_tools import mail_tool
                result = mail_tool(
                    draft_data["recipients"],
                    draft_data["subject"], 
                    draft_data["body"],
                    draft_data["attachments"]
                )
                print(f"DEBUG: Email sent, result: {result}")
                
                # Clear the draft from session storage
                del EMAIL_DRAFTS[session_id]
                
                if "[OK]" in result or "successfully" in result.lower():
                    reply = "✅ Email has been sent successfully!"
                else:
                    reply = f"❌ Error sending email: {result}"
            else:
                print(f"DEBUG: No draft found in session storage")
                reply = "❌ No email draft found to approve."
            return JSONResponse({"reply": reply})
        elif user_message_lower in ["reject", "rejected", "no", "cancel", "don't send"]:
            # User rejected the email draft
            session_id = "default"
            if session_id in EMAIL_DRAFTS:
                del EMAIL_DRAFTS[session_id]
                print(f"DEBUG: Cleared draft from session storage")
            reply = "❌ Email draft has been cancelled."
            return JSONResponse({"reply": reply})

        # Use Gemini for help mode response
        # Convert messages to Gemini format
        gemini_history = []
        for msg in messages:
            if msg["role"] == "system":
                continue
            elif msg["role"] == "user":
                gemini_history.append(types.Content(role="user", parts=[types.Part.from_text(text=msg["content"])]))
            elif msg["role"] == "assistant":
                gemini_history.append(types.Content(role="model", parts=[types.Part.from_text(text=msg["content"])]))
        
        # Create chat and get response
        help_chat = genai_client.chats.create(
            model=CHAT_MODEL,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.5
            ),
            history=gemini_history[:-1] if gemini_history else []
        )
        current_msg = gemini_history[-1].parts[0].text if gemini_history else user_message
        
        try:
            single_resp = help_chat.send_message(current_msg)
        except Exception as gemini_err:
            logger.error(f"Gemini API Error: {gemini_err}")
            if "429" in str(gemini_err) or "Resource has been exhausted" in str(gemini_err):
                return JSONResponse({"reply": "⚠️ **System Overloaded:** I am receiving too many requests right now. Please wait a minute and try again."})
            logger.error(f"Gemini Error: {gemini_err}", exc_info=True)
            return JSONResponse({"reply": f"⚠️ **System Error:** {str(gemini_err)}"})

        reply = (single_resp.candidates[0].content.parts[0].text if single_resp.candidates else "I couldn't generate a response.").strip()
        
        # === Post-process help response (add links) ===
        # Prefer links strictly from embedded docs and only when the doc actually matches the query.
        candidates = []
        try:
            for _, d in (top_docs or []):
                url = (d or {}).get("source_url", "")
                if isinstance(url, str) and url:
                    candidates.append((url, d))
        except Exception:
            candidates = []

        import re
        tokens = [t for t in re.split(r"[^a-z0-9]+", query.lower()) if len(t) >= 3]
        stop = {"the","and","for","with","from","that","this","into","how","what","where","when","rate","cube","help","guide","page","see","link"}
        keywords = [t for t in tokens if t not in stop]

        def is_specific(url: str) -> bool:
            trimmed = url.rstrip('/')
            return (bool(trimmed) and not trimmed.endswith('/help') and not trimmed.endswith('/help/') and not trimmed.endswith('/help/home.html'))

        best_url, best_score = "", 0
        for url, d in candidates:
            title = (d.get("section_title") or "").lower()
            content = (d.get("content") or "").lower()
            hay = f"{title} {content}"
            score = sum(1 for k in keywords if k in hay)
            if is_specific(url): score += 1
            if score > best_score:
                best_score = score
                best_url = url

        def in_whitelist(u: str) -> bool:
            return any(u == w for w in HELP_URL_WHITELIST)
        
        # Fallback chooser
        def choose_from_whitelist_simple(q):
            if not HELP_URL_WHITELIST: return ""
            return "" # Simplified for now, rely on embeddings

        chosen = ""
        if best_url and best_score >= 1 and in_whitelist(best_url):
            chosen = best_url
        
        if chosen and chosen not in reply:
            reply += f"\n\n[Open related guide]({chosen})"

        return JSONResponse({"reply": reply})

    except ResourceExhausted:
        logger.warning("Quota exhausted (429).")
        return JSONResponse(status_code=429, content={"reply": "Oops. I am out of fuel! Tell your Developer to refuel me!"})

    except Exception as e:
        # Fallback in case ResourceExhausted is not caught by the specific block
        if "ResourceExhausted" in type(e).__name__:
             logger.warning("Quota exhausted (429) - caught by fallback.")
             return JSONResponse(status_code=429, content={"reply": "Oops. I am out of fuel! Tell your Developer to refuel me!"})

        import traceback
        print("Error during /api/query request:")
        traceback.print_exc()  # This prints the full error in your terminal
        # Log to file for debugging
        logger.error(f"Error during /api/query request: {e}", exc_info=True)
        # Return 200 so the frontend displays the error instead of hanging
        return JSONResponse(status_code=200, content={"reply": "⚠️ **System Error:** Something went wrong. I have logged the error for the developers to fix."})