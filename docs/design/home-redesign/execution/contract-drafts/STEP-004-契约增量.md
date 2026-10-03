# STEP-004 契约增量草稿：有截止加载

> 状态：STEP 草稿，STEP-004 已本地验证；未汇总为已过闸门的里程碑临时契约。  
> 对应里程碑：M2；日期：2026-10-02；来源：STEP-004。  
> 来源需求／验收：F203／F201／RQ-02；AC202／AC203／AC213。  
> 正式目标：docs/contract/current/h5-app/api.md；M5 全部业务验收后整合。

## 1. 本阶段摘要

背景和完整人物核心等待至多 5 秒，正常 3000／500／550ms，启动绝对 8 秒兜底；API、头像、可选图不作加载门闩，遮罩释放后入口立即可见。

## 2. 契约变更

- 数据与存储：原 Session lxm_home_loader_done 仍为 1；刷新走正常加载，合法标记非刷新返回跳过；读写失败不中断，无法读取 token 时保留 unknown。
- 接口、事件、配置与兼容：HomeStartup 只用于首页启动／安全存储／内存登录快照；共享 API 的默认非首页行为保留。
- 服务端接口／协议新增、删除：无。
- 实现位置：frontend/pages/index.html；frontend/static/js/api.js；frontend/static/css/home-scene.css。

## 3. 对现有正式契约的影响

更新首页场景／加载／交互的对应语义；保留当前开放页登录、端点和数据字段，不新增重复业务入口。

## 4. 验证证据

execution/evidence/home-m2/step-004-results.json；home-m2/step-004-boundaries-results.json；最终源码复核汇总见 home-m3/final-browser-verification.json，实际状态以 steps-verified.md §9 为准。

## 5. 未决项与跨阶段依赖

四类手机加载与部署仍归 M4。

## 6. 正式整合后复验提示

核对本条与实际实现一致，运行对应首页浏览器行为与共享 API 兼容检查；真机、部署、声音或性能子条款不可由静态字符串或受控响应替代。

## 7. 正式整合说明

本稿不直接修改正式契约，不代表里程碑闸门通过；M5 按原计划汇总、整合并提交复验，未完成子条款保留待验。
