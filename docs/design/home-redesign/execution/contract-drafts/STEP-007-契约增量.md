# STEP-007 契约增量草稿：场景统一生命周期

> 状态：STEP 草稿，STEP-007 已本地验证；未汇总为已过闸门的里程碑临时契约。  
> 对应里程碑：M3；日期：2026-10-02；来源：STEP-007。  
> 来源需求／验收：F208／F209；AC208／AC209／AC202。  
> 正式目标：docs/contract/current/h5-app/api.md；M5 全部业务验收后整合。

## 1. 本阶段摘要

HomeScene.mount 幂等，每页唯一场景主 RAF；帧时间差 0—40ms，隐藏／bfcache 不排队场景帧，恢复不追赶时间；loading／hidden／reduced 基础原因共同治理，后续原因叠加。事件、计时器、特效和观察器登记后统一销毁。

## 2. 契约变更

- 数据与存储：无新增持久化；bfcache 保留原页面实例，真正 pagehide 清资源。
- 接口、事件、配置与兼容：读取 HomeStartup 已有状态，晚加载或 Session 跳过仍初始化一次；可选 API 故障隔离，不中断静态与业务。
- 服务端接口／协议新增、删除：无。
- 实现位置：frontend/static/js/home-scene.js；frontend/static/js/home-scene-core.js。

## 3. 对现有正式契约的影响

更新首页场景／加载／交互的对应语义；保留当前开放页登录、端点和数据字段，不新增重复业务入口。

## 4. 验证证据

execution/evidence/home-m3/step-007-results.json；home-m3/scene-boundaries-results.json；home-m3/native-bfcache-results.json；最终源码复核汇总见 home-m3/final-browser-verification.json，实际状态以 steps-verified.md §9 为准。

## 5. 未决项与跨阶段依赖

真机浏览器 bfcache 行为未由桌面推定。

## 6. 正式整合后复验提示

核对本条与实际实现一致，运行对应首页浏览器行为与共享 API 兼容检查；真机、部署、声音或性能子条款不可由静态字符串或受控响应替代。

## 7. 正式整合说明

本稿不直接修改正式契约，不代表里程碑闸门通过；M5 按原计划汇总、整合并提交复验，未完成子条款保留待验。
