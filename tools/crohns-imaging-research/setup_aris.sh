#!/usr/bin/env bash
# setup_aris.sh — 配置 ARIS 研究环境（克罗恩病影像综述）
# 使用方式: bash setup_aris.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SKILLS_DIR="$HOME/.claude/skills"
ARIS_SKILLS_DIR="$REPO_ROOT/skills"

echo "======================================"
echo " ARIS 环境配置 - 克罗恩病影像研究"
echo "======================================"

# ── 1. 检查 Claude Code ──────────────────
echo ""
echo "[1/6] 检查 Claude Code..."
if ! command -v claude &>/dev/null; then
    echo "  ✗ 未找到 claude 命令，请先安装 Claude Code："
    echo "    npm install -g @anthropic-ai/claude-code"
    exit 1
fi
echo "  ✓ Claude Code 已安装: $(claude --version 2>/dev/null || echo '版本未知')"

# ── 2. 检查 Python ───────────────────────
echo ""
echo "[2/6] 检查 Python 环境..."
if ! command -v python3 &>/dev/null; then
    echo "  ✗ 未找到 python3，请安装 Python 3.10+"
    exit 1
fi
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "  ✓ Python $PYTHON_VERSION"

# ── 3. 安装 Python 依赖 ──────────────────
echo ""
echo "[3/6] 安装 Python 依赖..."
pip3 install -q \
    biopython \
    arxiv \
    requests \
    pydicom \
    nibabel \
    SimpleITK \
    numpy \
    pandas \
    matplotlib \
    scikit-image \
    tqdm \
    openai
echo "  ✓ 依赖安装完成"

# ── 4. 复制 ARIS 技能文件 ────────────────
echo ""
echo "[4/6] 配置 ARIS 技能..."
mkdir -p "$SKILLS_DIR"
if [ -d "$ARIS_SKILLS_DIR" ]; then
    cp -r "$ARIS_SKILLS_DIR"/. "$SKILLS_DIR/"
    echo "  ✓ 技能文件已复制到 $SKILLS_DIR"
else
    echo "  ✗ 未找到技能目录: $ARIS_SKILLS_DIR"
    exit 1
fi

# ── 5. 配置工作目录 ──────────────────────
echo ""
echo "[5/6] 初始化研究工作目录..."
WORK_DIR="$HOME/crohns-imaging-research"
mkdir -p "$WORK_DIR"/{refine-logs,literature,imaging-data,results}

# 写入 CLAUDE.md（ARIS 研究上下文）
cat > "$WORK_DIR/CLAUDE.md" << 'CLAUDE_MD'
# 克罗恩病影像研究项目

## 研究方向
克罗恩病（Crohn's Disease）影像学综述，聚焦：
- MRI 小肠造影（MRE）在 CD 诊断与活动度评估中的应用
- CT 肠道造影（CTE）的诊断效能
- 超声（肠道超声）的现状与进展
- 影像学评分系统（MaRIA、Clermont、CDAI 影像学对应指标）
- 深度学习在 CD 影像分析中的应用

## 目标期刊
European Radiology / Abdominal Radiology / Radiology

## 工具配置
- 文献库: PubMed + arXiv
- 影像数据: DICOM / NIfTI
- 结果保存: JSON/CSV
CLAUDE_MD

echo "  ✓ 工作目录已创建: $WORK_DIR"

# ── 6. 配置 API Key 提示 ─────────────────
echo ""
echo "[6/6] API 密钥配置..."
echo ""
echo "  请在 ~/.bashrc 或 ~/.zshrc 中添加以下环境变量："
echo ""
echo "  # Anthropic (Claude Code)"
echo "  export ANTHROPIC_API_KEY='your-key-here'"
echo ""
echo "  # OpenAI (GPT-5.4 交叉审稿，可选)"
echo "  export OPENAI_API_KEY='your-key-here'"
echo ""
echo "  # NCBI Entrez (PubMed 文献检索，免费注册)"
echo "  export NCBI_EMAIL='your-email@example.com'"
echo "  export NCBI_API_KEY='your-ncbi-key-here'  # 可选，提升速率限制"
echo ""

# ── 完成 ─────────────────────────────────
echo "======================================"
echo " 配置完成！"
echo "======================================"
echo ""
echo "下一步："
echo "  1. 配置上述 API 密钥"
echo "  2. cd $WORK_DIR"
echo "  3. 运行文献检索："
echo "     python3 $REPO_ROOT/tools/crohns-imaging-research/literature/fetch_pubmed.py"
echo "  4. 启动 ARIS 研究流水线："
echo "     claude"
echo "     /idea-discovery \"克罗恩病影像学综述\""
echo ""
