# 未登录可用功能开放与登录弹窗改造 · 临时契约目录

> 状态：历史实施快照，非权威契约；有效条款已于 2026-08-02 整合到正式契约。  
> 执行依据：`docs/design/open_login/prd-delivery-runs/20260802T095138Z-open-login/steps-verified.md`  
> 正式权威来源：`docs/contract/current/life-feed/api.md` 与 `docs/contract/current/h5-app/api.md`。

## 文件

| 文件 | 范围 | 状态 |
|---|---|---|
| `M1_契约草案.md` | 三个匿名 GET、可选鉴权、共享登录弹窗和 401 策略 | 已实现并专项验证 |
| `M2_契约草案.md` | Index、Feed、Settings、Chat 访客态与登录恢复 | 已实现并浏览器验证 |
| `M3_契约草案.md` | Diary、Memory、Relationship 强鉴权回退 | 已实现并浏览器验证 |
| `M4_契约草案.md` | 总体验收、排除项、正式契约收口与已知仓库门禁 | 用户验收并已同步正式契约 |

## 边界

- 本目录只保留本轮代码行为的里程碑快照，不再作为当前契约来源；若与正式契约冲突，以 `docs/contract/current/` 为准。
- 匿名接口白名单固定为 M1 中三个 GET，不从“页面可访问”推导出更多匿名 API。
- 未引入游客身份、游客试聊、数据继承、数据库迁移、第三方登录、return URL 或写操作自动重放。
- 找回密码保持既有能力和风险，不在本轮加固。
- 本轮仅同步相关正式契约；未改写全局技术债索引，也未自行分配 TD-AUTH-01/02 全局编号。
