"""Knowledge-base loader and retrieval engine.

Implements high-precision error-code indexing and BM25 full-text ranking
in pure Python with automatic handling of deprecated/superseded articles.
"""
from collections import Counter
import math
from pathlib import Path
import re

KB_DIR = Path(__file__).resolve().parent.parent / "kb"


def _parse(text: str) -> tuple[dict, str]:
    """Parse YAML front matter and markdown body."""
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        k, _, v = line.partition(":")
        v = v.strip()
        if v.startswith("[") and v.endswith("]"):
            v = [x.strip() for x in v[1:-1].split(",") if x.strip()]
        meta[k.strip()] = v
    return meta, text[m.end():]


def load_kb() -> list[dict]:
    """Return a list of {"id", "meta", "body"} for every article."""
    out = []
    for p in sorted(KB_DIR.glob("*.md")):
        meta, body = _parse(p.read_text(encoding="utf-8"))
        out.append({"id": meta.get("id", p.stem), "meta": meta, "body": body})
    return out


def _tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric word tokenizer."""
    return re.findall(r"[a-z0-9_-]+", text.lower())


class KBStore:
    """In-memory search engine for knowledge base with BM25 and error-code indexing."""

    def __init__(self, kb_articles: list[dict]):
        self.articles = kb_articles
        self.by_id: dict[str, dict] = {a["id"]: a for a in kb_articles}
        self.error_code_to_ids: dict[str, list[str]] = {}
        self.superseded_by: dict[str, str] = {}

        # 1. Index error codes and deprecation mappings
        for a in kb_articles:
            art_id = a["id"]
            meta = a["meta"]
            codes = meta.get("error_codes", [])
            if isinstance(codes, str) and codes:
                codes = [codes]
            for c in codes:
                c_clean = c.strip().upper()
                if c_clean:
                    self.error_code_to_ids.setdefault(c_clean, []).append(art_id)

            if meta.get("status") == "deprecated" and meta.get("superseded_by"):
                self.superseded_by[art_id] = meta["superseded_by"]

        # 2. Build BM25 index over title, module, and body
        self.doc_ids = []
        self.doc_lengths = []
        self.doc_term_freqs = []  # list of Counter
        self.doc_freqs = Counter()  # word -> number of docs containing word

        for a in kb_articles:
            art_id = a["id"]
            meta = a["meta"]
            # Boost title and module weight by repeating tokens
            title_tokens = _tokenize(meta.get("title", "")) * 3
            module_tokens = _tokenize(meta.get("module", "")) * 2
            body_tokens = _tokenize(a["body"])
            all_tokens = title_tokens + module_tokens + body_tokens

            counts = Counter(all_tokens)
            self.doc_ids.append(art_id)
            self.doc_lengths.append(len(all_tokens))
            self.doc_term_freqs.append(counts)
            for word in counts.keys():
                self.doc_freqs[word] += 1

        self.N = len(self.doc_ids)
        self.avgdl = sum(self.doc_lengths) / max(self.N, 1)

    def _bm25_score(self, doc_idx: int, query_tokens: list[str], k1: float = 1.5, b: float = 0.75) -> float:
        score = 0.0
        doc_len = self.doc_lengths[doc_idx]
        tf_dict = self.doc_term_freqs[doc_idx]

        for token in query_tokens:
            if token not in tf_dict:
                continue
            df = self.doc_freqs.get(token, 0)
            # Standard Lucene/BM25 IDF
            idf = math.log(1.0 + (self.N - df + 0.5) / (df + 0.5))
            tf = tf_dict[token]
            num = tf * (k1 + 1.0)
            denom = tf + k1 * (1.0 - b + b * (doc_len / self.avgdl))
            score += idf * (num / denom)
        return score

    def search(
        self,
        query: str,
        module: str | None = None,
        error_code: str | None = None,
        top_k: int = 3,
    ) -> list[dict]:
        """Search articles by error code or BM25 query with automatic deprecation resolution."""
        results = []
        seen_ids = set()

        # 1. Exact error code match (highest precision)
        # Check error_code parameter or extract E-#### from query text
        codes_to_check = set()
        if error_code:
            codes_to_check.add(error_code.strip().upper())
        for found in re.findall(r"\bE-\d+\b", query.upper()):
            codes_to_check.add(found)

        for code in codes_to_check:
            for art_id in self.error_code_to_ids.get(code, []):
                # Resolve deprecation if superseded
                resolved_id = self.superseded_by.get(art_id, art_id)
                if resolved_id not in seen_ids and resolved_id in self.by_id:
                    seen_ids.add(resolved_id)
                    art = self.by_id[resolved_id]
                    results.append({
                        "id": resolved_id,
                        "title": art["meta"].get("title"),
                        "module": art["meta"].get("module"),
                        "type": art["meta"].get("type"),
                        "status": art["meta"].get("status"),
                        "match_reason": f"Exact match for error code {code}",
                        "preview": art["body"][:250].strip() + "...",
                        "score": 100.0,
                    })

        # 2. BM25 search for keyword relevance
        q_tokens = _tokenize(query)
        if module:
            q_tokens += _tokenize(module) * 2

        scores = []
        for i, art_id in enumerate(self.doc_ids):
            resolved_id = self.superseded_by.get(art_id, art_id)
            if resolved_id in seen_ids or resolved_id not in self.by_id:
                continue
            s = self._bm25_score(i, q_tokens)
            if s > 0:
                scores.append((s, resolved_id))

        scores.sort(key=lambda x: x[0], reverse=True)
        for s, resolved_id in scores:
            if len(results) >= top_k:
                break
            if resolved_id not in seen_ids:
                seen_ids.add(resolved_id)
                art = self.by_id[resolved_id]
                results.append({
                    "id": resolved_id,
                    "title": art["meta"].get("title"),
                    "module": art["meta"].get("module"),
                    "type": art["meta"].get("type"),
                    "status": art["meta"].get("status"),
                    "match_reason": "BM25 keyword relevance",
                    "preview": art["body"][:250].strip() + "...",
                    "score": round(s, 2),
                })

        return results

    def get_article(self, article_id: str) -> dict | None:
        """Fetch full article content, following superseded_by if deprecated."""
        art_id = article_id.strip()
        note = None
        if art_id in self.superseded_by:
            note = f"Article {art_id} is deprecated and was superseded by {self.superseded_by[art_id]}."
            art_id = self.superseded_by[art_id]

        art = self.by_id.get(art_id)
        if not art:
            return None

        return {
            "id": art["id"],
            "title": art["meta"].get("title"),
            "module": art["meta"].get("module"),
            "type": art["meta"].get("type"),
            "status": art["meta"].get("status"),
            "error_codes": art["meta"].get("error_codes", []),
            "related": art["meta"].get("related", []),
            "note": note,
            "body": art["body"].strip(),
        }


if __name__ == "__main__":
    print("Testing pure Python KB store and BM25 retrieval...")
    raw_articles = load_kb()
    kb_store = KBStore(raw_articles)
    print(f"PASS: Loaded and indexed {len(kb_store.articles)} articles")

    # Test 1: Error code search
    res = kb_store.search("System thrown E-8174 during login")
    assert len(res) > 0, "Failed to find article by error code"
    print(f"PASS: Found article for E-8174 -> {res[0]['id']} ({res[0]['title']})")

    # Test 2: Keyword search with module
    res2 = kb_store.search("spend cube refresh does not trigger", module="Spend Analytics")
    assert len(res2) > 0, "Failed keyword search"
    print(f"PASS: Found article for spend cube refresh -> {res2[0]['id']} ({res2[0]['title']})")

    # Test 3: Get full article & related links
    policy_doc = kb_store.get_article("KB-2914")
    assert policy_doc is not None
    print(f"PASS: Fetched {policy_doc['id']}: '{policy_doc['title']}', related: {policy_doc['related']}")

    print("\nAll KB retrieval tests passed successfully!")
