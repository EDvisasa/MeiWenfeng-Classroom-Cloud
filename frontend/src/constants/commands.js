/**
 * 全局斜杠指令契约定义 (Single Source of Truth, SSOT)
 * 全站指令唯一事实标准，供输入框联想补全、工具栏快捷菜单及自动化测试统一引用。
 */

export const COMMANDS = [
  { cmd: '/set_mission', label: '/set_mission', desc: '设定或更改宏大学习目标（触发严苛审问）' },
  { cmd: '/cancel_mission', label: '/cancel_mission', desc: '退出当前的目标设定状态' },
  { cmd: '/lesson', label: '/lesson', desc: '开始新的课时，进入授课模式' },
  { cmd: '/plan', label: '/plan', desc: '生成或更新接下来的具体课程大纲' },
  { cmd: '/submit', label: '/submit', desc: '进行课题考核，AI会对你进行提问' },
  { cmd: '/reward', label: '/reward', desc: '获取好感奖励，触发狐妖娘溺爱互动' },
  { cmd: '/compact', label: '/compact', desc: '压缩当前会话历史，防止长对话 Token 溢出' },
  { cmd: '/summarize', label: '/summarize', desc: '沉淀并衰变短期记忆，生成全局长期记忆' },
  { cmd: '/prepare', label: '/prepare', desc: '将当前选定的文件切块并同步至系统知识库 (RAG)' },
  { cmd: '/update_persona', label: '/update_persona', desc: '根据最新记忆迭代并精简系统人设' }
];

export const SLASH_COMMANDS = COMMANDS;
