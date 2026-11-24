import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { describe, it, expect, vi } from 'vitest';
import MissionProposalCard from './MissionProposalCard';

describe('MissionProposalCard', () => {
  it('preserves proposalData.course_id when user edits fields and confirms', () => {
    const onConfirm = vi.fn();
    render(
      <MissionProposalCard
        proposalData={{
          goal: '系统研读《滴天髓》原典',
          time: '每日50分钟',
          constraints: '结合名家批注解析',
          skill: '零基础小白',
          course_id: 'ditiansui_bazi',
        }}
        onConfirm={onConfirm}
        onReject={vi.fn()}
      />
    );

    const timeInput = screen.getByDisplayValue('每日50分钟');
    fireEvent.change(timeInput, { target: { value: '每日60分钟' } });

    fireEvent.click(screen.getByRole('button', { name: /确认并下发/ }));

    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onConfirm).toHaveBeenCalledWith({
      goal: '系统研读《滴天髓》原典',
      time: '每日60分钟',
      constraints: '结合名家批注解析',
      skill: '零基础小白',
      course_id: 'ditiansui_bazi',
    });
  });
});
