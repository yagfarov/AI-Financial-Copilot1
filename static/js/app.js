/**
 * app.js — Alpine.js компонент financialApp
 * AI Financial Copilot — B2B SPA
 */

document.addEventListener('alpine:init', () => {
  Alpine.data('financialApp', () => ({
    // ── State ──────────────────────────────────────────────
    view: 'dashboard',
    loading: false,
    loadingText: 'Загрузка...',
    data: null,
    insights: [],
    insightsLoading: false,
    activeDemo: null,

    sessionId: null,
    availableMonths: [],
    selectedMonth: null,

    chatMessages: [],
    chatInput: '',
    chatLoading: false,

    agentInfo: null,

    darkMode: true,

    // ── Init ───────────────────────────────────────────────
    async init() {
      const saved = localStorage.getItem('theme');
      this.darkMode = saved ? saved === 'dark' : true;
      this._applyTheme();
      await this.loadInitialData();
    },

    // ── Theme ─────────────────────────────────────────────
    toggleTheme() {
      this.darkMode = !this.darkMode;
      localStorage.setItem('theme', this.darkMode ? 'dark' : 'light');
      this._applyTheme();
    },

    _applyTheme() {
      document.documentElement.setAttribute('data-theme', this.darkMode ? 'dark' : 'light');
    },

    // ── Data loading ──────────────────────────────────────
    async loadInitialData() {
      this.loading = true;
      this.loadingText = 'Загрузка данных...';
      try {
        const resp = await fetch('/api/init');
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const result = await resp.json();
        if (!result.empty) {
          this._applyResponse(result);
        }
      } catch (e) {
        console.error('Init error:', e);
      } finally {
        this.loading = false;
      }
    },

    _applyResponse(result) {
      if (result.session_id) this.sessionId = result.session_id;
      if (result.months && result.months.length > 0) {
        this.availableMonths = result.months;
        const preferred = result.default_month || this.availableMonths[0];
        if (!this.selectedMonth || !this.availableMonths.includes(this.selectedMonth)) {
          this.selectedMonth = preferred;
        }
      }

      const { session_id, months, ...analyticsData } = result;
      this.data = analyticsData;

      this.$nextTick(() => {
        if (typeof updateCharts === 'function') updateCharts(this.data);
      });
    },

    async loadDemo(type) {
      this.loading = true;
      this.loadingText = type === 'good'
        ? 'Загружаем стабильного пользователя...'
        : 'Загружаем проблемный профиль...';
      this.activeDemo = type;
      this.insights = [];
      this.sessionId = null;
      this.availableMonths = [];
      this.selectedMonth = null;

      try {
        const resp = await fetch(`/api/demo/${type}`);
        if (!resp.ok) {
          const err = await resp.json().catch(() => ({}));
          throw new Error(err.detail || `HTTP ${resp.status}`);
        }
        this._applyResponse(await resp.json());
      } catch (e) {
        console.error('loadDemo error:', e);
        this._showError(`Ошибка загрузки демо: ${e.message}`);
      } finally {
        this.loading = false;
      }
    },

    async uploadCSV(event) {
      const files = event.target.files;
      if (!files || files.length === 0) return;

      this.loading = true;
      this.loadingText = files.length === 1
        ? `Обрабатываем ${files[0].name}...`
        : `Объединяем ${files.length} файлов...`;
      this.activeDemo = null;
      this.insights = [];

      const prevSessionId = this.sessionId;
      this.sessionId = null;
      this.availableMonths = [];
      this.selectedMonth = null;

      const formData = new FormData();
      for (const file of files) {
        formData.append('files', file);
      }
      if (prevSessionId) {
        formData.append('session_id', prevSessionId);
      }

      try {
        const resp = await fetch('/api/upload', { method: 'POST', body: formData });
        if (!resp.ok) {
          const err = await resp.json().catch(() => ({}));
          throw new Error(err.detail || `HTTP ${resp.status}`);
        }
        this._applyResponse(await resp.json());
      } catch (e) {
        console.error('uploadCSV error:', e);
        this._showError(`Ошибка обработки файла: ${e.message}`);
      } finally {
        this.loading = false;
        event.target.value = '';
      }
    },

    async changeMonth(month) {
      if (!this.sessionId || !month || month === this.selectedMonth) return;

      this.loading = true;
      this.loadingText = `Загружаем данные за ${month}...`;
      this.insights = [];
      this.selectedMonth = month;

      try {
        const resp = await fetch(`/api/analytics/${this.sessionId}?month=${month}`);
        if (!resp.ok) {
          const err = await resp.json().catch(() => ({}));
          throw new Error(err.detail || `HTTP ${resp.status}`);
        }
        const result = await resp.json();
        this.data = result;
        this.$nextTick(() => {
          if (typeof updateCharts === 'function') updateCharts(this.data);
        });
      } catch (e) {
        console.error('changeMonth error:', e);
        this._showError(`Ошибка загрузки месяца: ${e.message}`);
      } finally {
        this.loading = false;
      }
    },

    async generateInsights() {
      if (!this.data || this.insightsLoading) return;

      this.insightsLoading = true;

      try {
        const body = {
          analytics: {
            total_income: this.data.total_income,
            total_expenses: this.data.total_expenses,
            profit: this.data.profit,
            profit_margin: this.data.profit_margin,
            burn_rate: this.data.burn_rate,
            runway: this.data.runway,
            by_category: this.data.by_category,
            by_category_pct: this.data.by_category_pct,
            revenue_by_channel: this.data.revenue_by_channel,
            monthly_income: this.data.monthly_income,
            monthly_expenses: this.data.monthly_expenses,
            top_transactions: this.data.top_transactions,
          },
          anomalies: this.data.anomalies || [],
          health: this.data.health_score || {},
          forecast: this.data.forecast || {},
        };

        const resp = await fetch('/api/insights', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });

        if (!resp.ok) {
          const err = await resp.json().catch(() => ({}));
          throw new Error(err.detail || `HTTP ${resp.status}`);
        }

        const result = await resp.json();
        this.insights = result.insights || [];
      } catch (e) {
        console.error('generateInsights error:', e);
        this._showError(`Ошибка генерации инсайтов: ${e.message}`);
      } finally {
        this.insightsLoading = false;
      }
    },

    // ── Chat ──────────────────────────────────────────────
    async sendChat() {
      const msg = this.chatInput.trim();
      if (!msg || this.chatLoading) return;

      this.chatMessages.push({ role: 'user', text: msg, time: this._timeNow() });
      this.chatInput = '';
      this.chatLoading = true;
      this.$nextTick(() => this._scrollChat());

      try {
        const context = this.data ? {
          total_income: this.data.total_income,
          total_expenses: this.data.total_expenses,
          profit: this.data.profit,
          profit_margin: this.data.profit_margin,
          burn_rate: this.data.burn_rate,
          runway: this.data.runway,
          by_category: this.data.by_category,
          revenue_by_channel: this.data.revenue_by_channel,
          health_score: this.data.health_score,
          forecast: this.data.forecast,
          anomalies: this.data.anomalies,
        } : {};

        const resp = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: msg, context }),
        });

        if (!resp.ok) {
          const err = await resp.json().catch(() => ({}));
          throw new Error(err.detail || `HTTP ${resp.status}`);
        }

        const result = await resp.json();
        this.chatMessages.push({ role: 'assistant', text: result.reply || 'Нет ответа', time: this._timeNow() });
      } catch (e) {
        this.chatMessages.push({ role: 'assistant', text: `Ошибка: ${e.message}`, time: this._timeNow() });
      } finally {
        this.chatLoading = false;
        this.$nextTick(() => this._scrollChat());
      }
    },

    handleChatKeydown(event) {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        this.sendChat();
      }
    },

    useSuggestion(text) {
      this.chatInput = text;
      this.$nextTick(() => {
        const ta = document.getElementById('chat-textarea');
        if (ta) ta.focus();
      });
    },

    // ── Agent ─────────────────────────────────────────────
    async loadAgentInfo() {
      if (this.agentInfo) return;
      try {
        const resp = await fetch('/api/agent');
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        this.agentInfo = await resp.json();
      } catch (e) {
        console.error('loadAgentInfo error:', e);
        this.agentInfo = { error: e.message };
      }
    },

    switchView(target) {
      this.view = target;
      if (target === 'agent') {
        this.loadAgentInfo();
      }
      if (target === 'dashboard' || target === 'analytics') {
        this.$nextTick(() => {
          if (this.data && typeof updateCharts === 'function') updateCharts(this.data);
        });
      }
    },

    // ── Upload trigger ────────────────────────────────────
    triggerUpload() {
      const input = document.getElementById('csv-file-input');
      if (input) input.click();
    },

    // ── Format helpers ────────────────────────────────────
    momDelta(field, inverseColors = false) {
      const delta = this.data?.mom_kpi_delta;
      if (!delta || delta[field] === undefined) return null;
      const val = delta[field];
      if (val === 0) return null;
      const isPositive = inverseColors ? val < 0 : val > 0;
      const sign = val > 0 ? '+' : '';
      const arrow = val > 0 ? '\u2191' : '\u2193';
      let text;
      if (field === 'profit_margin') {
        text = `${sign}${parseFloat(val).toFixed(1)}% к пр. мес.`;
      } else {
        text = `${sign}${Math.round(Math.abs(val)).toLocaleString('ru-RU')} \u20BD`;
      }
      return { text: `${arrow} ${text}`, positive: isPositive };
    },

    formatMoney(n) {
      if (n === null || n === undefined) return '\u2014';
      return Math.round(n).toLocaleString('ru-RU') + ' \u20BD';
    },

    formatPercent(n) {
      if (n === null || n === undefined) return '\u2014';
      return parseFloat(n).toFixed(1) + '%';
    },

    getInsightType(type) {
      const map = { warning: 'Внимание', positive: 'Позитив', tip: 'Совет', anomaly: 'Аномалия', trend: 'Тренд' };
      return map[type] || type;
    },

    getInsightIcon(type) {
      const map = { warning: '\u26A0\uFE0F', positive: '\u2705', tip: '\uD83D\uDCA1', anomaly: '\uD83D\uDEA8', trend: '\uD83D\uDCC8' };
      return map[type] || '\uD83D\uDCCC';
    },

    get healthScoreColor() {
      const score = this.data?.health_score?.total ?? 0;
      if (score >= 70) return 'green';
      if (score >= 40) return 'yellow';
      return 'red';
    },

    get healthScoreLabel() {
      const score = this.data?.health_score?.total ?? 0;
      if (score >= 70) return 'Отличное';
      if (score >= 40) return 'Среднее';
      return 'Требует внимания';
    },

    getScoreColor(score) {
      if (score >= 70) return 'green';
      if (score >= 40) return 'yellow';
      return 'red';
    },

    getCategoryIcon(category) {
      const lower = (category || '').toLowerCase();
      const map = {
        'зарплата': '\uD83D\uDC65',
        'реклама': '\uD83D\uDCE2',
        'saas': '\uD83D\uDCBB',
        'sas': '\uD83D\uDCBB',
        'оборудование': '\uD83D\uDD27',
        'логистика': '\uD83D\uDE9B',
        'коммунальные услуги': '\uD83C\uDFE2',
        'коммунальные': '\uD83C\uDFE2',
        'маркетплейсы': '\uD83D\uDED2',
        'соцсети': '\uD83D\uDCF1',
        'аренда': '\uD83C\uDFE2',
        'налоги': '\uD83D\uDCCB',
        'транспорт': '\uD83D\uDE97',
        'еда': '\uD83C\uDF55',
        'продукты': '\uD83D\uDED2',
        'подписки': '\uD83D\uDCF1',
        'развлечения': '\uD83C\uDFAC',
        'здоровье': '\uD83D\uDC8A',
      };
      for (const [key, icon] of Object.entries(map)) {
        if (lower.includes(key)) return icon;
      }
      return '\uD83D\uDCB3';
    },

    get forecastInterval() {
      const f = this.data?.forecast;
      if (!f) return null;
      if (f.confidence_low !== undefined && f.confidence_high !== undefined) {
        return { lower: this.formatMoney(f.confidence_low), upper: this.formatMoney(f.confidence_high) };
      }
      const predicted = f.predicted_monthly;
      if (predicted) {
        return { lower: this.formatMoney(predicted * 0.85), upper: this.formatMoney(predicted * 1.15) };
      }
      return null;
    },

    get topTransactions() {
      const txs = this.data?.top_transactions;
      if (!txs) return [];
      if (Array.isArray(txs)) return txs.slice(0, 10);
      return Object.entries(txs)
        .map(([date, amount]) => ({ date, abs_amount: Math.abs(amount), description: date, category: '' }))
        .sort((a, b) => b.abs_amount - a.abs_amount)
        .slice(0, 10);
    },

    get anomaliesList() {
      return (this.data?.anomalies || []).slice(0, 6);
    },

    get profitColor() {
      const profit = this.data?.profit ?? 0;
      if (profit > 0) return 'green';
      if (profit < 0) return 'red';
      return 'yellow';
    },

    // ── Internal helpers ──────────────────────────────────
    _showError(msg) {
      console.error(msg);
    },

    _timeNow() {
      return new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
    },

    _scrollChat() {
      const el = document.getElementById('chat-messages-container');
      if (el) el.scrollTop = el.scrollHeight;
    },
  }));
});
