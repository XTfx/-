#!/usr/bin/env python3
"""
preprocess.py — MRI / CT 影像预处理流水线（克罗恩病影像研究）

功能：
  - 重采样到目标体素大小
  - 强度归一化（MRI: z-score 或 percentile clip；CT: HU 窗口）
  - 方向标准化（RAS+）
  - 裁剪 / Padding 到固定大小
  - 批量处理 NIfTI 目录

依赖: pip install SimpleITK nibabel numpy tqdm

使用:
    python3 preprocess.py --input ./nifti_output --out ./preprocessed
    python3 preprocess.py --input ./nifti_output --out ./preprocessed --modality CT --hu-min -150 --hu-max 250
"""

import argparse
from pathlib import Path

import numpy as np
from tqdm import tqdm

try:
    import SimpleITK as sitk
except ImportError:
    import sys
    sys.exit("请安装依赖: pip install SimpleITK numpy tqdm")


# ── 重采样 ────────────────────────────────────────────────────────────────────

def resample_image(
    image: sitk.Image,
    target_spacing: tuple[float, float, float] = (1.5, 1.5, 3.0),
    interpolator=sitk.sitkLinear,
) -> sitk.Image:
    """将图像重采样到目标体素大小（mm）。"""
    original_spacing = image.GetSpacing()
    original_size    = image.GetSize()

    new_size = [
        int(round(orig_sz * orig_sp / tgt_sp))
        for orig_sz, orig_sp, tgt_sp in zip(original_size, original_spacing, target_spacing)
    ]

    resampler = sitk.ResampleImageFilter()
    resampler.SetOutputSpacing(target_spacing)
    resampler.SetSize(new_size)
    resampler.SetOutputDirection(image.GetDirection())
    resampler.SetOutputOrigin(image.GetOrigin())
    resampler.SetTransform(sitk.Transform())
    resampler.SetDefaultPixelValue(image.GetPixelIDValue())
    resampler.SetInterpolator(interpolator)
    return resampler.Execute(image)


# ── 强度归一化 ────────────────────────────────────────────────────────────────

def normalize_mri(arr: np.ndarray, method: str = "zscore") -> np.ndarray:
    """MRI 强度归一化。method: 'zscore' 或 'percentile'"""
    mask = arr > 0
    if method == "zscore":
        mean = arr[mask].mean()
        std  = arr[mask].std()
        arr  = (arr - mean) / (std + 1e-8)
    elif method == "percentile":
        p1, p99 = np.percentile(arr[mask], [1, 99])
        arr = np.clip(arr, p1, p99)
        arr = (arr - p1) / (p99 - p1 + 1e-8)
    return arr.astype(np.float32)


def normalize_ct(
    arr: np.ndarray,
    hu_min: float = -150.0,
    hu_max: float = 250.0,
) -> np.ndarray:
    """CT 腹部窗口归一化（默认软组织/肠道窗口）。"""
    arr = np.clip(arr, hu_min, hu_max)
    arr = (arr - hu_min) / (hu_max - hu_min)
    return arr.astype(np.float32)


# ── 方向标准化 ────────────────────────────────────────────────────────────────

def orient_to_ras(image: sitk.Image) -> sitk.Image:
    """将图像重定向为 RAS+ 标准方向。"""
    orienter = sitk.DICOMOrientImageFilter()
    orienter.SetDesiredCoordinateOrientation("RAS")
    return orienter.Execute(image)


# ── 裁剪 / Padding ────────────────────────────────────────────────────────────

def pad_or_crop(
    arr: np.ndarray,
    target_shape: tuple[int, int, int] = (256, 256, 64),
) -> np.ndarray:
    """将 3D 数组 (H, W, D) 裁剪或 padding 到目标大小（中心对齐）。"""
    result = np.zeros(target_shape, dtype=arr.dtype)
    for dim, (src, tgt) in enumerate(zip(arr.shape, target_shape)):
        if src >= tgt:
            start = (src - tgt) // 2
            arr = np.take(arr, range(start, start + tgt), axis=dim)
        else:
            pad_before = (tgt - src) // 2
            pad_width = [(0, 0)] * 3
            pad_width[dim] = (pad_before, tgt - src - pad_before)
            arr = np.pad(arr, pad_width, mode="constant", constant_values=0)
    return arr


# ── 完整流水线 ────────────────────────────────────────────────────────────────

def preprocess_volume(
    nii_path: Path,
    out_path: Path,
    modality: str = "MR",
    target_spacing: tuple[float, float, float] = (1.5, 1.5, 3.0),
    target_shape: tuple[int, int, int] | None = None,
    hu_min: float = -150.0,
    hu_max: float = 250.0,
    mri_norm: str = "zscore",
) -> bool:
    """
    对单个 NIfTI 文件执行完整预处理流水线。
    返回 True 表示成功。
    """
    try:
        image = sitk.ReadImage(str(nii_path))

        # 方向标准化
        image = orient_to_ras(image)

        # 重采样
        image = resample_image(image, target_spacing=target_spacing)

        # 转 numpy 归一化
        arr = sitk.GetArrayFromImage(image).astype(np.float32)  # (D, H, W)
        arr = arr.transpose(1, 2, 0)  # → (H, W, D)

        if modality.upper() == "CT":
            arr = normalize_ct(arr, hu_min=hu_min, hu_max=hu_max)
        else:
            arr = normalize_mri(arr, method=mri_norm)

        # 可选 Pad/Crop
        if target_shape is not None:
            arr = pad_or_crop(arr, target_shape=target_shape)

        # 写出
        arr_d = arr.transpose(2, 0, 1)  # → (D, H, W)
        out_image = sitk.GetImageFromArray(arr_d)
        out_image.SetSpacing(target_spacing)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        sitk.WriteImage(out_image, str(out_path))
        return True

    except Exception as e:
        print(f"  ✗ 失败 [{nii_path.name}]: {e}")
        return False


# ── 主程序 ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="MRI/CT 预处理流水线")
    parser.add_argument("--input",    required=True,            help="NIfTI 输入目录")
    parser.add_argument("--out",      default="./preprocessed", help="预处理输出目录")
    parser.add_argument("--modality", default="MR",             help="MR 或 CT")
    parser.add_argument("--spacing",  nargs=3, type=float,      default=[1.5, 1.5, 3.0],
                        metavar=("X", "Y", "Z"),                help="目标体素大小 (mm)")
    parser.add_argument("--shape",    nargs=3, type=int,        default=None,
                        metavar=("H", "W", "D"),                help="裁剪/Padding 目标大小")
    parser.add_argument("--hu-min",   type=float, default=-150.0, help="CT HU 下界")
    parser.add_argument("--hu-max",   type=float, default=250.0,  help="CT HU 上界")
    parser.add_argument("--mri-norm", default="zscore",         choices=["zscore", "percentile"],
                        help="MRI 归一化方法")
    args = parser.parse_args()

    input_dir = Path(args.input)
    out_dir   = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    nii_files = sorted(input_dir.rglob("*.nii.gz")) + sorted(input_dir.rglob("*.nii"))
    print(f"找到 {len(nii_files)} 个 NIfTI 文件")

    ok, fail = 0, 0
    for nii_path in tqdm(nii_files, desc="预处理进度"):
        rel = nii_path.relative_to(input_dir)
        out_path = out_dir / rel
        success = preprocess_volume(
            nii_path, out_path,
            modality=args.modality,
            target_spacing=tuple(args.spacing),
            target_shape=tuple(args.shape) if args.shape else None,
            hu_min=args.hu_min,
            hu_max=args.hu_max,
            mri_norm=args.mri_norm,
        )
        if success:
            ok += 1
        else:
            fail += 1

    print(f"\n完成：成功 {ok}，失败 {fail}")
    print(f"输出目录: {out_dir.resolve()}")


if __name__ == "__main__":
    main()
