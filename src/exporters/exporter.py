#!/usr/bin/env python3
"""
Obsidian Knowledge Assistant - Data Exporter
导出分析结果为 JSON 和 CSV 格式
"""

import json
import csv
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List
import sys
from pathlib import Path

# 添加父目录到路径以导入 core 模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.analyzer import Note


class DataExporter:
    """数据导出器"""

    def __init__(self, stats: Dict, notes: Dict[str, Note], vault_path: str):
        self.stats = stats
        self.notes = notes
        self.vault_path = vault_path

    def export_json(self, output_dir: str) -> Path:
        """导出为 JSON 格式"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # 构建 JSON 数据
        json_data = {
            "meta": {
                "generated_at": datetime.now().isoformat(),
                "vault_path": self.vault_path,
                "total_notes": self.stats["total_notes"],
                "total_words": self.stats["total_words"],
                "total_links": self.stats["total_links"],
            },
            "statistics": {
                "overview": {
                    "total_notes": self.stats["total_notes"],
                    "total_words": self.stats["total_words"],
                    "avg_word_count": self.stats["avg_word_count"],
                    "total_links": self.stats["total_links"],
                    "bidirectional_links": self.stats["bidirectional_links"],
                    "avg_links_per_note": self.stats["avg_links_per_note"],
                    "unique_tags": len(self.stats["tag_counter"]),
                },
                "orphan_notes": {
                    "count": len(self.stats["orphan_notes"]),
                    "notes": [
                        {
                            "name": note.name,
                            "word_count": note.word_count,
                            "modified_time": note.modified_time.isoformat(),
                            "path": str(note.path),
                        }
                        for note in self.stats["orphan_notes"]
                    ],
                },
                "top_notes": {
                    "most_outgoing": [
                        {
                            "name": note.name,
                            "outgoing_links": len(note.outgoing_links),
                            "incoming_links": len(note.incoming_links),
                            "word_count": note.word_count,
                        }
                        for note in self.stats["most_outgoing"][:20]
                    ],
                    "most_incoming": [
                        {
                            "name": note.name,
                            "incoming_links": len(note.incoming_links),
                            "outgoing_links": len(note.outgoing_links),
                            "word_count": note.word_count,
                        }
                        for note in self.stats["most_incoming"][:20]
                    ],
                },
                "tags": {
                    "total_unique": len(self.stats["tag_counter"]),
                    "untagged_count": len(self.stats["untagged_notes"]),
                    "top_tags": [
                        {"tag": tag, "count": count}
                        for tag, count in self.stats["tag_counter"].most_common(50)
                    ],
                },
                "time_distribution": self.stats["recent_counts"],
            },
            "all_notes": [
                {
                    "name": note.name,
                    "word_count": note.word_count,
                    "outgoing_links": len(note.outgoing_links),
                    "incoming_links": len(note.incoming_links),
                    "tags": list(note.tags),
                    "is_orphan": note.is_orphan,
                    "created_time": note.created_time.isoformat(),
                    "modified_time": note.modified_time.isoformat(),
                    "path": str(note.path),
                }
                for note in self.notes.values()
            ],
        }

        # 保存 JSON 文件
        filename = datetime.now().strftime("analysis-data-%Y-%m-%d.json")
        filepath = output_path / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)

        return filepath

    def export_csv_notes(self, output_dir: str) -> Path:
        """导出笔记列表为 CSV"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        filename = datetime.now().strftime("notes-%Y-%m-%d.csv")
        filepath = output_path / filename

        with open(filepath, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)

            # 写入表头
            writer.writerow(
                [
                    "Note Name",
                    "Word Count",
                    "Outgoing Links",
                    "Incoming Links",
                    "Total Links",
                    "Tags",
                    "Is Orphan",
                    "Created Date",
                    "Modified Date",
                    "Path",
                ]
            )

            # 写入数据
            for note in sorted(self.notes.values(), key=lambda x: x.name):
                writer.writerow(
                    [
                        note.name,
                        note.word_count,
                        len(note.outgoing_links),
                        len(note.incoming_links),
                        note.total_links,
                        ", ".join(sorted(note.tags)),
                        "Yes" if note.is_orphan else "No",
                        note.created_time.strftime("%Y-%m-%d %H:%M:%S"),
                        note.modified_time.strftime("%Y-%m-%d %H:%M:%S"),
                        str(note.path),
                    ]
                )

        return filepath

    def export_csv_orphans(self, output_dir: str) -> Path:
        """导出孤岛笔记为 CSV"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        filename = datetime.now().strftime("orphan-notes-%Y-%m-%d.csv")
        filepath = output_path / filename

        with open(filepath, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)

            writer.writerow(
                ["Note Name", "Word Count", "Tags", "Modified Date", "Path"]
            )

            for note in self.stats["orphan_notes"]:
                writer.writerow(
                    [
                        note.name,
                        note.word_count,
                        ", ".join(sorted(note.tags)),
                        note.modified_time.strftime("%Y-%m-%d %H:%M:%S"),
                        str(note.path),
                    ]
                )

        return filepath

    def export_csv_tags(self, output_dir: str) -> Path:
        """导出标签统计为 CSV"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        filename = datetime.now().strftime("tags-%Y-%m-%d.csv")
        filepath = output_path / filename

        with open(filepath, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)

            writer.writerow(["Tag", "Count", "Percentage"])

            total_notes = self.stats["total_notes"]
            for tag, count in self.stats["tag_counter"].most_common():
                percentage = (count / total_notes * 100) if total_notes > 0 else 0
                writer.writerow([tag, count, f"{percentage:.1f}%"])

        return filepath

    def export_csv_links(self, output_dir: str) -> Path:
        """导出链接关系为 CSV"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        filename = datetime.now().strftime("links-%Y-%m-%d.csv")
        filepath = output_path / filename

        with open(filepath, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)

            writer.writerow(["Source Note", "Target Note", "Link Type"])

            # 记录所有链接关系
            for note_name, note in self.notes.items():
                for target in note.outgoing_links:
                    if target in self.notes:
                        # 检查是否是双向链接
                        is_bidirectional = (
                            note_name in self.notes[target].outgoing_links
                        )
                        link_type = (
                            "Bidirectional" if is_bidirectional else "Unidirectional"
                        )
                        writer.writerow([note_name, target, link_type])

        return filepath

    def export_all(self, output_dir: str) -> Dict[str, Path]:
        """导出所有格式"""
        exported_files = {}

        # 检查配置
        export_json = os.getenv("EXPORT_JSON", "true").lower() == "true"
        export_csv = os.getenv("EXPORT_CSV", "true").lower() == "true"
        csv_types = os.getenv("CSV_EXPORT_TYPES", "notes,orphans,tags").split(",")

        # 导出 JSON
        if export_json:
            json_path = self.export_json(output_dir)
            exported_files["json"] = json_path
            print(f"  📄 JSON exported: {json_path}")

        # 导出 CSV
        if export_csv:
            csv_files = []

            if "notes" in csv_types:
                notes_csv = self.export_csv_notes(output_dir)
                csv_files.append(notes_csv)
                print(f"  📊 Notes CSV exported: {notes_csv}")

            if "orphans" in csv_types:
                orphans_csv = self.export_csv_orphans(output_dir)
                csv_files.append(orphans_csv)
                print(f"  📊 Orphans CSV exported: {orphans_csv}")

            if "tags" in csv_types:
                tags_csv = self.export_csv_tags(output_dir)
                csv_files.append(tags_csv)
                print(f"  📊 Tags CSV exported: {tags_csv}")

            if "links" in csv_types:
                links_csv = self.export_csv_links(output_dir)
                csv_files.append(links_csv)
                print(f"  📊 Links CSV exported: {links_csv}")

            exported_files["csv"] = csv_files

        return exported_files


if __name__ == "__main__":
    print("This module should be imported, not run directly.")
