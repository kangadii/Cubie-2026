# Cubie – Complete Feature Test Suite & Demo Guide

**Version:** 2.0  
**Last Updated:** 13-Feb-2026  
**Prepared by:** Product Development  
**Purpose:** End-to-end validation of all Cubie features before demo, or deployment.

---

## How to Use This Document

This sheet is meant to be used in two ways:

1. **As a Test Checklist** – Run through every section, execute the test queries, and mark Pass/Fail.
2. **As a Demo Script** – Walk your audience through each section in order. The flow is designed to tell a story: greet Cubie, ask for help, pull data, visualize it, email it, and navigate away.

> **Pre-requisite:** Application must be running locally (`python run.py`) and accessible at `http://127.0.0.1:5000`. Login with valid credentials.

---

## 1. Login & Authentication

| # | Test Case | How to Test | Expected Outcome | Pass/Fail |
|---|-----------|-------------|-------------------|-----------|
| 1.1 | Valid login | Enter correct username & password on the login page | Redirected to the chat interface | |
| 1.2 | Invalid login | Enter wrong credentials | Error message displayed, stays on login page | |
| 1.3 | Session persistence | Refresh the page after logging in | Should stay logged in (not kicked to login) | |
| 1.4 | Logout | Click the logout button | Redirected back to the login page | |

---

## 2. General Chat & Greeting

This confirms that Cubie responds conversationally and doesn't break on casual input.

| # | Test Query | Expected Outcome | Pass/Fail |
|---|-----------|-------------------|-----------|
| 2.1 | `Hello` | Cubie greets back by name (if set in preferences) | |
| 2.2 | `Good morning` | Friendly greeting, no error | |
| 2.3 | `Tell me a joke` | Cubie responds playfully | |
| 2.4 | `Who are you?` | Cubie introduces itself as the TCube360 assistant | |

---

## 3. Help Mode (Application Knowledge Base)

Cubie should provide detailed, context-aware answers sourced from the embedded help documentation. It should NOT navigate or pull data here — just explain.

| # | Test Query | What We're Checking | Expected Outcome | Pass/Fail |
|---|-----------|---------------------|-------------------|-----------|
| 3.1 | `What is the Rate Calculator?` | Help vs Navigation distinction | Returns a definition/explanation of Rate Calculator. Does NOT redirect. | |
| 3.2 | `How do I create a new rate in Rate Maintenance?` | Step-by-step guidance | Detailed steps with bullet points or numbered list | |
| 3.3 | `Explain the Audit Dashboard` | Feature explanation | Describes what the Audit Dashboard shows and how to use it | |
| 3.4 | `Where can I find shipment tracking?` | Location guidance (not redirect) | Tells the user where the feature is located in the app | |
| 3.5 | `What is the difference between Rate Calculator and Rate Simulation?` | Comparison query | Explains both features and the difference | |

**Key Point:** "What is X?" and "Explain X" should always stay in Help mode. This was a known issue before — previously these were being misrouted to Navigation.

---

## 4. Analytics Mode (Data Queries)

Cubie queries the live database and returns actual data. Switch to Analytics mode (or it auto-detects).

| # | Test Query | What We're Checking | Expected Outcome | Pass/Fail |
|---|-----------|---------------------|-------------------|-----------|
| 4.1 | `How many shipments do we have this month?` | Basic count query | Returns a number with brief context | |
| 4.2 | `Show me the top 5 carriers by shipment volume` | Ranked data | Table or list of top 5 carriers | |
| 4.3 | `What is the average delivery time by carrier?` | Aggregation query | Average transit times per carrier | |
| 4.4 | `How many open disputes do we have?` | Dispute data | Count of open disputes | |
| 4.5 | `Show me monthly shipment trends for the last 6 months` | Time-series data | Month-wise breakdown of shipment counts | |

**What to watch for:**
- Cubie should NOT show raw SQL in the response.
- If there's no data, it should say "No data available" — not crash.
- Responses should be concise, not a wall of text.

---

## 5. Visualization (Charts & Graphs)

Cubie generates interactive Plotly charts. These render as embedded iframes in the chat window.

| # | Test Query | Chart Type Expected | What to Verify | Pass/Fail |
|---|-----------|---------------------|----------------|-----------|
| 5.1 | `Show me a bar chart of top 5 carriers by shipment count` | Bar Chart | Chart renders inside chat, no horizontal scroll, no white grid lines | |
| 5.2 | `Create a pie chart of shipments by carrier` | Pie Chart | Labels and percentages visible inside the pie | |
| 5.3 | `Show me a line chart of monthly shipment trends` | Line Chart | Markers on data points, clean axes | |
| 5.4 | `Create a donut chart of dispute types` | Donut Chart | Hole in center, labels readable | |
| 5.5 | `Show me a bar chart of revenue by service type` | Bar Chart | Professional color palette, no grid lines | |

**UI Checks (do these once after generating any chart):**

| # | Check | Expected Outcome | Pass/Fail |
|---|-------|-------------------|-----------|
| 5.6 | "View Full Screen" button | Styled as a blue pill button, centered below the chart | |
| 5.7 | Click "View Full Screen" | Opens a modal with blue gradient header, chart fills the modal | |
| 5.8 | Close the modal | Click X or click outside — modal closes smoothly | |
| 5.9 | Chart fits in chat window | No horizontal scrollbar on the chat container | |
| 5.10 | Grid lines | No white grid lines on any chart type | |

---

## 6. Email Feature

Cubie can compose and send emails with data summaries and chart attachments.

| # | Test Query | What We're Checking | Expected Outcome | Pass/Fail |
|---|-----------|---------------------|-------------------|-----------|
| 6.1 | `Email me the top 5 carriers summary` | End-to-end email | Cubie asks for confirmation, then sends. Email arrives with formatted content and AI disclaimer. | |
| 6.2 | (After generating a chart) `Send me this chart via email` | Chart attachment | Email sent with the chart attached as PNG | |
| 6.3 | `Send a report to john@example.com` | Direct email address | Cubie asks what content to include, then sends to the specified address | |
| 6.4 | `Email this to Admin` | Username resolution | Resolves "Admin" to the actual email from UserProfile table | |
| 6.5 | `Send me an email` (with no prior context) | Ambiguous request handling | Cubie asks what to include instead of sending a blank email | |

**Email Content Checks:**

| # | Check | Expected | Pass/Fail |
|---|-------|----------|-----------|
| 6.6 | Sender name | Shows as "Cubie-TCube360" (not raw email address) | |
| 6.7 | AI Disclaimer | Footer includes "This e-mail is auto-generated using AI" | |
| 6.8 | HTML formatting | Email body is professionally formatted with the blue header template | |

---

## 7. Navigation (Smart Router)

Cubie can redirect users to specific pages in the TCube360 application. The key improvement here is the **Smart Router** — it uses AI to distinguish between "tell me about X" (Help) vs "take me to X" (Navigation).

| # | Test Query | Expected Intent | Expected Outcome | Pass/Fail |
|---|-----------|-----------------|-------------------|-----------|
| 7.1 | `Take me to Rate Calculator` | NAVIGATION | Opens Rate Calculator in new tab | |
| 7.2 | `Open the Audit Dashboard` | NAVIGATION | Opens Audit Dashboard in new tab | |
| 7.3 | `Go to Dispute Management` | NAVIGATION | Opens Dispute Management page | |
| 7.4 | `Navigate to Shipment Details` | NAVIGATION | Opens Shipment Details page | |
| 7.5 | `What is Rate Calculator?` | HELP (NOT navigation) | Explains the feature, does NOT redirect | |

**Smart Router Validation (Critical):**

These queries specifically test that the AI correctly differentiates intent:

| # | Test Query | Should Route To | Why | Pass/Fail |
|---|-----------|-----------------|-----|-----------|
| 7.6 | `What is the Rate Calculator?` | Help | User wants a definition, not a redirect | |
| 7.7 | `I want to see the Rate Calculator` | Navigation | User wants to go there | |
| 7.8 | `Explain Dispute Management` | Help | User wants to understand the feature | |
| 7.9 | `Open Rate Maintenance` | Navigation | Explicit action command | |
| 7.10 | `Where is the Audit Dashboard?` | Help | User is asking for location/guidance | |

**Available Navigation Targets:**

For reference, these are all the pages Cubie can navigate to:

| Page | Route |
|------|-------|
| Rate Calculator | `/rate-calculator` |
| Rate Maintenance | `/rate-maintenance` |
| Rate Dashboard | `/rate-dashboard` |
| Audit Dashboard | `/audit-dashboard` |
| Executive Summary | `/executive-summary` |
| Invoice Details | `/invoice-details` |
| Shipment Details | `/shipment-details` |
| Dispute Management | `/dispute-management` |
| Discrepancy Report | `/discrepancy-report` |
| Approved Freight Report | `/approved-freight-report` |
| Rate Simulation | `/rate-simulation` |
| Amendment Report | `/amendment-report` |
| Contract Analysis | `/contract-analysis` |
| Route Group | `/route-group` |
| Route Rule | `/route-rule` |
| Unit Change Report | `/unit-change-report` |
| Rate Configuration | `/rate-config` |
| UN/LOCODE | `/unlocode` |

---

## 8. Dispute Management Actions

Cubie can update dispute statuses and add audit comments directly from the chat.

| # | Test Query | Expected Outcome | Pass/Fail |
|---|-----------|-------------------|-----------|
| 8.1 | `Close dispute 1001` | Dispute status updated to Closed | |
| 8.2 | `Reopen dispute 1001` | Dispute status updated to Open | |
| 8.3 | `Add a comment to dispute 1001: Reviewed and approved by finance team` | Comment added to AuditTrail | |
| 8.4 | `What is the status of dispute 1001?` | Returns current status | |

---

## 9. User Preferences & Customization

| # | Test Case | How to Test | Expected Outcome | Pass/Fail |
|---|-----------|-------------|-------------------|-----------|
| 9.1 | Set preferred name | Open settings, set name to "Alex" | Cubie greets as "Alex" in first message | |
| 9.2 | Response length | Set to "short" | Cubie gives brief answers | |
| 9.3 | Personality: Cheerful | Select "Cheerful" trait | Cubie uses exclamation points and upbeat tone | |
| 9.4 | Personality: Professional | Select "Professional" trait | Cubie is more formal and businesslike | |
| 9.5 | Dark Mode | Toggle dark mode | UI switches to dark theme, chat and modals included | |

---

## 10. Edge Cases & Error Handling

| # | Test Case | Test Query | Expected Outcome | Pass/Fail |
|---|-----------|-----------|-------------------|-----------|
| 10.1 | Empty input | (submit with no text) | Should not crash, prompt user to type something | |
| 10.2 | Very long query | Paste a 500-word paragraph | Should still process and respond | |
| 10.3 | Non-existent page | `Take me to salary calculator` | "I couldn't find that page" with available options listed | |
| 10.4 | Data query with no results | `Show me shipments from Antarctica` | "No data available" — clean message, no crash | |
| 10.5 | Special characters | `What about <script>alert('hi')</script>` | No XSS, query is sanitized | |

---

## 11. Voice Input (Speech-to-Text)

| # | Test Case | Expected Outcome | Pass/Fail |
|---|-----------|-------------------|-----------|
| 11.1 | Click microphone icon | Browser asks for microphone permission | |
| 11.2 | Speak a query | Transcribed text appears in the input box | |
| 11.3 | Submit voice query | Cubie processes it like a typed query | |

---

## Quick Demo Flow (Recommended Order)

If you're demoing Cubie to someone, follow this sequence for maximum impact:

1. **Login** – Show the authentication flow.
2. **Greet Cubie** – "Hello" → Get a friendly response.
3. **Ask for Help** – "What is the Rate Calculator?" → Show knowledge base capability.
4. **Pull Data** – "Show me the top 5 carriers by shipment volume" → Show live data querying.
5. **Visualize** – "Create a bar chart of that" → Show chart generation.
6. **Full Screen** – Click "View Full Screen" → Show the modal.
7. **Email** – "Email this to me" → Show the email feature with chart attachment.
8. **Navigate** – "Take me to Rate Dashboard" → Show in-app navigation.
9. **Smart Routing** – "What is Rate Dashboard?" → Prove it gives Help, not Navigation.
10. **Customize** – Open settings, switch personality, toggle dark mode.

---

## Feature Summary

| Feature | Status | Tech Stack |
|---------|--------|------------|
| Authentication | Active | FastAPI Sessions, SQL Server |
| Help Mode (RAG) | Active | Gemini Embeddings + Cosine Similarity |
| Analytics | Active | Gemini Function Calling + SQL Server |
| Visualization | Active | Plotly (Interactive HTML Charts) |
| Email | Active | SMTP (SendGrid) with HTML Templates |
| Navigation | Active | Smart Router (Gemini 2.0 Flash) |
| Voice Input | Active | Web Speech API |
| Dark Mode | Active | CSS Toggle |
| Dispute Management | Active | Direct DB Mutations via Chat |

---

**End of Test Suite.**
