# STEP-002 契约增量（待里程碑判定）

来源：F210／AC212、AC213，steps-verified.md §6 STEP-002；实现 index.html、api.js::updateAvatarEmotion。

- 首页默认／情绪／回退／日记图使用 home-thumbnails/v2 内容哈希 URL；首页不请求原头像／日记大图。原件及其他页默认映射保留。
- updateAvatarEmotion(emotionLabel, avatarOptions={}) 增加可选 avatarMap 与 onError(img, failedSrc)，不提供参数时保留既有映射与默认失败回退。此参数只改变图像来源，不改变状态语、鉴权、业务请求或关系数据。
- 首页失败 URL 不在同页重复预载；默认／加载头像依次回退，均不可用时隐藏图像。加载头像始终保留自身内容职责。
- 验证：§9.8 与 execution/evidence/home-m1/step-002-results.json、step-002-requests.json；真实前端、桌面 Chrome、受控 API。四类手机正式首页仍待后续实测。
- 正式契约落点候选：docs/contract/current/h5-app/api.md 的首页资源／共享头像说明；本轮未写入正式契约。
