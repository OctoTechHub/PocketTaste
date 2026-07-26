"use client";

/**
 * The blend, drawn as a DNA double helix.
 *
 * The metaphor is not decoration — it is the algorithm. Two strands are the two
 * listeners, each scored independently by the production ranker. The rungs are the
 * base pairs: the places the two tastes actually bond. A blend with nothing in
 * common is two loose strands; a strong one is a tight, fully-paired molecule.
 *
 * So `bonded` is the whole animation. While the server is still streaming, the
 * strands sit apart, unpaired, searching. When the result lands they *zip* — the
 * pairing travels left to right, the strands wind around each other, and the coil
 * settles into a slow rotation. That is the blending moment, and it is driven by
 * real state rather than a timer pretending to be busy.
 *
 * Canvas rather than SVG: at ~140 nodes redrawn every frame, animating that many
 * DOM attributes would cost more than the picture is worth.
 */

import { useEffect, useRef } from "react";

import { THEM_RGB, YOU_RGB, type Rgb } from "./seam";

const rgba = (colour: Rgb, alpha: number) =>
  `rgba(${colour[0]}, ${colour[1]}, ${colour[2]}, ${alpha})`;

const clamp01 = (value: number) => (value < 0 ? 0 : value > 1 ? 1 : value);
const easeOutCubic = (t: number) => 1 - (1 - t) ** 3;

/** Turns of the coil across the full width. Non-integer so it never looks tiled. */
const TURNS = 3.15;
/** Nodes per CSS pixel. Enough for a smooth strand, few enough to stay cheap. */
const NODE_DENSITY = 0.13;
/** One rung every N nodes. Fewer rungs than nodes, or it reads as a ladder. */
const RUNG_EVERY = 6;
/** How long the pairing takes to travel the full width, in ms. */
const ZIP_MS = 1250;
/** Fraction of the zip spent on the travelling wavefront rather than the settle. */
const ZIP_TRAVEL = 0.4;

interface HelixProps {
  /** True once the result has landed. Flipping this true plays the zip. */
  bonded: boolean;
  /** 0..1 taste match. Drives how strongly the base pairs read. */
  match?: number;
  height?: number;
  className?: string;
}

export function Helix({ bonded, match = 0.5, height = 116, className }: HelixProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  // Props live in a ref so the render loop always sees current values without
  // being torn down and restarted on every parent re-render.
  const props = useRef({ bonded, match, zipAt: 0 });

  useEffect(() => {
    if (props.current.bonded !== bonded) {
      props.current.zipAt = performance.now();
    }
    props.current.bonded = bonded;
    props.current.match = match;
  }, [bonded, match]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const context = canvas?.getContext("2d");
    if (!canvas || !context) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let width = 0;
    let cssHeight = 0;
    let frame = 0;

    const resize = () => {
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      const rect = canvas.getBoundingClientRect();
      width = Math.max(1, rect.width);
      cssHeight = Math.max(1, rect.height);
      canvas.width = Math.round(width * ratio);
      canvas.height = Math.round(cssHeight * ratio);
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
    };

    const draw = (now: number) => {
      const { bonded: isBonded, match: strength, zipAt } = props.current;

      // Reduced motion gets one still frame of the settled molecule — the shape
      // carries the meaning, the rotation is only pleasure.
      const zip = reduced
        ? isBonded
          ? 1
          : 0
        : isBonded
          ? easeOutCubic(clamp01((now - zipAt) / ZIP_MS))
          : 0;
      const spin = reduced ? 0.6 : (now / 1000) * (isBonded ? 0.5 : 1.1);
      // A slow bright band travelling the length, so a settled helix still breathes.
      const pulse = reduced ? -1 : ((now / 4200) % 1.6) - 0.3;

      const centreY = cssHeight / 2;
      const maxAmplitude = cssHeight * 0.29;
      const restGap = cssHeight * 0.2;
      const nodeSize = Math.max(1.7, cssHeight * 0.021);
      const count = Math.max(40, Math.round(width * NODE_DENSITY));
      const turn = Math.PI * 2 * TURNS;

      context.clearRect(0, 0, width, cssHeight);

      type Node = { x: number; y: number; depth: number; glow: number; paired: number };
      const strandA: Node[] = [];
      const strandB: Node[] = [];

      for (let index = 0; index <= count; index += 1) {
        const u = index / count;
        // The wavefront: pairing completes at u=0 first and travels right.
        const paired = clamp01((zip - u * ZIP_TRAVEL) / (1 - ZIP_TRAVEL));
        const angle = turn * u + spin;
        const amplitude = maxAmplitude * (0.42 + 0.58 * paired);
        const gap = restGap * (1 - paired);
        const wave = Math.sin(angle);
        const depth = Math.cos(angle);
        const glow = pulse < -0.2 ? 0 : Math.exp(-((u - pulse) ** 2) / 0.004);

        strandA.push({
          x: u * width,
          y: centreY - gap + amplitude * wave,
          depth,
          glow,
          paired,
        });
        strandB.push({
          x: u * width,
          y: centreY + gap - amplitude * wave,
          depth: -depth,
          glow,
          paired,
        });
      }

      // --- back-facing nodes, then rungs, then front-facing nodes. Painting in
      // depth order is what makes a flat sine pair read as a solid 3D coil.
      const drawNodes = (front: boolean) => {
        for (let index = 0; index <= count; index += 1) {
          for (const [node, colour] of [
            [strandA[index], YOU_RGB],
            [strandB[index], THEM_RGB],
          ] as const) {
            if (front !== node.depth >= 0) continue;
            const near = (node.depth + 1) / 2;
            const radius = nodeSize * (0.5 + 0.5 * near) * (1 + node.glow * 0.5);
            context.beginPath();
            context.arc(node.x, node.y, radius, 0, Math.PI * 2);
            context.fillStyle = rgba(colour, 0.22 + 0.55 * near + node.glow * 0.3);
            context.fill();
          }
        }
      };

      const drawStrand = (nodes: Node[], colour: Rgb) => {
        context.beginPath();
        nodes.forEach((node, index) => {
          if (index === 0) context.moveTo(node.x, node.y);
          else context.lineTo(node.x, node.y);
        });
        context.strokeStyle = rgba(colour, 0.24);
        context.lineWidth = Math.max(1, nodeSize * 0.5);
        context.lineJoin = "round";
        context.stroke();
      };

      drawStrand(strandA, YOU_RGB);
      drawStrand(strandB, THEM_RGB);
      drawNodes(false);

      // Base pairs. They only exist where the strands have actually bonded, and
      // they vanish at the crossings, where the rung is edge-on to the viewer.
      const rungAlpha = 0.3 + 0.7 * clamp01(strength);
      for (let index = 0; index <= count; index += RUNG_EVERY) {
        const a = strandA[index];
        const b = strandB[index];
        if (a.paired < 0.04) continue;
        const spread = Math.abs(a.y - b.y) / (maxAmplitude * 2);
        const alpha = a.paired * rungAlpha * (0.15 + 0.85 * spread) + a.glow * 0.25;
        if (alpha < 0.02) continue;
        const gradient = context.createLinearGradient(a.x, a.y, b.x, b.y);
        gradient.addColorStop(0, rgba(YOU_RGB, alpha));
        gradient.addColorStop(1, rgba(THEM_RGB, alpha));
        context.beginPath();
        context.moveTo(a.x, a.y);
        context.lineTo(b.x, b.y);
        context.strokeStyle = gradient;
        context.lineWidth = Math.max(1, nodeSize * 0.62);
        context.lineCap = "round";
        context.stroke();
      }

      drawNodes(true);

      if (!reduced) frame = requestAnimationFrame(draw);
    };

    const observer = new ResizeObserver(() => {
      resize();
      if (reduced) draw(performance.now());
    });
    observer.observe(canvas);
    resize();

    if (reduced) draw(performance.now());
    else frame = requestAnimationFrame(draw);

    return () => {
      observer.disconnect();
      cancelAnimationFrame(frame);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden
      className={className}
      style={{ display: "block", width: "100%", height }}
    />
  );
}
