import { useEffect, useMemo, useRef, useState } from "react";
import { motion } from "motion/react";
import heroImg from "@/assets/companion-hero.jpg";
import avatarImg from "@/assets/companion-avatar.jpg";
import beachImg from "@/assets/memory-beach.jpg";
import diaryImg from "@/assets/memory-diary.jpg";

const MIN_DURATION = 2000; // 最短停留，避免一闪而过
const messages = [
  "正在为你点亮这个夜晚…",
  "她已经在等你啦…",
  "马上就好，再等一下下…",
];

const assets = [heroImg, avatarImg, beachImg, diaryImg];

export function LoadingScreen({ onComplete }: { onComplete: () => void }) {
  const [progress, setProgress] = useState(0);
  const [msgIndex, setMsgIndex] = useState(0);
  const loadedRef = useRef(0);
  const startRef = useRef(Date.now());
  const doneRef = useRef(false);

  // 漂浮粒子
  const particles = useMemo(
    () =>
      Array.from({ length: 16 }, () => ({
        left: Math.random() * 100,
        size: 2 + Math.random() * 4,
        delay: Math.random() * 6,
        duration: 6 + Math.random() * 5,
      })),
    [],
  );

  // 预加载真实资源
  useEffect(() => {
    let cancelled = false;
    assets.forEach((src) => {
      const img = new Image();
      const mark = () => {
        if (cancelled) return;
        loadedRef.current += 1;
      };
      img.onload = mark;
      img.onerror = mark;
      img.src = src;
    });
    return () => {
      cancelled = true;
    };
  }, []);

  // 进度推进：综合真实加载进度 + 最短时长
  useEffect(() => {
    const id = window.setInterval(() => {
      const elapsed = Date.now() - startRef.current;
      const loadRatio = loadedRef.current / assets.length;
      const timeRatio = Math.min(elapsed / MIN_DURATION, 1);
      // 目标进度：资源与时间都满足才允许到 100%
      const target = Math.min(loadRatio, timeRatio) * 100;
      setProgress((p) => {
        const next = p + (target - p) * 0.18 + 0.6;
        return Math.min(next, target >= 99.5 ? 100 : 97);
      });
    }, 60);
    return () => window.clearInterval(id);
  }, []);

  // 文案轮播
  useEffect(() => {
    const id = window.setInterval(
      () => setMsgIndex((i) => (i + 1) % messages.length),
      1500,
    );
    return () => window.clearInterval(id);
  }, []);

  // 完成
  useEffect(() => {
    if (progress >= 100 && !doneRef.current) {
      doneRef.current = true;
      const t = window.setTimeout(onComplete, 600);
      return () => window.clearTimeout(t);
    }
  }, [progress, onComplete]);

  const p = progress / 100;

  return (
    <div className="relative mx-auto flex min-h-screen w-full max-w-md flex-col items-center justify-between overflow-hidden bg-background">
      {/* 角色：从暗到亮逐渐点亮 */}
      <div className="pointer-events-none absolute inset-0">
        <img
          src={heroImg}
          alt="林小梦"
          width={1024}
          height={1024}
          className="h-full w-full object-cover object-top transition-[filter,opacity] duration-300"
          style={{
            filter: `brightness(${0.25 + p * 0.85}) saturate(${0.5 + p * 0.7}) blur(${(1 - p) * 10}px)`,
            opacity: 0.35 + p * 0.65,
          }}
        />
        <div className="absolute inset-0 bg-gradient-to-b from-background/50 via-transparent to-background" />
        {/* 呼吸光晕 */}
        <div
          className="animate-breathe absolute left-1/2 top-[42%] h-72 w-72 -translate-x-1/2 -translate-y-1/2 rounded-full"
          style={{
            background:
              "radial-gradient(circle, oklch(0.72 0.18 320 / 0.35) 0%, transparent 70%)",
          }}
        />
      </div>

      {/* 漂浮粒子 */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        {particles.map((pt, i) => (
          <span
            key={i}
            className="absolute bottom-0 rounded-full bg-primary-glow/70"
            style={{
              left: `${pt.left}%`,
              width: pt.size,
              height: pt.size,
              animation: `float-up ${pt.duration}s ease-in ${pt.delay}s infinite`,
              boxShadow: "0 0 8px oklch(0.78 0.17 320 / 0.8)",
            }}
          />
        ))}
      </div>

      {/* 顶部留白 */}
      <div className="h-24" />

      {/* 中部品牌 */}
      <motion.div
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7 }}
        className="relative z-10 flex flex-col items-center"
      >
        <img
          src={avatarImg}
          alt="林小梦"
          width={96}
          height={96}
          className="animate-pulse-glow h-24 w-24 rounded-full border-2 border-primary/60 object-cover"
        />
        <h1 className="mt-4 text-2xl font-semibold tracking-wide text-foreground text-glow">
          林小梦
        </h1>
        <span className="mt-1 text-xs text-muted-foreground">你的专属虚拟陪伴</span>
      </motion.div>

      {/* 底部进度区 */}
      <div className="relative z-10 mb-14 flex w-full flex-col items-center px-10">
        <motion.p
          key={msgIndex}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="mb-4 h-5 text-sm text-foreground/85"
        >
          {messages[msgIndex]}
        </motion.p>

        <div className="relative h-1.5 w-full overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full shadow-[0_0_12px_oklch(0.75_0.17_320/0.8)] transition-[width] duration-150"
            style={{ width: `${progress}%`, background: "var(--gradient-cta)" }}
          />
        </div>
        <span className="mt-2 text-xs tabular-nums text-muted-foreground">
          {Math.round(progress)}%
        </span>
      </div>
    </div>
  );
}