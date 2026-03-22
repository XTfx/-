#!/usr/bin/env python3
"""
organize_papers.py — 整合 PubMed + arXiv 文献，去重、分类，生成 ARIS 可读的参考文献库

输入: 多个 JSON 文件（fetch_pubmed.py / fetch_arxiv.py 的输出）
输出:
  - merged_library.json       完整文献库（ARIS 可读）
  - merged_library.csv        人工筛选用表格
  - REFERENCES.md             Markdown 参考文献列表（按主题分组）
  - stats_report.md           文献统计报告

使用:
    python3 organize_papers.py --input ./literature_output
    python3 organize_papers.py --input ./literature_output --out ./refine-logs
"""

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd

# ── 主题分类关键词 ─────────────────────────────────────────────────────────────

TOPIC_KEYWORDS: dict[str, list[str]] = {
    "MRI 小肠造影（MRE）": [
        "MR enterography", "MRE", "magnetic resonance enterography",
        "MR enteroclysis", "small bowel MRI",
    ],
    "CT 肠道造影（CTE）": [
        "CT enterography", "CTE", "computed tomography enterography",
        "CT enteroclysis",
    ],
    "肠道超声": [
        "bowel ultrasound", "intestinal ultrasound", "IUS",
        "ultrasonography", "ultrasound",
    ],
    "影像学评分系统": [
        "MaRIA", "Clermont", "Simple Endoscopic Score", "SES-CD",
        "Magnetic Resonance Index of Activity", "CDAI", "Harvey-Bradshaw",
    ],
    "深度学习 / AI": [
        "deep learning", "convolutional neural network", "CNN",
        "artificial intelligence", "machine learning", "segmentation",
        "U-Net", "transformer",
    ],
    "疾病活动度评估": [
        "disease activity", "inflammation", "stenosis", "stricture",
        "fistula", "abscess", "penetrating",
    ],
    "治疗监测": [
        "treatment response", "monitoring", "anti-TNF", "biologics",
        "vedolizumab", "ustekinumab", "remission",
    ],
}


def classify_record(record: dict) -> list[str]:
    """返回记录所属的主题标签列表。"""
    text = " ".join([
        record.get("title", ""),
        record.get("abstract", ""),
        record.get("keywords", ""),
    ]).lower()
    topics = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(kw.lower() in text for kw in keywords):
            topics.append(topic)
    return topics or ["其他"]


def load_json_files(input_dir: Path) -> list[dict]:
    """递归加载目录下所有 JSON 文献文件。"""
    records = []
    for json_file in sorted(input_dir.rglob("*.json")):
        if "summary" in json_file.name:
            continue
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                records.extend(data)
                print(f"  载入 {len(data)} 条: {json_file.relative_to(input_dir)}")
        except Exception as e:
            print(f"  ✗ 跳过 {json_file.name}: {e}")
    return records


def deduplicate(records: list[dict]) -> list[dict]:
    """按 PMID / arXiv ID / 标题去重。"""
    seen: set[str] = set()
    unique = []
    for r in records:
        key = (
            r.get("pmid") or
            r.get("arxiv_id") or
            re.sub(r"\W+", "", r.get("title", "").lower())[:60]
        )
        if key and key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


def build_reference_md(records: list[dict]) -> str:
    """生成按主题分组的 Markdown 参考文献列表。"""
    topic_map: defaultdict[str, list[dict]] = defaultdict(list)
    for r in records:
        for topic in r.get("_topics", ["其他"]):
            topic_map[topic].append(r)

    lines = [
        "# 克罗恩病影像学参考文献库",
        f"\n生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"文献总数：{len(records)}\n",
    ]

    for topic in TOPIC_KEYWORDS:
        topic_records = topic_map.get(topic, [])
        if not topic_records:
            continue
        lines.append(f"## {topic}（{len(topic_records)} 篇）\n")
        for r in sorted(topic_records, key=lambda x: x.get("year", "0"), reverse=True)[:50]:
            authors = r.get("authors", "")
            authors_short = authors.split(";")[0].strip() + " et al." if ";" in authors else authors
            year = r.get("year", "")
            title = r.get("title", "无标题")
            journal = r.get("journal", "")
            url = r.get("pubmed_url") or r.get("arxiv_url") or ""
            doi = r.get("doi", "")

            ref_line = f"- **{authors_short}** ({year}). {title}. *{journal}*."
            if doi:
                ref_line += f" https://doi.org/{doi}"
            elif url:
                ref_line += f" {url}"
            lines.append(ref_line)
        lines.append("")

    return "\n".join(lines)


def build_stats_report(records: list[dict]) -> str:
    """生成文献统计报告。"""
    years = [r.get("year", "") for r in records if r.get("year", "").isdigit()]
    year_counter = Counter(years)
    journals = [r.get("journal", "") for r in records if r.get("journal")]
    journal_counter = Counter(journals)
    topic_counter: Counter = Counter()
    for r in records:
        for t in r.get("_topics", []):
            topic_counter[t] += 1

    lines = [
        "# 文献统计报告",
        f"\n生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"文献总数：{len(records)}\n",
        "## 按年份分布\n",
        "| 年份 | 篇数 |",
        "|------|------|",
    ]
    for year in sorted(year_counter, reverse=True)[:15]:
        lines.append(f"| {year} | {year_counter[year]} |")

    lines += [
        "\n## 按主题分布\n",
        "| 主题 | 篇数 |",
        "|------|------|",
    ]
    for topic, count in topic_counter.most_common():
        lines.append(f"| {topic} | {count} |")

    lines += [
        "\n## 高频期刊 Top 20\n",
        "| 期刊 | 篇数 |",
        "|------|------|",
    ]
    for journal, count in journal_counter.most_common(20):
        lines.append(f"| {journal} | {count} |")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="整合 PubMed + arXiv 文献")
    parser.add_argument("--input", type=str, default="./literature_output", help="JSON 文件所在目录")
    parser.add_argument("--out",   type=str, default="./refine-logs",       help="输出目录")
    args = parser.parse_args()

    input_dir = Path(args.input)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/4] 载入文献...")
    records = load_json_files(input_dir)
    print(f"  载入总计：{len(records)} 条")

    print(f"\n[2/4] 去重...")
    records = deduplicate(records)
    print(f"  去重后：{len(records)} 条")

    print(f"\n[3/4] 主题分类...")
    for r in records:
        r["_topics"] = classify_record(r)
    print(f"  分类完成")

    print(f"\n[4/4] 写出文件...")

    # merged_library.json
    json_path = out_dir / "merged_library.json"
    json_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✓ {json_path}")

    # merged_library.csv
    csv_path = out_dir / "merged_library.csv"
    df = pd.DataFrame(records)
    df["_topics"] = df["_topics"].apply(lambda t: "; ".join(t))
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"  ✓ {csv_path}")

    # REFERENCES.md
    ref_path = out_dir / "REFERENCES.md"
    ref_path.write_text(build_reference_md(records), encoding="utf-8")
    print(f"  ✓ {ref_path}")

    # stats_report.md
    stats_path = out_dir / "stats_report.md"
    stats_path.write_text(build_stats_report(records), encoding="utf-8")
    print(f"  ✓ {stats_path}")

    print(f"\n完成！文献库保存至: {out_dir.resolve()}")
    print(f"  → 可将 {json_path} 提供给 ARIS /idea-discovery 使用")


if __name__ == "__main__":
    main()
