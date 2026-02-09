"""
糖化アンケートOCR照合システム v2.1
メインプログラム: PDF処理 → 傾斜補正 → 領域切り出し → OCR → 照合HTML生成

変更履歴:
  v2.1 - 質問2「QRコードで回答」チェックボックス対応
       - 質問2行全体の確認用切り出し
       - 矛盾検出（QR+生年月日の整合性チェック）
       - 確認UI改善（行全体画像 + 個別OCR結果表示）
  v2.0 - 医師入力欄（質問14・15）追加
"""

import os
import sys
import json
import glob
import math
import base64
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

# 画像処理
try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False
    print("Warning: opencv-python がインストールされていません")

# PDF処理
try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False
    print("Warning: PyMuPDF がインストールされていません")

# PIL
try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from config import (
    RELATIVE_REGIONS, ANCHOR_POINTS, PATHS,
    INSTITUTION_MASTER, VALIDATION_RULES, REVIEW_GROUPS,
    CLAUDE_API, OCR_PROMPT_TEMPLATE,
)


# ============================================
# PDF → 画像変換
# ============================================

def pdf_to_image(pdf_path: str, dpi: int = 300) -> Optional[np.ndarray]:
    """PDFの1ページ目を画像に変換"""
    if not HAS_FITZ:
        print("Error: PyMuPDFが必要です。pip install PyMuPDF")
        return None

    doc = fitz.open(pdf_path)
    page = doc.load_page(0)
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)

    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
    if pix.n == 4:
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
    elif pix.n == 3:
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    doc.close()
    return img


def load_image(file_path: str) -> Optional[np.ndarray]:
    """画像またはPDFを読み込み"""
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        return pdf_to_image(file_path)
    else:
        return cv2.imread(file_path)


# ============================================
# 傾斜補正（2点参照方式）
# ============================================

def detect_skew_angle(gray: np.ndarray) -> float:
    """
    2点参照方式による傾き検出
    質問1と質問15の「質問」文字位置を基準点として使用
    """
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 100,
                            minLineLength=200, maxLineGap=10)

    if lines is None:
        return 0.0

    # 水平に近い線の角度を収集
    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
        if abs(angle) < 10:  # ±10度以内の水平線のみ
            angles.append(angle)

    if not angles:
        return 0.0

    return np.median(angles)


def correct_skew(image: np.ndarray) -> np.ndarray:
    """傾斜補正を適用"""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    angle = detect_skew_angle(gray)

    if abs(angle) < 0.1:
        return image

    print(f"  検出傾斜角: {angle:.2f}°")
    h, w = image.shape[:2]
    center = (w / 2, h / 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    corrected = cv2.warpAffine(image, M, (w, h),
                               flags=cv2.INTER_CUBIC,
                               borderMode=cv2.BORDER_REPLICATE)
    return corrected


# ============================================
# 領域切り出し
# ============================================

def extract_region(image: np.ndarray, region: dict) -> np.ndarray:
    """相対座標から画像領域を切り出す"""
    h, w = image.shape[:2]
    x = int(region["x"] * w)
    y = int(region["y"] * h)
    rw = int(region["width"] * w)
    rh = int(region["height"] * h)

    # 画像境界チェック
    x = max(0, min(x, w - 1))
    y = max(0, min(y, h - 1))
    rw = min(rw, w - x)
    rh = min(rh, h - y)

    return image[y:y + rh, x:x + rw]


def extract_all_regions(image: np.ndarray) -> Dict[str, np.ndarray]:
    """全領域を切り出し"""
    regions = {}
    for name, region in RELATIVE_REGIONS.items():
        try:
            roi = extract_region(image, region)
            if roi.size > 0:
                regions[name] = roi
        except Exception as e:
            print(f"  Warning: {name} 切り出し失敗 - {e}")
    return regions


# ============================================
# チェックボックス検出
# ============================================

def detect_checkbox(roi: np.ndarray, threshold: float = 0.25) -> bool:
    """
    チェックボックスの塗りつぶし/チェックマーク検出
    黒ピクセル比率で判定
    """
    if roi.size == 0:
        return False

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if len(roi.shape) == 3 else roi
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    black_ratio = np.sum(binary > 0) / binary.size
    return black_ratio > threshold


def detect_filled_box(roi: np.ndarray, options: list,
                      threshold: float = 0.15) -> Optional[str]:
    """
    複数選択肢の黒塗りチェックボックス検出
    各選択肢領域を均等分割し、黒ピクセル比率が最大のものを返す
    """
    if roi.size == 0 or not options:
        return None

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if len(roi.shape) == 3 else roi
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    h, w = binary.shape
    n = len(options)
    option_width = w // n

    max_ratio = 0
    selected = None

    for i, option in enumerate(options):
        x_start = i * option_width
        x_end = min(x_start + option_width, w)
        option_roi = binary[:, x_start:x_end]

        # チェックボックス部分（左側の一部）を重点的に見る
        checkbox_width = min(35, option_width // 4)
        checkbox = option_roi[:, :checkbox_width]
        black_ratio = np.sum(checkbox > 0) / checkbox.size

        if black_ratio > max_ratio and black_ratio > threshold:
            max_ratio = black_ratio
            selected = option

    return selected


# ============================================
# v2.1新規: 質問2バリデーション
# ============================================

def validate_q2_consistency(ocr_results: Dict[str, Any]) -> Dict[str, Any]:
    """
    質問2の矛盾検出
    「QRコードで回答」チェック有の場合、生年月日欄が空欄であることを確認

    Returns:
        {
            "has_warning": bool,
            "message": str,
            "severity": str,  # "warning" or "error"
            "details": dict
        }
    """
    qr_checked = ocr_results.get("質問2_QRコード回答", {}).get("value", False)

    if not qr_checked:
        return {"has_warning": False, "message": "", "severity": "none", "details": {}}

    # QRチェックありの場合、生年月日フィールドを確認
    birthdate_fields = ["質問2_元号", "質問2_年", "質問2_月", "質問2_日"]
    filled_fields = []

    for field in birthdate_fields:
        value = ocr_results.get(field, {}).get("value")
        if value is not None and str(value).strip():
            filled_fields.append(field)

    if filled_fields:
        rule = VALIDATION_RULES.get("qr_birthdate_consistency", {})
        return {
            "has_warning": True,
            "message": rule.get("message",
                "「QRコードで回答」にチェックがありますが、生年月日にも記入があります。"),
            "severity": rule.get("severity", "warning"),
            "details": {
                "qr_checked": True,
                "filled_birthdate_fields": filled_fields,
            }
        }

    return {"has_warning": False, "message": "", "severity": "none", "details": {}}


# ============================================
# 画像 → Base64変換（HTML埋め込み用）
# ============================================

def image_to_base64(image: np.ndarray) -> str:
    """OpenCV画像をBase64エンコード"""
    _, buffer = cv2.imencode('.png', image)
    return base64.b64encode(buffer).decode('utf-8')


# ============================================
# 照合用HTML生成
# ============================================

def generate_verification_html(
    regions: Dict[str, np.ndarray],
    ocr_results: Dict[str, Any],
    full_page_image: np.ndarray,
    validation_results: Dict[str, Any],
    output_path: str
) -> str:
    """照合用HTMLを生成（v2.1: 質問2行全体表示+矛盾検出対応）"""

    # 各切り出し画像をBase64に変換
    image_data = {}
    for name, roi in regions.items():
        image_data[name] = image_to_base64(roi)

    # 全体画像
    full_page_b64 = image_to_base64(full_page_image)

    # 質問2のバリデーション結果
    q2_validation = validation_results.get("質問2", {})

    html = _build_html(image_data, ocr_results, full_page_b64,
                       q2_validation, validation_results)

    # ファイル保存
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"  照合HTML: {output_path}")
    return output_path


def _build_html(
    image_data: Dict[str, str],
    ocr_results: Dict[str, Any],
    full_page_b64: str,
    q2_validation: Dict[str, Any],
    all_validations: Dict[str, Any],
) -> str:
    """HTML文字列を構築"""

    # --- 質問2セクション用HTML ---
    q2_warning_html = ""
    if q2_validation.get("has_warning"):
        severity_class = "warning" if q2_validation["severity"] == "warning" else "error"
        q2_warning_html = f"""
        <div class="validation-alert {severity_class}">
            ⚠️ {q2_validation['message']}
        </div>
        """

    # 質問2のOCRフィールドをテーブル行として生成
    q2_fields_html = ""
    q2_field_names = [
        ("質問2_元号", "元号"),
        ("質問2_年", "年"),
        ("質問2_月", "月"),
        ("質問2_日", "日"),
        ("質問2_QRコード回答", "QRコードで回答"),
    ]
    for field_key, label in q2_field_names:
        result = ocr_results.get(field_key, {})
        value = result.get("value", "")
        confidence = result.get("confidence", "low")

        # 表示値の整形
        if field_key == "質問2_QRコード回答":
            display_value = "✓ チェックあり" if value else "☐ チェックなし"
        else:
            display_value = str(value) if value else "(空欄)"

        confidence_class = {
            "high": "confirmed",
            "medium": "needs-review",
            "low": "needs-review",
        }.get(confidence, "needs-review")

        q2_fields_html += f"""
            <tr class="{confidence_class}">
                <td>{label}</td>
                <td>
                    <input type="text" class="ocr-value" data-field="{field_key}"
                           value="{display_value}" />
                </td>
                <td>
                    <span class="confidence-badge {confidence}">{confidence}</span>
                </td>
                <td>
                    <button class="btn-ok" onclick="confirmField(this, '{field_key}')">OK</button>
                    <button class="btn-edit" onclick="editField(this, '{field_key}')">編集</button>
                </td>
            </tr>
        """

    # --- 全体の質問セクション用HTML ---
    sections_html = ""
    processed_q2 = False

    for name, region_config in RELATIVE_REGIONS.items():
        # review_only フラグが立っているものはスキップ（質問2_行全体はQ2セクション内で表示）
        if region_config.get("review_only"):
            continue

        # 質問2のフィールドは専用セクションで処理
        if name.startswith("質問2_"):
            if not processed_q2:
                processed_q2 = True
                q2_row_b64 = image_data.get("質問2_行全体", "")
                sections_html += f"""
                <div class="section" id="section-q2">
                    <h3>質問2: 生年月日 + QRコード回答</h3>
                    {q2_warning_html}
                    <div class="review-image-container">
                        <img src="data:image/png;base64,{q2_row_b64}"
                             alt="質問2行全体" class="review-image-full-row" />
                    </div>
                    <table class="ocr-result-table">
                        <thead>
                            <tr>
                                <th>項目</th>
                                <th>OCR結果</th>
                                <th>信頼度</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            {q2_fields_html}
                        </tbody>
                    </table>
                </div>
                """
            continue

        # 通常の質問セクション
        b64 = image_data.get(name, "")
        result = ocr_results.get(name, {})
        value = result.get("value", "")
        confidence = result.get("confidence", "low")
        description = region_config.get("description", name)

        confidence_class = {
            "high": "confirmed",
            "medium": "needs-review",
            "low": "needs-review",
        }.get(confidence, "needs-review")

        sections_html += f"""
        <div class="section {confidence_class}" id="section-{name}">
            <h3>{description}</h3>
            <div class="field-row">
                <div class="field-image">
                    <img src="data:image/png;base64,{b64}" alt="{name}" />
                </div>
                <div class="field-result">
                    <input type="text" class="ocr-value" data-field="{name}"
                           value="{value if value else ''}" />
                    <span class="confidence-badge {confidence}">{confidence}</span>
                    <button class="btn-ok" onclick="confirmField(this, '{name}')">OK</button>
                    <button class="btn-edit" onclick="editField(this, '{name}')">編集</button>
                </div>
            </div>
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>糖化アンケート照合画面 v2.1</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', 'Hiragino Sans', sans-serif;
            background: #f5f5f5;
            padding: 20px;
        }}
        .header {{
            background: #1a73e8;
            color: white;
            padding: 16px 24px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .header h1 {{ font-size: 20px; }}
        .header .version {{ font-size: 12px; opacity: 0.8; }}

        /* 全体画像サムネイル */
        .full-page-thumb {{
            max-width: 200px;
            cursor: pointer;
            border: 2px solid #ddd;
            border-radius: 4px;
        }}
        .full-page-thumb:hover {{ border-color: #1a73e8; }}

        /* セクション共通 */
        .section {{
            background: white;
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 12px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            border-left: 4px solid #ddd;
        }}
        .section.confirmed {{ border-left-color: #34a853; }}
        .section.needs-review {{ border-left-color: #ea4335; }}
        .section h3 {{
            font-size: 14px;
            margin-bottom: 10px;
            color: #333;
        }}

        /* 質問2専用: 行全体画像 */
        .review-image-container {{
            background: #fafafa;
            border: 1px solid #e0e0e0;
            border-radius: 4px;
            padding: 8px;
            margin-bottom: 12px;
            overflow-x: auto;
        }}
        .review-image-full-row {{
            max-width: 100%;
            height: auto;
            display: block;
        }}

        /* バリデーション警告 */
        .validation-alert {{
            padding: 10px 14px;
            border-radius: 6px;
            margin-bottom: 12px;
            font-size: 13px;
            font-weight: 500;
        }}
        .validation-alert.warning {{
            background: #fff3cd;
            border: 1px solid #ffc107;
            color: #856404;
        }}
        .validation-alert.error {{
            background: #f8d7da;
            border: 1px solid #dc3545;
            color: #721c24;
        }}

        /* OCR結果テーブル */
        .ocr-result-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        .ocr-result-table th {{
            background: #f8f9fa;
            padding: 8px 10px;
            text-align: left;
            border-bottom: 2px solid #dee2e6;
            font-weight: 600;
        }}
        .ocr-result-table td {{
            padding: 8px 10px;
            border-bottom: 1px solid #eee;
            vertical-align: middle;
        }}
        .ocr-result-table tr.confirmed {{ background: #f0fff0; }}
        .ocr-result-table tr.needs-review {{ background: #fff8f0; }}

        /* フィールド行（通常質問用） */
        .field-row {{
            display: flex;
            gap: 16px;
            align-items: center;
        }}
        .field-image {{
            flex: 0 0 auto;
            max-width: 400px;
        }}
        .field-image img {{
            max-width: 100%;
            border: 1px solid #ddd;
            border-radius: 4px;
        }}
        .field-result {{
            flex: 1;
            display: flex;
            gap: 8px;
            align-items: center;
            flex-wrap: wrap;
        }}

        /* 入力フィールド */
        .ocr-value {{
            padding: 6px 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
            min-width: 120px;
        }}
        .ocr-value:focus {{
            border-color: #1a73e8;
            outline: none;
            box-shadow: 0 0 0 2px rgba(26,115,232,0.2);
        }}

        /* 信頼度バッジ */
        .confidence-badge {{
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 11px;
            font-weight: 600;
        }}
        .confidence-badge.high {{ background: #d4edda; color: #155724; }}
        .confidence-badge.medium {{ background: #fff3cd; color: #856404; }}
        .confidence-badge.low {{ background: #f8d7da; color: #721c24; }}

        /* ボタン */
        .btn-ok {{
            background: #34a853;
            color: white;
            border: none;
            padding: 6px 14px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
        }}
        .btn-ok:hover {{ background: #2d8f47; }}
        .btn-edit {{
            background: #fbbc04;
            color: #333;
            border: none;
            padding: 6px 14px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
        }}
        .btn-edit:hover {{ background: #e5a800; }}

        /* フッター操作バー */
        .footer-bar {{
            position: sticky;
            bottom: 0;
            background: white;
            padding: 12px 20px;
            box-shadow: 0 -2px 8px rgba(0,0,0,0.1);
            border-radius: 8px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 20px;
        }}
        .btn-save {{
            background: #1a73e8;
            color: white;
            border: none;
            padding: 10px 24px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
        }}
        .btn-save:hover {{ background: #155ab6; }}

        .progress-info {{
            font-size: 13px;
            color: #666;
        }}
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>糖化アンケート照合画面</h1>
            <span class="version">v2.1 - QRコード回答チェック対応</span>
        </div>
        <img src="data:image/png;base64,{full_page_b64}"
             class="full-page-thumb" alt="全体画像"
             onclick="window.open(this.src)" title="クリックで拡大" />
    </div>

    {sections_html}

    <div class="footer-bar">
        <div class="progress-info">
            確認済: <span id="confirmed-count">0</span> /
            <span id="total-count">0</span>
        </div>
        <div>
            <button class="btn-save" onclick="saveResults()">
                照合完了・保存
            </button>
        </div>
    </div>

    <script>
        // 確認済フィールドの追跡
        const confirmedFields = new Set();
        const totalFields = document.querySelectorAll('.ocr-value').length;
        document.getElementById('total-count').textContent = totalFields;

        function confirmField(btn, fieldName) {{
            const row = btn.closest('tr') || btn.closest('.section');
            if (row) {{
                row.classList.remove('needs-review');
                row.classList.add('confirmed');
            }}
            confirmedFields.add(fieldName);
            updateProgress();
        }}

        function editField(btn, fieldName) {{
            const row = btn.closest('tr') || btn.closest('.section');
            const input = row ? row.querySelector('.ocr-value') : null;
            if (input) {{
                input.focus();
                input.select();
            }}
            confirmedFields.delete(fieldName);
            if (row) {{
                row.classList.remove('confirmed');
                row.classList.add('needs-review');
            }}
            updateProgress();
        }}

        function updateProgress() {{
            document.getElementById('confirmed-count').textContent = confirmedFields.size;
        }}

        // Shift+OK で範囲一括確定
        document.addEventListener('click', function(e) {{
            if (e.shiftKey && e.target.classList.contains('btn-ok')) {{
                const allOkButtons = document.querySelectorAll('.btn-ok');
                const clickedIndex = Array.from(allOkButtons).indexOf(e.target);
                allOkButtons.forEach((btn, index) => {{
                    if (index <= clickedIndex) {{
                        const fieldName = btn.getAttribute('onclick')
                            .match(/'([^']+)'/)?.[1];
                        if (fieldName) confirmField(btn, fieldName);
                    }}
                }});
            }}
        }});

        function saveResults() {{
            const results = {{}};
            document.querySelectorAll('.ocr-value').forEach(input => {{
                results[input.dataset.field] = {{
                    value: input.value,
                    confirmed: confirmedFields.has(input.dataset.field)
                }};
            }});

            // JSONダウンロード
            const blob = new Blob([JSON.stringify(results, null, 2)],
                                  {{ type: 'application/json' }});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'survey_result.json';
            a.click();
            URL.revokeObjectURL(url);
        }}
    </script>
</body>
</html>"""


# ============================================
# メイン処理フロー
# ============================================

def process_survey(file_path: str) -> Dict[str, Any]:
    """
    アンケート処理メインフロー

    1. 画像読み込み
    2. 傾斜補正
    3. 全領域切り出し
    4. チェックボックス検出（質問2_QRコード回答含む）
    5. バリデーション（矛盾検出）
    6. 照合HTML生成

    Args:
        file_path: PDF/画像ファイルパス

    Returns:
        OCR結果辞書
    """
    print(f"処理開始: {file_path}")

    # 1. 画像読み込み
    print("  [1/6] 画像読み込み...")
    image = load_image(file_path)
    if image is None:
        print("Error: 画像の読み込みに失敗しました")
        return {}

    print(f"  画像サイズ: {image.shape[1]}x{image.shape[0]} px")

    # 2. 傾斜補正
    print("  [2/6] 傾斜補正...")
    corrected = correct_skew(image)

    # 全体画像を保存
    full_page_path = os.path.join(PATHS["cropped_images"], "full_page.png")
    os.makedirs(PATHS["cropped_images"], exist_ok=True)
    cv2.imwrite(full_page_path, corrected)

    # 3. 全領域切り出し
    print("  [3/6] 領域切り出し...")
    regions = extract_all_regions(corrected)

    # 切り出し画像を保存
    for name, roi in regions.items():
        safe_name = name.replace("/", "_").replace("\\", "_")
        path = os.path.join(PATHS["cropped_images"], f"{safe_name}.png")
        cv2.imwrite(path, roi)
    print(f"  切り出し完了: {len(regions)} 領域")

    # 4. OCR/チェックボックス検出
    print("  [4/6] OCR・チェックボックス検出...")
    ocr_results = {}

    for name, region_config in RELATIVE_REGIONS.items():
        if region_config.get("review_only"):
            continue

        roi = regions.get(name)
        if roi is None:
            ocr_results[name] = {"value": None, "confidence": "low"}
            continue

        field_type = region_config.get("type", "")

        if field_type == "checkbox_single" and name == "質問2_QRコード回答":
            # v2.1: QRコード回答チェックボックス
            checked = detect_checkbox(roi, threshold=0.20)
            ocr_results[name] = {
                "value": checked,
                "confidence": "medium",
                "raw_type": "checkbox",
            }
            print(f"    {name}: {'チェックあり' if checked else 'チェックなし'}")

        elif field_type == "filled_box":
            options = region_config.get("options", [])
            selected = detect_filled_box(roi, options)
            ocr_results[name] = {
                "value": selected,
                "confidence": "medium" if selected else "low",
            }

        elif field_type in ("checkbox_single",):
            options = region_config.get("options", [])
            selected = detect_filled_box(roi, options)
            ocr_results[name] = {
                "value": selected,
                "confidence": "medium" if selected else "low",
            }

        else:
            # 手書き文字・数値はClaude API or 手動
            ocr_results[name] = {
                "value": None,
                "confidence": "low",
                "note": "Claude APIまたは手動入力が必要"
            }

    # 5. バリデーション
    print("  [5/6] バリデーション...")
    validation_results = {}

    # 質問2の矛盾検出
    q2_validation = validate_q2_consistency(ocr_results)
    validation_results["質問2"] = q2_validation
    if q2_validation.get("has_warning"):
        print(f"    ⚠️ {q2_validation['message']}")

    # 6. 照合HTML生成
    print("  [6/6] 照合HTML生成...")
    generate_verification_html(
        regions=regions,
        ocr_results=ocr_results,
        full_page_image=corrected,
        validation_results=validation_results,
        output_path=PATHS["output_html"],
    )

    # JSON保存
    output = {
        "ocr_results": {k: v for k, v in ocr_results.items()},
        "validation": validation_results,
        "source_file": os.path.basename(file_path),
    }
    with open(PATHS["output_json"], 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"  JSON保存: {PATHS['output_json']}")

    print("処理完了!")
    return output


# ============================================
# CLI エントリーポイント
# ============================================

def select_pdf() -> Optional[str]:
    """Scan Dataフォルダ内のPDFを選択"""
    scan_dir = PATHS["scan_data"]
    if not os.path.exists(scan_dir):
        os.makedirs(scan_dir, exist_ok=True)
        print(f"'{scan_dir}' フォルダにPDFを配置してください。")
        return None

    files = sorted(glob.glob(os.path.join(scan_dir, "*.pdf")))
    files += sorted(glob.glob(os.path.join(scan_dir, "*.PDF")))
    files += sorted(glob.glob(os.path.join(scan_dir, "*.png")))
    files += sorted(glob.glob(os.path.join(scan_dir, "*.jpg")))

    if not files:
        print(f"'{scan_dir}' にファイルが見つかりません。")
        return None

    print("\n=== 処理するファイルを選択 ===")
    for i, f in enumerate(files, 1):
        print(f"  {i}. {os.path.basename(f)}")

    try:
        choice = int(input("\n番号を入力: ")) - 1
        if 0 <= choice < len(files):
            return files[choice]
    except (ValueError, EOFError):
        pass

    print("無効な選択です。")
    return None


if __name__ == "__main__":
    # コマンドライン引数があればそれを使用
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = select_pdf()

    if file_path and os.path.exists(file_path):
        process_survey(file_path)
    else:
        print("ファイルが見つかりません。")
