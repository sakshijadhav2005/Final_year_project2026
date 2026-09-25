import { useEffect, useRef } from "react";

export function AuroraBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const glowRef = useRef<HTMLDivElement>(null);
  const dotRef = useRef<HTMLDivElement>(null);
  const ringRef = useRef<HTMLDivElement>(null);
  const blobARef = useRef<HTMLDivElement>(null);
  const blobBRef = useRef<HTMLDivElement>(null);
  const blobCRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animId: number;
    const bubbles: Array<{
      x: number;
      y: number;
      r: number;
      baseR: number;
      vy: number;
      vx: number;
      life: number;
      decay: number;
      phase: number;
      color: string;
    }> = [];
    const palette = ["216,180,120", "185,166,218", "111,207,196", "245,158,11"]; // gold, lavender, teal, amber

    function resizeCanvas() {
      if (!canvas || !ctx) return;
      canvas.width = window.innerWidth * window.devicePixelRatio;
      canvas.height = window.innerHeight * window.devicePixelRatio;
      canvas.style.width = window.innerWidth + "px";
      canvas.style.height = window.innerHeight + "px";
      ctx.setTransform(window.devicePixelRatio, 0, 0, window.devicePixelRatio, 0, 0);
    }
    resizeCanvas();
    window.addEventListener("resize", resizeCanvas);

    function spawnBubble(x: number, y: number, burst = false) {
      const count = burst ? 8 : 1;
      for (let k = 0; k < count; k++) {
        const r = burst ? 5 + Math.random() * 10 : 3 + Math.random() * 8;
        bubbles.push({
          x: x + (Math.random() - 0.5) * (burst ? 30 : 12),
          y: y + (Math.random() - 0.5) * (burst ? 30 : 12),
          r,
          baseR: r,
          vy: burst ? (Math.random() - 0.5) * 2.5 - 0.5 : -(0.3 + Math.random() * 0.8),
          vx: (Math.random() - 0.5) * (burst ? 2.5 : 0.4),
          life: 1,
          decay: burst ? 0.015 + Math.random() * 0.02 : 0.007 + Math.random() * 0.009,
          phase: Math.random() * Math.PI * 2,
          color: palette[Math.floor(Math.random() * palette.length)],
        });
      }
      if (bubbles.length > 120) bubbles.splice(0, bubbles.length - 120);
    }

    function drawBubbles() {
      if (!ctx || !canvas) return;
      ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);

      for (let i = bubbles.length - 1; i >= 0; i--) {
        const b = bubbles[i];
        b.phase += 0.05;
        b.x += b.vx + Math.sin(b.phase) * 0.3;
        b.y += b.vy;
        b.life -= b.decay;
        b.r = b.baseR * (0.7 + 0.3 * Math.sin(b.phase * 1.3));
        if (b.life <= 0) {
          bubbles.splice(i, 1);
          continue;
        }

        const grad = ctx.createRadialGradient(
          b.x - b.r * 0.3,
          b.y - b.r * 0.3,
          b.r * 0.1,
          b.x,
          b.y,
          b.r,
        );
        grad.addColorStop(0, `rgba(255,255,255,${0.4 * b.life})`);
        grad.addColorStop(0.4, `rgba(${b.color},${0.32 * b.life})`);
        grad.addColorStop(1, `rgba(${b.color},0)`);

        ctx.beginPath();
        ctx.fillStyle = grad;
        ctx.arc(b.x, b.y, b.r, 0, Math.PI * 2);
        ctx.fill();

        ctx.beginPath();
        ctx.strokeStyle = `rgba(255,255,255,${0.2 * b.life})`;
        ctx.lineWidth = 0.6;
        ctx.arc(b.x, b.y, b.r, 0, Math.PI * 2);
        ctx.stroke();
      }
      animId = requestAnimationFrame(drawBubbles);
    }
    drawBubbles();

    let gx = 0;
    let gy = 0;
    let cx = 0;
    let cy = 0;
    let rx = 0;
    let ry = 0;
    let lastSpawn = 0;
    let isHoveringInteractive = false;

    const handleMouseMove = (e: MouseEvent) => {
      gx = e.clientX;
      gy = e.clientY;

      const target = e.target as HTMLElement | null;
      isHoveringInteractive = !!target?.closest(
        'a, button, input, select, textarea, summary, [role="button"], [role="tab"], [role="checkbox"], .cursor-pointer, .glass, .neo-btn'
      );

      if (dotRef.current) {
        dotRef.current.style.opacity = "1";
        dotRef.current.style.transform = `translate3d(${gx}px,${gy}px,0) translate(-50%,-50%) scale(${
          isHoveringInteractive ? 1.6 : 1
        })`;
      }
      if (glowRef.current) {
        glowRef.current.style.opacity = isHoveringInteractive ? "1" : "0.75";
      }
      if (ringRef.current) {
        ringRef.current.style.opacity = isHoveringInteractive ? "1" : "0.3";
      }

      const now = performance.now();
      if (now - lastSpawn > (isHoveringInteractive ? 35 : 55)) {
        spawnBubble(gx, gy);
        lastSpawn = now;
      }

      const relX = e.clientX / window.innerWidth - 0.5;
      const relY = e.clientY / window.innerHeight - 0.5;
      if (blobARef.current) blobARef.current.style.transform = `translate(${relX * 30}px,${relY * 30}px)`;
      if (blobBRef.current) blobBRef.current.style.transform = `translate(${relX * -24}px,${relY * -24}px)`;
      if (blobCRef.current) blobCRef.current.style.transform = `translate(${relX * 18}px,${relY * 18}px)`;
    };

    const handleMouseDown = (e: MouseEvent) => {
      spawnBubble(e.clientX, e.clientY, true);
      if (ringRef.current) {
        ringRef.current.style.transform = `translate3d(${gx}px,${gy}px,0) translate(-50%,-50%) scale(0.6)`;
      }
    };

    const handleMouseUp = () => {
      if (ringRef.current) {
        ringRef.current.style.transform = `translate3d(${gx}px,${gy}px,0) translate(-50%,-50%) scale(${
          isHoveringInteractive ? 1.8 : 1
        })`;
      }
    };

    const handleMouseLeave = () => {
      if (dotRef.current) dotRef.current.style.opacity = "0";
      if (glowRef.current) glowRef.current.style.opacity = "0";
      if (ringRef.current) ringRef.current.style.opacity = "0";
    };

    window.addEventListener("mousemove", handleMouseMove, { passive: true });
    window.addEventListener("mousedown", handleMouseDown, { passive: true });
    window.addEventListener("mouseup", handleMouseUp, { passive: true });
    window.addEventListener("mouseleave", handleMouseLeave);

    let trailId: number;
    function trail() {
      cx += (gx - cx) * 0.12;
      cy += (gy - cy) * 0.12;
      rx += (gx - rx) * 0.22;
      ry += (gy - ry) * 0.22;

      if (glowRef.current) {
        glowRef.current.style.transform = `translate3d(${cx}px,${cy}px,0) translate(-50%,-50%)`;
      }
      if (ringRef.current) {
        ringRef.current.style.transform = `translate3d(${rx}px,${ry}px,0) translate(-50%,-50%) scale(${
          isHoveringInteractive ? 1.8 : 1
        })`;
      }
      trailId = requestAnimationFrame(trail);
    }
    trail();

    return () => {
      cancelAnimationFrame(animId);
      cancelAnimationFrame(trailId);
      window.removeEventListener("resize", resizeCanvas);
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mousedown", handleMouseDown);
      window.removeEventListener("mouseup", handleMouseUp);
      window.removeEventListener("mouseleave", handleMouseLeave);
    };
  }, []);

  return (
    <>
      <div className="grain" />
      <div className="thin-lines" />
      <div className="vignette" />
      {/* Dynamic Cursor Follower Aura - Global Top Layer */}
      <div
        ref={glowRef}
        className="pointer-events-none fixed left-0 top-0 z-[9998] h-48 w-48 -translate-x-1/2 -translate-y-1/2 rounded-full opacity-0 transition-opacity duration-300 will-change-transform"
        style={{
          background:
            "radial-gradient(circle, rgba(216,180,120,0.22), rgba(185,166,218,0.1) 45%, transparent 70%)",
        }}
      />
      {/* Interactive Cursor Ring */}
      <div
        ref={ringRef}
        className="pointer-events-none fixed left-0 top-0 z-[9999] h-8 w-8 -translate-x-1/2 -translate-y-1/2 rounded-full border border-amber-400/50 opacity-0 transition-all duration-150 will-change-transform shadow-[0_0_12px_rgba(216,180,120,0.4)]"
      />
      {/* Center Golden Cursor Dot */}
      <div
        ref={dotRef}
        className="pointer-events-none fixed left-0 top-0 z-[10000] h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full opacity-0 shadow-[0_0_12px_3px_rgba(216,180,120,0.8)] transition-all duration-150"
        style={{ background: "var(--gold-soft)" }}
      />
      {/* Global Particle Canvas */}
      <canvas ref={canvasRef} className="pointer-events-none fixed inset-0 z-[9997]" />
      <div ref={blobARef} className="blob blob-a" />
      <div ref={blobBRef} className="blob blob-b" />
      <div ref={blobCRef} className="blob blob-c" />
      <div className="spark" style={{ top: "14%", left: "22%", animationDelay: "0s" }} />
      <div className="spark" style={{ top: "64%", left: "8%", animationDelay: "1.2s" }} />
      <div className="spark" style={{ top: "30%", left: "78%", animationDelay: "2.1s" }} />
      <div className="spark" style={{ top: "80%", left: "66%", animationDelay: "0.6s" }} />
    </>
  );
}
