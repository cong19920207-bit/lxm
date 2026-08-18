<!-- prd-delivery-harness-meta {"schema_version":2,"run_id":"20260802T095138Z-open-login","artifact":"decision_addendum","owner_phase":"initialization","state":"IMPLEMENTATION_PLAN_READY","outcome":"PASS_WITH_RISKS","code_status":"NOT_STARTED","source_digest":"819af0688f9c56cfc9cbca57ea71aad2b64883753e0046c418f6926b52d5525f"} -->
# 用户决定补充记录

> Harness: phase=initialization; state=IMPLEMENTATION_PLAN_READY; outcome=PASS_WITH_RISKS; code_status=NOT_STARTED

## 用户原始确认

用户回复：“全部采用方案A”。原始上下文与回复已冻结在 `sources/user-decision-20260802T100750Z.md`，并以 `USER_DECISION` 来源 `user-decision-all-a` 纳入 `source_manifest`。

## 已确认口径

| ID | 决定 |
|---|---|
| UD-01 | 弹窗注册成功直接保存注册接口返回的 token，关闭弹窗并刷新当前页；独立 `login.html` 保持现有注册后再登录行为。 |
| UD-02 | 访客 Feed 初始化跳过 `/enter`、badge、SSE、评论回复已读和帖子停留已读，只匿名请求列表与 Header；显式写交互才打开登录弹窗。 |
| UD-03 | Chat 无 token 或 token 过期时静默显示现有页面壳，不请求或展示私有 timeline、Agent 消息、Feed badge；主动交互才打开登录弹窗。 |

以上只收敛上一轮 Phase 0 的 B-01～B-03，没有新增游客身份、游客试聊、数据继承、第三方登录或密码找回加固范围。
