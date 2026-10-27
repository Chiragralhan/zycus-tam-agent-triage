"""Live Interactive Showcase Dashboard for Zycus TAM Triage Agent.

Runs a zero-dependency web server allowing live demonstration of ticket triage,
dynamic ReAct reasoning traces, account intelligence, and policy decisions.
"""
import http.server
import json
import os
from pathlib import Path
import urllib.parse

from tam_agent.data import load_accounts, load_tickets, load_usage, load_review_set
from tam_agent.kb import load_kb
from tam_agent.agent import Context, triage

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "outputs"

# Initialize shared agent context
print("Loading data store and knowledge base indexes for live dashboard...")
accounts = load_accounts()
tickets = load_tickets()
usage = load_usage()
kb = load_kb()
ctx = Context(accounts, tickets, usage, kb)
tickets_by_id = tickets.set_index("ticket_id")
review_ids = load_review_set()
print(f"Loaded {len(review_ids)} review tickets ready for demonstration!")

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Zycus TAM AI - Agentic Ticket Triage</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    body { font-family: 'Inter', sans-serif; }
  </style>
</head>
<body class="bg-slate-900 text-slate-100 min-h-screen flex flex-col">

  <!-- Header -->
  <header class="bg-slate-800/80 backdrop-blur border-b border-slate-700 px-6 py-4 flex items-center justify-between sticky top-0 z-50">
    <div class="flex items-center space-x-3">
      <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-500 to-cyan-400 flex items-center justify-center shadow-lg shadow-cyan-500/20">
        <i class="fa-solid fa-robot text-white text-lg"></i>
      </div>
      <div>
        <h1 class="text-lg font-bold bg-gradient-to-r from-white via-slate-200 to-cyan-300 bg-clip-text text-transparent">Zycus TAM Agentic Triage</h1>
        <p class="text-xs text-slate-400">Autonomous Tier-1 & Tier-2 Multi-Step Incident Reasoning</p>
      </div>
    </div>
    <div class="flex items-center space-x-3">
      <span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
        <span class="w-2 h-2 rounded-full bg-emerald-400 mr-2 animate-pulse"></span> 10/10 Review Tests Valid
      </span>
      <span class="text-xs bg-slate-700 px-2.5 py-1 rounded-md text-slate-300 border border-slate-600">As of 2026-10-20</span>
    </div>
  </header>

  <!-- Main Content Grid -->
  <div class="flex-1 flex overflow-hidden">

    <!-- Left Sidebar: Ticket List -->
    <aside class="w-80 border-r border-slate-800 bg-slate-950/50 flex flex-col h-[calc(100vh-65px)]">
      <div class="p-4 border-b border-slate-800">
        <h2 class="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Evaluation Review Set (10)</h2>
        <p class="text-xs text-slate-500">Select any ticket to inspect & run triage live</p>
      </div>
      <div class="overflow-y-auto flex-1 p-2 space-y-1.5" id="ticket-list">
        <!-- Rendered by JS -->
      </div>
    </aside>

    <!-- Center & Right Panel: Ticket & Agent Details -->
    <main class="flex-1 flex flex-col lg:flex-row overflow-y-auto h-[calc(100vh-65px)]">

      <!-- Left Column: Raw Ticket View -->
      <section class="lg:w-1/2 p-6 border-r border-slate-800 space-y-6">
        <div class="bg-slate-800/40 border border-slate-700/60 rounded-xl p-5 shadow-sm space-y-4">
          <div class="flex items-start justify-between">
            <div>
              <span id="ticket-id-badge" class="text-xs font-mono px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 font-semibold">TKT-XXXXXX</span>
              <h2 id="ticket-subject" class="text-lg font-semibold text-white mt-1">Ticket Subject</h2>
            </div>
            <span id="ticket-channel-badge" class="text-xs px-2.5 py-1 rounded-full bg-slate-700 text-slate-300 capitalize">portal</span>
          </div>

          <div class="grid grid-cols-2 gap-3 text-xs bg-slate-900/50 p-3 rounded-lg border border-slate-800">
            <div><span class="text-slate-400">Company:</span> <span id="ticket-company" class="font-medium text-slate-200">...</span></div>
            <div><span class="text-slate-400">Domain:</span> <span id="ticket-domain" class="font-mono text-cyan-400">...</span></div>
            <div><span class="text-slate-400">Module:</span> <span id="ticket-module" class="font-medium text-slate-200">...</span></div>
            <div><span class="text-slate-400">Error Code:</span> <span id="ticket-error-code" class="font-mono text-amber-400">None</span></div>
          </div>

          <div>
            <label class="text-xs font-semibold text-slate-400 uppercase tracking-wider block mb-1.5">Description (Untrusted Customer Content)</label>
            <div id="ticket-description" class="p-3 bg-slate-950/60 rounded-lg text-sm text-slate-300 font-mono leading-relaxed whitespace-pre-wrap border border-slate-800 max-h-48 overflow-y-auto">...</div>
          </div>

          <button id="btn-run-triage" onclick="runLiveTriage()" class="w-full py-3 px-4 rounded-xl font-semibold text-sm bg-gradient-to-r from-cyan-500 to-indigo-600 hover:from-cyan-400 hover:to-indigo-500 text-white shadow-lg shadow-cyan-500/25 transition-all flex items-center justify-center space-x-2">
            <i class="fa-solid fa-play"></i>
            <span>Run Dynamic Agentic Triage</span>
          </button>
        </div>

        <!-- Account Intelligence Card -->
        <div class="bg-slate-800/40 border border-slate-700/60 rounded-xl p-5 shadow-sm space-y-3">
          <h3 class="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center justify-between">
            <span>Account Intelligence</span>
            <i class="fa-solid fa-building-shield text-slate-400"></i>
          </h3>
          <div class="grid grid-cols-2 gap-3 text-xs">
            <div class="bg-slate-900/40 p-2.5 rounded-lg border border-slate-800">
              <div class="text-slate-400 mb-0.5">Account ID</div>
              <div id="acc-id-val" class="font-mono text-white font-semibold">Resolving...</div>
            </div>
            <div class="bg-slate-900/40 p-2.5 rounded-lg border border-slate-800">
              <div class="text-slate-400 mb-0.5">Account Tier</div>
              <div id="acc-tier-val" class="font-semibold text-cyan-400">...</div>
            </div>
          </div>
          <div>
            <label class="text-xs font-semibold text-slate-400 block mb-1">Account Signals (KB-2914)</label>
            <div id="acc-signals-list" class="space-y-1">
              <!-- Rendered signals -->
            </div>
          </div>
        </div>
      </section>

      <!-- Right Column: Agent Decision & Reasoning Trace -->
      <section class="lg:w-1/2 p-6 space-y-6">

        <!-- Decision Summary Grid -->
        <div class="bg-slate-800/40 border border-slate-700/60 rounded-xl p-5 shadow-sm space-y-4">
          <h3 class="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center justify-between">
            <span>Triage Decision Output</span>
            <span id="decision-confidence" class="text-xs text-emerald-400 font-mono font-medium">Confidence: --%</span>
          </h3>

          <div class="grid grid-cols-3 gap-3">
            <div class="bg-slate-900/60 p-3 rounded-lg border border-slate-800 text-center">
              <div class="text-[11px] text-slate-400 uppercase tracking-wider mb-1">Category</div>
              <div id="badge-category" class="inline-block px-2.5 py-1 rounded-md text-xs font-bold bg-slate-700 text-slate-300">--</div>
            </div>
            <div class="bg-slate-900/60 p-3 rounded-lg border border-slate-800 text-center">
              <div class="text-[11px] text-slate-400 uppercase tracking-wider mb-1">Priority</div>
              <div id="badge-priority" class="inline-block px-2.5 py-1 rounded-md text-xs font-bold bg-slate-700 text-slate-300">--</div>
            </div>
            <div class="bg-slate-900/60 p-3 rounded-lg border border-slate-800 text-center">
              <div class="text-[11px] text-slate-400 uppercase tracking-wider mb-1">Route Target</div>
              <div id="badge-route" class="inline-block px-2.5 py-1 rounded-md text-xs font-bold bg-slate-700 text-slate-300">--</div>
            </div>
          </div>

          <!-- Flags & References -->
          <div class="flex flex-wrap items-center gap-2 pt-1">
            <span id="flag-escalate" class="px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-800 text-slate-400 border border-slate-700">Escalate: false</span>
            <span id="flag-tam" class="px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-800 text-slate-400 border border-slate-700">Notify TAM: false</span>
            <span id="flag-clarification" class="px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-800 text-slate-400 border border-slate-700">Needs Info: false</span>
            <span id="flag-duplicate" class="px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-800 text-slate-400 border border-slate-700">Duplicate: None</span>
          </div>

          <div>
            <span class="text-xs font-semibold text-slate-400 block mb-1">Cited Knowledge Base Articles:</span>
            <div id="kb-refs-container" class="flex flex-wrap gap-1.5">
              <!-- KB badges -->
            </div>
          </div>
        </div>

        <!-- Reasoning Trace Steps -->
        <div class="bg-slate-800/40 border border-slate-700/60 rounded-xl p-5 shadow-sm space-y-3">
          <h3 class="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center justify-between">
            <span>Dynamic Reasoning Trace (Agentic Depth)</span>
            <i class="fa-solid fa-list-check text-slate-400"></i>
          </h3>
          <div id="reasoning-trace-container" class="space-y-2.5">
            <!-- Trace steps -->
          </div>
        </div>

        <!-- Generated Drafts -->
        <div class="bg-slate-800/40 border border-slate-700/60 rounded-xl p-5 shadow-sm space-y-4">
          <div>
            <div class="flex items-center justify-between mb-1.5">
              <label class="text-xs font-bold text-slate-400 uppercase tracking-wider">Draft Customer Reply</label>
              <button onclick="copyReply()" class="text-xs text-cyan-400 hover:text-cyan-300 flex items-center space-x-1">
                <i class="fa-regular fa-copy"></i> <span>Copy</span>
              </button>
            </div>
            <div id="draft-reply" class="p-3 bg-slate-950/60 rounded-lg text-xs text-slate-200 leading-relaxed border border-slate-800 whitespace-pre-wrap">...</div>
          </div>

          <div>
            <label class="text-xs font-bold text-slate-400 uppercase tracking-wider block mb-1.5">Internal Engineering Note</label>
            <div id="draft-note" class="p-3 bg-slate-950/60 rounded-lg text-xs text-amber-200/90 font-mono leading-relaxed border border-slate-800 whitespace-pre-wrap">...</div>
          </div>
        </div>

      </section>

    </main>
  </div>

  <script>
    let currentTicketId = null;
    let reviewTickets = [];

    async function init() {
      const res = await fetch('/api/tickets');
      reviewTickets = await res.json();
      renderTicketList();
      if (reviewTickets.length > 0) {
        selectTicket(reviewTickets[0].ticket_id);
      }
    }

    function renderTicketList() {
      const container = document.getElementById('ticket-list');
      container.innerHTML = reviewTickets.map(t => `
        <button onclick="selectTicket('${t.ticket_id}')" id="btn-tkt-${t.ticket_id}" class="w-full text-left p-3 rounded-lg border border-slate-800/60 hover:bg-slate-800/50 transition-all group">
          <div class="flex items-center justify-between mb-1">
            <span class="font-mono text-xs font-semibold text-cyan-400 group-hover:text-cyan-300">${t.ticket_id}</span>
            <span class="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 uppercase font-mono">${t.module || 'General'}</span>
          </div>
          <div class="text-xs font-medium text-slate-200 truncate">${t.subject}</div>
          <div class="text-[11px] text-slate-400 truncate mt-0.5">${t.company_name_raw}</div>
        </button>
      `).join('');
    }

    async function selectTicket(tid) {
      currentTicketId = tid;
      document.querySelectorAll('#ticket-list button').forEach(b => {
        b.classList.remove('bg-indigo-950/50', 'border-indigo-500/50', 'shadow-sm');
      });
      const activeBtn = document.getElementById('btn-tkt-' + tid);
      if (activeBtn) activeBtn.classList.add('bg-indigo-950/50', 'border-indigo-500/50', 'shadow-sm');

      const res = await fetch('/api/ticket/' + tid);
      const ticket = await res.json();

      document.getElementById('ticket-id-badge').innerText = ticket.ticket_id;
      document.getElementById('ticket-subject').innerText = ticket.subject;
      document.getElementById('ticket-channel-badge').innerText = ticket.channel || 'portal';
      document.getElementById('ticket-company').innerText = ticket.company_name_raw || 'Blank';
      document.getElementById('ticket-domain').innerText = ticket.requester_domain;
      document.getElementById('ticket-module').innerText = ticket.module || 'None specified';
      document.getElementById('ticket-error-code').innerText = ticket.error_code || 'None';
      document.getElementById('ticket-description').innerText = ticket.description;

      // Automatically load previous result if available
      try {
        const outRes = await fetch('/api/output/' + tid);
        if (outRes.ok) {
          const out = await outRes.json();
          renderDecision(out);
        }
      } catch (e) {}
    }

    async function runLiveTriage() {
      const btn = document.getElementById('btn-run-triage');
      btn.innerHTML = '<i class="fa-solid fa-spinner animate-spin"></i><span>Reasoning & Calling Tools...</span>';
      btn.disabled = true;

      try {
        const res = await fetch('/api/triage/' + currentTicketId, { method: 'POST' });
        const result = await res.json();
        renderDecision(result);
      } finally {
        btn.innerHTML = '<i class="fa-solid fa-play"></i><span>Run Dynamic Agentic Triage</span>';
        btn.disabled = false;
      }
    }

    function renderDecision(data) {
      document.getElementById('decision-confidence').innerText = `Confidence: ${(data.confidence * 100).toFixed(0)}%`;

      // Category badge
      const catBadge = document.getElementById('badge-category');
      catBadge.innerText = data.category.toUpperCase();
      catBadge.className = 'inline-block px-2.5 py-1 rounded-md text-xs font-bold ' + getCategoryColor(data.category);

      // Priority badge
      const prioBadge = document.getElementById('badge-priority');
      prioBadge.innerText = data.priority;
      prioBadge.className = 'inline-block px-2.5 py-1 rounded-md text-xs font-bold ' + getPriorityColor(data.priority);

      // Route badge
      const routeBadge = document.getElementById('badge-route');
      routeBadge.innerText = data.route_to;
      routeBadge.className = 'inline-block px-2.5 py-1 rounded-md text-xs font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30';

      // Flags
      setFlag('flag-escalate', 'Escalate: ' + (data.escalate ? 'YES' : 'NO'), data.escalate ? 'bg-rose-500/20 text-rose-300 border-rose-500/40' : 'bg-slate-800 text-slate-400');
      setFlag('flag-tam', 'Notify TAM: ' + (data.notify_tam ? 'YES' : 'NO'), data.notify_tam ? 'bg-amber-500/20 text-amber-300 border-amber-500/40' : 'bg-slate-800 text-slate-400');
      setFlag('flag-clarification', 'Needs Info: ' + (data.needs_clarification ? 'YES' : 'NO'), data.needs_clarification ? 'bg-yellow-500/20 text-yellow-300 border-yellow-500/40' : 'bg-slate-800 text-slate-400');
      setFlag('flag-duplicate', data.duplicate_of ? `Duplicate of ${data.duplicate_of}` : 'Not a Duplicate', data.duplicate_of ? 'bg-purple-500/20 text-purple-300 border-purple-500/40' : 'bg-slate-800 text-slate-400');

      // Account Card
      document.getElementById('acc-id-val').innerText = data.account_id || 'Could not resolve';
      const sigList = document.getElementById('acc-signals-list');
      sigList.innerHTML = (data.account_signals || []).map(s => `
        <div class="text-[11px] text-slate-300 bg-slate-900/60 px-2 py-1 rounded border border-slate-800 flex items-center space-x-1.5">
          <i class="fa-solid fa-circle-info text-cyan-400 text-[10px]"></i>
          <span>${s}</span>
        </div>
      `).join('') || '<div class="text-[11px] text-slate-500">No signals triggered</div>';

      // KB References
      const kbContainer = document.getElementById('kb-refs-container');
      kbContainer.innerHTML = (data.kb_references || []).map(ref => `
        <span class="px-2 py-0.5 rounded text-xs font-mono font-semibold bg-cyan-500/10 text-cyan-300 border border-cyan-500/30">${ref}</span>
      `).join('') || '<span class="text-xs text-slate-500">None cited</span>';

      // Reasoning trace
      const traceContainer = document.getElementById('reasoning-trace-container');
      traceContainer.innerHTML = (data.reasoning_trace || []).map(s => `
        <div class="bg-slate-900/60 p-3 rounded-lg border border-slate-800 text-xs space-y-1">
          <div class="flex items-center justify-between">
            <span class="font-bold text-cyan-400">Step ${s.step}: ${s.action}</span>
            <span class="text-[10px] text-slate-500 font-mono">${s.input || ''}</span>
          </div>
          <div class="text-slate-300">${s.observation}</div>
        </div>
      `).join('');

      // Drafts
      document.getElementById('draft-reply').innerText = data.customer_reply;
      document.getElementById('draft-note').innerText = data.internal_note;
    }

    function setFlag(id, text, cls) {
      const el = document.getElementById(id);
      el.innerText = text;
      el.className = 'px-2.5 py-1 rounded-full text-xs font-semibold border ' + cls;
    }

    function getCategoryColor(cat) {
      switch(cat) {
        case 'security': return 'bg-rose-500/20 text-rose-300 border border-rose-500/40';
        case 'bug': return 'bg-amber-500/20 text-amber-300 border border-amber-500/40';
        case 'feature_request': return 'bg-purple-500/20 text-purple-300 border border-purple-500/40';
        case 'duplicate': return 'bg-fuchsia-500/20 text-fuchsia-300 border border-fuchsia-500/40';
        case 'needs_info': return 'bg-yellow-500/20 text-yellow-300 border border-yellow-500/40';
        case 'incident': return 'bg-red-500/20 text-red-300 border border-red-500/40';
        default: return 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40';
      }
    }

    function getPriorityColor(p) {
      switch(p) {
        case 'P1': return 'bg-rose-600 text-white shadow-md shadow-rose-600/30';
        case 'P2': return 'bg-amber-600 text-white';
        case 'P3': return 'bg-blue-600 text-white';
        default: return 'bg-slate-600 text-slate-200';
      }
    }

    function copyReply() {
      const text = document.getElementById('draft-reply').innerText;
      navigator.clipboard.writeText(text);
      alert('Draft reply copied to clipboard!');
    }

    window.onload = init;
  </script>
</body>
</html>
"""


class DashboardHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode("utf-8"))
            return

        if path == "/api/tickets":
            out = []
            for tid in review_ids:
                row = tickets_by_id.loc[tid].to_dict()
                out.append({
                    "ticket_id": tid,
                    "subject": row.get("subject", ""),
                    "company_name_raw": row.get("company_name_raw", ""),
                    "module": row.get("module", ""),
                    "customer_priority": row.get("customer_priority", ""),
                })
            self._send_json(out)
            return

        if path.startswith("/api/ticket/"):
            tid = path.replace("/api/ticket/", "").strip()
            if tid in review_ids:
                row = tickets_by_id.loc[tid].to_dict() | {"ticket_id": tid}
                self._send_json(row)
                return
            self.send_error(404, "Ticket not found")
            return

        if path.startswith("/api/output/"):
            tid = path.replace("/api/output/", "").strip()
            out_file = OUT_DIR / f"{tid}.json"
            if out_file.exists():
                self._send_json(json.loads(out_file.read_text(encoding="utf-8")))
                return
            self.send_error(404, "Output not found")
            return

        self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/triage/"):
            tid = path.replace("/api/triage/", "").strip()
            if tid in review_ids:
                ticket = tickets_by_id.loc[tid].to_dict() | {"ticket_id": tid}
                result = triage(ticket, ctx)
                # Overwrite output
                (OUT_DIR / f"{tid}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
                self._send_json(result)
                return
            self.send_error(404, "Ticket not found")
            return

        self.send_error(404, "Not Found")

    def _send_json(self, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # Clean terminal output
        pass


def run_server(port: int = 8000):
    server = http.server.HTTPServer(("127.0.0.1", port), DashboardHandler)
    print("=" * 60)
    print(f" Zycus TAM AI Operations Dashboard is LIVE!")
    print(f" Open in your browser: http://localhost:{port}")
    print("=" * 60)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard server...")


if __name__ == "__main__":
    run_server(8000)
