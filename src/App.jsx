import { useState, useEffect } from 'react'
import ImagePreview from './components/ImagePreview'
import QuestionForm from './components/QuestionForm'
import ResultDisplay from './components/ResultDisplay'
import ApiKeySettings from './components/ApiKeySettings'
import { runGeminiOCR, runGeminiOCRStructured } from './utils/geminiOCR'
import './App.css'

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
  const [isProcessing, setIsProcessing] = useState(false)
  const [formData, setFormData] = useState({})
  const [results, setResults] = useState([])
  const [activeTab, setActiveTab] = useState('input')
  const [fileType, setFileType] = useState('image')
  const [apiKey, setApiKey] = useState('')
  const [showSettings, setShowSettings] = useState(false)
  const [ocrMode, setOcrMode] = useState('structured') // 'text' or 'structured'

  // APIキーをローカルストレージから読み込み
  useEffect(() => {
    const savedKey = localStorage.getItem('gemini_api_key')
    if (savedKey) {
      setApiKey(savedKey)
    }
  }, [])

  // APIキーを保存
  const saveApiKey = (key) => {
    setApiKey(key)
    localStorage.setItem('gemini_api_key', key)
    setShowSettings(false)
  }

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

  const handlePdfLoad = (imageDataUrl, pdfFile) => {
    setImagePreview(imageDataUrl)
    setImage(imageDataUrl)
    setFileType('pdf')
  }

  const runOCR = async () => {
    if (!imagePreview) {
      alert('先にファイルを選択してください。')
      return
    }

    if (!apiKey) {
      alert('APIキーを設定してください。右上の⚙️ボタンから設定できます。')
      setShowSettings(true)
      return
    }

    setIsProcessing(true)
    setOcrText('🔄 Gemini APIで読み取り中...')

    try {
      const imageSource = fileType === 'pdf' ? imagePreview : image

      if (ocrMode === 'structured') {
        // 構造化データとして読み取り → フォームに自動入力
        const structuredData = await runGeminiOCRStructured(apiKey, imageSource)
        
        if (structuredData) {
          setFormData(structuredData)
          setOcrText('✅ 読み取り完了！フォームに自動入力しました。\n\n【読み取り結果】\n' + 
            JSON.stringify(structuredData, null, 2))
        } else {
          setOcrText('⚠️ 構造化データの抽出に失敗しました。テキストモードで再試行してください。')
        }
      } else {
        // テキストとして読み取り
        const text = await runGeminiOCR(apiKey, imageSource)
        setOcrText(text)
      }
    } catch (error) {
      console.error('OCR Error:', error)
      setOcrText(`❌ エラー: ${error.message}`)
      
      if (error.message.includes('API key')) {
        alert('APIキーが無効です。正しいAPIキーを設定してください。')
        setShowSettings(true)
      }
    } finally {
      setIsProcessing(false)
    }
  }

  const handleInputChange = (id, value) => {
    setFormData(prev => ({ ...prev, [id]: value }))
  }

  const clearForm = () => {
    if (window.confirm('入力内容をクリアしますか？')) {
      setFormData({})
      setOcrText('')
      setImage(null)
      setImagePreview(null)
      setFileType('image')
    }
  }

  const addResult = () => {
    const newResult = {
      id: Date.now(),
      timestamp: new Date().toLocaleString('ja-JP'),
      data: { ...formData }
    }
    setResults(prev => [...prev, newResult])
    alert('結果を追加しました。')
  }

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
        <p>Touka Assist - Gemini AI OCR対応版</p>
        <button 
          className="settings-btn"
          onClick={() => setShowSettings(true)}
          title="API設定"
        >
          ⚙️
        </button>
      </header>

      {showSettings && (
        <ApiKeySettings
          apiKey={apiKey}
          onSave={saveApiKey}
          onClose={() => setShowSettings(false)}
        />
      )}

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
            <section className="left-panel">
              <ImagePreview
                imagePreview={imagePreview}
                onImageSelect={handleImageSelect}
                onPdfLoad={handlePdfLoad}
                onRunOCR={runOCR}
                isProcessing={isProcessing}
                ocrProgress={0}
              />

              {/* OCRモード切替 */}
              <div className="ocr-mode-selector">
                <label>
                  <input
                    type="radio"
                    value="structured"
                    checked={ocrMode === 'structured'}
                    onChange={(e) => setOcrMode(e.target.value)}
                  />
                  🎯 自動入力モード（推奨）
                </label>
                <label>
                  <input
                    type="radio"
                    value="text"
                    checked={ocrMode === 'text'}
                    onChange={(e) => setOcrMode(e.target.value)}
                  />
                  📄 テキスト抽出モード
                </label>
              </div>
              
              <div className="ocr-result">
                <h3>📄 OCR読み取り結果</h3>
                <textarea
                  value={ocrText}
                  onChange={(e) => setOcrText(e.target.value)}
                  placeholder="Gemini AIでOCRを実行すると、ここに結果が表示されます..."
                  rows={10}
                />
              </div>

              {!apiKey && (
                <div className="api-key-warning">
                  ⚠️ APIキーが設定されていません。
                  <button onClick={() => setShowSettings(true)}>設定する</button>
                </div>
              )}
            </section>

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
        <p>© 2026 Touka Assist | ホワイト歯科医院 | Gemini AI OCR版</p>
      </footer>
    </div>
  )
}

export default App
