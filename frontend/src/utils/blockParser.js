function stripControlTags(text) {
  if (!text) return '';
  let cleaned = text;
  cleaned = cleaned.replace(/\s*<monologue>((?:(?!<monologue>)[\s\S])*?)(?:<\/monologue>|\/>|$)\s*/gi, '');
  cleaned = cleaned.replace(/\s*<execute_bash>[\s\S]*?(?:<\/execute_bash>|\/>|$)\s*/gi, '');
  cleaned = cleaned.replace(/\s*<call_tool[\s\S]*?(?:<\/call_tool>|\/>|$)\s*/gi, '');
  cleaned = cleaned.replace(/\s*<tool_batch>[\s\S]*?(?:<\/tool_batch>|\/>|$)\s*/gi, '');
  cleaned = cleaned.replace(/\s*<property_update[\s\S]*?(?:<\/property_update>|\/>|$)\s*/gi, '');
  cleaned = cleaned.replace(/\s*<system_pass[\s\S]*?(?:<\/system_pass>|\/>|$)\s*/gi, '');
  cleaned = cleaned.replace(/\s*<memory_decay[\s\S]*?(?:<\/memory_decay>|\/>|$)\s*/gi, '');
  cleaned = cleaned.replace(/\s*<new_course[\s\S]*?(?:<\/new_course>|\/>|$)\s*/gi, '');
  cleaned = cleaned.replace(/\s*\[SYSTEM_PASS\]\s*/gi, '');
  return cleaned;
}

function parseBodyCards(bodyText) {
  if (!bodyText) return [];
  let text = bodyText;

  // Strip markdown bold markers that the AI might incorrectly place around our custom block tags
  text = text.replace(/\*\*\s*<glossary/gi, '<glossary').replace(/<\/glossary>\s*\*\*/gi, '</glossary>');
  text = text.replace(/\*\*\s*<explainer/gi, '<explainer').replace(/<\/explainer>\s*\*\*/gi, '</explainer>');
  text = text.replace(/\*\*\s*<quiz/gi, '<quiz').replace(/<\/quiz>\s*\*\*/gi, '</quiz>');

  // Force "盘古之白" (spaces) around inline bold markdown to prevent CommonMark parsing failures with Chinese punctuation
  text = text.replace(/\*\*([^\n]+?)\*\*/g, ' **$1** ');

  const quizRegex = /<quiz\b[^>]*>([\s\S]*?)(?:<\/quiz>|$)/gi;
  const missionRegex = /<mission_proposal([^>]*?)\/?>/gi;
  const explainerRegex = /<explainer\s+title=['"]?([^'"<>]+)['"]?>([\s\S]*?)(?:<\/explainer>|$)/gi;
  const glossaryRegex = /<glossary\s+term=['"]?([^'"<>]+)['"]?>([\s\S]*?)(?:<\/glossary>|$)/gi;

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
    let missionMatch;
    let lastMissionIndex = 0;
    let finalSegments = [];

    while ((missionMatch = missionRegex.exec(remainder)) !== null) {
      if (missionMatch.index > lastMissionIndex) {
        finalSegments.push({ isQuiz: false, isMission: false, content: remainder.substring(lastMissionIndex, missionMatch.index) });
      }
      const attrsStr = missionMatch[1];
      const goalMatch = attrsStr.match(/goal="([^"]*)"/);
      const timeMatch = attrsStr.match(/time="([^"]*)"/);
      const constraintsMatch = attrsStr.match(/constraints="([^"]*)"/);
      const skillMatch = attrsStr.match(/skill="([^"]*)"/);

      finalSegments.push({
        isQuiz: false,
        isMission: true,
        data: {
          goal: goalMatch ? goalMatch[1] : '',
          time: timeMatch ? timeMatch[1] : '',
          constraints: constraintsMatch ? constraintsMatch[1] : '',
          skill: skillMatch ? skillMatch[1] : ''
        }
      });
      lastMissionIndex = missionRegex.lastIndex;
    }
    if (lastMissionIndex < remainder.length) {
      finalSegments.push({ isQuiz: false, isMission: false, content: remainder.substring(lastMissionIndex) });
    }

    segments.push(...finalSegments);
  }

  let explainerSegments = [];
  segments.forEach(seg => {
    if (seg.isQuiz || seg.isMission) {
      explainerSegments.push(seg);
      return;
    }
    let subText = seg.content;
    let lastExpIndex = 0;
    let expMatch;
    while ((expMatch = explainerRegex.exec(subText)) !== null) {
      if (expMatch.index > lastExpIndex) {
        explainerSegments.push({ isQuiz: false, isMission: false, isExplainer: false, content: subText.substring(lastExpIndex, expMatch.index) });
      }
      explainerSegments.push({ isExplainer: true, title: expMatch[1], content: expMatch[2].trim() });
      lastExpIndex = explainerRegex.lastIndex;
    }
    if (lastExpIndex < subText.length) {
      explainerSegments.push({ isQuiz: false, isMission: false, isExplainer: false, content: subText.substring(lastExpIndex) });
    }
  });
  segments = explainerSegments;

  let glossarySegments = [];
  segments.forEach(seg => {
    if (seg.isQuiz || seg.isMission || seg.isExplainer) {
      glossarySegments.push(seg);
      return;
    }
    let subText = seg.content;
    let lastGlosIndex = 0;
    let glosMatch;
    while ((glosMatch = glossaryRegex.exec(subText)) !== null) {
      if (glosMatch.index > lastGlosIndex) {
        glossarySegments.push({ isQuiz: false, isMission: false, isExplainer: false, isGlossary: false, content: subText.substring(lastGlosIndex, glosMatch.index) });
      }
      glossarySegments.push({ isGlossary: true, term: glosMatch[1], content: glosMatch[2].trim() });
      lastGlosIndex = glossaryRegex.lastIndex;
    }
    if (lastGlosIndex < subText.length) {
      glossarySegments.push({ isQuiz: false, isMission: false, isExplainer: false, isGlossary: false, content: subText.substring(lastGlosIndex) });
    }
  });
  segments = glossarySegments;

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
    } else if (segment.isMission) {
      blocks.push({ type: 'mission_proposal', data: segment.data, status: 'done' });
    } else if (segment.isExplainer) {
      blocks.push({ type: 'explainer', title: segment.title, text: segment.content, status: 'done' });
    } else if (segment.isGlossary) {
      blocks.push({ type: 'glossary', term: segment.term, text: segment.content, status: 'done' });
    } else {
      const snippet = (segment.content || '').replace(/<\/think>/g, '').trim();
      const cleanedSnippet = stripControlTags(snippet);
      if (cleanedSnippet) {
        blocks.push({ type: 'text', text: cleanedSnippet });
      }
    }
  });
  return blocks;
}

export function parseAndMergeBlocks(blocksOrText, isStreaming = false) {
  let rawBlocks = Array.isArray(blocksOrText) ? blocksOrText : [{ type: 'text', text: blocksOrText || '' }];

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
          const bodyBlocks = parseBodyCards(preText);
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
        const bodyBlocks = parseBodyCards(postText);
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
