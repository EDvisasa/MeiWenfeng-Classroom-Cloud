/**
 * 递归倒序逐轮回滚指定会话在数据库和向量库中的记忆（LIFO 栈式回滚）。
 * 从当前窗口最后一条开始，逐步回退到目标待重新发送的对话索引。
 */
export async function executeRecursiveRollback({
  messages,
  index,
  activeSessionId,
  apiBase,
  fetchFn = fetch
}) {
  const currMessages = [...messages];
  if (!activeSessionId) {
    return { success: true, remainingMessages: currMessages.slice(0, index) };
  }

  while (currMessages.length > index) {
    // 过滤并穿透尾部多余的系统提示信息（如 [系统设置]、🔍 检索提示等）
    let asstIdx = currMessages.length - 1;
    while (asstIdx >= index && currMessages[asstIdx].role === 'system_info') {
      asstIdx--;
    }
    if (asstIdx < index) {
      // 目标索引之后仅剩系统辅助信息，直接裁剪返回
      return { success: true, remainingMessages: currMessages.slice(0, index) };
    }

    // 寻找当前轮次对应的用户消息（穿透中间夹杂的 system_info 检索提示）
    let userIdx = asstIdx - 1;
    while (userIdx >= 0 && currMessages[userIdx].role === 'system_info') {
      userIdx--;
    }

    let expectedAsst = null;
    let expectedUser = null;
    let numToPop = 1;

    if (
      currMessages[asstIdx].role === 'assistant' &&
      userIdx >= index &&
      currMessages[userIdx].role === 'user'
    ) {
      expectedAsst = currMessages[asstIdx].content;
      expectedUser = currMessages[userIdx].content;
      numToPop = currMessages.length - userIdx;
    } else if (currMessages[asstIdx].role === 'assistant') {
      expectedAsst = currMessages[asstIdx].content;
      numToPop = currMessages.length - asstIdx;
    } else {
      expectedUser = currMessages[asstIdx].content;
      numToPop = currMessages.length - asstIdx;
    }

    try {
      const res = await fetchFn(`${apiBase}/api/chat/sessions/${activeSessionId}/rollback_step`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          expected_user_msg: expectedUser,
          expected_assistant_msg: expectedAsst
        })
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        const detail = errData.detail || '回滚失败，已中止重新发送以保护历史数据。';
        return { success: false, error: detail, remainingMessages: currMessages };
      }
    } catch (e) {
      return { success: false, error: `网络异常：回滚请求失败 (${e.message})`, remainingMessages: currMessages };
    }

    currMessages.splice(currMessages.length - numToPop, numToPop);
  }

  return { success: true, remainingMessages: currMessages };
}
