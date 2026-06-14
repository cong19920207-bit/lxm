import { motion } from "motion/react";
import {
  Phone,
  Video,
  Music,
  Moon,
  Sparkles,
  Heart,
  BookOpen,
  Star,
  MessageCircle,
  ChevronRight,
} from "lucide-react";
import heroImg from "@/assets/companion-hero.jpg";
import avatarImg from "@/assets/companion-avatar.jpg";
import beachImg from "@/assets/memory-beach.jpg";
import diaryImg from "@/assets/memory-diary.jpg";

const actions = [
  { icon: Phone, label: "语音通话" },
  { icon: Video, label: "视频通话" },
  { icon: Music, label: "一起听歌" },
  { icon: Moon, label: "陪我入睡" },
  { icon: Sparkles, label: "更多互动" },
];

const fade = {
  hidden: { opacity: 0, y: 16 },
  show: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: 0.1 + i * 0.08, duration: 0.5, ease: "easeOut" as const },
  }),
};

export function CompanionHome() {
  return (
    <div className="relative mx-auto min-h-screen w-full max-w-md overflow-hidden bg-background">
      {/* Character backdrop */}
      <div className="pointer-events-none absolute inset-0">
        <img
          src={heroImg}
          alt="林小梦"
          width={1024}
          height={1024}
          className="h-[78vh] w-full object-cover object-top"
        />
        <div className="absolute inset-0 bg-gradient-to-b from-background/40 via-background/30 to-background" />
        <div className="absolute inset-x-0 bottom-0 h-[55%] bg-gradient-to-t from-background via-background/85 to-transparent" />
      </div>

      <div className="relative z-10 flex flex-col gap-4 px-4 pb-32 pt-5">
        {/* Top bar */}
        <motion.header
          variants={fade}
          custom={0}
          initial="hidden"
          animate="show"
          className="flex items-start justify-between"
        >
          <div className="flex items-center gap-3">
            <img
              src={avatarImg}
              alt="林小梦头像"
              width={56}
              height={56}
              className="h-12 w-12 rounded-full border-2 border-primary/60 object-cover shadow-[var(--glow-primary)]"
            />
            <div>
              <div className="flex items-center gap-1.5">
                <span className="text-lg font-semibold text-foreground text-glow">林小梦</span>
                <Heart className="h-4 w-4 fill-accent text-accent" />
              </div>
              <span className="text-xs text-muted-foreground">陪伴你的第 31 天</span>
            </div>
          </div>

          <div className="glass-panel rounded-2xl px-3 py-2">
            <div className="flex items-center gap-1.5">
              <Star className="h-3.5 w-3.5 fill-gold text-gold" />
              <span className="text-xs font-medium text-foreground">亲密度</span>
            </div>
            <div className="mt-1.5 flex items-center gap-2">
              <div className="h-1.5 w-16 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full"
                  style={{ width: "52%", background: "var(--gradient-primary)" }}
                />
              </div>
              <span className="text-xs tabular-nums text-muted-foreground">1045 / 2000</span>
            </div>
          </div>
        </motion.header>

        {/* Time + quote */}
        <motion.div variants={fade} custom={1} initial="hidden" animate="show" className="mt-1">
          <div className="flex items-end gap-3">
            <span className="text-5xl font-light tracking-wide text-foreground text-glow">11:22</span>
            <div className="mb-1.5 flex items-center gap-1 text-muted-foreground">
              <Moon className="h-4 w-4" />
              <span className="text-sm">上午</span>
            </div>
          </div>
          <p className="mt-2 text-base italic text-foreground/90">
            “今天状态不错，继续陪伴你吧~”
          </p>
          <div className="mt-2 flex items-end gap-1">
            {[0.5, 0.9, 0.6, 1, 0.7].map((h, i) => (
              <span
                key={i}
                className="eq-bar w-1 rounded-full bg-primary"
                style={{ height: 18, transform: `scaleY(${h})`, animationDelay: `${i * 0.12}s` }}
              />
            ))}
          </div>
        </motion.div>

        {/* Action buttons */}
        <motion.div
          variants={fade}
          custom={2}
          initial="hidden"
          animate="show"
          className="mt-[34vh] grid grid-cols-5 gap-2"
        >
          {actions.map(({ icon: Icon, label }) => (
            <button key={label} className="flex flex-col items-center gap-1.5">
              <span className="glass-panel flex h-14 w-full items-center justify-center rounded-2xl transition-transform active:scale-95">
                <Icon className="h-6 w-6 text-primary-glow" />
              </span>
              <span className="text-[11px] text-foreground/85">{label}</span>
            </button>
          ))}
        </motion.div>

        {/* Cards */}
        <motion.button
          variants={fade}
          custom={3}
          initial="hidden"
          animate="show"
          className="glass-panel flex items-center gap-3 rounded-3xl p-3 text-left transition-transform active:scale-[0.98]"
        >
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-accent/15">
            <Heart className="h-5 w-5 fill-accent text-accent" />
          </span>
          <div className="min-w-0 flex-1">
            <div className="font-semibold text-foreground">我们的记忆</div>
            <div className="text-xs text-muted-foreground">她记得你们的点点滴滴</div>
          </div>
          <div className="hidden max-w-[42%] shrink-0 text-right text-[11px] leading-tight text-muted-foreground xs:block">
            日常常喝冰美式，今日决定更换饮品
          </div>
          <img src={beachImg} alt="" width={512} height={512} loading="lazy" className="h-12 w-16 shrink-0 rounded-xl object-cover" />
          <ChevronRight className="h-5 w-5 shrink-0 text-muted-foreground" />
        </motion.button>

        <motion.button
          variants={fade}
          custom={4}
          initial="hidden"
          animate="show"
          className="glass-panel flex items-center gap-3 rounded-3xl p-3 text-left transition-transform active:scale-[0.98]"
        >
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-gold/15">
            <BookOpen className="h-5 w-5 text-gold" />
          </span>
          <div className="min-w-0 flex-1">
            <div className="font-semibold text-foreground">她的日记</div>
            <div className="text-xs text-muted-foreground">记录她的心情和生活</div>
          </div>
          <div className="hidden shrink-0 text-right text-[11px] leading-tight text-muted-foreground xs:block">
            今天记录点什么好呢...
            <div className="mt-0.5">刚刚写下 · 17小时前</div>
          </div>
          <img src={diaryImg} alt="" width={512} height={512} loading="lazy" className="h-12 w-16 shrink-0 rounded-xl object-cover" />
          <ChevronRight className="h-5 w-5 shrink-0 text-muted-foreground" />
        </motion.button>

        <motion.button
          variants={fade}
          custom={5}
          initial="hidden"
          animate="show"
          className="glass-panel flex items-center gap-3 rounded-3xl p-3 text-left transition-transform active:scale-[0.98]"
        >
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-accent/15">
            <Heart className="h-5 w-5 fill-accent text-accent" />
          </span>
          <div className="min-w-0 flex-1">
            <div className="font-semibold text-foreground">关系状态</div>
            <div className="text-xs text-muted-foreground">你们的关系在慢慢升温</div>
          </div>
          <div className="shrink-0 text-right">
            <div className="font-semibold text-accent">亲密</div>
            <div className="text-sm">💗 💗</div>
          </div>
          <ChevronRight className="h-5 w-5 shrink-0 text-muted-foreground" />
        </motion.button>
      </div>

      {/* Bottom CTA */}
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.6, duration: 0.5 }}
        className="fixed inset-x-0 bottom-0 z-20 mx-auto max-w-md p-4"
      >
        <div className="flex items-center gap-3">
          <button
            className="animate-pulse-glow flex-1 rounded-full py-4 text-center transition-transform active:scale-[0.98]"
            style={{ background: "var(--gradient-cta)" }}
          >
            <div className="text-lg font-bold text-primary-foreground">和她说说话吧</div>
            <div className="text-xs text-primary-foreground/80">她在等你哦</div>
          </button>
          <button className="glass-panel flex h-14 w-14 shrink-0 items-center justify-center rounded-full">
            <MessageCircle className="h-6 w-6 text-primary-glow" />
          </button>
        </div>
      </motion.div>
    </div>
  );
}