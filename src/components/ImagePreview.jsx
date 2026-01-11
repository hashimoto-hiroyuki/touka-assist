import React, { useState } from 'react'
import { isPdf, pdfToImage, getPdfPageCount } from '../utils/pdfUtils'

function ImagePreview({ 
  imagePreview, 
  onImageSelect, 
  onRunOCR, 
  isProcessing, 
  ocrProgress,
  onPdfLoad 
}) {
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [isPdfFile, setIsPdfFile] = useState(false)
  const [pdfFile, setPdfFile] = useState(null)
  const [isLoadingPage, setIsLoadingPage] = useState(false)

  const handleFileSelect = async (e) => {
    const file = e.target.files[0]
    if (!file) return

    if (isPdf(file)) {
      // PDFファイルの処理
      setIsPdfFile(true)
      setPdfFile(file)
      setIsLoadingPage(true)
      
      try {
        const pageCount = await getPdfPageCount(file)
        setTotalPages(pageCount)
        setCurrentPage(1)
        
        // 最初のページを画像に変換
        const imageDataUrl = await pdfToImage(file, 1, 2.0)
        onPdfLoad(imageDataUrl, file)
      } catch (error) {
        console.error('PDF読み込みエラー:', error)
        alert('PDFの読み込みに失敗しました。')
      } finally {
        setIsLoadingPage(false)
      }
    } else {
      // 画像ファイルの処理
      setIsPdfFile(false)
      setPdfFile(null)
      setTotalPages(1)
      setCurrentPage(1)
      onImageSelect(e)
    }
  }

  const changePage = async (newPage) => {
    if (newPage < 1 || newPage > totalPages || !pdfFile) return
    
    setIsLoadingPage(true)
    try {
      const imageDataUrl = await pdfToImage(pdfFile, newPage, 2.0)
      setCurrentPage(newPage)
      onPdfLoad(imageDataUrl, pdfFile)
    } catch (error) {
      console.error('ページ変更エラー:', error)
    } finally {
      setIsLoadingPage(false)
    }
  }

  return (
    <div className="image-preview">
      <h3>🖼️ 画像 / PDF プレビュー</h3>
      
      <div className="preview-area">
        {isLoadingPage ? (
          <div className="preview-placeholder">
            <p>📄 ページを読み込み中...</p>
          </div>
        ) : imagePreview ? (
          <img src={imagePreview} alt="アンケート" />
        ) : (
          <div className="preview-placeholder">
            <p>📷 画像またはPDFを選択してください</p>
            <p style={{ fontSize: '0.8rem', marginTop: '10px' }}>
              対応形式: PNG, JPG, JPEG, BMP, TIFF, <strong>PDF</strong>
            </p>
          </div>
        )}
      </div>

      {/* PDFページナビゲーション */}
      {isPdfFile && totalPages > 1 && (
        <div className="pdf-navigation">
          <button 
            className="btn btn-secondary"
            onClick={() => changePage(currentPage - 1)}
            disabled={currentPage <= 1 || isLoadingPage}
          >
            ◀ 前
          </button>
          <span className="page-info">
            {currentPage} / {totalPages} ページ
          </span>
          <button 
            className="btn btn-secondary"
            onClick={() => changePage(currentPage + 1)}
            disabled={currentPage >= totalPages || isLoadingPage}
          >
            次 ▶
          </button>
        </div>
      )}

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
            📁 ファイルを選択
          </button>
          <input
            type="file"
            accept="image/*,.pdf"
            onChange={handleFileSelect}
          />
        </div>
        
        <button
          className="btn btn-success"
          onClick={onRunOCR}
          disabled={!imagePreview || isProcessing || isLoadingPage}
        >
          {isProcessing ? '🔄 処理中...' : '🔍 OCR実行'}
        </button>
      </div>

      {isPdfFile && (
        <div className="pdf-info">
          <p>📄 PDFファイル ({totalPages}ページ)</p>
        </div>
      )}
    </div>
  )
}

export default ImagePreview
