(function () {
  "use strict";

  window.addEventListener("scroll", function () {
    var header = document.querySelector(".header");
    if (header) {
      header.classList.toggle("scrolled", window.scrollY > 10);
    }
  });

  if ("IntersectionObserver" in window) {
    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("visible");
          }
        });
      },
      { threshold: 0.1 }
    );

    document
      .querySelectorAll(".product-card, .category-card, .delivery-info-card")
      .forEach(function (el) {
        el.style.opacity = "0";
        el.style.transform = "translateY(20px)";
        el.style.transition = "opacity 0.4s ease, transform 0.4s ease";
        observer.observe(el);
      });
  }

  document.querySelectorAll(".product-gallery__thumb").forEach(function (thumb) {
    thumb.addEventListener("click", function () {
      document.querySelectorAll(".product-gallery__thumb").forEach(function (t) {
        t.classList.remove("active");
      });
      thumb.classList.add("active");
      var mainImg = document.querySelector(".product-gallery__main img");
      var inner = thumb.querySelector("img");
      if (mainImg && inner) mainImg.src = inner.src;
    });
  });

  document.querySelectorAll(".qty-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var wrap = btn.closest(".qty-control");
      if (!wrap) return;
      var input = wrap.querySelector(".qty-input");
      if (!input) return;
      var val = parseInt(input.value, 10) || 1;
      if (btn.dataset.action === "plus") input.value = String(val + 1);
      if (btn.dataset.action === "minus" && val > 1) input.value = String(val - 1);
    });
  });

  document.querySelectorAll(".counter-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var wrap = btn.closest(".quantity-control");
      if (!wrap) return;
      var input = wrap.querySelector('input[name="quantity"]');
      if (!input) return;
      var val = parseInt(input.value, 10) || 0;
      var action = btn.getAttribute("data-action");
      if (action === "increment") input.value = String(val + 1);
      if (action === "decrement" && val > 0) input.value = String(val - 1);
    });
  });
})();
