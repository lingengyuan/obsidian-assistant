#!/usr/bin/env python3
"""
Obsidian Knowledge Assistant - Search Tool
搜索和查询笔记的命令行工具
"""

import os
import sys
import argparse
from pathlib import Path
from typing import List
import sys

# 添加 src 目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from core.analyzer import ObsidianAnalyzer, Note


def display_search_results(results: List[Note], title: str):
    """显示搜索结果"""
    if not results:
        print(f"\n{title}")
        print("  No results found.")
        return
    
    print(f"\n{title}")
    print(f"  Found {len(results)} note(s):")
    print()
    
    for i, note in enumerate(results, 1):
        print(f"  {i}. {note.name}")
        print(f"     Words: {note.word_count} | Links: {note.total_links} (↗{len(note.outgoing_links)} ↘{len(note.incoming_links)})")
        if note.tags:
            print(f"     Tags: {', '.join(sorted(note.tags))}")
        print(f"     Modified: {note.modified_time.strftime('%Y-%m-%d %H:%M')}")
        print()


def search_command(analyzer: ObsidianAnalyzer, args):
    """执行搜索命令"""
    query = args.query if hasattr(args, 'query') else None
    tags = args.tags.split(',') if args.tags else None
    min_links = args.min_links
    max_links = args.max_links
    
    results = analyzer.search_notes(
        query=query,
        tags=tags,
        min_links=min_links,
        max_links=max_links
    )
    
    # 构建搜索条件描述
    conditions = []
    if query:
        conditions.append(f"keyword '{query}'")
    if tags:
        conditions.append(f"tags {tags}")
    if min_links is not None:
        conditions.append(f"min_links >= {min_links}")
    if max_links is not None:
        conditions.append(f"max_links <= {max_links}")
    
    title = f"🔍 Search Results"
    if conditions:
        title += f" ({', '.join(conditions)})"
    
    display_search_results(results, title)


def list_orphans_command(analyzer: ObsidianAnalyzer, args):
    """列出孤岛笔记"""
    orphans = [note for note in analyzer.notes.values() if note.is_orphan]
    orphans.sort(key=lambda x: x.modified_time, reverse=True)
    
    if args.limit:
        orphans = orphans[:args.limit]
    
    display_search_results(orphans, "🏝️ Orphan Notes")


def list_hubs_command(analyzer: ObsidianAnalyzer, args):
    """列出知识枢纽"""
    hubs = sorted(
        analyzer.notes.values(),
        key=lambda x: len(x.outgoing_links),
        reverse=True
    )
    
    if args.limit:
        hubs = hubs[:args.limit]
    
    display_search_results(hubs, "🌐 Knowledge Hubs (Most Outgoing Links)")


def list_popular_command(analyzer: ObsidianAnalyzer, args):
    """列出热门笔记"""
    popular = sorted(
        analyzer.notes.values(),
        key=lambda x: len(x.incoming_links),
        reverse=True
    )
    
    if args.limit:
        popular = popular[:args.limit]
    
    display_search_results(popular, "⭐ Popular Notes (Most Incoming Links)")


def stats_command(analyzer: ObsidianAnalyzer, args):
    """显示统计信息"""
    stats = analyzer.get_statistics()
    
    print("\n" + "=" * 60)
    print("  📊 Vault Statistics")
    print("=" * 60)
    print(f"  Total notes:      {stats['total_notes']}")
    print(f"  Total words:      {stats['total_words']:,}")
    print(f"  Avg words/note:   {stats['avg_word_count']}")
    print(f"  Total links:      {stats['total_links']}")
    print(f"  Bidirectional:    {stats['bidirectional_links']}")
    print(f"  Avg links/note:   {stats['avg_links_per_note']:.1f}")
    print(f"  Orphan notes:     {len(stats['orphan_notes'])}")
    print(f"  Unique tags:      {len(stats['tag_counter'])}")
    print(f"  Untagged notes:   {len(stats['untagged_notes'])}")
    print("=" * 60)
    print()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='Obsidian Knowledge Assistant - Search Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--vault',
        type=str,
        help='Vault path (overrides VAULT_PATH env var)'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # search 命令
    search_parser = subparsers.add_parser('search', help='Search notes')
    search_parser.add_argument('query', nargs='?', help='Search query (keyword in name or content)')
    search_parser.add_argument('--tags', type=str, help='Filter by tags (comma-separated)')
    search_parser.add_argument('--min-links', type=int, help='Minimum number of links')
    search_parser.add_argument('--max-links', type=int, help='Maximum number of links')
    
    # orphans 命令
    orphans_parser = subparsers.add_parser('orphans', help='List orphan notes')
    orphans_parser.add_argument('--limit', type=int, default=20, help='Limit results (default: 20)')
    
    # hubs 命令
    hubs_parser = subparsers.add_parser('hubs', help='List knowledge hubs')
    hubs_parser.add_argument('--limit', type=int, default=10, help='Limit results (default: 10)')
    
    # popular 命令
    popular_parser = subparsers.add_parser('popular', help='List popular notes')
    popular_parser.add_argument('--limit', type=int, default=10, help='Limit results (default: 10)')
    
    # stats 命令
    stats_parser = subparsers.add_parser('stats', help='Show statistics')
    
    args = parser.parse_args()
    
    # 获取 vault 路径
    vault_path = args.vault or os.getenv('VAULT_PATH')
    if not vault_path:
        print("❌ Error: Vault path not specified")
        print("   Use --vault or set VAULT_PATH environment variable")
        sys.exit(1)
    
    vault_path = Path(vault_path)
    if not vault_path.exists():
        print(f"❌ Error: Vault does not exist: {vault_path}")
        sys.exit(1)
    
    # 加载配置
    exclude_folders = os.getenv('EXCLUDE_FOLDERS', '.obsidian,.trash').split(',')
    exclude_notes = os.getenv('EXCLUDE_NOTES', '').split(',') if os.getenv('EXCLUDE_NOTES') else []
    
    # 创建分析器
    print(f"🔍 Loading vault: {vault_path}")
    analyzer = ObsidianAnalyzer(str(vault_path), exclude_folders, exclude_notes)
    analyzer.scan_vault()
    
    # 执行命令
    if args.command == 'search':
        search_command(analyzer, args)
    elif args.command == 'orphans':
        list_orphans_command(analyzer, args)
    elif args.command == 'hubs':
        list_hubs_command(analyzer, args)
    elif args.command == 'popular':
        list_popular_command(analyzer, args)
    elif args.command == 'stats':
        stats_command(analyzer, args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
