"use strict";

// ---- Tabs ----

for (const btn of document.querySelectorAll(".tab-btn")) {
  btn.addEventListener("click", () => {
    for (const b of document.querySelectorAll(".tab-btn")) b.classList.remove("active");
    for (const p of document.querySelectorAll(".tab-panel")) p.classList.remove("active");
    btn.classList.add("active");
    document.getElementById(btn.dataset.tab).classList.add("active");
    if (btn.dataset.tab === "database") loadVariants();
  });
}

// ---- Markdown rendering ----
// Minimal, dependency-free markdown -> HTML. All text is escaped before any
// tag is introduced, so nothing from the model output can inject markup.

function escapeHtml(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function renderInline(text) {
  let out = escapeHtml(text);
  out = out.replace(/`([^`]+)`/g, "<code>$1</code>");
  out = out.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  out = out.replace(/(?<!\*)\*([^*\n]+)\*(?!\*)/g, "<em>$1</em>");
  out = out.replace(
    /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
  );
  return out;
}

function renderMarkdown(text) {
  const lines = text.replace(/\r\n/g, "\n").split("\n");
  let html = "";
  let listType = null;
  let i = 0;

  function closeList() {
    if (listType) {
      html += `</${listType}>`;
      listType = null;
    }
  }

  while (i < lines.length) {
    const line = lines[i];

    const fenceMatch = line.match(/^```(\w*)\s*$/);
    if (fenceMatch) {
      closeList();
      const codeLines = [];
      i++;
      while (i < lines.length && !/^```\s*$/.test(lines[i])) {
        codeLines.push(lines[i]);
        i++;
      }
      i++;
      html += `<pre><code>${escapeHtml(codeLines.join("\n"))}</code></pre>`;
      continue;
    }

    const headerMatch = line.match(/^(#{1,6})\s+(.*)$/);
    if (headerMatch) {
      closeList();
      const level = headerMatch[1].length;
      html += `<h${level}>${renderInline(headerMatch[2])}</h${level}>`;
      i++;
      continue;
    }

    const ulMatch = line.match(/^[-*]\s+(.*)$/);
    if (ulMatch) {
      if (listType !== "ul") {
        closeList();
        html += "<ul>";
        listType = "ul";
      }
      html += `<li>${renderInline(ulMatch[1])}</li>`;
      i++;
      continue;
    }

    const olMatch = line.match(/^\d+\.\s+(.*)$/);
    if (olMatch) {
      if (listType !== "ol") {
        closeList();
        html += "<ol>";
        listType = "ol";
      }
      html += `<li>${renderInline(olMatch[1])}</li>`;
      i++;
      continue;
    }

    if (!line.trim()) {
      closeList();
      i++;
      continue;
    }

    closeList();
    const paraLines = [line];
    i++;
    while (
      i < lines.length &&
      lines[i].trim() &&
      !/^```/.test(lines[i]) &&
      !/^#{1,6}\s+/.test(lines[i]) &&
      !/^[-*]\s+/.test(lines[i]) &&
      !/^\d+\.\s+/.test(lines[i])
    ) {
      paraLines.push(lines[i]);
      i++;
    }
    html += `<p>${renderInline(paraLines.join("\n")).replace(/\n/g, "<br>")}</p>`;
  }

  closeList();
  return html;
}

// ---- Chat ----

const chatLog = document.getElementById("chat-log");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const chatSend = document.getElementById("chat-send");

const history = [];

function addBubble(role, text) {
  const el = document.createElement("div");
  el.className = `msg ${role}`;
  if (role === "assistant") {
    el.innerHTML = renderMarkdown(text);
  } else {
    el.textContent = text;
  }
  chatLog.appendChild(el);
  chatLog.scrollTop = chatLog.scrollHeight;
  return el;
}

function addSources(sources) {
  const withUrl = sources.filter((s) => s.url);
  if (withUrl.length === 0) return;
  const wrap = document.createElement("div");
  wrap.className = "sources";
  for (const s of withUrl) {
    const a = document.createElement("a");
    a.className = "source-chip";
    a.href = s.url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.textContent = s.heading_path || s.document_id || s.url;
    wrap.appendChild(a);
  }
  chatLog.appendChild(wrap);
  chatLog.scrollTop = chatLog.scrollHeight;
}

async function sendChat(text) {
  history.push({ role: "user", content: text });
  addBubble("user", text);

  chatSend.disabled = true;
  const assistantEl = addBubble("assistant", "");
  let assistantText = "";

  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ messages: history }),
    });

    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Request failed (${res.status})`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let newlineIndex;
      while ((newlineIndex = buffer.indexOf("\n")) !== -1) {
        const line = buffer.slice(0, newlineIndex);
        buffer = buffer.slice(newlineIndex + 1);
        if (!line.trim()) continue;

        const event = JSON.parse(line);
        if (event.type === "sources") {
          addSources(event.sources || []);
        } else if (event.type === "delta") {
          assistantText += event.text;
          assistantEl.innerHTML = renderMarkdown(assistantText);
          chatLog.scrollTop = chatLog.scrollHeight;
        } else if (event.type === "error") {
          throw new Error(event.detail || "Chat backend failed.");
        }
        // "done" carries only usage; nothing to render.
      }
    }
  } catch (err) {
    assistantEl.remove();
    if (assistantText) {
      addBubble("assistant", assistantText);
    }
    addBubble("error", err.message || String(err));
    // Drop the failed turn so a retry doesn't resend a half-answered exchange.
    history.pop();
    chatSend.disabled = false;
    return;
  }

  history.push({ role: "assistant", content: assistantText });
  chatSend.disabled = false;
}

chatForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = chatInput.value.trim();
  if (!text) return;
  chatInput.value = "";
  sendChat(text);
});

chatInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    chatForm.requestSubmit();
  }
});

// ---- Search ----

const searchForm = document.getElementById("search-form");
const searchInput = document.getElementById("search-input");
const searchK = document.getElementById("search-k");
const searchSend = document.getElementById("search-send");
const searchResults = document.getElementById("search-results");

function renderResults(results) {
  searchResults.innerHTML = "";
  if (results.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "No results.";
    searchResults.appendChild(empty);
    return;
  }

  for (const r of results) {
    const card = document.createElement("div");
    card.className = "result-card";

    const head = document.createElement("div");
    head.className = "result-head";

    const heading = document.createElement("span");
    heading.className = "heading-path";
    if (r.url) {
      const a = document.createElement("a");
      a.href = r.url;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.textContent = r.heading_path || r.document_id;
      heading.appendChild(a);
    } else {
      heading.textContent = r.heading_path || r.document_id;
    }

    const score = document.createElement("span");
    score.className = "score";
    score.textContent = r.score.toFixed(3);

    head.appendChild(heading);
    head.appendChild(score);

    const docId = document.createElement("div");
    docId.className = "doc-id";
    docId.textContent = r.document_id;

    const snippet = document.createElement("div");
    snippet.className = "snippet";
    snippet.textContent = r.text;

    card.appendChild(head);
    card.appendChild(docId);
    card.appendChild(snippet);
    searchResults.appendChild(card);
  }
}

async function runSearch(query, k) {
  searchSend.disabled = true;
  searchResults.innerHTML = '<div class="empty-state">Searching…</div>';

  try {
    const res = await fetch("/search", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ query, k }),
    });

    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Request failed (${res.status})`);
    }

    const data = await res.json();
    renderResults(data.results);
  } catch (err) {
    searchResults.innerHTML = "";
    const errorEl = document.createElement("div");
    errorEl.className = "empty-state";
    errorEl.style.color = "var(--error)";
    errorEl.textContent = err.message || String(err);
    searchResults.appendChild(errorEl);
  } finally {
    searchSend.disabled = false;
  }
}

searchForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const query = searchInput.value.trim();
  if (!query) return;
  const k = Math.max(1, Math.min(50, Number(searchK.value) || 6));
  runSearch(query, k);
});

// ---- Database ----

const fetchBtn = document.getElementById("fetch-btn");
const ingestBtn = document.getElementById("ingest-btn");
const ingestForce = document.getElementById("ingest-force");
const refreshVariantsBtn = document.getElementById("refresh-variants-btn");
const dbStatus = document.getElementById("db-status");
const variantList = document.getElementById("variant-list");

function formatDate(seconds) {
  return seconds ? new Date(seconds * 1000).toLocaleString() : "—";
}

function formatSeconds(seconds) {
  return seconds ? `${seconds.toFixed(1)}s` : "—";
}

function setDbStatus(text, isError) {
  dbStatus.textContent = text;
  dbStatus.style.color = isError ? "var(--error)" : "var(--muted)";
}

async function triggerAction(url, button, startedMessage) {
  button.disabled = true;
  try {
    const res = await fetch(url, { method: "POST", headers: { "content-type": "application/json" }, body: "{}" });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Request failed (${res.status})`);
    }
    setDbStatus(startedMessage, false);
    setTimeout(loadVariants, 3000);
  } catch (err) {
    setDbStatus(err.message || String(err), true);
  } finally {
    button.disabled = false;
  }
}

fetchBtn.addEventListener("click", () => {
  triggerAction("/fetch", fetchBtn, "Fetch started — pulling upstream repos in the background.");
});

ingestBtn.addEventListener("click", async () => {
  ingestBtn.disabled = true;
  try {
    const res = await fetch("/ingest", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ force: ingestForce.checked }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Request failed (${res.status})`);
    }
    setDbStatus("Ingest started — this can take a while for a full rebuild.", false);
    setTimeout(loadVariants, 3000);
  } catch (err) {
    setDbStatus(err.message || String(err), true);
  } finally {
    ingestBtn.disabled = false;
  }
});

refreshVariantsBtn.addEventListener("click", loadVariants);

function statusBadgeClass(status) {
  if (status === "ok") return "badge status-ok";
  if (status === "running") return "badge status-running";
  return "badge status-error";
}

function renderRunsTable(runs) {
  if (runs.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "No ingest runs recorded.";
    return empty;
  }

  const table = document.createElement("table");
  table.className = "runs-table";
  table.innerHTML =
    "<thead><tr><th>Started</th><th>Status</th><th>Docs</th><th>Chunks</th><th>Embed time</th></tr></thead>";
  const tbody = document.createElement("tbody");
  for (const run of runs) {
    const tr = document.createElement("tr");
    const cells = [
      formatDate(run.started_at),
      run.status,
      String(run.docs_total),
      String(run.chunks_written),
      formatSeconds(run.embed_seconds),
    ];
    for (const text of cells) {
      const td = document.createElement("td");
      td.textContent = text;
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  return table;
}

async function toggleRuns(fingerprint, container, toggleBtn) {
  if (container.childElementCount > 0) {
    container.innerHTML = "";
    toggleBtn.textContent = "Show runs";
    return;
  }
  toggleBtn.textContent = "Loading…";
  try {
    const res = await fetch(`/variants/${encodeURIComponent(fingerprint)}/runs`);
    if (!res.ok) throw new Error(`Request failed (${res.status})`);
    const data = await res.json();
    container.appendChild(renderRunsTable(data.runs));
    toggleBtn.textContent = "Hide runs";
  } catch (err) {
    container.textContent = err.message || String(err);
    toggleBtn.textContent = "Show runs";
  }
}

async function dropVariant(fingerprint, collectionName) {
  if (!confirm(`Drop the collection for ${collectionName}? This removes its vectors; run history is kept.`)) {
    return;
  }
  try {
    const res = await fetch(`/variants/${encodeURIComponent(fingerprint)}`, { method: "DELETE" });
    if (!res.ok && res.status !== 204) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Request failed (${res.status})`);
    }
    setDbStatus(`Dropped ${collectionName}.`, false);
    loadVariants();
  } catch (err) {
    setDbStatus(err.message || String(err), true);
  }
}

function renderVariantCard(variant) {
  const card = document.createElement("div");
  card.className = variant.is_current ? "variant-card current" : "variant-card";

  const head = document.createElement("div");
  head.className = "variant-head";

  const name = document.createElement("span");
  name.className = "variant-name";
  name.textContent = variant.collection_name;
  head.appendChild(name);

  if (variant.is_current) {
    const badge = document.createElement("span");
    badge.className = "badge current";
    badge.textContent = "current";
    head.appendChild(badge);
  }

  if (variant.latest_run) {
    const badge = document.createElement("span");
    badge.className = statusBadgeClass(variant.latest_run.status);
    badge.textContent = variant.latest_run.status;
    head.appendChild(badge);
  }

  card.appendChild(head);

  const meta = document.createElement("div");
  meta.className = "variant-meta";
  const metaFields = [
    ["Model", variant.embedding_model],
    ["Strategy", variant.strategy],
    ["Chunks", String(variant.chunk_count)],
    ["Created", formatDate(variant.created_at)],
  ];
  for (const [label, value] of metaFields) {
    const span = document.createElement("span");
    span.textContent = `${label}: ${value}`;
    meta.appendChild(span);
  }
  const fp = document.createElement("span");
  fp.className = "variant-fingerprint";
  fp.textContent = variant.fingerprint;
  meta.appendChild(fp);
  card.appendChild(meta);

  if (variant.latest_run) {
    const run = document.createElement("div");
    run.className = "variant-run";
    run.textContent = `Last run: ${formatDate(variant.latest_run.started_at)} — ${variant.latest_run.docs_total} docs, ${variant.latest_run.chunks_written} chunks, ${formatSeconds(variant.latest_run.embed_seconds)} embedding`;
    card.appendChild(run);
  }

  const actions = document.createElement("div");
  actions.className = "variant-actions";

  const runsContainer = document.createElement("div");

  const toggleBtn = document.createElement("button");
  toggleBtn.type = "button";
  toggleBtn.textContent = "Show runs";
  toggleBtn.addEventListener("click", () => toggleRuns(variant.fingerprint, runsContainer, toggleBtn));
  actions.appendChild(toggleBtn);

  const dropBtn = document.createElement("button");
  dropBtn.type = "button";
  dropBtn.className = "danger";
  dropBtn.textContent = "Drop";
  dropBtn.addEventListener("click", () => dropVariant(variant.fingerprint, variant.collection_name));
  actions.appendChild(dropBtn);

  card.appendChild(actions);
  card.appendChild(runsContainer);

  return card;
}

async function loadVariants() {
  variantList.innerHTML = '<div class="empty-state">Loading…</div>';
  try {
    const res = await fetch("/variants");
    if (!res.ok) throw new Error(`Request failed (${res.status})`);
    const data = await res.json();

    variantList.innerHTML = "";

    const hasCurrent = data.variants.some((v) => v.fingerprint === data.current_fingerprint);
    if (data.current_fingerprint && !hasCurrent) {
      const notice = document.createElement("div");
      notice.className = "current-notice";
      notice.textContent =
        "The current config/corpus hasn't been ingested yet. Click “Ingest current variant” to build it.";
      variantList.appendChild(notice);
    }

    if (data.variants.length === 0) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "No variants ingested yet.";
      variantList.appendChild(empty);
      return;
    }

    for (const variant of data.variants) {
      variantList.appendChild(renderVariantCard(variant));
    }
  } catch (err) {
    variantList.innerHTML = "";
    const errorEl = document.createElement("div");
    errorEl.className = "empty-state";
    errorEl.style.color = "var(--error)";
    errorEl.textContent = err.message || String(err);
    variantList.appendChild(errorEl);
  }
}
