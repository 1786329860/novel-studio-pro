"""硅基流动 Embedding 客户端，使用 BAAI/bge-m3 模型"""
from __future__ import annotations
import os
import httpx
import math


class EmbeddingClient:
    def __init__(self):
        self.api_key = os.getenv("SILICONFLOW_API_KEY", "")
        self.base_url = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
        self.model = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """批量文本向量化"""
        if not self.api_key or not texts:
            return []

        # 硅基流动兼容 OpenAI 格式
        url = f"{self.base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        body = {
            "model": self.model,
            "input": texts,
            "encoding_format": "float"
        }

        # 分批处理，每批最多 20 条
        all_embeddings = []
        batch_size = 20
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            body["input"] = batch
            resp = httpx.post(url, headers=headers, json=body, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            # 按 index 排序
            sorted_data = sorted(data["data"], key=lambda x: x["index"])
            all_embeddings.extend([item["embedding"] for item in sorted_data])

        return all_embeddings

    def embed_query(self, text: str) -> list[float]:
        """单条查询向量化"""
        results = self.embed_texts([text])
        return results[0] if results else []

    def cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """计算余弦相似度"""
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def search_similar(self, query: str, documents: list[dict], top_k: int = 5, score_threshold: float = 0.3) -> list[dict]:
        """
        语义搜索：找到与 query 最相似的文档
        documents: [{"id": str, "text": str, "embedding": list[float]|None, ...}, ...]
        返回: [{"id": str, "text": str, "score": float, ...}, ...] 按 score 降序
        """
        if not query or not documents:
            return []

        query_vec = self.embed_query(query)
        if not query_vec:
            return []

        results = []
        for doc in documents:
            doc_vec = doc.get("embedding")
            if doc_vec:
                score = self.cosine_similarity(query_vec, doc_vec)
                if score >= score_threshold:
                    result = {**doc, "score": round(score, 4)}
                    results.append(result)

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]


embedding_client = EmbeddingClient()
