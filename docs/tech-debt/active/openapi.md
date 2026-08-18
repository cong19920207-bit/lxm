# openapi 技术债

- 文档 ID：`tech-debt-openapi`
- 权威状态：`canonical`
- 功能范围：`openapi`
- 必读依赖：无
- 相关技术债：`TD-031`

> 状态完全沿用迁移源；本次迁移不确认清偿、不执行归档。

### [TD-031] Open API `check_send_quota`（10104）为非原子「先 SELECT 再 INSERT」（**待清偿**）

- **位置**：`backend/services/chat_service.py` → `fetch_open_window_user_rows` + `check_send_quota`（PRD V9 / §8 TD-NEW-05）；H5/Open send 共用。
- **问题**：10104 判定为 **先读未闭环 user 行、再 INSERT 新 user 行**，无 Redis 锁 / Lua / 事务级原子保护。H5 现网已如此；Open 搬迁后 **行为一致，不新增恶化**；极端并发（H5+Open 双端）下两请求可能同时读到 pending&lt;5 并均入队。
- **需求确认（2026-06-04）**：PRD V9 / TD-NEW-05 — **本期接受**，50 用户规模影响可忽略。
- **当前处理**：不改功能设计；Open v1 已落地，行为与 H5 一致；PRD §8 已标注。
- **待处理（单独立项）**：Redis 原子计数或等价机制；**须 H5 + Open 同期改造**。
- **触发时机**：并发 send 导致队列明显超过 5 且无叹号时评估。
- **风险等级**：**低**
- **关联**：PRD **TD-NEW-05**；**TD-030**（独立项）。
