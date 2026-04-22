(function () {
  var NAV_ICONS = {
    accessories:
      '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.847a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.847.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 0 0-2.456 2.456Z"/></svg>',
    paper:
      '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z"/></svg>',
    notebooks:
      '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25"/></svg>',
    games:
      '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M21 11.25v8.25a1.5 1.5 0 0 1-1.5 1.5H5.25a1.5 1.5 0 0 1-1.5-1.5v-8.25M12 4.875A2.625 2.625 0 1 0 9.375 7.5H12m0-2.625V7.5m0-2.625A2.625 2.625 0 1 1 14.625 7.5H12m0 0V21m-8.625-9.75h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-1.036-.84-1.875-1.875-1.875h-17.25c-1.036 0-1.875.84-1.875 1.875v1.5c0 .621.504 1.125 1.125 1.125Z"/></svg>',
    books:
      '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25"/></svg>',
    writing:
      '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L6.832 19.82a4.5 4.5 0 0 1-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 0 1 1.13-1.897L16.863 4.487Zm0 0L19.5 7.125"/></svg>',
    copybooks:
      '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z"/></svg>',
    sketch:
      '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9.53 16.122a3 3 0 0 0-5.78 1.128 2.25 2.25 0 0 1-2.4 2.245 4.5 4.5 0 0 0 8.4-2.245c0-.399-.078-.78-.22-1.128Zm0 0a15.998 15.998 0 0 0 3.388-1.62m-5.043-.025a15.994 15.994 0 0 1 1.622-3.395m3.42 3.42a15.995 15.995 0 0 0 4.764-4.648l3.876-5.814a1.151 1.151 0 0 0-1.597-1.597L14.146 6.32a15.996 15.996 0 0 0-4.649 4.763m0 0a15.994 15.994 0 0 1-3.394 1.62m3.42-3.42a15.998 15.998 0 0 0-3.388-1.62"/></svg>',
    office:
      '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M20.25 14.15v4.25c0 1.094-.787 2.036-1.872 2.18-2.087.277-4.216.42-6.378.42s-4.291-.143-6.378-.42c-1.085-.144-1.872-1.086-1.872-2.18v-4.25m16.5 0a2.18 2.18 0 0 0 .75-1.661V8.706c0-1.081-.768-2.015-1.837-2.175a48.114 48.114 0 0 0-3.413-.387m4.5 8.006c-.194.165-.42.295-.673.38A23.978 23.978 0 0 1 12 15.75c-2.648 0-5.195-.429-7.577-1.22a2.016 2.016 0 0 1-.673-.38m0 0A11.955 11.955 0 0 1 2.25 12c0-1.036.132-2.04.38-2.98m0 0C4.09 7.195 7.293 6.75 12 6.75c4.707 0 7.91.445 10.37 2.27.248.94.38 1.944.38 2.98m0 0a11.955 11.955 0 0 1-2.38 2.77"/></svg>',
    party:
      '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M21 11.25v8.25a1.5 1.5 0 0 1-1.5 1.5H5.25a1.5 1.5 0 0 1-1.5-1.5v-8.25a1.5 1.5 0 0 1 1.5-1.5h3.379a3 3 0 0 0 5.242 0h3.379a1.5 1.5 0 0 1 1.5 1.5Zm-9-3.75h.008v.008H12V7.5Z"/></svg>',
    craft:
      '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9.568 3H5.25A2.25 2.25 0 0 0 3 5.25v4.318c0 .597.237 1.17.659 1.591l9.581 9.582c.699.699 1.78.872 2.607.33a18.095 18.095 0 0 0 5.223-5.223c.542-.827.369-1.908-.33-2.607L11.16 3.66A2.25 2.25 0 0 0 9.568 3Z"/><path stroke-linecap="round" stroke-linejoin="round" d="M6 6h.008v.008H6V6Z"/></svg>',
    school:
      '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M4.26 10.147a60.438 60.438 0 0 0-.491 6.347A48.62 48.62 0 0 1 12 20.904a48.62 48.62 0 0 1 8.232-4.41 60.46 60.46 0 0 0-.491-6.347m-15.482 0a50.636 50.636 0 0 0-2.658-.813A59.906 59.906 0 0 1 12 3.493a59.903 59.903 0 0 1 10.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.717 50.717 0 0 1 12 13.489a50.702 50.702 0 0 1 7.74-3.342M6.75 15a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Zm0 0v-3.675A55.378 55.378 0 0 1 12 8.443m-7.007 11.55A59.769 59.769 0 0 0 12 21.75a59.768 59.768 0 0 0 7.007-.394m-15.004-3.345A59.77 59.77 0 0 1 12 21.75a59.77 59.77 0 0 1-7.007-.394m0 0A59.77 59.77 0 0 0 12 8.443m0 0V5.25A2.25 2.25 0 0 0 9.75 3h-1.5A2.25 2.25 0 0 0 6 5.25v3.118"/></svg>',
    default:
      '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M2.25 7.125h19.5M3.75 7.125v10.5a2.25 2.25 0 0 0 2.25 2.25h12a2.25 2.25 0 0 0 2.25-2.25v-10.5m-16.5 0V5.25A2.25 2.25 0 0 1 7.5 3h9a2.25 2.25 0 0 1 2.25 2.25v1.875m-16.5 0h16.5"/></svg>',
  };

  var FALLBACK_CATALOG_CATEGORIES = [
    { slug: "accessories", name: "Аксессуары", subs: [] },
    { slug: "paper", name: "Бумага и бумажная продукция.", subs: [] },
    { slug: "notebooks", name: "Ежедневники и записные книги.", subs: [] },
    { slug: "games", name: "Игры", subs: [] },
    { slug: "books", name: "Книги", subs: [] },
    { slug: "writing", name: "Письменные товары, черчение", subs: [] },
    { slug: "copybooks", name: "Прописи и Раскраски.", subs: [] },
    { slug: "sketch", name: "Скетбуки", subs: [] },
    { slug: "office", name: "Товары для Офиса.", subs: [] },
    { slug: "party", name: "Товары для праздника.", subs: [] },
    { slug: "craft", name: "Товары для творчества.", subs: [] },
    { slug: "school", name: "Школа", subs: [] },
  ];

  function withFallbackCategories(categories) {
    if (Array.isArray(categories) && categories.length > 0) return categories;
    return FALLBACK_CATALOG_CATEGORIES.slice();
  }

  function norm(s) {
    return (s || "")
      .trim()
      .toLowerCase()
      .replace(/\s+/g, " ")
      .replace(/\.+$/g, "");
  }

  function iconKeyForCategory(cat) {
    var n = norm(cat && cat.name);
    var rules = [
      ["школа", "school"],
      ["аксессуары", "accessories"],
      ["бумага и бумажная продукция", "paper"],
      ["ежедневники и записные книги", "notebooks"],
      ["игры", "games"],
      ["книги", "books"],
      ["письменные товары", "writing"],
      ["прописи и раскраски", "copybooks"],
      ["скетчбуки", "sketch"],
      ["товары для офиса", "office"],
      ["товары для праздника", "party"],
      ["товары для творчества", "craft"],
    ];
    for (var i = 0; i < rules.length; i++) {
      if (n.indexOf(rules[i][0]) === 0 || n === rules[i][0]) return rules[i][1];
    }
    for (var j = 0; j < rules.length; j++) {
      if (n.indexOf(rules[j][0]) !== -1) return rules[j][1];
    }
    return "default";
  }

  function makeBaseState(cfg) {
    return {
      shopUrl: cfg.shopUrl,
      searchUrl: cfg.searchUrl,
      categories: [],
      catalogQuery: "",
      loading: false,
      openCats: {},
      searchTimer: null,
      iconSvgFor: function (cat) {
        var k = iconKeyForCategory(cat);
        return NAV_ICONS[k] || NAV_ICONS.default;
      },
      goShopSearch: function () {
        var q = (this.catalogQuery || "").trim();
        if (!q) return;
        window.location.href = this.shopUrl + "?search=" + encodeURIComponent(q);
      },
      scheduleSearch: function () {
        var self = this;
        clearTimeout(this.searchTimer);
        this.searchTimer = setTimeout(function () {
          self.runSearch();
        }, 300);
      },
      runSearch: function () {
        var self = this;
        var q = (this.catalogQuery || "").trim();
        this.loading = true;
        var url = new URL(this.searchUrl, window.location.origin);
        url.searchParams.set("q", q);
        fetch(url.toString())
          .then(function (r) {
            if (!r.ok) throw new Error("bad response");
            return r.json();
          })
          .then(function (data) {
            self.categories = data.categories || [];
          })
          .catch(function () {})
          .finally(function () {
            self.loading = false;
          });
      },
    };
  }

  function registerCatalogAlpineData() {
    if (!window.Alpine || typeof window.Alpine.data !== "function") return;
    Alpine.data("catalogDropdown", function (cfg) {
      var state = makeBaseState(cfg);
      state.init = function () {
        var el = document.getElementById("catalog-nav-initial");
        if (!el) return;
        try {
          this.categories = withFallbackCategories(JSON.parse(el.textContent) || []);
        } catch (e) {
          this.categories = withFallbackCategories([]);
        }
      };
      return state;
    });

    Alpine.data("catalogSidebarNav", function (cfg) {
      var state = makeBaseState(cfg);
      state.selectedSlugs = [];
      state.isActive = function (slug) {
        return this.selectedSlugs.indexOf(slug) !== -1;
      };
      state.init = function () {
        var self = this;
        var el = document.getElementById("catalog-nav-sidebar-initial");
        if (el) {
          try {
            this.categories = withFallbackCategories(JSON.parse(el.textContent) || []);
          } catch (e) {
            this.categories = withFallbackCategories([]);
          }
        } else {
          this.categories = withFallbackCategories([]);
        }

        var sel = document.getElementById("catalog-sidebar-selected");
        if (sel) {
          try {
            this.selectedSlugs = JSON.parse(sel.textContent) || [];
          } catch (e2) {
            this.selectedSlugs = [];
          }
        }

        function syncSelectedFromUrl() {
          try {
            var u = new URL(window.location.href);
            self.selectedSlugs = u.searchParams.getAll("categories");
          } catch (_e) {}
        }

        function syncOpenFromSelected() {
          var selected = Array.isArray(self.selectedSlugs) ? self.selectedSlugs : [];
          var nextOpen = {};
          (self.categories || []).forEach(function (cat) {
            var isCatSelected = selected.indexOf(cat.slug) !== -1;
            var hasSelectedSub = (cat.subs || []).some(function (sub) {
              return selected.indexOf(sub.slug) !== -1;
            });
            if (isCatSelected || hasSelectedSub) {
              nextOpen[cat.slug] = true;
            }
          });
          self.openCats = Object.assign({}, self.openCats, nextOpen);
        }

        syncOpenFromSelected();
        document.body.addEventListener("htmx:afterSwap", function (e3) {
          if (e3.detail.target && e3.detail.target.id === "product-grid") {
            syncSelectedFromUrl();
            syncOpenFromSelected();
          }
        });
      };
      return state;
    });

  }

  document.addEventListener("alpine:init", registerCatalogAlpineData);
  // Fallback: if Alpine already initialized before this file loaded.
  if (window.Alpine && typeof window.Alpine.data === "function") {
    registerCatalogAlpineData();
  }
})();
