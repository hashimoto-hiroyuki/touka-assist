# 糖化アンケートOCR照合システム v2.1

## 概要
北海道大学病院の「糖化アンケート」紙フォーマットをOCRでデジタル化するシステム。

## v2.1 変更点
- **質問2に「□以降、QRコードで回答」チェックボックス追加**
  - 新規座標: `質問2_QRコード回答` (checkbox検出)
  - 新規座標: `質問2_行全体` (確認UI用の行全体切り出し)
- **矛盾検出（バリデーション）**
  - QRチェックあり + 生年月日記入あり → 「要確認」警告
  - `VALIDATION_RULES` で定義、拡張可能
- **確認UI改善**
  - 質問2: 行全体画像 + 個別フィールドOCR結果のテーブル表示
  - バリデーション警告の視覚表示

## ファイル構成
```
touka-ocr/
├── verify_survey.py       # メインプログラム（PDF処理→照合HTML生成）
├── ocr_claude.py          # Claude API OCRモジュール
├── config.py              # 座標定義・設定・バリデーションルール
├── start_verification.bat # 起動バッチ
├── setup.bat              # 初回セットアップ
├── requirements.txt       # Python依存パッケージ
├── CLAUDE.md              # 本ファイル
├── Scan Data/             # スキャンPDF配置先
├── Checked Data/          # 照合完了後の移動先
└── cropped_images/        # 切り出し画像・HTML出力先
```

## アンケート構成（質問項目）

### 患者記入欄
| 質問 | 内容 | 回答タイプ |
|------|------|-----------|
| ヘッダー | 医療機関名、患者ID | 印字/手書きボックス |
| 質問1 | 名前（カタカナ） | 手書きカタカナ |
| 質問2 | 生年月日 + **QRコード回答チェック** | 丸囲み + 手書き数字 + チェックボックス |
| 質問3 | 性別 | チェックボックス |
| 質問4 | 血液型 | チェックボックス |
| 質問5 | 身長・体重 | 手書き数字 |
| 質問6 | 糖尿病 | 黒塗りチェック |
| 質問7 | 脂質異常症 | 黒塗りチェック |
| 質問8 | 兄弟に糖尿病歴 | 黒塗りチェック |
| 質問9 | 両親に糖尿病歴 | 黒塗りチェック |
| 質問10 | 運動習慣 | 黒塗りチェック |
| 質問11 | お菓子頻度 | 黒塗りチェック |
| 質問12 | 飲み物 | 黒塗りチェック |
| 質問13 | 飲酒習慣 | 複合回答 |

### 医師入力欄
| 質問 | 内容 | 回答タイプ |
|------|------|-----------|
| 質問14 | 歯の抜去位置 | 手書き |
| 質問15 | コメント欄（HbA1c等） | 手書き |

## 座標定義

`config.py` の `RELATIVE_REGIONS` で定義。座標はページ全体に対する比率 (0.0〜1.0)。

### v2.1で追加された領域
```python
"質問2_QRコード回答": {
    "x": 0.72, "y": 0.158, "width": 0.025, "height": 0.020,
    "type": "checkbox_single",
    ...
}

"質問2_行全体": {
    "x": 0.03, "y": 0.155, "width": 0.94, "height": 0.025,
    "type": "review_image",
    "review_only": True,  # OCR対象外、確認UI用
}
```

## バリデーションルール

`config.py` の `VALIDATION_RULES` で定義。

```python
"qr_birthdate_consistency": {
    "trigger_field": "質問2_QRコード回答",
    "trigger_value": True,
    "check_fields": ["質問2_元号", "質問2_年", "質問2_月", "質問2_日"],
    "expected": "empty",
    "severity": "warning",
}
```

## 使い方
```powershell
# 1. セットアップ（初回のみ）
setup.bat

# 2. APIキー設定（OCR自動読み取り時）
$env:ANTHROPIC_API_KEY = "your-api-key"

# 3. PDFを Scan Data フォルダに配置

# 4. 実行
start_verification.bat

# 5. ブラウザで照合画面を確認・修正・保存
```

## Important Notes
- pipインストール時は必ずvenvを指定: `.\venv\Scripts\pip.exe install パッケージ名`
- 質問2_QRコード回答のチェックボックス座標は、テンプレート変更時に要調整
- `review_only: True` のフィールドはOCR処理をスキップし、確認UI画像のみ切り出す
