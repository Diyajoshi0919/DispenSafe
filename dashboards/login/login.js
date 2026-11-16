(function () {
  const form = document.getElementById("login-form");
  const err = document.getElementById("error");
  const btn = document.getElementById("submit");
  const pw = document.getElementById("password");
  const params = new URLSearchParams(location.search);

  // Only allow redirects to pages on this site
  const next = params.get("next");
  const safeNext = next && next.startsWith("/") && !next.startsWith("//") ? next : null;
  const titles = { "/opd": "OPD login", "/pharmacy": "Pharmacy login" };
  if (titles[safeNext]) {
    document.getElementById("login-title").textContent = titles[safeNext];
    document.title = titles[safeNext] + " | Campus Dispensary";
  }

  document.getElementById("show-pw").addEventListener("change", (e) => {
    pw.type = e.target.checked ? "text" : "password";
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    err.textContent = "";
    const username = form.username.value.trim();
    if (!username || !pw.value) {
      err.textContent = "Enter your username and password.";
      return;
    }
    btn.disabled = true;
    btn.textContent = "Logging in…";
    try {
      const r = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password: pw.value }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) {
        err.textContent = data.detail || "Could not log in. Try again.";
        pw.select();
        return;
      }
      const home = { opd: "/opd", pharmacy: "/pharmacy", admin: "/opd" }[data.role] || "/";
      location.href = safeNext || home;
    } catch {
      err.textContent = "Cannot reach the server. Check the network and try again.";
    } finally {
      btn.disabled = false;
      btn.textContent = "Log in";
    }
  });
})();
