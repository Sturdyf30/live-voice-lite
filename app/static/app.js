const state = {
  stream: null,
  recorder: null,
  chunks: [],
  recording: false,
  busy: false,
  autoMode: false,
  audio: null,
  audioContext: null,
  analyser: null,
  vadFrame: null,
  speechSeen: false,
  silenceStartedAt: null,
  recordStartedAt: null,
  sessionId: localStorage.getItem("lvl-session") || crypto.randomUUID(),
};
localStorage.setItem("lvl-session", state.sessionId);

const el = {
  orb: document.querySelector("#orb"),
  status: document.querySelector("#status"),
  latency: document.querySelector("#latency"),
  mic: document.querySelector("#micButton"),
  micLabel: document.querySelector("#micLabel"),
  interrupt: document.querySelector("#interruptButton"),
  transcript: document.querySelector("#transcript"),
  reset: document.querySelector("#resetButton"),
  settings: document.querySelector("#settingsButton"),
  settingsPanel: document.querySelector("#settingsPanel"),
  voice: document.querySelector("#voiceInput"),
  speed: document.querySelector("#speedInput"),
  speedValue: document.querySelector("#speedValue"),
  auto: document.querySelector("#autoToggle"),
  backend: document.querySelector("#backendSummary"),
  textForm: document.querySelector("#textForm"),
  textInput: document.querySelector("#textInput"),
};

function setStatus(text, mode = "idle") {
  el.status.textContent = text;
  el.orb.className = `orb ${mode}`;
}

function addMessage(role, text) {
  const card = document.createElement("div");
  card.className = `message ${role}`;
  const label = document.createElement("span");
  label.className = "role";
  label.textContent = role === "user" ? "You" : role === "assistant" ? "Hermes" : "Error";
  const body = document.createElement("div");
  body.textContent = text;
  card.append(label, body);
  el.transcript.append(card);
  card.scrollIntoView({ behavior: "smooth", block: "end" });
}

async function ensureMic() {
  if (state.stream) return state.stream;
  state.stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
      channelCount: 1,
    },
  });
  return state.stream;
}

function stopPlayback() {
  if (state.audio) {
    state.audio.pause();
    state.audio.currentTime = 0;
    state.audio = null;
  }
  el.interrupt.classList.add("hidden");
}

async function startRecording() {
  if (state.recording || state.busy) return;
  stopPlayback();
  const stream = await ensureMic();
  const mimeCandidates = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus"];
  const mimeType = mimeCandidates.find(type => MediaRecorder.isTypeSupported(type)) || "";
  state.chunks = [];
  state.recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
  state.recorder.ondataavailable = event => {
    if (event.data.size) state.chunks.push(event.data);
  };
  state.recorder.onstop = submitRecording;
  state.recorder.start(150);
  state.recording = true;
  state.recordStartedAt = performance.now();
  state.speechSeen = false;
  state.silenceStartedAt = null;
  el.mic.classList.add("recording");
  el.micLabel.textContent = state.autoMode ? "Listening…" : "Release to send";
  setStatus("Listening…", "listening");
  if (state.autoMode) startVad(stream);
}

function stopRecording() {
  if (!state.recording || !state.recorder) return;
  state.recording = false;
  stopVad();
  el.mic.classList.remove("recording");
  el.micLabel.textContent = state.autoMode ? "Start listening" : "Hold to talk";
  if (state.recorder.state !== "inactive") state.recorder.stop();
}

function startVad(stream) {
  state.audioContext ||= new AudioContext();
  const source = state.audioContext.createMediaStreamSource(stream);
  state.analyser = state.audioContext.createAnalyser();
  state.analyser.fftSize = 1024;
  source.connect(state.analyser);
  const samples = new Uint8Array(state.analyser.fftSize);

  const tick = () => {
    if (!state.recording || !state.analyser) return;
    state.analyser.getByteTimeDomainData(samples);
    let energy = 0;
    for (const sample of samples) {
      const normalized = (sample - 128) / 128;
      energy += normalized * normalized;
    }
    const rms = Math.sqrt(energy / samples.length);
    const now = performance.now();

    if (rms > 0.035) {
      state.speechSeen = true;
      state.silenceStartedAt = null;
    } else if (state.speechSeen) {
      state.silenceStartedAt ||= now;
      if (now - state.silenceStartedAt > 500 && now - state.recordStartedAt > 700) {
        stopRecording();
        return;
      }
    }
    if (now - state.recordStartedAt > 45000) {
      stopRecording();
      return;
    }
    state.vadFrame = requestAnimationFrame(tick);
  };
  tick();
}

function stopVad() {
  if (state.vadFrame) cancelAnimationFrame(state.vadFrame);
  state.vadFrame = null;
  state.analyser = null;
}

async function submitRecording() {
  const duration = performance.now() - state.recordStartedAt;
  if (duration < 300 || state.chunks.length === 0) {
    setStatus("Hold a little longer and speak", "idle");
    return;
  }
  const blob = new Blob(state.chunks, { type: state.recorder.mimeType || "audio/webm" });
  const form = new FormData();
  form.append("audio", blob, blob.type.includes("ogg") ? "turn.ogg" : "turn.webm");
  form.append("session_id", state.sessionId);
  form.append("voice", el.voice.value.trim());
  form.append("speed", el.speed.value);
  await sendTurn("/api/turn/audio", { method: "POST", body: form });
}

async function sendText(text) {
  await sendTurn("/api/turn/text", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: state.sessionId,
      text,
      voice: el.voice.value.trim(),
      speed: Number(el.speed.value),
    }),
  });
}

async function sendTurn(url, options) {
  if (state.busy) return;
  state.busy = true;
  el.mic.disabled = true;
  setStatus(url.endsWith("audio") ? "Transcribing and thinking…" : "Thinking…", "thinking");
  el.latency.textContent = "";
  try {
    const response = await fetch(url, options);
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail || `Request failed (${response.status})`);
    addMessage("user", body.user_text);
    addMessage("assistant", body.assistant_text);
    const timing = body.timing || {};
    const parts = [];
    if (timing.stt_ms) parts.push(`STT ${(timing.stt_ms / 1000).toFixed(1)}s`);
    if (timing.llm_ms) parts.push(`Hermes ${(timing.llm_ms / 1000).toFixed(1)}s`);
    if (timing.tts_ms > 0) parts.push(`TTS ${(timing.tts_ms / 1000).toFixed(1)}s`);
    el.latency.textContent = parts.join(" · ");
    if (body.audio_url) {
      await playAudio(body.audio_url);
    } else {
      setStatus("Ready", "idle");
    }
  } catch (error) {
    addMessage("error", error.message);
    setStatus(error.message, "error");
  } finally {
    state.busy = false;
    el.mic.disabled = false;
  }
}

async function playAudio(url) {
  stopPlayback();
  state.audio = new Audio(`${url}?t=${Date.now()}`);
  el.interrupt.classList.remove("hidden");
  setStatus("Speaking…", "speaking");
  state.audio.onended = () => {
    state.audio = null;
    el.interrupt.classList.add("hidden");
    setStatus(state.autoMode ? "Click to speak again" : "Hold the button or Space to talk", "idle");
  };
  state.audio.onerror = () => {
    state.audio = null;
    el.interrupt.classList.add("hidden");
    setStatus("Reply is in the transcript", "idle");
  };
  await state.audio.play();
}

el.mic.addEventListener("pointerdown", event => {
  if (state.autoMode) return;
  event.preventDefault();
  startRecording().catch(error => setStatus(error.message, "error"));
});
window.addEventListener("pointerup", () => {
  if (!state.autoMode) stopRecording();
});
el.mic.addEventListener("click", () => {
  if (!state.autoMode) return;
  if (state.recording) stopRecording();
  else startRecording().catch(error => setStatus(error.message, "error"));
});

document.addEventListener("keydown", event => {
  if (event.code !== "Space" || event.repeat || state.autoMode) return;
  if (["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) return;
  event.preventDefault();
  startRecording().catch(error => setStatus(error.message, "error"));
});
document.addEventListener("keyup", event => {
  if (event.code !== "Space" || state.autoMode) return;
  if (["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) return;
  event.preventDefault();
  stopRecording();
});

el.interrupt.addEventListener("click", () => {
  stopPlayback();
  setStatus("Interrupted. Speak whenever you’re ready.", "idle");
});

el.auto.addEventListener("change", () => {
  state.autoMode = el.auto.checked;
  el.micLabel.textContent = state.autoMode ? "Start listening" : "Hold to talk";
  setStatus(state.autoMode ? "Click once, then speak" : "Hold the button or Space to talk", "idle");
});

el.speed.addEventListener("input", () => {
  el.speedValue.textContent = `${Number(el.speed.value).toFixed(2)}×`;
});

el.settings.addEventListener("click", () => {
  const hidden = el.settingsPanel.classList.toggle("hidden");
  el.settings.setAttribute("aria-expanded", String(!hidden));
});

el.reset.addEventListener("click", async () => {
  stopPlayback();
  await fetch(`/api/reset/${encodeURIComponent(state.sessionId)}`, { method: "POST" });
  state.sessionId = crypto.randomUUID();
  localStorage.setItem("lvl-session", state.sessionId);
  el.transcript.replaceChildren();
  el.latency.textContent = "";
  setStatus("New conversation", "idle");
});

el.textForm.addEventListener("submit", event => {
  event.preventDefault();
  const text = el.textInput.value.trim();
  if (!text || state.busy) return;
  el.textInput.value = "";
  sendText(text);
});

fetch("/api/health")
  .then(response => response.json())
  .then(body => {
    el.voice.value = body.tts.voice || el.voice.value;
    el.speed.value = body.tts.speed || el.speed.value;
    el.speedValue.textContent = `${Number(el.speed.value).toFixed(2)}×`;
    el.backend.textContent = `Brain: ${body.llm.model} at ${body.llm.base_url} · STT: ${body.stt.backend}/${body.stt.model} · TTS: ${body.tts.backend}/${body.tts.model}`;
  })
  .catch(() => { el.backend.textContent = "Backend health check failed."; });
