// RingGraph.tsx
// Cytoscape-powered thumbnail of a community subgraph.
// Mirrors finance-genie/simple-finance-analyst/static/app.js's cose-driven
// rendering: real graph nodes and within-community TRANSFERRED_TO edges,
// laid out with the cose force-directed algorithm.

import { useEffect, useRef } from "react";
import cytoscape from "cytoscape";
import type { Core, ElementDefinition, LayoutOptions } from "cytoscape";
import { cn } from "@/lib/utils";

export interface RingGraphNode {
  id: string;
  risk: "H" | "M" | "L";
  is_hub: boolean;
}

export interface RingGraphEdge {
  source: string;
  target: string;
}

export interface RingGraphProps {
  nodes: RingGraphNode[];
  edges: RingGraphEdge[];
  width?: number;
  height?: number;
  selected?: boolean;
  className?: string;
  ariaLabel?: string;
}

// Resolved hex colors, since Cytoscape's style does not interpolate
// `var(--color-...)` from CSS custom properties.
const RISK_HEX: Record<"H" | "M" | "L", string> = {
  H: "#c2410c",
  M: "#b45309",
  L: "#475569",
};

const EDGE_HEX = "#d4d4d8";
const EDGE_HEX_SELECTED = "#c2410c";

function pickLayout(
  nodeCount: number,
  width: number,
  height: number,
): LayoutOptions {
  if (nodeCount === 0) return { name: "grid" };
  // Calibrate cose params for tile-sized rendering. The defaults overshoot.
  return {
    name: "cose",
    idealEdgeLength: () => Math.max(20, Math.min(width, height) / 3),
    nodeRepulsion: () => 8000,
    edgeElasticity: () => 16,
    gravity: 0.2,
    numIter: 1200,
    initialTemp: 200,
    coolingFactor: 0.95,
    animate: false,
    fit: true,
    padding: 6,
  } as LayoutOptions;
}

export function RingGraph({
  nodes,
  edges,
  width = 96,
  height = 44,
  selected = false,
  className,
  ariaLabel,
}: RingGraphProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const cyRef = useRef<Core | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const elements: ElementDefinition[] = [
      ...nodes.map((n) => ({
        data: {
          id: n.id,
          risk: n.risk,
          hub: n.is_hub ? 1 : 0,
        },
      })),
      ...edges
        .filter((e) => e.source !== e.target)
        .map((e, idx) => ({
          data: {
            id: `e-${idx}-${e.source}-${e.target}`,
            source: e.source,
            target: e.target,
          },
        })),
    ];

    const cy = cytoscape({
      container,
      elements,
      style: [
        {
          selector: "node",
          style: {
            "background-color": (ele: cytoscape.NodeSingular) =>
              RISK_HEX[(ele.data("risk") as "H" | "M" | "L") || "L"],
            width: (ele: cytoscape.NodeSingular) =>
              ele.data("hub") ? 5 : 3,
            height: (ele: cytoscape.NodeSingular) =>
              ele.data("hub") ? 5 : 3,
            "border-width": 0,
            label: "",
            opacity: 0.9,
          },
        },
        {
          selector: "edge",
          style: {
            width: 0.6,
            "line-color": selected ? EDGE_HEX_SELECTED : EDGE_HEX,
            "curve-style": "haystack",
            opacity: 0.6,
          },
        },
      ],
      layout: pickLayout(nodes.length, width, height),
      userZoomingEnabled: false,
      userPanningEnabled: false,
      autoungrabify: true,
      boxSelectionEnabled: false,
    });

    cyRef.current = cy;
    return () => {
      cy.destroy();
      cyRef.current = null;
    };
    // The node/edge identities are stable per ring_id; we redraw when ring data
    // changes. Selection only re-styles edges, no full rebuild needed.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes, edges, width, height]);

  // Restyle edges on selection without recreating the instance.
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.style()
      .selector("edge")
      .style({
        "line-color": selected ? EDGE_HEX_SELECTED : EDGE_HEX,
      })
      .update();
  }, [selected]);

  return (
    <div
      ref={containerRef}
      className={cn("block", className)}
      style={{ width, height }}
      role="img"
      aria-label={ariaLabel}
    />
  );
}

export default RingGraph;
