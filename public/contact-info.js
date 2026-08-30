(function () {
  var params = new URLSearchParams(window.location.search);
  var ref = params.get("ref");
  var company = params.get("company");

  if (!ref) {
    window.location.href = "open-account.html";
    return;
  }

  var companyLine = document.getElementById("company-name-line");
  if (company) {
    companyLine.textContent =
      "Documents received for " + company + ". Please provide a contact email and phone number so we can reach you about this application.";
  }

  var continueBtn = document.getElementById("continue-btn");
  var note = document.querySelector("[data-submit-note]");

  function makeFieldGroup(opts) {
    var container = document.getElementById(opts.containerId);
    var addBtn = document.getElementById(opts.addBtnId);

    function updateRemoveButtons() {
      var rows = container.querySelectorAll("[" + opts.rowAttr + "]");
      rows.forEach(function (row) {
        var existingBtn = row.querySelector(".remove-doc-btn");
        if (rows.length > 1 && !existingBtn) {
          var btn = document.createElement("button");
          btn.type = "button";
          btn.className = "remove-doc-btn";
          btn.textContent = "Remove";
          btn.addEventListener("click", function () {
            row.remove();
            updateRemoveButtons();
          });
          row.appendChild(btn);
        } else if (rows.length <= 1 && existingBtn) {
          existingBtn.remove();
        }
      });
    }

    addBtn.addEventListener("click", function () {
      var row = document.createElement("div");
      row.className = "contact-field-row";
      row.setAttribute(opts.rowAttr, "");

      var input = document.createElement("input");
      input.type = opts.inputType;
      input.className = "contact-input";
      input.setAttribute(opts.inputAttr, "");
      input.placeholder = opts.placeholder;

      row.appendChild(input);
      container.appendChild(row);
      updateRemoveButtons();
      input.focus();
    });

    updateRemoveButtons();

    return {
      values: function () {
        return Array.prototype.map
          .call(container.querySelectorAll("[" + opts.inputAttr + "]"), function (el) {
            return el.value.trim();
          })
          .filter(function (v) {
            return v.length > 0;
          });
      }
    };
  }

  var emailGroup = makeFieldGroup({
    containerId: "email-fields",
    addBtnId: "add-email-btn",
    rowAttr: "data-email-row",
    inputAttr: "data-email-input",
    inputType: "email",
    placeholder: "name@company.com"
  });

  var phoneGroup = makeFieldGroup({
    containerId: "phone-fields",
    addBtnId: "add-phone-btn",
    rowAttr: "data-phone-row",
    inputAttr: "data-phone-input",
    inputType: "tel",
    placeholder: "e.g. +971 4 123 4567"
  });

  function isValidEmail(value) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
  }

  continueBtn.addEventListener("click", function () {
    var emails = emailGroup.values();
    var phones = phoneGroup.values();

    note.classList.remove("submit-note-error");

    if (emails.length === 0) {
      note.textContent = "Please provide at least one contact email address.";
      note.classList.add("submit-note-error");
      return;
    }
    var invalid = emails.filter(function (e) { return !isValidEmail(e); });
    if (invalid.length > 0) {
      note.textContent = "Please enter valid email address(es): " + invalid.join(", ");
      note.classList.add("submit-note-error");
      return;
    }
    if (phones.length === 0) {
      note.textContent = "Please provide at least one contact number.";
      note.classList.add("submit-note-error");
      return;
    }

    continueBtn.disabled = true;
    continueBtn.textContent = "Saving...";
    note.textContent = "";

    fetch("/api/submit-contact-info", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ referenceNumber: ref, emails: emails, phones: phones })
    })
      .then(function (resp) {
        return resp.json().then(function (data) { return { ok: resp.ok, data: data }; });
      })
      .then(function (result) {
        if (result.ok && result.data.success) {
          var outParams = new URLSearchParams({ ref: ref || "", company: company || "" });
          window.location.href = "submission-success.html?" + outParams.toString();
        } else {
          note.textContent = "Could not save contact info: " + (result.data && result.data.error ? result.data.error : "Please try again.");
          note.classList.add("submit-note-error");
          continueBtn.disabled = false;
          continueBtn.textContent = "Continue";
        }
      })
      .catch(function () {
        note.textContent = "Network error. Please try again.";
        note.classList.add("submit-note-error");
        continueBtn.disabled = false;
        continueBtn.textContent = "Continue";
      });
  });
})();
