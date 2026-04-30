/**
 * Порядок фото галереи (products.Product): SortableJS на строках инлайна и на полоске превью.
 */
(function () {
  "use strict";

  var GROUP_ID = "images-group";
  var STRIP_ID = "product-gallery-admin-strip";

  function qs(root, sel) {
    return root.querySelector(sel);
  }

  function dataRows(tbody) {
    return Array.prototype.slice.call(
      tbody.querySelectorAll("tr.form-row:not(.empty-form):not(.row-form-errors)")
    );
  }

  /** Строка с реальным фото (иначе нельзя трогать sort_order — Django примет строку как заполненную и потребует файл). */
  function countsForGallerySort(tr) {
    if (tr.classList.contains("empty-form")) return false;
    var delInput = tr.querySelector('input[type="checkbox"][name$="-DELETE"]');
    if (delInput && delInput.checked) return false;
    var idInput = tr.querySelector('input[name$="-id"]');
    if (idInput && String(idInput.value).trim()) return true;
    var fileInput = tr.querySelector('input[type="file"][name$="-image"]');
    if (fileInput && fileInput.files && fileInput.files.length > 0) return true;
    return false;
  }

  function emptyRow(tbody) {
    return tbody.querySelector("tr.empty-form");
  }

  function syncSortOrder(tbody) {
    var order = 0;
    dataRows(tbody).forEach(function (tr) {
      var inp = tr.querySelector('input[name$="-sort_order"]');
      if (!inp) return;
      if (countsForGallerySort(tr)) {
        inp.value = String(order);
        order += 1;
      }
      /* Пустые extra-строки: не меняем sort_order — иначе форма перестаёт считаться «пустой». */
    });
  }

  function addHandles(tbody) {
    dataRows(tbody).forEach(function (tr) {
      var orig = qs(tr, "td.original");
      if (!orig || qs(orig, ".js-gallery-drag-handle")) return;
      var h = document.createElement("span");
      h.className = "js-gallery-drag-handle";
      h.setAttribute("role", "button");
      h.setAttribute("aria-label", "Перетащить для смены порядка фото");
      h.title = "Перетащите для смены порядка";
      orig.insertBefore(h, orig.firstChild);
    });
  }

  function reorderRowsFromStrip(strip, tbody) {
    var empty = emptyRow(tbody);
    if (!empty) return;
    var orderedPk = Array.prototype.map.call(
      strip.querySelectorAll(".product-gallery-admin-strip-item"),
      function (el) {
        return el.getAttribute("data-image-id");
      }
    );
    var byPk = {};
    var orphans = [];
    dataRows(tbody).forEach(function (tr) {
      var inp = tr.querySelector('input[name$="-id"]');
      var pk = inp && inp.value;
      if (pk) byPk[pk] = tr;
      else orphans.push(tr);
    });
    orderedPk.forEach(function (pk) {
      var tr = byPk[pk];
      if (tr) tbody.insertBefore(tr, empty);
    });
    orphans.forEach(function (tr) {
      tbody.insertBefore(tr, empty);
    });
  }

  function reorderStripFromTbody(strip, tbody) {
    dataRows(tbody).forEach(function (tr) {
      var inp = tr.querySelector('input[name$="-id"]');
      if (!inp || !inp.value) return;
      var pk = inp.value;
      var item = strip.querySelector(".product-gallery-admin-strip-item[data-image-id=\"" + pk + '"]');
      if (item) strip.appendChild(item);
    });
  }

  function bindTableSortable(tbody) {
    if (typeof Sortable === "undefined") return;
    if (tbody.dataset.gallerySortableBound === "1") return;
    tbody.dataset.gallerySortableBound = "1";

    Sortable.create(tbody, {
      handle: ".js-gallery-drag-handle",
      /* Строки формы — прямые дочерние <tr> у tbody */
      draggable: "> tr",
      filter: "tr.empty-form, tr.row-form-errors",
      preventOnFilter: false,
      animation: 150,
      /* Нативный HTML5-DnD для <tr> в таблице часто ломается в админке */
      forceFallback: true,
      fallbackOnBody: true,
      fallbackTolerance: 8,
      swapThreshold: 0.65,
      onEnd: function () {
        syncSortOrder(tbody);
        var strip = document.getElementById(STRIP_ID);
        if (strip) reorderStripFromTbody(strip, tbody);
      },
    });
  }

  function bindStripSortable(strip, tbody) {
    if (typeof Sortable === "undefined") return;
    if (strip.dataset.galleryStripSortBound === "1") return;
    strip.dataset.galleryStripSortBound = "1";

    Sortable.create(strip, {
      draggable: ".product-gallery-admin-strip-item",
      animation: 150,
      ignore: "a",
      forceFallback: true,
      fallbackTolerance: 6,
      onEnd: function () {
        reorderRowsFromStrip(strip, tbody);
        syncSortOrder(tbody);
      },
    });
  }

  function findGalleryTbody() {
    var root = document.getElementById(GROUP_ID);
    var tb = root ? root.querySelector("tbody") : null;
    if (tb) return tb;
    var inp = document.querySelector('tbody input[name^="images-"][name$="-sort_order"]');
    return inp ? inp.closest("tbody") : null;
  }

  function initGalleryInline(tbody) {
    if (!tbody || tbody.dataset.galleryInlineInit === "1") return;
    tbody.dataset.galleryInlineInit = "1";

    addHandles(tbody);
    syncSortOrder(tbody);
    bindTableSortable(tbody);

    var strip = document.getElementById(STRIP_ID);
    if (strip) bindStripSortable(strip, tbody);

    var moTimer = null;
    var mo = new MutationObserver(function () {
      if (moTimer) clearTimeout(moTimer);
      moTimer = setTimeout(function () {
        moTimer = null;
        addHandles(tbody);
        syncSortOrder(tbody);
      }, 50);
    });
    mo.observe(tbody, { childList: true });

    tbody.addEventListener("change", function (ev) {
      var t = ev.target;
      if (t && t.matches && t.matches('input[type="file"][name$="-image"]')) {
        syncSortOrder(tbody);
      }
    });
  }

  function boot() {
    var tbody = findGalleryTbody();
    if (tbody) initGalleryInline(tbody);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
  /* Медиа-скрипты админки иногда подключаются после DOMContentLoaded */
  window.addEventListener("load", boot);
})();
