# 🦷 Touka Assist - 糖化アンケート入力システム

歯科医院向けの糖化アンケートOCR入力支援Webアプリケーションです。

## ✨ 機能

- 📷 **画像アップロード**: PNG, JPG, JPEG, BMP, TIFF対応
- 📄 **PDFアップロード**: 複数ページPDFに対応（ページ切り替え可能）
- 🤖 **Gemini AI OCR**: Google Gemini APIによる高精度な日本語OCR
- 🎯 **自動入力機能**: 読み取り結果をフォームに自動入力
- 📝 **入力フォーム**: 各質問項目に対応した入力フィールド
- 📊 **結果管理**: 入力結果の一覧表示・削除
- 📥 **CSVエクスポート**: 結果をCSVファイルでダウンロード

## 🆕 v2.0.0 新機能

- **Gemini AI OCR**: Google Gemini APIによる高精度OCR
- **自動入力モード**: 読み取り結果を直接フォームに反映
- **手書き文字認識**: 手書きの日本語も高精度で認識
- **構造化データ抽出**: アンケートの項目を自動的に分類

## 🚀 セットアップ

### 必要要件

- Node.js 18以上
- npm または yarn
- **Google AI Studio APIキー**

### APIキーの取得

1. [Google AI Studio](https://aistudio.google.com/) にアクセス
2. Googleアカウントでログイン
3. 「Get API key」→「Create API key」
4. 作成されたAPIキーをコピー

### インストール

```bash
# リポジトリをクローン
git clone https://github.com/hashimoto-hiroyuki/touka-assist.git
cd touka-assist

# 依存関係をインストール
npm install

# 開発サーバーを起動
npm run dev
```

### ビルド

```bash
npm run build
```

## 📁 プロジェクト構成

```
touka-assist/
├── public/
├── src/
│   ├── components/
│   │   ├── ApiKeySettings.jsx  # API設定モーダル
│   │   ├── ImagePreview.jsx    # 画像/PDFプレビュー
│   │   ├── QuestionForm.jsx    # 質問フォーム
│   │   └── ResultDisplay.jsx   # 結果表示
│   ├── utils/
│   │   ├── geminiOCR.js        # Gemini API処理
│   │   └── pdfUtils.js         # PDF処理
│   ├── App.jsx
│   ├── App.css
│   ├── index.css
│   └── main.jsx
├── index.html
├── package.json
├── vite.config.js
└── README.md
```

## 🌐 デプロイ (Vercel)

1. GitHubにリポジトリをプッシュ
2. [Vercel](https://vercel.com) にログイン
3. 「New Project」→ GitHubリポジトリを選択
4. デフォルト設定で「Deploy」

## 📋 質問項目

- 患者ID
- 名前（カタカナ）
- 生年月日
- 性別
- 血液型
- 身長・体重
- 糖尿病・脂質異常症の有無
- 家族の糖尿病歴
- 運動習慣
- 食習慣（お菓子・飲み物）
- 飲酒習慣
- 歯の抜去位置
- その他コメント

## 🛠️ 技術スタック

- **フロントエンド**: React 18 + Vite
- **OCR**: Google Gemini API
- **PDF処理**: PDF.js
- **スタイリング**: CSS
- **デプロイ**: Vercel

## 🔐 セキュリティ

- APIキーはブラウザのローカルストレージに保存
- APIキーは外部に送信されません（Google APIへの直接通信のみ）

## 📄 ライセンス

MIT License

## 👨‍💻 作成者

hashimoto-hiroyuki
