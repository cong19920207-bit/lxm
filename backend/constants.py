# -*- coding: utf-8 -*-
# 统一错误码、业务常量定义

# ============ 通用 ============
SUCCESS = 0
ERR_SYSTEM = 10000  # 系统内部错误

# ============ 认证模块 10001-10099 ============
ERR_PARAM_INVALID = 10001  # 参数校验失败
ERR_USERNAME_FORMAT = 10002  # 用户名格式无效（需6-20位字母数字）
ERR_USERNAME_SENSITIVE = 10003  # 用户名含敏感词
ERR_USERNAME_EXISTS = 10004  # 用户名已存在
ERR_PASSWORD_FORMAT = 10005  # 密码格式无效（需8-20位，含字母和数字）
ERR_PASSWORD_MISMATCH = 10006  # 两次密码不一致
ERR_PASSWORD_SAME_AS_USERNAME = 10007  # 密码不可与用户名相同
ERR_USER_NOT_FOUND = 10008  # 用户不存在
ERR_PASSWORD_WRONG = 10009  # 密码错误
ERR_ACCOUNT_LOCKED = 10010  # 账号被锁定
ERR_ACCOUNT_BANNED = 10011  # 账号被封禁
ERR_TOKEN_INVALID = 10012  # Token无效
ERR_TOKEN_EXPIRED = 10013  # Token已过期

# ============ 认证业务常量 ============
MAX_LOGIN_FAIL_COUNT = 5  # 最大密码错误次数
LOCK_MINUTES = 15  # 锁定时长（分钟）
TOKEN_EXPIRE_DAYS_LONG = 30  # 记住我Token有效期（天）
TOKEN_EXPIRE_DAYS_SHORT = 1  # 普通Token有效期（天，即24小时）

# ============ 用户名敏感词列表 ============
SENSITIVE_WORDS = [
    "admin", "root", "system", "test", "null", "undefined",
    "林小梦", "管理员", "系统", "官方", "客服",
]

# ============ 消息合并（§2.9.1）============
MAX_MESSAGES_COUNT = 5            # messages 最大条数上限
MAX_SINGLE_MESSAGE_LENGTH = 2000  # 合并后单条 content 最大字符数

# ============ 对话模块 10100-10199 ============
ERR_CONTENT_EMPTY = 10100  # 消息内容为空
ERR_CONTENT_UNSAFE = 10101  # 内容安全检测不通过
ERR_LLM_FAILED = 10102  # LLM 调用失败
ERR_CHAT_RATE_LIMIT = 10103  # 对话频率限制
ERR_CHAT_QUEUE_FULL = 10104  # 未处理消息队列已满（无叹号时 ≤5）
ERR_CHAT_RESEND_LIMIT = 10105  # 叹号重发超过 2 次/分钟
ERR_CHAT_IDEMPOTENT_REPLAY = 10106  # 幂等键重复，返回已有结果语义（与实现一致）
ERR_CHAT_NOTHING_TO_RESEND = 10107  # 当前无可重发的失败句（未闭环窗口无叹号）
ERR_CHAT_GENERATION_OBSOLETE = 10108  # generation 已被新 send/resend 作废（Open 同步 JSON）

# ============ 对话 user 行 delivery_status（TD-015，H5 与 Admin 单点枚举）============
# 叹号映射：failed_timeout / failed_error 等可对用户展示重试；pending_llm 为等待中
DELIVERY_STATUS_DELIVERED = "delivered"
DELIVERY_STATUS_PENDING_LLM = "pending_llm"
DELIVERY_STATUS_FAILED_TIMEOUT = "failed_timeout"
DELIVERY_STATUS_FAILED_ERROR = "failed_error"
DELIVERY_STATUS_FAILED_BLOCKED = "failed_blocked"  # 内容安全拦截

# ============ 记忆模块 10200-10299 ============
ERR_MEMORY_NOT_FOUND = 10200  # 记忆不存在
ERR_MEMORY_CONTENT_EMPTY = 10201  # 记忆内容为空
ERR_MEMORY_EXTRACT_FAILED = 10202  # 记忆提取失败

# ============ 日记模块 10300-10399 ============
ERR_DIARY_NOT_FOUND = 10300  # 日记不存在

# ============ 主动消息模块 10400-10499 ============
ERR_AGENT_MSG_NOT_FOUND = 10400  # 主动消息不存在

# ============ 关系等级 ============
RELATION_LEVEL_STRANGER = 0  # 陌生
RELATION_LEVEL_FRIEND = 1  # 朋友（200分）
RELATION_LEVEL_CLOSE = 2  # 亲密（800分）
RELATION_LEVEL_SOULMATE = 3  # 知己（2000分）

# ============ DashVector 向量类型常量（R-L1L3-08 / R-VEC-01）============
MEMORY_TYPE_CHARACTER_GLOBAL = "character_global"       # 角色公开设定
MEMORY_TYPE_CHARACTER_PRIVATE = "character_private"      # 角色私有设定
MEMORY_TYPE_CHARACTER_KNOWLEDGE = "character_knowledge"  # 角色知识技能
MEMORY_TYPE_USER = "user"                                # 用户画像

VALID_MEMORY_TYPES = {
    MEMORY_TYPE_CHARACTER_GLOBAL,
    MEMORY_TYPE_CHARACTER_PRIVATE,
    MEMORY_TYPE_CHARACTER_KNOWLEDGE,
    MEMORY_TYPE_USER,
}

# ============ 错误信息映射 ============
ERROR_MESSAGES = {
    SUCCESS: "success",
    ERR_SYSTEM: "系统内部错误，请稍后重试",
    ERR_PARAM_INVALID: "参数校验失败",
    ERR_USERNAME_FORMAT: "用户名需为6-20位字母或数字",
    ERR_USERNAME_SENSITIVE: "用户名包含敏感词，请更换",
    ERR_USERNAME_EXISTS: "该用户名已被注册",
    ERR_PASSWORD_FORMAT: "密码需为8-20位，且同时包含字母和数字",
    ERR_PASSWORD_MISMATCH: "两次输入的密码不一致",
    ERR_PASSWORD_SAME_AS_USERNAME: "密码不可与用户名相同",
    ERR_USER_NOT_FOUND: "用户不存在",
    ERR_PASSWORD_WRONG: "密码错误",
    ERR_ACCOUNT_LOCKED: "账号已被锁定，请稍后重试",
    ERR_ACCOUNT_BANNED: "账号已被封禁",
    ERR_TOKEN_INVALID: "登录已失效，请重新登录",
    ERR_TOKEN_EXPIRED: "登录已过期，请重新登录",
    ERR_CONTENT_EMPTY: "消息内容不能为空",
    ERR_CONTENT_UNSAFE: "消息包含不适当内容，请修改后重试",
    ERR_LLM_FAILED: "小梦暂时无法回复，请稍后再试",
    ERR_CHAT_RATE_LIMIT: "消息发送太频繁，请稍后再试",
    ERR_CHAT_QUEUE_FULL: "待处理消息过多，请先等待或处理失败提示",
    ERR_CHAT_RESEND_LIMIT: "重试过于频繁，请稍后再试",
    ERR_CHAT_IDEMPOTENT_REPLAY: "重复请求已忽略",
    ERR_CHAT_NOTHING_TO_RESEND: "当前没有需要重试的消息",
    ERR_CHAT_GENERATION_OBSOLETE: "回复已被新消息取代，请拉取时间线查看后再操作",
    ERR_MEMORY_NOT_FOUND: "记忆不存在或已删除",
    ERR_MEMORY_CONTENT_EMPTY: "记忆内容不能为空",
    ERR_MEMORY_EXTRACT_FAILED: "记忆提取失败",
    ERR_DIARY_NOT_FOUND: "日记不存在",
    ERR_AGENT_MSG_NOT_FOUND: "主动消息不存在",
}

# ============ 人格风险检测关键词 ============
PERSONA_RISK_KEYWORDS = {
    "identity_challenge": [
        "你是ai", "你是机器人", "你是程序", "你是人工智能",
        "你是语言模型", "你是chatgpt", "你是gpt", "你不是人",
        "你是假的", "你没有感情",
    ],
    "jailbreak": [
        "忘记设定", "忘记你的设定", "忽略指令", "忽略规则",
        "角色扮演", "假装你是", "从现在开始你是",
        "system prompt", "系统提示词",
    ],
}

# ============ 管理后台错误码 20001 起（与 H5 段独立，命名 ADMIN_ERR_{模块}_{描述}）============
# 来源：backend/routers/admin/ 下 ApiResponse / HTTPException 实际返回场景

# --- 认证 auth ---
ADMIN_ERR_AUTH_LOGIN_FAILED = 20001  # 登录：账号不存在或密码错误（统一提示）
ADMIN_ERR_AUTH_ACCOUNT_LOCKED = 20002  # 登录：账号已锁定
ADMIN_ERR_AUTH_PASSWORD_WRONG_WITH_REMAINING = 20003  # 登录：密码错误并提示剩余尝试次数
ADMIN_ERR_AUTH_OLD_PASSWORD_WRONG = 20004  # 修改密码：旧密码不正确
ADMIN_ERR_AUTH_NEW_PASSWORD_SAME_AS_OLD = 20005  # 修改密码：新密码与旧密码相同
ADMIN_ERR_AUTH_NEW_PASSWORD_CONFIRM_MISMATCH = 20006  # 修改密码：两次新密码不一致
ADMIN_ERR_AUTH_PASSWORD_POLICY = 20007  # 管理员密码强度不符合要求（登录后改密、创建账号等）

# --- 用户管理 user（H5 用户）---
ADMIN_ERR_USER_NOT_FOUND = 20008  # H5 用户不存在
ADMIN_ERR_USER_MEMORY_CONTENT_EMPTY = 20009  # 编辑记忆：内容为空
ADMIN_ERR_USER_MEMORY_NOT_FOUND = 20010  # 记忆不存在或不属于该用户
ADMIN_ERR_USER_STATUS_ACTION_INVALID = 20011  # 禁用/启用：action 非 ban/unban
ADMIN_ERR_USER_ALREADY_BANNED = 20012  # 禁用：用户已处于禁用状态
ADMIN_ERR_USER_NOT_BANNED = 20013  # 启用：用户未被禁用

# --- 管理员账号 account ---
ADMIN_ERR_ACCOUNT_USERNAME_EXISTS = 20014  # 创建账号：用户名已存在
ADMIN_ERR_ACCOUNT_NOT_FOUND = 20015  # 管理员账号不存在
ADMIN_ERR_ACCOUNT_CANNOT_CHANGE_OWN_ROLE = 20016  # 不可修改自己的角色
ADMIN_ERR_ACCOUNT_CANNOT_DELETE_SELF = 20017  # 不可删除自己的账号
ADMIN_ERR_ACCOUNT_CANNOT_DELETE_SUPER = 20018  # 超级管理员账号不可删除

# --- 人格 / 配置发布流程 persona & 通用配置 ---
ADMIN_ERR_PERSONA_FIELD_EMPTY = 20019  # 人格五段字段存在空值
ADMIN_ERR_CONFIG_NO_DRAFT_DISCARD = 20020  # 丢弃草稿：当前无草稿
ADMIN_ERR_CONFIG_CONFIRM_TEXT_INVALID = 20021  # 发布/回滚：未按要求输入 CONFIRM
ADMIN_ERR_CONFIG_PUBLISH_TEST_NOT_PASSED = 20022  # 发布：测试未通过
ADMIN_ERR_CONFIG_ROLLBACK_VERSION_NOT_FOUND = 20023  # 回滚：目标版本不存在

# --- Prompt ---
ADMIN_ERR_PROMPT_MODULE_NOT_EDITABLE = 20024  # 保存草稿：模块不可编辑
ADMIN_ERR_PROMPT_PLACEHOLDER_MISSING = 20025  # 保存草稿：缺少必填占位符
ADMIN_ERR_PROMPT_NO_DRAFT_TO_PUBLISH = 20026  # 发布：无待发布草稿

# --- 记忆规则与向量 memory_mgmt ---
ADMIN_ERR_MEMORY_RULE_THRESHOLD_INVALID = 20027  # 记忆规则：检索/合并/存储阈值或区间不合法
ADMIN_ERR_VECTOR_DB_CONNECTION_FAILED = 20028  # 向量库：保存配置前连接测试失败
ADMIN_ERR_QUERY_DATE_FORMAT_INVALID = 20029  # 查询参数日期格式非法（须 YYYY-MM-DD）

# --- Agent ---
ADMIN_ERR_AGENT_RULE_PARAM_INVALID = 20030  # Agent 规则：P2/决策引擎等数值参数越界
ADMIN_ERR_AGENT_TRIGGER_TYPE_INVALID = 20031  # trigger_type 非 P0–P4
ADMIN_ERR_AGENT_MESSAGE_RULE_INVALID = 20032  # 主动消息模板：examples 数量或 max_length 非法

# --- 关系与日记 relationship_mgmt ---
ADMIN_ERR_RELATIONSHIP_RULE_INVALID = 20033  # 关系规则：等级数量、threshold 或 growth_rules 非法
ADMIN_ERR_DIARY_RULE_PARAM_INVALID = 20034  # 日记规则：max_length 或 generation_hour 等非法

# --- 情绪 emotion_config ---
ADMIN_ERR_EMOTION_CONFIG_INVALID = 20035  # 情绪名称、status_texts 条数或单条长度非法

# --- 内容安全 safety_rules ---
ADMIN_ERR_SAFETY_EXCEL_FILE_INVALID = 20036  # 违禁词导入：文件类型、解析失败或无可导入词
ADMIN_ERR_SYSTEM_OPENPYXL_MISSING = 20037  # 服务器缺少 openpyxl，无法解析 Excel

# --- 第三方与系统监控 system_monitor ---
ADMIN_ERR_THIRD_PARTY_SERVICE_NAME_INVALID = 20038  # 第三方服务名非法
ADMIN_ERR_THIRD_PARTY_REQUEST_BODY_EMPTY = 20039  # 更新第三方配置：请求体为空
ADMIN_ERR_THIRD_PARTY_CONNECTION_TEST_FAILED = 20040  # 第三方配置保存前连接测试失败
ADMIN_ERR_SYSTEM_LOG_QUERY_INVALID = 20041  # 系统日志查询/导出：类型、级别或日期范围非法

# --- 数据统计 stats ---
ADMIN_ERR_STATS_QUERY_INVALID = 20042  # 统计：metric/days/report_type 或时间范围非法

# --- 测试用例 test_cases ---
ADMIN_ERR_TEST_CASE_MIN_RETAIN = 20043  # 删除用例：将低于最少保留条数
ADMIN_ERR_TEST_CASE_NOT_FOUND = 20044  # 指定测试用例 ID 不存在

# --- 操作日志 operation_logs ---
ADMIN_ERR_OPERATION_LOG_NOT_FOUND = 20045  # 操作日志记录不存在

# --- 向量召回与 Prompt Token 热配置（STEP-025）---
ADMIN_ERR_VECTOR_TOKEN_CONFIG_INVALID = 20046  # PATCH 体为空、合并后越界或类型不合法

# --- 角色知识库 character_knowledge（STEP-027 / R-L1L3-20）---
ADMIN_ERR_CHARACTER_KNOWLEDGE_PARAM_INVALID = 20047  # type/key/value 不合法
ADMIN_ERR_CHARACTER_KNOWLEDGE_KEY_TOO_LONG = 20048  # key 超 20 汉字
ADMIN_ERR_CHARACTER_KNOWLEDGE_VALUE_TOO_LONG = 20049  # value 超 100 汉字
ADMIN_ERR_CHARACTER_KNOWLEDGE_DUPLICATE_KEY = 20050  # 同 type+key 已存在
ADMIN_ERR_CHARACTER_KNOWLEDGE_NOT_FOUND = 20051  # doc_id 不存在
ADMIN_ERR_CHARACTER_KNOWLEDGE_VECTOR_WRITE_FAILED = 20052  # Embedding 或 DashVector 失败

# ============ 管理后台错误信息映射（供路由与前端统一展示）============
ADMIN_ERROR_MESSAGES = {
    ADMIN_ERR_AUTH_LOGIN_FAILED: "账号或密码错误",
    ADMIN_ERR_AUTH_ACCOUNT_LOCKED: "账号已锁定，请联系超级管理员解锁",
    ADMIN_ERR_AUTH_PASSWORD_WRONG_WITH_REMAINING: "账号或密码错误，还可尝试{remaining}次",
    ADMIN_ERR_AUTH_OLD_PASSWORD_WRONG: "旧密码不正确",
    ADMIN_ERR_AUTH_NEW_PASSWORD_SAME_AS_OLD: "新密码不能与旧密码相同",
    ADMIN_ERR_AUTH_NEW_PASSWORD_CONFIRM_MISMATCH: "两次输入的新密码不一致",
    ADMIN_ERR_AUTH_PASSWORD_POLICY: "密码不符合强度要求（至少12位，含大小写字母、数字与特殊字符）",
    ADMIN_ERR_USER_NOT_FOUND: "用户不存在",
    ADMIN_ERR_USER_MEMORY_CONTENT_EMPTY: "记忆内容不能为空",
    ADMIN_ERR_USER_MEMORY_NOT_FOUND: "记忆不存在",
    ADMIN_ERR_USER_STATUS_ACTION_INVALID: "action 必须为 ban 或 unban",
    ADMIN_ERR_USER_ALREADY_BANNED: "用户已处于禁用状态",
    ADMIN_ERR_USER_NOT_BANNED: "用户未被禁用",
    ADMIN_ERR_ACCOUNT_USERNAME_EXISTS: "用户名已存在",
    ADMIN_ERR_ACCOUNT_NOT_FOUND: "账号不存在",
    ADMIN_ERR_ACCOUNT_CANNOT_CHANGE_OWN_ROLE: "不可修改自己的角色",
    ADMIN_ERR_ACCOUNT_CANNOT_DELETE_SELF: "不可删除自己的账号",
    ADMIN_ERR_ACCOUNT_CANNOT_DELETE_SUPER: "超级管理员账号不可删除",
    ADMIN_ERR_PERSONA_FIELD_EMPTY: "人格配置存在空字段",
    ADMIN_ERR_CONFIG_NO_DRAFT_DISCARD: "无草稿可丢弃",
    ADMIN_ERR_CONFIG_CONFIRM_TEXT_INVALID: "请输入 CONFIRM 以确认操作",
    ADMIN_ERR_CONFIG_PUBLISH_TEST_NOT_PASSED: "请先通过测试再发布",
    ADMIN_ERR_CONFIG_ROLLBACK_VERSION_NOT_FOUND: "回滚目标版本不存在",
    ADMIN_ERR_PROMPT_MODULE_NOT_EDITABLE: "该 Prompt 模块不可编辑",
    ADMIN_ERR_PROMPT_PLACEHOLDER_MISSING: "Prompt 内容缺少必填占位符",
    ADMIN_ERR_PROMPT_NO_DRAFT_TO_PUBLISH: "无待发布的草稿，请先保存草稿",
    ADMIN_ERR_MEMORY_RULE_THRESHOLD_INVALID: "记忆规则阈值或区间不合法",
    ADMIN_ERR_VECTOR_DB_CONNECTION_FAILED: "向量库连接测试失败",
    ADMIN_ERR_QUERY_DATE_FORMAT_INVALID: "日期格式错误，应为 YYYY-MM-DD",
    ADMIN_ERR_AGENT_RULE_PARAM_INVALID: "Agent 规则参数超出允许范围",
    ADMIN_ERR_AGENT_TRIGGER_TYPE_INVALID: "trigger_type 无效",
    ADMIN_ERR_AGENT_MESSAGE_RULE_INVALID: "主动消息模板规则参数不合法",
    ADMIN_ERR_RELATIONSHIP_RULE_INVALID: "关系等级规则不合法",
    ADMIN_ERR_DIARY_RULE_PARAM_INVALID: "日记生成规则参数不合法",
    ADMIN_ERR_EMOTION_CONFIG_INVALID: "情绪配置不合法",
    ADMIN_ERR_SAFETY_EXCEL_FILE_INVALID: "Excel 文件不合法或无可导入关键词",
    ADMIN_ERR_SYSTEM_OPENPYXL_MISSING: "服务器缺少 openpyxl 依赖，无法解析 Excel",
    ADMIN_ERR_THIRD_PARTY_SERVICE_NAME_INVALID: "第三方服务名无效",
    ADMIN_ERR_THIRD_PARTY_REQUEST_BODY_EMPTY: "请求体不能为空",
    ADMIN_ERR_THIRD_PARTY_CONNECTION_TEST_FAILED: "连接测试失败，配置未保存",
    ADMIN_ERR_SYSTEM_LOG_QUERY_INVALID: "系统日志查询条件不合法",
    ADMIN_ERR_STATS_QUERY_INVALID: "统计数据查询条件不合法",
    ADMIN_ERR_TEST_CASE_MIN_RETAIN: "至少需要保留规定条数的测试用例",
    ADMIN_ERR_TEST_CASE_NOT_FOUND: "未找到指定测试用例",
    ADMIN_ERR_OPERATION_LOG_NOT_FOUND: "日志记录不存在",
    ADMIN_ERR_VECTOR_TOKEN_CONFIG_INVALID: "配置参数不合法或请求体未包含任何待更新字段",
    ADMIN_ERR_CHARACTER_KNOWLEDGE_PARAM_INVALID: "参数不合法",
    ADMIN_ERR_CHARACTER_KNOWLEDGE_KEY_TOO_LONG: "key 汉字不能超过 20 个",
    ADMIN_ERR_CHARACTER_KNOWLEDGE_VALUE_TOO_LONG: "value 汉字不能超过 100 个",
    ADMIN_ERR_CHARACTER_KNOWLEDGE_DUPLICATE_KEY: "该类型下 key 已存在",
    ADMIN_ERR_CHARACTER_KNOWLEDGE_NOT_FOUND: "条目不存在",
    ADMIN_ERR_CHARACTER_KNOWLEDGE_VECTOR_WRITE_FAILED: "向量写入失败，请稍后重试",
}
