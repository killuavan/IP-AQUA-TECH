(function () {
  'use strict';

  const voltageEl = document.getElementById('batteryLiveVoltage');
  const percentEl = document.getElementById('batteryLivePercent');
  const progressEl = document.getElementById('batteryLiveBar');
  const badgeEl = document.getElementById('batteryLiveBadge');
  const statusEl = document.getElementById('batteryLiveStatus');
  if (!voltageEl) return;

  function setStatus(text, className) {
    if (!statusEl) return;
    statusEl.textContent = '(' + text + ')';
    statusEl.className = 'small ' + className;
  }

  function updateBatteryStatus(voltage) {
    const warningPercent = Number(voltageEl.dataset.warningPercent);
    const criticalPercent = Number(voltageEl.dataset.criticalPercent);
    const emptyVoltage = Number(voltageEl.dataset.emptyVoltage);
    const fullVoltage = Number(voltageEl.dataset.fullVoltage);
    const percent = Math.max(0, Math.min(100,
      ((voltage - emptyVoltage) / (fullVoltage - emptyVoltage)) * 100,
    ));
    const status = percent <= criticalPercent
      ? 'Critical'
      : percent <= warningPercent
        ? 'Warning'
        : 'Normal';

    if (percentEl) percentEl.textContent = percent.toFixed(2);
    if (progressEl) {
      progressEl.style.width = percent.toFixed(2) + '%';
      progressEl.className = 'progress-bar ' + (
        status === 'Critical' ? 'bg-danger' : status === 'Warning' ? 'bg-warning' : 'bg-success'
      );
    }
    if (badgeEl) {
      badgeEl.textContent = status;
      badgeEl.className = 'badge ' + (
        status === 'Critical' ? 'badge-critical' : status === 'Warning' ? 'badge-warning' : 'badge-normal'
      );
    }
  }

  async function refreshVoltage() {
    try {
      const response = await fetch('/iot/api/latest/', {
        cache: 'no-store',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      });
      if (!response.ok) throw new Error('Live Firebase request failed');

      const data = await response.json();
      const solar = data.readings && data.readings.solar;
      const payload = solar && solar.payload ? solar.payload : {};
      const voltage = payload.dc_voltage ?? payload.panel_voltage;
      const numericVoltage = Number(voltage);

      if (!Number.isFinite(numericVoltage)) {
        setStatus('waiting for Firebase', 'text-warning');
        return;
      }

      voltageEl.textContent = String(voltage);
      updateBatteryStatus(numericVoltage);
      setStatus(solar.live ? 'live' : 'cached', solar.live ? 'text-success' : 'text-warning');
    } catch (error) {
      setStatus('connection error', 'text-danger');
      console.error('Battery Firebase update failed:', error);
    }
  }

  refreshVoltage();
  window.setInterval(refreshVoltage, 5000);
})();
