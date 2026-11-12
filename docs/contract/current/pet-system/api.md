# 养宠接口与客户端

- 文档 ID：`contract-pet-system-api`
- 权威状态：`canonical`
- 功能范围：`pet-system`
- 实现入口：`backend/routers/pet.py`、`frontend/static/js/pet/`

## 客户端入口与鉴权

首页快捷区的养宠入口打开 `/pages/pet.html`。AppShell 使用 `frontend/templates/pet.html` 和 `frontend/static/js/pages/pet.js` 装配，独立页入口也可打开。未登录时可查看固定小狗介绍。进入领养流程需要登录，登录请求不自动重放领养或其他写操作。

`GET /api/pet/intro` 公开返回固定小狗标识、年龄文案和当前是否允许领养。其余养宠 API 使用用户 Bearer JWT，服务端按当前账号核对归属。路由设置 `Cache-Control: private, no-store` 和 `Vary: Authorization`，账号切换或离页后旧响应不能更新新页面。权限、错误与数据写入以服务端结果为准。

对外程序另使用现有 API Key 调用 [`/api/open/v1/pet/*`](../openapi/api.md#pet-openapi)。必须先在平台领养；未领养时只提供入口引导，Open 不开放领养。已领养后的喂食、抚摸、陪玩、查询与记录复用同一只宠物，成功程序互动等同本人参与，查询不计活跃。H5 手势模式与 Open 程序计时模式不能互换完成入口，其他状态、占用及奖励规则共享。

改名的空值与纯空格在客户端阻止提交，非法名字显示可修改的输入提示；服务端已明确拒绝的参数错误不进入结果未知恢复。日常房间收起可选回顾后恢复互动操作区；首次回访引导未退出时仍保留“回到日常”入口。

## 场景适配与音乐入口

房间以 `851×1848` 的原画坐标等比例居中铺满画布，屏幕比例不同时裁切超出部分，人物、小狗和球不按宽高分别拉伸。绘制、抚摸命中、球的拖动与可点击区域共用 `scene-viewport.js` 的正反坐标转换，视口变化时重新定位拖球区域。页面 SVG 图标保持原有固定正方形尺寸，介绍与成长图片沿用 `object-fit: contain`。

AppShell 与独立宠物页复用现有 BGM 悬浮唱片，保留播放／暂停、关闭本次及会话位置。唱片避开顶部导航、底部操作区、成长提醒和共同邀请；互动进行中与留影／照片回看时暂时隐藏，结束后按最新音乐状态恢复显示，不改变播放意图。动态内部页面通过 `pet:render` 及命名状态属性刷新避让区域。

`tests/test_pet_responsive_browser.cjs`（本地留存，未随本次提交）覆盖实际构建壳和独立页的六种视口比例、DPR 1／2、圆形像素与 SVG 尺寸、抚摸命中、实际指针拖球及音乐入口显隐／关闭；业务 API 使用受控数据。桌面 Chrome 验证不代表手机真机验收或生产构建已发布。

## 用户 API

以下路径相对于 `/api/pet`。成功响应使用共享 `ApiResponse`。业务失败以 `data.reason` 提供原因，鉴权失败走 HTTP 401。状态冲突和返回结果不确定时先核对原请求或尝试。

| 场景 | 方法和相对路径 | 约定 |
|---|---|---|
| 介绍与档案 | `GET /intro`、`GET /me` | 介绍不含个人数据。档案包含宠物状态及运行能力，读取档案可触发规则结算。 |
| 领养 | `POST /adopt`、`GET /adoption-result` | 提交 `name`、`acknowledged` 和 `request_key`。每个账号绑定一只宠物，结果查询不触发结算。 |
| 改名 | `POST /rename`、`GET /rename-requests/{request_key}` | 按请求键核对实际结果。改名不追改已归档的历史名字。 |
| 抚摸、陪玩和喂食 | `POST /interactions`、`GET /interaction-requests/{request_key}`、`GET /interactions/{attempt_id}`、`POST /interactions/{attempt_id}/finish`、`POST /feed` | 创建请求携带 `request_key`。交互结算由服务端结合尝试状态与证据处理，记录已完成事实。 |
| 共同玩球 | `POST /joint/invitations`、`POST /joint/{attempt_id}/accept`、`POST /joint/{attempt_id}/pass`、`POST /joint/{attempt_id}/resolve`、`POST /joint/{attempt_id}/cancel` | 后四条操作同一尝试。服务端区分邀请、接应、传球、完成与取消。 |
| 留影 | `POST /photos/growth-prompt`、`POST /photos`、`POST /photos/{attempt_id}/prepare`、`POST /photos/{attempt_id}/capture`、`POST /photos/{attempt_id}/archive`、`POST /photos/{attempt_id}/cancel`、`GET /photos/{attempt_id}` | 拍摄提交场景快照及阶段、记录、资源版本。拍摄成功可回看，手动归档后才进入正式记录。 |
| 记录与发现 | `GET /records`、`/events/{event_id}`、`/album`、`/preferences/{key}`、`/birthday` | 日记录按业务日查阅，事件和发现显示已保存依据。相册支持游标，默认 20 条，最多 50 条。 |
| 活动与回访 | `POST /view-sessions`、`POST /view-sessions/{session_id}/heartbeat`、`POST /returns/entry`、`GET /returns/{return_id}` | 心跳提交递增序号、前台状态和页面场景。回访读取冻结的离开期间依据。 |
| 即时表达 | `GET /expressions/{event_id}` | 查询指定已保存事件的表达状态或结果。 |

共同留影的照片保存在私有 OSS，访问链接经本人或有权后台接口校验后签发。旧照片不可用时保留历史依据并标示不可用。手机本地下载是后续版本需求，见 [RP-007](../../../requirement-pool/active/pet-photo-mobile-download/RP-007.md#rp-007)。

## 生效范围与联动

- 生效配置分规则、素材、运行开关和 AI 四域。新领养绑定成长规则版本。后续状态结算与互动按适用规则执行，历史事实、已归档快照和已保存文字保留原依据。
- 新领养、互动、自动照顾与 AI 表达由独立运行开关控制。模型生成另受事实资格、预算和并发约束。调试请求使用模拟输入并计入调试与全局额度。
- 管理接口使用独立前缀 `/api/admin/pets`，见[后台契约](admin-ui.md)。持久化与版本边界见[养宠数据契约](data.md)。
