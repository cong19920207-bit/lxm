"""Pet-domain business errors; authentication remains HTTP 401/403."""
PET_CONFIG_CONFLICT=20300
PET_CONFIG_INVALID=20301
PET_UNAVAILABLE=20302
PET_REQUEST_CONFLICT=20303
PET_STATE_CONFLICT=20304
PET_ACTION_DISABLED=20305
PET_ERROR_MESSAGES={20300:'养宠配置已变化，请重新核对',20301:'养宠配置或引用不合法',20302:'养宠能力暂不可用',
                    20303:'同一请求标识内容不一致',20304:'宠物状态已变化，请重新核对',20305:'当前养宠动作已停用'}
