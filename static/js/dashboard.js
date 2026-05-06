'use strict';

// ── Clock ──────────────────────────────────────────────────────────────────
function updateClock() {
  const now = new Date();
  document.getElementById('clock').textContent =
    now.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
}
setInterval(updateClock, 1000);
updateClock();

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

// ── Render ─────────────────────────────────────────────────────────────────
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
  // Preserve DOM nodes for existing orders to avoid flash on re-render
  const existing = new Set([...el.querySelectorAll('.order-card')].map(n => n.dataset.id));
  const incoming = new Set(orders.map(o => String(o.id)));

  // Remove cards no longer present
  el.querySelectorAll('.order-card').forEach(node => {
    if (!incoming.has(node.dataset.id)) node.remove();
  });

  // Add or update
  orders.forEach((order, i) => {
    const id = String(order.id);
    if (!existing.has(id)) {
      const placeholder = document.createElement('div');
      el.appendChild(placeholder);
      placeholder.outerHTML = template(order);
    }
  });
}

function badge(type) {
  const t = (type || 'collection').toLowerCase();
  return `<span class="badge ${t}">${t}</span>`;
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
  <div class="order-total">£${order.total_amount}</div>
  <div class="actions">
    <button class="btn btn-accept"  onclick="acceptOrder(${order.id}, this)">✓ Accept</button>
    <button class="btn btn-decline" onclick="declineOrder(${order.id}, this)">✗ Decline</button>
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
  <div class="order-total">£${order.total_amount}</div>
  <div class="actions single">
    <button class="btn btn-complete" onclick="completeOrder(${order.id}, this)">✓ Ready — Complete</button>
  </div>
</div>`;
}

// ── Actions ────────────────────────────────────────────────────────────────
function lockCard(btn, label) {
  const card = btn.closest('.order-card');
  card.querySelectorAll('.btn').forEach(b => { b.disabled = true; });
  btn.textContent = label;
}

async function acceptOrder(id, btn) {
  lockCard(btn, 'Accepting…');
  try {
    await post(`/api/orders/${id}/accept`, { eta_minutes: 20 });
    await fetchOrders();
  } catch {
    fetchOrders();
  }
}

async function declineOrder(id, btn) {
  lockCard(btn, 'Declining…');
  try {
    await post(`/api/orders/${id}/decline`);
    await fetchOrders();
  } catch {
    fetchOrders();
  }
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

function post(url, body) {
  return fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  }).then(r => { if (!r.ok) throw new Error(r.status); return r.json(); });
}
