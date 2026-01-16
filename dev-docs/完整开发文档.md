
> 这是可直接用于实现的完整开发文档：架构建议、稳定契约（Schema）、阶段提示词、验证步骤、单元测试/集成测试/性能测试、验收点、返回码约定。
> 约束：不引入 LLM；不做可视化；CLI 优先；一条命令体验。

---

## 0) “完成”的定义（Done）
用户可以做到：

- `oka run --vault <path>`：稳定生成机器可读输出（`health.json`、`action-items.json`、`run-summary.json`）与人读报告（`report.md`）。
- `oka run --apply`：安全写入：
  - 默认交互式确认（可 `--yes` 跳过）
  - 写入租约（Write Lease）+ 同步静默窗口（Sync Quiescence）+ 原子写（atomic write）
  - 冲突时不覆盖用户改动，输出 unified diff + HOWTO 命令提示
  - 支持全量回滚；支持 Class A 的局部回滚（Partial Rollback）
- 大 Vault 可用：
  - SQLite 增量索引（cache）
  - I/O 节流与资源限制
  - `oka watch` 后台维护 cache，使 `oka run --apply` 写入窗口接近毫秒级
- 分发支持：
  - `pipx` 安装（开发者/高级用户）
  - 后续可扩展到单文件可执行（PyInstaller/Nuitka）

---

## 1) 参考架构（推荐拆分）

### 1.1 模块结构（建议）
- `oka/cli/`
  - `main.py`（Typer/Click 入口）
  - `commands/run.py`, `commands/doctor.py`, `commands/rollback.py`, `commands/watch.py`, `commands/prune.py`
- `oka/core/`
  - `pipeline.py`（run 分阶段编排）
  - `scanner.py`（文件发现、过滤、采样）
  - `parser.py`（frontmatter + links 解析）
  - `index.py`（SQLite schema + 增量更新）
  - `analyzers/`（健康指标）
  - `recommenders/`（metadata/link/merge preview）
  - `scoring.py`（confidence 模型、归一化、filter 因子）
  - `planner.py`（组装 action-items）
  - `applier/`（apply 引擎、原子写、格式规范化）
  - `rollback/`（run-log 解析、规则限制、撤销/三向合并）
  - `conflicts/`（diff 生成、HOWTO 生成）
- `oka/integrations/`
  - `git.py`（repo 检测、状态、auto_commit）
  - `locks.py`（write lease、offline-lock）
  - `sync.py`（quiet window 检测、starvation 逻辑）
- `oka/config/`
  - `defaults.toml`, `loader.py`（配置分层）
- `oka/reporting/`
  - `json_out.py`, `md_report.py`, `summary.py`

### 1.2 Run 核心数据流
`scan -> parse -> index(incremental) -> analyze -> recommend -> plan -> report -> summary -> (apply?) -> prune`

### 1.3 Action 风险分级
- **Class A**：安全 apply + 安全局部回滚
  - 追加带锚点的区块
  - frontmatter 键级写入/撤销
- **Class B1**：跨文件事务（rename + update-links）
  - 必须事务化执行；禁止局部回滚
  - 强烈建议启用 Git 策略（尤其 auto_commit）
- **Read-only**：仅预览（merge preview、诊断等）

---

## 2) 稳定契约（Schemas，不得破坏）
所有 schema 需加 `version` 字段；后续变更必须兼容或升级版本。

### 2.1 action-items.json（最小 schema）
```json
{
  "version": "1",
  "vault": "/abs/path",
  "generated_at": "ISO8601",
  "profile": "conservative",
  "items": [
    {
      "id": "act_0001",
      "type": "append_related_links_section",
      "risk_class": "A",
      "target_path": "Notes/foo.md",
      "confidence": 0.87,
      "reason": {
        "content_sim": 0.81,
        "title_sim": 0.62,
        "link_overlap": 0.12,
        "filters": ["path_penalty=0.90"],
        "top_terms": ["x", "y"]
      },
      "payload": {
        "anchor": "oka_related_v1",
        "markdown_block": "## Related\n- [[Bar]] (0.87)\n"
      },
      "dependencies": []
    }
  ]
}
```

要求：

- `reason` 必须可解释（分项贡献 + filters）。
    
- `payload` 对 Class A 必须包含可定位锚点（用于幂等写入与局部回滚）。
    

---

### 2.2 run-log.json（回滚与审计必需）

记录所有回滚所需信息与冲突检测信息。

```json
{
  "version": "1",
  "run_id": "20260116_235959_abcd",
  "vault": "/abs/path",
  "started_at": "ISO8601",
  "ended_at": "ISO8601",
  "git": { "repo": true, "policy": "require_clean", "pre_commit": null, "post_commit": null },
  "apply": { "interactive": true, "offline_lock": false, "write_lease": { "ttl_sec": 60 } },
  "changes": [
    {
      "action_id": "act_0001",
      "risk_class": "A",
      "target_path": "Notes/foo.md",
      "base_hash": "sha256...",
      "before_hash": "sha256...",
      "after_hash": "sha256...",
      "patch_path": "reports/runs/<run_id>/patches/foo.md.patch",
      "backup_path": null,
      "anchors": ["oka_related_v1"],
      "frontmatter_keys": ["keywords", "related"]
    }
  ],
  "conflicts": [
    { "target_path": "Notes/bar.md", "diff_path": "conflicts/bar.md.diff", "note_path": "conflicts/bar.md.note" }
  ]
}
```

---

### 2.3 run-summary.json（性能爽感与可观测性）

```json
{
  "version": "1",
  "run_id": "…",
  "timing": {
    "total_ms": 1234,
    "stages": {
      "scan_ms": 120,
      "parse_ms": 300,
      "index_ms": 200,
      "analyze_ms": 100,
      "recommend_ms": 350,
      "plan_ms": 50,
      "report_ms": 80
    }
  },
  "io": {
    "scanned_files": 12000,
    "skipped": { "non_md": 1000, "too_large": 12, "no_permission": 2 }
  },
  "cache": { "present": true, "hit_rate": 0.93, "incremental_updated": 14 },
  "downgrades": [ "recommend_merge_preview_skipped_timeout" ],
  "sync": { "quiet_window_sec": 3, "waited_sec": 0, "starvation": false, "offline_lock": false },
  "git": { "repo": true, "status_clean": true, "policy": "require_clean" }
}
```

---

### 2.4 conflicts 输出（必须可手工解决）

- `conflicts/<file>.diff`：统一 **unified diff**（兼容 `patch` / `git apply`）
    
- `conflicts/HOWTO.txt`：必须包含命令提示：
    
    - `patch -p0 < <file>.diff`
        
    - `git apply <file>.diff`
        
    - 以及查看 diff 的建议
        

---

## 3) Apply 写入状态机（安全写入）

### 3.1 Pre-apply 顺序

1. 读取配置分层（CLI > oka.toml > defaults）
    
2. Doctor-lite：
    
    - Vault 可访问、配置有效、锁文件状态
        
3. Git 策略（若 repo）：
    
    - require_clean / allow_dirty / auto_stash / auto_commit
        
4. Sync 静默窗口检测（有上限）：
    
    - 检测 `.obsidian/*` 活跃 + mtime 抖动抽样
        
    - 等待 <= `apply.max_wait_sec`
        
    - 若 starvation：最小化写入集合 或 offline-lock 或退出
        
5. 获取 Write Lease（`locks/write-lease.json`，含 TTL）
    
6. 交互式确认（默认）：
    
    - 展示变更摘要表
        
    - `y/n/preview`
        
7. 执行写入：  
    -（可选）编码/换行规范化
    
    - 原子写入
        
    - hash 校验
        
    - 冲突：生成 diff + note + HOWTO，不覆盖
        
8. 释放锁
    
9. 执行 prune（若开启）
    
10. 输出 run-log + run-summary，返回码
    

---

### 3.2 返回码约定（建议）

- `0`：成功且无冲突
    
- `2`：成功但存在冲突（已生成可操作的冲突产物）
    
- `10`：因 Git 策略拒绝（工作区不干净等）
    
- `11`：因 sync starvation 拒绝（无法获取安全窗口，需用户处理）
    
- `12`：因锁拒绝（活动锁/陈旧锁，除非 `--force`）
    
- `20`：致命错误（异常）
    

---

## 4) 测试策略（必须自动化）

### 4.1 单元测试（pytest）

最低覆盖范围：

- 解析：
    
    - frontmatter 解析、links 解析
        
    - 编码检测（UTF-8 BOM / 非 UTF-8）
        
    - 换行检测（LF/CRLF）
        
- scoring：
    
    - 归一化模式（quantile 默认）与 clamp
        
    - filter 因子生效
        
- planner：
    
    - action-items 结构校验
        
    - risk_class 赋值与 dependencies
        
- locks：
    
    - write lease TTL、陈旧检测
        
    - offline-lock marker 创建/移除
        
- git：
    
    - repo 检测、status 解析、auto_commit（mock）
        
- diff：
    
    - unified diff 生成、HOWTO 内容生成
        

---

### 4.2 集成测试（sample vault fixtures）

建立 `tests/fixtures/sample_vault/`，包含：

- 孤岛笔记
    
- 断链
    
- 相似内容（跨文件夹）
    
- UTF-8 BOM 与非 BOM 混用
    
- CRLF 与 LF 混用
    
- 大文件（> max_file_mb，用于跳过）
    
- 冲突场景：
    
    - run 生成 plan
        
    - apply 写入
        
    - 手动修改文件
        
    - rollback => 必须走冲突流程，不覆盖
        

集成测试用例：

- `oka run` 输出稳定产物
    
- `oka run --json` stdout 输出 JSON
    
- `oka run --apply --yes`：
    
    - 生成 run-log 与 patches
        
    - 幂等：重复 apply 不应重复插入锚点区块
        
- rollback：
    
    - 全量回滚恢复到 before_hash
        
    - 局部回滚仅对 Class A 成功
        
- pruning：
    
    - 多次运行后按策略清理 runs
        
- sync starvation：
    
    - mock “持续 mtime 抖动” -> 有上限等待 -> 走 fallback（最小化写入/退出）
        
- git policy：
    
    - dirty tree -> require_clean 拒绝
        
    - auto_commit 创建两次 commit（mock）
        
- watch：
    
    - 更新 cache，并触发 run 快路径（mock 时间与文件变更）
        

---

### 4.3 性能基准（脚本 + CI smoke）

提供 `scripts/bench.py`：

- 生成或测试：100 / 1k / 10k 笔记（合成数据）
    
- 输出阶段耗时与资源统计（JSON）  
    CI smoke：至少跑 100/1k 防回退。
    

---

## 5) 里程碑验收标准（Acceptance）

### v1.0.0

- `oka run` 在 fixture vault 上输出：
    
    - `health.json`、`report.md`、`action-items.json`、`run-summary.json`
        
- `--json` 输出合法 JSON
    
- help 分组清晰
    

### v1.1.0

- 推荐可解释、可阈值控制
    
- 合并仅预览
    
- report.md 具备“上下文调参提示”
    

### v1.2.0

- `--apply` 默认启用 write lease + interactive
    
- 冲突输出 unified diff + HOWTO，可手工解决
    
- 全量回滚不覆盖未知修改
    

### v1.3.0

- 增量运行明显更快（hit_rate 可见）
    
- 归一化降低长文偏置（有单测）
    
- 资源限制/跳过策略稳定
    

### v1.4.0

- 局部回滚仅 Class A，安全且有测试
    
- pruning 生效，reports 有界
    
- 覆盖率 >= 80%，CI 门禁通过
    

### v1.5.0

- sync starvation 不会无限阻塞
    
- offline-lock 流程可用并有测试（mock markers）
    

### v1.6.0

- `oka watch` 维护 cache，run 走快路径（run-summary 可观测）
    
- I/O 节流降低冷启动冲击
    

### v2.0.0

- Git policy 完整，auto_commit（mock）验证
    
- Class B1（rename+update-links）事务化，禁止局部回滚，Git-first 绑定
    

### v2.3.0

- 生成 Win/macOS/Linux 单文件可执行
    
- 跨平台编码/换行/路径一致性通过测试
    

---

## 6) 给 Codex / Claude Code 的阶段提示词（Task Cards）

说明：每张卡都应产出代码 + 测试 + 文档更新；最后跑通验证步骤。

### Prompt v1.0.0 — CLI 骨架 + 产物 + summary + doctor init-config

**提示词**  
实现 `oka` CLI：`oka run`（只读 pipeline）输出 `reports/` 下的稳定产物，并打印简短性能摘要；实现 `oka doctor` 并支持 `--init-config` 生成 `oka.toml`；为 `oka run` 增加 `--json` 将结构化结果输出到 stdout。

**验证**

- 在 `tests/fixtures/sample_vault` 上运行：
    
    - 产物存在：health.json/report.md/action-items.json/run-summary.json
        
- `oka run --json` 输出可解析 JSON
    
- `oka --help` / `oka run --help` 分组清晰
    

---

### Prompt v1.1.0 — 推荐器 + 可解释评分 + report 调参提示

**提示词**  
实现推荐器：元数据（keywords/aliases/related）、链接建议（追加带锚点的 Related 区块）、合并候选仅预览。实现可解释的评分模型并输出 `reason`（分项贡献 + filters）。更新 report.md：对低置信度/高噪声建议给出“该调哪个配置”的提示。

**验证**

- action-items.json 中每条 item 含 confidence + reason
    
- report.md 至少对一类低置信度建议给出调参提示
    
- 合并输出仅预览，不进入 apply
    

---

### Prompt v1.2.0 — Apply 引擎 + Write Lease + Interactive + 冲突 diff + 全量回滚

**提示词**  
实现 `oka run --apply`：包含 preflight 静默检测、write lease（TTL）、默认交互确认（y/n/preview）、原子写入、hash 校验、冲突输出（unified diff + HOWTO）。实现 `oka rollback <run_id>` 全量回滚。补齐返回码约定。

**验证**

- apply 生成 run-log.json 与 patches
    
- 冲突时不覆盖用户修改，conflicts 目录产物可用
    
- rollback 在无外部修改时可恢复；有外部修改时走冲突流程
    

---

### Prompt v1.3.0 — SQLite 增量索引 + 并行 + 归一化置信度 + benchmark

**提示词**  
实现 SQLite 增量索引（版本化 schema），增量扫描与重计算；CPU 重阶段并行；大文件/资源限制；实现内容相似度归一化（quantile 默认）与 confidence clamp；提供 scripts/bench.py 并把命中率/跳过/降级写入 run-summary。

**验证**

- 小改动后二次 run：hit_rate 高、incremental_updated 小
    
- bench 脚本可跑 100/1k 并输出 JSON
    
- 单测证明归一化降低长文偏置
    

---

### Prompt v1.4.0 — 局部回滚（仅 Class A）+ pruning + CI 门禁

**提示词**  
实现局部回滚：`--item` 与 `--file`，仅允许 Class A（锚点区块/键级 frontmatter）。实现 pruning policy 并在 apply 后执行轻量清理。完善测试与 CI 门禁，覆盖率 >= 80%。

**验证**

- Class A 局部回滚可用
    
- Class B1 局部回滚被拒绝并提示用 Git revert
    
- 多次运行后 runs 被清理
    
- CI 与覆盖率门禁通过
    

---

### Prompt v1.5.0 — sync starvation（有上限等待）+ offline-lock

**提示词**  
实现 sync 静默检测的硬上限等待（apply.max_wait_sec）。当 starvation 发生时，走降级路径（最小化写入集合）并支持 `--offline-lock` 创建/移除 marker 文件。确保不会无限等待，run-summary 记录决策。

**验证**

- mock 持续 churn：工具不会卡死
    
- offline-lock 期间 marker 存在，结束后移除
    
- run-summary 记录 waited_sec/starvation/offline_lock
    

---

### Prompt v1.6.0 — `oka watch` 后台预检索引 + 快路径 + I/O 节流

**提示词**  
实现 `oka watch`：低优先级、I/O 节流、持续维护 cache。更新 `oka run`：cache 新鲜时走快路径，将写入窗口压缩。run-summary 需记录是否 fast-path。

**验证**

- watch 能更新 cache
    
- run-summary 标记 fast-path
    
- 节流参数生效（测试）
    

---

### Prompt v2.0.0 — Git 策略 + auto_commit + Class B1 事务

**提示词**  
实现 Git 集成：检测 repo、执行 require_clean/allow_dirty/auto_stash/auto_commit。实现 Class B1（rename+update-links）事务化执行，禁止局部回滚，强提示 Git-first。auto_commit 需要 pre-commit checkpoint 与 post-commit 记录在 run-log。

**验证**

- dirty tree 下 require_clean 拒绝
    
- auto_commit（mock）产生两次 commit 并记录
    
- rename+update-links 事务一致性与回滚建议正确
    

---

### Prompt v2.3.0 — 单文件分发

**提示词**  
加入 PyInstaller/Nuitka 构建流程，输出 Win/macOS/Linux 单文件可执行。补齐安装文档。添加跨平台一致性测试（编码/换行/路径/权限）。

**验证**

- 构建产物生成
    
- 二进制可在 sample vault 上跑通 smoke test
    
- 跨平台一致性测试通过
    

---

## 7) 实现注意事项（避免常见坑）

- 锚点区块必须包含唯一 anchor，apply/rollback 都靠它定位（幂等 + 局部回滚的基础）。
    
- frontmatter 修改必须键级别合并，禁止覆盖整个 frontmatter，避免丢字段。
    
- 不维护“长期全库依赖图”：只维护本次 run 的 transaction graph；Class B1 一律事务化。
    
- 冲突永远输出 artifacts，而不是覆盖；CLI 给出一眼看懂的摘要与 HOWTO。
    
- CLI flags 保持最少：复杂参数下沉到 `oka.toml`；report 负责引导调参。
    
- run-summary 必须可感知性能：命中率、跳过数、降级原因、等待秒数等。
    

---

## 8) DoR / DoD（工程门禁）

### DoR（准备完成）

- schema 版本明确
    
- fixtures 已准备
    
- CLI 骨架可跑
    

### DoD（交付完成）

- 所有测试通过 + 覆盖率门禁
    
- 输出契约稳定
    
- 文档更新
    
- 返回码一致
    
- run-summary 既写文件也在 CLI 末尾打印（性能爽感）
    
