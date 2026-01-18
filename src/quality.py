#!/usr/bin/env python3
"""
Obsidian Knowledge Assistant - Quality Scoring Tool
独立的笔记质量评分工具
"""

import os
import sys
import argparse
from pathlib import Path
import sys

# 添加 src 目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from core.analyzer import ObsidianAnalyzer
from core.quality_scorer import QualityScorer, QualityScore


def display_score_details(score: QualityScore):
    """显示单个笔记的详细评分"""
    print(f"\n{'='*60}")
    print(f"  📝 {score.note_name}")
    print(f"{'='*60}")
    print(f"  总分: {score.percentage:.1f}/100 (评级: {score.grade})")
    print()
    print("  各维度得分:")
    print(f"    字数:   {score.word_count_score:>5.1f}/100")
    print(f"    链接:   {score.link_score:>5.1f}/100")
    print(f"    标签:   {score.tag_score:>5.1f}/100")
    print(f"    新鲜度: {score.freshness_score:>5.1f}/100")

    if score.issues:
        print()
        print("  ❌ 存在问题:")
        for issue in score.issues:
            print(f"    • {issue}")

    if score.suggestions:
        print()
        print("  💡 改进建议:")
        for suggestion in score.suggestions:
            print(f"    • {suggestion}")

    print(f"{'='*60}")


def list_by_score(scores: dict, args):
    """按分数列出笔记"""
    sorted_scores = sorted(
        scores.values(), key=lambda x: x.percentage, reverse=not args.ascending
    )

    if args.limit:
        sorted_scores = sorted_scores[: args.limit]

    if args.grade:
        sorted_scores = [s for s in sorted_scores if s.grade == args.grade.upper()]

    print(f"\n{'='*60}")
    print(f"  📊 笔记质量排名")
    print(f"{'='*60}")
    print()

    for i, score in enumerate(sorted_scores, 1):
        print(f"{i:3}. [{score.grade}] {score.note_name}")
        print(
            f"     分数: {score.percentage:.1f}  |  字数:{score.word_count_score:.0f}  链接:{score.link_score:.0f}  标签:{score.tag_score:.0f}  新鲜:{score.freshness_score:.0f}"
        )
        print()


def show_statistics(stats: dict):
    """显示统计信息"""
    print(f"\n{'='*60}")
    print(f"  📊 质量统计")
    print(f"{'='*60}")
    print(f"  总笔记数:  {stats['total_notes']}")
    print(f"  平均分:    {stats['average_score']:.1f}")
    print(f"  中位数:    {stats['median_score']:.1f}")
    print(f"  最高分:    {stats['max_score']:.1f}")
    print(f"  最低分:    {stats['min_score']:.1f}")
    print()
    print("  评级分布:")

    grade_dist = stats["grade_distribution"]
    total = stats["total_notes"]

    for grade in ["A", "B", "C", "D", "F"]:
        count = grade_dist[grade]
        percentage = (count / total * 100) if total > 0 else 0
        bar = "█" * int(percentage / 2)
        print(f"    {grade}: {count:3} ({percentage:5.1f}%) {bar}")

    print(f"{'='*60}")


def show_needs_improvement(stats: dict, limit: int = 10):
    """显示需要改进的笔记"""
    needs_improvement = stats["needs_improvement"][:limit]

    print(f"\n{'='*60}")
    print(f"  ⚠️  需要改进的笔记 (Top {min(limit, len(stats['needs_improvement']))})")
    print(f"{'='*60}")
    print()

    for i, score in enumerate(needs_improvement, 1):
        print(f"{i}. {score.note_name} - {score.percentage:.1f}分 ({score.grade})")

        if score.issues:
            for issue in score.issues[:2]:  # 只显示前2个问题
                print(f"   ❌ {issue}")

        print()


def show_excellent(stats: dict, limit: int = 10):
    """显示优质笔记"""
    excellent = stats["excellent_notes"][:limit]

    print(f"\n{'='*60}")
    print(f"  ⭐ 优质笔记 (Top {min(limit, len(stats['excellent_notes']))})")
    print(f"{'='*60}")
    print()

    for i, score in enumerate(excellent, 1):
        print(f"{i}. {score.note_name} - {score.percentage:.1f}分 ({score.grade})")
        print(
            f"   字数:{score.word_count_score:.0f}  链接:{score.link_score:.0f}  标签:{score.tag_score:.0f}  新鲜:{score.freshness_score:.0f}"
        )
        print()


def check_note(scores: dict, note_name: str):
    """检查特定笔记的评分"""
    # 尝试精确匹配
    if note_name in scores:
        display_score_details(scores[note_name])
        return

    # 尝试模糊匹配
    matches = [name for name in scores.keys() if note_name.lower() in name.lower()]

    if not matches:
        print(f"\n❌ 未找到笔记: {note_name}")
        return

    if len(matches) == 1:
        display_score_details(scores[matches[0]])
    else:
        print(f"\n找到 {len(matches)} 个匹配的笔记:")
        for i, match in enumerate(matches[:10], 1):
            print(
                f"{i}. {match} - {scores[match].percentage:.1f}分 ({scores[match].grade})"
            )


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Obsidian Knowledge Assistant - Quality Scoring Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--vault", type=str, help="Vault path (overrides VAULT_PATH env var)"
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # score 命令
    score_parser = subparsers.add_parser("score", help="Score all notes")

    # list 命令
    list_parser = subparsers.add_parser("list", help="List notes by score")
    list_parser.add_argument("--limit", type=int, default=20, help="Limit results")
    list_parser.add_argument(
        "--grade", type=str, choices=["A", "B", "C", "D", "F"], help="Filter by grade"
    )
    list_parser.add_argument(
        "--ascending", action="store_true", help="Sort ascending (low to high)"
    )

    # stats 命令
    stats_parser = subparsers.add_parser("stats", help="Show quality statistics")

    # worst 命令
    worst_parser = subparsers.add_parser("worst", help="Show worst notes")
    worst_parser.add_argument(
        "--limit", type=int, default=10, help="Number of notes to show"
    )

    # best 命令
    best_parser = subparsers.add_parser("best", help="Show best notes")
    best_parser.add_argument(
        "--limit", type=int, default=10, help="Number of notes to show"
    )

    # check 命令
    check_parser = subparsers.add_parser("check", help="Check specific note")
    check_parser.add_argument("note_name", help="Note name to check")

    args = parser.parse_args()

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
    analyzer = ObsidianAnalyzer(str(vault_path), exclude_folders, exclude_notes)
    analyzer.scan_vault()

    # 计算质量评分
    print("🎯 Calculating quality scores...")
    scorer = QualityScorer(analyzer.notes)
    scores = scorer.score_all_notes()
    stats = scorer.get_statistics(scores)

    # 执行命令
    if args.command == "score" or args.command is None:
        show_statistics(stats)
        print()
        show_excellent(stats, 5)
        print()
        show_needs_improvement(stats, 5)

    elif args.command == "list":
        list_by_score(scores, args)

    elif args.command == "stats":
        show_statistics(stats)

    elif args.command == "worst":
        show_needs_improvement(stats, args.limit)

    elif args.command == "best":
        show_excellent(stats, args.limit)

    elif args.command == "check":
        check_note(scores, args.note_name)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
