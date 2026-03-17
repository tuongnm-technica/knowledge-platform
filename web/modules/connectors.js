// Connectors Module - Kết nối dữ liệu
import { authFetch, API } from '../api/client.js';
import { showToast } from '../utils/ui.js';

export async function loadConnectorStats(refresh = false) {
  try {
    const response = await authFetch(`${API}/connectors/stats`);
    if (!response.ok) throw new Error('Failed to load connector stats');
    
    const data = await response.json();
    updateConnectorUI(data.stats || {});
  } catch (e) {
    console.error('Error loading connector stats:', e);
  }
}

function updateConnectorUI(stats) {
  // Update connector badges/indicators in UI
  Object.entries(stats).forEach(([connectorId, stat]) => {
    const badge = document.querySelector(`[data-connector="${connectorId}"]`);
    if (badge) {
      badge.setAttribute('data-documents', stat.documents || 0);
      badge.setAttribute('data-chunks', stat.chunks || 0);
      badge.setAttribute('data-last-sync', stat.last_sync || 'No sync');
    }
  });
}
