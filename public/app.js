(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;

  // ---------- Einstellungen ----------
  const DEFAULTS = { accessCode: "", rate: 1, speak: true, handsfree: false, mode: "minute", callsign: "EVT1", dispatcher: "RotkreuzHamburg" };
  let settings = { ...DEFAULTS };
  try {
    settings = { ...DEFAULTS, ...JSON.parse(localStorage.getItem("settings") || "{}") };
    // Altlast aus der Version mit Browser-Key entfernen
    for (const k of ["apiKey", "baseUrl", "model"]) delete settings[k];
    localStorage.setItem("settings", JSON.stringify(settings));
  } catch {}
  const saveSettings = () => { try { localStorage.setItem("settings", JSON.stringify(settings)); } catch {} };

  // ---------- Zustand ----------
  let SCENARIOS = [];
  let scenario = null;
  let mode = "minute";    // "minute" = nur 1. Minute, "full" = ganzer Fall
  let busy = false;
  let listening = false;
  let recognition = null;
  let debriefDone = false;

  // Zeitmessung: zählt nur die Zeit der Nutzerin, nicht das Warten auf/Vorlesen der Antwort
  let startedAt = null;
  let busyMs = 0;
  let busySince = null;
  let userLog = [];       // { t: Sekunden, text } – geht bei jeder Äußerung komplett an den Server
  const fmt = (s) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;
  function netSec() {
    if (!startedAt) return 0;
    const now = Date.now();
    return Math.max(0, (now - startedAt - busyMs - (busySince ? now - busySince : 0)) / 1000);
  }
  const startClock = () => { if (!startedAt) startedAt = Date.now(); };
  setInterval(() => { if (scenario && startedAt && !debriefDone) $("timer").textContent = "⏱ " + fmt(netSec()); }, 500);

  // ---------- UI ----------
  function setStatus(text, error = false) {
    const el = $("status");
    el.textContent = text || "";
    el.classList.toggle("error", error);
  }
  function addMsg(text, cls) {
    const d = document.createElement("div");
    d.className = "msg " + cls;
    d.textContent = text;
    $("log").appendChild(d);
    $("log").scrollTop = $("log").scrollHeight;
    return d;
  }

  // Antwort der Simulation in Sprecher-Zeilen zerlegen: "Patient: …", "Kollege: …", "Umstehende: …", "Befund: …"
  const WHO_CLASS = { Patient: "them", Kollege: "them kollege", Umstehende: "them", Befund: "sys befund", Leitstelle: "them funk", AED: "them funk", Rettungsdienst: "them kollege" };
  const PITCH = { Patient: 1, Kollege: 0.8, Umstehende: 1.2, Befund: 0.9, Leitstelle: 0.65, AED: 0.6, Rettungsdienst: 0.85 };
  function addReply(segs) {
    for (const seg of segs) {
      const d = document.createElement("div");
      d.className = "msg " + WHO_CLASS[seg.who];
      const who = document.createElement("span");
      who.className = "who";
      who.textContent = seg.who;
      d.append(who, document.createTextNode(seg.text));
      $("log").appendChild(d);
    }
    $("log").scrollTop = $("log").scrollHeight;
  }

  function showHome() {
    stopAll();
    scenario = null;
    $("home").hidden = false;
    $("session").hidden = true;
    $("backBtn").hidden = true;
    $("title").textContent = "Fallbeispiel xABCDE";
  }
  async function loadScenarios() {
    try {
      const res = await fetch("/api/scenarios");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      SCENARIOS = await res.json();
      renderScenarios();
    } catch (err) {
      $("scenarioList").textContent = "Die Fälle konnten nicht geladen werden (" + err.message + "). Läuft der Server?";
    }
  }
  function renderScenarios() {
    const list = $("scenarioList");
    list.innerHTML = "";
    const items = [...SCENARIOS, { id: "random", group: "Zufall", letter: "?", title: "Zufälliger Fall", teaser: "Überrasch mich" }];
    let lastGroup = null;
    for (const s of items) {
      const group = s.group || "Grundlagen";
      if (group !== lastGroup) {
        const h = document.createElement("h2");
        h.className = "group";
        h.textContent = group;
        list.appendChild(h);
        lastGroup = group;
      }
      const b = document.createElement("button");
      b.className = "scenario";
      b.innerHTML = `<span class="letter"></span><span><strong></strong><small></small></span>`;
      b.querySelector(".letter").textContent = s.letter;
      b.querySelector(".letter").classList.toggle("small", s.letter.length > 1);
      b.querySelector("strong").textContent = s.title;
      b.querySelector("small").textContent = s.teaser;
      b.addEventListener("click", () => {
        const pick = s.id === "random" ? SCENARIOS[Math.floor(Math.random() * SCENARIOS.length)] : s;
        startSession(pick, s.id === "random");
      });
      list.appendChild(b);
    }
  }

  function startSession(s, hideTitle) {
    scenario = s;
    mode = settings.mode === "full" ? "full" : "minute";
    debriefDone = false;
    startedAt = null; busyMs = 0; busySince = null; userLog = [];
    $("timer").textContent = "⏱ 0:00";
    $("log").innerHTML = "";
    $("home").hidden = true;
    $("session").hidden = false;
    $("backBtn").hidden = false;
    $("title").textContent = hideTitle ? "Zufälliger Fall" : s.title;
    $("handsfree").checked = settings.handsfree;
    addMsg(s.dispatch.replace(/^Einsatzmeldung:\s*/, "Einsatzmeldung: "), "sys");
    addMsg(mode === "minute"
      ? `Du triffst mit deinem Kollegen ein (Funkrufname ${settings.callsign}, Leitstelle ${settings.dispatcher}). Übe die 1. Minute nach SANmemo bis zum Funkspruch.`
      : "Du triffst mit deinem Kollegen ein. Beginne mit der 1. Minute, danach geht der Einsatz weiter.", "sys");
    speak(s.dispatch.replace(/^Einsatzmeldung:\s*/, "Einsatzmeldung: "));
  }

  // ---------- Sprachausgabe ----------
  let germanVoice = null;
  function pickVoice() {
    const v = speechSynthesis.getVoices().filter((x) => x.lang && x.lang.toLowerCase().startsWith("de"));
    germanVoice = v.find((x) => /enhanced|premium|natural/i.test(x.name)) || v[0] || null;
  }
  if ("speechSynthesis" in window) { pickVoice(); speechSynthesis.onvoiceschanged = pickVoice; }

  function speak(text, pitch = 1) {
    return new Promise((resolve) => {
      if (!settings.speak || !("speechSynthesis" in window)) return resolve();
      speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(text.replace(/[*_#`]/g, ""));
      u.lang = "de-DE";
      if (germanVoice) u.voice = germanVoice;
      u.rate = Number(settings.rate) || 1;
      u.pitch = pitch;
      u.onend = u.onerror = () => resolve();
      speechSynthesis.speak(u);
    });
  }
  async function speakReply(segs) {
    // Regieanweisungen in Klammern werden angezeigt, aber nicht vorgelesen
    for (const seg of segs) {
      if (!scenario) return;
      const spoken = seg.text.replace(/\([^)]*\)/g, "").trim();
      if (spoken) await speak(spoken, PITCH[seg.who] || 1);
    }
  }

  // ---------- Spracheingabe ----------
  function startListening() {
    if (!SR) { setStatus("Spracherkennung wird von diesem Browser nicht unterstützt. Bitte tippen.", true); return; }
    if (listening || busy) return;
    if ("speechSynthesis" in window) speechSynthesis.cancel();
    startClock();
    recognition = new SR();
    recognition.lang = "de-DE";
    recognition.interimResults = true;
    recognition.continuous = false;
    let finalText = "";
    recognition.onstart = () => { listening = true; $("micBtn").classList.add("listening"); setStatus("Ich höre zu …"); };
    recognition.onresult = (e) => {
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const t = e.results[i][0].transcript;
        if (e.results[i].isFinal) finalText += t; else interim += t;
      }
      $("textInput").value = (finalText + interim).trim();
    };
    recognition.onerror = (e) => {
      if (e.error === "not-allowed" || e.error === "service-not-allowed") setStatus("Mikrofon nicht erlaubt. Bitte in den Browser-Einstellungen freigeben.", true);
      else if (e.error !== "no-speech" && e.error !== "aborted") setStatus("Spracherkennung: " + e.error, true);
    };
    recognition.onend = () => {
      listening = false;
      $("micBtn").classList.remove("listening");
      const text = (finalText || $("textInput").value).trim();
      if (text) { $("textInput").value = ""; send(text); }
      else { setStatus(""); if (settings.handsfree && scenario && !busy) setTimeout(startListening, 300); }
    };
    try { recognition.start(); } catch { /* läuft schon */ }
  }
  function stopListening() { if (recognition) { try { recognition.stop(); } catch {} } }
  function stopAll() {
    if (recognition) { recognition.onend = null; try { recognition.abort(); } catch {} }
    listening = false;
    $("micBtn").classList.remove("listening");
    if ("speechSynthesis" in window) speechSynthesis.cancel();
    setStatus("");
  }

  // ---------- Backend ----------
  const payload = () => ({ scenario: scenario.id, mode, callsign: settings.callsign, dispatcher: settings.dispatcher, log: [...userLog] });
  async function api(path, body = payload()) {
    const res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(settings.accessCode ? { "x-access-code": settings.accessCode } : {}) },
      body: JSON.stringify(body),
    });
    let data = {};
    try { data = await res.json(); } catch { /* keine JSON-Antwort */ }
    if (res.status === 401) { openSettings(); throw new Error(data.error || "Zugangscode fehlt oder ist falsch."); }
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    return data;
  }

  function beginBusy(text) { busy = true; busySince = Date.now(); setStatus(text); }
  function endBusy() { busyMs += Date.now() - busySince; busySince = null; busy = false; }

  async function send(text) {
    if (!scenario || busy) return;
    startClock();
    userLog.push({ t: Math.round(netSec() * 10) / 10, text });
    addMsg(text, "me");
    beginBusy("…");
    let ok = false;
    try {
      const data = await api("/api/turn");
      setStatus("");
      addReply(data.lines);
      await speakReply(data.lines);  // Vorlesen zählt nicht zur Nettozeit
      ok = true;
    } catch (err) {
      userLog.pop();
      setStatus("Fehler: " + err.message, true);
    } finally {
      endBusy();
    }
    if (ok && settings.handsfree && scenario) startListening();
  }

  async function debrief() {
    if (!scenario || busy || debriefDone) return;
    stopAll();
    if (userLog.length === 0) { setStatus("Starte erst den Einsatz, sonst gibt es nichts auszuwerten.", true); return; }
    debriefDone = true;
    const current = scenario;
    const body = payload();  // Stand festhalten – das Feedback kommt evtl. erst nach einem Fallwechsel zurück
    beginBusy("Werte aus …");
    let result, text;
    try {
      ({ result, text } = await api("/api/debrief", body));
    } catch (err) {
      debriefDone = false;
      setStatus("Fehler: " + err.message, true);
      return;
    } finally {
      endBusy();  // das KI-Feedback kann dauern – die App bleibt währenddessen bedienbar
    }
    addMsg(text, "debrief");
    setStatus("Die KI bewertet den Einsatz …");
    speak("Algorithmus " + result.verdict + ".");
    try {
      const fb = await api("/api/feedback", body);
      if (scenario !== current) return;
      addMsg(fb.text, "debrief");
      setStatus(fb.ai ? "" : "Keine KI-Bewertung konfiguriert, nur die regelbasierte Auswertung.");
    } catch (err) {
      if (scenario === current) setStatus(err.message, true);
    }
  }

  // ---------- Einstellungen-Dialog ----------
  function openSettings() {
    $("accessCode").value = settings.accessCode;
    $("rate").value = settings.rate;
    $("rateOut").textContent = Number(settings.rate).toFixed(2);
    $("speak").checked = settings.speak;
    $("callsign").value = settings.callsign;
    $("dispatcher").value = settings.dispatcher;
    $("settings").showModal();
  }

  // ---------- Events ----------
  $("settingsBtn").addEventListener("click", openSettings);
  $("rate").addEventListener("input", (e) => { $("rateOut").textContent = Number(e.target.value).toFixed(2); });
  $("settingsForm").addEventListener("submit", (e) => {
    if (e.submitter && e.submitter.value === "save") {
      settings.accessCode = $("accessCode").value.trim();
      settings.rate = $("rate").value;
      settings.speak = $("speak").checked;
      settings.callsign = $("callsign").value.trim() || DEFAULTS.callsign;
      settings.dispatcher = $("dispatcher").value.trim() || DEFAULTS.dispatcher;
      saveSettings();
    }
  });
  document.querySelectorAll('input[name="mode"]').forEach((r) => {
    r.checked = r.value === settings.mode;
    r.addEventListener("change", () => { settings.mode = r.value; saveSettings(); });
  });
  $("backBtn").addEventListener("click", showHome);
  $("micBtn").addEventListener("click", () => (listening ? stopListening() : startListening()));
  $("handsfree").addEventListener("change", (e) => {
    settings.handsfree = e.target.checked; saveSettings();
    if (settings.handsfree && !busy) startListening();
  });
  $("inputBar").addEventListener("submit", (e) => {
    e.preventDefault();
    const t = $("textInput").value.trim();
    if (!t) return;
    $("textInput").value = "";
    stopAll();
    send(t);
  });
  $("debriefBtn").addEventListener("click", debrief);

  loadScenarios();
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
})();
