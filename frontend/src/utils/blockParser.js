function decodeXmlAttr(value) {
  if (!value) return '';
  return value
    .replace(/&quot;/g, '"')
    .replace(/&#39;|&apos;/g, "'")
    .replace(/&amp;/g, '&');
}

function parseMissionAttributes(attrsStr) {
  const data = { goal: '', time: '', constraints: '', skill: '', course_id: '' };
  if (!attrsStr) return data;
  const attrRegex = /\b(goal|time|constraints|skill|course_id)\s*=\s*(?:"([^"]*)"|'([^']*)')/gi;
  let match;
  while ((match = attrRegex.exec(attrsStr)) !== null) {
    const key = match[1].toLowerCase();
    const rawVal = match[2] ?? match[3] ?? '';
    data[key] = decodeXmlAttr(rawVal);
  }
  return data;
}

function splitSelfClosingCardSegments(segments, tagName, blockType) {
  const tagRegex = new RegExp(`<${tagName}\\b([^>]*?)(?:\\s*\\/>|>(?:\\s*<\\/${tagName}>)?)`, 'gi');
  const result = [];
  segments.forEach(seg => {
    if (seg.isQuiz || seg.blockType || seg.isExplainer || seg.isGlossary) {
      result.push(seg);
      return;
    }
    const subText = seg.content || '';
    tagRegex.lastIndex = 0;
    let lastIdx = 0;
    let match;
    while ((match = tagRegex.exec(subText)) !== null) {
      if (match.index > lastIdx) {
        result.push({ content: subText.substring(lastIdx, match.index) });
      }
      result.push({
        blockType,
        data: parseMissionAttributes(match[1])
      });
      lastIdx = tagRegex.lastIndex;
    }
    if (lastIdx < subText.length) {
      result.push({ content: subText.substring(lastIdx) });
    }
  });
  return result;
}

function stripControlTags(text, options = {}) {
  if (!text) return '';
  let cleaned = text;
  cleaned = cleaned.replace(/\s*<monologue>((?:(?!<monologue>)[\s\S])*?)(?:<\/monologue>|\/>|$)\s*/gi, '');
  cleaned = cleaned.replace(/\s*<execute_bash\b[^>]*>((?:(?!<execute_bash>)[\s\S])*?)(?:<\/execute_bash>|\/>|$)\s*/gi, '');
  cleaned = cleaned.replace(/\s*<call_tool\b[^>]*>((?:(?!<call_tool>)[\s\S])*?)(?:<\/call_tool>|\/>|$)\s*/gi, '');
  cleaned = cleaned.replace(/\s*<tool_batch\b[^>]*>((?:(?!<tool_batch>)[\s\S])*?)(?:<\/tool_batch>|\/>|$)\s*/gi, '');
  cleaned = cleaned.replace(/\s*<property_update\b[^>]*\/?>(\s*<\/property_update>)?\s*/gi, '');
  cleaned = cleaned.replace(/\s*<system_pass\b[^>]*\/?>(\s*<\/system_pass>)?\s*/gi, '');
  cleaned = cleaned.replace(/\s*<memory_decay\b[^>]*\/?>(\s*<\/memory_decay>)?\s*/gi, '');
  cleaned = cleaned.replace(/\s*<new_course\b[^>]*\/?>(\s*<\/new_course>)?\s*/gi, '');
  if (options.stripFinalizeMission) {
    cleaned = cleaned.replace(/[ \t]*<finalize_mission\b[^>]*?(?:\s*\/>|>(?:\s*<\/finalize_mission>)?)[ \t]*/gi, '');
    cleaned = cleaned.replace(/\n{3,}/g, '\n\n').trim();
  }
  cleaned = cleaned.replace(/\s*\[SYSTEM_PASS\]\s*/gi, '');
  return cleaned;
}

function parseBodyCards(bodyText, options = {}) {
  if (!bodyText) return [];
  let text = bodyText;

  // Strip markdown bold markers that the AI might incorrectly wrap around custom block tags (matched pairs only)
  text = text.replace(/\*\*\s*(<glossary\b[\s\S]*?<\/glossary>)\s*\*\*/gi, '$1');
  text = text.replace(/\*\*\s*(<explainer\b[\s\S]*?<\/explainer>)\s*\*\*/gi, '$1');
  text = text.replace(/\*\*\s*(<quiz\b[\s\S]*?<\/quiz>)\s*\*\*/gi, '$1');

  // Force "盘古之白" (spaces) around inline bold markdown to prevent CommonMark parsing failures with Chinese punctuation
  text = text.replace(/\*\*([^\n]+?)\*\*/g, ' **$1** ');

  const quizRegex = /<quiz\b[^>]*>([\s\S]*?)(?:<\/quiz>|$)/gi;
  const explainerRegex = /<explainer\s+[^>]*?title=(?:"([^"]*)"|'([^']*)'|([^\s>]+))[^>]*?>([\s\S]*?)(?:<\/explainer>|(?!(?:(?!<explainer)[\s\S])*?<\/explainer>)(?=<monologue\b|<property_update\b|<quiz\b|<mission_proposal\b|<finalize_mission\b|<call_tool\b|<execute_bash\b)|$)/gi;
  const glossaryRegex = /<glossary\s+[^>]*?term=(?:"([^"]*)"|'([^']*)'|([^\s>]+))[^>]*?>([\s\S]*?)(?:<\/glossary>|(?!(?:(?!<glossary)[\s\S])*?<\/glossary>)(?=<monologue\b|<property_update\b|<quiz\b|<mission_proposal\b|<finalize_mission\b|<call_tool\b|<execute_bash\b)|$)/gi;

  let segments = [];
  let lastQuizIndex = 0;
  let quizMatch;

  while ((quizMatch = quizRegex.exec(text)) !== null) {
    if (quizMatch.index > lastQuizIndex) {
      segments.push({ isQuiz: false, isMission: false, content: text.substring(lastQuizIndex, quizMatch.index).replace(/<\/quiz>/g, '') });
    }
    segments.push({ isQuiz: true, isMission: false, content: quizMatch[1].trim() });
    lastQuizIndex = quizRegex.lastIndex;
  }
  if (lastQuizIndex < text.length) {
    let remainder = text.substring(lastQuizIndex).replace(/<\/quiz>/g, '');
    segments.push({ isQuiz: false, content: remainder });
  }

  let explainerSegments = [];
  segments.forEach(seg => {
    if (seg.isQuiz) {
      explainerSegments.push(seg);
      return;
    }
    let subText = seg.content;
    let lastExpIndex = 0;
    let expMatch;
    while ((expMatch = explainerRegex.exec(subText)) !== null) {
      if (expMatch.index > lastExpIndex) {
        explainerSegments.push({ isQuiz: false, isExplainer: false, content: subText.substring(lastExpIndex, expMatch.index) });
      }
      const title = expMatch[1] ?? expMatch[2] ?? expMatch[3] ?? '';
      const content = (expMatch[4] || '').trim();
      explainerSegments.push({ isExplainer: true, title, content });
      lastExpIndex = explainerRegex.lastIndex;
    }
    if (lastExpIndex < subText.length) {
      explainerSegments.push({ isQuiz: false, isExplainer: false, content: subText.substring(lastExpIndex) });
    }
  });
  segments = explainerSegments;

  let glossarySegments = [];
  segments.forEach(seg => {
    if (seg.isQuiz || seg.isExplainer) {
      glossarySegments.push(seg);
      return;
    }
    let subText = seg.content;
    let lastGlosIndex = 0;
    let glosMatch;
    while ((glosMatch = glossaryRegex.exec(subText)) !== null) {
      const prevNl = glosMatch.index > 0 ? subText.lastIndexOf('\n', glosMatch.index - 1) : -1;
      const lineBefore = subText.slice(prevNl + 1, glosMatch.index);
      const nextNl = subText.indexOf('\n', glossaryRegex.lastIndex);
      const lineAfter = subText.slice(glossaryRegex.lastIndex, nextNl === -1 ? subText.length : nextNl);
      const isStandaloneLine = lineBefore.trim() === '' && lineAfter.trim() === '';
      if (!isStandaloneLine) {
        continue;
      }
      if (glosMatch.index > lastGlosIndex) {
        glossarySegments.push({ isQuiz: false, isExplainer: false, isGlossary: false, content: subText.substring(lastGlosIndex, glosMatch.index) });
      }
      const term = glosMatch[1] ?? glosMatch[2] ?? glosMatch[3] ?? '';
      const content = (glosMatch[4] || '').trim();
      glossarySegments.push({ isGlossary: true, term, content });
      lastGlosIndex = glossaryRegex.lastIndex;
    }
    if (lastGlosIndex < subText.length) {
      glossarySegments.push({ isQuiz: false, isExplainer: false, isGlossary: false, content: subText.substring(lastGlosIndex) });
    }
  });
  segments = glossarySegments;

  segments = splitSelfClosingCardSegments(segments, 'mission_proposal', 'mission_proposal');
  if (!options.stripFinalizeMission) {
    segments = splitSelfClosingCardSegments(segments, 'finalize_mission', 'finalize_mission');
  }

  let blocks = [];
  segments.forEach(segment => {
    if (segment.isQuiz) {
      try {
        let cleanJsonStr = segment.content.replace(/^```json\s*/i, '').replace(/```\s*$/, '').trim();
        const quizData = JSON.parse(cleanJsonStr);
        blocks.push({ type: 'quiz', data: quizData, status: 'done' });
      } catch (e) {
        console.error("Failed to parse quiz JSON:", e, "Raw content:", segment.content);
        blocks.push({ type: 'text', text: `<quiz>\n${segment.content}\n</quiz>` });
      }
    } else if (segment.blockType) {
      blocks.push({ type: segment.blockType, data: segment.data, status: 'done' });
    } else if (segment.isExplainer) {
      const cleanedContent = stripControlTags(segment.content || '', { stripFinalizeMission: true }).trim();
      blocks.push({ type: 'explainer', title: segment.title, text: cleanedContent, status: 'done' });
    } else if (segment.isGlossary) {
      const cleanedContent = stripControlTags(segment.content || '', { stripFinalizeMission: true }).trim();
      blocks.push({ type: 'glossary', term: segment.term, text: cleanedContent, status: 'done' });
    } else {
      const snippet = (segment.content || '').replace(/<\/think>/g, '').trim();
      const cleanedSnippet = stripControlTags(snippet, options);
      if (cleanedSnippet) {
        blocks.push({ type: 'text', text: cleanedSnippet });
      }
    }
  });
  return blocks;
}

export function parseAndMergeBlocks(blocksOrText, isStreaming = false, options = {}) {
  let rawBlocks = Array.isArray(blocksOrText) ? blocksOrText : [{ type: 'text', text: blocksOrText || '' }];

  if (options.rawUserMessage) {
    return rawBlocks
      .filter((b) => (b.type === 'text' ? Boolean(b.text) : true))
      .map((b) => (b.type === 'text' ? { type: 'text', text: b.text } : b));
  }

  // 1. Normalize: Top-Level CoT Isolation (Tier-1)
  let normalized = [];
  rawBlocks.forEach(b => {
    if (b.type === 'text') {
      let text = b.text || '';

      // Tier-1: 优先提取 <think>...</think> 顶级隔离容器
      // 在 <think> 内部的任何内容（无论是草拟的卡片标签还是代码），纯粹作为思维链沙盒，绝不提前裂变出卡片
      const thinkRegex = /<think>([\s\S]*?)(?:<\/think>|$)/gi;
      let lastIndex = 0;
      let match;

      while ((match = thinkRegex.exec(text)) !== null) {
        // 1. <think> 之前的正文内容
        if (match.index > lastIndex) {
          const preText = text.substring(lastIndex, match.index);
          const bodyBlocks = parseBodyCards(preText, options);
          normalized.push(...bodyBlocks);
        }

        // 2. <think> 内部思维链沙盒 (Scratchpad Sandbox)
        const matchedFull = match[0];
        const hasClosing = matchedFull.toLowerCase().includes('</think>');
        const isRunning = isStreaming ? !hasClosing : false;

        normalized.push({
          type: 'thinking',
          text: match[1].trim(),
          status: isRunning ? 'running' : 'done'
        });

        lastIndex = thinkRegex.lastIndex;
      }

      // 3. 最后一个 <think> 之后的剩余正文内容
      if (lastIndex < text.length) {
        const postText = text.substring(lastIndex);
        const bodyBlocks = parseBodyCards(postText, options);
        normalized.push(...bodyBlocks);
      }
    } else {
      const bStatus = isStreaming ? b.status : (b.type === 'thinking' || b.type === 'tool' ? 'done' : b.status);
      normalized.push({ ...b, status: bStatus });
    }
  });

  // 2. Merge adjacent thinking blocks
  let merged = [];
  normalized.forEach(b => {
    if (b.type === 'thinking') {
      const last = merged[merged.length - 1];
      if (last && last.type === 'thinking') {
        if (b.text) {
          last.text = last.text ? (last.text + '\n\n' + b.text) : b.text;
        }
        // Inherit status from the newest block
        last.status = b.status;
      } else {
        merged.push({ ...b });
      }
    } else {
      merged.push(b);
    }
  });
  return merged;
}
