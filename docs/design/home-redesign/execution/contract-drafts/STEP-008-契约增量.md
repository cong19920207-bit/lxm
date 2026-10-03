# STEP-008 契约增量草稿：七类渐进动效

> 状态：STEP 草稿，STEP-008 已本地验证；未汇总为已过闸门的里程碑临时契约。  
> 对应里程碑：M3；日期：2026-10-02；来源：STEP-008。  
> 来源需求／验收：F201／F208／RQ-01；AC201／AC208／AC209。  
> 正式目标：docs/contract/current/h5-app/api.md；M5 全部业务验收后整合。

## 1. 本阶段摘要

呼吸、眨眼、发丝、待机、灯光、雨与城市窗星光由统一调度增强；无暂停原因且完整人物可用后才加载所需可选图；头发、眨眼与人物共享源画布坐标。暂停回到自然姿态，取消排队双眨眼与待机。

## 2. 契约变更

- 数据与存储：无新增持久化。
- 接口、事件、配置与兼容：单可选层坏图、Canvas／WAAPI 不可用不破坏完整核心图或业务入口；纹理缓存，环境优先 30fps；初始减少动态不下载可选图。
- 服务端接口／协议新增、删除：无。
- 实现位置：frontend/static/js/home-scene.js；frontend/static/js/home-scene-core.js；frontend/static/css/home-scene.css；frontend/pages/index.html。

## 3. 对现有正式契约的影响

更新首页场景／加载／交互的对应语义；保留当前开放页登录、端点和数据字段，不新增重复业务入口。

## 4. 验证证据

execution/evidence/home-m3/step-008-results.json；home-m3/scene-boundaries-results.json；home-m3/final-layout-results.json；最终源码复核汇总见 home-m3/final-browser-verification.json，实际状态以 steps-verified.md §9 为准。

## 5. 未决项与跨阶段依赖

Q201 性能预算未定，不据动效观察结算 AC210。

## 6. 正式整合后复验提示

核对本条与实际实现一致，运行对应首页浏览器行为与共享 API 兼容检查；真机、部署、声音或性能子条款不可由静态字符串或受控响应替代。

## 7. 正式整合说明

本稿不直接修改正式契约，不代表里程碑闸门通过；M5 按原计划汇总、整合并提交复验，未完成子条款保留待验。
