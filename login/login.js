/* Staff sign-in, shared by the OPD and pharmacy login pages.
   Each page sets its role and destination on <body data-role data-dashboard>. */
(function () {
  const SESSION_KEY = "dispensafe.staff";
  const $ = (sel) => document.querySelector(sel);

  const role = document.body.dataset.role === "pharmacy" ? "pharmacy" : "opd";
  const dashboardUrl = new URL(document.body.dataset.dashboard, location.href).href;
  const apiBase = window.DS_API || "";
  // Any staff endpoint checks the key. A wrong key returns 401.
  const checkPath = role === "pharmacy" ? "/api/pharmacy/bills" : "/api/opd/bills?status=pending";

  const form = $("#login-form");
  const nameInput = $("#staff-name");
  const keyInput = $("#staff-key");
  const submit = $("#submit");
  const errorBox = $("#error");
  const noticeBox = $("#notice");

  function showError(msg) {
    errorBox.textContent = msg || "";
    errorBox.hidden = !msg;
    if (msg) keyInput.setAttribute("aria-invalid", "true");
  }

  // Sent here because a session ended: show why.
  if (new URLSearchParams(location.search).get("reason") === "expired") {
    noticeBox.textContent = "Your session has ended. Please sign in again.";
    noticeBox.hidden = false;
  }

  // Keep the name from an earlier sign-in in this tab.
  try {
    const saved = JSON.parse(sessionStorage.getItem(SESSION_KEY) || "null");
    if (saved && saved.name) nameInput.value = saved.name;
  } catch (_) { /* ignore */ }

  $("#toggle-key").addEventListener("click", (e) => {
    const show = keyInput.type === "password";
    keyInput.type = show ? "text" : "password";
    e.currentTarget.textContent = show ? "Hide" : "Show";
    e.currentTarget.setAttribute("aria-pressed", String(show));
  });
  keyInput.addEventListener("input", () => keyInput.removeAttribute("aria-invalid"));

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    showError("");
    const name = nameInput.value.trim();
    const key = keyInput.value.trim();
    if (!name) { showError("Enter your name."); nameInput.focus(); return; }
    if (!key) { showError("Enter the staff key."); keyInput.focus(); return; }

    submit.disabled = true;
    submit.textContent = "Checking...";
    let redirecting = false;
    try {
      const r = await fetch(apiBase + checkPath, { headers: { "X-Staff-Key": key }, cache: "no-store" });
      if (r.status === 401 || r.status === 403) {
        showError("The staff key is not correct. Check it and try again.");
        keyInput.select();
        return;
      }
      if (!r.ok) {
        showError(`The server returned an error (${r.status}). Try again in a moment.`);
        return;
      }
      sessionStorage.setItem(SESSION_KEY, JSON.stringify({ name, key }));
      redirecting = true;
      location.replace(dashboardUrl);
    } catch (_) {
      showError("Cannot reach the dispensary server. Check that it is running, then try again.");
    } finally {
      if (!redirecting) {
        submit.disabled = false;
        submit.textContent = "Sign in";
      }
    }
  });
})();
