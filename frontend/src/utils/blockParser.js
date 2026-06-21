export function parseAndMergeBlocks(blocksOrText, isStreaming = false) {
  let rawBlocks = Array.isArray(blocksOrText) ? blocksOrText : [{ type: 'text', text: blocksOrText || '' }];

  // 1. Normalize: split text blocks containing <thought> into separate blocks
  let normalized = [];
  rawBlocks.forEach(b => {
    if (b.type === 'text') {
      let text = b.text || '';
      text = text.replace(/\s*【此刻内心】[：:]\s*[（(][\s\S]*?[)）]\s*/g, '');
      text = text.replace(/\s*<execute_bash>[\s\S]*?(?:<\/execute_bash>|$)\s*/g, '');
      text = text.replace(/\s*<call_tool[\s\S]*?(?:<\/call_tool>|$)\s*/g, '');
      text = text.replace(/\s*<tool_batch>[\s\S]*?(?:<\/tool_batch>|$)\s*/g, '');

      const quizRegex = /<quiz\b[^>]*>([\s\S]*?)(?:<\/quiz>|$)/g;
      const thoughtRegex = /<thought>([\s\S]*?)(?:<\/thought>|$)/g;
      const missionRegex = /<mission_proposal([^>]*?)\/?>/g;
      
      // We need to extract both quiz, mission_proposal and thought tags. Since they might be interleaved or one after another,
      // a robust way is to split by both, but since currently only text has thoughts, we can just extract quizzes and missions first.
      
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
        
        // Now find mission_proposals in the remainder
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

      segments.forEach(segment => {
        if (segment.isQuiz) {
          try {
            let cleanJsonStr = segment.content.replace(/^```json\s*/i, '').replace(/```\s*$/, '').trim();
            const quizData = JSON.parse(cleanJsonStr);
            normalized.push({ type: 'quiz', data: quizData, status: 'done' });
          } catch (e) {
            console.error("Failed to parse quiz JSON:", e, "Raw content:", segment.content);
            normalized.push({ type: 'text', text: `<quiz>\n${segment.content}\n</quiz>` });
          }
        } else if (segment.isMission) {
          normalized.push({ type: 'mission_proposal', data: segment.data, status: 'done' });
        } else {
          // Process thought tags within the text segment
          let textSegment = segment.content;
          let match;
          let lastIndex = 0;
          while ((match = thoughtRegex.exec(textSegment)) !== null) {
            if (match.index > lastIndex) {
              const snippet = textSegment.substring(lastIndex, match.index).replace(/<\/thought>/g, '').trim();
              if (snippet) normalized.push({ type: 'text', text: snippet });
            }
            const isRunning = isStreaming ? !textSegment.substring(match.index).includes('</thought>') : false;
            normalized.push({ type: 'thinking', text: match[1].trim(), status: isRunning ? 'running' : 'done' });
            lastIndex = thoughtRegex.lastIndex;
          }
          if (lastIndex < textSegment.length) {
            const snippet = textSegment.substring(lastIndex).replace(/<\/thought>/g, '').trim();
            if (snippet) normalized.push({ type: 'text', text: snippet });
          }
        }
      });

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
