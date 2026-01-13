# Obsidian Knowledge Assistant

<div align="center">

![Python](https://img.shields.io/badge/python-3.7+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)

**智能分析你的 Obsidian 知识库，提供深度洞察和改进建议**

[功能特性](#功能特性) • [快速开始](#快速开始) • [文档](#文档) • [贡献指南](#贡献指南)

</div>

---

## 📖 简介

Obsidian Knowledge Assistant 是一个强大的命令行工具，用于分析和优化你的 Obsidian 知识库。它提供全面的统计分析、质量评分、相似度检测等功能，帮助你：

- 🔍 发现孤岛笔记和缺失链接
- 📊 评估笔记质量并获得改进建议
- 🔗 识别内容相似的笔记
- 💾 导出数据用于进一步分析
- 📈 追踪知识库的健康度变化

## ✨ 功能特性

### 核心功能
- **📊 全面统计** - 笔记数量、字数、链接、标签等详细统计
- **🏝️ 孤岛检测** - 识别没有任何链接的孤立笔记
- **🔗 连接分析** - 发现知识枢纽和核心概念
- **🏷️ 标签统计** - 最常用标签和无标签笔记分析

### 高级功能
- **🎯 质量评分** - 基于字数、链接、标签、新鲜度的四维评分系统
- **🔍 相似度分析** - TF-IDF + 余弦相似度算法，找出内容相似的笔记
- **💾 数据导出** - 支持 JSON 和 CSV 格式导出
- **🗂️ 多 Vault 支持** - 同时分析多个知识库
- **🔎 强大搜索** - 按关键词、标签、链接数等条件搜索

## 🚀 快速开始

### 安装

```bash
# 克隆仓库
git clone https://github.com/yourusername/obsidian-knowledge-assistant.git
cd obsidian-knowledge-assistant

# 无需安装依赖（仅使用 Python 标准库）
```

### 配置

编辑 `config/set_env.sh` 设置你的 vault 路径：

```bash
export VAULT_PATH="/path/to/your/obsidian/vault"
```

### 运行

```bash
# 加载配置
source config/set_env.sh

# 生成完整分析报告
python src/main.py

# 查看质量评分
python src/quality.py score

# 查找相似笔记
python src/similar.py duplicates
```

## 📚 文档

- [安装指南](docs/installation.md)
- [使用教程](docs/usage.md)
- [功能详解](docs/features.md)
- [配置说明](docs/configuration.md)
- [API 文档](docs/api.md)

## 🎯 使用示例

### 生成知识库报告

```bash
python src/main.py
```

生成包含以下内容的 Markdown 报告：
- 总体概况统计
- 连接分析（知识枢纽、核心概念）
- 孤岛笔记列表
- 标签使用分析
- 质量评分报告

### 查找需要改进的笔记

```bash
# 查看质量最差的笔记
python src/quality.py worst --limit 10

# 查找可能重复的笔记
python src/similar.py duplicates --threshold 0.7

# 查找相关但未链接的笔记
python src/similar.py unlinked
```

### 搜索笔记

```bash
# 按关键词搜索
python src/search.py search "python"

# 按标签搜索
python src/search.py search --tags "编程,学习"

# 按链接数搜索
python src/search.py search --min-links 5
```

## 🎨 输出示例

### 知识库分析报告

```markdown
# 📊 Obsidian 知识库分析报告

**生成时间**: 2026-01-12 14:30:00
**知识库路径**: `/path/to/vault`

## 📈 总体概况
- **笔记总数**: 150 篇
- **总字数**: 45,678 字
- **总链接数**: 234 个
- **双向链接**: 45 对

## 🏝️ 孤岛笔记
发现 23 篇孤岛笔记...
```

### 质量评分报告

```
============================================================
  📊 质量统计
============================================================
  总笔记数:  150
  平均分:    72.5
  
  评级分布:
    A:  25 ( 16.7%) ████████
    B:  45 ( 30.0%) ███████████████
    C:  35 ( 23.3%) ███████████
```

## 🛠️ 项目结构

```
obsidian-knowledge-assistant/
├── src/                    # 源代码
│   ├── core/              # 核心模块
│   │   ├── analyzer.py    # 笔记分析器
│   │   ├── quality_scorer.py   # 质量评分
│   │   └── similarity.py  # 相似度分析
│   ├── exporters/         # 数据导出
│   │   ├── exporter.py    # 导出器基类
│   │   └── report_generator.py  # 报告生成
│   ├── main.py           # 主程序入口
│   ├── quality.py        # 质量评分工具
│   ├── search.py         # 搜索工具
│   └── similar.py        # 相似度分析工具
├── config/               # 配置文件
│   └── set_env.sh       # 环境配置
├── docs/                # 文档
│   ├── installation.md
│   ├── usage.md
│   ├── features.md
│   └── examples.md
├── tests/               # 测试文件
├── examples/            # 示例文件
├── .gitignore
├── LICENSE
├── README.md
└── requirements.txt
```

## ⚙️ 配置选项

所有配置都在 `config/set_env.sh` 中：

```bash
# Vault 配置
export VAULT_PATH="/path/to/vault"
export MULTI_VAULT_PATHS=""  # 多 vault 支持

# 排除配置
export EXCLUDE_FOLDERS=".obsidian,.trash,templates"
export EXCLUDE_NOTES=""  # 支持通配符

# 质量评分配置
export SCORE_WEIGHT_WORDS="0.25"
export SCORE_WEIGHT_LINKS="0.35"
export QUALITY_MIN_WORDS="100"

# 相似度配置
export SIMILARITY_MIN_THRESHOLD="0.3"
```

## 🤝 贡献指南

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
git clone https://github.com/yourusername/obsidian-knowledge-assistant.git

# 创建虚拟环境（可选）
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 运行测试
python -m pytest tests/
```

## 📝 更新日志

查看 [CHANGELOG.md](CHANGELOG.md) 了解版本历史和更新内容。

## 🐛 问题反馈

如果你遇到问题或有功能建议，请：

1. 查看 [常见问题](docs/faq.md)
2. 搜索 [已有 Issues](https://github.com/yourusername/obsidian-knowledge-assistant/issues)
3. 创建新的 Issue 并提供详细信息

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🙏 致谢

- 感谢 [Obsidian](https://obsidian.md/) 提供优秀的知识管理工具
- 感谢所有贡献者的付出

## 🌟 Star History

如果这个项目对你有帮助，请给一个 ⭐️！

---

<div align="center">

**[⬆ 回到顶部](#obsidian-knowledge-assistant)**

Made with ❤️ for better knowledge management

</div>
