/**
 * IP Aqua Tech - Firebase-to-web live readings.
 * Django reads Firebase with the Admin SDK; the browser polls Django so the
 * service-account credential never leaves the server.
 */
(function () {
  'use strict';

  const snapshotEl = document.getElementById('liveSnapshot');
  const badgeEl = document.getElementById('liveBadge');
  const modeEl = document.getElementById('liveModeLabel');
  const phEl = document.getElementById('livePh');
  const tdsEl = document.getElementById('liveTds');
  const turbidityEl = document.getElementById('liveTurbidity');
  const flowRateEl = document.getElementById('liveFlowRate');
  const waterLevelEl = document.getElementById('liveWaterLevel');
  const pumpStatusEl = document.getElementById('livePumpStatus');
  const batteryPercentEl = document.getElementById('liveBatteryPercent');
  const batteryVoltageEl = document.getElementById('liveBatteryVoltage');
  const systemStatusEl = document.getElementById('liveSystemStatus');
  const warningLevelEl = document.getElementById('liveWarningLevel');
  const waterAlertEl = document.getElementById('liveWaterAlert');
  const metaEl = document.getElementById('liveMeta');
  if (!snapshotEl) return;

  // Kept in the template as a fallback for old cached assets.
  snapshotEl.style.display = 'none';

  function setBadge(text, cls) {
    if (!badgeEl) return;
    badgeEl.textContent = text;
    badgeEl.className = 'badge ms-2 ' + (cls || 'bg-success');
  }

  function showNumber(element, value, decimals) {
    if (!element) return;
    const number = Number(value);
    element.textContent = Number.isFinite(number) ? number.toFixed(decimals) : '—';
  }

  function render(data) {
    const reading = data.readings && data.readings.water_quality;
    const payload = reading && reading.payload ? reading.payload : {};
    const pumpReading = data.readings && data.readings.pump;
    const pumpPayload = pumpReading && pumpReading.payload ? pumpReading.payload : {};
    const batteryReading = data.readings && data.readings.battery;
    const batteryPayload = batteryReading && batteryReading.payload ? batteryReading.payload : {};
    showNumber(phEl, payload.ph, 2);
    showNumber(tdsEl, payload.tds, 0);
    showNumber(turbidityEl, payload.turbidity, 2);
    showNumber(flowRateEl, payload.flow_rate, 2);

    if (waterLevelEl) {
      waterLevelEl.textContent = payload.water_level_status
        || payload.water_level
        || pumpPayload.water_level_status
        || '—';
    }
    if (pumpStatusEl) {
      const pumpStatus = pumpPayload.pump_status
        || (payload.pump_on === true ? 'ON' : payload.pump_on === false ? 'OFF' : '—');
      pumpStatusEl.textContent = pumpStatus;
      pumpStatusEl.classList.toggle('text-success', pumpStatus === 'ON');
      pumpStatusEl.classList.toggle('text-secondary', pumpStatus === 'OFF');
    }
    if (batteryPercentEl) {
      const percent = Number(batteryPayload.percentage);
      batteryPercentEl.textContent = Number.isFinite(percent) ? percent.toFixed(0) + '%' : '--';
    }
    if (batteryVoltageEl) {
      const voltage = Number(batteryPayload.voltage);
      batteryVoltageEl.textContent = Number.isFinite(voltage) ? voltage.toFixed(2) + ' V' : '-- V';
    }
    if (systemStatusEl) {
      const statuses = (data.devices || []).map(function (device) { return device.status; });
      const status = statuses.includes('ERROR')
        ? 'ERROR'
        : statuses.includes('ONLINE')
          ? 'ONLINE'
          : statuses.length
            ? 'OFFLINE'
            : 'WAITING';
      systemStatusEl.textContent = status;
      systemStatusEl.classList.toggle('text-success', status === 'ONLINE');
      systemStatusEl.classList.toggle('text-danger', status === 'ERROR');
      systemStatusEl.classList.toggle('text-secondary', status === 'OFFLINE' || status === 'WAITING');
    }
    if (warningLevelEl) {
      const warning = payload.warning_level || 'WAITING';
      warningLevelEl.textContent = 'Water: ' + warning;
      warningLevelEl.classList.toggle('text-success', warning === 'NORMAL');
      warningLevelEl.classList.toggle('text-danger', warning === 'DANGER');
      warningLevelEl.classList.toggle('text-warning', warning === 'FIRST' || warning === 'MIDDLE');
    }

    if (waterAlertEl) {
      const dirty = payload.water_dirty === true || pumpPayload.water_dirty === true;
      const levelFault = payload.level_sensor_fault === true
        || pumpPayload.level_sensor_fault === true;
      waterAlertEl.classList.toggle('d-none', !dirty && !levelFault);
      waterAlertEl.textContent = levelFault
        ? 'Level sensor fault: pump stopped for safety; buzzer is active.'
        : dirty
          ? 'Dirty water detected: buzzer is active.'
          : '';
    }

    if (!metaEl) return;
    if (!reading) {
      metaEl.textContent = data.firebase_error
        ? 'Firebase unavailable; no cached reading yet.'
        : 'Waiting for the first ESP32 reading…';
      return;
    }

    const timestamp = payload.timestamp || reading.received_at;
    const date = timestamp ? new Date(timestamp) : null;
    const when = date && !Number.isNaN(date.getTime())
      ? date.toLocaleString()
      : 'time unavailable';
    const device = payload.device_id || reading.device || 'unknown device';
    metaEl.textContent = device + ' • ' + when;
  }

  async function pollLatest() {
    try {
      const res = await fetch('/iot/api/latest/', {
        cache: 'no-store',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      });
      if (!res.ok) throw new Error('Firebase-to-web request failed');

      const data = await res.json();
      render(data);
      const waterReading = data.readings && data.readings.water_quality;
      if (data.firebase_error || (waterReading && !waterReading.live)) {
        setBadge('Cached', 'bg-warning');
      } else if (waterReading && waterReading.live) {
        setBadge('Live', 'bg-success');
      } else {
        setBadge('Waiting', 'bg-secondary');
      }
    } catch (err) {
      setBadge('Error', 'bg-danger');
      if (metaEl) metaEl.textContent = 'Could not load live sensor readings.';
      console.error(err);
    }
  }

  if (modeEl) modeEl.textContent = 'Firebase → Web';
  pollLatest();
  window.setInterval(pollLatest, 5000);
})();
