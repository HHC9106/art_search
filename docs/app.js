const TRACKING_KEY = "art-search-tracking";
const TRACKING_STATUSES = ["none", "interested", "applied", "accepted", "rejected", "ignored"];

let listings = [];

function loadTracking() {
  try {
    return JSON.parse(localStorage.getItem(TRACKING_KEY)) || {};
  } catch {
    return {};
  }
}

function saveTracking(tracking) {
  localStorage.setItem(TRACKING_KEY, JSON.stringify(tracking));
}

function setTrackingStatus(id, status) {
  const tracking = loadTracking();
  const prev = tracking[id] || {};
  tracking[id] = { ...prev, status, updated_at: new Date().toISOString() };
  saveTracking(tracking);
}

async function fetchJson(path) {
  const res = await fetch(path, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch ${path}: ${res.status}`);
  return res.json();
}

function mergeTracking(rawListings) {
  const tracking = loadTracking();
  return rawListings.map((l) => ({
    ...l,
    tracking: tracking[l.id] || { status: "none", note: "" },
  }));
}

function currentFilters() {
  const tierBoxes = document.querySelectorAll("#tier-filter input[type=checkbox]");
  const tiers = new Set(
    Array.from(tierBoxes)
      .filter((cb) => cb.checked)
      .map((cb) => Number(cb.value))
  );
  return {
    tiers,
    type: document.getElementById("type-filter").value,
    status: document.getElementById("status-filter").value,
    tracking: document.getElementById("tracking-filter").value,
    search: document.getElementById("search-box").value.trim().toLowerCase(),
    sort: document.getElementById("sort-order").value,
  };
}

function applyFilters(all, filters) {
  return all.filter((l) => {
    if (!filters.tiers.has(l.region_tier)) return false;
    if (filters.type && l.listing_type !== filters.type) return false;
    if (filters.status && l.status !== filters.status) return false;
    if (filters.tracking && l.tracking.status !== filters.tracking) return false;
    if (filters.search) {
      const haystack = `${l.title} ${l.organizer}`.toLowerCase();
      if (!haystack.includes(filters.search)) return false;
    }
    return true;
  });
}

function sortListings(items, sortOrder) {
  const sorted = [...items];
  const deadlineKey = (l) => (l.deadline ? l.deadline : "9999-99-99");
  if (sortOrder === "deadline") {
    sorted.sort((a, b) => deadlineKey(a).localeCompare(deadlineKey(b)));
  } else if (sortOrder === "recent") {
    sorted.sort((a, b) => (b.first_seen_date || "").localeCompare(a.first_seen_date || ""));
  } else {
    sorted.sort((a, b) => {
      if (a.region_tier !== b.region_tier) return a.region_tier - b.region_tier;
      return deadlineKey(a).localeCompare(deadlineKey(b));
    });
  }
  return sorted;
}

function tierLabel(tier) {
  return { 1: "UK", 2: "US/EU/TW", 3: "Other" }[tier] || "Other";
}

function render() {
  const filters = currentFilters();
  const filtered = sortListings(applyFilters(listings, filters), filters.sort);

  const tbody = document.getElementById("listings-body");
  tbody.innerHTML = "";

  document.getElementById("empty-state").hidden = filtered.length > 0;

  for (const listing of filtered) {
    const row = document.createElement("tr");
    if (listing.status === "closed") row.classList.add("closed-row");

    const deadlineCell = listing.deadline || listing.deadline_raw || "—";
    const urgentClass =
      listing.deadline && listing.status === "open"
        ? daysUntil(listing.deadline) <= 7
          ? "deadline-urgent"
          : daysUntil(listing.deadline) <= 30
          ? "deadline-soon"
          : ""
        : "";

    row.innerHTML = `
      <td><a href="${listing.url}" target="_blank" rel="noopener">${escapeHtml(listing.title)}</a></td>
      <td>${escapeHtml(listing.organizer || "")}</td>
      <td><span class="tier-badge tier-${listing.region_tier}">${tierLabel(listing.region_tier)}</span></td>
      <td>${escapeHtml(listing.listing_type || "")}</td>
      <td class="${urgentClass}">${escapeHtml(deadlineCell)}</td>
      <td>${listing.fee != null ? escapeHtml(String(listing.fee)) : "—"}</td>
      <td>${escapeHtml(listing.prize_amount || "—")}</td>
      <td></td>
    `;

    const trackingCell = row.lastElementChild;
    const select = document.createElement("select");
    for (const status of TRACKING_STATUSES) {
      const opt = document.createElement("option");
      opt.value = status;
      opt.textContent = status;
      if (listing.tracking.status === status) opt.selected = true;
      select.appendChild(opt);
    }
    select.addEventListener("change", () => {
      setTrackingStatus(listing.id, select.value);
      listing.tracking = { ...listing.tracking, status: select.value };
    });
    trackingCell.appendChild(select);

    tbody.appendChild(row);
  }
}

function daysUntil(isoDate) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const deadline = new Date(isoDate);
  return Math.floor((deadline - today) / (1000 * 60 * 60 * 24));
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function renderMetaBadge(meta) {
  const badge = document.getElementById("meta-badge");
  if (!meta.last_run) {
    badge.textContent = "No data yet — waiting for the first scrape run.";
    return;
  }
  const errored = Object.entries(meta.sources || {}).filter(([, v]) => v.status === "error");
  let text = `Last updated ${meta.last_run} · ${meta.open_listings} open / ${meta.total_listings} total`;
  if (errored.length) {
    text += ` · ${errored.length} source(s) failing`;
  }
  badge.textContent = text;
}

function setupExportImport() {
  document.getElementById("export-btn").addEventListener("click", () => {
    const blob = new Blob([JSON.stringify(loadTracking(), null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `art-search-tracking-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  });

  const importFile = document.getElementById("import-file");
  document.getElementById("import-btn").addEventListener("click", () => importFile.click());
  importFile.addEventListener("change", async () => {
    const file = importFile.files[0];
    if (!file) return;
    try {
      const data = JSON.parse(await file.text());
      saveTracking(data);
      listings = mergeTracking(listings.map(({ tracking, ...rest }) => rest));
      render();
    } catch (err) {
      alert(`Import failed: ${err.message}`);
    }
    importFile.value = "";
  });
}

function setupControls() {
  const ids = ["type-filter", "status-filter", "tracking-filter", "sort-order", "search-box"];
  for (const id of ids) {
    const el = document.getElementById(id);
    el.addEventListener("input", render);
    el.addEventListener("change", render);
  }
  document.querySelectorAll("#tier-filter input[type=checkbox]").forEach((cb) => {
    cb.addEventListener("change", render);
  });
}

async function init() {
  setupControls();
  setupExportImport();

  const [rawListings, meta] = await Promise.all([
    fetchJson("data/listings.json"),
    fetchJson("data/meta.json"),
  ]);

  listings = mergeTracking(rawListings);
  renderMetaBadge(meta);
  render();
}

init().catch((err) => {
  document.getElementById("meta-badge").textContent = `Failed to load data: ${err.message}`;
});
