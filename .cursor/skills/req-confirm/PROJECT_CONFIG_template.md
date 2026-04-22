# PROJECT_CONFIG 模板
# 使用说明：复制本文件，重命名为 PROJECT_CONFIG_[项目名].md，填入项目信息后上传到 Project 文件

---

## 基本信息

- **项目名称**：[填写项目名，如：B项目 / AI陋子]
- **项目类型**：[如：AI 虚拟人对话系统]
- **技术栈**：[如：FastAPI + MySQL + DashVector + Redis]

---

## 代码结构

- **代码根目录**：[如：backend/]
- **主要入口**：[如：backend/main.py]

### 关键文件映射

> 填写与本次需求最相关的文件，不需要列举所有文件

| 文件路径 | 职责描述 |
|---------|---------|
| [如：backend/routers/chat.py] | [对话接口入口，含 SSE 推送逻辑] |
| [如：backend/services/relationship_service.py] | [关系等级与成长值逻辑] |
| [如：backend/services/scheduler.py] | [后台定时任务] |
| [如：backend/services/memory_service.py] | [记忆提取与向量写入] |
| [如：backend/services/prompt_builder.py] | [Prompt 拼装，七模块结构] |

---

## 项目文档

- **契约文档**：@[填写契约文档文件名，如：contract.md]
- **需求文档**：@[填写需求文档文件名，如：B项目对话链路改造需求文档.md]

---

## 项目约定

> 填写本项目特有的命名、格式、规范约定，避免 AI 猜测

- **接口响应格式**：[如：统一 ApiResponse 信封，code=0 成功]
- **错误码规范**：[如：H5 端从 10001 起，Admin 端从 20001 起]
- **字段命名风格**：[如：snake_case，与数据库字段保持一致]
- **向量库类型标识**：[如：character_setting / character_knowledge / user，注意拼写]
- **其他约定**：[填写其他重要约定]

---

## 已知技术债 / 特殊情况

> 填写可能影响需求确认的已知问题，避免 AI 重复踩坑

| 编号 | 描述 | 影响范围 |
|------|------|---------|
| [如：TD-001] | [users 表与 relationship 表有并行字段，以 relationship 为准] | [关系相关需求] |
| [填写] | [填写] | [填写] |

---

## 本次需求背景（可选）

> 简述本次改造的背景，帮助 AI 快速建立上下文

[如：本次改造参考 A 项目（Luoyun）的9阶段对话链路，为 B 项目补充查询重写、多路检索、响应优化、记忆更新、主动消息等能力]
