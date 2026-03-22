#!/usr/bin/env python3
"""
fetch_pubmed.py — 从 PubMed 检索克罗恩病影像学文献并下载元数据

依赖: pip install biopython pandas tqdm
配置: 设置环境变量 NCBI_EMAIL 和 NCBI_API_KEY（可选）

使用:
    python3 fetch_pubmed.py
    python3 fetch_pubmed.py --query "Crohn MRI" --max 200 --out ./my_papers
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime

import pandas as pd
from tqdm import tqdm

try:
    from Bio import Entrez, Medline
except ImportError:
    sys.exit("请先安装 biopython: pip install biopython")

# ── 默认检索策略 ──────────────────────────────────────────────────────────────

DEFAULT_QUERIES = {
    "MRI_diagnosis": (
        '(Crohn disease[MeSH] OR "Crohn\'s disease"[tiab] OR "inflammatory bowel disease"[MeSH]) '
        'AND (MRI[tiab] OR "magnetic resonance imaging"[tiab] OR "MR enterography"[tiab] '
        'OR "MRE"[tiab] OR "MR enteroclysis"[tiab])'
    ),
    "CT_enterography": (
        '(Crohn disease[MeSH] OR "Crohn\'s disease"[tiab]) '
        'AND ("CT enterography"[tiab] OR "computed tomography enterography"[tiab] '
        'OR "CTE"[tiab] OR "CT enteroclysis"[tiab])'
    ),
    "ultrasound": (
        '(Crohn disease[MeSH] OR "Crohn\'s disease"[tiab]) '
        'AND (ultrasonography[MeSH] OR ultrasound[tiab] OR "bowel ultrasound"[tiab] '
        'OR "intestinal ultrasound"[tiab] OR "IUS"[tiab])'
    ),
    "deep_learning": (
        '(Crohn disease[MeSH] OR "Crohn\'s disease"[tiab]) '
        'AND ("deep learning"[tiab] OR "convolutional neural network"[tiab] '
        'OR "artificial intelligence"[tiab] OR "machine learning"[tiab]) '
        'AND (imaging[tiab] OR radiology[tiab] OR MRI[tiab] OR CT[tiab])'
    ),
    "scoring_systems": (
        '(Crohn disease[MeSH] OR "Crohn\'s disease"[tiab]) '
        'AND (MaRIA[tiab] OR Clermont[tiab] OR "Simple Endoscopic Score"[tiab] '
        'OR "Magnetic Resonance Index of Activity"[tiab] OR "CDAI"[tiab]) '
        'AND (imaging[tiab] OR MRI[tiab] OR radiology[tiab])'
    ),
}

# ── 工具函数 ──────────────────────────────────────────────────────────────────

def configure_entrez(email: str | None = None, api_key: str | None = None) -> None:
    Entrez.email = email or os.getenv("NCBI_EMAIL", "researcher@example.com")
    key = api_key or os.getenv("NCBI_API_KEY", "")
    if key:
        Entrez.api_key = key


def search_pubmed(query: str, max_results: int = 500, min_year: int = 2010) -> list[str]:
    """返回 PubMed ID 列表。"""
    full_query = f"({query}) AND {min_year}:{datetime.now().year}[dp]"
    handle = Entrez.esearch(db="pubmed", term=full_query, retmax=max_results, sort="relevance")
    record = Entrez.read(handle)
    handle.close()
    return record["IdList"]


def fetch_records(pmids: list[str], batch_size: int = 100) -> list[dict]:
    """批量拉取 Medline 记录，返回结构化字典列表。"""
    records = []
    for i in tqdm(range(0, len(pmids), batch_size), desc="Fetching records"):
        batch = pmids[i : i + batch_size]
        handle = Entrez.efetch(db="pubmed", id=batch, rettype="medline", retmode="text")
        for rec in Medline.parse(handle):
            records.append({
                "pmid":       rec.get("PMID", ""),
                "title":      rec.get("TI", ""),
                "authors":    "; ".join(rec.get("AU", [])),
                "journal":    rec.get("TA", ""),
                "year":       rec.get("DP", "")[:4] if rec.get("DP") else "",
                "abstract":   rec.get("AB", ""),
                "keywords":   "; ".join(rec.get("MH", []) + rec.get("OT", [])),
                "doi":        next(
                    (aid.split(" ")[0] for aid in rec.get("AID", []) if "[doi]" in aid),
                    ""
                ),
                "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{rec.get('PMID', '')}/",
            })
        handle.close()
        time.sleep(0.35)  # NCBI 速率限制：无 API Key 时 3 req/s
    return records


def deduplicate(records: list[dict]) -> list[dict]:
    seen_pmids: set[str] = set()
    unique = []
    for r in records:
        if r["pmid"] and r["pmid"] not in seen_pmids:
            seen_pmids.add(r["pmid"])
            unique.append(r)
    return unique


def save_results(records: list[dict], out_dir: Path, topic: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")

    # CSV
    csv_path = out_dir / f"{topic}_{timestamp}.csv"
    df = pd.DataFrame(records)
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    # JSON（供 ARIS 读取）
    json_path = out_dir / f"{topic}_{timestamp}.json"
    json_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    # Markdown 摘要
    md_path = out_dir / f"{topic}_{timestamp}_summary.md"
    lines = [
        f"# 文献检索结果：{topic}",
        f"\n检索时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"文献总数：{len(records)}\n",
        "| # | 年份 | 作者 | 标题 | 期刊 | PMID |",
        "|---|------|------|------|------|------|",
    ]
    for i, r in enumerate(records[:100], 1):  # Markdown 仅列前 100 条
        authors_short = r["authors"].split(";")[0].strip() + " et al." if ";" in r["authors"] else r["authors"]
        title_short = r["title"][:80] + "…" if len(r["title"]) > 80 else r["title"]
        lines.append(
            f"| {i} | {r['year']} | {authors_short} | {title_short} | {r['journal']} | "
            f"[{r['pmid']}]({r['pubmed_url']}) |"
        )
    if len(records) > 100:
        lines.append(f"\n*（仅显示前 100 条，完整结果见 CSV/JSON 文件）*")
    md_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"  ✓ CSV:      {csv_path}")
    print(f"  ✓ JSON:     {json_path}")
    print(f"  ✓ Markdown: {md_path}")


# ── 主程序 ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="PubMed 克罗恩病影像文献检索")
    parser.add_argument("--query",    type=str,  default=None,  help="自定义检索式（默认运行所有预设主题）")
    parser.add_argument("--topic",    type=str,  default="custom", help="自定义主题名称（配合 --query 使用）")
    parser.add_argument("--max",      type=int,  default=500,   help="每个主题最大文献数（默认 500）")
    parser.add_argument("--min-year", type=int,  default=2010,  help="最早发表年份（默认 2010）")
    parser.add_argument("--out",      type=str,  default="./literature_output", help="输出目录")
    args = parser.parse_args()

    configure_entrez()
    out_dir = Path(args.out)

    queries = {args.topic: args.query} if args.query else DEFAULT_QUERIES

    all_records: list[dict] = []
    for topic, query in queries.items():
        print(f"\n[主题] {topic}")
        print(f"  检索式: {query[:80]}...")
        pmids = search_pubmed(query, max_results=args.max, min_year=args.min_year)
        print(f"  命中: {len(pmids)} 篇")
        if not pmids:
            continue
        records = fetch_records(pmids)
        save_results(records, out_dir / topic, topic)
        all_records.extend(records)

    # 合并去重
    if len(queries) > 1:
        print("\n[合并] 去重所有主题...")
        merged = deduplicate(all_records)
        print(f"  合并后：{len(merged)} 篇（去重前 {len(all_records)} 篇）")
        save_results(merged, out_dir / "merged", "crohns_imaging_all")

    print(f"\n完成！所有结果保存至: {out_dir.resolve()}")


if __name__ == "__main__":
    main()
