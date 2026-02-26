// Consolidated, tidy script for portfolio widgets
// - Initializes Pyodide once
// - Sets up the shopping calculator
// - Sets up the journal (Python-backed)

let pyodideReadyPromise;
async function initPyodide() {
  if (!pyodideReadyPromise) {
    pyodideReadyPromise = loadPyodide();
  }
  return pyodideReadyPromise;
}

// --- Shopping Calculator ---
async function setupCalculator() {
  const addBtn = document.getElementById("add-btn");
  if (!addBtn) return; // Not on this page

  const removeBtn = document.getElementById("remove-btn");
  const clearBtn = document.getElementById("clear-btn");
  const output = document.getElementById("output");
  const itemInput = document.getElementById("item");
  const qtyInput = document.getElementById("quantity");
  const priceInput = document.getElementById("price");

  let shoppingList = [];
  try {
    const saved = localStorage.getItem("shoppingList");
    if (saved) shoppingList = JSON.parse(saved);
  } catch (e) {
    console.error("Could not load saved shopping list:", e);
  }

  function updateList() {
    if (!output) return;
    if (shoppingList.length === 0) {
      output.textContent = "Your shopping list is empty.";
      return;
    }

    const subtotal = shoppingList.reduce((sum, i) => sum + i.total, 0);
    const tax = subtotal * 0.06;
    const total = subtotal + tax;

    output.textContent = shoppingList
      .map((i, idx) => `${idx + 1}. ${i.name} - ${i.quantity} @ $${i.price.toFixed(2)} = $${i.total.toFixed(2)}`)
      .join("\n") + `\n\nSubtotal: $${subtotal.toFixed(2)}\nTax (6%): $${tax.toFixed(2)}\nTotal: $${total.toFixed(2)}`;

    try {
      localStorage.setItem("shoppingList", JSON.stringify(shoppingList));
    } catch {}
  }

  addBtn.addEventListener("click", () => {
    const name = (itemInput?.value || "").trim();
    const qty = parseFloat(qtyInput?.value || "");
    const price = parseFloat(priceInput?.value || "");

    if (!name || isNaN(qty) || isNaN(price)) {
      if (output) output.textContent = "Please fill in all fields correctly.";
      return;
    }

    shoppingList.push({ name, quantity: qty, price, total: qty * price });
    updateList();

    if (itemInput) itemInput.value = "";
    if (qtyInput) qtyInput.value = "";
    if (priceInput) priceInput.value = "";
  });

  removeBtn?.addEventListener("click", () => {
    shoppingList.pop();
    updateList();
  });

  clearBtn?.addEventListener("click", () => {
    shoppingList = [];
    updateList();
  });

  updateList();
}

// --- Journal ---
let journalInitPromise;
let journalFns; // { add_entry, view_entries, search_entries, journalPy }
async function ensureJournalReady() {
  if (journalInitPromise) return journalInitPromise;
  journalInitPromise = (async () => {
    const pyodide = await initPyodide();
    const response = await fetch("journal.py");
    const code = await response.text();
    await pyodide.runPythonAsync(code);
    const add_entry = pyodide.globals.get("add_entry");
    const view_entries = pyodide.globals.get("view_entries");
    const search_entries = pyodide.globals.get("search_entries");
    const journalPy = pyodide.globals.get("journal");
    // Load persisted entries into Python by calling add_entry
    try {
      const saved = localStorage.getItem("myJournal");
      if (saved) {
        const arr = JSON.parse(saved);
        if (Array.isArray(arr)) {
          arr.forEach(e => {
            try { add_entry(e.date || "", e.text || "", e.mood || ""); } catch {}
          });
        }
      }
    } catch (e) {
      console.error("Could not load saved journal:", e);
    }
    journalFns = { add_entry, view_entries, search_entries, journalPy };
  })();
  return journalInitPromise;
}

async function setupJournal() {
  const addBtn = document.getElementById("j-add");
  const output = document.getElementById("j-output");
  if (!addBtn || !output) return; // Not on this page

  function saveJournal() {
    try {
      if (!journalFns?.journalPy) return;
      const raw = journalFns.journalPy.toJs?.() || [];
      const normalized = Array.from(raw).map((e) => {
        if (e instanceof Map) return Object.fromEntries(e);
        if (typeof e === 'object' && e !== null) {
          // Best effort in case of plain objects
          const { date = "", text = "", mood = "" } = e;
          return { date, text, mood };
        }
        return e;
      });
      localStorage.setItem("myJournal", JSON.stringify(normalized));
    } catch {}
  }

  addBtn.addEventListener("click", async () => {
    await ensureJournalReady();
    const date = (document.getElementById("j-date")?.value || "").trim();
    const text = (document.getElementById("j-text")?.value || "").trim();
    const mood = (document.getElementById("j-mood")?.value || "").trim();
    const result = journalFns.add_entry(date, text, mood);
    output.textContent = result.toString();
    saveJournal();
    const d = document.getElementById("j-date"); if (d) d.value = "";
    const t = document.getElementById("j-text"); if (t) t.value = "";
    const m = document.getElementById("j-mood"); if (m) m.value = "";
  });

  const viewBtn = document.getElementById("j-view");
  viewBtn?.addEventListener("click", async () => {
    await ensureJournalReady();
    output.textContent = journalFns.view_entries().toString();
  });

  const searchBtn = document.getElementById("j-search-btn");
  searchBtn?.addEventListener("click", async () => {
    await ensureJournalReady();
    const keyword = (document.getElementById("j-search")?.value || "").trim();
    output.textContent = journalFns.search_entries(keyword).toString();
  });

  const clearBtn = document.getElementById("j-clear");
  clearBtn?.addEventListener("click", async () => {
    await ensureJournalReady();
    try {
      journalFns.journalPy.clear();
      localStorage.setItem("myJournal", JSON.stringify([]));
      output.textContent = "Journal cleared.";
    } catch (e) {
      console.error("Could not clear journal:", e);
    }
  });
}

// --- Slider (Projects page) ---
function setupSlider() {
  const slider = document.querySelector('.slider');
  if (!slider) return; // Not on this page

  const slidesWrap = slider.querySelector('.slides');
  const slides = Array.from(slidesWrap?.querySelectorAll('.slide') || []);
  const buttons = Array.from(slider.querySelectorAll('.slide-buttons button'));
  if (slides.length === 0 || buttons.length === 0) return;

  // Track width can be auto; use pixel-based transform for accuracy

  let activeIndex = buttons.findIndex(b => b.classList.contains('active'));
  if (activeIndex < 0) activeIndex = 0;

  let sliderWidth = slider.clientWidth;
  function showSlide(index) {
    // translate by slider width in pixels for reliable centering
    if (slidesWrap) {
      slidesWrap.style.transform = `translate3d(-${index * sliderWidth}px, 0, 0)`;
    }
    buttons.forEach((btn, i) => {
      if (i === index) btn.classList.add('active');
      else btn.classList.remove('active');
    });
    activeIndex = index;
    // When Journal becomes active (index 1), ensure it's ready and render entries
    if (index === 1) {
      ensureJournalReady()
        .then(() => {
          const out = document.getElementById('j-output');
          if (out && journalFns?.view_entries) {
            out.textContent = journalFns.view_entries().toString();
          }
        })
        .catch(() => {});
    }
  }
  showSlide(activeIndex);

  buttons.forEach((btn, i) => {
    btn.addEventListener('click', () => showSlide(i));
  });

  // Recompute position on resize to keep slide centered
  window.addEventListener('resize', () => {
    // debounce via rAF
    if (setupSlider._resizeTick) return;
    setupSlider._resizeTick = true;
    requestAnimationFrame(() => {
      sliderWidth = slider.clientWidth;
      showSlide(activeIndex);
      setupSlider._resizeTick = false;
    });
  }, { passive: true });

  // --- Swipe/Drag Navigation (pointer events) ---
  if (slidesWrap && window.PointerEvent) {
    let isPointerDown = false;
    let isDragging = false;
    let startX = 0;
    let deltaX = 0;
    let startOffset = 0;
    let moveTick = false;
    const dragThreshold = 5; // px before we treat as a drag

    function onPointerDown(e) {
      // Ignore interactions on controls/inputs
      if (e.target && e.target.closest && e.target.closest('.slide-buttons, button, input, textarea, select, a')) return;
      isPointerDown = true;
      isDragging = false;
      startX = e.clientX;
      deltaX = 0;
      startOffset = -activeIndex * slider.clientWidth;
    }

    function onPointerMove(e) {
      if (!isPointerDown) return;
      deltaX = e.clientX - startX;
      if (!isDragging && Math.abs(deltaX) > dragThreshold) {
        isDragging = true;
        slidesWrap.style.transition = 'none';
        try { slider.setPointerCapture(e.pointerId); } catch {}
      }
      if (!isDragging || moveTick) return;
      moveTick = true;
      requestAnimationFrame(() => {
        // Optional resistance at edges
        const atStart = activeIndex === 0 && deltaX > 0;
        const atEnd = activeIndex === slides.length - 1 && deltaX < 0;
        const effective = (atStart || atEnd) ? deltaX * 0.35 : deltaX;
        slidesWrap.style.transform = `translate3d(${startOffset + effective}px, 0, 0)`;
        moveTick = false;
      });
    }

    function onPointerUp(e) {
      if (!isPointerDown) return;
      isPointerDown = false;
      if (!isDragging) return; // treat as a normal click
      isDragging = false;
      slidesWrap.style.transition = '';
      const threshold = sliderWidth * 0.2;
      if (Math.abs(deltaX) > threshold) {
        const direction = deltaX < 0 ? 1 : -1; // swipe left -> next, right -> prev
        const next = Math.min(Math.max(activeIndex + direction, 0), slides.length - 1);
        showSlide(next);
      } else {
        showSlide(activeIndex);
      }
      try { slider.releasePointerCapture(e.pointerId); } catch {}
    }

    slider.addEventListener('pointerdown', onPointerDown, { passive: true });
    slider.addEventListener('pointermove', onPointerMove, { passive: true });
    slider.addEventListener('pointerup', onPointerUp, { passive: true });
    slider.addEventListener('pointercancel', onPointerUp, { passive: true });
    slider.addEventListener('pointerleave', onPointerUp, { passive: true });
  } else if (slidesWrap) {
    // Basic touch fallback
    let isDragging = false;
    let isTouching = false;
    let startX = 0;
    let deltaX = 0;
    let startOffset = 0;

    function getX(t) { return t.touches && t.touches[0] ? t.touches[0].clientX : 0; }

    slider.addEventListener('touchstart', (e) => {
      if (e.target && e.target.closest && e.target.closest('.slide-buttons, button, input, textarea, select, a')) return;
      isTouching = true;
      isDragging = false;
      startX = getX(e);
      deltaX = 0;
      startOffset = -activeIndex * slider.clientWidth;
    }, { passive: true });

    slider.addEventListener('touchmove', (e) => {
      if (!isTouching) return;
      deltaX = getX(e) - startX;
      if (!isDragging && Math.abs(deltaX) > 5) {
        isDragging = true;
        slidesWrap.style.transition = 'none';
      }
      if (!isDragging) return;
      const atStart = activeIndex === 0 && deltaX > 0;
      const atEnd = activeIndex === slides.length - 1 && deltaX < 0;
      const effective = (atStart || atEnd) ? deltaX * 0.35 : deltaX;
      slidesWrap.style.transform = `translate3d(${startOffset + effective}px, 0, 0)`;
    }, { passive: true });

    function endTouch() {
      if (!isTouching) return;
      isTouching = false;
      if (!isDragging) return; // treat as tap/click
      isDragging = false;
      slidesWrap.style.transition = '';
      const threshold = sliderWidth * 0.2;
      if (Math.abs(deltaX) > threshold) {
        const direction = deltaX < 0 ? 1 : -1;
        const next = Math.min(Math.max(activeIndex + direction, 0), slides.length - 1);
        showSlide(next);
      } else {
        showSlide(activeIndex);
      }
    }
    slider.addEventListener('touchend', endTouch);
    slider.addEventListener('touchcancel', endTouch);
  }
}

// Initialize when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
  setupCalculator().catch(err => console.error("Calculator setup failed:", err));
  setupJournal().catch(err => console.error("Journal setup failed:", err));
  setupSlider();
});
