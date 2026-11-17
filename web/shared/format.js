// Labels and formatting shared by the user pages and the admin console.
const LABELS = {
  video_embedded: "Vidéo sous-titrée",
  video_subtitles: "Vidéo + sous-titres",
  subtitles: "Sous-titres seuls",
  text: "Texte",
  video: "Vidéo",
  audio: "Audio",
  queued: "En attente",
  processing: "En cours",
  done: "Terminé",
  failed: "Échoué",
  cancelled: "Annulé",
  user: "Utilisateur",
  admin: "Administrateur",
};
const LANGUAGE_NAMES = {
  fr: "Français", en: "Anglais", es: "Espagnol", ru: "Russe", ar: "Arabe", zh: "Chinois",
  de: "Allemand", it: "Italien",
};

const fmt = {
  // The API sends naive UTC timestamps.
  date(value) {
    return value ? new Date(value + "Z").toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" }) : "–";
  },
  day(value) {
    return value ? new Date(value + "Z").toLocaleDateString("fr-FR", { dateStyle: "medium" }) : "–";
  },
  ago(value) {
    if (!value) return "jamais";
    const s = (Date.now() - new Date(value + "Z")) / 1000;
    if (s < 60) return "à l'instant";
    if (s < 3600) return `il y a ${Math.floor(s / 60)} min`;
    if (s < 86400) return `il y a ${Math.floor(s / 3600)} h`;
    return `il y a ${Math.floor(s / 86400)} j`;
  },
  duration(seconds) {
    if (seconds == null) return "–";
    if (seconds < 10) return `${fmt.decimal(seconds, 1)} s`;
    if (seconds < 60) return `${Math.round(seconds)} s`;
    const m = Math.floor(seconds / 60);
    if (m < 60) return `${m} min ${String(Math.round(seconds % 60)).padStart(2, "0")} s`;
    return `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")} min`;
  },
  bytes(n) {
    if (n == null) return "–";
    const units = ["o", "Ko", "Mo", "Go", "To"];
    let i = 0;
    while (n >= 1000 && i < units.length - 1) { n /= 1000; i += 1; }
    return `${fmt.decimal(n, n < 10 && i ? 1 : 0)} ${units[i]}`;
  },
  decimal(n, digits) {
    return n.toLocaleString("fr-FR", { minimumFractionDigits: digits, maximumFractionDigits: digits });
  },
  number(n) {
    return n == null ? "–" : n.toLocaleString("fr-FR");
  },
  percent(ratio) {
    return ratio == null ? "–" : `${Math.round(ratio * 100)} %`;
  },
  language(code) {
    return code ? LANGUAGE_NAMES[code] ?? code : "Langue d'origine";
  },
  label(key) {
    return LABELS[key] ?? key ?? "–";
  },
};

// Element builder: el("td", { className: "x" }, "text", child...).
function el(tag, props = {}, ...children) {
  const node = Object.assign(document.createElement(tag), props);
  for (const child of children) {
    if (child != null) node.append(child);
  }
  return node;
}

function statusBadge(job) {
  const text = job.status === "processing" ? `En cours (${job.progress ?? 0} %)` : fmt.label(job.status);
  const badge = el("span", { className: `badge ${job.status}`, textContent: text });
  if (job.error) badge.title = job.error;
  return badge;
}
