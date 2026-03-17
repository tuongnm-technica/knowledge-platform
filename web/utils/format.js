export function formatTime() {
  return new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
}

export function safeHostname(url) {
  try {
    return new URL(url).hostname;
  } catch {
    return '';
  }
}

export function parseThinking(content) {
  const text = String(content || '');
  const thinkMatch = text.match(/<think>([\s\S]*?)<\/think>/i);
  const thinking = thinkMatch ? thinkMatch[1].trim() : null;
  const answer = text.replace(/<think>[\s\S]*?<\/think>/gi, '').trim();
  return { thinking, answer };
}

export function getSourceIcon(source) {
  if (source === 'confluence') return '\u{1F4D8}';
  if (source === 'jira') return '\u{1F7E3}';
  if (source === 'slack') return '\u{1F4AC}';
  return '\u{1F4C4}';
}

export function getBadgeClass(source) {
  if (source === 'confluence') return 'badge-confluence';
  if (source === 'jira') return 'badge-jira';
  if (source === 'slack') return 'badge-slack';
  return 'badge-confluence';
}

export function formatRelevancePercent(score) {
  const n = Number(score);
  if (!Number.isFinite(n) || n <= 0) return '';

  // Heuristic: backend scores are often 0-3 (LLM relevance), sometimes 0-1.
  let pct = 0;
  if (n <= 1.00001) pct = n * 100;
  else if (n <= 3.5) pct = (n / 3) * 100;
  else if (n <= 100) pct = n;
  else pct = 100;

  pct = Math.max(0, Math.min(100, pct));
  return pct.toFixed(0) + '%';
}
