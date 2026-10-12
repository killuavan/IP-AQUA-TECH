(function () {
  'use strict';

  const endpoint = '/iot/api/latest/';
  const updatedEl = document.getElementById('dashboardUpdated');
  const phEl = document.getElementById('dashboardPh');
  const tdsEl = document.getElementById('dashboardTds');
  const turbidityEl = document.getElementById('dashboardTurbidity');
  const voltageEl = document.getElementById('dashboardVoltage');

  if (!phEl) return;

  function number(value, decimals) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed.toFixed(decimals) : '-';
  }

  function render(data) {
    const water = data.readings && data.readings.water_quality;
    const solar = data.readings && data.readings.solar;
    const waterPayload = water && water.payload ? water.payload : {};
    const solarPayload = solar && solar.payload ? solar.payload : {};

    const waterTimestamp = Date.parse(waterPayload.timestamp || (water && water.received_at) || '');
    const rangeStart = Date.parse(document.body.dataset.waterRangeStart || '');
    const rangeEnd = Date.parse(document.body.dataset.waterRangeEnd || '');
    const displayedTimestamp = Date.parse((updatedEl && updatedEl.dataset.readingTimestamp) || '');
    const isInSelectedRange = Number.isFinite(waterTimestamp)
      && (!Number.isFinite(rangeStart) || waterTimestamp >= rangeStart)
      && (!Number.isFinite(rangeEnd) || waterTimestamp <= rangeEnd)
      && waterTimestamp <= Date.now();
    const isNewerThanDisplayed = !Number.isFinite(displayedTimestamp)
      || waterTimestamp > displayedTimestamp;

    if (isInSelectedRange && isNewerThanDisplayed) {
      if (waterPayload.ph != null) phEl.textContent = number(waterPayload.ph, 2);
      if (waterPayload.tds != null) tdsEl.textContent = number(waterPayload.tds, 0);
      if (waterPayload.turbidity != null) {
        turbidityEl.textContent = number(waterPayload.turbidity, 2);
      }
      if (updatedEl) {
        const timestamp = waterPayload.timestamp || water.received_at;
        updatedEl.textContent = new Date(timestamp).toLocaleString();
        updatedEl.dataset.readingTimestamp = timestamp;
      }
    }
    if (solarPayload.panel_voltage != null) {
      voltageEl.textContent = number(solarPayload.panel_voltage, 2);
    }
  }

  async function refresh() {
    try {
      const response = await fetch(endpoint, {
        cache: 'no-store',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      });
      if (!response.ok) throw new Error('Firebase live request failed');
      render(await response.json());
    } catch (error) {
      console.error('Dashboard live data error:', error);
    }
  }

  refresh();
  window.setInterval(refresh, 5000);
})();
