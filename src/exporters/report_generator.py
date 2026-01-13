#!/usr/bin/env python3
"""
Obsidian Knowledge Assistant - Report Generator
生成 Markdown 格式的分析报告
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Dict


class ReportGenerator:
    """报告生成器"""
    
    def __init__(self, stats: Dict, vault_path: str):
        self.stats = stats
        self.vault_path = vault_path
        self.report_lines = []
    
    def generate(self) -> str:
        """生成完整报告"""
        self._add_header()
        self._add_overview()
        self._add_connection_analysis()
        self._add_orphan_notes()
        self._add_tag_analysis()
        self._add_time_distribution()
        self._add_footer()
        
        return '\n'.join(self.report_lines)
    
    def _add_header(self):
        """添加报告头部"""
        now = datetime.now()
        self.report_lines.extend([
            f"# 📊 Obsidian 知识库分析报告",
            f"",
            f"**生成时间**: {now.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**知识库路径**: `{self.vault_path}`",
            f"",
            "---",
            ""
        ])
    
    def _add_overview(self):
        """添加总览部分"""
        stats = self.stats
        self.report_lines.extend([
            "## 📈 总体概况",
            "",
            f"- **笔记总数**: {stats['total_notes']} 篇",
            f"- **总字数**: {stats['total_words']:,} 字",
            f"- **平均每篇**: {stats['avg_word_count']} 字",
            f"- **总链接数**: {stats['total_links']} 个",
            f"- **双向链接**: {stats['bidirectional_links']} 对",
            f"- **平均每篇链接数**: {stats['avg_links_per_note']:.1f} 个",
            "",
            "---",
            ""
        ])
    
    def _add_connection_analysis(self):
        """添加连接分析"""
        stats = self.stats
        top_count = int(os.getenv('TOP_NOTES_COUNT', '10'))
        
        self.report_lines.extend([
            "## 🔗 连接分析",
            "",
            "### 📤 出链最多的笔记 (知识枢纽)",
            "",
            "这些笔记连接了大量其他笔记，可能是重要的索引或 MOC (Map of Content)。",
            ""
        ])
        
        for i, note in enumerate(stats['most_outgoing'][:top_count], 1):
            outgoing_count = len(note.outgoing_links)
            incoming_count = len(note.incoming_links)
            self.report_lines.append(
                f"{i}. **{note.name}** - {outgoing_count} 个出链, {incoming_count} 个入链"
            )
        
        self.report_lines.extend([
            "",
            "### 📥 入链最多的笔记 (重要概念)",
            "",
            "这些笔记被大量引用，可能是核心概念或常用参考。",
            ""
        ])
        
        for i, note in enumerate(stats['most_incoming'][:top_count], 1):
            incoming_count = len(note.incoming_links)
            outgoing_count = len(note.outgoing_links)
            self.report_lines.append(
                f"{i}. **{note.name}** - {incoming_count} 个入链, {outgoing_count} 个出链"
            )
        
        self.report_lines.extend([
            "",
            "---",
            ""
        ])
    
    def _add_orphan_notes(self):
        """添加孤岛笔记分析"""
        stats = self.stats
        orphan_notes = stats['orphan_notes']
        display_count = int(os.getenv('ORPHAN_DISPLAY_COUNT', '20'))
        
        self.report_lines.extend([
            "## 🏝️ 孤岛笔记",
            "",
            f"**发现 {len(orphan_notes)} 篇孤岛笔记** (没有任何链接关系)",
            "",
            "⚠️ 这些笔记可能：",
            "- 是新创建还未整合的笔记",
            "- 是独立的想法碎片",
            "- 需要被链接到主知识体系中",
            "",
            f"### 最近修改的 {min(display_count, len(orphan_notes))} 篇孤岛笔记",
            ""
        ])
        
        for i, note in enumerate(orphan_notes[:display_count], 1):
            modified = note.modified_time.strftime('%Y-%m-%d')
            self.report_lines.append(
                f"{i}. **{note.name}** ({note.word_count} 字) - 最后修改: {modified}"
            )
        
        if len(orphan_notes) > display_count:
            self.report_lines.append(f"\n*...还有 {len(orphan_notes) - display_count} 篇孤岛笔记*")
        
        self.report_lines.extend([
            "",
            "---",
            ""
        ])
    
    def _add_tag_analysis(self):
        """添加标签分析"""
        stats = self.stats
        tag_counter = stats['tag_counter']
        untagged = stats['untagged_notes']
        top_count = int(os.getenv('TOP_TAGS_COUNT', '10'))
        
        self.report_lines.extend([
            "## 🏷️ 标签分析",
            "",
            f"- **不同标签数**: {len(tag_counter)} 个",
            f"- **无标签笔记**: {len(untagged)} 篇",
            "",
            f"### 最常用的 {min(top_count, len(tag_counter))} 个标签",
            ""
        ])
        
        for i, (tag, count) in enumerate(tag_counter.most_common(top_count), 1):
            percentage = (count / stats['total_notes']) * 100
            self.report_lines.append(
                f"{i}. `#{tag}` - {count} 次 ({percentage:.1f}%)"
            )
        
        self.report_lines.extend([
            "",
            "---",
            ""
        ])
    
    def _add_time_distribution(self):
        """添加时间分布"""
        stats = self.stats
        recent = stats['recent_counts']
        total = stats['total_notes']
        
        self.report_lines.extend([
            "## 📅 时间分布",
            "",
            "### 笔记活跃度",
            "",
            f"- **最近 7 天**: {recent['7_days']} 篇 ({recent['7_days']/total*100:.1f}%)",
            f"- **最近 30 天**: {recent['30_days']} 篇 ({recent['30_days']/total*100:.1f}%)",
            f"- **最近 90 天**: {recent['90_days']} 篇 ({recent['90_days']/total*100:.1f}%)",
            "",
            "---",
            ""
        ])
    
    def _add_footer(self):
        """添加报告尾部"""
        self.report_lines.extend([
            "## 💡 建议行动",
            "",
            "1. **处理孤岛笔记**: 查看上面列出的孤岛笔记，考虑：",
            "   - 是否可以链接到现有笔记？",
            "   - 是否需要扩展内容？",
            "   - 是否可以合并到其他笔记？",
            "",
            "2. **强化知识枢纽**: 维护那些出链最多的笔记，确保它们：",
            "   - 结构清晰",
            "   - 链接有效",
            "   - 持续更新",
            "",
            "3. **优化核心概念**: 完善那些入链最多的笔记，它们是你知识库的基石。",
            "",
            "4. **标签整理**: 考虑为无标签笔记添加合适的标签，提高可检索性。",
            "",
            "---",
            "",
            f"*由 Obsidian Knowledge Assistant 生成*"
        ])
    
    def save_report(self, output_dir: str) -> Path:
        """保存报告到文件"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 生成文件名
        filename_format = os.getenv('REPORT_FILENAME_FORMAT', 'knowledge-report-%Y-%m-%d.md')
        filename = datetime.now().strftime(filename_format)
        filepath = output_path / filename
        
        # 写入文件
        report_content = self.generate()
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        return filepath


if __name__ == '__main__':
    print("This module should be imported, not run directly.")
