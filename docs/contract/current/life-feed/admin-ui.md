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

内容页的「置顶管理」按保存顺序显示全部成员，并标明可见、待发布、隐藏、未就绪或超出范围。运营可追加、取消、上移、下移并保存整组顺序。旧版本冲突时提示刷新，帖子总表始终按原发布时间排序。可写角色为 super_admin、ai_trainer，ops_admin、observer 可查看。后台记录置顶及重排的操作人、对象、时间和结果。

朋友圈内容页默认展示「帖子列表」。「视频草稿」显示待发布及更换中的编辑数量，按最近编辑时间倒序列出文案、处理状态和媒体到期时间。点击「继续编辑」恢复表单，只读角色点击「查看」。放弃的新帖草稿从草稿和帖子列表移除。

视频发帖可填写文案、话题、情绪及北京时间的计划发布时间。文案必填，话题支持中英文逗号分隔，情绪留空取「平静」。运营可在同一弹窗上传视频、检查预览、调整封面与取景。更换已提交的视频时带入原帖字段，提交后一起生效，沿用原发布时间及互动计数。

上传进度与排队、处理、失败和就绪状态分别显示。运营可关闭后恢复原任务，预览就绪产物、替换或恢复两档封面，选择裁切或保留完整画面并设置纵向位置（0～100，默认 50）。无文案、时间已过或所选媒体未就绪时禁用提交。到期草稿提示重新上传并保留文案及计划时间。

换片收件失败后，重开草稿会显示失败文件与原因。运营可重传，也可点击「沿用原视频」确认仍然就绪的文件，再手动发布或保存更改。普通编辑仅在调整发布时间时回写该字段，编辑文案保留原帖精确到秒的时间。

**前端约定**：`LIFE_FEED_MENU` + `initLifeFeedPage`；列表统一 `admin-table`；只读角色隐藏 `[data-edit-only]`；侧栏滚动记忆 `admin_sidebar_scroll`。分组标题展示名 **「🌿 生活流 Prompt」**（原「生活宇宙」，2026-07-13）；插入位置在 **「对话流 Prompt」之后**（`MENU_CONFIG` 占位 `group:'life_feed'`）。  
**子项顺序（2026-07-13）**：**生活计划 → 生活流人格拓展 → 朋友圈·内容 → 评论 → 感知 → 她的宇宙 → Prompt·生活流 → 发布&系统参数**。  
ops_admin 可见子项相对顺序：生活计划 → 内容 → 评论 → 感知 → 她的宇宙。

「生活流 Prompt」下方是独立的「养宠管理」分组。养宠的导航、业务权限与版本操作见[养宠后台契约](../pet-system/admin-ui.md)。

**相关技术债**：TD-033 日计划 LLM 日志摘要未做；TD-035 真删帖未分离；TD-036 本地图片上传未实现。联调台账快照：`docs/contract/drafts/生活流/M1_临时缺陷台账.md`（TB-LF-001~010 均已闭合）。

---
