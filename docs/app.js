const TRACKING_KEY = "art-search-tracking";
const TRACKING_STATUSES = ["none", "interested", "applied", "accepted", "rejected", "ignored"];

const TIER_OVERRIDES_KEY = "art-search-tier-overrides";
const TIER_LEVELS = ["top", "high", "medium", "low"];
const TIER_LABELS = { top: "Top", high: "High", medium: "Medium", low: "Low" };

const DISMISSED_KEY = "art-search-dismissed";

// Mirrors scraper/discipline_tags.py's DISCIPLINE_TAGS keys/labels — keep in sync
// if the tag set changes there. "untagged" is a UI-only sentinel, not a real tag.
const DISCIPLINE_TAGS = {
  new_media_art: "New Media Art",
  digital_art: "Digital Art",
  data_art: "Data Art",
  civic_tech: "Civic Tech",
  open_data: "Open Data",
  urban_data: "Urban Data",
  information_art: "Information Art",
};

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

// Per-listing tier override - changing one row never affects any other,
// even ones sharing the same country.
function tierOverrideKey(listing) {
  return listing.id;
}

function loadTierOverrides() {
  try {
    return JSON.parse(localStorage.getItem(TIER_OVERRIDES_KEY)) || {};
  } catch {
    return {};
  }
}

function saveTierOverrides(overrides) {
  localStorage.setItem(TIER_OVERRIDES_KEY, JSON.stringify(overrides));
}

function setTierOverride(key, tier) {
  const overrides = loadTierOverrides();
  overrides[key] = tier;
  saveTierOverrides(overrides);
}

function effectiveTier(listing) {
  const overrides = loadTierOverrides();
  return overrides[tierOverrideKey(listing)] || listing.region_tier;
}

function loadDismissed() {
  try {
    return new Set(JSON.parse(localStorage.getItem(DISMISSED_KEY)) || []);
  } catch {
    return new Set();
  }
}

function isDismissed(id) {
  return loadDismissed().has(id);
}

function setDismissed(id, dismissed) {
  const ids = loadDismissed();
  if (dismissed) ids.add(id);
  else ids.delete(id);
  localStorage.setItem(DISMISSED_KEY, JSON.stringify([...ids]));
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
      .map((cb) => cb.value)
  );
  const disciplineBoxes = document.querySelectorAll("#discipline-filter input[type=checkbox]");
  const disciplines = new Set(
    Array.from(disciplineBoxes)
      .filter((cb) => cb.checked)
      .map((cb) => cb.value)
  );
  return {
    tiers,
    disciplines,
    type: document.getElementById("type-filter").value,
    status: document.getElementById("status-filter").value,
    tracking: document.getElementById("tracking-filter").value,
    search: document.getElementById("search-box").value.trim().toLowerCase(),
    sort: document.getElementById("sort-order").value,
    showRemoved: document.getElementById("show-removed-filter").checked,
  };
}

function applyFilters(all, filters) {
  return all.filter((l) => {
    if (isDismissed(l.id) !== filters.showRemoved) return false;
    if (!filters.tiers.has(effectiveTier(l))) return false;
    if (filters.disciplines.size < Object.keys(DISCIPLINE_TAGS).length + 1) {
      const tags = l.discipline || [];
      const passes = tags.length
        ? tags.some((tag) => filters.disciplines.has(tag))
        : filters.disciplines.has("untagged");
      if (!passes) return false;
    }
    if (filters.type && l.listing_type !== filters.type) return false;
    if (filters.status && l.status !== filters.status) return false;
    if (filters.tracking && l.tracking.status !== filters.tracking) return false;
    if (filters.search) {
      const haystack = `${l.title} ${l.organizer} ${l.eligibility || ""}`.toLowerCase();
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
      const tierDiff = TIER_LEVELS.indexOf(effectiveTier(a)) - TIER_LEVELS.indexOf(effectiveTier(b));
      if (tierDiff !== 0) return tierDiff;
      return deadlineKey(a).localeCompare(deadlineKey(b));
    });
  }
  return sorted;
}

function renderDisciplineBadges(tags) {
  if (!tags || !tags.length) return '<span class="discipline-badge discipline-untagged">untagged</span>';
  return tags
    .map((tag) => `<span class="discipline-badge">${escapeHtml(DISCIPLINE_TAGS[tag] || tag)}</span>`)
    .join(" ");
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
    if (filters.showRemoved) row.classList.add("dismissed-row");

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
      <td><a href="${listing.url}" target="_blank" rel="noopener" title="${escapeHtml(listing.title)}">${escapeHtml(truncateWords(listing.title, 9))}</a></td>
      <td>${escapeHtml(listing.organizer || "")}</td>
      <td>${escapeHtml(listing.country || "—")}</td>
      <td class="tier-cell"></td>
      <td>${escapeHtml(listing.listing_type || "")}</td>
      <td>${renderDisciplineBadges(listing.discipline)}</td>
      <td class="${urgentClass}">${escapeHtml(deadlineCell)}</td>
      <td>${listing.fee != null ? escapeHtml(String(listing.fee)) : "—"}</td>
      <td>${escapeHtml(listing.prize_amount || "—")}</td>
      <td class="eligibility-cell" title="${escapeHtml(listing.eligibility || "")}">${escapeHtml(listing.eligibility || "—")}</td>
      <td class="tracking-cell"></td>
      <td class="remove-cell"></td>
    `;

    const tier = effectiveTier(listing);
    const tierCell = row.querySelector(".tier-cell");
    const tierSelect = document.createElement("select");
    tierSelect.className = `tier-select tier-${tier}`;
    tierSelect.title = "Sets the tier for this listing only";
    for (const level of TIER_LEVELS) {
      const opt = document.createElement("option");
      opt.value = level;
      opt.textContent = TIER_LABELS[level];
      if (level === tier) opt.selected = true;
      tierSelect.appendChild(opt);
    }
    tierSelect.addEventListener("change", () => {
      setTierOverride(tierOverrideKey(listing), tierSelect.value);
      render();
    });
    tierCell.appendChild(tierSelect);

    const trackingCell = row.querySelector(".tracking-cell");
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

    const removeCell = row.querySelector(".remove-cell");
    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "remove-btn";
    removeBtn.textContent = filters.showRemoved ? "Restore" : "Remove";
    removeBtn.addEventListener("click", () => {
      setDismissed(listing.id, !filters.showRemoved);
      render();
    });
    removeCell.appendChild(removeBtn);

    tbody.appendChild(row);
  }
}

function daysUntil(isoDate) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const deadline = new Date(isoDate);
  return Math.floor((deadline - today) / (1000 * 60 * 60 * 24));
}

function truncateWords(text, maxWords) {
  const words = (text || "").trim().split(/\s+/).filter(Boolean);
  if (words.length <= maxWords) return text || "";
  return `${words.slice(0, maxWords).join(" ")}…`;
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

  document.getElementById("reset-tiers-btn").addEventListener("click", () => {
    if (confirm("Clear all your custom nation/region tier settings? This can't be undone.")) {
      localStorage.removeItem(TIER_OVERRIDES_KEY);
      render();
    }
  });
}

function setupDisciplineFilter() {
  const container = document.getElementById("discipline-filter");
  const entries = [...Object.entries(DISCIPLINE_TAGS), ["untagged", "Untagged"]];
  for (const [value, label] of entries) {
    const wrapper = document.createElement("label");
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.value = value;
    cb.checked = true;
    wrapper.appendChild(cb);
    wrapper.append(` ${label}`);
    container.appendChild(wrapper);
  }
}

function setupControls() {
  const ids = ["type-filter", "status-filter", "tracking-filter", "sort-order", "search-box", "show-removed-filter"];
  for (const id of ids) {
    const el = document.getElementById(id);
    el.addEventListener("input", render);
    el.addEventListener("change", render);
  }
  document.querySelectorAll("#tier-filter input[type=checkbox]").forEach((cb) => {
    cb.addEventListener("change", render);
  });
  document.querySelectorAll("#discipline-filter input[type=checkbox]").forEach((cb) => {
    cb.addEventListener("change", render);
  });
}

async function init() {
  setupDisciplineFilter();
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
