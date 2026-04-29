"use client";

import { useEffect, useRef } from "react";

const hourlyData = [
  { hour: "00", known: 2, unknown: 0 },
  { hour: "01", known: 0, unknown: 0 },
  { hour: "02", known: 0, unknown: 1 },
  { hour: "03", known: 0, unknown: 0 },
  { hour: "04", known: 1, unknown: 0 },
  { hour: "05", known: 3, unknown: 0 },
  { hour: "06", known: 8, unknown: 1 },
  { hour: "07", known: 15, unknown: 2 },
  { hour: "08", known: 22, unknown: 3 },
  { hour: "09", known: 18, unknown: 1 },
  { hour: "10", known: 12, unknown: 2 },
  { hour: "11", known: 8, unknown: 0 },
  { hour: "12", known: 14, unknown: 1 },
  { hour: "13", known: 10, unknown: 0 },
  { hour: "14", known: 6, unknown: 0 },
  { hour: "15", known: 9, unknown: 1 },
  { hour: "16", known: 11, unknown: 0 },
  { hour: "17", known: 20, unknown: 2 },
  { hour: "18", known: 25, unknown: 3 },
  { hour: "19", known: 18, unknown: 1 },
  { hour: "20", known: 12, unknown: 0 },
  { hour: "21", known: 7, unknown: 0 },
  { hour: "22", known: 4, unknown: 1 },
  { hour: "23", known: 2, unknown: 0 },
];

export default function ActivityChart() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const width = rect.width;
    const height = rect.height;
    const padding = { top: 20, right: 20, bottom: 40, left: 40 };
    const chartW = width - padding.left - padding.right;
    const chartH = height - padding.top - padding.bottom;

    const maxVal = Math.max(...hourlyData.map((d) => d.known + d.unknown)) + 5;
    const barWidth = chartW / hourlyData.length;

    // Clear
    ctx.clearRect(0, 0, width, height);

    // Grid lines
    ctx.strokeStyle = "rgba(255,255,255,0.06)";
    ctx.lineWidth = 1;
    for (let i = 0; i <= 5; i++) {
      const y = padding.top + (chartH / 5) * i;
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(width - padding.right, y);
      ctx.stroke();

      // Y-axis labels
      ctx.fillStyle = "rgba(255,255,255,0.3)";
      ctx.font = "11px Inter, sans-serif";
      ctx.textAlign = "right";
      ctx.fillText(
        String(Math.round(maxVal - (maxVal / 5) * i)),
        padding.left - 8,
        y + 4
      );
    }

    // Draw bars
    hourlyData.forEach((d, i) => {
      const x = padding.left + i * barWidth + barWidth * 0.15;
      const bw = barWidth * 0.7;

      // Known (blue gradient)
      const knownH = (d.known / maxVal) * chartH;
      const unknownH = (d.unknown / maxVal) * chartH;
      const totalH = knownH + unknownH;

      // Unknown bar (red) — stacked on top
      if (d.unknown > 0) {
        const gradient2 = ctx.createLinearGradient(
          0,
          padding.top + chartH - totalH,
          0,
          padding.top + chartH - knownH
        );
        gradient2.addColorStop(0, "rgba(248,113,113,0.9)");
        gradient2.addColorStop(1, "rgba(248,113,113,0.5)");
        ctx.fillStyle = gradient2;

        roundRect(
          ctx,
          x,
          padding.top + chartH - totalH,
          bw,
          unknownH,
          [3, 3, 0, 0]
        );
      }

      // Known bar (blue)
      if (d.known > 0) {
        const gradient1 = ctx.createLinearGradient(
          0,
          padding.top + chartH - knownH,
          0,
          padding.top + chartH
        );
        gradient1.addColorStop(0, "rgba(99,102,241,0.9)");
        gradient1.addColorStop(1, "rgba(99,102,241,0.4)");
        ctx.fillStyle = gradient1;

        const topRadius = d.unknown === 0 ? [3, 3, 0, 0] : [0, 0, 0, 0];
        roundRect(
          ctx,
          x,
          padding.top + chartH - knownH,
          bw,
          knownH,
          topRadius
        );
      }

      // X-axis labels
      if (i % 3 === 0) {
        ctx.fillStyle = "rgba(255,255,255,0.3)";
        ctx.font = "11px Inter, sans-serif";
        ctx.textAlign = "center";
        ctx.fillText(
          `${d.hour}:00`,
          x + bw / 2,
          height - padding.bottom + 20
        );
      }
    });

    // Legend
    ctx.font = "11px Inter, sans-serif";
    const legendY = height - 8;

    ctx.fillStyle = "rgba(99,102,241,0.8)";
    ctx.fillRect(width - 180, legendY - 8, 10, 10);
    ctx.fillStyle = "rgba(255,255,255,0.4)";
    ctx.textAlign = "left";
    ctx.fillText("Known", width - 166, legendY);

    ctx.fillStyle = "rgba(248,113,113,0.8)";
    ctx.fillRect(width - 100, legendY - 8, 10, 10);
    ctx.fillStyle = "rgba(255,255,255,0.4)";
    ctx.fillText("Unknown", width - 86, legendY);
  }, []);

  return (
    <div className="chart-container" style={{ background: "transparent" }}>
      <canvas
        ref={canvasRef}
        style={{ width: "100%", height: "100%", display: "block" }}
      />
    </div>
  );
}

function roundRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  radii: number[]
) {
  const [tl, tr, br, bl] = radii;
  ctx.beginPath();
  ctx.moveTo(x + tl, y);
  ctx.lineTo(x + w - tr, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + tr);
  ctx.lineTo(x + w, y + h - br);
  ctx.quadraticCurveTo(x + w, y + h, x + w - br, y + h);
  ctx.lineTo(x + bl, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - bl);
  ctx.lineTo(x, y + tl);
  ctx.quadraticCurveTo(x, y, x + tl, y);
  ctx.closePath();
  ctx.fill();
}
