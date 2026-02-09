"""
Claude API OCR処理モジュール v2.1
Claude APIを使用して画像からテキストを抽出

変更履歴:
  v2.1 - 全ページプロンプトに「QRコードで回答」フィールド追加
"""

import base64
import json
import os
from typing import Dict, Any, Optional
from pathlib import Path

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

from config import CLAUDE_API, OCR_PROMPT_TEMPLATE, RELATIVE_REGIONS


class ClaudeOCR:
    """Claude APIを使用したOCR処理クラス"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")

        if HAS_ANTHROPIC and self.api_key:
            self.client = anthropic.Anthropic(api_key=self.api_key)
        else:
            self.client = None
            if not self.api_key:
                print("Warning: ANTHROPIC_API_KEY が設定されていません")

    def is_available(self) -> bool:
        return self.client is not None

    def _image_to_base64(self, image) -> str:
        """OpenCV画像 or ファイルパスをBase64に変換"""
        if isinstance(image, str):
            with open(image, "rb") as f:
                return base64.standard_b64encode(f.read()).decode("utf-8")
        elif HAS_CV2:
            _, buffer = cv2.imencode('.png', image)
            return base64.standard_b64encode(buffer).decode("utf-8")
        raise ValueError("画像の変換に失敗しました")

    def recognize_field(self, image, field_name: str,
                        field_config: dict) -> Dict[str, Any]:
        """
        個別フィールドのOCR処理

        Args:
            image: 切り出し画像（np.ndarray or ファイルパス）
            field_name: フィールド名
            field_config: フィールド設定（RELATIVE_REGIONSの値）

        Returns:
            {"value": ..., "confidence": "high"/"medium"/"low"}
        """
        if not self.is_available():
            return {"value": None, "confidence": "low",
                    "note": "Claude API未接続"}

        description = field_config.get("description", field_name)
        field_type = field_config.get("type", "unknown")
        options = field_config.get("options", [])

        prompt = self._build_field_prompt(field_name, description,
                                          field_type, options)

        try:
            b64 = self._image_to_base64(image)
            response = self.client.messages.create(
                model=CLAUDE_API["model"],
                max_tokens=CLAUDE_API["max_tokens"],
                temperature=CLAUDE_API["temperature"],
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": b64,
                            }
                        },
                        {"type": "text", "text": prompt}
                    ]
                }]
            )

            text = response.content[0].text
            return self._parse_response(text)

        except Exception as e:
            print(f"  Claude API Error ({field_name}): {e}")
            return {"value": None, "confidence": "low", "error": str(e)}

    def recognize_full_page(self, image) -> Dict[str, Any]:
        """
        全ページ一括OCR処理（v2.1: QRコード回答フィールド追加）

        Args:
            image: 全ページ画像

        Returns:
            全フィールドのOCR結果辞書
        """
        if not self.is_available():
            return {}

        prompt = self._create_full_page_prompt()

        try:
            b64 = self._image_to_base64(image)
            response = self.client.messages.create(
                model=CLAUDE_API["model"],
                max_tokens=CLAUDE_API["max_tokens"],
                temperature=CLAUDE_API["temperature"],
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": b64,
                            }
                        },
                        {"type": "text", "text": prompt}
                    ]
                }]
            )

            text = response.content[0].text
            return self._parse_full_page_response(text)

        except Exception as e:
            print(f"  Claude API Error (full page): {e}")
            return {}

    def _build_field_prompt(self, field_name: str, description: str,
                            field_type: str, options: list) -> str:
        """個別フィールド用プロンプト構築"""
        field_desc = f"フィールド: {field_name}\n説明: {description}\n"
        field_desc += f"データタイプ: {field_type}\n"

        if options:
            field_desc += f"選択肢: {', '.join(options)}\n"

        if field_type == "checkbox_single" and "QRコード" in field_name:
            field_desc += "注意: チェックマーク（✓）や黒塗り（■）があるかどうかを判定してください。\n"
            field_desc += "チェックがあれば true、なければ false で回答してください。\n"

        return OCR_PROMPT_TEMPLATE.format(field_description=field_desc)

    def _create_full_page_prompt(self) -> str:
        """
        全ページ一括読み取りプロンプト（v2.1更新）
        """
        return """この画像は「糖化アンケート」の回答用紙です。
全ての質問の回答を読み取り、以下のJSON形式で出力してください。

【出力形式】
```json
{
  "医療機関名": {"value": "...", "confidence": "high/medium/low"},
  "患者ID": {"value": "...", "confidence": "high/medium/low"},
  "質問1_氏": {"value": "...", "confidence": "..."},
  "質問1_名": {"value": "...", "confidence": "..."},
  "質問2_元号": {"value": "昭和/平成/令和のいずれか", "confidence": "..."},
  "質問2_年": {"value": "数値", "confidence": "..."},
  "質問2_月": {"value": "数値", "confidence": "..."},
  "質問2_日": {"value": "数値", "confidence": "..."},
  "質問2_QRコード回答": {"value": true/false, "confidence": "..."},
  "質問3_性別": {"value": "男/女/回答しない", "confidence": "..."},
  "質問4_血液型": {"value": "A型/B型/O型/AB型/わからない", "confidence": "..."},
  "質問5_身長": {"value": "数値", "confidence": "..."},
  "質問5_体重": {"value": "数値", "confidence": "..."},
  "質問6_糖尿病": {"value": "なし/5年未満/5〜10年前/10年以上前/わからない", "confidence": "..."},
  "質問7_脂質異常症": {"value": "同上の選択肢", "confidence": "..."},
  "質問8_兄弟糖尿病歴": {"value": "はい/いいえ/わからない", "confidence": "..."},
  "質問9_両親糖尿病歴": {"value": "はい/いいえ/わからない", "confidence": "..."},
  "質問10_運動しない": {"value": "はい/いいえ", "confidence": "..."},
  "質問11_お菓子頻度": {"value": "ほぼ毎日/週2~3回/週1回以下または食べない", "confidence": "..."},
  "質問12_飲み物": {"value": "有糖飲料/無糖飲料", "confidence": "..."},
  "質問13_飲酒": {"value": "飲む/ほとんど飲まない", "confidence": "..."},
  "質問13_飲酒詳細": {"value": "自由記述（飲む場合の詳細）", "confidence": "..."},
  "質問14_歯の抜去位置": {"value": "記入された歯の位置", "confidence": "..."},
  "質問15_コメント欄": {"value": "自由記述", "confidence": "..."}
}
```

【読み取りルール】
1. 手書き文字は丁寧に判読してください
2. チェックマーク（✓）や黒塗り（■）を検出してください
3. 数字は半角で出力してください
4. カタカナはそのまま出力してください
5. 空欄の場合は value を null にしてください
6. confidence は読み取りの確実性に応じて設定してください:
   - "high": はっきり読める
   - "medium": 概ね判読可能だが確認推奨
   - "low": 判読困難

【v2.1追加フィールド: 質問2_QRコード回答】
質問2の行の右端に「□以降、QRコードで回答」というチェックボックスがあります。
チェックマーク（✓）や黒塗り（■）がある場合は true、ない場合は false を返してください。

【注意】
- 元号は丸で囲まれたものを選択してください
- 質問6, 7の選択肢は黒塗り（■）で選ばれます
- 質問13の飲酒詳細は、「飲む」にチェックがある場合のみ記載してください

JSONのみを出力してください（説明文は不要）。
"""

    def _parse_response(self, text: str) -> Dict[str, Any]:
        """Claude APIレスポンスをパース"""
        try:
            # JSON部分を抽出
            text = text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                text = text.rsplit("```", 1)[0]
            return json.loads(text)
        except json.JSONDecodeError:
            return {"value": text.strip(), "confidence": "low",
                    "raw_response": text}

    def _parse_full_page_response(self, text: str) -> Dict[str, Any]:
        """全ページレスポンスをパース"""
        try:
            text = text.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:])
                text = text.rsplit("```", 1)[0]
            return json.loads(text)
        except json.JSONDecodeError:
            print(f"  Warning: JSONパース失敗")
            return {}
