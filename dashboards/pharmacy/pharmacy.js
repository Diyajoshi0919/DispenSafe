/* Pharmacy dashboard: today's bills, approved-bill QR codes, hand-over, live refresh. */
(function () {
  const $ = (sel) => document.querySelector(sel);

  const state = {
    bills: [],          // today's bills, newest first (GET /api/pharmacy/bills)
    selectedId: null,
    qrUrl: null,        // object URL of the current QR image, revoked when replaced
    busy: false,
  };

  // ---------- List and counts ----------

  async function loadBills() {
    state.bills = await DS.api("/api/pharmacy/bills");
    const count = (status) => state.bills.filter((b) => b.status === status).length;
    DS.bind("stat-waiting-opd", count("pending"));
    DS.bind("stat-waiting-student", count("approved"));
    DS.bind("stat-ready", count("confirmed"));
    DS.bind("stat-handed", count("handed_over"));

    if (state.selectedId == null && state.bills.length) state.selectedId = state.bills[0].id;
    renderList();
  }

  function renderList() {
    const list = $("#bill-list");
    if (!state.bills.length) {
      list.replaceChildren(DS.el("li", { class: "empty", text: "No bills yet today." }));
      return;
    }
    list.replaceChildren(...state.bills.map(listItem));
  }

  function listItem(bill) {
    const n = bill.items.length;
    const meta = `Bill #${bill.bill_no} · ${DS.time(bill.created_at)} · ${DS.money(bill.total)}`;
    return DS.el("li", {},
      DS.el("button", {
        class: "bill-card",
        type: "button",
        "aria-pressed": String(bill.id === state.selectedId),
        onclick: () => selectBill(bill.id),
      },
        DS.el("div", { class: "bill-card-top" },
          DS.el("span", { class: "bill-roll", text: bill.roll_no }),
          DS.badge(bill.status, "pharmacy")),
        DS.el("div", { class: "bill-name", text: bill.student?.name || "Name not on record" }),
        DS.el("div", { class: "bill-meta", text: `${meta} · ${n} item${n === 1 ? "" : "s"}` })));
  }

  // ---------- Detail ----------

  function selectBill(id) {
    state.selectedId = id;
    renderList();
    renderDetail();
  }

  function selectedBill() {
    return state.bills.find((b) => b.id === state.selectedId) || null;
  }

  function renderDetail() {
    const bill = selectedBill();
    $("#detail-empty").hidden = !!bill;
    $("#detail-body").hidden = !bill;
    if (!bill) return;

    DS.bind("roll_no", bill.roll_no);
    DS.bind("student_name", bill.student ? `${bill.student.name} · ${bill.student.programme}` : "Name not on record");
    DS.bind("bill_line", `Bill #${bill.bill_no} · printed ${DS.time(bill.created_at)}`);
    $("#detail-status").replaceChildren(DS.badge(bill.status, "pharmacy"));

    DS.showWhen(bill.status);
    DS.bind("reject_reason", bill.reject_reason || "No reason given.");
    DS.bind("handed_at", bill.status === "handed_over" ? `Handed over at ${DS.time(bill.updated_at)}` : "");

    $("#bill-items").replaceChildren(...bill.items.map((item) =>
      DS.el("tr", {},
        DS.el("td", { text: item.medicine_name }),
        DS.el("td", { class: "num", text: item.qty }),
        DS.el("td", { class: "num", text: DS.money(item.amount) }))));
    DS.bind("total", DS.money(bill.total));

    $("#handover").disabled = state.busy;
    $("#new-qr").disabled = state.busy;

    if (bill.status === "approved") loadQR(bill);
    else clearQR();
  }

  // ---------- QR code ----------

  // An <img> tag cannot send the staff header, so the SVG is fetched and shown through an object URL.
  async function loadQR(bill) {
    try {
      const url = await DS.blobUrl(`/api/pharmacy/bills/${bill.id}/qr.svg`);
      if (state.selectedId !== bill.id) { URL.revokeObjectURL(url); return; }
      setQR(url, `QR code for bill #${bill.bill_no}`);
    } catch (err) {
      clearQR();
      DS.showError(err.message);
    }
  }

  function setQR(url, alt) {
    if (state.qrUrl) URL.revokeObjectURL(state.qrUrl);
    state.qrUrl = url;
    const img = $("#qr-img");
    img.src = url;
    img.alt = alt;
    img.hidden = false;
  }

  function clearQR() {
    if (state.qrUrl) URL.revokeObjectURL(state.qrUrl);
    state.qrUrl = null;
    const img = $("#qr-img");
    img.removeAttribute("src");
    img.hidden = true;
  }

  // ---------- Actions ----------

  async function act(path, body) {
    state.busy = true;
    setButtonsBusy(true);
    try {
      await DS.api(path, { method: "POST", json: body });
      DS.showError("");
    } catch (err) {
      // 409 means the bill already moved on. The refresh shows the current state.
      DS.showError(err.message);
    } finally {
      state.busy = false;
      setButtonsBusy(false);
      await refresh();
    }
  }

  function setButtonsBusy(busy) {
    $("#handover").disabled = busy;
    $("#new-qr").disabled = busy;
  }

  async function newQR() {
    const bill = selectedBill();
    if (!bill) return;
    await act(`/api/pharmacy/bills/${bill.id}/new-qr`, undefined);
  }

  async function handover() {
    const bill = selectedBill();
    if (!bill) return;
    await act(`/api/pharmacy/bills/${bill.id}/handover`, { actor: DS.session.name || "Pharmacy" });
  }

  // ---------- Refresh ----------

  async function refresh() {
    try {
      await loadBills();
      renderDetail();
    } catch (err) {
      DS.showError(err.message);
    }
  }

  const scheduleRefresh = DS.debounce(refresh, 150);

  // ---------- Start ----------

  DS.start(async () => {
    DS.initTabs();
    DS.connect((event) => { if (event.startsWith("bill_")) scheduleRefresh(); });

    $("#new-qr").addEventListener("click", newQR);
    $("#handover").addEventListener("click", handover);

    await refresh();
  });
})();
