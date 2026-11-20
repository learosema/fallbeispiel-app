(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;

  // ---------- Einstellungen ----------
  const API_URL = "/api/chat"; // Python-Backend mit lokalem Modell
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
  let scenario = null;
  let mode = "minute";    // "minute" = nur 1. Minute, "full" = ganzer Fall
  let messages = [];      // ohne System-Prompt
  let busy = false;
  let listening = false;
  let recognition = null;
  let debriefDone = false;

  // Zeitmessung: zählt nur die Zeit der Nutzerin, nicht das Warten auf/Vorlesen der Antwort
  let startedAt = null;
  let busyMs = 0;
  let busySince = null;
  let userLog = [];       // { t: Sekunden, text }
  const fmt = (s) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;
  function netSec() {
    if (!startedAt) return 0;
    const now = Date.now();
    return Math.max(0, (now - startedAt - busyMs - (busySince ? now - busySince : 0)) / 1000);
  }
  const startClock = () => { if (!startedAt) startedAt = Date.now(); };
  setInterval(() => { if (scenario && startedAt && !debriefDone) $("timer").textContent = "⏱ " + fmt(netSec()); }, 500);

  // ---------- Prompts ----------
  function systemPrompt(s) {
    const team = s.team || "Du bist mit einem Kollegen im Team, Sanitätsrucksack dabei. Der Rettungsdienst muss nachgefordert werden und trifft ca. 8 Minuten nach Nachforderung ein.";
    const modeText = mode === "minute"
      ? "MODUS 1. MINUTE: Der Fokus ist die 1. Minute nach SANmemo (Sicherheit/Lage, bedrohliche Blutung, Ansprechen, Schnellcheck, Teambesprechung, Funkspruch an die Leitstelle). Nach der Teambesprechung mit dem Kollegen (Lage, Verdachtsdiagnose, Notarzt) bestätigt der Kollege kurz. Danach setzt sie den Funkspruch ab. Sobald sie den Funkspruch mit ihrem Rufnamen und \"Ende\" abgeschlossen hat, ergänze als Befund: \"Die 1. Minute ist beendet. Du kannst die Auswertung starten.\" Danach keine neuen Untersuchungen mehr, außer sie besteht darauf. Vorher beendest du den Modus nie. Erinnere sie nicht an Teambesprechung oder Funkspruch."
      : "MODUS GANZER FALL: Nach der 1. Minute geht der Einsatz weiter (vollständiges ABCDE, Maßnahmen, Reevaluation, Übergabe).";
    return `Du bist die Simulation für ein Fallbeispiel-Training im Rettungsdienst (Ausbildung zur Sanitäterin beim DRK). Die Nutzerin ist die Sanitäterin in Ausbildung und spricht per Sprache mit dir. Antworte immer auf Deutsch.

SZENARIO: ${s.title}
${s.dispatch}
${s.role}

EINSATZSITUATION: ${team} Sanitätsrucksack-Ausrüstung (Pulsoxymeter, RR-Gerät, BZ-Messgerät, Thermometer, Absaugpumpe, Sauerstoff, AED, Verbandmaterial, Schienen, Rettungsdecke, Stifneck) steht zur Verfügung, wenn sie es verlangt. Alles, was darüber hinausgeht (Medikamente, Infusionen, Entlastungspunktion), steht dem Team nicht zur Verfügung.

${modeText}

SZENE (Auskunft zu Sicherheit und Lage, nur auf Nachfrage bzw. wenn sie die Umgebung prüft): ${s.scene}

VERBORGENE FAKTEN (nur preisgeben, wenn die Nutzerin danach fragt, untersucht, misst oder Maßnahmen durchführt; niemals von dir aus aufzählen):
${s.hidden}

ROLLEN UND FORMAT:
Jede Antwortzeile beginnt mit genau einem dieser Labels: "Patient:", "Kollege:", "Umstehende:", "Befund:", "Leitstelle:". Pro Antwort meist 1–3 kurze Zeilen. Kein Markdown, keine Aufzählungen, keine Emojis.
- Patient: Aussagen und Reaktionen der betroffenen Person, in kurzen, natürlichen Sätzen. Ist die Person bewusstlos, spricht sie nicht, beschreibe dann nur als Befund, was sichtbar ist.
- Kollege: ihr Teampartner. Er führt nur auf Zuruf aus, was sie ausspricht (z. B. manuelle HWS-Stabilisierung, Rucksack holen, Notruf/Nachforderung absetzen) und kündigt es kurz an, z. B. "Kollege: (übernimmt die manuelle HWS-Stabilisierung)". Er handelt fachlich nicht von sich aus und gibt keine Empfehlungen. In der Teambesprechung hört er zu und bestätigt knapp ("Verstanden.") oder fragt kurz nach, wenn etwas unverständlich ist, ohne Lücken zu füllen.
- Umstehende: Zeugen, Angehörige, Passanten.
- Leitstelle: die Funkzentrale "${settings.dispatcher}". Die Nutzerin ist das Team mit dem Funkrufnamen "${settings.callsign}". Die Leitstelle antwortet nur, wenn sie angefunkt wird, in knapper Funksprache: auf den Anruf ("${settings.dispatcher} von ${settings.callsign}, kommen") antwortet sie nur "Leitstelle: Hier ${settings.dispatcher}." Auf die Meldung wiederholt sie wortgleich die Nachforderung ("Leitstelle: RTW NEF kommt, verstanden."), nur das, was angefordert wurde. Ist etwas unverständlich, sagt sie "Leitstelle: Wiederholen." Sie gibt keine Empfehlungen, stellt keine Rückfragen zur Medizin und weist nichts zu, was nicht angefordert wurde. Fehlt der Anruf oder die Nachforderung, korrigiert sie nicht, sondern reagiert nur auf das, was gesagt wurde. Nach "${settings.callsign} Ende" sagt die Leitstelle nichts mehr. Außerhalb des Funkverkehrs spricht die Leitstelle nie.
- Befund: nüchterne Messwerte und Beobachtungen in einem Satz, z. B. "Befund: Puls 78, gut tastbar, Rekap unter 2 Sekunden." Nur, wenn sie wirklich gemessen oder untersucht wird.

REGELN FÜR DEN EINSATZ:
- Bleib in der Rolle. Gib keine Hinweise, was sie als Nächstes tun sollte, und lobe oder korrigiere nicht während des Einsatzes.
- Sagt sie nur, was sie tut oder feststellt (z. B. "Lage ist sicher", "Puls gut tastbar"), antworte minimal ("Kollege: Verstanden."), lass den Patienten reagieren, wenn es passt, und füge keine neuen Befunde hinzu. Widerspricht ihre Aussage den verborgenen Fakten, nenne den tatsächlichen Befund als "Befund:".
- Sagt sie die Lage sei sicher, obwohl die SZENE Gefahren enthält, lass die Gefahr später spürbar werden.
- Sagt sie nur "ich schaue nach den Atemwegen" o. Ä., gib den Befund dazu. Fragt sie vage, frage kurz nach, was genau sie tut.
- Der Zustand entwickelt sich realistisch: Fehlende oder falsche Maßnahmen verschlechtern ihn, richtige Maßnahmen verbessern ihn.
- Wärmeerhalt ist unabhängig von der Außentemperatur immer richtig. Wird die Person nicht zugedeckt und vom Boden isoliert, kühlt sie mit der Zeit aus (Temperatur und Hautbefund verschlechtern sich bzw. der Patient klagt über Kälte). Das Tempo hängt von der Außentemperatur ab: bei Kälte und Nässe schnell, bei Wärme langsam. Wird sie mit Decke/Rettungsdecke zugedeckt, wird es spürbar besser. Hinweise gibst du dazu nicht.
- Ist die Übergabe an den Rettungsdienst/Notarzt oder der Transport erfolgt, schließe den Einsatz knapp ab und sag, dass sie jetzt die Auswertung starten kann.

SCHLÜSSELMASSNAHMEN (nur für die Auswertung): ${s.keyActions}`;
  }

  function debriefPrompt() {
    const timeline = userLog.length
      ? userLog.map((e) => `[${fmt(e.t)}] ${e.text}`).join("\n")
      : "(keine Äußerungen)";
    const total = userLog.length ? fmt(userLog[userLog.length - 1].t) : "0:00";
    const abcde = mode === "full" ? `
x – Extreme Blutung: <✅ / ⚠️ / ❌ / –> <ein Satz>
A – Airway: <✅ / ⚠️ / ❌ / –> <ein Satz>
B – Breathing: <✅ / ⚠️ / ❌ / –> <ein Satz>
C – Circulation: <✅ / ⚠️ / ❌ / –> <ein Satz>
D – Disability: <✅ / ⚠️ / ❌ / –> <ein Satz>
E – Exposure/Environment (SAMPLE, Ganzkörperuntersuchung, Wärmeerhalt): <✅ / ⚠️ / ❌ / –> <ein Satz>
` : "";
    const fullTail = mode === "full" ? `
REEVALUATION: <wurde nach Maßnahmen erneut beurteilt bzw. nach E wieder bei A begonnen?>
KRITISCHE MASSNAHMEN: <was war in diesem Fall entscheidend und wurde es gemacht?>` : "";

    return `[AUSWERTUNG] Der Einsatz ist beendet. Verlasse die Rolle und bewerte nüchtern und wohlwollend, ob die Nutzerin dem Algorithmus gefolgt ist. Grundlage ist nur, was sie im Gespräch tatsächlich gesagt oder getan hat. Maßstab ist dieser Referenz-Algorithmus (DRK-SANmemo):

${window.ALGORITHM}

WICHTIG: Entscheidend ist das korrekte Einhalten des Algorithmus (vollständig, in der richtigen Reihenfolge, mit den richtigen Inhalten). Zeit ist nachrangig und nur eine Randnotiz. Die Funk-Rufnamen sind "${settings.callsign}" (eigenes Team) und "${settings.dispatcher}" (Leitstelle).

Zeitstempel ihrer Äußerungen (Nettozeit, ohne Wartezeiten der Simulation; nur zur Information):
${timeline}
Gesamtzeit bis zur letzten Äußerung: ${total}.

Bei Fällen mit Bewusstlosigkeit gilt für die "1. Minute" der Bewusstlos-Pfad (Atemwege freimachen, Atemkontrolle max. 10 s, Atmung nicht normal: HLW und AED, Atmung normal: Seitenlage, dazu immer Wärmeerhalt, unabhängig von der Außentemperatur). Prüfe dort auch, ob Schritte genau genannt wurden (Druckpunkt, Tiefe, Frequenz, Schock-Sicherheit bzw. Ablauf der Seitenlage). Schritte, die im Fall nicht relevant waren (z. B. HWS ohne Trauma), kennzeichne mit "–" statt ❌.

Nutze genau dieses Format, auf Deutsch, ohne Markdown-Sternchen. Zitiere kurz, was sie gesagt hat, wo es hilft:

ALGORITHMUS: <Erfüllt / Teilweise erfüllt / Nicht erfüllt>

1. MINUTE
Sicherheit und Lage: <✅ / ⚠️ / ❌ / –> <ein Satz>
Bedrohliche Blutung geprüft: <✅ / ⚠️ / ❌ / –> <ein Satz>
Vorstellung und Ansprache (Hallo, wir sind vom DRK, Was ist passiert?): <✅ / ⚠️ / ❌ / –> <ein Satz>
HWS bei Trauma (manuelle Stabilisierung): <✅ / ⚠️ / ❌ / –> <ein Satz>
Atmung (Luft? Schmerzen beim Atmen? Zyanose?): <✅ / ⚠️ / ❌ / –> <ein Satz>
Kreislauf (Hautfarbe, Puls, Rekap-Zeit, bei Trauma Bauch/Becken/Oberschenkel): <✅ / ⚠️ / ❌ / –> <ein Satz>
Neurologie (Reaktion angemessen, Gemütslage): <✅ / ⚠️ / ❌ / –> <ein Satz>
Umfeld (Verletzungsmechanismus, Umfeld, Frieren): <✅ / ⚠️ / ❌ / –> <ein Satz>
Wärmeerhalt (Decke/Rettungsdecke, Isolation vom Boden; immer richtig, unabhängig von der Außentemperatur; bei Kälte friert die Person nur schneller): <✅ / ⚠️ / ❌ / –> <ein Satz; nur nachfragen oder darüber sprechen reicht nicht, sie muss es ansagen oder durchführen>
Teambesprechung (Lage, Verdachtsdiagnose, Notarzt): <✅ / ⚠️ / ❌ / –> <ein Satz>
Funkspruch (Anruf mit beiden Rufnamen, auf Antwort gewartet, Patient/Ereignis/Verdachtsdiagnose, Nachforderung passend zur Lage, "kommen", Abschluss mit Rufname und "Ende"): <✅ / ⚠️ / ❌ / –> <ein bis zwei Sätze; nenne, was genau fehlte oder nicht passte>
${abcde}
TATSÄCHLICHE REIHENFOLGE: <die Schritte so aufzählen, wie sie im Gespräch tatsächlich vorkamen, mit Kürzeln und Pfeilen, z. B. Lage → Ansprache → HWS → Atmung>
ABWEICHUNGEN: <wo weicht das vom Algorithmus ab: vergessene Schritte, vertauschte Reihenfolge, falsche oder ungenaue Inhalte? Bei kritischen Problemen sofort behandelt? Wenn keine, schreibe "keine".>
ZEIT (nachrangig): <ein kurzer Satz, ohne Wertung des Algorithmus>${fullTail}
GUT GEMACHT: <1–2 Punkte>
VERBESSERN: <1–3 konkrete Punkte>

Bewerte einen Schritt mit ⚠️, wenn er nur teilweise oder zu spät kam, und mit ❌, wenn er gar nicht vorkam. Sei ehrlich, aber kurz.`;
  }

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
  const WHO_CLASS = { Patient: "them", Kollege: "them kollege", Umstehende: "them", Befund: "sys befund", Leitstelle: "them funk" };
  const PITCH = { Patient: 1, Kollege: 0.8, Umstehende: 1.2, Befund: 0.9, Leitstelle: 0.65 };
  function parseReply(text) {
    const segs = [];
    for (const raw of text.split(/\n+/)) {
      const line = raw.trim();
      if (!line) continue;
      const m = line.match(/^(Patient(?:in)?|Kolleg(?:e|in)|Umstehende[r]?|Befund|Leitstelle)\s*:\s*(.*)$/i);
      if (m) {
        const k = m[1].toLowerCase();
        const who = k.startsWith("patient") ? "Patient" : k.startsWith("kolleg") ? "Kollege" : k.startsWith("umsteh") ? "Umstehende" : k.startsWith("leit") ? "Leitstelle" : "Befund";
        segs.push({ who, text: m[2] });
      } else if (segs.length) segs[segs.length - 1].text += " " + line;
      else segs.push({ who: "Patient", text: line });
    }
    return segs;
  }
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
    scenario = s;
    mode = settings.mode === "full" ? "full" : "minute";
    messages = [];
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
    for (const seg of segs) {
      if (!scenario) return;
      await speak(seg.text, PITCH[seg.who] || 1);
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

  // ---------- LLM ----------
  async function chat(msgs, maxTokens) {
    const res = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(settings.accessCode ? { "x-access-code": settings.accessCode } : {}) },
      body: JSON.stringify({ messages: msgs, max_tokens: maxTokens }),
    });
    let data = {};
    try { data = await res.json(); } catch { /* keine JSON-Antwort */ }
    if (res.status === 401) { openSettings(); throw new Error(data.error || "Zugangscode fehlt oder ist falsch."); }
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    return (data.content || "").trim();
  }

  async function send(text, { debrief = false } = {}) {
    if (!scenario || busy) return;
    if (!debrief) { startClock(); userLog.push({ t: netSec(), text }); }
    busy = true;
    busySince = Date.now();
    let ok = false;
    if (debrief) addMsg("Auswertung angefordert …", "sys"); else addMsg(text, "me");
    messages.push({ role: "user", content: text });
    setStatus("Denke nach …");
    try {
      const reply = await chat([{ role: "system", content: systemPrompt(scenario) }, ...messages], debrief ? 1100 : 300);
      messages.push({ role: "assistant", content: reply });
      setStatus("");
      if (debrief) {
        debriefDone = true;
        addMsg(reply, "debrief");
        await speak(reply.split("\n").find((l) => l.startsWith("ALGORITHMUS")) || "Auswertung fertig.");
      } else {
        const segs = parseReply(reply);
        addReply(segs);
        await speakReply(segs);
      }
      ok = true;
    } catch (err) {
      messages.pop();
      if (!debrief) userLog.pop();
      setStatus("Fehler: " + err.message, true);
    } finally {
      busyMs += Date.now() - busySince;
      busySince = null;
      busy = false;
    }
    if (ok && !debrief && settings.handsfree && scenario) startListening();
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
  $("debriefBtn").addEventListener("click", () => {
    if (!scenario || busy) return;
    if (debriefDone) return;
    stopAll();
    if (messages.length === 0) { setStatus("Starte erst den Einsatz, sonst gibt es nichts auszuwerten.", true); return; }
    send(debriefPrompt(), { debrief: true });
  });

  renderScenarios();
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
})();
