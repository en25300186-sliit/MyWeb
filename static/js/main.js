// Auto-dismiss flash messages after 5 seconds
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.auto-dismiss').forEach(alert => {
    setTimeout(() => {
      const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
      bsAlert.close();
    }, 5000);
  });

  // Highlight active nav link
  const currentPath = window.location.pathname;
  document.querySelectorAll('.navbar-nav .nav-link').forEach(link => {
    if (link.getAttribute('href') === currentPath) {
      link.classList.add('active');
    }
  });

  // Live server clock via polling
  startServerClock();

  // Timetable notifications (runs on all pages for authenticated users)
  if (document.getElementById('todaySchedule') || window.__notificationsEnabled) {
    requestTimetableNotifications();
  }
  // Also request on dashboard
  if (document.getElementById('todaySchedule')) {
    scheduleNotificationChecks();
  }
});

// ── Live server clock ─────────────────────────────────────────────────────────
function startServerClock() {
  const timeEl = document.getElementById('serverTime');
  const dateEl = document.getElementById('serverDate');
  const dotEl  = document.getElementById('connectionDot');
  if (!timeEl) return;

  // Server time in seconds since midnight (used for local interpolation between polls)
  let serverSeconds = null;
  let lastSyncAt = null; // performance.now() at time of sync

  function syncClock() {
    const t0 = performance.now();
    fetch('/api/server-time/')
      .then(r => r.json())
      .then(data => {
        const roundTripMs = performance.now() - t0;
        // Parse server time from the formatted HH:MM:SS string
        const [hh, mm, ss] = data.time.split(':').map(Number);
        // Halve the round-trip time to estimate one-way network latency,
        // so the displayed time more closely matches the actual server time.
        serverSeconds = hh * 3600 + mm * 60 + ss + roundTripMs / 2000;
        lastSyncAt = performance.now();
        if (dateEl) dateEl.textContent = data.date + '\u00a0';
        dotEl && dotEl.classList.add('connected');
        dotEl && dotEl.classList.remove('disconnected');
      })
      .catch(() => {
        dotEl && dotEl.classList.add('disconnected');
        dotEl && dotEl.classList.remove('connected');
      });
  }

  function tick() {
    if (serverSeconds === null) return;
    const elapsed = (performance.now() - lastSyncAt) / 1000;
    const total = Math.round(serverSeconds + elapsed) % 86400;
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    const s = total % 60;
    timeEl.textContent = `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
  }

  syncClock();
  setInterval(syncClock, 30000); // Re-sync with server every 30 seconds
  setInterval(tick, 1000);        // Update display every second
}

// ── Timetable notifications ───────────────────────────────────────────────────
let notifiedIds = new Set();
let notifiedDate = null; // track which calendar date the Set belongs to

function requestTimetableNotifications() {
  if (!('Notification' in window)) return;
  if (Notification.permission === 'default') {
    // Don't auto-prompt; user must click the banner on timetable page
  }
}

function scheduleNotificationChecks() {
  checkUpcomingEvents();
  setInterval(checkUpcomingEvents, 60000); // check every minute
}

function checkUpcomingEvents() {
  if (!('Notification' in window) || Notification.permission !== 'granted') return;

  fetch('/api/today-timetable/')
    .then(r => r.json())
    .then(data => {
      const now = new Date();
      const todayStr = now.toDateString();

      // Reset notification tracking when the date rolls over midnight
      if (notifiedDate !== todayStr) {
        notifiedIds.clear();
        notifiedDate = todayStr;
      }

      data.entries.forEach(entry => {
        const [h, m] = entry.start_time.split(':').map(Number);
        const eventStart = new Date(now);
        eventStart.setHours(h, m, 0, 0);

        const diffMin = (eventStart - now) / 60000;

        // Notify when 10 minutes away (once per entry per day)
        const notifKey = `${todayStr}-${entry.id}-10`;
        if (diffMin > 0 && diffMin <= 10 && !notifiedIds.has(notifKey)) {
          notifiedIds.add(notifKey);
          const minsLeft = Math.round(diffMin);
          new Notification(`Starting in ${minsLeft} min: ${entry.title}`, {
            body: `${entry.event_type.charAt(0).toUpperCase() + entry.event_type.slice(1)} at ${entry.start_time}${entry.location ? ' — ' + entry.location : ''}`,
            icon: '/static/favicon.ico',
            tag: notifKey,
          });
        }

        // Notify when 2 minutes away
        const notifKey2 = `${todayStr}-${entry.id}-2`;
        if (diffMin > 0 && diffMin <= 2 && !notifiedIds.has(notifKey2)) {
          notifiedIds.add(notifKey2);
          new Notification(`Starting NOW: ${entry.title}`, {
            body: `Your ${entry.event_type} starts at ${entry.start_time}${entry.location ? ' in ' + entry.location : ''}`,
            icon: '/static/favicon.ico',
            tag: notifKey2,
          });
        }
      });

      // Update status labels in today's schedule on dashboard
      updateEntryStatuses(data.entries, now);
    })
    .catch(() => {});
}

function updateEntryStatuses(entries, now) {
  document.querySelectorAll('.timetable-entry').forEach(el => {
    const startStr = el.dataset.start;
    const endStr   = el.dataset.end;
    if (!startStr || !endStr) return;

    const [sh, sm] = startStr.split(':').map(Number);
    const [eh, em] = endStr.split(':').map(Number);
    const start = new Date(now); start.setHours(sh, sm, 0, 0);
    const end   = new Date(now); end.setHours(eh, em, 0, 0);
    const statusEl = el.querySelector('.entry-status');
    if (!statusEl) return;

    const diffMin = (start - now) / 60000;
    if (now >= start && now <= end) {
      statusEl.innerHTML = '<span class="badge bg-success">In Progress</span>';
      el.classList.add('entry-inprogress');
    } else if (diffMin > 0 && diffMin <= 10) {
      statusEl.innerHTML = `<span class="badge bg-warning text-dark">In ${Math.round(diffMin)} min</span>`;
    } else if (now > end) {
      statusEl.innerHTML = '<span class="badge bg-secondary">Done</span>';
      el.classList.add('entry-done');
    } else {
      const h = Math.floor(diffMin / 60);
      const m = Math.round(diffMin % 60);
      statusEl.textContent = h > 0 ? `in ${h}h ${m}m` : `in ${m}m`;
    }
  });
}

// ── Unit converter ────────────────────────────────────────────────────────────
const unitOptions = {
  length: [
    ['mm', 'Millimeters (mm)'], ['cm', 'Centimeters (cm)'], ['m', 'Meters (m)'],
    ['km', 'Kilometers (km)'], ['inch', 'Inches (in)'], ['foot', 'Feet (ft)'],
    ['yard', 'Yards (yd)'], ['mile', 'Miles (mi)'],
  ],
  mass: [
    ['mg', 'Milligrams (mg)'], ['g', 'Grams (g)'], ['kg', 'Kilograms (kg)'],
    ['tonne', 'Tonnes (t)'], ['oz', 'Ounces (oz)'], ['lb', 'Pounds (lb)'], ['ton', 'Tons (US)'],
  ],
  temperature: [
    ['celsius', 'Celsius (°C)'], ['fahrenheit', 'Fahrenheit (°F)'], ['kelvin', 'Kelvin (K)'],
  ],
  area: [
    ['mm2', 'mm²'], ['cm2', 'cm²'], ['m2', 'm²'], ['km2', 'km²'],
    ['ft2', 'ft²'], ['acre', 'Acres'], ['hectare', 'Hectares'],
  ],
  volume: [
    ['ml', 'Milliliters (mL)'], ['l', 'Liters (L)'], ['m3', 'm³'],
    ['fl_oz', 'Fluid Ounces'], ['cup', 'Cups'], ['pint', 'Pints'], ['gallon', 'Gallons'],
  ],
  speed: [
    ['m_s', 'm/s'], ['km_h', 'km/h'], ['mph', 'mph'], ['knot', 'Knots'],
  ],
  pressure: [
    ['pa', 'Pascals (Pa)'], ['kpa', 'Kilopascals (kPa)'], ['mpa', 'Megapascals (MPa)'],
    ['bar', 'Bar'], ['psi', 'PSI'], ['atm', 'Atmospheres (atm)'],
  ],
  energy: [
    ['j', 'Joules (J)'], ['kj', 'Kilojoules (kJ)'], ['mj', 'Megajoules (MJ)'],
    ['cal', 'Calories (cal)'], ['kcal', 'Kilocalories (kcal)'],
    ['kwh', 'Kilowatt-hours (kWh)'], ['btu', 'BTU'],
  ],
};

function populateUnits(selectId, options, defaultIndex) {
  const select = document.getElementById(selectId);
  if (!select) return;
  select.innerHTML = '';
  options.forEach(([value, label], i) => {
    const opt = document.createElement('option');
    opt.value = value;
    opt.textContent = label;
    if (i === defaultIndex) opt.selected = true;
    select.appendChild(opt);
  });
}

const categorySelect = document.getElementById('categorySelect');
if (categorySelect) {
  categorySelect.addEventListener('change', () => {
    const opts = unitOptions[categorySelect.value] || [];
    populateUnits('fromUnit', opts, 0);
    populateUnits('toUnit', opts, 1);
  });
  // Initialize on page load
  const opts = unitOptions[categorySelect.value] || [];
  populateUnits('fromUnit', opts, 0);
  populateUnits('toUnit', opts, 1);
}
