import React from 'react'

function QuestionForm({ questions, formData, onInputChange }) {
  const renderInput = (question) => {
    const value = formData[question.id] || ''

    switch (question.type) {
      case 'select':
        return (
          <select
            value={value}
            onChange={(e) => onInputChange(question.id, e.target.value)}
          >
            {question.options.map((option, index) => (
              <option key={index} value={option}>
                {option || '-- 選択してください --'}
              </option>
            ))}
          </select>
        )

      case 'textarea':
        return (
          <textarea
            value={value}
            onChange={(e) => onInputChange(question.id, e.target.value)}
            placeholder={question.placeholder || ''}
            rows={3}
          />
        )

      case 'number':
        return (
          <input
            type="number"
            value={value}
            onChange={(e) => onInputChange(question.id, e.target.value)}
            placeholder={question.placeholder || ''}
            step="0.1"
          />
        )

      default:
        return (
          <input
            type="text"
            value={value}
            onChange={(e) => onInputChange(question.id, e.target.value)}
            placeholder={question.placeholder || ''}
          />
        )
    }
  }

  return (
    <div className="question-form">
      <h3>📝 アンケート入力</h3>
      
      {questions.map((question) => (
        <div key={question.id} className="form-group">
          <label htmlFor={question.id}>
            {question.label}
          </label>
          {renderInput(question)}
        </div>
      ))}
    </div>
  )
}

export default QuestionForm
