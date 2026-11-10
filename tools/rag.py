from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path
from typing import TypedDict

import chromadb


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_STANDARDS_DIR = ROOT_DIR / "data" / "standards"
DEFAULT_CHROMA_DIR = ROOT_DIR / "storage" / "chroma"
COLLECTION_NAME = "python_standards"
VECTOR_SIZE = 384


class RetrievedChunk(TypedDict):
    source: str
    text: str
    distance: float


def _tokens(text: str) -> list[str]:
    raw_tokens = re.findall(
        r"[a-zA-Z_][a-zA-Z0-9_]*|\d+|[\u4e00-\u9fff]+", text.lower()
    )
    tokens: list[str] = []
    for token in raw_tokens:
        tokens.append(token)
        if re.fullmatch(r"[\u4e00-\u9fff]+", token):
            tokens.extend(
                token[index:index + 2]
                for index in range(max(0, len(token) - 1))
            )
    return tokens


def hashing_embedding(text: str) -> list[float]:
    vector = [0.0] * VECTOR_SIZE
    for token in _tokens(text):
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "big") % VECTOR_SIZE
        vector[index] += 1.0 if digest[4] & 1 else -1.0
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        vector[0] = 1.0
        return vector
    return [value / norm for value in vector]


def _split_chunks(text: str, max_chars: int = 900) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(
                paragraph[index:index + max_chars]
                for index in range(0, len(paragraph), max_chars)
            )
        elif current and len(current) + len(paragraph) > max_chars:
            chunks.append(current)
            current = paragraph
        else:
            current = f"{current}\n\n{paragraph}".strip()
    if current:
        chunks.append(current)
    return chunks


class StandardsRAG:
    def __init__(
        self,
        standards_dir: Path = DEFAULT_STANDARDS_DIR,
        chroma_dir: Path = DEFAULT_CHROMA_DIR,
    ) -> None:
        self.standards_dir = standards_dir
        self.chroma_dir = chroma_dir
        self.chroma_dir.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(self.chroma_dir))
        self.collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def index_standards(self) -> int:
        paths = sorted(self.standards_dir.glob("*.md"))
        if not paths:
            raise FileNotFoundError(f"规范目录中没有 Markdown 文件：{self.standards_dir}")

        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict[str, str]] = []
        embeddings: list[list[float]] = []
        for path in paths:
            for index, chunk in enumerate(_split_chunks(path.read_text(encoding="utf-8"))):
                digest = hashlib.sha1(
                    f"{path.name}:{index}:{chunk}".encode("utf-8")
                ).hexdigest()
                ids.append(digest)
                documents.append(chunk)
                metadatas.append({"source": path.name})
                embeddings.append(hashing_embedding(chunk))

        self.collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
        )
        return len(documents)

    def search(self, query: str, limit: int = 4) -> list[RetrievedChunk]:
        if self.collection.count() == 0:
            return []
        result = self.collection.query(
            query_embeddings=[hashing_embedding(query)],
            n_results=max(1, min(limit, 10)),
            include=["documents", "metadatas", "distances"],
        )
        documents = (result.get("documents") or [[]])[0] or []
        metadatas = (result.get("metadatas") or [[]])[0] or []
        distances = (result.get("distances") or [[]])[0] or []
        chunks: list[RetrievedChunk] = []
        for index, text in enumerate(documents):
            metadata = metadatas[index] if index < len(metadatas) else {}
            distance = distances[index] if index < len(distances) else 0.0
            chunks.append({
                "source": str((metadata or {}).get("source", "unknown")),
                "text": str(text),
                "distance": float(distance or 0.0),
            })
        return chunks
