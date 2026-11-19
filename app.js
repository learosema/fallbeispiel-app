(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;

  // ---------- Einstellungen ----------
  const DEFAULTS = { baseUrl: "https://api.openai.com/v1", apiKey: "", model: "gpt-4o-mini", rate: 1, speak: true, handsfree: false };
  let settings = { ...DEFAULTS };
  try { settings = { ...DEFAULTS, ...JSON.parse(localStorage.getItem("settings") || "{}") }; } catch {}
  const saveSettings = () => { try { localStorage.setItem("settings", JSON.stringify(settings)); } catch {} };

  // ---------- Zustand ----------
  let scenario = null;
  let messages = [];      // ohne System-Prompt
  let busy = false;
  let listening = false;
  let recognition = null;
  let debriefDone = false;

  // ---------- Prompts ----------
  function systemPrompt(s) {
    return `Du bist die Simulation für ein Fallbeispiel-Training im Rettungsdienst (Ausbildung zur Sanitäterin). Die Nutzerin ist die Sanitäterin in Ausbildung und spricht per Sprache mit dir. Antworte immer auf Deutsch.

SZENARIO: ${s.title}
${s.dispatch}
${s.role}
${s.team ? "\nEINSATZSITUATION: " + s.team + " Sanitätsrucksack-Ausrüstung (Pulsoxymeter, RR-Gerät, BZ-Messgerät, Thermometer, Absaugpumpe, Sauerstoff, AED, Verbandmaterial, Schienen, Rettungsdecke, Stifneck) steht zur Verfügung, wenn sie es verlangt. Alles, was darüber hinausgeht (Medikamente, Infusionen, Entlastungspunktion), steht dem Fußtrupp nicht zur Verfügung.\n" : ""}
SZENE (Auskunft zu Sicherheit und Lage in der 1. Minute, nur auf Nachfrage bzw. wenn sie die Umgebung prüft): ${s.scene}

VERBORGENE FAKTEN (nur preisgeben, wenn die Nutzerin danach fragt, untersucht, misst oder Maßnahmen durchführt; niemals von dir aus aufzählen):
${s.hidden}

REGELN FÜR DEN EINSATZ:
- Bleib in der Rolle. Sprich als Patient:in oder Umstehende, in kurzen, natürlichen Sätzen (max. 2–3 Sätze), da deine Antwort vorgelesen wird. Kein Markdown, keine Aufzählungen, keine Emojis.
- Misst oder untersucht die Nutzerin etwas (Puls, Blutdruck, SpO2, Auskultation, BZ, Pupillen, Temperatur …), nenne den Befund knapp und sachlich in einem Satz, z. B. "Puls 124, schwach tastbar." Ergebnisse nur, wenn sie wirklich gemessen oder untersucht wird.
- Sagt sie nur "ich schaue nach den Atemwegen" o. Ä., gib den Befund dazu. Fragt sie vage, frage kurz nach, was genau sie tut.
- Gib keine Hinweise, was sie als Nächstes tun sollte, und lobe oder korrigiere nicht während des Einsatzes.
- Der Zustand entwickelt sich realistisch: Fehlende oder falsche Maßnahmen verschlechtern ihn, richtige Maßnahmen verbessern ihn.
- Ist die Übergabe an den Rettungsdienst/Notarzt oder der Transport erfolgt, schließe den Einsatz knapp ab und sag, dass sie jetzt die Auswertung starten kann.

SCHLÜSSELMASSNAHMEN (nur für die Auswertung): ${s.keyActions}`;
  }

  const DEBRIEF_PROMPT = `[AUSWERTUNG] Der Einsatz ist beendet. Verlasse die Rolle und bewerte nüchtern und wohlwollend, ob die Nutzerin dem xABCDE-Algorithmus gefolgt ist. Grundlage ist nur, was sie im Gespräch tatsächlich gesagt oder getan hat. Maßstab ist dieser Referenz-Algorithmus (DRK-SANmemo):

${window.ALGORITHM}

Bei Fällen mit Bewusstlosigkeit gilt für die Zeile "1. Minute" der Bewusstlos-Pfad (Atemwege freimachen, Atemkontrolle max. 10 s, Atmung nicht normal: HLW und AED, Atmung normal: Seitenlage). Buchstaben, die nicht relevant waren, kennzeichne mit "–" statt ❌. Prüfe bei diesen Fällen auch, ob Schritte genau genannt wurden (z. B. Druckpunkt, Tiefe, Frequenz, Schock-Sicherheit bzw. Ablauf der Seitenlage).

Nutze genau dieses Format, auf Deutsch, ohne Markdown-Sternchen:

ALGORITHMUS: <Erfüllt / Teilweise erfüllt / Nicht erfüllt>

1. Minute (Sicherheit und Lage, bedrohliche Blutung, Ansprechen, Schnellcheck, Teambesprechung): <✅ / ⚠️ / ❌> <ein bis zwei Sätze>
x – Extreme Blutung: <✅ / ⚠️ / ❌> <ein Satz>
A – Airway: <✅ / ⚠️ / ❌> <ein Satz>
B – Breathing: <✅ / ⚠️ / ❌> <ein Satz>
C – Circulation: <✅ / ⚠️ / ❌> <ein Satz>
D – Disability: <✅ / ⚠️ / ❌> <ein Satz>
E – Exposure/Environment (SAMPLE, Ganzkörperuntersuchung, Wärmeerhalt): <✅ / ⚠️ / ❌> <ein Satz>

REIHENFOLGE: <wurde die Reihenfolge x-A-B-C-D-E eingehalten, wo wurde gesprungen oder etwas vergessen? Hat sie bei kritischen Problemen sofort behandelt, bevor sie weiterging?>
REEVALUATION: <wurde nach Maßnahmen erneut beurteilt bzw. nach E wieder bei A begonnen?>
KRITISCHE MASSNAHMEN: <was war in diesem Fall entscheidend und wurde es gemacht?>
GUT GEMACHT: <1–2 Punkte>
VERBESSERN: <1–3 konkrete Punkte>

Bewerte einen Buchstaben mit ⚠️, wenn er nur teilweise oder zu spät geprüft wurde, und mit ❌, wenn er gar nicht vorkam. Sei ehrlich, aber kurz.`;

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
  function showHome() {
    stopAll();
    scenario = null;
    $("home").hidden = false;
    $("session").hidden = true;
    $("backBtn").hidden = true;
    $("title").textContent = "Fallbeispiel xABCDE";
  }
  function renderScenarios() {
    const list = $("scenarioList");
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
    if (!settings.apiKey) { openSettings(); setStatus(""); }
    scenario = s;
    messages = [];
    debriefDone = false;
    $("log").innerHTML = "";
    $("home").hidden = true;
    $("session").hidden = false;
    $("backBtn").hidden = false;
    $("title").textContent = hideTitle ? "Zufälliger Fall" : s.title;
    $("handsfree").checked = settings.handsfree;
    // Einsatzmeldung ohne Lösungshinweise
    addMsg(s.dispatch.replace(/^Einsatzmeldung:\s*/, "Einsatzmeldung: "), "sys");
    addMsg("Du triffst ein. Beginne mit deiner Beurteilung, z. B. mit Eigenschutz und dem ersten Eindruck.", "sys");
    speak(s.dispatch.replace(/^Einsatzmeldung:\s*/, "Einsatzmeldung: "));
  }

  // ---------- Sprachausgabe ----------
  let germanVoice = null;
  function pickVoice() {
    const v = speechSynthesis.getVoices().filter((x) => x.lang && x.lang.toLowerCase().startsWith("de"));
    germanVoice = v.find((x) => /enhanced|premium|natural/i.test(x.name)) || v[0] || null;
  }
  if ("speechSynthesis" in window) { pickVoice(); speechSynthesis.onvoiceschanged = pickVoice; }

  function speak(text) {
    return new Promise((resolve) => {
      if (!settings.speak || !("speechSynthesis" in window)) return resolve();
      speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(text.replace(/[*_#`]/g, ""));
      u.lang = "de-DE";
      if (germanVoice) u.voice = germanVoice;
      u.rate = Number(settings.rate) || 1;
      u.onend = u.onerror = () => resolve();
      speechSynthesis.speak(u);
    });
  }

  // ---------- Spracheingabe ----------
  function startListening() {
    if (!SR) { setStatus("Spracherkennung wird von diesem Browser nicht unterstützt. Bitte tippen.", true); return; }
    if (listening || busy) return;
    if ("speechSynthesis" in window) speechSynthesis.cancel();
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

  // ---------- LLM ----------
  async function chat(msgs, maxTokens) {
    const url = settings.baseUrl.replace(/\/+$/, "") + "/chat/completions";
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(settings.apiKey ? { Authorization: "Bearer " + settings.apiKey } : {}) },
      body: JSON.stringify({ model: settings.model, messages: msgs, temperature: 0.7, max_tokens: maxTokens }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${(await res.text()).slice(0, 200)}`);
    const data = await res.json();
    return (data.choices?.[0]?.message?.content || "").trim();
  }

  async function send(text, { debrief = false } = {}) {
    if (!scenario || busy) return;
    busy = true;
    if (debrief) addMsg("Auswertung angefordert …", "sys"); else addMsg(text, "me");
    messages.push({ role: "user", content: text });
    setStatus("Denke nach …");
    try {
      const reply = await chat([{ role: "system", content: systemPrompt(scenario) }, ...messages], debrief ? 900 : 250);
      messages.push({ role: "assistant", content: reply });
      addMsg(reply, debrief ? "debrief" : "them");
      setStatus("");
      busy = false;
      if (debrief) {
        debriefDone = true;
        await speak(reply.split("\n").find((l) => l.startsWith("ALGORITHMUS")) || "Auswertung fertig.");
      } else {
        await speak(reply);
        if (settings.handsfree && scenario) startListening();
      }
    } catch (err) {
      messages.pop();
      setStatus("Fehler: " + err.message, true);
    } finally {
      busy = false;
    }
  }

  // ---------- Einstellungen-Dialog ----------
  function openSettings() {
    $("baseUrl").value = settings.baseUrl;
    $("apiKey").value = settings.apiKey;
    $("model").value = settings.model;
    $("rate").value = settings.rate;
    $("rateOut").textContent = Number(settings.rate).toFixed(2);
    $("speak").checked = settings.speak;
    $("settings").showModal();
  }

  // ---------- Events ----------
  $("settingsBtn").addEventListener("click", openSettings);
  $("rate").addEventListener("input", (e) => { $("rateOut").textContent = Number(e.target.value).toFixed(2); });
  $("settingsForm").addEventListener("submit", (e) => {
    if (e.submitter && e.submitter.value === "save") {
      settings.baseUrl = $("baseUrl").value.trim() || DEFAULTS.baseUrl;
      settings.apiKey = $("apiKey").value.trim();
      settings.model = $("model").value.trim() || DEFAULTS.model;
      settings.rate = $("rate").value;
      settings.speak = $("speak").checked;
      saveSettings();
    }
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
  $("debriefBtn").addEventListener("click", () => {
    if (!scenario || busy) return;
    if (debriefDone) return;
    stopAll();
    if (messages.length === 0) { setStatus("Starte erst den Einsatz, sonst gibt es nichts auszuwerten.", true); return; }
    send(DEBRIEF_PROMPT, { debrief: true });
  });

  renderScenarios();
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
})();
