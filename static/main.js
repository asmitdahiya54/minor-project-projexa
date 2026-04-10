const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const csrfToken = () => document.querySelector('meta[name="csrf-token"]')?.content || '';
const escapeHtml = (value = '') =>
  String(value).replace(/[&<>"']/g, (char) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }[char]));

function initTheme() {
  const toggle = $('#themeToggle');
  const root = document.documentElement;
  const stored = localStorage.getItem('theme') || 'light';
  root.dataset.theme = stored;

  if (toggle) {
    toggle.innerHTML = stored === 'dark'
      ? '<i class="fa-solid fa-sun"></i>'
      : '<i class="fa-solid fa-moon"></i>';

    toggle.addEventListener('click', () => {
      const next = root.dataset.theme === 'dark' ? 'light' : 'dark';
      root.dataset.theme = next;
      localStorage.setItem('theme', next);
      toggle.innerHTML = next === 'dark'
        ? '<i class="fa-solid fa-sun"></i>'
        : '<i class="fa-solid fa-moon"></i>';
    });
  }
}

function initSidebar() {
  const sidebar = $('#sidebar');
  const trigger = $('#menuToggle');
  if (sidebar && trigger) {
    trigger.addEventListener('click', () => sidebar.classList.toggle('is-open'));
    document.addEventListener('click', (event) => {
      if (
        window.innerWidth <= 900 &&
        sidebar.classList.contains('is-open') &&
        !sidebar.contains(event.target) &&
        !trigger.contains(event.target)
      ) {
        sidebar.classList.remove('is-open');
      }
    });
  }
}

function showToast(message, isError = false) {
  const stack =
    document.querySelector('.flash-stack') ||
    document.body.appendChild(
      Object.assign(document.createElement('section'), { className: 'flash-stack' })
    );

  const item = document.createElement('div');
  item.className = `flash flash--${isError ? 'error' : 'success'}`;
  item.textContent = message;
  stack.prepend(item);
  setTimeout(() => item.remove(), 3500);
}

function initAjaxForms() {
  $$('.js-ajax-form').forEach((form) => {
    form.addEventListener('submit', async (event) => {
      event.preventDefault();

      const submitter = form.querySelector('[type="submit"]');
      const formData = new FormData(form);
      submitter?.setAttribute('disabled', 'disabled');

      try {
        const response = await fetch(form.action || window.location.href, {
          method: form.method || 'POST',
          headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': csrfToken(),
            Accept: 'application/json',
          },
          body: formData,
        });

        const payload = await response.json();
        showToast(payload.message, !payload.success);

        if (payload.success && payload.redirect && form.dataset.redirectOnSuccess === 'true') {
          window.location.href = payload.redirect;
        }
      } catch (_error) {
        showToast('Something went wrong. Please try again.', true);
      } finally {
        submitter?.removeAttribute('disabled');
      }
    });
  });
}

function initAutocomplete() {
  const input = $('#studentSearchInput');
  const mount = $('#studentAutocomplete');
  if (!input || !mount) return;

  let timer;

  input.addEventListener('input', () => {
    clearTimeout(timer);
    const term = input.value.trim();

    if (term.length < 2) {
      mount.innerHTML = '';
      return;
    }

    timer = setTimeout(async () => {
      const response = await fetch(`/api/students/search?q=${encodeURIComponent(term)}`);
      const data = await response.json();

      if (!data.items?.length) {
        mount.innerHTML = '';
        return;
      }

      mount.innerHTML = `
        <div class="autocomplete-panel__menu">
          ${data.items
            .map(
              (item) => `
              <a href="/students/${item.id}">
                <strong>${escapeHtml(item.name)}</strong>
                <div class="table-sub">${escapeHtml(item.student_id)} &middot; ${escapeHtml(item.department)} &middot; ${escapeHtml(item.year)}</div>
              </a>
            `
            )
            .join('')}
        </div>
      `;
    }, 250);
  });

  document.addEventListener('click', (event) => {
    if (!mount.contains(event.target) && event.target !== input) {
      mount.innerHTML = '';
    }
  });
}

async function fetchChartData(endpoint, filters) {
  const params = new URLSearchParams(filters);
  const response = await fetch(`${endpoint}?${params.toString()}`);
  return response.json();
}

function renderChart(target, config, cache) {
  if (!target) return;

  const existing = cache[target.id];
  if (existing) existing.destroy();

  cache[target.id] = new Chart(target, config);
}

function initCharts() {
  const filterForm = $('#chartFilters');
  if (!filterForm || typeof Chart === 'undefined') return;

  const cache = {};

  const load = async () => {
    const filters = Object.fromEntries(new FormData(filterForm).entries());
    const [attendance, results, feedback] = await Promise.all([
      fetchChartData('/api/charts/attendance', filters),
      fetchChartData('/api/charts/results', filters),
      fetchChartData('/api/charts/feedback', filters),
    ]);

    const common = {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 1000, easing: 'easeOutQuart' },
    };

    renderChart($('#attendanceChart'), {
      type: 'bar',
      data: {
        labels: attendance.attendance_by_student.map((row) => row.name),
        datasets: [{
          label: 'Attendance %',
          data: attendance.attendance_by_student.map((row) => row.attendance_rate),
          backgroundColor: '#155eef',
          borderRadius: 999,
          maxBarThickness: 28,
        }],
      },
      options: { ...common, scales: { y: { beginAtZero: true, max: 100 } } },
    }, cache);

    renderChart($('#attendanceTrendChart'), {
      type: 'line',
      data: {
        labels: attendance.attendance_trend.map((row) => row.date),
        datasets: [{
          label: 'Present count',
          data: attendance.attendance_trend.map((row) => row.present_count),
          borderColor: '#0f9f76',
          backgroundColor: 'rgba(15,159,118,0.16)',
          fill: true,
          tension: 0.35,
        }],
      },
      options: common,
    }, cache);

    renderChart($('#resultsChart'), {
      type: 'bar',
      data: {
        labels: results.subject_average.map((row) => row.subject),
        datasets: [{
          label: 'Average %',
          data: results.subject_average.map((row) => row.average_score),
          backgroundColor: '#7a5af8',
          borderRadius: 999,
          maxBarThickness: 28,
        }],
      },
      options: { ...common, scales: { y: { beginAtZero: true, max: 100 } } },
    }, cache);

    renderChart($('#gradeChart'), {
      type: 'doughnut',
      data: {
        labels: results.grade_distribution.map((row) => row.grade),
        datasets: [{
          data: results.grade_distribution.map((row) => row.total),
          backgroundColor: ['#12b76a', '#155eef', '#7a5af8', '#f79009', '#f04438', '#ef6820', '#b42318'],
        }],
      },
      options: common,
    }, cache);

    renderChart($('#feedbackChart'), {
      type: 'polarArea',
      data: {
        labels: feedback.rating_distribution.map((row) => `${row.rating} stars`),
        datasets: [{
          data: feedback.rating_distribution.map((row) => row.total),
          backgroundColor: ['#155eef', '#0ba5ec', '#12b76a', '#f79009', '#f04438'],
        }],
      },
      options: common,
    }, cache);

    renderChart($('#deptChart'), {
      type: 'pie',
      data: {
        labels: feedback.department_split.map((row) => row.department),
        datasets: [{
          data: feedback.department_split.map((row) => row.total),
          backgroundColor: ['#155eef', '#7a5af8', '#12b76a', '#f79009', '#f04438', '#0ba5ec'],
        }],
      },
      options: common,
    }, cache);
  };

  filterForm.addEventListener('submit', (event) => {
    event.preventDefault();
    load();
  });

  load();
}

function getStoredNotifications() {
  try {
    return JSON.parse(localStorage.getItem('app_notifications') || '[]');
  } catch {
    return [];
  }
}

function setStoredNotifications(items) {
  localStorage.setItem('app_notifications', JSON.stringify(items));
}

function updateNotificationUI() {
  const items = getStoredNotifications();
  const countEl = $('#notificationCount');
  const listEl = $('#notificationList');

  if (countEl) {
    countEl.textContent = items.length;
    countEl.classList.toggle('is-visible', items.length > 0);
  }

  if (listEl) {
    listEl.innerHTML = items.length
      ? items.map((item) => `
          <article class="notification-item">
            <strong>${escapeHtml(item.title)}</strong>
            <p>${escapeHtml(item.message)}</p>
          </article>
        `).join('')
      : '<p class="empty">No notifications yet.</p>';
  }
}

function showToastNotification(item) {
  const container = $('#toastContainer');
  if (!container) return;

  const toast = document.createElement('article');
  toast.className = `toast toast--${item.type || 'info'}`;
  toast.innerHTML = `
    <div class="toast__icon">
      <i class="fa-solid ${item.type === 'warning' ? 'fa-triangle-exclamation' : 'fa-circle-info'}"></i>
    </div>
    <div>
      <strong>${escapeHtml(item.title)}</strong>
      <p>${escapeHtml(item.message)}</p>
    </div>
  `;

  container.appendChild(toast);

  setTimeout(() => {
    toast.classList.add('is-hiding');
    setTimeout(() => toast.remove(), 350);
  }, 3500);
}

function initNotifications() {
  const serverDataEl = $('#serverNotifications');
  const toggle = $('#notificationToggle');
  const panel = $('#notificationPanel');
  const clearBtn = $('#clearNotifications');

  let stored = getStoredNotifications();

  if (serverDataEl) {
    try {
      const incoming = JSON.parse(serverDataEl.textContent || '[]');
      incoming.forEach((item) => {
        const exists = stored.some((old) => old.title === item.title && old.message === item.message);
        if (!exists) {
          stored.unshift(item);
          showToastNotification(item);
        }
      });
      stored = stored.slice(0, 20);
      setStoredNotifications(stored);
    } catch {}
  }

  updateNotificationUI();

  if (toggle && panel) {
    toggle.addEventListener('click', () => {
      panel.classList.toggle('is-open');
    });

    document.addEventListener('click', (event) => {
      if (!panel.contains(event.target) && !toggle.contains(event.target)) {
        panel.classList.remove('is-open');
      }
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener('click', () => {
      setStoredNotifications([]);
      updateNotificationUI();
    });
  }
}

document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initSidebar();
  initAjaxForms();
  initAutocomplete();
  initCharts();
  initNotifications();
});
