'use strict';

// ── State ────────────────────────────────────────────────────────────────────

const state = {
  rings: [],
  selected: new Set(),
  cyInstances: [],
  conversationId: null,
  loadResult: null,
  askedCount: 0,
};

// ── Risk helpers ─────────────────────────────────────────────────────────────

function riskColor(score) {
  if (score >= 0.7) return '#d63031';
  if (score >= 0.4) return '#e17055';
  return '#00b894';
}

function riskBarHtml(score, label) {
  const filled = Math.round(score * 5);
  const color = riskColor(score);
  const squares = Array.from({ length: 5 }, (_, i) =>
    `<span class="risk-sq" style="background:${i < filled ? color : '#e0e0e0'}"></span>`
  ).join('');
  return `<span class="risk-bar">${squares}</span><span class="risk-label">${escHtml(label)}</span>`;
}

function riskPercent(score) {
  return `${Math.round((Number(score) || 0) * 100)}`;
}

function topologyLabel(topology) {
  return {
    star: 'Hub pattern',
    ring: 'Circular flow',
    chain: 'Layering path',
    mesh: 'Dense mesh',
  }[topology] || 'Cluster';
}

function topologyMeaning(topology) {
  return {
    star: 'One account is connected to many peers',
    ring: 'Transfers close back on themselves',
    chain: 'Funds move through a sequence of accounts',
    mesh: 'Many accounts share repeated connections',
  }[topology] || 'Connected accounts require review';
}

function evidenceHeadline(metrics) {
  const accounts = `${metrics.nodeCount.toLocaleString()} accounts`;
  if (metrics.hubCount >= 3) return `${metrics.hubCount} hub accounts`;
  if (metrics.maxDegree >= 5) return `Hub-led - ${accounts}`;
  if (metrics.densityLabel === 'High') return `High density - ${accounts}`;
  if (metrics.nodeCount >= 100) return `${accounts} - ${metrics.densityLabel} density`;
  if (metrics.edgeCount >= metrics.nodeCount) return `${metrics.edgeCount.toLocaleString()} links - ${accounts}`;
  return `Connected - ${accounts}`;
}

function evidenceMeaning(ring, metrics) {
  const sharedIds = Array.isArray(ring.shared_ids) && ring.shared_ids.length
    ? ring.shared_ids.join(', ')
    : 'shared identifiers';

  if (metrics.hubCount >= 3) {
    return `${metrics.hubCount} hub accounts concentrate the connections`;
  }
  if (metrics.maxDegree >= 5) {
    return `Highest-degree account connects to ${metrics.maxDegree} peers`;
  }
  if (metrics.densityLabel === 'High') {
    return `High connection density across ${metrics.nodeCount.toLocaleString()} accounts`;
  }
  if (metrics.nodeCount >= 100) {
    return `${metrics.nodeCount.toLocaleString()} accounts linked by ${sharedIds}`;
  }
  if (metrics.edgeCount >= metrics.nodeCount) {
    return `${metrics.edgeCount.toLocaleString()} relationships among ${metrics.nodeCount.toLocaleString()} accounts`;
  }
  return topologyMeaning(ring.topology);
}

function ringMetrics(ring) {
  const nodes = Array.isArray(ring.nodes) ? ring.nodes : [];
  const edges = Array.isArray(ring.edges) ? ring.edges : [];
  const nodeCount = Number(ring.node_count) || nodes.length;
  const degrees = {};

  nodes.forEach(node => {
    const data = node.data || {};
    degrees[data.id] = Number(data.degree) || 0;
  });
  edges.forEach(edge => {
    const data = edge.data || {};
    degrees[data.source] = Math.max(degrees[data.source] || 0, 1);
    degrees[data.target] = Math.max(degrees[data.target] || 0, 1);
  });

  const degreeVals = Object.values(degrees);
  const maxDegree = degreeVals.length ? Math.max(...degreeVals) : 0;
  const hubCount = degreeVals.filter(deg => deg >= Math.max(3, maxDegree * 0.5)).length;
  const possibleEdges = Math.max(1, (nodeCount * (nodeCount - 1)) / 2);
  const density = edges.length / possibleEdges;
  const densityLabel = density >= 0.12 ? 'High' : density >= 0.04 ? 'Med' : 'Low';
  const topRisk = nodes.reduce((max, node) => Math.max(max, Number((node.data || {}).risk_score) || 0), Number(ring.risk_score) || 0);

  return {
    density,
    densityLabel,
    edgeCount: edges.length,
    hubCount,
    maxDegree,
    nodeCount,
    shownCount: Math.min(nodes.length, 40),
    topRisk,
  };
}

// ── Topology SVG icon (for table column) ─────────────────────────────────────

function topologyIcon(ring) {
  const w = 36, h = 36, cx = 18, cy = 18, r = 11;
  const color = riskColor(ring.risk_score);
  const n = ring.node_count;

  if (ring.topology === 'star') {
    const spokes = Math.min(8, n - 1);
    const lines = Array.from({ length: spokes }, (_, i) => {
      const a = (i * 2 * Math.PI) / spokes;
      const x = (cx + r * Math.cos(a)).toFixed(1);
      const y = (cy + r * Math.sin(a)).toFixed(1);
      return `<line x1="${cx}" y1="${cy}" x2="${x}" y2="${y}" stroke="${color}" stroke-width="1.5"/>
              <circle cx="${x}" cy="${y}" r="2" fill="${color}" opacity="0.7"/>`;
    }).join('');
    return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">${lines}
      <circle cx="${cx}" cy="${cy}" r="4" fill="${color}"/></svg>`;
  }

  if (ring.topology === 'ring') {
    const dots = Math.min(10, n);
    const dotsSvg = Array.from({ length: dots }, (_, i) => {
      const a = (i * 2 * Math.PI) / dots - Math.PI / 2;
      const x = (cx + r * Math.cos(a)).toFixed(1);
      const y = (cy + r * Math.sin(a)).toFixed(1);
      return `<circle cx="${x}" cy="${y}" r="2.5" fill="${color}"/>`;
    }).join('');
    return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">
      <circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${color}" stroke-width="1.5" opacity="0.35"/>
      ${dotsSvg}</svg>`;
  }

  if (ring.topology === 'mesh') {
    const pts = 7;
    const coords = Array.from({ length: pts }, (_, i) => {
      if (i === 0) return { x: cx, y: cy };
      const a = ((i - 1) * 2 * Math.PI) / (pts - 1) - Math.PI / 2;
      return { x: cx + r * Math.cos(a), y: cy + r * Math.sin(a) };
    });
    const lines = [];
    for (let i = 1; i < coords.length; i++) {
      lines.push(`<line x1="${cx}" y1="${cy}" x2="${coords[i].x.toFixed(1)}" y2="${coords[i].y.toFixed(1)}" stroke="${color}" stroke-width="1.2" opacity="0.55"/>`);
      if (i < coords.length - 1) {
        lines.push(`<line x1="${coords[i].x.toFixed(1)}" y1="${coords[i].y.toFixed(1)}" x2="${coords[i + 1].x.toFixed(1)}" y2="${coords[i + 1].y.toFixed(1)}" stroke="${color}" stroke-width="1.2" opacity="0.35"/>`);
      }
    }
    const dots = coords.map(p => `<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="2.4" fill="${color}"/>`).join('');
    return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">${lines.join('')}${dots}</svg>`;
  }

  // chain
  const pts = Math.min(5, n);
  const step = (w - 8) / Math.max(pts - 1, 1);
  const chainSvg = Array.from({ length: pts }, (_, i) => {
    const x = (4 + i * step).toFixed(1);
    const y = i % 2 === 0 ? cy - 5 : cy + 5;
    const prev = i > 0 ? `<line x1="${(4 + (i - 1) * step).toFixed(1)}" y1="${(i - 1) % 2 === 0 ? cy - 5 : cy + 5}"
      x2="${x}" y2="${y}" stroke="${color}" stroke-width="1.5"/>` : '';
    return `${prev}<circle cx="${x}" cy="${y}" r="2.5" fill="${color}"/>`;
  }).join('');
  return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">${chainSvg}</svg>`;
}

// ── Cytoscape layout selection ────────────────────────────────────────────────

function positionNodesForTopology(nodes, topology, metrics) {
  if (!['star', 'ring', 'chain'].includes(topology)) return nodes;

  const n = Math.max(nodes.length, 1);
  const center = { x: 180, y: 90 };

  if (topology === 'ring') {
    const radius = n <= 8 ? 60 : 72;
    return nodes.map((node, i) => {
      const angle = (i * 2 * Math.PI) / n - Math.PI / 2;
      return {
        ...node,
        position: {
          x: center.x + Math.cos(angle) * radius,
          y: center.y + Math.sin(angle) * radius,
        },
      };
    });
  }

  if (topology === 'chain') {
    const step = 42;
    const offset = ((n - 1) * step) / 2;
    return nodes.map((node, i) => ({
      ...node,
      position: {
        x: center.x + i * step - offset,
        y: center.y + (i % 2 === 0 ? -18 : 18),
      },
    }));
  }

  const hubId = nodes.find(node => node.data.is_hub)?.data.id || nodes[0].data.id;
  const radius = n <= 10 ? 62 : 78;
  const outerNodes = nodes.filter(node => node.data.id !== hubId);
  return nodes.map(node => {
    if (node.data.id === hubId) {
      return { ...node, position: center };
    }
    const i = outerNodes.findIndex(outer => outer.data.id === node.data.id);
    const angle = (i * 2 * Math.PI) / Math.max(outerNodes.length, 1) - Math.PI / 2;
    const degreeBoost = metrics.maxDegree > 8 ? 1.05 : 1;
    return {
      ...node,
      position: {
        x: center.x + Math.cos(angle) * radius * degreeBoost,
        y: center.y + Math.sin(angle) * radius * degreeBoost,
      },
    };
  });
}

function pickLayout(nodes, edges, topology) {
  if (!nodes.length) return { name: 'grid' };
  if (['star', 'ring', 'chain'].includes(topology)) {
    return { name: 'preset', fit: true, padding: 24, animate: false };
  }

  const degrees = {};
  edges.forEach(e => {
    degrees[e.data.source] = (degrees[e.data.source] || 0) + 1;
    degrees[e.data.target] = (degrees[e.data.target] || 0) + 1;
  });
  const vals = Object.values(degrees);
  if (!vals.length) return { name: 'circle' };
  const avg = vals.reduce((a, b) => a + b, 0) / vals.length;
  const maxDeg = Math.max(...vals);
  if (maxDeg > Math.max(avg * 2.5, 4)) {
    return { name: 'cose', idealEdgeLength: 50, nodeRepulsion: 4500, animate: false };
  }
  if (edges.length === nodes.length && maxDeg <= 2) {
    return { name: 'circle', animate: false };
  }
  return {
    name: 'concentric',
    concentric: node => (Number(node.data('degree')) || 1) * 10 + (Number(node.data('risk_score')) || 0) * 8,
    levelWidth: () => 12,
    minNodeSpacing: 10,
    animate: false,
  };
}

// ── Cytoscape ring card ───────────────────────────────────────────────────────

function buildRingCard(ring, idx) {
  const card = document.createElement('div');
  card.className = 'ring-card';
  card.dataset.ringId = ring.ring_id;
  card.dataset.testid = `ring-card-${ring.ring_id}`;

  const vol = ring.volume ? `$${ring.volume.toLocaleString()}` : '';
  const metrics = ringMetrics(ring);
  const sharedIds = Array.isArray(ring.shared_ids) && ring.shared_ids.length
    ? ring.shared_ids.slice(0, 3)
    : ['No shared id'];
  const hiddenCount = Math.max(0, metrics.nodeCount - metrics.shownCount);
  const headline = evidenceHeadline(metrics);
  const meaning = evidenceMeaning(ring, metrics);
  const graphNote = hiddenCount > 0
    ? `Top ${metrics.shownCount} risk-ranked accounts shown, ${hiddenCount} more in cluster`
    : `${metrics.shownCount} accounts shown`;

  card.innerHTML = `
    <div class="ring-card-header">
      <div>
        <div class="ring-card-title">${escHtml(ring.ring_id)}</div>
        <div class="ring-card-subtitle">${escHtml(headline)}</div>
      </div>
      <div class="ring-card-risk" style="color:${riskColor(ring.risk_score)}">
        <strong>${escHtml(riskPercent(ring.risk_score))}</strong>
        <span>risk</span>
      </div>
    </div>
    <div class="ring-card-signals">
      <div class="risk-mini-meter" aria-label="Risk score ${escHtml(riskPercent(ring.risk_score))} percent">
        <span style="width:${escHtml(riskPercent(ring.risk_score))}%; background:${riskColor(ring.risk_score)}"></span>
      </div>
      <div class="ring-card-insights">
        <span class="metric-chip" tabindex="0" data-tip="Number of accounts assigned to this detected fraud-ring community.">
          <strong>${escHtml(metrics.nodeCount.toLocaleString())}</strong> accounts
        </span>
        <span class="metric-chip" tabindex="0" data-tip="Accounts with the most graph connections in this cluster. Hubs often deserve first review.">
          <strong>${escHtml(metrics.hubCount)}</strong> hubs
        </span>
        <span class="metric-chip" tabindex="0" data-tip="How connected the cluster is relative to its size. High density means repeated shared relationships.">
          <strong>${escHtml(metrics.densityLabel)}</strong> density
        </span>
        ${vol ? `<span class="metric-chip" tabindex="0" data-tip="Total transaction volume represented by accounts in this ring.">
          <strong>${escHtml(vol)}</strong> volume
        </span>` : ''}
      </div>
      <div class="shared-id-chips">
        ${sharedIds.map(id => `<span class="shared-id-chip">${escHtml(id)}</span>`).join('')}
      </div>
    </div>
    <div class="ring-graph-wrap">
      <div class="ring-card-canvas" id="cy-card-${idx}" data-testid="ring-graph-${escHtml(ring.ring_id)}"></div>
      <div class="graph-meaning">${escHtml(meaning)}</div>
      <div class="graph-scope">${escHtml(graphNote)}</div>
    </div>
  `;

  card.addEventListener('click', () => toggleRing(ring.ring_id));
  return card;
}

function initCardCytoscape(ring, idx) {
  const container = document.getElementById(`cy-card-${idx}`);
  if (!container || typeof cytoscape === 'undefined') return;

  const metrics = ringMetrics(ring);
  const topRiskCutoff = Math.max(0.8, metrics.topRisk - 0.05);
  const displayNodes = positionNodesForTopology(ring.nodes.slice(0, 40).map(node => {
    const data = { ...(node.data || {}) };
    data.degree = Number(data.degree) || 1;
    data.is_hub = data.degree === metrics.maxDegree && metrics.maxDegree >= 3;
    data.is_priority = (Number(data.risk_score) || 0) >= topRiskCutoff;
    return { data };
  }), ring.topology, metrics);
  const displayNodeIds = new Set(displayNodes.map(n => n.data.id));
  const displayEdges = ring.edges.filter(e => displayNodeIds.has(e.data.source) && displayNodeIds.has(e.data.target));

  const cy = cytoscape({
    container,
    elements: [...displayNodes, ...displayEdges],
    style: [
      {
        selector: 'node',
        style: {
          'background-color': ele => riskColor(ele.data('risk_score') || 0.3),
          'width': ele => Math.min(24, Math.max(7, 7 + (ele.data('degree') || 1) * 2.2)),
          'height': ele => Math.min(24, Math.max(7, 7 + (ele.data('degree') || 1) * 2.2)),
          'border-width': ele => ele.data('is_priority') || ele.data('is_hub') ? 2 : 0,
          'border-color': ele => ele.data('is_hub') ? '#111827' : '#ffffff',
          'opacity': ele => ele.data('is_priority') ? 1 : 0.82,
          'label': '',
        },
      },
      {
        selector: 'edge',
        style: {
          'width': ele => Math.min(3, Math.max(1, Number(ele.data('weight')) || 1)),
          'line-color': '#98a2b3',
          'opacity': 0.65,
          'curve-style': 'bezier',
        },
      },
    ],
    layout: pickLayout(displayNodes, displayEdges, ring.topology),
    userZoomingEnabled: false,
    userPanningEnabled: false,
    autoungrabify: true,
    boxSelectionEnabled: false,
  });

  state.cyInstances.push(cy);
  return cy;
}

// ── Selection sync ────────────────────────────────────────────────────────────

function toggleRing(ringId) {
  if (state.selected.has(ringId)) {
    state.selected.delete(ringId);
  } else {
    state.selected.add(ringId);
  }
  updateSelectionUI();
}

function setAllRingsSelected(selected) {
  state.selected.clear();
  if (selected) {
    state.rings.forEach(ring => state.selected.add(ring.ring_id));
  }
  updateSelectionUI();
}

function updateSelectionUI() {
  const count = state.selected.size;

  // sync ring cards
  document.querySelectorAll('.ring-card').forEach(card => {
    card.classList.toggle('selected', state.selected.has(card.dataset.ringId));
  });

  // sync table checkboxes
  document.querySelectorAll('#results-tbody tr').forEach(row => {
    const cb = row.querySelector('input[type=checkbox]');
    const selected = state.selected.has(row.dataset.ringId);
    if (cb) cb.checked = selected;
    row.classList.toggle('selected', selected);
  });

  document.getElementById('selected-count').textContent =
    `${count} selected`;
  document.getElementById('load-btn').disabled = count === 0;

  const selectAll = document.getElementById('select-all-rings');
  if (selectAll) {
    selectAll.disabled = state.rings.length === 0;
    selectAll.checked = state.rings.length > 0 && count === state.rings.length;
    selectAll.indeterminate = count > 0 && count < state.rings.length;
  }
}

// ── Screen 1: Search ─────────────────────────────────────────────────────────

document.getElementById('search-form').addEventListener('submit', async e => {
  e.preventDefault();
  const form = e.target;
  const signalType = form.elements.signal_type.value;
  const filters = {
    date_range: form.elements.date_range.value,
    min_amount: form.elements.min_amount.value || null,
    max_nodes: form.elements.max_nodes.value || null,
  };

  const btn = document.getElementById('search-btn');
  btn.textContent = 'Searching…';
  btn.disabled = true;

  try {
    state.rings = await postJson('/api/search', { signal_type: signalType, filters });
    state.selected.clear();
    renderResults(state.rings);
  } catch (error) {
    showError(error);
  } finally {
    btn.textContent = 'Search Neo4j →';
    btn.disabled = false;
  }
});

function renderResults(rings) {
  const panel = document.getElementById('results-panel');
  panel.classList.remove('hidden');

  document.getElementById('ring-count').textContent = `${rings.length} rings`;

  const nodeTotal = rings.reduce((s, r) => s + r.node_count, 0);
  document.getElementById('graph-summary').textContent =
    `${rings.length} clusters · ${nodeTotal} nodes total`;

  // destroy previous Cytoscape instances
  state.cyInstances.forEach(cy => cy.destroy());
  state.cyInstances = [];

  // graph grid
  const grid = document.getElementById('graph-grid');
  grid.innerHTML = '';
  rings.forEach((ring, i) => {
    const card = buildRingCard(ring, i);
    grid.appendChild(card);
  });
  // defer Cytoscape init so DOM is painted
  requestAnimationFrame(() => {
    rings.forEach((ring, i) => initCardCytoscape(ring, i));
  });

  // table
  const tbody = document.getElementById('results-tbody');
  tbody.innerHTML = '';
  rings.forEach(ring => {
    const tr = document.createElement('tr');
    tr.dataset.ringId = ring.ring_id;
    tr.dataset.testid = `ring-row-${ring.ring_id}`;
    const sharedIds = Array.isArray(ring.shared_ids) ? ring.shared_ids.map(escHtml).join(', ') : '';
    tr.innerHTML = `
      <td><input type="checkbox" data-ring-id="${escHtml(ring.ring_id)}" data-testid="ring-checkbox-${escHtml(ring.ring_id)}"></td>
      <td>${topologyIcon(ring)}</td>
      <td style="font-weight:600">${escHtml(ring.ring_id)}</td>
      <td>${escHtml(ring.node_count.toLocaleString())}</td>
      <td>${ring.volume ? '$' + escHtml(ring.volume.toLocaleString()) : '—'}</td>
      <td style="color:#555">${sharedIds || '—'}</td>
      <td>${riskBarHtml(ring.risk_score, ring.risk_label)}</td>
    `;
    tbody.appendChild(tr);

    tr.querySelector('input[type=checkbox]').addEventListener('change', () => {
      toggleRing(ring.ring_id);
    });
    tr.addEventListener('click', e => {
      if (e.target.tagName !== 'INPUT') toggleRing(ring.ring_id);
    });
  });

  updateSelectionUI();
  panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

document.getElementById('load-btn').addEventListener('click', () => {
  if (state.selected.size === 0) return;
  showScreen(2);
  startLoad([...state.selected]);
});

document.getElementById('select-all-rings').addEventListener('change', e => {
  setAllRingsSelected(e.target.checked);
});

// ── Screen 2: Load ────────────────────────────────────────────────────────────

document.getElementById('back-to-search').addEventListener('click', e => {
  e.preventDefault(); showScreen(1);
});
document.getElementById('continue-btn').addEventListener('click', () => {
  buildDataPanel();
  showScreen(3);
});

async function startLoad(ringIds) {
  const titleEl = document.getElementById('load-title');
  const ringsEl = document.getElementById('load-rings');
  titleEl.textContent = `Loading ${ringIds.length} fraud ring${ringIds.length > 1 ? 's' : ''} into Databricks Lakehouse`;
  ringsEl.textContent = ringIds.join(' · ');

  document.getElementById('preview-section').classList.add('hidden');
  document.getElementById('continue-btn').style.display = 'none';
  document.getElementById('progress-bar').style.width = '0%';
  document.getElementById('progress-pct').textContent = '0%';

  const fetchPromise = postJson('/api/load', { ring_ids: ringIds });

  // animate steps optimistically while fetch is in flight
  const stepLabels = [
    'Accounts extracted from Neo4j',
    'Merchants extracted from Neo4j',
    'Transactions extracted from Neo4j',
    'Graph edges extracted',
    'Writing to Delta tables',
    'Verifying row counts',
    'Running quality checks',
  ];
  const stepsEl = document.getElementById('progress-steps');
  stepsEl.innerHTML = stepLabels.map(l =>
    `<div class="step-row"><span class="step-icon">○</span><span>${escHtml(l)}</span><span class="step-count"></span></div>`
  ).join('');
  const stepRows = stepsEl.querySelectorAll('.step-row');

  const animStep = (i) => new Promise(resolve => {
    setTimeout(() => {
      stepRows[i].querySelector('.step-icon').textContent = '✓';
      const pct = Math.round(((i + 1) / stepLabels.length) * 100);
      document.getElementById('progress-bar').style.width = `${pct}%`;
      document.getElementById('progress-pct').textContent = `${pct}%`;
      resolve();
    }, 600 * (i + 1));
  });

  const animAll = Promise.all(stepLabels.map((_, i) => animStep(i)));
  let result;
  try {
    [result] = await Promise.all([fetchPromise, animAll]);
  } catch (error) {
    showError(error);
    return;
  }
  state.loadResult = result;

  // fill in actual counts from API
  result.steps.forEach((step, i) => {
    if (i < stepRows.length) {
      stepRows[i].querySelector('.step-icon').textContent = '✓';
      if (step.count) stepRows[i].querySelector('.step-count').textContent = step.count;
    }
  });

  // preview table
  if (result.preview && result.preview.length) {
    const cols = Object.keys(result.preview[0]);
    const table = document.getElementById('preview-table');
    table.innerHTML = `
      <thead><tr>${cols.map(c => `<th>${c}</th>`).join('')}</tr></thead>
      <tbody>${result.preview.map(row =>
        `<tr>${cols.map(c => `<td>${escHtml(row[c] ?? '')}</td>`).join('')}</tr>`
      ).join('')}</tbody>
    `;
  }

  // quality checks
  const qbody = document.getElementById('quality-tbody');
  qbody.innerHTML = (result.quality_checks || []).map(qc => {
    const cls = qc.status === 'pass' ? 'quality-status-pass' : qc.status === 'fail' ? 'quality-status-fail' : 'quality-status-pending';
    const label = qc.status === 'pass' ? '✓ Pass' : qc.status === 'fail' ? '✗ Fail' : 'Pending';
    return `<tr><td>${escHtml(qc.check)}</td><td class="${cls}">${escHtml(label)}</td></tr>`;
  }).join('');

  // summary counts
  const c = result.counts || {};
  document.getElementById('counts-summary').innerHTML =
    `<strong>${c.accounts ?? 0}</strong> accounts &nbsp;·&nbsp;
     <strong>${c.merchants ?? 0}</strong> merchants &nbsp;·&nbsp;
     <strong>${c.transactions ?? 0}</strong> transactions ready`;

  document.getElementById('preview-section').classList.remove('hidden');
  document.getElementById('continue-btn').style.display = 'inline-block';
}

// ── Screen 3: Analyze ─────────────────────────────────────────────────────────

document.getElementById('back-to-load').addEventListener('click', e => {
  e.preventDefault(); showScreen(2);
});

function buildDataPanel() {
  const c = (state.loadResult || {}).counts || {};
  const tables = [
    { name: 'fraud_signals.accounts', rows: c.accounts || 0,
      cols: ['account_id', 'ring_id', 'risk_score', 'first_seen'] },
    { name: 'fraud_signals.transactions', rows: c.transactions || 0,
      cols: ['txn_id', 'account_id', 'merchant_id', 'amount', 'txn_date'] },
    { name: 'fraud_signals.merchants', rows: c.merchants || 0,
      cols: ['merchant_id', 'merchant_name', 'category', 'total_txn_volume'] },
    { name: 'fraud_signals.graph_edges', rows: c.graph_edges || 0,
      cols: ['source_id', 'target_id', 'edge_type', 'weight'] },
  ];

  document.getElementById('data-tables-list').innerHTML = tables.map(t => `
    <div class="data-table-entry">
      <div class="data-table-name">${escHtml(t.name)}</div>
      <div class="data-table-rows">${escHtml(t.rows.toLocaleString())} rows</div>
      <ul class="data-table-cols">${t.cols.map(c => `<li>${escHtml(c)}</li>`).join('')}</ul>
    </div>
  `).join('');

  const samples = [
    'Which accounts have the highest risk scores?',
    `Show me all merchants linked to ${[...state.selected][0] || 'RING-0041'}`,
    'Which accounts share a device with 3 or more other accounts?',
    'What is the total txn volume per ring, ranked high to low?',
    'Are there merchants receiving funds from both rings?',
  ];
  document.getElementById('sample-q-list').innerHTML = samples.map(q =>
    `<div class="sample-q" data-testid="sample-question">${escHtml(q)}</div>`
  ).join('');

  document.querySelectorAll('.sample-q').forEach(el => {
    el.addEventListener('click', () => {
      document.getElementById('ask-input').value = el.textContent;
      document.getElementById('ask-input').focus();
    });
  });
}

document.getElementById('ask-form').addEventListener('submit', async e => {
  e.preventDefault();
  const input = document.getElementById('ask-input');
  const question = input.value.trim();
  if (!question) return;
  input.value = '';

  appendChat('You', question, null);

  const btn = e.target.querySelector('button[type=submit]');
  btn.disabled = true;
  btn.textContent = '…';

  try {
    const data = await postJson('/api/genie', { question, conversation_id: state.conversationId });
    state.conversationId = data.conversation_id;
    appendChat('Genie', data.answer, data.table_cols ? { cols: data.table_cols, rows: data.table_rows } : null);
    state.askedCount++;
    if (state.askedCount === 1) {
      document.getElementById('export-bar').classList.remove('hidden');
    }
  } catch (error) {
    appendChat('System', error.message || 'Request failed.', null);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Ask →';
  }
});

function appendChat(speaker, text, table) {
  const history = document.getElementById('chat-history');
  const placeholder = history.querySelector('.chat-placeholder');
  if (placeholder) placeholder.remove();

  if (state.askedCount > 0 || speaker === 'Genie') {
    const div = document.createElement('hr');
    div.className = 'chat-divider';
    history.appendChild(div);
  }

  const q = document.createElement('div');
  q.className = 'chat-q';
  q.innerHTML = `<strong>${escHtml(speaker)}:</strong> ${escHtml(text || '')}`;
  history.appendChild(q);

  if (table && table.cols && table.rows) {
    const wrap = document.createElement('div');
    wrap.className = 'chat-table-wrap';
    wrap.innerHTML = `
      <table class="results-table">
        <thead><tr>${table.cols.map(c => `<th>${escHtml(c)}</th>`).join('')}</tr></thead>
        <tbody>${table.rows.map(row =>
          `<tr>${row.map(cell => `<td>${escHtml(String(cell))}</td>`).join('')}</tr>`
        ).join('')}</tbody>
      </table>
    `;
    history.appendChild(wrap);
  }

  history.scrollTop = history.scrollHeight;
}

// ── Export report ─────────────────────────────────────────────────────────────

document.getElementById('export-btn').addEventListener('click', showReport);
document.getElementById('report-close').addEventListener('click', () =>
  document.getElementById('report-modal').classList.add('hidden'));
document.getElementById('report-close-2').addEventListener('click', () =>
  document.getElementById('report-modal').classList.add('hidden'));
document.getElementById('report-print').addEventListener('click', () => window.print());

function showReport() {
  const rings = state.rings.filter(r => state.selected.has(r.ring_id));
  const now = new Date().toLocaleString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  document.getElementById('report-date').textContent = now;

  const ringList = rings.map(r => `${escHtml(r.ring_id)} (${escHtml(r.node_count)} accounts)`).join(' · ');
  const highRisk = rings.flatMap(r =>
    (r.nodes || []).filter(n => (n.data.risk_score || 0) >= 0.8)
      .map(n => ({ ...n.data, ring_id: r.ring_id }))
  ).sort((a, b) => b.risk_score - a.risk_score).slice(0, 5);

  document.getElementById('report-body').innerHTML = `
    <div class="report-section">
      <h4>Source Rings Analyzed</h4>
      <p class="report-ring-list">${ringList}</p>
    </div>
    <div class="report-section">
      <h4>Priority Accounts for Investigation</h4>
      <table class="results-table">
        <thead><tr><th>Account ID</th><th>Ring ID</th><th>Risk Score</th><th>Flag</th></tr></thead>
        <tbody>${highRisk.map(a => `
          <tr>
            <td>${escHtml(a.id)}</td>
            <td>${escHtml(a.ring_id)}</td>
            <td>${escHtml((a.risk_score || 0).toFixed(2))}</td>
            <td style="color:#888">High risk score</td>
          </tr>`).join('')}
        </tbody>
      </table>
    </div>
    <div class="report-section">
      <h4>Analyst Notes</h4>
      <textarea class="analyst-notes" placeholder="Add your observations here…"></textarea>
    </div>
  `;

  document.getElementById('report-modal').classList.remove('hidden');
}

// ── Screen transitions ────────────────────────────────────────────────────────

function showScreen(n) {
  document.querySelectorAll('.screen').forEach((s, i) => {
    s.classList.toggle('active', i + 1 === n);
  });
  window.scrollTo(0, 0);
}

// ── Utilities ─────────────────────────────────────────────────────────────────

async function postJson(url, payload) {
  const resp = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    throw new Error(data.error || `Request failed with status ${resp.status}`);
  }
  return data;
}

function showError(error) {
  window.alert(error.message || 'Request failed.');
}

function escHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
