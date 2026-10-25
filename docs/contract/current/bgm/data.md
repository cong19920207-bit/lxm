# BGM 数据

- 文档 ID：`contract-bgm-data`
- 权威状态：`canonical`
- 功能范围：`bgm`
- 版本边界：冻结迁移`v9h_bgm_001`已在获准的本地Docker业务库生效，五表承接实际管理和测试媒体流程。2026-10-21 用户批准本版开发交付完结，未验项及满期资源清理仍保留；当前部署与资源状态唯一见[结项记录](../../../design/bgm_music/steps-verified.md#bgm-v13-closure)，不据本地迁移宣称生产迁移。
- 关联：[接口](api.md)、[管理页](admin-ui.md)。

| 表 | 职责 |
|---|---|
| `bgm_track` | 曲目标识/名称、记录版本、独立音频处理状态与启用标记、有序位置、曾公开标记/隐藏时间、音频与封面独立资产/版本、当前尝试/操作与故障类别 |
| `bgm_catalog` | id=1 的目录头、非负版本、默认曲目标识 |
| `bgm_operation` | 操作标识、提交管理员、动作/目标、请求摘要与快照、来源大小/摘要、attempt/owner、状态、绝对期限与结果 |
| `bgm_asset` | 曲目/操作/attempt归属、audio或cover、不可变对象位置/版本、内容摘要/MIME/体积、存储状态、清理状态及到期时间 |
| `bgm_processing_slot` | 全库共享槽位、当前操作/owner/attempt、槽位状态与期限 |

模型集中于 `backend/models/bgm.py` 并注册 `backend/models/__init__.py`。约束包括音频状态集合、enabled只能对应ready、record_version≥1、catalog版本非负、asset kind只能audio/cover；对象key及槽位operation_id唯一。时间按UTC存储，MySQL列保留微秒。

迁移 `alembic/versions/v9h_bgm.py`：revision=`v9h_bgm_001`，父级=`v9g_memory_diagnostic_001`；DDL在迁移内冻结，不动态引用应用模型。只建五张表并种入目录头和一个空闲处理槽，不伪造就绪音乐。降级仅删除这五张表。`create_all_tables` 排除这些受迁移管理表，缺表时要求先迁移，不能借启动绕过 Alembic。

这些表不存用户播放偏好，不绑定H5账号。STEP-003的独立MySQL证据覆盖冻结迁移、多连接、四个独立OS进程单槽位接纳及同id去重；隔离SQLite覆盖业务事务、撤权、旧结果和恢复。这些隔离证据与后续本地业务库部署分开记录，不能扩大为线上迁移或容量验收。

上传接纳后operation状态accepted，PUT取得owner后receiving，媒体阶段processing，最后succeeded/failed。track处理与enabled始终独立；完成上传不改变catalog。终态文件重放仅借用slot的replay/replay_quarantined状态，不改原operation终态/期限。内部owner、快照、摘要、结果与资产位置不直接序列化。

失败资产state=unknown、cleanup_state=pending，仍关联原操作/attempt；没有完成远端读回与当前资格校验时不关联到track正式audio_asset_id。已确认成功的SQL提交遇到响应丢失时保留成功，不回滚或新增对象。STEP-006手动删除与资产补偿复用这些定位。

STEP-004沿用现有五表，无新迁移。catalog单例行锁串行化目录写入；按ID取得曲目行锁后提交完整顺序和唯一默认。轻量目录动作不占用媒体处理槽，不执行外部存储I/O。目录操作state=succeeded、无处理deadline/owner，result保存原提交版本及有序ID的白名单快照；同id重放不重复审计或增加版本。真实MySQL跨engine/不同管理员并发设默认、隐藏和排序验证每轮一提交一版本冲突。

STEP-005无迁移。cover_asset_id零或一，cover_version独立服务端UUID；移除也产生新封面版本。track.attempt/active_operation_id继续只管理音频执行，封面操作用自己的id/owner及接纳时记录版本快照作资格检查，不改音频attempt。封面失败复用操作/资产恢复，因不占track音频active_operation_id，不会把正常音频标为失败。旧图仍以原asset定位归属，retired_at+not_before+cleanup_state承接后续手动清理，当前新图无退役标记。

STEP-006无迁移。delete_track/cleanup_retry操作复用bgm_operation，快照持有本次选中asset_ids、清理mode及期望版本；外部对象原定位始终保留于bgm_asset，不依赖进程内URL。deleting→deleted或delete_failed均为不可发布状态，完整成功清除track当前关联但保留曲目ID、资源及原操作去重墓碑。单对象确认删除后asset.state/cleanup_state=deleted；失败或未知为cleanup_state=failed且保留安全类别。未进入本次有界批次的资源保持原状态，remaining_count非零不能报全完成。

旧图/残留清理排除track当前audio_asset_id及cover_asset_id，遵守not_before；成功/失败不回滚当前图或音频。删曲依据最近隐藏等待期，符合资格后纳入当前、历史及失败残留的全部所属资产，不再单独等待每个旧图的not_before。同一全局slot保护新上传/清理执行；逐对象事实短事务保存。重启恢复失败状态及释放已确认停止的worker，不自动重新删除；所有剩余外部动作必须由管理员手动发起。

STEP-008无表/迁移变更。封面operation.request_snapshot新增服务端派生cover_action（add_cover/replace_cover），不进入客户端请求摘要；用于稳定区分审计动作，既有upload_cover操作及重放协议不变。审计继续写admin_operation_logs，不修改历史日志；版本与逐资产结果只按白名单保存。

2026-10-20本地Docker环境在用户明确授权后执行v9g→v9h；迁移当时五表存在、catalog/slot各一行且媒体记录为空，这是初始快照而非当前空库承诺。后续正式后台已生成实际曲目、操作及资产，版本结项不删除业务记录或将目录重置为空；仅本次获准测试批次隐藏并按最近隐藏时间满24小时后走普通手动精确清理，当前值与其他用户曲目以[结项快照](../../../design/bgm_music/steps-verified.md#bgm-v13-closure)为准。H5前端模块不新增数据库表或服务端用户偏好记录。
