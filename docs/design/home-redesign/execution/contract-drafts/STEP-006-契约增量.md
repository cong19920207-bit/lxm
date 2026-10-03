# STEP-006 契约增量草稿：首页独立模块与有界批次

> 状态：STEP 草稿，STEP-006 已本地验证；未汇总为已过闸门的里程碑临时契约。  
> 对应里程碑：M2；日期：2026-10-02；来源：STEP-006。  
> 来源需求／验收：F204／F203／RQ-02；AC204／AC205／AC202。  
> 正式目标：docs/contract/current/h5-app/api.md；M5 全部业务验收后整合。

## 1. 本阶段摘要

登录用户六模块并发独立更新；访客仅公共 Feed；每个批次绝对 8 秒，真实取消未完请求；登录快照、模块代次和头像异步回调避免旧数据写 UI，刷新／Feed／局部重试去重。

## 2. 契约变更

- 数据与存储：模块区分 pending／success／error／visitor／unknown；失败保留已知数据，局部重试。关系未知时日记 lockState=unknown；仅有效 level=0 才锁定。缺失必需字段的成功信封按模块失败处理。原 relationship_level 缓存保留，不新增私有持久化。
- 接口、事件、配置与兼容：既有 /relationship/status、/relationship/detail、/diary/list、/agent/unread-count、/feed/list、/feed/badge 端点与字段不变；有效当前 401 降级访客，存储故障／超时不伪造 401。主页监听 home-auth-change／token storage 更新；场景恢复不发完整 loadPage。
- 服务端接口／协议新增、删除：无。
- 实现位置：frontend/static/js/home-data.js；frontend/pages/index.html；frontend/static/js/api.js::updateAvatarEmotion。

## 3. 对现有正式契约的影响

更新首页场景／加载／交互的对应语义；保留当前开放页登录、端点和数据字段，不新增重复业务入口。

## 4. 验证证据

execution/evidence/home-m2/step-006-results.json；最终源码复核汇总见 home-m3/final-browser-verification.json，实际状态以 steps-verified.md §9 为准。

## 5. 未决项与跨阶段依赖

真实业务部署回归留 M4；受控响应不代表接入了实际后端。

## 6. 正式整合后复验提示

核对本条与实际实现一致，运行对应首页浏览器行为与共享 API 兼容检查；真机、部署、声音或性能子条款不可由静态字符串或受控响应替代。

## 7. 正式整合说明

本稿不直接修改正式契约，不代表里程碑闸门通过；M5 按原计划汇总、整合并提交复验，未完成子条款保留待验。
