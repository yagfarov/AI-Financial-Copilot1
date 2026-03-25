/**
 * charts.js -- Chart.js 4.x visualizations
 * AI Financial Copilot (B2B)
 *
 * Charts: Doughnut (categories), Bar+Line (monthly), Horizontal Bar (revenue by channel)
 * Theme-aware: dark / light via data-theme attribute on <html>
 */

/* ================================================================
   GLOBAL STATE
   ================================================================ */

let categoryChart = null;
let monthlyChart = null;
let revenueChart = null;

const PALETTE = [
  '#6366f1', // indigo
  '#10b981', // emerald
  '#f59e0b', // amber
  '#f43f5e', // rose
  '#0ea5e9', // sky
  '#8b5cf6', // violet
  '#f97316', // orange
  '#14b8a6', // teal
  '#ec4899', // pink
];

const FONT_STACK = 'Inter, -apple-system, BlinkMacSystemFont, "SF Pro Display", sans-serif';

/* ================================================================
   HELPERS
   ================================================================ */

function getThemeColors() {
  const theme = document.documentElement.getAttribute('data-theme');
  const isDark = theme === 'dark';
  return {
    grid: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)',
    text: isDark ? 'rgba(255,255,255,0.5)' : 'rgba(0,0,0,0.5)',
    tooltipBg: isDark ? 'rgba(20,20,35,0.95)' : 'rgba(255,255,255,0.96)',
    tooltipBorder: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)',
    tooltipTitle: isDark ? '#ffffff' : '#1D1D1F',
    tooltipBody: isDark ? 'rgba(255,255,255,0.65)' : 'rgba(0,0,0,0.55)',
    isDark,
  };
}

function formatMoneyCompact(n) {
  if (n === null || n === undefined) return '';
  const abs = Math.abs(n);
  const sign = n < 0 ? '-' : '';
  if (abs >= 1_000_000) return sign + (abs / 1_000_000).toFixed(1) + 'M \u20BD';
  if (abs >= 1_000) return sign + Math.round(abs / 1_000) + 'k \u20BD';
  return sign + Math.round(abs) + ' \u20BD';
}

function formatMoneyFull(n) {
  if (n === null || n === undefined) return '';
  return Math.round(n).toLocaleString('ru-RU') + ' \u20BD';
}

function hexToRgba(hex, alpha) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

function getNextMonthLabel(label) {
  try {
    const parts = label.split('-');
    if (parts.length === 2 && parts[0].length === 4) {
      let year = parseInt(parts[0], 10);
      let month = parseInt(parts[1], 10) + 1;
      if (month > 12) { month = 1; year += 1; }
      return `${year}-${String(month).padStart(2, '0')}`;
    }
  } catch (_) { /* fall through */ }
  return 'Прогноз';
}

/** Shared tooltip config */
function tooltipDefaults() {
  const t = getThemeColors();
  return {
    backgroundColor: t.tooltipBg,
    borderColor: t.tooltipBorder,
    borderWidth: 1,
    titleColor: t.tooltipTitle,
    bodyColor: t.tooltipBody,
    padding: 12,
    cornerRadius: 10,
    titleFont: { size: 13, weight: '600', family: FONT_STACK },
    bodyFont: { size: 12, family: FONT_STACK },
    displayColors: true,
    boxPadding: 4,
  };
}

/* ================================================================
   MAIN ENTRY POINT
   ================================================================ */

function updateCharts(data) {
  if (!data) return;
  updateCategoryChart(data.by_category || {});
  updateMonthlyChart(
    data.monthly_income || {},
    data.monthly_expenses || {},
    data.forecast || null,
  );
  updateRevenueChart(data.revenue_by_channel || {});
}

/* ================================================================
   DOUGHNUT -- expense categories
   ================================================================ */

function updateCategoryChart(byCategory) {
  const canvas = document.getElementById('categoryChart');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  const t = getThemeColors();

  const entries = Object.entries(byCategory).sort((a, b) => b[1] - a[1]);
  if (entries.length === 0) {
    if (categoryChart) { categoryChart.destroy(); categoryChart = null; }
    return;
  }

  const labels = entries.map(([cat]) => cat);
  const values = entries.map(([, v]) => v);
  const colors = labels.map((_, i) => PALETTE[i % PALETTE.length]);
  const total = values.reduce((s, v) => s + v, 0);

  // Center text plugin
  const centerTextPlugin = {
    id: 'doughnutCenterText',
    afterDraw(chart) {
      const { ctx: c, chartArea } = chart;
      if (!chartArea) return;

      const cx = (chartArea.left + chartArea.right) / 2;
      const cy = (chartArea.top + chartArea.bottom) / 2;
      const tc = getThemeColors();

      c.save();

      c.font = `bold 17px ${FONT_STACK}`;
      c.fillStyle = tc.isDark ? '#ffffff' : '#1D1D1F';
      c.textAlign = 'center';
      c.textBaseline = 'middle';
      c.fillText(formatMoneyCompact(total), cx, cy - 9);

      c.font = `11px ${FONT_STACK}`;
      c.fillStyle = tc.text;
      c.fillText('расходы', cx, cy + 10);

      c.restore();
    },
  };

  if (categoryChart) { categoryChart.destroy(); categoryChart = null; }

  categoryChart = new Chart(ctx, {
    type: 'doughnut',
    plugins: [centerTextPlugin],
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: colors,
        hoverBackgroundColor: colors.map(c => hexToRgba(c, 0.78)),
        borderWidth: 2,
        borderColor: t.isDark ? 'rgba(255,255,255,0.06)' : 'rgba(255,255,255,0.9)',
        hoverBorderColor: t.isDark ? 'rgba(255,255,255,0.15)' : '#ffffff',
        borderRadius: 4,
        hoverOffset: 6,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '80%',
      layout: { padding: 8 },
      plugins: {
        legend: {
          position: 'right',
          align: 'center',
          labels: {
            color: t.text,
            font: { size: 12, family: FONT_STACK },
            boxWidth: 10,
            boxHeight: 10,
            borderRadius: 3,
            padding: 10,
            generateLabels(chart) {
              return chart.data.labels.map((label, i) => ({
                text: label.length > 15 ? label.slice(0, 14) + '\u2026' : label,
                fillStyle: chart.data.datasets[0].backgroundColor[i],
                strokeStyle: 'transparent',
                lineWidth: 0,
                hidden: false,
                index: i,
              }));
            },
          },
        },
        tooltip: {
          ...tooltipDefaults(),
          callbacks: {
            title([item]) { return item.label; },
            label(item) {
              const pct = total > 0 ? ((item.raw / total) * 100).toFixed(1) : 0;
              return `  ${formatMoneyFull(item.raw)}  (${pct}%)`;
            },
          },
        },
      },
    },
  });
}

/* ================================================================
   BAR + LINE -- monthly income vs expenses + profit line + forecast
   ================================================================ */

function updateMonthlyChart(monthlyIncome, monthlyExpenses, forecast) {
  const canvas = document.getElementById('monthlyChart');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  const t = getThemeColors();

  // Merge month keys from both income and expenses
  const allMonthsSet = new Set([
    ...Object.keys(monthlyIncome),
    ...Object.keys(monthlyExpenses),
  ]);
  const monthKeys = Array.from(allMonthsSet).sort();

  if (monthKeys.length === 0) {
    if (monthlyChart) { monthlyChart.destroy(); monthlyChart = null; }
    return;
  }

  const incomeValues = monthKeys.map(k => monthlyIncome[k] || 0);
  const expenseValues = monthKeys.map(k => monthlyExpenses[k] || 0);
  const profitValues = monthKeys.map((_, i) => incomeValues[i] - expenseValues[i]);

  let allLabels = [...monthKeys];
  let incomeData = [...incomeValues];
  let expenseData = [...expenseValues];
  let profitData = [...profitValues];

  // Forecast bar for next month
  let forecastData = new Array(monthKeys.length).fill(null);
  const hasForecast = forecast && forecast.predicted_monthly;

  if (hasForecast) {
    const nextLabel = getNextMonthLabel(monthKeys[monthKeys.length - 1]);
    allLabels.push(nextLabel);
    incomeData.push(null);
    expenseData.push(null);
    profitData.push(null);
    forecastData.push(forecast.predicted_monthly);
  }

  // Gradients
  const h = canvas.offsetHeight || 300;

  let incomeGradient;
  try {
    incomeGradient = ctx.createLinearGradient(0, 0, 0, h);
    incomeGradient.addColorStop(0, '#6366f1');
    incomeGradient.addColorStop(1, '#3b82f6');
  } catch (_) {
    incomeGradient = '#6366f1';
  }

  let expenseGradient;
  try {
    expenseGradient = ctx.createLinearGradient(0, 0, 0, h);
    expenseGradient.addColorStop(0, '#f43f5e');
    expenseGradient.addColorStop(1, '#ef4444');
  } catch (_) {
    expenseGradient = '#f43f5e';
  }

  const datasets = [
    {
      label: 'Доход',
      data: incomeData,
      backgroundColor: incomeGradient,
      hoverBackgroundColor: '#818cf8',
      borderRadius: 6,
      borderSkipped: false,
      order: 2,
      yAxisID: 'y',
      barPercentage: 0.7,
      categoryPercentage: 0.65,
    },
    {
      label: 'Расходы',
      data: expenseData,
      backgroundColor: expenseGradient,
      hoverBackgroundColor: '#fb7185',
      borderRadius: 6,
      borderSkipped: false,
      order: 2,
      yAxisID: 'y',
      barPercentage: 0.7,
      categoryPercentage: 0.65,
    },
  ];

  // Forecast bar
  if (hasForecast) {
    datasets.push({
      label: 'Прогноз расходов',
      data: forecastData,
      backgroundColor: hexToRgba('#8b5cf6', 0.35),
      hoverBackgroundColor: hexToRgba('#8b5cf6', 0.55),
      borderColor: '#8b5cf6',
      borderWidth: 2,
      borderDash: [5, 4],
      borderRadius: 6,
      borderSkipped: false,
      order: 2,
      yAxisID: 'y',
      barPercentage: 0.7,
      categoryPercentage: 0.65,
    });
  }

  // Profit line on secondary axis
  datasets.push({
    label: 'Прибыль',
    data: profitData,
    type: 'line',
    borderColor: '#10b981',
    borderWidth: 2.5,
    backgroundColor: 'transparent',
    pointBackgroundColor: '#10b981',
    pointBorderColor: t.isDark ? '#1a1a2e' : '#ffffff',
    pointBorderWidth: 2,
    pointRadius: 4,
    pointHoverRadius: 6,
    tension: 0.35,
    fill: false,
    order: 1,
    yAxisID: 'y2',
    spanGaps: true,
  });

  if (monthlyChart) { monthlyChart.destroy(); monthlyChart = null; }

  monthlyChart = new Chart(ctx, {
    type: 'bar',
    data: { labels: allLabels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          position: 'top',
          align: 'end',
          labels: {
            color: t.text,
            font: { size: 12, family: FONT_STACK },
            boxWidth: 14,
            boxHeight: 10,
            borderRadius: 3,
            padding: 14,
            usePointStyle: false,
          },
        },
        tooltip: {
          ...tooltipDefaults(),
          callbacks: {
            label(item) {
              if (item.raw === null) return null;
              return `  ${item.dataset.label}: ${formatMoneyFull(item.raw)}`;
            },
          },
        },
      },
      scales: {
        x: {
          grid: { color: t.grid, drawBorder: false },
          border: { display: false },
          ticks: {
            color: t.text,
            font: { size: 11, family: FONT_STACK },
            maxRotation: 0,
          },
        },
        y: {
          position: 'left',
          grid: { color: t.grid, drawBorder: false },
          border: { display: false },
          ticks: {
            color: t.text,
            font: { size: 11, family: FONT_STACK },
            callback: (v) => formatMoneyCompact(v),
          },
          beginAtZero: true,
        },
        y2: {
          position: 'right',
          grid: { drawOnChartArea: false, drawBorder: false },
          border: { display: false },
          ticks: {
            color: '#10b981',
            font: { size: 11, family: FONT_STACK },
            callback: (v) => formatMoneyCompact(v),
          },
        },
      },
    },
  });
}

/* ================================================================
   HORIZONTAL BAR -- revenue by channel
   ================================================================ */

function updateRevenueChart(revenueByChannel) {
  const canvas = document.getElementById('revenueChart');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  const t = getThemeColors();

  const entries = Object.entries(revenueByChannel).sort((a, b) => b[1] - a[1]);
  if (entries.length === 0) {
    if (revenueChart) { revenueChart.destroy(); revenueChart = null; }
    return;
  }

  const labels = entries.map(([ch]) => ch);
  const values = entries.map(([, v]) => v);

  // Per-bar gradient colors from palette
  const barColors = labels.map((_, i) => {
    const base = PALETTE[i % PALETTE.length];
    const faded = hexToRgba(base, 0.7);
    return { base, faded };
  });

  // Create gradient per bar
  const w = canvas.offsetWidth || 400;
  const backgrounds = barColors.map(({ base, faded }) => {
    try {
      const grad = ctx.createLinearGradient(0, 0, w, 0);
      grad.addColorStop(0, faded);
      grad.addColorStop(1, base);
      return grad;
    } catch (_) {
      return base;
    }
  });

  if (revenueChart) { revenueChart.destroy(); revenueChart = null; }

  revenueChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Выручка',
        data: values,
        backgroundColor: backgrounds,
        hoverBackgroundColor: barColors.map(({ base }) => hexToRgba(base, 0.9)),
        borderRadius: 6,
        borderSkipped: false,
        barPercentage: 0.65,
        categoryPercentage: 0.75,
      }],
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          ...tooltipDefaults(),
          callbacks: {
            label(item) {
              return `  ${formatMoneyFull(item.raw)}`;
            },
          },
        },
      },
      scales: {
        x: {
          grid: { color: t.grid, drawBorder: false },
          border: { display: false },
          ticks: {
            color: t.text,
            font: { size: 11, family: FONT_STACK },
            callback: (v) => formatMoneyCompact(v),
          },
          beginAtZero: true,
        },
        y: {
          grid: { display: false },
          border: { display: false },
          ticks: {
            color: t.text,
            font: { size: 12, weight: '500', family: FONT_STACK },
            padding: 8,
          },
        },
      },
    },
  });
}
