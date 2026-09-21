/**
 * DYNAMIC ISLAND OVERLAY — CLIENT CONTROLLER (app.js)
 * 120 FPS Fluid Animations, WebSocket RPC Bridge, and State Machine
 * Upgraded for Z3RO Blueprint v2.0 (Economy Telemetry, Approvals, Compliance & Kill Switch)
 */

(function () {
  "use strict";

  // --- DOM Element References ---
  const island = document.getElementById("island");
  const islandHeader = document.getElementById("island-header");
  const statusOrb = document.getElementById("status-orb");
  const brandName = document.getElementById("brand-name");
  const pillBalance = document.getElementById("pill-balance");
  const statusLabel = document.getElementById("status-label");
  const waveContainer = document.getElementById("wave-container");
  const waveBars = document.querySelectorAll(".wave-bar");
  const thinkingContainer = document.getElementById("thinking-container");
  const thinkingLabel = thinkingContainer ? thinkingContainer.querySelector(".thinking-label") : null;
  const actionBadge = document.getElementById("action-badge");
  const actionText = document.getElementById("action-text");
  const btnStop = document.getElementById("btn-stop");
  const btnMic = document.getElementById("btn-mic");
  const btnExpand = document.getElementById("btn-expand");
  const btnInputMic = document.getElementById("btn-input-mic");
  const chatDrawer = document.getElementById("chat-drawer");
  const messageList = document.getElementById("message-list");
  const chatForm = document.getElementById("chat-form");
  const chatInput = document.getElementById("chat-input");

  // --- Segmented Tabs & Badges ---
  const navTabs = document.querySelectorAll(".nav-tab");
  const tabPanes = document.querySelectorAll(".tab-pane");
  const navApprovalBadge = document.getElementById("nav-approval-badge");

  // --- Telemetry & Economic Controls ---
  const econBalance = document.getElementById("econ-balance");
  const econNetSub = document.getElementById("econ-net-sub");
  const econRunway = document.getElementById("econ-runway");
  const econStatusBadge = document.getElementById("econ-status-badge");
  const econRateRatio = document.getElementById("econ-rate-ratio");
  const econDailyCap = document.getElementById("econ-daily-cap");
  const btnKillSwitch = document.getElementById("btn-kill-switch");
  const killText = document.getElementById("kill-text");
  const btnRunCycle = document.getElementById("btn-run-cycle");

  // --- Strategy Card Elements ---
  const activeStrategyMode = document.getElementById("active-strategy-mode");
  const activeStrategyName = document.getElementById("active-strategy-name");
  const activeStrategyDesc = document.getElementById("active-strategy-desc");
  const activeStrategyConf = document.getElementById("active-strategy-conf");
  const activeStrategyBar = document.getElementById("active-strategy-bar");

  // --- Feeds & Tables ---
  const tbodyLedger = document.getElementById("tbody-ledger");
  const approvalsContainer = document.getElementById("approvals-container");
  const complianceRejectionsContainer = document.getElementById("compliance-rejections-container");
  const badgeTotalRejections = document.getElementById("badge-total-rejections");
  const tbodyStrategies = document.getElementById("tbody-strategies");

  // --- Constants ---
  const WS_URL = "ws://127.0.0.1:8765";

  // --- State Variables ---
  let socket = null;
  let isExpanded = false;
  let isMicActive = false;
  let currentState = "idle";
  let speakingAnimFrame = null;
  let reconnectTimeout = null;
  let currentTab = "chat";
  let isKillActive = false;

  // =========================================================================
  // 1. EXPAND / COLLAPSE DRAWER ANIMATION (120 FPS Fluid Morph)
  // =========================================================================
  function releaseElectronFocus() {
    if (chatInput && document.activeElement === chatInput) {
      chatInput.blur();
    }
    if (window.electronAPI && window.electronAPI.blurWindow) {
      window.electronAPI.blurWindow();
    }
  }

  function toggleDrawer(forceState = null, autoFocus = false) {
    const nextState = forceState !== null ? forceState : !isExpanded;
    if (isExpanded === nextState) return;

    isExpanded = nextState;

    if (isExpanded) {
      island.classList.remove("collapsed");
      island.classList.add("expanded");
      if (currentTab !== "chat") {
        island.classList.add("wide-mode");
        if (window.electronAPI && window.electronAPI.setWindowSize) {
          window.electronAPI.setWindowSize(600, 540);
        }
      } else {
        island.classList.remove("wide-mode");
        if (window.electronAPI && window.electronAPI.setWindowSize) {
          window.electronAPI.setWindowSize(460, 500);
        }
      }

      if (autoFocus && currentTab === "chat") {
        setTimeout(() => {
          if (chatInput) chatInput.focus();
          scrollToBottom();
        }, 340);
      } else {
        releaseElectronFocus();
      }
    } else {
      island.classList.remove("expanded");
      island.classList.remove("wide-mode");
      island.classList.add("collapsed");
      if (window.electronAPI && window.electronAPI.setWindowSize) {
        window.electronAPI.setWindowSize(460, 500);
      }
      releaseElectronFocus();
    }
  }

  // High-performance mouse passthrough
  let isMouseOverIsland = false;
  window.addEventListener(
    "mousemove",
    (event) => {
      const inside = Boolean(event.target && event.target.closest && event.target.closest("#island"));
      if (inside && !isMouseOverIsland) {
        isMouseOverIsland = true;
        if (window.electronAPI && window.electronAPI.setIgnoreMouseEvents) {
          window.electronAPI.setIgnoreMouseEvents(false);
        }
      } else if (!inside && isMouseOverIsland) {
        isMouseOverIsland = false;
        if (window.electronAPI && window.electronAPI.setIgnoreMouseEvents) {
          window.electronAPI.setIgnoreMouseEvents(true, true);
        }
      }
    },
    { passive: true }
  );

  if (btnExpand) {
    btnExpand.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleDrawer(null, true);
    });
  }

  // =========================================================================
  // 2. SEGMENTED TAB SWITCHING & WIDE-MODE
  // =========================================================================
  function switchTab(tabId) {
    currentTab = tabId;
    navTabs.forEach((tab) => {
      if (tab.dataset.tab === tabId) tab.classList.add("active");
      else tab.classList.remove("active");
    });

    tabPanes.forEach((pane) => {
      if (pane.id === `tab-pane-${tabId}`) pane.classList.remove("hidden");
      else pane.classList.add("hidden");
    });

    if (tabId === "chat") {
      island.classList.remove("wide-mode");
      if (window.electronAPI && window.electronAPI.setWindowSize) {
        window.electronAPI.setWindowSize(460, 500);
      }
    } else {
      island.classList.add("wide-mode");
      if (window.electronAPI && window.electronAPI.setWindowSize) {
        window.electronAPI.setWindowSize(600, 540);
      }
      sendWsMessage({ type: "get_economy_state" });
    }
  }

  navTabs.forEach((tab) => {
    tab.addEventListener("click", (e) => {
      e.stopPropagation();
      const tabId = tab.dataset.tab;
      if (tabId) switchTab(tabId);
    });
  });

  // =========================================================================
  // 3. WEBSOCKET CLIENT & AUTO-RECONNECT
  // =========================================================================
  function connectWebSocket() {
    if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
      return;
    }

    try {
      socket = new WebSocket(WS_URL);
    } catch (e) {
      scheduleReconnect();
      return;
    }

    socket.onopen = () => {
      console.log("[UI Bridge] Connected to Python Assistant at", WS_URL);
      setStatus("idle", "Ready");
      if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
        reconnectTimeout = null;
      }
      sendWsMessage({ type: "get_economy_state" });
    };

    socket.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        handleServerMessage(msg);
      } catch (err) {
        console.warn("[UI Bridge] Invalid JSON message received:", event.data);
      }
    };

    socket.onerror = (err) => {
      console.warn("[UI Bridge] WebSocket error:", err);
    };

    socket.onclose = () => {
      console.log("[UI Bridge] Connection closed. Retrying...");
      setStatus("disconnected", "Offline");
      scheduleReconnect();
    };
  }

  function scheduleReconnect() {
    if (reconnectTimeout) return;
    reconnectTimeout = setTimeout(() => {
      reconnectTimeout = null;
      connectWebSocket();
    }, 2000);
  }

  function sendWsMessage(payload) {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(payload));
      return true;
    } else {
      console.warn("[UI Bridge] Cannot send message; WebSocket not open.");
      return false;
    }
  }

  // =========================================================================
  // 4. SERVER MESSAGE ROUTING & STATE MACHINE
  // =========================================================================
  function handleServerMessage(msg) {
    const type = msg.type;

    switch (type) {
      case "init":
        if (msg.name && brandName) {
          brandName.textContent = msg.name;
        }
        setStatus(msg.status || "idle", "Ready");
        if (msg.economy_state) {
          updateEconomyUI(msg.economy_state);
        }
        break;

      case "economy_state":
        if (msg.data) {
          updateEconomyUI(msg.data);
        }
        break;

      case "cycle_completed":
        if (msg.economy_state) {
          updateEconomyUI(msg.economy_state);
        }
        if (msg.result && msg.result.strategy) {
          showActionBadge(`Cycle: ${msg.result.strategy.name}`);
        }
        break;

      case "status":
        const state = msg.state || "idle";
        if (msg.name && brandName) {
          brandName.textContent = msg.name;
        }
        if (state === "listening") {
          setStatus("listening", "Listening...");
          isMicActive = true;
          updateMicUI(true);
        } else if (state === "transcribing") {
          setStatus("thinking", "Transcribing...");
          isMicActive = false;
          updateMicUI(false);
        } else if (state === "thinking") {
          setStatus("thinking", msg.prompt ? "Thinking..." : "Thinking");
        } else if (state === "speaking") {
          setStatus("speaking", "Speaking...");
        } else if (state === "idle") {
          isMicActive = false;
          updateMicUI(false);
          setStatus("idle", msg.message || "Ready");
        }
        break;

      case "audio_level":
        if (currentState === "listening" || currentState === "speaking") {
          renderWaveLevel(msg.level || 0.1);
        }
        break;

      case "transcript":
        if (msg.text) {
          appendMessage("user", msg.text, true);
        }
        break;

      case "response":
        if (msg.text) {
          appendMessage("assistant", msg.text);
        }
        break;

      case "action":
        releaseElectronFocus();
        if (msg.description) {
          showActionBadge(msg.description);
        }
        break;

      case "blur_focus":
        releaseElectronFocus();
        break;

      case "error":
        appendMessage("assistant", `⚠️ Error: ${msg.error || "Unknown error"}`);
        setStatus("idle", "Error");
        break;

      default:
        break;
    }
  }

  // =========================================================================
  // 5. ECONOMIC TELEMETRY & CONTROLS UI UPDATES
  // =========================================================================
  function updateEconomyUI(data) {
    if (!data) return;

    // Header chip
    if (data.wallet && pillBalance) {
      pillBalance.textContent = `$${data.wallet.balance.toLocaleString("en-US", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })}`;
    }

    // Telemetry cards
    if (data.wallet && econBalance) {
      econBalance.textContent = `$${data.wallet.balance.toLocaleString("en-US", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })}`;
      const net = data.wallet.net_profit;
      if (econNetSub) {
        econNetSub.textContent = `Net Profit: ${net >= 0 ? "+" : ""}$${net.toFixed(2)}`;
        econNetSub.style.color = net >= 0 ? "#34d399" : "#f87171";
      }
    }

    if (data.survival && econRunway) {
      econRunway.textContent = `${data.survival.remaining_hours.toFixed(1)}h`;
      if (econStatusBadge) {
        econStatusBadge.textContent = data.survival.status;
        econStatusBadge.className = `badge-status badge-${data.survival.status.toLowerCase()}`;
      }
    }

    if (data.limits && econRateRatio) {
      econRateRatio.textContent = `${data.limits.actions_last_hour} / ${data.limits.hourly_cap} actions/hr`;
      if (econDailyCap) {
        econDailyCap.textContent = `Daily Cap: $${data.limits.daily_spend_cap} | Single: $${data.limits.single_tx_cap}`;
      }

      // Kill Switch State
      isKillActive = Boolean(data.limits.kill_switch_active);
      if (btnKillSwitch && killText) {
        if (isKillActive) {
          btnKillSwitch.className = "btn-kill active";
          killText.textContent = "KILL SWITCH: ACTIVE (HALTED)";
        } else {
          btnKillSwitch.className = "btn-kill ready";
          killText.textContent = "READY (ACTIVE MONITORING)";
        }
      }
    }

    // Current Strategy & Experiment
    if (data.current_strategy) {
      const s = data.current_strategy;
      if (activeStrategyName) activeStrategyName.textContent = s.name || "Emerging Opportunity";
      if (activeStrategyDesc) activeStrategyDesc.textContent = s.description || "";
      const confPercent = Math.round((s.confidence || 0.5) * 100);
      if (activeStrategyConf) activeStrategyConf.textContent = `${confPercent}%`;
      if (activeStrategyBar) activeStrategyBar.style.width = `${confPercent}%`;
    }

    // Ledger table
    if (data.recent_ledger && tbodyLedger) {
      if (data.recent_ledger.length === 0) {
        tbodyLedger.innerHTML = '<tr><td colspan="6" class="text-center text-dim">No transactions recorded yet.</td></tr>';
      } else {
        tbodyLedger.innerHTML = data.recent_ledger
          .map((row) => {
            const netVal = row.net;
            const netColor = netVal >= 0 ? "#34d399" : "#f87171";
            const timeStr = (row.timestamp || "").split("T")[1]?.slice(0, 8) || row.timestamp;
            return `
              <tr>
                <td><code>${escapeHtml(timeStr)}</code></td>
                <td>${escapeHtml(row.action)}</td>
                <td>$${row.cost.toFixed(2)}</td>
                <td>$${row.verified_income.toFixed(2)}</td>
                <td style="color:${netColor}; font-weight:700;">${netVal >= 0 ? "+" : ""}$${netVal.toFixed(2)}</td>
                <td><span class="source-tag">${escapeHtml(row.verification_source)}</span></td>
              </tr>
            `;
          })
          .join("");
      }
    }

    // Pending Approvals Queue (Sections 9.1 & 9.6)
    if (approvalsContainer) {
      const pending = data.pending_approvals || [];
      if (navApprovalBadge) {
        if (pending.length > 0) {
          navApprovalBadge.textContent = pending.length;
          navApprovalBadge.classList.remove("hidden");
        } else {
          navApprovalBadge.classList.add("hidden");
        }
      }

      if (pending.length === 0) {
        approvalsContainer.innerHTML = `
          <div class="empty-state">
            <span class="empty-icon">✓</span>
            <p>No actions currently awaiting authorization.</p>
          </div>
        `;
      } else {
        approvalsContainer.innerHTML = pending
          .map(
            (item) => `
          <div class="approval-card" data-id="${item.action_id}">
            <div class="approval-card-top">
              <span class="tag-capability">${escapeHtml(item.capability)}</span>
              <span class="tag-irreversible">${escapeHtml(item.reversibility)}</span>
            </div>
            <div class="approval-message">${formatMessageText(item.message)}</div>
            <div style="font-size:10.5px; color:var(--text-muted);">
              Recipient: <code>${escapeHtml(item.recipient || "N/A")}</code> | Cost: $${item.estimated_cost.toFixed(2)}
            </div>
            <div class="approval-actions">
              <button type="button" class="btn-approve" onclick="window.__resolveApproval('${item.action_id}', true)">✓ Approve</button>
              <button type="button" class="btn-reject" onclick="window.__resolveApproval('${item.action_id}', false)">✕ Reject</button>
            </div>
          </div>
        `
          )
          .join("");
      }
    }

    // Compliance Rejections Feed (Section 13)
    if (complianceRejectionsContainer) {
      const rejections = data.compliance_rejections || [];
      if (badgeTotalRejections) {
        badgeTotalRejections.textContent = `${rejections.length} Violation${rejections.length === 1 ? "" : "s"}`;
      }

      if (rejections.length === 0) {
        complianceRejectionsContainer.innerHTML = `
          <div class="empty-state">
            <span class="empty-icon">🛡️</span>
            <p>Zero compliance violations. Legal filter active.</p>
          </div>
        `;
      } else {
        complianceRejectionsContainer.innerHTML = rejections
          .map((r) => {
            const timeStr = (r.timestamp || "").split("T")[1]?.slice(0, 8) || r.timestamp;
            return `
            <div class="compliance-card">
              <div class="compliance-card-header">
                <span class="tag-rule">${escapeHtml(r.category)} • ${escapeHtml(r.rule_id)}</span>
                <span style="font-size:10px; color:var(--text-dim);">${escapeHtml(timeStr)}</span>
              </div>
              <div class="compliance-strategy-title">${escapeHtml(r.strategy_name)}</div>
              <div class="compliance-reason">${escapeHtml(r.reason)}</div>
            </div>
          `;
          })
          .join("");
      }
    }

    // Strategy Memory Table (Section 8)
    if (tbodyStrategies) {
      const strats = data.strategies || [];
      if (strats.length === 0) {
        tbodyStrategies.innerHTML = '<tr><td colspan="6" class="text-center text-dim">Memory empty. Run discovery step to learn.</td></tr>';
      } else {
        tbodyStrategies.innerHTML = strats
          .map((s) => {
            const conf = Math.round((s.confidence || 0.5) * 100);
            const net = s.net_profit || 0;
            return `
            <tr>
              <td><strong>${escapeHtml(s.name)}</strong></td>
              <td>${conf}%</td>
              <td>$${(s.capital_spent || 0).toFixed(2)}</td>
              <td>$${(s.verified_revenue || 0).toFixed(2)}</td>
              <td style="color:${net >= 0 ? "#34d399" : "#f87171"}; font-weight:700;">${net >= 0 ? "+" : ""}$${net.toFixed(2)}</td>
              <td><span class="source-tag">${escapeHtml(s.status || "DISCOVERED")}</span></td>
            </tr>
          `;
          })
          .join("");
      }
    }
  }

  // Global resolve function for dynamically rendered buttons
  window.__resolveApproval = function (actionId, approved) {
    sendWsMessage({
      type: "resolve_approval",
      action_id: actionId,
      approved: approved,
    });
  };

  if (btnKillSwitch) {
    btnKillSwitch.addEventListener("click", (e) => {
      e.stopPropagation();
      sendWsMessage({
        type: "toggle_kill_switch",
        active: !isKillActive,
      });
    });
  }

  if (btnRunCycle) {
    btnRunCycle.addEventListener("click", (e) => {
      e.stopPropagation();
      btnRunCycle.textContent = "⏳ Exploring...";
      btnRunCycle.disabled = true;
      sendWsMessage({ type: "run_discovery_cycle" });
      setTimeout(() => {
        btnRunCycle.textContent = "▶ Run Discovery Step";
        btnRunCycle.disabled = false;
      }, 1500);
    });
  }

  // =========================================================================
  // 6. VISUAL STATE & ANIMATION MANAGEMENT
  // =========================================================================
  function setStatus(state, labelText) {
    currentState = state;

    if (waveContainer) waveContainer.classList.add("hidden");
    if (thinkingContainer) thinkingContainer.classList.add("hidden");
    if (actionBadge) actionBadge.classList.add("hidden");
    if (statusLabel) {
      statusLabel.classList.remove("hidden");
      statusLabel.textContent = labelText;
    }

    if (btnStop) {
      if (state === "thinking" || state === "speaking") {
        btnStop.classList.remove("hidden");
      } else {
        btnStop.classList.add("hidden");
      }
    }

    if (statusOrb) {
      statusOrb.className = `status-orb ${state}`;
    }

    if (state === "listening") {
      if (waveContainer) waveContainer.classList.remove("hidden");
      if (statusLabel) statusLabel.classList.add("hidden");
      cancelSpeakingAnim();
    } else if (state === "thinking") {
      if (thinkingContainer) {
        thinkingContainer.classList.remove("hidden");
        if (thinkingLabel) thinkingLabel.textContent = labelText || "Thinking";
      }
      if (statusLabel) statusLabel.classList.add("hidden");
      cancelSpeakingAnim();
    } else if (state === "speaking") {
      if (waveContainer) waveContainer.classList.remove("hidden");
      if (statusLabel) statusLabel.classList.add("hidden");
      startProceduralSpeakingAnim();
    } else {
      cancelSpeakingAnim();
      resetWaveBars();
    }
  }

  function showActionBadge(actionName) {
    if (actionBadge && actionText) {
      actionText.textContent = actionName;
      actionBadge.classList.remove("hidden");
      if (statusLabel) statusLabel.classList.add("hidden");
      if (thinkingContainer) thinkingContainer.classList.add("hidden");
      if (waveContainer) waveContainer.classList.add("hidden");
    }
  }

  function renderWaveLevel(level) {
    if (!waveBars || waveBars.length === 0) return;
    const clamped = Math.max(0.1, Math.min(1.0, level));
    const heights = [
      0.2 + clamped * 0.6,
      0.25 + clamped * 0.9,
      0.3 + clamped * 1.3,
      0.25 + clamped * 0.9,
      0.2 + clamped * 0.6,
    ];

    waveBars.forEach((bar, idx) => {
      const scale = heights[idx] !== undefined ? Math.min(heights[idx], 1.5) : 0.2;
      bar.style.transform = `scaleY(${scale})`;
    });
  }

  function resetWaveBars() {
    if (!waveBars) return;
    waveBars.forEach((bar) => {
      bar.style.transform = "scaleY(0.2)";
    });
  }

  function startProceduralSpeakingAnim() {
    cancelSpeakingAnim();
    let angle = 0;

    function step() {
      if (currentState !== "speaking") return;
      angle += 0.12;

      waveBars.forEach((bar, idx) => {
        const offset = idx * 0.8;
        const scale = 0.35 + Math.sin(angle + offset) * 0.35 + Math.cos(angle * 1.5 + offset) * 0.15;
        bar.style.transform = `scaleY(${Math.max(0.2, scale)})`;
      });

      speakingAnimFrame = requestAnimationFrame(step);
    }
    speakingAnimFrame = requestAnimationFrame(step);
  }

  function cancelSpeakingAnim() {
    if (speakingAnimFrame) {
      cancelAnimationFrame(speakingAnimFrame);
      speakingAnimFrame = null;
    }
  }

  // =========================================================================
  // 7. MICROPHONE & VOICE CONTROLS
  // =========================================================================
  function updateMicUI(active) {
    if (btnMic) {
      if (active) btnMic.classList.add("active");
      else btnMic.classList.remove("active");
    }
    if (btnInputMic) {
      if (active) btnInputMic.classList.add("active");
      else btnInputMic.classList.remove("active");
    }
  }

  function toggleMicrophone() {
    if (!isMicActive) {
      const sent = sendWsMessage({ type: "start_mic" });
      if (sent) {
        isMicActive = true;
        updateMicUI(true);
        setStatus("listening", "Listening...");
      }
    } else {
      sendWsMessage({ type: "stop_mic" });
      isMicActive = false;
      updateMicUI(false);
      setStatus("thinking", "Transcribing...");
    }
  }

  if (btnMic) {
    btnMic.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleMicrophone();
    });
  }

  if (btnInputMic) {
    btnInputMic.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleMicrophone();
    });
  }

  // =========================================================================
  // 8. STOP GENERATION & ABORT BUTTON
  // =========================================================================
  function stopGeneration() {
    console.log("[UI Bridge] Requesting stop generation.");
    sendWsMessage({ type: "stop_generation" });
    setStatus("idle", "Stopped");
    if (btnStop) btnStop.classList.add("hidden");
  }

  if (btnStop) {
    btnStop.addEventListener("click", (e) => {
      e.stopPropagation();
      stopGeneration();
    });
  }

  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (currentState === "thinking" || currentState === "speaking") {
        stopGeneration();
      } else if (isExpanded) {
        toggleDrawer(false);
      }
    }
  });

  // =========================================================================
  // 9. CHAT MESSAGE RENDERING & FORM INPUT
  // =========================================================================
  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function formatMessageText(str) {
    if (!str) return "";
    let safe = escapeHtml(str);
    safe = safe.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    safe = safe.replace(/\*([^*]+)\*/g, "<em>$1</em>");
    safe = safe.replace(/`([^`]+)`/g, "<code>$1</code>");
    return safe;
  }

  function appendMessage(role, text, isVoice = false) {
    if (!messageList) return;

    if (!isExpanded) {
      toggleDrawer(true, false);
    }
    // Switch to chat tab if another tab was open
    if (currentTab !== "chat") {
      switchTab("chat");
    }
    releaseElectronFocus();

    const welcomeHero = document.getElementById("welcome-hero");
    if (welcomeHero) {
      welcomeHero.style.display = "none";
    }
    if (chatDrawer) {
      chatDrawer.classList.add("has-messages");
    }

    const rowEl = document.createElement("div");
    rowEl.className = `message-row ${role}`;

    if (role === "assistant") {
      const avatarEl = document.createElement("img");
      avatarEl.src = "assets/logo.png";
      avatarEl.className = "msg-avatar";
      avatarEl.alt = "SOBIA";
      rowEl.appendChild(avatarEl);
    }

    const msgEl = document.createElement("div");
    msgEl.className = `message ${role}`;

    const textSpan = document.createElement("span");
    textSpan.className = "msg-text";

    if (isVoice) {
      textSpan.innerHTML = `<span style="opacity: 0.6; margin-right: 4px;">🎙️</span>${formatMessageText(text)}`;
    } else {
      textSpan.innerHTML = formatMessageText(text);
    }

    msgEl.appendChild(textSpan);
    rowEl.appendChild(msgEl);
    messageList.appendChild(rowEl);
    scrollToBottom();
  }

  function scrollToBottom() {
    if (messageList) {
      messageList.scrollTop = messageList.scrollHeight;
    }
  }

  if (chatForm) {
    chatForm.addEventListener("submit", (e) => {
      e.preventDefault();
      if (!chatInput) return;

      const userText = chatInput.value.trim();
      if (!userText) return;

      chatInput.value = "";
      appendMessage("user", userText);

      sendWsMessage({ type: "chat", text: userText });
      setStatus("thinking", "Thinking...");
    });
  }

  // =========================================================================
  // 10. INITIAL BOOTSTRAP
  // =========================================================================
  connectWebSocket();
})();
