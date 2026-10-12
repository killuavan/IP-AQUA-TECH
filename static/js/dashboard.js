/**
 * IP Aqua Tech – Dashboard Chart.js integration
 */
(function () {
  'use strict';

  const COLORS = {
    primary: '#0a4d68',
    secondary: '#088395',
    accent: '#05bfdb',
    light: '#00ffca',
    green: '#198754',
    yellow: '#ffc107',
    red: '#dc3545',
    purple: '#6f42c1',
    orange: '#fd7e14',
  };

  function baseOptions(title) {
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'bottom',
          labels: { usePointStyle: true, padding: 16, font: { size: 11 } },
        },
        title: title
          ? { display: true, text: title, color: COLORS.primary, font: { size: 13, weight: '600' } }
          : { display: false },
        tooltip: {
          backgroundColor: 'rgba(6, 40, 61, 0.9)',
          padding: 10,
          cornerRadius: 8,
        },
      },
      scales: {
        x: {
          grid: { color: 'rgba(10, 77, 104, 0.06)' },
          ticks: { color: '#6c757d', font: { size: 10 }, maxRotation: 45 },
        },
        y: {
          beginAtZero: true,
          grid: { color: 'rgba(10, 77, 104, 0.06)' },
          ticks: { color: '#6c757d', font: { size: 10 } },
        },
      },
    };
  }

  function createLineChart(canvasId, labels, datasets, title) {
    const el = document.getElementById(canvasId);
    if (!el || typeof Chart === 'undefined') return null;
    return new Chart(el, {
      type: 'line',
      data: { labels, datasets },
      options: baseOptions(title),
    });
  }

  function createBarChart(canvasId, labels, datasets, title) {
    const el = document.getElementById(canvasId);
    if (!el || typeof Chart === 'undefined') return null;
    return new Chart(el, {
      type: 'bar',
      data: { labels, datasets },
      options: baseOptions(title),
    });
  }

  function createDoughnutChart(canvasId, labels, data, colors) {
    const el = document.getElementById(canvasId);
    if (!el || typeof Chart === 'undefined') return null;
    return new Chart(el, {
      type: 'doughnut',
      data: {
        labels,
        datasets: [{
          data,
          backgroundColor: colors,
          borderWidth: 0,
          hoverOffset: 6,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '65%',
        plugins: {
          legend: {
            position: 'bottom',
            labels: { usePointStyle: true, padding: 12, font: { size: 11 } },
          },
        },
      },
    });
  }

  async function loadDashboardCharts() {
    const chartDataUrl = document.body.dataset.chartUrl;
    if (!chartDataUrl) return;

    try {
      const requestUrl = new URL(chartDataUrl, window.location.origin);
      const filterForm = document.getElementById('dashboardDateFilter');
      if (filterForm) {
        requestUrl.searchParams.set('from_datetime', filterForm.elements.from_datetime.value);
        requestUrl.searchParams.set('to_datetime', filterForm.elements.to_datetime.value);
      }
      const res = await fetch(requestUrl, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      });
      if (!res.ok) throw new Error('Failed to load chart data');
      const data = await res.json();
      renderWaterQualityHistory(data.water_quality);

      // Water Production
      createBarChart(
        'chartProduction',
        data.production.labels,
        [{
          label: 'Production (L)',
          data: data.production.data,
          backgroundColor: COLORS.accent,
          borderRadius: 6,
          borderSkipped: false,
        }],
        'Daily Water Production'
      );

      // Solar Energy
      createLineChart(
        'chartSolar',
        data.solar.labels,
        [{
          label: 'Energy (kWh)',
          data: data.solar.data,
          borderColor: COLORS.orange,
          backgroundColor: 'rgba(253, 126, 20, 0.15)',
          fill: true,
          tension: 0.35,
          pointRadius: 3,
          pointBackgroundColor: COLORS.orange,
        }],
        'Solar Energy Generation'
      );

      // Battery Level
      createLineChart(
        'chartBattery',
        data.battery.labels,
        [{
          label: 'Battery %',
          data: data.battery.data,
          borderColor: COLORS.green,
          backgroundColor: 'rgba(25, 135, 84, 0.15)',
          fill: true,
          tension: 0.35,
          pointRadius: 3,
          pointBackgroundColor: COLORS.green,
        }],
        'Battery Level'
      );

      // Water Quality multi-line
      createLineChart(
        'chartWaterQuality',
        data.water_quality.labels,
        [
          {
            label: 'pH',
            data: data.water_quality.ph,
            borderColor: COLORS.primary,
            tension: 0.3,
            pointRadius: 2,
          },
          {
            label: 'TDS (ppm)',
            data: data.water_quality.tds,
            borderColor: COLORS.secondary,
            tension: 0.3,
            pointRadius: 2,
            yAxisID: 'y1',
          },
          {
            label: 'Turbidity',
            data: data.water_quality.turbidity,
            borderColor: COLORS.purple,
            tension: 0.3,
            pointRadius: 2,
          },
          {
            label: 'Temp (°C)',
            data: data.water_quality.temperature,
            borderColor: COLORS.red,
            tension: 0.3,
            pointRadius: 2,
          },
        ],
        'Water Quality History'
      );

      // Override dual axis for WQ chart if exists
      const wqChart = Chart.getChart('chartWaterQuality');
      if (wqChart) {
        wqChart.options.scales.y1 = {
          position: 'right',
          beginAtZero: true,
          grid: { drawOnChartArea: false },
          ticks: { color: '#6c757d', font: { size: 10 } },
        };
        wqChart.update();
      }

      // Battery doughnut (current level)
      const pct = data.battery.current || 0;
      createDoughnutChart(
        'chartBatteryDonut',
        ['Charged', 'Remaining'],
        [pct, Math.max(0, 100 - pct)],
        [COLORS.green, '#e0eef2']
      );
    } catch (err) {
      console.error('Dashboard charts error:', err);
    }
  }

  function renderWaterQualityHistory(history) {
    const rowsEl = document.getElementById('dashboardHistoryRows');
    const countEl = document.getElementById('dashboardHistoryCount');
    if (!rowsEl || !countEl) return;

    rowsEl.replaceChildren();
    const records = history.records || [];
    countEl.textContent = records.length < history.count
      ? `Showing ${records.length} of ${history.count} readings`
      : `${history.count} readings`;

    if (!records.length) {
      const row = document.createElement('tr');
      const cell = document.createElement('td');
      cell.colSpan = 6;
      cell.className = 'text-center text-muted py-3';
      cell.textContent = 'No readings in this date-time range.';
      row.appendChild(cell);
      rowsEl.appendChild(row);
      return;
    }

    records.forEach(function (record) {
      const row = document.createElement('tr');
      [
        record.recorded_at,
        Number(record.ph).toFixed(2),
        Number(record.tds).toFixed(2),
        Number(record.turbidity).toFixed(2),
        Number(record.temperature).toFixed(2) + ' °C',
        record.status,
      ].forEach(function (value) {
        const cell = document.createElement('td');
        cell.textContent = value;
        row.appendChild(cell);
      });
      rowsEl.appendChild(row);
    });
  }

  // Sidebar toggle
  function initSidebar() {
    const toggle = document.getElementById('sidebarToggle');
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    if (!toggle || !sidebar) return;

    toggle.addEventListener('click', function () {
      sidebar.classList.toggle('show');
      if (overlay) overlay.classList.toggle('show');
    });
    if (overlay) {
      overlay.addEventListener('click', function () {
        sidebar.classList.remove('show');
        overlay.classList.remove('show');
      });
    }
  }

  // Auto-dismiss alerts
  function initAlerts() {
    document.querySelectorAll('.alert-dismissible').forEach(function (el) {
      setTimeout(function () {
        const bsAlert = bootstrap.Alert.getOrCreateInstance(el);
        if (bsAlert) bsAlert.close();
      }, 5000);
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    initSidebar();
    initAlerts();
    const filterForm = document.getElementById('dashboardDateFilter');
    if (filterForm) {
      filterForm.addEventListener('submit', function (event) {
        const fromValue = filterForm.elements.from_datetime.value;
        const toValue = filterForm.elements.to_datetime.value;
        if (fromValue && toValue && fromValue > toValue) {
          event.preventDefault();
          filterForm.elements.to_datetime.setCustomValidity('End must be after start.');
          filterForm.elements.to_datetime.reportValidity();
          filterForm.elements.to_datetime.addEventListener('input', function clearValidity() {
            filterForm.elements.to_datetime.setCustomValidity('');
            filterForm.elements.to_datetime.removeEventListener('input', clearValidity);
          });
        }
      });
    }
    if (document.getElementById('chartProduction')) {
      loadDashboardCharts();
    }
  });
})();
