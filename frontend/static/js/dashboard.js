const API_BASE_URL = window.location.origin;

const uploadForm = document.getElementById("uploadForm");
const documentType = document.getElementById("documentType");
const documentFile = document.getElementById("documentFile");
const processButton = document.getElementById("processButton");

const processingMessage = document.getElementById("processingMessage");
const errorMessage = document.getElementById("errorMessage");
const successMessage = document.getElementById("successMessage");

const documentsTableBody = document.getElementById("documentsTableBody");

const totalDocuments = document.getElementById("totalDocuments");
const passedDocuments = document.getElementById("passedDocuments");
const failedDocuments = document.getElementById("failedDocuments");

const resultPanel = document.getElementById("resultPanel");
const resultTitle = document.getElementById("resultTitle");
const resultDocumentType = document.getElementById("resultDocumentType");
const resultProcessingStatus = document.getElementById("resultProcessingStatus");
const resultFileValidation = document.getElementById("resultFileValidation");

const extractedDataContainer =
    document.getElementById("extractedDataContainer");

const validationContainer =
    document.getElementById("validationContainer");

const rawJson =
    document.getElementById("rawJson");

const refreshDocuments =
    document.getElementById("refreshDocuments");

const closeResult =
    document.getElementById("closeResult");

const copyJson =
    document.getElementById("copyJson");


function showMessage(element, message) {
    element.textContent = message;
    element.classList.remove("hidden");
}


function hideMessage(element) {
    element.classList.add("hidden");
}


function resetMessages() {
    hideMessage(processingMessage);
    hideMessage(errorMessage);
    hideMessage(successMessage);
}


/* Load documents from the API */

async function loadDocuments() {

    try {

        const response = await fetch(
            `${API_BASE_URL}/api/v1/documents`
        );

        if (!response.ok) {
            throw new Error("Unable to load documents.");
        }

        const data = await response.json();

        const documents = data.documents || [];

        renderDocuments(documents);
        updateStatistics(documents);

    } catch (error) {

        documentsTableBody.innerHTML = `
            <tr>
                <td colspan="5" class="empty-state">
                    Unable to load documents.
                </td>
            </tr>
        `;

        console.error(error);
    }
}


/* Render document table */

function renderDocuments(documents) {

    if (!documents.length) {

        documentsTableBody.innerHTML = `
            <tr>
                <td colspan="5" class="empty-state">
                    No processed documents found.
                </td>
            </tr>
        `;

        return;
    }

    documentsTableBody.innerHTML = documents.map(document => {

        const status = document.processing_status || "UNKNOWN";

        const statusClass =
            status === "PASS"
                ? "status-pass"
                : "status-failed";

        const encodedName =
            encodeURIComponent(document.document_name);

        return `
            <tr>

                <td>
                    <strong>${escapeHtml(document.document_name)}</strong>
                </td>

                <td>
                    ${escapeHtml(document.document_type || "-")}
                </td>

                <td>
                    <span class="status-badge ${statusClass}">
                        ${escapeHtml(status)}
                    </span>
                </td>

                <td>
                    ${formatDate(document.created_at)}
                </td>

                <td>
                    <button
                        class="secondary-button"
                        onclick="openDocument('${encodedName}')"
                    >
                        View
                    </button>
                </td>

            </tr>
        `;

    }).join("");
}


/* Statistics */

function updateStatistics(documents) {

    totalDocuments.textContent = documents.length;

    const passed = documents.filter(
        document => document.processing_status === "PASS"
    ).length;

    const failed = documents.filter(
        document => document.processing_status === "FAILED"
    ).length;

    passedDocuments.textContent = passed;
    failedDocuments.textContent = failed;
}


/* Process document */

uploadForm.addEventListener("submit", async function(event) {

    event.preventDefault();

    resetMessages();

    const type = documentType.value;
    const file = documentFile.files[0];

    if (!type) {
        showMessage(errorMessage, "Please select a document type.");
        return;
    }

    if (!file) {
        showMessage(errorMessage, "Please select a document file.");
        return;
    }

    const formData = new FormData();

    formData.append("file", file);
    formData.append("document_type", type);

    processButton.disabled = true;

    const buttonText = processButton.querySelector("span");

    if (buttonText) {
        buttonText.textContent = "Processing...";
    }

    showMessage(
        processingMessage,
        "Processing document. Please wait..."
    );

    try {

        const response = await fetch(
            `${API_BASE_URL}/api/v1/documents/process`,
            {
                method: "POST",
                body: formData
            }
        );

        const data = await response.json();

        /*
         * Backend error responses use:
         *
         * {
         *     "error": {
         *         "code": "...",
         *         "message": "..."
         *     }
         * }
         *
         * Therefore we must read data.error.message
         * instead of displaying data.error directly.
         */

        if (!response.ok) {

            const backendMessage =
                data?.error?.message ||
                data?.message ||
                "Document processing failed.";

            throw new Error(backendMessage);
        }

        hideMessage(processingMessage);

        /*
         * A financial validation failure can still return HTTP 200
         * because the document was successfully processed but failed
         * a financial calculation check.
         */

        if (data.processing_status === "FAILED") {

            showMessage(
                errorMessage,
                `Document "${data.document_name}" was processed, but validation FAILED.`
            );

        } else {

            showMessage(
                successMessage,
                `Document "${data.document_name}" processed successfully.`
            );
        }

        uploadForm.reset();

        await loadDocuments();

        displayResult(data);

    } catch (error) {

        hideMessage(processingMessage);

        showMessage(
            errorMessage,
            error.message || "An unexpected error occurred."
        );

        console.error(error);

    } finally {

        processButton.disabled = false;

        if (buttonText) {
            buttonText.textContent = "Process Document";
        }
    }
});


/* Open a stored document */

async function openDocument(encodedName) {

    const documentName = decodeURIComponent(encodedName);

    resetMessages();

    try {

        const response = await fetch(
            `${API_BASE_URL}/api/v1/documents/${encodeURIComponent(documentName)}`
        );

        const data = await response.json();

        if (!response.ok) {

            const backendMessage =
                data?.error?.message ||
                data?.message ||
                "Unable to retrieve document.";

            throw new Error(backendMessage);
        }

        displayResult(data);

    } catch (error) {

        showMessage(
            errorMessage,
            error.message || "Unable to retrieve document."
        );

        console.error(error);
    }
}


/* Display result */

function displayResult(data) {

    resultPanel.classList.remove("hidden");

    resultTitle.textContent =
        data.document_name || "Document Result";

    resultDocumentType.textContent =
        data.document_type || "-";

    resultProcessingStatus.textContent =
        data.processing_status || "-";

    resultFileValidation.textContent =
        data.file_validation?.status || "-";

    renderExtractedData(data.extracted_data);
    renderValidation(data.validation);

    rawJson.textContent =
        JSON.stringify(data, null, 2);

    resultPanel.scrollIntoView({
        behavior: "smooth",
        block: "start"
    });
}


/* Render extracted data */

function renderExtractedData(data) {

    if (!data) {

        extractedDataContainer.innerHTML =
            "<p>No extracted data available.</p>";

        return;
    }

    let html = "";


    /* Metadata */

    if (data.document_metadata) {

        html += `
            <h5>Document Metadata</h5>

            <div class="table-wrapper">

                <table>

                    <tbody>

                        ${Object.entries(data.document_metadata)
                            .map(([key, value]) => `
                                <tr>
                                    <td>
                                        <strong>${escapeHtml(key)}</strong>
                                    </td>

                                    <td>
                                        ${escapeHtml(value ?? "null")}
                                    </td>
                                </tr>
                            `)
                            .join("")}

                    </tbody>

                </table>

            </div>
        `;
    }


    /* Fields */

    if (data.fields && data.fields.length) {

        html += `
            <h5>Fields</h5>

            <div class="table-wrapper">

                <table>

                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>Value</th>
                            <th>Page</th>
                            <th>Evidence</th>
                        </tr>
                    </thead>

                    <tbody>

                        ${data.fields.map(field => `
                            <tr>

                                <td>
                                    ${escapeHtml(field.name)}
                                </td>

                                <td>
                                    ${escapeHtml(field.value ?? "null")}
                                </td>

                                <td>
                                    ${escapeHtml(field.page_number ?? "-")}
                                </td>

                                <td>
                                    ${escapeHtml(field.evidence ?? "-")}
                                </td>

                            </tr>
                        `).join("")}

                    </tbody>

                </table>

            </div>
        `;
    }


    /* Line items */

    if (data.line_items && data.line_items.length) {

        html += `
            <h5>Line Items</h5>

            <div class="table-wrapper">

                <table>

                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>Value</th>
                            <th>Period</th>
                            <th>Page</th>
                        </tr>
                    </thead>

                    <tbody>

                        ${data.line_items.map(item => `
                            <tr>

                                <td>
                                    ${escapeHtml(item.name)}
                                </td>

                                <td>
                                    ${escapeHtml(item.value ?? "null")}
                                </td>

                                <td>
                                    ${escapeHtml(item.period ?? "-")}
                                </td>

                                <td>
                                    ${escapeHtml(item.page_number ?? "-")}
                                </td>

                            </tr>
                        `).join("")}

                    </tbody>

                </table>

            </div>
        `;
    }


    /* Tables */

    if (data.tables && data.tables.length) {

        data.tables.forEach(table => {

            html += `
                <h5>
                    ${escapeHtml(table.title || "Extracted Table")}
                </h5>

                <div class="table-wrapper">

                    <table>

                        <thead>

                            <tr>
                                ${table.columns.map(column => `
                                    <th>
                                        ${escapeHtml(column)}
                                    </th>
                                `).join("")}
                            </tr>

                        </thead>

                        <tbody>

                            ${table.rows.map(row => `
                                <tr>

                                    ${row.map(value => `
                                        <td>
                                            ${escapeHtml(value ?? "null")}
                                        </td>
                                    `).join("")}

                                </tr>
                            `).join("")}

                        </tbody>

                    </table>

                </div>
            `;

        });
    }


    extractedDataContainer.innerHTML =
        html || "<p>No extracted data available.</p>";
}


/* Render financial validation */

function renderValidation(validation) {

    if (!validation) {

        validationContainer.innerHTML =
            "<p>No validation result available.</p>";

        return;
    }

    let html = "";


    if (Array.isArray(validation.checks)) {

        html += `
            <div class="table-wrapper">

                <table>

                    <thead>

                        <tr>
                            <th>Check</th>
                            <th>Status</th>
                            <th>Calculated</th>
                            <th>Reported</th>
                            <th>Variance</th>
                        </tr>

                    </thead>

                    <tbody>

                        ${validation.checks.map(check => {

                            const status =
                                check.status || "-";

                            const statusClass =
                                status === "PASS"
                                    ? "status-pass"
                                    : "status-failed";

                            return `
                                <tr>

                                    <td>
                                        ${escapeHtml(
                                            check.check || "-"
                                        )}
                                    </td>

                                    <td>
                                        <span class="status-badge ${statusClass}">
                                            ${escapeHtml(status)}
                                        </span>
                                    </td>

                                    <td>
                                        ${escapeHtml(
                                            check.calculated ?? "-"
                                        )}
                                    </td>

                                    <td>
                                        ${escapeHtml(
                                            check.reported ?? "-"
                                        )}
                                    </td>

                                    <td>
                                        ${escapeHtml(
                                            check.variance ?? "-"
                                        )}
                                    </td>

                                </tr>
                            `;

                        }).join("")}

                    </tbody>

                </table>

            </div>
        `;
    }

    validationContainer.innerHTML =
        html || "<p>No validation checks available.</p>";
}


/* Close result */

closeResult.addEventListener("click", function() {

    resultPanel.classList.add("hidden");

});


/* Refresh */

refreshDocuments.addEventListener("click", function() {

    loadDocuments();

});


/* Copy JSON */

copyJson.addEventListener("click", async function() {

    try {

        await navigator.clipboard.writeText(
            rawJson.textContent
        );

        copyJson.textContent = "Copied!";

        setTimeout(() => {
            copyJson.textContent = "Copy JSON";
        }, 1500);

    } catch (error) {

        console.error(error);
    }

});


/* Utility */

function escapeHtml(value) {

    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}


function formatDate(value) {

    if (!value) {
        return "-";
    }

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
        return value;
    }

    return date.toLocaleString();
}


/* Initial load */

loadDocuments();