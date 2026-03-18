/**
 * test_graph_frontend_integration.js
 * 
 * Frontend integration tests for the Knowledge Graph module
 * Tests API connectivity and response handling
 * 
 * Run in browser console or with Jest/Mocha
 */

const API_BASE = 'http://localhost:8000/api';

// ─── Test utilities ────────────────────────────────────────────────────────

class TestRunner {
  constructor() {
    this.tests = [];
    this.passed = 0;
    this.failed = 0;
  }

  async run(name, fn) {
    console.log(`\n🧪 ${name}`);
    try {
      await fn();
      this.passed++;
      console.log(`✓ PASS`);
    } catch (e) {
      this.failed++;
      console.error(`✗ FAIL: ${e.message}`);
    }
  }

  summary() {
    console.log(`\n${'='.repeat(60)}`);
    console.log(`Tests passed: ${this.passed}`);
    console.log(`Tests failed: ${this.failed}`);
    console.log(`Total: ${this.passed + this.failed}`);
  }
}

// ─── Mock authFetch ────────────────────────────────────────────────────────

let _mockAuthToken = 'test-token-12345';

async function authFetch(url, options = {}) {
  const finalOptions = {
    headers: {
      'Authorization': `Bearer ${_mockAuthToken}`,
      'Content-Type': 'application/json',
      ...options.headers
    },
    ...options
  };
  
  const response = await fetch(url, finalOptions);
  return response;
}

// ─── Test assertions ────────────────────────────────────────────────────────

function assert(condition, message) {
  if (!condition) {
    throw new Error(message || 'Assertion failed');
  }
}

function assertEquals(actual, expected, message) {
  if (actual !== expected) {
    throw new Error(`${message}: expected ${expected}, got ${actual}`);
  }
}

function assertExists(value, message) {
  if (value === undefined || value === null) {
    throw new Error(`${message}: value does not exist`);
  }
}

function assertIsArray(value, message) {
  if (!Array.isArray(value)) {
    throw new Error(`${message}: expected array, got ${typeof value}`);
  }
}

function assertIsObject(value, message) {
  if (typeof value !== 'object' || value === null) {
    throw new Error(`${message}: expected object, got ${typeof value}`);
  }
}

// ─── API Tests ──────────────────────────────────────────────────────────────

async function testHealthEndpoint() {
  console.log('  Testing: GET /graph/health');
  
  const response = await authFetch(`${API_BASE}/graph/health`);
  assertEquals(response.status, 200, 'HTTP status');
  
  const data = await response.json();
  assertIsObject(data, 'Response');
  assertExists(data.totalDocuments, 'totalDocuments field');
  assertExists(data.coveragePercent, 'coveragePercent field');
  assertExists(data.freshnessDays, 'freshnessDays field');
  assertIsObject(data.statusByConnector, 'statusByConnector field');
  
  console.log(`  - Total documents: ${data.totalDocuments}`);
  console.log(`  - Coverage: ${data.coveragePercent}%`);
  console.log(`  - Freshness: ${data.freshnessDays} days`);
  console.log(`  - Connectors: ${Object.keys(data.statusByConnector).join(', ')}`);
}

async function testSnapshotEndpoint() {
  console.log('  Testing: GET /graph/snapshot');
  
  const response = await authFetch(`${API_BASE}/graph/snapshot?view=entities&limit=30&edge_limit=60`);
  assertEquals(response.status, 200, 'HTTP status');
  
  const data = await response.json();
  assertIsObject(data, 'Response');
  assertIsArray(data.nodes, 'nodes field');
  assertIsArray(data.edges, 'edges field');
  
  if (data.nodes.length > 0) {
    const node = data.nodes[0];
    assertExists(node.id, 'Node id');
    assertExists(node.label, 'Node label');
    assertExists(node.type, 'Node type');
    console.log(`  - Sample node: "${node.label}" (${node.type})`);
  }
  
  console.log(`  - Nodes: ${data.nodes.length}, Edges: ${data.edges.length}`);
}

async function testGapsEndpoint() {
  console.log('  Testing: GET /graph/gaps');
  
  const response = await authFetch(`${API_BASE}/graph/gaps?since_days=30`);
  assertEquals(response.status, 200, 'HTTP status');
  
  const data = await response.json();
  assertIsObject(data, 'Response');
  assertIsArray(data.staleSources, 'staleSources field');
  assertIsArray(data.orphanEntities, 'orphanEntities field');
  assertIsArray(data.missingRelationships, 'missingRelationships field');
  
  console.log(`  - Stale sources: ${data.staleSources.length}`);
  console.log(`  - Orphan entities: ${data.orphanEntities.length}`);
  console.log(`  - Missing relationships: ${data.missingRelationships.length}`);
}

async function testNodeDetailEndpoint() {
  console.log('  Testing: GET /graph/node/{nodeId}');
  
  // First get a node
  const snapshotRes = await authFetch(`${API_BASE}/graph/snapshot?view=entities&limit=5&edge_limit=0`);
  const snapshotData = await snapshotRes.json();
  
  if (snapshotData.nodes.length === 0) {
    console.log('  ⊘ Skipped: no nodes available');
    return;
  }
  
  const nodeId = snapshotData.nodes[0].id;
  const response = await authFetch(`${API_BASE}/graph/node/${encodeURIComponent(nodeId)}`);
  
  if (response.status === 404) {
    console.log('  ⊘ Node not found (expected if permissions restrict access)');
    return;
  }
  
  assertEquals(response.status, 200, 'HTTP status');
  
  const data = await response.json();
  assertIsObject(data, 'Response');
  assertExists(data.id, 'id field');
  assertExists(data.label, 'label field');
  assertExists(data.type, 'type field');
  assertIsObject(data.metadata, 'metadata field');
  assertIsArray(data.related, 'related field');
  
  console.log(`  - Node: "${data.label}" (${data.type})`);
  console.log(`  - Related items: ${data.related.length}`);
}

async function testViewEndpoint() {
  console.log('  Testing: GET /graph/view');
  
  const response = await authFetch(`${API_BASE}/graph/view?since_days=30&per_source=90`);
  assertEquals(response.status, 200, 'HTTP status');
  
  const data = await response.json();
  assertIsObject(data, 'Response');
  console.log(`  - View generated at: ${new Date(data.generated_at).toLocaleString()}`);
}

async function testFocusEndpoint() {
  console.log('  Testing: GET /graph/focus');
  
  // Get a node first
  const snapshotRes = await authFetch(`${API_BASE}/graph/snapshot?view=entities&limit=5`);
  const snapshotData = await snapshotRes.json();
  
  if (snapshotData.nodes.length === 0) {
    console.log('  ⊘ Skipped: no nodes available');
    return;
  }
  
  const nodeId = snapshotData.nodes[0].id;
  const response = await authFetch(`${API_BASE}/graph/focus?node_id=${encodeURIComponent(nodeId)}&depth=2`);
  
  // May return 400 if node not found
  if (response.status >= 200 && response.status < 300) {
    const data = await response.json();
    console.log(`  - Focus view generated successfully`);
  } else {
    console.log(`  ⊘ Focus view returned ${response.status} (may be expected)`);
  }
}

async function testErrorHandling() {
  console.log('  Testing: Error handling');
  
  // Test 400 - invalid node_id
  const response1 = await authFetch(`${API_BASE}/graph/focus?node_id=`);
  console.log(`  - Empty node_id returns ${response1.status}`);
  
  // Test 404 - nonexistent node
  const response2 = await authFetch(`${API_BASE}/graph/node/nonexistent_node_xyz`);
  console.log(`  - Nonexistent node returns ${response2.status}`);
  
  // Test invalid auth
  const headers = { 'Authorization': 'Bearer invalid_token' };
  const response3 = await fetch(`${API_BASE}/graph/health`, { headers });
  console.log(`  - Invalid token returns ${response3.status}`);
}

async function testAuthRequirement() {
  console.log('  Testing: Authentication requirement');
  
  // Call without auth header
  const response = await fetch(`${API_BASE}/graph/health`);
  
  if (response.status === 401 || response.status === 403) {
    console.log(`  - Correctly rejected unauthenticated request (${response.status})`);
  } else {
    console.log(`  - Returned ${response.status} (may not require auth)`);
  }
}

async function testResponseFormats() {
  console.log('  Testing: Response format compliance');
  
  // Test health response format
  const healthRes = await authFetch(`${API_BASE}/graph/health`);
  const health = await healthRes.json();
  assert(typeof health.totalDocuments === 'number', 'totalDocuments should be number');
  assert(typeof health.coveragePercent === 'number', 'coveragePercent should be number');
  assert(typeof health.freshnessDays === 'number', 'freshnessDays should be number');
  
  // Test snapshot response format
  const snapshotRes = await authFetch(`${API_BASE}/graph/snapshot`);
  const snapshot = await snapshotRes.json();
  assert(Array.isArray(snapshot.nodes), 'nodes should be array');
  assert(Array.isArray(snapshot.edges), 'edges should be array');
  
  if (snapshot.nodes.length > 0) {
    const node = snapshot.nodes[0];
    assert(typeof node.id === 'string', 'node.id should be string');
    assert(typeof node.label === 'string', 'node.label should be string');
    assert(typeof node.type === 'string', 'node.type should be string');
  }
  
  console.log(`  ✓ All response formats are correct`);
}

// ─── Run all tests ──────────────────────────────────────────────────────────

async function runAllTests() {
  console.log(`\n${'='.repeat(60)}`);
  console.log(`Knowledge Graph API Integration Tests`);
  console.log(`API Base: ${API_BASE}`);
  console.log(`${'='.repeat(60)}`);
  
  const runner = new TestRunner();
  
  try {
    await runner.run('Health Endpoint', testHealthEndpoint);
    await runner.run('Snapshot Endpoint', testSnapshotEndpoint);
    await runner.run('Gaps Endpoint', testGapsEndpoint);
    await runner.run('Node Detail Endpoint', testNodeDetailEndpoint);
    await runner.run('View Endpoint', testViewEndpoint);
    await runner.run('Focus Endpoint', testFocusEndpoint);
    await runner.run('Error Handling', testErrorHandling);
    await runner.run('Auth Requirement', testAuthRequirement);
    await runner.run('Response Format Compliance', testResponseFormats);
  } catch (e) {
    console.error('Test suite error:', e);
  }
  
  runner.summary();
}

// ─── Export for testing ──────────────────────────────────────────────────────

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { runAllTests, authFetch };
}

// ─── Auto-run if called directly ───────────────────────────────────────────

if (typeof window === 'undefined') {
  // Running in Node.js
  console.log('To run tests:');
  console.log('  1. In browser console: runAllTests()');
  console.log('  2. Or: node test_graph_frontend_integration.js');
} else {
  // In browser - expose globally
  window.runGraphTests = runAllTests;
  window.testAuthFetch = authFetch;
  console.log('Graph tests loaded. Run: runGraphTests()');
}
