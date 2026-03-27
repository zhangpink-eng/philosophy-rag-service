#!/usr/bin/env python3
"""
Export chunks to HTML viewer.
Usage: python scripts/view_chunks.py
"""

import json
from pathlib import Path
from db.qdrant_client import QdrantClientWrapper

def export_chunks_to_html(output_path: str = "chunks_viewer.html"):
    """Export all chunks to an HTML file with English/Chinese side-by-side view."""

    qdrant = QdrantClientWrapper()

    # Search for all points (using a dummy vector to get all)
    from core.embedder import Embedder
    embedder = Embedder()

    # Get all chunks by searching with a common word
    results = qdrant.search_dense(embedder.embed("the")["dense"], top_k=1000)

    # Group by source file
    chunks_by_source = {}
    for r in results:
        source = r["source"]
        if source not in chunks_by_source:
            chunks_by_source[source] = []
        chunks_by_source[source].append(r)

    # Generate HTML
    html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chunks Viewer - 中英文对照</title>
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }
        h1 {
            text-align: center;
            color: #333;
            margin-bottom: 30px;
        }
        .file-section {
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .file-title {
            font-size: 1.4em;
            color: #2C3E50;
            border-bottom: 2px solid #2C3E50;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }
        .chunk {
            border: 1px solid #e0e0e0;
            border-radius: 6px;
            margin-bottom: 15px;
            overflow: hidden;
        }
        .chunk-header {
            background: #34495E;
            color: white;
            padding: 8px 15px;
            font-size: 0.85em;
            display: flex;
            justify-content: space-between;
        }
        .chunk-content {
            display: grid;
            grid-template-columns: 1fr 1fr;
        }
        .lang-section {
            padding: 15px;
        }
        .lang-section.english {
            background: #fafafa;
            border-right: 1px solid #e0e0e0;
        }
        .lang-section.chinese {
            background: #f0f7ff;
        }
        .lang-label {
            font-weight: bold;
            color: #666;
            font-size: 0.8em;
            margin-bottom: 8px;
        }
        .english .lang-label { color: #555; }
        .chinese .lang-label { color: #2C3E50; }
        .text {
            font-size: 0.95em;
            color: #333;
            white-space: pre-wrap;
            word-break: break-word;
        }
        .chinese .text {
            font-family: "PingFang SC", "Microsoft YaHei", sans-serif;
        }
        .empty {
            color: #999;
            font-style: italic;
        }
        .stats {
            text-align: center;
            color: #666;
            margin-bottom: 30px;
            font-size: 0.9em;
        }
        .search-box {
            text-align: center;
            margin-bottom: 30px;
        }
        .search-box input {
            width: 100%;
            max-width: 500px;
            padding: 12px 20px;
            font-size: 16px;
            border: 2px solid #ddd;
            border-radius: 25px;
            outline: none;
        }
        .search-box input:focus {
            border-color: #2C3E50;
        }
        @media (max-width: 768px) {
            .chunk-content {
                grid-template-columns: 1fr;
            }
            .lang-section.english {
                border-right: none;
                border-bottom: 1px solid #e0e0e0;
            }
        }
    </style>
</head>
<body>
    <h1>📚 Chunks Viewer - 中英文对照</h1>

    <div class="search-box">
        <input type="text" id="searchInput" placeholder="搜索关键词..." onkeyup="filterChunks()">
    </div>

    <div class="stats">
        共 <span id="totalChunks">0</span> 个 Chunks，<span id="totalFiles">0</span> 个文件
    </div>
"""

    total_chunks = 0
    for source, chunks in sorted(chunks_by_source.items()):
        chunks_sorted = sorted(chunks, key=lambda x: x.get("chunk_index", 0))
        total_chunks += len(chunks_sorted)

        html += f'''
    <div class="file-section">
        <div class="file-title">📄 {source}</div>
        <div class="file-chunks">
'''

        for chunk in chunks_sorted:
            idx = chunk.get("chunk_index", 0)
            en = chunk.get("text_en", "").strip()
            zh = chunk.get("text_zh", "").strip()

            en_display = en if en else '<span class="empty">(暂无英文)</span>'
            zh_display = zh if zh else '<span class="empty">(暂无中文翻译)</span>'

            # Escape HTML
            en_escaped = en.replace("<", "&lt;").replace(">", "&gt;") if en else ""
            zh_escaped = zh.replace("<", "&lt;").replace(">", "&gt;") if zh else ""

            search_text = f"{en} {zh}".lower()

            html += f'''
            <div class="chunk" data-search="{search_text}">
                <div class="chunk-header">
                    <span>Chunk #{idx}</span>
                    <span>Score: {chunk.get('score', 0):.4f}</span>
                </div>
                <div class="chunk-content">
                    <div class="lang-section english">
                        <div class="lang-label">🇬🇧 English</div>
                        <div class="text">{en_escaped if en else '<span class="empty">(暂无英文)</span>'}</div>
                    </div>
                    <div class="lang-section chinese">
                        <div class="lang-label">🇨🇳 中文</div>
                        <div class="text">{zh_escaped if zh else '<span class="empty">(暂无中文翻译)</span>'}</div>
                    </div>
                </div>
            </div>
'''

        html += '''
        </div>
    </div>
'''

    html += f'''
    <script>
        document.getElementById('totalChunks').textContent = {total_chunks};
        document.getElementById('totalFiles').textContent = {len(chunks_by_source)};

        function filterChunks() {{
            const query = document.getElementById('searchInput').value.toLowerCase();
            const chunks = document.querySelectorAll('.chunk');

            chunks.forEach(chunk => {{
                const searchText = chunk.getAttribute('data-search');
                chunk.style.display = searchText.includes(query) ? 'block' : 'none';
            }});

            // Update visible count
            const visibleChunks = document.querySelectorAll('.chunk[style="display: block"], .chunk:not([style])');
            let count = 0;
            chunks.forEach(c => {{
                if (c.style.display !== 'none') count++;
            }});
        }}
    </script>
</body>
</html>
'''

    # Write to file
    output = Path(output_path)
    output.write_text(html, encoding="utf-8")
    print(f"Exported to: {output.absolute()}")
    print(f"Total: {total_chunks} chunks from {len(chunks_by_source)} files")


if __name__ == "__main__":
    export_chunks_to_html()
