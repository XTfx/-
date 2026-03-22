#!/usr/bin/env python3
"""
fetch_arxiv.py — 从 arXiv 检索克罗恩病影像 / 深度学习相关预印本

依赖: pip install arxiv pandas tqdm
使用:
    python3 fetch_arxiv.py
    python3 fetch_arxiv.py --query "Crohn deep learning MRI" --max 100
"""

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from tqdm import tqdm

try:
    import arxiv
except ImportError:
    import sys
    sys.exit("请先安装 arxiv: pip install arxiv")

# ── 预设检索主题 ───────────────────────────────────────────────────────────────

DEFAULT_QUERIES = {
    "crohns_mri_dl": (
        "Crohn disease MRI deep learning segmentation"
    ),
    "ibd_imaging_ai": (
        "inflammatory bowel disease imaging artificial intelligence"
    ),
    "bowel_segmentation": (
        "small bowel large bowel segmentation CT MRI neural network"
    ),
    "crohns_activity": (
        "Crohn disease activity assessment imaging scoring"
    ),
}

# ── 核心函数 ──────────────────────────────────────────────────────────────────

def search_arxiv(query: str, max_results: int = 100) -> list[dict]:
    """检索 arXiv 并返回结构化记录列表。"""
    client = arxiv.Client(page_size=50, delay_seconds=1.0, num_retries=3)
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.Relevance,
    )

    records = []
    for result in tqdm(client.results(search), desc=f"arXiv: {query[:50]}", total=max_results):
        records.append({
            "arxiv_id":   result.entry_id.split("/abs/")[-1],
            "title":      result.title,
            "authors":    "; ".join(a.name for a in result.authors),
            "published":  result.published.strftime("%Y-%m-%d") if result.published else "",
            "year":       str(result.published.year) if result.published else "",
            "abstract":   result.summary.replace("\n", " "),
            "categories": "; ".join(result.categories),
            "pdf_url":    result.pdf_url or "",
            "arxiv_url":  result.entry_id,
            "journal":    result.journal_ref or "arXiv preprint",
            "doi":        result.doi or "",
        })
        time.sleep(0.1)
    return records


def save_results(records: list[dict], out_dir: Path, topic: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")

    csv_path = out_dir / f"arxiv_{topic}_{timestamp}.csv"
    pd.DataFrame(records).to_csv(csv_path, index=False, encoding="utf-8-sig")

    json_path = out_dir / f"arxiv_{topic}_{timestamp}.json"
    json_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    md_path = out_dir / f"arxiv_{topic}_{timestamp}_summary.md"
    lines = [
        f"# arXiv 检索结果：{topic}",
        f"\n检索时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"文献总数：{len(records)}\n",
        "| # | 年份 | 作者 | 标题 | arXiv ID |",
        "|---|------|------|------|----------|",
    ]
    for i, r in enumerate(records, 1):
        authors_short = r["authors"].split(";")[0].strip() + " et al." if ";" in r["authors"] else r["authors"]
        title_short = r["title"][:80] + "…" if len(r["title"]) > 80 else r["title"]
        lines.append(
            f"| {i} | {r['year']} | {authors_short} | [{title_short}]({r['arxiv_url']}) | `{r['arxiv_id']}` |"
        )
    md_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"  ✓ CSV:      {csv_path}")
    print(f"  ✓ JSON:     {json_path}")
    print(f"  ✓ Markdown: {md_path}")


# ── 主程序 ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="arXiv 克罗恩病影像文献检索")
    parser.add_argument("--query", type=str, default=None)
    parser.add_argument("--topic", type=str, default="custom")
    parser.add_argument("--max",   type=int, default=100)
    parser.add_argument("--out",   type=str, default="./literature_output")
    args = parser.parse_args()

    out_dir = Path(args.out)
    queries = {args.topic: args.query} if args.query else DEFAULT_QUERIES

    all_records: list[dict] = []
    for topic, query in queries.items():
        print(f"\n[主题] {topic}")
        records = search_arxiv(query, max_results=args.max)
        print(f"  命中: {len(records)} 篇")
        if records:
            save_results(records, out_dir / topic, topic)
            all_records.extend(records)

    print(f"\n完成！所有结果保存至: {out_dir.resolve()}")


if __name__ == "__main__":
    main()
