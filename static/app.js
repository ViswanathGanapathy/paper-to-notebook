/* Paper-to-Notebook — Frontend Logic */
(function () {
    "use strict";

    // ── State ───────────────────────────────────────────
    var apiKey = "";
    var selectedFile = null;

    // ── DOM References ──────────────────────────────────
    var phaseApiKey = document.getElementById("phase-api-key");
    var phaseUpload = document.getElementById("phase-upload");
    var phaseResults = document.getElementById("phase-results");

    var apiKeyInput = document.getElementById("api-key-input");
    var apiKeySubmit = document.getElementById("api-key-submit");
    var apiKeyError = document.getElementById("api-key-error");

    var uploadZone = document.getElementById("upload-zone");
    var fileInput = document.getElementById("file-input");
    var fileSelected = document.getElementById("file-selected");
    var fileName = document.getElementById("file-name");
    var fileSize = document.getElementById("file-size");
    var generateBtnWrap = document.getElementById("generate-btn-wrap");
    var generateBtn = document.getElementById("generate-btn");

    var statusLog = document.getElementById("status-log");
    var progressPulse = document.getElementById("progress-pulse");
    var actionButtons = document.getElementById("action-buttons");
    var downloadBtn = document.getElementById("download-btn");
    var colabBtn = document.getElementById("colab-btn");

    var historyPanel = document.getElementById("history-panel");
    var historyList = document.getElementById("history-list");

    // ── Phase Transitions ───────────────────────────────
    function showPhase(phase) {
        [phaseApiKey, phaseUpload, phaseResults].forEach(function (p) {
            p.classList.add("hidden");
        });
        phase.classList.remove("hidden");

        // Show history panel alongside the upload phase
        if (phase === phaseUpload) {
            loadHistory();
        } else {
            historyPanel.classList.add("hidden");
        }
    }

    // ── Phase 1: API Key ────────────────────────────────
    function handleApiKeySubmit() {
        var key = apiKeyInput.value.trim();

        if (!key) {
            showError(apiKeyError, "Please enter your OpenAI API key.");
            return;
        }

        if (!key.startsWith("sk-")) {
            showError(apiKeyError, "API key should start with 'sk-'.");
            return;
        }

        apiKey = key;
        hideError(apiKeyError);
        showPhase(phaseUpload);
    }

    apiKeySubmit.addEventListener("click", handleApiKeySubmit);

    apiKeyInput.addEventListener("keydown", function (e) {
        if (e.key === "Enter") {
            handleApiKeySubmit();
        }
    });

    // ── Phase 2: Upload ─────────────────────────────────
    uploadZone.addEventListener("click", function () {
        fileInput.click();
    });

    uploadZone.addEventListener("dragover", function (e) {
        e.preventDefault();
        uploadZone.classList.add("drag-over");
    });

    uploadZone.addEventListener("dragleave", function () {
        uploadZone.classList.remove("drag-over");
    });

    uploadZone.addEventListener("drop", function (e) {
        e.preventDefault();
        uploadZone.classList.remove("drag-over");
        var files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFile(files[0]);
        }
    });

    fileInput.addEventListener("change", function () {
        if (fileInput.files.length > 0) {
            handleFile(fileInput.files[0]);
        }
    });

    function handleFile(file) {
        if (file.type !== "application/pdf") {
            alert("Please upload a PDF file.");
            return;
        }

        selectedFile = file;
        fileName.textContent = file.name;
        fileSize.textContent = formatSize(file.size);
        fileSelected.classList.add("visible");
        generateBtnWrap.classList.add("visible");
    }

    function formatSize(bytes) {
        if (bytes < 1024) return bytes + " B";
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
        return (bytes / (1024 * 1024)).toFixed(1) + " MB";
    }

    generateBtn.addEventListener("click", function () {
        if (!selectedFile) return;
        startGeneration();
    });

    // ── Phase 3: Generation via SSE ─────────────────────
    function startGeneration() {
        showPhase(phaseResults);
        statusLog.textContent = "";
        progressPulse.classList.add("active");
        actionButtons.classList.remove("visible");

        addStatus("Uploading paper and starting generation...", true);

        var formData = new FormData();
        formData.append("file", selectedFile);

        // API key sent via header, not form body (SEC-001)
        fetch("/api/generate", {
            method: "POST",
            headers: { "X-API-Key": apiKey },
            body: formData,
        })
            .then(function (response) {
                if (!response.ok) {
                    return response.json().then(function (err) {
                        throw new Error(err.detail || "Upload failed");
                    });
                }
                return readSSEStream(response.body.getReader());
            })
            .catch(function (err) {
                addStatus("Error: " + err.message, false);
                progressPulse.classList.remove("active");
                showRetryButton();
            });
    }

    function readSSEStream(reader) {
        var decoder = new TextDecoder();
        var buffer = "";

        function processChunk(result) {
            if (result.done) {
                // Process any remaining data in buffer
                if (buffer.trim()) {
                    parseSSEBuffer(buffer);
                }
                return;
            }

            buffer += decoder.decode(result.value, { stream: true });

            // Split on double newline (SSE event boundary)
            var parts = buffer.split("\n\n");
            // Keep the last partial chunk in buffer
            buffer = parts.pop() || "";

            parts.forEach(function (eventBlock) {
                parseSSEBlock(eventBlock.trim());
            });

            return reader.read().then(processChunk);
        }

        return reader.read().then(processChunk);
    }

    function parseSSEBuffer(text) {
        var blocks = text.split("\n\n");
        blocks.forEach(function (block) {
            if (block.trim()) {
                parseSSEBlock(block.trim());
            }
        });
    }

    function parseSSEBlock(block) {
        var eventType = "";
        var data = "";

        block.split("\n").forEach(function (line) {
            line = line.trim();
            if (line.startsWith("event:")) {
                eventType = line.substring(6).trim();
            } else if (line.startsWith("data:")) {
                data = line.substring(5).trim();
            }
        });

        if (!eventType || !data) return;

        var parsed;
        try {
            parsed = JSON.parse(data);
        } catch (e) {
            return;
        }

        if (eventType === "status") {
            // Mark previous active entries as done
            markPreviousComplete();
            addStatus(parsed.message, true);
        } else if (eventType === "complete") {
            markPreviousComplete();
            progressPulse.classList.remove("active");
            addStatus("Notebook ready for download!", false);

            var fileId = parsed.file_id;
            var downloadUrl = "/api/download/" + encodeURIComponent(fileId);

            // Build Colab URL using the current origin
            var notebookPath = parsed.notebook_path || ("/api/notebook/" + encodeURIComponent(fileId));
            var fullNotebookUrl = window.location.origin + notebookPath;
            var colabUrl = "https://colab.research.google.com/url=" + encodeURIComponent(fullNotebookUrl);

            showComplete(downloadUrl, colabUrl);
        } else if (eventType === "error") {
            markPreviousComplete();
            progressPulse.classList.remove("active");
            addStatus("Error: " + parsed.message, false);
            showRetryButton();
        }
    }

    function markPreviousComplete() {
        var entries = statusLog.querySelectorAll(".status-entry.active");
        for (var i = 0; i < entries.length; i++) {
            entries[i].classList.remove("active");
            var icon = entries[i].querySelector(".status-icon");
            if (icon) icon.textContent = "\u2713";
        }
    }

    function addStatus(text, active) {
        var entry = document.createElement("div");
        entry.className = "status-entry" + (active ? " active" : "");

        var icon = document.createElement("span");
        icon.className = "status-icon";
        icon.textContent = active ? "\u25CF" : "\u2713";

        var span = document.createElement("span");
        span.className = "status-text";
        span.textContent = text;

        entry.appendChild(icon);
        entry.appendChild(span);
        statusLog.appendChild(entry);
        statusLog.scrollTop = statusLog.scrollHeight;
    }

    function showComplete(downloadUrl, colabUrl) {
        actionButtons.classList.add("visible");
        if (downloadUrl) downloadBtn.href = downloadUrl;
        if (colabUrl) colabBtn.href = colabUrl;
    }

    function showRetryButton() {
        // Show a retry option by making action buttons visible with a "Try Again" approach
        var existing = document.getElementById("retry-btn");
        if (existing) return;

        var retryBtn = document.createElement("button");
        retryBtn.id = "retry-btn";
        retryBtn.className = "btn-primary";
        retryBtn.textContent = "Try Again";
        retryBtn.setAttribute("data-testid", "retry-btn");
        retryBtn.style.width = "100%";
        retryBtn.style.marginTop = "16px";
        retryBtn.addEventListener("click", function () {
            retryBtn.remove();
            showPhase(phaseUpload);
        });
        statusLog.parentNode.appendChild(retryBtn);
    }

    // ── Utilities ───────────────────────────────────────
    function showError(el, msg) {
        el.textContent = msg;
        el.classList.add("visible");
    }

    function hideError(el) {
        el.textContent = "";
        el.classList.remove("visible");
    }

    // ── History ─────────────────────────────────────────
    function loadHistory() {
        fetch("/api/history")
            .then(function (response) { return response.json(); })
            .then(function (entries) {
                if (!entries || entries.length === 0) {
                    historyPanel.classList.add("hidden");
                    return;
                }
                historyPanel.classList.remove("hidden");
                historyList.textContent = "";
                entries.forEach(function (entry) {
                    var item = document.createElement("div");
                    item.className = "history-item";

                    var title = document.createElement("span");
                    title.className = "history-item-title";
                    title.textContent = entry.title || "Untitled";

                    var time = document.createElement("span");
                    time.className = "history-item-time";
                    var date = new Date(entry.timestamp * 1000);
                    time.textContent = date.toLocaleTimeString();

                    var actions = document.createElement("span");
                    actions.className = "history-item-actions";

                    var dl = document.createElement("a");
                    dl.href = "/api/download/" + encodeURIComponent(entry.file_id);
                    dl.textContent = "Download";
                    dl.setAttribute("download", "");

                    actions.appendChild(dl);
                    item.appendChild(title);
                    item.appendChild(time);
                    item.appendChild(actions);
                    historyList.appendChild(item);
                });
            })
            .catch(function () {
                historyPanel.classList.add("hidden");
            });
    }

    // ── Expose for testing (no sensitive data) ─────────
    window.P2N = {
        addStatus: addStatus,
        showComplete: showComplete,
        showPhase: showPhase,
        phaseResults: phaseResults,
    };
})();
