#!/usr/bin/env python3
"""
Obsidian Knowledge Assistant - Core Analyzer
分析 Obsidian vault 的笔记结构和连接关系
"""

import os
import re
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import List, Dict, Set, Tuple


@dataclass
class Note:
    """笔记数据结构"""

    path: Path
    name: str
    content: str
    word_count: int
    outgoing_links: Set[str]  # 该笔记链接到的其他笔记
    incoming_links: Set[str]  # 链接到该笔记的其他笔记
    tags: Set[str]
    created_time: datetime
    modified_time: datetime

    @property
    def is_orphan(self) -> bool:
        """是否为孤岛笔记（没有任何链接关系）"""
        return len(self.outgoing_links) == 0 and len(self.incoming_links) == 0

    @property
    def total_links(self) -> int:
        """总链接数"""
        return len(self.outgoing_links) + len(self.incoming_links)


class ObsidianAnalyzer:
    """Obsidian vault 分析器"""

    def __init__(
        self,
        vault_path: str,
        exclude_folders: List[str] = None,
        exclude_notes: List[str] = None,
    ):
        self.vault_path = Path(vault_path)
        self.exclude_folders = exclude_folders or [".obsidian", ".trash"]
        self.exclude_notes = exclude_notes or []
        self.notes: Dict[str, Note] = {}
        self.link_pattern = re.compile(r"\[\[([^\]]+)\]\]")
        self.tag_pattern = re.compile(r"#([\w\-/]+)")

    def _should_exclude_note(self, note_name: str) -> bool:
        """检查笔记是否应该被排除"""
        for pattern in self.exclude_notes:
            # 简单的通配符支持
            if "*" in pattern:
                import fnmatch

                if fnmatch.fnmatch(note_name, pattern):
                    return True
            elif pattern == note_name:
                return True
        return False

    def scan_vault(self) -> None:
        """扫描整个 vault"""
        print(f"🔍 Scanning vault: {self.vault_path}")

        md_files = []
        for md_file in self.vault_path.rglob("*.md"):
            # 检查是否在排除目录中
            if any(excluded in md_file.parts for excluded in self.exclude_folders):
                continue

            # 检查是否是排除的笔记
            note_name = md_file.stem
            if self._should_exclude_note(note_name):
                continue

            md_files.append(md_file)

        print(f"📝 Found {len(md_files)} markdown files")

        # 第一遍：解析所有笔记
        for md_file in md_files:
            self._parse_note(md_file)

        # 第二遍：建立反向链接（incoming links）
        self._build_incoming_links()

        print(f"✅ Analysis complete: {len(self.notes)} notes processed")

    def _parse_note(self, file_path: Path) -> None:
        """解析单个笔记"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # 获取笔记名称（不含扩展名）
            note_name = file_path.stem

            # 提取链接
            outgoing_links = set()
            for match in self.link_pattern.finditer(content):
                link = match.group(1)
                # 处理别名 [[note|alias]]
                if "|" in link:
                    link = link.split("|")[0]
                # 处理标题链接 [[note#heading]]
                if "#" in link:
                    link = link.split("#")[0]
                outgoing_links.add(link.strip())

            # 提取标签
            tags = set(self.tag_pattern.findall(content))

            # 统计字数（简单统计，排除代码块）
            text_content = re.sub(r"```.*?```", "", content, flags=re.DOTALL)
            word_count = len(text_content.split())

            # 获取文件时间
            stat = file_path.stat()
            created_time = datetime.fromtimestamp(stat.st_ctime)
            modified_time = datetime.fromtimestamp(stat.st_mtime)

            # 创建 Note 对象
            note = Note(
                path=file_path,
                name=note_name,
                content=content,
                word_count=word_count,
                outgoing_links=outgoing_links,
                incoming_links=set(),  # 稍后填充
                tags=tags,
                created_time=created_time,
                modified_time=modified_time,
            )

            self.notes[note_name] = note

        except Exception as e:
            print(f"⚠️  Error parsing {file_path}: {e}")

    def _build_incoming_links(self) -> None:
        """建立反向链接关系"""
        for note_name, note in self.notes.items():
            for linked_note in note.outgoing_links:
                if linked_note in self.notes:
                    self.notes[linked_note].incoming_links.add(note_name)

    def get_statistics(self) -> Dict:
        """获取统计数据"""
        total_notes = len(self.notes)
        total_words = sum(note.word_count for note in self.notes.values())

        # 孤岛笔记
        orphan_notes = [note for note in self.notes.values() if note.is_orphan]
        orphan_notes.sort(key=lambda x: x.modified_time, reverse=True)

        # 链接最多的笔记（出链）
        most_outgoing = sorted(
            self.notes.values(), key=lambda x: len(x.outgoing_links), reverse=True
        )

        # 被链接最多的笔记（入链）
        most_incoming = sorted(
            self.notes.values(), key=lambda x: len(x.incoming_links), reverse=True
        )

        # 标签统计
        all_tags = []
        for note in self.notes.values():
            all_tags.extend(note.tags)
        tag_counter = Counter(all_tags)

        # 无标签笔记
        untagged_notes = [note for note in self.notes.values() if len(note.tags) == 0]

        # 时间分布
        now = datetime.now()
        recent_counts = {"7_days": 0, "30_days": 0, "90_days": 0}

        for note in self.notes.values():
            days_ago = (now - note.modified_time).days
            if days_ago <= 7:
                recent_counts["7_days"] += 1
            if days_ago <= 30:
                recent_counts["30_days"] += 1
            if days_ago <= 90:
                recent_counts["90_days"] += 1

        # 链接统计
        total_links = sum(len(note.outgoing_links) for note in self.notes.values())
        bidirectional_links = (
            sum(
                1
                for note in self.notes.values()
                for link in note.outgoing_links
                if link in self.notes and note.name in self.notes[link].outgoing_links
            )
            // 2
        )  # 除以2因为双向链接被计算了两次

        return {
            "total_notes": total_notes,
            "total_words": total_words,
            "orphan_notes": orphan_notes,
            "most_outgoing": most_outgoing,
            "most_incoming": most_incoming,
            "tag_counter": tag_counter,
            "untagged_notes": untagged_notes,
            "recent_counts": recent_counts,
            "total_links": total_links,
            "bidirectional_links": bidirectional_links,
            "avg_word_count": total_words // total_notes if total_notes > 0 else 0,
            "avg_links_per_note": total_links / total_notes if total_notes > 0 else 0,
        }

    def search_notes(
        self,
        query: str = None,
        tags: List[str] = None,
        min_links: int = None,
        max_links: int = None,
    ) -> List[Note]:
        """搜索笔记

        Args:
            query: 关键词搜索（在笔记名称和内容中搜索）
            tags: 标签列表（笔记必须包含所有这些标签）
            min_links: 最小链接数
            max_links: 最大链接数

        Returns:
            符合条件的笔记列表
        """
        results = list(self.notes.values())

        # 关键词过滤
        if query:
            query_lower = query.lower()
            results = [
                note
                for note in results
                if query_lower in note.name.lower()
                or query_lower in note.content.lower()
            ]

        # 标签过滤
        if tags:
            tag_set = set(tags)
            results = [note for note in results if tag_set.issubset(note.tags)]

        # 链接数过滤
        if min_links is not None:
            results = [note for note in results if note.total_links >= min_links]

        if max_links is not None:
            results = [note for note in results if note.total_links <= max_links]

        return results


class MultiVaultAnalyzer:
    """多 vault 分析器"""

    def __init__(
        self,
        vault_paths: List[str],
        exclude_folders: List[str] = None,
        exclude_notes: List[str] = None,
    ):
        self.vault_paths = [Path(p) for p in vault_paths]
        self.exclude_folders = exclude_folders
        self.exclude_notes = exclude_notes
        self.analyzers: Dict[str, ObsidianAnalyzer] = {}
        self.combined_stats = None

    def scan_all_vaults(self) -> None:
        """扫描所有 vaults"""
        print(f"🔍 Scanning {len(self.vault_paths)} vaults...")
        print()

        for vault_path in self.vault_paths:
            vault_name = vault_path.name
            print(f"📂 Vault: {vault_name}")

            analyzer = ObsidianAnalyzer(
                str(vault_path), self.exclude_folders, self.exclude_notes
            )
            analyzer.scan_vault()
            self.analyzers[vault_name] = analyzer
            print()

    def get_combined_statistics(self) -> Dict:
        """获取所有 vaults 的合并统计"""
        if not self.analyzers:
            return {}

        total_notes = sum(len(a.notes) for a in self.analyzers.values())
        total_words = sum(
            sum(n.word_count for n in a.notes.values()) for a in self.analyzers.values()
        )

        all_orphans = []
        all_tags = []
        total_links = 0

        for analyzer in self.analyzers.values():
            stats = analyzer.get_statistics()
            all_orphans.extend(stats["orphan_notes"])
            total_links += stats["total_links"]

            for note in analyzer.notes.values():
                all_tags.extend(note.tags)

        tag_counter = Counter(all_tags)

        return {
            "total_vaults": len(self.analyzers),
            "total_notes": total_notes,
            "total_words": total_words,
            "total_orphans": len(all_orphans),
            "total_links": total_links,
            "total_unique_tags": len(tag_counter),
            "vault_breakdown": {
                name: {
                    "notes": len(a.notes),
                    "words": sum(n.word_count for n in a.notes.values()),
                    "orphans": len([n for n in a.notes.values() if n.is_orphan]),
                }
                for name, a in self.analyzers.items()
            },
        }

    def search_across_vaults(self, **search_params) -> Dict[str, List[Note]]:
        """在所有 vaults 中搜索"""
        results = {}
        for vault_name, analyzer in self.analyzers.items():
            vault_results = analyzer.search_notes(**search_params)
            if vault_results:
                results[vault_name] = vault_results
        return results


if __name__ == "__main__":
    # 测试代码
    vault_path = os.getenv("VAULT_PATH", "F:/Project/Obsidian")
    exclude_folders = os.getenv("EXCLUDE_FOLDERS", ".obsidian,.trash").split(",")
    exclude_notes = (
        os.getenv("EXCLUDE_NOTES", "").split(",") if os.getenv("EXCLUDE_NOTES") else []
    )

    analyzer = ObsidianAnalyzer(vault_path, exclude_folders, exclude_notes)
    analyzer.scan_vault()

    stats = analyzer.get_statistics()
    print(f"\n📊 Statistics:")
    print(f"   Total notes: {stats['total_notes']}")
    print(f"   Total words: {stats['total_words']:,}")
    print(f"   Orphan notes: {len(stats['orphan_notes'])}")
    print(f"   Total links: {stats['total_links']}")
