const form = document.getElementById("fridge-form");
const optionsContainer = document.getElementById("options");
const selectedContainer = document.getElementById("selected");
const statusEl = document.getElementById("form-status");
const timeRange = document.getElementById("time_budget_minutes");
const timeLabel = document.getElementById("time-label");
const resetBtn = document.getElementById("reset-btn");
const themeToggle = document.getElementById("theme-toggle");

const STORAGE_THEME = "frw_theme";
const STORAGE_CHIPS = "frw_chips";

const escapeHtml = (input) =>
  String(input ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

const splitToTokens = (value) =>
  String(value || "")
    .split(/[,\n]/g)
    .map((s) => s.trim())
    .filter(Boolean);

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

const chipState = {
  main_vegetables: [],
  aromatics: [],
  spices: [],
  proteins: [],
  dietary: [],
  equipment: [],
};

const loadChips = () => {
  try {
    const raw = localStorage.getItem(STORAGE_CHIPS);
    if (!raw) return;
    const parsed = JSON.parse(raw);
    for (const key of Object.keys(chipState)) {
      if (Array.isArray(parsed[key])) chipState[key] = uniq(parsed[key]);
    }
  } catch {
    // ignore
  }
};

const saveChips = () => {
  try {
    localStorage.setItem(STORAGE_CHIPS, JSON.stringify(chipState));
  } catch {
    // ignore
  }
};

const renderChips = (fieldName) => {
  const wrap = document.querySelector(`[data-chips-for="${fieldName}"]`);
  if (!wrap) return;
  wrap.innerHTML = "";
  for (const token of chipState[fieldName]) {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.innerHTML = `
      <span>${escapeHtml(token)}</span>
      <button type="button" aria-label="Remove ${escapeHtml(token)}">×</button>
    `;
    chip.querySelector("button").addEventListener("click", () => {
      chipState[fieldName] = chipState[fieldName].filter((x) => x !== token);
      saveChips();
      renderChips(fieldName);
    });
    wrap.appendChild(chip);
  }
};

const addChipsFromInput = (inputEl) => {
  const fieldName = inputEl.name;
  if (!chipState[fieldName]) return;
  const tokens = splitToTokens(inputEl.value);
  if (!tokens.length) return;
  chipState[fieldName] = uniq([...chipState[fieldName], ...tokens]);
  inputEl.value = "";
  saveChips();
  renderChips(fieldName);
};

const wireChipInputs = () => {
  const chipInputs = Array.from(form.querySelectorAll("input.input[type='text']"));
  for (const inputEl of chipInputs) {
    if (!chipState[inputEl.name]) continue;

    inputEl.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        addChipsFromInput(inputEl);
      }
      if (e.key === "," || e.key === "Tab") {
        addChipsFromInput(inputEl);
      }
      if (e.key === "Backspace" && !inputEl.value) {
        chipState[inputEl.name].pop();
        saveChips();
        renderChips(inputEl.name);
      }
    });

    inputEl.addEventListener("blur", () => addChipsFromInput(inputEl));
  }
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
  const btn = document.getElementById("submit-btn");
  btn.disabled = isLoading;
  btn.querySelector(".btn-label").textContent = isLoading ? "Summoning options..." : "Generate options";
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
    optionsContainer.innerHTML = `<p class="muted">No options yet. Add a few ingredients and hit “Generate options”.</p>`;
    return;
  }

  options.forEach((option, index) => {
    const card = document.createElement("div");
    card.className = "option-card";

    const ingredientsPreview = (option.ingredients || []).slice(0, 10);
    const moreCount = Math.max(0, (option.ingredients || []).length - ingredientsPreview.length);

    card.innerHTML = `
      <div class="option-top">
        <div>
          <h3 class="option-title">${escapeHtml(option.title)}</h3>
          <div class="badges">
            <span class="badge info">${escapeHtml(option.cuisine || "weeknight")}</span>
            <span class="badge good">${escapeHtml(option.time_minutes)} min</span>
            <span class="badge">${escapeHtml(option.difficulty || "easy")}</span>
            <span class="badge warn">${escapeHtml(formatSource(option))}</span>
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

const getPayload = () => {
  const data = new FormData(form);
  const mood = String(data.get("cuisine_mood") || "").trim() || "quick and comforting";
  return {
    main_vegetables: uniq([...chipState.main_vegetables, ...splitToTokens(data.get("main_vegetables") || "")]),
    aromatics: uniq([...chipState.aromatics, ...splitToTokens(data.get("aromatics") || "")]),
    spices: uniq([...chipState.spices, ...splitToTokens(data.get("spices") || "")]),
    proteins: uniq([...chipState.proteins, ...splitToTokens(data.get("proteins") || "")]),
    dietary: uniq([...chipState.dietary, ...splitToTokens(data.get("dietary") || "")]),
    cuisine_mood: mood,
    time_budget_minutes: Number(data.get("time_budget_minutes")) || 30,
    servings: Number(data.get("servings")) || 2,
    equipment: uniq([...chipState.equipment, ...splitToTokens(data.get("equipment") || "")]),
  };
};

const setTheme = (theme) => {
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem(STORAGE_THEME, theme);
  } catch {
    // ignore
  }
};

const getTheme = () => {
  try {
    return localStorage.getItem(STORAGE_THEME) || "";
  } catch {
    return "";
  }
};

let lastPayload = null;
let lastOptions = [];

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  setStatus("");
  renderSelected(null);
  setLoading(true);
  renderOptionsSkeleton();

  // absorb any pending text in chip inputs
  for (const key of Object.keys(chipState)) {
    const inputEl = form.querySelector(`input[name="${key}"]`);
    if (inputEl && inputEl.value) addChipsFromInput(inputEl);
  }

  const payload = getPayload();
  lastPayload = payload;

  try {
    const response = await fetch("/api/recipes/options", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `HTTP ${response.status}`);
    }
    const data = await response.json();
    lastOptions = data.options || [];
    renderOptions(lastOptions);
    if (!lastOptions.length) setStatus("No hits. Try adding a protein or changing the mood.", "warn");
  } catch (err) {
    renderOptions([]);
    setStatus(`Couldn’t fetch options. ${err?.message || ""}`.trim(), "bad");
  } finally {
    setLoading(false);
  }
});

const chooseOption = async (index) => {
  if (!lastPayload) return;
  setStatus("Locking in a plan...", "muted");
  selectedContainer.innerHTML = `<div class="skeleton" style="height: 220px"></div>`;

  try {
    const response = await fetch("/api/recipes/choose", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ option_id: String(index), fridge_input: lastPayload }),
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

// mood pills
document.getElementById("mood-pills")?.addEventListener("click", (e) => {
  const btn = e.target?.closest?.("button[data-mood]");
  if (!btn) return;
  const mood = btn.getAttribute("data-mood");
  const input = document.getElementById("cuisine_mood");
  input.value = mood;
  for (const el of Array.from(document.querySelectorAll(".pill"))) el.classList.remove("is-active");
  btn.classList.add("is-active");
});

// time slider label
const syncTime = () => {
  timeLabel.textContent = String(timeRange.value);
};
timeRange?.addEventListener("input", syncTime);
syncTime();

resetBtn?.addEventListener("click", () => {
  for (const key of Object.keys(chipState)) chipState[key] = [];
  saveChips();
  for (const key of Object.keys(chipState)) renderChips(key);
  form.reset();
  syncTime();
  renderOptions([]);
  renderSelected(null);
  setStatus("Reset.", "muted");
});

themeToggle?.addEventListener("click", () => {
  const current = document.documentElement.dataset.theme || "dark";
  setTheme(current === "dark" ? "light" : "dark");
});

// init
setTheme(getTheme() || "dark");
loadChips();
wireChipInputs();
for (const key of Object.keys(chipState)) renderChips(key);
renderOptions([]);
renderSelected(null);
setStatus("Tip: press Enter to add chips. Backspace removes the last chip.", "muted");
