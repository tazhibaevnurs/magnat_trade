(function () {
  "use strict";

  function csrfToken() {
    var inp = document.querySelector('input[name="csrfmiddlewaretoken"]');
    if (inp && inp.value) {
      return inp.value;
    }
    var m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
  }

  function chunkArray(arr, size) {
    var out = [];
    for (var i = 0; i < arr.length; i += size) {
      out.push(arr.slice(i, i + size));
    }
    return out;
  }

  window.initProductGalleryBatchUpload = function (root) {
    var url = root.getAttribute("data-upload-url");
    var batchSize = parseInt(root.getAttribute("data-files-per-batch") || "8", 10) || 8;
    var input = root.querySelector("#product-gallery-batch-input");
    var btn = root.querySelector("#product-gallery-batch-submit");
    var statusEl = root.querySelector("#product-gallery-batch-status");
    var errEl = root.querySelector("#product-gallery-batch-errors");
    if (!url || !input || !btn || !statusEl || !errEl) {
      return;
    }

    function setStatus(t) {
      statusEl.textContent = t || "";
    }

    function setErrors(lines) {
      errEl.textContent = lines.length ? lines.join("\n") : "";
    }

    btn.addEventListener("click", function () {
      var files = input.files;
      if (!files || !files.length) {
        setStatus("Выберите один или несколько файлов.");
        return;
      }
      var list = Array.prototype.slice.call(files);
      var batches = chunkArray(list, batchSize);
      var token = csrfToken();
      btn.disabled = true;
      setErrors([]);
      var totalCreated = 0;
      var errLines = [];

      function runBatch(idx) {
        if (idx >= batches.length) {
          btn.disabled = false;
          setStatus("Готово. Добавлено файлов: " + totalCreated + ".");
          setErrors(errLines);
          if (totalCreated > 0) {
            window.location.reload();
          }
          return;
        }

        setStatus("Загрузка пакета " + (idx + 1) + " из " + batches.length + "…");
        var fd = new FormData();
        batches[idx].forEach(function (f) {
          fd.append("images", f, f.name);
        });

        fetch(url, {
          method: "POST",
          headers: { "X-CSRFToken": token },
          body: fd,
          credentials: "same-origin",
        })
          .then(function (r) {
            return r
              .json()
              .catch(function () {
                return {};
              })
              .then(function (data) {
                return { ok: r.ok, status: r.status, data: data };
              });
          })
          .then(function (res) {
            var d = res.data || {};
            if (!res.ok) {
              errLines.push(
                "Пакет " +
                  (idx + 1) +
                  ": " +
                  (d.detail || "ошибка HTTP " + res.status)
              );
              runBatch(idx + 1);
              return;
            }
            totalCreated += d.created || 0;
            if (d.errors && d.errors.length) {
              d.errors.forEach(function (e) {
                errLines.push((e.name || "?") + ": " + (e.detail || ""));
              });
            }
            runBatch(idx + 1);
          })
          .catch(function (err) {
            errLines.push("Пакет " + (idx + 1) + ": сеть — " + err);
            btn.disabled = false;
            setErrors(errLines);
          });
      }

      runBatch(0);
    });
  };
})();
