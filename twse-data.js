(function () {
  function loadCachedData() {
    try {
      var xhr = new XMLHttpRequest();
      xhr.open("GET", "twse-cache.json?v=20260609-3", false);
      xhr.send(null);

      if (xhr.status >= 200 && xhr.status < 300 && xhr.responseText) {
        var payload = JSON.parse(xhr.responseText);
        window.TWSE_ALL_STOCKS = payload && Array.isArray(payload.all_stocks) ? payload.all_stocks : [];
        return payload && payload.site_data ? payload.site_data : null;
      }
    } catch (error) {
      // Fall through to the live API fetch in app.js.
    }
    window.TWSE_ALL_STOCKS = [];
    return null;
  }

  window.TWSE_DATA = loadCachedData();
})();
