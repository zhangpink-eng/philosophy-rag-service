#!/usr/bin/env python3
"""
语料预处理分析脚本

用途：
1. 分析文件语言结构
2. 检测双语格式
3. 分离中英文内容
4. 生成处理报告

使用方法：
    python scripts/preprocess_analyze.py <文件路径>
    python scripts/preprocess_analyze.py <目录路径>
    python scripts/preprocess_analyze.py --all  # 分析所有文件
"""
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.preprocessor import (
    analyze_document,
    TextCleaner,
    LanguageDetector
)


def analyze_file(file_path: Path) -> Dict:
    """分析单个文件"""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 清洗（保留段落结构）
    cleaned = TextCleaner.clean(content)
    # 不要合并换行，避免破坏段落结构
    cleaned = content  # 直接使用原始内容

    # 分析
    result = analyze_document(cleaned)

    # 添加基本信息
    result['file_name'] = file_path.name
    result['file_path'] = str(file_path)
    result['file_size'] = len(content)

    return result


def analyze_directory(dir_path: Path, extensions: List[str] = ['.txt']) -> List[Dict]:
    """分析目录下所有文件"""
    results = []

    for ext in extensions:
        for file_path in dir_path.rglob(f"*{ext}"):
            # 跳过隐藏文件和缓存目录
            if file_path.name.startswith('.') or 'translation_cache' in str(file_path):
                continue

            try:
                result = analyze_file(file_path)
                results.append(result)
            except Exception as e:
                print(f"  Error analyzing {file_path.name}: {e}", file=sys.stderr)

    return results


def print_result(result: Dict):
    """打印单个文件分析结果"""
    print(f"\n{'='*60}")
    print(f"文件: {result['file_name']}")
    print(f"{'='*60}")

    lang = result['language']
    lang_display = {
        'zh': '中文',
        'en': '英文',
        'bilingual': '双语',
        'mixed': '混合'
    }.get(lang, lang)

    print(f"语言类型: {lang_display}")
    print(f"文件大小: {result['file_size']} 字符")

    stats = result.get('stats', {})

    if lang == 'bilingual':
        print(f"\n双语结构:")
        print(f"  中文段落: {stats.get('zh_paragraphs', 0)} 段 ({stats.get('zh_chars', 0)} 字符)")
        print(f"  英文段落: {stats.get('en_paragraphs', 0)} 段 ({stats.get('en_chars', 0)} 字符)")

        print(f"\n中文内容预览:")
        zh_preview = result['text_zh'][:300] if result['text_zh'] else "(无)"
        print(f"  {zh_preview}...")

        print(f"\n英文内容预览:")
        en_preview = result['text_en'][:300] if result['text_en'] else "(无)"
        print(f"  {en_preview}...")

    else:
        print(f"\n单语言文件，直接处理即可")


def print_summary(results: List[Dict]):
    """打印汇总报告"""
    print(f"\n{'='*60}")
    print("汇总报告")
    print(f"{'='*60}")

    total = len(results)
    lang_counts = {'zh': 0, 'en': 0, 'bilingual': 0, 'mixed': 0}

    for r in results:
        lang = r['language']
        lang_counts[lang] = lang_counts.get(lang, 0) + 1

    print(f"\n总计文件: {total}")
    print(f"  中文文件: {lang_counts.get('zh', 0)}")
    print(f"  英文文件: {lang_counts.get('en', 0)}")
    print(f"  双语文件: {lang_counts.get('bilingual', 0)}")
    print(f"  混合文件: {lang_counts.get('mixed', 0)}")

    # 双语文件列表
    bilingual_files = [r for r in results if r['language'] == 'bilingual']
    if bilingual_files:
        print(f"\n需要特殊处理的双语文件:")
        for r in bilingual_files:
            stats = r.get('stats', {})
            print(f"  - {r['file_name']}")
            print(f"    中文: {stats.get('zh_paragraphs', 0)}段, 英文: {stats.get('en_paragraphs', 0)}段")


def main():
    parser = argparse.ArgumentParser(description='语料预处理分析')
    parser.add_argument('path', nargs='?', help='文件或目录路径')
    parser.add_argument('--all', action='store_true', help='分析所有文件')
    parser.add_argument('--output', '-o', help='输出JSON结果到文件')
    parser.add_argument('--filter', choices=['zh', 'en', 'bilingual', 'mixed'],
                        help='只显示特定语言类型的文件')

    args = parser.parse_args()

    results = []

    if args.all or args.path is None:
        # 分析所有文件
        data_dir = Path(__file__).parent.parent / "data" / "raw"
        if not data_dir.exists():
            data_dir = Path("/Users/caiyuanjie/Desktop/哲学咨询/奥斯卡/文本")

        print(f"分析目录: {data_dir}", file=sys.stderr)
        results = analyze_directory(data_dir)
    elif Path(args.path).is_file():
        # 分析单个文件
        result = analyze_file(Path(args.path))
        results = [result]
    elif Path(args.path).is_dir():
        # 分析目录
        results = analyze_directory(Path(args.path))
    else:
        print(f"路径不存在: {args.path}", file=sys.stderr)
        return 1

    # 过滤
    if args.filter:
        results = [r for r in results if r['language'] == args.filter]

    # 输出
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"结果已保存到: {args.output}")

    # 打印结果
    for result in results:
        print_result(result)

    if len(results) > 1:
        print_summary(results)

    return 0


if __name__ == '__main__':
    sys.exit(main())
