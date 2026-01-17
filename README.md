# Obsidian Assistant

<div align="center">

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)

**只读分析 Obsidian 知识库，输出稳定 JSON 与报告（CLI: `oka`）**

[功能特性](#功能特性) · [快速开始](#快速开始) · [输出与目录契约](#输出与目录契约) · [贡献指南](#贡献指南)

</div>

---

## 简介

Obsidian Assistant 是一个以安全只读为默认的命令行工具，专注输出稳定产物与可解释的推荐建议。核心体验是：

- 一条命令：`oka run --vault <path>`
- 产物稳定：`reports/health.json`, `reports/action-items.json`, `reports/run-summary.json`, `reports/report.md`
- 推荐系统仅生成 action-items（不写入 vault）
- `oka doctor` 检查路径、锁文件、编码与换行符

## 功能特性

### 核心功能

- **只读扫描与解析**：递归扫描 Markdown，解析 frontmatter 与内部链接 `[[...]]`
- **健康指标**：文件数、frontmatter 覆盖、链接统计、断链候选、孤岛笔记
- **推荐系统**：metadata 建议（keywords/aliases/related）、Related 追加区块（Class A）、相似笔记合并预览（只读）
- **可解释置信度**：reason 中包含分项得分与 filters
- **Doctor 检查**：路径/权限、锁文件、UTF-8 BOM/非 UTF-8、LF/CRLF 混用
- **增量索引**：`cache/index.sqlite` 持久化解析结果，命中时减少重复计算
- **Watch 与快路径**：`oka watch` 低优先级更新索引，`oka run` 在缓存新鲜时 fast-path
- **安全写入**：`oka run --apply` 写入 Class A，写入租约、冲突产物与回滚日志
- **回滚**：支持全量回滚与 `--item`/`--file` 的局部回滚（仅 Class A）
- **存储治理**：run 日志自动裁剪与可选压缩，避免报告目录膨胀

### 结构化输出（JSON 示例）

`action-items.json`（节选）：

```json
{
  "version": "1",
  "vault": "/abs/path",
  "generated_at": "2026-01-16T14:44:27Z",
  "profile": "conservative",
  "items": [
    {
      "id": "act_0001",
      "type": "append_related_links_section",
      "risk_class": "A",
      "target_path": "notes/alpha.md",
      "confidence": 0.51,
      "reason": {
        "content_sim": 0.846,
        "title_sim": 0.0,
        "link_overlap": 0.0,
        "filters": ["path_penalty=0.90"],
        "weights": { "content": 0.6, "title": 0.3, "link": 0.1 },
        "norm_method": "quantile"
      },
      "payload": {
        "anchor": "oka_related_v1",
        "markdown_block": "## Related\n<!-- oka_related_v1 -->\n- [[beta]] (0.51)\n"
      },
      "dependencies": []
    }
  ]
}
```

`run-summary.json`（节选）：

```json
{
  "version": "1",
  "run_id": "20260116_144427_c872c4",
  "fast_path": true,
  "timing": { "total_ms": 4, "stages": { "scan_ms": 0, "parse_ms": 1 } },
  "io": { "scanned_files": 12, "skipped": { "non_md": 0, "too_large": 0, "no_permission": 0 } },
  "cache": { "present": false, "hit_rate": 0.0, "incremental_updated": 0 },
  "apply": { "waited_sec": 0, "starvation": false, "fallback": "none", "offline_lock": false },
  "downgrades": []
}
```

### 设计约束

- 不引入 LLM
- 不写入 vault（默认只读）
- 输出 schema 带 `version` 字段

## 快速开始

### 运行（不安装）

Windows PowerShell：

```powershell
$env:PYTHONPATH = "$(Get-Location)\src"
python -m oka run --vault <path-to-vault>
```

macOS/Linux：

```bash
PYTHONPATH=src python -m oka run --vault <path-to-vault>
```

### 安装（可选）

```bash
python -m pip install -e .
oka run --vault <path-to-vault>
```

### Doctor

```bash
python -m oka doctor --vault <path-to-vault>
python -m oka doctor --init-config --vault <path-to-vault>
```

### JSON 输出

```bash
python -m oka run --vault <path-to-vault> --json
```

### Apply 与回滚

```bash
python -m oka run --vault <path-to-vault> --apply
python -m oka run --vault <path-to-vault> --apply --yes
python -m oka rollback <run_id>
python -m oka rollback <run_id> --item <action_id>
python -m oka rollback <run_id> --file <path>
```

### Watch

```bash
python -m oka watch --vault <path-to-vault>
python -m oka watch --vault <path-to-vault> --once
```

## 输出与目录契约

```
reports/
  health.json
  action-items.json
  run-summary.json
  report.md
  runs/
    <run_id>/
      run-log.json
      patches/
      backups/
      conflicts/
        HOWTO.txt
cache/
  index.sqlite
locks/
  write-lease.json
  offline-lock.json
```

可选 marker（写入 vault 根目录）：

- `.nosync`（或自定义 marker，见 `apply.offline_lock_marker`）

## 配置

使用 `oka doctor --init-config` 生成 `oka.toml`，规则如下：

- 传入 `--vault` 时写入 vault 根目录
- 否则写入当前工作目录
- 若已存在则不会覆盖

示例（节选）：

```toml
[profile]
name = "conservative"

[scan]
max_file_mb = 5
max_files_per_sec = 0
sleep_ms = 0
exclude_dirs = [".obsidian"]

[apply]
max_wait_sec = 30
offline_lock_marker = ".nosync"
offline_lock_cleanup = true

[performance]
fast_path_max_age_sec = 10

[storage]
max_run_logs = 50
max_run_days = 30
max_total_mb = 200
compress_runs = false
auto_prune = true

[scoring]
model = "quantile"
w_content = 0.6
w_title = 0.3
w_link = 0.1

[filters]
path_penalty = 0.9
```

## 使用示例

```bash
python -m oka run --vault <path-to-vault>
python -m oka run --vault <path-to-vault> --json
python -m oka doctor --vault <path-to-vault>
```

## 项目结构

```
obsidian-assistant/
├── src/oka/
│   ├── cli/              # CLI 入口
│   └── core/             # pipeline/scoring/doctor
├── tests/
│   └── fixtures/
├── docs/
└── README.md
```

## 测试

```bash
pytest -q
```

## 文档

- [开发基线](docs/development.md)
- [安装指南](docs/installation.md)
- [示例](docs/examples.md)

## 旧版工具（Legacy）

项目仍保留旧版脚本入口（`src/main.py`, `src/quality.py`, `src/search.py`, `src/similar.py`），但新功能以 `oka` 为主。

## 贡献指南

我们欢迎各种形式的贡献！

### 如何贡献

1. Fork 本项目
2. 创建你的特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交你的更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启一个 Pull Request

### 开发设置

```bash
# 克隆你的 fork
git clone https://github.com/yourusername/obsidian-assistant.git

# 创建虚拟环境（可选）
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 运行测试
pytest -q
```

## 更新日志

查看 [CHANGELOG.md](CHANGELOG.md) 了解版本历史和更新内容。

## 问题反馈

如果你遇到问题或有功能建议，请：

1. 搜索 [已有 Issues](https://github.com/yourusername/obsidian-assistant/issues)
2. 创建新的 Issue 并提供详细信息

## 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 致谢

- 感谢 [Obsidian](https://obsidian.md/) 提供优秀的知识管理工具
- 感谢所有贡献者的付出

## Star History

如果这个项目对你有帮助，请给一个 Star！

---

<div align="center">

**[回到顶部](#obsidian-assistant)**

Made with care for better knowledge management

</div>
