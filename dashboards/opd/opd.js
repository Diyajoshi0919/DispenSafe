/* OPD dashboard: today's bill queue, bill review, approve or reject, live refresh. */
(function () {
  const $ = (sel) => document.querySelector(sel);

  // Every status the OPD side needs for the counts and the queue.
  const STATUSES = "pending,approved,confirmed,handed_over,rejected";

  const state = {
    queue: [],          // bills waiting for review
    selectedId: null,
    detail: null,       // response of GET /api/opd/bills/{id}
    busy: false,        // true while an approve or reject request is in flight
  };

  // ---------- Queue ----------

  async function loadQueue() {
    const bills = await DS.api(`/api/opd/bills?status=${STATUSES}`);
    const count = (...statuses) => bills.filter((b) => statuses.includes(b.status)).length;
    DS.bind("stat-waiting", count("pending"));
    DS.bind("stat-approved", count("approved", "confirmed", "handed_over"));
    DS.bind("stat-rejected", count("rejected"));

    state.queue = bills.filter((b) => b.status === "pending");
    if (state.selectedId == null && state.queue.length) state.selectedId = state.queue[0].id;
    renderQueue();
  }

  function renderQueue() {
    const list = $("#bill-list");
    if (!state.queue.length) {
      list.replaceChildren(DS.el("li", { class: "empty", text: "No bills waiting for review." }));
      return;
    }
    list.replaceChildren(...state.queue.map(queueItem));
  }

  function queueItem(bill) {
    const n = bill.items.length;
    const meta = `${DS.time(bill.created_at)} · ${n} item${n === 1 ? "" : "s"} · ${DS.money(bill.total)}`;
    return DS.el("li", {},
      DS.el("button", {
        class: "bill-card",
        type: "button",
        "aria-pressed": String(bill.id === state.selectedId),
        onclick: () => selectBill(bill.id),
      },
        DS.el("div", { class: "bill-card-top" },
          DS.el("span", { class: "bill-roll", text: bill.roll_no }),
          DS.badge(bill.status, "opd")),
        DS.el("div", { class: "bill-name", text: bill.student?.name || "Name not on record" }),
        DS.el("div", { class: "bill-meta", text: meta })));
  }

  // ---------- Detail ----------

  async function selectBill(id) {
    state.selectedId = id;
    renderQueue();
    await loadDetail(id);
  }

  async function loadDetail(id) {
    const data = await DS.api(`/api/opd/bills/${id}`);
    if (state.selectedId !== id) return; // user clicked another bill while this loaded
    state.detail = data;
    renderDetail(data);
  }

  function renderDetail({ bill, prescription: rx, not_on_prescription: flagged = [], activity = [] }) {
    $("#detail-empty").hidden = true;
    $("#detail-body").hidden = false;

    DS.bind("roll_no", bill.roll_no);
    DS.bind("student_name", bill.student?.name || "Name not on record");
    DS.bind("student_programme", bill.student?.programme || "");
    DS.bind("bill_line", `Bill #${bill.bill_no} · printed ${DS.time(bill.created_at)}`);
    $("#detail-status").replaceChildren(DS.badge(bill.status, "opd"));

    // Pharmacy bill. Lines not on the prescription are highlighted.
    $("#bill-items").replaceChildren(...bill.items.map((item) =>
      DS.el("tr", { class: flagged.includes(item.medicine_name) ? "flag" : null },
        DS.el("td", { text: item.medicine_name }),
        DS.el("td", { class: "num", text: item.qty }),
        DS.el("td", { class: "num", text: DS.money(item.amount) }))));
    DS.bind("total", DS.money(bill.total));

    const warn = $("#warn-box");
    warn.hidden = !flagged.length;
    warn.textContent = flagged.length ? `Not on the prescription: ${flagged.join(", ")}` : "";

    // Prescription on record.
    if (rx) {
      DS.bind("rx_meta", `Dr. ${rx.doctor_name || "Unknown"} · ${DS.time(rx.created_at)}`);
      DS.bind("rx_notes", rx.notes || "");
      $("#rx-items").replaceChildren(...rx.items.map((i) =>
        DS.el("tr", {},
          DS.el("td", { text: i.medicine_name }),
          DS.el("td", { class: "num", text: i.dose || "" }))));
      $("#view-photo").hidden = !rx.photo_file;
    } else {
      DS.bind("rx_meta", "No prescription on record");
      DS.bind("rx_notes", "");
      $("#rx-items").replaceChildren();
      $("#view-photo").hidden = true;
    }

    // Activity log.
    $("#activity").replaceChildren(...activity.map((a) =>
      DS.el("li", {},
        DS.el("time", { text: DS.time(a.at) }),
        DS.el("span", { text: a.detail || a.action }))));

    // Decisions are only possible while the bill is pending.
    updateButtons();
  }

  // ---------- Decisions ----------

  // Decisions are allowed only while the bill is pending and no request is in flight.
  function updateButtons() {
    const pending = state.detail?.bill.status === "pending";
    const hasReason = $("#reject-reason").value.trim().length > 0;
    $("#reject-reason").disabled = !pending || state.busy;
    $("#approve").disabled = !pending || state.busy;
    $("#reject").disabled = !pending || !hasReason || state.busy;
  }

  async function decide(kind) {
    const detail = state.detail;
    if (!detail) return;
    const body = { actor: DS.session.name || "OPD" };
    if (kind === "reject") body.reason = $("#reject-reason").value.trim();

    state.busy = true;
    updateButtons();
    try {
      await DS.api(`/api/opd/bills/${detail.bill.id}/${kind}`, { method: "POST", json: body });
      $("#reject-reason").value = "";
      DS.showError("");
    } catch (err) {
      // 409 means someone else already decided this bill. The refresh below shows the new state.
      DS.showError(err.message);
    } finally {
      state.busy = false;
      await refresh();
    }
  }

  async function viewPhoto() {
    const rx = state.detail?.prescription;
    if (!rx) return;
    try {
      const url = await DS.blobUrl(`/api/opd/prescriptions/${rx.id}/photo`);
      window.open(url, "_blank", "noopener");
    } catch (err) {
      DS.showError(err.message);
    }
  }

  // ---------- Refresh ----------

  async function refresh() {
    try {
      await loadQueue();
      if (state.selectedId != null) await loadDetail(state.selectedId);
    } catch (err) {
      DS.showError(err.message);
    }
  }

  const scheduleRefresh = DS.debounce(refresh, 150);

  // ---------- Start ----------

  DS.start(async () => {
    DS.initTabs();
    DS.connect((event) => { if (event.startsWith("bill_")) scheduleRefresh(); });

    $("#reject-reason").addEventListener("input", updateButtons);
    document.querySelectorAll("[data-reason]").forEach((chip) =>
      chip.addEventListener("click", () => {
        $("#reject-reason").value = chip.dataset.reason;
        updateButtons();
      }));

    $("#approve").addEventListener("click", () => decide("approve"));
    $("#reject").addEventListener("click", () => decide("reject"));
    $("#view-photo").addEventListener("click", viewPhoto);

    await refresh();
  });
})();
