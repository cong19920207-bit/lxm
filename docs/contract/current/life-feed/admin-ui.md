# Life Feed Admin

- 文档 ID：`contract-life-feed-admin`
- 权威状态：`canonical`
- 功能范围：`life-feed`
- 必读依赖：`contract-shared-conventions`
- 相关技术债：`TD-032`, `TD-033`, `TD-034`, `TD-035`, `TD-036`, `TD-037`

### 生活流管理页（`admin/pages/` · 侧栏「🌿 生活流 Prompt」）

| 页面 | 菜单 key | 内容摘要 |
|------|----------|----------|
| `life-plan.html` | life-plan | 周大纲 / 日场景 CRUD；ops 只读 |
| `life-feed-global.html` | life-feed-global | **生活流人格拓展**（原「全局配置」：人设扩展 + 词汇表 + Header 配置） |
| `feed-posts.html` | feed-posts | 列表/详情/编辑/发帖/显隐；计划时间 `formatWallClock`；详情含虚拟评论底；**无**删除钮 |
| `feed-comments.html` | feed-comments | 筛评/编辑/软删/补发 |
| `agent-aware.html` | agent-aware | 队列视图/重试/删除；super 可重置特殊档 |
| `worldview.html` | worldview | 快照近14天分页 + 事件库；ops 只读 |
| `life-feed-prompts.html` | life-feed-prompts / -i | P-01~14 + 图像映射 + 互动参数（模型/延迟/特殊档） |
| `life-feed-system.html` | life-feed-system | 自动发布/窗口/可见范围/点赞倍率 + **Liblib 生图参数** + Liblib 看板 |

**前端约定**：`LIFE_FEED_MENU` + `initLifeFeedPage`；列表统一 `admin-table`；只读角色隐藏 `[data-edit-only]`；侧栏滚动记忆 `admin_sidebar_scroll`。分组标题展示名 **「🌿 生活流 Prompt」**（原「生活宇宙」，2026-07-13）；插入位置在 **「对话流 Prompt」之后**（`MENU_CONFIG` 占位 `group:'life_feed'`）。  
**子项顺序（2026-07-13）**：**生活计划 → 生活流人格拓展 → 朋友圈·内容 → 评论 → 感知 → 她的宇宙 → Prompt·生活流 → 发布&系统参数**。  
ops_admin 可见子项相对顺序：生活计划 → 内容 → 评论 → 感知 → 她的宇宙。

**相关技术债**：TD-033 日计划 LLM 日志摘要未做；TD-035 真删帖未分离；TD-036 本地图片上传未实现。联调台账快照：`docs/contract/drafts/生活流/M1_临时缺陷台账.md`（TB-LF-001~010 均已闭合）。

---
