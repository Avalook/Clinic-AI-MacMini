"use strict";
const query = document.getElementById("query");
const scope = document.getElementById("scope");
const visibleCount = document.getElementById("visible-count");
const findingCards = [...document.querySelectorAll(".finding")];
const riskRows = [...document.querySelectorAll("[data-risk-row]")];
function updateFilter() {
  const text = query.value.trim().toLocaleLowerCase("vi");
  const selected = scope.value;
  let count = 0;
  for (const card of findingCards) {
    const matchesText = card.textContent.toLocaleLowerCase("vi").includes(text);
    const matchesScope = selected === "all"
      || (selected === "open" && card.dataset.mainStatus !== "addressed_on_main")
      || (selected === "patched" && card.dataset.mainStatus === "addressed_on_main")
      || (selected === "uncertain" && ["hypothesis", "design_gap"].includes(card.dataset.level));
    card.hidden = !(matchesText && matchesScope);
    if (!card.hidden) count += 1;
  }
  for (const row of riskRows) {
    const card = document.getElementById(row.dataset.riskRow);
    row.hidden = card ? card.hidden : false;
  }
  visibleCount.textContent = `${count} / ${findingCards.length} hồ sơ`;
  document.getElementById("empty").hidden = count !== 0;
}
query.addEventListener("input", updateFilter);
scope.addEventListener("change", updateFilter);
let previouslyOpen = [];
let previouslyHidden = [];
function preparePrint() {
  previouslyOpen = [...document.querySelectorAll(".finding details[open]")];
  previouslyHidden = [...document.querySelectorAll(".finding[hidden], [data-risk-row][hidden]")];
  for (const detail of document.querySelectorAll(".finding details")) detail.open = true;
  for (const element of previouslyHidden) element.hidden = false;
}
function restoreAfterPrint() {
  for (const detail of document.querySelectorAll(".finding details")) {
    detail.open = previouslyOpen.includes(detail);
  }
  for (const element of previouslyHidden) element.hidden = true;
}
window.addEventListener("beforeprint", preparePrint);
window.addEventListener("afterprint", restoreAfterPrint);
document.getElementById("print").addEventListener("click", () => window.print());
updateFilter();
