const OUTPUTS = {
  video_embedded: ["Vidéo sous-titrée", "Sous-titres incrustés dans l'image"],
  video_subtitles: ["Vidéo + sous-titres", "Piste de sous-titres activable et fichier .srt séparé"],
  subtitles: ["Sous-titres seuls", "Fichier .srt horodaté"],
  text: ["Texte", "Transcription sans horodatage"],
};
const STAGES = {
  transcription: "Transcription",
  translation: "Traduction",
  video: "Incrustation des sous-titres",
};
const LANGUAGES = { fr: "Français", en: "Anglais", es: "Espagnol", de: "Allemand", it: "Italien" };
const POLL_MS = 700;

const $ = (id) => document.getElementById(id);
const show = (el, visible = true) => { el.hidden = !visible; };

let config = null;
let upload = null;
let currentJob = null;
let pollTimer = null;

function fail(message) {
  $("error").textContent = message;
  show($("error"));
}

function setProgress(id, percent, label) {
  const box = $(id);
  box.querySelector("progress").value = percent;
  box.querySelector("span").textContent = `${label} · ${Math.round(percent)} %`;
  show(box);
}

function toLogin() {
  location.replace("/login.html");
  return new Promise(() => {}); // the page is being replaced: stop the caller here
}

async function api(path, options) {
  const response = await fetch(`/api${path}`, options);
  if (response.status === 401) return toLogin();
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : `Erreur ${response.status}`);
  }
  return response.json();
}

function formatDuration(seconds) {
  if (seconds == null) return "";
  const s = Math.round(seconds);
  return `${Math.floor(s / 60)} min ${String(s % 60).padStart(2, "0")} s`;
}

function formatSize(megabytes) {
  return megabytes >= 1024 ? `${(megabytes / 1024).toFixed(megabytes % 1024 ? 1 : 0)} Go` : `${megabytes} Mo`;
}

// Duration read by the browser, or 0 when it cannot tell (the server decides then).
function readDuration(file) {
  return new Promise((resolve) => {
    const element = document.createElement(file.name.toLowerCase().endsWith(".wav") ? "audio" : "video");
    const url = URL.createObjectURL(file);
    const done = (value) => { URL.revokeObjectURL(url); resolve(Number.isFinite(value) ? value : 0); };
    element.preload = "metadata";
    element.onloadedmetadata = () => done(element.duration);
    element.onerror = () => done(0);
    setTimeout(() => done(0), 5000);
    element.src = url;
  });
}

const MAX_UPLOAD_RETRIES = 8;
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// Resumable uploads are remembered per file, so that picking the same file
// again after a reload or a crash continues instead of starting over.
const resumeKey = (file) => `upload:${file.name}:${file.size}:${file.lastModified}`;
function remember(key, value) {
  try {
    if (value) localStorage.setItem(key, value);
    else localStorage.removeItem(key);
  } catch { /* storage unavailable: resuming after a reload just will not work */ }
}
function recall(key) {
  try { return localStorage.getItem(key); } catch { return null; }
}

async function openUploadSession(file) {
  const known = recall(resumeKey(file));
  if (known) {
    const response = await fetch(`/api/uploads/sessions/${known}`);
    if (response.ok) return response.json();
  }
  const session = await api("/uploads/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename: file.name, size_bytes: file.size }),
  });
  remember(resumeKey(file), session.id);
  return session;
}

// One chunk, with progress inside the chunk. Rejects only on a network failure.
function putChunk(sessionId, blob, offset, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const body = new FormData();
    body.append("offset", offset);
    body.append("chunk", blob);
    xhr.open("PUT", `/api/uploads/sessions/${sessionId}`);
    xhr.upload.onprogress = (e) => { if (e.lengthComputable) onProgress(e.loaded / e.total); };
    xhr.onerror = () => reject(new Error("réseau"));
    xhr.onload = () => {
      let data = {};
      try { data = JSON.parse(xhr.responseText); } catch { /* non-JSON error page */ }
      resolve({ status: xhr.status, data });
    };
    xhr.send(body);
  });
}

async function sendFile(file) {
  const session = await openUploadSession(file);
  const showProgress = (bytes, label = "Envoi") =>
    setProgress("upload-progress", (bytes / file.size) * 100, label);
  let offset = session.received_bytes;
  let failures = 0;
  if (offset > 0) showProgress(offset, "Reprise de l'envoi");

  while (offset < file.size) {
    const blob = file.slice(offset, offset + session.chunk_bytes);
    let answer;
    try {
      answer = await putChunk(session.id, blob, offset, (part) => showProgress(offset + part * blob.size));
    } catch {
      // Connection lost: wait and carry on from where the server stands.
      failures += 1;
      if (failures > MAX_UPLOAD_RETRIES) {
        throw new Error("Envoi interrompu : la connexion ne revient pas. Choisissez à nouveau ce fichier pour reprendre là où l'envoi s'est arrêté.");
      }
      showProgress(offset, `Connexion perdue, nouvelle tentative (${failures}/${MAX_UPLOAD_RETRIES})`);
      await sleep(Math.min(1000 * 2 ** failures, 15000));
      continue;
    }
    if (answer.status === 401) return toLogin();
    if (answer.status === 200 || answer.status === 409) {
      // 409: the server already has other bytes than expected; it says where it stands.
      offset = answer.data.received_bytes;
      failures = 0;
      continue;
    }
    if (answer.status >= 500 && failures < MAX_UPLOAD_RETRIES) {
      failures += 1;
      await sleep(Math.min(1000 * 2 ** failures, 15000));
      continue;
    }
    remember(resumeKey(file), null);
    throw new Error(typeof answer.data.detail === "string" ? answer.data.detail : `Erreur ${answer.status}`);
  }

  showProgress(file.size, "Vérification du fichier");
  try {
    return await api(`/uploads/sessions/${session.id}/complete`, { method: "POST" });
  } finally {
    remember(resumeKey(file), null);
  }
}

async function handleFile(file) {
  if (!file) return;
  show($("error"), false);
  const extension = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  if (!(extension in config.extensions)) {
    return fail("Format non supporté : choisissez un fichier .mp4 ou .wav");
  }
  if (file.size > config.max_upload_mb * 1024 * 1024) {
    return fail(`Fichier trop volumineux (maximum ${formatSize(config.max_upload_mb)})`);
  }
  // Checked here to avoid a long upload for nothing; the server checks again.
  const localDuration = await readDuration(file);
  if (localDuration > config.max_duration_s) {
    return fail(`Fichier trop long : ${formatDuration(localDuration)} (maximum ${formatDuration(config.max_duration_s)})`);
  }
  // No point in sending a large file if its processing would be refused.
  const queue = await api("/queue").catch(() => null);
  if (queue && !queue.accepting) {
    return fail("Le service est saturé pour le moment : réessayez dans quelques minutes.");
  }
  show($("options"), false);
  show($("job"), false);
  $("file-info").textContent = file.name;
  show($("file-info"));
  setProgress("upload-progress", 0, "Envoi");
  try {
    upload = await sendFile(file);
  } catch (e) {
    show($("file-info"), false);
    return fail(e.message);
  } finally {
    show($("upload-progress"), false);
  }
  const duration = formatDuration(upload.duration_s);
  $("file-info").textContent = `${upload.filename}${duration ? ` · ${duration}` : ""}`;
  renderOutputs();
  show($("options"));
}

function selectedOutput() {
  return document.querySelector("input[name=output]:checked")?.value;
}

function renderOutputs() {
  const container = $("outputs");
  container.replaceChildren();
  for (const [value, [title, hint]] of Object.entries(OUTPUTS)) {
    const allowed = upload.allowed_outputs.includes(value);
    const label = document.createElement("label");
    label.className = "choice" + (allowed ? "" : " disabled");
    const input = document.createElement("input");
    input.type = "radio";
    input.name = "output";
    input.value = value;
    input.disabled = !allowed;
    input.onchange = () => {
      $("start").disabled = false;
      show($("burn-style"), value === "video_embedded");
    };
    const strong = document.createElement("strong");
    strong.textContent = title;
    const small = document.createElement("small");
    small.textContent = allowed ? hint : "Disponible uniquement pour une vidéo";
    label.append(input, strong, small);
    container.append(label);
  }
  $("start").disabled = true;
  show($("burn-style"), false);
}

async function startJob() {
  const output = selectedOutput();
  if (!output) return;
  show($("error"), false);
  $("start").disabled = true;
  const body = {
    upload_id: upload.id,
    output_type: output,
    model: $("model").value,
    translate_to: $("language").value || null,
  };
  if (output === "video_embedded") {
    body.subtitle_style = { size: $("burn-size").value, color: $("burn-color").value };
  }
  try {
    const job = await api("/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    show($("options"), false);
    show($("result"), false);
    show($("job"));
    renderJob(job);
    poll(job.id);
  } catch (e) {
    $("start").disabled = false;
    fail(e.message);
  }
}

function poll(jobId) {
  clearTimeout(pollTimer);
  pollTimer = setTimeout(async () => {
    try {
      const job = await api(`/jobs/${jobId}`);
      renderJob(job);
      if (job.status === "queued" || job.status === "processing") poll(jobId);
    } catch {
      poll(jobId); // transient network error or server restart: keep trying
    }
  }, POLL_MS);
}

function renderJob(job) {
  currentJob = job;
  const status = $("job-status");
  status.className = `status ${job.status}`;
  const active = job.status === "queued" || job.status === "processing";
  const available = job.status === "done" && job.artifacts.length > 0;
  show($("job-progress"), false);
  show($("cancel"), active);
  show($("editor"), false);
  show($("result"), !active);
  show($("download"), available);
  show($("edit"), available);
  if (!available) {
    show($("player-style"), false);
    $("preview").replaceChildren();
  }

  if (job.status === "queued") {
    status.textContent = `En file d'attente (position ${job.queue_position ?? "?"})…`;
  } else if (job.status === "processing") {
    status.textContent = "Traitement en cours…";
    setProgress("job-progress", job.progress, STAGES[job.stage] ?? "Préparation");
  } else if (job.status === "failed") {
    status.textContent = `Le traitement a échoué : ${job.error}`;
  } else if (job.status === "cancelled") {
    status.textContent = "Traitement annulé.";
  } else if (!available) {
    status.textContent = "Ce résultat a été supprimé du serveur (un fichier plus récent l'a remplacé ou il a expiré).";
  } else {
    status.textContent = `Terminé en ${job.compute_s.toFixed(1)} s`;
    $("download").href = `/api/jobs/${job.id}/download`;
    renderPreview(job);
  }
}

async function cancelJob() {
  if (!currentJob) return;
  clearTimeout(pollTimer);
  try {
    renderJob(await api(`/jobs/${currentJob.id}/cancel`, { method: "POST" }));
  } catch {
    poll(currentJob.id); // it finished in the meantime: show where it stands
  }
}

async function deleteUpload() {
  if (!upload || !confirm("Supprimer définitivement ce fichier et ses résultats du serveur ?")) return;
  clearTimeout(pollTimer);
  try {
    const response = await fetch(`/api/uploads/${upload.id}`, { method: "DELETE" });
    if (!response.ok) throw new Error(`Erreur ${response.status}`);
    reset();
  } catch (e) {
    fail(`Suppression impossible : ${e.message}`);
  }
}

function clock(seconds) {
  const s = Math.floor(seconds);
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

async function openEditor() {
  show($("error"), false);
  let transcript;
  try {
    transcript = await api(`/jobs/${currentJob.id}/transcript`);
  } catch (e) {
    return fail(e.message);
  }
  $("editor-rows").replaceChildren(...transcript.segments.map((segment) => {
    const label = document.createElement("label");
    const time = document.createElement("span");
    time.textContent = `${clock(segment.start)} → ${clock(segment.end)}`;
    const input = document.createElement("input");
    input.value = segment.text;
    input.maxLength = 500;
    label.append(time, input);
    return label;
  }));
  show($("result"), false);
  show($("editor"));
}

async function saveEditor(event) {
  event.preventDefault();
  const texts = [...$("editor-rows").querySelectorAll("input")].map((input) => input.value);
  try {
    const job = await api(`/jobs/${currentJob.id}/segments`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ texts }),
    });
    renderJob(job);
    poll(job.id);
  } catch (e) {
    fail(e.message);
  }
}

async function renderPreview(job) {
  const preview = $("preview");
  preview.replaceChildren();
  show($("player-style"), false);
  const fileUrl = (name) => `/api/jobs/${job.id}/files/${name}?v=${encodeURIComponent(job.finished_at)}`;
  const has = (name) => job.artifacts.some((a) => a.name === name);

  if (has("video.mp4")) {
    const video = document.createElement("video");
    video.controls = true;
    video.src = fileUrl("video.mp4");
    if (has("subtitles.vtt")) {
      const track = document.createElement("track");
      track.kind = "subtitles";
      track.src = fileUrl("subtitles.vtt");
      track.srclang = job.target_language ?? "en";
      track.default = true;
      video.append(track);
      show($("player-style"));
    }
    preview.append(video);
    return;
  }
  const name = has("subtitles.srt") ? "subtitles.srt" : "transcript.txt";
  const pre = document.createElement("pre");
  pre.textContent = await (await fetch(fileUrl(name))).text();
  preview.append(pre);
}

// Subtitle track appearance in the player; remembered on this browser.
function applyCueStyle() {
  const size = $("cue-size").value;
  const color = $("cue-color").value;
  $("cue-style").textContent = `video::cue { font-size: ${size}%; color: ${color}; }`;
  try {
    localStorage.setItem("cueStyle", JSON.stringify({ size, color }));
  } catch { /* storage unavailable: the choice just is not remembered */ }
}

function restoreCueStyle() {
  try {
    const saved = JSON.parse(localStorage.getItem("cueStyle"));
    if (saved) {
      $("cue-size").value = saved.size;
      $("cue-color").value = saved.color;
    }
  } catch { /* nothing saved */ }
  applyCueStyle();
}

function reset() {
  clearTimeout(pollTimer);
  upload = null;
  currentJob = null;
  $("file").value = "";
  for (const id of ["file-info", "options", "job", "error"]) show($(id), false);
}

async function init() {
  try {
    const me = await api("/auth/me");
    $("username").textContent = me.username;
    show($("account"));
    config = await api("/config");
  } catch (e) {
    return fail(`Service indisponible : ${e.message}`);
  }
  for (const name of config.models) {
    const scope = name.endsWith(".en") ? "anglais uniquement" : "multilingue, langue détectée";
    $("model").add(new Option(`${name} (${scope})`, name, false, name === config.default_model));
  }
  $("language").add(new Option("Langue d'origine", ""));
  for (const code of config.translation_targets) {
    $("language").add(new Option(`${LANGUAGES[code] ?? code} (traduction)`, code));
  }
  const zone = $("dropzone");
  $("file").onchange = (e) => handleFile(e.target.files[0]);
  zone.ondragover = (e) => { e.preventDefault(); zone.classList.add("over"); };
  zone.ondragleave = () => zone.classList.remove("over");
  zone.ondrop = (e) => {
    e.preventDefault();
    zone.classList.remove("over");
    handleFile(e.dataTransfer.files[0]);
  };
  $("start").onclick = startJob;
  $("logout").onclick = async () => {
    await fetch("/api/auth/logout", { method: "POST" }).catch(() => {});
    location.replace("/login.html");
  };
  $("reset").onclick = reset;
  $("cancel").onclick = cancelJob;
  $("delete").onclick = deleteUpload;
  $("edit").onclick = openEditor;
  $("editor").onsubmit = saveEditor;
  $("editor-close").onclick = () => renderJob(currentJob);
  $("another").onclick = () => {
    clearTimeout(pollTimer);
    show($("job"), false);
    renderOutputs();
    show($("options"));
  };
  $("cue-size").oninput = applyCueStyle;
  $("cue-color").oninput = applyCueStyle;
  restoreCueStyle();
  $("limits").textContent =
    `Vidéo .mp4 ou audio .wav · ${Math.round(config.max_duration_s / 60)} min et ${formatSize(config.max_upload_mb)} maximum`;
  restoreLastUpload();
}

// Coming back to the page: pick up the latest file and its most recent job.
async function restoreLastUpload() {
  const last = await api("/uploads/last").catch(() => null);
  if (!last?.upload) return;
  upload = last.upload;
  const duration = formatDuration(upload.duration_s);
  $("file-info").textContent = `Dernier fichier : ${upload.filename}${duration ? ` · ${duration}` : ""}`;
  show($("file-info"));
  const job = last.jobs[0];
  if (!job) {
    renderOutputs();
    return show($("options"));
  }
  show($("job"));
  renderJob(job);
  if (job.status === "queued" || job.status === "processing") poll(job.id);
}

init();
