# 🦷 Touka Assist - 糖化アンケート入力システム

歯科医院向けの糖化アンケートOCR入力支援Webアプリケーションです。

## ✨ 機能

- 📷 **画像アップロード**: PNG, JPG, JPEG, BMP, TIFF対応
- 📄 **PDFアップロード**: 複数ページPDFに対応（ページ切り替え可能）
- 🔍 **OCR読み取り**: Tesseract.jsによる日本語文字認識
- 📝 **入力フォーム**: 各質問項目に対応した入力フィールド
- 📊 **結果管理**: 入力結果の一覧表示・削除
- 📥 **CSVエクスポート**: 結果をCSVファイルでダウンロード

## 🆕 v1.1.0 新機能

- **PDF対応**: PDFファイルを直接読み込み可能
- **複数ページ対応**: PDFの各ページを切り替えてOCR実行
- **高解像度変換**: PDFを高品質な画像に変換してOCR精度向上

## 🚀 セットアップ

### 必要要件

- Node.js 18以上
- npm または yarn

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
│   │   ├── ImagePreview.jsx    # 画像/PDFプレビュー
│   │   ├── QuestionForm.jsx    # 質問フォーム
│   │   └── ResultDisplay.jsx   # 結果表示
│   ├── utils/
│   │   └── pdfUtils.js         # PDF処理ユーティリティ
│   ├── App.jsx                 # メインコンポーネント
│   ├── App.css                 # スタイル
│   ├── index.css               # グローバルスタイル
│   └── main.jsx                # エントリーポイント
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
- **OCR**: Tesseract.js
- **PDF処理**: PDF.js
- **スタイリング**: CSS
- **デプロイ**: Vercel

## 📄 ライセンス

MIT License

## 👨‍💻 作成者

hashimoto-hiroyuki
