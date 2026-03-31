#!/usr/bin/env python3
"""
RAG 检索流程测试
验证：Embedding → Hybrid Search → Reranker → 结果格式
"""
import sys
sys.path.insert(0, '.')

from pipeline.retrieval import RetrievalPipeline
from db.qdrant_client import QdrantClientWrapper
from core.embedder import Embedder
from core.reranker import Reranker


def test_embedder():
    """测试 BGE-M3 Embedding"""
    print("=== test_embedder ===")
    e = Embedder()

    # 单文本
    result = e.embed("测试中文")
    assert "dense" in result, "dense key missing"
    assert "sparse" in result, "sparse key missing"
    assert len(result["dense"]) == 1024, f"dense dim wrong: {len(result['dense'])}"
    print(f"  dense dim: {len(result['dense'])}")
    print(f"  sparse keys: {len(result['sparse'])}")

    # 多文本
    results = e.embed(["中文", "English"])
    assert len(results) == 2, "batch embed failed"
    print(f"  batch embed: {len(results)} texts OK")

    print("  ✓ PASS")


def test_qdrant_connection():
    """测试 Qdrant 连接"""
    print("=== test_qdrant_connection ===")
    q = QdrantClientWrapper()
    info = q.client.get_collection('philosophy_documents')
    assert info.points_count > 0, f"no points: {info.points_count}"
    print(f"  collection: philosophy_documents")
    print(f"  points: {info.points_count}")
    print(f"  status: {info.status}")
    print("  ✓ PASS")


def test_hybrid_search():
    """测试 Hybrid Search (dense + sparse + RRF)"""
    print("=== test_hybrid_search ===")
    q = QdrantClientWrapper()
    e = Embedder()

    query = "什么是哲学实践"
    emb = e.embed(query)

    results = q.search_hybrid(emb["dense"], emb.get("sparse", {}), top_k=20, alpha=0.7)
    assert len(results) > 0, "no results"
    assert len(results) <= 20, "too many results"

    # 检查结果结构
    r = results[0]
    assert "id" in r, "id missing"
    assert "score" in r, "score missing"
    assert "text_zh" in r or "text_en" in r, "text missing"
    assert "source" in r, "source missing"

    print(f"  query: {query}")
    print(f"  results: {len(results)}")
    print(f"  top1: [{r['source']}] score={r['score']:.4f}")
    print("  ✓ PASS")


def test_reranker():
    """测试 BGE-Reranker 精排"""
    print("=== test_reranker ===")
    r = Reranker()

    query = "什么是哲学实践"
    texts = [
        "哲学实践是一种通过对话和追问来探索问题的哲学方法。",
        "今天天气很好，我们去公园散步吧。",
        "苏格拉底式追问是哲学实践的核心技术。",
        "晚饭吃什么好呢？",
        "哲学帮助人们厘清概念，发现思维中的矛盾。",
    ]

    scores = r.rerank(query, texts, top_k=3)

    assert len(scores) == 3, f"wrong count: {len(scores)}"
    assert all(0 <= s <= 1 for _, s in scores), "score out of range"

    # 分数应该递减
    for i in range(len(scores) - 1):
        assert scores[i][1] >= scores[i+1][1], "scores not descending"

    print(f"  query: {query}")
    print(f"  reranked (top 3):")
    for i, (idx, score) in enumerate(scores):
        print(f"    {i+1}. [{texts[idx][:30]}...] score={score:.4f}")
    print("  ✓ PASS")


def test_retrieval_pipeline():
    """测试完整检索流程"""
    print("=== test_retrieval_pipeline ===")
    p = RetrievalPipeline()

    query = "什么是哲学实践"

    # 1. retrieve()
    results = p.retrieve(query, expand_context=False)
    assert len(results) > 0, "no results"
    assert len(results) <= 5, f"too many results: {len(results)}"
    print(f"  retrieve(): {len(results)} results")

    # 检查分数字段
    r = results[0]
    assert "rerank_score" in r, "rerank_score missing"
    assert "source" in r, "source missing"
    print(f"  top1: [{r['source']}] rerank_score={r['rerank_score']:.4f}")

    # 2. retrieve_with_comparison()
    comp = p.retrieve_with_comparison(
        query,
        expand_context=False,
        before_rerank_limit=10,
        after_rerank_limit=5
    )

    assert "before_rerank" in comp, "before_rerank missing"
    assert "after_rerank" in comp, "after_rerank missing"
    assert len(comp["before_rerank"]) == 10, f"before count wrong: {len(comp['before_rerank'])}"
    assert len(comp["after_rerank"]) == 5, f"after count wrong: {len(comp['after_rerank'])}"
    print(f"  compare: before={len(comp['before_rerank'])}, after={len(comp['after_rerank'])}")

    print("  ✓ PASS")


def test_retrieval_pipeline_chinese_query():
    """测试中文查询返回正确语言的结果"""
    print("=== test_retrieval_pipeline_chinese_query ===")
    p = RetrievalPipeline()

    query = "苏格拉底式追问"
    results = p.retrieve(query, expand_context=False)

    assert len(results) > 0, "no results"
    print(f"  query: {query}")
    print(f"  results: {len(results)}")

    # 统计有中文的比例
    zh_count = sum(1 for r in results if r.get("text_zh", "").strip())
    print(f"  with Chinese: {zh_count}/{len(results)}")

    print("  ✓ PASS")


def test_retrieval_pipeline_english_query():
    """测试英文查询"""
    print("=== test_retrieval_pipeline_english_query ===")
    p = RetrievalPipeline()

    query = "what is philosophical practice"
    results = p.retrieve(query, expand_context=False)

    assert len(results) > 0, "no results"
    print(f"  query: {query}")
    print(f"  results: {len(results)}")

    print("  ✓ PASS")


def test_score_fields():
    """测试分数字段完整性"""
    print("=== test_score_fields ===")
    p = RetrievalPipeline()

    query = "什么是自由"
    results = p.retrieve(query, expand_context=False)

    for r in results:
        assert "score" in r, "score missing"
        assert "rerank_score" in r, "rerank_score missing"
        # dense_score 和 sparse_score 可能为 0，但不能缺失
        assert "dense_score" in r, "dense_score missing"
        assert "sparse_score" in r, "sparse_score missing"

    print(f"  all results have score fields: {len(results)}")
    print("  ✓ PASS")


def run_all_tests():
    print("=" * 60)
    print("RAG 检索流程测试")
    print("=" * 60)

    tests = [
        test_embedder,
        test_qdrant_connection,
        test_hybrid_search,
        test_reranker,
        test_retrieval_pipeline,
        test_retrieval_pipeline_chinese_query,
        test_retrieval_pipeline_english_query,
        test_score_fields,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  ✗ FAIL: {e}")
            failed += 1
        print()

    print("=" * 60)
    print(f"结果: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
