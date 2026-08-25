/**
 * Cloudflare Worker — Slack interactive payload handler + unsubscribe endpoint
 * for the <YOUR_COMPANY> sales-ops pipeline.
 *
 * Routes:
 *   POST /slack/interactive  — Handles Slack button actions (approve/reject leads)
 *   GET  /unsubscribe        — Handles email unsubscribe requests (?email=...)
 */

const GITHUB_API = "https://api.github.com";

// --- HMAC-SHA256 verification ---

async function hmacSha256(key, message) {
  const enc = new TextEncoder();
  const cryptoKey = await crypto.subtle.importKey(
    "raw",
    enc.encode(key),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const sig = await crypto.subtle.sign("HMAC", cryptoKey, enc.encode(message));
  return Array.from(new Uint8Array(sig))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

async function verifySlackSignature(request, body, signingSecret) {
  const timestamp = request.headers.get("x-slack-request-timestamp");
  const slackSig = request.headers.get("x-slack-signature");
  if (!timestamp || !slackSig) return false;

  const now = Math.floor(Date.now() / 1000);
  if (Math.abs(now - parseInt(timestamp)) > 300) return false;

  const sigBaseString = `v0:${timestamp}:${body}`;
  const computed = `v0=${await hmacSha256(signingSecret, sigBaseString)}`;

  if (computed.length !== slackSig.length) return false;
  let mismatch = 0;
  for (let i = 0; i < computed.length; i++) {
    mismatch |= computed.charCodeAt(i) ^ slackSig.charCodeAt(i);
  }
  return mismatch === 0;
}

// --- GitHub file write via API ---

async function writeFileToGitHub(env, path, content, message) {
  const url = `${GITHUB_API}/repos/${env.GITHUB_REPO}/contents/${path}`;
  const encoded = btoa(unescape(encodeURIComponent(content)));

  let sha;
  const existing = await fetch(url, {
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "User-Agent": "sales-ops-worker",
    },
  });
  if (existing.ok) {
    const data = await existing.json();
    sha = data.sha;
  }

  const body = { message, content: encoded };
  if (sha) body.sha = sha;

  const resp = await fetch(url, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "Content-Type": "application/json",
      "User-Agent": "sales-ops-worker",
    },
    body: JSON.stringify(body),
  });

  if (!resp.ok) {
    const err = await resp.text();
    throw new Error(`GitHub write failed (${resp.status}): ${err}`);
  }
  return resp.json();
}

// --- Slack interactive handler ---

async function handleSlackInteractive(request, env, bodyText) {
  const params = new URLSearchParams(bodyText);
  const payloadRaw = params.get("payload");
  if (!payloadRaw) return new Response("Missing payload", { status: 400 });

  let payload;
  try {
    payload = JSON.parse(payloadRaw);
  } catch {
    return new Response("Invalid JSON payload", { status: 400 });
  }

  const action = payload?.actions?.[0];
  if (!action) return new Response("No action found", { status: 400 });

  const actionId = action.action_id;
  const leadId = action.value;
  const approvedBy = payload?.user?.id || "unknown";
  const approvedAt = new Date().toISOString().split("T")[0];

  let decision;
  if (actionId === "lead_approve") decision = "approved";
  else if (actionId === "lead_reject") decision = "rejected";
  else if (actionId === "lead_linkedin_only") decision = "linkedin_only";
  else return new Response("Unknown action", { status: 400 });

  const decisionData = {
    lead_id: leadId,
    decision,
    approved_by: approvedBy,
    decided_at: approvedAt,
    slack_user: payload?.user?.name || approvedBy,
  };

  try {
    await writeFileToGitHub(
      env,
      `leads/decisions/${leadId}.json`,
      JSON.stringify(decisionData, null, 2),
      `decision: ${decision} for lead ${leadId} by ${approvedBy}`
    );
  } catch (e) {
    console.error("GitHub write error:", e.message);
    return new Response("Failed to record decision", { status: 500 });
  }

  const emoji = decision === "approved" ? "Approved" : decision === "rejected" ? "Rejected" : "LinkedIn-Only";
  return new Response(
    JSON.stringify({
      response_type: "ephemeral",
      text: `${emoji} Decision recorded: *${decision}* for lead \`${leadId}\``,
    }),
    { headers: { "Content-Type": "application/json" } }
  );
}

// --- Unsubscribe handler ---

async function handleUnsubscribe(request, env) {
  const url = new URL(request.url);
  const email = url.searchParams.get("email");

  if (!email || !email.includes("@")) {
    return new Response(unsubscribeHtml("Invalid email address."), {
      status: 400,
      headers: { "Content-Type": "text/html" },
    });
  }

  const today = new Date().toISOString().split("T")[0];
  const record = JSON.stringify({
    email: email.toLowerCase().trim(),
    domain: null,
    reason: "unsubscribed",
    added_date: today,
    added_by: "unsubscribe-worker",
  });

  const path = "suppression/list.jsonl";
  const fileUrl = `${GITHUB_API}/repos/${env.GITHUB_REPO}/contents/${path}`;
  let existingContent = "";
  let sha;

  try {
    const resp = await fetch(fileUrl, {
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "sales-ops-worker",
      },
    });
    if (resp.ok) {
      const data = await resp.json();
      sha = data.sha;
      existingContent = atob(data.content.replace(/\n/g, ""));
    }
  } catch (e) {
    console.error("Error reading suppression list:", e.message);
  }

  const newContent = existingContent.trimEnd() + (existingContent ? "\n" : "") + record + "\n";
  const encoded = btoa(unescape(encodeURIComponent(newContent)));
  const body = { message: `suppression: unsubscribe ${email}`, content: encoded };
  if (sha) body.sha = sha;

  try {
    const writeResp = await fetch(fileUrl, {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        Accept: "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "sales-ops-worker",
      },
      body: JSON.stringify(body),
    });
    if (!writeResp.ok) throw new Error(`GitHub write ${writeResp.status}`);
  } catch (e) {
    console.error("Suppression write error:", e.message);
    return new Response(unsubscribeHtml("Error processing your request. Please try again."), {
      status: 500,
      headers: { "Content-Type": "text/html" },
    });
  }

  return new Response(
    unsubscribeHtml(`You have been unsubscribed. <strong>${email}</strong> will receive no further emails from us.`),
    { headers: { "Content-Type": "text/html" } }
  );
}

function unsubscribeHtml(message) {
  return `<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Unsubscribe - <YOUR_COMPANY></title>
<style>body{font-family:system-ui,sans-serif;max-width:480px;margin:80px auto;padding:0 24px;color:#1a1a1a}
h1{font-size:1.4rem;margin-bottom:12px}p{color:#555;line-height:1.6}</style>
</head>
<body>
<h1><YOUR_COMPANY> Outreach</h1>
<p>${message}</p>
<p style="font-size:0.85rem;color:#999;margin-top:32px">You've been unsubscribed.</p>
</body></html>`;
}

// --- Main handler ---

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/slack/interactive" && request.method === "POST") {
      const bodyText = await request.text();
      const valid = await verifySlackSignature(request, bodyText, env.SLACK_SIGNING_SECRET);
      if (!valid) return new Response("Unauthorized", { status: 401 });
      return handleSlackInteractive(request, env, bodyText);
    }

    if (url.pathname === "/unsubscribe" && request.method === "GET") {
      return handleUnsubscribe(request, env);
    }

    return new Response("Not found", { status: 404 });
  },
};
