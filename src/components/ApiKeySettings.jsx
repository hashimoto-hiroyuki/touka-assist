import React, { useState } from 'react'

function ApiKeySettings({ apiKey, onSave, onClose }) {
  const [inputKey, setInputKey] = useState(apiKey || '')
  const [showKey, setShowKey] = useState(false)

  const handleSave = () => {
    if (!inputKey.trim()) {
      alert('APIキーを入力してください。')
      return
    }
    onSave(inputKey.trim())
  }

  const handleClear = () => {
    if (window.confirm('APIキーを削除しますか？')) {
      setInputKey('')
      localStorage.removeItem('gemini_api_key')
      onSave('')
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <h2>⚙️ API設定</h2>
        
        <div className="form-group">
          <label>Gemini APIキー</label>
          <div className="api-key-input">
            <input
              type={showKey ? 'text' : 'password'}
              value={inputKey}
              onChange={(e) => setInputKey(e.target.value)}
              placeholder="AIza..."
            />
            <button 
              type="button" 
              className="toggle-visibility"
              onClick={() => setShowKey(!showKey)}
            >
              {showKey ? '🙈' : '👁️'}
            </button>
          </div>
        </div>

        <div className="api-key-help">
          <p>📌 APIキーの取得方法:</p>
          <ol>
            <li><a href="https://aistudio.google.com/" target="_blank" rel="noopener noreferrer">Google AI Studio</a> にアクセス</li>
            <li>「Get API key」をクリック</li>
            <li>「Create API key」でキーを作成</li>
            <li>作成されたキーをコピーして貼り付け</li>
          </ol>
        </div>

        <div className="modal-actions">
          <button className="btn btn-secondary" onClick={onClose}>
            キャンセル
          </button>
          {apiKey && (
            <button className="btn btn-danger" onClick={handleClear}>
              削除
            </button>
          )}
          <button className="btn btn-primary" onClick={handleSave}>
            保存
          </button>
        </div>
      </div>
    </div>
  )
}

export default ApiKeySettings
