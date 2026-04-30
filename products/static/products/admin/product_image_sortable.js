/**
 * Перетаскивание строк инлайна галереи (ProductImage) для смены sort_order.
 * Формсет: related_name=images → id="images-group".
 */
(function () {
  "use strict";

  var GROUP_ID = "images-group";

  function qs(root, sel) {
    return root.querySelector(sel);
  }

  function dataRows(tbody) {
    return Array.prototype.slice.call(
      tbody.querySelectorAll("tr.form-row:not(.empty-form):not(.row-form-errors)")
    );
  }

  function emptyRow(tbody) {
    return tbody.querySelector("tr.empty-form");
  }

  function syncSortOrder(tbody) {
    dataRows(tbody).forEach(function (tr, i) {
      var inp = tr.querySelector('input[name$="-sort_order"]');
      if (inp) inp.value = String(i);
    });
  }

  function addHandles(tbody) {
    dataRows(tbody).forEach(function (tr) {
      var orig = qs(tr, "td.original");
      if (!orig || qs(orig, ".js-gallery-drag-handle")) return;
      var h = document.createElement("span");
      h.className = "js-gallery-drag-handle";
      h.setAttribute("draggable", "true");
      h.setAttribute("role", "button");
      h.setAttribute("aria-label", "Перетащить для смены порядка фото");
      h.title = "Перетащите для смены порядка";
      orig.insertBefore(h, orig.firstChild);
    });
  }

  function getDragAfterElement(tbody, y, dragEl) {
    var els = dataRows(tbody).filter(function (c) {
      return c !== dragEl;
    });
    var closest = { offset: Number.NEGATIVE_INFINITY, element: null };
    els.forEach(function (child) {
      var box = child.getBoundingClientRect();
      var offset = y - box.top - box.height / 2;
      if (offset < 0 && offset > closest.offset) {
        closest = { offset: offset, element: child };
      }
    });
    return closest.element;
  }

  function initGroup(root) {
    var tbody = qs(root, "tbody");
    if (!tbody) return;

    addHandles(tbody);
    syncSortOrder(tbody);

    var dragRow = null;

    tbody.addEventListener("dragstart", function (e) {
      var handle = e.target.closest(".js-gallery-drag-handle");
      if (!handle) return;
      var tr = handle.closest("tr.form-row");
      if (!tr || tr.classList.contains("empty-form") || !tbody.contains(tr)) return;
      dragRow = tr;
      e.dataTransfer.effectAllowed = "move";
      try {
        e.dataTransfer.setData("text/plain", tr.id || "row");
      } catch (_err) {}
      tr.classList.add("is-gallery-dragging");
    });

    tbody.addEventListener("dragend", function () {
      if (dragRow) dragRow.classList.remove("is-gallery-dragging");
      dragRow = null;
      syncSortOrder(tbody);
    });

    tbody.addEventListener("dragover", function (e) {
      e.preventDefault();
      if (!dragRow) return;
      e.dataTransfer.dropEffect = "move";
      var afterEl = getDragAfterElement(tbody, e.clientY, dragRow);
      var empty = emptyRow(tbody);
      if (!afterEl) {
        if (empty) tbody.insertBefore(dragRow, empty);
        else tbody.appendChild(dragRow);
      } else {
        tbody.insertBefore(dragRow, afterEl);
      }
    });

    tbody.addEventListener("drop", function (e) {
      e.preventDefault();
    });

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
  }

  function boot() {
    var root = document.getElementById(GROUP_ID);
    if (root) initGroup(root);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
