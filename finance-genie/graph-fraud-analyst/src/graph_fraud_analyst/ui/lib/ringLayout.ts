// ringLayout.ts
// Deterministic seed-based SVG layout for ring thumbnails.
// Verbatim TypeScript port of the wireframe ringSeed/ringLayout in
// /tmp/design-fetch/fraud-analyst/project/app.jsx (lines 14–71).

export type Topology = "star" | "mesh" | "chain";

export interface RingLayoutInput {
  id: string;
  nodes: number;
  topology: Topology;
}

export interface LaidOutNode {
  x: number;
  y: number;
  hub?: boolean;
}

export interface LaidOutRing {
  nodes: LaidOutNode[];
  edges: Array<[number, number]>;
}

export interface RingLayoutOpts {
  maxNodes?: number;
  pad?: number;
}

export function ringSeed(id: string): () => number {
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) | 0;
  return () => {
    h = (h * 9301 + 49297) % 233280;
    return h / 233280;
  };
}

export function ringLayout(
  ring: RingLayoutInput,
  w: number,
  h: number,
  opts: RingLayoutOpts = {},
): LaidOutRing {
  const rand = ringSeed(ring.id);
  const n = Math.min(ring.nodes, opts.maxNodes ?? 14);
  const cx = w / 2;
  const cy = h / 2;
  const pad = opts.pad ?? 8;
  const nodes: LaidOutNode[] = [];
  const edges: Array<[number, number]> = [];

  if (ring.topology === "star") {
    nodes.push({ x: cx, y: cy, hub: true });
    for (let i = 1; i < n; i++) {
      const a = (i / (n - 1)) * Math.PI * 2 + rand() * 0.4;
      const r = Math.min(w, h) / 2 - pad;
      nodes.push({ x: cx + Math.cos(a) * r, y: cy + Math.sin(a) * r });
      edges.push([0, i]);
    }
    // a few peripheral cross-links
    for (let i = 0; i < Math.max(1, Math.floor(n / 6)); i++) {
      const a = 1 + Math.floor(rand() * (n - 1));
      const b = 1 + Math.floor(rand() * (n - 1));
      if (a !== b) edges.push([a, b]);
    }
  } else if (ring.topology === "mesh") {
    for (let i = 0; i < n; i++) {
      const a = (i / n) * Math.PI * 2;
      const r = Math.min(w, h) / 2 - pad - rand() * 4;
      nodes.push({ x: cx + Math.cos(a) * r, y: cy + Math.sin(a) * r });
    }
    for (let i = 0; i < n; i++) edges.push([i, (i + 1) % n]);
    const extra = Math.floor(n * 0.6);
    for (let i = 0; i < extra; i++) {
      const a = Math.floor(rand() * n);
      const b = Math.floor(rand() * n);
      if (a !== b) edges.push([a, b]);
    }
  } else {
    // chain: 2-row staggered with cross-row edges
    const rows = 2;
    const per = Math.ceil(n / rows);
    for (let i = 0; i < n; i++) {
      const row = i % rows;
      const col = Math.floor(i / rows);
      const x = pad + (col / Math.max(1, per - 1)) * (w - pad * 2) + (row * 6 - 3);
      const y = cy + (row === 0 ? -8 : 8) + (rand() - 0.5) * 4;
      nodes.push({ x, y });
      if (i > 0) edges.push([i - 1, i]);
      if (row === 1 && i - rows >= 0) edges.push([i - rows, i]);
    }
  }

  return { nodes, edges };
}
