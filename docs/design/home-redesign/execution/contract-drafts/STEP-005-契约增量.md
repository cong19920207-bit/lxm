# STEP-005 契约增量草稿：共享请求取消与失效保护

> 状态：STEP 草稿，STEP-005 已本地验证；未汇总为已过闸门的里程碑临时契约。  
> 对应里程碑：M2；日期：2026-10-02；来源：STEP-005。  
> 来源需求／验收：F204／F212／RQ-02；AC205。  
> 正式目标：docs/contract/current/h5-app/api.md；M5 全部业务验收后整合。

## 1. 本阶段摘要

request(method,path,data,options) 新增可选 signal／isCurrent；传入 fetch，并在请求前、响应副作用前、JSON 解析后检查有效性。被取消／失效的显式调用抛 AbortError／StaleRequestError，不交付数据或执行旧 401 副作用。

## 2. 契约变更

- 数据与存储：无新存储、无迁移。
- 接口、事件、配置与兼容：新选项未传时，网络失败仍 code=-1；原 legacy-login-page／silent-visitor／protected-home-modal／interactive-modal 有效 401 导航、清理、弹窗和回调保持。saveToken／clearToken 仅首页发布 home-auth-change，其他页无新增事件。
- 服务端接口／协议新增、删除：无。
- 实现位置：frontend/static/js/api.js::request／assertRequestCurrent／saveToken／clearToken。

## 3. 对现有正式契约的影响

更新首页场景／加载／交互的对应语义；保留当前开放页登录、端点和数据字段，不新增重复业务入口。

## 4. 验证证据

execution/evidence/home-m2/step-005-results.json；最终源码复核汇总见 home-m3/final-browser-verification.json，实际状态以 steps-verified.md §9 为准。

## 5. 未决项与跨阶段依赖

无新后端响应／状态码／鉴权协议。

## 6. 正式整合后复验提示

核对本条与实际实现一致，运行对应首页浏览器行为与共享 API 兼容检查；真机、部署、声音或性能子条款不可由静态字符串或受控响应替代。

## 7. 正式整合说明

本稿不直接修改正式契约，不代表里程碑闸门通过；M5 按原计划汇总、整合并提交复验，未完成子条款保留待验。
