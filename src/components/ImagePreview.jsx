import React from 'react'

function ImagePreview({ imagePreview, onImageSelect, onRunOCR, isProcessing, ocrProgress }) {
  return (
    <div className="image-preview">
      <h3>🖼️ 画像プレビュー</h3>
      
      <div className="preview-area">
        {imagePreview ? (
          <img src={imagePreview} alt="アンケート画像" />
        ) : (
          <div className="preview-placeholder">
            <p>📷 画像を選択してください</p>
            <p style={{ fontSize: '0.8rem', marginTop: '10px' }}>
              対応形式: PNG, JPG, JPEG, BMP, TIFF
            </p>
          </div>
        )}
      </div>

      {isProcessing && (
        <div className="progress-bar">
          <div 
            className="progress-fill" 
            style={{ width: `${ocrProgress}%` }}
          >
            {ocrProgress}%
          </div>
        </div>
      )}

      <div className="image-actions">
        <div className="file-input-wrapper">
          <button className="btn btn-primary">
            📁 画像を選択
          </button>
          <input
            type="file"
            accept="image/*"
            onChange={onImageSelect}
          />
        </div>
        
        <button
          className="btn btn-success"
          onClick={onRunOCR}
          disabled={!imagePreview || isProcessing}
        >
          {isProcessing ? '🔄 処理中...' : '🔍 OCR実行'}
        </button>
      </div>
    </div>
  )
}

export default ImagePreview
