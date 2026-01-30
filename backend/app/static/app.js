const form = document.getElementById("fridge-form");
const optionsContainer = document.getElementById("options");
const selectedContainer = document.getElementById("selected");

const toList = (value) =>
  value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);

const renderOptions = (options) => {
  optionsContainer.innerHTML = "";
  if (!options.length) {
    optionsContainer.textContent = "No options yet.";
    return;
  }

  options.forEach((option, index) => {
    const card = document.createElement("div");
    card.className = "option-card";
    card.innerHTML = `
      <h3>${option.title}</h3>
      <p><strong>Cuisine:</strong> ${option.cuisine}</p>
      <p><strong>Time:</strong> ${option.time_minutes} minutes</p>
      <p><strong>Difficulty:</strong> ${option.difficulty}</p>
      <p><strong>Ingredients:</strong> ${option.ingredients.join(", ")}</p>
      <button data-index="${index}">Choose</button>
    `;
    card.querySelector("button").addEventListener("click", () => chooseOption(index));
    optionsContainer.appendChild(card);
  });
};

const renderSelected = (recipe) => {
  if (!recipe) {
    selectedContainer.textContent = "Select an option to see details.";
    return;
  }
  selectedContainer.innerHTML = `
    <h3>${recipe.title}</h3>
    <p><strong>Cuisine:</strong> ${recipe.cuisine}</p>
    <p><strong>Time:</strong> ${recipe.time_minutes} minutes</p>
    <p><strong>Ingredients:</strong> ${recipe.ingredients.join(", ")}</p>
    <ol>${recipe.steps.map((step) => `<li>${step}</li>`).join("")}</ol>
    ${recipe.notes ? `<p class="note">${recipe.notes}</p>` : ""}
  `;
};

const getPayload = () => {
  const data = new FormData(form);
  return {
    main_vegetables: toList(data.get("main_vegetables") || ""),
    aromatics: toList(data.get("aromatics") || ""),
    spices: toList(data.get("spices") || ""),
    proteins: toList(data.get("proteins") || ""),
    dietary: toList(data.get("dietary") || ""),
    cuisine_mood: data.get("cuisine_mood") || "quick and comforting",
    time_budget_minutes: Number(data.get("time_budget_minutes")) || 30,
    servings: Number(data.get("servings")) || 2,
    equipment: toList(data.get("equipment") || ""),
  };
};

let lastPayload = null;
let lastOptions = [];

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  optionsContainer.textContent = "Loading...";
  selectedContainer.textContent = "";

  const payload = getPayload();
  lastPayload = payload;
  const response = await fetch("/api/recipes/options", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  lastOptions = data.options || [];
  renderOptions(lastOptions);
  renderSelected(null);
});

const chooseOption = async (index) => {
  if (!lastPayload) {
    return;
  }
  selectedContainer.textContent = "Loading...";
  const response = await fetch("/api/recipes/choose", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ option_id: String(index), fridge_input: lastPayload }),
  });
  const data = await response.json();
  renderSelected(data.selected);
};

renderOptions([]);
renderSelected(null);
