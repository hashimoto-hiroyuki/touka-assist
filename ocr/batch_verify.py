# -*- coding: utf-8 -*-
"""
アンケートPDF バッチ照合プログラム（LabelMe風ワークフロー）

- Scan Dataフォルダ内の全PDFを事前処理
- 各PDFに対応するJSONファイル（同名.json）から読み取り結果を読み込み
- 1つのHTMLで全ファイルを切り替えながら照合
- 確認完了→保存→Nextで次のファイルへ
- 確認済みJSONは同じフォルダに保存（_verified.json）
- ローカルHTTPサーバーで直接ファイル保存
"""

import fitz  # PyMuPDF
from PIL import Image, ImageDraw
import cv2
import numpy as np
import json
import os
import base64
import io
import shutil
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading
import webbrowser
import urllib.parse

# verify_survey.pyから必要な関数をインポート
from verify_survey import (
    pdf_to_image, ImageDeskewer, detect_paper_region,
    calculate_crop_regions_simple, crop_regions, save_cropped_images,
    image_to_base64, QUESTION_ORDER, QUESTION_LABELS
)

# 設定
BASE_DIR = Path(__file__).parent
SCAN_DATA_DIR = BASE_DIR / "Scan Data"
CHECKED_DATA_DIR = BASE_DIR / "Checked Data"
OUTPUT_DIR = BASE_DIR / "cropped_images"
BATCH_DATA_DIR = OUTPUT_DIR / "batch_data"
SERVER_PORT = 8765


class VerificationHandler(SimpleHTTPRequestHandler):
    """
    照合用HTTPハンドラ
    - GET: 静的ファイル配信
    - POST /save: JSON保存
    """

    def __init__(self, *args, **kwargs):
        # カレントディレクトリをcropped_imagesに設定
        super().__init__(*args, directory=str(OUTPUT_DIR), **kwargs)

    def do_POST(self):
        """POSTリクエストを処理（JSON保存）"""
        if self.path == '/save':
            try:
                # リクエストボディを読み取り
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))

                # 保存先パスを取得
                filename = data.get('filename', 'unknown_verified.json')
                json_data = data.get('data', {})

                # Scan Dataフォルダに保存
                save_path = SCAN_DATA_DIR / filename

                with open(save_path, 'w', encoding='utf-8') as f:
                    json.dump(json_data, f, ensure_ascii=False, indent=2)

                print(f"    [保存完了] {save_path}")

                # 成功レスポンス
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                response = {'status': 'success', 'path': str(save_path)}
                self.wfile.write(json.dumps(response).encode('utf-8'))

            except Exception as e:
                print(f"    [保存エラー] {e}")
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                response = {'status': 'error', 'message': str(e)}
                self.wfile.write(json.dumps(response).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        """CORSプリフライトリクエスト対応"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def log_message(self, format, *args):
        """ログを抑制（GETリクエストのログは非表示）"""
        if 'POST' in str(args):
            print(f"    [HTTP] {args[0]}")


def start_server():
    """ローカルHTTPサーバーを起動"""
    server = HTTPServer(('localhost', SERVER_PORT), VerificationHandler)
    print(f"\n[サーバー起動] http://localhost:{SERVER_PORT}/")
    server.serve_forever()


def get_pdf_files():
    """Scan Dataフォルダ内のPDFファイル一覧を取得"""
    if not SCAN_DATA_DIR.exists():
        os.makedirs(SCAN_DATA_DIR, exist_ok=True)
        return []

    pdf_files = set()
    for pattern in ["*.pdf", "*.PDF"]:
        for f in SCAN_DATA_DIR.glob(pattern):
            pdf_files.add(f)

    return sorted(list(pdf_files), key=lambda x: x.name.lower())


def load_ocr_result(pdf_path):
    """
    PDFファイルに対応するOCR結果JSONを読み込む

    JSONファイル名の規則:
    - PDFと同名: img20260114_15333920.json
    - または survey_result.json（従来形式、フォールバック）

    Returns:
        dict: OCR結果データ、見つからない場合は空のdict
    """
    # 同名のJSONファイルを探す
    json_path = pdf_path.with_suffix('.json')

    if json_path.exists():
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"    OCR結果読み込み: {json_path.name}")
                return data
        except Exception as e:
            print(f"    JSON読み込みエラー: {e}")

    # フォールバック: survey_result.json
    fallback_path = BASE_DIR / "survey_result.json"
    if fallback_path.exists():
        try:
            with open(fallback_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"    OCR結果読み込み（フォールバック）: survey_result.json")
                return data
        except Exception as e:
            print(f"    JSON読み込みエラー: {e}")

    print(f"    OCR結果なし（手動入力モード）")
    return {}


def format_ocr_value(key, value):
    """
    OCR結果の値を表示用文字列に変換
    """
    if value is None:
        return ""

    if isinstance(value, str):
        return value

    if isinstance(value, dict):
        # 質問ごとの特殊フォーマット
        if key == "患者さんID":
            return value.get("値", "")

        if "氏" in value and "名" in value:
            # 質問1_名前
            return f"氏: {value.get('氏', '')} / 名: {value.get('名', '')}"

        if "年号" in value:
            # 質問2_生年月日
            return f"{value.get('年号', '')} {value.get('年', '')}年{value.get('月', '')}月{value.get('日', '')}日"

        if "身長_cm" in value:
            # 質問5_身体情報
            return f"身長: {value.get('身長_cm', '')}cm / 体重: {value.get('体重_kg', '')}kg"

        if "回答" in value:
            # 選択式質問
            return value.get("回答", "")

        if "選択" in value:
            # 質問13_飲酒習慣
            lines = [f"選択: {value.get('選択', '')}"]
            if value.get('回答1'):
                r1 = value['回答1']
                lines.append(f"回答1: {r1.get('酒類', '')} 週{r1.get('頻度', '')} {r1.get('サイズ', '')} {r1.get('数量', '')}杯")
            return "\n".join(lines)

        if "左右" in value:
            # 質問14_歯の抜去位置
            return f"{value.get('左右', '')} / {value.get('上下', '')} / 番号: {value.get('番号', '')}"

        if "内容" in value:
            # 質問15_コメント
            return value.get("内容", "")

        # その他のdict
        return json.dumps(value, ensure_ascii=False)

    return str(value)


def process_single_pdf(pdf_path, output_folder):
    """
    単一のPDFを処理して画像を保存

    Returns:
        dict: 処理結果情報
    """
    result = {
        "filename": pdf_path.name,
        "filepath": str(pdf_path),
        "status": "error",
        "images": {},
        "skew_angle": 0,
        "base64_scan": None,
        "ocr_results": {}  # OCR結果を追加
    }

    try:
        # OCR結果を読み込み
        ocr_data = load_ocr_result(pdf_path)

        # OCR結果を整形して保存
        if ocr_data:
            # 医療機関名
            if "医療機関名" in ocr_data:
                result["ocr_results"]["医療機関名"] = ocr_data["医療機関名"]

            # 患者さんID
            if "患者さんID" in ocr_data:
                result["ocr_results"]["患者さんID"] = format_ocr_value("患者さんID", ocr_data["患者さんID"])

            # 回答データ
            if "回答データ" in ocr_data:
                for key, value in ocr_data["回答データ"].items():
                    result["ocr_results"][key] = format_ocr_value(key, value)

        # PDFを画像に変換
        image = pdf_to_image(pdf_path)

        # 傾斜補正
        deskewer = ImageDeskewer()
        corrected_image, skew_angle = deskewer.deskew(image, method="template")
        result["skew_angle"] = skew_angle

        # スキャン画像をBase64に変換
        result["base64_scan"] = image_to_base64(corrected_image)

        # 基準点を自動検出
        detection_info = detect_paper_region(corrected_image)

        # 切り出し座標を計算
        regions = calculate_crop_regions_simple(corrected_image, detection_info)

        # 各質問領域を切り取り
        cropped_images = crop_regions(corrected_image, regions)

        # 切り取り画像を保存
        os.makedirs(output_folder, exist_ok=True)
        saved_paths = save_cropped_images(cropped_images, output_folder)

        # 画像パスを相対パスで記録
        for name, path in saved_paths.items():
            rel_path = path.relative_to(OUTPUT_DIR)
            result["images"][name] = str(rel_path).replace("\\", "/")

        result["status"] = "success"
        result["question_count"] = len(regions)

    except Exception as e:
        result["error"] = str(e)
        print(f"    エラー: {e}")

    return result


def process_all_pdfs():
    """
    全PDFファイルを処理

    Returns:
        list: 各ファイルの処理結果
    """
    pdf_files = get_pdf_files()

    if not pdf_files:
        print("Scan Dataフォルダにpdfファイルがありません。")
        return []

    print(f"処理対象: {len(pdf_files)}ファイル")

    # バッチデータフォルダを作成
    os.makedirs(BATCH_DATA_DIR, exist_ok=True)

    all_results = []

    for i, pdf_path in enumerate(pdf_files):
        print(f"\n[{i+1}/{len(pdf_files)}] {pdf_path.name}")

        # 各PDFごとのフォルダを作成
        safe_name = pdf_path.stem.replace(" ", "_")
        output_folder = BATCH_DATA_DIR / safe_name

        result = process_single_pdf(pdf_path, output_folder)
        result["index"] = i
        result["folder"] = safe_name
        all_results.append(result)

        if result["status"] == "success":
            print(f"    完了: {result['question_count']}項目検出")
        else:
            print(f"    失敗: {result.get('error', '不明なエラー')}")

    return all_results


def create_batch_verification_html(all_results):
    """
    バッチ照合用HTMLを生成

    全ファイルのデータを含み、JavaScript でファイルを切り替える
    """

    # ファイルデータをJSON形式で埋め込み
    files_data = []
    for result in all_results:
        if result["status"] != "success":
            continue

        file_data = {
            "index": result["index"],
            "filename": result["filename"],
            "filepath": result["filepath"],
            "folder": result["folder"],
            "images": result["images"],
            "skew_angle": result["skew_angle"],
            "base64_scan": result["base64_scan"],
            "ocr_results": result.get("ocr_results", {}),  # OCR結果を追加
            "confirmed": False,
            "results": {}
        }
        files_data.append(file_data)

    files_json = json.dumps(files_data, ensure_ascii=False, indent=2)
    question_order_json = json.dumps(QUESTION_ORDER, ensure_ascii=False)

    html_content = f'''<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>アンケート照合 - バッチモード</title>
    <style>
        * {{
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Meiryo', sans-serif;
            margin: 0;
            padding: 0;
            display: flex;
            height: 100vh;
            background: #f5f5f5;
        }}

        /* サイドバー（ファイル一覧） */
        .sidebar {{
            width: 280px;
            background: #2c3e50;
            color: white;
            overflow-y: auto;
            flex-shrink: 0;
        }}
        .sidebar-header {{
            padding: 15px;
            background: #1a252f;
            font-size: 16px;
            font-weight: bold;
            border-bottom: 1px solid #34495e;
        }}
        .file-list {{
            list-style: none;
            padding: 0;
            margin: 0;
        }}
        .file-item {{
            padding: 12px 15px;
            cursor: pointer;
            border-bottom: 1px solid #34495e;
            display: flex;
            align-items: center;
            gap: 10px;
            transition: background 0.2s;
        }}
        .file-item:hover {{
            background: #34495e;
        }}
        .file-item.active {{
            background: #3498db;
        }}
        .file-item.completed {{
            background: #27ae60;
        }}
        .file-item.completed.active {{
            background: #2ecc71;
        }}
        .file-status {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: #7f8c8d;
            flex-shrink: 0;
        }}
        .file-item.completed .file-status {{
            background: #2ecc71;
        }}
        .file-name {{
            flex: 1;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            font-size: 13px;
        }}
        .file-index {{
            color: #95a5a6;
            font-size: 11px;
        }}

        /* メインエリア */
        .main-area {{
            flex: 1;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }}

        /* ヘッダー（ナビゲーション） */
        .nav-header {{
            background: white;
            padding: 15px 20px;
            display: flex;
            align-items: center;
            gap: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            flex-shrink: 0;
        }}
        .nav-button {{
            padding: 8px 16px;
            font-size: 14px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            transition: background 0.2s;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .nav-button:disabled {{
            opacity: 0.3;
            cursor: not-allowed;
        }}
        .nav-button.prev {{
            background: #95a5a6;
            color: white;
        }}
        .nav-button.prev:hover:not(:disabled) {{
            background: #7f8c8d;
        }}
        .nav-button.next {{
            background: #3498db;
            color: white;
        }}
        .nav-button.next:hover:not(:disabled) {{
            background: #2980b9;
        }}
        .current-file {{
            flex: 1;
            font-size: 18px;
            font-weight: bold;
            color: #2c3e50;
        }}
        .progress-info {{
            color: #7f8c8d;
            font-size: 14px;
        }}

        /* コンテンツエリア */
        .content-area {{
            flex: 1;
            overflow-y: auto;
            padding: 20px;
        }}

        /* 質問ブロック */
        .question-block {{
            background: white;
            margin: 15px 0;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .question-block.confirmed {{
            background: #f1f8e9;
            border-left: 4px solid #4CAF50;
        }}
        .question-title {{
            font-size: 16px;
            font-weight: bold;
            color: #2196F3;
            margin-bottom: 15px;
        }}
        .question-block.confirmed .question-title {{
            color: #4CAF50;
        }}
        .image-section {{
            margin-bottom: 15px;
        }}
        .image-section img {{
            max-width: 100%;
            border: 1px solid #ddd;
            border-radius: 4px;
        }}
        .result-section {{
            display: flex;
            align-items: center;
            gap: 15px;
            justify-content: flex-end;
        }}
        .result-label {{
            font-weight: bold;
            color: #666;
            flex-shrink: 0;
        }}
        .result-title {{
            color: #2196F3;
            font-weight: bold;
            margin-right: 10px;
        }}
        .result-input {{
            font-size: 16px;
            padding: 10px 15px;
            background: #e8f5e9;
            border: 2px solid #a5d6a7;
            border-radius: 4px;
            min-width: 200px;
            font-family: inherit;
        }}
        .result-input:focus {{
            outline: none;
            border-color: #4CAF50;
            background: #fff;
        }}
        .result-input.confirmed {{
            background: #c8e6c9;
            border-color: #4CAF50;
        }}
        .result-input:disabled {{
            background: #c8e6c9;
            color: #333;
        }}
        textarea.result-input {{
            resize: vertical;
            min-height: 60px;
        }}
        .ok-button {{
            padding: 8px 16px;
            background: #4CAF50;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            display: flex;
            align-items: center;
            gap: 4px;
        }}
        .ok-button:hover {{
            background: #388E3C;
        }}
        .ok-button:disabled {{
            background: #a5d6a7;
            cursor: not-allowed;
        }}
        .edit-button {{
            padding: 8px 16px;
            background: #ff9800;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            display: none;
            align-items: center;
            gap: 4px;
        }}
        .edit-button:hover {{
            background: #f57c00;
        }}
        .question-block.confirmed .edit-button {{
            display: flex;
        }}
        .question-block.confirmed .ok-button {{
            display: none;
        }}

        /* フッター（保存ボタン） */
        .footer {{
            background: white;
            padding: 15px 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 20px;
            box-shadow: 0 -2px 4px rgba(0,0,0,0.1);
            flex-shrink: 0;
        }}
        .save-button {{
            padding: 15px 40px;
            font-size: 16px;
            font-weight: bold;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }}
        .save-button.complete {{
            background: #27ae60;
            color: white;
        }}
        .save-button.complete:hover {{
            background: #219a52;
        }}
        .save-button.complete:disabled {{
            background: #95a5a6;
            cursor: not-allowed;
        }}
        .status-message {{
            padding: 10px;
            border-radius: 4px;
            display: none;
        }}
        .status-message.success {{
            display: block;
            background: #d4edda;
            color: #155724;
        }}
        .status-message.error {{
            display: block;
            background: #f8d7da;
            color: #721c24;
        }}

        /* ヘルプボタン */
        .help-button {{
            position: fixed;
            bottom: 20px;
            right: 20px;
            width: 40px;
            height: 40px;
            background: #3498db;
            color: white;
            border: none;
            border-radius: 50%;
            cursor: pointer;
            font-size: 20px;
            font-weight: bold;
            z-index: 100;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        }}
        .help-button:hover {{
            background: #2980b9;
        }}

        /* キーボードショートカットヘルプ（ポップアップ） */
        .shortcuts-help {{
            position: fixed;
            bottom: 70px;
            right: 20px;
            background: rgba(0,0,0,0.9);
            color: white;
            padding: 15px 20px;
            border-radius: 8px;
            font-size: 13px;
            z-index: 100;
            display: none;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }}
        .shortcuts-help.show {{
            display: block;
        }}
        .shortcuts-help h4 {{
            margin: 0 0 10px 0;
            font-size: 14px;
            border-bottom: 1px solid #555;
            padding-bottom: 8px;
        }}
        .shortcuts-help div {{
            margin: 6px 0;
        }}
        .shortcuts-help kbd {{
            background: #555;
            padding: 3px 8px;
            border-radius: 3px;
            margin-right: 8px;
            font-family: monospace;
        }}
    </style>
</head>
<body>
    <!-- サイドバー -->
    <div class="sidebar">
        <div class="sidebar-header">
            ファイル一覧 (<span id="completed-count">0</span>/<span id="total-count">0</span>)
        </div>
        <ul class="file-list" id="file-list">
        </ul>
    </div>

    <!-- メインエリア -->
    <div class="main-area">
        <!-- ナビゲーションヘッダー -->
        <div class="nav-header">
            <button class="nav-button prev" onclick="prevFile()" id="prev-btn" title="前へ">◀ 前へ</button>
            <div class="current-file" id="current-file">ファイルを選択してください</div>
            <div class="progress-info" id="progress-info"></div>
            <button class="nav-button next" onclick="nextFile()" id="next-btn" title="次へ">次へ ▶</button>
        </div>

        <!-- コンテンツエリア -->
        <div class="content-area" id="content-area">
            <p style="text-align: center; color: #7f8c8d; margin-top: 100px;">
                左のファイル一覧からファイルを選択してください
            </p>
        </div>

        <!-- フッター -->
        <div class="footer">
            <button class="save-button complete" onclick="saveAndNext()" id="save-btn" disabled>
                確認完了・保存して次へ
            </button>
            <div class="status-message" id="status-message"></div>
        </div>
    </div>

    <!-- ヘルプボタン -->
    <button class="help-button" onclick="toggleHelp()" title="操作方法">?</button>

    <!-- キーボードショートカット（ポップアップ） -->
    <div class="shortcuts-help" id="shortcuts-help">
        <h4>操作方法</h4>
        <div style="margin-bottom: 8px; color: #aaa;">キーボード</div>
        <div><kbd>←</kbd> 前のファイル</div>
        <div><kbd>→</kbd> 次のファイル</div>
        <div><kbd>Enter</kbd> 保存して次へ</div>
        <div><kbd>Shift</kbd>+<kbd>Enter</kbd> 全項目OK</div>
        <div style="margin-top: 12px; margin-bottom: 8px; color: #aaa;">ボタン</div>
        <div><span style="background:#4CAF50;color:white;padding:2px 8px;border-radius:3px;margin-right:8px;">✓ OK</span> 項目を確定</div>
        <div><span style="background:#ff9800;color:white;padding:2px 8px;border-radius:3px;margin-right:8px;">✎ 編集</span> 確定を解除して編集</div>
        <div style="margin-top: 12px; margin-bottom: 8px; color: #aaa;">保存</div>
        <div style="font-size: 12px;">保存先: Scan Data フォルダ</div>
        <div style="font-size: 12px;">ファイル名: [元PDF名]_verified.json</div>
        <div style="margin-top: 10px; color: #aaa; font-size: 11px;">クリックで閉じる</div>
    </div>

    <script>
        // ファイルデータ
        const filesData = {files_json};
        const questionOrder = {question_order_json};

        // 現在の状態
        let currentFileIndex = -1;
        let confirmedItems = {{}};

        // ヘルプ表示切り替え
        function toggleHelp() {{
            const help = document.getElementById('shortcuts-help');
            help.classList.toggle('show');
        }}

        // ヘルプをクリックで閉じる
        document.getElementById('shortcuts-help').addEventListener('click', function() {{
            this.classList.remove('show');
        }});

        // 初期化
        function init() {{
            document.getElementById('total-count').textContent = filesData.length;
            renderFileList();
            updateCompletedCount();

            // 最初のファイルを選択
            if (filesData.length > 0) {{
                selectFile(0);
            }}
        }}

        // ファイル一覧を描画
        function renderFileList() {{
            const list = document.getElementById('file-list');
            list.innerHTML = '';

            filesData.forEach((file, index) => {{
                const li = document.createElement('li');
                li.className = 'file-item' + (file.confirmed ? ' completed' : '');
                li.onclick = () => selectFile(index);
                li.innerHTML = `
                    <span class="file-status"></span>
                    <span class="file-name">${{file.filename}}</span>
                    <span class="file-index">#${{index + 1}}</span>
                `;
                list.appendChild(li);
            }});
        }}

        // ファイルを選択
        function selectFile(index) {{
            if (index < 0 || index >= filesData.length) return;

            // 前のファイルの状態を保存
            if (currentFileIndex >= 0) {{
                saveCurrentState();
            }}

            currentFileIndex = index;
            const file = filesData[index];

            // UI更新
            document.querySelectorAll('.file-item').forEach((item, i) => {{
                item.classList.toggle('active', i === index);
            }});

            document.getElementById('current-file').textContent = file.filename;
            document.getElementById('progress-info').textContent =
                `${{index + 1}} / ${{filesData.length}}`;

            // ナビゲーションボタン
            document.getElementById('prev-btn').disabled = (index === 0);
            document.getElementById('next-btn').disabled = (index === filesData.length - 1);

            // コンテンツを描画
            renderQuestions(file);

            // 保存ボタンの状態
            updateSaveButton();
        }}

        // 質問を描画
        function renderQuestions(file) {{
            const content = document.getElementById('content-area');
            let html = '';

            questionOrder.forEach((name, qIndex) => {{
                const imagePath = file.images[name];
                if (!imagePath) return;

                const isConfirmed = file.results[name] !== undefined;
                // 確定済みの値、またはOCR結果、またはを空文字を初期値として使用
                const value = file.results[name] || file.ocr_results[name] || '';

                // 入力フィールドのタイプを決定
                let inputElement;
                const inputId = `input_${{qIndex}}`;

                // 特殊文字をエスケープ
                const escapedValue = value.replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

                if (name === '質問13_飲酒習慣' || name === '質問15_コメント') {{
                    inputElement = `<textarea id="${{inputId}}" class="result-input${{isConfirmed ? ' confirmed' : ''}}"
                        rows="5" style="min-width: 500px;" ${{isConfirmed ? 'disabled' : ''}}>${{value}}</textarea>`;
                }} else if (['質問1_名前', '質問2_生年月日', '質問5_身体情報'].includes(name)) {{
                    inputElement = `<textarea id="${{inputId}}" class="result-input${{isConfirmed ? ' confirmed' : ''}}"
                        rows="2" style="min-width: 350px;" ${{isConfirmed ? 'disabled' : ''}}>${{value}}</textarea>`;
                }} else {{
                    inputElement = `<input type="text" id="${{inputId}}" class="result-input${{isConfirmed ? ' confirmed' : ''}}"
                        value="${{escapedValue}}" ${{isConfirmed ? 'disabled' : ''}}>`;
                }}

                html += `
                <div class="question-block${{isConfirmed ? ' confirmed' : ''}}" id="block_${{qIndex}}" data-name="${{name}}">
                    <div class="question-title">${{name}}</div>
                    <div class="image-section">
                        <img src="batch_data/${{file.folder}}/${{imagePath.split('/').pop()}}" alt="${{name}}">
                    </div>
                    <div class="result-section">
                        <span class="result-label">読み取り結果:</span>
                        <span class="result-title">${{name}}</span>
                        ${{inputElement}}
                        <button class="ok-button" onclick="confirmItem(${{qIndex}})" title="確定">✓ OK</button>
                        <button class="edit-button" onclick="editItem(${{qIndex}})" title="編集">✎ 編集</button>
                    </div>
                </div>
                `;
            }});

            content.innerHTML = html;
        }}

        // 項目を確定
        function confirmItem(qIndex) {{
            const block = document.getElementById('block_' + qIndex);
            const input = document.getElementById('input_' + qIndex);
            const name = block.dataset.name;

            // 現在のファイルに結果を保存
            filesData[currentFileIndex].results[name] = input.value;

            // UI更新
            block.classList.add('confirmed');
            input.classList.add('confirmed');
            input.disabled = true;

            updateSaveButton();
        }}

        // 項目を編集
        function editItem(qIndex) {{
            const block = document.getElementById('block_' + qIndex);
            const input = document.getElementById('input_' + qIndex);
            const name = block.dataset.name;

            // 確定を解除
            delete filesData[currentFileIndex].results[name];

            // UI更新
            block.classList.remove('confirmed');
            input.classList.remove('confirmed');
            input.disabled = false;
            input.focus();

            updateSaveButton();
        }}

        // 全項目を確定
        function confirmAllItems() {{
            questionOrder.forEach((name, qIndex) => {{
                const block = document.getElementById('block_' + qIndex);
                if (block && !block.classList.contains('confirmed')) {{
                    confirmItem(qIndex);
                }}
            }});
        }}

        // 現在の状態を保存
        function saveCurrentState() {{
            if (currentFileIndex < 0) return;

            // 入力値を保存
            questionOrder.forEach((name, qIndex) => {{
                const input = document.getElementById('input_' + qIndex);
                if (input && !input.disabled) {{
                    // 未確定の値も一時保存
                }}
            }});
        }}

        // 保存ボタンの状態を更新
        function updateSaveButton() {{
            if (currentFileIndex < 0) return;

            const file = filesData[currentFileIndex];
            const confirmedCount = Object.keys(file.results).length;
            const totalCount = Object.keys(file.images).length;

            const btn = document.getElementById('save-btn');
            // 1つ以上確定していれば保存可能（全項目必須ではない）
            btn.disabled = false;

            if (confirmedCount >= totalCount) {{
                btn.textContent = '確認完了・保存して次へ';
            }} else {{
                btn.textContent = `保存して次へ (${{confirmedCount}}/${{totalCount}} 確定)`;
            }}
        }}

        // 完了数を更新
        function updateCompletedCount() {{
            const count = filesData.filter(f => f.confirmed).length;
            document.getElementById('completed-count').textContent = count;
            renderFileList();
        }}

        // 保存して次へ（確認ダイアログ付き）
        async function saveAndNext() {{
            if (currentFileIndex < 0) return;

            const file = filesData[currentFileIndex];

            // ファイル名: PDFと同名_verified.json
            const baseName = file.filename.replace(/\\.pdf$/i, '');
            const defaultFilename = `${{baseName}}_verified.json`;

            // 確認ダイアログを表示
            const saveFilename = prompt(
                '保存するファイル名を確認してください。\\n\\n保存先: Scan Data フォルダ',
                defaultFilename
            );

            // キャンセルされた場合は中止
            if (saveFilename === null) {{
                return;
            }}

            // 空のファイル名チェック
            if (!saveFilename.trim()) {{
                showStatus('ファイル名が空です', 'error');
                return;
            }}

            // JSONデータを生成
            const jsonData = {{
                "ファイル名": file.filename,
                "元ファイルパス": file.filepath,
                "照合日時": new Date().toISOString(),
                "傾斜角度": file.skew_angle,
                "医療機関名": file.results["医療機関名"] || file.ocr_results["医療機関名"] || "",
                "患者さんID": file.results["患者さんID"] || file.ocr_results["患者さんID"] || "",
                "回答データ": {{}},
                "スキャン画像_base64": file.base64_scan
            }};

            // 回答データを整理
            questionOrder.forEach(name => {{
                if (name !== "医療機関名" && name !== "患者さんID") {{
                    jsonData["回答データ"][name] = file.results[name] || file.ocr_results[name] || "";
                }}
            }});

            // サーバーに保存リクエスト
            try {{
                const response = await fetch('/save', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json'
                    }},
                    body: JSON.stringify({{
                        filename: saveFilename,
                        data: jsonData
                    }})
                }});

                const result = await response.json();

                if (result.status === 'success') {{
                    // 完了マーク
                    file.confirmed = true;
                    updateCompletedCount();

                    // ステータスメッセージ
                    showStatus('保存完了: ' + saveFilename, 'success');

                    // 次のファイルへ
                    setTimeout(() => {{
                        if (currentFileIndex < filesData.length - 1) {{
                            selectFile(currentFileIndex + 1);
                        }} else {{
                            showStatus('全てのファイルの照合が完了しました！', 'success');
                        }}
                    }}, 500);
                }} else {{
                    showStatus('保存エラー: ' + result.message, 'error');
                }}
            }} catch (error) {{
                showStatus('通信エラー: ' + error.message, 'error');
            }}
        }}

        // ステータスメッセージを表示
        function showStatus(message, type) {{
            const el = document.getElementById('status-message');
            el.textContent = message;
            el.className = 'status-message ' + type;

            setTimeout(() => {{
                el.className = 'status-message';
            }}, 3000);
        }}

        // ナビゲーション
        function prevFile() {{
            if (currentFileIndex > 0) {{
                selectFile(currentFileIndex - 1);
            }}
        }}

        function nextFile() {{
            if (currentFileIndex < filesData.length - 1) {{
                selectFile(currentFileIndex + 1);
            }}
        }}

        // キーボードショートカット
        document.addEventListener('keydown', (e) => {{
            if (e.key === 'ArrowLeft') {{
                prevFile();
            }} else if (e.key === 'ArrowRight') {{
                nextFile();
            }} else if (e.key === 'Enter' && e.shiftKey) {{
                e.preventDefault();
                confirmAllItems();
            }} else if (e.key === 'Enter' && !e.target.matches('textarea')) {{
                e.preventDefault();
                const btn = document.getElementById('save-btn');
                if (!btn.disabled) {{
                    saveAndNext();
                }}
            }}
        }});

        // 初期化実行
        init();
    </script>
</body>
</html>
'''

    html_path = OUTPUT_DIR / "batch_verification.html"
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    return html_path


def main():
    print("=" * 60)
    print("アンケート照合 バッチモード（LabelMe風ワークフロー）")
    print("=" * 60)

    # 出力ディレクトリを作成
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(CHECKED_DATA_DIR, exist_ok=True)

    # 全PDFを処理
    print("\n[1] 全PDFファイルを処理中...")
    all_results = process_all_pdfs()

    if not all_results:
        print("\n処理するファイルがありません。")
        print(f"Scan Dataフォルダにpdfファイルを配置してください: {SCAN_DATA_DIR}")
        return

    # 成功したファイル数
    success_count = sum(1 for r in all_results if r["status"] == "success")
    print(f"\n処理完了: {success_count}/{len(all_results)} ファイル")

    # HTMLを生成
    print("\n[2] 照合用HTMLを生成中...")
    html_path = create_batch_verification_html(all_results)
    print(f"    生成完了: {html_path}")

    # 完了メッセージ
    print("\n" + "=" * 60)
    print("準備完了")
    print("=" * 60)

    print("\n【操作方法】")
    print("  ← → キー: ファイル切り替え")
    print("  Enter: 保存して次へ")
    print("  Shift+Enter: 全項目OK")
    print("\n終了するには Ctrl+C を押してください")

    # サーバーを別スレッドで起動
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    # ブラウザで自動的に開く
    import time
    time.sleep(0.5)
    url = f"http://localhost:{SERVER_PORT}/batch_verification.html"
    print(f"\n[ブラウザ起動] {url}")
    webbrowser.open(url)

    # メインスレッドを維持（Ctrl+Cで終了）
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n終了しました。")


if __name__ == "__main__":
    main()
