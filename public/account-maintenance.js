(function () {
  var companyName = sessionStorage.getItem("maintenanceCompanyName");
  var identifierType = sessionStorage.getItem("maintenanceIdentifierType");
  var identifierValue = sessionStorage.getItem("maintenanceIdentifierValue");

  if (!companyName || !identifierType || !identifierValue) {
    window.location.href = "account-maintenance-identify.html";
    return;
  }

  var identifierLabel = identifierType === "cif" ? "CIF" : "Account Number";
  document.getElementById("account-context-line").textContent =
    "For " + companyName + " (" + identifierLabel + ": " + identifierValue + "). Select the type of change below. " +
    "If you need to make more than one type of change to your account, click the plus box to add another.";

  var CHANGE_TYPES = [
    { value: "additional-signatory", label: "Addition of a Signatory" },
    { value: "deletion-signatory", label: "Deletion of Signatory" },
    { value: "signing-instructions", label: "Change in Signing Instructions" },
    { value: "company-name", label: "Change Company Name" },
    { value: "shareholders", label: "Change in Shareholders" }
  ];

  var grid = document.getElementById("change-grid");
  var addBtn = document.getElementById("add-change-card");
  var continueBtn = document.getElementById("continue-btn");
  var note = document.querySelector("[data-submit-note]");

  function cards() {
    return Array.prototype.slice.call(grid.querySelectorAll("[data-change-card]"));
  }

  // Options are built once per <select>, when it's created, and never torn
  // down/rebuilt afterward. Duplicate selections across cards are caught on
  // Continue rather than by dynamically disabling options — rebuilding a
  // <select>'s options from inside its own 'change' event is a fragile
  // pattern that behaves inconsistently across browsers/devices.
  function fillOptions(select) {
    var placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "Select a change type";
    placeholder.disabled = true;
    placeholder.selected = true;
    select.appendChild(placeholder);

    CHANGE_TYPES.forEach(function (ct) {
      var opt = document.createElement("option");
      opt.value = ct.value;
      opt.textContent = ct.label;
      select.appendChild(opt);
    });
  }

  function selectedValues() {
    return cards()
      .map(function (card) { return card.querySelector("[data-change-select]").value; })
      .filter(function (v) { return v; });
  }

  function updateRemoveButtons() {
    var cardEls = cards();
    cardEls.forEach(function (card) {
      var existingBtn = card.querySelector(".change-card-remove");
      if (cardEls.length > 1 && !existingBtn) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "change-card-remove";
        btn.setAttribute("aria-label", "Remove this change type");
        btn.textContent = "×";
        btn.addEventListener("click", function () {
          card.remove();
          updateRemoveButtons();
          updateAddButtonVisibility();
          updateContinueState();
        });
        card.appendChild(btn);
      } else if (cardEls.length <= 1 && existingBtn) {
        existingBtn.remove();
      }
    });
  }

  function updateAddButtonVisibility() {
    var atCapacity = cards().length >= CHANGE_TYPES.length;
    addBtn.style.display = atCapacity ? "none" : "flex";
  }

  function updateContinueState() {
    var values = selectedValues();
    var anySelected = values.length > 0;
    var hasDuplicates = new Set(values).size !== values.length;

    continueBtn.disabled = !anySelected || hasDuplicates;
    note.classList.remove("submit-note-ready", "submit-note-error");

    if (hasDuplicates) {
      note.textContent = "Each change type can only be selected once — please choose a different type for the duplicate.";
      note.classList.add("submit-note-error");
    } else if (anySelected) {
      note.textContent = "Ready to continue with the selected change type(s).";
      note.classList.add("submit-note-ready");
    } else {
      note.textContent = "Select at least one change type to continue.";
    }
  }

  function createCard() {
    var card = document.createElement("div");
    card.className = "change-card";
    card.setAttribute("data-change-card", "");

    var label = document.createElement("label");
    label.className = "contact-field-label";
    label.style.marginTop = "0";
    label.textContent = "Type of change";

    var select = document.createElement("select");
    select.className = "contact-input change-select";
    select.setAttribute("data-change-select", "");
    fillOptions(select);
    select.addEventListener("change", updateContinueState);

    card.appendChild(label);
    card.appendChild(select);
    return card;
  }

  addBtn.addEventListener("click", function () {
    if (cards().length >= CHANGE_TYPES.length) return;
    var card = createCard();
    grid.insertBefore(card, addBtn);
    updateRemoveButtons();
    updateAddButtonVisibility();
    updateContinueState();
  });

  // The initial card's <select> already has a static placeholder option in
  // the HTML (so it still shows something if JS fails to load at all) — JS
  // replaces it here with the same fully-built option list every other card
  // uses, so there's exactly one code path for populating a select.
  var initialSelect = grid.querySelector("[data-change-select]");
  initialSelect.innerHTML = "";
  fillOptions(initialSelect);
  initialSelect.addEventListener("change", updateContinueState);

  continueBtn.addEventListener("click", function () {
    if (continueBtn.disabled) return;
    var selections = selectedValues();

    sessionStorage.setItem("maintenanceChangeTypes", JSON.stringify(selections));

    var params = new URLSearchParams({ changes: selections.join(",") });
    window.location.href = "account-maintenance-documents.html?" + params.toString();
  });

  updateRemoveButtons();
  updateAddButtonVisibility();
  updateContinueState();
})();
