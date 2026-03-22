# 克罗恩病影像研究工具集

基于 ARIS 框架的克罗恩病影像学研究自动化工具，包含三个模块：

## 目录结构

```
tools/crohns-imaging-research/
├── setup_aris.sh              # ARIS 环境一键配置
├── requirements.txt           # Python 依赖
├── literature/
│   ├── fetch_pubmed.py        # PubMed 文献检索（5 个预设主题）
│   ├── fetch_arxiv.py         # arXiv 预印本检索
│   └── organize_papers.py    # 合并去重 + 主题分类 + 生成参考文献库
└── imaging/
    ├── dicom_loader.py        # DICOM → NIfTI 批量转换
    ├── preprocess.py          # MRI/CT 预处理流水线
    └── visualize.py           # 三平面 MPR 可视化 + 批量 QC
```

## 快速开始

### 1. 配置 ARIS 环境

```bash
bash tools/crohns-imaging-research/setup_aris.sh
```

在 `~/.bashrc` 中设置：

```bash
export ANTHROPIC_API_KEY="your-key"
export NCBI_EMAIL="your-email@example.com"
export NCBI_API_KEY="your-ncbi-key"      # 可选
export OPENAI_API_KEY="your-key"         # 可选，用于 GPT-5.4 交叉审稿
```

### 2. 文献检索

```bash
pip install -r tools/crohns-imaging-research/requirements.txt

# 检索 PubMed（5 个预设主题：MRI、CTE、超声、深度学习、评分系统）
python3 tools/crohns-imaging-research/literature/fetch_pubmed.py

# 检索 arXiv 预印本
python3 tools/crohns-imaging-research/literature/fetch_arxiv.py

# 合并去重、分类，生成 ARIS 可读的参考文献库
python3 tools/crohns-imaging-research/literature/organize_papers.py \
    --input ./literature_output \
    --out   ./refine-logs
```

输出文件：
- `refine-logs/merged_library.json` — ARIS 文献库
- `refine-logs/REFERENCES.md` — 按主题分组的参考文献
- `refine-logs/stats_report.md` — 文献统计报告

### 3. 启动 ARIS 综述流水线

```bash
cd ~/crohns-imaging-research
claude
```

在 Claude Code 中：

```
/idea-discovery "克罗恩病影像学综述：MRI、CT、超声与深度学习进展"
```

### 4. 医学影像数据处理（如有本地数据）

```bash
# DICOM → NIfTI
python3 tools/crohns-imaging-research/imaging/dicom_loader.py \
    --input /data/dicom \
    --out   /data/nifti \
    --modality MR

# 预处理（重采样 + 归一化）
python3 tools/crohns-imaging-research/imaging/preprocess.py \
    --input /data/nifti \
    --out   /data/preprocessed \
    --modality MR \
    --spacing 1.5 1.5 3.0

# 批量 QC 可视化
python3 tools/crohns-imaging-research/imaging/visualize.py \
    --batch /data/preprocessed \
    --out   /data/qc_figures
```

## 预设文献检索主题

| 主题 | 关键词 |
|------|--------|
| MRI 小肠造影 | MRE, MR enterography, magnetic resonance |
| CT 肠道造影 | CTE, CT enterography |
| 肠道超声 | IUS, bowel ultrasound |
| 深度学习 | deep learning, CNN, AI, segmentation |
| 影像评分系统 | MaRIA, Clermont, SES-CD |
