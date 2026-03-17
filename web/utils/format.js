const timeFormatter = new Intl.DateTimeFormat('vi-VN', { hour: '2-digit', minute: '2-digit' });

export function formatTime() {
  return timeFormatter.format(new Date());
}

export function safeHostname(url) {
  try {
    return new URL(url).hostname;
  } catch {
    return '';
  }
}

const THINK_REGEX = /<think>([\s\S]*?)<\/think>/i;

export function parseThinking(content) {
  const text = String(content || '');
  const match = text.match(THINK_REGEX);
  if (match) {
    return {
      thinking: match[1].trim(),
      answer: text.replace(THINK_REGEX, '').trim()
    };
  }
  return { thinking: null, answer: text.trim() };
}

const ICONS = {
  confluence: '\u{1F4D8}',
  jira: '\u{1F7E3}',
  slack: '\u{1F4AC}'
};

export function getSourceIcon(source) {
  return ICONS[source] || '\u{1F4C4}';
}

const BADGES = {
  confluence: 'badge-confluence',
  jira: 'badge-jira',
  slack: 'badge-slack'
};

export function getBadgeClass(source) {
  return BADGES[source] || 'badge-confluence';
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

  return Math.max(0, Math.min(100, pct)).toFixed(0) + '%';
}
