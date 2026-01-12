/**
 * Gemini API を使用したOCR処理
 */

const GEMINI_API_URL = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent'

/**
 * 画像をBase64に変換
 */
export async function imageToBase64(imageSource) {
  // すでにDataURLの場合
  if (typeof imageSource === 'string' && imageSource.startsWith('data:')) {
    return imageSource.split(',')[1]
  }
  
  // Fileオブジェクトの場合
  if (imageSource instanceof File) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onloadend = () => {
        const base64 = reader.result.split(',')[1]
        resolve(base64)
      }
      reader.onerror = reject
      reader.readAsDataURL(imageSource)
    })
  }
  
  throw new Error('Unsupported image source')
}

/**
 * Gemini APIでOCR実行（テキスト抽出のみ）
 */
export async function runGeminiOCR(apiKey, imageSource) {
  const base64Image = await imageToBase64(imageSource)
  
  const prompt = `この画像に写っているアンケート用紙の内容を読み取ってください。
手書きの文字も含めて、できるだけ正確に読み取ってください。
読み取った内容をそのまま日本語テキストで出力してください。`

  const response = await fetch(`${GEMINI_API_URL}?key=${apiKey}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      contents: [{
        parts: [
          { text: prompt },
          { 
            inline_data: { 
              mime_type: 'image/png', 
              data: base64Image 
            } 
          }
        ]
      }],
      generationConfig: {
        temperature: 0.1,
        maxOutputTokens: 4096,
      }
    })
  })

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.error?.message || 'Gemini API error')
  }

  const data = await response.json()
  return data.candidates[0].content.parts[0].text
}

/**
 * Gemini APIでOCR実行（構造化データ抽出）
 */
export async function runGeminiOCRStructured(apiKey, imageSource) {
  const base64Image = await imageToBase64(imageSource)
  
  const prompt = `この画像は糖化アンケートです。内容を読み取り、以下のJSON形式で出力してください。
手書きの文字も正確に読み取ってください。チェックされている項目を判別してください。

{
  "patient_id": "患者ID",
  "name_sei": "氏（カタカナ）",
  "name_mei": "名（カタカナ）",
  "birthday": "生年月日（例: 昭和35年12月18日）",
  "gender": "性別（男/女/回答しない）",
  "blood_type": "血液型（A型/B型/O型/AB型/わからない）",
  "height": "身長（数値のみ）",
  "weight": "体重（数値のみ）",
  "diabetes": "糖尿病（なし/5年未満/5〜10年前/10年以上前/わからない）",
  "dyslipidemia": "脂質異常症（なし/5年未満/5〜10年前/10年以上前/わからない）",
  "sibling_diabetes": "兄弟に糖尿病歴（はい/いいえ/わからない）",
  "parent_diabetes": "両親に糖尿病歴（はい/いいえ/わからない）",
  "no_exercise": "ほとんど運動しない（はい/いいえ）",
  "sweets_frequency": "お菓子・スイーツ頻度（ほぼ毎日/週2-3回/週1回以下または食べない）",
  "drink_type": "よく飲む飲み物（有糖飲料/無糖飲料）",
  "alcohol": "飲酒習慣（飲む/ほとんど飲まない）",
  "alcohol_detail": "飲酒詳細",
  "tooth_extraction": "歯の抜去位置",
  "comment": "その他コメント"
}

読み取れない項目は空文字""にしてください。
JSONのみを出力し、他の説明は不要です。`

  const response = await fetch(`${GEMINI_API_URL}?key=${apiKey}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      contents: [{
        parts: [
          { text: prompt },
          { 
            inline_data: { 
              mime_type: 'image/png', 
              data: base64Image 
            } 
          }
        ]
      }],
      generationConfig: {
        temperature: 0.1,
        maxOutputTokens: 4096,
      }
    })
  })

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.error?.message || 'Gemini API error')
  }

  const data = await response.json()
  const text = data.candidates[0].content.parts[0].text
  
  // JSONを抽出
  const jsonMatch = text.match(/\{[\s\S]*\}/)
  if (jsonMatch) {
    try {
      return JSON.parse(jsonMatch[0])
    } catch (e) {
      console.error('JSON parse error:', e)
      return null
    }
  }
  
  return null
}
