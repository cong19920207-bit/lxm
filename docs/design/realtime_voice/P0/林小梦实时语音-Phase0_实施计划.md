# 林小梦实时语音 Phase0 实施计划

> 日期：2026-07-26  
> 需求源：`PLAN-林小梦实时语音-Phase0验证方案-v1.md`（v1.1）  
> 步骤拆解：`林小梦实时语音-Phase0_steps.md`  
> 进度：`docs/progress/林小梦实时语音-Phase0_progress.md`  
> 临时契约：`docs/contract/drafts/realtime-voice-phase0/`（**不合并**正式契约）

---

## 1. 锁定决策

- STEP 顺序与验收口径 100% 遵循 steps 文档；不扩正式 PRD（微信/计费/四路/危机/会后写入）。
- STEP-011 放在 M2 末尾；推荐链路：`010 → 007 → 011`。
- `preamble_memory_doc_ids` 超过 5 个：**加载时报错**（不静默截断）。
- 弱网（STEP-015）：本地 delay/loss 代理脚本为主，toxiproxy 作文档化备选。
- Phase0 实验接口**永不合并**进 `docs/contract.md` / `docs/contract/current/`。

## 2. 代码落点

| 区域 | 路径 |
|------|------|
| 后端包 | `backend/phase0_realtime_voice/` |
| API 前缀 | `/api/phase0/realtime-voice` |
| 测试页 | `frontend/pages/phase0_realtime_voice.html` |
| 单测 | `tests/test_phase0_*.py` |
| 挂载 | `backend/main.py`（仅实验注释挂载） |

禁止改动：`routers/chat.py`、`embedding_service.py`、`dashvector_client.py`、正式首页语音入口。

## 3. 里程碑

| 里程碑 | STEP | 闸门 |
|--------|------|------|
| M1 裸通话 | 001～005 | Chrome 裸通话往返、打断、事件、单测绿 |
| M2 会前小包 | 006∥008∥009∥011 → 010 → 007 | 完整/降级小包、归属校验、无现网 client import |
| M3 召回采数 | 012～016 | 1s 超时丢弃、导出脱敏、弱网四档、Go 模板 |

## 4. 临时契约规则

1. 单 STEP 完成：契约增量记入 progress「契约更新记录」，不改正式契约。
2. 里程碑验收通过后：汇总写入 `docs/contract/drafts/realtime-voice-phase0/M*_契约草案.md`。
3. 全部完成后仍不合并正式契约（与 PLAN §3/§10 一致）。

## 5. 每 STEP 完成定义

- 对应单测通过（页面类以手工+最小自动化）
- progress 勾选 ✅
- 前置 ✅ 后才进入下一 STEP
