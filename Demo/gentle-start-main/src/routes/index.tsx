import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { LoadingScreen } from "@/components/companion/LoadingScreen";
import { CompanionHome } from "@/components/companion/CompanionHome";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "林小梦 · 你的专属虚拟陪伴" },
      { name: "description", content: "林小梦是你的专属虚拟陪伴，陪你聊天、听歌、入睡，记录你们的点点滴滴。" },
      { property: "og:title", content: "林小梦 · 你的专属虚拟陪伴" },
      { property: "og:description", content: "林小梦是你的专属虚拟陪伴，陪你聊天、听歌、入睡，记录你们的点点滴滴。" },
    ],
  }),
  component: Index,
});

function Index() {
  const [loading, setLoading] = useState(true);

  return (
    <AnimatePresence mode="wait">
      {loading ? (
        <motion.div
          key="loader"
          exit={{ opacity: 0, y: -24, filter: "blur(8px)" }}
          transition={{ duration: 0.6, ease: "easeInOut" }}
        >
          <LoadingScreen onComplete={() => setLoading(false)} />
        </motion.div>
      ) : (
        <motion.div
          key="home"
          initial={{ opacity: 0, scale: 1.02 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.7, ease: "easeOut" }}
        >
          <CompanionHome />
        </motion.div>
      )}
    </AnimatePresence>
  );
}
