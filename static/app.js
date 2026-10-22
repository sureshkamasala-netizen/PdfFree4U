const toolDetails = {
  merge: { title: "Merge PDF", description: "Put your PDFs in the order you want them combined.", accept: ".pdf,application/pdf", multiple: true, label: "Merge PDF", hint: "PDF files · up to 100 MB", category: "organize" },
  split: { title: "Split PDF", description: "Save individual pages or choose page ranges to split out.", accept: ".pdf,application/pdf", multiple: false, label: "Split PDF", hint: "PDF files · up to 100 MB", category: "organize" },
  compress: { title: "Compress PDF", description: "Reduce file size while preserving readable pages.", accept: ".pdf,application/pdf", multiple: false, label: "Compress PDF", hint: "PDF files · up to 100 MB", category: "optimize" },
  rotate: { title: "Rotate PDF", description: "Turn every page in your document in one go.", accept: ".pdf,application/pdf", multiple: false, label: "Rotate PDF", hint: "PDF files · up to 100 MB", category: "organize" },
  "images-to-pdf": { title: "Images to PDF", description: "Combine JPG and PNG images into a single PDF.", accept: ".jpg,.jpeg,.png,image/jpeg,image/png", multiple: true, label: "Create PDF", hint: "JPG or PNG images · up to 100 MB", category: "convert" },
  protect: { title: "Protect PDF", description: "Lock your PDF with a password so it stays private.", accept: ".pdf,application/pdf", multiple: false, label: "Protect PDF", hint: "PDF files · up to 100 MB", category: "organize" },
  unlock: { title: "Unlock PDF", description: "Remove a PDF password and make it editable again.", accept: ".pdf,application/pdf", multiple: false, label: "Unlock PDF", hint: "PDF files · up to 100 MB", category: "organize" },
  "remove-pages": { title: "Remove PDF pages", description: "Delete specific pages without breaking the rest of the document.", accept: ".pdf,application/pdf", multiple: false, label: "Remove pages", hint: "PDF files · up to 100 MB", category: "organize" },
  "extract-pages": { title: "Extract PDF pages", description: "Save just the pages you need as a new PDF.", accept: ".pdf,application/pdf", multiple: false, label: "Extract pages", hint: "PDF files · up to 100 MB", category: "organize" },
  "rearrange-pages": { title: "Rearrange PDF pages", description: "Put pages in a new order before you save the PDF.", accept: ".pdf,application/pdf", multiple: false, label: "Rearrange pages", hint: "PDF files · up to 100 MB", category: "organize" },
  "pdf-to-images": { title: "PDF to Images", description: "Turn each PDF page into an image for easy sharing.", accept: ".pdf,application/pdf", multiple: false, label: "Export images", hint: "PDF files · up to 100 MB", category: "convert" },
  "extract-pdf-images": { title: "Extract PDF images", description: "Pull embedded images out of a PDF as separate files.", accept: ".pdf,application/pdf", multiple: false, label: "Extract images", hint: "PDF files · up to 100 MB", category: "convert" },
  "pdf-ocr": { title: "PDF OCR", description: "Recognize text from scanned or image-heavy PDFs.", accept: ".pdf,application/pdf", multiple: false, label: "OCR PDF", hint: "PDF files · up to 100 MB", category: "convert" },
  "add-watermark": { title: "Add watermark", description: "Stamp a transparent watermark across your page layout.", accept: ".pdf,application/pdf", multiple: false, label: "Add watermark", hint: "PDF files · up to 100 MB", category: "organize" },
  "add-page-numbers": { title: "Add page numbers", description: "Add page numbers to the bottom or corner of each sheet.", accept: ".pdf,application/pdf", multiple: false, label: "Number pages", hint: "PDF files · up to 100 MB", category: "organize" },
  "pdf-overlay": { title: "PDF Overlay", description: "Overlay one PDF onto another for quick composite layouts.", accept: ".pdf,application/pdf", multiple: true, label: "Overlay PDF", hint: "2 PDF files · up to 100 MB", category: "organize" },
  "compare-pdfs": { title: "Compare PDFs", description: "Compare two PDF files and generate a short summary.", accept: ".pdf,application/pdf", multiple: true, label: "Compare PDFs", hint: "2 PDF files · up to 100 MB", category: "convert" },
  "web-optimizer": { title: "Web optimize PDF", description: "Reduce file size for sharing over the web.", accept: ".pdf,application/pdf", multiple: false, label: "Optimize PDF", hint: "PDF files · up to 100 MB", category: "optimize" },
  "redact-pdf": { title: "Redact PDF", description: "Black out sections to hide content before publishing.", accept: ".pdf,application/pdf", multiple: false, label: "Redact PDF", hint: "PDF files · up to 100 MB", category: "organize" },
  "create-pdf": { title: "Create PDF", description: "Build a PDF from images or existing PDFs.", accept: ".jpg,.jpeg,.png,.pdf,image/jpeg,image/png,application/pdf", multiple: true, label: "Create PDF", hint: "Images or PDF files · up to 100 MB", category: "convert" },
  "edit-pdf": { title: "Edit PDF", description: "Add text to selected pages or replace text already in the PDF.", accept: ".pdf,application/pdf", multiple: false, label: "Save PDF", hint: "PDF files · up to 100 MB", category: "organize" },
  "sign-pdf": { title: "Sign PDF", description: "Draw your signature directly on a page of the PDF.", accept: ".pdf,application/pdf", multiple: false, label: "Save signed PDF", hint: "PDF files · up to 100 MB", category: "organize" },
  "pdf-converter": { title: "PDF Converter", description: "Apply a conversion style pass to a PDF document.", accept: ".pdf,application/pdf", multiple: false, label: "Convert PDF", hint: "PDF files · up to 100 MB", category: "convert" },
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
const editorPanel = document.querySelector("#pdf-editor");
const editorPreview = document.querySelector("#editor-preview");
const editorCanvas = document.querySelector("#editor-canvas");
const editorStage = document.querySelector("#editor-stage");
const editorPageArea = document.querySelector(".editor-page-area");
const editorLoading = document.querySelector("#editor-loading");
const editorOperations = [];
const removedPages = new Set();
const editorImageCache = new Map();
let editorFile = null;
let editorPage = 1;
let editorPageCount = 1;
let editorTool = "text";
let editorDraft = null;
let editorImageData = "";
let editorPreviewUrl = "";
let editorZoom = 1;

function setEditorTool(tool) {
  editorTool = tool;
  document.querySelectorAll("[data-editor-tool]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.editorTool === tool);
  });
  const hints = {
    text: "Type text above, then click where it should appear.",
    freehand: "Drag on the page to sketch freehand.",
    signature: "Draw your signature on the page. Use Undo to remove the last stroke.",
    rectangle: "Drag on the page to draw a rectangle.",
    circle: "Drag on the page to draw an ellipse.",
    arrow: "Drag on the page to draw an arrow.",
    image: "Drag on the page to place the selected image.",
  };
  document.querySelector("#editor-hint").textContent = hints[tool];
  editorCanvas.style.cursor = tool === "text" ? "text" : "crosshair";
}

function editorPoint(event) {
  const rect = editorCanvas.getBoundingClientRect();
  return {
    x: Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width)),
    y: Math.min(1, Math.max(0, (event.clientY - rect.top) / rect.height)),
  };
}

function drawEditorCanvas() {
  const bounds = editorCanvas.getBoundingClientRect();
  if (!bounds.width || !bounds.height) return;
  const ratio = window.devicePixelRatio || 1;
  const backingWidth = Math.round(bounds.width * ratio);
  const backingHeight = Math.round(bounds.height * ratio);
  if (editorCanvas.width !== backingWidth || editorCanvas.height !== backingHeight) {
    editorCanvas.width = backingWidth;
    editorCanvas.height = backingHeight;
  }
  const context = editorCanvas.getContext("2d");
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  context.clearRect(0, 0, bounds.width, bounds.height);
  const visibleOperations = editorOperations.filter((operation) => operation.page === editorPage - 1);
  if (editorDraft) visibleOperations.push(editorDraft);

  for (const operation of visibleOperations) {
    const x = operation.x * bounds.width;
    const y = operation.y * bounds.height;
    const x2 = (operation.x2 ?? operation.x) * bounds.width;
    const y2 = (operation.y2 ?? operation.y) * bounds.height;
    context.strokeStyle = operation.color;
    context.fillStyle = operation.color;
    context.lineWidth = (operation.width || 2) * bounds.width / Math.max(1, editorPreview.naturalWidth);
    context.lineCap = "round";
    context.lineJoin = "round";

    if (operation.type === "text") {
      const fontSize = operation.font_size * bounds.width / Math.max(1, editorPreview.naturalWidth);
      context.font = `${fontSize}px sans-serif`;
      operation.text.split("\n").forEach((line, index) => context.fillText(line, x, y + fontSize * (index + 1)));
    } else if (operation.type === "rectangle") {
      context.strokeRect(x, y, x2 - x, y2 - y);
    } else if (operation.type === "circle") {
      context.beginPath();
      context.ellipse((x + x2) / 2, (y + y2) / 2, Math.abs(x2 - x) / 2, Math.abs(y2 - y) / 2, 0, 0, Math.PI * 2);
      context.stroke();
    } else if (operation.type === "arrow") {
      const angle = Math.atan2(y2 - y, x2 - x);
      const head = 12;
      context.beginPath();
      context.moveTo(x, y);
      context.lineTo(x2, y2);
      context.lineTo(x2 - head * Math.cos(angle - Math.PI / 7), y2 - head * Math.sin(angle - Math.PI / 7));
      context.moveTo(x2, y2);
      context.lineTo(x2 - head * Math.cos(angle + Math.PI / 7), y2 - head * Math.sin(angle + Math.PI / 7));
      context.stroke();
    } else if (["freehand", "signature"].includes(operation.type)) {
      context.beginPath();
      operation.points.forEach((point, index) => {
        const pointX = point[0] * bounds.width;
        const pointY = point[1] * bounds.height;
        if (index === 0) context.moveTo(pointX, pointY);
        else context.lineTo(pointX, pointY);
      });
      context.stroke();
    } else if (operation.type === "image" && operation.data) {
      let image = editorImageCache.get(operation.data);
      if (!image) {
        image = new Image();
        image.onload = drawEditorCanvas;
        image.src = operation.data;
        editorImageCache.set(operation.data, image);
      }
      if (image.complete && image.naturalWidth) context.drawImage(image, x, y, x2 - x, y2 - y);
    }
  }
}

function resizeEditorPage() {
  if (!editorPreview.naturalWidth) return;
  const maxWidth = Math.max(220, editorPageArea.clientWidth - 32);
  const maxHeight = Math.max(220, window.innerHeight * 0.58);
  const fit = Math.min(maxWidth / editorPreview.naturalWidth, maxHeight / editorPreview.naturalHeight, 1);
  const width = Math.round(editorPreview.naturalWidth * fit * editorZoom);
  const height = Math.round(editorPreview.naturalHeight * fit * editorZoom);
  editorStage.style.width = `${width}px`;
  editorStage.style.height = `${height}px`;
  editorPreview.style.width = `${width}px`;
  editorPreview.style.height = `${height}px`;
  editorCanvas.style.width = `${width}px`;
  editorCanvas.style.height = `${height}px`;
  document.querySelector("#editor-zoom-label").textContent = `${Math.round(editorZoom * 100)}%`;
  drawEditorCanvas();
}

async function loadEditorPage() {
  editorLoading.hidden = false;
  editorLoading.textContent = "Preparing page preview…";
  editorPreview.hidden = true;
  editorCanvas.hidden = true;
  const payload = new FormData();
  payload.append("file", editorFile);
  payload.append("page", String(editorPage));
  try {
    const response = await fetch("/api/pdf-preview", { method: "POST", body: payload });
    if (!response.ok) {
      const result = await response.json();
      throw new Error(result.error || "This PDF page could not be previewed.");
    }
    editorPageCount = Number(response.headers.get("X-PDF-Page-Count")) || 1;
    if (editorPreviewUrl) URL.revokeObjectURL(editorPreviewUrl);
    editorPreviewUrl = URL.createObjectURL(await response.blob());
    await new Promise((resolve, reject) => {
      editorPreview.onload = resolve;
      editorPreview.onerror = reject;
      editorPreview.src = editorPreviewUrl;
    });
    editorPreview.hidden = false;
    editorCanvas.hidden = false;
    editorLoading.hidden = true;
    document.querySelector("#editor-page-label").textContent = `Page ${editorPage} of ${editorPageCount}`;
    document.querySelector("#editor-prev").disabled = editorPage <= 1;
    document.querySelector("#editor-next").disabled = editorPage >= editorPageCount;
    if (activeTool === "remove-pages") updatePageRemovalControls();
    resizeEditorPage();
  } catch (error) {
    editorLoading.textContent = error.message;
    jobError.textContent = error.message;
    jobError.hidden = false;
  }
}

function updatePageRemovalControls() {
  const marked = removedPages.has(editorPage - 1);
  document.querySelector("#toggle-page-removal").textContent = marked ? "Keep this page" : "Remove this page";
  document.querySelector("#removed-page-count").textContent = removedPages.size
    ? `${removedPages.size} page${removedPages.size === 1 ? "" : "s"} marked for removal`
    : "No pages marked for removal";
  document.querySelector("#editor-page-label").textContent = `Page ${editorPage} of ${editorPageCount}${marked ? " · marked for removal" : ""}`;
  editorStage.classList.toggle("is-marked-for-removal", marked);
}

async function openPdfEditor(file) {
  const signing = activeTool === "sign-pdf";
  const removing = activeTool === "remove-pages";
  editorFile = file;
  queuedFiles = [file];
  editorOperations.length = 0;
  removedPages.clear();
  editorImageCache.clear();
  editorPage = 1;
  editorPageCount = 1;
  editorZoom = 1;
  document.querySelector("#tool-intro").hidden = true;
  document.querySelector("#upload-panel").hidden = true;
  editorPanel.hidden = false;
  editorPanel.classList.toggle("is-removing-pages", removing);
  form.classList.add("is-editor");
  dialog.classList.add("is-editor");
  processLabel.textContent = signing ? "Save signed PDF" : removing ? "Save without selected pages" : "Save edited PDF";
  document.querySelector(".editor-toolbar").hidden = removing;
  document.querySelector("#page-removal-controls").hidden = !removing;
  document.querySelectorAll(".editor-tool[data-editor-tool]").forEach((button) => {
    button.hidden = signing ? button.dataset.editorTool !== "signature" : button.dataset.editorTool === "signature";
  });
  document.querySelector("#editor-text").hidden = signing || removing;
  editorCanvas.style.pointerEvents = removing ? "none" : "";
  document.querySelector("#editor-size-control").firstChild.textContent = signing ? "Stroke" : "Size";
  document.querySelector("#editor-hint").textContent = removing
    ? "Use Remove this page to mark pages. Navigate through the PDF, then save the remaining pages."
    : document.querySelector("#editor-hint").textContent;
  jobError.hidden = true;
  jobSuccess.hidden = true;
  if (!removing) setEditorTool(signing ? "signature" : "text");
  if (!dialog.open) dialog.showModal();
  await loadEditorPage();
}

function commitEditorDraft() {
  if (!editorDraft) return;
  if (["freehand", "signature"].includes(editorDraft.type) && editorDraft.points.length < 2) {
    editorDraft = null;
    drawEditorCanvas();
    return;
  }
  if (["rectangle", "circle", "arrow", "image"].includes(editorDraft.type)) {
    const width = Math.abs(editorDraft.x2 - editorDraft.x);
    const height = Math.abs(editorDraft.y2 - editorDraft.y);
    const tooSmall = editorDraft.type === "arrow"
      ? Math.hypot(width, height) < 0.012
      : width < 0.006 || height < 0.006;
    if (tooSmall) {
      editorDraft = null;
      drawEditorCanvas();
      return;
    }
  }
  editorOperations.push(editorDraft);
  editorDraft = null;
  document.querySelector("#editor-undo").disabled = false;
  drawEditorCanvas();
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function openTool(tool, initialFiles = []) {
  activeTool = tool;
  queuedFiles = [...initialFiles];
  form.classList.remove("is-editor");
  dialog.classList.remove("is-editor");
  document.querySelector("#tool-intro").hidden = false;
  document.querySelector("#upload-panel").hidden = false;
  editorPanel.hidden = true;
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
  document.querySelector("#compress-options").hidden = tool !== "compress";
  document.querySelector("#protect-options").hidden = tool !== "protect";
  document.querySelector("#unlock-options").hidden = tool !== "unlock";
  document.querySelector("#protect-password").value = "";
  document.querySelector("#unlock-password").value = "";
  document.querySelector("#compression-strength").value = "85";
  document.querySelector("#compression-strength-value").value = "85%";
  document.querySelector("#page-ranges").value = "";
  document.querySelector("#rotation").value = "90";
  document.querySelector("#editor-text").value = "";
  document.querySelector("#editor-image-input").value = "";
  editorImageData = "";
  editorOperations.length = 0;
  document.querySelector("#editor-undo").disabled = true;
  jobError.hidden = true;
  jobSuccess.hidden = true;
  renderFileList();
  dialog.showModal();
  if (["edit-pdf", "sign-pdf", "remove-pages"].includes(tool) && initialFiles.length) void openPdfEditor(initialFiles[0]);
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
      : ["edit-pdf", "sign-pdf", "remove-pages", "compress", "split", "rotate"];
  document.querySelector("#picker-title").textContent = "What would you like to do?";
  document.querySelector("#picker-description").textContent = `${selectedFiles.length} ${imageFiles.length ? "image" : "PDF"}${selectedFiles.length === 1 ? "" : "s"} selected.`;
  quickToolList.replaceChildren();

  const icons = { merge: "▢", compress: "⤢", split: "◫", rotate: "↻", "images-to-pdf": "▧", "edit-pdf": "✎", "sign-pdf": "✒", "remove-pages": "⊖" };
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
document.querySelector("#compression-strength").addEventListener("input", (event) => {
  document.querySelector("#compression-strength-value").value = `${event.target.value}%`;
});
document.querySelectorAll("[data-editor-tool]").forEach((button) => {
  button.addEventListener("click", () => setEditorTool(button.dataset.editorTool));
});
document.querySelector("#editor-image-button").addEventListener("click", () => {
  document.querySelector("#editor-image-input").click();
});
document.querySelector("#editor-image-input").addEventListener("change", (event) => {
  const image = event.target.files[0];
  event.target.value = "";
  if (!image) return;
  if (!/^image\/(png|jpeg)$/.test(image.type) || image.size > 8 * 1024 * 1024) {
    jobError.textContent = "Choose a PNG or JPEG image smaller than 8 MB.";
    jobError.hidden = false;
    return;
  }
  const reader = new FileReader();
  reader.addEventListener("load", () => {
    editorImageData = String(reader.result);
    setEditorTool("image");
  });
  reader.readAsDataURL(image);
});
document.querySelector("#editor-undo").addEventListener("click", () => {
  editorOperations.pop();
  document.querySelector("#editor-undo").disabled = editorOperations.length === 0;
  drawEditorCanvas();
});
document.querySelector("#toggle-page-removal").addEventListener("click", () => {
  const pageIndex = editorPage - 1;
  if (removedPages.has(pageIndex)) {
    removedPages.delete(pageIndex);
    jobError.hidden = true;
  } else if (removedPages.size >= editorPageCount - 1) {
    jobError.textContent = "Keep at least one page in the PDF.";
    jobError.hidden = false;
    return;
  } else {
    removedPages.add(pageIndex);
    jobError.hidden = true;
  }
  updatePageRemovalControls();
});
document.querySelector("#editor-prev").addEventListener("click", async () => {
  if (editorPage > 1) {
    editorPage -= 1;
    await loadEditorPage();
  }
});
document.querySelector("#editor-next").addEventListener("click", async () => {
  if (editorPage < editorPageCount) {
    editorPage += 1;
    await loadEditorPage();
  }
});
document.querySelector("#editor-zoom-out").addEventListener("click", () => {
  editorZoom = Math.max(0.6, editorZoom - 0.15);
  resizeEditorPage();
});
document.querySelector("#editor-zoom-in").addEventListener("click", () => {
  editorZoom = Math.min(1.6, editorZoom + 0.15);
  resizeEditorPage();
});
editorCanvas.addEventListener("pointerdown", (event) => {
  if (editorCanvas.hidden || editorLoading.hidden === false) return;
  const point = editorPoint(event);
  if (editorTool === "text") {
    const text = document.querySelector("#editor-text").value.trim();
    if (!text) {
      document.querySelector("#editor-hint").textContent = "Type the text you want to add, then click the page.";
      document.querySelector("#editor-text").focus();
      return;
    }
    editorOperations.push({
      type: "text",
      page: editorPage - 1,
      ...point,
      text,
      font_size: Math.max(8, Math.min(72, Number(document.querySelector("#editor-font-size").value) || 18)),
      color: document.querySelector("#editor-color").value,
    });
    document.querySelector("#editor-undo").disabled = false;
    drawEditorCanvas();
    return;
  }
  if (editorTool === "image" && !editorImageData) {
    document.querySelector("#editor-image-input").click();
    return;
  }
  editorCanvas.setPointerCapture(event.pointerId);
  const operation = {
    type: editorTool,
    page: editorPage - 1,
    ...point,
    x2: point.x,
    y2: point.y,
    color: document.querySelector("#editor-color").value,
    width: 2.5,
  };
  if (["freehand", "signature"].includes(editorTool)) {
    operation.points = [[point.x, point.y]];
    if (editorTool === "signature") operation.width = Math.max(1.5, Math.min(8, (Number(document.querySelector("#editor-font-size").value) || 18) / 6));
  }
  if (editorTool === "image") operation.data = editorImageData;
  editorDraft = operation;
});
editorCanvas.addEventListener("pointermove", (event) => {
  if (!editorDraft) return;
  const point = editorPoint(event);
  editorDraft.x2 = point.x;
  editorDraft.y2 = point.y;
  if (["freehand", "signature"].includes(editorDraft.type) && editorDraft.points.length < 3000) editorDraft.points.push([point.x, point.y]);
  drawEditorCanvas();
});
editorCanvas.addEventListener("pointerup", commitEditorDraft);
editorCanvas.addEventListener("pointercancel", commitEditorDraft);
window.addEventListener("resize", resizeEditorPage);
dialog.addEventListener("close", () => {
  if (editorPreviewUrl) URL.revokeObjectURL(editorPreviewUrl);
  editorPreviewUrl = "";
});
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
  if (["edit-pdf", "sign-pdf", "remove-pages"].includes(activeTool) && queuedFiles.length) void openPdfEditor(queuedFiles[0]);
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
dropZone.addEventListener("drop", (event) => {
  addFiles(event.dataTransfer.files);
  if (["edit-pdf", "sign-pdf", "remove-pages"].includes(activeTool) && queuedFiles.length) void openPdfEditor(queuedFiles[0]);
});

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
  if (activeTool === "compress") payload.append("target_reduction_percent", document.querySelector("#compression-strength").value);
  if (activeTool === "protect") {
    const password = document.querySelector("#protect-password").value.trim();
    if (!password) {
      jobError.textContent = "Enter a password to protect this PDF.";
      jobError.hidden = false;
      document.querySelector("#protect-password").focus();
      return;
    }
    payload.append("password", password);
  }
  if (activeTool === "unlock") {
    const password = document.querySelector("#unlock-password").value.trim();
    if (!password) {
      jobError.textContent = "Enter the PDF password to unlock this file.";
      jobError.hidden = false;
      document.querySelector("#unlock-password").focus();
      return;
    }
    payload.append("password", password);
  }
  if (activeTool === "remove-pages") {
    if (!removedPages.size) {
      jobError.textContent = "Mark at least one page to remove.";
      jobError.hidden = false;
      return;
    }
    if (removedPages.size >= editorPageCount) {
      jobError.textContent = "Keep at least one page in the PDF.";
      jobError.hidden = false;
      return;
    }
    payload.append("ranges", [...removedPages].sort((left, right) => left - right).map((page) => page + 1).join(","));
  }
  if (["edit-pdf", "sign-pdf"].includes(activeTool)) {
    const hasSignature = editorOperations.some((operation) => operation.type === "signature");
    if (activeTool === "sign-pdf" && !hasSignature) {
      jobError.textContent = "Draw your signature on the PDF before saving.";
      jobError.hidden = false;
      return;
    }
    if (!editorOperations.length) {
      jobError.textContent = "Add text, a shape, a drawing, or an image before saving.";
      jobError.hidden = false;
      return;
    }
    payload.append("edit_operations", JSON.stringify(editorOperations));
  }
  processButton.disabled = true;
  processLabel.textContent = "Working…";
  try {
    const response = await fetch("/api/jobs", { method: "POST", body: payload });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "The job could not be completed.");
    const message = document.createElement("span");
    if (activeTool === "compress") {
      message.className = "compression-summary";
      const title = document.createElement("strong");
      title.textContent = `${formatBytes(result.inputBytes)} → ${formatBytes(result.outputBytes)}`;
      const byteDifference = result.inputBytes - result.outputBytes;
      const target = document.createElement("small");
      target.textContent = `Requested: ${result.targetReductionPercent}% reduction`;
      const detail = document.createElement("small");
      if (byteDifference > 0) {
        detail.textContent = `Actual: ${result.reductionPercent}% smaller · ${formatBytes(byteDifference)} saved`;
      } else if (byteDifference < 0) {
        detail.textContent = `Actual: ${Math.abs(result.reductionPercent)}% larger · ${formatBytes(-byteDifference)} added`;
      } else {
        detail.textContent = "Actual: no size change";
      }
      const note = document.createElement("small");
      note.textContent = result.targetMet ? "Target reached" : "Closest achievable result for this PDF";
      message.append(title, target, detail, note);
    } else {
      message.textContent = `${result.outputName} is ready · ${formatBytes(result.outputBytes)}`;
    }
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