import React, { useEffect, useRef } from 'react';
import { useReducedMotion } from 'framer-motion';

interface KnowledgeCoreProps {
  documentCount?: number;
  isOnline?: boolean;
  className?: string;
}

interface NodePoint {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  pulsePhase: number;
  pulseSpeed: number;
  cluster: number;
  label?: string;
}

export const KnowledgeCoreVisualization: React.FC<KnowledgeCoreProps> = ({
  documentCount = 0,
  isOnline = true,
  className = '',
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const shouldReduceMotion = useReducedMotion();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animId: number;

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      canvas.width = rect.width * (window.devicePixelRatio || 1);
      canvas.height = rect.height * (window.devicePixelRatio || 1);
      ctx.scale(window.devicePixelRatio || 1, window.devicePixelRatio || 1);
    };

    resize();
    window.addEventListener('resize', resize);

    const w = () => canvas.getBoundingClientRect().width;
    const h = () => canvas.getBoundingClientRect().height;

    // Generate orbiting knowledge nodes
    const nodeCount = 24;
    const nodes: NodePoint[] = [];
    for (let i = 0; i < nodeCount; i++) {
      const angle = (i / nodeCount) * Math.PI * 2;
      const dist = 60 + Math.random() * 110;
      nodes.push({
        x: Math.cos(angle) * dist,
        y: Math.sin(angle) * dist,
        vx: (Math.random() - 0.5) * 0.15,
        vy: (Math.random() - 0.5) * 0.15,
        radius: 1.5 + Math.random() * 2,
        pulsePhase: Math.random() * Math.PI * 2,
        pulseSpeed: 0.02 + Math.random() * 0.02,
        cluster: i % 4,
        label: i % 6 === 0 ? `VEC.0${i}` : undefined,
      });
    }

    let angleRing1 = 0;
    let angleRing2 = 0;
    let pulseTime = 0;
    let isVisible = true;

    const handleVisibility = () => {
      isVisible = !document.hidden;
    };
    document.addEventListener('visibilitychange', handleVisibility);

    const render = () => {
      if (!isVisible) {
        animId = requestAnimationFrame(render);
        return;
      }

      const currentW = w();
      const currentH = h();
      const cx = currentW / 2;
      const cy = currentH / 2;

      ctx.clearRect(0, 0, currentW, currentH);

      const isDark = document.documentElement.getAttribute('data-theme') !== 'light';
      const cyan = isDark ? '0, 240, 255' : '2, 132, 199';
      const accent = isDark ? '56, 189, 248' : '3, 105, 161';

      pulseTime += 0.025;
      if (!shouldReduceMotion) {
        angleRing1 += 0.003;
        angleRing2 -= 0.002;
      }

      // 1. Concentric HUD Reticles & Orbital Rings
      const ringRadii = [45, 90, 135, 175];
      ringRadii.forEach((r, idx) => {
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(${cyan}, ${idx === 1 ? 0.22 : 0.08})`;
        ctx.lineWidth = idx === 1 ? 1.2 : 0.75;
        if (idx % 2 === 1) {
          ctx.setLineDash([4, 8]);
        } else {
          ctx.setLineDash([]);
        }
        ctx.stroke();
        ctx.setLineDash([]);
      });

      // 2. Rotating Telemetry Crosshairs & Coordinate Ticks
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(angleRing1);

      // Ring 2 ticks
      const tickCount = 24;
      for (let i = 0; i < tickCount; i++) {
        const a = (i / tickCount) * Math.PI * 2;
        const x1 = Math.cos(a) * 88;
        const y1 = Math.sin(a) * 88;
        const x2 = Math.cos(a) * (i % 6 === 0 ? 96 : 92);
        const y2 = Math.sin(a) * (i % 6 === 0 ? 96 : 92);

        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.strokeStyle = `rgba(${cyan}, ${i % 6 === 0 ? 0.35 : 0.15})`;
        ctx.lineWidth = i % 6 === 0 ? 1 : 0.6;
        ctx.stroke();
      }

      // Orbital cross marker
      ctx.beginPath();
      ctx.arc(Math.cos(0) * 135, Math.sin(0) * 135, 3, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${cyan}, 0.8)`;
      ctx.fill();

      ctx.restore();

      // Outer Counter-Rotating Arc
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(angleRing2);
      ctx.beginPath();
      ctx.arc(0, 0, 175, 0, Math.PI * 0.4);
      ctx.strokeStyle = `rgba(${accent}, 0.35)`;
      ctx.lineWidth = 1.5;
      ctx.stroke();

      ctx.beginPath();
      ctx.arc(0, 0, 175, Math.PI, Math.PI * 1.35);
      ctx.strokeStyle = `rgba(${accent}, 0.25)`;
      ctx.lineWidth = 1;
      ctx.stroke();
      ctx.restore();

      // 3. Central Intelligence Core
      const corePulse = Math.sin(pulseTime) * 0.15 + 0.85;
      const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, 38 * corePulse);
      grad.addColorStop(0, `rgba(${cyan}, ${isDark ? 0.45 : 0.3})`);
      grad.addColorStop(0.5, `rgba(${accent}, ${isDark ? 0.18 : 0.12})`);
      grad.addColorStop(1, 'rgba(0, 0, 0, 0)');

      ctx.beginPath();
      ctx.arc(cx, cy, 38 * corePulse, 0, Math.PI * 2);
      ctx.fillStyle = grad;
      ctx.fill();

      // Core inner nucleus
      ctx.beginPath();
      ctx.arc(cx, cy, 7, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${cyan}, ${isOnline ? 0.95 : 0.4})`;
      ctx.shadowColor = `rgba(${cyan}, 0.8)`;
      ctx.shadowBlur = isDark ? 12 : 6;
      ctx.fill();
      ctx.shadowBlur = 0;

      // 4. Floating Knowledge Nodes & Retrieval Pathways
      const maxDistance = 75;
      for (let i = 0; i < nodes.length; i++) {
        const p1 = nodes[i];
        if (!shouldReduceMotion) {
          p1.x += p1.vx;
          p1.y += p1.vy;

          // Boundary bounce within radius 150
          const dist = Math.sqrt(p1.x * p1.x + p1.y * p1.y);
          if (dist > 150 || dist < 35) {
            p1.vx = -p1.vx;
            p1.vy = -p1.vy;
          }
        }

        const screenX1 = cx + p1.x;
        const screenY1 = cy + p1.y;

        // Faint retrieval vector lines to center
        if (i % 3 === 0) {
          const coreDist = Math.sqrt(p1.x * p1.x + p1.y * p1.y);
          const lineAlpha = (1 - coreDist / 160) * (isDark ? 0.16 : 0.1);
          ctx.beginPath();
          ctx.moveTo(cx, cy);
          ctx.lineTo(screenX1, screenY1);
          ctx.strokeStyle = `rgba(${cyan}, ${lineAlpha})`;
          ctx.lineWidth = 0.6;
          ctx.stroke();
        }

        // Inter-node connections
        for (let j = i + 1; j < nodes.length; j++) {
          const p2 = nodes[j];
          const dx = p1.x - p2.x;
          const dy = p1.y - p2.y;
          const d = Math.sqrt(dx * dx + dy * dy);

          if (d < maxDistance) {
            const lineAlpha = (1 - d / maxDistance) * (isDark ? 0.18 : 0.12);
            ctx.beginPath();
            ctx.moveTo(screenX1, screenY1);
            ctx.lineTo(cx + p2.x, cy + p2.y);
            ctx.strokeStyle = `rgba(${cyan}, ${lineAlpha})`;
            ctx.lineWidth = 0.6;
            ctx.stroke();
          }
        }

        // Draw node
        const nodePulse = Math.sin(pulseTime * 2 + p1.pulsePhase) * 0.3 + 0.7;
        ctx.beginPath();
        ctx.arc(screenX1, screenY1, p1.radius * nodePulse, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${cyan}, ${0.45 * nodePulse})`;
        ctx.fill();

        // Technical node label
        if (p1.label && isDark) {
          ctx.font = '9px "Space Mono", monospace';
          ctx.fillStyle = `rgba(${cyan}, 0.55)`;
          ctx.fillText(p1.label, screenX1 + 5, screenY1 - 4);
        }
      }

      if (!shouldReduceMotion) {
        animId = requestAnimationFrame(render);
      }
    };

    render();

    return () => {
      window.removeEventListener('resize', resize);
      document.removeEventListener('visibilitychange', handleVisibility);
      if (animId) cancelAnimationFrame(animId);
    };
  }, [shouldReduceMotion, isOnline]);

  return (
    <div className={`knowledge-core-container ${className}`} aria-hidden="true">
      <canvas ref={canvasRef} className="knowledge-core-canvas" />

      {/* Decorative HUD Telemetry Badges */}
      <div className="knowledge-core-hud">
        <div className="core-telemetry-tag top-left">
          <span className="telemetry-coord">VEC.384 // DENSE</span>
          <span className="telemetry-sub">DIM: 384-F</span>
        </div>

        <div className="core-telemetry-tag top-right">
          <span className="telemetry-coord">RETRIEVAL // READY</span>
          <span className="telemetry-sub">{isOnline ? 'ONLINE' : 'STANDBY'}</span>
        </div>

        <div className="core-telemetry-tag bottom-left">
          <span className="telemetry-coord">INDEXED DATA</span>
          <span className="telemetry-sub">{documentCount} REPOSITORIES</span>
        </div>

        <div className="core-telemetry-tag bottom-right">
          <span className="telemetry-coord">SYS.STATUS</span>
          <span className="telemetry-sub">VERIFIED 200 OK</span>
        </div>
      </div>
    </div>
  );
};
