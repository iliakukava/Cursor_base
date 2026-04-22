/**
 * TeleFlow pitch deck: section nav, scroll-spy, keyboard, flow diagram pulse,
 * slide counter, speaker timer (5:00 green / 7:00 amber / 7:00+ red).
 */
(function () {
  const deck = document.getElementById("deck");
  const slides = deck ? Array.from(deck.querySelectorAll(".slide")) : [];
  const navList = document.querySelector(".deck-nav__list");
  const progressEl = document.getElementById("deck-progress");
  const counterEl = document.getElementById("slide-counter");
  const timerEl = document.getElementById("speaker-timer");
  const timeEl = document.getElementById("speaker-time");
  const toggleBtn = document.getElementById("timer-toggle");
  const resetBtn = document.getElementById("timer-reset");

  const pad = (n) => (n < 10 ? "0" + n : "" + n);

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
    if (counterEl) {
      counterEl.textContent = `${pad(idx + 1)} / ${pad(slides.length)}`;
    }
    const slide = slides[idx];
    if (slide && slide.dataset.title) {
      document.title = `${slide.dataset.title} · TeleFlow`;
    }
  }

  function scrollToIndex(delta) {
    const idx = currentSlideIndex();
    const next = Math.max(0, Math.min(slides.length - 1, idx + delta));
    slides[next].scrollIntoView({ behavior: "smooth", block: "start" });
  }

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

  /* -------- Speaker timer (5:00 / 7:00 zones) -------- */
  const SOFT_LIMIT_SEC = 5 * 60;
  const HARD_LIMIT_SEC = 7 * 60;
  let seconds = 0;
  let interval = null;

  function renderTimer() {
    if (!timeEl || !timerEl) return;
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    timeEl.textContent = `${pad(m)}:${pad(s)}`;
    timerEl.classList.toggle("is-running", Boolean(interval));
    timerEl.classList.toggle("is-warn", seconds >= SOFT_LIMIT_SEC && seconds < HARD_LIMIT_SEC);
    timerEl.classList.toggle("is-over", seconds >= HARD_LIMIT_SEC);
  }

  function toggleTimer() {
    if (!toggleBtn) return;
    if (interval) {
      clearInterval(interval);
      interval = null;
      toggleBtn.textContent = "старт";
    } else {
      interval = window.setInterval(() => {
        seconds += 1;
        renderTimer();
      }, 1000);
      toggleBtn.textContent = "пауза";
    }
    renderTimer();
  }

  function resetTimer() {
    if (interval) {
      clearInterval(interval);
      interval = null;
    }
    seconds = 0;
    if (toggleBtn) toggleBtn.textContent = "старт";
    renderTimer();
  }

  if (toggleBtn) toggleBtn.addEventListener("click", toggleTimer);
  if (resetBtn) resetBtn.addEventListener("click", resetTimer);
  renderTimer();

  /* -------- Keyboard -------- */
  document.addEventListener("keydown", (e) => {
    if (!deck || slides.length === 0) return;
    const t = e.target;
    if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable)) return;
    if (e.altKey || e.ctrlKey || e.metaKey) return;

    switch (e.key) {
      case "ArrowDown":
      case "ArrowRight":
      case "PageDown":
      case " ":
        e.preventDefault();
        scrollToIndex(1);
        break;
      case "ArrowUp":
      case "ArrowLeft":
      case "PageUp":
        e.preventDefault();
        scrollToIndex(-1);
        break;
      case "Home":
        e.preventDefault();
        slides[0].scrollIntoView({ behavior: "smooth", block: "start" });
        break;
      case "End":
        e.preventDefault();
        slides[slides.length - 1].scrollIntoView({ behavior: "smooth", block: "start" });
        break;
      case "t":
      case "T":
      case "е":
      case "Е":
        e.preventDefault();
        toggleTimer();
        break;
      case "f":
      case "F":
      case "а":
      case "А":
        e.preventDefault();
        if (!document.fullscreenElement) {
          document.documentElement.requestFullscreen().catch(() => {});
        } else {
          document.exitFullscreen().catch(() => {});
        }
        break;
      case "p":
      case "P":
      case "з":
      case "З":
        e.preventDefault();
        window.print();
        break;
      default:
        break;
    }
  });

  /* -------- Touch swipes -------- */
  let touchStartY = null;
  let touchStartX = null;
  deck.addEventListener(
    "touchstart",
    (e) => {
      if (e.touches && e.touches[0]) {
        touchStartY = e.touches[0].clientY;
        touchStartX = e.touches[0].clientX;
      }
    },
    { passive: true }
  );
  deck.addEventListener(
    "touchend",
    (e) => {
      if (touchStartY === null || touchStartX === null) return;
      const endTouch = (e.changedTouches && e.changedTouches[0]) || null;
      if (!endTouch) return;
      const dy = endTouch.clientY - touchStartY;
      const dx = endTouch.clientX - touchStartX;
      if (Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy)) {
        scrollToIndex(dx < 0 ? 1 : -1);
      }
      touchStartY = null;
      touchStartX = null;
    },
    { passive: true }
  );

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
