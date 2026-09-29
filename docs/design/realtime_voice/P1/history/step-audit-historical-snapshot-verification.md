# STEP 审计历史整合快照无损验证记录

> 状态：`history`
>
> 自动阅读：`false`
>
> 开发必读：`false`
>
> 验证日期：2026-08-29

## 1. 验证对象

- 合并文档：`docs/design/realtime_voice/P1/step-audit-historical-snapshot.md`
- SOURCE_A：`docs/design/realtime_voice/P1/history/step-audit.md`
- SOURCE_B：`docs/design/realtime_voice/P1/history/修正补充.md`

两个源文件从 P1 根目录移动到 `history/` 时只改变路径，没有改写内容。

## 2. 源文件移动前后指纹

| 源文件 | SHA-256 | 字节数 | 行数 | 移动前后 |
|---|---|---:|---:|---|
| SOURCE_A | `c0182a6c48f1d25f8ff48ec92cde2e3c0e8619680483071424bd6eed5e3e0fa8` | 41,278 | 485 | 完全一致 |
| SOURCE_B | `05085742b2c63ddf86535e1ded9c30522b3e7b88769f6f616ce5c6b96025c7e5` | 12,494 | 154 | 完全一致 |

## 3. 合并文档反向提取验证

从合并文档的 `BEGIN_SOURCE_A` / `END_SOURCE_A` 和 `BEGIN_SOURCE_B` / `END_SOURCE_B` 标记之间反向提取两段原文，再与历史目录中的源文件逐字节比较。

| 验证项 | SOURCE_A | SOURCE_B | 结果 |
|---|---:|---:|---|
| 逐字节比较 | `cmp=0` | `cmp=0` | 通过 |
| 提取内容 SHA-256 | `c0182a6c48f1d25f8ff48ec92cde2e3c0e8619680483071424bd6eed5e3e0fa8` | `05085742b2c63ddf86535e1ded9c30522b3e7b88769f6f616ce5c6b96025c7e5` | 与源文件相同 |
| 提取内容字节数 | 41,278 | 12,494 | 与源文件相同 |
| 提取内容行数 | 485 | 154 | 与源文件相同 |

验证结论：两个历史权威源文件均被合并文档 100% 无损收录，没有删除、替换或静默改写历史原文。

## 4. 合并文档指纹

| 文件 | SHA-256 | 字节数 | 行数 |
|---|---|---:|---:|
| `step-audit-historical-snapshot.md` | `39b857dd71a445bcfa578f2b37a010e48151036d60e2423df560ef3ca524fc7a` | 58,681 | 726 |

## 5. 自动阅读边界

- `docs/llm-manifest.json` 已将 `docs/design/realtime_voice/P1/history` 列入 `exclude_roots`。
- `docs/INDEX.md` 已将 `design/realtime_voice/P1/history/` 列入默认排除目录。
- 本目录 `README.md` 明确标记：历史资料、默认不自动读取、不是开发必读、不是当前权威。

因此，本验证记录及两个源快照只在用户明确要求历史核验、版本对比、恢复或审计追溯时读取。
