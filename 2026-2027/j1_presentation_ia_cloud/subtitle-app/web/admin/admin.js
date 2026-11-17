// Admin console: dashboard and metrics, accounts, jobs, logs.
const $ = (id) => document.getElementById(id);
const show = (node, visible = true) => { node.hidden = !visible; };
const REFRESH_MS = { overview: 10000, jobs: 3000, logs: 3000 };

let tab = "overview";
let days = 30;
let timer = null;
let me = null;
let jobUser = null; // {id, username} when the jobs tab is filtered on one account
let openUser = null;
const openRows = new Set();

class Unauthorized extends Error {}

async function call(path, options) {
  const response = await fetch(`/api${path}`, options);
  if (response.status === 401 && path !== "/login") throw new Unauthorized();
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : `Erreur ${response.status}`);
  }
  return response.status === 204 ? null : response.json();
}

const send = (method, body) => ({
  method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
});

function notify(text, isError = false, target = "") {
  const error = $(`${target}error`) ?? $("error");
  if (isError) {
    error.textContent = text;
    show(error);
  } else {
    show(error, false);
    $("notice").textContent = text;
    show($("notice"), !!text);
    clearTimeout(notify.timer);
    notify.timer = setTimeout(() => show($("notice"), false), 4000);
  }
}

const tile = (value, label, hint) =>
  el("div", { className: "tile", title: hint ?? "" }, el("strong", { textContent: value }), el("span", { textContent: label }));

// --- dashboard -------------------------------------------------------------------

function pill(label, up, detail) {
  const span = el("span", { className: `pill ${up ? "up" : "down"}`, textContent: `${label} : ${up ? "en service" : "à l'arrêt"}` });
  if (detail) span.title = detail;
  return span;
}

function renderServices(overview) {
  const pills = [
    pill("Application utilisateur", overview.api.up, overview.api.detail),
    pill("Base de données", overview.database.up, overview.database.detail),
  ];
  if (overview.workers.length === 0) pills.push(pill("Worker", false, "Aucun worker enregistré"));
  for (const worker of overview.workers) {
    const device = { cuda: " (GPU)", cpu: " (CPU)" }[worker.device] ?? "";
    pills.push(pill(`Worker ${worker.id}${device}`, worker.up, `Dernier signal : ${fmt.date(worker.heartbeat_at)}`));
  }
  pills.push(el("span", { className: "pill", textContent: `Disque : ${overview.disk.free_gb.toFixed(0)} Go libres sur ${overview.disk.total_gb.toFixed(0)}` }));
  $("services").replaceChildren(...pills);
}

const shortDay = (iso) => { const [, m, d] = iso.split("-"); return `${d}/${m}`; };
const longDay = (iso) => new Date(`${iso}T12:00:00Z`).toLocaleDateString("fr-FR", { weekday: "short", day: "numeric", month: "long" });
const count = (v) => fmt.number(Math.round(v));
const minutes = (v) => `${(v).toLocaleString("fr-FR", { maximumFractionDigits: v < 10 ? 1 : 0 })} min`;

function renderMetrics(m, overview) {
  const j = m.jobs;
  const allTime = overview.stats;
  $("tiles").replaceChildren(
    tile(fmt.number(m.users.total), "Comptes", `${m.users.admins} administrateur(s), ${m.users.sso} avec connexion unique, ${m.users.disabled} désactivé(s)`),
    tile(`+${fmt.number(m.users.new)}`, `Nouveaux comptes (${m.days} j)`),
    tile(fmt.number(m.users.active_7d), "Utilisateurs actifs (7 j)", `${m.users.active_30d} sur 30 jours`),
    tile(fmt.number(j.total), `Traitements (${m.days} j)`, allTime ? `${allTime.completed.total} réussis depuis le début` : undefined),
    tile(fmt.percent(j.success_rate), "Taux de réussite", "Réussis / (réussis + échoués)"),
    tile(fmt.duration(j.wait_s.avg), "Attente moyenne", `95 % des traitements ont attendu moins de ${fmt.duration(j.wait_s.p95)}`),
    tile(fmt.duration(j.compute_s.avg), "Calcul moyen", `95 % en moins de ${fmt.duration(j.compute_s.p95)}`),
    tile(fmt.bytes(m.storage.uploads_bytes), "Fichiers conservés", `${m.storage.uploads} fichier(s) déposé(s) encore sur le disque`),
  );

  const series = m.series;
  const categories = series.map((d) => shortDay(d.day));
  const titles = series.map((d) => longDay(d.day));
  Charts.columns($("chart-jobs"), {
    label: "Traitements par jour", categories, titles, format: count, integer: true,
    series: [
      { name: "Réussis", color: "--series-1", values: series.map((d) => d.done) },
      { name: "Échoués", color: "--series-2", values: series.map((d) => d.failed) },
      { name: "Autres", color: "--series-3", values: series.map((d) => d.jobs - d.done - d.failed) },
    ],
  });
  Charts.lines($("chart-users"), {
    label: "Utilisateurs par jour", categories, titles, format: count, integer: true,
    series: [
      { name: "Actifs", color: "--series-1", values: series.map((d) => d.active_users) },
      { name: "Nouveaux comptes", color: "--series-2", values: series.map((d) => d.new_users) },
    ],
  });
  Charts.lines($("chart-minutes"), {
    label: "Minutes traitées par jour", categories, titles, format: minutes,
    series: [
      { name: "Média transcrit", color: "--series-1", values: series.map((d) => d.media_s / 60) },
      { name: "Temps de calcul", color: "--series-2", values: series.map((d) => d.compute_s / 60) },
    ],
  });
  Charts.hbars($("chart-languages"), {
    label: "Langues demandées", valueName: "Traitements", format: count,
    items: m.by_language.map((r) => ({ label: fmt.language(r.language), value: r.jobs })),
  });
  Charts.hbars($("chart-outputs"), {
    label: "Types de résultat", valueName: "Traitements", format: count,
    items: Object.entries(m.jobs.by_output_type)
      .sort((a, b) => b[1] - a[1])
      .map(([type, n]) => ({ label: fmt.label(type), value: n })),
  });

  const body = $("models").tBodies[0];
  body.replaceChildren(...(m.by_model.length ? m.by_model.map((r) => el("tr", {},
    el("td", { textContent: r.model }),
    el("td", { className: "num", textContent: fmt.number(r.jobs) }),
    el("td", { className: "num", textContent: fmt.duration(r.avg_compute_s) }),
    el("td", { className: "num", textContent: r.realtime_factor == null ? "–" : `× ${fmt.decimal(r.realtime_factor, 2)}` }),
  )) : [el("tr", {}, el("td", { colSpan: 4, className: "muted", textContent: "Aucun traitement réussi sur la période." }))]));
}

async function refreshOverview() {
  const overview = await call("/overview");
  renderServices(overview);
  try {
    const m = await call(`/metrics?days=${days}`);
    show($("metrics-error"), false);
    renderMetrics(m, overview);
  } catch (e) {
    if (e instanceof Unauthorized) throw e;
    $("metrics-error").textContent = `Métriques indisponibles : ${e.message}`;
    show($("metrics-error"));
  }
}

for (const button of $("period").querySelectorAll("button")) {
  button.onclick = () => {
    days = Number(button.dataset.days);
    for (const b of $("period").querySelectorAll("button")) b.setAttribute("aria-pressed", String(b === button));
    refresh();
  };
}

// --- accounts ---------------------------------------------------------------------

function userCell(u) {
  return el("td", {},
    el("span", { textContent: u.display_name || u.username }),
    el("small", { textContent: [`@${u.username}`, u.email].filter(Boolean).join(" · ") }));
}

function loginMethods(u) {
  const methods = [];
  if (u.has_password) methods.push("Mot de passe");
  for (const p of u.providers ?? []) methods.push(p === "keycloak" ? "Keycloak" : p);
  return methods.join(" + ") || "–";
}

async function refreshUsers() {
  const users = await call(`/users?q=${encodeURIComponent($("user-search").value)}`);
  const body = $("users").tBodies[0];
  body.replaceChildren(...users.map((u) => {
    const row = el("tr", { className: "clickable", tabIndex: 0 },
      userCell(u),
      el("td", {}, el("span", { className: `badge ${u.role}`, textContent: fmt.label(u.role) })),
      el("td", {}, el("span", { className: `badge ${u.disabled ? "off" : "done"}`, textContent: u.disabled ? "Désactivé" : "Actif" })),
      el("td", { textContent: loginMethods(u) }),
      el("td", { className: "num", textContent: fmt.number(u.jobs) }),
      el("td", { className: "num", textContent: fmt.duration(u.compute_s) }),
      el("td", { textContent: fmt.ago(u.last_login_at) }),
      el("td", { textContent: fmt.ago(u.last_job_at) }),
    );
    row.onclick = () => openUserDialog(u.id);
    row.onkeydown = (e) => { if (e.key === "Enter") openUserDialog(u.id); };
    return row;
  }));
  show($("users-empty"), users.length === 0);
}

let searchTimer = null;
$("user-search").oninput = () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => refreshUsers().catch(handle), 250);
};

function historyRows(table, jobs) {
  const head = ["Date", "Fichier", "Résultat", "Langue", "Statut", "Attente", "Calcul"];
  table.replaceChildren(el("thead", {}, el("tr", {}, ...head.map((h) => el("th", { textContent: h })))));
  const body = table.createTBody();
  for (const job of jobs) {
    body.append(el("tr", {},
      el("td", { textContent: fmt.date(job.created_at) }),
      el("td", {}, el("span", { textContent: job.filename }), el("small", { textContent: `${fmt.duration(job.duration_s)} · ${fmt.bytes(job.size_bytes)}` })),
      el("td", { textContent: fmt.label(job.output_type) }),
      el("td", { textContent: fmt.language(job.target_language) }),
      el("td", {}, statusBadge(job)),
      el("td", { textContent: fmt.duration(job.wait_s) }),
      el("td", { textContent: fmt.duration(job.compute_s) }),
    ));
  }
  if (!jobs.length) body.append(el("tr", {}, el("td", { colSpan: head.length, className: "muted", textContent: "Aucun traitement." })));
}

async function openUserDialog(id) {
  try {
    const u = await call(`/users/${id}`);
    openUser = u;
    show($("ud-error"), false);
    $("ud-title").textContent = u.display_name || u.username;
    $("ud-subtitle").textContent = [
      `@${u.username}`, u.email, `créé le ${fmt.day(u.created_at)}`,
      `dernière connexion ${fmt.ago(u.last_login_at)}`, `connexion : ${loginMethods({ ...u, providers: u.identities.map((i) => i.provider) })}`,
    ].filter(Boolean).join(" · ");
    const s = u.stats;
    $("ud-tiles").replaceChildren(
      tile(fmt.number(s.jobs_total), "Traitements", `${s.jobs_done} réussi(s), ${s.jobs_failed} échoué(s), ${s.jobs_cancelled} annulé(s)`),
      tile(fmt.duration(s.media_s), "De média transcrit"),
      tile(fmt.duration(s.compute_s), "De calcul"),
      tile(fmt.bytes(s.storage_bytes), "Sur le disque"),
    );
    $("ud-display-name").value = u.display_name ?? "";
    $("ud-email").value = u.email ?? "";
    $("ud-role").value = u.role;
    $("ud-disabled").value = String(u.disabled);
    const self = me && me.id === u.id;
    $("ud-role").disabled = self;
    $("ud-disabled").disabled = self;
    $("ud-delete").disabled = self;
    $("ud-delete").title = self ? "Vous ne pouvez pas supprimer votre propre compte ici" : "";
    historyRows($("ud-history"), u.history.jobs);
    if (!$("user-dialog").open) $("user-dialog").showModal();
  } catch (e) {
    handle(e);
  }
}

$("ud-close").onclick = () => $("user-dialog").close();

$("ud-profile").onsubmit = async (e) => {
  e.preventDefault();
  const body = { display_name: $("ud-display-name").value, email: $("ud-email").value };
  if (!$("ud-role").disabled) {
    body.role = $("ud-role").value;
    body.disabled = $("ud-disabled").value === "true";
  }
  try {
    await call(`/users/${openUser.id}`, send("PATCH", body));
    notify("Compte mis à jour.");
    await Promise.all([openUserDialog(openUser.id), refreshUsers()]);
  } catch (err) {
    if (err instanceof Unauthorized) return handle(err);
    notify(err.message, true, "ud-");
  }
};

$("ud-password").onsubmit = async (e) => {
  e.preventDefault();
  try {
    await call(`/users/${openUser.id}/password`, send("POST", { new_password: $("ud-new-password").value }));
    $("ud-password").reset();
    notify(`Mot de passe de ${openUser.username} réinitialisé ; ses connexions sont fermées.`);
  } catch (err) {
    if (err instanceof Unauthorized) return handle(err);
    notify(err.message, true, "ud-");
  }
};

$("ud-all-jobs").onclick = () => {
  jobUser = { id: openUser.id, username: openUser.username };
  $("user-dialog").close();
  openTab("jobs");
};

$("ud-delete").onclick = async () => {
  const typed = prompt(`Supprimer définitivement le compte « ${openUser.username} », ses fichiers et son historique ?\nSaisissez son nom d'utilisateur pour confirmer.`);
  if (typed === null) return;
  if (typed.trim().toLowerCase() !== openUser.username) return notify("Nom d'utilisateur différent : rien n'a été supprimé.", true, "ud-");
  try {
    await call(`/users/${openUser.id}`, { method: "DELETE" });
    $("user-dialog").close();
    notify(`Compte ${openUser.username} supprimé.`);
    await refreshUsers();
  } catch (err) {
    if (err instanceof Unauthorized) return handle(err);
    notify(err.message, true, "ud-");
  }
};

$("new-user").onclick = () => {
  $("new-user-form").reset();
  show($("nu-error"), false);
  $("new-user-dialog").showModal();
};
$("nu-close").onclick = () => $("new-user-dialog").close();
$("new-user-form").onsubmit = async (e) => {
  e.preventDefault();
  try {
    const user = await call("/users", send("POST", {
      username: $("nu-username").value, password: $("nu-password").value, role: $("nu-role").value,
      display_name: $("nu-display-name").value, email: $("nu-email").value,
    }));
    $("new-user-dialog").close();
    notify(`Compte ${user.username} créé.`);
    await refreshUsers();
  } catch (err) {
    if (err instanceof Unauthorized) return handle(err);
    notify(err.message, true, "nu-");
  }
};

// --- jobs --------------------------------------------------------------------------

function renderJobs(jobs) {
  const body = $("jobs").tBodies[0];
  body.replaceChildren();
  for (const job of jobs) {
    const row = body.insertRow();
    const cell = (content, className = "") => row.append(el("td", { className }, content ?? "–"));
    cell(fmt.date(job.created_at));
    const who = el("a", { href: "#", textContent: job.username });
    who.onclick = (e) => { e.preventDefault(); openUserDialog(job.owner_id); };
    cell(who);
    cell(job.filename);
    cell(fmt.label(job.output_type));
    cell(fmt.language(job.target_language));
    cell(job.model);
    cell(statusBadge(job));
    cell(job.compute_s == null ? "–" : fmt.duration(job.compute_s), "num");
    const content = job.text ?? job.error;
    if (!content) { cell("–"); continue; }
    const details = el("details", { open: openRows.has(job.id) },
      el("summary", { textContent: job.text ? "Voir le texte" : "Voir l'erreur" }),
      el("p", { textContent: content }));
    details.ontoggle = () => (details.open ? openRows.add(job.id) : openRows.delete(job.id));
    cell(details);
  }
  if (!jobs.length) body.append(el("tr", {}, el("td", { colSpan: 9, className: "muted", textContent: "Aucun traitement." })));
}

async function refreshJobs() {
  show($("job-user-filter"), !!jobUser);
  if (jobUser) $("job-user-name").textContent = `Utilisateur : ${jobUser.username}`;
  const params = new URLSearchParams({ limit: "200" });
  if ($("job-status").value) params.set("status", $("job-status").value);
  if (jobUser) params.set("user_id", jobUser.id);
  try {
    renderJobs(await call(`/jobs?${params}`));
    show($("jobs-error"), false);
  } catch (e) {
    if (e instanceof Unauthorized) throw e;
    $("jobs-error").textContent = e.message;
    show($("jobs-error"));
  }
}

$("job-status").onchange = () => refresh();
$("job-user-clear").onclick = () => { jobUser = null; refresh(); };

// --- logs --------------------------------------------------------------------------

async function refreshLogs() {
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

$("log-file").onchange = () => refreshLogs().catch(handle);

// --- navigation, session -------------------------------------------------------------

function openTab(name) {
  tab = name;
  for (const t of document.querySelectorAll("[role=tab]")) t.setAttribute("aria-selected", String(t.dataset.tab === name));
  for (const panel of document.querySelectorAll("[data-panel]")) show(panel, panel.dataset.panel === name);
  history.replaceState(null, "", `#${name}`);
  refresh();
}

for (const t of document.querySelectorAll("[role=tab]")) t.onclick = () => openTab(t.dataset.tab);

function showLogin(message) {
  clearTimeout(timer);
  me = null;
  show($("dashboard"), false);
  show($("account"), false);
  show($("login"));
  if (message) notify(message, true);
  else show($("error"), false);
}

function handle(e) {
  if (e instanceof Unauthorized) return showLogin();
  notify(e.message, true);
}

async function refresh() {
  clearTimeout(timer);
  try {
    me ??= await call("/me").catch((e) => {
      if (e instanceof Unauthorized) throw e;
      return null; // database down: the console still shows services and logs
    });
    show($("login"), false);
    show($("account"));
    show($("dashboard"));
    $("whoami").textContent = me ? `Connecté : ${me.username}` : "";
    const loaders = { overview: refreshOverview, users: refreshUsers, jobs: refreshJobs, logs: refreshLogs };
    await loaders[tab]();
  } catch (e) {
    if (e instanceof Unauthorized) return showLogin();
    notify(`Console injoignable : ${e.message}`, true);
  }
  if (REFRESH_MS[tab]) timer = setTimeout(refresh, REFRESH_MS[tab]);
}

$("login").onsubmit = async (e) => {
  e.preventDefault();
  try {
    await call("/login", send("POST", { username: $("username").value, password: $("password").value }));
    $("password").value = "";
    show($("error"), false);
    refresh();
  } catch (err) {
    showLogin(err.message);
  }
};

$("logout").onclick = async () => {
  await call("/logout", { method: "POST" }).catch(() => {});
  showLogin();
};

const initial = location.hash.slice(1);
if (["overview", "users", "jobs", "logs"].includes(initial)) {
  tab = initial;
  for (const t of document.querySelectorAll("[role=tab]")) t.setAttribute("aria-selected", String(t.dataset.tab === tab));
  for (const panel of document.querySelectorAll("[data-panel]")) show(panel, panel.dataset.panel === tab);
}
refresh();
