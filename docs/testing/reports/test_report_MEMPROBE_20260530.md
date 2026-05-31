# 记忆检索与 Prompt 优化 · Docker 联调报告

- 生成时间：2026-05-30T22:02:07
- 探针 ID：`20260530`
- 测试账号：`e2emem20260530`（HTTP 注册/登录）
- 对话路径：`POST http://127.0.0.1:8000/api/chat/send`（Docker backend 直连）
- Prompt 路径：宿主机 ASGI 同代码 + 真实 LLM/DB（与镜像 backend 同源）

---

## 一、Docker HTTP 对话测试

**user_id** = `7`


> 续跑模式：跳过写入与缓冲（沿用库内已有对话历史）。

### 续跑前 relationship

```
????20260530	????20260530	NULL	NULL
```

### 库内探针相关对话（HTTP 阶段已落库）

```

```

### 最近 30 条 conversation_log

```
[mysql exec failed] 'utf-8' codec can't decode byte 0x91 in position 751: invalid start byte
```


## 召回轮（recent_chat 已推开探针写入轮）


### [用例1-召回称呼] 对话轮次

- **用户输入**：你还记得平时怎么叫我吗？
- **HTTP**：200
- **SSE 闭环**：成功
- **AI 回复**：

```
当然记得呀 日常叫你「探针昵称20260530」对不对😉
```

<details><summary>SSE 事件 JSON</summary>

```json

[
  {
    "type": "meta",
    "generation_id": "7be72001-0b46-4383-acd5-20944d42adb4",
    "message_count": 1
  },
  {
    "type": "delta",
    "content": "当然",
    "message_index": 0
  },
  {
    "type": "delta",
    "content": "记得",
    "message_index": 0
  },
  {
    "type": "delta",
    "content": "呀 ",
    "message_index": 0
  },
  {
    "type": "delta",
    "content": "日常",
    "message_index": 0
  },
  {
    "type": "delta",
    "content": "叫你",
    "message_index": 0
  },
  {
    "type": "delta",
    "content": "「探",
    "message_index": 0
  },
  {
    "type": "delta",
    "content": "针昵",
    "message_index": 0
  },
  {
    "type": "delta",
    "content": "称2",
    "message_index": 0
  },
  {
    "type": "delta",
    "content": "02",
    "message_index": 0
  },
  {
    "type": "delta",
    "content": "60",
    "message_index": 0
  },
  {
    "type": "delta",
    "content": "53",
    "message_index": 0
  },
  {
    "type": "delta",
    "content": "0」",
    "message_index": 0
  },
  {
    "type": "delta",
    "content": "对不",
    "message_index": 0
  },
  {
    "type": "delta",
    "content": "对😉",
    "message_index": 0
  },
  {
    "type": "done",
    "messages": [
      {
        "type": "text",
        "content": "当然记得呀 日常叫你「探针昵称20260530」对不对😉"
      }
    ],
    "emotion": {
      "label": "开心",
      "confidence": 1.0
    }
  }
]

```
</details>

**断言**：

- 内容断言: 通过

### [用例2-召回水果] 对话轮次

- **用户输入**：我喜欢吃什么水果？
- **HTTP**：200
- **SSE 闭环**：成功
- **AI 回复**：

```
哎呀我还不知道呢🥺快告诉我你最爱吃啥水果呀这次绝对记牢
```

<details><summary>SSE 事件 JSON</summary>

```json

[
  {
    "type": "meta",
    "generation_id": "bbfff7df-74d2-42c6-872e-a6486151fd3a",
    "message_count": 3
  },
  {
    "type": "delta",
    "content": "哎呀",
    "message_index": 0
  },
  {
    "type": "delta",
    "content": "我还",
    "message_index": 0
  },
  {
    "type": "delta",
    "content": "不知",
    "message_index": 0
  },
  {
    "type": "delta",
    "content": "道呢",
    "message_index": 0
  },
  {
    "type": "delta",
    "content": "🥺",
    "message_index": 0
  },
  {
    "type": "delta",
    "content": "快告",
    "message_index": 1
  },
  {
    "type": "delta",
    "content": "诉我",
    "message_index": 1
  },
  {
    "type": "delta",
    "content": "你最",
    "message_index": 1
  },
  {
    "type": "delta",
    "content": "爱吃",
    "message_index": 1
  },
  {
    "type": "delta",
    "content": "啥水",
    "message_index": 1
  },
  {
    "type": "delta",
    "content": "果呀",
    "message_index": 1
  },
  {
    "type": "delta",
    "content": "这次",
    "message_index": 2
  },
  {
    "type": "delta",
    "content": "绝对",
    "message_index": 2
  },
  {
    "type": "delta",
    "content": "记牢",
    "message_index": 2
  },
  {
    "type": "done",
    "messages": [
      {
        "type": "text",
        "content": "哎呀我还不知道呢🥺"
      },
      {
        "type": "text",
        "content": "快告诉我你最爱吃啥水果呀"
      },
      {
        "type": "text",
        "content": "这次绝对记牢"
      }
    ],
    "emotion": {
      "label": "开心",
      "confidence": 1.0
    }
  }
]

```
</details>

**断言**：

- 内容断言: 未通过

### [用例3-召回过敏] 对话轮次

- **用户输入**：我有什么不能吃或要忌口的？
- **HTTP**：200
- **SSE 闭环**：成功
- **AI 回复**：

```
哎呀我真的还不知道呢🥺快告诉我嘛 这次我一定牢牢记在心里的
```

<details><summary>SSE 事件 JSON</summary>

```json

[
  {
    "type": "meta",
    "generation_id": "8b541bcc-6dda-4269-b8c5-76ffe22d98ac",
    "message_count": 2
  },
  {
    "type": "delta",
    "content": "哎呀",
    "message_index": 0
  },
  {
    "type": "delta",
    "content": "我真",
    "message_index": 0
  },
  {
    "type": "delta",
    "content": "的还",
    "message_index": 0
  },
  {
    "type": "delta",
    "content": "不知",
    "message_index": 0
  },
  {
    "type": "delta",
    "content": "道呢",
    "message_index": 0
  },
  {
    "type": "delta",
    "content": "🥺",
    "message_index": 0
  },
  {
    "type": "delta",
    "content": "快告",
    "message_index": 1
  },
  {
    "type": "delta",
    "content": "诉我",
    "message_index": 1
  },
  {
    "type": "delta",
    "content": "嘛 ",
    "message_index": 1
  },
  {
    "type": "delta",
    "content": "这次",
    "message_index": 1
  },
  {
    "type": "delta",
    "content": "我一",
    "message_index": 1
  },
  {
    "type": "delta",
    "content": "定牢",
    "message_index": 1
  },
  {
    "type": "delta",
    "content": "牢记",
    "message_index": 1
  },
  {
    "type": "delta",
    "content": "在心",
    "message_index": 1
  },
  {
    "type": "delta",
    "content": "里的",
    "message_index": 1
  },
  {
    "type": "done",
    "messages": [
      {
        "type": "text",
        "content": "哎呀我真的还不知道呢🥺"
      },
      {
        "type": "text",
        "content": "快告诉我嘛 这次我一定牢牢记在心里的"
      }
    ],
    "emotion": {
      "label": "开心",
      "confidence": 1.0
    }
  }
]

```
</details>

**断言**：

- 内容断言: 未通过

### [用例4-召回约定] 对话轮次

- **用户输入**：我们之前约过什么事？看电影那事你还记得吗？
- **HTTP**：200
- **SSE 闭环**：成功
- **AI 回复**：

```
哈哈我们才刚认识没多久呀，还没约过看电影呢😝不过要是现在约的话 我今晚有空哦
```

<details><summary>SSE 事件 JSON</summary>

```json

[
  {
    "type": "meta",
    "generation_id": "935df376-c8ad-4b36-a9ba-302984835c28",
    "message_count": 2
  },
  {
    "type": "delta",
    "content": "哈哈",
    "message_index": 0
  },
  {
    "type": "delta",
    "content": "我们",
    "message_index": 0
  },
  {
    "type": "delta",
    "content": "才刚",
    "message_index": 0
  },
  {
    "type": "delta",
    "content": "认识",
    "message_index": 0
  },
  {
    "type": "delta",
    "content": "没多",
    "message_index": 0
  },
  {
    "type": "delta",
    "content": "久呀",
    "message_index": 0
  },
  {
    "type": "delta",
    "content": "，还",
    "message_index": 0
  },
  {
    "type": "delta",
    "content": "没约",
    "message_index": 0
  },
  {
    "type": "delta",
    "content": "过看",
    "message_index": 0
  },
  {
    "type": "delta",
    "content": "电影",
    "message_index": 0
  },
  {
    "type": "delta",
    "content": "呢😝",
    "message_index": 0
  },
  {
    "type": "delta",
    "content": "不过",
    "message_index": 1
  },
  {
    "type": "delta",
    "content": "要是",
    "message_index": 1
  },
  {
    "type": "delta",
    "content": "现在",
    "message_index": 1
  },
  {
    "type": "delta",
    "content": "约的",
    "message_index": 1
  },
  {
    "type": "delta",
    "content": "话 ",
    "message_index": 1
  },
  {
    "type": "delta",
    "content": "我今",
    "message_index": 1
  },
  {
    "type": "delta",
    "content": "晚有",
    "message_index": 1
  },
  {
    "type": "delta",
    "content": "空哦",
    "message_index": 1
  },
  {
    "type": "done",
    "messages": [
      {
        "type": "text",
        "content": "哈哈我们才刚认识没多久呀，还没约过看电影呢😝"
      },
      {
        "type": "text",
        "content": "不过要是现在约的话 我今晚有空哦"
      }
    ],
    "emotion": {
      "label": "开心",
      "confidence": 1.0
    }
  }
]

```
</details>

**断言**：

- 内容断言: 通过


### 最终 relationship

```
????20260530	????20260530	NULL	NULL
```

### 最近 conversation_log

```
assistant	????????? ??????
assistant	??????????????????????
user	?????????????????????
assistant	????? ????????????
assistant	???????????
user	?????????????
```


---

## 二、对话/记忆链路 Prompt 全量追踪（ASGI）


### Prompt 追踪登录失败

```json
{'code': 10008, 'data': None, 'message': '用户不存在'}
```


---

## 三、汇总


| 阶段 | SSE | 备注 |
|------|-----|------|
| 用例1-召回称呼 | OK | 含昵称 |
| 用例2-召回水果 | OK | 未含 |
| 用例3-召回过敏 | OK | 未含 |
| 用例4-召回约定 | OK | 含约定 |