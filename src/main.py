#!/usr/bin/env python3
"""
Obsidian Knowledge Assistant - Main Entry Point
主程序入口
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime
import sys

# 添加 src 目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from core.analyzer import ObsidianAnalyzer, MultiVaultAnalyzer
from exporters.report_generator import ReportGenerator
from exporters.exporter import DataExporter
from core.quality_scorer import QualityScorer, generate_quality_report


def load_env_from_file():
    """从 set_env.sh 加载环境变量"""
    env_file = Path(__file__).parent / 'set_env.sh'
    if not env_file.exists():
        print(f"⚠️  Warning: {env_file} not found, using default values")
        return
    
    # 简单解析 export 语句
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line.startswith('export '):
                line = line[7:]  # 移除 'export '
                if '=' in line:
                    key, value = line.split('=', 1)
                    # 移除引号
                    value = value.strip('"').strip("'")
                    os.environ[key] = value


def analyze_single_vault(vault_path: Path, exclude_folders: list, exclude_notes: list, args):
    """分析单个 vault"""
    print("=" * 60)
    print("  Obsidian Knowledge Assistant")
    print("=" * 60)
    print()
    
    try:
        analyzer = ObsidianAnalyzer(str(vault_path), exclude_folders, exclude_notes)
        analyzer.scan_vault()
        
        stats = analyzer.get_statistics()
        
        print()
        print("=" * 60)
        print("  📊 Quick Statistics")
        print("=" * 60)
        print(f"  Total notes:      {stats['total_notes']}")
        print(f"  Total words:      {stats['total_words']:,}")
        print(f"  Orphan notes:     {len(stats['orphan_notes'])}")
        print(f"  Total links:      {stats['total_links']}")
        print(f"  Bidirectional:    {stats['bidirectional_links']}")
        print(f"  Unique tags:      {len(stats['tag_counter'])}")
        print("=" * 60)
        print()
        
        # 生成报告
        if not args.no_report:
            output_dir = args.output or os.getenv('REPORT_OUTPUT', 'reports')
            
            generator = ReportGenerator(stats, str(vault_path))
            report_path = generator.save_report(output_dir)
            
            print(f"✅ Report generated: {report_path}")
            
            # 质量评分
            if os.getenv('ENABLE_QUALITY_SCORING', 'true').lower() == 'true':
                print()
                print("🎯 Calculating quality scores...")
                
                scorer = QualityScorer(analyzer.notes)
                scores = scorer.score_all_notes()
                quality_stats = scorer.get_statistics(scores)
                
                # 生成质量报告
                quality_report = generate_quality_report(scores, quality_stats)
                
                # 保存质量报告
                quality_report_path = Path(output_dir) / datetime.now().strftime('quality-report-%Y-%m-%d.md')
                with open(quality_report_path, 'w', encoding='utf-8') as f:
                    f.write(quality_report)
                
                print(f"✅ Quality report generated: {quality_report_path}")
                
                # 显示快速质量统计
                print()
                print("📊 Quality Overview:")
                print(f"  Average score:     {quality_stats['average_score']:.1f}")
                print(f"  Grade A notes:     {quality_stats['grade_distribution']['A']}")
                print(f"  Needs improvement: {len(quality_stats['needs_improvement'])}")
            
            # 导出数据
            if args.export or os.getenv('EXPORT_JSON', 'true').lower() == 'true' or \
               os.getenv('EXPORT_CSV', 'true').lower() == 'true':
                print()
                print("📦 Exporting data...")
                exporter = DataExporter(stats, analyzer.notes, str(vault_path))
                exported = exporter.export_all(output_dir)
                print()
            
            print()
            print("💡 Tip: Open the report in Obsidian to see formatted results")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Analysis interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def analyze_multi_vaults(vault_paths: list, exclude_folders: list, exclude_notes: list, args):
    """分析多个 vaults"""
    print("=" * 60)
    print("  Obsidian Knowledge Assistant - Multi-Vault Mode")
    print("=" * 60)
    print()
    
    try:
        multi_analyzer = MultiVaultAnalyzer(vault_paths, exclude_folders, exclude_notes)
        multi_analyzer.scan_all_vaults()
        
        combined_stats = multi_analyzer.get_combined_statistics()
        
        print("=" * 60)
        print("  📊 Combined Statistics")
        print("=" * 60)
        print(f"  Total vaults:     {combined_stats['total_vaults']}")
        print(f"  Total notes:      {combined_stats['total_notes']}")
        print(f"  Total words:      {combined_stats['total_words']:,}")
        print(f"  Total orphans:    {combined_stats['total_orphans']}")
        print(f"  Total links:      {combined_stats['total_links']}")
        print(f"  Unique tags:      {combined_stats['total_unique_tags']}")
        print("=" * 60)
        print()
        
        print("📂 Breakdown by vault:")
        for vault_name, breakdown in combined_stats['vault_breakdown'].items():
            print(f"  • {vault_name}:")
            print(f"    Notes: {breakdown['notes']} | Words: {breakdown['words']:,} | Orphans: {breakdown['orphans']}")
        print()
        
        # 为每个 vault 生成单独的报告
        if not args.no_report:
            output_dir = args.output or os.getenv('REPORT_OUTPUT', 'reports')
            
            for vault_name, analyzer in multi_analyzer.analyzers.items():
                stats = analyzer.get_statistics()
                vault_output = Path(output_dir) / vault_name
                
                generator = ReportGenerator(stats, str(analyzer.vault_path))
                report_path = generator.save_report(str(vault_output))
                
                print(f"✅ Report generated for {vault_name}: {report_path}")
                
                # 导出数据
                if args.export:
                    exporter = DataExporter(stats, analyzer.notes, str(analyzer.vault_path))
                    exporter.export_all(str(vault_output))
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Analysis interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description='Obsidian Knowledge Assistant - 分析你的知识库'
    )
    parser.add_argument(
        '--vault',
        type=str,
        help='Obsidian vault 路径（覆盖环境变量）'
    )
    parser.add_argument(
        '--multi-vault',
        type=str,
        help='多个 vault 路径（逗号分隔）'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='报告输出目录（覆盖环境变量）'
    )
    parser.add_argument(
        '--no-report',
        action='store_true',
        help='只分析不生成报告'
    )
    parser.add_argument(
        '--export',
        action='store_true',
        help='导出 JSON 和 CSV 数据'
    )
    
    args = parser.parse_args()
    
    # 加载环境变量
    load_env_from_file()
    
    # 获取配置
    exclude_folders = os.getenv('EXCLUDE_FOLDERS', '.obsidian,.trash').split(',')
    exclude_folders = [f.strip() for f in exclude_folders if f.strip()]
    
    exclude_notes = os.getenv('EXCLUDE_NOTES', '').split(',')
    exclude_notes = [n.strip() for n in exclude_notes if n.strip()]
    
    # 确定 vault 路径
    if args.multi_vault:
        # 多 vault 模式
        vault_paths = [p.strip() for p in args.multi_vault.split(',')]
        
        # 验证所有路径
        for vault_path in vault_paths:
            if not Path(vault_path).exists():
                print(f"❌ Error: Vault path does not exist: {vault_path}")
                sys.exit(1)
        
        analyze_multi_vaults(vault_paths, exclude_folders, exclude_notes, args)
        
    else:
        # 单 vault 模式
        vault_path = args.vault or os.getenv('VAULT_PATH')
        multi_vault_env = os.getenv('MULTI_VAULT_PATHS', '')
        
        if multi_vault_env.strip():
            # 使用环境变量中的多 vault 配置
            vault_paths = [p.strip() for p in multi_vault_env.split(',')]
            
            # 验证所有路径
            for vp in vault_paths:
                if not Path(vp).exists():
                    print(f"❌ Error: Vault path does not exist: {vp}")
                    sys.exit(1)
            
            analyze_multi_vaults(vault_paths, exclude_folders, exclude_notes, args)
            
        else:
            # 单 vault
            if not vault_path:
                print("❌ Error: Vault path not specified")
                print("   Use --vault or set VAULT_PATH in set_env.sh")
                sys.exit(1)
            
            vault_path = Path(vault_path)
            if not vault_path.exists():
                print(f"❌ Error: Vault path does not exist: {vault_path}")
                sys.exit(1)
            
            analyze_single_vault(vault_path, exclude_folders, exclude_notes, args)


if __name__ == '__main__':
    main()
