function toneClass(tone) {
  if (tone === "up") return "up";
  if (tone === "down") return "down";
  return "flat";
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[character]);
}

function normalizeSafeUrl(value, fallback = "#") {
  const raw = String(value ?? "").trim();
  const fallbackUrl = String(fallback ?? "#").trim() || "#";
  if (!raw) return fallbackUrl;
  const compact = raw.replace(/[\u0000-\u001f\u007f\s]+/g, "").toLowerCase();
  if (compact.startsWith("javascript:") || compact.startsWith("data:") || compact.startsWith("vbscript:")) return fallbackUrl;
  if (raw.startsWith("#") || raw.startsWith("/") || raw.startsWith("./") || raw.startsWith("../")) return raw;
  try {
    const parsed = new URL(raw, window.location.origin);
    return parsed.protocol === "http:" || parsed.protocol === "https:" ? raw : fallbackUrl;
  } catch {
    return fallbackUrl;
  }
}

function safeUrl(value, fallback = "#") {
  return escapeHtml(normalizeSafeUrl(value, fallback));
}

function sanitizeHtml(value) {
  const template = document.createElement("template");
  const html = String(value ?? "");
  if (nativeInnerHtmlDescriptor?.set) {
    nativeInnerHtmlDescriptor.set.call(template, html);
  } else {
    template.innerHTML = html;
  }
  template.content.querySelectorAll("script, iframe, object, embed").forEach((node) => node.remove());
  template.content.querySelectorAll("*").forEach((node) => {
    [...node.attributes].forEach((attribute) => {
      const name = attribute.name.toLowerCase();
      if (name.startsWith("on")) {
        node.removeAttribute(attribute.name);
        return;
      }
      if (["href", "src", "xlink:href", "formaction"].includes(name)) {
        node.setAttribute(attribute.name, normalizeSafeUrl(attribute.value));
      }
    });
  });
  if (nativeInnerHtmlDescriptor?.get) {
    return nativeInnerHtmlDescriptor.get.call(template);
  }
  return template.innerHTML;
}

(function enforceSafeInnerHtml() {
  if (window.__MARKET_PULSE_SAFE_INNER_HTML__) return;
  const descriptor = Object.getOwnPropertyDescriptor(Element.prototype, "innerHTML");
  if (!descriptor?.set || !descriptor?.get) return;
  nativeInnerHtmlDescriptor = descriptor;
  window.__MARKET_PULSE_SAFE_INNER_HTML__ = true;
  Object.defineProperty(Element.prototype, "innerHTML", {
    configurable: descriptor.configurable,
    enumerable: descriptor.enumerable,
    get() {
      return descriptor.get.call(this);
    },
    set(value) {
      descriptor.set.call(this, sanitizeHtml(value));
    },
  });
})();

function formatRocDateFromDate(date) {
  const year = String(date.getFullYear() - 1911).padStart(3, "0");
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}/${month}/${day}`;
}

function parseTwseNumber(value) {
  const parsed = Number(String(value ?? "").replace(/,/g, "").trim());
  return Number.isFinite(parsed) ? parsed : null;
}

function formatYmdDate(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}${month}${day}`;
}

function parseYmdDate(value) {
  const match = String(value || "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return new Date();
  const [, year, month, day] = match;
  return new Date(Number(year), Number(month) - 1, Number(day));
}

function clampScore(value) {
  if (!Number.isFinite(value)) return 50;
  return Math.max(0, Math.min(100, Math.round(value)));
}

function setText(id, value) {
  const element = document.getElementById(id);
  if (element) element.textContent = value;
}

function parseAnalysisNumber(value) {
  if (value === null || value === undefined || value === "" || value === "--") return null;
  const parsed = Number(String(value).replace(/,/g, "").replace("%", "").trim());
  return Number.isFinite(parsed) ? parsed : null;
}

function parseMarketNumber(value) {
  if (value === null || value === undefined) return null;
  const parsed = Number(String(value).replace(/,/g, "").replace("%", "").trim());
  return Number.isFinite(parsed) ? parsed : null;
}

function formatGlobalValue(value, digits = 2) {
  const parsed = parseMarketNumber(value);
  if (!Number.isFinite(parsed)) return "--";
  return parsed.toLocaleString("zh-TW", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function formatGlobalVolume(value) {
  const parsed = parseMarketNumber(value);
  if (!Number.isFinite(parsed)) return "--";
  if (parsed >= 1000000000) return `${(parsed / 1000000000).toFixed(2)}B`;
  if (parsed >= 1000000) return `${(parsed / 1000000).toFixed(2)}M`;
  return Math.round(parsed).toLocaleString("zh-TW");
}

function formatSignedPercentValue(value, digits = 2) {
  return Number.isFinite(value) ? `${value >= 0 ? "+" : ""}${value.toFixed(digits)}%` : "--";
}

function formatUsDetailMetric(value, digits = 2) {
  const parsed = parseMarketNumber(value);
  return Number.isFinite(parsed) ? parsed.toLocaleString("zh-TW", { maximumFractionDigits: digits }) : "--";
}

function formatBacktestRatio(value, digits = 2) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed.toFixed(digits) : "--";
}

function formatBacktestPercent(value, digits = 0) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return "--";
  const percent = Math.abs(parsed) <= 1 ? parsed * 100 : parsed;
  return `${percent.toFixed(digits)}%`;
}

function formatUsSimulationMoney(value) {
  if (!Number.isFinite(value)) return "--";
  const prefix = value > 0 ? "+" : value < 0 ? "-" : "";
  return `${prefix}US$${Math.abs(value).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function assetHubTone(item) {
  const pct = parseMarketNumber(item?.pct);
  return pct > 0 ? "up" : pct < 0 ? "down" : "flat";
}

function formatAssetHubExpiration(value) {
  const text = String(value || "").trim();
  const timestamp = Number(text);
  if (!text) return "--";
  if (!Number.isFinite(timestamp) || timestamp <= 0) return text;
  return new Date(timestamp * 1000).toISOString().slice(0, 10);
}

function formatAssetOptionNumber(value, digits = 2) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "--";
  return number.toLocaleString("en-US", { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

function formatAssetOptionWhole(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "--";
  return Math.round(number).toLocaleString("en-US");
}

function formatAssetOptionIv(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "--";
  return `${(number * 100).toFixed(1)}%`;
}

function formatChartDate(date) {
  if (!date) return "";
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}
