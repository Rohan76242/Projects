/**
 * DYNAMIC ISLAND OVERLAY — CLIENT CONTROLLER (app.js)
 * 120 FPS Fluid Animations, WebSocket RPC Bridge, and State Machine
 */

(function () {
  "use strict";

  // --- DOM Element References ---
  const island = document.getElementById("island");
  const islandHeader = document.getElementById("island-header");
  const statusOrb = document.getElementById("status-orb");
  const brandName = document.getElementById("brand-name");
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

  // --- Constants & Sizing for Dynamic Island ---
  const COLLAPSED_WIDTH = 260;
  const COLLAPSED_HEIGHT = 64;
  const EXPANDED_WIDTH = 440;
  const EXPANDED_HEIGHT = 480;
  const WS_URL = "ws://127.0.0.1:8765";

  // --- State Variables ---
  let socket = null;
  let isExpanded = false;
  let isMicActive = false;
  let currentState = "idle";
  let speakingAnimFrame = null;
  let reconnectTimeout = null;

  // =========================================================================
  // 1. EXPAND / COLLAPSE DRAWER ANIMATION (120 FPS Fluid Morph)
  // =========================================================================
  function toggleDrawer(forceState = null) {
    const nextState = forceState !== null ? forceState : !isExpanded;
    if (isExpanded === nextState) return;

    isExpanded = nextState;

    if (isExpanded) {
      island.classList.remove("collapsed");
      island.classList.add("expanded");
      setTimeout(() => {
        if (chatInput) chatInput.focus();
        scrollToBottom();
      }, 100);
    } else {
      island.classList.remove("expanded");
      island.classList.add("collapsed");
    }
  }

  // Mouse passthrough management: Only capture clicks when hovering over the Island
  let isMouseOverIsland = false;
  window.addEventListener("mousemove", (event) => {
    if (!island) return;
    const rect = island.getBoundingClientRect();
    const inside = (
      event.clientX >= rect.left &&
      event.clientX <= rect.right &&
      event.clientY >= rect.top &&
      event.clientY <= rect.bottom
    );

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
  });


  if (btnExpand) {
    btnExpand.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleDrawer();
    });
  }

  // =========================================================================
  // 2. WEBSOCKET CLIENT & AUTO-RECONNECT
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
  // 3. SERVER MESSAGE ROUTING & STATE MACHINE
  // =========================================================================
  function handleServerMessage(msg) {
    const type = msg.type;

    switch (type) {
      case "init":
        if (msg.name && brandName) {
          brandName.textContent = msg.name;
        }
        setStatus(msg.status || "idle", "Ready");
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
        if (msg.description) {
          showActionBadge(msg.description);
        }
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
  // 4. VISUAL STATE & ANIMATION MANAGEMENT
  // =========================================================================
  function setStatus(state, labelText) {
    currentState = state;

    // Reset components visibility
    if (waveContainer) waveContainer.classList.add("hidden");
    if (thinkingContainer) thinkingContainer.classList.add("hidden");
    if (actionBadge) actionBadge.classList.add("hidden");
    if (statusLabel) {
      statusLabel.classList.remove("hidden");
      statusLabel.textContent = labelText;
    }

    // Stop button visibility (shown during active processing)
    if (btnStop) {
      if (state === "thinking" || state === "speaking") {
        btnStop.classList.remove("hidden");
      } else {
        btnStop.classList.add("hidden");
      }
    }

    // Status Orb styling
    if (statusOrb) {
      statusOrb.className = `status-orb ${state}`;
    }

    // State specific layouts
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

  // Live Audio Wave Animation based on real microphone volume (RMS)
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

  // Procedural subtle wave oscillation during Edge TTS speech
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
  // 5. MICROPHONE & VOICE CONTROLS
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
      // Start recording
      const sent = sendWsMessage({ type: "start_mic" });
      if (sent) {
        isMicActive = true;
        updateMicUI(true);
        setStatus("listening", "Listening...");
      }
    } else {
      // Stop recording and process
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
  // 6. STOP GENERATION & ABORT BUTTON
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

  // Global Esc key to abort generation or close drawer
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
  // 7. CHAT MESSAGE RENDERING & FORM INPUT
  // =========================================================================
  function escapeHtml(str) {
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function appendMessage(role, text, isVoice = false) {
    if (!messageList) return;

    // Automatically expand drawer if a message arrives and it is collapsed
    if (!isExpanded) {
      toggleDrawer(true);
    }

    // Hide welcome hero on first message
    const welcomeHero = document.getElementById("welcome-hero");
    if (welcomeHero) {
      welcomeHero.style.display = "none";
    }

    const msgEl = document.createElement("div");
    msgEl.className = `message ${role}`;

    const textSpan = document.createElement("span");
    textSpan.className = "msg-text";

    if (isVoice) {
      textSpan.innerHTML = `<span style="opacity: 0.6; margin-right: 4px;">🎙️</span>${escapeHtml(text)}`;
    } else {
      textSpan.textContent = text;
    }

    msgEl.appendChild(textSpan);
    messageList.appendChild(msgEl);
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

      // Send to Python backend
      sendWsMessage({ type: "chat", text: userText });
      setStatus("thinking", "Thinking...");
    });
  }

  // =========================================================================
  // 8. INITIAL BOOTSTRAP
  // =========================================================================
  connectWebSocket();
})();
