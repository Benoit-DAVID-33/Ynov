// Login and account creation pages: the same form, posted to data-endpoint.
const $ = (id) => document.getElementById(id);
const form = $("auth");

function fail(message) {
  $("error").textContent = message;
  $("error").hidden = false;
}

// Already logged in: nothing to do here.
fetch("/api/auth/me").then((response) => { if (response.ok) location.replace("/"); });

// Single sign-on button, when a provider is configured.
fetch("/api/config")
  .then((response) => (response.ok ? response.json() : null))
  .then((config) => {
    if (!config?.sso?.enabled) return;
    for (const label of document.querySelectorAll(".sso-label")) label.textContent = config.sso.label;
    $("sso").hidden = false;
  })
  .catch(() => {});

// Error sent back by the single sign-on flow (?error=...).
const returned = new URLSearchParams(location.search).get("error");
if (returned) {
  fail(returned);
  history.replaceState(null, "", location.pathname);
}

form.onsubmit = async (event) => {
  event.preventDefault();
  $("error").hidden = true;
  if (form.hasAttribute("data-confirm") && $("password").value !== $("confirm").value) {
    return fail("Les deux mots de passe ne sont pas identiques.");
  }
  const button = form.querySelector("button");
  button.disabled = true;
  try {
    const response = await fetch(form.dataset.endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: $("username").value, password: $("password").value }),
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      let detail = body.detail;
      if (Array.isArray(detail)) detail = "Saisie invalide : vérifiez le nom d'utilisateur et le mot de passe.";
      throw new Error(detail ?? `Erreur ${response.status}`);
    }
    location.replace("/");
  } catch (e) {
    fail(e.message);
    button.disabled = false;
  }
};
