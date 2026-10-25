# BGM 接口

> 材料边界：文中标注“本地留存”的过程稿、测试报告、截图及运行证据未随本次提交。历史验证结论保留原日期、环境和未验边界，不代表远端可复现或生产已验收。

- 文档 ID：`contract-bgm-api`
- 权威状态：`canonical`
- 功能范围：`bgm`
- 版本边界：2026-10-21 用户明确批准本版按“开发交付完成、未验项保留”完结。管理库、处理与恢复、匿名目录、H5 播放/跨页/控件及音频互斥已实现并在本地 Docker 生效；本契约登记当前行为，不等于所有 STEP/AC 或生产发布通过。用户反馈已人工测试，未提供具体设备和用例，因此不扩充逐项通过范围。结项、延期验收与清理待办唯一见 [STEP §9.28](../../../design/bgm_music/steps-verified.md#bgm-v13-closure)。
- 关联：[共享约定](../_shared/conventions.md)、[认证与 RBAC](../_shared/auth-rbac.md)、[数据](data.md)、[管理页](admin-ui.md)。

## 管理读取

五个 GET（下表三项及后文order/assets）均要求有效 Admin JWT，并使用数据库当前账号、角色、锁定/启用状态及 token_version。允许 `super_admin / ops_admin / observer`，拒绝 `ai_trainer / tech_ops`。认证失败 HTTP 401，角色拒绝 HTTP 403；前端角色不授予服务端权限。

| 方法与路径 | 输入 | `ApiResponse.data` |
|---|---|---|
| `GET /api/admin/bgm/tracks` | page≥1；page_size=20、1～100；search≤60字符，按字面包含匹配；state 可选 receiving/processing/ready/failed/deleting/delete_failed；filter=all（默认）/enabled/hidden/failed；sort=created（默认）/playlist | list/total/page/page_size/catalog_version/default_track_id/summary/default_track |
| `GET /api/admin/bgm/tracks/{track_id}` | 曲目标识 | track/catalog_version |
| `GET /api/admin/bgm/operations/{operation_id}` | 操作标识 | id/track_id/action/state/attempt/deadline_at/created_at/finished_at/failure_category（有限安全分类） |

已删除曲目不进入列表与详情。曲目/操作不存在返回 HTTP 200、业务码 `20200`、data=null。分页/枚举/长度非法由 FastAPI 返回 HTTP 422。默认 `sort=created` 按 created_at 降序、id 升序稳定排序；`sort=playlist` 先展示启用曲目并按 sort_position 升序，其余按创建时间降序/id升序。`filter=enabled` 只取启用，`hidden` 只取 ready 且未启用，`failed` 包含 failed/delete_failed；与旧 state、search 条件取交集。

`summary={total,enabled,hidden,failed}` 为全库未删除曲目汇总，不受搜索、筛选和分页影响，total 则仍为当前条件的匹配数。`default_track={id,name}|null` 独立提供全局默认曲，不要求它在当前页中。

曲目投影包含 id/name/record_version/audio_state/enabled/is_default/sort_position、独立 media_version/cover_version、audio_url/cover_url、duration_seconds/size_bytes、ever_published/hidden_at/deletable_at、created_at/updated_at。新增 `failure_category|null`：仅当前 audio_state=failed 时投影最新失败音频上传/重试操作的有限类别，未知类别收敛 processing_failed，不返回原始错误；`cleanup_summary={audio:{pending,failed},cover:{pending,failed}}` 分类型统计待清理（含 deleting）及失败数，计数不代表已到清理时间。资产只有归属本曲、类型匹配且 ready 时才提供 HTTPS URL。时间为 UTC ISO 字符串。

所有 GET 只查询，不创建目录头、不恢复过期操作、不启动转码或清理、不写业务记录或操作日志。不返回原始请求快照、来源路径、哈希、OSS key、进程 owner、凭据、内部异常或二进制内容。

## 共用写入边界

当前写入口使用 `BgmAuditRoute` 和 S/O allowlist。既有 observer POST/PUT/PATCH/DELETE 总闸不变。共用拒绝审计已经覆盖依赖鉴权拒绝、提交前撤权、参数拒绝与处理器失败；业务回滚后用独立数据库事务写 module=bgm、action=denied/failed。身份仅来自已验证 JWT 与数据库查询；无可信身份记为空，不从输入伪造 actor。记录请求标识、实时角色、HTTP 状态、分类及路由模板，不记录 Token、原始路径或异常详情。审计存储失败保留原拒绝结果并输出脱敏告警，不转为成功。

写入口新增如下；成功/失败使用现有log_operation记录。既有操作日志页已接BGM模块及动作筛选（STEP-008）。

## 音频上传与原操作恢复（STEP-003）

| 方法与路径 | 输入与结果 |
|---|---|
| `POST /api/admin/bgm/operations` | JSON：客户端先保存的UUID operation_id；action=upload_audio/retry_audio；规范化name；extension=.mp3/.m4a/.aac/.wav；mime_type；source_size；source_sha256。retry另需原track_id与expected_revision。返回安全操作投影。 |
| `PUT /api/admin/bgm/operations/{operation_id}/content` | 原始文件Blob，明确Content-Type；只能继续本人操作。流式计算实际大小与SHA256核对已登记快照；成功或明确处理失败返回操作投影，GET核对同一id。 |

仅S/O可写，V/A/T拒绝；接纳、接收和完成提交均重核账号、角色、token_version。名称trim后1～60 Unicode码点，控制字符拒绝、重复名允许。禁止额外字段，客户端不能指定存储位置、就绪状态或媒体版本。分页读角色不扩大写角色。

POST同id同规范化快照/提交人返回原记录，同id异内容或提交人HTTP409/20203；内容包含真实来源摘要、大小、格式、名称、动作和目标版本。原操作失败后用新id、新选源文件、原曲目id和最新记录版本重试，attempt递增且保留曲目身份。记录过期HTTP409/20202。资源忙碌HTTP429/20205；请求校验HTTP422。处理失败是state=failed，不表示上传成功；错误详情仅有限类别。

浏览器可能在断连后自动重发PUT。终态操作的文件重放先占用同一全库接收名额，再校验实际文件；同内容复用原终态，异内容409/20203，不重启处理、不产生新曲目或新Key。尚在执行时重复PUT明确忙碌，客户端查询原操作。结果未知、401/403或超时均保留原标识，不从“未查到”推断必须另建对象。

## 处理与运行边界

- 确认规格：源>0且≤100MiB，MP3/M4A/AAC/WAV真实格式与解码检查，时长>0且≤300秒；产物单一AAC-LC/M4A、目标96000bps、完整文件≤4MiB。当前采用44.1kHz、mono保留/最多stereo、faststart；采用值不升格为新增PRD门槛。移除源内嵌图像/视频、章节与无关元数据；独立封面不参与音频流程。
- 接纳使用MySQL全库单例槽位行锁，默认1；不在内存中另建排队平台。接纳后绝对总预算300秒，接收120秒，接收后处理最多180秒且受剩余总预算限制，保留10秒收尾，单次编码最多120秒。重查和分阶段调用不延长原处理预算；终态重放只做有界文件校验。
- 媒体在独立Python进程内处理，FFmpeg单线程，Linux虚拟内存1GiB、CPU180秒、单文件8MiB、描述符64；源文件只由有界接收器写入。独立墙钟定时器、Linux父进程死亡信号和进程组终止相互配合；重新获取所有执行者继承的文件锁，确认退出后才释放名额。
- `bgm_runtime`是应用生命周期内的5秒受限恢复检查，复用已激活环境的memory business epoch门禁，不由GET触发。过期无执行者接纳置失败；本地持久卷锁证明执行者已退出后收尾。异机缺失目录不是死亡证明，故障操作可标失败但名额隔离，不能凭租约超时重放并发。`BGM_TEMP_ROOT`指定运行根目录，代码缺省`/tmp/lxm-bgm-runtime`；仓库Compose设置`/var/lib/lxm-bgm-runtime`并挂载`bgm_runtime`命名卷，容器替换及同一主机各后端副本须保留/共享支持POSIX锁的该卷。
- 每个对象在PUT前注册曲目/操作/attempt归属及不可变Key。复用现有OSS配置自动生成`bgm/tracks/{track_id}/{version}.m4a`和HTTPS地址；写入禁止覆盖，超时仍核对原Key。通过OSS元数据和匿名HTTPS全文件摘要验证后才就绪，始终未启用。音频还必须通过下述实际来源CORS和Range验证；失败保留可定位资产与pending清理状态，不能靠更换Key盲重传。当前有效资产不自动删除。
- 音频与封面对象均写入正确MIME、内容摘要元数据及`Cache-Control: public, max-age=2592000, immutable`；更新通过新版本Key表达，旧对象依原资产归属等待手动清理。浏览器普通HTTP缓存可复用媒体，不据此承诺CDN或终端缓存立即失效。
- 业务提交先于成功响应；提交结果未知先查原操作，不把已成功提交改为失败。原attempt、已失效资格或撤权不能将曲目标就绪。临时源在收尾后删除；DB不可用时保留无源文件的owner锁凭据供后续恢复。

代理对content请求使用100m大小、关闭请求缓冲、接收空闲超时120秒、读取310秒；页面处理请求最长330秒并结合原deadline计算剩余等待。验收时部署候选镜像/同Nginx配置已取得120.088秒绝对接收失败、110.101秒慢收后真实AAC转码及原看门狗在总280.165秒内结束的隔离证据；后者的存储挂起为受控故障，不是实际OSS服务故障。原120/180/300秒及10秒收尾预算未改，不能据此声称实际等待满300秒、浏览器330秒超时或主业务容量通过。出处见下方本版证据汇总，当前版本匹配以结项核对为准。

2026-10-20 STEP-020实际发现原实现未检查CORS/Range的发布缺口，现已补齐：`BGM_MEDIA_ORIGINS`须明确列出所有实际H5 Origin，逗号分隔、最多16项、无路径/尾斜杠/通配符；HTTPS，或本机开发HTTP localhost/127.0.0.1/[::1]。音频缺少合法配置时在PUT前失败为`storage_configuration`。全文件GET带首个Origin，额外逐Origin请求前至多1024字节，要求206、精确Content-Range、正确MIME、内容与已核验全文件一致，且响应允许匿名跨域（`*`或精确Origin）。缺CORS/不匹配为`remote_cors`，Range状态/范围/内容错误为`remote_range`；不携带用户Token/Cookie，不自动修改Bucket规则、不放宽原worker绝对预算。普通封面显示不进入音频图，保持原图片验证。此修复仅约束新处理结果，不追溯改写既有ready记录；旧结果重新发布前须核对实际配置和播放。本次获准测试批次已另行完成真实来源CORS/Range与播放核对，验收结束后两曲均隐藏，满期精确清理仍为待办。

2026-10-19经用户明确授权，使用现有Bucket/CDN配置完成4秒、50,023字节AAC产物的单对象上传、匿名HTTPS完整读回并核对SHA256；随后精确删除并用源站存在检查确认清理。凭据与对象定位见执行证据`step003/oss-smoke-plan.json`（不含密钥）。这项证据不覆盖Range/CORS/实际部署容量；这些仍归STEP-020。

## 目录维护（STEP-004）

| 方法与路径 | 输入/结果 |
|---|---|
| `GET /api/admin/bgm/order` | S/O/V读取完整已启用顺序；返回catalog_version/default_track_id/tracks，每项id/name/record_version。单SQL读取目录头和全部成员，空目录也有同一版本；GET不写。 |
| `PATCH /api/admin/bgm/tracks/{track_id}` | S/O；operation_id、action=rename/enable/hide/set_default、expected_catalog_version≥0、expected_revision≥1。rename另需name；仅hide可带replacement_default_id。 |
| `PUT /api/admin/bgm/order` | S/O；operation_id、expected_catalog_version、完整track_ids排列。缺失、重复、未启用或未知ID整体409/20201；过期目录409/20202。 |

所有提交使用客户端预先保存的UUID。事务先锁catalog单例，重新授权，再按ID锁曲目；校验预期版本、状态、完整成员与默认。目录变更、操作结果和成功审计同事务显式commit。同id同提交人同规范化快照返回原结果（包括原目录版本），同id异内容/目标/提交人409/20203。提交响应丢失先查原记录；不会另建操作。提交后调用STEP-007缓存失效；失败不会回滚或改写已经提交的操作结果，旧缓存只在有限有效期内返回。

成功返回安全操作投影，并为这五类目录动作增加白名单`result`：catalog_version、default_track_id、ordered_track_ids、track_id、record_version。GET原操作返回同一快照，不能当作最新目录。上传操作仍不暴露其内部result/快照/位置；不存在额外的任意JSON透传。

启用要求ready、无活动尝试、同曲目audio资产已验证、版本/大小/MIME/时长有效且未退役/待清理；客户端伪造ready或资源位置不可绕过。首次和重新启用追加末尾，原目录为空则同时设默认，否则保留原默认；清空隐藏时间并记录曾公开。隐藏默认且尚有成员必须同次指定其中一首替代默认；最后一首隐藏同时清空默认。隐藏保留资产，以服务端UTC记录最近隐藏时间。删除中/失败不能执行目录动作。未启用改名也递增目录版本；重复名允许。

每次成功目录提交递增catalog_version；PATCH直接目标递增record_version。排序及隐藏后的位置压紧由目录版本约束，不额外递增非目标曲目的记录版本；所有PATCH同时要求两种版本，因此旧页面不能覆盖并发更新。音频/封面版本、URL和媒体对象不被目录维护重建。

## 独立封面维护（STEP-005）

POST/operations支持判别联合：音频原清单不变；action=upload_cover时须带track_id、expected_revision、expected_catalog_version、extension（.jpg/.jpeg/.png/.webp）、mime_type、source_size及source_sha256，不接受name/自定义URL/版本等额外字段。PUT原content入口按已登记动作分派，只有音频/封面上传操作可接收文件；目录操作或移除操作不可借content路由重放文件。处理/状态查询与音频复用同一个全库槽、绝对预算及受监督worker，不建立额外图片并发。

`DELETE /api/admin/bgm/tracks/{track_id}/cover`接受JSON operation_id、expected_revision、expected_catalog_version；S/O重新授权，同id同内容返回原结果，异内容冲突。成功只解除当前关联并生成独立cover_version，不执行外部对象删除。无封面为合法状态。

图片实现采用静态JPEG/PNG/WebP、源>0且≤5MiB、长边≤4096px；真实格式与MIME对应，完整解码、拒绝多帧/动画、损坏与伪类型。在受限worker内按EXIF方向校正、居中裁为512×512 WebP，清除元数据，保留透明度；200KiB只作为85/75/65质量优化目标，不是发布拒绝门槛。这些候选已通过真实解码和隔离链路验证，不把建议数值表述为PRD确认值。

封面接纳不改track音频状态/attempt/active_operation_id或启用标记。资源先登记bgm/covers不可变Key，再经SDK上传及匿名HTTPS完整摘要/MIME读回。完成事务依次锁catalog/slot，重新授权、核原owner/期限/曲目记录版本/目录版本/非删除态；确认后才关联新图。旧图在同事务记录retired_at/not_before（当前候选24小时）与pending清理；替换失败、撤权、版本冲突或删除态拒绝时保留旧关联及音频，新对象仍留原操作归属。STEP-006负责手动精确清理闭环。

保存/移除递增record_version与cover_version；仅已启用曲目的目录版本同时递增。隐藏曲目隐藏时间不重置，未启用/隐藏不因此启用，audio_asset_id/media_version/audio_url不变。封面操作的安全result白名单为track_id、record_version、cover_version、cover_url、catalog_version、association_removed、cleanup_state（pending/not_requested），分别表达关联成功和旧对象清理状态；不把待清理表述为对象已删除。

真实本地图片/worker/OSS SDK/HTTPS夹具以及实际API浏览器已通过；真实封面OSS单对象验证另获用户明确授权后完成：execution/evidence/step005/oss-cover-smoke-plan.json记录verified_and_cleaned，HTTPS完整内容一致、精确删除并确认不存在；未修改Bucket权限或业务数据。

## 手动删除与专属资源清理（STEP-006）

| 方法与路径 | 输入与结果 |
|---|---|
| `GET /api/admin/bgm/tracks/{track_id}/assets` | S/O/V；page≥1、page_size默认20/最大100。返回服务器UTC时间、隐藏/可删除时间、can_delete/can_cleanup、曲目/目录版本及分页资源id/kind/version/cleanup_state/failure_category/not_before，不返回bucket/key/凭据。已删除曲目保留只读资产核对；不存在为HTTP200/20200。 |
| `DELETE /api/admin/bgm/tracks/{track_id}` | S/O；operation_id、expected_revision、expected_catalog_version，禁止额外字段。仅显式手动发起，返回安全操作投影及逐对象结果。 |
| `POST /api/admin/bgm/tracks/{track_id}/cleanup-retry` | 同上。删除未完成时继续原曲目剩余资产；正常曲目只清理已到期、非当前关联的旧版本/已定位失败残留。 |

- 曾发布曲目须当前未启用且距最近hidden_at至少实际等待期（当前采用86400秒），服务端UTC在提交时判断；再次启用再隐藏重计。未发布且ready/failed、无活动音频/封面操作可直接删除。已启用、处理中、版本不符或权限不足拒绝；没有到期自动删除。
- 接纳事务锁catalog→全局slot→管理员→曲目；同id同提交人/同内容返回原操作，异内容20203。先提交deleting不可发布态及原资产定位，再逐个外部删除，每个确认结果独立提交。当前流程不删除公开目录成员，catalog_version不递增；删除状态转移递增record_version并废止旧音频attempt。迟到上传结果不能重关联或发布。
- 对象仅来自bgm_asset；删除前以kind/track_id/version重建完整专属Key并比对已登记bucket/key和当前Bucket配置。禁止前缀扫描、跟随URL、删除默认静态图或朋友圈对象。SDK DELETE不确定时仍核对同一Key；源站确认不存在才记deleted，不能推断CDN/终端缓存同步消失。
- cleanup与上传共用同一全库名额，独立可终止worker逐对象执行；候选配置为总180秒、单对象最多25秒、预留10秒收尾、每请求最多100对象。超时/未处理/部分失败保留定位并报failed/delete_failed，手动新操作只选剩余资产；批次上限不意味着全部完成。原操作重放只查询原结果，不隐式重试。崩溃恢复只将未完成项标失败并凭进程锁证明释放名额，不自动执行外部删除。
- 安全result为track_id/record_version/mode/track_deleted/remaining_count/assets；每项含id/kind/cleanup_state/failure_category。成功删曲保留最小曲目/操作/资产墓碑，普通列表和详情排除；结果未知保留原id。删除期间已完成的外部事实即使撤权仍登记，下一对象前重核实时权限，未完成部分保留可重试状态。
- STEP-006的SDK+本机HTTPS、跨连接隔离MySQL与Chrome管理页证据覆盖删除与恢复逻辑；早期获准单对象OSS测试已精确删除。随后本地业务库已迁移，并产生独立获准的2音频/2封面测试批次；该批次当前隐藏待满期，不据早期单对象清理声称整批删曲通过。

## 匿名公共目录与受控缓存（STEP-007）

`GET /api/bgm/catalog` 不解析用户/Admin Token，不依赖账号或个人偏好。无头、有效或无效Authorization均返回同一公开快照；客户端应显式无Authorization调用。现有私有接口与可选Bearer三接口的权限保持各自契约。

成功HTTP200、code=0，data为catalog_version、default_track_id、tracks有序数组。曲目字段仅id/name/media_version/audio_url/duration_seconds/cover_url/cover_version；URL为HTTPS、封面可空且独立版本。一个SQL读取目录头及enabled且ready成员和归属资产，默认必须在非空集合中，空集合默认null；内部不一致明确失败。没有源文件、内部Key、身份或偏好字段，也不下载或解码任何媒体。

缓存沿用现有Redis连接池。`bgm:catalog:v1`保存完整版本和生成时间，最大新鲜期60秒；存储TTL扣除回源耗时，内存命中最多1秒且仍检查原生成时间。`bgm:catalog:version-floor:v1`为单个版本水位，Lua原子更新阻止旧回源覆盖更高版本，迟到旧失效也不删除新值。同进程失效同时清内存并废止旧在途任务的缓存写入。已开始读取可返回原完整快照；不同进程的1秒内存缓存及失效失败后的有限旧缓存不构成实时推送承诺。

目录改名/启用/隐藏/默认/排序，以及已启用曲目封面保存/移除在业务事务提交后尝试失效；未启用图片变更不影响公共版本。Redis单操作预算0.25秒、SQL回源1.5秒、请求等待3秒，每进程一个在途回源；Redis异常/坏缓存下回源间隔2秒，回源失败冷却2秒。取消单个HTTP等待不取消共享查询。无法受控取得有效快照返回HTTP503、code=20207、data=null、Retry-After:2，区别于合法空目录。HTTP响应均Cache-Control:no-store，浏览器成功快照另由下文客户端目录协议管理。

上述参数已用专属Redis7/真实拒绝EVAL、真实本机断连、SQL超时、隔离MySQL并发与Chrome网络检查验证；本地Docker正式H5也已通过匿名目录接线、播放与目录更新局部核对。GET只可能写派生缓存，不写业务记录/审计或启动媒体处理。生产环境、目标手机和完整容量验收未由这些证据覆盖。

## 既有操作日志（STEP-008）

沿用`GET /api/admin/operation-logs?module=bgm&action=...`及详情/导出接口，没有独立日志服务。日志读取角色仍S/O/T/V，A拒绝；observer不可导出，不改变BGM管理仅S/O/V可读的规则。

动作：upload_audio/retry_audio、add_cover/replace_cover/remove_cover、rename/enable/hide/set_default/reorder、delete_track/cleanup_retry、denied/failed。封面操作API的action仍upload_cover；接纳时按当前有无封面记录服务端派生cover_action，后续审计沿用，失败也能区分新增/替换。旧操作无此字段仍记录upload_cover，页面保留旧记录筛选。所有action在既有20字符字段内。

成功/接纳/明确失败审计在对应业务事务内flush并提交；同操作重放不重复成功日志。通用载荷含operation_id/track_id/attempt/role/result/failure_category及当前record/media/cover/catalog版本；封面移除另含关联/清理状态，清理另含mode/track_deleted/remaining_count与最多100个资产id/kind/cleanup_state/failure_category。部分清理结果记录failed与实际剩余，不能当全成功。日志行保留操作者与UTC时间。

提前拒绝/回滚后的审计仍独立提交；只从已验证身份提取角色，从匹配路径提取合法UUID track_id/operation_id，其他原始路径值和请求正文不记录。没有源摘要、二进制、URL、Bucket/Key、凭据或五项偏好。既有读写双重脱敏保持；缓存失效失败和提交响应丢失均保留真实成功及原操作关联。

## H5单文档控制核心（STEP-010）

`frontend/static/js/bgm-controller.js`提供BgmController.create（注入测试/输出）和getDocumentInstance（同文档单例）。initialize只建立选择与意图，不自行创建媒体；会话曲目/合法同版本进度优先，其次有效最后手选、默认、首曲、空。意图、closed、actual、recoveryRequired与临时blockers分开；媒体pause事件不改用户意图，play兑现仍须输出适配器确认playing且contextRunning。

列表选曲/当前续播、手动下一首与顺序回首按PRD；仅手动列表/下一首写lastSelectedTrackId。自动请求不能覆盖暂停；关闭仅home播放或home-list选曲且无阻断时重开。pause/close/block/destroy废止旧代次，迟到媒体/进度/曲终钩子不复活旧输出。setCatalog同音频只更新元数据，失效选择默认/首曲且不主动播放；beforeAdvance为每次自然结束保留目录复核入口，单曲也执行。

核心不请求网络、不写会话、不直接接页面UI；增益与过渡由输出层负责，目录、跨页与控件由下文对应模块接线。控制规则有独立SIM证据，组合行为另有本地正式页面证据，均不替代目标手机验收。输出端口为play({signal})/silence/destroy/seek/getState及事件回调，所有权只属于本控制器，不使用通话音频对象。

## 独立输出、可取消过渡与能力协议（STEP-011）

`bgm-output.js`提供BgmOutput默认引擎及createEngine测试/独立注入入口。每引擎仅持有自己的AudioContext、MediaElementSource/Gain和按需HTMLAudioElement，crossOrigin=anonymous、preload=none、不用原生loop；不引用语音通话上下文。新曲在旧曲fadeOut及物理停止后建立曲源逻辑句柄并复用本引擎物理输出，pause意图先提交，完成淡出后保存实际进度；close/block/destroy立即静音停止，不等待渐变。旧过渡通过代次/AbortSignal作废；过渡失败仍停止旧输出并继续基本播放。

采用每段0.5音频秒的线性增益渐变，下载/等待play与context.resume不计入渐变；起点使用本引擎已设置的增益值，不读取尚未渲染的新AudioParam.value冒充当前起点。媒体play与context.resume在同一明确操作内发起，等待后仍检查真实媒体与上下文状态；权限拒绝/基本媒体404明确失败。暂停/切歌最新操作取消旧promise与过渡，旧media事件不能复活。

能力按实际建立的增益链→显式验证有效的media.volume→设备音量选取。默认不凭volume属性存在推断有效；未知环境增益不可用时使用设备音量，隐藏精细控件的协议为capabilities.preciseVolume=false、note=“此环境请使用设备音量”。capabilities另含mode/fadeAvailable/volume/muted。仅渐变自动化不可用时保留直接增益播放，不改fadeEnabled偏好。setVolume/setFadeEnabled/unmute/refresh为页面接线接口；setMultiplier只调运行时乘数不写偏好，活动管理由017负责。

零音量同时可靠设置media.muted，能力降级不自动解除；只有明确unmute把零值保存为0.30。设备音量路径不声称改变系统音量。改渐变开关使当前过渡安全收敛，下一次采用新值，不自行更改意图。输出端口增加fadeOut；控制器pause在真实渐变时返回完成Promise，意图在调用时已生效。

早期输出验证：Chrome155.0.8059.85有界面、真实本机HTTPS AAC与后增益波形通过，0.3→0.6实测幅度比2.013；注入增益不可用后的已验证媒体音量路径比2.020，设备音量路径零值/明确取消静音及无自动化直接播放通过。降级故障为受控注入，媒体与波形为真实浏览器。无头音频时钟停滞不计通过；采样使用实际音频时钟并设3秒墙钟上限。后续实际桌面Safari已核对非零增益、零音量及恢复，正式控件已接入；目标iPhone/Android/微信仍未覆盖，见本版证据汇总。

技术依据：[HTMLMediaElement.play](https://developer.mozilla.org/en-US/docs/Web/API/HTMLMediaElement/play)、[媒体元素音频源](https://developer.mozilla.org/en-US/docs/Web/API/AudioContext/createMediaElementSource)、[AudioParam取消自动化](https://developer.mozilla.org/en-US/docs/Web/API/AudioParam/cancelAndHoldAtTime)、[media.volume兼容性](https://developer.mozilla.org/en-US/docs/Web/API/HTMLMediaElement/volume)。这些资料只支持API边界，不代替本项目实测。

## 事件目录与统一故障预算（STEP-012）

`bgm-catalog.js`提供BgmCatalog.create/getDocumentInstance、read/peek及limits；固定读取`/api/bgm/catalog`，显式GET、credentials=omit、cache=no-store、仅Accept头、no-referrer、拒绝重定向，不调用自动附带Token的API.request。只接收完整合法公开快照：版本/唯一ID/有效唯一默认/HTTPS媒体/独立可空封面；失败和非法数据不转为空目录，也不续期较新的成功版本。

同标签页sessionStorage键`lxm_bgm_catalog_v1`保存version=1、完整catalog、successAt和独立failureAt；不可写时仅当前文档内存缓存。事件发生才读取：有播放需要的初始化/可见返回、明确播放/列表或下一首、面板、自然结束和明确重试；无周期请求/推送。采用新鲜期300000ms、旧成功目录最长1800000ms（边界不含），同文档年龄取墙钟与单调时钟差的较大者，倒退/非法时间视过期。过期按需请求，同文档在途合并；取消一个消费者不取消其他等待者，目录正文解码也包含在超时内。失败冷却30000ms只抑制自然事件读目录，冷却结束没有网络任务。有效旧目录回退保留原successAt；超龄不能用于新开、换曲或循环，当前已播放媒体可继续至结束。

`bgm-player.js`提供BgmPlayer.create/getDocumentInstance及initialize({session})、play(source)、select(id)、next、event(panel/visible/initialize/ended)、pause/close/block/unblock、state/checkpoint/subscribe/destroy。它协调目录和故障，媒体唯一所有者仍为BgmController；页面控件应经此层操作，不能绕开目录资格直接调用核心reconcile。核心新增defer播放意图、setCatalog(initialCheckpoint)、halt和onEnded接管口；正常独立核心beforeAdvance仍保留。

第一次冷目录恢复有效会话/最后手选优先，运行更新失效当前曲回默认/首曲；同音频的名称/封面/默认/顺序变化不重建媒体，下一首采用新排序。面板读取本身不授予播放资格，暂停/关闭/阻断不会发声。若新目录使当前曲目失效且已有意图仍允许播放，则按新默认/首曲继续；没有活动失败链时沿用本次面板读取的剩余总预算和重试计数，不重新取得30秒。

一次启动/切换/资源故障采用总30000ms单调截止时间，目录单次8000ms、整链自动重试最多1次且退避1000ms、媒体实际就绪最多15000ms、最多3个不同ID候选、故障后强制目录刷新最多1次；所有子阶段扣同一剩余预算，不重复取得30秒。资源缓冲事件有界等待，恢复playing则结束该次等待；持续失败停止当前输出并有限回退。权限拒绝/输出上下文未运行立即等待手动，不以换曲绕过。暂停/关闭/阻断/销毁取消当前链，迟到结果只能更新合法共享目录缓存，不能发声。

耗尽时核心recoveryRequired=true，`lxm_bgm_recovery_v1`仅保存v1的required/category，不存身份或偏好；下一文档初始化同时采纳该标记和传入session标记。只有明确BGM播放/重试/主页列表选曲解除，目录成功、自然事件、冷却或跳页不能重获预算。会话模块负责跨页保存和存储不可靠时的保护。state额外含catalogStatus（idle/loading/ready/stale/empty/error）、catalogAgeMs、recoveryScope及notice；catalog失败文案不同于有效empty和媒体resource失败。手选失败可恢复同版本有效旧曲进度，仅最新意图允许时执行；保留失败手选偏好，并以notice说明已发生选曲失败。

早期目录客户端验证：模拟时钟/媒体验证采用参数边界、共享预算、同ID不循环、故障恢复标记与取消；真实Chrome155+公共API/隔离SQLite+本机HTTPS AAC验证匿名网络、元数据/排序、跨文档缓存、真实404有限候选和原生自动播放拒绝。TTL跨越由客户端墙钟偏移注入，不是实际静置30分钟。后续本地业务库/正式页面与桌面Safari取得局部播放证据；这些不补齐所有目录故障和目标手机验收。

## 独立页面生命周期与会话（STEP-013）

`bgm-session.js`通过sessionStorage专用probe验证读、写、读回和删除；会话键`lxm_bgm_session_v1`保存version/revision、trackId/mediaVersion/position、intent/closed/recoveryRequired及bubble比例。没有账号字段、跨标签广播或按离开时间补算进度。非法进度归零，最终仍按当前音频版本/时长核对；封面版本不使进度失效。未知版本保留原文，当前页保守暂停。读写故障提示“本页音乐控制仍可使用；当前无法可靠保存会话，跨页恢复受限”，尽量写小型`lxm_bgm_session_unsafe_v1`标记；无法保存时只承诺当前页控制，后续初始化再次验证可靠性，不把能读旧值当可恢复自动播放。

`bgm-page.js`提供BgmPage.create/mount/getCurrent；旧HTML模式保持同文档幂等，AppShell模式按PageContext重入挂载并接入壳AudioService；模式为home/content/login。首页、朋友圈、聊天和设置直接接入；日记/记忆/关系在原页面门禁成立后接入，原私有API策略保持。共享api.js只在实际受保护页面回首页之前调用suspendAccess，同页登录弹窗不阻断BGM。独立登录页使用login临时阻断，不新启动、不记关闭；原曲目/进度与播放意图保留。Admin不接入。

初始化使用同标签会话优先于长期自动播放开关；存储不可靠则以暂停意图进入，当前页明确播放仍可操作。播放时采用2000ms本地检查点，意图/选择/关闭/恢复资格/实际状态变化即时保存，暂停渐变结束另存实际位置。尚无目录时保留待校验曲目与检查点，不把登录页保存成空曲目。输出getState在元数据未就绪时报告待执行seek值，权限拒绝不把待恢复进度误存为0。

visibilitychange隐藏与pagehide先同步停止输出和当前故障链，再保存检查点；已冻结旧页不再次覆盖其他文档写入的记录。pageshow/可见返回先重新读取并验证会话和完整目录缓存，再恢复核心选择/意图/关闭/进度，最后解除对应隐藏阻断；恢复本身不清人工恢复标记，仍经BgmPlayer事件与浏览器许可。真正非BFCache文档销毁才销毁文档级输出；普通AppShell路由卸载只清页面适配器，不能走文档销毁分支。persisted页面保留生命周期对象并对账后恢复，壳内统一恢复顺序以[H5契约](../h5-app/api.md#appshell-recovery)为准。不同标签独立，复制继承的关闭状态保守保持。

首页加载层顶部安全区的低存在感“暂停音乐”按钮只响应同一个BgmPage播放器。BGM未加入HomeStartup任何就绪条件/截止/业务数据请求，正文不重建控制器。主页面板和内容页气泡已按下文接入；当前本地证据及未覆盖的终端/手机验收以唯一执行记录为准。


## 主页控件与共享唱片（STEP-014）

`bgm-home.js`提供BgmHome.mount/current，持有公开第五格与背景音乐Bottom Sheet；控件经BgmPlayer操作，真实actual状态决定播放/加载/暂停/失败显示。只明确主页播放或选曲能够解除本次关闭，开合不会解除关闭。浏览器返回使用仅本页面板history标记，不改变页面地址；连续开合按最新状态收敛，只有一个可交互唱片节点和旋转动画。背景inert/滚动锁、焦点循环、Escape/遮罩/下拉收起及焦点恢复由面板负责，不使用人物场景恢复事件启动音乐。

`bgm-record.js`提供BgmRecord.create（element/disc/update/setLabel/destroy）。全站共享一份`/static/images/bgm/record.svg`默认黑胶；无图与图片失败回退同图，默认资源失败仍保留CSS黑胶/音乐符号与按钮。封面整图object-fit:cover、中心圆形，异步结果按曲目ID/封面版本/URL及代次确认；5秒等待上限，同实例最多记64个失败版本，不做图片重试循环。图片不触碰媒体、进度或偏好。播放时缩放1.18，采用12秒一圈；暂停/加载/关闭/阻断静止，隐藏/减少动态效果停持续动画。主页长名仅在实际播放且确实溢出时20px/s往返、两端各停1秒；完整名可在列表换行阅读，短名不滚动。采用值仅是本地实现参数，终端实际表现仍需核验。

`BgmOutput.previewVolume`只改运行预览并立即更新输出，`commitVolume`提交一次本地值并清预览，重复结束事件不重复写；`cancelVolumePreview`恢复已存值。设置页fadeEnabled调用setFadeEnabled收敛当前渐变，autoplayEnabled仅写偏好。motion沿用HomePreferences与原账号门禁，不影响BGM或淡入淡出值。没有偏好上报接口、账号命名空间或服务端偏好落库。

早期本地验证使用实际H5与Chrome155、真实匿名公共API/隔离SQLite/HTTPS合成AAC和增益；登录A/退出/登录B走正式弹窗与token/退出路径，认证响应为受控夹具。后续本地Docker正式页面与实际OSS、Chrome/Safari取得播放、音量、关闭及部分跨页证据；不把这些扩大为目标手机/微信、实际软键盘或完整账号往返声音验收，具体边界见本版证据汇总。


## 六页悬浮唱片（STEP-015）

`bgm-bubble.js`提供BgmBubble.mount/current，限定Feed/Diary/Memory/Relationship/Chat/Settings且BgmPage模式为content；日记/记忆/关系原门禁在挂载前执行。Index、独立Login和Admin没有气泡。复用BgmRecord及当前封面；未知目录、加载、暂停、权限拒绝或临时资源失败保留可恢复入口，确认为empty、本次关闭、call/access阻断则移除气泡节点和命中区。打开操作区只有播放/暂停（失败时明确重试）与关闭本次，不能选曲、下一首或调音量；泡内play使用bubble来源，不解除本次关闭。

采用48px唱片、右侧16px加安全区、竖拖阈值6px、拖后400ms抑制指针生成的误点击；键盘上下箭头可按0.1比例移动。拖动从当前实际显示位置计算，松手保存x=1及可用高度y比例到现有BgmSession，不新增长期偏好键或账号字段。resize/旋转/visualViewport/页面滚动重算并夹入边界，扩大操作区所需高度也预留；空间不足暂时隐藏控件，不改变声音或意图。

预定义适配：Feed返回栏、图片预览/评论面板/首次加载层；Diary返回栏与安全区；Memory顶部栏、底栏/recenter、抽屉及遮罩；Relationship返回栏和升级覆盖层；Chat顶部栏、可见视口及输入/发送区；Settings顶部栏、退出区，并按明确的设置开关/可点行/展开表单避让，不自动识别任意内容。登录弹窗、已有确认窗与全屏状态共用临时隐藏规则；覆盖层结束重新读取最新状态，不能复活关闭的节点。仅观察已命名的区域属性/尺寸及body直接新增模态根，不扫描画布动画后代或轮询网络。

本地实际六HTML+Chrome/HTTPS AAC/公共API验证控制、右侧竖拖、相对恢复、横屏、关闭/空态移除、私有页门禁与图片版本竞态。Feed预览/评论和Relationship升级调用原产品函数；Memory抽屉与键盘缩小视口采用明确状态注入，只证明适配处理，不能替代实际抽屉操作/手机键盘。当前Chrome未稳定出现原生拒播前提，气泡拒播UI以受控NotAllowedError注入后明确点击、原生AAC恢复验证；原生权限处理证据沿用014，不把受控注入列为原生拒播。STEP-015仍IMPLEMENTED，终端及这些剩余真实交互待验。

## 真实通话互斥（STEP-016）

BgmPage挂载及voice:audio-occupancy事件都读取VoiceEntry.isAudioOccupied()最新聚合状态。获准准备即block(call)并close，冻结旧播放/故障链并保存本次关闭；BGM晚于语音初始化也保持关闭。释放只unblock(call)，不得复播或清除关闭标记；通话中主页明确播放也无效，真实清理后才允许主页明确播放/选曲重开。气泡随call/closed状态退出。

VoiceEntry能力拒绝不改变BGM；获准用途说明、拒麦、取消及失败均属于已关闭阶段。本地输出关闭成功、待采麦操作收尾及精确远端清理/可信终态按准备和call归属确认，未知保守保持。接点及旧回调隔离见[语音契约](../realtime-voice/api.md)。本地Docker/Chrome实际采麦及输出前停播、32秒真实通话挂断、等待接听取消与人工重开已有证据；另有两次回复结束、短暂reconnecting和silence_timeout期间保持关闭的局部观察。实际权限拒绝、成功重连/恢复流、完整失败创建清理、Safari通话及目标手机/微信仍未验，不能将短暂重连状态当恢复成功。

## 短音频临时衰减（STEP-017）

`bgm-ducking.js`提供BgmDucking.create，八类允许页面由BgmPage建立一个ducking实例；接入方调用`BgmPage.getCurrent().ducking.begin(id, {timeoutMs})`取得不可变活动句柄，使用句柄的end/cancel/destroy配对释放。同一活动ID未释放前重复begin返回同一句柄；结束后可重用ID，旧句柄不能释放新一代。默认30秒超时，允许0＜timeoutMs≤60000；到期自动释放，模块销毁取消全部计时并解除本模块状态，不产生负计数。

可靠增益或已验证媒体音量模式使用当前用户音量×0.25，最后一路结束才还原乘数1；该比例为本期采用值，不是新增产品硬阈值。setMultiplier可请求按当前fadeEnabled/capability进行0.5秒变化，用户中途调音量及取消渐变时重新收敛到最新目标，音量0始终静音。衰减/恢复不保存音量；只有原用户调音量操作保存新值。

输出能力未知或无可靠衰减时持有short-audio临时阻断，立即暂停并保留播放意图；活动全部释放后，仅最新意图仍play且未关闭、无其他阻断、无人工恢复要求时通过BgmPlayer.resume恢复。resume不新设播放意图、不清recoveryRequired，复用原目录与有限故障链。旧结束的延迟恢复还受活动修订号保护，用户暂停/关闭/通话/隐藏优先。页面销毁先停页，再释放活动，不能复活输出。

当前独立短TTS产品链不存在；本期只有接口模拟及实际Chrome AAC增益/降级能力验证，不能声明已新增TTS业务。重叠、同ID换代、取消/销毁/超时与优先级SIM通过；实际增益25%、改音量恢复、渐变与设备降级暂停通过。H5-M输出能力仍待验，采用比例的主观听感尚未用户确认。

## 普通媒体与未知中断（STEP-018）

`bgm-media.js`提供BgmMedia.create，每页BgmPage.mediaActivities可显式begin(id, {audible, kind})，kind为media或recording。无声media不占用；录音即使无输出仍暂停BGM。活动句柄end/cancel/destroy按当前归属释放，同ID重复开始幂等，旧句柄不解除重用ID。多路共用ordinary-media阻断，最后一路才解除；与call/short-audio/hidden等其他阻断分开。

释放方仅在自身已结束且允许尝试恢复时传resumeAllowed:true，仍重检最新暂停/关闭/人工恢复和所有其他阻断，再走普通浏览器许可与有限播放链。缺省或未知许可在仍有play意图时设置人工恢复要求，不能让后续另一路“允许”覆盖该要求；模块销毁释放资源并保守等待明确操作。无活动二进制/偏好持久化和全站音频扫描。

原生BGM media意外pause（非用户/程序已持有阻断、非自然ended）以及运行中的AudioContext非running，都保留用户意图但进入手动恢复。明确播放操作的context.resume尚未完成时，不把先到的playing或旧statechange判为失败；等待本次resume/play结果，晚到旧pause且元素实际已重新播放时忽略。真实拒绝仍保留手动入口；没有控制系统音频焦点的承诺。

实际接入清单：八类H5及自有非vendor脚本未发现独立普通带声媒体/录音入口；真实VoiceEntry继续使用其独立生命周期，不重复包装。本期接口受控模拟及Chrome原生其他Audio、pause/context.suspend恢复通过；不冒领真实系统电话、其他App或H5-M中断验证。

## 单候选无声准备（STEP-019）

`bgm-preparation.js`提供BgmPreparation.create，每页由BgmPage.preparation持有并销毁。当前曲实际playing、意图play、未关闭、无阻断/人工恢复、页面可见且主页面加载完成、目录未超龄，才考虑一个顺序下一首。采用剩余时间≤min(20秒,曲长四分之一)，单曲、未知时长、离线、省流量、已知2G/3G或下行低于1Mbps时跳过；不存在可选网络识别API时仍可尝试。参数是本地采用值，未宣称手机或网络容量已验证。

候选HTMLAudioElement只用preload=metadata、muted、volume=0、crossOrigin=anonymous，不调用play、不接AudioContext或整首decode，不写偏好/意图/检查点。主页面及当前曲优先，延后一轮任务启动；目录刷新中的有效旧候选可保留，刷新结束前不新发准备。一个播放代次/当前音频/下一首音频组合只尝试一次；5秒元数据超时或error仅释放该候选，不启动当前故障链、不试遍歌单。

暂停/关闭/隐藏/离页/通话/媒体阻断/目录超龄取消并尽力释放src，迟到回调按候选归属失效。重排、隐藏、手选或音频版本/URL变化重检；只换封面/名称/目录版本保留仍有效的音频准备。准备对象不直接晋升为播放器；真正切歌始终由BgmPlayer重新核对目录、资格、最新意图及统一预算，按当前渐变设置加载，可能受益于浏览器普通HTTP缓存。没有SW、Cache API、IndexedDB或音频二进制本地库。

早期本地SIM与Chrome/HTTPS AAC/匿名公共API验证单候选无声、封面刷新保留、隐藏/重排后的实际切歌、可选404及省流量跳过、关闭时在途取消；其TTL/seek/rate及网络故障为受控输入，no-store夹具不作为OSS缓存命中证据。后续本地Docker正式Chrome页面已观察实际OSS下一首候选就绪及自然切换，原生媒体诊断另取得Chrome/Safari的HTTP缓存和Range局部证据；不合并声称所有Safari准备分支、就绪候选取消、实际缓存淘汰或目标手机通过。

## 本版交付与验证边界（2026-10-21）

本版按用户明确决定结束开发和扩展测试，保留PRD要求及逐项原始结果；“交付完成”不把`PARTIAL_EVIDENCE`或`NOT_RUN_FULL_FLOW`改成PASS。当前本地Docker已运行BGM后端及冻结迁移`v9h_bgm_001`，共用POSIX锁运行卷和明确`BGM_MEDIA_ORIGINS`为部署前提；生产部署及新的外部配置仍须对应授权。

| 有效证据 | 能支持的结论 | 保留边界 |
|---|---|---|
| [真实媒体批次与本地部署进度](../../../design/bgm_music/steps-verified.md#bgm-v13-closure) | 正式后台上传/试听/启用、独立封面及前台实际OSS播放；原CORS问题已定位修复 | 本地2音频/2封面获准测试批次，不代表生产发布或满期删除完成 |
| Chrome HTTP缓存/Range（本地留存，未随本次提交；原引用：`../../../design/bgm_music/execution/evidence/step020/http-cache-live-check.json`）、Safari HTTP缓存/Range（本地留存，未随本次提交；原引用：`../../../design/bgm_music/execution/evidence/step020/safari-cache-live-check.json`） | 原生媒体真实响应与解码；Chrome受限带宽下未缓冲区Range后继续播放 | 独立媒体诊断，非全量正式流程；无实际缓存淘汰、手机或Safari未缓冲区证明 |
| 正式下一首准备（本地留存，未随本次提交；原引用：`../../../design/bgm_music/execution/evidence/step020/preparation-formal-live-check.json`） | Chrome正式页实际OSS单候选就绪、当前曲继续及自然切换 | Fast4G模拟；未证明所有候选取消、长歌单或移动端 |
| UI对齐（本地留存，未随本次提交；原引用：`../../../design/bgm_music/execution/evidence/ui-alignment-20261021/results.json`）、本地部署更新（本地留存，未随本次提交；原引用：`../../../design/bgm_music/execution/evidence/ui-alignment-20261021/docker-update.json`） | 已确认C01–C07/A01–A13控件/布局、全库汇总与完整排序协议的受控验证及本地部署接线 | UI验收使用隔离SQL/受控认证和媒体；部署正常读取不替代新一轮全量手机或媒体转码验收 |
| 真实通话时序（本地留存，未随本次提交；原引用：`../../../design/bgm_music/execution/evidence/step020/voice-timing-live-check.json`）、回复/网络局部观察（本地留存，未随本次提交；原引用：`../../../design/bgm_music/execution/evidence/step020/voice-network-live-check.json`） | 原生采麦/输出前停止，挂断、取消及回复结束不复播；可信终态后仍关闭 | CALL-01决策兜底事实保留；无成功重连、实际拒麦或完整失败创建清理验收 |
| 代理绝对接收预算（本地留存，未随本次提交；原引用：`../../../design/bgm_music/execution/evidence/step020/nginx-deadline-live-check.json`）、慢收与处理看门狗（本地留存，未随本次提交；原引用：`../../../design/bgm_music/execution/evidence/step020/staged-budget-live-check.json`） | 验收时部署候选镜像/代理配置、原预算和进程组回收次序的隔离运行证据 | SQLite/lifespan off及受控本地存储挂起；不扩大为真实OSS故障、浏览器330秒、业务容量 |

手机/微信、未覆盖异常分支及完整跨环境验收按已接受交付边界保留；用户未说明范围的人工测试只记作人工反馈。当前测试资源隐藏、满期精确清理及临时设置恢复的最新状态只在[唯一结项记录](../../../design/bgm_music/steps-verified.md#bgm-v13-closure)维护，不在契约复制易过期的资源版本、清理截止或浏览器标签状态。

## AppShell 源码增量（2026-10-23）

本增量描述AppShell模式；旧HTML回退分支及本文件既有历史验证记录保留原适用范围。当前设备证据见[AppShell唯一进度](../../../design/h5-appshell/steps-verified.md#8-h5-appshell-step进度)，不将未验目标记为通过。

<a id="appshell-delta-07"></a>
### H5单文档控制核心/独立输出

文档级 BGM 持有单一物理媒体元素、source、gain 和 context。普通路由只替换页面 adapter，不重播、换源、seek；曲源逻辑代次隔离迟到事件。页面阻塞、call/媒体租约和用户关闭意图独立合并，解除一个阻塞不能越过其他阻塞。

<a id="appshell-delta-19"></a>
### Login临时阻塞与意图

Login路由在旧页释放前安装临时音频阻塞，退出归还本句柄后对账；保留曲目/进度/播放/暂停/关闭/人工恢复意图。共享登录窗无此阻塞。

AuthService访问失效交接另持有access句柄，覆盖清身份/本地回滚/Home或Login准备与挂载；新导航、换身份、失败或完成只释放原owner，不能解除新事务占用。交接后由当前有效页统一对账，暂停/关闭/人工恢复要求不变；同页共享窗不取得此句柄。

<a id="appshell-delta-24"></a>
### 六页悬浮唱片

共享音乐气泡增加当前page root的直接childList观察，用于动态升级层；不观察图形或动画子树。原文档body入口兼容。 当前页面适配器卸载即取消观察和订阅；跨路由的BGM播放器与稳定物理输出仍由壳持有。

<a id="appshell-delta-31"></a>
### 偏好与双向会话兼容

BGM旧键/schema保留。未知自动播放偏好且无已知兼容显式值时安全默认false，不覆盖未知记录；新用户默认及已知用户显式设置保持。未知session和双写失败在当前页面显示对应降级提示，由页面适配器订阅、卸载移除；旧→新→旧保留暂停/关闭/进度/人工恢复意图。无新增业务存储字段。 未知版本的读取不重获自动播放许可；可见提示由当前页面适配器拥有并在卸载时移除。

<a id="appshell-entry-audio"></a>
### AppShell 开场音乐选择（2026-10-23）

新文档在播放器初始化前取得独立entry阻塞，任何既有自动播放偏好 / 会话恢复均不能在开场选择前出声。准备阶段只提前读取目录；目录已可用时，“开启并进入”从原始点击同步调用现有播放 / AudioContext恢复路径，不先等待权限、动画或网络。目录尚不可用或浏览器拒播时沿用真实失败 / 手动恢复入口，不声称手势解锁一定成功，也不阻塞页面进入。

主按钮视为本次显式主页开启，可解除本次暂停 / 关闭意图；“直接进入”先写暂停再释放entry阻塞。两者只释放自己的句柄，保留Login、通话、其他媒体及隐藏阻塞；不改自动播放等持久偏好。方向授权等待时音乐可独立开始，视觉仍等待允许 / 拒绝。后台取消未完成开场会重新取得entry句柄，旧授权不能释放它；同文档切页不重启播放器或再次展示开场。旧HTML分支及既有BGM验证边界保留，新增证据见[开场接入记录](../../../design/h5-entry-experience/设计说明.md#产品接入验证2026-10-23)。


2026-10-23开场集成的本地预览曾使用未在音频CORS允许名单中的8924来源，两首真实歌曲均被拦截；现改为已允许的 `http://localhost:8000` 独立预览，旧入口重定向。启动时核对实际曲库的匿名206与Origin允许头；浏览器仍直连原始HTTPS资源，不修改catalog或媒体、不代理音频、不修改Bucket规则。实际两曲播放输出、切页连续播放已在Chrome核验，证据见开场真实链路（本地留存，未随本次提交；原引用：`../../../design/h5-entry-experience/implementation-evidence/entry-live-checks.json`）。该本机结果不覆盖新部署Origin、iPhone或微信；新来源仍须遵守上述 `BGM_MEDIA_ORIGINS` 和真实CORS/Range验收要求。
