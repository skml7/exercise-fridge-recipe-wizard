const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-text");
const chatThread = document.getElementById("chat-thread");
const optionsContainer = document.getElementById("options");
const selectedContainer = document.getElementById("selected");
const statusEl = document.getElementById("form-status");
const sendBtn = document.getElementById("send-btn");

const escapeHtml = (input) =>
  String(input ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

const uniq = (items) => {
  const out = [];
  const seen = new Set();
  for (const item of items) {
    const key = item.trim().toLowerCase();
    if (!key || seen.has(key)) continue;
    seen.add(key);
    out.push(item.trim());
  }
  return out;
};

const setStatus = (text, tone = "muted") => {
  statusEl.textContent = text || "";
  statusEl.style.color =
    tone === "bad"
      ? "var(--bad)"
      : tone === "good"
        ? "var(--good)"
        : tone === "warn"
          ? "var(--warn)"
          : "var(--muted)";
};

const setLoading = (isLoading) => {
  if (!sendBtn) return;
  sendBtn.disabled = isLoading;
  sendBtn.querySelector(".btn-label").textContent = isLoading ? "Thinking..." : "Send";
};

const renderOptionsSkeleton = () => {
  optionsContainer.innerHTML = "";
  for (let i = 0; i < 3; i += 1) {
    const sk = document.createElement("div");
    sk.className = "skeleton";
    optionsContainer.appendChild(sk);
  }
};

const formatSource = (option) => {
  const source = String(option?.source || "generated");
  if (source === "spoonacular") return "Spoonacular";
  if (source === "mealdb") return "TheMealDB";
  return "Generated";
};

const renderOptions = (options) => {
  optionsContainer.innerHTML = "";
  if (!options.length) {
    optionsContainer.innerHTML = `<p class="muted">No options yet. Share a few ingredients to get started.</p>`;
    return;
  }

  options.forEach((option, index) => {
    const card = document.createElement("div");
    card.className = "option-card";

    const ingredientsPreview = (option.ingredients || []).slice(0, 10);
    const moreCount = Math.max(0, (option.ingredients || []).length - ingredientsPreview.length);

    card.innerHTML = `
      <div class="option-top">
        <div class="option-media">
          <div>
            <h3 class="option-title">${escapeHtml(option.title)}</h3>
            <div class="badges">
              <span class="badge info">${escapeHtml(option.cuisine || "weeknight")}</span>
              <span class="badge good">${escapeHtml(option.time_minutes)} min</span>
              <span class="badge">${escapeHtml(option.difficulty || "easy")}</span>
              <span class="badge warn">${escapeHtml(formatSource(option))}</span>
            </div>
          </div>
        </div>
        <div class="option-actions">
          <button class="btn btn-primary" data-index="${index}">Choose</button>
        </div>
      </div>
      <div class="option-meta">
        <div><strong>Ingredients:</strong> ${escapeHtml(ingredientsPreview.join(", "))}${
          moreCount ? ` <span class="muted">(+${moreCount} more)</span>` : ""
        }</div>
        ${
          option.source_url
            ? `<div><a class="link" href="${escapeHtml(option.source_url)}" target="_blank" rel="noreferrer">Source</a></div>`
            : ""
        }
      </div>
    `;
    card.querySelector("button").addEventListener("click", () => chooseOption(index));
    optionsContainer.appendChild(card);
  });
};

const buildShoppingList = (recipe) => uniq((recipe?.ingredients || []).map((x) => String(x || "").trim()).filter(Boolean));

const renderSelected = (recipe) => {
  if (!recipe) {
    selectedContainer.innerHTML = `<p class="muted">Pick an option to see the full steps.</p>`;
    return;
  }

  const list = buildShoppingList(recipe);
  const textToCopy = [
    recipe.title,
    `Time: ${recipe.time_minutes} min`,
    "",
    "Ingredients:",
    ...list.map((x) => `- ${x}`),
    "",
    "Steps:",
    ...(recipe.steps || []).map((x, i) => `${i + 1}. ${x}`),
  ].join("\n");

  selectedContainer.innerHTML = `
    <h3>${escapeHtml(recipe.title)}</h3>
    <div class="badges">
      <span class="badge info">${escapeHtml(recipe.cuisine || "weeknight")}</span>
      <span class="badge good">${escapeHtml(recipe.time_minutes)} min</span>
      <span class="badge warn">${escapeHtml(formatSource(recipe))}</span>
      ${
        recipe.source_url
          ? `<a class="badge link" href="${escapeHtml(recipe.source_url)}" target="_blank" rel="noreferrer">Source</a>`
          : ""
      }
    </div>
    <p class="muted" style="margin-top:0.7rem">Ingredients:</p>
    <div class="chips" style="margin-bottom:0.6rem">
      ${list.map((x) => `<span class="chip"><span>${escapeHtml(x)}</span></span>`).join("")}
    </div>
    <p class="muted">Steps:</p>
    <ol>${(recipe.steps || []).map((step) => `<li>${escapeHtml(step)}</li>`).join("")}</ol>
    ${recipe.notes ? `<p class="note">${escapeHtml(recipe.notes)}</p>` : ""}
    <div class="option-actions" style="margin-top:0.9rem">
      <button type="button" class="btn btn-ghost" id="copy-btn">Copy</button>
    </div>
  `;

  const copyBtn = document.getElementById("copy-btn");
  if (copyBtn) {
    copyBtn.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(textToCopy);
        setStatus("Copied. Go cook.", "good");
      } catch {
        setStatus("Copy failed. (Browser permissions)", "warn");
      }
    });
  }
};

const renderChat = (messages) => {
  chatThread.innerHTML = "";
  for (const message of messages) {
    const bubble = document.createElement("div");
    bubble.className = `chat-bubble ${message.role === "user" ? "is-user" : "is-assistant"}`;
    bubble.innerHTML = `<p>${escapeHtml(message.content)}</p>`;
    chatThread.appendChild(bubble);
  }
  chatThread.scrollTop = chatThread.scrollHeight;
};

let chatMessages = [
  {
    role: "assistant",
    content: "What’s in your fridge? You can also tell me the vibe you want.",
  },
];
let lastOptions = [];
let lastFridgeInput = null;

const sendChatTurn = async () => {
  const text = String(chatInput.value || "").trim();
  if (!text) return;

  chatMessages = [...chatMessages, { role: "user", content: text }];
  chatInput.value = "";
  renderChat(chatMessages);
  setStatus("");
  setLoading(true);
  renderOptionsSkeleton();

  try {
    const response = await fetch("/api/chat/turn", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: chatMessages, fridge_input: lastFridgeInput }),
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `HTTP ${response.status}`);
    }
    const data = await response.json();
    if (data.assistant_message) {
      chatMessages = [...chatMessages, { role: "assistant", content: data.assistant_message }];
      renderChat(chatMessages);
    }
    if (data.fridge_input) lastFridgeInput = data.fridge_input;
    lastOptions = data.options || [];
    renderOptions(lastOptions);
    if (data.next_action === "ask") {
      setStatus("Give me a bit more detail so I can personalize.", "muted");
    } else if (!lastOptions.length) {
      setStatus("No hits. Try adding a protein or changing the mood.", "warn");
    }
  } catch (err) {
    renderOptions([]);
    setStatus(`Couldn’t fetch options. ${err?.message || ""}`.trim(), "bad");
  } finally {
    setLoading(false);
  }
};

const chooseOption = async (index) => {
  if (!lastFridgeInput) return;
  setStatus("Locking in a plan...", "muted");
  selectedContainer.innerHTML = `<div class="skeleton" style="height: 220px"></div>`;

  try {
    const response = await fetch("/api/recipes/choose", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ option_id: String(index), fridge_input: lastFridgeInput }),
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `HTTP ${response.status}`);
    }
    const data = await response.json();
    renderSelected(data.selected);
    setStatus("Selected. You’ve got this.", "good");
  } catch (err) {
    renderSelected(null);
    setStatus(`Couldn’t select option. ${err?.message || ""}`.trim(), "bad");
  }
};

chatForm.addEventListener("submit", (event) => {
  event.preventDefault();
  sendChatTurn();
});

chatInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    sendChatTurn();
  }
});

renderOptions([]);
renderSelected(null);
renderChat(chatMessages);
setStatus("Tip: include a time like “20 min” or “for 4”.", "muted");
