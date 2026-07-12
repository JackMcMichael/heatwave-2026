/* timeline.js — date slider, play/pause, and event dots.
 * Autoplay advances ~2 steps/second via requestAnimationFrame (PLAN.md
 * Phase 3) and is disabled by default when the user prefers reduced motion. */

const STEP_MS = 500; // 2 steps per second

const REDUCED_MOTION =
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export function initTimeline({ dates, events, onChange }) {
  const slider = document.getElementById("date-slider");
  const label = document.getElementById("date-label");
  const playBtn = document.getElementById("play-btn");
  const dotsEl = document.getElementById("event-dots");

  slider.max = String(dates.length - 1);

  // One dot per date that has at least one dated event.
  const eventDates = new Set(events.map((e) => e.date).filter(Boolean));
  for (const [i, d] of dates.entries()) {
    const dot = document.createElement("span");
    dot.className = "event-dot" + (eventDates.has(d) ? " has-event" : "");
    dot.style.left = `${(i / (dates.length - 1)) * 100}%`;
    dotsEl.appendChild(dot);
  }

  const fmt = new Intl.DateTimeFormat("en-GB",
    { day: "numeric", month: "long", year: "numeric" });

  let index = -1;
  let playing = false;
  let lastStep = 0;

  function setIndex(i, fromUser = false) {
    i = Math.max(0, Math.min(dates.length - 1, i));
    if (i === index) return;
    index = i;
    slider.value = String(i);
    label.textContent = fmt.format(new Date(dates[i]));
    onChange(i);
    if (fromUser) stop(); // manual scrub interrupts autoplay
  }

  function tick(now) {
    if (!playing) return;
    if (now - lastStep >= STEP_MS) {
      lastStep = now;
      if (index >= dates.length - 1) return stop();
      setIndex(index + 1);
    }
    requestAnimationFrame(tick);
  }

  function play() {
    playing = true;
    playBtn.textContent = "⏸";
    playBtn.setAttribute("aria-label", "Pause");
    if (index >= dates.length - 1) setIndex(0); // replay from the start
    lastStep = performance.now();
    requestAnimationFrame(tick);
  }

  function stop() {
    playing = false;
    playBtn.textContent = "▶";
    playBtn.setAttribute("aria-label", "Play");
  }

  slider.addEventListener("input", () => setIndex(Number(slider.value), true));
  playBtn.addEventListener("click", () => (playing ? stop() : play()));

  setIndex(0);
  if (!REDUCED_MOTION) play(); // gentle intro; a scrub or ⏸ stops it

  return { setIndex, stop };
}
