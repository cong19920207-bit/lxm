# STEP-014 契约增量草稿：版本缓存与旧场景回退

> 状态：STEP 草稿，本地 IMPLEMENTED／VERIFIED；外层 HTTPS 和四类设备验收未完成。  
> 对应里程碑：M4；日期：2026-10-02；来源：STEP-014。  
> 来源需求／验收：F211／RQ-05；AC215／AC213。  
> 正式目标：docs/contract/current/h5-app/api.md；M5 总验收后整合。

## 1. 本阶段摘要

首页支持保留当前加载和数据逻辑的旧背景回退。缓存变更只覆盖首页 HTML、四个首页专用模块，以及两个首页资源目录内带内容摘要的图片。

## 2. 契约变更

- HTML 根节点的 `data-home-scene-mode="dynamic"` 为默认模式；运营回退时改成 `legacy` 并刷新。初始旧背景模式只请求精确路径 `/static/images/Index/Index.png`，不预热新场景七图；偏好保存值仍保留，动态状态明确显示“当前为旧背景，动态未运行”，倾斜操作反馈旧背景不支持倾斜，不申请权限。
- 默认模式不下载旧大图。两张核心图同时失败或截止时均未获得可用图片，切回旧背景；单张核心失败保留可用层，可选图失败沿用渐进保底。回退不重建 HomeStartup／HomeData，不重置原 5 秒／8 秒截止，不循环重试失败旧图。旧图也失败时隐藏坏图并保留底色和业务入口。
- 首页 HTML 和 `/static/js/home-data.js`、`home-scene-core.js`、`home-scene.js`、`/static/css/home-scene.css` 返回 `Cache-Control: no-cache`，关闭 ETag 和 If-Modified-Since 判断，避免同长度、同文件时间的新版本仍得到旧内容。其他页面、共享脚本、语音资源及非摘要图片维持既有策略。
- `/static/images/home-scene/v4/` 和 `/static/images/home-thumbnails/v2/` 下，名称带 12 位十六进制内容摘要的 WebP／JPG 成功响应返回 `public, max-age=31536000, immutable`；缺失图片的 404 不附长期缓存头。更新图片必须换内容摘要 URL，不覆盖同一不可变 URL 的内容。manifest 不套用此规则。
- 新增浏览器存储 key、服务端 API、权限模型、数据库迁移：无。核心静态层由早期内联挂载，场景脚本失败仍保留基础画面。
- 实现位置：frontend/pages/index.html::HomeStartup／mountScene／runHomeLoader；frontend/static/js/home-scene.js::legacy 原因及控件；frontend/static/css/home-scene.css；nginx/nginx.conf。

## 3. 对现有正式契约的影响

M5 收口时补充首页回退和专用缓存语义。原语音背景精确引用、开放页／访客门禁、四类有效 401 策略、主页独立取数和正常展示节奏保持。正式契约本轮只读。

## 4. 验证证据

execution/evidence/home-m4/step-014-cache-results.json：一次性 Linux 文件系统中的真实 Nginx 响应、大小写、缺失图 404、原 API／语音／后台转发、浏览器旧缓存与新版本切换。step-014-fallback-results.json：7 类默认／主动旧背景／双核心失败／单核心失败／存储与 API 挂起／坏旧图／偏好保留。final-browser-verification.json：最终生产源码 17 项浏览器回归。隔离语音 Nginx WebSocket／HTTP 回归通过，真实声音未验。

## 5. 未决项与跨阶段依赖

真实 HTTPS 测试地址、外层缓存配置、iOS Safari／Android Chrome／iOS 微信／Android 微信版本及实际响应未提供；不能据本地 HTTP 推定线上缓存、权限或声音验收通过。STEP-013 的真机选参与正式自动降级配置仍待完成。STEP-014 整项保持 IN_PROGRESS，M4 闸门 NOT_REACHED。

## 6. 正式整合后复验提示

核对最终模式、精确旧图路径、摘要 URL 与响应头；确认刷新可获取模式和资源新版本，回退不撤销加载／数据保护；在实际 HTTPS 与四类设备上补验。共享 Nginx 转发变更需运行受影响语音传输回归，传输通过不能代替真实声音。

## 7. 正式整合说明

本稿不代表 M4 闸门通过或发布授权。唯一进度与未验项维护在 steps-verified.md §9，M5 按已确认计划整合。
