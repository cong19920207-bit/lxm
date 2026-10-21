"""BGM constraints and error categories. Candidate tuning is recorded in STEP §9.5."""
BGM_READ_ROLES = ('super_admin', 'ops_admin', 'observer')
BGM_WRITE_ROLES = ('super_admin', 'ops_admin')

ADMIN_ERR_BGM_NOT_FOUND = 20200
ADMIN_ERR_BGM_INVALID = 20201
ADMIN_ERR_BGM_VERSION_CONFLICT = 20202
ADMIN_ERR_BGM_IDEMPOTENCY_CONFLICT = 20203
ADMIN_ERR_BGM_TOO_LARGE = 20204
ADMIN_ERR_BGM_BUSY = 20205
ADMIN_ERR_BGM_PROCESSING_FAILED = 20206
ADMIN_ERR_BGM_UNAVAILABLE = 20207
ADMIN_ERR_BGM_RESULT_UNKNOWN = 20208

BGM_ERROR_MESSAGES = {
    20200: '音乐或操作记录不存在', 20201: '音乐参数不合法',
    20202: '目录或曲目已更新，请刷新后重新决定', 20203: '操作标识与原提交内容不一致',
    20204: '文件超过允许大小', 20205: '音乐处理忙碌，请稍后重试',
    20206: '音乐处理失败', 20207: '音乐服务暂时不可用', 20208: '操作结果待核对',
}

# Confirmed PRD specifications; tuning must not change these.
AUDIO_SOURCE_MAX_BYTES = 100 * 1024 * 1024
AUDIO_OUTPUT_MAX_BYTES = 4 * 1024 * 1024
AUDIO_MAX_SECONDS = 300
AUDIO_TARGET_BITRATE = 96_000

# Candidate SUG-015, retained as configurable implementation policy, not a PRD threshold.
HIDDEN_DELETE_WAIT_SECONDS = 24 * 60 * 60

# SUG-016/017 implementation policy, verified with the real static-image decoder.
# 200 KiB is a quality optimization target, never a publication rejection limit.
COVER_SOURCE_MAX_BYTES = 5 * 1024 * 1024
COVER_MAX_EDGE = 4096
COVER_OUTPUT_EDGE = 512
