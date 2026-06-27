'use strict';

// ── Order data cache (used for reprint) ────────────────────────────────────
const _orderData = new Map();

// ── Touch scroll ───────────────────────────────────────────────────────────
let _scrollTarget = null, _scrollStartY = 0, _scrollStartTop = 0;

document.addEventListener('pointerdown', e => {
  _scrollTarget = e.target.closest('.orders-list, #history-view');
  if (_scrollTarget) {
    _scrollStartY = e.clientY;
    _scrollStartTop = _scrollTarget.scrollTop;
  }
});

document.addEventListener('pointermove', e => {
  if (_scrollTarget && e.buttons > 0) {
    const dy = _scrollStartY - e.clientY;
    requestAnimationFrame(() => {
      if (_scrollTarget) _scrollTarget.scrollTop = _scrollStartTop + dy;
    });
  }
});

document.addEventListener('pointerup',     () => { _scrollTarget = null; });
document.addEventListener('pointercancel', () => { _scrollTarget = null; });

// ── Clock ──────────────────────────────────────────────────────────────────
function updateClock() {
  const now = new Date();
  document.getElementById('clock').textContent =
    now.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
}
setInterval(updateClock, 1000);
updateClock();

// ── Tabs ───────────────────────────────────────────────────────────────────
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    const isHistory = btn.dataset.tab === 'history';
    document.getElementById('live-view').classList.toggle('hidden', isHistory);
    document.getElementById('history-view').classList.toggle('hidden', !isHistory);

    if (isHistory) fetchHistory();
  });
});

// ── Polling ────────────────────────────────────────────────────────────────
async function fetchOrders() {
  try {
    const res = await fetch('/api/orders');
    if (!res.ok) throw new Error(res.status);
    const data = await res.json();
    render(data);
    setStatus(true);
  } catch {
    setStatus(false);
  }
}

function setStatus(ok) {
  const el = document.getElementById('status');
  el.textContent = ok ? '● Connected' : '● Disconnected';
  el.className = 'status ' + (ok ? 'connected' : 'disconnected');
}

setInterval(fetchOrders, 5000);
fetchOrders();

// ── Render live ────────────────────────────────────────────────────────────
function render(data) {
  const incoming = data.NEW || [];
  const inPrep = [...(data.ACCEPTED || []), ...(data.PRINTED || [])];

  document.getElementById('new-count').textContent  = incoming.length;
  document.getElementById('prep-count').textContent = inPrep.length;

  renderList('new-orders',  incoming, cardNew);
  renderList('prep-orders', inPrep,   cardPrep);
}

function renderList(containerId, orders, template) {
  const el = document.getElementById(containerId);
  if (orders.length === 0) {
    el.innerHTML = '<div class="empty"><span class="empty-icon">✓</span>All clear</div>';
    return;
  }

  const existing = new Set([...el.querySelectorAll('.order-card')].map(n => n.dataset.id));
  const incoming = new Set(orders.map(o => String(o.id)));

  el.querySelector('.empty')?.remove();
  el.querySelectorAll('.order-card').forEach(node => {
    if (!incoming.has(node.dataset.id)) node.remove();
  });

  orders.forEach(order => {
    _orderData.set(order.id, order);
    const id = String(order.id);
    if (!existing.has(id)) {
      const placeholder = document.createElement('div');
      el.appendChild(placeholder);
      placeholder.outerHTML = template(order);
    }
  });
}

// ── History ────────────────────────────────────────────────────────────────
async function fetchHistory() {
  const el = document.getElementById('history-list');
  el.innerHTML = '<div class="empty">Loading…</div>';
  try {
    const res = await fetch('/api/orders/history');
    if (!res.ok) throw new Error(res.status);
    const data = await res.json();
    renderHistory(data.orders || []);
  } catch {
    el.innerHTML = '<div class="empty">Failed to load history</div>';
  }
}

function renderHistory(orders) {
  const el = document.getElementById('history-list');
  if (!orders.length) {
    el.innerHTML = '<div class="empty"><span class="empty-icon">📋</span>No past orders yet</div>';
    return;
  }
  const sorted = [...orders].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  sorted.forEach(order => _orderData.set(order.id, order));
  el.innerHTML = sorted.map(cardHistory).join('');
}

function cardHistory(order) {
  const statusClass = (order.status || '').toLowerCase();
  const createdAt = order.created_at ? new Date(order.created_at) : null;
  const updatedAt = order.updated_at ? new Date(order.updated_at) : null;

  const fmtDate = d => d ? d.toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit' }) : '';
  const fmtTime = d => d ? d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }) : '';

  const timeStr = createdAt
    ? `${fmtDate(createdAt)} ${fmtTime(createdAt)}${updatedAt ? ' → ' + fmtTime(updatedAt) : ''}`
    : '';

  const items = (order.metadata && order.metadata.line_items) || [];
  const itemQty = items.reduce((sum, i) => sum + (i.quantity || 1), 0);

  return `
<div class="history-card ${statusClass}" data-id="${order.id}">
  <div class="history-meta">
    <span class="history-time">${timeStr}</span>
    <div class="history-badges">
      ${badge(order.delivery_type)}
      <span class="status-badge ${statusClass}">${order.status}</span>
    </div>
  </div>
  <div class="history-header">
    <span class="order-num">#${order.woo_order_id}</span>
    <span class="order-total" style="margin:0">£${order.total_amount || '0.00'}</span>
  </div>
  <div class="customer-name">${order.customer_name || 'Customer'}</div>
  ${order.customer_phone ? `<div class="customer-phone">${order.customer_phone}</div>` : ''}
  ${order.customer_email ? `<div class="customer-phone">${order.customer_email}</div>` : ''}
  ${order.delivery_type === 'delivery' && order.delivery_address ? `<div class="address">${order.delivery_address}</div>` : ''}
  ${itemsList(order)}
  ${noteBlock(order)}
  ${itemQty > 0 ? `<div class="item-count">${itemQty} item${itemQty !== 1 ? 's' : ''}</div>` : ''}
  <div class="actions single reprint-row">
    <button class="btn btn-reprint" onclick="reprintOrder(${order.id}, this)">↺ Reprint</button>
  </div>
</div>`;
}

// ── Card templates ─────────────────────────────────────────────────────────
function badge(type) {
  const t = (type || 'collection').toLowerCase();
  return `<span class="badge ${t}">${t}</span>`;
}

function noteBlock(order) {
  const note = order.metadata?.customer_note;
  if (!note) return '';
  return `<div class="order-note"><span class="order-note-label">Note</span>${note}</div>`;
}

function itemsList(order) {
  const items = (order.metadata && order.metadata.line_items) || [];
  if (!items.length) return '';
  const rows = items.map(item => {
    const price = item.total ? `<span class="item-price">£${item.total}</span>` : '';
    return `<li>${item.quantity}× ${item.name}${price}</li>`;
  }).join('');
  return `<ul class="items">${rows}</ul>`;
}

function cardNew(order) {
  return `
<div class="order-card new" data-id="${order.id}">
  <div class="order-header">
    <span class="order-num">#${order.woo_order_id}</span>
    ${badge(order.delivery_type)}
  </div>
  <div class="customer-name">${order.customer_name || 'Customer'}</div>
  ${order.customer_phone ? `<div class="customer-phone">${order.customer_phone}</div>` : ''}
  ${order.delivery_type === 'delivery' && order.delivery_address ? `<div class="address">${order.delivery_address}</div>` : ''}
  ${itemsList(order)}
  ${noteBlock(order)}
  <div class="order-total">£${order.total_amount}</div>
  <div class="actions">
    <button class="btn btn-accept"  onclick="acceptOrder(${order.id}, this)">✓ Accept</button>
    <button class="btn btn-decline" onclick="declineOrder(${order.id}, this)">✗ Decline</button>
  </div>
  <div class="actions single reprint-row">
    <button class="btn btn-reprint" onclick="reprintOrder(${order.id}, this)">↺ Reprint</button>
  </div>
</div>`;
}

function cardPrep(order) {
  return `
<div class="order-card prep" data-id="${order.id}">
  <div class="order-header">
    <span class="order-num">#${order.woo_order_id}</span>
    ${badge(order.delivery_type)}
  </div>
  <div class="customer-name">${order.customer_name || 'Customer'}</div>
  ${itemsList(order)}
  ${noteBlock(order)}
  <div class="order-total">£${order.total_amount}</div>
  <div class="actions">
    <button class="btn btn-complete" onclick="completeOrder(${order.id}, this)">✓ Complete</button>
    <button class="btn btn-reprint"  onclick="reprintOrder(${order.id}, this)">↺ Reprint</button>
  </div>
</div>`;
}

// ── Actions ────────────────────────────────────────────────────────────────
function lockCard(btn, label) {
  const card = btn.closest('.order-card');
  card.querySelectorAll('.btn').forEach(b => { b.disabled = true; });
  btn.textContent = label;
}

function acceptOrder(id, btn) {
  showEtaModal(id, btn);
}

function declineOrder(id, btn) {
  showDeclineConfirm(id, btn);
}

async function completeOrder(id, btn) {
  lockCard(btn, 'Completing…');
  try {
    await post(`/api/orders/${id}/complete`);
    await fetchOrders();
  } catch {
    fetchOrders();
  }
}

async function reprintOrder(id, btn) {
  btn.disabled = true;
  btn.textContent = 'Printing…';
  try {
    await post(`/api/orders/${id}/reprint`, _orderData.get(id) || {});
    btn.textContent = '✓ Sent';
  } catch {
    btn.textContent = '✗ Failed';
  }
  setTimeout(() => { btn.disabled = false; btn.textContent = '↺ Reprint'; }, 2000);
}

// ── Modal ──────────────────────────────────────────────────────────────────
let _pendingBtn = null;

function closeModal() {
  document.getElementById('modal-overlay').classList.add('hidden');
  _pendingBtn = null;
}

function showModal(message) {
  const box = document.getElementById('modal-box');
  box.innerHTML = '';

  const msg = document.createElement('div');
  msg.className = 'modal-message';
  msg.textContent = message;

  const btn = document.createElement('button');
  btn.className = 'btn btn-secondary modal-btn-full';
  btn.textContent = 'Dismiss';
  btn.onclick = closeModal;

  box.appendChild(msg);
  box.appendChild(btn);
  document.getElementById('modal-overlay').classList.remove('hidden');
}

function showDeclineConfirm(id, btn) {
  _pendingBtn = btn;
  const order = _orderData.get(id);
  const wooId = order ? order.woo_order_id : '';

  const box = document.getElementById('modal-box');
  box.innerHTML = '';

  const title = document.createElement('div');
  title.className = 'modal-title';
  title.textContent = `Decline order #${wooId}?`;

  const sub = document.createElement('div');
  sub.className = 'modal-sub';
  sub.textContent = 'The customer will be refunded if they paid by card.';

  const actions = document.createElement('div');
  actions.className = 'actions';

  const cancelBtn = document.createElement('button');
  cancelBtn.className = 'btn btn-secondary';
  cancelBtn.textContent = 'Cancel';
  cancelBtn.onclick = closeModal;

  const confirmBtn = document.createElement('button');
  confirmBtn.className = 'btn btn-decline';
  confirmBtn.textContent = 'Yes, Decline';
  confirmBtn.onclick = () => confirmDecline(id);

  actions.appendChild(cancelBtn);
  actions.appendChild(confirmBtn);
  box.appendChild(title);
  box.appendChild(sub);
  box.appendChild(actions);
  document.getElementById('modal-overlay').classList.remove('hidden');
}

function showEtaModal(id, btn) {
  _pendingBtn = btn;

  const box = document.getElementById('modal-box');
  box.innerHTML = '';

  const title = document.createElement('div');
  title.className = 'modal-title';
  title.textContent = 'How long?';

  const grid = document.createElement('div');
  grid.className = 'eta-grid';

  [10, 15, 20, 25, 30, 45].forEach(mins => {
    const b = document.createElement('button');
    b.className = 'btn btn-eta';
    b.innerHTML = `${mins}<span class="eta-unit">min</span>`;
    b.onclick = () => confirmAccept(id, mins);
    grid.appendChild(b);
  });

  const cancelBtn = document.createElement('button');
  cancelBtn.className = 'btn btn-secondary modal-btn-full';
  cancelBtn.textContent = 'Cancel';
  cancelBtn.onclick = closeModal;

  box.appendChild(title);
  box.appendChild(grid);
  box.appendChild(cancelBtn);
  document.getElementById('modal-overlay').classList.remove('hidden');
}

async function confirmAccept(id, etaMinutes) {
  const btn = _pendingBtn;
  closeModal();
  lockCard(btn, 'Accepting…');
  try {
    const res = await post(`/api/orders/${id}/accept`, { eta_minutes: etaMinutes });
    if (!res.print_ok) showModal('Printer error — receipt not printed. Please reprint manually.');
    await fetchOrders();
  } catch {
    fetchOrders();
  }
}

async function confirmDecline(id) {
  const btn = _pendingBtn;
  closeModal();
  lockCard(btn, 'Declining…');
  try {
    const res = await fetch(`/api/orders/${id}/decline`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    if (res.status === 502) {
      const data = await res.json().catch(() => ({}));
      showModal(data.error || 'Refund failed — contact Orderbox support before declining.');
    }
    await fetchOrders();
  } catch {
    fetchOrders();
  }
}

function post(url, body) {
  return fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  }).then(r => { if (!r.ok) throw new Error(r.status); return r.json(); });
}
