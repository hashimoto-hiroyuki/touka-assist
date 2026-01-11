import { useState } from 'react'
import Tesseract from 'tesseract.js'
import ImagePreview from './components/ImagePreview'
import QuestionForm from './components/QuestionForm'
import ResultDisplay from './components/ResultDisplay'
import './App.css'

// 質問項目の定義
const QUESTIONS = [
  { id: "patient_id", label: "患者さんID", type: "text" },
  { id: "name_sei", label: "名前（カタカナ）氏", type: "text" },
  { id: "name_mei", label: "名前（カタカナ）名", type: "text" },
  { id: "birthday", label: "生年月日", type: "text", placeholder: "例: 昭和35年12月18日" },
  { id: "gender", label: "性別", type: "select", options: ["", "男", "女", "回答しない"] },
  { id: "blood_type", label: "血液型", type: "select", options: ["", "A型", "B型", "O型", "AB型", "わからない"] },
  { id: "height", label: "身長（cm）", type: "number" },
  { id: "weight", label: "体重（kg）", type: "number" },
  { id: "diabetes", label: "糖尿病", type: "select", options: ["", "なし", "5年未満", "5〜10年前", "10年以上前", "わからない"] },
  { id: "dyslipidemia", label: "脂質異常症", type: "select", options: ["", "なし", "5年未満", "5〜10年前", "10年以上前", "わからない"] },
  { id: "sibling_diabetes", label: "兄弟に糖尿病歴", type: "select", options: ["", "はい", "いいえ", "わからない"] },
  { id: "parent_diabetes", label: "両親に糖尿病歴", type: "select", options: ["", "はい", "いいえ", "わからない"] },
  { id: "no_exercise", label: "ほとんど運動しない", type: "select", options: ["", "はい", "いいえ"] },
  { id: "sweets_frequency", label: "お菓子・スイーツ頻度", type: "select", options: ["", "ほぼ毎日", "週2-3回", "週1回以下または食べない"] },
  { id: "drink_type", label: "よく飲む飲み物", type: "select", options: ["", "有糖飲料", "無糖飲料"] },
  { id: "alcohol", label: "飲酒習慣", type: "select", options: ["", "飲む", "ほとんど飲まない"] },
  { id: "alcohol_detail", label: "飲酒詳細", type: "text", placeholder: "例: ビールを週5回、350ml缶を3本" },
  { id: "tooth_extraction", label: "歯の抜去位置", type: "text" },
  { id: "comment", label: "その他コメント", type: "textarea" },
]

function App() {
  const [image, setImage] = useState(null)
  const [imagePreview, setImagePreview] = useState(null)
  const [ocrText, setOcrText] = useState('')
  const [ocrProgress, setOcrProgress] = useState(0)
  const [isProcessing, setIsProcessing] = useState(false)
  const [formData, setFormData] = useState({})
  const [results, setResults] = useState([])
  const [activeTab, setActiveTab] = useState('input')
  const [fileType, setFileType] = useState('image') // 'image' or 'pdf'

  // 画像選択ハンドラ
  const handleImageSelect = (e) => {
    const file = e.target.files[0]
    if (file) {
      setImage(file)
      setFileType('image')
      const reader = new FileReader()
      reader.onloadend = () => {
        setImagePreview(reader.result)
      }
      reader.readAsDataURL(file)
    }
  }

  // PDF読み込みハンドラ
  const handlePdfLoad = (imageDataUrl, pdfFile) => {
    setImagePreview(imageDataUrl)
    setImage(imageDataUrl) // DataURLをそのまま使用
    setFileType('pdf')
  }

  // OCR実行
  const runOCR = async () => {
    if (!imagePreview) {
      alert('先にファイルを選択してください。')
      return
    }

    setIsProcessing(true)
    setOcrProgress(0)

    try {
      // 画像またはPDFから変換された画像に対してOCR実行
      const imageSource = fileType === 'pdf' ? imagePreview : image
      
      const result = await Tesseract.recognize(
        imageSource,
        'jpn',
        {
          logger: (m) => {
            if (m.status === 'recognizing text') {
              setOcrProgress(Math.round(m.progress * 100))
            }
          }
        }
      )
      setOcrText(result.data.text)
    } catch (error) {
      console.error('OCR Error:', error)
      alert('OCR処理中にエラーが発生しました。')
    } finally {
      setIsProcessing(false)
      setOcrProgress(0)
    }
  }

  // フォーム入力ハンドラ
  const handleInputChange = (id, value) => {
    setFormData(prev => ({ ...prev, [id]: value }))
  }

  // フォームクリア
  const clearForm = () => {
    if (window.confirm('入力内容をクリアしますか？')) {
      setFormData({})
      setOcrText('')
      setImage(null)
      setImagePreview(null)
      setFileType('image')
    }
  }

  // 結果を追加
  const addResult = () => {
    const newResult = {
      id: Date.now(),
      timestamp: new Date().toLocaleString('ja-JP'),
      data: { ...formData }
    }
    setResults(prev => [...prev, newResult])
    alert('結果を追加しました。')
  }

  // CSVダウンロード
  const downloadCSV = () => {
    if (results.length === 0) {
      alert('保存する結果がありません。')
      return
    }

    const headers = QUESTIONS.map(q => q.label)
    const csvContent = [
      headers.join(','),
      ...results.map(r => 
        QUESTIONS.map(q => {
          const value = r.data[q.id] || ''
          return value.includes(',') || value.includes('\n') 
            ? `"${value.replace(/"/g, '""')}"` 
            : value
        }).join(',')
      )
    ].join('\n')

    const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `touka_results_${new Date().toISOString().slice(0, 10)}.csv`
    link.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="app">
      <header className="header">
        <h1>🦷 糖化アンケート入力システム</h1>
        <p>Touka Assist - 画像・PDF対応 OCR入力支援</p>
      </header>

      <nav className="tabs">
        <button 
          className={`tab ${activeTab === 'input' ? 'active' : ''}`}
          onClick={() => setActiveTab('input')}
        >
          📝 入力
        </button>
        <button 
          className={`tab ${activeTab === 'results' ? 'active' : ''}`}
          onClick={() => setActiveTab('results')}
        >
          📊 結果一覧 ({results.length})
        </button>
      </nav>

      <main className="main">
        {activeTab === 'input' ? (
          <div className="input-container">
            {/* 左側: 画像・OCR */}
            <section className="left-panel">
              <ImagePreview
                imagePreview={imagePreview}
                onImageSelect={handleImageSelect}
                onPdfLoad={handlePdfLoad}
                onRunOCR={runOCR}
                isProcessing={isProcessing}
                ocrProgress={ocrProgress}
              />
              
              <div className="ocr-result">
                <h3>📄 OCR読み取り結果（参考）</h3>
                <textarea
                  value={ocrText}
                  onChange={(e) => setOcrText(e.target.value)}
                  placeholder="OCRを実行すると、ここに結果が表示されます..."
                  rows={10}
                />
              </div>
            </section>

            {/* 右側: 入力フォーム */}
            <section className="right-panel">
              <QuestionForm
                questions={QUESTIONS}
                formData={formData}
                onInputChange={handleInputChange}
              />
              
              <div className="form-actions">
                <button className="btn btn-secondary" onClick={clearForm}>
                  🗑️ クリア
                </button>
                <button className="btn btn-primary" onClick={addResult}>
                  ✅ 結果を追加
                </button>
              </div>
            </section>
          </div>
        ) : (
          <ResultDisplay
            results={results}
            questions={QUESTIONS}
            onDownloadCSV={downloadCSV}
            onDeleteResult={(id) => setResults(prev => prev.filter(r => r.id !== id))}
          />
        )}
      </main>

      <footer className="footer">
        <p>© 2026 Touka Assist | ホワイト歯科医院 | PDF対応版</p>
      </footer>
    </div>
  )
}

export default App
