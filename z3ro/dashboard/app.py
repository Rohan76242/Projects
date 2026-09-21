"""Z3RO — Standalone Local Economic Dashboard & REST API.

Implements Section 5 & Section 13:
- Provides JSON API and local web dashboard.
- Displays: wallet balance, verified revenue, costs, net profit, burn rate,
  remaining operational time, current strategy, pending approvals,
  compliance rejections panel, strategy performance, and kill switch.
"""

import json
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any
from urllib.parse import urlparse, parse_qs

from z3ro.economy.wallet import wallet
from z3ro.economy.ledger import ledger
from z3ro.economy.survival import survival_engine
from z3ro.economy.limits import limits_manager
from z3ro.compliance.legal_filter import legal_filter
from z3ro.memory.strategies import strategy_memory
from z3ro.tools.communication import approval_queue
from z3ro.autonomy.exploration import loop_coordinator


def get_full_dashboard_state() -> Dict[str, Any]:
    """Compile complete real-time economic telemetry for dashboard consumers."""
    wallet_state = wallet.get_wallet_state()
    survival_state = survival_engine.get_telemetry()
    rate_stats = limits_manager.rate_limiter.get_stats()
    rejections = legal_filter.get_recent_rejections(limit=15)
    approvals = approval_queue.get_pending()
    strategies = strategy_memory.get_all_strategies(limit=20)
    recent_ledger = ledger.get_recent_entries(limit=15)

    last_cycle = loop_coordinator.last_cycle_telemetry

    return {
        "timestamp": time.time(),
        "wallet": {
            "balance": wallet_state["current_balance"],
            "initial_capital": wallet_state["initial_capital"],
            "verified_revenue": wallet_state["verified_revenue"],
            "total_costs": wallet_state["total_costs"],
            "net_profit": wallet_state["net_profit"],
        },
        "survival": {
            "burn_rate_daily": survival_state["daily_burn_rate"],
            "burn_rate_hourly": survival_state["hourly_burn_rate"],
            "remaining_hours": survival_state["remaining_hours"],
            "remaining_days": survival_state["remaining_days"],
            "status": survival_state["status"],
            "is_terminated": survival_state["is_terminated"],
        },
        "limits": {
            "kill_switch_active": limits_manager.is_kill_switch_active(),
            "daily_spend_cap": limits_manager.config.daily_spend_cap,
            "single_tx_cap": limits_manager.config.single_transaction_cap,
            "actions_last_hour": rate_stats["actions_last_hour"],
            "hourly_cap": rate_stats["hourly_cap"],
            "actions_last_24h": rate_stats["actions_last_24h"],
            "daily_cap": rate_stats["daily_cap"],
        },
        "current_strategy": last_cycle.get("strategy") if last_cycle else None,
        "current_experiment": last_cycle.get("experiment") if last_cycle else None,
        "last_cycle_outcome": last_cycle.get("outcome") if last_cycle else None,
        "pending_approvals": approvals,
        "compliance_rejections": rejections,
        "strategies": strategies,
        "recent_ledger": recent_ledger,
    }


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Z3RO Autonomous Economic Agent Dashboard</title>
  <style>
    :root {
      --bg: #090a0f;
      --card-bg: rgba(22, 27, 34, 0.85);
      --border: rgba(255, 255, 255, 0.08);
      --text: #f0f6fc;
      --text-muted: #8b949e;
      --accent: #58a6ff;
      --green: #3fb950;
      --red: #f85149;
      --yellow: #d29922;
    }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      margin: 0;
      padding: 24px;
    }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--border);
    }
    .metrics-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 16px;
      backdrop-filter: blur(10px);
    }
    .card-title { font-size: 13px; color: var(--text-muted); margin-bottom: 8px; }
    .card-value { font-size: 26px; font-weight: 700; color: var(--text); }
    .status-badge {
      display: inline-block;
      padding: 4px 10px;
      border-radius: 20px;
      font-size: 12px;
      font-weight: 600;
    }
    .status-healthy { background: rgba(63, 185, 80, 0.2); color: var(--green); }
    .status-warning { background: rgba(210, 153, 34, 0.2); color: var(--yellow); }
    .status-critical { background: rgba(248, 81, 73, 0.2); color: var(--red); }
    .btn {
      background: #21262d;
      border: 1px solid var(--border);
      color: var(--text);
      padding: 8px 16px;
      border-radius: 6px;
      cursor: pointer;
      font-weight: 600;
      font-size: 13px;
    }
    .btn-danger { background: rgba(248, 81, 73, 0.2); border-color: var(--red); color: var(--red); }
    .btn-success { background: rgba(63, 185, 80, 0.2); border-color: var(--green); color: var(--green); }
    table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 13px; }
    th, td { text-align: left; padding: 10px; border-bottom: 1px solid var(--border); }
    th { color: var(--text-muted); }
  </style>
</head>
<body>
  <div class="header">
    <div>
      <h1 style="margin:0; font-size: 22px;">Z3RO Autonomous Economic Dashboard</h1>
      <span style="color: var(--text-muted); font-size: 13px;">Blueprint v2.0 Architecture</span>
    </div>
    <div>
      <button id="btn-kill" class="btn btn-danger" onclick="toggleKillSwitch()">Kill Switch: OFF</button>
      <button class="btn btn-success" style="margin-left: 8px;" onclick="runCycle()">▶ Run Discovery Step</button>
    </div>
  </div>

  <div class="metrics-grid">
    <div class="card">
      <div class="card-title">WALLET BALANCE</div>
      <div class="card-value" id="val-balance">$1,000.00</div>
    </div>
    <div class="card">
      <div class="card-title">VERIFIED NET PROFIT</div>
      <div class="card-value" id="val-net" style="color: var(--green);">$0.00</div>
    </div>
    <div class="card">
      <div class="card-title">DAILY BURN RATE</div>
      <div class="card-value">$100.00 <span style="font-size: 14px; font-weight: normal; color: var(--text-muted);">/ day</span></div>
    </div>
    <div class="card">
      <div class="card-title">OPERATIONAL RUNWAY</div>
      <div class="card-value" id="val-runway">240.0 hrs</div>
      <div id="badge-status" class="status-badge status-healthy" style="margin-top: 6px;">HEALTHY</div>
    </div>
  </div>

  <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 24px;">
    <div class="card">
      <div class="card-title">PENDING HUMAN APPROVALS</div>
      <div id="approvals-container">No pending actions.</div>
    </div>
    <div class="card">
      <div class="card-title">COMPLIANCE-FILTER REJECTIONS PANEL</div>
      <div id="rejections-container">No rejections logged.</div>
    </div>
  </div>

  <div class="card">
    <div class="card-title">STRATEGY MEMORY (LEARNED METRICS)</div>
    <table id="table-strategies">
      <thead>
        <tr><th>Strategy ID</th><th>Name</th><th>Confidence</th><th>Spent</th><th>Revenue</th><th>Net</th><th>Status</th></tr>
      </thead>
      <tbody></tbody>
    </table>
  </div>

  <script>
    async function loadData() {
      try {
        const res = await fetch('/api/status');
        const data = await res.json();
        document.getElementById('val-balance').textContent = '$' + data.wallet.balance.toFixed(2);
        document.getElementById('val-net').textContent = (data.wallet.net_profit >= 0 ? '+' : '') + '$' + data.wallet.net_profit.toFixed(2);
        document.getElementById('val-runway').textContent = data.survival.remaining_hours.toFixed(1) + ' hrs';
        
        const badge = document.getElementById('badge-status');
        badge.textContent = data.survival.status;
        badge.className = 'status-badge status-' + (data.survival.status.toLowerCase());

        const btnKill = document.getElementById('btn-kill');
        if (data.limits.kill_switch_active) {
          btnKill.textContent = 'Kill Switch: ACTIVE (HALTED)';
          btnKill.style.background = '#f85149';
          btnKill.style.color = '#fff';
        } else {
          btnKill.textContent = 'Kill Switch: READY';
          btnKill.style.background = 'rgba(248, 81, 73, 0.2)';
          btnKill.style.color = '#f85149';
        }

        // Approvals
        const appContainer = document.getElementById('approvals-container');
        if (!data.pending_approvals || data.pending_approvals.length === 0) {
          appContainer.innerHTML = '<div style="color:var(--text-muted); font-size:13px;">No actions awaiting authorization.</div>';
        } else {
          appContainer.innerHTML = data.pending_approvals.map(a => `
            <div style="border-bottom:1px solid var(--border); padding:8px 0; font-size:13px;">
              <strong>${a.capability}</strong>: ${a.message} (Cost: $${a.estimated_cost})
              <div style="margin-top:6px;">
                <button class="btn btn-success" style="padding:3px 8px; font-size:11px;" onclick="resolveApproval('${a.action_id}', true)">Approve</button>
                <button class="btn btn-danger" style="padding:3px 8px; font-size:11px; margin-left:6px;" onclick="resolveApproval('${a.action_id}', false)">Reject</button>
              </div>
            </div>
          `).join('');
        }

        // Compliance Rejections
        const rejContainer = document.getElementById('rejections-container');
        if (!data.compliance_rejections || data.compliance_rejections.length === 0) {
          rejContainer.innerHTML = '<div style="color:var(--text-muted); font-size:13px;">No compliance violations detected.</div>';
        } else {
          rejContainer.innerHTML = data.compliance_rejections.map(r => `
            <div style="border-bottom:1px solid var(--border); padding:8px 0; font-size:13px;">
              <span class="status-badge status-critical" style="padding:2px 6px; font-size:10px;">${r.category}</span>
              <strong style="margin-left:6px;">${r.strategy_name}</strong>
              <div style="color:var(--text-muted); font-size:12px; margin-top:2px;">${r.reason}</div>
            </div>
          `).join('');
        }

        // Strategy Table
        const tbody = document.querySelector('#table-strategies tbody');
        tbody.innerHTML = (data.strategies || []).map(s => `
          <tr>
            <td><code>${s.strategy_id}</code></td>
            <td>${s.name}</td>
            <td>${(s.confidence * 100).toFixed(0)}%</td>
            <td>$${s.capital_spent.toFixed(2)}</td>
            <td>$${s.verified_revenue.toFixed(2)}</td>
            <td style="color:${s.net_profit >= 0 ? 'var(--green)' : 'var(--red)'};">$${s.net_profit.toFixed(2)}</td>
            <td>${s.status}</td>
          </tr>
        `).join('');

      } catch (err) {
        console.error('Failed loading data:', err);
      }
    }

    async function toggleKillSwitch() {
      const active = document.getElementById('btn-kill').textContent.includes('READY');
      await fetch('/api/killswitch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ active: active }),
      });
      loadData();
    }

    async function resolveApproval(actionId, approved) {
      await fetch('/api/approvals/resolve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action_id: actionId, approved: approved }),
      });
      loadData();
    }

    async function runCycle() {
      await fetch('/api/cycle/run', { method: 'POST' });
      loadData();
    }

    setInterval(loadData, 2000);
    loadData();
  </script>
</body>
</html>
"""


class DashboardRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler providing REST API and embedded web UI."""

    def log_message(self, format, *args):
        # Silence routine request logging to keep console clean
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode("utf-8"))

        elif path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            data = get_full_dashboard_state()
            self.wfile.write(json.dumps(data).encode("utf-8"))

        elif path == "/api/approvals":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(approval_queue.get_pending()).encode("utf-8"))

        elif path == "/api/compliance/rejections":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(legal_filter.get_recent_rejections()).encode("utf-8"))

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            payload = json.loads(body)
        except Exception:
            payload = {}

        if path == "/api/killswitch":
            active = bool(payload.get("active", False))
            limits_manager.set_kill_switch(active)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "kill_switch_active": active}).encode("utf-8"))

        elif path == "/api/approvals/resolve":
            action_id = payload.get("action_id", "")
            approved = bool(payload.get("approved", False))
            ok = approval_queue.resolve_action(action_id, approved=approved)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": ok}).encode("utf-8"))

        elif path == "/api/cycle/run":
            res = loop_coordinator.run_discovery_cycle()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))

        else:
            self.send_response(404)
            self.end_headers()


def run_dashboard_server(port: int = 8766):
    """Run local dashboard server."""
    server = HTTPServer(("127.0.0.1", port), DashboardRequestHandler)
    print(f"[Z3RO Dashboard] Serving at http://127.0.0.1:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    run_dashboard_server()
