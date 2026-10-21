const toolDetails = {
  merge: { title: "Merge PDF", description: "Put your PDFs in the order you want them combined.", accept: ".pdf,application/pdf", multiple: true, label: "Merge PDF", hint: "PDF files · up to 100 MB" },
  split: { title: "Split PDF", description: "Save individual pages or choose page ranges to split out.", accept: ".pdf,application/pdf", multiple: false, label: "Split PDF", hint: "PDF files · up to 100 MB" },
  compress: { title: "Compress PDF", description: "Reduce file size while preserving readable pages.", accept: ".pdf,application/pdf", multiple: false, label: "Compress PDF", hint: "PDF files · up to 100 MB" },
  rotate: { title: "Rotate PDF", description: "Turn every page in your document in one go.", accept: ".pdf,application/pdf", multiple: false, label: "Rotate PDF", hint: "PDF files · up to 100 MB" },
  "images-to-pdf": { title: "Image to PDF", description: "Combine JPG and PNG images into a single PDF.", accept: ".jpg,.jpeg,.png,image/jpeg,image/png", multiple: true, label: "Create PDF", hint: "JPG or PNG images · up to 100 MB" },
};

const dialog = document.querySelector("#tool-dialog");
const form = document.querySelector("#job-form");
const fileInput = document.querySelector("#file-input");
const dropZone = document.querySelector("#drop-zone");
const fileList = document.querySelector("#file-list");
const processButton = document.querySelector("#process-button");
const processLabel = document.querySelector("#process-label");
const jobError = document.querySelector("#job-error");
const jobSuccess = document.querySelector("#job-success");
const historyBody = document.querySelector("#history-body");
const heroDropZone = document.querySelector("#hero-drop-zone");
const heroFileInput = document.querySelector("#hero-file-input");
const heroError = document.querySelector("#hero-error");
const toolPicker = document.querySelector("#tool-picker-dialog");
const quickToolList = document.querySelector("#quick-tool-list");
let activeTool = "merge";
let queuedFiles = [];
let heroFiles = [];

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function openTool(tool, initialFiles = []) {
  activeTool = tool;
  queuedFiles = [...initialFiles];
  const details = toolDetails[tool];
  document.querySelector("#dialog-kicker").textContent = `${tool === "images-to-pdf" ? "CONVERT" : tool.toUpperCase()} TOOL`;
  document.querySelector("#dialog-title").textContent = details.title;
  document.querySelector("#dialog-description").textContent = details.description;
  document.querySelector("#accepted-types").textContent = details.hint;
  processLabel.textContent = details.label;
  fileInput.accept = details.accept;
  fileInput.multiple = details.multiple;
  document.querySelector("#split-options").hidden = tool !== "split";
  document.querySelector("#rotate-options").hidden = tool !== "rotate";
  document.querySelector("#page-ranges").value = "";
  document.querySelector("#rotation").value = "90";
  jobError.hidden = true;
  jobSuccess.hidden = true;
  renderFileList();
  dialog.showModal();
}

function showToolPicker(files) {
  heroError.hidden = true;
  const selectedFiles = [...files];
  const pdfFiles = selectedFiles.filter((file) => file.name.toLowerCase().endsWith(".pdf"));
  const imageFiles = selectedFiles.filter((file) => /\.(jpe?g|png)$/i.test(file.name));
  if (!selectedFiles.length || (pdfFiles.length && imageFiles.length) || pdfFiles.length + imageFiles.length !== selectedFiles.length) {
    heroError.textContent = "Choose PDF files or JPG/PNG images, one file type at a time.";
    heroError.hidden = false;
    return;
  }

  heroFiles = selectedFiles;
  const availableTools = imageFiles.length
    ? ["images-to-pdf"]
    : pdfFiles.length > 1
      ? ["merge"]
      : ["compress", "split", "rotate"];
  document.querySelector("#picker-title").textContent = "What would you like to do?";
  document.querySelector("#picker-description").textContent = `${selectedFiles.length} ${imageFiles.length ? "image" : "PDF"}${selectedFiles.length === 1 ? "" : "s"} selected.`;
  quickToolList.replaceChildren();

  const icons = { merge: "▢", compress: "⤢", split: "◫", rotate: "↻", "images-to-pdf": "▧" };
  for (const tool of availableTools) {
    const button = document.createElement("button");
    button.className = "quick-tool-button";
    button.type = "button";
    button.dataset.tool = tool;
    const icon = document.createElement("span");
    icon.className = `tool-icon quick-icon-${tool}`;
    icon.setAttribute("aria-hidden", "true");
    icon.textContent = icons[tool];
    const copy = document.createElement("span");
    copy.className = "tool-copy";
    const title = document.createElement("strong");
    title.textContent = toolDetails[tool].title;
    const description = document.createElement("small");
    description.textContent = toolDetails[tool].description;
    copy.append(title, description);
    const arrow = document.createElement("span");
    arrow.className = "tool-arrow";
    arrow.setAttribute("aria-hidden", "true");
    arrow.textContent = "→";
    button.append(icon, copy, arrow);
    button.addEventListener("click", () => {
      toolPicker.close();
      openTool(tool, heroFiles);
      heroFiles = [];
    });
    quickToolList.append(button);
  }
  toolPicker.showModal();
}

function addFiles(files) {
  const accepted = toolDetails[activeTool].multiple;
  const incoming = [...files];
  queuedFiles = accepted ? [...queuedFiles, ...incoming] : incoming.slice(0, 1);
  renderFileList();
  jobError.hidden = true;
  jobSuccess.hidden = true;
}

function renderFileList() {
  fileList.replaceChildren();
  queuedFiles.forEach((file, index) => {
    const row = document.createElement("div");
    row.className = "file-row";
    const badge = document.createElement("span");
    badge.className = "file-badge";
    badge.textContent = file.name.toLowerCase().endsWith(".pdf") ? "PDF" : "IMG";
    const details = document.createElement("span");
    details.className = "file-details";
    const filename = document.createElement("strong");
    filename.textContent = file.name;
    const size = document.createElement("small");
    size.textContent = formatBytes(file.size);
    details.append(filename, size);
    row.append(badge, details);
    if (activeTool === "merge") {
      const controls = document.createElement("span");
      controls.className = "file-controls";
      for (const [label, symbol, offset] of [["Move up", "↑", -1], ["Move down", "↓", 1]]) {
        const button = document.createElement("button");
        button.type = "button";
        button.setAttribute("aria-label", label);
        button.textContent = symbol;
        button.disabled = index + offset < 0 || index + offset >= queuedFiles.length;
        button.addEventListener("click", () => {
          [queuedFiles[index], queuedFiles[index + offset]] = [queuedFiles[index + offset], queuedFiles[index]];
          renderFileList();
        });
        controls.append(button);
      }
      row.append(controls);
    }
    const remove = document.createElement("button");
    remove.className = "history-action";
    remove.type = "button";
    remove.setAttribute("aria-label", `Remove ${file.name}`);
    remove.textContent = "×";
    remove.addEventListener("click", () => {
      queuedFiles.splice(index, 1);
      renderFileList();
    });
    row.append(remove);
    fileList.append(row);
  });
}

document.querySelectorAll(".tool-card").forEach((card) => {
  card.addEventListener("click", () => openTool(card.dataset.tool));
});
document.querySelector("#close-dialog").addEventListener("click", () => dialog.close());
document.querySelector("#cancel-dialog").addEventListener("click", () => dialog.close());
document.querySelector("#close-picker").addEventListener("click", () => toolPicker.close());
dialog.addEventListener("click", (event) => {
  if (event.target === dialog) dialog.close();
});
toolPicker.addEventListener("click", (event) => {
  if (event.target === toolPicker) toolPicker.close();
});
dropZone.addEventListener("click", () => fileInput.click());
dropZone.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    fileInput.click();
  }
});
fileInput.addEventListener("change", () => {
  addFiles(fileInput.files);
  fileInput.value = "";
});
for (const eventName of ["dragenter", "dragover"]) {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.add("is-dragging");
  });
}
for (const eventName of ["dragleave", "drop"]) {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.remove("is-dragging");
  });
}
dropZone.addEventListener("drop", (event) => addFiles(event.dataTransfer.files));

heroDropZone.addEventListener("click", (event) => {
  if (event.target !== heroBrowse) heroFileInput.click();
});
heroDropZone.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    heroFileInput.click();
  }
});
const heroBrowse = document.querySelector("#hero-browse");
heroBrowse.addEventListener("click", (event) => {
  event.stopPropagation();
  heroFileInput.click();
});
heroFileInput.addEventListener("change", () => {
  showToolPicker(heroFileInput.files);
  heroFileInput.value = "";
});
for (const eventName of ["dragenter", "dragover"]) {
  heroDropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    heroDropZone.classList.add("is-dragging");
  });
}
for (const eventName of ["dragleave", "drop"]) {
  heroDropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    heroDropZone.classList.remove("is-dragging");
  });
}
heroDropZone.addEventListener("drop", (event) => {
  event.preventDefault();
  showToolPicker(event.dataTransfer.files);
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  jobError.hidden = true;
  jobSuccess.hidden = true;
  if (!queuedFiles.length) {
    jobError.textContent = "Choose a file before continuing.";
    jobError.hidden = false;
    return;
  }
  const payload = new FormData();
  payload.append("tool", activeTool);
  queuedFiles.forEach((file) => payload.append("files", file));
  if (activeTool === "split") payload.append("ranges", document.querySelector("#page-ranges").value);
  if (activeTool === "rotate") payload.append("degrees", document.querySelector("#rotation").value);
  processButton.disabled = true;
  processLabel.textContent = "Working…";
  try {
    const response = await fetch("/api/jobs", { method: "POST", body: payload });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "The job could not be completed.");
    const message = document.createElement("span");
    message.textContent = `${result.outputName} is ready · ${formatBytes(result.outputBytes)}`;
    const download = document.createElement("a");
    download.href = result.downloadUrl;
    download.textContent = "Download";
    download.setAttribute("download", result.outputName);
    jobSuccess.replaceChildren(message, download);
    jobSuccess.hidden = false;
    await loadHistory();
  } catch (error) {
    jobError.textContent = error.message;
    jobError.hidden = false;
  } finally {
    processButton.disabled = false;
    processLabel.textContent = toolDetails[activeTool].label;
  }
});

function relativeDate(value) {
  const elapsed = Math.max(0, Date.now() - new Date(value).getTime());
  if (elapsed < 60_000) return "Just now";
  if (elapsed < 3_600_000) return `${Math.floor(elapsed / 60_000)} min ago`;
  if (elapsed < 86_400_000) return `${Math.floor(elapsed / 3_600_000)} hr ago`;
  return new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

async function loadHistory() {
  const response = await fetch("/api/history");
  if (!response.ok) return;
  const jobs = await response.json();
  historyBody.replaceChildren();
  if (!jobs.length) {
    const row = document.createElement("tr");
    row.innerHTML = '<td class="empty-history" colspan="5"><span class="empty-mark">◷</span><strong>Nothing here yet</strong><span>Your finished files will show up here.</span></td>';
    historyBody.append(row);
    return;
  }
  for (const job of jobs) {
    const row = document.createElement("tr");
    const fileCell = document.createElement("td");
    fileCell.className = "history-file";
    const mark = document.createElement("span");
    mark.className = "file-type-mark";
    mark.textContent = job.output_name.toLowerCase().endsWith(".zip") ? "ZIP" : "PDF";
    const link = document.createElement("a");
    link.className = "history-download";
    link.href = `/api/jobs/${encodeURIComponent(job.id)}/download`;
    link.textContent = job.output_name;
    link.setAttribute("download", job.output_name);
    fileCell.append(mark, link);
    const toolCell = document.createElement("td");
    toolCell.textContent = toolDetails[job.tool]?.title || job.tool;
    const sizeCell = document.createElement("td");
    sizeCell.textContent = formatBytes(job.output_bytes);
    const dateCell = document.createElement("td");
    dateCell.textContent = relativeDate(job.created_at);
    const actionCell = document.createElement("td");
    const removeButton = document.createElement("button");
    removeButton.className = "history-action";
    removeButton.type = "button";
    removeButton.textContent = "×";
    removeButton.setAttribute("aria-label", `Delete ${job.output_name} from history`);
    removeButton.addEventListener("click", async () => {
      const deleted = await fetch(`/api/history/${encodeURIComponent(job.id)}`, { method: "DELETE" });
      if (deleted.ok) loadHistory();
    });
    actionCell.append(removeButton);
    row.append(fileCell, toolCell, sizeCell, dateCell, actionCell);
    historyBody.append(row);
  }
}

function applyFilters(category = document.querySelector(".filter-chip.is-selected")?.dataset.filter || "all") {
  let visibleCount = 0;
  for (const card of document.querySelectorAll(".tool-card")) {
    const matchesCategory = category === "all" || card.dataset.category === category;
    card.hidden = !matchesCategory;
    if (!card.hidden) visibleCount += 1;
  }
  document.querySelector("#no-results").hidden = visibleCount > 0;
  document.querySelectorAll(".filter-chip").forEach((chip) => chip.classList.toggle("is-selected", chip.dataset.filter === category));
  document.querySelectorAll(".main-nav .nav-item[data-filter]").forEach((link) => link.classList.toggle("is-active", link.dataset.filter === category));
}

document.querySelectorAll(".filter-chip").forEach((chip) => chip.addEventListener("click", () => applyFilters(chip.dataset.filter)));
document.querySelectorAll(".main-nav .nav-item[data-filter]").forEach((link) => link.addEventListener("click", () => applyFilters(link.dataset.filter)));
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && dialog.open) dialog.close();
  if (event.key === "Escape" && toolPicker.open) toolPicker.close();
});

loadHistory();