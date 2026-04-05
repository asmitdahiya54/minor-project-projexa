const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const csrfToken = () => document.querySelector('meta[name="csrf-token"]')?.content || '';

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
            'Accept': 'application/json',
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
                <strong>${item.name}</strong>
                <div class="table-sub">${item.student_id} • ${item.department} • ${item.year}</div>
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

    const attendance = await fetchChartData('/api/charts/attendance', filters);
    const results = await fetchChartData('/api/charts/results', filters);
    const feedback = await fetchChartData('/api/charts/feedback', filters);

    const common = {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 1000, easing: 'easeOutQuart' },
    };

    renderChart(
      $('#attendanceChart'),
      {
        type: 'bar',
        data: {
          labels: attendance.attendance_by_student.map((row) => row.name),
          datasets: [
            {
              label: 'Attendance %',
              data: attendance.attendance_by_student.map((row) => row.attendance_rate),
              backgroundColor: '#2563eb',
              borderRadius: 10,
            },
          ],
        },
        options: { ...common, scales: { y: { beginAtZero: true, max: 100 } } },
      },
      cache
    );

    renderChart(
      $('#attendanceTrendChart'),
      {
        type: 'line',
        data: {
          labels: attendance.attendance_trend.map((row) => row.date),
          datasets: [
            {
              label: 'Present count',
              data: attendance.attendance_trend.map((row) => row.present_count),
              borderColor: '#059669',
              backgroundColor: 'rgba(5,150,105,0.15)',
              fill: true,
              tension: 0.35,
            },
          ],
        },
        options: common,
      },
      cache
    );

    renderChart(
      $('#resultsChart'),
      {
        type: 'bar',
        data: {
          labels: results.subject_average.map((row) => row.subject),
          datasets: [
            {
              label: 'Average %',
              data: results.subject_average.map((row) => row.average_score),
              backgroundColor: '#7c3aed',
              borderRadius: 10,
            },
          ],
        },
        options: { ...common, scales: { y: { beginAtZero: true, max: 100 } } },
      },
      cache
    );

    renderChart(
      $('#gradeChart'),
      {
        type: 'doughnut',
        data: {
          labels: results.grade_distribution.map((row) => row.grade),
          datasets: [
            {
              data: results.grade_distribution.map((row) => row.total),
              backgroundColor: ['#14b8a6', '#3b82f6', '#6366f1', '#f59e0b', '#f97316', '#ef4444', '#dc2626'],
            },
          ],
        },
        options: common,
      },
      cache
    );

    renderChart(
      $('#feedbackChart'),
      {
        type: 'polarArea',
        data: {
          labels: feedback.rating_distribution.map((row) => `${row.rating} stars`),
          datasets: [
            {
              data: feedback.rating_distribution.map((row) => row.total),
              backgroundColor: ['#2563eb', '#0ea5e9', '#14b8a6', '#f59e0b', '#ef4444'],
            },
          ],
        },
        options: common,
      },
      cache
    );

    renderChart(
      $('#deptChart'),
      {
        type: 'pie',
        data: {
          labels: feedback.department_split.map((row) => row.department),
          datasets: [
            {
              data: feedback.department_split.map((row) => row.total),
              backgroundColor: ['#2563eb', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444', '#14b8a6'],
            },
          ],
        },
        options: common,
      },
      cache
    );
  };

  filterForm.addEventListener('submit', (event) => {
    event.preventDefault();
    load();
  });

  load();
}

function initAutoDismissNotices() {
  document.querySelectorAll('.auto-dismiss-stack .notice').forEach((notice, index) => {
    setTimeout(() => {
      notice.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
      notice.style.opacity = '0';
      notice.style.transform = 'translateY(-8px)';
      setTimeout(() => notice.remove(), 400);
    }, 4000 + index * 500);
  });
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
            <strong>${item.title}</strong>
            <p>${item.message}</p>
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
      <strong>${item.title}</strong>
      <p>${item.message}</p>
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
