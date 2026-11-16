// Shared by staff dashboards: shows who is logged in and handles log out.
// Usage: include this script, then call DS.session() which resolves to {id, name, role, username}.
window.DS = window.DS || {};

DS.session = async function () {
  const r = await fetch("/api/auth/me", { cache: "no-store" });
  if (r.status === 401) {
    location.href = "/login?next=" + encodeURIComponent(location.pathname);
    return new Promise(() => {}); // stop here while the browser redirects
  }
  const me = await r.json();
  document.querySelectorAll("[data-user-name]").forEach((el) => { el.textContent = me.name; });
  document.querySelectorAll("[data-logout]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await fetch("/api/auth/logout", { method: "POST" });
      location.href = "/";
    });
  });
  return me;
};
