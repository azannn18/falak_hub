"""
HILTRON FalakHub — Lightweight In-Memory Knowledge Retriever (BM25 + Keyword Boost).
Zero heavy dependencies, blazing fast (<5ms), works 100% offline and online.
"""

import json
import math
import os
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from collections import Counter

# Indonesian common stopwords including interrogative & auxiliary words
STOPWORDS_ID = {
    "yang", "untuk", "pada", "ke", "para", "namun", "menurut", "antara", "dia", "dua",
    "ia", "seperti", "jika", "jikalau", "sehingga", "kembali", "dan", "tidak", "ini",
    "karena", "kepada", "oleh", "saat", "harus", "sementara", "setelah", "belum",
    "kami", "sekitar", "bagi", "serta", "di", "dari", "telah", "sebagai", "masih",
    "hal", "ketika", "adalah", "itu", "dalam", "bisa", "bahwa", "atau", "hanya",
    "kita", "dengan", "akan", "juga", "ada", "mereka", "sudah", "saya", "kamu",
    "apakah", "bagaimana", "mengapa", "kenapa", "kapan", "siapa", "mana", "apa",
    "berapa", "kalau", "lalu", "terus", "tentang", "mengenai", "saja", "tahukah",
    "secara", "sebutkan", "jelaskan", "berikan", "menurutmu", "adanya", "sebuah",
    "kasih", "tolong", "mohon", "kira", "hari", "ini", "cara", "tata", "nama", "tahun", "pasti"
}


class BM25Retriever:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.documents: List[Dict[str, Any]] = []
        self.doc_tokens: List[List[str]] = []
        self.doc_lengths: List[int] = []
        self.avg_dl: float = 0.0
        self.df: Counter = Counter()
        self.idf: Dict[str, float] = {}
        self.num_docs: int = 0

    @staticmethod
    def tokenize(text: str) -> List[str]:
        """Tokenize text into lowercase alphanumeric words, filtering out stopwords."""
        words = re.findall(r"\b[a-zA-Z0-9_\-']+\b", text.lower())
        return [w for w in words if len(w) > 1 and w not in STOPWORDS_ID]

    def build_index(self, documents: List[Dict[str, Any]]):
        self.documents = documents
        self.num_docs = len(documents)
        if self.num_docs == 0:
            return

        self.doc_tokens = []
        self.doc_lengths = []
        self.df = Counter()

        total_length = 0
        for doc in documents:
            kw_str = " ".join(doc.get("kata_kunci", []))
            full_text = f"{doc.get('topik', '')} {kw_str} {doc.get('ringkasan_singkat', '')} {doc.get('penjelasan_lengkap', '')}"
            tokens = self.tokenize(full_text)
            self.doc_tokens.append(tokens)
            dl = len(tokens)
            self.doc_lengths.append(dl)
            total_length += dl

            unique_tokens = set(tokens)
            for t in unique_tokens:
                self.df[t] += 1

        self.avg_dl = total_length / self.num_docs if self.num_docs > 0 else 1.0

        # Precompute IDF with Robertson-Spärck Jones formula
        self.idf = {}
        for term, freq in self.df.items():
            self.idf[term] = math.log(1.0 + (self.num_docs - freq + 0.5) / (freq + 0.5))

    def score(self, query: str) -> List[Tuple[float, Dict[str, Any]]]:
        q_tokens = self.tokenize(query)
        q_raw = query.lower().strip()
        if not q_tokens or self.num_docs == 0:
            return []

        scores: List[float] = [0.0] * self.num_docs
        for i, doc in enumerate(self.documents):
            # 1. Base BM25 score
            doc_tf = Counter(self.doc_tokens[i])
            doc_len = self.doc_lengths[i]
            bm25_score = 0.0

            matched_q_tokens = [t for t in q_tokens if t in doc_tf]

            for q_term in q_tokens:
                if q_term in doc_tf:
                    tf = doc_tf[q_term]
                    idf_val = self.idf.get(q_term, 0.0)
                    numerator = tf * (self.k1 + 1.0)
                    denominator = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / self.avg_dl))
                    bm25_score += idf_val * (numerator / denominator)

            # 2. Heuristic boost: exact keyword phrase match
            kw_boost = 0.0
            keywords = [k.lower() for k in doc.get("kata_kunci", [])]
            has_exact_phrase = False
            for kw in keywords:
                if kw in q_raw:
                    kw_boost += 6.0
                    has_exact_phrase = True
                else:
                    kw_tokens = set(self.tokenize(kw))
                    overlap = set(q_tokens) & kw_tokens
                    if overlap:
                        kw_boost += 1.5 * len(overlap)

            # 3. Topic token match boost
            topik_tokens = set(self.tokenize(doc.get("topik", "")))
            topik_overlap = set(q_tokens) & topik_tokens
            if topik_overlap:
                kw_boost += 2.0 * len(topik_overlap)

            final_score = bm25_score + kw_boost

            # Filter single incidental word matches when query is long (anti false-positive)
            if len(q_tokens) >= 3 and len(set(matched_q_tokens)) <= 1 and not has_exact_phrase:
                final_score = 0.5

            scores[i] = final_score

        # Pair scores with documents and sort descending
        paired = [(scores[i], self.documents[i]) for i in range(self.num_docs) if scores[i] > 0.5]
        paired.sort(key=lambda x: x[0], reverse=True)
        return paired


class FalakKnowledgeRetriever:
    """Manages knowledge base directories, indexing, and retrieval for HILMI."""

    def __init__(self, knowledge_dir: Optional[Path] = None):
        if knowledge_dir is None:
            knowledge_dir = Path(__file__).resolve().parent.parent / "knowledge"
        self.knowledge_dir = knowledge_dir
        self.documents: List[Dict[str, Any]] = []
        self.retriever = BM25Retriever()
        self.load_knowledge_base()

    def load_knowledge_base(self):
        """Loads all JSON files from the knowledge directory and builds the BM25 index."""
        self.documents = []
        if not self.knowledge_dir.exists():
            return

        for file_path in self.knowledge_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        for item in data:
                            item["_source_file"] = file_path.name
                            self.documents.append(item)
                    elif isinstance(data, dict):
                        data["_source_file"] = file_path.name
                        self.documents.append(data)
            except Exception as e:
                print(f"[KnowledgeRetriever] Error loading {file_path}: {e}")

        self.retriever.build_index(self.documents)

    def retrieve(self, query: str, top_k: int = 3, min_score: float = 1.0) -> List[Dict[str, Any]]:
        """
        Retrieves top_k most relevant knowledge entries.
        Returns entries that meet or exceed min_score.
        """
        scored_docs = self.retriever.score(query)
        results = []
        for score, doc in scored_docs[:top_k]:
            if score >= min_score:
                doc_copy = dict(doc)
                doc_copy["_retrieval_score"] = round(score, 3)
                results.append(doc_copy)
        return results

    def format_for_prompt(self, docs: List[Dict[str, Any]]) -> str:
        """Formats retrieved documents into a clean 'KONTEKS TERPERCAYA' section for Gemini LLM."""
        if not docs:
            return ""

        formatted_lines = [
            "=== KONTEKS TERPERCAYA ILMU FALAK (PRIORITAS UTAMA JAWABAN) ==="
        ]
        for i, doc in enumerate(docs, 1):
            formatted_lines.append(
                f"\n[Dokumen {i}]: {doc.get('topik', 'Falak')} (Sumber: {doc.get('sumber', 'Kemenag RI')})"
            )
            formatted_lines.append(f"Ringkasan: {doc.get('ringkasan_singkat', '')}")
            formatted_lines.append(f"Rincian: {doc.get('penjelasan_lengkap', '')}")

        formatted_lines.append(
            "\nPetunjuk: Utamakan informasi ilmiah dan fikih di atas untuk menjawab. "
            "Jangan mengarang data atau hukum di luar konteks terpercaya ini."
        )
        return "\n".join(formatted_lines)
