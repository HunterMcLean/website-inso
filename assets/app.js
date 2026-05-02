/* Webstacks Inspiration Library — vanilla JS frontend */
(function(){
  const PAGE_SIZE = 12;
  const EDIT_PAGE_SIZE = 25; // browse pagination (unused in edit view)
  const state = {
    entries: [], schema: null,
    filters: {
      companySize: new Set(),
      companyType: new Set(),
      companyIndustry: new Set(),
      designAesthetic: new Set(),
      standoutElements: new Set(),  // values like "Components::Hero"
      wordAssociations: new Set(),
      flags: new Set(),
    },
    search: "",
    sort: "created-desc",
    page: 1,
    view: "browse",          // "browse" or "edit"
    dirty: new Set(),         // entry ids that have been edited this session
    detailId: null,           // currently-open detail modal entry id
    detailEditing: false,     // detail modal is in edit mode
    favorites: new Set(),     // entry ids saved to localStorage
    showFavorites: false,     // when true, grid shows only favorites
    customTags: {},           // { tagName: siteId[] } — persisted to localStorage
    activeCustomTags: new Set(), // tag names currently active as filters
    albums: [],               // [{id, name, siteIds:[], createdAt}] — persisted to localStorage
    activeAlbum: null,        // album id currently being viewed
    sharedAlbum: null,        // {name, ids} decoded from ?album= URL param (read-only)
    gridCols: 3,              // 3 or 2 — persisted to localStorage
    editShowUntagged: false,  // edit view: show only entries missing wordAssociations
  };

  // Industries get tiny SVG icons (Lucide-style) for the sidebar
  const INDUSTRY_ICONS = {
    "AI": '<path d="M5 8a2 2 0 0 1 2-2h0a2 2 0 0 1 2 2v3M5 11h4M11 6h2v5M11 11h2" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>',
    "ML": '<path d="M3 4v8M3 4l4 4M3 12l4-4M9 4v8M9 12l4-4M9 4l4 4" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>',
    "Blockchain/Web3": '<path d="M7 1l5 3v5l-5 3-5-3V4l5-3z" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/>',
    "FinTech": '<path d="M3 9V5h8v4M3 9l4 3 4-3M5 7h4" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>',
    "eCommerce": '<path d="M2 3h2l1 7h7M5 13a1 1 0 1 0 0-2 1 1 0 0 0 0 2zM11 13a1 1 0 1 0 0-2 1 1 0 0 0 0 2z" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>',
    "MarTech": '<path d="M2 7l7-4v8l-7-4zM4 7v3a1 1 0 0 0 1 1h1l1 2" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>',
    "Legal": '<path d="M7 2v9M3 4h8M3 4l1 4h2l1-4M11 4l-1 4h-2l-1-4M3 11h8" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>',
    "Energy/Infrastructure": '<path d="M7 1l-3 6h3l-1 6 4-7H7l1-5z" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/>',
    "Real Estate": '<path d="M2 6l5-4 5 4v6H2V6zM6 12V8h2v4" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/>',
    "Manufacturing": '<path d="M2 12h10M2 5l3 2V5l3 2V5l3 2v5H2V5z" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/>',
    "Restaurants/Hospitality/Tourism": '<path d="M3 2v6a2 2 0 0 0 4 0V2M5 2v10M11 2c-1 1-1 4-1 5h2c0 0 0-4-1-5zM10 7v5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>',
    "Logistics": '<path d="M1 4h7v6H1zM8 6h3l2 2v2h-5z" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/>',
    "Cybersecurity": '<path d="M7 1l5 2v4c0 3-2 5-5 6-3-1-5-3-5-6V3l5-2z" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/>',
    "Healthcare": '<path d="M5 1v4H1v4h4v4h4V9h4V5H9V1z" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/>',
    "Automotive/EV": '<path d="M2 9V7l1-3h8l1 3v2M3 9v2M11 9v2M3 9h8M4 9a1 1 0 1 1-2 0 1 1 0 0 1 2 0zM12 9a1 1 0 1 1-2 0 1 1 0 0 1 2 0z" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>',
    "HR Tech": '<path d="M5 4a2 2 0 1 1 4 0 2 2 0 0 1-4 0zM2 12c0-2 2-4 5-4s5 2 5 4" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>',
    "Entertainment": '<path d="M2 3h10v8H2zM2 5h10M5 8h4" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/>',
    "Activism": '<path d="M3 12V3l4 1 5-2v6l-5 2-4-1z" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/>',
    "Sales Tech": '<path d="M2 11l4-4 2 2 4-5M11 4h2v2" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>',
    "Dev Tools": '<path d="M5 4L2 7l3 3M9 4l3 3-3 3" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>',
    "Agency": '<path d="M2 6l5-4 5 4v6H2V6zM6 12V8h2v4M5 5h4" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/>',
  };
  const TYPE_ICONS = {
    "B2B": '<rect x="2" y="3" width="4" height="8" stroke="currentColor" stroke-width="1.2"/><rect x="8" y="5" width="4" height="6" stroke="currentColor" stroke-width="1.2"/>',
    "B2C": '<rect x="2" y="3" width="4" height="8" stroke="currentColor" stroke-width="1.2"/><circle cx="10" cy="7" r="2" stroke="currentColor" stroke-width="1.2"/>',
  };
  const FLAG_ICONS = {
    "industryLeader": '<path d="M7 1l1.7 3.5 3.8.6-2.8 2.7.7 3.8L7 9.8l-3.4 1.8.7-3.8L1.5 5.1l3.8-.6L7 1z" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/>',
    "unconventional": '<path d="M7 1l-3 7h3v5l3-7H7V1z" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/>',
    "webstacksClient": '<rect x="2" y="3" width="10" height="8" rx="1.5" stroke="currentColor" stroke-width="1.2"/><path d="M5 7h4M7 5v4" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>',
  };
  const SIZE_ICONS = {
    "Startup":    '<path d="M7 10V6M5 8l2-2 2 2M3 12l2-5M11 12l-2-5M3 12h8" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>',
    "MidMarket":  '<path d="M2 12V6l2-2h6l2 2v6M5 12V8h4v4" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/>',
    "Enterprise": '<path d="M1 12V5l3-3h6l3 3v7M4 12V8h6v4M6 5h2" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/>',
    "Agency":     '<path d="M3 12V5l4-3 4 3v7M6 12V9h2v3M5 5h4" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/><circle cx="7" cy="3.5" r="1" fill="currentColor"/>',
  };

  // ------- Boot -------
  function boot(data) {
    state.entries = data.entries;
    state.schema = data.schema;
    checkSharedAlbumUrl();
    initEditToken();
    loadFavorites();
    loadCustomTags();
    loadAlbums();
    loadGridCols();
    buildSidebar();
    buildFilterBar();
    attachEvents();
    paintCollage();
    applyEditAuthUI();
    updateHeroCopy();   // applies shared-album-mode class before first render
    render();
  }

  // ------- Favorites -------
  function loadFavorites() {
    try {
      const saved = localStorage.getItem("inspoFavorites");
      if (saved) {
        const ids = JSON.parse(saved);
        if (Array.isArray(ids)) state.favorites = new Set(ids);
      }
    } catch(e) {}
    updateFavoritesNav();
  }
  function saveFavorites() {
    try { localStorage.setItem("inspoFavorites", JSON.stringify(Array.from(state.favorites))); }
    catch(e) {}
  }
  function toggleFavorite(id) {
    if (state.favorites.has(id)) state.favorites.delete(id);
    else state.favorites.add(id);
    saveFavorites();
    updateFavoritesNav();
    if (state.showFavorites) { render(); return; }
    // Update heart buttons in place without full re-render
    const on = state.favorites.has(id);
    document.querySelectorAll(`.card-fav-btn[data-fav-id="${cssEscape(id)}"]`).forEach(btn => {
      btn.classList.toggle("active", on);
      btn.setAttribute("aria-label", on ? "Remove from favorites" : "Add to favorites");
    });
    document.querySelectorAll(`.detail-fav-btn[data-fav-id="${cssEscape(id)}"]`).forEach(btn => {
      btn.classList.toggle("active", on);
      btn.textContent = on ? "♥ Favorited" : "♡ Favorite";
    });
  }
  function updateFavoritesNav() {
    const badge = document.getElementById("fav-count");
    if (badge) badge.textContent = state.favorites.size;
    badge && badge.classList.toggle("has-count", state.favorites.size > 0);
  }
  function setShowFavorites(val) {
    state.showFavorites = val;
    state.activeAlbum = null;
    state.page = 1;
    if (!val) state.activeCustomTags.clear();
    document.getElementById("nav-home").classList.toggle("active", !val);
    document.getElementById("nav-favorites").classList.toggle("active", val);
    renderAlbumsNav();
    updateHeroCopy();
    updateCustomTagsDropdown();
    render();
  }

  function setActiveAlbum(albumId) {
    state.activeAlbum = albumId;
    state.showFavorites = false;
    state.activeCustomTags.clear();
    state.page = 1;
    document.getElementById("nav-home").classList.toggle("active", !albumId);
    document.getElementById("nav-favorites").classList.remove("active");
    renderAlbumsNav();
    updateHeroCopy();
    updateCustomTagsDropdown();
    render();
  }

  function updateHeroCopy() {
    const h1      = document.getElementById("hero-headline");
    const sub     = document.getElementById("hero-sub");
    const caution = document.getElementById("hero-caution");
    const shareBtn = document.getElementById("share-album-btn");
    const banner  = document.getElementById("shared-album-banner");
    // Hide sidebar + filter bar when viewing a shared album URL
    document.body.classList.toggle("shared-album-mode", !!state.sharedAlbum);
    if (state.sharedAlbum) {
      h1.textContent  = state.sharedAlbum.name;
      sub.textContent = `Shared album · ${state.sharedAlbum.ids.length} site${state.sharedAlbum.ids.length !== 1 ? "s" : ""}`;
      caution.hidden = true; shareBtn.hidden = true; banner.hidden = false;
    } else if (state.activeAlbum) {
      const album = state.albums.find(a => a.id === state.activeAlbum);
      const n = album ? album.siteIds.length : 0;
      h1.textContent  = album ? album.name : "Album";
      sub.textContent = `${n} site${n !== 1 ? "s" : ""} in this collection.`;
      caution.hidden = true; banner.hidden = true;
      shareBtn.hidden = false;
      shareBtn.dataset.albumId = state.activeAlbum;
    } else if (state.showFavorites) {
      h1.textContent  = "Your favorited websites.";
      sub.textContent = "All of your saved sites, in one place. Add custom tags and sort by your own filters.";
      caution.hidden = false; shareBtn.hidden = true; banner.hidden = true;
    } else {
      h1.textContent  = "Webstacks’ very own website inspiration library.";
      sub.textContent = "Find web inspo for whatever you’re working on. Filter by overall style, individual design system elements, or even word association terms.";
      caution.hidden = true; shareBtn.hidden = true; banner.hidden = true;
    }
  }

  // ------- Custom Tags -------
  function loadCustomTags() {
    try {
      const raw = localStorage.getItem("inspoCustomTags");
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed === "object" && !Array.isArray(parsed))
          state.customTags = parsed;
      }
    } catch(e) {}
  }
  function saveCustomTags() {
    try { localStorage.setItem("inspoCustomTags", JSON.stringify(state.customTags)); }
    catch(e) {}
  }
  function getTagsForSite(siteId) {
    return Object.keys(state.customTags).filter(t => (state.customTags[t] || []).includes(siteId));
  }
  function getAllTagNames() {
    return Object.keys(state.customTags).sort((a, b) => a.localeCompare(b));
  }
  function addSiteToTag(tagName, siteId) {
    const name = tagName.trim();
    if (!name || !siteId) return;
    if (!state.customTags[name]) state.customTags[name] = [];
    if (!state.customTags[name].includes(siteId)) state.customTags[name].push(siteId);
    saveCustomTags();
    updateCustomTagsDropdown();
  }
  function removeSiteFromTag(tagName, siteId) {
    if (!state.customTags[tagName]) return;
    state.customTags[tagName] = state.customTags[tagName].filter(id => id !== siteId);
    if (state.customTags[tagName].length === 0) {
      delete state.customTags[tagName];
      state.activeCustomTags.delete(tagName);
    }
    saveCustomTags();
    updateCustomTagsDropdown();
  }
  function toggleCustomTagFilter(tagName) {
    if (state.activeCustomTags.has(tagName)) state.activeCustomTags.delete(tagName);
    else state.activeCustomTags.add(tagName);
    state.page = 1;
    updateCustomTagsDropdown();
    render();
  }
  function updateCustomTagsDropdown() {
    const drop = document.getElementById("filter-custom-tags");
    if (!drop) return;
    const tagNames = getAllTagNames();
    drop.hidden = tagNames.length === 0 || !state.showFavorites;
    if (drop.hidden) drop.open = false;
    const opts = drop.querySelector(".drop-options");
    if (!opts) return;
    opts.innerHTML = "";
    tagNames.forEach(tag => {
      const count = (state.customTags[tag] || []).length;
      const active = state.activeCustomTags.has(tag);
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "filter-chip";
      btn.setAttribute("aria-pressed", active ? "true" : "false");
      btn.innerHTML = `${escapeHtml(tag)}<span class="count">${count}</span>`;
      btn.addEventListener("click", e => { e.stopPropagation(); toggleCustomTagFilter(tag); });
      opts.appendChild(btn);
    });
  }
  function renderCustomTagSectionHtml(siteId) {
    const tags = getTagsForSite(siteId);
    const chips = tags.map(t =>
      `<span class="custom-tag-chip">${escapeHtml(t)}<button type="button" class="custom-tag-remove" data-tag="${escapeHtml(t)}" aria-label="Remove tag ${escapeHtml(t)}">×</button></span>`
    ).join("");
    const suggestions = getAllTagNames().filter(t => !tags.includes(t))
      .map(t => `<option value="${escapeHtml(t)}">`).join("");
    return `
      <div class="detail-section custom-tags-section">
        <h4>My Tags</h4>
        <div class="custom-tag-chips">${chips || '<span class="custom-tag-empty">No tags yet</span>'}</div>
        <div class="custom-tag-input-row">
          <input type="text" class="custom-tag-input" list="ct-dl-${escapeHtml(siteId)}" placeholder="Add a tag…" autocomplete="off" />
          <datalist id="ct-dl-${escapeHtml(siteId)}">${suggestions}</datalist>
          <button type="button" class="custom-tag-add-btn">Add</button>
        </div>
      </div>`;
  }
  function wireCustomTagSection(scope, siteId) {
    function refreshChips() {
      const tags = getTagsForSite(siteId);
      const container = scope.querySelector(".custom-tag-chips");
      if (!container) return;
      container.innerHTML = tags.length
        ? tags.map(t =>
            `<span class="custom-tag-chip">${escapeHtml(t)}<button type="button" class="custom-tag-remove" data-tag="${escapeHtml(t)}" aria-label="Remove tag ${escapeHtml(t)}">×</button></span>`
          ).join("")
        : '<span class="custom-tag-empty">No tags yet</span>';
      container.querySelectorAll(".custom-tag-remove").forEach(btn => {
        btn.addEventListener("click", e => {
          e.stopPropagation();
          removeSiteFromTag(btn.dataset.tag, siteId);
          refreshChips(); refreshSuggestions();
        });
      });
    }
    function refreshSuggestions() {
      const dl = scope.querySelector(`datalist[id^="ct-dl"]`);
      if (!dl) return;
      const current = getTagsForSite(siteId);
      dl.innerHTML = getAllTagNames().filter(t => !current.includes(t))
        .map(t => `<option value="${escapeHtml(t)}">`).join("");
    }
    // Wire initial removes
    scope.querySelectorAll(".custom-tag-remove").forEach(btn => {
      btn.addEventListener("click", e => {
        e.stopPropagation();
        removeSiteFromTag(btn.dataset.tag, siteId);
        refreshChips(); refreshSuggestions();
      });
    });
    const input = scope.querySelector(".custom-tag-input");
    const addBtn = scope.querySelector(".custom-tag-add-btn");
    function doAdd() {
      const val = input ? input.value.trim() : "";
      if (!val) return;
      addSiteToTag(val, siteId);
      if (input) input.value = "";
      refreshChips(); refreshSuggestions();
    }
    if (addBtn) addBtn.addEventListener("click", doAdd);
    if (input) input.addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); doAdd(); } });
  }

  // ------- Edit auth (token in URL → localStorage) -------
  function initEditToken() {
    try {
      const url = new URL(location.href);
      const fromUrl = url.searchParams.get("edit");
      if (fromUrl) {
        if (fromUrl === "off" || fromUrl === "logout") {
          localStorage.removeItem("inspoEditToken");
        } else {
          localStorage.setItem("inspoEditToken", fromUrl);
        }
        url.searchParams.delete("edit");
        history.replaceState({}, "", url.pathname + (url.search || "") + url.hash);
      }
    } catch (e) { /* localStorage may be unavailable */ }
  }
  function getEditToken() {
    try { return localStorage.getItem("inspoEditToken") || ""; }
    catch (e) { return ""; }
  }
  function applyEditAuthUI() {
    const allowed = !!getEditToken();
    document.body.classList.toggle("edit-allowed", allowed);
    const tg = document.querySelector(".view-toggle");
    if (tg) tg.style.display = allowed ? "" : "none";
    if (!allowed && state.view === "edit") setView("browse");
    const lockBtn = document.getElementById("edit-token-btn");
    if (lockBtn) lockBtn.classList.toggle("unlocked", allowed);
  }

  document.getElementById("edit-token-btn").addEventListener("click", () => {
    const current = getEditToken();
    if (current) {
      // Already unlocked — offer to lock
      if (confirm("Edit mode is active. Click OK to sign out of edit mode.")) {
        try { localStorage.removeItem("inspoEditToken"); } catch(e) {}
        applyEditAuthUI();
      }
    } else {
      const token = prompt("Enter edit token:");
      if (!token || !token.trim()) return;
      const trimmed = token.trim();
      // Verify token against the function before unlocking
      fetch("/.netlify/functions/save-inspiration", {
        method: "GET",
        headers: { "X-Edit-Token": trimmed },
      })
        .then(r => r.json().then(d => ({ ok: r.ok, data: d })).catch(() => ({ ok: false, data: {} })))
        .then(({ ok }) => {
          if (ok) {
            try { localStorage.setItem("inspoEditToken", trimmed); } catch(e) {}
            applyEditAuthUI();
          } else {
            alert("Incorrect token — edit mode not unlocked.");
          }
        })
        .catch(() => {
          // Offline / function unreachable — store anyway, will fail at save time
          try { localStorage.setItem("inspoEditToken", trimmed); } catch(e) {}
          applyEditAuthUI();
        });
    }
  });
  // Prefer inline data (works under file://). Fall back to fetch when served over http(s).
  if (window.INSPIRATION_DATA) {
    boot(window.INSPIRATION_DATA);
  } else {
    fetch("data/inspiration.json", { cache: "no-store" })
      .then(r => r.json())
      .then(boot)
      .catch(err => {
        document.querySelector(".main").innerHTML = `<p style="padding:40px;color:#f08080">Could not load data/inspiration.json: ${err.message}</p>`;
      });
  }

  // ------- Grid density -------
  function loadGridCols() {
    try {
      const v = localStorage.getItem("inspoGridCols");
      if (v === "2" || v === "3") state.gridCols = parseInt(v, 10);
    } catch(e) {}
    applyGridCols();
  }
  function applyGridCols() {
    document.getElementById("grid").classList.toggle("grid-cols-2", state.gridCols === 2);
    document.querySelectorAll(".grid-density-btn").forEach(b => {
      b.classList.toggle("active", parseInt(b.dataset.cols, 10) === state.gridCols);
    });
  }

  // ------- Albums -------
  function loadAlbums() {
    try {
      const raw = localStorage.getItem("inspoAlbums");
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) state.albums = parsed;
      }
    } catch(e) {}
    renderAlbumsNav();
  }
  function saveAlbums() {
    try { localStorage.setItem("inspoAlbums", JSON.stringify(state.albums)); } catch(e) {}
  }
  function genAlbumId() { return "alb_" + Date.now().toString(36) + Math.random().toString(36).slice(2, 5); }

  function createAlbum(name) {
    name = name.trim();
    if (!name) return null;
    const album = { id: genAlbumId(), name, siteIds: [], createdAt: new Date().toISOString() };
    state.albums.push(album);
    saveAlbums();
    renderAlbumsNav();
    return album;
  }
  function deleteAlbum(id) {
    state.albums = state.albums.filter(a => a.id !== id);
    if (state.activeAlbum === id) { state.activeAlbum = null; updateHeroCopy(); }
    saveAlbums();
    renderAlbumsNav();
    render();
  }
  function addSiteToAlbum(albumId, siteId) {
    const album = state.albums.find(a => a.id === albumId);
    if (!album || album.siteIds.includes(siteId)) return;
    album.siteIds.push(siteId);
    saveAlbums();
    renderAlbumsNav();
  }
  function removeSiteFromAlbum(albumId, siteId) {
    const album = state.albums.find(a => a.id === albumId);
    if (!album) return;
    album.siteIds = album.siteIds.filter(id => id !== siteId);
    saveAlbums();
    renderAlbumsNav();
  }

  function renderAlbumsNav() {
    const list = document.getElementById("album-list");
    if (!list) return;
    list.innerHTML = "";
    state.albums.forEach(album => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "side-link album-nav-item" + (state.activeAlbum === album.id ? " active" : "");
      btn.innerHTML = `
        <span class="ico"><svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M1 4.5C1 3.67 1.67 3 2.5 3h3l1.5 1.5H11.5c.83 0 1.5.67 1.5 1.5V10.5c0 .83-.67 1.5-1.5 1.5h-9C1.67 12 1 11.33 1 10.5V4.5z" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/></svg></span>
        <span class="lbl">${escapeHtml(album.name)}</span>
        <span class="count">${album.siteIds.length}</span>
        <button type="button" class="album-delete-btn" data-album-id="${escapeHtml(album.id)}" aria-label="Delete album" title="Delete album">
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M2 2l6 6M8 2L2 8" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg>
        </button>
      `;
      btn.addEventListener("click", e => {
        if (e.target.closest(".album-delete-btn")) {
          e.stopPropagation();
          if (confirm(`Delete album "${album.name}"?`)) deleteAlbum(album.id);
          return;
        }
        setActiveAlbum(album.id);
      });
      list.appendChild(btn);
    });
  }

  function generateShareUrl(album) {
    const payload = JSON.stringify({ n: album.name, i: album.siteIds });
    const b64 = btoa(unescape(encodeURIComponent(payload)));
    return location.origin + location.pathname + "?album=" + encodeURIComponent(b64);
  }

  function checkSharedAlbumUrl() {
    try {
      const raw = new URLSearchParams(location.search).get("album");
      if (!raw) return;
      const payload = JSON.parse(decodeURIComponent(escape(atob(decodeURIComponent(raw)))));
      if (payload.n && Array.isArray(payload.i)) {
        state.sharedAlbum = { name: payload.n, ids: payload.i };
      }
    } catch(e) {}
  }

  function renderAlbumAddSectionHtml(siteId) {
    if (!state.albums.length) return "";
    const rows = state.albums.map(album => {
      const checked = album.siteIds.includes(siteId) ? " checked" : "";
      return `<label class="album-check-item">
        <input type="checkbox" class="album-check-input" data-album-id="${escapeHtml(album.id)}"${checked}/>
        <span class="album-check-name">${escapeHtml(album.name)}</span>
        <span class="album-check-count" data-album-id="${escapeHtml(album.id)}">${album.siteIds.length}</span>
      </label>`;
    }).join("");
    return `<div class="album-add-section">
      <div class="album-add-title">
        <svg width="12" height="12" viewBox="0 0 14 14" fill="none"><path d="M1 4.5C1 3.67 1.67 3 2.5 3h3l1.5 1.5H11.5c.83 0 1.5.67 1.5 1.5V10.5c0 .83-.67 1.5-1.5 1.5h-9C1.67 12 1 11.33 1 10.5V4.5z" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/></svg>
        Add to Album
      </div>
      <div class="album-check-list">${rows}</div>
    </div>`;
  }

  function wireAlbumAddSection(scope, siteId) {
    scope.querySelectorAll(".album-check-input").forEach(cb => {
      cb.addEventListener("change", () => {
        const albumId = cb.dataset.albumId;
        if (cb.checked) addSiteToAlbum(albumId, siteId);
        else removeSiteFromAlbum(albumId, siteId);
        // Update count badge next to album name
        const album = state.albums.find(a => a.id === albumId);
        scope.querySelectorAll(`.album-check-count[data-album-id="${cssEscape(albumId)}"]`).forEach(el => {
          if (album) el.textContent = album.siteIds.length;
        });
        // Also update hero sub if we're viewing this album
        if (state.activeAlbum === albumId) updateHeroCopy();
      });
    });
  }

  // ------- Sidebar (Type / Industry / Flags) -------
  function buildSidebar() {
    const typeEl = document.getElementById("filter-type");
    state.schema.companyType.forEach(v => {
      typeEl.appendChild(makeSideOption("companyType", v, v, countTag("companyType", v), TYPE_ICONS[v] || ""));
    });

    const industryEl = document.getElementById("filter-industry");
    state.schema.companyIndustry.forEach(v => {
      industryEl.appendChild(makeSideOption("companyIndustry", v, v, countTag("companyIndustry", v), INDUSTRY_ICONS[v] || defaultIcon()));
    });

    const sizeEl = document.getElementById("filter-company-size");
    state.schema.companySize.forEach(v => {
      sizeEl.appendChild(makeSideOption("companySize", v, v, countTag("companySize", v), SIZE_ICONS[v] || defaultIcon()));
    });

    const flagsEl = document.getElementById("filter-flags");
    flagsEl.appendChild(makeSideOption("flags", "industryLeader", "Industry Leader", state.entries.filter(e => e.industryLeader).length, FLAG_ICONS.industryLeader));
    flagsEl.appendChild(makeSideOption("flags", "unconventional", "Unconventional", state.entries.filter(e => e.unconventional).length, FLAG_ICONS.unconventional));
    flagsEl.appendChild(makeSideOption("flags", "webstacksClient", "Webstacks Client", state.entries.filter(e => e.webstacksClient).length, FLAG_ICONS.webstacksClient));
  }
  function defaultIcon(){ return '<circle cx="7" cy="7" r="2.5" stroke="currentColor" stroke-width="1.2"/>'; }

  function makeSideOption(category, value, label, count, iconSvg, isExtra=false) {
    const b = document.createElement("button");
    b.type = "button"; b.className = "side-option" + (isExtra ? " is-extra" : "");
    b.setAttribute("data-cat", category);
    b.setAttribute("data-val", value);
    b.setAttribute("aria-pressed", "false");
    b.innerHTML = `
      <span class="ico"><svg width="14" height="14" viewBox="0 0 14 14" fill="none">${iconSvg}</svg></span>
      <span class="lbl">${escapeHtml(label)}</span>
      <span class="count">${count}</span>
    `;
    b.addEventListener("click", () => toggleFilter(category, value, b));
    return b;
  }

  // ------- Filter bar (Site Structure / Standout / Aesthetic / Word) -------
  function buildFilterBar() {
    document.querySelectorAll(".filter-drop").forEach(drop => {
      const cat = drop.dataset.cat;
      // My Tags dropdown: content is managed by updateCustomTagsDropdown(); just wire open/close here
      if (cat === "customTags") {
        drop.addEventListener("toggle", () => {
          if (drop.open) document.querySelectorAll(".filter-drop").forEach(d => { if (d !== drop) d.open = false; });
        });
        document.addEventListener("click", e => { if (drop.open && !drop.contains(e.target)) drop.open = false; });
        return;
      }
      const opts = drop.querySelector(".drop-options");
      if (cat === "standoutElements") {
        const groups = state.schema.standoutElements;
        Object.entries(groups).forEach(([sub, list]) => {
          const t = document.createElement("div"); t.className = "filter-subgroup-title"; t.textContent = sub;
          opts.appendChild(t);
          const grid = document.createElement("div"); grid.className = "subgroup-chips";
          list.forEach(o => grid.appendChild(makeChip("standoutElements", `${sub}::${o}`, o, countStandout(sub, o))));
          opts.appendChild(grid);
        });
      } else {
        state.schema[cat].forEach(o => opts.appendChild(makeChip(cat, o, o, countTag(cat, o))));
      }
      // Keep dropdowns open behavior — close others when one opens
      drop.addEventListener("toggle", () => {
        if (drop.open) document.querySelectorAll(".filter-drop").forEach(d => { if (d !== drop) d.open = false; });
      });
      // Click outside to close
      document.addEventListener("click", e => {
        if (drop.open && !drop.contains(e.target)) drop.open = false;
      });
    });
  }
  function makeChip(category, value, label, count, isExtra=false) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "filter-chip" + (isExtra ? " flag-extra" : "");
    b.setAttribute("data-cat", category);
    b.setAttribute("data-val", value);
    b.setAttribute("aria-pressed", "false");
    b.innerHTML = `${escapeHtml(label)}<span class="count">${count}</span>`;
    b.addEventListener("click", e => { e.stopPropagation(); toggleFilter(category, value, b); });
    return b;
  }

  // ------- Counters -------
  function countTag(cat, val) {
    return state.entries.filter(e => {
      const a = e[cat];
      return Array.isArray(a) && a.includes(val);
    }).length;
  }
  function countStandout(sub, opt) {
    return state.entries.filter(e => (e.standoutElements?.[sub] || []).includes(opt)).length;
  }

  // ------- Filter / sort logic -------
  function toggleFilter(cat, val, btn) {
    const set = state.filters[cat];
    if (set.has(val)) set.delete(val); else set.add(val);
    state.page = 1;
    if (btn) btn.setAttribute("aria-pressed", set.has(val) ? "true" : "false");
    // Sync alternate UI for same category (sidebar ↔ dropdown)
    document.querySelectorAll(`[data-cat="${cssEscape(cat)}"][data-val="${cssEscape(val)}"]`).forEach(el => {
      el.setAttribute("aria-pressed", set.has(val) ? "true" : "false");
    });
    render();
  }

  function entryMatches(e) {
    // Shared album view: only show those entries, skip all other filters
    if (state.sharedAlbum) return state.sharedAlbum.ids.includes(e.id);

    const f = state.filters;
    function hasAny(cat, getter) {
      if (f[cat].size === 0) return true;
      const ev = getter(e);
      for (const v of f[cat]) if (ev.includes(v)) return true;
      return false;
    }
    if (state.showFavorites && !state.favorites.has(e.id)) return false;
    if (state.activeAlbum) {
      const album = state.albums.find(a => a.id === state.activeAlbum);
      if (!album || !album.siteIds.includes(e.id)) return false;
    }
    if (!hasAny("companySize", x => x.companySize || [])) return false;
    if (!hasAny("companyType", x => x.companyType || [])) return false;
    if (!hasAny("companyIndustry", x => x.companyIndustry || [])) return false;
    if (!hasAny("designAesthetic", x => x.designAesthetic || [])) return false;
    if (!hasAny("wordAssociations", x => x.wordAssociations || [])) return false;
    if (f.standoutElements.size) {
      let any = false;
      for (const v of f.standoutElements) {
        const [sub, opt] = v.split("::");
        if ((e.standoutElements?.[sub] || []).includes(opt)) { any = true; break; }
      }
      if (!any) return false;
    }
    if (f.flags.size) {
      let any = false;
      if (f.flags.has("industryLeader") && e.industryLeader) any = true;
      if (f.flags.has("unconventional") && e.unconventional) any = true;
      if (f.flags.has("webstacksClient") && e.webstacksClient) any = true;
      if (!any) return false;
    }
    if (state.activeCustomTags.size) {
      const siteTags = getTagsForSite(e.id);
      if (!siteTags.some(t => state.activeCustomTags.has(t))) return false;
    }
    if (state.search) {
      const q = state.search.toLowerCase();
      const hay = [e.name, e.domain, e.url, ...(e.typefaces||[])].join(" ").toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  }
  function sorted(arr) {
    const a = arr.slice();
    switch (state.sort) {
      case "name-asc":  a.sort((x,y) => x.name.localeCompare(y.name)); break;
      case "name-desc": a.sort((x,y) => y.name.localeCompare(x.name)); break;
      case "created-asc":  a.sort((x,y) => parseDate(x.createdAt) - parseDate(y.createdAt)); break;
      case "created-desc": a.sort((x,y) => parseDate(y.createdAt) - parseDate(x.createdAt)); break;
    }
    return a;
  }
  function parseDate(s){ if(!s) return 0; const d = Date.parse(s); return isFinite(d) ? d : 0; }

  // ------- Render -------
  const EDIT_TABLE_PAGE_SIZE = 75;

  function render() {
    const grid      = document.getElementById("grid");
    const tableWrap = document.getElementById("edit-table-wrap");

    const all = sorted(state.entries.filter(entryMatches));
    document.getElementById("count").textContent = `${all.length} of ${state.entries.length} sites`;

    if (state.view === "edit") {
      const totalPages = Math.max(1, Math.ceil(all.length / EDIT_TABLE_PAGE_SIZE));
      if (state.page > totalPages) state.page = totalPages;
      grid.hidden = true;
      tableWrap.hidden = false;
      renderEditTable(all);
      renderPagination(0, 0); // edit table has its own inline pagination
    } else {
      tableWrap.hidden = true;
      grid.hidden = false;
      const totalPages = Math.max(1, Math.ceil(all.length / PAGE_SIZE));
      if (state.page > totalPages) state.page = totalPages;
      const paged = all.slice((state.page - 1) * PAGE_SIZE, state.page * PAGE_SIZE);
      grid.innerHTML = paged.map(renderCard).join("");
      grid.querySelectorAll(".card").forEach(c => c.addEventListener("click", () => openDetail(c.dataset.id)));
      grid.querySelectorAll(".card-fav-btn").forEach(btn => btn.addEventListener("click", e => {
        e.stopPropagation();
        toggleFavorite(btn.dataset.favId);
      }));
      grid.querySelectorAll(".card-visit-btn").forEach(a => a.addEventListener("click", e => {
        e.stopPropagation();
      }));
      renderPagination(state.page, totalPages);
    }

    const emptyEl = document.getElementById("empty");
    emptyEl.classList.toggle("hidden", all.length > 0);
    if (all.length === 0 && state.showFavorites) {
      emptyEl.innerHTML = `<p>No favorites yet. Click the ♥ on any site to save it here.</p>`;
    } else if (all.length === 0) {
      emptyEl.innerHTML = `<p>No sites match these filters.</p><button class="link-btn" type="button" onclick="window.WebInspo.resetFilters()">Reset filters</button>`;
    }
    renderActiveChips();
  }

  // ------- Edit table -------
  function renderEditTable(allFiltered) {
    const wrap = document.getElementById("edit-table-wrap");

    // Untagged filter applied on top of whatever browse filters are already active
    const untaggedCount = allFiltered.filter(e => !(e.wordAssociations || []).length).length;
    const visible = state.editShowUntagged
      ? allFiltered.filter(e => !(e.wordAssociations || []).length)
      : allFiltered;

    const total = Math.max(1, Math.ceil(visible.length / EDIT_TABLE_PAGE_SIZE));
    if (state.page > total) state.page = total;
    const paged = visible.slice((state.page - 1) * EDIT_TABLE_PAGE_SIZE, state.page * EDIT_TABLE_PAGE_SIZE);

    // Rebuild the whole wrap each render so controls stay in sync
    wrap.innerHTML = `
      <div class="et-controls">
        <span class="et-stats">${visible.length} site${visible.length !== 1 ? "s" : ""}&thinsp;·&thinsp;<span class="et-untagged-count">${untaggedCount} untagged</span></span>
        <button type="button" id="et-untagged-toggle" class="et-filter-btn${state.editShowUntagged ? " active" : ""}">
          ${state.editShowUntagged ? "Show all" : "Untagged only"}
        </button>
      </div>
      <table class="et-table">
        <thead><tr>
          <th class="etc-site">Site</th>
          <th class="etc-words">Word Associations</th>
          <th class="etc-industry">Industry</th>
          <th class="etc-more"></th>
        </tr></thead>
        <tbody>${paged.map(renderEditRow).join("")}</tbody>
      </table>
      <div class="et-pagination"></div>
    `;

    // Wire all rows
    wrap.querySelectorAll("tr.edit-row").forEach(tr => {
      const id = tr.dataset.id;
      const entry = state.entries.find(e => e.id === id);
      if (!entry) return;
      attachChipGroupEvents(tr, entry, "wordAssociations", state.schema.wordAssociations);
      attachChipGroupEvents(tr, entry, "companyIndustry", state.schema.companyIndustry);
      const more = tr.querySelector(".row-more");
      if (more) more.addEventListener("click", () => openDetail(id, { edit: true }));
    });

    // Thumbnail click → enlarge popup
    wrap.querySelectorAll(".et-thumb img").forEach(img => {
      img.style.cursor = "zoom-in";
      img.addEventListener("click", () => openThumbPopup(img.src));
    });

    // Untagged toggle
    wrap.querySelector("#et-untagged-toggle").addEventListener("click", () => {
      state.editShowUntagged = !state.editShowUntagged;
      state.page = 1;
      render();
    });

    // Inline pagination
    const pgEl = wrap.querySelector(".et-pagination");
    if (total > 1) {
      const prev = state.page > 1;
      const next = state.page < total;
      pgEl.innerHTML = `
        <button class="pg-btn${prev ? "" : " disabled"}" data-tpg="${state.page - 1}"${prev ? "" : " disabled"}>‹</button>
        <span class="pg-info">Page ${state.page} of ${total}</span>
        <button class="pg-btn${next ? "" : " disabled"}" data-tpg="${state.page + 1}"${next ? "" : " disabled"}>›</button>
      `;
      pgEl.querySelectorAll("[data-tpg]").forEach(b => b.addEventListener("click", () => {
        state.page = parseInt(b.dataset.tpg, 10);
        wrap.scrollIntoView({ behavior: "smooth" });
        render();
      }));
    }
  }

  function renderEditRow(e) {
    const hasWords = (e.wordAssociations || []).length > 0;
    const dirtyClass = state.dirty.has(e.id) ? " is-dirty" : "";
    const untaggedClass = hasWords ? "" : " et-row-untagged";
    const thumb = e.screenshot
      ? `<img src="${escapeHtml(e.screenshot)}" alt="" loading="lazy"/>`
      : `<div class="et-thumb-empty"></div>`;
    return `
      <tr class="edit-row${dirtyClass}${untaggedClass}" data-id="${escapeHtml(e.id)}">
        <td class="etc-site">
          <div class="et-site-cell">
            <div class="et-thumb">${thumb}</div>
            <span class="et-site-name">${escapeHtml(e.name)}</span>
          </div>
        </td>
        <td class="etc-words">${renderChipGroup(e, "wordAssociations")}</td>
        <td class="etc-industry">${renderChipGroup(e, "companyIndustry")}</td>
        <td class="etc-more">
          <button type="button" class="row-more" title="Edit all fields">⋯</button>
        </td>
      </tr>`;
  }

  function renderChipGroup(entry, field) {
    const vals = entry[field] || [];
    const chips = vals.map(v =>
      `<span class="chip-edit" data-val="${escapeHtml(v)}">${escapeHtml(v)}<button type="button" class="chip-edit-remove" data-remove="${escapeHtml(v)}" aria-label="Remove ${escapeHtml(v)}">×</button></span>`
    ).join("");
    const empty = !vals.length ? `<span class="chip-empty">none</span>` : "";
    return `<div class="chip-edit-group" data-field="${escapeHtml(field)}">
      ${chips}${empty}
      <button type="button" class="chip-add" data-add>+ Add</button>
    </div>`;
  }

  function attachChipGroupEvents(scope, entry, field, options, opts={}) {
    const grp = scope.querySelector(`.chip-edit-group[data-field="${cssEscape(field)}"]`);
    if (!grp) return;
    wireChipRemoves(grp, () => {
      // remove handler reads the just-clicked button's value
    }, val => {
      entry[field] = (entry[field] || []).filter(x => x !== val);
      markDirty(entry.id);
      updateChipsInGroup(grp, entry[field] || []);
      markRowDirty(scope);
    });
    const addBtn = grp.querySelector(".chip-add");
    if (addBtn) {
      addBtn.addEventListener("click", e => {
        e.stopPropagation();
        openPopover(addBtn, options,
          () => entry[field] || [],
          (newVals) => {
            entry[field] = newVals;
            markDirty(entry.id);
            updateChipsInGroup(grp, newVals);
            markRowDirty(scope);
          }
        );
      });
    }
  }

  // Update only the chip elements inside a group; leave the +Add button DOM node stable
  function updateChipsInGroup(grp, vals) {
    grp.querySelectorAll(".chip-edit, .chip-empty").forEach(el => el.remove());
    const addBtn = grp.querySelector(".chip-add");
    if (!vals.length) {
      const empty = document.createElement("span");
      empty.className = "chip-empty";
      empty.textContent = "none";
      grp.insertBefore(empty, addBtn);
      return;
    }
    vals.forEach(v => {
      const chip = document.createElement("span");
      chip.className = "chip-edit";
      chip.dataset.val = v;
      chip.innerHTML = `${escapeHtml(v)}<button type="button" class="chip-edit-remove" data-remove="${escapeHtml(v)}" aria-label="Remove ${escapeHtml(v)}">×</button>`;
      grp.insertBefore(chip, addBtn);
    });
    // Re-wire remove handlers — they were destroyed when we cleared chips
    wireChipRemoves(grp, null, val => {
      const ev = new CustomEvent("chip-remove", { detail: val, bubbles: true });
      grp.dispatchEvent(ev);
    });
  }

  function wireChipRemoves(grp, _unused, onRemove) {
    grp.querySelectorAll(".chip-edit-remove").forEach(btn => {
      btn.onclick = e => {
        e.stopPropagation();
        onRemove(btn.dataset.remove);
      };
    });
  }

  function markRowDirty(scope) {
    const row = scope.closest && scope.closest("tr.edit-row");
    if (row) row.classList.add("is-dirty");
  }

  // ------- Popover (chip add) -------
  // Now takes getValues + setValues callbacks so it stays in sync if the
  // entry's array is mutated externally (e.g. user clicks a chip × while
  // the popover is open).
  function openPopover(anchor, options, getValues, setValues) {
    closePopover();

    // Render inside the active <dialog> if one is open — otherwise the
    // popover renders below the dialog's top-layer backdrop and can't be
    // clicked. Falls back to popover-root for the main page.
    const openDlg = document.querySelector("dialog[open]");
    const host = openDlg || document.getElementById("popover-root");
    if (host.id === "popover-root") host.hidden = false;

    const pop = document.createElement("div");
    pop.className = "popover";
    pop.innerHTML = `
      <input class="popover-search" type="search" placeholder="Search…" />
      <div class="popover-list"></div>
    `;
    host.appendChild(pop);

    const list = pop.querySelector(".popover-list");
    let q = "";

    function paint() {
      const current = new Set(getValues());
      const filtered = options.filter(o => o.toLowerCase().includes(q));
      if (!filtered.length) {
        list.innerHTML = `<div class="popover-empty">no matches</div>`;
        return;
      }
      list.innerHTML = filtered.map(o => {
        const on = current.has(o);
        return `<div class="popover-item${on ? " selected" : ""}" data-val="${escapeHtml(o)}">
          <span class="check">${on ? `<svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M2 5l2 2 4-5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>` : ""}</span>
          <span>${escapeHtml(o)}</span>
        </div>`;
      }).join("");
      list.querySelectorAll(".popover-item").forEach(item => {
        item.addEventListener("click", () => {
          const cur = new Set(getValues());
          const v = item.dataset.val;
          if (cur.has(v)) cur.delete(v); else cur.add(v);
          setValues(Array.from(cur));
          paint();
        });
      });
    }

    pop.querySelector(".popover-search").addEventListener("input", e => {
      q = e.target.value.trim().toLowerCase(); paint();
    });

    // Position near anchor — using fixed positioning, viewport coords
    function position() {
      const rect = anchor.getBoundingClientRect();
      const POP_W = 260;
      const POP_H_EST = Math.min(320, list.scrollHeight + 60);
      let left = rect.left;
      if (left + POP_W > window.innerWidth - 12) left = window.innerWidth - POP_W - 12;
      if (left < 12) left = 12;
      let top = rect.bottom + 6;
      if (top + POP_H_EST > window.innerHeight - 12) top = Math.max(12, rect.top - POP_H_EST - 6);
      pop.style.left = left + "px";
      pop.style.top = top + "px";
    }

    paint();
    position();

    // Reposition on scroll/resize
    const onMove = () => position();
    window.addEventListener("scroll", onMove, true);
    window.addEventListener("resize", onMove);

    // Click outside closes
    setTimeout(() => {
      document.addEventListener("click", outsideHandler, true);
    }, 0);
    function outsideHandler(e) {
      if (!pop.contains(e.target) && e.target !== anchor) closePopover();
    }
    pop._outside = outsideHandler;
    pop._onMove = onMove;
    pop.querySelector(".popover-search").focus();
  }
  function openThumbPopup(src) {
    const existing = document.getElementById("thumb-popup-overlay");
    if (existing) existing.remove();
    const ov = document.createElement("div");
    ov.id = "thumb-popup-overlay";
    ov.className = "thumb-popup-overlay";
    ov.innerHTML = `<img class="thumb-popup-img" src="${escapeHtml(src)}" alt=""/>`;
    document.body.appendChild(ov);
    requestAnimationFrame(() => ov.classList.add("visible"));
    const close = () => {
      ov.classList.remove("visible");
      ov.addEventListener("transitionend", () => ov.remove(), { once: true });
    };
    ov.addEventListener("click", close);
    document.addEventListener("keydown", function onKey(e) {
      if (e.key === "Escape") { close(); document.removeEventListener("keydown", onKey); }
    });
  }

  function closePopover() {
    document.querySelectorAll(".popover").forEach(p => {
      if (p._outside) document.removeEventListener("click", p._outside, true);
      if (p._onMove) {
        window.removeEventListener("scroll", p._onMove, true);
        window.removeEventListener("resize", p._onMove);
      }
      p.remove();
    });
    const root = document.getElementById("popover-root");
    if (root) root.hidden = true;
  }

  // ------- Edit mode toggle + save bar -------
  function setView(view) {
    state.view = view === "edit" ? "edit" : "browse";
    state.page = 1;
    document.body.classList.toggle("edit-mode", state.view === "edit");
    document.querySelectorAll(".view-toggle-btn").forEach(b => {
      const on = b.dataset.view === state.view;
      b.classList.toggle("active", on);
      b.setAttribute("aria-selected", on ? "true" : "false");
    });
    closePopover();
    render();
  }
  function markDirty(id) {
    state.dirty.add(id);
    updateSaveBar();
  }
  function updateSaveBar() {
    const bar = document.getElementById("save-bar");
    if (!bar) return;
    if (state.dirty.size === 0) {
      bar.hidden = true;
    } else {
      bar.hidden = false;
      bar.querySelector(".save-count").textContent = state.dirty.size;
    }
  }
  function discardChanges() {
    if (state.dirty.size === 0) return;
    if (!confirm(`Discard ${state.dirty.size} edited entr${state.dirty.size === 1 ? "y" : "ies"}? They'll revert to the last saved state by reloading the page.`)) return;
    location.reload();
  }
  async function publishChanges() {
    const token = getEditToken();
    if (!token) {
      alert("No edit token. Visit the site with ?edit=YOUR_TOKEN once to enable saving.");
      return;
    }
    if (state.dirty.size === 0) return;
    const btn = document.querySelector("[data-save-publish]");
    const originalLabel = btn ? btn.textContent : "";
    if (btn) { btn.disabled = true; btn.textContent = "Saving…"; }
    try {
      const payload = { schema: state.schema, entries: state.entries };
      const res = await fetch("/.netlify/functions/save-inspiration", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Edit-Token": token,
          "X-Edit-Author": "editor-ui",
        },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.error || `Save failed (HTTP ${res.status})`);
      }
      state.dirty.clear();
      updateSaveBar();
      document.querySelectorAll("tr.is-dirty").forEach(tr => tr.classList.remove("is-dirty"));
      showSavedToast(data);
    } catch (err) {
      const msg = err && err.message ? err.message : String(err);
      const fallback = confirm(
        `Save failed: ${msg}\n\nFall back to download instead?`
      );
      if (fallback) downloadPatchedFallback();
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = originalLabel || "Save changes"; }
    }
  }

  function downloadPatchedFallback() {
    const payload = { schema: state.schema, entries: state.entries };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "inspiration.json";
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    alert("inspiration.json downloaded.\nNext: run scripts/apply_edits.py, then commit + push (or ./scripts/deploy.sh).");
  }

  function showSavedToast(data) {
    const root = document.getElementById("save-toast") || (() => {
      const el = document.createElement("div");
      el.id = "save-toast";
      el.className = "save-toast";
      document.body.appendChild(el);
      return el;
    })();
    const commitLink = data.commitUrl
      ? `<a href="${data.commitUrl}" target="_blank" rel="noopener">view commit ↗</a>`
      : "";
    root.innerHTML = `
      <div class="save-toast-inner">
        <strong>Saved.</strong> Netlify is rebuilding (~30s). ${commitLink}
        <button type="button" class="save-toast-close" aria-label="Close">×</button>
      </div>`;
    root.classList.add("active");
    const close = () => root.classList.remove("active");
    root.querySelector(".save-toast-close").addEventListener("click", close);
    setTimeout(close, 8000);
  }

  function renderCard(e) {
    // Card tags: Industries (primary) + Word Associations (secondary). Cap each so cards don't sprawl.
    const industries = (e.companyIndustry || []).slice(0, 2);
    const words = (e.wordAssociations || []).slice(0, 3);
    const totalTags = industries.length + words.length;

    const flagChips = [];
    if (e.industryLeader) flagChips.push(`<span class="card-tag flag" title="Industry Leader">★</span>`);
    if (e.unconventional) flagChips.push(`<span class="card-tag flag" title="Unconventional">⚡</span>`);

    const industryHtml = industries.map(v =>
      `<span class="card-tag tag-industry">${escapeHtml(v)}</span>`).join("");
    const wordHtml = words.map(v =>
      `<span class="card-tag tag-word">${escapeHtml(v)}</span>`).join("");
    const tagsHtml = (totalTags || flagChips.length)
      ? `<div class="card-foot-tags">${industryHtml}${wordHtml}${flagChips.join("")}</div>`
      : `<div class="card-foot-tags card-foot-empty"><span class="card-tag tag-muted">untagged</span></div>`;

    const faved = state.favorites.has(e.id);
    const thumb = e.screenshot
      ? `<img src="${escapeHtml(e.screenshot)}" alt="${escapeHtml(e.name)} screenshot" loading="lazy" />`
      : `<div class="placeholder"><span class="ph-domain">${escapeHtml(e.domain || e.name)}</span><span class="ph-note">screenshot pending</span></div>`;

    return `
      <article class="card" data-id="${escapeHtml(e.id)}">
        <div class="card-head">
          <div class="card-title">${escapeHtml(e.name)}</div>
          <span class="card-arrow"><svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M4 10L10 4M10 4H5M10 4V9" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg></span>
        </div>
        <div class="card-thumb">
          ${thumb}
          ${e.webstacksClient ? `<div class="card-client-badge">Webstacks Client</div>` : ""}
          <button type="button" class="card-fav-btn${faved ? " active" : ""}" data-fav-id="${escapeHtml(e.id)}" aria-label="${faved ? "Remove from favorites" : "Add to favorites"}">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M7 12S1.5 8 1.5 4.5a3 3 0 0 1 5.5-1.7A3 3 0 0 1 12.5 4.5C12.5 8 7 12 7 12z" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/></svg>
          </button>
          <a class="card-visit-btn" href="${escapeHtml(e.url)}" target="_blank" rel="noopener noreferrer" aria-label="Visit ${escapeHtml(e.name)}">
            Visit site
            <svg width="11" height="11" viewBox="0 0 11 11" fill="none"><path d="M3 8L8 3M8 3H4.5M8 3V6.5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg>
          </a>
        </div>
        <div class="card-foot">${tagsHtml}</div>
      </article>`;
  }

  function renderPagination(page, total) {
    const root = document.getElementById("pagination");
    if (total <= 1) { root.innerHTML = ""; return; }
    const html = [];
    const btn = (label, p, disabled=false, active=false) =>
      `<button class="pg-btn${active?' active':''}${disabled?' disabled':''}" data-page="${p}">${label}</button>`;
    html.push(btn("‹", Math.max(1, page-1), page === 1));
    // Compact pages: 1, 2, 3, ..., total
    const pages = compactPages(page, total);
    pages.forEach(p => {
      if (p === "…") html.push(`<span class="pg-ellipsis">…</span>`);
      else html.push(btn(p, p, false, p === page));
    });
    html.push(btn("›", Math.min(total, page+1), page === total));
    root.innerHTML = html.join("");
    root.querySelectorAll(".pg-btn").forEach(b => b.addEventListener("click", () => {
      state.page = parseInt(b.dataset.page, 10);
      window.scrollTo({ top: document.querySelector(".main").offsetTop, behavior: "smooth" });
      render();
    }));
  }
  function compactPages(p, total) {
    const out = [];
    const push = n => { if (!out.includes(n)) out.push(n); };
    push(1); if (total >= 2) push(2); if (total >= 3) push(3);
    if (p > 4) out.push("…");
    if (p > 3 && p < total - 2) push(p);
    if (p < total - 3) out.push("…");
    if (total - 2 > 3) push(total - 2);
    if (total - 1 > 3) push(total - 1);
    if (total > 3) push(total);
    return out;
  }

  function renderActiveChips() {
    const root = document.getElementById("active-chips");
    const chips = [];
    Object.entries(state.filters).forEach(([cat, set]) => {
      set.forEach(v => {
        const display = cat === "standoutElements" ? v.split("::")[1]
                      : cat === "flags" ? (v === "industryLeader" ? "★ Industry Leader" : v === "unconventional" ? "⚡ Unconventional" : "✦ Webstacks Client")
                      : v;
        chips.push(`<button class="active-chip" data-cat="${escapeHtml(cat)}" data-val="${escapeHtml(v)}">${escapeHtml(display)}</button>`);
      });
    });
    state.activeCustomTags.forEach(tag => {
      chips.push(`<button class="active-chip" data-custom-tag="${escapeHtml(tag)}">🏷 ${escapeHtml(tag)}</button>`);
    });
    if (state.search) chips.push(`<button class="active-chip" data-clear-search>"${escapeHtml(state.search)}"</button>`);
    root.innerHTML = chips.join("");
    root.querySelectorAll(".active-chip").forEach(c => c.addEventListener("click", () => {
      if (c.dataset.customTag !== undefined) {
        toggleCustomTagFilter(c.dataset.customTag); return;
      }
      if (c.dataset.clearSearch !== undefined) {
        state.search = ""; document.getElementById("search").value = ""; state.page = 1; render(); return;
      }
      const cat = c.dataset.cat, val = c.dataset.val;
      state.filters[cat].delete(val);
      document.querySelectorAll(`[data-cat="${cssEscape(cat)}"][data-val="${cssEscape(val)}"]`).forEach(b => b.setAttribute("aria-pressed","false"));
      state.page = 1;
      render();
    }));
  }

  // ------- Hero collage -------
  function paintCollage() {
    // pick 6 entries with screenshots; if fewer, fill with empty tiles
    const withImg = state.entries.filter(e => e.screenshot).slice(0, 6);
    document.querySelectorAll(".collage-tile").forEach((tile, i) => {
      if (withImg[i]) {
        tile.style.backgroundImage = `url('${withImg[i].screenshot}')`;
      } else {
        tile.classList.add("empty");
      }
    });
  }

  // ------- Detail dialog -------
  function openDetail(id, opts={}) {
    const e = state.entries.find(x => x.id === id); if (!e) return;
    state.detailId = id;
    state.detailEditing = !!opts.edit;
    renderDetail();
    const dlg = document.getElementById("detail");
    if (typeof dlg.showModal === "function" && !dlg.open) dlg.showModal();
    else if (!dlg.open) dlg.setAttribute("open","");
    upgradeDownloadToFull(dlg, id);
  }

  function upgradeDownloadToFull(dlg, id) {
    const fullSrc = `assets/screenshots/full/${id}.jpg`;
    fetch(fullSrc, { method: "HEAD" }).then(r => {
      if (!r.ok) return;
      const a = dlg.querySelector(`a.detail-action[data-full-src]`);
      if (a) a.href = fullSrc;
    }).catch(() => {});
  }

  function renderDetail() {
    const e = state.entries.find(x => x.id === state.detailId);
    if (!e) return;
    const dlg = document.getElementById("detail");
    const body = dlg.querySelector(".dialog-body");
    const editing = state.detailEditing;

    // Read-only section
    const sec = (title, vals, flag=false) => vals && vals.length ? `
      <div class="detail-section"><h4>${escapeHtml(title)}</h4>
        <div class="detail-tags">${vals.map(v=>`<span class="detail-tag${flag?' flag':''}">${escapeHtml(v)}</span>`).join("")}</div>
      </div>` : "";
    // Editable section (chip group with + add)
    const editSec = (title, field, options) => `
      <div class="detail-section editing"><h4>${escapeHtml(title)}</h4>
        ${renderChipGroup(e, field)}
      </div>`;

    // Action buttons
    const visitHref = e.url ? escapeHtml(e.url) : "";
    const visitBtn = e.url
      ? `<a class="detail-action primary" href="${visitHref}" target="_blank" rel="noopener">
           Visit site
           <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M4 10L10 4M10 4H5M10 4V9" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
         </a>`
      : `<button class="detail-action primary" type="button" disabled>Visit site</button>`;
    const downloadName = `${e.id || slugify(e.name)}.jpg`;
    const fullShotPath = e.id ? `assets/screenshots/full/${e.id}.jpg` : null;
    const downloadBtn = e.screenshot || fullShotPath
      ? `<a class="detail-action" href="${escapeHtml(e.screenshot || '')}" download="${escapeHtml(downloadName)}" data-full-src="${escapeHtml(fullShotPath || '')}">
           Download screenshot
           <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M7 1v9M3.5 6.5L7 10l3.5-3.5M2 12h10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
         </a>`
      : `<button class="detail-action" type="button" disabled>Download screenshot</button>`;
    const editBtn = `<button type="button" class="detail-edit-toggle${editing ? " active" : ""}" data-edit-toggle>${editing ? "Done editing" : "Edit tags"}</button>`;
    const faved = state.favorites.has(e.id);
    const favBtn = `<button type="button" class="detail-fav-btn${faved ? " active" : ""}" data-fav-id="${escapeHtml(e.id)}">${faved ? "♥ Favorited" : "♡ Favorite"}</button>`;

    const domainLine = e.url
      ? `<div class="detail-domain"><a href="${visitHref}" target="_blank" rel="noopener">${escapeHtml(e.domain || e.url)} ↗</a></div>`
      : (e.domain ? `<div class="detail-domain">${escapeHtml(e.domain)}</div>` : "");

    const updatedTs = e.screenshotUpdatedAt || e.screenshotCapturedAt;
    const updatedLine = updatedTs
      ? `<div class="detail-updated">Screenshot updated ${formatMonthYear(updatedTs)}</div>`
      : "";

    let sections;
    if (!editing) {
      const standout = Object.entries(e.standoutElements||{}).map(([sub, vs]) =>
        vs.length ? `<div class="detail-section"><h4>Standout · ${escapeHtml(sub)}</h4><div class="detail-tags">${vs.map(v=>`<span class="detail-tag">${escapeHtml(v)}</span>`).join("")}</div></div>` : ""
      ).join("");
      const flagsBlock = (e.industryLeader || e.unconventional)
        ? `<div class="detail-section"><h4>Flags</h4><div class="detail-tags">${e.industryLeader?'<span class="detail-tag flag">★ Industry Leader</span>':''}${e.unconventional?'<span class="detail-tag flag">⚡ Unconventional</span>':''}</div></div>`
        : "";
      sections =
        sec("Company Size", e.companySize)
        + sec("Company Type", e.companyType)
        + sec("Industry", e.companyIndustry)
        + sec("Site Structure", e.siteStructure)
        + sec("Design Aesthetic", e.designAesthetic)
        + standout
        + sec("Word Associations", e.wordAssociations)
        + sec("Typefaces", e.typefaces)
        + flagsBlock;
    } else {
      // Type single-select
      const types = state.schema.companyType.map(v => {
        const on = (e.companyType || []).includes(v);
        return `<button type="button" class="single-pick-btn" data-val="${escapeHtml(v)}" aria-pressed="${on}">${escapeHtml(v)}</button>`;
      }).join("");
      const standoutEdit = Object.entries(state.schema.standoutElements).map(([sub, opts]) => {
        const fakeField = `standoutElements::${sub}`;
        const vals = (e.standoutElements && e.standoutElements[sub]) || [];
        const chips = vals.map(v =>
          `<span class="chip-edit" data-val="${escapeHtml(v)}">${escapeHtml(v)}<button type="button" class="chip-edit-remove" data-remove="${escapeHtml(v)}" aria-label="Remove">×</button></span>`
        ).join("");
        const empty = !vals.length ? `<span class="chip-empty">none</span>` : "";
        return `
        <div class="detail-section editing"><h4>Standout · ${escapeHtml(sub)}</h4>
          <div class="chip-edit-group" data-field="${escapeHtml(fakeField)}">
            ${chips}${empty}
            <button type="button" class="chip-add" data-add>+ Add</button>
          </div>
        </div>`;
      }).join("");
      // Free-text typefaces editor (comma list)
      const typefacesVal = (e.typefaces || []).join(", ");
      const sizes = state.schema.companySize.map(v => {
        const on = (e.companySize || []).includes(v);
        return `<button type="button" class="single-pick-btn size-pick-btn" data-val="${escapeHtml(v)}" aria-pressed="${on}">${escapeHtml(v)}</button>`;
      }).join("");
      sections = `
        <div class="detail-section editing"><h4>Company Size</h4>
          <div class="single-pick">${sizes}</div>
        </div>
        <div class="detail-section editing"><h4>Company Type</h4>
          <div class="single-pick">${types}</div>
        </div>
        ${editSec("Industry", "companyIndustry", state.schema.companyIndustry)}
        ${editSec("Design Aesthetic", "designAesthetic", state.schema.designAesthetic)}
        ${editSec("Word Associations", "wordAssociations", state.schema.wordAssociations)}
        ${standoutEdit}
        <div class="detail-section editing"><h4>Typefaces</h4>
          <input type="text" class="typefaces-input" data-field="typefaces" value="${escapeHtml(typefacesVal)}" placeholder="comma-separated, e.g. Inter, Tiempos" style="width:100%;padding:8px 12px;border:1px solid var(--border-2);border-radius:8px;background:var(--surface-2);color:var(--text);font:inherit;font-size:13px;" />
        </div>
        <div class="detail-section editing"><h4>Flags</h4>
          <div class="flag-toggles">
            <label class="flag-toggle${e.industryLeader ? " on" : ""}">
              <input type="checkbox" data-field="industryLeader"${e.industryLeader ? " checked" : ""}/>
              <span class="flag-mark">★</span><span>Industry Leader</span>
            </label>
            <label class="flag-toggle${e.unconventional ? " on" : ""}">
              <input type="checkbox" data-field="unconventional"${e.unconventional ? " checked" : ""}/>
              <span class="flag-mark">⚡</span><span>Unconventional</span>
            </label>
          </div>
        </div>
      `;
    }

    body.innerHTML = `
      <div class="detail-thumb">${e.screenshot ? `<img src="${escapeHtml(e.screenshot)}" alt="${escapeHtml(e.name)}"/>` : `<div class="detail-thumb-empty">screenshot pending</div>`}</div>
      <div class="detail-header">
        <div>
          <div class="detail-name">${escapeHtml(e.name)}</div>
          ${domainLine}
          ${updatedLine}
        </div>
        <div class="detail-actions">
          ${favBtn}
          ${editBtn}
          ${visitBtn}
          ${downloadBtn}
        </div>
      </div>
      ${faved ? renderCustomTagSectionHtml(e.id) : ""}
      ${state.sharedAlbum ? "" : renderAlbumAddSectionHtml(e.id)}
      ${sections}
    `;

    // Wire up edit toggle
    const editToggle = body.querySelector("[data-edit-toggle]");
    if (editToggle) {
      editToggle.addEventListener("click", () => {
        state.detailEditing = !state.detailEditing;
        renderDetail();
      });
    }

    // Wire up favorite button in detail
    const favBtnEl = body.querySelector(".detail-fav-btn");
    if (favBtnEl) {
      favBtnEl.addEventListener("click", () => {
        toggleFavorite(favBtnEl.dataset.favId);
        // Show/hide custom tags section when fav state changes
        renderDetail();
      });
    }

    // Wire custom tag section (only present when favorited)
    if (faved) wireCustomTagSection(body, e.id);
    // Wire album checkboxes (always present unless shared album view)
    if (!state.sharedAlbum) wireAlbumAddSection(body, e.id);

    if (editing) {
      // Size single-pick
      body.querySelectorAll(".size-pick-btn").forEach(btn => {
        btn.addEventListener("click", () => {
          const v = btn.dataset.val;
          const cur = e.companySize || [];
          e.companySize = cur.includes(v) ? cur.filter(x => x !== v) : [v];
          markDirty(e.id);
          body.querySelectorAll(".size-pick-btn").forEach(b => {
            b.setAttribute("aria-pressed", (e.companySize || []).includes(b.dataset.val) ? "true" : "false");
          });
        });
      });
      // Type single-pick — partial update, no full re-render
      body.querySelectorAll(".single-pick-btn:not(.size-pick-btn)").forEach(btn => {
        btn.addEventListener("click", () => {
          const v = btn.dataset.val;
          const cur = e.companyType || [];
          e.companyType = cur.includes(v) ? cur.filter(x => x !== v) : [v];
          markDirty(e.id);
          body.querySelectorAll(".single-pick-btn:not(.size-pick-btn)").forEach(b => {
            b.setAttribute("aria-pressed", (e.companyType || []).includes(b.dataset.val) ? "true" : "false");
          });
        });
      });
      // Chip groups for the simple multi-tag fields. Partial updates keep the popover open.
      ["companyIndustry","designAesthetic","wordAssociations"].forEach(field => {
        const opts = state.schema[field];
        attachChipGroupEvents(body, e, field, opts);
      });
      // Standout sub-groups (split on ::). Partial update so popover stays open.
      Object.entries(state.schema.standoutElements).forEach(([sub, opts]) => {
        const fakeField = `standoutElements::${sub}`;
        const grp = body.querySelector(`.chip-edit-group[data-field="${cssEscape(fakeField)}"]`);
        if (!grp) return;

        function getVals() {
          return (e.standoutElements && e.standoutElements[sub]) || [];
        }
        function setVals(vals) {
          e.standoutElements = e.standoutElements || {};
          e.standoutElements[sub] = vals;
          markDirty(e.id);
          updateChipsInGroup(grp, vals);
          // Re-wire remove handlers for the new chips so they call setVals
          wireChipRemoves(grp, null, val => setVals(getVals().filter(x => x !== val)));
        }

        // Initial wire for any existing chips
        wireChipRemoves(grp, null, val => setVals(getVals().filter(x => x !== val)));

        const addBtn = grp.querySelector(".chip-add");
        if (addBtn) {
          addBtn.addEventListener("click", evt => {
            evt.stopPropagation();
            openPopover(addBtn, opts, getVals, setVals);
          });
        }
      });
      // Typefaces text input
      const typefacesInput = body.querySelector(".typefaces-input");
      if (typefacesInput) {
        typefacesInput.addEventListener("change", () => {
          e.typefaces = typefacesInput.value.split(",").map(s => s.trim()).filter(Boolean);
          markDirty(e.id);
        });
      }
      // Flag toggles — partial update, no full re-render
      body.querySelectorAll(".flag-toggle input[type=checkbox]").forEach(cb => {
        cb.addEventListener("change", () => {
          e[cb.dataset.field] = cb.checked;
          markDirty(e.id);
          cb.closest(".flag-toggle").classList.toggle("on", cb.checked);
        });
      });
    }
  }
  function slugify(s){ return String(s||"").toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-+|-+$/g,""); }

  // ------- Events -------
  function attachEvents() {
    document.getElementById("search").addEventListener("input", e => { state.search = e.target.value.trim(); state.page = 1; render(); });
    document.getElementById("sort").addEventListener("change", e => { state.sort = e.target.value; render(); });
    document.getElementById("reset-filters").addEventListener("click", resetFilters);
    document.querySelectorAll(".grid-density-btn").forEach(b => {
      b.addEventListener("click", () => {
        state.gridCols = parseInt(b.dataset.cols, 10);
        try { localStorage.setItem("inspoGridCols", state.gridCols); } catch(e) {}
        applyGridCols();
      });
    });
    document.getElementById("nav-home").addEventListener("click", e => { e.preventDefault(); setShowFavorites(false); });
    document.getElementById("nav-favorites").addEventListener("click", e => { e.preventDefault(); setShowFavorites(true); });

    // Add-album button
    const addAlbumBtn = document.getElementById("add-album-btn");
    const newAlbumForm = document.getElementById("new-album-form");
    const newAlbumInput = document.getElementById("new-album-input");
    addAlbumBtn.addEventListener("click", () => {
      newAlbumForm.hidden = false;
      newAlbumInput.value = "";
      newAlbumInput.focus();
    });
    newAlbumInput.addEventListener("keydown", ev => {
      if (ev.key === "Enter") {
        const album = createAlbum(newAlbumInput.value);
        newAlbumForm.hidden = true;
        if (album) setActiveAlbum(album.id);
      } else if (ev.key === "Escape") {
        newAlbumForm.hidden = true;
      }
    });
    newAlbumInput.addEventListener("blur", () => {
      // small delay so Enter can fire first
      setTimeout(() => { newAlbumForm.hidden = true; }, 150);
    });

    // Share-album button
    const shareAlbumBtn = document.getElementById("share-album-btn");
    shareAlbumBtn.addEventListener("click", () => {
      const album = state.albums.find(a => a.id === state.activeAlbum);
      if (!album) return;
      const url = generateShareUrl(album);
      navigator.clipboard.writeText(url).then(() => {
        const orig = shareAlbumBtn.innerHTML;
        shareAlbumBtn.textContent = "✓ Link copied!";
        setTimeout(() => { shareAlbumBtn.innerHTML = orig; }, 2500);
      }).catch(() => {
        prompt("Copy this link:", url);
      });
    });
    document.querySelectorAll("dialog .dialog-close").forEach(b => b.addEventListener("click", () => b.closest("dialog").close()));
    document.getElementById("detail").addEventListener("click", e => { if (e.target.tagName === "DIALOG") e.target.close(); });
    document.getElementById("detail").addEventListener("close", () => {
      state.detailId = null; state.detailEditing = false;
      // Re-render so dirty styling on the underlying table refreshes
      if (state.view === "edit") render();
    });

    // View toggle (Browse / Edit)
    document.querySelectorAll(".view-toggle-btn").forEach(b => {
      b.addEventListener("click", () => setView(b.dataset.view));
    });

    // Save bar
    const pub = document.querySelector("[data-save-publish]");
    if (pub) pub.addEventListener("click", publishChanges);
    const dc = document.querySelector("[data-save-discard]");
    if (dc) dc.addEventListener("click", discardChanges);

    // Warn before leaving with unsaved changes
    window.addEventListener("beforeunload", e => {
      if (state.dirty.size > 0) { e.preventDefault(); e.returnValue = ""; }
    });

    // Esc closes popover
    document.addEventListener("keydown", e => { if (e.key === "Escape") closePopover(); });

    attachSubmitForm();
  }

  // ------- Submit-a-URL dialog -------
  function attachSubmitForm() {
    const dlg = document.getElementById("submit-dialog");
    if (!dlg) return;
    const form = document.getElementById("submit-url-form");
    const states = dlg.querySelectorAll(".submit-state");
    const errEl = dlg.querySelector(".submit-error");

    function showState(name) {
      states.forEach(s => { s.hidden = s.dataset.state !== name; });
    }
    function openSubmit() {
      showState("form");
      if (errEl) { errEl.hidden = true; errEl.textContent = ""; }
      if (typeof dlg.showModal === "function") dlg.showModal(); else dlg.setAttribute("open", "");
      const first = form && form.querySelector("input, textarea");
      if (first) first.focus();
    }

    document.querySelectorAll("[data-open-submit]").forEach(el => {
      el.addEventListener("click", e => { e.preventDefault(); openSubmit(); });
    });
    dlg.querySelectorAll("[data-close-submit]").forEach(el => {
      el.addEventListener("click", () => dlg.close());
    });
    dlg.querySelectorAll("[data-submit-another]").forEach(el => {
      el.addEventListener("click", () => { form.reset(); showState("form"); });
    });
    dlg.addEventListener("click", e => { if (e.target === dlg) dlg.close(); });

    if (!form) return;
    form.addEventListener("submit", async e => {
      e.preventDefault();
      const submitBtn = form.querySelector('button[type="submit"]');
      if (errEl) { errEl.hidden = true; errEl.textContent = ""; }
      submitBtn.disabled = true; submitBtn.textContent = "Submitting…";
      try {
        const fd = new FormData(form);
        const body = new URLSearchParams();
        fd.forEach((v, k) => body.append(k, v));
        const res = await fetch("/", {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: body.toString(),
        });
        if (!res.ok) throw new Error(`Server returned ${res.status}`);
        showState("success");
        form.reset();
      } catch (err) {
        if (errEl) {
          errEl.textContent = "Couldn't submit. Try again, or send the URL directly to Hunter.";
          errEl.hidden = false;
        }
        // file:// won't have Netlify form handling — surface a useful hint
        if (location.protocol === "file:") {
          if (errEl) errEl.textContent = "Form submissions only work on the deployed site (webstacks-inspolibrary.netlify.app).";
        }
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = "Submit site";
      }
    });
  }
  function resetFilters() {
    Object.values(state.filters).forEach(s => s.clear());
    state.activeCustomTags.clear();
    state.activeAlbum = null;
    state.search = ""; state.page = 1;
    document.getElementById("search").value = "";
    document.querySelectorAll('[aria-pressed="true"]').forEach(c => c.setAttribute("aria-pressed","false"));
    renderAlbumsNav();
    updateHeroCopy();
    updateCustomTagsDropdown();
    render();
  }

  // ------- Helpers -------
  function escapeHtml(s){ return String(s ?? "").replace(/[&<>"']/g, m => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[m])); }
  function cssEscape(s){ return String(s).replace(/(["\\])/g, "\\$1"); }
  function formatMonthYear(iso){ try { return new Date(iso).toLocaleDateString("en-US",{month:"long",year:"numeric"}); } catch(e){ return ""; } }
  window.WebInspo = { resetFilters };
})();
