/**
 * OCR精度向上のための画像前処理ユーティリティ
 */

/**
 * 画像を前処理してOCR精度を向上させる
 * @param {string} imageDataUrl - 画像のDataURL
 * @returns {Promise<string>} - 処理済み画像のDataURL
 */
export async function preprocessImage(imageDataUrl) {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => {
      try {
        const canvas = document.createElement('canvas')
        const ctx = canvas.getContext('2d')
        
        // 解像度を上げる（2倍）
        const scale = 2
        canvas.width = img.width * scale
        canvas.height = img.height * scale
        
        // 画像を描画
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
        
        // 画像データを取得
        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height)
        const data = imageData.data
        
        // グレースケール変換 + コントラスト強調 + 二値化
        for (let i = 0; i < data.length; i += 4) {
          // グレースケール化
          const gray = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2]
          
          // コントラスト強調
          const contrast = 1.5 // コントラスト係数
          const factor = (259 * (contrast * 100 + 255)) / (255 * (259 - contrast * 100))
          let enhanced = factor * (gray - 128) + 128
          
          // 二値化（閾値: 180）
          const threshold = 180
          const binary = enhanced > threshold ? 255 : 0
          
          data[i] = binary     // R
          data[i + 1] = binary // G
          data[i + 2] = binary // B
          // Alpha はそのまま
        }
        
        ctx.putImageData(imageData, 0, 0)
        
        resolve(canvas.toDataURL('image/png'))
      } catch (error) {
        reject(error)
      }
    }
    img.onerror = reject
    img.src = imageDataUrl
  })
}

/**
 * 画像をシャープ化
 * @param {string} imageDataUrl - 画像のDataURL
 * @returns {Promise<string>} - 処理済み画像のDataURL
 */
export async function sharpenImage(imageDataUrl) {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => {
      try {
        const canvas = document.createElement('canvas')
        const ctx = canvas.getContext('2d')
        
        canvas.width = img.width
        canvas.height = img.height
        ctx.drawImage(img, 0, 0)
        
        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height)
        const data = imageData.data
        const width = canvas.width
        const height = canvas.height
        
        // シャープ化カーネル
        const kernel = [
          0, -1, 0,
          -1, 5, -1,
          0, -1, 0
        ]
        
        const output = new Uint8ClampedArray(data.length)
        
        for (let y = 1; y < height - 1; y++) {
          for (let x = 1; x < width - 1; x++) {
            for (let c = 0; c < 3; c++) {
              let sum = 0
              for (let ky = -1; ky <= 1; ky++) {
                for (let kx = -1; kx <= 1; kx++) {
                  const idx = ((y + ky) * width + (x + kx)) * 4 + c
                  sum += data[idx] * kernel[(ky + 1) * 3 + (kx + 1)]
                }
              }
              output[(y * width + x) * 4 + c] = Math.min(255, Math.max(0, sum))
            }
            output[(y * width + x) * 4 + 3] = 255
          }
        }
        
        const outputImageData = new ImageData(output, width, height)
        ctx.putImageData(outputImageData, 0, 0)
        
        resolve(canvas.toDataURL('image/png'))
      } catch (error) {
        reject(error)
      }
    }
    img.onerror = reject
    img.src = imageDataUrl
  })
}

/**
 * 画像を高解像度化
 * @param {string} imageDataUrl - 画像のDataURL
 * @param {number} scale - 拡大倍率
 * @returns {Promise<string>} - 処理済み画像のDataURL
 */
export async function upscaleImage(imageDataUrl, scale = 2) {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => {
      try {
        const canvas = document.createElement('canvas')
        const ctx = canvas.getContext('2d')
        
        canvas.width = img.width * scale
        canvas.height = img.height * scale
        
        // 高品質な拡大
        ctx.imageSmoothingEnabled = true
        ctx.imageSmoothingQuality = 'high'
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
        
        resolve(canvas.toDataURL('image/png'))
      } catch (error) {
        reject(error)
      }
    }
    img.onerror = reject
    img.src = imageDataUrl
  })
}
