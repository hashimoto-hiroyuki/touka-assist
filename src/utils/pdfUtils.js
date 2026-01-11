import * as pdfjsLib from 'pdfjs-dist'

// PDF.js ワーカーの設定
pdfjsLib.GlobalWorkerOptions.workerSrc = `//cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjsLib.version}/pdf.worker.min.js`

/**
 * PDFファイルを画像（DataURL）に変換する
 * @param {File} file - PDFファイル
 * @param {number} pageNumber - ページ番号（1から開始）
 * @param {number} scale - 解像度スケール（大きいほど高解像度）
 * @returns {Promise<string>} - 画像のDataURL
 */
export async function pdfToImage(file, pageNumber = 1, scale = 2.0) {
  const arrayBuffer = await file.arrayBuffer()
  const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise
  const page = await pdf.getPage(pageNumber)
  
  const viewport = page.getViewport({ scale })
  
  // Canvasを作成
  const canvas = document.createElement('canvas')
  const context = canvas.getContext('2d')
  canvas.width = viewport.width
  canvas.height = viewport.height
  
  // PDFをCanvasに描画
  await page.render({
    canvasContext: context,
    viewport: viewport
  }).promise
  
  // DataURLとして返す
  return canvas.toDataURL('image/png')
}

/**
 * PDFの総ページ数を取得
 * @param {File} file - PDFファイル
 * @returns {Promise<number>} - 総ページ数
 */
export async function getPdfPageCount(file) {
  const arrayBuffer = await file.arrayBuffer()
  const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise
  return pdf.numPages
}

/**
 * PDFの全ページを画像に変換
 * @param {File} file - PDFファイル
 * @param {number} scale - 解像度スケール
 * @param {function} onProgress - 進捗コールバック
 * @returns {Promise<string[]>} - 各ページの画像DataURL配列
 */
export async function pdfToImages(file, scale = 2.0, onProgress = null) {
  const arrayBuffer = await file.arrayBuffer()
  const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise
  const numPages = pdf.numPages
  const images = []
  
  for (let i = 1; i <= numPages; i++) {
    const page = await pdf.getPage(i)
    const viewport = page.getViewport({ scale })
    
    const canvas = document.createElement('canvas')
    const context = canvas.getContext('2d')
    canvas.width = viewport.width
    canvas.height = viewport.height
    
    await page.render({
      canvasContext: context,
      viewport: viewport
    }).promise
    
    images.push(canvas.toDataURL('image/png'))
    
    if (onProgress) {
      onProgress(i, numPages)
    }
  }
  
  return images
}

/**
 * ファイルがPDFかどうか判定
 * @param {File} file - ファイル
 * @returns {boolean}
 */
export function isPdf(file) {
  return file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
}
