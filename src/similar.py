#!/usr/bin/env python3
"""
Obsidian Knowledge Assistant - Similarity Analysis Tool
相似度分析命令行工具
"""

import os
import sys
import argparse
from pathlib import Path
import sys

# 添加 src 目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from core.analyzer import ObsidianAnalyzer
from core.similarity import SimilarityAnalyzer


def find_similar_command(analyzer: SimilarityAnalyzer, args):
    """查找与指定笔记相似的笔记"""
    results = analyzer.find_similar_notes(args.note_name, top_n=args.limit)

    if not results:
        print(f"\n❌ 未找到与 '{args.note_name}' 相似的笔记")
        print("   提示: 可能笔记名称不正确，或相似度阈值太高")
        return

    print(f"\n{'='*60}")
    print(f"  📝 与 '{args.note_name}' 相似的笔记")
    print(f"{'='*60}")
    print()

    for i, result in enumerate(results, 1):
        print(f"{i}. {result.note2}")
        print(f"   相似度: {result.similarity:.1%} | 原因: {result.reason}")
        if result.common_words:
            print(f"   共同关键词: {', '.join(result.common_words[:5])}")
        print()


def find_duplicates_command(analyzer: SimilarityAnalyzer, args):
    """查找可能重复的笔记"""
    threshold = args.threshold if hasattr(args, "threshold") and args.threshold else 0.7

    duplicates = analyzer.find_potential_duplicates(threshold=threshold)

    if not duplicates:
        print(f"\n✅ 未发现相似度 ≥{threshold:.0%} 的重复笔记")
        return

    print(f"\n{'='*60}")
    print(f"  ⚠️  可能重复的笔记 (相似度 ≥{threshold:.0%})")
    print(f"{'='*60}")
    print()

    for i, dup in enumerate(duplicates[: args.limit], 1):
        print(f"{i}. {dup.note1} ←→ {dup.note2}")
        print(f"   相似度: {dup.similarity:.1%}")
        print(f"   原因: {dup.reason}")
        if dup.common_words:
            print(f"   共同词: {', '.join(dup.common_words[:5])}")
        print()


def find_unlinked_command(analyzer: SimilarityAnalyzer, args):
    """查找相关但未链接的笔记"""
    print("\n🔍 分析相关笔记的链接状态...")

    related = analyzer.find_related_unlinked()

    # 只显示未链接的
    unlinked = [(sim, linked) for sim, linked in related if not linked]

    if not unlinked:
        print("\n✅ 所有相关笔记都已建立链接！")
        return

    print(f"\n{'='*60}")
    print(f"  🔗 相关但未链接的笔记 (建议添加链接)")
    print(f"{'='*60}")
    print()

    for i, (sim, _) in enumerate(unlinked[: args.limit], 1):
        print(f"{i}. {sim.note1} ←→ {sim.note2}")
        print(f"   相似度: {sim.similarity:.1%}")
        print(f"   💡 建议: 考虑在笔记间添加 [[链接]]")
        if sim.common_words:
            print(f"   共同主题: {', '.join(sim.common_words[:5])}")
        print()


def suggest_merges_command(analyzer: SimilarityAnalyzer, args):
    """建议合并的笔记"""
    print("\n🔍 分析可合并的笔记...")

    threshold = args.threshold if hasattr(args, "threshold") and args.threshold else 0.6
    suggestions = analyzer.suggest_merges(min_similarity=threshold)

    if not suggestions:
        print(f"\n✅ 未发现需要合并的笔记")
        return

    print(f"\n{'='*60}")
    print(f"  📦 建议合并的笔记")
    print(f"{'='*60}")
    print()

    for i, (note1, note2, similarity, reasons) in enumerate(
        suggestions[: args.limit], 1
    ):
        print(f"{i}. {note1} + {note2}")
        print(f"   相似度: {similarity:.1%}")
        print(f"   原因:")
        for reason in reasons:
            print(f"     • {reason}")
        print()


def analyze_all_command(analyzer: SimilarityAnalyzer, args):
    """分析所有相似笔记对"""
    threshold = args.threshold if hasattr(args, "threshold") and args.threshold else 0.3

    results = analyzer.find_all_similar_pairs(min_similarity=threshold)

    if not results:
        print(f"\n未发现相似度 ≥{threshold:.0%} 的笔记对")
        return

    # 显示统计
    stats = analyzer.get_statistics(results)

    print(f"\n{'='*60}")
    print(f"  📊 相似度分析统计")
    print(f"{'='*60}")
    print(f"  相似笔记对:   {stats['total_pairs']}")
    print(f"  高相似(≥70%): {stats['high_similarity']}")
    print(f"  中等(50-70%): {stats['medium_similarity']}")
    print(f"  低相似(<50%): {stats['low_similarity']}")
    print(f"  平均相似度:   {stats['avg_similarity']:.1%}")
    print(f"  最高相似度:   {stats['max_similarity']:.1%}")
    print(f"{'='*60}")
    print()

    # 显示 Top 结果
    print(f"Top {min(args.limit, len(results))} 最相似的笔记对:")
    print()

    for i, result in enumerate(results[: args.limit], 1):
        print(f"{i}. {result.note1} ←→ {result.note2}")
        print(f"   相似度: {result.similarity:.1%} | 原因: {result.reason}")
        if result.common_words:
            print(f"   共同词: {', '.join(result.common_words[:5])}")
        print()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Obsidian Knowledge Assistant - Similarity Analysis Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--vault", type=str, help="Vault path (overrides VAULT_PATH env var)"
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # find 命令 - 查找与指定笔记相似的笔记
    find_parser = subparsers.add_parser(
        "find", help="Find notes similar to a specific note"
    )
    find_parser.add_argument("note_name", help="Note name to find similar notes for")
    find_parser.add_argument(
        "--limit", type=int, default=5, help="Number of results (default: 5)"
    )

    # duplicates 命令 - 查找可能重复的笔记
    dup_parser = subparsers.add_parser(
        "duplicates", help="Find potential duplicate notes"
    )
    dup_parser.add_argument(
        "--threshold", type=float, help="Similarity threshold (default: 0.7)"
    )
    dup_parser.add_argument(
        "--limit", type=int, default=20, help="Number of results (default: 20)"
    )

    # unlinked 命令 - 查找相关但未链接的笔记
    unlink_parser = subparsers.add_parser(
        "unlinked", help="Find related but unlinked notes"
    )
    unlink_parser.add_argument(
        "--limit", type=int, default=20, help="Number of results (default: 20)"
    )

    # merge 命令 - 建议合并的笔记
    merge_parser = subparsers.add_parser("merge", help="Suggest notes to merge")
    merge_parser.add_argument(
        "--threshold", type=float, help="Similarity threshold (default: 0.6)"
    )
    merge_parser.add_argument(
        "--limit", type=int, default=10, help="Number of results (default: 10)"
    )

    # all 命令 - 分析所有相似笔记对
    all_parser = subparsers.add_parser("all", help="Analyze all similar note pairs")
    all_parser.add_argument(
        "--threshold", type=float, help="Minimum similarity threshold (default: 0.3)"
    )
    all_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Number of results to display (default: 20)",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # 获取 vault 路径
    vault_path = args.vault or os.getenv("VAULT_PATH")
    if not vault_path:
        print("❌ Error: Vault path not specified")
        print("   Use --vault or set VAULT_PATH environment variable")
        sys.exit(1)

    vault_path = Path(vault_path)
    if not vault_path.exists():
        print(f"❌ Error: Vault does not exist: {vault_path}")
        sys.exit(1)

    # 加载配置
    exclude_folders = os.getenv("EXCLUDE_FOLDERS", ".obsidian,.trash").split(",")
    exclude_notes = (
        os.getenv("EXCLUDE_NOTES", "").split(",") if os.getenv("EXCLUDE_NOTES") else []
    )

    # 创建分析器
    print(f"🔍 Loading vault: {vault_path}")
    obs_analyzer = ObsidianAnalyzer(str(vault_path), exclude_folders, exclude_notes)
    obs_analyzer.scan_vault()

    print("🧮 Initializing similarity analyzer...")
    sim_analyzer = SimilarityAnalyzer(obs_analyzer.notes)

    # 执行命令
    try:
        if args.command == "find":
            find_similar_command(sim_analyzer, args)

        elif args.command == "duplicates":
            find_duplicates_command(sim_analyzer, args)

        elif args.command == "unlinked":
            find_unlinked_command(sim_analyzer, args)

        elif args.command == "merge":
            suggest_merges_command(sim_analyzer, args)

        elif args.command == "all":
            analyze_all_command(sim_analyzer, args)

    except KeyboardInterrupt:
        print("\n\n⚠️  Analysis interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
