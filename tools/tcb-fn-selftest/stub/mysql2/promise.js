/* 自检用假 mysql2/promise（只记录 SQL、返回固定数据，不连真库） */
const calls = [];
function fake(sql) {
  const s = String(sql).toUpperCase();
  if (s.indexOf('GROUP BY APP_VERSION') >= 0) return [[{ v: '3.00.41', c: 2 }]];
  if (s.indexOf('GROUP BY FEATURE') >= 0) return [[{ f: 'ai', c: 1 }]];
  if (s.indexOf('COUNT(') >= 0) return [[{ c: '7' }]];
  if (s.indexOf('FROM APP_LICENSE') >= 0) {
    return [[{ id: 1, code: 'C3-TEST-0001', plan: 'pro', features: 'ai,routes,feedback', device_id: '', expires_at: null, enabled: 1 }]];
  }
  return [[{ affectedRows: 1 }]];
}
module.exports = {
  createPool: () => ({
    query: async (sql, params) => { calls.push(['query', sql, params || []]); return fake(sql); },
    execute: async (sql, params) => { calls.push(['execute', sql, params || []]); return fake(sql); }
  }),
  __calls: calls
};
