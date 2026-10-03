# STEP-009 契约增量草稿：人物本地回应

> 状态：STEP 草稿，STEP-009 已本地验证；未汇总为已过闸门的里程碑临时契约。  
> 对应里程碑：M3；日期：2026-10-02；来源：STEP-009。  
> 来源需求／验收：F205／RQ-01／RQ-03；AC201／AC206。  
> 正式目标：docs/contract/current/h5-app/api.md；M5 全部业务验收后整合。

## 1. 本阶段摘要

人物头脸与上身有效区域使用原生可访问 button，支持点击、Enter 和 Space；当前回应连发合并，动态关闭／减少动态／暂停不启动；业务按钮、卡片和覆盖层优先。

## 2. 契约变更

- 数据与存储：无业务存储、关系写入。
- 接口、事件、配置与兼容：纯本地动作，无聊天／关系／模型请求或跳页；访客不初始化私有数据，不拦截正常滚动与缩放。
- 服务端接口／协议新增、删除：无。
- 实现位置：frontend/pages/index.html::.home-scene-hit；frontend/static/js/home-scene.js；frontend/static/css/home-scene.css。

## 3. 对现有正式契约的影响

更新首页场景／加载／交互的对应语义；保留当前开放页登录、端点和数据字段，不新增重复业务入口。

## 4. 验证证据

execution/evidence/home-m3/step-009-results.json；home-m3/final-layout-results.json；最终源码复核汇总见 home-m3/final-browser-verification.json，实际状态以 steps-verified.md §9 为准。

## 5. 未决项与跨阶段依赖

原生手机缩放／键盘由 M4 实测。

## 6. 正式整合后复验提示

核对本条与实际实现一致，运行对应首页浏览器行为与共享 API 兼容检查；真机、部署、声音或性能子条款不可由静态字符串或受控响应替代。

## 7. 正式整合说明

本稿不直接修改正式契约，不代表里程碑闸门通过；M5 按原计划汇总、整合并提交复验，未完成子条款保留待验。
