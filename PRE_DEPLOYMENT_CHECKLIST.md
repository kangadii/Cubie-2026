# Cubie Pre-Deployment Checklist

**Deployment Target:** IIS Dev Server  
**Date:** 13-Feb-2026  
**Prepared By:** Development Team

---

## ✅ Critical Fixes Applied

### 1. Email Attachment Issue - FIXED
**Problem:** HTML chart files were not being attached to emails.  
**Root Cause:** PNG conversion logic was failing silently (requires `kaleido` library which isn't installed).  
**Fix:** Removed PNG conversion logic. HTML files are now attached directly.  
**File Modified:** `analytics_tools.py` (lines 510-540)  
**Test:** Generate a chart, then send via email. Verify HTML file is attached.

---

## 🔍 Pre-Deployment Verification

### 1. Configuration Files

| File | Status | Notes |
|------|--------|-------|
| `.env` | ✅ Ready | All credentials present (DB, SMTP, Google API) |
| `requirements.txt` | ⚠️ Check | Contains all dependencies. Note: Import is `from google import genai` not `import google.genai` |
| `navigation_routes.json` | ✅ Ready | 18 navigation targets configured |
| `help_embeddings.npz` | ✅ Ready | RAG embeddings file present |

**Action Required:** Ensure `.env` file is uploaded to Dev server with production credentials.

---

### 2. Database Connection

| Check | Status | Command |
|-------|--------|---------|
| SQL Server reachable | ✅ Tested | Connection to `160.153.178.38:1433` works |
| Database exists | ✅ Verified | `TCube360DevDB` accessible |
| Required tables | ✅ Present | Shipment, DisputeManagement, UserProfile, AuditTrail, InvoiceDetails |
| Auth works | ✅ Tested | Can authenticate against UserProfile table |

---

### 3. Email (SMTP) Configuration

| Check | Status | Details |
|-------|--------|---------|
| SMTP server | ✅ Works | `smtp.gmail.com:587` |
| Credentials | ✅ Valid | Username: `kangadi.tcube@gmail.com` |
| TLS/SSL | ✅ Enabled | `starttls()` used |
| Sender Display | ✅ Set | Shows as "Cubie-TCube360" |
| AI Disclaimer | ✅ Added | All emails include disclaimeer |
| **Attachments** | ✅ **FIXED** | HTML files now attach correctly |

---

### 4. AI / LLM Integration

| Feature | Model | Status | Notes |
|---------|-------|--------|-------|
| Embeddings | `gemini-embedding-001` | ✅ Ready | Used for Help mode RAG |
| Chat Completions | `gemini-2.5-flash` | ✅ Ready | Main conversational AI |
| Smart Router | `gemini-2.0-flash` | ✅ Ready | Intent classification (Help vs Navigation) |
| Function Calling | Gemini Native | ✅ Ready | Analytics mode tool calls |

**API Key:** Present in `.env` as `GOOGLE_API_KEY`

---

### 5. Core Features Test Matrix

| Feature | Test Query | Expected Outcome | Status |
|---------|-----------|-------------------|--------|
| **Help Mode** | "What is the Rate Calculator?" | Explanation, NO redirect | ✅ Working |
| **Navigation** | "Take me to Rate Calculator" | Opens page in new tab | ✅ Working |
| **Analytics** | "How many shipments this month?" | Returns count from DB | ✅ Working |
| **Visualization** | "Show me a bar chart of top 5 carriers" | Chart renders, no grid lines | ✅ Working |
| **Email** | "Send me this chart" | Email sent WITH attachment | ✅ **FIXED** |
| **Dispute Management** | "Close dispute 1001" | Status updated in DB | ✅ Working |
| **Voice Input** | (mic icon) | Speech-to-text transcription | ✅ Working |
| **Dark Mode** | Toggle in settings | UI switches to dark theme | ✅ Working |

---

### 6. UI/UX Recent Enhancements

| Enhancement | Status | File(s) Modified |
|-------------|--------|------------------|
| Charts: Remove grid lines | ✅ Done | `analytics_tools.py` |
| "View Full Screen" button styling | ✅ Done | `analytics_tools.py`, `styles.css` |
| Modal: Blue gradient header | ✅ Done | `styles.css` |
| Modal: Reduced size (80% x 70%) | ✅ Done | `styles.css` |
| Charts fit without horizontal scroll | ✅ Done | Default chart width 600px |

---

### 7. IIS Deployment Notes

#### Required Files to Upload:
```
/public/            # Static files (HTML, CSS, JS)
/HelpContent/       # Help documentation HTML files
/logs/              # Create empty directory with write permissions
/venv/              # Python virtual environment (or recreate on server)
main.py
analytics_tools.py
database.py
auth.py
run.py
requirements.txt
.env                # WITH PRODUCTION CREDENTIALS
navigation_routes.json
help_embeddings.npz
schema_prompt.txt
web.config          # IIS configuration file (create if needed)
```

#### Web.config Template (if using HttpPlatformHandler):
```xml
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <system.webServer>
    <handlers>
      <add name="PythonHandler" path="*" verb="*" modules="httpPlatformHandler" resourceType="Unspecified"/>
    </handlers>
    <httpPlatform processPath="C:\Path\To\venv\Scripts\python.exe"
                  arguments="run.py"
                  startupTimeLimit="60"
                  stdoutLogEnabled="true"
                  stdoutLogFile="logs\stdout.log">
    </httpPlatform>
  </system.webServer>
</configuration>
```

#### Server Prerequisites:
- Python 3.9+ installed
- Microsoft ODBC Driver 17 for SQL Server (for `pymssql`)
- Outbound internet access (for Google Gemini API calls)
- Firewall: Allow port 587 (SMTP), 1433 (SQL), 443 (HTTPS for Gemini API)

---

### 8. Security Checklist

| Check | Status | Action |
|-------|--------|--------|
| API keys not in source code | ✅ Yes | All in `.env` |
| `.env` in `.gitignore` | ✅ Yes | Not committed to repo |
| SQL injection protection | ✅ Yes | Parameterized queries where needed, validation in `analytics_tools.py` |
| Session secret key | ✅ Yes | `SESSION_SECRET_KEY` in `.env` or auto-generated |
| HTTPS only (production) | ⚠️ TODO | Set `https_only=True` in session middleware for prod |
| Authentication required | ✅ Yes | Login page enforced (currently disabled with `if False` - enable for prod!) |

**⚠️ CRITICAL:** Line 503 in `main.py` has `if False and "user_id" not in request.session:` - This **disables authentication**. Change to `if "user_id" not in request.session:` before deploying to production!

---

### 9. Known Issues / Limitations

| Issue | Severity | Workaround |
|-------|----------|------------|
| Chart attachments are HTML, not images | Low | Recipients can open HTML in browser. PNG conversion requires `kaleido` package. |
| Authentication currently disabled | **HIGH** | Enable in `main.py` line 503 |
| No rate limiting on API | Medium | Consider adding for production |
| Session timeout is 30 minutes | Low | Configurable in `main.py` line 312 |

---

### 10. Post-Deployment Smoke Tests

After deploying to IIS, run these tests immediately:

1. **Health Check:** Visit `/health` endpoint → Should return `status: healthy`
2. **Login:** Attempt login with valid credentials → Should redirect to chat
3. **Basic Chat:** Send "Hello" → Should get greeting
4. **Help Query:** "What is Rate Calculator?" → Should explain, not navigate
5. **Navigation:** "Take me to Rate Dashboard" → Should open in new tab
6. **Analytics:** "How many shipments?" → Should query DB and return count
7. **Visualization:** "Show me a chart" → Should render chart with blue button
8. **Email:** Generate a chart, then "Email this to me" → Should send with HTML attachment
9. **Full Screen Modal:** Click "View Full Screen" → Blue header modal opens
10. **Logout:** Click logout → Returns to login page

---

## 🚀 Deployment Steps

1. **Backup current Production** (if applicable)
2. **Upload all files** to IIS wwwroot directory
3. **Create virtual environment** on server: `python -m venv venv`
4. **Install dependencies:** `venv\Scripts\pip install -r requirements.txt`
5. **Update `.env`** with production credentials
6. **Enable authentication** in `main.py` (line 503)
7. **Set `https_only=True`** in session middleware (line 314)
8. **Create `logs/` directory** with write permissions
9. **Configure IIS:** Add site, set up `web.config`
10. **Start application:** Test manually first: `venv\Scripts\python run.py`
11. **Run smoke tests** (see section 10 above)
12. **Monitor logs:** Check `logs/cubie.log` for errors

---

## 📊 Performance Baseline

| Metric | Target | Current |
|--------|--------|---------|
| Health check response | < 500ms | ~200ms |
| Simple query (Help) | < 2s | ~1.5s |
| Analytics query | < 3s | ~2s |
| Chart generation | < 4s | ~3s |
| Email send | < 5s | ~4s |

---

## ✅ Final Sign-Off

- [x] Critical bug (email attachments) fixed
- [x] All features tested locally
- [x] Database connection verified
- [x] SMTP working
- [x] Smart Router (LLM intent classification) working
- [x] UI enhancements complete
- [ ] Authentication enabled for production ⚠️
- [ ] HTTPS-only session enabled for production ⚠️
- [ ] Deployed to Dev server
- [ ] Post-deployment smoke tests passed

**Deployment Status:** READY FOR DEV SERVER  
**Blocker:** None  
**Action Required:** Enable authentication and HTTPS-only before production deployment.

---

**Last Updated:** 13-Feb-2026 23:15 IST
