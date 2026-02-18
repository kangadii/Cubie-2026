const form = document.getElementById('chat-form');
const userInput = document.getElementById('user-input');
const chatBox = document.getElementById('chat-box');
const typingIndicator = document.getElementById('typing-indicator');
const toggleDark = document.getElementById('toggle-dark');
const micButton = document.getElementById('mic-button');
const notesBtn = document.getElementById('notes-btn');
const notesModal = document.getElementById('notes-modal');
const closeNotesBtn = document.getElementById('close-notes');
const notesList = document.getElementById('notes-list');
const notesEmpty = document.getElementById('notes-empty');
const logoutBtn = document.getElementById('logout-btn');
const root = document.body;

let isRecording = false;
let recognition;
let isSubmitting = false; // Debounce flag to prevent multiple submissions

// Track current conversation mode: "help" (default) or "analytics"
let currentMode = 'help';
// Sticky routing after user clicks a mode button (e.g., Analyze Data)
let stickyMode = null; // 'help' | 'analytics' | null
let stickyRemaining = 0; // number of messages to keep the sticky mode

// === Backend API URL ===
// Local dev uses same origin
const API_URL = '/api/query';

// SVG constants for copy button (user provided, no border, no fill)
const COPY_SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8"><rect x="9" y="9" width="11" height="11" rx="2" ry="2"></rect><path d="M15 9V7a2 2 0 0 0-2-2H7a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2"></path></svg>`;
const COPIED_SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><polyline points="5 13 9 17 19 7" /></svg>`;

function scrollToBottom() {
  chatBox.scrollTop = chatBox.scrollHeight;
}

async function typeText(container, text) {
  container.innerHTML = '';
  const temp = document.createElement('div');
  temp.innerHTML = marked.parse(text, { breaks: true, gfm: true });
  const fullHTML = temp.innerHTML;

  // Extract iframes/objects to prevent re-fetching during typewriter animation
  // Each innerHTML assignment destroys and recreates iframes, causing repeated HTTP requests
  const iframeRegex = /<(iframe|object)[^>]*>[\s\S]*?<\/\1>/gi;
  const extractedIframes = [];
  let iframeIndex = 0;
  const animatableHTML = fullHTML.replace(iframeRegex, (match) => {
    const placeholder = `<span class="iframe-placeholder" data-iframe-index="${iframeIndex}"></span>`;
    extractedIframes.push({ index: iframeIndex, html: match });
    iframeIndex++;
    return placeholder;
  });

  let i = 0;
  function type() {
    if (i <= animatableHTML.length) {
      container.innerHTML = animatableHTML.slice(0, i += 4);
      scrollToBottom();
      setTimeout(type, 4);
    } else {
      // Animation complete - now inject the real iframes
      extractedIframes.forEach(({ index, html }) => {
        const placeholder = container.querySelector(`[data-iframe-index="${index}"]`);
        if (placeholder) {
          const tempEl = document.createElement('div');
          tempEl.innerHTML = html;
          placeholder.replaceWith(tempEl.firstChild);
        }
      });
      scrollToBottom();
    }
  }
  type();
}

function createCopyButton(inner) {
  const buttonContainer = document.createElement('div');
  buttonContainer.className = 'message-buttons';

  const copyBtn = document.createElement('button');
  copyBtn.className = 'copy-btn-right';
  copyBtn.title = 'Copy to clipboard';
  copyBtn.innerHTML = COPY_SVG;
  copyBtn.onclick = function () {
    navigator.clipboard.writeText(inner.textContent.trim());
    copyBtn.innerHTML = COPIED_SVG;
    setTimeout(() => { copyBtn.innerHTML = COPY_SVG; }, 1200);
  };

  const saveBtn = document.createElement('button');
  saveBtn.className = 'save-btn-right';
  saveBtn.title = 'Save to notes';
  saveBtn.innerHTML = `
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
      <polyline points="14,2 14,8 20,8"/>
      <line x1="16" y1="13" x2="8" y2="13"/>
      <line x1="16" y1="17" x2="8" y2="17"/>
      <polyline points="10,9 9,9 8,9"/>
    </svg>
  `;
  saveBtn.onclick = function () {
    addNote(inner.textContent.trim());
    updateNotesDisplay();
    saveBtn.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M9 12l2 2 4-4"/>
        <circle cx="12" cy="12" r="10"/>
      </svg>
    `;
    setTimeout(() => {
      saveBtn.innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14,2 14,8 20,8"/>
          <line x1="16" y1="13" x2="8" y2="13"/>
          <line x1="16" y1="17" x2="8" y2="17"/>
          <polyline points="10,9 9,9 8,9"/>
        </svg>
      `;
    }, 1200);
  };

  buttonContainer.appendChild(copyBtn);
  buttonContainer.appendChild(saveBtn);
  return buttonContainer;
}

function addMessage(content, sender = 'user', slowType = false) {
  const msg = document.createElement('div');
  msg.className = `message ${sender}`;
  const inner = document.createElement('div');
  inner.className = 'message-content';
  msg.appendChild(inner);
  chatBox.appendChild(msg);
  scrollToBottom();

  if (sender === 'bot' && slowType) {
    typeText(inner, content);
  } else if (sender === 'bot') {
    inner.innerHTML = marked.parse(content, { breaks: true, gfm: true });
  } else {
    inner.textContent = content;
  }

  if (sender === 'bot') {
    const copyWrapper = document.createElement('div');
    copyWrapper.className = 'copy-btn-right-wrapper';
    copyWrapper.appendChild(createCopyButton(inner));
    // Place the copy button wrapper as a child of the message bubble for absolute positioning
    msg.appendChild(copyWrapper);
    // Email approval buttons removed - emails are now sent directly
  }
}

window.addEventListener('DOMContentLoaded', () => {
  // Typewriter effect for initial message
  const prefs = getCubiePrefs();
  const initialMsg = prefs.name
    ? `Hi ${prefs.name}! I'm Cubie 👋 Just ask me anything - I'll automatically help you with app questions, data analysis, or create visualizations!`
    : "Hi, I'm Cubie 👋 Just ask me anything - I'll automatically help you with app questions, data analysis, or create visualizations!";
  function typeInitialMessage(msg, cb) {
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message bot';
    const inner = document.createElement('div');
    inner.className = 'message-content';
    msgDiv.appendChild(inner);
    chatBox.appendChild(msgDiv);
    let i = 0;
    function type() {
      if (i <= msg.length) {
        inner.textContent = msg.slice(0, i++);
        scrollToBottom();
        setTimeout(type, 18);
      } else {
        if (cb) cb(msgDiv);
      }
    }
    type();
  }
  // Remove any existing suggestion bubbles
  let oldBubbles = document.getElementById('suggestion-bubbles');
  if (oldBubbles) oldBubbles.remove();
  // Type initial message, then show suggestion bubbles right after it
  typeInitialMessage(initialMsg, (msgDiv) => {
    setTimeout(() => {
      // Create and insert suggestion bubbles after the first message
      const suggestionBubbles = document.createElement('div');
      suggestionBubbles.className = 'suggestion-bubbles';
      suggestionBubbles.id = 'suggestion-bubbles';
      suggestionBubbles.innerHTML = `
        <button class="suggestion-btn">📚 Application Help</button>
        <button class="suggestion-btn">📊 Analyze Data</button>
        <button class="suggestion-btn">📈 Visualize Data</button>
      `;
      msgDiv.after(suggestionBubbles);
      setTimeout(() => {
        suggestionBubbles.classList.add('visible');
      }, 50);
      // Suggestion bubble click handler
      suggestionBubbles.addEventListener('click', function (e) {
        if (e.target.classList.contains('suggestion-btn')) {
          e.preventDefault();
          e.stopPropagation();
          const text = e.target.textContent.trim();
          console.log('Button clicked:', text); // Debug log
          // Mode switch buttons shouldn't hit backend immediately
          if (text.includes('Analyze Data')) {
            console.log('Analyze Data button detected!'); // Debug log
            currentMode = 'analytics';
            stickyMode = 'analytics';
            stickyRemaining = 3; // keep analytics for next 3 user messages
            addMessage("I'm ready to analyze your data! Ask me about shipments, disputes, invoices, or any specific metrics you want to explore.", 'bot', true);
            return;
          }
          if (text.includes('Application Help')) {
            currentMode = 'help';
            stickyMode = 'help';
            stickyRemaining = 2;
            addMessage("Sure! I'm ready to answer any application questions. What would you like to know?", 'bot', true);
            userInput.value = '';
            return;
          }
          if (text.includes('Visualize Data')) {
            console.log('Visualize Data button detected!'); // Debug log
            currentMode = 'analytics';
            addMessage("I can create charts and graphs for you! Tell me what data you want to visualize - shipments, disputes, invoices, or any specific metrics.", 'bot', true);
            return;
          }
          // For other suggestions, keep default behavior
          userInput.value = text;
          form.dispatchEvent(new Event('submit'));
          // Remove focus to prevent border from staying
          e.target.blur();
        }
      });
    }, 400);
  });
  if (localStorage.getItem('cubie-theme') === 'dark') {
    root.classList.add('dark-mode');
    toggleDark.textContent = '☀️';
  }
  const downloadBtn = document.getElementById('download-pdf');
  if (downloadBtn) {
    downloadBtn.addEventListener('click', function () {
      const messages = Array.from(document.querySelectorAll('.message'));
      let text = '';
      messages.forEach(msg => {
        if (msg.classList.contains('user')) {
          text += 'You: ';
        } else {
          text += 'Cubie: ';
        }
        text += msg.textContent.trim() + '\n\n';
      });
      const { jsPDF } = window.jspdf;
      const doc = new jsPDF({ unit: 'pt', format: 'a4' });
      const margin = 40;
      let y = margin + 30;
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(18);
      doc.text('Cubie Conversation', margin, margin);
      doc.setFont('helvetica', 'normal');
      doc.setFontSize(12);
      const now = new Date();
      const dateStr = now.toLocaleString();
      doc.text('Date: ' + dateStr, margin, margin + 18);
      doc.setLineWidth(0.5);
      doc.line(margin, margin + 24, 555, margin + 24);
      y = margin + 40;
      const lines = doc.splitTextToSize(text, 515 - margin * 2);
      lines.forEach(line => {
        if (y > 780) {
          doc.addPage();
          y = margin;
        }
        doc.text(line, margin, y);
        y += 18;
      });
      doc.save('Cubie_Conversation.pdf');
    });
  }

  // === Logout Handler ===
  if (logoutBtn) {
    logoutBtn.addEventListener('click', async function () {
      if (confirm('Are you sure you want to log out?')) {
        try {
          await fetch('/api/logout', { method: 'POST' });
          window.location.href = '/';
        } catch (error) {
          console.error('Logout error:', error);
          // Redirect anyway
          window.location.href = '/';
        }
      }
    });
  }
});

// === Customize Modal Logic ===
const customizeBtn = document.getElementById('customize-btn');
const customizeModal = document.getElementById('customize-modal');
const closeCustomize = document.getElementById('close-customize');
const customizeCancel = document.getElementById('customize-cancel');
const customizeForm = document.getElementById('customize-form');
const cubieNameInput = document.getElementById('cubie-name');

function getCubiePrefs() {
  try {
    return JSON.parse(localStorage.getItem('cubiePrefs')) || {};
  } catch (e) {
    return {};
  }
}

function setCubiePrefs(prefs) {
  localStorage.setItem('cubiePrefs', JSON.stringify(prefs));
}

function openCustomizeModal() {
  customizeModal.style.display = 'flex';
  // Load preferences from localStorage
  const prefs = getCubiePrefs();
  cubieNameInput.value = prefs.name || '';
  // Set response length
  document.querySelectorAll('.response-length-btn').forEach(btn => {
    btn.classList.toggle('selected', btn.dataset.length === prefs.length);
  });
  // Set traits
  document.querySelectorAll('.trait-btn').forEach(btn => {
    btn.classList.toggle('selected', (prefs.traits || []).includes(btn.dataset.trait));
  });
}
function closeCustomizeModal() {
  customizeModal.style.display = 'none';
}
if (customizeBtn) customizeBtn.onclick = openCustomizeModal;
if (closeCustomize) closeCustomize.onclick = closeCustomizeModal;
if (customizeCancel) customizeCancel.onclick = closeCustomizeModal;
// Response length single select
customizeModal && customizeModal.addEventListener('click', function (e) {
  if (e.target.classList.contains('response-length-btn')) {
    document.querySelectorAll('.response-length-btn').forEach(btn => btn.classList.remove('selected'));
    e.target.classList.add('selected');
  }
  // Multi-select for traits
  if (e.target.classList.contains('trait-btn')) {
    e.target.classList.toggle('selected');
  }
});
// Save preferences
if (customizeForm) customizeForm.onsubmit = function (e) {
  e.preventDefault();
  const name = cubieNameInput.value.trim();
  const lengthBtn = document.querySelector('.response-length-btn.selected');
  const length = lengthBtn ? lengthBtn.dataset.length : '';
  const traits = Array.from(document.querySelectorAll('.trait-btn.selected')).map(btn => btn.dataset.trait);
  setCubiePrefs({ name, length, traits });
  closeCustomizeModal();
  // Reload the page to update the initial greeting
  window.location.reload();
};

// Use preferences in next message
// On page load, always load prefs and use for greeting
let cubiePrefs = getCubiePrefs();

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  console.log('Form submitted with question:', userInput.value.trim()); // Debug log

  if (isSubmitting) {
    console.warn('Submission blocked: already submitting');
    return;
  }
  isSubmitting = true;
  userInput.disabled = true;

  // Always reload prefs in case they changed
  cubiePrefs = getCubiePrefs();
  const question = userInput.value.trim();
  if (!question) return;
  // --- Per-message mode detection: default to help unless strong analytics cues ---
  const ql = question.toLowerCase();
  // If a sticky mode is active from a recent button click, apply it first
  if (stickyMode) {
    currentMode = stickyMode;
    stickyRemaining = Math.max(0, stickyRemaining - 1);
    if (stickyRemaining === 0) stickyMode = null;
  } else {
    // Enhanced auto-detection of mode based on user message

    // Visualization keywords - strongly indicate chart/graph requests
    const vizWords = ['chart', 'graph', 'plot', 'visualize', 'visualization', 'bar chart', 'line chart', 'pie chart', 'heatmap', 'stacked', 'trend line', 'show me a chart', 'create a chart', 'generate a chart', 'draw a'];

    // Analytics/metrics keywords - indicate data queries
    const metricWords = ['top', 'total', 'sum', 'average', 'avg', 'count', 'rate', 'trend', 'percentage', 'percent', 'max', 'min', 'median', 'mean', 'kpi', 'amount', 'volume', 'number of', 'how many', 'statistics', 'stats', 'performance', 'compare', 'comparison'];

    // Domain/entity keywords - entities in the database
    const domainWords = ['shipment', 'shipments', 'invoice', 'invoices', 'dispute', 'disputes', 'carrier', 'carriers', 'lane', 'lanes', 'destination', 'origin', 'delivery', 'deliveries', 'package', 'packages', 'tracking'];

    // Action keywords - indicate mutations/operations
    const actionWords = ['close', 'reopen', 'update', 'set status', 'change status', 'add comment', 'assign'];

    // Email keywords - indicate email requests
    const emailWords = ['email', 'send email', 'mail', 'send to', 'email me', 'send me'];

    // Navigation action words - require explicit action intent
    const navigationActions = ['take me to', 'go to', 'open', 'navigate to', 'navigate me', 'redirect me', 'bring me to', 'launch'];

    // Navigation targets - specific TCube screens/pages
    const navigationTargets = ['rate calculator', 'rate dashboard', 'rate maintenance', 'audit dashboard', 'shipment tracking', 'dispute management', 'reports', 'admin', 'admin settings'];

    // Time/period keywords - often indicate analytics
    const timeWords = ['last', 'past', 'ytd', 'q1', 'q2', 'q3', 'q4', 'week', 'weeks', 'month', 'months', 'day', 'days', 'year', 'years', 'quarter', 'quarters', 'november', 'december', 'today', 'yesterday', 'this week', 'this month', 'this year', '2024', '2025'];

    // Help/documentation keywords - indicate application help
    const helpWords = ['how do i', 'how to', 'what is', 'where is', 'where can i', 'explain', 'help me', 'help with', 'guide', 'tutorial', 'documentation', 'show me how', 'teach me', 'feature', 'module', 'menu', 'find the', 'access', 'rate cube', 'audit cube', 'admin cube', 'track cube', 'setting', 'settings', 'configure', 'configuration', 'step by step', 'steps to', 'walkthrough', 'instructions'];

    const has = (arr) => arr.some(w => ql.includes(w));

    // First check if it's clearly a help request
    const isHelpRequest = has(helpWords) && !has(metricWords) && !has(vizWords);

    // Check for navigation - require BOTH action AND target to avoid false positives
    const isNavigation = has(navigationActions) && has(navigationTargets);

    // Then check for analytics/visualization
    const isAnalytics = (
      has(vizWords) ||
      isNavigation ||  // Navigation requests need analytics mode for navigate_tool
      (has(domainWords) && has(metricWords)) ||
      (has(metricWords) && has(timeWords)) ||
      (has(domainWords) && has(timeWords)) ||
      // mutation/intents like closing disputes
      ((ql.includes('dispute') || ql.includes('disputes')) && has(actionWords)) ||
      has(emailWords) ||
      ql.startsWith('how many ') ||
      ql.startsWith('what is the total') ||
      ql.startsWith('show me the top') ||
      ql.startsWith('get me') ||
      ql.startsWith('from the data') ||
      ql.startsWith('analyze ') ||
      ql.includes('return the numbers') ||
      ql.includes('create a ') && (ql.includes('chart') || ql.includes('graph')) ||
      ql.includes('generate a ') && (ql.includes('chart') || ql.includes('graph'))
    );

    // SMART CONTEXT LOGIC
    const lastBotMsg = Array.from(document.querySelectorAll('.message.bot')).pop();
    const lastBotText = lastBotMsg ? lastBotMsg.textContent.toLowerCase() : '';

    // 1. Transaction Check: Is this a reply to a bot question?
    // Check if bot asked a question or asked for confirmation/sending
    const isReplyContext = lastBotText.includes('?') || lastBotText.includes('confirm') || lastBotText.includes('send') || lastBotText.includes('should i');
    const isConfirmation = ['yes', 'sure', 'proceed', 'go ahead', 'do it', 'ok', 'right', 'correct', 'please'].some(w => ql.includes(w));

    if (isReplyContext && isConfirmation) {
      // User is confirming a previous bot action -> FORCE Analytics
      currentMode = 'analytics';
      console.log('Smart Context: Detected confirmation reply, forcing Analytics mode.');
    }
    // 2. Sticky Context: If already in Analytics, and input is ambiguous, STAY in Analytics
    // This allows follow-up questions like "what about FedEx?" without restating intent
    else if (currentMode === 'analytics' && !isHelpRequest && !isNavigation) {
      currentMode = 'analytics';
      console.log('Smart Context: Ambiguous input, persisting Analytics mode.');
    }
    // 3. Explicit Mode Logic
    else if (isAnalytics) {
      currentMode = 'analytics';
    }
    else if (isHelpRequest) {
      currentMode = 'help';
    }
    // 4. Default Fallback
    else {
      currentMode = 'help'; // Default to help mode
    }

    console.log('Auto-detected mode:', currentMode, 'for query:', ql.substring(0, 50) + '...'); // Debug log
  }
  addMessage(question, 'user');
  userInput.value = '';
  typingIndicator.style.display = 'flex';
  try {
    // Build conversation history from current messages
    const messages = Array.from(document.querySelectorAll('.message'));
    const history = [];

    messages.forEach(msg => {
      if (msg.classList.contains('user')) {
        history.push({ role: 'user', content: msg.textContent.trim() });
      } else if (msg.classList.contains('bot')) {
        history.push({ role: 'assistant', content: msg.textContent.trim() });
      }
    });

    console.log('Sending request to:', API_URL); // Debug log
    console.log('Request payload:', { question, mode: currentMode, prefs: cubiePrefs, history: history }); // Debug log

    const response = await fetch(API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question,
        mode: currentMode,
        prefs: cubiePrefs,
        history: history
      }),
    });

    console.log('Response status:', response.status); // Debug log
    console.log('Response ok:', response.ok); // Debug log

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    console.log('Response data:', data); // Debug log

    if (data.reply) {
      // Check for navigation marker in the response
      let finalReply = data.reply;
      let navigationUrl = null;

      // First check for dedicated navigation_url field (most reliable)
      if (data.navigation_url) {
        navigationUrl = data.navigation_url;
        console.log('Navigation URL from JSON field:', navigationUrl);
      }

      // Also look for <!-- NAVIGATE_TO:URL --> marker as fallback
      const navMarkerMatch = data.reply.match(/<!--\s*NAVIGATE_TO:(.*?)\s*-->/);
      if (navMarkerMatch && navMarkerMatch[1]) {
        if (!navigationUrl) {
          navigationUrl = navMarkerMatch[1].trim();
        }
        // Remove the marker from the displayed message
        finalReply = data.reply.replace(navMarkerMatch[0], '').trim();
        console.log('Navigation detected from marker:', navigationUrl);
      }

      // If user says hi cubie, use preferred name
      if (/^hi\s*cubie/i.test(question) && cubiePrefs.name) {
        addMessage(`Hi ${cubiePrefs.name}!`, 'bot', false);
      } else {
        addMessage(finalReply, 'bot', true);
      }

      // Show navigation toast and then redirect
      if (navigationUrl) {
        console.log('Navigating to:', navigationUrl);

        // Create toast notification
        const toast = document.createElement('div');
        toast.className = 'nav-toast';
        toast.innerHTML = `
          <div class="nav-toast-content">
            <span class="nav-icon">🧭</span>
            <div class="nav-text">
              <strong>Navigating to page...</strong>
              <span class="nav-url">${navigationUrl}</span>
            </div>
          </div>
        `;
        document.body.appendChild(toast);

        // style the toast dynamically
        Object.assign(toast.style, {
          position: 'fixed',
          top: '20px',
          right: '20px',
          background: '#fff',
          padding: '12px 20px',
          borderRadius: '8px',
          boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
          borderLeft: '4px solid #004aad',
          zIndex: '10000',
          animation: 'slideIn 0.3s ease-out'
        });

        // Open in NEW tab logic with popup blocker handling
        setTimeout(() => {
          // Attempt to open in new tab
          const win = window.open(navigationUrl, '_blank');

          // Check if blocked
          if (!win || win.closed || typeof win.closed == 'undefined') {
            // Popup blocked
            console.warn('Popup blocked for navigationUrl:', navigationUrl);
            const navText = toast.querySelector('.nav-text');
            if (navText) {
              navText.innerHTML = `<strong>Popup blocked!</strong><br><a href="${navigationUrl}" target="_blank" style="color:#004aad;text-decoration:underline;font-weight:bold;cursor:pointer;">Click here to open page</a>`;
              // Keep toast visible so user can click
            }
          } else {
            // Success
            toast.remove();
          }
        }, 800);
      }
    } else {
      console.log('No reply in response data:', data); // Debug log
      addMessage("I'm not sure how to help with that. Try rephrasing your question.", 'bot');
    }
  } catch (err) {
    console.error("Backend error:", err);
    console.error("Error details:", err.message); // Debug log

    // Check if session expired (401 error)
    if (err.message.includes('401')) {
      alert('Your session has expired. Please log in again.');
      window.location.href = '/';
      return;
    }

    addMessage("Oops! Something went wrong. Please try again later.", 'bot');
  } finally {
    typingIndicator.style.display = 'none';
    isSubmitting = false;
    userInput.disabled = false;
    // Keep focus on input for next query
    setTimeout(() => userInput.focus(), 50);
  }
});

userInput.addEventListener('keydown', function (e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    form.dispatchEvent(new Event('submit'));
  }
});

toggleDark.addEventListener('click', () => {
  root.classList.toggle('dark-mode');
  const isDark = root.classList.contains('dark-mode');
  toggleDark.textContent = isDark ? '☀️' : '🌙';
  localStorage.setItem('cubie-theme', isDark ? 'dark' : 'light');
});

// === Voice to Text Manual Toggle ===
if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SpeechRecognition();
  recognition.lang = 'en-US';
  recognition.continuous = false;
  recognition.interimResults = false;

  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    userInput.value = transcript;
    micButton.style.background = 'transparent';
    micButton.style.color = '#666';
    isRecording = false;
    // Remove recording indicator
    const recordingMsg = document.getElementById('recording-message');
    if (recordingMsg) recordingMsg.remove();
  };

  recognition.onerror = (event) => {
    console.error('Speech recognition error:', event.error);
    micButton.style.background = 'transparent';
    micButton.style.color = '#666';
    isRecording = false;
    // Remove recording indicator
    const recordingMsg = document.getElementById('recording-message');
    if (recordingMsg) recordingMsg.remove();
  };

  recognition.onend = () => {
    micButton.style.background = 'transparent';
    micButton.style.color = '#666';
    isRecording = false;
    // Remove recording indicator
    const recordingMsg = document.getElementById('recording-message');
    if (recordingMsg) recordingMsg.remove();
  };

  micButton.addEventListener('click', () => {
    if (!isRecording) {
      recognition.start();
      micButton.style.background = '#004aad';
      micButton.style.color = '#fff';
      isRecording = true;

      // Add recording indicator message
      const recordingMsg = document.createElement('div');
      recordingMsg.id = 'recording-message';
      recordingMsg.className = 'message bot recording-indicator';
      recordingMsg.innerHTML = `
        <div class="message-content">
          🎤 <span class="recording-text">Listening... Speak now</span>
          <div class="recording-dots">
            <span></span><span></span><span></span>
          </div>
        </div>
      `;
      chatBox.appendChild(recordingMsg);
      scrollToBottom();
    } else {
      recognition.stop();
      micButton.style.background = 'transparent';
      micButton.style.color = '#666';
      isRecording = false;
      // Remove recording indicator
      const recordingMsg = document.getElementById('recording-message');
      if (recordingMsg) recordingMsg.remove();
    }
  });
} else {
  console.warn("Speech recognition not supported in this browser.");
  micButton.style.display = 'none';
}

// Add click handler for when microphone is blocked
micButton.addEventListener('click', () => {
  if (!('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
    alert('Voice input is not supported in this browser. Please use Chrome or Edge.');
    return;
  }

  if (!recognition) {
    alert('Microphone access is blocked. Please allow microphone access in your browser settings and refresh the page.');
    return;
  }
});

// === Notes System ===
function getSavedNotes() {
  try {
    return JSON.parse(localStorage.getItem('cubieNotes')) || [];
  } catch (e) {
    return [];
  }
}

function saveNotes(notes) {
  localStorage.setItem('cubieNotes', JSON.stringify(notes));
}

function addNote(content) {
  const notes = getSavedNotes();
  const newNote = {
    id: Date.now(),
    content: content,
    date: new Date().toLocaleString()
  };
  notes.unshift(newNote);
  saveNotes(notes);
  updateNotesDisplay();
}

function deleteNote(noteId) {
  const notes = getSavedNotes();
  const filteredNotes = notes.filter(note => note.id !== noteId);
  saveNotes(filteredNotes);
  updateNotesDisplay();
}

function updateNotesDisplay() {
  const notes = getSavedNotes();

  if (notes.length === 0) {
    notesList.style.display = 'none';
    notesEmpty.style.display = 'block';
    return;
  }

  notesList.style.display = 'block';
  notesEmpty.style.display = 'none';

  notesList.innerHTML = notes.map(note => `
    <div class="note-item">
      <div class="note-content">${note.content}</div>
      <div class="note-date">Saved: ${note.date}</div>
      <div class="note-actions">
        <button class="note-copy-btn" onclick="copyNoteToClipboard('${note.content.replace(/'/g, "\\'")}')">Copy</button>
        <button class="note-delete-btn" onclick="deleteNote(${note.id})">Delete</button>
      </div>
    </div>
  `).join('');
}

function copyNoteToClipboard(content) {
  navigator.clipboard.writeText(content).then(() => {
    // Show brief success feedback
    const btn = event.target;
    const originalText = btn.textContent;
    btn.textContent = 'Copied!';
    btn.style.background = '#28a745';
    setTimeout(() => {
      btn.textContent = originalText;
      btn.style.background = '#004aad';
    }, 1000);
  });
}

// Notes modal functionality
notesBtn.addEventListener('click', () => {
  updateNotesDisplay();
  notesModal.style.display = 'flex';
});

closeNotesBtn.addEventListener('click', () => {
  notesModal.style.display = 'none';
});


// Close modal when clicking outside
// Remove backdrop click functionality since there's no backdrop

// Interactive Data Analysis Interface
function showDataAnalysisInterface() {
  const analysisInterface = document.createElement('div');
  analysisInterface.className = 'analysis-interface';
  analysisInterface.innerHTML = `
    <div class="analysis-header">
      <h3>📊 Data Analysis</h3>
      <p>Choose a data category to explore:</p>
    </div>
    <div class="analysis-categories">
      <div class="category-card" data-category="shipments">
        <div class="category-icon">🚚</div>
        <h4>Shipments</h4>
        <p>Track delivery performance, routes, and carrier data</p>
        <div class="quick-queries">
          <button class="query-btn" data-query="shipment-performance">Performance Metrics</button>
          <button class="query-btn" data-query="carrier-analysis">Carrier Analysis</button>
          <button class="query-btn" data-query="route-optimization">Route Data</button>
        </div>
      </div>
      <div class="category-card" data-category="disputes">
        <div class="category-icon">⚖️</div>
        <h4>Disputes</h4>
        <p>Analyze dispute patterns, resolution times, and costs</p>
        <div class="quick-queries">
          <button class="query-btn" data-query="dispute-trends">Dispute Trends</button>
          <button class="query-btn" data-query="resolution-times">Resolution Times</button>
          <button class="query-btn" data-query="dispute-costs">Cost Analysis</button>
        </div>
      </div>
      <div class="category-card" data-category="invoices">
        <div class="category-icon">💰</div>
        <h4>Invoices</h4>
        <p>Review billing data, payment status, and financial metrics</p>
        <div class="quick-queries">
          <button class="query-btn" data-query="payment-status">Payment Status</button>
          <button class="query-btn" data-query="revenue-analysis">Revenue Analysis</button>
          <button class="query-btn" data-query="billing-trends">Billing Trends</button>
        </div>
      </div>
    </div>
    <div class="custom-query-section">
      <h4>Custom Query</h4>
      <textarea placeholder="Ask me anything about your data... (e.g., 'Show me average delivery times by carrier for the last 3 months')" class="custom-query-input"></textarea>
      <button class="analyze-btn">Analyze Data</button>
    </div>
  `;

  addMessage('', 'bot', false, analysisInterface);

  // Add event listeners for the interface
  analysisInterface.addEventListener('click', function (e) {
    if (e.target.classList.contains('query-btn')) {
      const query = e.target.dataset.query;
      const category = e.target.closest('.category-card').dataset.category;
      executeQuickQuery(query, category);
    }
  });

  const analyzeBtn = analysisInterface.querySelector('.analyze-btn');
  const customInput = analysisInterface.querySelector('.custom-query-input');

  analyzeBtn.addEventListener('click', function () {
    const customQuery = customInput.value.trim();
    if (customQuery) {
      userInput.value = customQuery;
      form.dispatchEvent(new Event('submit'));
    }
  });
}

// Interactive Data Visualization Interface
function showDataVisualizationInterface() {
  const visualizationInterface = document.createElement('div');
  visualizationInterface.className = 'visualization-interface';
  visualizationInterface.innerHTML = `
    <div class="viz-header">
      <h6>📈 Data Visualization</h6>
      <p>Create custom charts and graphs from your data:</p>
    </div>
    <div class="chart-builder">
      <div class="chart-type-selector">
        <h4>Chart Type</h4>
        <div class="chart-types">
          <button class="chart-type-btn active" data-type="line">📈 Line Chart</button>
          <button class="chart-type-btn" data-type="bar">📊 Bar Chart</button>
          <button class="chart-type-btn" data-type="stacked">📊 Stacked Bar</button>
          <button class="chart-type-btn" data-type="heatmap">🔥 Heatmap</button>
        </div>
      </div>
      <div class="data-source-selector">
        <h4>Data Source</h4>
        <select class="data-source-select">
          <option value="shipments">Shipments</option>
          <option value="disputes">Disputes</option>
          <option value="invoices">Invoices</option>
        </select>
      </div>
      <div class="quick-visualizations">
        <h4>Quick Visualizations</h4>
        <div class="quick-viz-buttons">
          <button class="quick-viz-btn" data-viz="delivery-trends">Delivery Performance Trends</button>
          <button class="quick-viz-btn" data-viz="carrier-comparison">Carrier Comparison</button>
          <button class="quick-viz-btn" data-viz="dispute-heatmap">Dispute Patterns</button>
          <button class="quick-viz-btn" data-viz="revenue-chart">Revenue Analysis</button>
        </div>
      </div>
      <div class="custom-viz-section">
        <h4>Custom Visualization</h4>
        <textarea placeholder="Describe what you want to visualize... (e.g., 'Show me a line chart of monthly shipment volumes by carrier')" class="custom-viz-input"></textarea>
        <button class="visualize-btn">Create Chart</button>
      </div>
    </div>
  `;

  addMessage('', 'bot', false, visualizationInterface);

  // Add event listeners for the interface
  visualizationInterface.addEventListener('click', function (e) {
    if (e.target.classList.contains('chart-type-btn')) {
      // Remove active class from all buttons
      visualizationInterface.querySelectorAll('.chart-type-btn').forEach(btn => btn.classList.remove('active'));
      // Add active class to clicked button
      e.target.classList.add('active');
    }

    if (e.target.classList.contains('quick-viz-btn')) {
      const vizType = e.target.dataset.viz;
      executeQuickVisualization(vizType);
    }
  });

  const visualizeBtn = visualizationInterface.querySelector('.visualize-btn');
  const customVizInput = visualizationInterface.querySelector('.custom-viz-input');
  const chartTypeSelect = visualizationInterface.querySelector('.chart-type-btn.active');
  const dataSourceSelect = visualizationInterface.querySelector('.data-source-select');

  visualizeBtn.addEventListener('click', function () {
    const customViz = customVizInput.value.trim();
    const chartType = chartTypeSelect.dataset.type;
    const dataSource = dataSourceSelect.value;

    if (customViz) {
      const fullQuery = `Create a ${chartType} chart showing: ${customViz}`;
      userInput.value = fullQuery;
      form.dispatchEvent(new Event('submit'));
    }
  });
}

// Execute quick queries
function executeQuickQuery(queryType, category) {
  const queries = {
    'shipment-performance': 'Show me shipment performance metrics including on-time delivery rates, average transit times, and delivery success rates',
    'carrier-analysis': 'Analyze carrier performance including cost per shipment, delivery times, and reliability metrics',
    'route-optimization': 'Show me route data and optimization opportunities including distance analysis and delivery patterns',
    'dispute-trends': 'Show me dispute trends over time including dispute types, frequency, and resolution patterns',
    'resolution-times': 'Analyze dispute resolution times by category and identify bottlenecks in the resolution process',
    'dispute-costs': 'Show me dispute cost analysis including average dispute amounts and financial impact',
    'payment-status': 'Show me invoice payment status analysis including overdue payments and payment trends',
    'revenue-analysis': 'Analyze revenue data including monthly trends, customer revenue, and revenue by service type',
    'billing-trends': 'Show me billing trends and patterns including invoice volumes and billing cycle analysis'
  };

  const query = queries[queryType];
  if (query) {
    userInput.value = query;
    form.dispatchEvent(new Event('submit'));
  }
}

// Execute quick visualizations
function executeQuickVisualization(vizType) {
  const visualizations = {
    'delivery-trends': 'Create a line chart showing delivery performance trends over the last 6 months',
    'carrier-comparison': 'Create a bar chart comparing carrier performance metrics',
    'dispute-heatmap': 'Create a heatmap showing dispute patterns by region and time',
    'revenue-chart': 'Create a stacked bar chart showing monthly revenue breakdown by service type'
  };

  const vizQuery = visualizations[vizType];
  if (vizQuery) {
    userInput.value = vizQuery;
    form.dispatchEvent(new Event('submit'));
  }
}
// === Chart Modal Logic ===
function showChartModal(url) {
  const modal = document.createElement('div');
  modal.className = 'chart-modal-overlay';
  modal.innerHTML = `
    <div class="chart-modal-content">
      <div class="chart-modal-header">
        <span class="chart-modal-title">Data Visualization</span>
        <button class="chart-modal-close">&times;</button>
      </div>
      <div class="chart-modal-body">
        <iframe src="${url}" class="chart-modal-iframe" title="Chart Visualization"></iframe>
      </div>
    </div>
  `;
  document.body.appendChild(modal);

  const closeBtn = modal.querySelector('.chart-modal-close');
  const close = () => {
    modal.style.opacity = '0';
    setTimeout(() => modal.remove(), 300);
  };

  closeBtn.onclick = close;
  modal.onclick = (e) => {
    if (e.target === modal) close();
  };
}

// Intercept clicks on links that look like charts or "View Full Screen"
window.addEventListener('DOMContentLoaded', () => {
  const chatBox = document.getElementById('chat-box');
  if (chatBox) {
    console.log('Attaching chart link interceptor to chatBox');
    chatBox.addEventListener('click', function (e) {
      const link = e.target.closest('a');
      if (!link) return;

      const href = link.getAttribute('href');
      if (!href) return;

      if (href.match(/\.html$/i) || href.includes('/static/demo/')) {
        console.log('Intercepted chart link:', href);
        e.preventDefault();
        e.stopPropagation();
        showChartModal(href);
      }
    });
  } else {
    console.warn('chatBox not found for chart interceptor');
  }
});
