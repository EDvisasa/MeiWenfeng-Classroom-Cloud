import React, { useState } from 'react';
import { Check, X, Send } from 'lucide-react';

export default function QuizBlock({ data, onQuizSubmit }) {
  const { question, options, correct_index, explanation } = data;
  const [selectedIndex, setSelectedIndex] = useState(null);
  const [hasSubmitted, setHasSubmitted] = useState(false);

  const handleSubmit = () => {
    if (selectedIndex === null) return;
    setHasSubmitted(true);
    
    // Call the parent handler to inform backend silently
    const isCorrect = selectedIndex === correct_index;
    if (onQuizSubmit) {
      onQuizSubmit({
        question,
        selectedOption: options[selectedIndex],
        isCorrect
      });
    }
  };

  return (
    <div style={{
      margin: '16px 0',
      padding: '16px',
      borderRadius: '12px',
      border: '1px solid var(--border-color, #e2e8f0)',
      background: 'var(--bg-secondary, #f8fafc)',
      boxShadow: 'var(--shadow-sm, 0 1px 2px 0 rgba(0, 0, 0, 0.05))',
      color: 'var(--text-primary, #1e293b)'
    }}>
      <h3 style={{ fontSize: '15px', fontWeight: '600', marginBottom: '16px', marginTop: 0 }}>
        {question}
      </h3>
      
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {options.map((option, idx) => {
          let optionStyle = {
            padding: '12px 16px',
            borderRadius: '8px',
            border: '1px solid var(--border-color, #cbd5e1)',
            cursor: hasSubmitted ? 'default' : 'pointer',
            transition: 'all 0.2s',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: 'var(--bg-panel, #ffffff)',
          };

          let icon = null;

          if (hasSubmitted) {
            if (idx === correct_index) {
              // The correct answer gets green highlight
              optionStyle.border = '1px solid #10b981';
              optionStyle.background = 'rgba(16, 185, 129, 0.1)';
              icon = <Check size={18} color="#10b981" />;
            } else if (idx === selectedIndex) {
              // Wrong answer selected gets red highlight
              optionStyle.border = '1px solid #ef4444';
              optionStyle.background = 'rgba(239, 68, 68, 0.1)';
              icon = <X size={18} color="#ef4444" />;
            } else {
              optionStyle.opacity = 0.6;
            }
          } else {
            // Hover and active states before submission
            if (selectedIndex === idx) {
              optionStyle.border = '1px solid var(--accent-pink, #f472b6)';
              optionStyle.background = 'rgba(244, 114, 182, 0.05)';
            }
          }

          return (
            <div 
              key={idx}
              style={optionStyle}
              onClick={() => !hasSubmitted && setSelectedIndex(idx)}
              onMouseOver={(e) => {
                if (!hasSubmitted && selectedIndex !== idx) {
                  e.currentTarget.style.background = 'var(--bg-secondary, #f1f5f9)';
                }
              }}
              onMouseOut={(e) => {
                if (!hasSubmitted && selectedIndex !== idx) {
                  e.currentTarget.style.background = 'var(--bg-panel, #ffffff)';
                }
              }}
            >
              <span style={{ fontSize: '14px' }}>{option}</span>
              {icon && <span>{icon}</span>}
            </div>
          );
        })}
      </div>

      {!hasSubmitted && (
        <button
          onClick={handleSubmit}
          disabled={selectedIndex === null}
          style={{
            marginTop: '16px',
            width: '100%',
            padding: '10px',
            borderRadius: '8px',
            border: 'none',
            background: selectedIndex !== null ? 'var(--accent-pink, #f472b6)' : 'var(--bg-tertiary, #e2e8f0)',
            color: selectedIndex !== null ? '#ffffff' : 'var(--text-secondary, #64748b)',
            fontWeight: '600',
            cursor: selectedIndex !== null ? 'pointer' : 'not-allowed',
            transition: 'background 0.2s',
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            gap: '8px'
          }}
        >
          <Send size={16} /> 提交答案
        </button>
      )}

      {hasSubmitted && explanation && (
        <div style={{
          marginTop: '16px',
          padding: '12px',
          borderRadius: '8px',
          background: 'var(--bg-panel, #ffffff)',
          borderLeft: `4px solid ${selectedIndex === correct_index ? '#10b981' : '#ef4444'}`,
          fontSize: '13px',
          color: 'var(--text-secondary, #475569)'
        }}>
          <strong>解析：</strong> {explanation}
        </div>
      )}
    </div>
  );
}
