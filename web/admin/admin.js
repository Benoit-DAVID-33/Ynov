const LABELS = {
  video_embedded: "Vidéo sous-titrée",
  video_subtitles: "Vidéo + sous-titres",
  subtitles: "Sous-titres seuls",
  text: "Texte",
  video: "Entrée vidéo",
  audio: "Entrée audio",
  queued: "En attente",
  processing: "En cours",
  done: "Terminé",
  failed: "Échoué",
  cancelled: "Annulé",
};
const REFRESH_MS = 3000;

const $ = (id) => document.getElementById(id);
const show = (el, visible = true) => { el.hidden = !visible; };
let timer = null;
const openRows = new Set();

class Unauthorized extends Error {}

async function call(path, options) {
  const response = await fetch(`/api${path}`, options);
  if (response.status === 401 && path !== "/login") throw new Unauthorized();
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : `Erreur ${response.status}`);
  }
  return response.json();
}

function cell(row, text) {
  const td = row.insertCell();
  td.textContent = text ?? "–";
  return td;
}

function pill(label, up, detail) {
  const span = document.createElement("span");
  span.className = `pill ${up ? "up" : "down"}`;
  span.textContent = `${label} : ${up ? "en service" : "à l'arrêt"}`;
  if (detail) span.title = detail;
  return span;
}

function renderServices(overview) {
  const pills = [
    pill("Application utilisateur", overview.api.up, overview.api.detail),
    pill("Base de données", overview.database.up, overview.database.detail),
  ];
  if (overview.workers.length === 0) {
    pills.push(pill("Worker", false, "Aucun worker enregistré"));
  }
  for (const worker of overview.workers) {
    const seen = new Date(worker.heartbeat_at + "Z").toLocaleTimeString("fr-FR");
    const device = { cuda: " (GPU)", cpu: " (CPU)" }[worker.device] ?? "";
    pills.push(pill(`Worker ${worker.id}${device}`, worker.up, `Dernier signal : ${seen}`));
  }
  const disk = document.createElement("span");
  disk.className = "pill";
  disk.textContent = `Disque : ${overview.disk.free_gb.toFixed(0)} Go libres sur ${overview.disk.total_gb.toFixed(0)}`;
  $("services").replaceChildren(...pills, disk);
}

function renderStats(stats) {
  show($("tiles"), !!stats);
  show($("by-type").closest("section"), !!stats);
  if (!stats) return;
  const tiles = [
    ["Inférences réalisées", stats.completed.total],
    ["Traitements non terminés", stats.unfinished.total],
    ["Traitements échoués", stats.failed.total],
    ["Traitements annulés", stats.cancelled.total],
    ["Temps de calcul moyen", stats.avg_compute_s == null ? "–" : `${stats.avg_compute_s.toFixed(1)} s`],
    ["Calcul / durée du média", stats.avg_realtime_factor == null ? "–" : `× ${stats.avg_realtime_factor.toFixed(2)}`],
  ];
  $("tiles").replaceChildren(...tiles.map(([label, value]) => {
    const tile = document.createElement("div");
    tile.className = "tile";
    const strong = document.createElement("strong");
    strong.textContent = value;
    const span = document.createElement("span");
    span.textContent = label;
    tile.append(strong, span);
    return tile;
  }));

  const body = $("by-type").tBodies[0];
  body.replaceChildren();
  for (const [group, keys] of [
    ["by_output_type", ["video_embedded", "video_subtitles", "subtitles", "text"]],
    ["by_input_kind", ["video", "audio"]],
  ]) {
    for (const key of keys) {
      const row = body.insertRow();
      cell(row, LABELS[key]);
      for (const metric of ["completed", "unfinished", "failed"]) {
        cell(row, stats[metric][group][key] ?? 0);
      }
    }
  }
}

function renderJobs(jobs) {
  const body = $("jobs").tBodies[0];
  body.replaceChildren();
  for (const job of jobs) {
    const row = body.insertRow();
    cell(row, new Date(job.created_at + "Z").toLocaleString("fr-FR"));
    cell(row, job.filename);
    cell(row, LABELS[job.output_type]);
    cell(row, job.target_language ?? "origine");
    cell(row, job.model);
    const status = job.status === "processing" ? `En cours (${job.progress} %)` : LABELS[job.status];
    cell(row, status).className = `status ${job.status}`;
    cell(row, job.compute_s == null ? null : `${job.compute_s.toFixed(1)} s`);
    const content = job.text ?? job.error;
    const td = cell(row, content ? "" : null);
    if (content) {
      const details = document.createElement("details");
      details.open = openRows.has(job.id);
      details.ontoggle = () => (details.open ? openRows.add(job.id) : openRows.delete(job.id));
      const summary = document.createElement("summary");
      summary.textContent = job.text ? "Voir le texte" : "Voir l'erreur";
      const p = document.createElement("p");
      p.textContent = content;
      details.append(summary, p);
      td.append(details);
    }
  }
}

async function renderLogs() {
  const files = await call("/logs");
  const select = $("log-file");
  const current = select.value;
  select.replaceChildren(...files.map((f) => new Option(f.name, f.name)));
  if (files.some((f) => f.name === current)) select.value = current;
  if (!select.value) {
    $("log").textContent = "Aucun journal pour l'instant.";
    return;
  }
  const log = $("log");
  const atBottom = log.scrollTop + log.clientHeight >= log.scrollHeight - 20;
  log.textContent = (await call(`/logs/${encodeURIComponent(select.value)}?lines=300`)).lines.join("\n");
  if (atBottom) log.scrollTop = log.scrollHeight;
}

function showLogin(message) {
  clearTimeout(timer);
  show($("dashboard"), false);
  show($("logout"), false);
  show($("login"));
  $("error").textContent = message ?? "";
  show($("error"), !!message);
}

async function refresh() {
  clearTimeout(timer);
  try {
    const overview = await call("/overview");
    show($("login"), false);
    show($("error"), false);
    show($("logout"));
    show($("dashboard"));
    renderServices(overview);
    renderStats(overview.stats);
    // Logs and jobs are independent: a database outage must not hide the logs.
    await Promise.all([
      call("/jobs").then(
        (jobs) => { show($("jobs-error"), false); renderJobs(jobs); },
        (e) => {
          if (e instanceof Unauthorized) throw e;
          $("jobs-error").textContent = e.message;
          show($("jobs-error"));
        },
      ),
      renderLogs(),
    ]);
  } catch (e) {
    if (e instanceof Unauthorized) return showLogin();
    $("error").textContent = `Console injoignable : ${e.message}`;
    show($("error"));
  }
  timer = setTimeout(refresh, REFRESH_MS);
}

$("login").onsubmit = async (e) => {
  e.preventDefault();
  try {
    await call("/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: $("username").value, password: $("password").value }),
    });
    $("password").value = "";
    refresh();
  } catch (err) {
    showLogin(err.message);
  }
};

$("logout").onclick = async () => {
  await call("/logout", { method: "POST" }).catch(() => {});
  showLogin();
};

$("log-file").onchange = () => renderLogs().catch(() => {});

refresh();
