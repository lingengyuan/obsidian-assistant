# Obsidian Assistant vNext.3 SPEC

This is the source of truth for vNext.3 implementation, tests, acceptance, and CI gates.

MUST rules in this spec are implementation gates. Any deviation must be documented via a PR updating this SPEC.

## 0. 文档定位

- 本文档是 vNext.3 的**最终可交付 SPEC**：用于指导实现、测试、验收、回归与持续集成。
    
- “强约束（MUST）”条款为实现门禁；任何偏离必须在 PR 中显式说明并更新本 SPEC。
    

---

## 1. 背景与目标

### 1.1 背景

用户主要痛点（优先级）：

- **A1**：写完笔记不想手工加 tags / aliases / related
    
- **A2**：笔记之间关系弱，缺少自动“相关笔记”浮现
    
- **A3**：笔记质量与一致性不足（重复、断链、格式等），缺少自动化检查与改进闭环
    

规模：

- 当前：100–200 篇，约 50MB（含少量图片）
    
- 未来：可能扩展至 10GB
    

内容：

- 主要中文（9:1），tags 用英文
    

### 1.2 M1 两周最小可用成果（H1）

运行工具后实现安全闭环：

- 自动生成并可写入（受控、可回滚）：
    
    - `tags`（英文，目标 3–6）
        
    - `aliases`
        
    - `keywords`
        
    - `Related` 区块（正文）+ related 列表（frontmatter）
        
- 默认只读：输出计划 + 报告
    
- 必须 `--apply` 才写入
    
- `--apply` 前必须摘要确认（y/n/preview）
    
- 支持 `--json` 输出结构化结果到 stdout（供脚本/Skill）
    

### 1.3 明确不做（Non-goals）

- 不自动执行高风险结构操作（只建议不执行）：
    
    - 重命名文件、跨文件更新链接（C5）
        
    - 合并/删除笔记（C6）
        
- 核心运行时不依赖 LLM（可离线辅助词典 bootstrap，但不进入 runtime）
    

---

## 2. 总体设计原则

1. **默认只读 + 显式写入**
    
2. **幂等性**：重复 run/apply 不产生重复块或重复字段
    
3. **可解释性**：related 推荐必须输出 reasoning（可审计）
    
4. **可回滚**：以 Git 为终极保险；run-log 记录细粒度动作
    
5. **性能友好**：watch 常驻索引；run 增量秒级；I/O 节流不影响 Obsidian
    
6. **配置分层**：CLI > oka.toml > 默认值，避免“火车头命令”
    

---

## 3. 动作分级（写入边界）

### 3.1 Class A（允许自动写入，必须可回滚/可审计）

- Frontmatter 增补/更新：`tags / aliases / keywords / related`
    
- 正文块更新：`## Related`（受锚点契约保护）
    
- 断链修复：仅在“目标可确定且低风险”时（否则只建议）
    
- 格式规范化：可选（建议独立开关/独立命令）
    

### 3.2 Class B（只建议不执行）

- 合并/删除笔记
    
- 重命名文件并更新全库链接
    
- 大规模目录重组（Daily 归档 M1 只建议，M3 才可选 apply）
    

---

## 4. CLI 与交互契约（MUST）

### 4.1 核心命令

- `oka watch`
    
- `oka run [--apply] [--json]`
    
- `oka rollback <run_id> [--files ...] [--actions ...] [--preview]`
    
- `oka doctor [--fix-format]`
    
- （推荐）`oka dict suggest` / `oka dict apply`
    
- （后续）`oka prune-stubs [--dry-run|--apply]`
    

### 4.2 `--json` 静默模式（MUST）

- `oka run --json`：仅输出结构化 JSON 到 stdout，不混入人读日志
    
- 人读报告仍写入 `reports/runs/<run_id>/report.md`
    

### 4.3 `--apply` 两层确认（MUST）

**层 1：全局摘要确认**  
展示：

- 本次将写入的文件数
    
- 动作类型计数（add_tags/update_related_block/add_aliases…）
    
- conflicts 数与类型摘要  
    输入：`y / n / preview`
    

**层 2：逐文件确认（条件触发，MUST）**  
触发条件（任一满足进入“逐文件队列”）：

- 存在 conflicts
    
- 检测到“用户删除 related 块，需要重建”
    
- tags 置信度在确认区间 `[min_confidence_for_confirmation, min_confidence_for_auto_apply)`
    
- related 块 hash mismatch（用户修改过）
    

逐文件菜单（MUST）：

- `[c]` Show new content
    
- `[d]` Show diff（若 N/A 必须说明原因）
    
- `[r]` Show reasoning
    
- `[s]` Skip this file
    
- `[y]` Apply this change
    
- `[n]` Abort apply（中止整个 apply）
    

### 4.4 preview 决策记录（Baseline Patch，MUST）

在 run-log 中记录每个进入 preview 的 action 的决策，枚举如下（MUST）：

- `auto_applied`
    
- `applied`
    
- `user_skipped`
    
- `user_aborted`
    
- `preview_timeout`（若实现超时）
    

---

## 5. 配置分层与默认值

优先级：CLI Flags > `oka.toml` > 内置默认

建议最小默认配置（示例）：

```toml
[tags]
enabled = true
prefix_hash = true
max_tags_per_note = 6
min_confidence_for_auto_apply = 0.90
min_confidence_for_confirmation = 0.75
min_confidence_for_suggestion = 0.60

[related]
enabled = true
top_k = 5
anchor_max_nonempty_lines = 3
format = "wikilink"  # wikilink|filename
force_overwrite = false

[watch]
enabled = true
scan_interval_sec = 2

[watch.retry_backoff]
initial_delay_sec = 10
max_delay_sec = 600
max_retries = 5
skipped_recheck_interval_sec = 3600
immediate_retry_debounce_sec = 5
immediate_retry_max_concurrent = 3

[watch.resources]
max_rss_mb = 200
io_sleep_ms = 100
max_files_per_sec = 10

[daily.stub]
lazy_reference_tracking = "auto"  # auto|always|never
auto_threshold_gb = 5
```

---

## 6. Tags / Keywords / Dictionary 策略（MUST）

### 6.1 设计：tags 受控、keywords 开放

- tags：英文，默认带 `#`，目标每篇 3–6
    
- keywords：中文为主，用于索引与相关性计算
    
- 目标：降低 tags 噪声，保留关键词覆盖
    

### 6.2 置信度分级（MUST）

- `>= 0.90`：可自动写入（apply）
    
- `[0.75, 0.90)`：进入逐文件确认
    
- `[0.60, 0.75)`：只建议，不写入
    
- `< 0.60`：仅 keywords/unmapped，不建议 tag
    

### 6.3 confidence_hint 计算（Baseline Patch，MUST）

用于 `dict-suggestions.template.yml` 给用户参考。

规则（MUST）：

- 若 `keyword_freq < 3` → `hint = 0.60`（样本量惩罚，强制降级）
    
- 否则：
    
    - ratio >= 0.60 → 0.90
        
    - ratio >= 0.35 → 0.75
        
    - else → 0.60
        
- 若 `keyword_freq >= 10` → `hint += 0.05`（上限 0.99）
    
- 最终 `round(hint, 2)`
    

### 6.4 dict template schema（MUST）

```yaml
unmapped_keywords:
  - keyword: "数据库"
    frequency: 23
    suggested_tag: "#database"
    confidence: 0.95
    confidence_hint: 0.92
    suggestion_source: "co_occurring:#backend(15),#performance(8)"
    contexts:
      - file: "Notes/MySQL优化.md"
        snippet: "...MySQL数据库的索引优化..."
    co_occurring_tags:
      - "#backend": 15
      - "#performance": 8
```

---

## 7. Related 推荐与写入契约（MUST）

### 7.1 信号优先级（用户偏好）

内容相似度 > 链接共现 > 同目录/同 tag boost

### 7.2 Related 双输出（MUST）

- frontmatter：`related: [...]`（机器读）
    
- 正文：`## Related`（人读）
    

### 7.3 Related 块契约（MUST）

- 标题：`## Related`
    
- 锚点：`<!-- oka:related:v1 -->`
    
- 锚点位置：标题后的 **前 3 个非空行**内（允许夹杂其他注释）
    
- 替换范围：从锚点行开始替换，直到下一个 H2（`^##` ）或文件末尾
    
- 标题行不替换（必须保留用户控制感）
    

### 7.4 边界 case（MUST → conflicts）

- 多个 `## Related`：`multiple_related_headings`（不自动更新）
    
- 有标题无锚点或锚点超距离：`missing_anchor` / `anchor_too_far`（视为用户自管）
    
- 用户删除块：`user_deleted_block`（apply 时交互确认是否重建）
    
- hash mismatch：`hash_mismatch`（输出 diff；需逐文件确认或 `--force-related`）
    
- base_hash 变化：`base_hash_changed`（避免 stale 写入）
    

### 7.5 reasoning 输出规范（MUST）

每个候选必须输出四要素：

1. Overall score（数值 + 语义标签）
    
2. Why recommended（三信号分项与勾选）
    
3. Shared keywords（中文关键词 + 若可映射显示 (#tag)）
    
4. Top evidence
    

语义标签阈值（MUST 固化）：

- > =0.90 Very High
    
- 0.80–0.90 High
    
- 0.70–0.80 Medium
    
- <0.70 Low
    

### 7.6 Top evidence（Baseline Patch，MUST，方案 C）

- 取 `shared_keywords` 前 3 项：
    
    - 若可映射则输出 `词(#tag)`，不可映射仅输出词
        
- 输出：`Top evidence: Shared topics: ...`
    
- 若无共享关键词：必须输出 `N/A` 并说明原因
    

---

## 8. watch 模式（MUST）

目标：后台维护索引，缩短 apply 碰撞窗口；不影响 Obsidian。

退避与恢复（MUST）：

- 解析失败：指数退避；超过 `max_retries` → skipped
    
- skipped：每小时 recheck；若 mtime/hash 变化触发优先重试
    
- 防抖与并发上限（MUST）：debounce 5s；并发最大 3
    

资源约束（MUST）：

- I/O 节流：默认 `io_sleep_ms=100`，`max_files_per_sec=10`
    
- RSS 上限：默认 200MB（超限必须降级或提示）
    

---

## 9. 写入安全：Git 策略与竞争控制

### 9.1 Git 终极保险（MUST）

- apply 前检查 repo dirty：
    
    - 若 dirty：要求 commit/stash 或启用 auto-commit
        
- 建议默认启用 auto-commit（首次 apply 交互询问并写入配置）
    

commit message 模板（MUST）：

- Pre-apply：`oka: checkpoint before apply [run:<run_id>]`
    
- Post-apply：包含统计 + summary 路径 + 回滚命令  
    末尾必须附：`To rollback: oka rollback <run_id>`
    

### 9.2 写入租约（建议但强烈推荐）

- apply 前短时静默检查（workspace.json 等写入频率）
    
- 高写入频率提示用户关闭 Obsidian / 暂停同步
    
- 可选 `--offline-lock`：尝试 `.nosync` 或系统锁（高级）
    

---

## 10. Rollback（MUST）

### 10.1 过滤语义（MUST）

- 支持 `--files` 与 `--actions`
    
- 同时提供时取交集：`files ∩ actions`
    

### 10.2 rollback preview（MUST）

- 必须显示：总 actions、files 匹配数、actions 匹配数、交集结果数
    
- 列出将回滚的 action_id 列表
    

### 10.3 preview 截断规则（Baseline Patch，MUST）

- 默认只展示 changed keys 的 before/after
    
- 未变更键显示 `(unchanged, N items)`
    
- `[d]` 才显示完整 diff
    

### 10.4 base_hash 校验（MUST）

- 回滚前校验 base_hash
    
- 不匹配进入 conflicts，不强行回滚
    

---

## 11. Daily 归档与 stub（阶段化）

### 11.1 M1：只建议

- 归档目录建议、重复/可合并/可删除建议（不执行）
    

### 11.2 M3：可选 apply（强绑定 Git auto-commit）

- 引用数分级：0 / 1–3 / 4+（分别：自动/确认/只建议）
    

### 11.3 stub 模板（MUST：方案 A，无插件依赖）

必须包含 `created_at`，便于 prune：

```md
---
stub: true
created_by: oka
created_at: "2026-01-17T20:30:00Z"
archived_to: "Archive/2026-01/2026-01-17"
aliases: ["2026-01-17"]
---

# 📌 此笔记已归档

原笔记已移至: [[Archive/2026-01/2026-01-17]]

此文件为自动生成跳转占位符，可安全删除（建议用 oka prune-stubs 管理）。

<!-- oka:stub:do_not_index -->
```

### 11.4 stub lazy 引用统计（Baseline Patch，MUST）

配置：

- `lazy_reference_tracking = "auto|always|never"`
    
- `auto`：当 vault_size >= 5GB 自动启用 lazy，并在 run-summary 给 tip 提示
    

lazy 行为（MUST）：

- 日常 watch/run 不做 stub 引用全库统计
    
- 仅在 `prune-stubs` 时触发一次引用统计
    

---

## 12. 输出与可观测性（MUST）

### 12.1 run-summary.json（MUST）

必须包含：

- run_id / mode
    
- timing_ms.total + stages（scan/parse/index 的 actual/target/met）
    
- SLA：**target threshold**（非分位数），必须写 note
    
- cache 命中/跳过数
    
- resources（max_rss、cpu_percent_10s、io_sleep_ms）
    
- errors（含 first_failed_at）
    
- degraded_files
    
- fallbacks
    
- conflicts：count + types 分类
    

SLA 口径（Baseline Patch，MUST）：

```json
"sla": {
  "target_ms": 30000,
  "met_sla": true,
  "note": "target threshold (not percentile measurement). For real P90, see 'oka benchmark --help' (future)"
}
```

### 12.2 run-log.json（MUST）

必须记录：

- action_id / file / action_type
    
- before_hash / after_hash / base_hash
    
- rollback.method
    
- preview_decisions（Baseline Patch，MUST）
    

### 12.3 conflicts 分类细分（Baseline Patch，MUST）

conflicts.types 必须按类型统计：

- multiple_related_headings
    
- missing_anchor
    
- anchor_too_far
    
- user_deleted_block
    
- hash_mismatch
    
- base_hash_changed
    
- （可扩展，但不得删除上述项）
    

---

## 13. 性能目标（SLO）

### 13.1 M1（200 篇 / 50MB）

- 增量 run：目标阈值 < 3s
    
- 冷启动 run：P50 < 15s；目标阈值（“P90 目标”）< 30s
    
- watch：RSS < 200MB；I/O 节流生效
    

### 13.2 M3（10GB 预留）

- 冷启动索引：目标阈值 < 5min（以真实数据校准）
    
- 必须有进度条与资源限制
    

> 重要：此处的 “P90” 为**目标阈值**，不是统计分位数。真实分位数统计属于未来可选 `oka benchmark`。

---

## 14. 分发与安装（目标）

- 提供单文件二进制（推荐），避免 Python 环境问题
    
- pipx/uv 安装可作为可选路径
    

---

## 15. 开发拆分与门禁

### 15.1 P0（必须）

1. Related block 引擎（契约/冲突/幂等）
    
2. preview 交互框架（两层确认 + 菜单）
    
3. reasoning 输出标准化（含 Top evidence 方案 C）
    
4. run-summary / run-log schema 落地（errors/conflicts/stages/SLA note）
    
5. watch 退避与自愈（防抖/并发/资源节流）
    

### 15.2 P1（强烈建议）

1. preview_decisions 完整记录（含 skip/abort/timeout）
    
2. confidence_hint + 样本量惩罚（dict suggest）
    
3. rollback 组合过滤 + preview 统计 + 截断规则 + detailed diff
    
4. stub lazy auto（5GB 自动切换 + tip）
    
5. errors recovered 记录（可选增强）
    

---

## 16. 测试 Vault 规范（Baseline Patch，MUST）

> 目的：将 SPEC 变成可回归测试合同。所有 edge cases 必须可在 fixtures 中复现。

### 16.1 目录结构（MUST）

```
tests/fixtures/test_vault/
├── Daily/
├── Notes/
├── Projects/
├── Archive/
├── Attachments/              # 少量图片/二进制模拟
└── manifest.json             # 每篇笔记的“预期特征”元数据
```

### 16.2 规模与分布（MUST）

- 总笔记数：**50 篇**（足以覆盖所有边界与回归）
    
- 场景覆盖（最少样本数）：
    
    - 正常笔记（frontmatter + 内容）：10
        
    - Daily 笔记：5（路径 `Daily/2026-01-XX.md`）
        
    - 多个 `## Related`：3（触发 `multiple_related_headings`）
        
    - 缺锚点：2（触发 `missing_anchor`）
        
    - 锚点超 3 行：2（触发 `anchor_too_far`）
        
    - 用户删除 Related：2（触发 `user_deleted_block`）
        
    - hash mismatch（手改块内容）：2（触发 `hash_mismatch`）
        
    - 特殊字符标题：5（包含 `[]`, `|`, `#`, 空格等）
        
    - 纯中文内容：3
        
    - 技术笔记（含代码块）：5
        
    - 大文件：2（>1MB，模拟性能与 I/O）
        
    - 空文件/极短文件：2（解析降级与 degraded_files）
        
    - 其余：随机组合填充（覆盖 link_overlap、path/tag boost）
        

### 16.3 manifest.json（MUST）

manifest 记录每个样本文件的预期特征（用于测试断言与生成 golden outputs）：

```json
{
  "Notes/sample1.md": {
    "has_frontmatter": true,
    "has_related_heading": true,
    "has_anchor": true,
    "expected_conflict": null
  },
  "Notes/multi_related.md": {
    "expected_conflict": "multiple_related_headings"
  }
}
```

### 16.4 Golden Outputs（MUST）

在 `tests/golden/` 固化回归输出：

```
tests/golden/
├── run-summary-cold-start.json
├── run-summary-incremental.json
├── run-log-sample.json
├── reasoning-output-sample.txt
├── related-block-normal.md
├── related-block-missing-anchor.md
├── related-block-multi-headings.md
└── conflicts-summary.json
```

规则（MUST）：

- 集成测试运行后必须对比 golden outputs
    
- 若 golden 变更，必须说明 SPEC 更新点或 bug 修复原因
    

---

## 17. 验收标准（MUST）

M1 验收必须满足：

- `oka run` 输出 report + run-summary（schema 合法）
    
- `oka run --apply`：
    
    - 全局摘要确认 + 条件触发逐文件 preview
        
    - Related 块幂等，无重复
        
    - tags/aliases/keywords 写入遵循置信度规则
        
- `oka rollback`：
    
    - 可全量回滚
        
    - 支持 `--files`/`--actions` 组合过滤（交集）
        
    - preview 截断规则生效
        
- `oka watch`：
    
    - backoff / skipped / recheck 生效
        
    - 资源节流不明显影响 Obsidian
        
- `--json`：stdout 结构化输出稳定可被脚本消费
    
- conflicts 分类统计准确，errors 含 first_failed_at，stages 有实际值
    

---

## 附录 A：Golden Outputs 对比规则（MUST）

- 对比应使用稳定字段（剔除时间戳等非稳定字段，或将其标准化）
    
- 任何 schema 字段增删必须同步更新：
    
    - SPEC（本文）
        
    - fixtures manifest
        
    - golden outputs
        
    - CI 断言
        

---

## 附录 B：AI 自检清单模板（MUST 推荐每阶段提示词内嵌）

**BEFORE YOU CODE**

-  已阅读对应 SPEC 章节与所有 MUST 条款
    
-  已列出 edge cases 与对应 fixtures 文件
    
-  已明确输出格式（schema / golden）
    

**AFTER YOU CODE**

-  函数均有 type annotations + docstring
    
-  覆盖所有 edge cases 的单测
    
-  集成测试对比 golden outputs
    
-  关键输出含 N/A 降级说明（不允许沉默缺失）
    
-  性能门禁：冷启动 < 30s（目标阈值）、增量 < 3s（目标阈值）
    
-  run-summary：SLA note 明确为 target threshold
    
-  run-log：preview_decisions 枚举完整
    

---

## 附录 C：PR/Commit 规范（MUST）

- PR 必须引用 SPEC 章节（如：`Ref: vNext.3 §7.4`）
    
- commit message 必须包含 run_id 回滚提示（post-apply 模板）
    

---

# 版本标识建议（落地用）

- 将本方案作为 `ROADMAP.md` 或 `SPEC.md`（推荐 `SPEC.md`）
    
- 版本号建议：`vNext.3-baseline`（用于区分“补丁后可开工基线”）
    

---
