// Proxy zum OpenAI-kompatiblen Chat-Completions-Endpunkt.
// Der API-Key liegt nur als Umgebungsvariable bei Netlify, nie im Browser.
//
// Umgebungsvariablen:
//   LLM_API_KEY   (Pflicht) API-Key des Anbieters
//   LLM_BASE_URL  (optional) Standard: https://api.openai.com/v1
//   LLM_MODEL     (optional) Standard: gpt-4o-mini
//   ACCESS_CODE   (optional, empfohlen) Zugangscode; der Browser sendet ihn als Header x-access-code
import { timingSafeEqual } from "node:crypto";

const MAX_MESSAGES = 80;
const MAX_TOTAL_CHARS = 80_000;
const MAX_TOKENS_CAP = 1200;
const ROLES = new Set(["system", "user", "assistant"]);

const env = (name, fallback = "") => (globalThis.Netlify?.env.get(name) ?? process.env[name] ?? fallback);
const json = (body, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });

function sameSecret(a, b) {
  const x = Buffer.from(a), y = Buffer.from(b);
  return x.length === y.length && timingSafeEqual(x, y);
}

export default async (req) => {
  if (req.method !== "POST") return json({ error: "Nur POST erlaubt." }, 405);

  const apiKey = env("LLM_API_KEY");
  if (!apiKey) return json({ error: "LLM_API_KEY ist auf dem Server nicht gesetzt." }, 500);

  const code = env("ACCESS_CODE");
  if (code && !sameSecret(req.headers.get("x-access-code") || "", code)) {
    return json({ error: "Zugangscode fehlt oder ist falsch." }, 401);
  }

  let payload;
  try { payload = await req.json(); } catch { return json({ error: "Ungültiges JSON." }, 400); }

  const { messages, max_tokens } = payload || {};
  if (!Array.isArray(messages) || messages.length === 0 || messages.length > MAX_MESSAGES) {
    return json({ error: "messages fehlt oder ist zu lang." }, 400);
  }
  let total = 0;
  const clean = [];
  for (const m of messages) {
    if (!m || !ROLES.has(m.role) || typeof m.content !== "string") return json({ error: "Ungültige Nachricht." }, 400);
    total += m.content.length;
    clean.push({ role: m.role, content: m.content });
  }
  if (total > MAX_TOTAL_CHARS) return json({ error: "Anfrage zu groß." }, 413);

  const url = env("LLM_BASE_URL", "https://api.openai.com/v1").replace(/\/+$/, "") + "/chat/completions";
  try {
    const upstream = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: "Bearer " + apiKey },
      // Modell, Temperatur und Obergrenze bestimmt der Server, nicht der Browser.
      body: JSON.stringify({
        model: env("LLM_MODEL", "gpt-4o-mini"),
        messages: clean,
        temperature: 0.7,
        max_tokens: Math.min(Math.max(parseInt(max_tokens, 10) || 300, 1), MAX_TOKENS_CAP),
      }),
      signal: AbortSignal.timeout(55_000),
    });
    if (!upstream.ok) {
      const detail = (await upstream.text()).slice(0, 300);
      return json({ error: `LLM-Anbieter antwortete mit HTTP ${upstream.status}: ${detail}` }, 502);
    }
    const data = await upstream.json();
    return json({ content: (data.choices?.[0]?.message?.content || "").trim() });
  } catch (err) {
    const timeout = err?.name === "TimeoutError";
    return json({ error: timeout ? "Zeitüberschreitung beim LLM-Anbieter." : "LLM-Anbieter nicht erreichbar." }, 504);
  }
};

export const config = { path: "/api/chat" };
