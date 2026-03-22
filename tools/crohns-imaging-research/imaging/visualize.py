#!/usr/bin/env python3
"""
visualize.py — 克罗恩病 MRI/CT 影像可视化工具

功能：
  - 多平面重建（MPR）：轴位 / 矢状位 / 冠状位
  - 批量生成 QC 图（质量控制）
  - 叠加分割 mask（如有）
  - 导出 PNG / PDF 报告

依赖: pip install SimpleITK nibabel numpy matplotlib tqdm

使用:
    python3 visualize.py --input volume.nii.gz
    python3 visualize.py --input volume.nii.gz --mask seg.nii.gz --out ./figures
    python3 visualize.py --batch ./preprocessed --out ./qc_report
"""

import argparse
from pathlib import Path

import numpy as np
from tqdm import tqdm

try:
    import SimpleITK as sitk
    import matplotlib
    matplotlib.use("Agg")  # 无显示器环境
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.colors import ListedColormap
except ImportError:
    import sys
    sys.exit("请安装依赖: pip install SimpleITK matplotlib numpy tqdm")


# ── 颜色配置 ──────────────────────────────────────────────────────────────────

# 克罗恩病常用分割标签（可按需扩展）
LABEL_COLORS = {
    0: (0.0, 0.0, 0.0, 0.0),   # 背景（透明）
    1: (1.0, 0.2, 0.2, 0.5),   # 肠壁增厚
    2: (0.2, 0.8, 0.2, 0.5),   # 正常肠管
    3: (1.0, 0.8, 0.0, 0.5),   # 肠系膜炎症
    4: (0.2, 0.4, 1.0, 0.5),   # 瘘管
    5: (0.8, 0.0, 0.8, 0.5),   # 脓肿
}
LABEL_NAMES = {
    1: "肠壁增厚",
    2: "正常肠管",
    3: "肠系膜炎症",
    4: "瘘管",
    5: "脓肿",
}


# ── 核心可视化 ────────────────────────────────────────────────────────────────

def load_volume(path: Path) -> np.ndarray:
    """加载 NIfTI，返回 (H, W, D) numpy 数组。"""
    image = sitk.ReadImage(str(path))
    arr = sitk.GetArrayFromImage(image)  # (D, H, W)
    return arr.transpose(1, 2, 0)       # → (H, W, D)


def get_center_slices(arr: np.ndarray) -> tuple[int, int, int]:
    """返回各轴中心切片索引（自动跳过空白边缘）。"""
    h, w, d = arr.shape
    nonzero = np.argwhere(arr > arr.min())
    if len(nonzero) == 0:
        return h // 2, w // 2, d // 2
    mins = nonzero.min(axis=0)
    maxs = nonzero.max(axis=0)
    return (
        (mins[0] + maxs[0]) // 2,
        (mins[1] + maxs[1]) // 2,
        (mins[2] + maxs[2]) // 2,
    )


def plot_mpr(
    arr: np.ndarray,
    mask: np.ndarray | None = None,
    title: str = "",
    out_path: Path | None = None,
    vmin: float | None = None,
    vmax: float | None = None,
    cmap: str = "gray",
) -> None:
    """绘制三平面 MPR 图（轴位、矢状位、冠状位）。"""
    h_idx, w_idx, d_idx = get_center_slices(arr)
    vmin = vmin or float(np.percentile(arr, 1))
    vmax = vmax or float(np.percentile(arr, 99))

    slices = {
        "轴位 (Axial)":     arr[:, :, d_idx],
        "冠状位 (Coronal)": arr[:, w_idx, :],
        "矢状位 (Sagittal)":arr[h_idx, :, :],
    }
    mask_slices = {}
    if mask is not None:
        mask_slices = {
            "轴位 (Axial)":     mask[:, :, d_idx],
            "冠状位 (Coronal)": mask[:, w_idx, :],
            "矢状位 (Sagittal)":mask[h_idx, :, :],
        }

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle(title, fontsize=14, fontproperties="SimHei" if _has_cjk_font() else None)

    for ax, (view_name, sl) in zip(axes, slices.items()):
        ax.imshow(sl.T, cmap=cmap, origin="lower", vmin=vmin, vmax=vmax, aspect="auto")
        if view_name in mask_slices:
            _overlay_mask(ax, mask_slices[view_name].T)
        ax.set_title(view_name, fontsize=10)
        ax.axis("off")

    # 图例
    if mask is not None:
        labels_present = np.unique(mask)
        labels_present = labels_present[labels_present > 0]
        patches = [
            mpatches.Patch(color=LABEL_COLORS.get(lbl, (1, 1, 1, 0.5))[:3],
                           label=LABEL_NAMES.get(lbl, f"Label {lbl}"))
            for lbl in labels_present
        ]
        if patches:
            fig.legend(handles=patches, loc="lower right", fontsize=8)

    plt.tight_layout()
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(str(out_path), dpi=150, bbox_inches="tight")
    plt.close(fig)


def _overlay_mask(ax, mask_slice: np.ndarray) -> None:
    """在轴上叠加分割 mask（多标签彩色）。"""
    labels = np.unique(mask_slice)
    for lbl in labels:
        if lbl == 0:
            continue
        color = LABEL_COLORS.get(int(lbl), (1.0, 1.0, 0.0, 0.4))
        rgba = np.zeros((*mask_slice.shape, 4), dtype=np.float32)
        mask_bin = mask_slice == lbl
        rgba[mask_bin] = color
        ax.imshow(rgba, origin="lower", aspect="auto")


def _has_cjk_font() -> bool:
    """检查是否有可用的 CJK 字体（避免 matplotlib 警告）。"""
    try:
        import matplotlib.font_manager as fm
        fonts = [f.name for f in fm.fontManager.ttflist]
        return any(name in fonts for name in ["SimHei", "WenQuanYi Micro Hei", "Noto Sans CJK SC"])
    except Exception:
        return False


# ── 批量 QC ───────────────────────────────────────────────────────────────────

def batch_qc(input_dir: Path, out_dir: Path, mask_dir: Path | None = None) -> None:
    """批量为目录下所有 NIfTI 文件生成 MPR QC 图。"""
    nii_files = sorted(input_dir.rglob("*.nii.gz")) + sorted(input_dir.rglob("*.nii"))
    out_dir.mkdir(parents=True, exist_ok=True)

    ok, fail = 0, 0
    for nii_path in tqdm(nii_files, desc="生成 QC 图"):
        rel = nii_path.relative_to(input_dir)
        out_path = out_dir / rel.with_suffix("").with_suffix(".png")

        mask_path = None
        if mask_dir:
            candidate = mask_dir / rel
            if candidate.exists():
                mask_path = candidate

        try:
            arr  = load_volume(nii_path)
            mask = load_volume(mask_path).astype(np.uint8) if mask_path else None
            plot_mpr(
                arr, mask=mask,
                title=str(rel),
                out_path=out_path,
            )
            ok += 1
        except Exception as e:
            print(f"  ✗ 失败 [{nii_path.name}]: {e}")
            fail += 1

    print(f"\nQC 报告完成：成功 {ok}，失败 {fail}")
    print(f"输出目录: {out_dir.resolve()}")


# ── 主程序 ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="MRI/CT 三平面可视化")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--input",  help="单个 NIfTI 文件")
    group.add_argument("--batch",  help="批量处理目录")
    parser.add_argument("--mask",     default=None, help="分割 mask NIfTI 文件（单文件模式）")
    parser.add_argument("--mask-dir", default=None, help="分割 mask 目录（批量模式）")
    parser.add_argument("--out",   default="./figures", help="输出目录")
    parser.add_argument("--cmap",  default="gray",    help="colormap（默认 gray）")
    args = parser.parse_args()

    out_dir = Path(args.out)

    if args.input:
        nii_path = Path(args.input)
        arr  = load_volume(nii_path)
        mask = load_volume(Path(args.mask)).astype(np.uint8) if args.mask else None
        out_path = out_dir / (nii_path.stem.replace(".nii", "") + "_mpr.png")
        plot_mpr(arr, mask=mask, title=nii_path.name, out_path=out_path, cmap=args.cmap)
        print(f"✓ 保存至: {out_path.resolve()}")

    elif args.batch:
        batch_qc(
            input_dir=Path(args.batch),
            out_dir=out_dir,
            mask_dir=Path(args.mask_dir) if args.mask_dir else None,
        )


if __name__ == "__main__":
    main()
