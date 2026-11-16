// Home page: fills "Today at the dispensary" and the live updates strip.
// Expects GET /api/home to return:
// {
//   "opd_open": true,
//   "doctor_on_duty": "Dr. ...",
//   "pharmacy_hours": "9:00 to 17:00",
//   "bills_waiting": 3,
//   "emergency_phone": "...",
//   "notices": ["OPD closes at 2 pm today", "..."]
// }
// Until that endpoint exists, the placeholders in the HTML stay as they are.

(function () {
  const REFRESH_MS = 30000;

  const today = new Date();
  document.getElementById("today-date").textContent =
    today.toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" });
  document.getElementById("today-date").dateTime = today.toISOString().slice(0, 10);
  document.getElementById("year").textContent = today.getFullYear();

  function setField(name, value) {
    document.querySelectorAll(`[data-field="${name}"]`).forEach((el) => { el.textContent = value; });
  }

  function renderNotices(notices) {
    const list = document.getElementById("updates-list");
    if (!notices || !notices.length) return;
    // The list is duplicated so the scrolling animation loops without a gap.
    const items = notices.concat(notices);
    list.replaceChildren(...items.map((text, i) => {
      const li = document.createElement("li");
      li.textContent = text;
      if (i >= notices.length) li.setAttribute("aria-hidden", "true");
      return li;
    }));
  }

  async function load() {
    try {
      const r = await fetch("/api/home", { cache: "no-store" });
      if (!r.ok) return;
      const d = await r.json();

      const opd = document.querySelector('[data-field="opd_status"]');
      opd.textContent = d.opd_open ? "Open" : "Closed";
      opd.className = d.opd_open ? "open" : "closed";

      if (d.doctor_on_duty) setField("doctor_on_duty", d.doctor_on_duty);
      if (d.pharmacy_hours) setField("pharmacy_hours", d.pharmacy_hours);
      if (d.bills_waiting != null) setField("bills_waiting", d.bills_waiting);
      if (d.emergency_phone) setField("emergency_phone", d.emergency_phone);
      renderNotices(d.notices);
    } catch (e) {
      // Server not reachable or endpoint not built yet: keep the placeholders.
    }
  }

  load();
  setInterval(load, REFRESH_MS);
})();
