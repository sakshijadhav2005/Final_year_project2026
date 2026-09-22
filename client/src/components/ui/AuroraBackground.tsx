import { useEffect, useRef } from "react";

export function AuroraBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const glowRef = useRef<HTMLDivElement>(null);
  const dotRef = useRef<HTMLDivElement>(null);
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
    const palette = ["216,180,120", "185,166,218", "111,207,196"]; // gold, lavender, teal

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

    function spawnBubble(x: number, y: number) {
      const r = 4 + Math.random() * 9;
      bubbles.push({
        x: x + (Math.random() - 0.5) * 14,
        y: y + (Math.random() - 0.5) * 14,
        r,
        baseR: r,
        vy: -(0.4 + Math.random() * 0.9),
        vx: (Math.random() - 0.5) * 0.4,
        life: 1,
        decay: 0.006 + Math.random() * 0.008,
        phase: Math.random() * Math.PI * 2,
        color: palette[Math.floor(Math.random() * palette.length)],
      });
      if (bubbles.length > 80) bubbles.shift();
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
        grad.addColorStop(0, `rgba(255,255,255,${0.35 * b.life})`);
        grad.addColorStop(0.4, `rgba(${b.color},${0.28 * b.life})`);
        grad.addColorStop(1, `rgba(${b.color},0)`);

        ctx.beginPath();
        ctx.fillStyle = grad;
        ctx.arc(b.x, b.y, b.r, 0, Math.PI * 2);
        ctx.fill();

        ctx.beginPath();
        ctx.strokeStyle = `rgba(255,255,255,${0.18 * b.life})`;
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
    let lastSpawn = 0;

    const handleMouseMove = (e: MouseEvent) => {
      gx = e.clientX;
      gy = e.clientY;

      if (dotRef.current) {
        dotRef.current.style.opacity = "1";
        dotRef.current.style.transform = `translate(${gx}px,${gy}px) translate(-50%,-50%)`;
      }
      if (glowRef.current) {
        glowRef.current.style.opacity = "1";
      }

      const now = performance.now();
      if (now - lastSpawn > 45) {
        spawnBubble(gx, gy);
        lastSpawn = now;
      }

      const relX = e.clientX / window.innerWidth - 0.5;
      const relY = e.clientY / window.innerHeight - 0.5;
      if (blobARef.current) blobARef.current.style.transform = `translate(${relX * 30}px,${relY * 30}px)`;
      if (blobBRef.current) blobBRef.current.style.transform = `translate(${relX * -24}px,${relY * -24}px)`;
      if (blobCRef.current) blobCRef.current.style.transform = `translate(${relX * 18}px,${relY * 18}px)`;
    };

    const handleMouseLeave = () => {
      if (dotRef.current) dotRef.current.style.opacity = "0";
      if (glowRef.current) glowRef.current.style.opacity = "0";
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseleave", handleMouseLeave);

    let trailId: number;
    function trail() {
      cx += (gx - cx) * 0.12;
      cy += (gy - cy) * 0.12;
      if (glowRef.current) {
        glowRef.current.style.transform = `translate(${cx}px,${cy}px) translate(-50%,-50%)`;
      }
      trailId = requestAnimationFrame(trail);
    }
    trail();

    return () => {
      cancelAnimationFrame(animId);
      cancelAnimationFrame(trailId);
      window.removeEventListener("resize", resizeCanvas);
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseleave", handleMouseLeave);
    };
  }, []);

  return (
    <>
      <div className="grain" />
      <div className="thin-lines" />
      <div className="vignette" />
      <div
        ref={glowRef}
        className="pointer-events-none fixed left-0 top-0 z-[4] h-44 w-44 -translate-x-1/2 -translate-y-1/2 rounded-full opacity-0 transition-opacity duration-300 will-change-transform"
        style={{
          background:
            "radial-gradient(circle, rgba(216,180,120,0.16), rgba(185,166,218,0.08) 45%, transparent 70%)",
        }}
      />
      <div
        ref={dotRef}
        className="pointer-events-none fixed left-0 top-0 z-[5] h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full opacity-0 shadow-[0_0_10px_2px_rgba(216,180,120,0.6)] transition-opacity duration-300"
        style={{ background: "var(--gold-soft)" }}
      />
      <canvas ref={canvasRef} className="pointer-events-none fixed inset-0 z-[6]" />
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
