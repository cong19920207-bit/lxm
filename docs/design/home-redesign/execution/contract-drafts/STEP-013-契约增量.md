# STEP-013 契约增量草稿：调度、质量策略与量测接点

> 状态：STEP 草稿，局部 IMPLEMENTED，Q201 正式选参未完成；未汇总为已过闸门的里程碑临时契约。  
> 对应里程碑：M3；日期：2026-10-02；来源：STEP-013。  
> 来源需求／验收：F209／F208／RQ-06；AC210／AC208。  
> 正式目标：docs/contract/current/h5-app/api.md；M5 全部业务验收后整合。

## 1. 本阶段摘要

单主 RAF，环境优先 30fps，DPR≤1.5；雨／光点纹理缓存；支持量测像素预算限制。质量顺序为减少雨和星光、停止发丝、静态，同实例暂停／弹窗／bfcache 不升档，新实例重新评估并保留偏好／系统抑制。

## 2. 契约变更

- 数据与存储：无质量持久化，偏好 key 不变。
- 接口、事件、配置与兼容：HomeScene.quality 采集帧间隔、长任务与可用堆指标，HomeScene.motion 记录人物回应首帧延迟；quality.configure 接受带来源的 pixelBudget／windowMs／minimumFps。正式 Q201 参数未提供，生产默认未启用自动降级判断；测试参数 200000px／300ms／30fps 只在夹具，不当作最终配置。
- 服务端接口／协议新增、删除：无。
- 实现位置：frontend/static/js/home-scene.js::quality／motion；frontend/static/js/home-scene-core.js。

## 3. 对现有正式契约的影响

更新首页场景／加载／交互的对应语义；保留当前开放页登录、端点和数据字段，不新增重复业务入口。

## 4. 验证证据

execution/evidence/home-m3/step-013-controlled-results.json；home-m3/native-bfcache-results.json；最终源码复核汇总见 home-m3/final-browser-verification.json，实际状态以 steps-verified.md §9 为准。

## 5. 未决项与跨阶段依赖

待四类真机选定像素预算、统计／降级窗口和判定口径，接入正式配置后复验，不能声称 AC210 或 M3 完成。

## 6. 正式整合后复验提示

核对本条与实际实现一致，运行对应首页浏览器行为与共享 API 兼容检查；真机、部署、声音或性能子条款不可由静态字符串或受控响应替代。

## 7. 正式整合说明

本稿不直接修改正式契约，不代表里程碑闸门通过；M5 按原计划汇总、整合并提交复验，未完成子条款保留待验。
