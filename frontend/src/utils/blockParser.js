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

      const thoughtRegex = /<thought>([\s\S]*?)(?:<\/thought>|$)/g;
      let match;
      let lastIndex = 0;
      while ((match = thoughtRegex.exec(text)) !== null) {
        if (match.index > lastIndex) {
          const snippet = text.substring(lastIndex, match.index).replace(/<\/thought>/g, '').trim();
          if (snippet) normalized.push({ type: 'text', text: snippet });
        }
        const isRunning = isStreaming ? !text.substring(match.index).includes('</thought>') : false;
        normalized.push({ type: 'thinking', text: match[1].trim(), status: isRunning ? 'running' : 'done' });
        lastIndex = thoughtRegex.lastIndex;
      }
      if (lastIndex < text.length) {
        // 清理孤立的 </thought>
        const snippet = text.substring(lastIndex).replace(/<\/thought>/g, '').trim();
        if (snippet) normalized.push({ type: 'text', text: snippet });
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
