
> 不引入 LLM。不做可视化。CLI 优先。一条命令体验。高性能。安全自动化。

## 目标（North Star）
- **性能**：增量运行足够快；冷启动可控；I/O 峰值可控、可节流。
- **体验**：用户只需要记住 `oka run`。
- **安全**：默认只读；写入必须显式 `--apply`；可预览；可回滚；冲突不覆盖用户改动。
- **真实世界鲁棒性**：跨设备同步、Git 工作流、编码/换行符混乱、插件字段冲突、并发竞争、同步饥饿等边界条件可控。
- **分发**：同时支持 `pipx` 与单文件可执行（PyInstaller/Nuitka）。

---

## 非目标（v2.4 线内不做）
- 核心代码路径不引入 LLM（未来 Skill Wrapper 可在外部调用 LLM，但不进入本仓库核心逻辑）。
- 不做 Dashboard/图表/可视化（仅文本与 JSON 输出）。
- 不做“自动合并笔记”（合并只做预览）。

---

## UX：主命令（用户只记这一套）

### 一条命令（默认只读）
```bash
oka run --vault /path/to/vault
```

### 一条命令（写入）

```bash
oka run --vault /path/to/vault --apply
# 默认：写入前交互式确认
```

### Script / Skill 集成（静默 JSON）

```bash
oka run --vault /path/to/vault --json
oka run --vault /path/to/vault --json --apply --yes
```

### 后台预检与索引维护（可选，但强烈建议同步频繁用户开启）

```bash
oka watch --vault /path/to/vault
```

### Doctor（健康诊断 / 初始化配置）

```bash
oka doctor --vault /path/to/vault
oka doctor --vault /path/to/vault --init-config
```

### 回滚

```bash
oka rollback <run_id>
oka rollback <run_id> --file path/to/note.md
oka rollback <run_id> --item <action_id>     # 局部回滚（仅 Class A）
```

---

## 输出与存储契约（稳定接口）

输出必须稳定、可机器消费（后续 Skill Wrapper 会依赖）。

```
reports/
  health.json
  report.md
  action-items.json
  run-summary.json
  runs/<run_id>/
    run-log.json
    patches/                 # 默认（patch 优先）
    backups/                 # 可选
    conflicts/
      <file>.diff            # 统一 diff（兼容 patch / git apply）
      <file>.note            # 冲突解释 + 建议处理
      HOWTO.txt              # 手工解决命令提示
cache/
  index.sqlite               # 版本化索引/缓存（增量）
locks/
  write-lease.json           # 写入租约锁
  offline-lock.json          # 强制离线锁（启用时）
```

默认采用 **Patch-first 存储** 以减少 metadata 膨胀。全量备份由策略控制（可选）。

---

## 核心概念

### 1) 配置分层（保持 CLI 简洁）

- **Level 1**：CLI Flags（临时覆盖）
    
- **Level 2**：`oka.toml`（项目级持久化配置）
    
- **Level 3**：内置默认（保守策略）
    

用户日常只跑 `oka run`，调参在 `oka.toml` 完成（通过 `oka doctor --init-config` 生成模板）。

### 2) Profiles（降低认知成本）

提供稳定预设：

- `conservative`（默认）：阈值更高、噪声更少、写入更克制
    
- `balanced`
    
- `aggressive`（建议更多，但仍默认安全）
    

支持 `--profile` 选择，并可写入 `oka.toml` 固化。

### 3) Action Items（统一自动化接口）

所有“建议/批量操作/自动化”都必须表达为 `action-items.json`。

要求：

- 必含：`id`, `type`, `target_path`, `confidence`, `reason`, `payload`
    
- 可选：`dependencies`, `risk_class`
    
- apply/rollback 只处理 action-items
    

### 4) 置信度模型（可解释、可归一化、可 clamp）

不使用 LLM，模型必须可解释、可调参。

公式：

```
Confidence = clamp(
  (w1 * Norm(Sim_Content) + w2 * Sim_Title + w3 * Overlap_Link) * Π FilterFactors,
  0, 1
)
```

要求：

- `Norm(Sim_Content)` 默认使用分位数归一化（quantile）以降低长文天然占优。
    
- `reason` 必须包含分项贡献与生效的过滤因子。
    
- 在 `oka.toml` 中可配置。
    

### 5) 安全写入：Write Lease + Sync Quiescence + 原子写

写入路径必须降低并发风险并避免数据丢失。

- 默认只读；写入必须 `--apply`。
    
- 默认交互式确认（可用 `--yes` 跳过）。
    
- 原子写：临时文件 -> fsync -> 原子 rename。
    
- 哈希跟踪：记录 `base_hash`（生成计划时）、`before_hash`（写入前）、`after_hash`（写入后）。
    
- 冲突安全：永不覆盖未知用户改动；输出 conflicts diff + 处理指引。
    

### 6) Sync Quiescence 与 Sync Starvation（同步静默与同步饥饿）

必须处理跨设备同步，以及同步工具持续写入的极端情况。

- Sync Quiescence Window：apply 前检测静默窗口（`.obsidian/*` 活跃、mtime 抖动等）。
    
- **不允许无限等待**：`apply.max_wait_sec` 硬上限。
    
- 若长期无法静默（饥饿）：
    
    - A) 最小化写入集合（仅 Class A / 用户选择子集）
        
    - B) 可选 `--offline-lock`（标记文件 + 更短写入窗口）
        
    - C) 明确退出并给出可操作指引
        

### 7) 强制离线模式（`--offline-lock`）

为同步饥饿用户提供：

- 临时创建部分同步工具可识别的标记文件（如 `.nosync`、`.stignore`，可配置）。
    
- 仍严格执行 hash 校验（offline-lock 不是强制覆盖）。
    
- 推荐与 `oka watch` 配合使用以压缩写入窗口。
    

### 8) Git 集成（终极保险）

若 Vault 是 Git 仓库，apply 前执行 Git 策略：

策略：

- `require_clean`（默认）：工作区不干净则拒绝 apply
    
- `allow_dirty`（高级用户）
    
- `auto_stash`（可选，默认关闭）
    
- `auto_commit`（高级安全）：apply 前 checkpoint commit -> apply -> apply 后 commit
    
    - 回滚直接走 `git revert`（强安全）
        

对高风险跨文件操作强烈建议启用 Git 策略。

### 9) 回滚模型（安全、可解释、可边界）

- 支持按 run_id 全量回滚。
    
- 局部回滚（Partial Rollback）：
    
    - **仅允许 Class A**（安全）：锚点区块追加/删除、frontmatter 键级撤销。
        
    - **Class B1（事务）**：rename + update-links 必须作为不可分割事务；禁止局部回滚。
        
    - **Class B2（不安全结构性变更）**：默认禁止，或仅 `--force` 且强交互确认，并提示改用 Git revert。
        
- 若文件在 apply 后被用户手动修改：
    
    - 优先对区块/字段做三向合并
        
    - 否则输出 conflicts，不覆盖
        

### 10) 存储清理策略（避免 Metadata Bloat）

`reports/runs` 必须有 pruning policy，避免无限增长。

`oka.toml` 需要支持：

- 保留最近 N 次
    
- 保留最近 M 天
    
- reports 总体积预算上限
    
- 可选压缩归档
    
- 每次 apply 后执行轻量 prune
    

### 11) I/O 节流与冷启动峰值控制

- 支持扫描速率限制、分批读取。
    
- `oka watch` 默认低优先级 + I/O 节流，提前维护索引以降低前台冲击。
    
- 避免与 Obsidian 同时运行时造成 UI 卡顿。
    

### 12) Doctor 增强点（必须覆盖）

`oka doctor` 需要检测：

- 路径/权限
    
- cache 兼容性、锁文件陈旧
    
- 插件 frontmatter 字段争用（可配置字段列表）
    
- 编码问题（UTF-8 BOM / 非 UTF-8）
    
- 换行符混用（LF/CRLF）
    
- 输出建议与推荐配置（降低 hash 不稳定）
    

### 13) 写入时格式规范化（可选但推荐）

开启后 apply 会统一：

- 编码（utf-8，BOM false）
    
- 换行符（lf 或 crlf）  
    以减少跨平台不可见差异带来的 hash 冲突。
    

---

## 里程碑与交付物（Milestones）

### v1.0.0 — 一条命令基线 + JSON + Doctor + 性能摘要

**交付**

- `oka run`（只读 pipeline）：scan -> analyze -> recommend -> plan -> report -> summary
    
- `--json`：stdout 输出结构化 JSON
    
- `run-summary.json` + CLI 末尾性能摘要：
    
    - 总耗时、阶段耗时
        
    - 扫描文件数、按原因统计跳过
        
    - cache 状态（存在与否）
        
- `oka doctor` 基线 + `--init-config`
    
- 基础编码/换行检测（只报告，不自动修复）
    

**验收**

- 在 sample vault 可稳定运行并输出上述文件。
    
- `--help` 输出按 Common / Safety / Performance / Advanced 分组清晰。
    

---

### v1.1.0 — 推荐系统（无 LLM）+ 可解释性 + 配置提示

**交付**

- 元数据建议（默认 `keywords/aliases/related`，tags 可选）
    
- 链接建议：追加带锚点的 Related 区块（安全追加）
    
- 合并：候选聚类 + 预览（不自动合并）
    
- 置信度模型：reason 内给出分项贡献 + filters
    
- `report.md`：对低置信度/高噪声建议给出“该调哪个参数”的提示
    

**验收**

- 建议可解释、可阈值控制。
    
- 合并仅预览，不进入 apply。
    

---

### v1.2.0 — Apply 框架：写入租约 + 交互确认 + 冲突 diff + 全量回滚

**交付**

- `--dry-run`：diff 摘要
    
- `--apply`：
    
    - preflight 静默检测（`.obsidian/*` 活跃等）
        
    - write lease（TTL）与 doctor 可识别陈旧锁
        
    - 默认交互确认（y/n/preview），`--yes` 可跳过
        
    - 原子写 + hash 跟踪
        
    - conflicts：统一 diff + HOWTO.txt（patch/git apply 命令提示）
        
- 全量回滚（按 run_id）
    

**验收**

- 不覆盖未知用户修改。
    
- 冲突产物可操作（用户能按 HOWTO 解决）。
    

---

### v1.3.0 — 增量性能 + 归一化置信度 + 基准脚本

**交付**

- SQLite 索引/缓存（版本化）
    
- 增量扫描与增量重计算
    
- 仅 CPU 重阶段并行
    
- 大文件策略 + 资源限制（max_file_mb/max_mem_mb/cpu/timeout）
    
- 内容相似度归一化（quantile 默认）+ confidence clamp
    
- benchmark 脚本 + summary 展示命中率/跳过/降级原因
    

**验收**

- 小改动后二次运行明显加速（hit_rate 明确展示）。
    
- 归一化降低长文天然占优（有单测证明）。
    

---

### v1.4.0 — 局部回滚（仅 Class A）+ 存储清理 + 质量门禁

**交付**

- 局部回滚：
    
    - 仅 Class A（锚点区块、frontmatter 键级）
        
    - 提示依赖关系（dependencies）与风险
        
- pruning policy：
    
    - 保留 N 次 / M 天 / reports 总体积上限 / 可选压缩
        
- 测试覆盖率 >= 80%，CI 质量门禁
    
- fixtures 覆盖：冲突、stale data、partial rollback
    

**验收**

- Class A 局部回滚稳定可靠。
    
- reports 目录长期可控，不膨胀。
    

---

### v1.5.0 — 同步饥饿处理 + 离线锁

**交付**

- 静默等待硬上限（apply.max_wait_sec）
    
- 饥饿 fallback：
    
    - 最小化写入集合（仅 Class A / 子集）
        
    - `--offline-lock`（可配置 marker）
        
- 清晰 UX：不会无限等待
    

**验收**

- 同步持续写入时工具不会卡死；要么安全降级 apply，要么解释清楚退出。
    

---

### v1.6.0 — `oka watch` 后台预检索引 + I/O 节流

**交付**

- `oka watch`：
    
    - 低优先级索引维护
        
    - I/O 节流与分批
        
- `oka run` 快路径：cache 足够新鲜时跳过重计算，把写入窗口压到毫秒级
    

**验收**

- sync 压力下冲突明显减少（run-summary 可观测）。
    
- 冷启动峰值被节流缓解。
    

---

### v2.0.0 — Git 策略（含 auto_commit）+ Class B1 事务模型 + 格式规范化写入

**交付**

- Git 检测与策略：
    
    - require_clean / allow_dirty / auto_stash / auto_commit
        
- Class B1 事务：rename + update-links 原子执行
    
    - 禁止局部回滚
        
    - 强烈建议 Git policy（尤其 auto_commit）
        
- 写入规范化（编码/换行）
    

**验收**

- 高风险跨文件变更可用 git revert 可靠恢复。
    
- 跨平台 hash 不稳定显著降低。
    

---

### v2.3.0 — 单文件分发 + 跨平台一致性

**交付**

- PyInstaller/Nuitka 单文件可执行（Win/macOS/Linux）
    
- pipx 与 binary 双路线文档
    
- 跨平台一致性测试：路径、编码、换行、权限
    

**验收**

- 用户无需管理 Python 环境即可使用。
    
- 三平台行为一致。
    

---

## 附录：配置键（高层）

`oka.toml` 必须覆盖：

- `[profile]`
    
- `[storage]`：保留策略 + patch/backups 模式
    
- `[apply]`：交互默认 + 等待上限 + 重试/退避
    
- `[apply.offline_lock]`：markers, ttl
    
- `[apply.git]`：策略（含 auto_commit）
    
- `[scan]`：I/O 节流与大文件过滤
    
- `[format]`：编码/换行规范化
    
- `[scoring]`：权重、归一化、clamp
    
- `[filters]`：路径惩罚/标签冲突惩罚/范围惩罚等
    

---

## 附录：Action Types（最小集合）

- `append_related_links_section`（Class A）
    
- `add_frontmatter_fields`（Class A）
    
- `create_stub_note`（可选，Class A）
    
- `fix_broken_links`（可选，保守处理，Class A/B 取决范围）
    
- `merge_preview`（只读）
    
- `rename_note_and_update_links`（Class B1 事务；强烈建议启用 Git）
    

```
::contentReference[oaicite:0]{index=0}
```