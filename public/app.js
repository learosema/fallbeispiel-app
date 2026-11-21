(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;

  // ---------- Einstellungen ----------
  const DEFAULTS = { rate: 1, speak: true, handsfree: false, mode: "minute", callsign: "EVT1", dispatcher: "RotkreuzHamburg", tips: true };
  let settings = { ...DEFAULTS };
  try {
    settings = { ...DEFAULTS, ...JSON.parse(localStorage.getItem("settings") || "{}") };
    // Altlasten aus früheren Versionen entfernen (Browser-Key, Zugangscode für die KI-Bewertung)
    for (const k of ["apiKey", "baseUrl", "model", "accessCode"]) delete settings[k];
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
  let nextEventAt = null; // Nettozeit, zu der laut Server das nächste Ereignis fällig ist (z. B. AED-Analyse)

  // Zeitmessung: zählt nur die Zeit der Nutzerin, nicht das Warten auf/Vorlesen der Antwort
  let startedAt = null;
  let busyMs = 0;
  let busySince = null;
  let userLog = [];       // { t: Sekunden, text } bzw. { t, text: "", tick: true } – geht jedes Mal komplett an den Server
  const fmt = (s) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;
  function netSec() {
    if (!startedAt) return 0;
    const now = Date.now();
    return Math.max(0, (now - startedAt - busyMs - (busySince ? now - busySince : 0)) / 1000);
  }
  const startClock = () => { if (!startedAt) startedAt = Date.now(); };
  setInterval(() => { if (scenario && startedAt && !debriefDone) $("timer").textContent = fmt(netSec()); }, 500);

  // Takt: Die Simulation läuft weiter, auch wenn gerade niemand spricht (AED alle 2 Minuten, Auskühlen …)
  const tickDue = () => scenario && startedAt && !debriefDone && nextEventAt != null && netSec() >= nextEventAt;
  setInterval(() => {
    if (!tickDue() || busy) return;
    if (listening) {
      // nur unterbrechen, wenn gerade nichts erkannt wurde – onend schickt dann den Takt
      if (!$("textInput").value.trim() && recognition) { try { recognition.stop(); } catch {} }
      return;
    }
    turn({ tick: true });
  }, 500);

  // ---------- UI ----------
  const APP_TITLE = "Fallbeispiel xABCDE";
  let lastScenarioButton = null; // für den Fokus beim Zurückgehen

  function setStatus(text, error = false) {
    const el = $("status");
    el.setAttribute("aria-live", error ? "assertive" : "polite"); // Fehler sofort ansagen
    el.textContent = text || "";
    el.classList.toggle("error", error);
  }
  function scrollLog() { $("log").scrollTop = $("log").scrollHeight; }
  function addMsg(text, cls) {
    const li = document.createElement("li");
    li.className = "msg " + cls;
    li.textContent = text;
    $("log").appendChild(li);
    scrollLog();
    return li;
  }

  // Antwort der Simulation: eine Zeile pro Sprecher (Patient, Kollege, Umstehende, Befund, Leitstelle, AED, Rettungsdienst)
  const WHO_CLASS = { Patient: "them", Kollege: "them kollege", Umstehende: "them", Befund: "sys befund", Leitstelle: "them funk", AED: "them funk", Rettungsdienst: "them kollege" };
  const PITCH = { Patient: 1, Kollege: 0.8, Umstehende: 1.2, Befund: 0.9, Leitstelle: 0.65, AED: 0.6, Rettungsdienst: 0.85 };
  function addReply(segs) {
    for (const seg of segs) {
      const li = document.createElement("li");
      li.className = "msg " + (WHO_CLASS[seg.who] || "them");
      const who = document.createElement("span");
      who.className = "who";
      who.textContent = seg.who;
      const colon = document.createElement("span");
      colon.className = "visually-hidden";
      colon.textContent = ": ";
      who.append(colon);
      li.append(who, document.createTextNode(seg.text));
      $("log").appendChild(li);
    }
    scrollLog();
  }

  function setTitle(text) {
    $("title").textContent = text;
    document.title = text === APP_TITLE ? APP_TITLE : `${text} – ${APP_TITLE}`;
  }
  function showHome() {
    stopAll();
    scenario = null;
    $("home").hidden = false;
    $("session").hidden = true;
    $("backBtn").hidden = true;
    setTitle(APP_TITLE);
    (lastScenarioButton && lastScenarioButton.isConnected ? lastScenarioButton : $("title")).focus();
  }
  async function loadScenarios() {
    const list = $("scenarioList");
    try {
      const res = await fetch("/api/scenarios");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      SCENARIOS = await res.json();
      renderScenarios();
    } catch (err) {
      list.innerHTML = "";
      const p = document.createElement("p");
      p.className = "lead";
      p.setAttribute("role", "alert");
      p.textContent = "Die Fälle konnten nicht geladen werden (" + err.message + "). Läuft der Server?";
      list.append(p);
    } finally {
      list.setAttribute("aria-busy", "false");
    }
  }
  function renderScenarios() {
    const list = $("scenarioList");
    list.innerHTML = "";
    const items = [...SCENARIOS, { id: "random", group: "Zufall", letter: "?", title: "Zufälliger Fall", teaser: "Überrasch mich" }];
    const groups = new Map();
    for (const s of items) {
      const g = s.group || "Grundlagen";
      if (!groups.has(g)) groups.set(g, []);
      groups.get(g).push(s);
    }
    let n = 0;
    for (const [group, scenarios] of groups) {
      const section = document.createElement("section");
      const h = document.createElement("h3");
      h.className = "group";
      h.id = `group-${n++}`;
      h.textContent = group;
      section.setAttribute("aria-labelledby", h.id);
      const ul = document.createElement("ul");
      for (const s of scenarios) {
        const li = document.createElement("li");
        const b = document.createElement("button");
        b.type = "button";
        b.className = "scenario";
        b.innerHTML = `<span class="letter" aria-hidden="true"></span><span><strong></strong><small></small></span>`;
        b.querySelector(".letter").textContent = s.letter;
        b.querySelector(".letter").classList.toggle("small", s.letter.length > 1);
        b.querySelector("strong").textContent = s.title;
        b.querySelector("small").textContent = s.teaser;
        b.addEventListener("click", () => {
          lastScenarioButton = b;
          const pick = s.id === "random" ? SCENARIOS[Math.floor(Math.random() * SCENARIOS.length)] : s;
          startSession(pick, s.id === "random");
        });
        li.append(b);
        ul.append(li);
      }
      section.append(h, ul);
      list.append(section);
    }
  }

  function startSession(s, hideTitle) {
    scenario = s;
    mode = settings.mode === "full" ? "full" : "minute";
    debriefDone = false;
    startedAt = null; busyMs = 0; busySince = null; userLog = []; nextEventAt = null;
    $("timer").textContent = "0:00";
    $("log").innerHTML = "";
    setStatus("");
    $("home").hidden = true;
    $("session").hidden = false;
    $("backBtn").hidden = false;
    setTitle(hideTitle ? "Zufälliger Fall" : s.title);
    $("title").focus(); // Screenreader: neuer Fall wird angesagt
    $("handsfree").checked = settings.handsfree;
    const dispatch = s.dispatch.replace(/^Einsatzmeldung:\s*/, "Einsatzmeldung: ");
    const intro = mode === "minute"
      ? `Du triffst mit deinem Kollegen ein (Funkrufname ${settings.callsign}, Leitstelle ${settings.dispatcher}). Übe die 1. Minute nach SANmemo bis zum Funkspruch.`
      : "Du triffst mit deinem Kollegen ein. Beginne mit der 1. Minute, danach geht der Einsatz weiter.";
    addMsg(dispatch, "sys");
    addMsg(intro, "sys");
    // nacheinander vorlesen (speak() bricht laufende Ausgaben ab, deshalb abwarten)
    (async () => {
      for (const text of [dispatch, intro]) {
        if (scenario !== s) return;
        await speak(text, PITCH.Befund);
      }
    })();
  }

  // ---------- Sprachausgabe ----------
  let germanVoice = null;
  function pickVoice() {
    const v = speechSynthesis.getVoices().filter((x) => x.lang && x.lang.toLowerCase().startsWith("de"));
    germanVoice = v.find((x) => /enhanced|premium|natural/i.test(x.name)) || v[0] || null;
  }
  if ("speechSynthesis" in window) { pickVoice(); speechSynthesis.onvoiceschanged = pickVoice; }

  // Buchstabieren beim Vorlesen: Rufname „EVT1“ → „E Fau Te 1“ (sonst liest die Stimme ihn als Wort),
  // dazu Abkürzungen, die man buchstabiert spricht. NEF bleibt ein Wort („Neff“).
  const LETTERS = { A: "A", B: "Be", C: "Ze", D: "De", E: "E", F: "Eff", G: "Ge", H: "Ha", I: "I", J: "Jott", K: "Ka", L: "El",
    M: "Em", N: "En", O: "O", P: "Pe", Q: "Ku", R: "Er", S: "Ess", T: "Te", U: "U", V: "Fau", W: "We", X: "Ix", Y: "Üpsilon", Z: "Zett",
    Ä: "Ä", Ö: "Ö", Ü: "Ü" };
  const SPELLED = ["RTW", "KTW", "DRK", "AED", "HWS", "SHT", "GCS", "EKG", "AVPU", "BZ", "RR"];
  // Aussprache, wo die Stimme sonst danebenliegt (Ergänzungen einfach hier eintragen)
  const PRONOUNCE = [
    [/\bSAN-?memo\b/gi, "San-Memo"],
    // „1. Minute“ liest Android als Satzende mit „1“
    [/\b(der|einer)\s+1\.\s*Minute/g, "$1 ersten Minute"],
    [/\b1\.\s*Minute/g, "erste Minute"],
  ];
  const spell = (word) => [...word].map((ch) => LETTERS[ch.toUpperCase()] ?? ch).join(" ");
  function forSpeech(text) {
    let out = PRONOUNCE.reduce((s, [re, say]) => s.replace(re, say), text);
    const cs = String(settings.callsign || "").trim();
    if (/[A-Za-zÄÖÜäöü]/.test(cs)) {
      // Buchstaben und Ziffern des Rufnamens, im Text auch mit Leerzeichen dazwischen („EVT 1“)
      const parts = cs.match(/[A-Za-zÄÖÜäöü]+|\d+/g) || [];
      const re = new RegExp("\\b" + parts.map((p) => p.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("\\s?") + "\\b", "gi");
      // nur Kürzel buchstabieren („EVT“), Wörter wie „Florian“ nicht
      out = out.replace(re, () => parts.map((p) => (/\d/.test(p) || p.length > 4 ? p : spell(p))).join(" "));
    }
    out = out.replace(/([a-zäöü])([A-ZÄÖÜ])/g, "$1 $2"); // „RotkreuzHamburg“ → „Rotkreuz Hamburg“
    return out.replace(new RegExp("\\b(" + SPELLED.join("|") + ")\\b", "g"), (m) => spell(m));
  }

  function speak(text, pitch = 1) {
    return new Promise((resolve) => {
      if (!settings.speak || !("speechSynthesis" in window)) return resolve();
      speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(forSpeech(text.replace(/[*_#`]/g, "")));
      u.lang = "de-DE";
      if (germanVoice) u.voice = germanVoice;
      u.rate = Number(settings.rate) || 1;
      u.pitch = pitch;
      u.onend = u.onerror = () => resolve();
      speechSynthesis.speak(u);
    });
  }
  // Was vorgelesen wird:
  // - eine reine Handlung in Klammern wird erzählt: „Kollege: (übernimmt die HWS)“ → „Kollege übernimmt die HWS“
  // - kurze Tonangaben neben gesprochenem Text entfallen: „(aufgelöst) Er ist umgefallen!“ → „Er ist umgefallen!“
  function spokenText(seg) {
    const text = seg.text.trim();
    const action = text.match(/^\(([^)]*)\)\.?$/);
    if (action) return { text: seg.who === "Befund" ? action[1] : `${seg.who} ${action[1]}`, narration: true };
    return { text: text.replace(/\([^)]*\)/g, "").replace(/\s+/g, " ").trim(), narration: false };
  }
  async function speakReply(segs) {
    for (const seg of segs) {
      if (!scenario) return;
      const { text, narration } = spokenText(seg);
      if (text) await speak(text, narration ? PITCH.Befund : PITCH[seg.who] || 1);
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
    recognition.onstart = () => { listening = true; $("micBtn").classList.add("listening"); $("micBtn").setAttribute("aria-pressed", "true"); setStatus("Ich höre zu …"); };
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
      $("micBtn").setAttribute("aria-pressed", "false");
      const text = (finalText || $("textInput").value).trim();
      if (text) { $("textInput").value = ""; send(text); }
      else if (tickDue() && !busy) turn({ tick: true });
      else { setStatus(""); if (settings.handsfree && scenario && !busy) setTimeout(startListening, 300); }
    };
    try { recognition.start(); } catch { /* läuft schon */ }
  }
  function stopListening() { if (recognition) { try { recognition.stop(); } catch {} } }
  function stopAll() {
    if (recognition) { recognition.onend = null; try { recognition.abort(); } catch {} }
    listening = false;
    $("micBtn").classList.remove("listening");
    $("micBtn").setAttribute("aria-pressed", "false");
    if ("speechSynthesis" in window) speechSynthesis.cancel();
    setStatus("");
  }

  // ---------- Backend ----------
  const payload = () => ({ scenario: scenario.id, mode, callsign: settings.callsign, dispatcher: settings.dispatcher, tips: settings.tips !== false, log: [...userLog] });
  async function api(path, body = payload()) {
    const res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    let data = {};
    try { data = await res.json(); } catch { /* keine JSON-Antwort */ }
    if (!res.ok) throw Object.assign(new Error(data.error || `HTTP ${res.status}`), { status: res.status });
    return data;
  }

  function beginBusy(text) { busy = true; busySince = Date.now(); setStatus(text); }
  function endBusy() { busyMs += Date.now() - busySince; busySince = null; busy = false; }

  const send = (text) => turn({ text });

  async function turn({ text = "", tick = false }) {
    if (!scenario || busy) return;
    startClock();
    userLog.push(tick ? { t: Math.round(netSec() * 10) / 10, text: "", tick: true } : { t: Math.round(netSec() * 10) / 10, text });
    if (!tick) addMsg(text, "me");
    beginBusy(tick ? "" : "…");
    let ok = false;
    try {
      const data = await api("/api/turn");
      nextEventAt = data.next_event_at ?? null;
      setStatus("");
      addReply(data.lines);
      await speakReply(data.lines);  // Vorlesen zählt nicht zur Nettozeit
      ok = true;
    } catch (err) {
      userLog.pop();
      nextEventAt = null;  // keinen Takt-Sturm bei Serverfehlern
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
    beginBusy("Werte aus …");
    let result, text;
    try {
      ({ result, text } = await api("/api/debrief"));
    } catch (err) {
      debriefDone = false;
      setStatus("Fehler: " + err.message, true);
      return;
    } finally {
      endBusy();
    }
    addMsg(text, "debrief");
    speak("Algorithmus " + result.verdict + ".");
  }

  // ---------- Einstellungen-Dialog ----------
  function openSettings() {
    $("rate").value = settings.rate;
    $("rateOut").textContent = Number(settings.rate).toFixed(2);
    $("speak").checked = settings.speak;
    $("tips").checked = settings.tips !== false;
    $("callsign").value = settings.callsign;
    $("dispatcher").value = settings.dispatcher;
    $("settings").showModal();
  }

  // ---------- Events ----------
  $("settingsBtn").addEventListener("click", openSettings);
  $("rate").addEventListener("input", (e) => { $("rateOut").textContent = Number(e.target.value).toFixed(2); });
  $("settingsForm").addEventListener("submit", (e) => {
    if (e.submitter && e.submitter.value === "save") {
      settings.rate = $("rate").value;
      settings.speak = $("speak").checked;
      settings.tips = $("tips").checked;
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
