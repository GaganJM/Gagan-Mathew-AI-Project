(function () {
  "use strict";

  var DOWNLOADABLE_FORMS_URL = "https://www.rakbank.ae/en/help-centre/support/downloadable-forms";
  var CUSTOMER_INFORMATION_FORM_URL = "https://www.rakbank.ae/globalassets/rakbank/all-pdfs/001---downloadable-forms/account-services/aj00635rakcustomerinformationformindividual-editable.pdf";
  var INDIVIDUAL_FATCA_CRS_FORM_URL = "https://www.rakbank.ae/globalassets/rakbank/all-pdfs/001---downloadable-forms/kyc-updates/individual-self-certification-fatca--crs_v082020.pdf";

  var SECTION_ID = "maintenance-documents";

  var CHANGE_LABELS = {
    "additional-signatory": "Addition of a Signatory",
    "deletion-signatory": "Deletion of Signatory",
    "signing-instructions": "Change in Signing Instructions",
    "company-name": "Change Company Name",
    "shareholders": "Change in Shareholders"
  };

  var DOCUMENT_CATALOG = {
    "additional-signatory": [
      { name: "Customer Information File", level: "mandatory", link: CUSTOMER_INFORMATION_FORM_URL, bankForm: true },
      { name: "Individual FATCA & CRS", level: "mandatory", link: INDIVIDUAL_FATCA_CRS_FORM_URL, bankForm: true },
      { name: "Address Proof of the Signatory", level: "mandatory" },
      { name: "Specimen Signature of the Signatory", level: "mandatory" },
      { name: "Resolution Appointing Signatory with Banking Powers / Bank Mandate", level: "mandatory" },
      { name: "Passport and Emirates ID of the New Signatory", level: "mandatory" }
    ],
    "deletion-signatory": [
      { name: "Customer Letter for Deletion", level: "mandatory" },
      { name: "New Bank Mandate", level: "optional" }
    ],
    "signing-instructions": [
      { name: "New Bank Mandate", level: "mandatory" }
    ],
    "company-name": [
      { name: "Customer Letter (Bank standard form if required)", level: "mandatory", link: DOWNLOADABLE_FORMS_URL, bankForm: true },
      { name: "New Trade License", level: "mandatory" },
      { name: "Amended MOA or AOA", level: "mandatory" },
      { name: "List of Cheques to be Honored Under the Old Name", level: "optional" }
    ],
    "shareholders": [
      { name: "New Trade License", level: "mandatory" },
      { name: "Share Sale Agreement", level: "mandatory" },
      { name: "Amended MOA or AOA", level: "mandatory" }
    ]
  };

  var companyName = sessionStorage.getItem("maintenanceCompanyName");
  var identifierType = sessionStorage.getItem("maintenanceIdentifierType");
  var identifierValue = sessionStorage.getItem("maintenanceIdentifierValue");

  if (!companyName || !identifierType || !identifierValue) {
    window.location.href = "account-maintenance-identify.html";
    return;
  }

  var params = new URLSearchParams(window.location.search);
  var changesParam = params.get("changes");
  var selected = (changesParam ? changesParam.split(",") : JSON.parse(sessionStorage.getItem("maintenanceChangeTypes") || "[]"))
    .filter(function (v) { return CHANGE_LABELS.hasOwnProperty(v); });

  if (selected.length === 0) {
    window.location.href = "account-maintenance.html";
    return;
  }

  sessionStorage.setItem("maintenanceChangeTypes", JSON.stringify(selected));

  var identifierLabel = identifierType === "cif" ? "CIF" : "Account Number";
  var selectedLabels = selected.map(function (v) { return CHANGE_LABELS[v]; });
  document.getElementById("selected-changes-line").textContent =
    "For " + companyName + " (" + identifierLabel + ": " + identifierValue + "). Change(s) selected: " +
    selectedLabels.join(", ") + ". Please upload the following documents.";

  // Merge each selected change type's document list into one index, keyed by
  // document name so a document required by more than one change type is
  // only listed once. A document counts as mandatory overall if ANY selected
  // change type requires it as mandatory, even if another change type only
  // lists it as optional.
  var docIndex = new Map();
  selected.forEach(function (typeVal) {
    (DOCUMENT_CATALOG[typeVal] || []).forEach(function (doc) {
      var entry = docIndex.get(doc.name);
      if (!entry) {
        entry = { link: doc.link || null, mandatoryFor: [], optionalFor: [], bankForm: false };
        docIndex.set(doc.name, entry);
      }
      if (!entry.link && doc.link) entry.link = doc.link;
      if (doc.bankForm) entry.bankForm = true;
      var list = doc.level === "mandatory" ? entry.mandatoryFor : entry.optionalFor;
      list.push(CHANGE_LABELS[typeVal]);
    });
  });

  var GENERIC_OPTIONAL_DOCS = [
    { name: "Supporting Documents" },
    { name: "Others" }
  ];

  var mandatoryDocs = [];
  var optionalDocs = [];
  docIndex.forEach(function (entry, name) {
    if (entry.mandatoryFor.length > 0) {
      mandatoryDocs.push({ name: name, link: entry.link, requiredFor: entry.mandatoryFor, bankForm: entry.bankForm });
    } else {
      optionalDocs.push({ name: name, link: entry.link, relevantFor: entry.optionalFor });
    }
  });

  GENERIC_OPTIONAL_DOCS.forEach(function (doc) {
    if (!optionalDocs.some(function (d) { return d.name === doc.name; })) {
      optionalDocs.push({ name: doc.name, link: null, relevantFor: [] });
    }
  });

  function createDocRow(name, opts) {
    opts = opts || {};
    var row = document.createElement("div");
    row.className = "doc-row";
    row.setAttribute("data-doc-row", "true");

    var main = document.createElement("div");
    main.className = "doc-row-main";

    var nameWrap = document.createElement("div");
    nameWrap.className = "doc-name-wrap";

    var nameEl = document.createElement("span");
    nameEl.className = "doc-name";
    nameEl.textContent = name;
    nameWrap.appendChild(nameEl);

    if (opts.captionLabel && opts.captionList && opts.captionList.length > 0) {
      var caption = document.createElement("span");
      caption.className = "doc-required-for";
      caption.textContent = opts.captionLabel + opts.captionList.join(", ");
      nameWrap.appendChild(caption);
    }

    main.appendChild(nameWrap);

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
        updateProgress();
        updateSubmitState();
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
      updateProgress();
      updateSubmitState();
    }

    input.addEventListener("change", refreshFileState);

    return row;
  }

  function updateProgress() {
    var mandatoryList = document.querySelector('[data-mandatory-list="' + SECTION_ID + '"]');
    var progressEl = document.querySelector('[data-progress-for="' + SECTION_ID + '"]');
    if (!mandatoryList || !progressEl) return;
    var rows = mandatoryList.querySelectorAll("[data-doc-row]");
    var uploaded = mandatoryList.querySelectorAll(".doc-row-uploaded").length;
    progressEl.textContent = uploaded + " / " + rows.length + " uploaded";
  }

  function allMandatoryUploaded() {
    var mandatoryList = document.querySelector('[data-mandatory-list="' + SECTION_ID + '"]');
    var allRows = mandatoryList.querySelectorAll("[data-doc-row]");
    var uploadedRows = mandatoryList.querySelectorAll(".doc-row-uploaded");
    return allRows.length > 0 && allRows.length === uploadedRows.length;
  }

  function updateSubmitState() {
    var btn = document.getElementById("submit-maintenance");
    var note = document.querySelector("[data-submit-note]");

    if (allMandatoryUploaded()) {
      btn.disabled = false;
      note.textContent = "All mandatory documents received. Ready to submit.";
      note.classList.add("submit-note-ready");
      note.classList.remove("submit-note-error");
    } else {
      btn.disabled = true;
      note.textContent = "Upload all mandatory documents to enable submission.";
      note.classList.remove("submit-note-ready", "submit-note-error");
    }
  }

  function buildMandatoryRows() {
    var list = document.querySelector('[data-mandatory-list="' + SECTION_ID + '"]');
    mandatoryDocs.forEach(function (doc) {
      var row = createDocRow(doc.name, {
        link: doc.link,
        captionLabel: "Required for: ",
        captionList: doc.requiredFor
      });
      var nameEl = row.querySelector(".doc-name");
      nameEl.setAttribute("data-source-name", doc.name);
      if (doc.bankForm) nameEl.setAttribute("data-bank-form", "true");
      list.appendChild(row);
    });
    updateProgress();
  }

  function remainingOptionalDocs() {
    var optionalList = document.querySelector('[data-optional-list="' + SECTION_ID + '"]');
    var used = Array.prototype.map.call(
      optionalList.querySelectorAll(".doc-name"),
      function (el) { return el.getAttribute("data-source-name") || el.textContent; }
    );
    return optionalDocs.filter(function (doc) { return used.indexOf(doc.name) === -1; });
  }

  function updateAddOptionalVisibility() {
    var addBtn = document.getElementById("add-optional-btn");
    if (optionalDocs.length === 0) {
      addBtn.style.display = "none";
      return;
    }
    addBtn.style.display = remainingOptionalDocs().length > 0 ? "inline-block" : "none";
  }

  function openOptionalPicker(triggerBtn) {
    var existing = document.querySelector("[data-picker-for]");
    if (existing) {
      existing.remove();
      return;
    }

    var remaining = remainingOptionalDocs();
    if (remaining.length === 0) return;

    var picker = document.createElement("div");
    picker.className = "optional-picker";
    picker.setAttribute("data-picker-for", SECTION_ID);

    var select = document.createElement("select");
    remaining.forEach(function (doc) {
      var opt = document.createElement("option");
      opt.value = doc.name;
      opt.textContent = doc.name;
      select.appendChild(opt);
    });
    picker.appendChild(select);

    var confirmBtn = document.createElement("button");
    confirmBtn.type = "button";
    confirmBtn.className = "optional-confirm-btn";
    confirmBtn.textContent = "Add";
    confirmBtn.addEventListener("click", function () {
      var chosen = remaining.filter(function (d) { return d.name === select.value; })[0];
      if (!chosen) return;

      var optionalList = document.querySelector('[data-optional-list="' + SECTION_ID + '"]');
      var row = createDocRow(chosen.name, {
        optional: true,
        link: chosen.link,
        captionLabel: "Optional — relevant for: ",
        captionList: chosen.relevantFor
      });
      row.querySelector(".doc-name").setAttribute("data-source-name", chosen.name);
      optionalList.appendChild(row);
      picker.remove();
      updateAddOptionalVisibility();
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

  function initOptionalPicker() {
    var addBtn = document.getElementById("add-optional-btn");
    addBtn.addEventListener("click", function () { openOptionalPicker(addBtn); });
    updateAddOptionalVisibility();
  }

  function collectDocRows() {
    var rows = [];
    document.querySelectorAll("[data-doc-row]").forEach(function (rowEl) {
      var input = rowEl.querySelector('input[type="file"]');
      var nameEl = rowEl.querySelector(".doc-name");
      rows.push({
        docName: nameEl.getAttribute("data-source-name") || nameEl.textContent,
        mandatory: !!rowEl.closest("[data-mandatory-list]"),
        bankForm: nameEl.getAttribute("data-bank-form") === "true",
        input: input
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
        section: SECTION_ID,
        docName: row.docName,
        mandatory: row.mandatory,
        bankForm: row.bankForm,
        fieldName: fieldName
      });
    });
    formData.append("manifest", JSON.stringify(manifest));
    formData.append("companyName", companyName);
    formData.append("identifierType", identifierType);
    formData.append("identifierValue", identifierValue);
    formData.append("changeTypes", JSON.stringify(selected));
    return formData;
  }

  function initSubmit() {
    var btn = document.getElementById("submit-maintenance");
    var note = document.querySelector("[data-submit-note]");
    btn.addEventListener("click", function () {
      if (btn.disabled) return;
      btn.disabled = true;
      btn.textContent = "Submitting…";
      note.textContent = "Submitting request, please wait…";
      note.classList.remove("submit-note-error");

      fetch("/api/submit-maintenance-request", { method: "POST", body: buildSubmissionFormData() })
        .then(function (resp) {
          return resp.json().then(function (data) { return { ok: resp.ok, data: data }; });
        })
        .then(function (result) {
          if (result.ok && result.data.success) {
            var outParams = new URLSearchParams({
              ref: result.data.referenceNumber || "",
              company: result.data.companyName || ""
            });
            window.location.href = "contact-info.html?" + outParams.toString();
          } else {
            note.textContent = "Submission failed: " + (result.data && result.data.error ? result.data.error : "Please try again.");
            note.classList.add("submit-note-error");
            btn.disabled = false;
            btn.textContent = "Submit Request";
          }
        })
        .catch(function () {
          note.textContent = "Network error — could not reach the server. Please try again.";
          note.classList.add("submit-note-error");
          btn.disabled = false;
          btn.textContent = "Submit Request";
        });
    });
  }

  buildMandatoryRows();
  initOptionalPicker();
  initSubmit();
  updateSubmitState();
})();
