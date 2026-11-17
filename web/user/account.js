// "Mon compte": profile, history, figures, password, single sign-on, account deletion.
const $ = (id) => document.getElementById(id);
const PAGE_SIZE = 20;
let account = null;
let offset = 0;

async function api(path, options = {}) {
  const response = await fetch(`/api${path}`, options);
  if (response.status === 401) {
    location.replace("/login.html");
    return new Promise(() => {});
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : `Erreur ${response.status}`);
  }
  return response.status === 204 ? null : response.json();
}

const send = (method, body) => ({
  method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
});

function message(text, isError = false) {
  $("notice").hidden = isError || !text;
  $("error").hidden = !isError || !text;
  $(isError ? "error" : "notice").textContent = text ?? "";
  if (text) window.scrollTo({ top: 0, behavior: "smooth" });
}

// --- tabs -----------------------------------------------------------------------

function openTab(name) {
  for (const tab of document.querySelectorAll("[role=tab]")) {
    tab.setAttribute("aria-selected", String(tab.dataset.tab === name));
  }
  for (const panel of document.querySelectorAll("[data-panel]")) {
    panel.hidden = panel.dataset.panel !== name;
  }
  history.replaceState(null, "", `#${name}`);
  if (name === "history") loadHistory();
}

for (const tab of document.querySelectorAll("[role=tab]")) {
  tab.onclick = () => openTab(tab.dataset.tab);
}

// --- rendering --------------------------------------------------------------------

function tile(value, label, hint) {
  return el("div", { className: "tile", title: hint ?? "" }, el("strong", { textContent: value }), el("span", { textContent: label }));
}

function renderOverview() {
  const name = account.display_name || account.username;
  $("avatar").textContent = name.trim().charAt(0).toUpperCase();
  $("title").textContent = name;
  const parts = [`@${account.username}`, fmt.label(account.role), `membre depuis le ${fmt.day(account.created_at)}`];
  $("subtitle").textContent = parts.join(" · ");

  const s = account.stats;
  $("tiles").replaceChildren(
    tile(fmt.number(s.jobs_total), "Traitements demandés"),
    tile(fmt.number(s.jobs_done), "Traitements réussis",
      s.jobs_failed ? `${s.jobs_failed} échoué(s), ${s.jobs_cancelled} annulé(s)` : undefined),
    tile(fmt.duration(s.media_s), "De média transcrit"),
    tile(fmt.duration(s.compute_s), "De calcul",
      s.realtime_factor == null ? undefined : `${fmt.decimal(s.realtime_factor, 2)} s de calcul par seconde de média`),
    tile(fmt.bytes(s.storage_bytes), "Conservés sur le serveur"),
    tile(fmt.ago(s.last_job_at), "Dernier traitement"),
  );
}

function historyTable(table, jobs, compact) {
  const head = ["Date", "Fichier", "Résultat", "Langue", "Modèle", "Statut", "Attente", "Calcul", "Total", ""];
  const columns = compact ? [0, 1, 2, 5, 8, 9] : head.map((_, i) => i);
  table.replaceChildren(
    el("thead", {}, el("tr", {}, ...columns.map((i) => el("th", { textContent: head[i] })))),
  );
  const body = table.createTBody();
  for (const job of jobs) {
    const file = el("div", {}, el("span", { textContent: job.filename }),
      el("small", { textContent: `${fmt.label(job.input_kind)} · ${fmt.duration(job.duration_s)} · ${fmt.bytes(job.size_bytes)}` }));
    const action = job.available
      ? el("a", { href: `/api/jobs/${job.id}/download`, textContent: "Télécharger" })
      : el("span", { className: "muted", textContent: job.status === "done" ? "Supprimé" : "" });
    const cells = [
      fmt.date(job.created_at), file, fmt.label(job.output_type), fmt.language(job.target_language),
      job.model, statusBadge(job), fmt.duration(job.wait_s), fmt.duration(job.compute_s),
      fmt.duration(job.total_s), action,
    ];
    const row = body.insertRow();
    for (const i of columns) row.append(el("td", {}, cells[i]));
  }
}

function renderProfile() {
  $("username").value = account.username;
  $("role").value = fmt.label(account.role);
  $("display-name").value = account.display_name ?? "";
  $("email").value = account.email ?? "";
  const facts = [
    ["Compte créé le", fmt.date(account.created_at)],
    ["Dernière connexion", fmt.date(account.last_login_at)],
    ["Connexion par mot de passe", account.has_password ? "oui" : "non (compte créé par connexion unique)"],
  ];
  $("facts").replaceChildren(...facts.flatMap(([k, v]) => [el("dt", { textContent: k }), el("dd", { textContent: v })]));
}

function renderSecurity() {
  const hasPassword = account.has_password;
  $("current-label").hidden = !hasPassword;
  $("current").required = hasPassword;
  $("password-title").textContent = hasPassword ? "Changer de mot de passe" : "Définir un mot de passe";
  $("password-help").hidden = hasPassword;
  $("password-help").textContent = `Votre compte a été créé avec ${account.sso.label} : définissez un mot de passe pour pouvoir aussi vous connecter avec votre nom d'utilisateur (${account.username}).`;
  $("delete-password-label").hidden = !hasPassword;
  $("delete-password").required = hasPassword;

  const linked = account.identities.find((i) => i.provider === account.sso.provider);
  $("sso").hidden = !account.sso.enabled && !linked;
  for (const label of document.querySelectorAll(".sso-label")) label.textContent = account.sso.label;
  $("sso-linked").hidden = !linked;
  $("sso-unlinked").hidden = !!linked || !account.sso.enabled;
  if (linked) {
    $("sso-detail").textContent = ` (${linked.email ?? "adresse non communiquée"}, associé le ${fmt.day(linked.created_at)})`;
  }
}

async function load() {
  account = await api("/account");
  renderOverview();
  renderProfile();
  renderSecurity();
  const recent = await api("/account/jobs?limit=5");
  historyTable($("recent"), recent.jobs, true);
  $("recent-empty").hidden = recent.total > 0;
  $("recent").hidden = recent.total === 0;
}

async function loadHistory() {
  const page = await api(`/account/jobs?limit=${PAGE_SIZE}&offset=${offset}`);
  historyTable($("history"), page.jobs, false);
  const last = Math.min(offset + PAGE_SIZE, page.total);
  $("page").textContent = page.total ? `${offset + 1}–${last} sur ${page.total}` : "Aucun traitement";
  $("newer").disabled = offset === 0;
  $("older").disabled = last >= page.total;
}

$("newer").onclick = () => { offset = Math.max(offset - PAGE_SIZE, 0); loadHistory(); };
$("older").onclick = () => { offset += PAGE_SIZE; loadHistory(); };

// --- forms ----------------------------------------------------------------------

$("profile").onsubmit = async (e) => {
  e.preventDefault();
  try {
    account = await api("/account", send("PATCH", {
      display_name: $("display-name").value, email: $("email").value,
    }));
    renderOverview();
    renderProfile();
    message("Profil enregistré.");
  } catch (err) {
    message(err.message, true);
  }
};

$("password").onsubmit = async (e) => {
  e.preventDefault();
  if ($("new").value !== $("confirm").value) return message("Les deux mots de passe ne sont pas identiques.", true);
  try {
    await api("/account/password", send("POST", {
      current_password: $("current").value || null, new_password: $("new").value,
    }));
    $("password").reset();
    message("Mot de passe enregistré. Vos autres connexions ont été fermées.");
    await load();
  } catch (err) {
    message(err.message, true);
  }
};

$("unlink").onclick = async () => {
  if (!confirm(`Dissocier votre compte ${account.sso.label} ?`)) return;
  try {
    await api(`/account/identities/${encodeURIComponent(account.sso.provider)}`, { method: "DELETE" });
    message(`Compte ${account.sso.label} dissocié.`);
    await load();
  } catch (err) {
    message(err.message, true);
  }
};

$("delete").onsubmit = async (e) => {
  e.preventDefault();
  if (!confirm("Supprimer définitivement votre compte, vos fichiers et votre historique ?")) return;
  try {
    await api("/account", send("DELETE", {
      confirm: $("delete-confirm").value, password: $("delete-password").value || null,
    }));
    location.replace("/login.html");
  } catch (err) {
    message(err.message, true);
  }
};

$("logout").onclick = async () => {
  await fetch("/api/auth/logout", { method: "POST" }).catch(() => {});
  location.replace("/login.html");
};

// --- start ----------------------------------------------------------------------

const params = new URLSearchParams(location.search);
if (params.get("error")) message(params.get("error"), true);
else if (params.get("linked")) message("Compte associé : vous pouvez maintenant vous connecter avec lui.");
if (params.has("error") || params.has("linked")) history.replaceState(null, "", location.pathname + location.hash);

load()
  .then(() => {
    const tab = location.hash.slice(1);
    const known = [...document.querySelectorAll("[role=tab]")].some((t) => t.dataset.tab === tab);
    openTab(known ? tab : params.has("linked") || params.has("error") ? "security" : "overview");
  })
  .catch((err) => message(`Chargement impossible : ${err.message}`, true));
