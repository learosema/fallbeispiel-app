(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;

  // ---------- Einstellungen ----------
  const DEFAULTS = { rate: 1, speak: true, handsfree: false, mode: "minute", callsign: "EVT1", dispatcher: "RotkreuzHamburg", tips: true, keepAwake: true };
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

  // ---------- Display anlassen ----------
  // Während eines Falls darf das Display nicht ausgehen, sonst hält Android Mikrofon, Vorlesen und Takt an.
  // Der Browser gibt die Sperre selbst frei, wenn die Seite in den Hintergrund geht; bei Rückkehr neu anfordern.
  let wakeLock = null;
  async function keepAwake() {
    if (!settings.keepAwake || !scenario || wakeLock || !("wakeLock" in navigator) || document.visibilityState !== "visible") return;
    try {
      wakeLock = await navigator.wakeLock.request("screen");
      wakeLock.addEventListener("release", () => { wakeLock = null; });
      if (!scenario || !settings.keepAwake) releaseAwake(); // inzwischen zurück zur Auswahl
    } catch { wakeLock = null; /* z. B. Energiesparmodus: dann eben ohne */ }
  }
  function releaseAwake() { if (wakeLock) { wakeLock.release().catch(() => {}); wakeLock = null; } }
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") { keepAwake(); resumeSpeech(); } else pauseSpeech();
  });

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
    releaseAwake();
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
    keepAwake();
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

  // Android-Chrome hält die Sprachausgabe an, wenn die App im Hintergrund war; dann kommt onend nie
  // und der Zug bliebe „beschäftigt“. Deshalb: resume() vor jedem Sprechen und ein Wachhund, der aufgibt.
  let lastSpokeAt = 0;    // Ende der letzten Ausgabe – iOS braucht danach eine kurze Pause fürs Mikrofon
  let speechEpoch = 0;    // zählt hoch, wenn die App in den Hintergrund geht: Rest der Antwort nicht mehr vorlesen
  function speak(text, pitch = 1) {
    return new Promise((resolve) => {
      if (!settings.speak || !("speechSynthesis" in window) || document.hidden) return resolve();
      speechSynthesis.cancel();
      const spoken = forSpeech(text.replace(/[*_#`]/g, ""));
      const u = new SpeechSynthesisUtterance(spoken);
      u.lang = "de-DE";
      if (germanVoice) u.voice = germanVoice;
      u.rate = Number(settings.rate) || 1;
      u.pitch = pitch;
      let done = false, started = false;
      const finish = () => {
        if (done) return;
        done = true;
        clearTimeout(noStart); clearTimeout(maxTime);
        lastSpokeAt = Date.now();
        resolve();
      };
      const giveUp = () => { if (!done) { try { speechSynthesis.cancel(); } catch {} finish(); } };
      // fängt gar nicht an → hängt; großzügige Obergrenze (≈ 100 Wörter/Minute) für den Fall, dass onend fehlt
      const noStart = setTimeout(() => { if (!started) giveUp(); }, 4000);
      const maxTime = setTimeout(giveUp, 4000 + (spoken.split(/\s+/).length * 600) / u.rate);
      u.onstart = () => { started = true; };
      u.onend = u.onerror = finish;
      try { speechSynthesis.resume(); } catch {}
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
    const epoch = speechEpoch;
    for (const seg of segs) {
      if (!scenario || epoch !== speechEpoch) return;
      const { text, narration } = spokenText(seg);
      if (text) await speak(text, narration ? PITCH.Befund : PITCH[seg.who] || 1);
    }
  }

  // ---------- Spracheingabe ----------
  const IOS = /iP(hone|ad|od)/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const STANDALONE = navigator.standalone === true || window.matchMedia?.("(display-mode: standalone)").matches;
  const FATAL = ["not-allowed", "service-not-allowed", "audio-capture", "language-not-supported"];
  let restartTimer = null;
  let quickEnds = 0;      // Erkennungen hintereinander, die sofort wieder endeten (iOS) – sonst startet Freisprechen im Kreis

  function setMicUi(on) {
    $("micBtn").classList.toggle("listening", on);
    $("micBtn").setAttribute("aria-pressed", on ? "true" : "false");
  }
  function scheduleListening(ms) {
    clearTimeout(restartTimer);
    restartTimer = setTimeout(() => { restartTimer = null; startListening(); }, ms);
  }
  function errorText(code) {
    if (code === "service-not-allowed" && IOS)
      return STANDALONE
        ? "Spracherkennung geht in der Home-Bildschirm-App auf dem iPhone oft nicht. Bitte die Seite in Safari öffnen – oder tippen."
        : "Spracherkennung nicht verfügbar. Auf dem iPhone: Einstellungen → Allgemein → Tastatur → „Diktierfunktion“ einschalten.";
    if (code === "not-allowed" || code === "service-not-allowed") return "Mikrofon nicht erlaubt. Bitte in den Browser-Einstellungen freigeben – oder einmal aufs Mikrofon tippen.";
    if (code === "audio-capture") return "Kein Mikrofon gefunden oder gerade von einer anderen App belegt.";
    return "Spracherkennung: " + code;
  }

  function startListening({ byUser = false } = {}) {
    if (!SR) { setStatus("Spracherkennung wird von diesem Browser nicht unterstützt. Bitte tippen.", true); return; }
    if (listening || busy || document.hidden) return;
    clearTimeout(restartTimer); restartTimer = null;
    if (byUser) quickEnds = 0;
    if ("speechSynthesis" in window && (speechSynthesis.speaking || speechSynthesis.pending)) { speechSynthesis.cancel(); lastSpokeAt = Date.now(); }
    // iOS: direkt nach dem Vorlesen ist die Audio-Sitzung noch auf Wiedergabe – dann hört die Erkennung nichts
    const wait = IOS ? lastSpokeAt + 600 - Date.now() : 0;
    if (wait > 0) { scheduleListening(wait); return; }
    startClock();

    const rec = new SR();
    recognition = rec;
    rec.lang = "de-DE";
    rec.interimResults = true;
    rec.continuous = false;
    let finalText = "", lastError = "", recStartedAt = 0, silence = null;
    listening = true; // schon jetzt, damit kein zweiter Start dazwischenkommt
    const noStart = setTimeout(() => { if (!recStartedAt && recognition === rec) { try { rec.abort(); } catch {} } }, 5000);

    rec.onstart = () => { recStartedAt = Date.now(); setMicUi(true); setStatus("Ich höre zu …"); };
    rec.onresult = (e) => {
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const t = e.results[i][0].transcript;
        if (e.results[i].isFinal) finalText += t; else interim += t;
      }
      $("textInput").value = (finalText + interim).trim();
      // iOS meldet oft kein isFinal und hört nicht von selbst auf: nach kurzer Pause selbst beenden
      if (IOS) { clearTimeout(silence); silence = setTimeout(() => { try { rec.stop(); } catch {} }, 1500); }
    };
    rec.onerror = (e) => { lastError = e.error || ""; };
    rec.onend = () => {
      clearTimeout(noStart); clearTimeout(silence);
      if (recognition !== rec) return; // veraltet
      recognition = null;
      listening = false;
      setMicUi(false);
      const text = (finalText || $("textInput").value).trim();
      if (text) { quickEnds = 0; $("textInput").value = ""; send(text); return; }
      if (FATAL.includes(lastError)) { setStatus(errorText(lastError), true); return; }
      if (lastError && !["no-speech", "aborted"].includes(lastError)) setStatus(errorText(lastError), true);
      else setStatus("");
      if (tickDue() && !busy) { turn({ tick: true }); return; }
      if (!settings.handsfree || !scenario || busy || debriefDone || document.hidden) return;
      // Normales „nichts gesagt“ dauert einige Sekunden. Endet es sofort, ist die Erkennung gestört:
      // mit wachsender Pause neu versuchen und nach ein paar Fehlversuchen Freisprechen anhalten.
      const quick = !recStartedAt || Date.now() - recStartedAt < 2000;
      quickEnds = quick ? quickEnds + 1 : 0;
      if (quickEnds >= 3) {
        quickEnds = 0;
        setStatus(IOS && STANDALONE
          ? "Spracherkennung hört nichts. In der Home-Bildschirm-App auf dem iPhone klappt sie oft nicht – bitte in Safari öffnen oder aufs Mikrofon tippen."
          : "Spracherkennung hört nichts – Freisprechen pausiert. Tippe aufs Mikrofon, um weiterzumachen.", true);
        return;
      }
      scheduleListening(300 + quickEnds * 1200);
    };
    try { rec.start(); }
    catch { clearTimeout(noStart); recognition = null; listening = false; setMicUi(false); }
  }
  function stopListening() { if (recognition) { try { recognition.stop(); } catch {} } }
  function abortListening() {
    clearTimeout(restartTimer); restartTimer = null;
    if (recognition) { const r = recognition; recognition = null; r.onend = null; try { r.abort(); } catch {} }
    listening = false;
    setMicUi(false);
  }
  function stopAll() {
    abortListening();
    if ("speechSynthesis" in window) speechSynthesis.cancel();
    setStatus("");
  }
  // App geht in den Hintergrund: Mikrofon und Vorlesen sauber beenden, statt sie halb hängen zu lassen …
  function pauseSpeech() {
    speechEpoch++;
    abortListening();
    if ("speechSynthesis" in window) speechSynthesis.cancel();
  }
  // … und bei Rückkehr neu aufsetzen (sonst musste man auf Android erst Schalter aus- und einschalten)
  function resumeSpeech() {
    if ("speechSynthesis" in window) { try { speechSynthesis.cancel(); speechSynthesis.resume(); } catch {} pickVoice(); }
    quickEnds = 0;
    if (settings.handsfree && scenario && !busy && !debriefDone) scheduleListening(400);
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
    // Musterlösung erst nach der Auswertung anbieten – in neuem Tab, damit der Einsatz erhalten bleibt
    const li = document.createElement("li");
    li.className = "msg sys";
    const a = document.createElement("a");
    a.href = "loesungen.html#" + encodeURIComponent(scenario.id);
    a.target = "_blank";
    a.rel = "noopener";
    a.textContent = "Musterlösung zu diesem Fall ansehen";
    li.appendChild(a);
    $("log").appendChild(li);
    scrollLog();
    speak("Algorithmus " + result.verdict + ".");
  }

  // ---------- Einstellungen-Dialog ----------
  function openSettings() {
    $("rate").value = settings.rate;
    $("rateOut").textContent = Number(settings.rate).toFixed(2);
    $("speak").checked = settings.speak;
    $("tips").checked = settings.tips !== false;
    $("keepAwake").checked = settings.keepAwake !== false;
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
      settings.keepAwake = $("keepAwake").checked;
      settings.callsign = $("callsign").value.trim() || DEFAULTS.callsign;
      settings.dispatcher = $("dispatcher").value.trim() || DEFAULTS.dispatcher;
      saveSettings();
      if (settings.keepAwake) keepAwake(); else releaseAwake();
    }
  });
  document.querySelectorAll('input[name="mode"]').forEach((r) => {
    r.checked = r.value === settings.mode;
    r.addEventListener("change", () => { settings.mode = r.value; saveSettings(); });
  });
  $("backBtn").addEventListener("click", showHome);
  $("micBtn").addEventListener("click", () => (listening ? stopListening() : startListening({ byUser: true })));
  $("handsfree").addEventListener("change", (e) => {
    settings.handsfree = e.target.checked; saveSettings();
    if (settings.handsfree && !busy) startListening({ byUser: true });
    else if (!settings.handsfree) clearTimeout(restartTimer);
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
