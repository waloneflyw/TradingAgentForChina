# -*- coding: utf-8 -*-
"""用 BM25 实现的「情境记忆库」（Financial situation memory）。

【作用】每个需要「从错误中学习」的角色（多头/空头/交易员/研究经理/组合经理）
各持一个本类实例。它存「（当时的市场情境 → 经验教训建议）」键值对，下次遇到
相似情境时检索最相关的几条经验喂给 LLM。

【为什么选 BM25】经典的词频相关性检索，纯本地计算、不需要 embedding API、
离线可用。对「找相似金融情境」这种任务，词面重叠已足够好用，且零成本。

【A股 MVP 处理】本阶段只实例化空对象（get_memories 自然返回 []），不接
reflection.py（复盘写经验留到 L3）。因此 rank_bm25 也改成「用到才 import」：
不装也不影响启动，只有真正 add_situations 时才会触发导入。
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple


class FinancialSituationMemory:
    """Memory system for storing and retrieving financial situations using BM25."""

    def __init__(self, name: str, config: Optional[dict] = None):
        """Initialize the memory system.

        Args:
            name: 记忆实例名（标识是哪个角色在用）
            config: 配置 dict（保留参数以兼容接口，BM25 用不到）
        """
        self.name = name
        self.documents: List[str] = []
        self.recommendations: List[str] = []
        self.bm25 = None

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text for BM25 indexing.

        简单分词：转小写 + 按非字母数字切分。中文场景后续换 jieba（L3 再改）。
        """
        tokens = re.findall(r"\b\w+\b", text.lower())
        return tokens

    def _rebuild_index(self):
        """Rebuild the BM25 index after adding documents."""
        if self.documents:
            # 延迟导入：MVP 空记忆不会走到这里，rank_bm25 未安装也不报错
            from rank_bm25 import BM25Okapi

            tokenized_docs = [self._tokenize(doc) for doc in self.documents]
            self.bm25 = BM25Okapi(tokenized_docs)
        else:
            self.bm25 = None

    def add_situations(self, situations_and_advice: List[Tuple[str, str]]):
        """Add financial situations and their corresponding advice.

        Args:
            situations_and_advice: (情境, 建议) 元组列表
        """
        for situation, recommendation in situations_and_advice:
            self.documents.append(situation)
            self.recommendations.append(recommendation)

        self._rebuild_index()

    def get_memories(self, current_situation: str, n_matches: int = 1) -> List[dict]:
        """Find matching recommendations using BM25 similarity.

        把当前情境 tokenize 后用 BM25 给所有历史情境打分，取最高 n_matches 条。
        MVP 空记忆直接返回 []，各 Agent 拿到空列表就跳过「过往经验」注入。

        Returns:
            List of dicts: matched_situation / recommendation / similarity_score
        """
        if not self.documents or self.bm25 is None:
            return []

        query_tokens = self._tokenize(current_situation)
        scores = self.bm25.get_scores(query_tokens)

        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:n_matches]

        results = []
        max_score = max(scores) if max(scores) > 0 else 1

        for idx in top_indices:
            normalized_score = scores[idx] / max_score if max_score > 0 else 0
            results.append({
                "matched_situation": self.documents[idx],
                "recommendation": self.recommendations[idx],
                "similarity_score": normalized_score,
            })

        return results

    def clear(self):
        """Clear all stored memories."""
        self.documents = []
        self.recommendations = []
        self.bm25 = None
