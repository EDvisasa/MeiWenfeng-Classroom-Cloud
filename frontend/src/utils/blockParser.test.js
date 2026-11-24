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

  // Behavior 12: ISSUE-42
  it('should NOT let drafted control tags like <property_update> cross-tag bleed or swallow middle text', () => {
    const input = 'Plan: mention <property_update> here.\n\nGreat story text...\n\n<property_update affection_delta="1" />';
    const result = parseAndMergeBlocks(input, false);

    expect(result).toEqual([
      { type: 'text', text: 'Plan: mentionhere.\n\nGreat story text...' }
    ]);
  });


  // Behavior 9: ISSUE-37
  it('should NOT let cards (<explainer>, <quiz>) inside <think> prematurely create blocks', () => {
    const input = `<think>
Let me plan the card:
<explainer title="同盘不同命">
> **钱羽擎**
> **媚吻锋**
</explainer>
And now write the final response.
</think>
*嫣然一笑* 夫君请看：
<explainer title="同盘不同命">
> **钱羽擎**
> **媚吻锋**
</explainer>
这就是分晓。`;

    const result = parseAndMergeBlocks(input, false);

    expect(result).toEqual([
      {
        type: 'thinking',
        text: `Let me plan the card:
<explainer title="同盘不同命">
> **钱羽擎**
> **媚吻锋**
</explainer>
And now write the final response.`,
        status: 'done'
      },
      {
        type: 'text',
        text: '*嫣然一笑* 夫君请看：'
      },
      {
        type: 'explainer',
        title: '同盘不同命',
        text: '>  **钱羽擎** \n>  **媚吻锋**',
        status: 'done'
      },
      {
        type: 'text',
        text: '这就是分晓。'
      }
    ]);
  });

  // Behavior 10: ISSUE-37 (streaming)
  it('should keep thinking as running and NOT extract cards when <think> is unclosed during streaming', () => {
    const input = `<think>
Thinking in progress...
<explainer title="草案">
草案内容
</explainer>
Still thinking...`;

    const result = parseAndMergeBlocks(input, true);

    expect(result).toEqual([
      {
        type: 'thinking',
        text: `Thinking in progress...
<explainer title="草案">
草案内容
</explainer>
Still thinking...`,
        status: 'running'
      }
    ]);
  });

  // Behavior 11: ISSUE-37 (nested quotes in card attributes)
  it('should parse <explainer> and <glossary> when title/term contains nested quotes', () => {
    const input = `<explainer title="🦊 媚吻锋拆夫君命 · 比劫夺财之坎，被'由心'一破">
> **钱羽擎**：庚辰 庚辰 丙午 丁酉
</explainer>
<glossary term="Father's Day">
Celebration of fathers.
</glossary>
<glossary term='Words with "Double Quotes"'>
Definitions with nested double quotes.
</glossary>`;

    const result = parseAndMergeBlocks(input, false);

    expect(result).toEqual([
      {
        type: 'explainer',
        title: "🦊 媚吻锋拆夫君命 · 比劫夺财之坎，被'由心'一破",
        text: ">  **钱羽擎** ：庚辰 庚辰 丙午 丁酉",
        status: 'done'
      },
      {
        type: 'glossary',
        term: "Father's Day",
        text: "Celebration of fathers.",
        status: 'done'
      },
      {
        type: 'glossary',
        term: 'Words with "Double Quotes"',
        text: "Definitions with nested double quotes.",
        status: 'done'
      }
    ]);
  });

  // Behavior 13: ISSUE-43 (unclosed card and control tag isolation)
  it('should NOT leak control tags (<monologue>, <property_update>) inside <explainer> even if unclosed', () => {
    const input = `<explainer title="Test FFT">
Lecture notes here.
<monologue>This is secret inner thought.</monologue>
<property_update affection_delta="1" />`;

    const result = parseAndMergeBlocks(input, false);

    expect(result).toEqual([
      {
        type: 'explainer',
        title: 'Test FFT',
        text: 'Lecture notes here.',
        status: 'done'
      }
    ]);
  });

  it('should strip control tags inside properly closed <explainer> or <glossary> as defense-in-depth', () => {
    const input = `<explainer title="Safety Test">
Explanation text.
<monologue>Accidental thought in explainer</monologue>
</explainer>
<glossary term="Term">
Glossary text.
<monologue>Accidental thought in glossary</monologue>
</glossary>`;

    const result = parseAndMergeBlocks(input, false);

    expect(result).toEqual([
      {
        type: 'explainer',
        title: 'Safety Test',
        text: 'Explanation text.',
        status: 'done'
      },
      {
        type: 'glossary',
        term: 'Term',
        text: 'Glossary text.',
        status: 'done'
      }
    ]);
  });

  // Behavior 14: Bug #50 (keep inline <glossary> inside Markdown bold/list intact for inline rendering)
  it('should keep inline <glossary> embedded inside bold/list lines inside the text block without breaking Markdown', () => {
    const input = '- **巧思机制（<glossary term="Looped Transformer">循环层架构说明</glossary>）**：物理上只有 24 层。\n- **术语前缀：<glossary term="MoE">混合专家</glossary>**：继续讲解。';

    const result = parseAndMergeBlocks(input, false);

    expect(result).toHaveLength(1);
    expect(result[0].type).toBe('text');
    expect(result[0].text).toContain('<glossary term="Looped Transformer">循环层架构说明</glossary>');
    expect(result[0].text).toContain('**术语前缀：<glossary term="MoE">混合专家</glossary>**');
  });

  // Behavior 15: Bug #53 (parse multiline <finalize_mission /> with course_id and entities into a structured card block)
  it('should parse single-line and multiline <finalize_mission /> tags into finalize_mission card blocks between text', () => {
    const input = [
      '我眼见你落笔应下这桩学契。',
      '',
      '<finalize_mission goal="系统研读《滴天髓》&quot;原典&quot;" time="每日50分钟" constraints="结合名家批注" skill="零基础小白" course_id="ditiansui_bazi"',
      '/>',
      '',
      '输入 `/lesson` 即可开讲第一课。'
    ].join('\n');

    const result = parseAndMergeBlocks(input, false);

    expect(result).toEqual([
      {
        type: 'text',
        text: '我眼见你落笔应下这桩学契。'
      },
      {
        type: 'finalize_mission',
        data: {
          goal: '系统研读《滴天髓》"原典"',
          time: '每日50分钟',
          constraints: '结合名家批注',
          skill: '零基础小白',
          course_id: 'ditiansui_bazi'
        },
        status: 'done'
      },
      {
        type: 'text',
        text: '输入 `/lesson` 即可开讲第一课。'
      }
    ]);
  });

  // Behavior 16: preserve raw user messages completely intact (no control-tag stripping or card splitting)
  it('should keep raw user messages untouched without stripping control tags or splitting cards when rawUserMessage is true', () => {
    const input = '我已确定学习目标<finalize_mission goal="研读原典" time="每日50分钟" constraints="精读" skill="入门" course_id="ditiansui_bazi" /> 并保留 `<property_update />` 和 <monologue>引用</monologue> 与 **粗体**';

    const result = parseAndMergeBlocks(input, false, { rawUserMessage: true });

    expect(result).toEqual([
      {
        type: 'text',
        text: input
      }
    ]);
  });

  // Behavior 17: Bug #53 (propagate course_id in <mission_proposal />)
  it('should extract course_id from <mission_proposal /> along with standard attributes', () => {
    const input = '请确认草案：<mission_proposal goal="系统研读《滴天髓》" time="每日50分钟" constraints="结合批注" skill="零基础" course_id="ditiansui_bazi" />';

    const result = parseAndMergeBlocks(input, false);

    expect(result).toEqual([
      {
        type: 'text',
        text: '请确认草案：'
      },
      {
        type: 'mission_proposal',
        data: {
          goal: '系统研读《滴天髓》',
          time: '每日50分钟',
          constraints: '结合批注',
          skill: '零基础',
          course_id: 'ditiansui_bazi'
        },
        status: 'done'
      }
    ]);
  });

  // Behavior 18: Bug #53 (Tier-1 <think> isolation & defense-in-depth stripping inside <explainer>/<glossary>)
  it('should isolate <finalize_mission /> inside <think> and strip stray <finalize_mission /> inside containers', () => {
    const input = `<think>Draft <finalize_mission goal="draft" time="10m" constraints="none" skill="low" /></think>
<explainer title="Notes">
Content inside explainer.
<finalize_mission goal="stray" time="10m" constraints="none" skill="low" />
</explainer>`;

    const result = parseAndMergeBlocks(input, false);

    expect(result).toEqual([
      {
        type: 'thinking',
        text: 'Draft <finalize_mission goal="draft" time="10m" constraints="none" skill="low" />',
        status: 'done'
      },
      {
        type: 'explainer',
        title: 'Notes',
        text: 'Content inside explainer.',
        status: 'done'
      }
    ]);
  });
});