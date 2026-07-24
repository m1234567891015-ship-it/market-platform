function buildTwseInstitutionTradeUrl(dateStr) {
  const params = new URLSearchParams({
    date: dateStr,
    selectType: "ALLBUT0999",
    response: "json",
  });
  return `https://www.twse.com.tw/rwd/zh/fund/T86?${params.toString()}`;
}
async function fetchClientInstitutionalTradeForDate(code, dateStr) {
  const response = await fetchWithTimeout(
    buildTwseInstitutionTradeUrl(dateStr),
    { cache: "no-store" },
    10000,
  );
  if (!response.ok) return null;
  const payload = await response.json();
  if (payload?.stat !== "OK" || !Array.isArray(payload.data)) return null;
  const row = payload.data.find((item) => String(item?.[0] || "").trim() === String(code));
  return row ? buildClientInstitutionalTradeRecord(row, dateStr) : null;
}
async function fetchClientInstitutionalTradeHistory(detail, limit = 30) {
  const periods = [5, 10, 20, 30];
  const maxPeriod = Math.max(limit, ...periods);
  const snapshotDate = parseYmdDate(detail.snapshotDate);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  snapshotDate.setHours(0, 0, 0, 0);
  const baseDate = snapshotDate > today ? snapshotDate : today;
  const candidates = [];
  for (let offset = 0; offset <= 90; offset += 1) {
    const target = new Date(baseDate);
    target.setDate(baseDate.getDate() - offset);
    candidates.push(formatYmdDate(target));
  }
  const records = [];
  const seen = new Set();
  const batchSize = 10;
  for (let start = 0; start < candidates.length; start += batchSize) {
    const batch = candidates.slice(start, start + batchSize);
    const results = await Promise.allSettled(
      batch.map((dateStr) => fetchClientInstitutionalTradeForDate(detail.code, dateStr)),
    );
    results.forEach((result) => {
      if (result.status !== "fulfilled" || !result.value?.date || seen.has(result.value.date)) return;
      seen.add(result.value.date);
      records.push(result.value);
    });
    if (records.length >= maxPeriod) break;
  }
  const rows = records
    .sort((left, right) => String(right.date || "").localeCompare(String(left.date || "")))
    .slice(0, maxPeriod);
  const summaries = {};
  periods.forEach((period) => {
    summaries[String(period)] = buildClientInstitutionalTradeSummary(rows, period);
  });
  const latestDate = rows[0]?.date ? rows[0].date.replaceAll("-", "") : formatYmdDate(baseDate);
  return {
    available: Boolean(rows.length),
    unit: "張",
    limit: maxPeriod,
    periods,
    defaultPeriod: 5,
    rows,
    summaries,
    summary: summaries["5"],
    source: "TWSE T86",
    sourceLink: buildTwseInstitutionTradeUrl(latestDate),
    sourceNote: "法人買賣超明細同步自證交所 T86，每日公告後更新。",
  };
}
async function fetchWithTimeout(url, options = {}, timeoutMs = 8000) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(timeoutId);
  }
}
