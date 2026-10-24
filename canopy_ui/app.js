"use strict";
const $ = (id) => document.getElementById(id);
const state = {
  mode: "verify",
  selected: null,
  run: null,
  chat: null,
  chatSelected: null,
  chats: [],
  busy: false,
  cases: [],
  tab: "execution",
};
const examples = {
  refund:
    "Policy: Our fictional store refunds purchases within 14 days. Damaged items qualify for a refund within 30 days, even after use.\nEvidence: The customer bought an item 21 days ago, used it, and provided photos showing it arrived damaged.\nClaim: We must refuse the refund because the item was used and the normal 14-day window has passed.",
  access:
    "Policy: Our fictional company grants production access only after a manager approves the request and the employee completes security training.\nEvidence: A new employee has completed security training. The request contains no manager approval record.\nClaim: This employee is eligible for production access.",
};
function node(tag, cls, text) {
  const el = document.createElement(tag);
  if (cls) el.className = cls;
  if (text !== undefined) el.textContent = text;
  return el;
}
function notice(text) {
  $("notice").textContent = text;
  $("notice").hidden = false;
  setTimeout(() => {
    $("notice").hidden = true;
  }, 6000);
}
async function api(path, options = {}, timeoutMs = 15000) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
    signal: AbortSignal.timeout(timeoutMs),
  });
  const data = await response.json();
  if (!response.ok)
    throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}
function tab(name) {
  state.tab = name;
  for (const key of ["execution", "evidence"]) {
    $(`${key}-tab`).setAttribute("aria-selected", String(key === name));
    $(`${key}-panel`).hidden = key !== name;
  }
}
function trace(show) {
  document.querySelector(".shell").classList.toggle("trace-hidden", !show);
  $("trace-toggle").textContent = show ? "Hide trace" : "Show trace";
  $("trace-toggle").setAttribute("aria-expanded", String(show));
}
function busy(value) {
  state.busy = value;
  $("run-button").disabled = value;
  $("new-case").disabled = value;
  $("new-chat").disabled = value;
  $("chat-mode").disabled = value;
  $("reset-case").disabled = value;
  $("run-status").textContent = value
    ? state.mode === "chat"
      ? "replying"
      : "running"
    : "ready";
}
function turn(role, text, at = new Date()) {
  const wrapper = node("article", `turn ${role}`);
  const label = node("div", "turn-label", role === "user" ? "you" : "canopy");
  const time = node(
    "span",
    "muted",
    new Date(at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
  );
  label.append(time);
  const body = node("div", "turn-body", text);
  wrapper.append(label, body);
  $("transcript").append(wrapper);
  return body;
}
function scroll() {
  const el = $("transcript");
  el.scrollTop = el.scrollHeight;
}
function newCase() {
  if (state.busy) return;
  state.mode = "verify";
  state.selected = null;
  state.run = null;
  $("transcript").replaceChildren(welcomeTemplate.cloneNode(true));
  wireSamples();
  $("run-title").textContent = "new case";
  $("prompt").value = "";
  renderEvents([]);
  renderEvidence(null);
  modeControls();
  renderCases();
  renderChats();
  $("prompt").focus();
}
const welcomeTemplate = $("welcome").cloneNode(true);
function modeControls() {
  const chatting = state.mode === "chat";
  $("chat-mode").textContent = chatting ? "Verify a case" : "Chat with Canopy";
  $("reset-case").textContent = chatting ? "New chat" : "New case";
  $("prompt-label").textContent = chatting
    ? "Message Canopy"
    : "Describe a case";
  $("prompt").placeholder = chatting
    ? "Ask Canopy anything..."
    : "Describe a case, or paste Policy: ... Evidence: ... Claim: ...";
  $("run-button").textContent = chatting ? "Send message ↵" : "Run check ↵";
  document.querySelector(".composer-foot span").textContent = chatting
    ? "Enter to send · Shift + Enter for a new line"
    : "Enter to run · Shift + Enter for a new line";
  $("transcript").setAttribute(
    "aria-label",
    chatting ? "Chat conversation" : "Case conversation",
  );
}
function newChat() {
  if (state.busy) return;
  state.mode = "chat";
  state.chat = null;
  state.chatSelected = null;
  const welcome = node("section", "welcome");
  welcome.id = "welcome";
  welcome.append(
    node("div", "session-heading", "Canopy / chat"),
    node("p", "welcome-lead", "Ask me anything."),
    node(
      "p",
      "",
      "This conversation goes through Mubit. For a policy verdict, switch to Verify a case.",
    ),
  );
  $("transcript").replaceChildren(welcome);
  $("run-title").textContent = "new chat";
  $("prompt").value = "";
  renderEvents([]);
  renderEvidence(null);
  tab("execution");
  modeControls();
  renderCases();
  renderChats();
  $("prompt").focus();
}
function wireSamples() {
  for (const key of ["refund", "access"]) {
    const button = $(`sample-${key}`);
    if (button)
      button.addEventListener("click", () => {
        $("prompt").value = examples[key];
        $("prompt").focus();
      });
  }
}
function renderEvents(events) {
  $("trace-count").textContent = `${events.length} events`;
  $("trace-empty").hidden = events.length > 0;
  const list = $("events");
  const wasBottom =
    list.parentElement.scrollHeight -
      list.parentElement.scrollTop -
      list.parentElement.clientHeight <
    100;
  list.replaceChildren();
  for (const event of events) {
    const ended =
      event.state === "running" &&
      events.some(
        (next) =>
          next.tool === event.tool &&
          ["completed", "failed"].includes(next.state),
      );
    const displayState = ended ? "started" : event.state;
    const row = node("article", `trace-event ${displayState}`);
    const head = node("div", "trace-event-head");
    head.append(
      node("span", "tool-name", event.tool),
      node("span", "tool-state", displayState),
    );
    row.append(head, node("div", "trace-message", event.message));
    const details = [];
    if (event.host) details.push(event.host);
    if (event.model) details.push(`model: ${event.model}`);
    if (event.recording) details.push(`recording: ${event.recording}`);
    if (event.ms !== undefined) details.push(`${event.ms.toLocaleString()} ms`);
    if (event.usage?.total_tokens)
      details.push(`${event.usage.total_tokens} tokens`);
    row.append(node("div", "trace-detail", details.join(" · ")));
    if (event.request_id) row.append(node("div", "trace-id", event.request_id));
    row.append(
      node("div", "trace-detail", new Date(event.at).toLocaleTimeString()),
    );
    list.append(row);
  }
  if (wasBottom) list.parentElement.scrollTop = list.parentElement.scrollHeight;
}
function renderEvidence(run) {
  const content = $("evidence-content");
  content.replaceChildren();
  $("evidence-empty").hidden =
    !!run?.fields && Object.keys(run.fields).length > 0;
  if (!run?.fields) return;
  for (const key of ["policy", "evidence", "claim"]) {
    const section = node("section", "evidence-field");
    section.append(node("span", "section-label", key.toUpperCase()));
    if (key === "policy")
      section.append(
        node(
          "p",
          "evidence-note",
          "Supplied policy. No external law is assumed.",
        ),
      );
    section.append(
      node("div", "evidence-value", run.fields[key] || "Not supplied"),
    );
    content.append(section);
  }
  if (run.result) {
    const section = node("section", "evidence-field");
    section.append(
      node("span", "section-label", "VERIFIED THROUGH MUBIT"),
      node("div", "trace-id", run.result.request_id),
    );
    content.append(section);
  }
}
function renderCases() {
  const list = $("case-list");
  list.replaceChildren();
  $("case-count").textContent = state.cases.length;
  if (!state.cases.length)
    list.append(node("p", "nav-empty", "Your checked cases will appear here."));
  for (const item of state.cases) {
    const button = node(
      "button",
      `case-link${state.mode === "verify" && item.id === state.selected ? " selected" : ""}`,
    );
    button.append(
      node(
        "span",
        "case-title",
        item.title.replace(/^Policy:\s*/, "").slice(0, 55),
      ),
      node(
        "span",
        "case-meta",
        `${item.id.slice(0, 6)} / ${item.reviewed ? "reviewed" : item.status.replace("_", " ")}`,
      ),
    );
    button.addEventListener("click", () => openCase(item.id));
    list.append(button);
  }
}
async function refreshCases() {
  state.cases = await api("/api/cases");
  renderCases();
}
function renderChats() {
  const list = $("chat-list");
  list.replaceChildren();
  $("chat-count").textContent = state.chats.length;
  if (!state.chats.length)
    list.append(node("p", "nav-empty", "Your chats will appear here."));
  for (const item of state.chats) {
    const button = node(
      "button",
      `case-link${state.mode === "chat" && item.id === state.chatSelected ? " selected" : ""}`,
    );
    button.append(
      node("span", "case-title", item.title.slice(0, 55)),
      node("span", "case-meta", `${item.id.slice(0, 6)} / chat`),
    );
    button.addEventListener("click", () => openChat(item.id));
    list.append(button);
  }
}
async function refreshChats() {
  state.chats = await api("/api/chats");
  renderChats();
}
function chatAnswer(body, message) {
  body.replaceChildren(
    node("div", "chat-answer", message.content),
    node(
      "div",
      "result-meta",
      `${message.ms.toLocaleString()} ms · ${message.model} through Mubit\n${message.request_id}`,
    ),
  );
}
async function openChat(id) {
  if (state.busy) return;
  try {
    const chat = await api(`/api/chats/${id}`);
    state.mode = "chat";
    state.chat = chat;
    state.chatSelected = id;
    $("transcript").replaceChildren();
    for (const message of chat.messages) {
      const body = turn(
        message.role === "user" ? "user" : "agent",
        "",
        message.at,
      );
      if (message.role === "assistant") chatAnswer(body, message);
      else body.textContent = message.content;
    }
    $("run-title").textContent = `chat ${id.slice(0, 8)}`;
    renderEvents(chat.events);
    renderEvidence(null);
    tab("execution");
    modeControls();
    renderCases();
    renderChats();
    scroll();
  } catch (error) {
    notice(error.message);
  }
}
async function startChat(text) {
  if (state.busy) return;
  busy(true);
  $("welcome")?.remove();
  turn("user", text);
  const body = turn("agent", "");
  body.append(node("span", "pending", "Waiting for Canopy through Mubit"));
  $("prompt").value = "";
  scroll();
  tab("execution");
  if (innerWidth > 680) trace(true);
  try {
    const path = state.chatSelected
      ? `/api/chats/${state.chatSelected}/messages`
      : "/api/chats";
    const chat = await api(
      path,
      {
        method: "POST",
        body: JSON.stringify({ input: text, record: $("record").checked }),
      },
      55000,
    );
    state.chat = chat;
    state.chatSelected = chat.id;
    $("run-title").textContent = `chat ${chat.id.slice(0, 8)}`;
    chatAnswer(body, chat.messages.at(-1));
    renderEvents(chat.events);
    $("connection").textContent = "Mubit replied";
    $("connection").className = "connection connected";
    await refreshChats();
    scroll();
  } catch (error) {
    body.replaceChildren(node("p", "error-text", error.message));
    $("prompt").value = text;
    scroll();
  } finally {
    busy(false);
    $("prompt").focus();
  }
}
function resultBody(body, run) {
  body.replaceChildren();
  if (run.status === "failed") {
    body.append(node("p", "error-text", run.error));
    const retry = node(
      "button",
      "underlined-button",
      "Put the case back in the prompt",
    );
    retry.addEventListener("click", () => {
      $("prompt").value = run.input;
      $("prompt").focus();
    });
    body.append(retry);
    return;
  }
  if (run.status === "needs_input") {
    body.append(
      node(
        "div",
        "result-heading verdict-INSUFFICIENT",
        "More information needed",
      ),
      node(
        "p",
        "result-reason",
        `Please supply: ${run.missing.join(", ")}. I have not guessed the missing information.`,
      ),
    );
    const form = node("form", "missing-form");
    for (const key of ["policy", "evidence", "claim"]) {
      const label = node("label", "field-label", key.toUpperCase());
      const input = node("textarea");
      input.name = key;
      input.value = run.fields[key] || "";
      input.required = true;
      input.maxLength = 12000;
      label.append(input);
      form.append(label);
    }
    const button = node("button", "run-button", "Run with these inputs");
    button.type = "submit";
    form.append(button);
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const fields = Object.fromEntries(new FormData(form));
      start(run.input, fields);
    });
    body.append(form);
    return;
  }
  const result = run.result;
  if (!result) return;
  body.append(
    node("div", `result-heading verdict-${result.verdict}`, result.verdict),
    node("div", "result-reason", result.reason),
  );
  if (result.policy_excerpt)
    body.append(node("blockquote", "result-quote", result.policy_excerpt));
  if (result.missing?.length)
    body.append(node("p", "muted", `Missing: ${result.missing.join("; ")}`));
  body.append(
    node(
      "div",
      "result-meta",
      `${result.ms.toLocaleString()} ms · ${result.model} through Mubit\n${result.request_id}`,
    ),
  );
  if (run.review) {
    saved(body, run.review);
    return;
  }
  const actions = node("div", "result-actions");
  const review = node("button", "underlined-button", "Review this verdict");
  review.addEventListener("click", () => reviewForm(body, run));
  const evidence = node("button", "underlined-button", "Inspect evidence");
  evidence.addEventListener("click", () => {
    trace(true);
    tab("evidence");
  });
  actions.append(review, evidence);
  body.append(actions);
}
function saved(body, review) {
  const el = node("div", "saved-review");
  el.append(
    node("strong", "", `Human review: ${review.verdict}`),
    node("div", "", review.reason),
    node(
      "div",
      "",
      "Saved locally. Mubit feedback submission is not connected.",
    ),
  );
  body.append(el);
}
function reviewForm(body, run) {
  if (body.querySelector(".review-form")) return;
  const form = node("form", "review-form");
  form.append(node("div", "section-label", "HUMAN REVIEW"));
  const label = node("label", "field-label", "Correct verdict");
  const select = node("select");
  select.name = "verdict";
  for (const value of ["SUPPORTED", "VIOLATES", "INSUFFICIENT"]) {
    const option = node("option", "", value);
    option.value = value;
    select.append(option);
  }
  select.value = run.result.verdict;
  label.append(select);
  const reasonLabel = node(
    "label",
    "field-label",
    "Why? Reference the supplied policy or missing facts.",
  );
  const reason = node("textarea");
  reason.name = "reason";
  reason.required = true;
  reason.minLength = 3;
  reason.maxLength = 2000;
  reasonLabel.append(reason);
  const button = node("button", "run-button", "Save human review");
  button.type = "submit";
  const note = node(
    "p",
    "result-meta",
    "This saves a correction linked to this case and its Mubit request ID. It does not claim a model update.",
  );
  form.append(label, reasonLabel, button, note);
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    button.disabled = true;
    try {
      const review = await api(`/api/runs/${run.id}/review`, {
        method: "POST",
        body: JSON.stringify({ verdict: select.value, reason: reason.value }),
      });
      run.review = review;
      resultBody(body, run);
      const updated = await api(`/api/runs/${run.id}`);
      state.run = updated;
      renderEvents(updated.events);
      await refreshCases();
    } catch (error) {
      notice(error.message);
      button.disabled = false;
    }
  });
  body.append(form);
  reason.focus();
  scroll();
}
async function openCase(id) {
  if (state.busy) return;
  try {
    const run = await api(`/api/runs/${id}`);
    state.mode = "verify";
    state.selected = id;
    state.run = run;
    $("transcript").replaceChildren();
    turn("user", run.input || run.fields.claim);
    const body = turn("agent", "");
    resultBody(body, run);
    $("run-title").textContent = `case ${id.slice(0, 8)}`;
    renderEvents(run.events);
    renderEvidence(run);
    modeControls();
    renderCases();
    renderChats();
  } catch (error) {
    notice(error.message);
  }
}
async function start(text, fields = {}) {
  if (state.busy) return;
  busy(true);
  $("welcome")?.remove();
  turn("user", text || fields.claim);
  const body = turn("agent", "");
  body.append(
    node("span", "pending", "Waiting for the server to accept the case"),
  );
  scroll();
  tab("execution");
  if (innerWidth > 680) trace(true);
  let runId;
  try {
    const response = await api("/api/runs", {
      method: "POST",
      body: JSON.stringify({
        input: text,
        ...fields,
        record: $("record").checked,
      }),
    });
    runId = response.id;
    state.selected = runId;
    $("run-title").textContent = `case ${runId.slice(0, 8)}`;
    $("prompt").value = "";
    const deadline = Date.now() + 130000;
    while (Date.now() < deadline) {
      const run = await api(`/api/runs/${runId}`);
      state.run = run;
      renderEvents(run.events);
      renderEvidence(run);
      if (run.status !== "running") {
        if (run.status === "completed") {
          $("connection").textContent = "Mubit verified";
          $("connection").className = "connection connected";
        }
        resultBody(body, run);
        await refreshCases();
        body.closest(".turn").scrollIntoView({ block: "start" });
        return;
      }
      const last = run.events[run.events.length - 1];
      body.replaceChildren(
        node(
          "span",
          "pending",
          last?.tool === "mubit.verify"
            ? "Verifying the supplied policy and evidence through Mubit"
            : "Extracting the supplied case through Mubit",
        ),
      );
      await new Promise((resolve) => setTimeout(resolve, 650));
    }
    throw new Error(
      "This run is taking longer than expected. Reopen it from the case history shortly.",
    );
  } catch (error) {
    body.replaceChildren(node("p", "error-text", error.message));
    if (runId) refreshCases().catch(() => {});
    scroll();
  } finally {
    busy(false);
    $("prompt").focus();
  }
}
$("composer").addEventListener("submit", (e) => {
  e.preventDefault();
  const text = $("prompt").value.trim();
  if (text) {
    if (state.mode === "chat") startChat(text);
    else start(text);
  }
});
$("prompt").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    $("composer").requestSubmit();
  }
});
$("new-case").addEventListener("click", newCase);
$("new-chat").addEventListener("click", newChat);
$("chat-mode").addEventListener("click", () =>
  state.mode === "chat" ? newCase() : newChat(),
);
$("reset-case").addEventListener("click", () =>
  state.mode === "chat" ? newChat() : newCase(),
);
$("trace-toggle").addEventListener("click", () =>
  trace(document.querySelector(".shell").classList.contains("trace-hidden")),
);
for (const name of ["execution", "evidence"]) {
  $(`${name}-tab`).addEventListener("click", () => tab(name));
  $(`${name}-tab`).addEventListener("keydown", (e) => {
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
      e.preventDefault();
      const other = name === "execution" ? "evidence" : "execution";
      tab(other);
      $(`${other}-tab`).focus();
    }
  });
}
document.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === "k") {
    e.preventDefault();
    newCase();
  }
  if (e.key === "Escape" && innerWidth <= 680) trace(false);
});
wireSamples();
newChat();
if (innerWidth <= 680) trace(false);
api("/api/status")
  .then((config) => {
    $("model-name").textContent = config.model;
    $("build-label").textContent = config.build;
    $("connection").textContent = config.configured
      ? "Mubit configured"
      : "Mubit key missing";
    $("connection").className =
      `connection ${config.configured ? "connected" : "failed"}`;
    if (!config.configured)
      $("run-status").textContent = "configuration needed";
  })
  .catch(() => {
    $("connection").textContent = "server unavailable";
    $("connection").className = "connection failed";
  });
refreshCases().catch((error) => notice(error.message));
refreshChats().catch((error) => notice(error.message));
