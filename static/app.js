(() => {
  "use strict";

  const tg = window.Telegram && window.Telegram.WebApp;
  if (tg) {
    tg.ready();
    tg.expand();
  }
  const INIT_DATA = tg ? tg.initData : "";

  const PALETTE = ["#2dd4a7", "#6c8cf5", "#f2a93b", "#f2637b", "#a879f2",
                    "#4fd1e8", "#e8d24f", "#f28fce", "#7fe07f", "#f28f5c"];

  const state = {
    period: "oy",
    ref: todayIso(),
    kind: "hammasi",
    currency: "som",
    currencies: ["som"],
    summary: null,
    debts: null,
    recentOffset: 0,
    recentLimit: 20,
    me: null,
  };

  function todayIso() {
    const d = new Date();
    const tz = d.getTimezoneOffset();
    const local = new Date(d.getTime() - tz * 60000);
    return local.toISOString().slice(0, 10);
  }

  // ----------------------------------------------------------------------- //
  // API
  // ----------------------------------------------------------------------- //

  async function api(path, opts) {
    const res = await fetch(path, Object.assign({
      headers: { "X-Telegram-Init-Data": INIT_DATA },
    }, opts || {}));
    if (!res.ok) {
      let detail = res.statusText;
      try { detail = (await res.json()).detail || detail; } catch (_) {}
      throw new Error(detail);
    }
    if (res.status === 204) return null;
    return res.json();
  }

  // ----------------------------------------------------------------------- //
  // Formatlash
  // ----------------------------------------------------------------------- //

  function fmtMoney(value, currency) {
    const symbols = (state.me && state.me.currency_symbols) || { som: "so'm", usd: "$" };
    if (currency === "usd") {
      const v = Math.round(value * 100) / 100;
      let text = Number.isInteger(v) ? String(v) : v.toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
      return "$" + groupThousands(text);
    }
    const rounded = Math.round(value);
    return groupThousands(String(rounded)) + " " + (symbols.som || "so'm");
  }

  function groupThousands(numStr) {
    const neg = numStr.startsWith("-");
    if (neg) numStr = numStr.slice(1);
    const [intPart, frac] = numStr.split(".");
    const grouped = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, " ");
    return (neg ? "-" : "") + grouped + (frac ? "." + frac : "");
  }

  function catIcon(name) {
    return (state.me && state.me.category_icons && state.me.category_icons[name]) || "•";
  }

  function kindIcon(kind) {
    return (state.me && state.me.kind_icons && state.me.kind_icons[kind]) || "•";
  }

  function fmtDate(iso) {
    const MONTHS = ["yan", "fev", "mar", "apr", "may", "iyun", "iyul", "avg", "sen", "okt", "noy", "dek"];
    const [y, m, d] = iso.split("-").map(Number);
    return `${d}-${MONTHS[m - 1]}`;
  }

  function toast(msg) {
    const el = document.getElementById("toast");
    el.textContent = msg;
    el.classList.remove("hidden");
    clearTimeout(toast._t);
    toast._t = setTimeout(() => el.classList.add("hidden"), 2200);
  }

  // ----------------------------------------------------------------------- //
  // Davr navigatsiyasi
  // ----------------------------------------------------------------------- //

  function shiftRef(period, isoRef, delta) {
    const d = new Date(isoRef + "T00:00:00");
    if (period === "hafta") {
      d.setDate(d.getDate() + delta * 7);
    } else if (period === "oy") {
      d.setMonth(d.getMonth() + delta, 1);
    } else if (period === "yil") {
      d.setFullYear(d.getFullYear() + delta);
    }
    return d.toISOString().slice(0, 10);
  }

  // ----------------------------------------------------------------------- //
  // Donut (SVG)
  // ----------------------------------------------------------------------- //

  function renderDonut(segments, centerValue, centerSub) {
    const g = document.getElementById("donutSegments");
    g.innerHTML = "";
    g.setAttribute("class", "donut-segments");
    const r = 80, cx = 100, cy = 100, circumference = 2 * Math.PI * r;
    const total = segments.reduce((s, seg) => s + seg.value, 0);

    if (total > 0) {
      let offset = 0;
      segments.forEach((seg) => {
        if (seg.value <= 0) return;
        const share = seg.value / total;
        const len = share * circumference;
        const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        circle.setAttribute("cx", cx);
        circle.setAttribute("cy", cy);
        circle.setAttribute("r", r);
        circle.setAttribute("stroke", seg.color);
        circle.setAttribute("stroke-dasharray", `${len} ${circumference - len}`);
        circle.setAttribute("stroke-dashoffset", -offset);
        g.appendChild(circle);
        offset += len;
      });
    }

    document.getElementById("donutValue").textContent = centerValue;
    document.getElementById("donutSub").textContent = centerSub;
  }

  function renderCategoryList(rows, total, currency) {
    const el = document.getElementById("categoryList");
    el.innerHTML = "";
    if (!rows.length) {
      el.innerHTML = '<div class="empty-state">Bu davrda yozuv yo\'q.</div>';
      return;
    }
    rows.forEach((row, i) => {
      const share = total > 0 ? row.summa / total : 0;
      const color = PALETTE[i % PALETTE.length];
      const div = document.createElement("div");
      div.className = "cat-row";
      div.innerHTML = `
        <div class="cat-icon">${catIcon(row.kategoriya)}</div>
        <div class="cat-info">
          <div class="cat-name-row">
            <span class="cat-name">${escapeHtml(row.kategoriya)}</span>
            <span class="cat-amount">${fmtMoney(row.summa, currency)}</span>
          </div>
          <div class="cat-bar-bg"><div class="cat-bar-fill" style="width:${(share * 100).toFixed(0)}%;background:${color}"></div></div>
        </div>
        <div class="cat-share">${Math.round(share * 100)}%</div>
      `;
      el.appendChild(div);
    });
  }

  function renderPersonList(items, currency) {
    const el = document.getElementById("categoryList");
    el.innerHTML = "";
    if (!items.length) {
      el.innerHTML = '<div class="empty-state">Ochiq qarz yo\'q.</div>';
      return;
    }
    const total = items.reduce((s, i) => s + i.amount, 0);
    items.forEach((item) => {
      const share = total > 0 ? item.amount / total : 0;
      const div = document.createElement("div");
      div.className = "cat-row";
      div.innerHTML = `
        <div class="cat-icon">🤝</div>
        <div class="cat-info">
          <div class="cat-name-row">
            <span class="cat-name">${escapeHtml(item.person)}</span>
            <span class="cat-amount">${fmtMoney(item.amount, currency)}</span>
          </div>
          <div class="cat-bar-bg"><div class="cat-bar-fill" style="width:${(share * 100).toFixed(0)}%;background:var(--qarz-berdim)"></div></div>
        </div>
      `;
      el.appendChild(div);
    });
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  // ----------------------------------------------------------------------- //
  // Yuklash
  // ----------------------------------------------------------------------- //

  async function loadMe() {
    state.me = await api("/api/me");
  }

  async function loadSummary() {
    const data = await api(`/api/summary?period=${state.period}&ref=${state.ref}`);
    state.summary = data;
    document.getElementById("rangeLabel").textContent = data.label;

    // Valyuta chiplarini yangilash
    state.currencies = data.currencies.length ? data.currencies : ["som"];
    if (!state.currencies.includes(state.currency)) state.currency = state.currencies[0];
    renderCurrencyToggle();

    renderCurrentKind();
    state.recentOffset = 0;
    loadRecent(false);
  }

  async function loadDebts() {
    state.debts = await api("/api/debts");
  }

  function renderCurrencyToggle() {
    const el = document.getElementById("currencyToggle");
    el.innerHTML = "";
    if (state.currencies.length <= 1) return; // faqat bitta valyuta bo'lsa tugma shart emas
    const symbols = state.me.currency_symbols;
    state.currencies.forEach((cur) => {
      const btn = document.createElement("button");
      btn.textContent = symbols[cur] || cur.toUpperCase();
      if (cur === state.currency) btn.classList.add("active");
      btn.onclick = () => { state.currency = cur; renderCurrentKind(); loadRecent(false); };
      el.appendChild(btn);
    });
  }

  function renderCurrentKind() {
    const cur = state.currency;
    const data = state.summary && state.summary.by_currency[cur];

    if (state.kind === "qarz") {
      renderQarzKind();
      return;
    }

    if (!data) {
      renderDonut([], fmtMoney(0, cur), "");
      renderCategoryList([], 0, cur);
      return;
    }

    if (state.kind === "hammasi") {
      renderDonut(
        [
          { value: data.kirim, color: "#2dd4a7" },
          { value: data.chiqim, color: "#f2637b" },
        ],
        fmtMoney(data.farq, cur),
        "Farq (kirim − chiqim)"
      );
      const combined = [
        ...data.kirim_kategoriyalari.map((c) => ({ ...c, _tag: "kirim" })),
        ...data.chiqim_kategoriyalari.map((c) => ({ ...c, _tag: "chiqim" })),
      ].sort((a, b) => b.summa - a.summa);
      renderCategoryList(combined, data.kirim + data.chiqim, cur);
    } else if (state.kind === "kirim") {
      renderDonut(
        data.kirim_kategoriyalari.map((c, i) => ({ value: c.summa, color: PALETTE[i % PALETTE.length] })),
        fmtMoney(data.kirim, cur), "Kirim"
      );
      renderCategoryList(data.kirim_kategoriyalari, data.kirim, cur);
    } else if (state.kind === "chiqim") {
      renderDonut(
        data.chiqim_kategoriyalari.map((c, i) => ({ value: c.summa, color: PALETTE[i % PALETTE.length] })),
        fmtMoney(data.chiqim, cur), "Chiqim"
      );
      renderCategoryList(data.chiqim_kategoriyalari, data.chiqim, cur);
    }
  }

  function renderQarzKind() {
    if (!state.debts) { renderDonut([], "…", ""); return; }
    const cur = state.currency;
    const berdim = (state.debts.qarz_berdim.totals[cur]) || 0;
    const oldim = (state.debts.qarz_oldim.totals[cur]) || 0;
    renderDonut(
      [
        { value: berdim, color: "#f2a93b" },
        { value: oldim, color: "#6c8cf5" },
      ],
      fmtMoney(berdim - oldim, cur),
      "Sof qarz (menga − mendan)"
    );
    const items = [
      ...((state.debts.qarz_berdim.items[cur] || []).map((i) => ({ ...i, _dir: "📤" }))),
      ...((state.debts.qarz_oldim.items[cur] || []).map((i) => ({ ...i, _dir: "📥" }))),
    ].sort((a, b) => b.amount - a.amount);
    renderPersonList(items, cur);
  }

  async function loadRecent(append) {
    const listEl = document.getElementById("recentList");
    if (!append) listEl.innerHTML = '<div class="spinner">Yuklanmoqda…</div>';

    if (state.kind === "qarz") {
      // Qarzlar davr bilan bog'liq emas — /api/debts dan olinadi, alohida ro'yxat.
      document.getElementById("loadMore").classList.add("hidden");
      if (!state.debts) return;
      const cur = state.currency;
      const items = [
        ...((state.debts.qarz_berdim.items[cur] || []).map((i) => ({ ...i, kind: "qarz_berdim" }))),
        ...((state.debts.qarz_oldim.items[cur] || []).map((i) => ({ ...i, kind: "qarz_oldim" }))),
      ].sort((a, b) => (a.date < b.date ? 1 : -1));
      listEl.innerHTML = "";
      if (!items.length) { listEl.innerHTML = '<div class="empty-state">Ochiq qarz yo\'q.</div>'; return; }
      items.forEach((it) => listEl.appendChild(buildDebtRow(it, cur)));
      return;
    }

    const params = new URLSearchParams({
      start: state.summary.start, end: state.summary.end,
      currency: state.currency, limit: state.recentLimit, offset: state.recentOffset,
    });
    if (state.kind !== "hammasi") params.set("kind", state.kind);

    const data = await api(`/api/transactions?${params.toString()}`);
    if (!append) listEl.innerHTML = "";
    if (!data.items.length && !append) {
      listEl.innerHTML = '<div class="empty-state">Yozuv yo\'q.</div>';
    }
    data.items.forEach((tx) => listEl.appendChild(buildTxRow(tx)));

    const shown = state.recentOffset + data.items.length;
    document.getElementById("loadMore").classList.toggle("hidden", shown >= data.total_count);
  }

  function buildTxRow(tx) {
    const div = document.createElement("div");
    div.className = "tx-row";
    const icon = tx.kind.startsWith("qarz") ? "🤝" : catIcon(tx.category);
    div.innerHTML = `
      <div class="tx-icon">${icon}</div>
      <div class="tx-main">
        <div class="tx-note">${escapeHtml(tx.note || tx.category)}${tx.person ? " — " + escapeHtml(tx.person) : ""}</div>
        <div class="tx-meta">${fmtDate(tx.date)} · ${escapeHtml(tx.category)}</div>
      </div>
      <div class="tx-amount ${tx.kind}">${kindIcon(tx.kind)} ${fmtMoney(tx.amount, tx.currency)}</div>
      <button class="tx-del" data-id="${tx.id}" aria-label="O'chirish">🗑</button>
    `;
    div.querySelector(".tx-del").onclick = () => deleteTx(tx.id, div);
    return div;
  }

  function buildDebtRow(item, currency) {
    const div = document.createElement("div");
    div.className = "tx-row";
    div.innerHTML = `
      <div class="tx-icon">${item.kind === "qarz_berdim" ? "📤" : "📥"}</div>
      <div class="tx-main">
        <div class="tx-note">${escapeHtml(item.person)}</div>
        <div class="tx-meta">${fmtDate(item.date)}${item.note ? " · " + escapeHtml(item.note) : ""}</div>
      </div>
      <div class="tx-amount ${item.kind}">${fmtMoney(item.amount, currency)}</div>
    `;
    return div;
  }

  async function deleteTx(id, rowEl) {
    if (tg && tg.showConfirm) {
      tg.showConfirm("Bu yozuvni o'chirasizmi?", async (ok) => {
        if (ok) await doDelete(id, rowEl);
      });
    } else if (confirm("Bu yozuvni o'chirasizmi?")) {
      await doDelete(id, rowEl);
    }
  }

  async function doDelete(id, rowEl) {
    try {
      await api(`/api/transactions/${id}`, { method: "DELETE" });
      rowEl.remove();
      toast("O'chirildi");
      loadSummary();
    } catch (e) {
      toast("Xatolik: " + e.message);
    }
  }

  // ----------------------------------------------------------------------- //
  // Qidiruv
  let searchTimer = null;

  function initSearch() {
    const panel = document.getElementById("searchPanel");
    const dashboard = document.getElementById("dashboard");
    const toggle = document.getElementById("searchToggle");
    const input = document.getElementById("searchInput");

    toggle.onclick = () => {
      const opening = panel.classList.contains("hidden");
      panel.classList.toggle("hidden");
      dashboard.classList.toggle("hidden", opening);
      if (opening) input.focus();
    };

    input.oninput = () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(runSearch, 350);
    };
  }

  async function runSearch() {
    const q = document.getElementById("searchInput").value.trim();
    const resultsEl = document.getElementById("searchResults");
    const metaEl = document.getElementById("searchMeta");
    if (!q) { resultsEl.innerHTML = ""; metaEl.textContent = ""; return; }

    resultsEl.innerHTML = '<div class="spinner">Qidirilmoqda…</div>';
    try {
      const data = await api(`/api/transactions?search=${encodeURIComponent(q)}&limit=100`);
      resultsEl.innerHTML = "";
      if (!data.items.length) {
        metaEl.textContent = "Natija topilmadi.";
        return;
      }
      const totalsStr = Object.entries(data.totals)
        .map(([cur, v]) => fmtMoney(v, cur)).join(" + ");
      metaEl.textContent = `${data.total_count} ta natija · Jami: ${totalsStr}`;
      data.items.forEach((tx) => resultsEl.appendChild(buildTxRow(tx)));
    } catch (e) {
      metaEl.textContent = "Xatolik: " + e.message;
    }
  }

  // ----------------------------------------------------------------------- //
  // Boshlash
  // ----------------------------------------------------------------------- //

  function initTabs() {
    document.querySelectorAll("#periodTabs button").forEach((btn) => {
      btn.onclick = () => {
        document.querySelectorAll("#periodTabs button").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        state.period = btn.dataset.period;
        state.ref = todayIso();
        loadSummary();
      };
    });

    document.querySelectorAll("#kindTabs button").forEach((btn) => {
      btn.onclick = () => {
        document.querySelectorAll("#kindTabs button").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        state.kind = btn.dataset.kind;
        renderCurrentKind();
        state.recentOffset = 0;
        loadRecent(false);
      };
    });

    document.getElementById("prevRange").onclick = () => {
      state.ref = shiftRef(state.period, state.ref, -1);
      loadSummary();
    };
    document.getElementById("nextRange").onclick = () => {
      state.ref = shiftRef(state.period, state.ref, 1);
      loadSummary();
    };
    document.getElementById("loadMore").onclick = () => {
      state.recentOffset += state.recentLimit;
      loadRecent(true);
    };
  }

  async function main() {
    if (!INIT_DATA) {
      document.getElementById("app").innerHTML =
        '<div class="empty-state" style="padding-top:60px">⚠️ Bu sahifa faqat Telegram ichida ishlaydi.<br>Botdagi «📊 Boshqaruv paneli» tugmasini bosing.</div>';
      return;
    }
    try {
      await loadMe();
    } catch (e) {
      document.getElementById("app").innerHTML =
        `<div class="empty-state" style="padding-top:60px">⚠️ ${escapeHtml(e.message)}</div>`;
      return;
    }
    initTabs();
    initSearch();
    await Promise.all([loadSummary(), loadDebts()]);
  }

  main();
})();
