# 产品设计与需求文档索引

> 材料边界：文中标注“本地留存”的过程稿、测试报告、截图及运行证据未随本次提交。历史验证结论保留原日期、环境和未验边界，不代表远端可复现或生产已验收。

> 本目录按功能聚合 PRD、开发步骤、实施计划、审查记录与专项规格；文件名保留原样，避免丢失既有版本语义和历史引用。

| 功能目录 | 内容 |
| --- | --- |
| [h5-appshell/](h5-appshell/) | [改造方案 v2](h5-appshell/改造方案-v2-20261022.md) · [唯一 STEP 进度](h5-appshell/steps-verified.md)：八页、候选及源码契约已交付；2026-10-23复查4项遗漏已修复并回归，原AppShell范围27/27完成，见STEP §8.33；并行新增开场体验的整体集成不计入本次结论；[上线前待验项](h5-appshell/execution/真机验收操作单.md#上线前待验清单2026-10-23复查)单列，生产未部署；旧v1不再作为开发入口 |
| [life-feed/](life-feed/) | 生活流 / 朋友圈 PRD、Prompt 规格、页面展示规范、开发步骤、审查与实施计划 |
| [admin-observer-security/](admin-observer-security/) | 管理后台观察者角色与安全加固 PRD、开发步骤、审查与实施计划 |
| [bgm_music/](bgm_music/) | [当前 PRD V1.3](bgm_music/PRD-LXM-BGM-V1.3-20261019.md)；[唯一 STEP／版本完结](bgm_music/steps-verified.md#bgm-v13-closure)：2026-10-21 按用户决定完成开发交付，保留未验项；[现行接口与播放器](../contract/current/bgm/api.md) · [数据](../contract/current/bgm/data.md) · [管理页](../contract/current/bgm/admin-ui.md) |
| [home-redesign/](home-redesign/) | [当前主页改版 PRD v2](home-redesign/PRD-林小梦主页改版-v2.md)；本期主页已于 `2026-10-03` 由用户确认真机人工验收通过，契约及倾斜参数已同步；Q201 未启用及专项量测保留后续跟进，见 [唯一 STEP 记录 §9.21](home-redesign/steps-verified.md#921-本期主页人工验收通过与文档收尾2026-10-03)；旧版 PRD、步骤、审查与进度见 [history](home-redesign/history/README.md) |
| [memory-retrieval/](memory-retrieval/) | [当前开发入口](memory-retrieval/README.md)：[PRD v3.2 后台闭环修正版](memory-retrieval/PRD-记忆存入与分路混合召回优化-v3.2-后台闭环修正版.md)与[STEP v3.2 后台闭环修正版](memory-retrieval/steps-verified-v3.2-后台闭环修正版.md)；重点文字漏召回、混淆与稍复杂查询，费用不作门槛，日常延迟/提升幅度仅记录；固定整轮180秒，六项评审修正及后台12个子用例已写回，静态复核PASS_WITH_RISKS / DOC_REVISED_WITH_GATES，M1/M2已核验，M3实施与验证见STEP §3，尚未部署新链；旧PRD v1/v2/v3/v3.1、原验证版STEP/v3.1及过程资料见 history（本地留存，未随本次提交；原引用：`memory-retrieval/history/README.md`）；语音读取升级仍延期至 [RP-004](../requirement-pool/active/realtime-voice-memory-recall/RP-004.md) |
| [openapi/](openapi/) | Open API / API Key PRD、开发步骤与第三方集成说明 |
| [realtime_voice/P1/](realtime_voice/P1/) | [实时语音通话 PRD v2.1](realtime_voice/P1/PRD-LXM语音通话仿真交互设计-v2.md)、[后台配置与管理设计 v1](realtime_voice/P1/DESIGN-LXM语音通话后台配置与管理-v1.md)、高保真状态 Demo 与交互规格映射；[当前接口契约](../contract/current/realtime-voice/api.md) · [数据](../contract/current/realtime-voice/data.md) · [后台](../contract/current/realtime-voice/admin-ui.md) |

## 共享参考

- [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md)：跨页面设计系统。
- [PROJECT_CONFIG_林小梦.md](PROJECT_CONFIG_林小梦.md)：项目实况与长期约束。
- [chat-message-pipeline.md](chat-message-pipeline.md)：对话消息链路说明。
- [product-development-plan-h5-chat.md](product-development-plan-h5-chat.md)：H5 对话产品开发方案。
