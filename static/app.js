/* ================================================================
   SecureHealth Cloud — Client-side JavaScript
   Dark mode, tabs, toasts, modals, quick search, table sorting
   ================================================================ */

(function () {
  'use strict';

  // ── Dark Mode ──────────────────────────────────────────────────
  const ThemeManager = {
    STORAGE_KEY: 'securehealth-theme',

    init() {
      const saved = localStorage.getItem(this.STORAGE_KEY);
      if (saved) {
        document.documentElement.setAttribute('data-theme', saved);
      } else {
        // Detect system preference
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        document.documentElement.setAttribute('data-theme', prefersDark ? 'dark' : 'light');
      }

      // Listen for system changes
      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
        if (!localStorage.getItem(this.STORAGE_KEY)) {
          document.documentElement.setAttribute('data-theme', e.matches ? 'dark' : 'light');
        }
      });
    },

    toggle() {
      const current = document.documentElement.getAttribute('data-theme');
      const next = current === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      localStorage.setItem(this.STORAGE_KEY, next);
    }
  };

  // ── Toast Notifications ────────────────────────────────────────
  const Toast = {
    container: null,

    init() {
      this.container = document.getElementById('toast-container');
      if (!this.container) {
        this.container = document.createElement('div');
        this.container.id = 'toast-container';
        this.container.className = 'toast-container';
        document.body.appendChild(this.container);
      }
    },

    show(type, title, message, duration = 5000) {
      const toast = document.createElement('div');
      toast.className = `toast ${type}`;

      const icons = {
        success: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',
        error: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
        warning: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
        info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>'
      };

      toast.innerHTML = `
        <div class="toast-icon">${icons[type] || icons.info}</div>
        <div class="toast-body">
          <div class="toast-title">${title}</div>
          ${message ? `<div class="toast-message">${message}</div>` : ''}
        </div>
        <button class="toast-close" aria-label="Close">&times;</button>
      `;

      const closeBtn = toast.querySelector('.toast-close');
      closeBtn.addEventListener('click', () => this.dismiss(toast));

      this.container.appendChild(toast);

      if (duration > 0) {
        setTimeout(() => this.dismiss(toast), duration);
      }

      return toast;
    },

    dismiss(toast) {
      toast.classList.add('toast-exit');
      toast.addEventListener('animationend', () => toast.remove());
    }
  };

  // ── Tab Switching ──────────────────────────────────────────────
  const Tabs = {
    init() {
      document.querySelectorAll('.tabs').forEach(tabContainer => {
        const buttons = tabContainer.querySelectorAll('.tab-btn');
        buttons.forEach(btn => {
          btn.addEventListener('click', () => {
            const target = btn.dataset.tab;
            if (!target) return;

            // Deactivate all tabs in this group
            buttons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Hide all panels, show target
            const parent = tabContainer.parentElement;
            parent.querySelectorAll('.tab-panel').forEach(panel => {
              panel.classList.remove('active');
            });

            const targetPanel = parent.querySelector(`#tab-${target}`);
            if (targetPanel) targetPanel.classList.add('active');
          });
        });
      });
    }
  };

  // ── Confirmation Modal ─────────────────────────────────────────
  const Modal = {
    overlay: null,

    init() {
      this.overlay = document.getElementById('modal-overlay');
    },

    confirm({ title, message, confirmText = 'Delete', confirmClass = 'btn-danger', onConfirm }) {
      if (!this.overlay) return;

      const modal = this.overlay.querySelector('.modal');
      modal.querySelector('h3').textContent = title;
      modal.querySelector('p').textContent = message;

      const confirmBtn = modal.querySelector('.modal-confirm');
      confirmBtn.textContent = confirmText;
      confirmBtn.className = `btn ${confirmClass} modal-confirm`;

      // Remove old listeners by cloning
      const newBtn = confirmBtn.cloneNode(true);
      confirmBtn.parentNode.replaceChild(newBtn, confirmBtn);

      newBtn.addEventListener('click', () => {
        onConfirm();
        this.close();
      });

      this.overlay.classList.add('open');
      document.body.style.overflow = 'hidden';
    },

    close() {
      if (this.overlay) {
        this.overlay.classList.remove('open');
        document.body.style.overflow = '';
      }
    }
  };

  // ── Quick Search (Ctrl+K) ─────────────────────────────────────
  const QuickSearch = {
    overlay: null,
    input: null,
    results: null,

    init() {
      this.overlay = document.getElementById('search-overlay');
      if (!this.overlay) return;

      this.input = this.overlay.querySelector('.search-modal-input');
      this.results = this.overlay.querySelector('.search-modal-results');

      // Ctrl+K / Cmd+K to open
      document.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
          e.preventDefault();
          this.open();
        }
        if (e.key === 'Escape') {
          this.close();
        }
      });

      // Click outside to close
      this.overlay.addEventListener('click', (e) => {
        if (e.target === this.overlay) this.close();
      });

      // Search trigger button
      document.querySelectorAll('.search-trigger').forEach(btn => {
        btn.addEventListener('click', () => this.open());
      });

      // Live search
      if (this.input) {
        this.input.addEventListener('input', () => this.search(this.input.value));
      }
    },

    open() {
      if (!this.overlay) return;
      this.overlay.classList.add('open');
      document.body.style.overflow = 'hidden';
      setTimeout(() => this.input && this.input.focus(), 100);
    },

    close() {
      if (!this.overlay) return;
      this.overlay.classList.remove('open');
      document.body.style.overflow = '';
      if (this.input) this.input.value = '';
      if (this.results) this.results.innerHTML = '';
    },

    async search(query) {
      if (!query || query.length < 2) {
        if (this.results) this.results.innerHTML = '<div class="text-center text-muted text-small" style="padding:1.5rem;">Type at least 2 characters to search…</div>';
        return;
      }

      try {
        const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
        if (!response.ok) throw new Error('Search failed');
        const data = await response.json();

        if (!this.results) return;

        if (data.results.length === 0) {
          this.results.innerHTML = '<div class="text-center text-muted text-small" style="padding:1.5rem;">No patients found</div>';
          return;
        }

        this.results.innerHTML = data.results.map(p => `
          <a href="/patients/${p.id}" class="search-result-item">
            <div class="avatar avatar-sm avatar-${(p.id % 6) + 1}">${p.initials}</div>
            <div>
              <strong>${this.highlight(p.name, query)}</strong>
              <div class="text-small text-muted">${p.id_number || ''} ${p.gender ? '· ' + p.gender : ''}</div>
            </div>
          </a>
        `).join('');
      } catch (err) {
        console.error('Search error:', err);
        if (this.results) {
          this.results.innerHTML = '<div class="text-center text-muted text-small" style="padding:1.5rem;">Search unavailable</div>';
        }
      }
    },

    highlight(text, query) {
      const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
      return text.replace(regex, '<mark style="background:var(--color-accent-light);color:var(--color-accent);padding:0 2px;border-radius:2px;">$1</mark>');
    }
  };

  // ── Table Sorting ──────────────────────────────────────────────
  const TableSort = {
    init() {
      document.querySelectorAll('.data-table th.sortable').forEach(th => {
        th.addEventListener('click', () => {
          const table = th.closest('table');
          const tbody = table.querySelector('tbody');
          const colIndex = Array.from(th.parentElement.children).indexOf(th);
          const isAsc = th.classList.contains('sorted-asc');

          // Reset all headers
          table.querySelectorAll('th').forEach(h => {
            h.classList.remove('sorted', 'sorted-asc', 'sorted-desc');
          });

          th.classList.add('sorted', isAsc ? 'sorted-desc' : 'sorted-asc');

          const rows = Array.from(tbody.querySelectorAll('tr'));
          rows.sort((a, b) => {
            const aVal = a.children[colIndex]?.textContent.trim().toLowerCase() || '';
            const bVal = b.children[colIndex]?.textContent.trim().toLowerCase() || '';

            // Try numeric comparison first
            const aNum = parseFloat(aVal);
            const bNum = parseFloat(bVal);
            if (!isNaN(aNum) && !isNaN(bNum)) {
              return isAsc ? bNum - aNum : aNum - bNum;
            }

            return isAsc ? bVal.localeCompare(aVal) : aVal.localeCompare(bVal);
          });

          rows.forEach(row => tbody.appendChild(row));
        });
      });
    }
  };

  // ── Sidebar Toggle (Mobile) ────────────────────────────────────
  const Sidebar = {
    sidebar: null,
    overlay: null,

    init() {
      this.sidebar = document.querySelector('.sidebar');
      this.overlay = document.querySelector('.sidebar-overlay');

      document.querySelectorAll('.hamburger').forEach(btn => {
        btn.addEventListener('click', () => this.toggle());
      });

      if (this.overlay) {
        this.overlay.addEventListener('click', () => this.close());
      }
    },

    toggle() {
      if (!this.sidebar) return;
      this.sidebar.classList.toggle('open');
      if (this.overlay) this.overlay.classList.toggle('open');
    },

    close() {
      if (!this.sidebar) return;
      this.sidebar.classList.remove('open');
      if (this.overlay) this.overlay.classList.remove('open');
    }
  };

  // ── Delete Confirmation ────────────────────────────────────────
  const DeleteConfirm = {
    init() {
      document.querySelectorAll('[data-confirm-delete]').forEach(form => {
        form.addEventListener('submit', (e) => {
          e.preventDefault();
          const name = form.dataset.confirmDelete || 'this record';

          Modal.confirm({
            title: 'Confirm Deletion',
            message: `Are you sure you want to delete ${name}? This action cannot be undone.`,
            confirmText: 'Delete',
            confirmClass: 'btn-danger',
            onConfirm: () => form.submit()
          });
        });
      });
    }
  };

  // ── Flash Messages → Toasts ────────────────────────────────────
  const FlashToasts = {
    init() {
      document.querySelectorAll('.flash-data').forEach(el => {
        const type = el.dataset.type || 'info';
        const message = el.dataset.message || '';
        if (message) {
          const typeMap = { success: 'success', error: 'error', danger: 'error', warning: 'warning', info: 'info' };
          const titles = { success: 'Success', error: 'Error', warning: 'Warning', info: 'Info' };
          const t = typeMap[type] || 'info';
          Toast.show(t, titles[t], message);
        }
        el.remove();
      });
    }
  };

  // ── Print Summary ──────────────────────────────────────────────
  const PrintSummary = {
    init() {
      document.querySelectorAll('[data-print]').forEach(btn => {
        btn.addEventListener('click', (e) => {
          e.preventDefault();
          // Show all tab panels for print
          document.querySelectorAll('.tab-panel').forEach(p => p.style.display = 'block');
          window.print();
          // Restore tab state
          setTimeout(() => {
            document.querySelectorAll('.tab-panel').forEach(p => p.style.display = '');
          }, 500);
        });
      });
    }
  };

  // ── Form Validation ────────────────────────────────────────────
  const FormValidation = {
    init() {
      document.querySelectorAll('form[data-validate]').forEach(form => {
        form.addEventListener('submit', (e) => {
          let valid = true;
          form.querySelectorAll('[required]').forEach(input => {
            const errorEl = input.parentElement.querySelector('.form-error');
            if (!input.value.trim()) {
              valid = false;
              input.classList.add('error');
              if (errorEl) errorEl.style.display = 'flex';
            } else {
              input.classList.remove('error');
              if (errorEl) errorEl.style.display = 'none';
            }
          });

          if (!valid) {
            e.preventDefault();
            Toast.show('error', 'Validation Error', 'Please fill in all required fields.');
          }
        });

        // Clear error on input
        form.querySelectorAll('[required]').forEach(input => {
          input.addEventListener('input', () => {
            input.classList.remove('error');
            const errorEl = input.parentElement.querySelector('.form-error');
            if (errorEl) errorEl.style.display = 'none';
          });
        });
      });
    }
  };

  // ── Initialize Everything on DOM Ready ─────────────────────────
  document.addEventListener('DOMContentLoaded', () => {
    ThemeManager.init();
    Toast.init();
    Tabs.init();
    Modal.init();
    QuickSearch.init();
    TableSort.init();
    Sidebar.init();
    DeleteConfirm.init();
    FlashToasts.init();
    PrintSummary.init();
    FormValidation.init();

    // Expose theme toggle globally for the button
    window.toggleTheme = () => ThemeManager.toggle();

    // Expose modal close globally
    window.closeModal = () => Modal.close();
  });
})();
