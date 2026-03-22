#!/usr/bin/env python3
"""
dicom_loader.py — 加载并整理克罗恩病 MRI / CT DICOM 数据集

功能：
  - 递归扫描 DICOM 目录，按 Patient / Study / Series 组织
  - 导出 NIfTI 格式（供深度学习框架使用）
  - 生成数据集清单 CSV

依赖: pip install pydicom nibabel numpy pandas tqdm SimpleITK

使用:
    python3 dicom_loader.py --input /data/dicom_root --out /data/nifti_out
    python3 dicom_loader.py --input /data/dicom_root --out /data/nifti_out --modality MR
"""

import argparse
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm

try:
    import pydicom
    import SimpleITK as sitk
except ImportError:
    import sys
    sys.exit("请安装依赖: pip install pydicom SimpleITK nibabel numpy pandas tqdm")

warnings.filterwarnings("ignore", category=UserWarning)

# ── DICOM 扫描 ────────────────────────────────────────────────────────────────

def scan_dicom_dir(root: Path, modality_filter: str | None = None) -> list[dict]:
    """
    递归扫描 DICOM 文件，返回每个 Series 的元数据列表。
    每个元素包含：patient_id, study_uid, series_uid, modality, files。
    """
    series_map: dict[str, dict] = {}

    dcm_files = list(root.rglob("*.dcm")) + list(root.rglob("*.DCM"))
    # 如果没有 .dcm 扩展名，尝试扫描所有文件
    if not dcm_files:
        dcm_files = [f for f in root.rglob("*") if f.is_file() and not f.suffix]

    for fpath in tqdm(dcm_files, desc="扫描 DICOM 文件"):
        try:
            ds = pydicom.dcmread(str(fpath), stop_before_pixels=True)
        except Exception:
            continue

        modality = getattr(ds, "Modality", "UNKNOWN")
        if modality_filter and modality != modality_filter:
            continue

        series_uid = getattr(ds, "SeriesInstanceUID", "UNKNOWN")
        if series_uid not in series_map:
            series_map[series_uid] = {
                "patient_id":   getattr(ds, "PatientID", "UNKNOWN"),
                "patient_name": str(getattr(ds, "PatientName", "")),
                "study_uid":    getattr(ds, "StudyInstanceUID", "UNKNOWN"),
                "study_date":   getattr(ds, "StudyDate", ""),
                "study_desc":   getattr(ds, "StudyDescription", ""),
                "series_uid":   series_uid,
                "series_num":   str(getattr(ds, "SeriesNumber", "")),
                "series_desc":  getattr(ds, "SeriesDescription", ""),
                "modality":     modality,
                "files":        [],
            }
        series_map[series_uid]["files"].append(str(fpath))

    # 按 slice location 排序
    for info in series_map.values():
        info["num_slices"] = len(info["files"])
        info["files"].sort()

    return list(series_map.values())


# ── NIfTI 转换 ────────────────────────────────────────────────────────────────

def series_to_nifti(series_info: dict, out_dir: Path) -> Path | None:
    """
    将一个 DICOM series 转换为 NIfTI 文件，保留空间信息（方向矩阵、体素大小）。
    返回输出 NIfTI 文件路径，失败返回 None。
    """
    patient_id = series_info["patient_id"].replace("/", "_")
    series_uid  = series_info["series_uid"]
    series_desc = series_info["series_desc"].replace(" ", "_").replace("/", "_")[:40]

    out_subdir = out_dir / patient_id
    out_subdir.mkdir(parents=True, exist_ok=True)
    nii_path = out_subdir / f"{series_desc}_{series_uid[:8]}.nii.gz"

    if nii_path.exists():
        return nii_path  # 已转换，跳过

    try:
        reader = sitk.ImageSeriesReader()
        dicom_names = reader.GetGDCMSeriesFileNames(
            str(Path(series_info["files"][0]).parent)
        )
        if not dicom_names:
            dicom_names = series_info["files"]
        reader.SetFileNames(dicom_names)
        image = reader.Execute()
        sitk.WriteImage(image, str(nii_path))
        return nii_path
    except Exception as e:
        print(f"  ✗ 转换失败 [{series_uid[:8]}]: {e}")
        return None


# ── 数据集清单 ────────────────────────────────────────────────────────────────

def build_manifest(series_list: list[dict], nifti_paths: list[Path | None], out_dir: Path) -> None:
    rows = []
    for info, nii in zip(series_list, nifti_paths):
        rows.append({
            "patient_id":  info["patient_id"],
            "study_date":  info["study_date"],
            "study_desc":  info["study_desc"],
            "series_desc": info["series_desc"],
            "modality":    info["modality"],
            "num_slices":  info["num_slices"],
            "nifti_path":  str(nii) if nii else "",
            "status":      "ok" if nii else "failed",
        })
    df = pd.DataFrame(rows)
    manifest_path = out_dir / "dataset_manifest.csv"
    df.to_csv(manifest_path, index=False, encoding="utf-8-sig")
    print(f"\n✓ 数据集清单: {manifest_path}")
    print(f"  成功: {(df['status'] == 'ok').sum()} / {len(df)} 个 Series")


# ── 主程序 ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="DICOM → NIfTI 转换（克罗恩病 MRI/CT）")
    parser.add_argument("--input",    required=True,       help="DICOM 根目录")
    parser.add_argument("--out",      default="./nifti_output", help="NIfTI 输出目录")
    parser.add_argument("--modality", default=None,        help="仅处理指定模态（如 MR / CT）")
    parser.add_argument("--no-convert", action="store_true", help="仅扫描，不转换 NIfTI")
    args = parser.parse_args()

    input_dir = Path(args.input)
    out_dir   = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/3] 扫描 DICOM 目录: {input_dir}")
    series_list = scan_dicom_dir(input_dir, modality_filter=args.modality)
    print(f"  发现 {len(series_list)} 个 Series")

    # 保存扫描清单（JSON）
    scan_json = out_dir / "scan_result.json"
    scan_data = [{k: v for k, v in s.items() if k != "files"} for s in series_list]
    scan_json.write_text(json.dumps(scan_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  扫描结果: {scan_json}")

    if args.no_convert:
        print("\n--no-convert 模式，跳过 NIfTI 转换")
        return

    print(f"\n[2/3] 转换为 NIfTI...")
    nifti_paths = []
    for series_info in tqdm(series_list, desc="转换进度"):
        nifti_paths.append(series_to_nifti(series_info, out_dir))

    print(f"\n[3/3] 生成数据集清单...")
    build_manifest(series_list, nifti_paths, out_dir)


if __name__ == "__main__":
    main()
