// Module xử lý tính năng Drafts

export function loadDraftsPage(forceReload = false) {
  console.log('Loading Drafts page...', forceReload);
  
  const container = document.getElementById('page-drafts');
  if (container) {
    // Placeholder UI trong lúc chờ phát triển hoàn thiện
    container.innerHTML = '<div style="padding: 2rem;"><h3>Drafts</h3><p>Tính năng quản lý Drafts đang được phát triển...</p></div>';
  }
}