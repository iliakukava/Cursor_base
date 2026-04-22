/**
 * TeleFlow pitch deck: section nav, scroll-spy, keyboard, flow diagram pulse.
 */
(function () {
  const deck = document.getElementById("deck");
  const slides = deck ? Array.from(deck.querySelectorAll(".slide")) : [];
  const navList = document.querySelector(".deck-nav__list");
  const progressEl = document.getElementById("deck-progress");

  function buildNav() {
    if (!navList || slides.length === 0) return;
    navList.innerHTML = "";
    slides.forEach((slide, i) => {
      const id = slide.id || `slide-${i}`;
      if (!slide.id) slide.id = id;
      const title = slide.dataset.title || `Слайд ${i + 1}`;
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = `#${id}`;
      a.textContent = title;
      a.title = title;
      a.addEventListener("click", (e) => {
        e.preventDefault();
        slide.scrollIntoView({ behavior: "smooth", block: "start" });
      });
      li.appendChild(a);
      navList.appendChild(li);
    });
  }

  function currentSlideIndex() {
    if (!deck || slides.length === 0) return 0;
    const mid = deck.scrollTop + deck.clientHeight * 0.35;
    let best = 0;
    let bestDist = Infinity;
    slides.forEach((el, i) => {
      const top = el.offsetTop;
      const d = Math.abs(top - mid);
      if (d < bestDist) {
        bestDist = d;
        best = i;
      }
    });
    return best;
  }

  function updateNavActive() {
    if (!navList) return;
    const idx = currentSlideIndex();
    const links = navList.querySelectorAll("a");
    links.forEach((a, i) => {
      a.classList.toggle("is-active", i === idx);
    });
  }

  function scrollToIndex(delta) {
    const idx = currentSlideIndex();
    const next = Math.max(0, Math.min(slides.length - 1, idx + delta));
    slides[next].scrollIntoView({ behavior: "smooth", block: "start" });
  }

  /* IntersectionObserver: fade-in blocks */
  function initReveals() {
    const nodes = document.querySelectorAll(".reveal");
    if (!("IntersectionObserver" in window)) {
      nodes.forEach((n) => n.classList.add("is-visible"));
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((en) => {
          if (en.isIntersecting) en.target.classList.add("is-visible");
        });
      },
      { root: deck, threshold: 0.15, rootMargin: "0px 0px -8% 0px" }
    );
    nodes.forEach((n) => io.observe(n));
  }

  /* Flow diagram: cycle highlight on #flow when visible */
  function initFlowHighlight() {
    const flowSlide = document.getElementById("flow");
    if (!flowSlide) return;
    const nodes = flowSlide.querySelectorAll(".flow-node");
    if (nodes.length === 0) return;
    let step = 0;
    let timer = null;

    function setStep(n) {
      nodes.forEach((node, i) => {
        node.classList.toggle("is-active", i === n);
      });
    }

    function startLoop() {
      if (timer) return;
      timer = window.setInterval(() => {
        step = (step + 1) % nodes.length;
        setStep(step);
      }, 900);
    }

    function stopLoop() {
      if (timer) {
        window.clearInterval(timer);
        timer = null;
      }
      nodes.forEach((node) => node.classList.remove("is-active"));
    }

    if (!("IntersectionObserver" in window)) {
      startLoop();
      return;
    }

    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((en) => {
          if (en.isIntersecting) startLoop();
          else stopLoop();
        });
      },
      { root: deck, threshold: 0.25 }
    );
    io.observe(flowSlide);
  }

  document.addEventListener("keydown", (e) => {
    if (!deck || slides.length === 0) return;
    const t = e.target;
    if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable)) return;

    if (e.key === "ArrowDown" || e.key === "PageDown") {
      e.preventDefault();
      scrollToIndex(1);
    } else if (e.key === "ArrowUp" || e.key === "PageUp") {
      e.preventDefault();
      scrollToIndex(-1);
    } else if (e.key === "Home") {
      e.preventDefault();
      slides[0].scrollIntoView({ behavior: "smooth", block: "start" });
    } else if (e.key === "End") {
      e.preventDefault();
      slides[slides.length - 1].scrollIntoView({ behavior: "smooth", block: "start" });
    }
  });

  function updateDeckProgress() {
    if (!deck || !progressEl) return;
    const max = deck.scrollHeight - deck.clientHeight;
    const ratio = max <= 0 ? 1 : Math.min(1, Math.max(0, deck.scrollTop / max));
    progressEl.style.setProperty("--deck-progress", String(ratio));
    const pct = Math.round(ratio * 100);
    progressEl.setAttribute("aria-valuenow", String(pct));
  }

  if (deck) {
    deck.addEventListener(
      "scroll",
      () => {
        window.requestAnimationFrame(() => {
          updateNavActive();
          updateDeckProgress();
        });
      },
      { passive: true }
    );
  }

  buildNav();
  initReveals();
  initFlowHighlight();
  updateNavActive();
  updateDeckProgress();
  window.addEventListener("resize", () => window.requestAnimationFrame(updateDeckProgress));
})();
