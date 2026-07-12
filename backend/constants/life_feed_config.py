# -*- coding: utf-8 -*-
# 生活流全局配置项常量（STEP-003）
#
# 约定：
#   1. 所有 config_key 均为 snake_case + 生活流前缀（feed_* / lxm_* / like_aware_* /
#      read_aware_* / emotion_* / venue_* / category_* 等），与 IM 主链命名空间独立。
#   2. 全部延迟/时长类配置**单位统一为「秒」**（避免 min/max 单位混淆）。
#      —— 关系档延迟窗口来源 PRD 6.3 / 7.3，已由「分钟/小时」换算为秒。
#   3. 本文件为生活流关系档映射（RELATIONSHIP_STAGE_MAP）的**唯一来源**，
#      STEP-018/019/020/021 必须复用，禁止在 service 层重造。
#   4. 默认值仅作为「种子脚本」写入 admin_config 的初始值与运行时兜底 default，
#      实际生效值以 admin_config 当前生效版本为准（后台可改）。

from typing import Any

# ============ 关系档映射（生活流唯一来源，PRD 6.3 四档命名沿用 IM）============
# level（relationship.level：0/1/2/3）→ 生活流关系档字符串
RELATIONSHIP_STAGE_MAP: dict[int, str] = {
    0: "stranger",
    1: "friend",
    2: "intimate",
    3: "soulmate",
}

# 关系档字符串 → 中文（供日志/后台展示）
RELATIONSHIP_STAGE_ZH: dict[str, str] = {
    "stranger": "陌生",
    "friend": "朋友",
    "intimate": "亲密",
    "soulmate": "知己",
}

# 有序档位（供遍历种子/校验）
RELATIONSHIP_STAGES: tuple[str, ...] = ("stranger", "friend", "intimate", "soulmate")


def level_to_stage(level: int) -> str:
    """关系等级 → 生活流关系档字符串；越界回落到最近合法档（<0→stranger，>3→soulmate）。"""
    if level in RELATIONSHIP_STAGE_MAP:
        return RELATIONSHIP_STAGE_MAP[level]
    if level < 0:
        return "stranger"
    return "soulmate"


# ============ 全局人设扩展 / 词汇表（PRD 0.2 / 0.3 / 0.4）============
CONFIG_CATEGORIES_VOCAB = "categories_vocab"
CONFIG_EMOTION_VOCAB = "emotion_vocab"
CONFIG_LXM_LIKES = "lxm_likes"
CONFIG_LXM_DISLIKES = "lxm_dislikes"
CONFIG_LXM_WRITING_STYLE = "lxm_writing_style"
CONFIG_LXM_CONTENT_LIMITS = "lxm_content_limits"

# 人物图生图（P-12）人物描述 / 通用负向词（文档未给默认，提供可后台调初始值）
CONFIG_LXM_IMG1_CHARACTER_DESC = "lxm_img1_character_desc"
CONFIG_LXM_IMG1_NEGATIVE_BASE = "lxm_img1_negative_base"

# 主场城市 / 文本相似度阈值
CONFIG_HOME_CITY = "home_city"
CONFIG_FEED_TEXT_SIMILARITY_THRESHOLD = "feed_text_similarity_threshold"

# ============ 互动特殊档参数（PRD 9.5 / 9.6）============
CONFIG_LIKE_AWARE_SPECIAL_WINDOW_HOURS = "like_aware_special_window_hours"
CONFIG_LIKE_AWARE_SPECIAL_MAX_COUNT = "like_aware_special_max_count"
CONFIG_LIKE_AWARE_SPECIAL_DELAY_SEC = "like_aware_special_delay_sec"
CONFIG_READ_AWARE_SPECIAL_WINDOW_HOURS = "read_aware_special_window_hours"
CONFIG_READ_AWARE_SPECIAL_MAX_COUNT = "read_aware_special_max_count"
CONFIG_READ_AWARE_SPECIAL_DELAY_SEC = "read_aware_special_delay_sec"
CONFIG_READ_SUPPRESS_AFTER_LIKE_IM_HOURS = "read_suppress_after_like_im_hours"
# 已读感知用户级冷却：按入队 created_at 滚动窗口内最多 1 条 READ_AWARE
CONFIG_READ_AWARE_USER_COOLDOWN_HOURS = "read_aware_user_cooldown_hours"

# ============ 发布频率 / 图片分布（PRD 4.2.1 / 4.4.1 / 4.4.2）============
CONFIG_FEED_DAILY_POST_COUNT_2_WEIGHT = "feed_daily_post_count_2_weight"
CONFIG_FEED_DAILY_POST_COUNT_3_WEIGHT = "feed_daily_post_count_3_weight"

# 自动发布总开关 —— PRD 10.3（STEP-013 读取 / STEP-014 管理）
CONFIG_FEED_AUTO_PUBLISH_ENABLED = "feed_auto_publish_enabled"

# 话题标签数量概率分布 —— PRD 4.3.4（0/1/2/3 个：50/30/10/10）
CONFIG_FEED_HASHTAG_COUNT_0_WEIGHT = "feed_hashtag_count_0_weight"
CONFIG_FEED_HASHTAG_COUNT_1_WEIGHT = "feed_hashtag_count_1_weight"
CONFIG_FEED_HASHTAG_COUNT_2_WEIGHT = "feed_hashtag_count_2_weight"
CONFIG_FEED_HASHTAG_COUNT_3_WEIGHT = "feed_hashtag_count_3_weight"

CONFIG_FEED_IMAGE_COUNT_0_WEIGHT = "feed_image_count_0_weight"
CONFIG_FEED_IMAGE_COUNT_1_WEIGHT = "feed_image_count_1_weight"
CONFIG_FEED_IMAGE_COUNT_2_3_WEIGHT = "feed_image_count_2_3_weight"
CONFIG_FEED_IMAGE_COUNT_4_WEIGHT = "feed_image_count_4_weight"

CONFIG_FEED_IMAGE_TYPE_SELFIE_WEIGHT = "feed_image_type_selfie_weight"
CONFIG_FEED_IMAGE_TYPE_DAILY_WEIGHT = "feed_image_type_daily_weight"
CONFIG_FEED_IMAGE_TYPE_SCENERY_WEIGHT = "feed_image_type_scenery_weight"
CONFIG_FEED_IMAGE_TYPE_EMOTION_WEIGHT = "feed_image_type_emotion_weight"

# ============ LiblibAI 生图参数（TB-LF-001）============
CONFIG_LIBLIB_TEXT2IMG_TEMPLATE_UUID = "liblib_text2img_template_uuid"
CONFIG_LIBLIB_IMG2IMG_TEMPLATE_UUID = "liblib_img2img_template_uuid"
CONFIG_LIBLIB_GEN_STEPS = "liblib_gen_steps"
CONFIG_LIBLIB_GEN_WIDTH = "liblib_gen_width"
CONFIG_LIBLIB_GEN_HEIGHT = "liblib_gen_height"
CONFIG_LIBLIB_IMG2IMG_STRENGTH = "liblib_img2img_strength"
# 图生图专用：参考图缩放目标尺寸（与出图 width/height 语义不同）
CONFIG_LIBLIB_IMG2IMG_RESIZED_WIDTH = "liblib_img2img_resized_width"
CONFIG_LIBLIB_IMG2IMG_RESIZED_HEIGHT = "liblib_img2img_resized_height"

# ============ 朋友圈页 Header 展示（自定义）============
CONFIG_FEED_PAGE_HEADER_BG_URL = "feed_page_header_bg_url"
CONFIG_FEED_PAGE_HEADER_AVATAR_URL = "feed_page_header_avatar_url"
CONFIG_FEED_PAGE_SIGNATURE = "feed_page_signature"
CONFIG_FEED_PAGE_DISPLAY_NICKNAME = "feed_page_display_nickname"

# ============ 发布窗口 / 历史可见范围（PRD 10.5 / 10.6）============
CONFIG_FEED_PUBLISH_WINDOW_1 = "feed_publish_window_1"
CONFIG_FEED_PUBLISH_WINDOW_2 = "feed_publish_window_2"
CONFIG_FEED_PUBLISH_WINDOW_3 = "feed_publish_window_3"
CONFIG_FEED_HISTORY_VISIBLE_RANGE = "feed_history_visible_range"

# ============ 南半球城市白名单（PRD 10.7#4）============
CONFIG_SOUTHERN_HEMISPHERE_CITIES = "southern_hemisphere_cities"

# ============ 点赞倍率范围（PRD 10.7#2）============
CONFIG_FEED_BASE_LIKES_MIN = "feed_base_likes_min"
CONFIG_FEED_BASE_LIKES_MAX = "feed_base_likes_max"
CONFIG_FEED_LIKE_MULTIPLIER_MIN = "feed_like_multiplier_min"
CONFIG_FEED_LIKE_MULTIPLIER_MAX = "feed_like_multiplier_max"


def comment_reply_delay_key(stage: str, bound: str) -> str:
    """评论回复延迟 config_key，bound ∈ {'min','max'}。"""
    return f"comment_reply_delay_{stage}_{bound}"


def like_regular_delay_key(stage: str, bound: str) -> str:
    """点赞常规档延迟 config_key。"""
    return f"like_regular_delay_{stage}_{bound}"


def read_regular_delay_key(stage: str, bound: str) -> str:
    """已读常规档延迟 config_key。"""
    return f"read_regular_delay_{stage}_{bound}"


# ============ 默认值（种子脚本写入 + 运行时兜底）============
# 词汇表 —— PRD 0.3（10 项）/ 0.4（14 核心词）
DEFAULT_CATEGORIES_VOCAB = [
    "工作", "学习", "旅游", "购物逛街", "探店美食",
    "户外散步", "休闲在家", "看展文化", "运动健身", "社交",
]
DEFAULT_EMOTION_VOCAB = [
    "慵懒", "雀跃", "低落", "平静", "焦虑", "满足", "怀念",
    "烦躁", "期待", "感慨", "孤独", "无聊", "迷茫", "释然",
]

# 人设扩展 —— PRD 0.2
DEFAULT_LXM_LIKES = (
    "咖啡馆（偏安静偏角落的）、沿河或街边散步、逛市集和菜市场、"
    "看展览（当代艺术/摄影/设计均可）、独自发呆、旧书店、在家窝着不动"
)
DEFAULT_LXM_DISLIKES = (
    "人多嘈杂的热门景区、排队等候的网红打卡点、被催促或按计划行事、"
    "强制性社交聚会、过度正能量内容、精心摆拍的“精致生活”人设感"
)
DEFAULT_LXM_WRITING_STYLE = (
    "口语化句子可不完整；用“……”表停顿，emoji克制（0-2个）；"
    "偶尔有不影响理解的小错别字；情绪真实可以有小抱怨/无聊/发呆感；"
    "不写排比句和总结式升华；段落短（1-2段，不超过3段）；不在朋友圈提及具体用户"
)
DEFAULT_LXM_CONTENT_LIMITS = (
    "不出现：工作收入/接单价格/商业合作细节、家庭矛盾或家人具体信息、"
    "健康状况细节（轻描淡写的日常小事除外）、对真实品牌/商家的具体评价、"
    "直接点名批评某人的内容"
)

DEFAULT_HOME_CITY = "杭州"
DEFAULT_FEED_TEXT_SIMILARITY_THRESHOLD = 0.75

# 人物图生图 P-12（偏插画氛围试验；底模仍为写实 UUID 时效果有限）
DEFAULT_LXM_IMG1_CHARACTER_DESC = (
    "a young anime-style asian woman in her early twenties, "
    "long dark hair with soft purple highlights, large expressive eyes, "
    "gentle pensive face, simple dark turtleneck and jacket, delicate earring, "
    "2d illustration character design"
)
DEFAULT_LXM_IMG1_NEGATIVE_BASE = (
    "deformed, distorted, disfigured, bad anatomy, extra limbs, "
    "extra fingers, mutated hands, low quality, blurry face, "
    "photorealistic skin pores, real photo, 3d render, multiple people"
)

# LiblibAI WebUI 参数模板（text2img 默认值经冒烟验证；img2img 需后台人工填入）
DEFAULT_LIBLIB_TEXT2IMG_TEMPLATE_UUID = "6f7c4652458d4802969f8d089cf5b91f"
DEFAULT_LIBLIB_IMG2IMG_TEMPLATE_UUID = ""
DEFAULT_LIBLIB_GEN_STEPS = 20
DEFAULT_LIBLIB_GEN_WIDTH = 768
DEFAULT_LIBLIB_GEN_HEIGHT = 1024
DEFAULT_LIBLIB_IMG2IMG_STRENGTH = 0.6
DEFAULT_LIBLIB_IMG2IMG_RESIZED_WIDTH = 768
DEFAULT_LIBLIB_IMG2IMG_RESIZED_HEIGHT = 1024

# 互动特殊档 —— PRD 9.5 / 9.6
DEFAULT_LIKE_AWARE_SPECIAL_WINDOW_HOURS = 48
DEFAULT_LIKE_AWARE_SPECIAL_MAX_COUNT = 1
DEFAULT_LIKE_AWARE_SPECIAL_DELAY_SEC = 30
DEFAULT_READ_AWARE_SPECIAL_WINDOW_HOURS = 48
DEFAULT_READ_AWARE_SPECIAL_MAX_COUNT = 1
DEFAULT_READ_AWARE_SPECIAL_DELAY_SEC = 60
DEFAULT_READ_SUPPRESS_AFTER_LIKE_IM_HOURS = 6
DEFAULT_READ_AWARE_USER_COOLDOWN_HOURS = 6

# 自动发布开关 —— 默认开启
DEFAULT_FEED_AUTO_PUBLISH_ENABLED = True

# 发布频率 —— PRD 4.2.1（2 条 / 3 条各 50%）
DEFAULT_FEED_DAILY_POST_COUNT_2_WEIGHT = 50
DEFAULT_FEED_DAILY_POST_COUNT_3_WEIGHT = 50

# 话题标签数量概率 —— PRD 4.3.4（0/1/2/3 个：50/30/10/10）
DEFAULT_FEED_HASHTAG_COUNT_0_WEIGHT = 50
DEFAULT_FEED_HASHTAG_COUNT_1_WEIGHT = 30
DEFAULT_FEED_HASHTAG_COUNT_2_WEIGHT = 10
DEFAULT_FEED_HASHTAG_COUNT_3_WEIGHT = 10

# 图片张数分布 —— PRD 4.4.1
DEFAULT_FEED_IMAGE_COUNT_0_WEIGHT = 30
DEFAULT_FEED_IMAGE_COUNT_1_WEIGHT = 35
DEFAULT_FEED_IMAGE_COUNT_2_3_WEIGHT = 25
DEFAULT_FEED_IMAGE_COUNT_4_WEIGHT = 10

# 图片类型权重 —— PRD 4.4.2
DEFAULT_FEED_IMAGE_TYPE_SELFIE_WEIGHT = 40
DEFAULT_FEED_IMAGE_TYPE_DAILY_WEIGHT = 30
DEFAULT_FEED_IMAGE_TYPE_SCENERY_WEIGHT = 20
DEFAULT_FEED_IMAGE_TYPE_EMOTION_WEIGHT = 10

# 朋友圈页 Header —— 自定义（PRD 无原文默认，回落链见 STEP-022/030）
DEFAULT_FEED_PAGE_HEADER_BG_URL = "/static/images/feed/bg_default.jpg"
DEFAULT_FEED_PAGE_HEADER_AVATAR_URL = "/static/images/avatar/character-ref/base.png"
DEFAULT_FEED_PAGE_SIGNATURE = "今天也要好好生活呀~"
DEFAULT_FEED_PAGE_DISPLAY_NICKNAME = "林小梦"

# 发布窗口 —— PRD 10.5
DEFAULT_FEED_PUBLISH_WINDOW_1 = "10:00-12:00"
DEFAULT_FEED_PUBLISH_WINDOW_2 = "15:00-20:00"
DEFAULT_FEED_PUBLISH_WINDOW_3 = "20:00-23:00"

# 历史可见范围 —— PRD 10.6（枚举 7d|30d|180d|all）
DEFAULT_FEED_HISTORY_VISIBLE_RANGE = "all"

# 南半球城市白名单 —— PRD 10.7#4
DEFAULT_SOUTHERN_HEMISPHERE_CITIES = [
    "悉尼", "墨尔本", "布里斯班", "珀斯",
    "奥克兰", "惠灵顿", "开普敦", "布宜诺斯艾利斯", "圣地亚哥",
]

# 点赞倍率范围 —— PRD 10.7#2
DEFAULT_FEED_BASE_LIKES_MIN = 1
DEFAULT_FEED_BASE_LIKES_MAX = 8
DEFAULT_FEED_LIKE_MULTIPLIER_MIN = 1
DEFAULT_FEED_LIKE_MULTIPLIER_MAX = 3

# 关系档延迟窗口默认值（单位：秒）
# 评论回复（LLM-05）—— PRD 6.3
DEFAULT_COMMENT_REPLY_DELAY_SEC = {
    "stranger": (300, 600),    # 5–10 分钟
    "friend": (300, 600),      # 5–10 分钟
    "intimate": (60, 180),     # 1–3 分钟
    "soulmate": (30, 60),      # 30 秒–1 分钟
}
# 点赞 IM 常规档（LLM-06）—— PRD 6.3
DEFAULT_LIKE_REGULAR_DELAY_SEC = {
    "stranger": (3600, 7200),  # 1–2 小时
    "friend": (3600, 7200),    # 1–2 小时
    "intimate": (1200, 2400),  # 20–40 分钟
    "soulmate": (600, 1200),   # 10–20 分钟
}
# 已读常规档（LLM-07）—— PRD 7.3（30 分钟–2 小时，各阶段可配，默认统一区间）
DEFAULT_READ_REGULAR_DELAY_SEC = {
    "stranger": (1800, 7200),
    "friend": (1800, 7200),
    "intimate": (1800, 7200),
    "soulmate": (1800, 7200),
}


def build_seed_config_items() -> list[dict[str, Any]]:
    """
    汇总全部生活流 admin_config 种子项（幂等种子脚本使用）。

    返回：[{"config_key": str, "config_value": Any}, ...]
    config_value 为原始 Python 对象；脚本写库时统一 json.dumps（含标量）。
    """
    items: list[dict[str, Any]] = [
        {"config_key": CONFIG_CATEGORIES_VOCAB, "config_value": DEFAULT_CATEGORIES_VOCAB},
        {"config_key": CONFIG_EMOTION_VOCAB, "config_value": DEFAULT_EMOTION_VOCAB},
        {"config_key": CONFIG_LXM_LIKES, "config_value": DEFAULT_LXM_LIKES},
        {"config_key": CONFIG_LXM_DISLIKES, "config_value": DEFAULT_LXM_DISLIKES},
        {"config_key": CONFIG_LXM_WRITING_STYLE, "config_value": DEFAULT_LXM_WRITING_STYLE},
        {"config_key": CONFIG_LXM_CONTENT_LIMITS, "config_value": DEFAULT_LXM_CONTENT_LIMITS},
        {"config_key": CONFIG_LXM_IMG1_CHARACTER_DESC,
         "config_value": DEFAULT_LXM_IMG1_CHARACTER_DESC},
        {"config_key": CONFIG_LXM_IMG1_NEGATIVE_BASE,
         "config_value": DEFAULT_LXM_IMG1_NEGATIVE_BASE},
        {"config_key": CONFIG_HOME_CITY, "config_value": DEFAULT_HOME_CITY},
        {"config_key": CONFIG_FEED_TEXT_SIMILARITY_THRESHOLD,
         "config_value": DEFAULT_FEED_TEXT_SIMILARITY_THRESHOLD},
        # 互动特殊档
        {"config_key": CONFIG_LIKE_AWARE_SPECIAL_WINDOW_HOURS,
         "config_value": DEFAULT_LIKE_AWARE_SPECIAL_WINDOW_HOURS},
        {"config_key": CONFIG_LIKE_AWARE_SPECIAL_MAX_COUNT,
         "config_value": DEFAULT_LIKE_AWARE_SPECIAL_MAX_COUNT},
        {"config_key": CONFIG_LIKE_AWARE_SPECIAL_DELAY_SEC,
         "config_value": DEFAULT_LIKE_AWARE_SPECIAL_DELAY_SEC},
        {"config_key": CONFIG_READ_AWARE_SPECIAL_WINDOW_HOURS,
         "config_value": DEFAULT_READ_AWARE_SPECIAL_WINDOW_HOURS},
        {"config_key": CONFIG_READ_AWARE_SPECIAL_MAX_COUNT,
         "config_value": DEFAULT_READ_AWARE_SPECIAL_MAX_COUNT},
        {"config_key": CONFIG_READ_AWARE_SPECIAL_DELAY_SEC,
         "config_value": DEFAULT_READ_AWARE_SPECIAL_DELAY_SEC},
        {"config_key": CONFIG_READ_SUPPRESS_AFTER_LIKE_IM_HOURS,
         "config_value": DEFAULT_READ_SUPPRESS_AFTER_LIKE_IM_HOURS},
        {"config_key": CONFIG_READ_AWARE_USER_COOLDOWN_HOURS,
         "config_value": DEFAULT_READ_AWARE_USER_COOLDOWN_HOURS},
        # 自动发布开关
        {"config_key": CONFIG_FEED_AUTO_PUBLISH_ENABLED,
         "config_value": DEFAULT_FEED_AUTO_PUBLISH_ENABLED},
        # 发布频率
        {"config_key": CONFIG_FEED_DAILY_POST_COUNT_2_WEIGHT,
         "config_value": DEFAULT_FEED_DAILY_POST_COUNT_2_WEIGHT},
        {"config_key": CONFIG_FEED_DAILY_POST_COUNT_3_WEIGHT,
         "config_value": DEFAULT_FEED_DAILY_POST_COUNT_3_WEIGHT},
        # 话题标签数量概率（PRD 4.3.4）
        {"config_key": CONFIG_FEED_HASHTAG_COUNT_0_WEIGHT,
         "config_value": DEFAULT_FEED_HASHTAG_COUNT_0_WEIGHT},
        {"config_key": CONFIG_FEED_HASHTAG_COUNT_1_WEIGHT,
         "config_value": DEFAULT_FEED_HASHTAG_COUNT_1_WEIGHT},
        {"config_key": CONFIG_FEED_HASHTAG_COUNT_2_WEIGHT,
         "config_value": DEFAULT_FEED_HASHTAG_COUNT_2_WEIGHT},
        {"config_key": CONFIG_FEED_HASHTAG_COUNT_3_WEIGHT,
         "config_value": DEFAULT_FEED_HASHTAG_COUNT_3_WEIGHT},
        # 图片张数分布
        {"config_key": CONFIG_FEED_IMAGE_COUNT_0_WEIGHT,
         "config_value": DEFAULT_FEED_IMAGE_COUNT_0_WEIGHT},
        {"config_key": CONFIG_FEED_IMAGE_COUNT_1_WEIGHT,
         "config_value": DEFAULT_FEED_IMAGE_COUNT_1_WEIGHT},
        {"config_key": CONFIG_FEED_IMAGE_COUNT_2_3_WEIGHT,
         "config_value": DEFAULT_FEED_IMAGE_COUNT_2_3_WEIGHT},
        {"config_key": CONFIG_FEED_IMAGE_COUNT_4_WEIGHT,
         "config_value": DEFAULT_FEED_IMAGE_COUNT_4_WEIGHT},
        # 图片类型权重
        {"config_key": CONFIG_FEED_IMAGE_TYPE_SELFIE_WEIGHT,
         "config_value": DEFAULT_FEED_IMAGE_TYPE_SELFIE_WEIGHT},
        {"config_key": CONFIG_FEED_IMAGE_TYPE_DAILY_WEIGHT,
         "config_value": DEFAULT_FEED_IMAGE_TYPE_DAILY_WEIGHT},
        {"config_key": CONFIG_FEED_IMAGE_TYPE_SCENERY_WEIGHT,
         "config_value": DEFAULT_FEED_IMAGE_TYPE_SCENERY_WEIGHT},
        {"config_key": CONFIG_FEED_IMAGE_TYPE_EMOTION_WEIGHT,
         "config_value": DEFAULT_FEED_IMAGE_TYPE_EMOTION_WEIGHT},
        # LiblibAI 生图参数（TB-LF-001）
        {"config_key": CONFIG_LIBLIB_TEXT2IMG_TEMPLATE_UUID,
         "config_value": DEFAULT_LIBLIB_TEXT2IMG_TEMPLATE_UUID},
        {"config_key": CONFIG_LIBLIB_IMG2IMG_TEMPLATE_UUID,
         "config_value": DEFAULT_LIBLIB_IMG2IMG_TEMPLATE_UUID},
        {"config_key": CONFIG_LIBLIB_GEN_STEPS,
         "config_value": DEFAULT_LIBLIB_GEN_STEPS},
        {"config_key": CONFIG_LIBLIB_GEN_WIDTH,
         "config_value": DEFAULT_LIBLIB_GEN_WIDTH},
        {"config_key": CONFIG_LIBLIB_GEN_HEIGHT,
         "config_value": DEFAULT_LIBLIB_GEN_HEIGHT},
        {"config_key": CONFIG_LIBLIB_IMG2IMG_STRENGTH,
         "config_value": DEFAULT_LIBLIB_IMG2IMG_STRENGTH},
        {"config_key": CONFIG_LIBLIB_IMG2IMG_RESIZED_WIDTH,
         "config_value": DEFAULT_LIBLIB_IMG2IMG_RESIZED_WIDTH},
        {"config_key": CONFIG_LIBLIB_IMG2IMG_RESIZED_HEIGHT,
         "config_value": DEFAULT_LIBLIB_IMG2IMG_RESIZED_HEIGHT},
        # 朋友圈页 Header
        {"config_key": CONFIG_FEED_PAGE_HEADER_BG_URL,
         "config_value": DEFAULT_FEED_PAGE_HEADER_BG_URL},
        {"config_key": CONFIG_FEED_PAGE_HEADER_AVATAR_URL,
         "config_value": DEFAULT_FEED_PAGE_HEADER_AVATAR_URL},
        {"config_key": CONFIG_FEED_PAGE_SIGNATURE,
         "config_value": DEFAULT_FEED_PAGE_SIGNATURE},
        {"config_key": CONFIG_FEED_PAGE_DISPLAY_NICKNAME,
         "config_value": DEFAULT_FEED_PAGE_DISPLAY_NICKNAME},
        # 发布窗口 / 历史可见范围
        {"config_key": CONFIG_FEED_PUBLISH_WINDOW_1, "config_value": DEFAULT_FEED_PUBLISH_WINDOW_1},
        {"config_key": CONFIG_FEED_PUBLISH_WINDOW_2, "config_value": DEFAULT_FEED_PUBLISH_WINDOW_2},
        {"config_key": CONFIG_FEED_PUBLISH_WINDOW_3, "config_value": DEFAULT_FEED_PUBLISH_WINDOW_3},
        {"config_key": CONFIG_FEED_HISTORY_VISIBLE_RANGE,
         "config_value": DEFAULT_FEED_HISTORY_VISIBLE_RANGE},
        # 南半球城市白名单
        {"config_key": CONFIG_SOUTHERN_HEMISPHERE_CITIES,
         "config_value": DEFAULT_SOUTHERN_HEMISPHERE_CITIES},
        # 点赞倍率范围
        {"config_key": CONFIG_FEED_BASE_LIKES_MIN, "config_value": DEFAULT_FEED_BASE_LIKES_MIN},
        {"config_key": CONFIG_FEED_BASE_LIKES_MAX, "config_value": DEFAULT_FEED_BASE_LIKES_MAX},
        {"config_key": CONFIG_FEED_LIKE_MULTIPLIER_MIN,
         "config_value": DEFAULT_FEED_LIKE_MULTIPLIER_MIN},
        {"config_key": CONFIG_FEED_LIKE_MULTIPLIER_MAX,
         "config_value": DEFAULT_FEED_LIKE_MULTIPLIER_MAX},
    ]

    # 关系档延迟窗口（评论回复 / 点赞常规 / 已读常规），单位秒
    for stage in RELATIONSHIP_STAGES:
        c_min, c_max = DEFAULT_COMMENT_REPLY_DELAY_SEC[stage]
        items.append({"config_key": comment_reply_delay_key(stage, "min"), "config_value": c_min})
        items.append({"config_key": comment_reply_delay_key(stage, "max"), "config_value": c_max})

        l_min, l_max = DEFAULT_LIKE_REGULAR_DELAY_SEC[stage]
        items.append({"config_key": like_regular_delay_key(stage, "min"), "config_value": l_min})
        items.append({"config_key": like_regular_delay_key(stage, "max"), "config_value": l_max})

        r_min, r_max = DEFAULT_READ_REGULAR_DELAY_SEC[stage]
        items.append({"config_key": read_regular_delay_key(stage, "min"), "config_value": r_min})
        items.append({"config_key": read_regular_delay_key(stage, "max"), "config_value": r_max})

    return items
