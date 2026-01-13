# 新功能使用示例

本文档展示如何使用 Obsidian Knowledge Assistant 的新功能。

## 1. 多 Vault 分析

### 配置方式 1：使用环境变量

编辑 `set_env.sh`：

```bash
export MULTI_VAULT_PATHS="F:/Project/Obsidian,F:/Work/Notes,D:/Personal"
```

然后运行：

```bash
source set_env.sh
python main.py
```

### 配置方式 2：使用命令行参数

```bash
python main.py --multi-vault "F:/Project/Obsidian,F:/Work/Notes,D:/Personal"
```

### 输出示例

```
============================================================
  Obsidian Knowledge Assistant - Multi-Vault Mode
============================================================

📂 Vault: Obsidian
🔍 Scanning vault: F:/Project/Obsidian
📝 Found 150 markdown files
✅ Analysis complete: 150 notes processed

📂 Vault: Notes
🔍 Scanning vault: F:/Work/Notes
📝 Found 89 markdown files
✅ Analysis complete: 89 notes processed

📂 Vault: Personal
🔍 Scanning vault: D:/Personal
📝 Found 45 markdown files
✅ Analysis complete: 45 notes processed

============================================================
  📊 Combined Statistics
============================================================
  Total vaults:     3
  Total notes:      284
  Total words:      45,678
  Total orphans:    23
  Total links:      567
  Unique tags:      89
============================================================

📂 Breakdown by vault:
  • Obsidian:
    Notes: 150 | Words: 25,000 | Orphans: 12
  • Notes:
    Notes: 89 | Words: 15,000 | Orphans: 8
  • Personal:
    Notes: 45 | Words: 5,678 | Orphans: 3
```

每个 vault 会生成独立的报告在：
- `reports/Obsidian/knowledge-report-2025-01-12.md`
- `reports/Notes/knowledge-report-2025-01-12.md`
- `reports/Personal/knowledge-report-2025-01-12.md`

---

## 2. 排除特定笔记

### 使用场景

- 排除草稿笔记
- 排除临时笔记
- 排除模板文件
- 排除特定项目的笔记

### 配置方式

编辑 `set_env.sh`：

```bash
# 排除文件夹
export EXCLUDE_FOLDERS=".obsidian,.trash,templates,drafts"

# 排除特定笔记（支持通配符）
export EXCLUDE_NOTES="草稿*,临时*,README,TODO"
```

### 通配符示例

```bash
# 排除所有以"草稿"开头的笔记
export EXCLUDE_NOTES="草稿*"

# 排除多个模式
export EXCLUDE_NOTES="草稿*,临时*,test-*"

# 精确匹配
export EXCLUDE_NOTES="README,TODO,CHANGELOG"
```

---

## 3. 数据导出功能

### JSON 导出

配置：

```bash
export EXPORT_JSON="true"
```

生成文件：`reports/analysis-data-2025-01-12.json`

JSON 结构：

```json
{
  "meta": {
    "generated_at": "2025-01-12T10:30:00",
    "vault_path": "F:/Project/Obsidian",
    "total_notes": 150
  },
  "statistics": {
    "overview": { ... },
    "orphan_notes": [ ... ],
    "top_notes": { ... },
    "tags": { ... }
  },
  "all_notes": [
    {
      "name": "Python 编程",
      "word_count": 1234,
      "outgoing_links": 5,
      "incoming_links": 3,
      "tags": ["python", "编程"],
      "is_orphan": false,
      "created_time": "2025-01-01T00:00:00",
      "modified_time": "2025-01-10T15:30:00",
      "path": "F:/Project/Obsidian/Python 编程.md"
    }
  ]
}
```

### CSV 导出

配置：

```bash
export EXPORT_CSV="true"
export CSV_EXPORT_TYPES="notes,orphans,tags,links"
```

生成的文件：

1. **notes-2025-01-12.csv** - 所有笔记
```csv
Note Name,Word Count,Outgoing Links,Incoming Links,Total Links,Tags,Is Orphan,Created Date,Modified Date,Path
Python 编程,1234,5,3,8,"python, 编程",No,2025-01-01 00:00:00,2025-01-10 15:30:00,F:/Project/Obsidian/Python 编程.md
```

2. **orphan-notes-2025-01-12.csv** - 孤岛笔记
```csv
Note Name,Word Count,Tags,Modified Date,Path
随机想法,45,"",2025-01-12 10:00:00,F:/Project/Obsidian/随机想法.md
```

3. **tags-2025-01-12.csv** - 标签统计
```csv
Tag,Count,Percentage
python,25,16.7%
编程,20,13.3%
学习,15,10.0%
```

4. **links-2025-01-12.csv** - 链接关系
```csv
Source Note,Target Note,Link Type
Python 编程,Python 函数,Bidirectional
Python 编程,Python 装饰器,Unidirectional
```

### 只导出特定类型

```bash
# 只导出笔记列表和标签
export CSV_EXPORT_TYPES="notes,tags"

# 只导出孤岛笔记
export CSV_EXPORT_TYPES="orphans"
```

---

## 4. 搜索功能

### 基本搜索

```bash
# 搜索包含 "python" 的笔记（在名称或内容中）
python search.py search "python"
```

输出：

```
🔍 Scanning vault: F:/Project/Obsidian
📝 Found 150 markdown files
✅ Analysis complete: 150 notes processed

🔍 Search Results (keyword 'python')
  Found 8 note(s):

  1. Python 编程索引
     Words: 234 | Links: 10 (↗8 ↘2)
     Tags: python, 编程, 学习索引
     Modified: 2025-01-10 15:30

  2. Python 装饰器
     Words: 456 | Links: 3 (↗1 ↘2)
     Tags: python, 装饰器, 进阶
     Modified: 2025-01-09 14:20
```

### 按标签搜索

```bash
# 搜索同时包含多个标签的笔记
python search.py search --tags "python,进阶"
```

### 按链接数搜索

```bash
# 找出链接数在 5-20 之间的笔记
python search.py search --min-links 5 --max-links 20

# 找出链接特别多的笔记（可能是重要索引）
python search.py search --min-links 10
```

### 组合搜索

```bash
# 找出关于 Python 且至少有 3 个链接的笔记
python search.py search "python" --min-links 3

# 找出带有特定标签且链接丰富的笔记
python search.py search --tags "项目" --min-links 5
```

### 列出孤岛笔记

```bash
python search.py orphans --limit 20
```

### 列出知识枢纽

```bash
# 列出出链最多的 10 个笔记
python search.py hubs --limit 10
```

### 列出热门笔记

```bash
# 列出入链最多的 10 个笔记
python search.py popular --limit 10
```

### 显示统计信息

```bash
python search.py stats
```

---

## 5. 实际工作流示例

### 工作流 1：每周知识库体检

```bash
#!/bin/bash
# weekly_check.sh

source set_env.sh

echo "=== 每周知识库体检 ==="
echo ""

# 1. 生成完整报告
echo "📊 生成分析报告..."
python main.py --export

# 2. 检查孤岛笔记
echo ""
echo "🏝️ 孤岛笔记（需要整合）："
python search.py orphans --limit 10

# 3. 查看知识枢纽
echo ""
echo "🌐 知识枢纽（需要维护）："
python search.py hubs --limit 5

echo ""
echo "✅ 体检完成！请查看 reports/ 目录"
```

### 工作流 2：查找和整理特定主题

```bash
#!/bin/bash
# organize_topic.sh

TOPIC=$1

if [ -z "$TOPIC" ]; then
    echo "Usage: ./organize_topic.sh <topic>"
    exit 1
fi

source set_env.sh

echo "=== 整理主题: $TOPIC ==="
echo ""

# 1. 搜索相关笔记
echo "📝 相关笔记："
python search.py search "$TOPIC"

# 2. 找出该主题的孤岛笔记
echo ""
echo "🏝️ 孤岛笔记（可以链接到主题索引）："
python search.py search "$TOPIC" --max-links 0

echo ""
echo "💡 建议："
echo "   1. 为这些孤岛笔记添加链接"
echo "   2. 考虑创建一个 '$TOPIC 索引' 笔记"
echo "   3. 统一使用标签: #$TOPIC"
```

### 工作流 3：多项目管理

```bash
#!/bin/bash
# analyze_all_projects.sh

source set_env.sh

echo "=== 分析所有项目 ==="
echo ""

# 分析所有 vaults
python main.py --multi-vault "F:/Work/ProjectA,F:/Work/ProjectB,F:/Personal"

echo ""
echo "📊 项目对比："
echo ""

# 对每个项目运行统计
for vault in "F:/Work/ProjectA" "F:/Work/ProjectB" "F:/Personal"; do
    echo "📂 $(basename $vault):"
    python search.py stats --vault "$vault" | grep "Total"
    echo ""
done
```

---

## 6. 使用 CSV 数据做进一步分析

### 在 Excel 中使用

1. 打开 `notes-YYYY-MM-DD.csv`
2. 创建数据透视表
3. 分析：
   - 哪些月份笔记最多？
   - 哪些标签组合最常见？
   - 字数和链接数的关系？

### 在 Python 中使用

```python
import pandas as pd

# 读取数据
notes = pd.read_csv('reports/notes-2025-01-12.csv')

# 分析字数分布
print(notes['Word Count'].describe())

# 找出最活跃的标签组合
tag_combos = notes['Tags'].value_counts().head(10)
print(tag_combos)

# 分析链接和字数的关系
import matplotlib.pyplot as plt
plt.scatter(notes['Total Links'], notes['Word Count'])
plt.xlabel('Total Links')
plt.ylabel('Word Count')
plt.title('Links vs Word Count')
plt.show()
```

### 使用 JSON 数据

```python
import json

with open('reports/analysis-data-2025-01-12.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 获取所有孤岛笔记
orphans = data['statistics']['orphan_notes']['notes']
print(f"发现 {len(orphans)} 个孤岛笔记")

# 分析标签使用
top_tags = data['statistics']['tags']['top_tags'][:10]
for tag_info in top_tags:
    print(f"{tag_info['tag']}: {tag_info['count']} 次")
```

---

## 7. 高级配置示例

### 完整的 set_env.sh 配置

```bash
#!/bin/bash

# === 多 Vault 配置 ===
# 同时分析工作和个人笔记
export MULTI_VAULT_PATHS="F:/Work/Notes,D:/Personal/Obsidian,E:/Archive"

# === 排除配置 ===
# 排除文件夹
export EXCLUDE_FOLDERS=".obsidian,.trash,templates,drafts,archive"

# 排除特定笔记
export EXCLUDE_NOTES="草稿*,临时*,test-*,README,TODO,CHANGELOG"

# === 导出配置 ===
# 导出所有格式
export EXPORT_JSON="true"
export EXPORT_CSV="true"
export CSV_EXPORT_TYPES="notes,orphans,tags,links"

# === 显示配置 ===
# 显示更多孤岛笔记
export ORPHAN_DISPLAY_COUNT="50"

# 显示更多 Top 笔记
export TOP_NOTES_COUNT="20"

# === 报告配置 ===
# 自定义报告文件名
export REPORT_FILENAME_FORMAT="weekly-report-%Y-W%W.md"

# === 分析参数 ===
# 低于 50 字视为"空笔记"
export MIN_WORD_COUNT="50"

echo "✅ 高级配置已加载"
echo "   Vaults: $(echo $MULTI_VAULT_PATHS | tr ',' '\n' | wc -l)"
echo "   排除文件夹: $EXCLUDE_FOLDERS"
echo "   排除笔记模式: $EXCLUDE_NOTES"
```

---

## 8. 笔记质量评分

### 评分系统说明

质量评分从四个维度评估笔记：

1. **字数（25%权重）**
   - 少于100字：内容太少
   - 100-500字：逐步提高
   - 500字以上：满分

2. **链接（35%权重）**
   - 0个链接：孤岛笔记，0分
   - 少于2个：链接太少
   - 2-5个：逐步提高
   - 5个以上：满分

3. **标签（15%权重）**
   - 0个标签：0分
   - 少于1个：标签太少
   - 1-3个：逐步提高
   - 3个以上：满分

4. **新鲜度（25%权重）**
   - 7天内：100分
   - 30天内：90分
   - 90天内：70分
   - 180天内：50分
   - 更久：30分

**评级标准**：
- A: 90-100分（优秀）
- B: 80-89分（良好）
- C: 70-79分（中等）
- D: 60-69分（及格）
- F: <60分（不及格）

### 基本使用

```bash
# 评分所有笔记（显示概览）
python quality.py score
```

输出示例：

```
============================================================
  📊 质量统计
============================================================
  总笔记数:  150
  平均分:    72.5
  中位数:    75.0
  最高分:    98.5
  最低分:    15.0

  评级分布:
    A:  25 ( 16.7%) ████████
    B:  45 ( 30.0%) ███████████████
    C:  35 ( 23.3%) ███████████
    D:  20 ( 13.3%) ██████
    F:  25 ( 16.7%) ████████
============================================================

⭐ 优质笔记 (Top 5)
1. Python 编程完全指南 - 98.5分 (A)
   字数:100  链接:95  标签:100  新鲜:100
...

⚠️  需要改进的笔记 (Top 5)
1. 临时想法 - 15.0分 (F)
   ❌ 内容太少（仅 10 字）
   ❌ 没有任何链接（孤岛笔记）
...
```

### 查看详细统计

```bash
python quality.py stats
```

### 列出所有笔记按分数排序

```bash
# 从高到低（默认）
python quality.py list --limit 20

# 从低到高
python quality.py list --ascending --limit 20

# 只显示 A 级笔记
python quality.py list --grade A

# 只显示不及格笔记
python quality.py list --grade F
```

### 查看最差的笔记

```bash
python quality.py worst --limit 10
```

输出示例：

```
============================================================
  ⚠️  需要改进的笔记 (Top 10)
============================================================

1. 临时想法 - 15.0分 (F)
   ❌ 内容太少（仅 10 字）
   ❌ 没有任何链接（孤岛笔记）

2. 草稿笔记 - 25.5分 (F)
   ❌ 内容太少（仅 45 字）
   ❌ 链接太少（仅 1 个）
...
```

### 查看最好的笔记

```bash
python quality.py best --limit 10
```

### 检查特定笔记

```bash
python quality.py check "Python 编程"
```

输出示例：

```
============================================================
  📝 Python 编程
============================================================
  总分: 85.5/100 (评级: B)

  各维度得分:
    字数:    90.0/100
    链接:    85.0/100
    标签:   100.0/100
    新鲜度:  70.0/100

  💡 改进建议:
    • 可以继续扩展内容（目标 500 字）
    • 考虑添加更多相关链接
    • 已 95 天未更新，考虑复习

============================================================
```

### 自定义评分标准

在 `set_env.sh` 中调整：

```bash
# 调整权重（总和应为 1.0）
export SCORE_WEIGHT_WORDS="0.30"      # 更重视内容
export SCORE_WEIGHT_LINKS="0.40"      # 最重视链接
export SCORE_WEIGHT_TAGS="0.10"       # 降低标签权重
export SCORE_WEIGHT_FRESHNESS="0.20"  # 降低新鲜度权重

# 调整标准（适应你的写作习惯）
export QUALITY_MIN_WORDS="200"        # 提高最小字数要求
export QUALITY_IDEAL_WORDS="800"      # 提高理想字数
export QUALITY_MIN_LINKS="3"          # 提高最小链接数
export QUALITY_IDEAL_LINKS="8"        # 提高理想链接数
export QUALITY_FRESHNESS_DAYS="180"   # 放宽新鲜度要求
```

### 质量报告

运行 `python main.py` 会自动生成质量报告：

```
reports/quality-report-2025-01-12.md
```

报告包含：
- 总体评分统计
- 评级分布图
- 优质笔记列表（≥90分）
- 需要改进的笔记详细分析（<70分）
  - 列出每个问题
  - 给出具体改进建议
  - 显示各维度得分
- 整体改进建议

---

## 9. 质量评分工作流示例

### 工作流 1：每日质量检查

```bash
#!/bin/bash
# daily_quality_check.sh

source set_env.sh

echo "=== 每日质量检查 ==="
echo ""

# 1. 显示昨天创建/修改的笔记质量
echo "📊 最新笔记质量："
python quality.py list --limit 5

# 2. 检查是否有新的低分笔记
echo ""
echo "⚠️  需要关注的笔记："
python quality.py worst --limit 3

echo ""
echo "💡 建议：优先改进低分笔记"
```

### 工作流 2：周末深度整理

```bash
#!/bin/bash
# weekend_cleanup.sh

source set_env.sh

echo "=== 周末深度整理 ==="
echo ""

# 1. 生成完整报告
echo "📊 生成完整报告..."
python main.py --export

# 2. 找出所有不及格笔记
echo ""
echo "❌ 不及格笔记列表："
python quality.py list --grade F > cleanup_list.txt

# 3. 找出长时间未更新的笔记
echo ""
echo "📅 长期未更新的笔记："
python search.py search --max-links 1 | grep "Modified" | sort

echo ""
echo "✅ 清理列表已保存到 cleanup_list.txt"
echo "💡 建议：逐个检查这些笔记，决定是完善、合并还是删除"
```

### 工作流 3：提升笔记质量

```bash
#!/bin/bash
# improve_note.sh

NOTE_NAME=$1

if [ -z "$NOTE_NAME" ]; then
    echo "Usage: ./improve_note.sh <note_name>"
    exit 1
fi

source set_env.sh

echo "=== 改进笔记: $NOTE_NAME ==="
echo ""

# 1. 查看当前评分
echo "📊 当前评分："
python quality.py check "$NOTE_NAME"

# 2. 找相似主题的优质笔记作为参考
echo ""
echo "⭐ 参考优质笔记："
python quality.py best --limit 3

# 3. 搜索相关笔记可以添加链接
echo ""
echo "🔗 可以链接的相关笔记："
python search.py search "$NOTE_NAME"

echo ""
echo "💡 改进建议："
echo "   1. 扩充内容到至少 100 字"
echo "   2. 添加 2-5 个相关链接"
echo "   3. 添加合适的标签"
echo "   4. 完成后重新评分查看提升"
```

### 工作流 4：追踪改进进度

创建一个脚本定期记录平均分：

```bash
#!/bin/bash
# track_progress.sh

source set_env.sh

DATE=$(date +%Y-%m-%d)
STATS=$(python quality.py stats | grep "平均分")

echo "$DATE: $STATS" >> quality_progress.log

# 显示最近7天的趋势
echo "=== 质量趋势（最近7天）==="
tail -7 quality_progress.log
```

---

## 9. 常见问题

### Q: 如何只导出 JSON 不导出 CSV？

```bash
export EXPORT_JSON="true"
export EXPORT_CSV="false"
```

### Q: 搜索功能支持正则表达式吗？

当前版本支持简单的关键词搜索。正则表达式支持在未来版本中添加。

### Q: 可以搜索笔记的创建时间吗？

当前版本不支持按时间搜索，但你可以：
1. 导出 CSV
2. 在 Excel 中按 Created Date 列过滤

### Q: 多 vault 模式下，搜索会查询所有 vault 吗？

搜索工具目前只支持单个 vault。如果要搜索多个 vault，需要分别指定：

```bash
python search.py search "keyword" --vault "F:/Vault1"
python search.py search "keyword" --vault "F:/Vault2"
```

### Q: 导出的文件太大怎么办？

可以只导出需要的 CSV 类型：

```bash
# 只导出孤岛笔记
export CSV_EXPORT_TYPES="orphans"

# 或只导出标签统计
export CSV_EXPORT_TYPES="tags"
```

---

## 总结

新增的五个功能让你可以：

1. ✅ **导出数据** - 在其他工具中做进一步分析
2. ✅ **管理多个 vault** - 统一管理工作和个人笔记
3. ✅ **排除不需要的笔记** - 更精确的分析
4. ✅ **快速搜索** - 不用打开 Obsidian 也能找到笔记
5. ✅ **质量评分** - 自动识别需要改进的笔记，提供具体建议

这些功能组合使用，可以打造出适合你的知识管理工作流！
