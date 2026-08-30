(function () {
  "use strict";

  var companyInput = document.getElementById("company-name-input");
  var identifierInput = document.getElementById("identifier-input");
  var continueBtn = document.getElementById("continue-btn");
  var note = document.querySelector("[data-submit-note]");

  continueBtn.addEventListener("click", function () {
    var companyName = companyInput.value.trim();
    var identifier = identifierInput.value.trim();

    note.classList.remove("submit-note-error", "submit-note-ready");

    if (!companyName) {
      note.textContent = "Please enter the company name.";
      note.classList.add("submit-note-error");
      companyInput.focus();
      return;
    }

    if (!/^\d+$/.test(identifier)) {
      note.textContent = "The account/CIF number must contain digits only.";
      note.classList.add("submit-note-error");
      identifierInput.focus();
      return;
    }

    var identifierType;
    if (identifier.length === 7) {
      identifierType = "cif";
    } else if (identifier.length === 13) {
      identifierType = "account";
    } else {
      note.textContent = "Enter a 7-digit CIF number or a 13-digit account number (got " + identifier.length + " digits).";
      note.classList.add("submit-note-error");
      identifierInput.focus();
      return;
    }

    sessionStorage.setItem("maintenanceCompanyName", companyName);
    sessionStorage.setItem("maintenanceIdentifierType", identifierType);
    sessionStorage.setItem("maintenanceIdentifierValue", identifier);

    window.location.href = "account-maintenance.html";
  });
})();
