import React, { useState, useEffect } from 'react';
import { Target, Check, RefreshCw, ChevronDown, ChevronUp } from 'lucide-react';

const MissionProposalCard = ({ proposalData, onConfirm, onReject }) => {
  const [isExpanded, setIsExpanded] = useState(true);
  const [formData, setFormData] = useState({
    goal: '',
    time: '',
    constraints: '',
    skill: ''
  });
  const [feedback, setFeedback] = useState('');

  // 同步属性
  useEffect(() => {
    if (proposalData) {
      setFormData({
        goal: proposalData.goal || '',
        time: proposalData.time || '',
        constraints: proposalData.constraints || '',
        skill: proposalData.skill || ''
      });
      setFeedback('');
    }
  }, [proposalData]);

  if (!proposalData) return null;

  const handleConfirm = () => {
    onConfirm(formData);
  };

  const handleReject = () => {
    onReject(feedback, formData);
  };

  const inputStyle = {
    width: '100%',
    boxSizing: 'border-box',
    padding: '6px 0',
    border: 'none',
    borderBottom: '1px solid var(--border-color, #e2e8f0)',
    background: 'transparent',
    color: 'var(--text-primary, #334155)',
    fontSize: '13px',
    fontFamily: 'inherit',
    resize: 'vertical',
    minHeight: '28px',
    outline: 'none',
    transition: 'border-color 0.2s'
  };

  const labelStyle = {
    display: 'block',
    fontSize: '12px',
    fontWeight: '600',
    color: 'var(--text-secondary, #64748b)',
    marginBottom: '2px',
    marginTop: '16px',
    letterSpacing: '0.3px'
  };

  return (
    <div style={{
      position: 'absolute',
      bottom: '100%',
      marginBottom: '16px',
      left: 0,
      width: '100%',
      boxSizing: 'border-box',
      background: 'var(--bg-panel, #ffffff)',
      border: '1px solid var(--border-color, #e2e8f0)',
      borderRadius: '8px',
      padding: '20px 24px',
      boxShadow: '0 12px 32px -4px rgba(0, 0, 0, 0.1), 0 8px 16px -8px rgba(0, 0, 0, 0.05)',
      zIndex: 10000,
      display: 'flex',
      flexDirection: 'column',
      color: 'var(--text-primary, #1e293b)',
      maxHeight: '70vh',
      overflowY: 'auto',
      transition: 'all 0.3s ease'
    }}>
      <div 
        style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer', paddingBottom: isExpanded ? '8px' : '0' }}
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Target size={16} color="var(--text-primary)" />
          <span style={{ fontSize: '15px', fontWeight: '700', letterSpacing: '0.2px' }}>确认学习目标</span>
        </div>
        <div style={{ color: 'var(--text-secondary, #64748b)' }}>
          {isExpanded ? <ChevronDown size={18} /> : <ChevronUp size={18} />}
        </div>
      </div>
      
      {isExpanded && (
        <>
          <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '4px'
      }}>
        <label style={{ ...labelStyle, marginTop: 8 }}>核心目标</label>
        <textarea 
          style={inputStyle}
          value={formData.goal}
          onChange={(e) => setFormData({...formData, goal: e.target.value})}
          onFocus={(e) => e.target.style.borderBottomColor = '#0ea5e9'}
          onBlur={(e) => e.target.style.borderBottomColor = 'var(--border-color, #e2e8f0)'}
        />

        <label style={labelStyle}>每日投入时间</label>
        <input 
          type="text"
          style={inputStyle}
          value={formData.time}
          onChange={(e) => setFormData({...formData, time: e.target.value})}
          onFocus={(e) => e.target.style.borderBottomColor = '#0ea5e9'}
          onBlur={(e) => e.target.style.borderBottomColor = 'var(--border-color, #e2e8f0)'}
        />

        <label style={labelStyle}>学习约束</label>
        <textarea 
          style={inputStyle}
          value={formData.constraints}
          onChange={(e) => setFormData({...formData, constraints: e.target.value})}
          onFocus={(e) => e.target.style.borderBottomColor = '#0ea5e9'}
          onBlur={(e) => e.target.style.borderBottomColor = 'var(--border-color, #e2e8f0)'}
        />

        <label style={labelStyle}>当前水平</label>
        <textarea 
          style={inputStyle}
          value={formData.skill}
          onChange={(e) => setFormData({...formData, skill: e.target.value})}
          onFocus={(e) => e.target.style.borderBottomColor = '#0ea5e9'}
          onBlur={(e) => e.target.style.borderBottomColor = 'var(--border-color, #e2e8f0)'}
        />
      </div>

      <div style={{ marginTop: '24px', paddingTop: '16px', borderTop: '1px dashed var(--border-color, #e2e8f0)' }}>
        <textarea 
          style={{ ...inputStyle, minHeight: '36px', borderBottom: '1px solid transparent', backgroundColor: 'var(--bg-secondary, #f8fafc)', padding: '10px 12px', borderRadius: '6px' }}
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          placeholder="如需调整，请在此输入反馈意见发给AI..."
          onFocus={(e) => e.target.style.borderBottomColor = '#cbd5e1'}
          onBlur={(e) => e.target.style.borderBottomColor = 'transparent'}
        />
      </div>

      <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end', marginTop: '20px' }}>
        <button
          onClick={handleReject}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '8px 16px',
            borderRadius: '6px',
            border: '1px solid var(--border-color, #cbd5e1)',
            background: 'transparent',
            color: 'var(--text-secondary, #475569)',
            fontSize: '13px',
            fontWeight: '500',
            cursor: 'pointer',
            transition: 'background 0.2s, color 0.2s'
          }}
          onMouseOver={(e) => { e.currentTarget.style.background = 'var(--bg-secondary, #f1f5f9)'; e.currentTarget.style.color = 'var(--text-primary, #0f172a)' }}
          onMouseOut={(e) => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--text-secondary, #475569)' }}
        >
          <RefreshCw size={14} /> 重新拟定
        </button>
        <button
          onClick={handleConfirm}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '8px 20px',
            borderRadius: '6px',
            border: '1px solid #0f172a',
            background: '#0f172a',
            color: '#ffffff',
            fontSize: '13px',
            fontWeight: '600',
            cursor: 'pointer',
            boxShadow: '0 2px 4px rgba(0, 0, 0, 0.1)',
            transition: 'opacity 0.2s'
          }}
          onMouseOver={(e) => e.currentTarget.style.opacity = '0.9'}
          onMouseOut={(e) => e.currentTarget.style.opacity = '1'}
        >
          <Check size={14} /> 确认并下发
        </button>
      </div>
        </>
      )}
    </div>
  );
};

export default MissionProposalCard;
