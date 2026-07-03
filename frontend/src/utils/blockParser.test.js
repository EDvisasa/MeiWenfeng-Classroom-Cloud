import { describe, it, expect } from 'vitest';
import { parseAndMergeBlocks } from './blockParser';

describe('parseAndMergeBlocks', () => {
  // Tracer Bullet: Behavior 1
  it('should split text with <think> into separate text and done thinking blocks', () => {
    const input = 'Before thought. <think>This is a thought.</think> After thought.';
    const result = parseAndMergeBlocks(input, false);

    expect(result).toEqual([
      { type: 'text', text: 'Before thought.' },
      { type: 'thinking', text: 'This is a thought.', status: 'done' },
      { type: 'text', text: 'After thought.' }
    ]);
  });

  // Behavior 2
  it('should mark unclosed <think> as running when isStreaming is true', () => {
    const input = 'Start. <think>This is an ongoing thought...';
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
  it('should strip <monologue> completely from the final text', () => {
    const input = 'Normal text. <monologue>This is hidden.</monologue> More normal text.';
    const result = parseAndMergeBlocks(input, false);

    expect(result).toEqual([
      { type: 'text', text: 'Normal text.More normal text.' }
    ]);
  });

  // Behavior 6
  it('should strip side-effect tags like <property_update> and [SYSTEM_PASS] completely from the final text', () => {
    const input = 'Here is text. <property_update affection_delta="1" /> [SYSTEM_PASS] <new_course phase="1" topic="test"></new_course>';
    const result = parseAndMergeBlocks(input, false);

    expect(result).toEqual([
      { type: 'text', text: 'Here is text.' }
    ]);
  });

  // Behavior 7
  it('should NOT let <monologue> regex corrupt text if mentioned inside <think> block', () => {
    const input = '<think>Output an <monologue> block and at the very end</think> Hello world! <monologue>actual inner thought</monologue>';
    const result = parseAndMergeBlocks(input, false);

    expect(result).toEqual([
      { type: 'thinking', text: 'Output an <monologue> block and at the very end', status: 'done' },
      { type: 'text', text: 'Hello world!' }
    ]);
  });

  // Behavior 8
  it('should prevent greedy matching across opening tags when multiple or unclosed monologue tags exist', () => {
    const input = 'Mention <monologue> here. Middle text. <monologue>Actual thought</monologue> End text.';
    const result = parseAndMergeBlocks(input, false);

    expect(result).toEqual([
      { type: 'text', text: 'Mention <monologue> here. Middle text.End text.' }
    ]);
  });
});