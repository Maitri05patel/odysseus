/* ====================================================================
   ODYSSEUS — app.js  ·  Booking UI Logic
   Connects to FastAPI backend at /api/v1
   ==================================================================== */

const API = '/api/v1';

// ── Global State ─────────────────────────────────────────────
const state = {
  step: 1,
  cruise: null,
  adults: 2,
  children: 0,
  childAges: [],
  selectedExtras: [],
  promoCode: '',
  promoApplied: false,
  customer: null,
  quote: null,
  quoteTimer: null,
  quoteSeconds: 0,
};

// ── Init ──────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadCruises();
  window.addEventListener('scroll', () => {
    document.getElementById('nav').classList.toggle('scrolled', window.scrollY > 10);
  });
});

// ── Page routing ─────────────────────────────────────────────
function showPage(name) {
  ['home', 'booking', 'confirmed', 'lookup'].forEach(p => {
    const el = document.getElementById(`page-${p}`);
    if (el) el.classList.toggle('hidden', p !== name);
  });
  // Hero section visibility
  const hero = document.getElementById('page-home');
  const cruises = document.getElementById('cruises-section');
  if (name === 'home') {
    if (hero) hero.classList.remove('hidden');
    if (cruises) cruises.style.display = '';
  } else {
    if (cruises) cruises.style.display = 'none';
  }
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function scrollToCruises() {
  document.getElementById('cruises-section').scrollIntoView({ behavior: 'smooth' });
}

// ── Load Cruises ─────────────────────────────────────────────
async function loadCruises() {
  try {
    const res = await fetch(`${API}/cruises`);
    const cruises = await res.json();
    renderCruises(cruises);
  } catch (e) {
    showToast('Could not load cruises. Is the server running?', 'error');
    document.getElementById('cruise-grid').innerHTML = `
      <div class="no-cruises">
        <h3>Unable to connect</h3>
        <p>Start the API server with: <code>python -m uvicorn main:app --reload</code></p>
      </div>`;
  }
}

function renderCruises(cruises) {
  const grid = document.getElementById('cruise-grid');
  if (!cruises.length) {
    grid.innerHTML = `<div class="no-cruises"><h3>No cruises available right now</h3><p>Check back soon for new voyages.</p></div>`;
    return;
  }
  grid.innerHTML = cruises.map((c, i) => {
    const avail = c.available_capacity;
    const dotClass = avail <= 2 ? 'critical' : avail <= 5 ? 'low' : '';
    const availLabel = avail <= 2 ? `Only ${avail} left!` : `${avail} spaces left`;
    return `
    <div class="cruise-card" style="animation-delay:${i * 0.08}s" onclick="selectCruise(${JSON.stringify(JSON.stringify(c))})">
      <div class="card-header">
        <div class="card-badge">${c.destination}</div>
        <div class="card-capacity-badge">
          <span class="capacity-dot ${dotClass}"></span>
          ${availLabel}
        </div>
      </div>
      <div class="card-body">
        <div class="card-name">${c.name}</div>
        <div class="card-dest">${c.destination}</div>
        <div class="card-meta">
          <div class="meta-item">
            <span class="meta-label">Duration</span>
            <span class="meta-value">${c.duration_nights} nights</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">Departure</span>
            <span class="meta-value">${formatDate(c.departure_date)}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">Capacity</span>
            <span class="meta-value">${c.total_capacity} pax</span>
          </div>
        </div>
        <div class="card-footer">
          <div class="card-fare">
            <span class="fare-from">From</span>
            <span class="fare-amount">$${Number(c.adult_fare).toLocaleString()} <span>/ adult</span></span>
          </div>
          <button class="btn-book" onclick="event.stopPropagation(); selectCruise(${JSON.stringify(JSON.stringify(c))})">
            Book Now
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
          </button>
        </div>
      </div>
    </div>`;
  }).join('');
}

function selectCruise(cruiseJson) {
  const cruise = typeof cruiseJson === 'string' ? JSON.parse(cruiseJson) : cruiseJson;
  state.cruise = cruise;
  state.step = 1;
  state.adults = 2;
  state.children = 0;
  state.childAges = [];
  state.selectedExtras = [];
  state.promoCode = '';
  state.promoApplied = false;
  state.quote = null;
  stopQuoteTimer();

  // Update banner
  document.getElementById('banner-name').textContent = cruise.name;
  document.getElementById('banner-meta').textContent =
    `${cruise.destination} · ${cruise.duration_nights} nights · Departs ${formatDate(cruise.departure_date)}`;
  document.getElementById('banner-fare').textContent = `$${Number(cruise.adult_fare).toLocaleString()}/adult`;

  showPage('booking');
  goStep(1);
}

// ── Wizard Step Logic ─────────────────────────────────────────
function goStep(n) {
  if (n < 1 || n > 4) return;

  // Validate before leaving step 1
  if (n > 1) {
    const ageInputs = document.querySelectorAll('.child-age-input');
    let valid = true;
    ageInputs.forEach((inp, i) => {
      const age = parseInt(inp.value);
      if (isNaN(age) || age < 0 || age > 17) {
        inp.style.borderColor = 'var(--red)';
        valid = false;
      }
    });
    if (!valid) { showToast('Please enter valid ages (0–17) for all children.', 'error'); return; }
    // collect child ages
    state.childAges = Array.from(ageInputs).map(i => parseInt(i.value));
  }

  // Validate step 3 (customer details)
  if (state.step === 3 && n === 4) return; // handled by requestQuote

  state.step = n;

  // Hide all steps
  for (let i = 1; i <= 4; i++) {
    document.getElementById(`step-${i}`).classList.toggle('hidden', i !== n);
    const ps = document.getElementById(`pstep-${i}`);
    ps.classList.remove('active', 'done');
    if (i === n) ps.classList.add('active');
    else if (i < n) ps.classList.add('done');
  }

  // Progress bar
  const fills = { 1: '0%', 2: '33%', 3: '66%', 4: '100%' };
  document.getElementById('progress-fill').style.width = fills[n];

  updatePaxInfo();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ── Passenger Counters ────────────────────────────────────────
function changeAdults(delta) {
  const next = state.adults + delta;
  const maxAdults = 6 - state.children;
  if (next < 1 || next > maxAdults) return;
  state.adults = next;
  document.getElementById('adult-count').textContent = next;
  document.getElementById('adult-dec').disabled = next <= 1;
  document.getElementById('adult-inc').disabled = next >= maxAdults;
  updatePaxInfo();
}

function changeChildren(delta) {
  const next = state.children + delta;
  const maxChildren = 6 - state.adults;
  if (next < 0 || next > maxChildren) return;
  state.children = next;
  document.getElementById('child-count').textContent = next;

  // Update age inputs
  const wrap = document.getElementById('child-ages-wrap');
  if (delta > 0) {
    state.childAges.push('');
    const row = document.createElement('div');
    row.className = 'child-age-row';
    row.id = `child-row-${next}`;
    row.innerHTML = `
      <span class="child-age-label">Child ${next}</span>
      <input type="number" class="child-age-input" min="0" max="17" placeholder="Age"
        oninput="updateAgeBand(this, ${next - 1})" />
      <span class="child-age-band" id="age-band-${next - 1}"></span>`;
    wrap.appendChild(row);
  } else {
    state.childAges.pop();
    const row = document.getElementById(`child-row-${state.children + 1}`);
    if (row) row.remove();
  }

  document.getElementById('child-dec').disabled = next <= 0;
  document.getElementById('child-inc').disabled = next >= maxChildren;
  document.getElementById('adult-inc').disabled = state.adults >= (6 - next);
  updatePaxInfo();
}

function updateAgeBand(inp, idx) {
  const age = parseInt(inp.value);
  const el = document.getElementById(`age-band-${idx}`);
  inp.style.borderColor = '';
  if (isNaN(age) || inp.value === '') { el.textContent = ''; return; }
  if (age < 0 || age > 17) { inp.style.borderColor = 'var(--red)'; el.textContent = 'Invalid'; return; }
  el.textContent = age <= 4 ? 'Free 🎁' : age <= 11 ? '50% off' : '75% fare';
}

function updatePaxInfo() {
  const total = state.adults + state.children;
  const remaining = 6 - total;
  document.getElementById('pax-info-text').textContent =
    `${state.adults} adult${state.adults !== 1 ? 's' : ''} · ${state.children} child${state.children !== 1 ? 'ren' : ''} · ${total}/6 passengers · ${remaining} more allowed`;
}

// ── Extras ────────────────────────────────────────────────────
function updateExtras() {
  state.selectedExtras = Array.from(
    document.querySelectorAll('.extra-card input:checked')
  ).map(el => el.value);
}

// ── Promo ─────────────────────────────────────────────────────
function clearPromoStatus() {
  document.getElementById('promo-status').textContent = '';
  state.promoApplied = false;
}

function applyPromo() {
  const code = document.getElementById('promo-input').value.trim().toUpperCase();
  if (!code) return;
  state.promoCode = code;
  state.promoApplied = true;
  document.getElementById('promo-status').className = 'promo-status success';
  document.getElementById('promo-status').textContent = `✓ Code "${code}" will be applied at quote time.`;
}

// ── Request Quote (Step 3 → 4) ────────────────────────────────
async function requestQuote() {
  const firstName = document.getElementById('first-name').value.trim();
  const lastName  = document.getElementById('last-name').value.trim();
  const email     = document.getElementById('email').value.trim();

  if (!firstName || !lastName) { showToast('Please enter your full name.', 'error'); return; }
  if (!email || !email.includes('@')) { showToast('Please enter a valid email address.', 'error'); return; }

  // Collect child ages one more time
  const ageInputs = document.querySelectorAll('.child-age-input');
  state.childAges = Array.from(ageInputs).map(i => parseInt(i.value) || 0);

  const btn = document.querySelector('#step-3 .btn-primary');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Getting your quote…';

  try {
    // 1. Upsert customer
    const custRes = await fetch(`${API}/customers`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, first_name: firstName, last_name: lastName }),
    });
    if (!custRes.ok) throw new Error('Could not register your details.');
    state.customer = await custRes.json();

    // 2. Get quote
    const quotePayload = {
      customer_id: state.customer.id,
      cruise_id: state.cruise.id,
      num_adults: state.adults,
      child_ages: state.childAges,
      service_codes: state.selectedExtras,
      promo_code: state.promoApplied && state.promoCode ? state.promoCode : null,
    };
    const quoteRes = await fetch(`${API}/quotes`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(quotePayload),
    });
    const quoteData = await quoteRes.json();

    if (!quoteRes.ok) {
      const msg = quoteData.detail?.message || 'Could not get quote.';
      const code = quoteData.detail?.code || '';
      // Clear promo if invalid
      if (code.startsWith('PROMO_')) {
        document.getElementById('promo-status').className = 'promo-status error';
        document.getElementById('promo-status').textContent = `✗ ${msg}`;
        state.promoApplied = false;
        goStep(2);
        showToast(msg, 'error');
      } else {
        showToast(msg, 'error');
      }
      return;
    }

    state.quote = quoteData;
    goStep(4);
    renderBreakdown(quoteData.breakdown, quoteData.total_amount);
    startQuoteTimer(quoteData.expires_at);
  } catch (e) {
    showToast(e.message || 'Something went wrong. Please try again.', 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = 'Get My Quote <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>';
  }
}

// ── Render Breakdown ──────────────────────────────────────────
function renderBreakdown(bd, total) {
  const body = document.getElementById('breakdown-body');
  const rows = [];

  // Passengers
  rows.push(`<div class="bd-section">
    <div class="bd-section-label">Passengers</div>`);
  (bd.passenger_fares || []).forEach(p => {
    const label = p.passenger_type === 'ADULT'
      ? 'Adult' : `Child (age ${p.age})`;
    rows.push(`<div class="bd-row"><span class="bd-label">${label}</span><span class="bd-val">$${fmt(p.fare)}</span></div>`);
  });
  rows.push(`<div class="bd-row"><span class="bd-label">Passenger subtotal</span><span class="bd-val blue">$${fmt(bd.base_fare_total)}</span></div>`);
  rows.push(`</div>`);

  // Group discount
  if (parseFloat(bd.group_discount_amount) > 0) {
    rows.push(`<div class="bd-section">
      <div class="bd-section-label">Group Discount (${bd.group_discount_pct}% off)</div>
      <div class="bd-row"><span class="bd-label">Discount applied</span><span class="bd-val green">−$${fmt(bd.group_discount_amount)}</span></div>
    </div>`);
  }

  // Extras
  if ((bd.extras || []).length > 0) {
    rows.push(`<div class="bd-section"><div class="bd-section-label">Extras</div>`);
    bd.extras.forEach(e => {
      rows.push(`<div class="bd-row"><span class="bd-label">${e.name}</span><span class="bd-val">$${fmt(e.line_total)}</span></div>`);
    });
    rows.push(`</div>`);
  }

  // Promo
  if (parseFloat(bd.promo_discount_amount) > 0) {
    rows.push(`<div class="bd-section">
      <div class="bd-section-label">Promo Code (${bd.promo?.code || ''})</div>
      <div class="bd-row"><span class="bd-label">Discount</span><span class="bd-val green">−$${fmt(bd.promo_discount_amount)}</span></div>
    </div>`);
  }

  // Tax
  rows.push(`<div class="bd-section">
    <div class="bd-section-label">Tax & Fees</div>
    <div class="bd-row"><span class="bd-label">Tax (${(parseFloat(bd.tax_rate_pct) * 100).toFixed(0)}%)</span><span class="bd-val">$${fmt(bd.tax_amount)}</span></div>
  </div>`);

  rows.push(`<div class="bd-total">
    <span>Total</span>
    <span class="bd-total-amount">$${fmt(total)}</span>
  </div>`);

  body.innerHTML = rows.join('');

  // Summary card
  const sumRows = document.getElementById('summary-rows');
  sumRows.innerHTML = `
    <div class="summary-row"><span>${state.adults} Adult${state.adults !== 1 ? 's' : ''}</span><span>$${fmt(bd.base_fare_total)}</span></div>
    ${state.children > 0 ? `<div class="summary-row"><span>${state.children} Child${state.children !== 1 ? 'ren' : ''}</span><span>included above</span></div>` : ''}
    ${(bd.extras || []).map(e => `<div class="summary-row"><span>${e.name}</span><span>$${fmt(e.line_total)}</span></div>`).join('')}
    ${parseFloat(bd.group_discount_amount) > 0 ? `<div class="summary-row"><span>Group Discount</span><span style="color:var(--green)">−$${fmt(bd.group_discount_amount)}</span></div>` : ''}
    ${parseFloat(bd.promo_discount_amount) > 0 ? `<div class="summary-row"><span>Promo (${bd.promo?.code})</span><span style="color:var(--green)">−$${fmt(bd.promo_discount_amount)}</span></div>` : ''}
    <div class="summary-row"><span>Tax</span><span>$${fmt(bd.tax_amount)}</span></div>`;
  document.getElementById('summary-total').textContent = `$${fmt(total)}`;
}

// ── Quote Timer ───────────────────────────────────────────────
function startQuoteTimer(expiresAt) {
  stopQuoteTimer();
  const expiry = new Date(expiresAt + 'Z').getTime();
  const tick = () => {
    const remaining = Math.max(0, Math.floor((expiry - Date.now()) / 1000));
    const m = Math.floor(remaining / 60).toString().padStart(2, '0');
    const s = (remaining % 60).toString().padStart(2, '0');
    const el = document.getElementById('quote-ttl');
    if (el) el.textContent = `${m}:${s}`;
    if (remaining <= 0) {
      showToast('Your quote has expired. Please go back and get a new one.', 'error');
      document.getElementById('confirm-btn').disabled = true;
    }
  };
  tick();
  state.quoteTimer = setInterval(tick, 1000);
}
function stopQuoteTimer() {
  if (state.quoteTimer) { clearInterval(state.quoteTimer); state.quoteTimer = null; }
}

// ── Confirm Booking ───────────────────────────────────────────
async function confirmBooking() {
  const btn = document.getElementById('confirm-btn');
  btn.disabled = true;
  document.getElementById('confirm-btn-text').innerHTML = '<span class="spinner"></span> Confirming…';

  try {
    const res = await fetch(`${API}/bookings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ quote_token: state.quote.quote_token }),
    });
    const data = await res.json();

    if (!res.ok) {
      const msg = data.detail?.message || 'Booking failed. Please try again.';
      showToast(msg, 'error');
      btn.disabled = false;
      document.getElementById('confirm-btn-text').textContent = 'Confirm & Book';
      return;
    }

    stopQuoteTimer();
    showConfirmed(data);
  } catch (e) {
    showToast('Network error. Please try again.', 'error');
    btn.disabled = false;
    document.getElementById('confirm-btn-text').textContent = 'Confirm & Book';
  }
}

function showConfirmed(booking) {
  document.getElementById('confirmed-ref').textContent = booking.reference;

  // Details
  const snap = booking.snapshot || {};
  document.getElementById('confirmed-details').innerHTML = `
    <div class="confirmed-detail-row"><span class="label">Cruise</span><span class="val">${state.cruise.name}</span></div>
    <div class="confirmed-detail-row"><span class="label">Destination</span><span class="val">${state.cruise.destination}</span></div>
    <div class="confirmed-detail-row"><span class="label">Passengers</span><span class="val">${state.adults + state.children}</span></div>
    <div class="confirmed-detail-row"><span class="label">Departure</span><span class="val">${formatDate(state.cruise.departure_date)}</span></div>
    <div class="confirmed-detail-row"><span class="label">Nights</span><span class="val">${state.cruise.duration_nights}</span></div>
    <div class="confirmed-detail-row"><span class="label">Email</span><span class="val">${state.customer.email}</span></div>
    <div class="confirmed-detail-row"><span class="label">Total Charged</span><span class="val" style="color:var(--blue)">$${fmt(booking.total_charged)}</span></div>`;

  showPage('confirmed');
}

// ── Booking Lookup ────────────────────────────────────────────
async function lookupRef(refParam) {
  const ref = (refParam || document.getElementById('lookup-input').value).trim().toUpperCase();
  if (!ref) { showToast('Please enter a booking reference.', 'error'); return; }

  document.getElementById('lookup-result').innerHTML = `<div style="text-align:center;padding:20px;color:var(--text-3)"><span class="spinner" style="border-color:rgba(255,255,255,0.2);border-top-color:var(--blue);width:28px;height:28px;"></span></div>`;

  try {
    const res = await fetch(`${API}/bookings/${ref}`);
    const data = await res.json();

    if (!res.ok) {
      document.getElementById('lookup-result').innerHTML = `
        <div class="lookup-card">
          <p style="color:var(--red)">Booking "${ref}" not found. Check the reference and try again.</p>
        </div>`;
      return;
    }

    const snap = data.snapshot || {};
    const passengerRows = (data.passengers || []).map(p =>
      `<div class="lookup-row"><span class="lk-label">${p.passenger_type === 'ADULT' ? 'Adult' : `Child (age ${p.age})`}</span><span class="lk-val">$${fmt(p.fare_charged)}</span></div>`
    ).join('');

    const extraRows = (data.extras || []).map(e =>
      `<div class="lookup-row"><span class="lk-label">${e.service_name}</span><span class="lk-val">$${fmt(e.line_total)}</span></div>`
    ).join('');

    document.getElementById('lookup-result').innerHTML = `
      <div class="lookup-card">
        <div class="lookup-card-title">Booking Found</div>
        <div class="lookup-ref">${data.reference}</div>
        <div class="lookup-status">${data.status}</div>
        <div class="lookup-rows">
          ${snap.cruise_name ? `<div class="lookup-row"><span class="lk-label">Cruise</span><span class="lk-val">${snap.cruise_name}</span></div>` : ''}
          ${snap.departure_date ? `<div class="lookup-row"><span class="lk-label">Departure</span><span class="lk-val">${formatDate(snap.departure_date)}</span></div>` : ''}
          ${snap.duration_nights ? `<div class="lookup-row"><span class="lk-label">Duration</span><span class="lk-val">${snap.duration_nights} nights</span></div>` : ''}
          ${passengerRows}
          ${extraRows}
          <div class="lookup-row"><span class="lk-label">Confirmed On</span><span class="lk-val">${formatDateTime(data.created_at)}</span></div>
          <div class="lookup-row"><span class="lk-label" style="font-weight:700">Total Charged</span><span class="lk-val lookup-total">$${fmt(data.total_charged)}</span></div>
        </div>
      </div>`;
  } catch (e) {
    document.getElementById('lookup-result').innerHTML = `<div class="lookup-card"><p style="color:var(--red)">Network error. Is the API running?</p></div>`;
  }
}

// ── Helpers ───────────────────────────────────────────────────
function fmt(val) {
  return Number(val).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatDate(dateStr) {
  return new Date(dateStr + 'T00:00:00').toLocaleDateString('en-GB', {
    day: 'numeric', month: 'short', year: 'numeric'
  });
}

function formatDateTime(dtStr) {
  if (!dtStr) return '—';
  return new Date(dtStr).toLocaleDateString('en-GB', {
    day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit'
  });
}

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const icons = { error: '⚠', success: '✓', info: 'ℹ' };
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span class="toast-icon">${icons[type] || 'ℹ'}</span><span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.classList.add('fadeout');
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}
