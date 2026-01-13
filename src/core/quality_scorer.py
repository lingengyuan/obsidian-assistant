#!/usr/bin/env python3
"""
Obsidian Knowledge Assistant - Quality Scorer
笔记质量评分系统
"""

import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from dataclasses import dataclass
import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.analyzer import Note


@dataclass
class QualityScore:
    """笔记质量评分"""
    note_name: str
    total_score: float
    max_score: float
    percentage: float
    
    # 各维度得分
    word_count_score: float
    link_score: float
    tag_score: float
    freshness_score: float
    
    # 评级
    grade: str
    issues: List[str]
    suggestions: List[str]
    
    def __repr__(self):
        return f"QualityScore({self.note_name}: {self.percentage:.1f}% - {self.grade})"


class QualityScorer:
    """笔记质量评分器"""
    
    def __init__(self, notes: Dict[str, Note]):
        self.notes = notes
        
        # 评分权重配置（可通过环境变量调整）
        self.weights = {
            'word_count': float(os.getenv('SCORE_WEIGHT_WORDS', '0.25')),
            'links': float(os.getenv('SCORE_WEIGHT_LINKS', '0.35')),
            'tags': float(os.getenv('SCORE_WEIGHT_TAGS', '0.15')),
            'freshness': float(os.getenv('SCORE_WEIGHT_FRESHNESS', '0.25'))
        }
        
        # 评分标准配置
        self.standards = {
            'min_words': int(os.getenv('QUALITY_MIN_WORDS', '100')),
            'ideal_words': int(os.getenv('QUALITY_IDEAL_WORDS', '500')),
            'min_links': int(os.getenv('QUALITY_MIN_LINKS', '2')),
            'ideal_links': int(os.getenv('QUALITY_IDEAL_LINKS', '5')),
            'min_tags': int(os.getenv('QUALITY_MIN_TAGS', '1')),
            'ideal_tags': int(os.getenv('QUALITY_IDEAL_TAGS', '3')),
            'freshness_days': int(os.getenv('QUALITY_FRESHNESS_DAYS', '90'))
        }
    
    def score_word_count(self, note: Note) -> Tuple[float, List[str], List[str]]:
        """评分：字数（满分 100）"""
        word_count = note.word_count
        min_words = self.standards['min_words']
        ideal_words = self.standards['ideal_words']
        
        issues = []
        suggestions = []
        
        if word_count < min_words:
            score = (word_count / min_words) * 50  # 少于最小值，最多50分
            issues.append(f"内容太少（仅 {word_count} 字）")
            suggestions.append(f"建议扩展到至少 {min_words} 字")
        elif word_count < ideal_words:
            # 线性插值从 50 到 100
            score = 50 + ((word_count - min_words) / (ideal_words - min_words)) * 50
            if word_count < ideal_words * 0.7:
                suggestions.append(f"可以继续扩展内容（目标 {ideal_words} 字）")
        else:
            score = 100
        
        return score, issues, suggestions
    
    def score_links(self, note: Note) -> Tuple[float, List[str], List[str]]:
        """评分：链接数（满分 100）"""
        total_links = note.total_links
        min_links = self.standards['min_links']
        ideal_links = self.standards['ideal_links']
        
        issues = []
        suggestions = []
        
        if total_links == 0:
            score = 0
            issues.append("没有任何链接（孤岛笔记）")
            suggestions.append("添加到相关笔记的链接")
        elif total_links < min_links:
            score = (total_links / min_links) * 50
            issues.append(f"链接太少（仅 {total_links} 个）")
            suggestions.append(f"建议添加至少 {min_links} 个链接")
        elif total_links < ideal_links:
            score = 50 + ((total_links - min_links) / (ideal_links - min_links)) * 50
        else:
            score = 100
        
        # 检查链接平衡性
        if total_links > 0:
            outgoing = len(note.outgoing_links)
            incoming = len(note.incoming_links)
            
            if outgoing == 0 and incoming > 0:
                suggestions.append("考虑添加出链，增强知识网络")
            elif incoming == 0 and outgoing > 0:
                suggestions.append("这个笔记还没被其他笔记引用")
        
        return score, issues, suggestions
    
    def score_tags(self, note: Note) -> Tuple[float, List[str], List[str]]:
        """评分：标签（满分 100）"""
        tag_count = len(note.tags)
        min_tags = self.standards['min_tags']
        ideal_tags = self.standards['ideal_tags']
        
        issues = []
        suggestions = []
        
        if tag_count == 0:
            score = 0
            issues.append("没有标签")
            suggestions.append("添加合适的标签以便分类")
        elif tag_count < min_tags:
            score = (tag_count / min_tags) * 50
            issues.append(f"标签太少（仅 {tag_count} 个）")
            suggestions.append(f"建议添加至少 {min_tags} 个标签")
        elif tag_count < ideal_tags:
            score = 50 + ((tag_count - min_tags) / (ideal_tags - min_tags)) * 50
        else:
            score = 100
            if tag_count > ideal_tags * 2:
                suggestions.append("标签可能过多，考虑精简")
        
        return score, issues, suggestions
    
    def score_freshness(self, note: Note) -> Tuple[float, List[str], List[str]]:
        """评分：新鲜度（满分 100）"""
        now = datetime.now()
        days_old = (now - note.modified_time).days
        freshness_threshold = self.standards['freshness_days']
        
        issues = []
        suggestions = []
        
        if days_old <= 7:
            score = 100
        elif days_old <= 30:
            score = 90
        elif days_old <= freshness_threshold:
            score = 70
        elif days_old <= freshness_threshold * 2:
            score = 50
            suggestions.append(f"已 {days_old} 天未更新，考虑复习")
        else:
            score = 30
            issues.append(f"已 {days_old} 天未更新")
            suggestions.append("检查内容是否仍然相关")
        
        return score, issues, suggestions
    
    def calculate_score(self, note: Note) -> QualityScore:
        """计算笔记的综合质量得分"""
        all_issues = []
        all_suggestions = []
        
        # 计算各维度得分
        word_score, word_issues, word_suggestions = self.score_word_count(note)
        link_score, link_issues, link_suggestions = self.score_links(note)
        tag_score, tag_issues, tag_suggestions = self.score_tags(note)
        fresh_score, fresh_issues, fresh_suggestions = self.score_freshness(note)
        
        all_issues.extend(word_issues)
        all_issues.extend(link_issues)
        all_issues.extend(tag_issues)
        all_issues.extend(fresh_issues)
        
        all_suggestions.extend(word_suggestions)
        all_suggestions.extend(link_suggestions)
        all_suggestions.extend(tag_suggestions)
        all_suggestions.extend(fresh_suggestions)
        
        # 加权计算总分
        total_score = (
            word_score * self.weights['word_count'] +
            link_score * self.weights['links'] +
            tag_score * self.weights['tags'] +
            fresh_score * self.weights['freshness']
        )
        
        max_score = 100
        percentage = total_score
        
        # 评级
        if percentage >= 90:
            grade = 'A'
        elif percentage >= 80:
            grade = 'B'
        elif percentage >= 70:
            grade = 'C'
        elif percentage >= 60:
            grade = 'D'
        else:
            grade = 'F'
        
        return QualityScore(
            note_name=note.name,
            total_score=total_score,
            max_score=max_score,
            percentage=percentage,
            word_count_score=word_score,
            link_score=link_score,
            tag_score=tag_score,
            freshness_score=fresh_score,
            grade=grade,
            issues=all_issues,
            suggestions=all_suggestions
        )
    
    def score_all_notes(self) -> Dict[str, QualityScore]:
        """为所有笔记评分"""
        scores = {}
        for note_name, note in self.notes.items():
            scores[note_name] = self.calculate_score(note)
        return scores
    
    def get_statistics(self, scores: Dict[str, QualityScore]) -> Dict:
        """获取评分统计"""
        if not scores:
            return {}
        
        all_scores = [s.percentage for s in scores.values()]
        
        grade_distribution = {
            'A': len([s for s in scores.values() if s.grade == 'A']),
            'B': len([s for s in scores.values() if s.grade == 'B']),
            'C': len([s for s in scores.values() if s.grade == 'C']),
            'D': len([s for s in scores.values() if s.grade == 'D']),
            'F': len([s for s in scores.values() if s.grade == 'F'])
        }
        
        # 需要改进的笔记（低于70分）
        needs_improvement = [
            s for s in scores.values() 
            if s.percentage < 70
        ]
        needs_improvement.sort(key=lambda x: x.percentage)
        
        # 优质笔记（90分以上）
        excellent_notes = [
            s for s in scores.values()
            if s.percentage >= 90
        ]
        excellent_notes.sort(key=lambda x: x.percentage, reverse=True)
        
        return {
            'total_notes': len(scores),
            'average_score': sum(all_scores) / len(all_scores),
            'median_score': sorted(all_scores)[len(all_scores) // 2],
            'min_score': min(all_scores),
            'max_score': max(all_scores),
            'grade_distribution': grade_distribution,
            'needs_improvement': needs_improvement,
            'excellent_notes': excellent_notes,
            'all_scores': scores
        }
    
    def get_top_issues(self, scores: Dict[str, QualityScore], limit: int = 10) -> List[Tuple[str, List[str]]]:
        """获取最需要改进的笔记及其问题"""
        scored_notes = [(s.note_name, s.percentage, s.issues) 
                       for s in scores.values() if s.issues]
        scored_notes.sort(key=lambda x: x[1])
        
        return [(name, issues) for name, _, issues in scored_notes[:limit]]


def generate_quality_report(scores: Dict[str, QualityScore], stats: Dict) -> str:
    """生成质量评分报告"""
    lines = []
    
    lines.append("# 📊 笔记质量评分报告")
    lines.append("")
    lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # 总体统计
    lines.append("## 📈 总体评分")
    lines.append("")
    lines.append(f"- **笔记总数**: {stats['total_notes']}")
    lines.append(f"- **平均分**: {stats['average_score']:.1f}")
    lines.append(f"- **中位数**: {stats['median_score']:.1f}")
    lines.append(f"- **最高分**: {stats['max_score']:.1f}")
    lines.append(f"- **最低分**: {stats['min_score']:.1f}")
    lines.append("")
    
    # 评级分布
    lines.append("## 🎯 评级分布")
    lines.append("")
    grade_dist = stats['grade_distribution']
    total = stats['total_notes']
    
    for grade in ['A', 'B', 'C', 'D', 'F']:
        count = grade_dist[grade]
        percentage = (count / total * 100) if total > 0 else 0
        bar = '█' * int(percentage / 2)
        lines.append(f"**{grade}**: {count} 篇 ({percentage:.1f}%) {bar}")
    
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # 优质笔记
    if stats['excellent_notes']:
        lines.append("## ⭐ 优质笔记 (≥90分)")
        lines.append("")
        lines.append("这些笔记质量优秀，值得参考和维护。")
        lines.append("")
        
        for i, score in enumerate(stats['excellent_notes'][:10], 1):
            lines.append(f"{i}. **{score.note_name}** - {score.percentage:.1f}分 ({score.grade})")
            lines.append(f"   - 字数: {score.word_count_score:.0f}/100")
            lines.append(f"   - 链接: {score.link_score:.0f}/100")
            lines.append(f"   - 标签: {score.tag_score:.0f}/100")
            lines.append(f"   - 新鲜度: {score.freshness_score:.0f}/100")
            lines.append("")
        
        lines.append("---")
        lines.append("")
    
    # 需要改进的笔记
    if stats['needs_improvement']:
        lines.append("## ⚠️ 需要改进的笔记 (<70分)")
        lines.append("")
        lines.append("这些笔记存在一些问题，建议优先处理。")
        lines.append("")
        
        for i, score in enumerate(stats['needs_improvement'][:20], 1):
            lines.append(f"### {i}. {score.note_name} - {score.percentage:.1f}分 ({score.grade})")
            lines.append("")
            
            if score.issues:
                lines.append("**问题**:")
                for issue in score.issues:
                    lines.append(f"- ❌ {issue}")
                lines.append("")
            
            if score.suggestions:
                lines.append("**建议**:")
                for suggestion in score.suggestions:
                    lines.append(f"- 💡 {suggestion}")
                lines.append("")
            
            lines.append(f"**各维度得分**:")
            lines.append(f"- 字数: {score.word_count_score:.0f}/100")
            lines.append(f"- 链接: {score.link_score:.0f}/100")
            lines.append(f"- 标签: {score.tag_score:.0f}/100")
            lines.append(f"- 新鲜度: {score.freshness_score:.0f}/100")
            lines.append("")
            lines.append("---")
            lines.append("")
    
    # 改进建议
    lines.append("## 💡 整体改进建议")
    lines.append("")
    
    # 分析常见问题
    low_word_count = sum(1 for s in scores.values() if s.word_count_score < 50)
    low_links = sum(1 for s in scores.values() if s.link_score < 50)
    low_tags = sum(1 for s in scores.values() if s.tag_score < 50)
    low_freshness = sum(1 for s in scores.values() if s.freshness_score < 50)
    
    if low_word_count > total * 0.2:
        lines.append(f"1. **内容问题**: {low_word_count} 篇笔记内容太少")
        lines.append("   - 建议定期扩展笔记内容")
        lines.append("   - 或者将短笔记合并到相关笔记中")
        lines.append("")
    
    if low_links > total * 0.2:
        lines.append(f"2. **链接问题**: {low_links} 篇笔记缺少链接")
        lines.append("   - 建议为孤岛笔记添加链接")
        lines.append("   - 创建索引笔记连接相关内容")
        lines.append("")
    
    if low_tags > total * 0.2:
        lines.append(f"3. **标签问题**: {low_tags} 篇笔记缺少标签")
        lines.append("   - 建议统一标签体系")
        lines.append("   - 为笔记添加合适的分类标签")
        lines.append("")
    
    if low_freshness > total * 0.3:
        lines.append(f"4. **更新问题**: {low_freshness} 篇笔记长时间未更新")
        lines.append("   - 建议定期复习旧笔记")
        lines.append("   - 删除或归档过时内容")
        lines.append("")
    
    lines.append("---")
    lines.append("")
    lines.append("*由 Obsidian Knowledge Assistant 生成*")
    
    return '\n'.join(lines)


if __name__ == '__main__':
    print("This module should be imported, not run directly.")
