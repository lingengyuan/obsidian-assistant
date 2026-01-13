#!/usr/bin/env python3
"""
Obsidian Knowledge Assistant - Similarity Analyzer
内容相似度分析模块
"""

import os
import re
import math
from collections import Counter, defaultdict
from typing import Dict, List, Tuple, Set
from dataclasses import dataclass
import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.analyzer import Note


@dataclass
class SimilarityResult:
    """相似度结果"""
    note1: str
    note2: str
    similarity: float
    common_words: List[str]
    reason: str  # 相似原因：'content', 'title', 'tags'
    
    def __repr__(self):
        return f"SimilarityResult({self.note1} <-> {self.note2}: {self.similarity:.2%})"


class SimilarityAnalyzer:
    """相似度分析器"""
    
    def __init__(self, notes: Dict[str, Note]):
        self.notes = notes
        
        # 停用词（中英文常见词）
        self.stopwords = set([
            # 英文停用词
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
            'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'should', 'could', 'may', 'might', 'must', 'can', 'this',
            'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they',
            'my', 'your', 'his', 'her', 'its', 'our', 'their', 'me', 'him', 'us',
            'them', 'what', 'which', 'who', 'when', 'where', 'why', 'how',
            # 中文停用词
            '的', '了', '和', '是', '在', '我', '有', '个', '不', '人', '这', '中',
            '大', '为', '上', '来', '他', '时', '要', '就', '出', '们', '到', '说',
            '也', '地', '她', '你', '会', '着', '没', '看', '好', '自', '而', '能',
            '下', '对', '于', '把', '那', '与', '去', '得', '起', '还', '从', '用'
        ])
        
        # 最小相似度阈值
        self.min_similarity = float(os.getenv('SIMILARITY_MIN_THRESHOLD', '0.3'))
        
        # 词向量缓存
        self._word_vectors = {}
        self._idf_scores = {}
    
    def _tokenize(self, text: str) -> List[str]:
        """分词（简单实现）"""
        # 移除代码块
        text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
        # 移除链接
        text = re.sub(r'\[\[.*?\]\]', '', text)
        text = re.sub(r'\[.*?\]\(.*?\)', '', text)
        # 移除 Markdown 标记
        text = re.sub(r'[#*_`]', '', text)
        
        # 分割为单词（保留中英文）
        # 英文单词
        words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
        # 中文字符（按字分）
        chinese = re.findall(r'[\u4e00-\u9fff]+', text)
        for chars in chinese:
            words.extend(list(chars))
        
        # 过滤停用词和短词
        words = [w for w in words if w not in self.stopwords and len(w) > 1]
        
        return words
    
    def _calculate_idf(self):
        """计算 IDF (Inverse Document Frequency)"""
        # 统计每个词出现在多少个文档中
        doc_count = defaultdict(int)
        total_docs = len(self.notes)
        
        for note in self.notes.values():
            words = set(self._tokenize(note.content))
            for word in words:
                doc_count[word] += 1
        
        # 计算 IDF
        for word, count in doc_count.items():
            self._idf_scores[word] = math.log(total_docs / count)
    
    def _get_tfidf_vector(self, note: Note) -> Dict[str, float]:
        """获取笔记的 TF-IDF 向量"""
        if note.name in self._word_vectors:
            return self._word_vectors[note.name]
        
        words = self._tokenize(note.content)
        
        # 计算 TF (Term Frequency)
        word_count = Counter(words)
        total_words = len(words)
        
        if total_words == 0:
            self._word_vectors[note.name] = {}
            return {}
        
        # 计算 TF-IDF
        tfidf = {}
        for word, count in word_count.items():
            tf = count / total_words
            idf = self._idf_scores.get(word, 0)
            tfidf[word] = tf * idf
        
        self._word_vectors[note.name] = tfidf
        return tfidf
    
    def _cosine_similarity(self, vec1: Dict[str, float], vec2: Dict[str, float]) -> float:
        """计算余弦相似度"""
        if not vec1 or not vec2:
            return 0.0
        
        # 计算点积
        common_words = set(vec1.keys()) & set(vec2.keys())
        dot_product = sum(vec1[w] * vec2[w] for w in common_words)
        
        # 计算向量长度
        norm1 = math.sqrt(sum(v ** 2 for v in vec1.values()))
        norm2 = math.sqrt(sum(v ** 2 for v in vec2.values()))
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def _title_similarity(self, title1: str, title2: str) -> float:
        """标题相似度（简单的词重叠）"""
        words1 = set(self._tokenize(title1))
        words2 = set(self._tokenize(title2))
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    def _tag_similarity(self, tags1: Set[str], tags2: Set[str]) -> float:
        """标签相似度"""
        if not tags1 or not tags2:
            return 0.0
        
        intersection = len(tags1 & tags2)
        union = len(tags1 | tags2)
        
        return intersection / union if union > 0 else 0.0
    
    def find_similar_notes(self, note_name: str, top_n: int = 5) -> List[SimilarityResult]:
        """找出与指定笔记相似的笔记"""
        if note_name not in self.notes:
            return []
        
        target_note = self.notes[note_name]
        target_vec = self._get_tfidf_vector(target_note)
        
        results = []
        
        for other_name, other_note in self.notes.items():
            if other_name == note_name:
                continue
            
            # 计算内容相似度
            other_vec = self._get_tfidf_vector(other_note)
            content_sim = self._cosine_similarity(target_vec, other_vec)
            
            # 计算标题相似度
            title_sim = self._title_similarity(target_note.name, other_note.name)
            
            # 计算标签相似度
            tag_sim = self._tag_similarity(target_note.tags, other_note.tags)
            
            # 综合相似度（加权）
            total_sim = content_sim * 0.6 + title_sim * 0.2 + tag_sim * 0.2
            
            if total_sim >= self.min_similarity:
                # 找出共同的关键词
                common = set(target_vec.keys()) & set(other_vec.keys())
                common_words = sorted(common, 
                                     key=lambda w: target_vec[w] + other_vec[w], 
                                     reverse=True)[:10]
                
                # 判断主要相似原因
                if content_sim > 0.5:
                    reason = 'content'
                elif title_sim > 0.3:
                    reason = 'title'
                elif tag_sim > 0.3:
                    reason = 'tags'
                else:
                    reason = 'mixed'
                
                results.append(SimilarityResult(
                    note1=note_name,
                    note2=other_name,
                    similarity=total_sim,
                    common_words=common_words,
                    reason=reason
                ))
        
        # 按相似度排序
        results.sort(key=lambda x: x.similarity, reverse=True)
        
        return results[:top_n]
    
    def find_all_similar_pairs(self, min_similarity: float = None) -> List[SimilarityResult]:
        """找出所有相似的笔记对"""
        if min_similarity is None:
            min_similarity = self.min_similarity
        
        print("🔄 Computing TF-IDF vectors...")
        # 预计算 IDF
        self._calculate_idf()
        
        # 预计算所有笔记的向量
        for note in self.notes.values():
            self._get_tfidf_vector(note)
        
        results = []
        note_names = list(self.notes.keys())
        total_pairs = len(note_names) * (len(note_names) - 1) // 2
        
        print(f"🔍 Analyzing {total_pairs} note pairs...")
        
        processed = 0
        for i, name1 in enumerate(note_names):
            note1 = self.notes[name1]
            vec1 = self._word_vectors[name1]
            
            for name2 in note_names[i + 1:]:
                note2 = self.notes[name2]
                vec2 = self._word_vectors[name2]
                
                # 计算各维度相似度
                content_sim = self._cosine_similarity(vec1, vec2)
                title_sim = self._title_similarity(name1, name2)
                tag_sim = self._tag_similarity(note1.tags, note2.tags)
                
                # 综合相似度
                total_sim = content_sim * 0.6 + title_sim * 0.2 + tag_sim * 0.2
                
                if total_sim >= min_similarity:
                    common = set(vec1.keys()) & set(vec2.keys())
                    common_words = sorted(common,
                                        key=lambda w: vec1[w] + vec2[w],
                                        reverse=True)[:10]
                    
                    if content_sim > 0.5:
                        reason = 'content'
                    elif title_sim > 0.3:
                        reason = 'title'
                    elif tag_sim > 0.3:
                        reason = 'tags'
                    else:
                        reason = 'mixed'
                    
                    results.append(SimilarityResult(
                        note1=name1,
                        note2=name2,
                        similarity=total_sim,
                        common_words=common_words,
                        reason=reason
                    ))
                
                processed += 1
                if processed % 1000 == 0:
                    print(f"  Processed {processed}/{total_pairs} pairs...")
        
        # 按相似度排序
        results.sort(key=lambda x: x.similarity, reverse=True)
        
        print(f"✅ Found {len(results)} similar pairs")
        
        return results
    
    def find_potential_duplicates(self, threshold: float = 0.7) -> List[SimilarityResult]:
        """找出可能重复的笔记（高相似度）"""
        all_similar = self.find_all_similar_pairs(min_similarity=threshold)
        
        # 过滤出高相似度的
        duplicates = [s for s in all_similar if s.similarity >= threshold]
        
        return duplicates
    
    def find_related_unlinked(self) -> List[Tuple[SimilarityResult, bool]]:
        """找出相关但未链接的笔记"""
        all_similar = self.find_all_similar_pairs()
        
        results = []
        for sim in all_similar:
            note1 = self.notes[sim.note1]
            note2 = self.notes[sim.note2]
            
            # 检查是否已有链接
            has_link = (sim.note2 in note1.outgoing_links or 
                       sim.note1 in note2.outgoing_links)
            
            if not has_link:
                results.append((sim, False))
            else:
                results.append((sim, True))
        
        return results
    
    def suggest_merges(self, min_similarity: float = 0.6) -> List[Tuple[str, str, float, List[str]]]:
        """建议合并的笔记"""
        duplicates = self.find_potential_duplicates(threshold=min_similarity)
        
        suggestions = []
        for dup in duplicates:
            note1 = self.notes[dup.note1]
            note2 = self.notes[dup.note2]
            
            # 如果两个笔记都很短，更可能需要合并
            if note1.word_count < 200 and note2.word_count < 200:
                reasons = ["两个笔记都很短", f"内容相似度: {dup.similarity:.1%}"]
                suggestions.append((dup.note1, dup.note2, dup.similarity, reasons))
            elif dup.similarity > 0.8:
                reasons = [f"内容高度相似: {dup.similarity:.1%}"]
                if dup.reason == 'title':
                    reasons.append("标题相似")
                suggestions.append((dup.note1, dup.note2, dup.similarity, reasons))
        
        return suggestions
    
    def get_statistics(self, results: List[SimilarityResult]) -> Dict:
        """获取相似度统计"""
        if not results:
            return {
                'total_pairs': 0,
                'high_similarity': 0,
                'medium_similarity': 0,
                'low_similarity': 0,
                'avg_similarity': 0
            }
        
        similarities = [r.similarity for r in results]
        
        return {
            'total_pairs': len(results),
            'high_similarity': len([s for s in similarities if s >= 0.7]),
            'medium_similarity': len([s for s in similarities if 0.5 <= s < 0.7]),
            'low_similarity': len([s for s in similarities if s < 0.5]),
            'avg_similarity': sum(similarities) / len(similarities),
            'max_similarity': max(similarities),
            'min_similarity': min(similarities)
        }


if __name__ == '__main__':
    print("This module should be imported, not run directly.")
