"use strict";

const heroReveal = document.getElementById("hero-reveal");
const heroCompare = document.querySelector(".hero-compare");
if (heroReveal && heroCompare) {
  const comparisonViews = {
    cloud: {label: "LiDAR point cloud", note: "Top-down projection of the source LiDAR points. All comparisons share the same map extent and scale."},
    lidar: {label: "LiDAR-only", note: "Measured wall and column reconstruction before joint correction and conditional completion."},
    design: {label: "Design CAD", note: "Author-annotated original design at its archived initial global registration, before refined alignment and local correction. Red circles mark matched discrepancy regions; registration residuals are not necessarily physical design changes.", alt: "Author-annotated design CAD of the ICPARK scene with red circles marking matched discrepancy regions"},
    hough: {label: "P. Hough", note: "Probabilistic Hough baseline from the manuscript's frozen full-scene linework."},
    contour: {label: "DP-Contour", note: "Douglas–Peucker contour baseline from the manuscript's frozen full-scene linework."},
    ransac: {label: "RANSAC", note: "RANSAC line baseline from the manuscript's frozen full-scene linework."},
    skeleton: {label: "Morph-Skel", note: "Morphological skeleton baseline from the manuscript's frozen full-scene linework."},
    lsd: {label: "LSD", note: "Line Segment Detector baseline from the manuscript's frozen full-scene linework."},
    fld: {label: "FLD", note: "Fast Line Detector baseline from the manuscript's frozen full-scene linework."},
    edlines: {label: "EDLines", note: "EDLines baseline from the manuscript's frozen full-scene linework."}
  };
  let currentComparison = "cloud";
  let requestedComparison = 0;
  const beforeImage = heroCompare.querySelector(".compare-before");
  const beforeLabel = heroCompare.querySelector(".before-label");
  const comparisonNote = document.getElementById("comparison-note");
  const comparisonButtons = Array.from(document.querySelectorAll("[data-comparison]"));
  heroReveal.disabled = false;
  const updateReveal = () => {
    const amount = Math.max(0, Math.min(100, Number(heroReveal.value)));
    heroCompare.style.setProperty("--reveal", amount + "%");
    heroReveal.setAttribute("aria-valuetext", amount + "% " + comparisonViews[currentComparison].label + ", " + (100 - amount) + "% complete reconstruction");
  };
  comparisonButtons.forEach(button => {
    button.disabled = false;
    button.addEventListener("click", async () => {
      const key = button.dataset.comparison;
      const view = comparisonViews[key];
      if (!view) return;
      const request = ++requestedComparison;
      heroCompare.setAttribute("aria-busy", "true");
      try {
        const image = new Image();
        image.src = "assets/compare-" + key + ".webp";
        await image.decode();
        if (request !== requestedComparison) return;
        beforeImage.src = image.src;
        beforeImage.alt = view.alt || (view.label + " of the ICPARK scene, using the same map extent as complete reconstruction");
        beforeLabel.textContent = view.label;
        comparisonNote.textContent = view.note;
        currentComparison = key;
        comparisonButtons.forEach(option => {
          const active = option === button;
          option.classList.toggle("active", active);
          option.setAttribute("aria-pressed", String(active));
        });
        heroReveal.setAttribute("aria-label", "Position the divider between " + view.label + " and complete reconstruction");
        heroReveal.value = "48";
        updateReveal();
      } catch (_error) {
        if (request === requestedComparison) comparisonNote.textContent = "This view could not be loaded. The previous comparison is retained; please try again.";
      } finally {
        if (request === requestedComparison) heroCompare.setAttribute("aria-busy", "false");
      }
    });
  });
  const revealAtPointer = event => {
    const bounds = heroCompare.getBoundingClientRect();
    heroReveal.value = String(Math.round((event.clientX - bounds.left) / bounds.width * 100));
    updateReveal();
  };
  let draggingPointer = null;
  heroReveal.addEventListener("input", updateReveal);
  heroCompare.classList.add("is-interactive");
  heroCompare.addEventListener("pointerdown", event => {
    if (!event.isPrimary || event.button !== 0) return;
    draggingPointer = event.pointerId;
    heroCompare.setPointerCapture(event.pointerId);
    revealAtPointer(event);
  });
  heroCompare.addEventListener("pointermove", event => {
    if (event.pointerId === draggingPointer) revealAtPointer(event);
  });
  const finishDrag = event => {
    if (event.pointerId === draggingPointer) draggingPointer = null;
  };
  heroCompare.addEventListener("pointerup", finishDrag);
  heroCompare.addEventListener("pointercancel", finishDrag);
  heroCompare.addEventListener("lostpointercapture", finishDrag);
  heroCompare.querySelectorAll("img").forEach(img => {
    img.draggable = false;
  });
  updateReveal();
}

const comparisonShowcase = document.querySelector(".comparison-showcase");
const fullscreenButton = document.querySelector(".fullscreen-button");
if (comparisonShowcase && fullscreenButton) {
  fullscreenButton.hidden = false;
  let pendingFullscreen = false;
  const isExpanded = () => document.fullscreenElement === comparisonShowcase || comparisonShowcase.classList.contains("is-expanded");
  const syncFullscreen = () => {
    const active = isExpanded();
    fullscreenButton.setAttribute("aria-pressed", String(active));
    fullscreenButton.setAttribute("aria-label", active ? "Exit comparison fullscreen" : "Enter comparison fullscreen");
    fullscreenButton.title = active ? "Exit fullscreen (Esc)" : "Enter fullscreen";
    fullscreenButton.querySelector("span").textContent = active ? "Exit fullscreen" : "Fullscreen";
    document.body.classList.toggle("comparison-expanded", active);
    if (active) fullscreenButton.focus({preventScroll: true});
  };
  const closeFallback = () => {
    comparisonShowcase.classList.remove("is-expanded");
    comparisonShowcase.removeAttribute("role");
    comparisonShowcase.removeAttribute("aria-modal");
    syncFullscreen();
    fullscreenButton.focus({preventScroll: true});
  };
  fullscreenButton.addEventListener("click", async () => {
    if (pendingFullscreen) return;
    if (comparisonShowcase.classList.contains("is-expanded")) {
      closeFallback();
      return;
    }
    pendingFullscreen = true;
    try {
      if (document.fullscreenElement === comparisonShowcase) {
        await document.exitFullscreen();
      } else {
        try {
          if (!comparisonShowcase.requestFullscreen) throw new Error("Native fullscreen unavailable");
          await comparisonShowcase.requestFullscreen();
        } catch (_error) {
          comparisonShowcase.classList.add("is-expanded");
          comparisonShowcase.setAttribute("role", "dialog");
          comparisonShowcase.setAttribute("aria-modal", "true");
        }
      }
    } finally {
      pendingFullscreen = false;
      syncFullscreen();
    }
  });
  document.addEventListener("fullscreenchange", syncFullscreen);
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && document.fullscreenElement === comparisonShowcase) {
      event.preventDefault();
      document.exitFullscreen().catch(() => syncFullscreen());
      return;
    }
    if (!comparisonShowcase.classList.contains("is-expanded")) return;
    if (event.key === "Escape") {
      event.preventDefault();
      closeFallback();
    } else if (event.key === "Tab") {
      const controls = [fullscreenButton, heroReveal].filter(element => element && !element.disabled);
      const first = controls[0], last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
  });
}

// Progressive enhancement: paper links and the default region work without JS.
const regionNotes = {
  1: "eva-01 · Wall F1: 97.75% · Reference wall length: 18.29 m.",
  2: "eva-02 · Wall F1: 98.74% · Reference wall length: 19.21 m.",
  3: "eva-03 · Wall F1: 96.50% · Reference wall length: 39.57 m.",
  4: "eva-04 · Wall F1: 81.95% · Reference wall length: 189.34 m (about 71.07% of the total)."
};

document.querySelectorAll("[data-region]").forEach(button => {
  button.addEventListener("click", () => {
    const region = button.dataset.region;
    document.querySelectorAll("[data-region]").forEach(tab => {
      const selected = tab === button;
      tab.classList.toggle("active", selected);
      tab.setAttribute("aria-pressed", String(selected));
    });
    document.querySelectorAll("#roi-comparison [data-stage]").forEach(img => {
      img.src = "assets/roi-" + region + "-stage-" + img.dataset.stage + ".webp";
      img.alt = img.alt.replace(/ROI \d+/, "ROI " + region);
    });
    document.getElementById("region-note").textContent = regionNotes[region];
  });
});

const dialog = document.querySelector(".image-dialog");
const dialogImage = document.getElementById("dialog-image");
const dialogCaption = document.getElementById("dialog-caption");
document.querySelectorAll("[data-zoom]").forEach(button => {
  button.addEventListener("click", () => {
    const img = button.querySelector("img");
    if (!dialog.showModal) {
      window.open(img.src, "_blank", "noopener");
      return;
    }
    dialogImage.src = img.currentSrc || img.src;
    dialogImage.alt = img.alt;
    dialogCaption.textContent = img.alt;
    dialog.showModal();
    document.body.classList.add("dialog-open");
  });
});
dialog.querySelector(".close-dialog").addEventListener("click", () => dialog.close());
dialog.addEventListener("click", event => {
  const rect = dialog.getBoundingClientRect();
  if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close();
});
dialog.addEventListener("close", () => document.body.classList.remove("dialog-open"));

if ("IntersectionObserver" in window) {
  const links = Array.from(document.querySelectorAll(".nav-links a"));
  const observer = new IntersectionObserver(entries => {
    const visible = entries.filter(entry => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio);
    if (!visible.length) return;
    const activeId = visible[0].target.id;
    links.forEach(link => {
      const active = link.hash === "#" + activeId;
      link.classList.toggle("active", active);
      if (active) link.setAttribute("aria-current", "location");
      else link.removeAttribute("aria-current");
    });
  }, {rootMargin: "-70px 0px -55% 0px", threshold: [0, .1, .3, .6]});
  document.querySelectorAll("main section[id]").forEach(section => observer.observe(section));
}
