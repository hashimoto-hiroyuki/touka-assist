import React from 'react'

function ResultDisplay({ results, questions, onDownloadCSV, onDeleteResult }) {
  if (results.length === 0) {
    return (
      <div className="results-container">
        <div className="no-results">
          <h2>📊 結果一覧</h2>
          <p style={{ marginTop: '20px' }}>まだ結果がありません。</p>
          <p>「入力」タブからアンケートを入力して「結果を追加」してください。</p>
        </div>
      </div>
    )
  }

  // 表示する主要な項目
  const displayFields = [
    'patient_id',
    'name_sei',
    'name_mei',
    'birthday',
    'gender',
    'blood_type',
  ]

  const getFieldLabel = (id) => {
    const question = questions.find(q => q.id === id)
    return question ? question.label : id
  }

  return (
    <div className="results-container">
      <div className="results-header">
        <h2>📊 結果一覧 ({results.length}件)</h2>
        <button className="btn btn-success" onClick={onDownloadCSV}>
          📥 CSVダウンロード
        </button>
      </div>

      <div className="results-table">
        <table>
          <thead>
            <tr>
              <th>No.</th>
              <th>登録日時</th>
              {displayFields.map(field => (
                <th key={field}>{getFieldLabel(field)}</th>
              ))}
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {results.map((result, index) => (
              <tr key={result.id}>
                <td>{index + 1}</td>
                <td>{result.timestamp}</td>
                {displayFields.map(field => (
                  <td key={field}>{result.data[field] || '-'}</td>
                ))}
                <td>
                  <button
                    className="btn btn-danger"
                    style={{ padding: '5px 10px', fontSize: '0.8rem' }}
                    onClick={() => {
                      if (window.confirm('この結果を削除しますか？')) {
                        onDeleteResult(result.id)
                      }
                    }}
                  >
                    🗑️
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={{ marginTop: '20px', padding: '15px', background: '#f5f7fa', borderRadius: '5px' }}>
        <p style={{ fontSize: '0.9rem', color: '#666' }}>
          💡 ヒント: CSVダウンロードで全ての項目を含むファイルを取得できます。
        </p>
      </div>
    </div>
  )
}

export default ResultDisplay
