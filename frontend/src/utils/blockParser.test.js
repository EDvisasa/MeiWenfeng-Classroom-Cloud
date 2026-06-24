import { describe, it, expect } from 'vitest';
import { parseAndMergeBlocks } from './blockParser';

describe('parseAndMergeBlocks', () => {
  // Tracer Bullet: Behavior 1
  it('should split text with <thought> into separate text and done thinking blocks', () => {
    const input = 'Before thought. <thought>This is a thought.</thought> After thought.';
    const result = parseAndMergeBlocks(input, false);

    expect(result).toEqual([
      { type: 'text', text: 'Before thought.' },
      { type: 'thinking', text: 'This is a thought.', status: 'done' },
      { type: 'text', text: 'After thought.' }
    ]);
  });

  // Behavior 2
  it('should mark unclosed <thought> as running when isStreaming is true', () => {
    const input = 'Start. <thought>This is an ongoing thought...';
    const result = parseAndMergeBlocks(input, true);

    expect(result).toEqual([
      { type: 'text', text: 'Start.' },
      { type: 'thinking', text: 'This is an ongoing thought...', status: 'running' }
    ]);
  });

  // Behavior 3
  it('should merge adjacent thinking blocks and inherit the status of the newest block', () => {
    const inputBlocks = [
      { type: 'thinking', text: 'First thought.', status: 'done' },
      { type: 'thinking', text: 'Second thought...', status: 'running' }
    ];
    // isStreaming = true is required for the second block to retain 'running' if it came from text originally,
    // but here we are passing structured blocks directly to test the merge logic.
    const result = parseAndMergeBlocks(inputBlocks, true);

    expect(result).toEqual([
      { type: 'thinking', text: 'First thought.\n\nSecond thought...', status: 'running' }
    ]);
  });

  // Behavior 4
  it('should NOT merge thinking blocks if separated by a tool block', () => {
    const inputBlocks = [
      { type: 'thinking', text: 'First thought.', status: 'done' },
      { type: 'tool', command: 'ls', status: 'done' },
      { type: 'thinking', text: 'Second thought...', status: 'running' }
    ];
    const result = parseAndMergeBlocks(inputBlocks, true);

    expect(result).toEqual([
      { type: 'thinking', text: 'First thought.', status: 'done' },
      { type: 'tool', command: 'ls', status: 'done' },
      { type: 'thinking', text: 'Second thought...', status: 'running' }
    ]);
  });

  // Behavior 5
  it('should strip <inner_thought> completely from the final text', () => {
    const input = 'Normal text. <inner_thought>This is hidden.</inner_thought> More normal text.';
    const result = parseAndMergeBlocks(input, false);

    expect(result).toEqual([
      { type: 'text', text: 'Normal text.More normal text.' }
    ]);
  });
});