(function () {
  "use strict";

  // TODO: these three placeholder links point at the general downloadable-forms
  // page because the exact PDF URLs for these forms could not be found in the
  // site's static markup (RAKBank's Wholesale/Business forms tab loads its list
  // client-side). Replace with the direct PDF links once available.
  var DOWNLOADABLE_FORMS_URL = "https://www.rakbank.ae/en/help-centre/support/downloadable-forms";
  var ACCOUNT_OPENING_FORM_URL = "https://www.rakbank.ae/globalassets/rakbank/all-pdfs/001---downloadable-forms/account-services/pps-a1105_corporate-account-form-26-08-2025-edl-2.pdf";
  var FATCA_CRS_FORM_URL = "https://www.rakbank.ae/globalassets/rakbank/all-pdfs/001---downloadable-forms/kyc-updates/2-8-101120fatcacrscorporateallinone-editable-1222.pdf";

  var SECTIONS = {
    "bank-forms": {
      mandatory: [
        { name: "Account Opening Form", link: ACCOUNT_OPENING_FORM_URL },
        { name: "Corporate FATCA and CRS", link: FATCA_CRS_FORM_URL },
        { name: "Sanctions Declaration", link: DOWNLOADABLE_FORMS_URL }
      ],
      optional: [
        { name: "Digital Banking Application", link: DOWNLOADABLE_FORMS_URL }
      ]
    },
    "entity-documents": {
      mandatory: [
        "Trade License / Certificate of Incorporation",
        "Memorandum & Articles of Association (MOA/AOA) and any amendments",
        "Certificate of Incumbency / Good Standing",
        "Shareholder Register",
        { name: "Valid Passport and ID Documents of the Signatories", multiple: true },
        "Residence Address Proof of the Signatories"
      ],
      optional: [
        "VAT Registration Certificate",
        "Power of Attorney",
        "3 Months Bank Statement",
        "Shareholder Resolution (required only if signing powers are not mentioned in the MOA/AOA or POA)",
        "Organizational Chart",
        "Shareholder Documents",
        "Corporate Tax Registration Certificate"
      ]
    },
    "ubo-documents": {
      mandatory: [
        "Passport Copy",
        "Emirates ID / National ID",
        "Proof of Residential Address"
      ],
      optional: [
        "UBO Declaration Form",
        "Source of Wealth/Funds Declaration"
      ]
    }
  };

  var OTHER_VALUE = "__other__";
  var optionalRowCounter = 0;

  function normalizeDoc(doc) {
    if (typeof doc === "string") return { name: doc, multiple: false, link: null };
    return {
      name: doc.name,
      multiple: doc.multiple || false,
      link: doc.link || null
    };
  }

  function createDocRow(name, opts) {
    opts = opts || {};
    var row = document.createElement("div");
    row.className = "doc-row";
    row.setAttribute("data-doc-row", "true");

    var main = document.createElement("div");
    main.className = "doc-row-main";

    var nameEl = document.createElement("span");
    nameEl.className = "doc-name";
    nameEl.textContent = name;
    main.appendChild(nameEl);

    if (opts.link) {
      var formLink = document.createElement("a");
      formLink.className = "doc-form-link";
      formLink.href = opts.link;
      formLink.target = "_blank";
      formLink.rel = "noopener noreferrer";
      formLink.textContent = "Download form ↗";
      main.appendChild(formLink);
    }

    var badge = document.createElement("span");
    badge.className = opts.optional ? "doc-badge doc-badge-optional" : "doc-badge doc-badge-required";
    badge.textContent = opts.optional ? "Optional" : "Required";
    main.appendChild(badge);

    row.appendChild(main);

    var uploadWrap = document.createElement("div");
    uploadWrap.className = "doc-row-upload";

    var label = document.createElement("label");
    label.className = "file-btn";
    label.textContent = "Choose file(s)";

    var input = document.createElement("input");
    input.type = "file";
    input.multiple = true;
    label.appendChild(input);
    uploadWrap.appendChild(label);

    var status = document.createElement("span");
    status.className = "file-status";
    status.textContent = "No file selected";
    status.setAttribute("data-file-status", "true");
    uploadWrap.appendChild(status);

    var cancelUploadBtn = document.createElement("button");
    cancelUploadBtn.type = "button";
    cancelUploadBtn.className = "cancel-upload-btn";
    cancelUploadBtn.setAttribute("aria-label", "Cancel upload for " + name);
    cancelUploadBtn.textContent = "Cancel upload";
    cancelUploadBtn.style.display = "none";
    cancelUploadBtn.addEventListener("click", function () {
      input.value = "";
      refreshFileState();
    });
    uploadWrap.appendChild(cancelUploadBtn);

    if (opts.optional) {
      var removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.className = "remove-doc-btn";
      removeBtn.setAttribute("aria-label", "Remove " + name);
      removeBtn.textContent = "Remove";
      removeBtn.addEventListener("click", function () {
        row.remove();
        if (opts.onRemove) opts.onRemove();
        updateProgress(opts.sectionId);
      });
      uploadWrap.appendChild(removeBtn);
    }

    row.appendChild(uploadWrap);

    function refreshFileState() {
      if (input.files && input.files.length > 0) {
        var names = Array.prototype.map.call(input.files, function (f) { return f.name; });
        status.textContent = names.join(", ");
        row.classList.add("doc-row-uploaded");
        cancelUploadBtn.style.display = "inline-block";
      } else {
        status.textContent = "No file selected";
        row.classList.remove("doc-row-uploaded");
        cancelUploadBtn.style.display = "none";
      }
      updateProgress(opts.sectionId);
      updateSubmitState();
    }

    input.addEventListener("change", refreshFileState);

    return row;
  }

  function updateProgress(sectionId) {
    var mandatoryList = document.querySelector('[data-mandatory-list="' + sectionId + '"]');
    var progressEl = document.querySelector('[data-progress-for="' + sectionId + '"]');
    if (!mandatoryList || !progressEl) return;
    var rows = mandatoryList.querySelectorAll("[data-doc-row]");
    var uploaded = mandatoryList.querySelectorAll(".doc-row-uploaded").length;
    progressEl.textContent = uploaded + " / " + rows.length + " uploaded";
  }

  function allMandatoryUploaded() {
    var allRows = document.querySelectorAll('[data-mandatory-list] [data-doc-row]');
    var uploadedRows = document.querySelectorAll('[data-mandatory-list] [data-doc-row].doc-row-uploaded');
    return allRows.length > 0 && allRows.length === uploadedRows.length;
  }

  function updateSubmitState() {
    var btn = document.getElementById("submit-application");
    var note = document.querySelector("[data-submit-note]");
    if (!btn || !note) return;
    if (allMandatoryUploaded()) {
      btn.disabled = false;
      note.textContent = "All mandatory documents received. Ready to submit.";
      note.classList.add("submit-note-ready");
    } else {
      btn.disabled = true;
      note.textContent = "Upload all mandatory documents to enable submission.";
      note.classList.remove("submit-note-ready");
    }
  }

  function buildMandatorySections() {
    Object.keys(SECTIONS).forEach(function (sectionId) {
      var list = document.querySelector('[data-mandatory-list="' + sectionId + '"]');
      if (!list) return;
      SECTIONS[sectionId].mandatory.forEach(function (doc) {
        var d = normalizeDoc(doc);
        var row = createDocRow(d.name, { multiple: d.multiple, link: d.link, optional: false, sectionId: sectionId });
        row.querySelector(".doc-name").setAttribute("data-source-name", d.name);
        list.appendChild(row);
      });
      updateProgress(sectionId);
    });
  }

  function buildAddOptionalControls() {
    var buttons = document.querySelectorAll("[data-add-optional]");
    buttons.forEach(function (btn) {
      btn.addEventListener("click", function () {
        var sectionId = btn.getAttribute("data-add-optional");
        openOptionalPicker(sectionId, btn);
      });
    });
  }

  function remainingOptionalDocs(sectionId) {
    var optionalList = document.querySelector('[data-optional-list="' + sectionId + '"]');
    var used = Array.prototype.map.call(
      optionalList.querySelectorAll(".doc-name"),
      function (el) { return el.getAttribute("data-source-name") || el.textContent; }
    );
    return SECTIONS[sectionId].optional
      .map(normalizeDoc)
      .filter(function (doc) { return used.indexOf(doc.name) === -1; });
  }

  function openOptionalPicker(sectionId, triggerBtn) {
    var existing = document.querySelector('[data-picker-for="' + sectionId + '"]');
    if (existing) {
      existing.remove();
      return;
    }

    var remaining = remainingOptionalDocs(sectionId);
    var linksByName = {};
    remaining.forEach(function (doc) { linksByName[doc.name] = doc.link; });

    var picker = document.createElement("div");
    picker.className = "optional-picker";
    picker.setAttribute("data-picker-for", sectionId);

    var select = document.createElement("select");
    remaining.forEach(function (doc) {
      var opt = document.createElement("option");
      opt.value = doc.name;
      opt.textContent = doc.name;
      select.appendChild(opt);
    });
    var otherOpt = document.createElement("option");
    otherOpt.value = OTHER_VALUE;
    otherOpt.textContent = "Other (specify)";
    select.appendChild(otherOpt);
    picker.appendChild(select);

    var otherInput = document.createElement("input");
    otherInput.type = "text";
    otherInput.placeholder = "Document name";
    otherInput.className = "optional-other-input";
    otherInput.style.display = "none";
    picker.appendChild(otherInput);

    select.addEventListener("change", function () {
      otherInput.style.display = select.value === OTHER_VALUE ? "inline-block" : "none";
    });
    if (select.value === OTHER_VALUE) otherInput.style.display = "inline-block";

    var confirmBtn = document.createElement("button");
    confirmBtn.type = "button";
    confirmBtn.className = "optional-confirm-btn";
    confirmBtn.textContent = "Add";
    confirmBtn.addEventListener("click", function () {
      var chosenName;
      if (select.value === OTHER_VALUE) {
        chosenName = otherInput.value.trim();
        if (!chosenName) {
          otherInput.focus();
          return;
        }
      } else {
        chosenName = select.value;
      }

      optionalRowCounter += 1;
      var optionalList = document.querySelector('[data-optional-list="' + sectionId + '"]');
      var chosenLink = select.value === OTHER_VALUE ? null : linksByName[chosenName];
      var row = createDocRow(chosenName, {
        optional: true,
        sectionId: sectionId,
        link: chosenLink,
        onRemove: function () { /* no-op, list re-derives from DOM */ }
      });
      var nameEl = row.querySelector(".doc-name");
      nameEl.setAttribute("data-source-name", chosenName);
      optionalList.appendChild(row);
      picker.remove();
    });
    picker.appendChild(confirmBtn);

    var cancelBtn = document.createElement("button");
    cancelBtn.type = "button";
    cancelBtn.className = "optional-cancel-btn";
    cancelBtn.textContent = "Cancel";
    cancelBtn.addEventListener("click", function () { picker.remove(); });
    picker.appendChild(cancelBtn);

    triggerBtn.insertAdjacentElement("afterend", picker);
  }

  function collectDocRows() {
    var rows = [];
    document.querySelectorAll(".doc-section").forEach(function (sectionEl) {
      var sectionId = sectionEl.id;
      sectionEl.querySelectorAll("[data-doc-row]").forEach(function (rowEl) {
        var input = rowEl.querySelector('input[type="file"]');
        var nameEl = rowEl.querySelector(".doc-name");
        rows.push({
          sectionId: sectionId,
          docName: nameEl.getAttribute("data-source-name") || nameEl.textContent,
          mandatory: !!rowEl.closest("[data-mandatory-list]"),
          input: input
        });
      });
    });
    return rows;
  }

  function buildSubmissionFormData() {
    var formData = new FormData();
    var manifest = [];
    var counter = 0;
    collectDocRows().forEach(function (row) {
      if (!row.input.files || row.input.files.length === 0) return;
      var fieldName = "file_" + (counter++);
      Array.prototype.forEach.call(row.input.files, function (f) {
        formData.append(fieldName, f, f.name);
      });
      manifest.push({
        section: row.sectionId,
        docName: row.docName,
        mandatory: row.mandatory,
        fieldName: fieldName
      });
    });
    formData.append("manifest", JSON.stringify(manifest));
    return formData;
  }

  function initSubmit() {
    var btn = document.getElementById("submit-application");
    btn.addEventListener("click", function () {
      if (btn.disabled) return;
      var note = document.querySelector("[data-submit-note]");
      btn.disabled = true;
      btn.textContent = "Submitting…";
      note.textContent = "Submitting application, please wait…";
      note.classList.remove("submit-note-error");

      fetch("/api/submit-application", { method: "POST", body: buildSubmissionFormData() })
        .then(function (resp) {
          return resp.json().then(function (data) { return { ok: resp.ok, data: data }; });
        })
        .then(function (result) {
          if (result.ok && result.data.success) {
            var params = new URLSearchParams({
              ref: result.data.referenceNumber || "",
              company: result.data.companyName || ""
            });
            window.location.href = "contact-info.html?" + params.toString();
          } else {
            note.textContent = "Submission failed: " + (result.data && result.data.error ? result.data.error : "Please try again.");
            note.classList.add("submit-note-error");
            btn.disabled = false;
            btn.textContent = "Submit Application";
          }
        })
        .catch(function () {
          note.textContent = "Network error — could not reach the server. Please try again.";
          note.classList.add("submit-note-error");
          btn.disabled = false;
          btn.textContent = "Submit Application";
        });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    buildMandatorySections();
    buildAddOptionalControls();
    initSubmit();
    updateSubmitState();
  });
})();
