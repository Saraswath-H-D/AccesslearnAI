/**
 * AccessLearn AI - Accessibility Engine
 * Handles theme switching, font scaling, screen reader announcements, and keyboard shortcuts.
 */

class AccessibilityEngine {
  constructor() {
    this.currentTheme = localStorage.getItem('accesslearn_theme') || 'light';
    this.currentFontSize = localStorage.getItem('accesslearn_font_size') || 'medium';
    this.init();
  }

  init() {
    this.applyTheme(this.currentTheme);
    this.applyFontSize(this.currentFontSize);
    this.setupEventListeners();
    this.setupKeyboardShortcuts();
  }

  applyTheme(theme) {
    this.currentTheme = theme;
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('accesslearn_theme', theme);
    this.announceToScreenReader(`Theme changed to ${theme.replace('-', ' ')} mode`);
  }

  applyFontSize(size) {
    this.currentFontSize = size;
    document.documentElement.setAttribute('data-font-size', size);
    localStorage.setItem('accesslearn_font_size', size);
    this.announceToScreenReader(`Font size set to ${size}`);
  }

  toggleHighContrast() {
    const newTheme = this.currentTheme === 'high-contrast' ? 'light' : 'high-contrast';
    this.applyTheme(newTheme);
  }

  toggleTheme() {
    let nextTheme = 'light';
    if (this.currentTheme === 'light') nextTheme = 'dark';
    else if (this.currentTheme === 'dark') nextTheme = 'high-contrast';
    else nextTheme = 'light';
    this.applyTheme(nextTheme);
  }

  announceToScreenReader(message, priority = 'polite') {
    const announcer = document.getElementById('a11y-announcer');
    if (announcer) {
      announcer.setAttribute('aria-live', priority);
      announcer.textContent = message;
      // Clear after short duration to allow re-announcing
      setTimeout(() => {
        announcer.textContent = '';
      }, 3000);
    }
  }

  setupEventListeners() {
    // Quick sidebar controls + Preferences drawer controls share behavior;
    // wire every matching pair of IDs so both surfaces stay in sync.
    const wireAll = (ids, handler) => {
      ids.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('click', handler);
      });
    };

    wireAll(['btn-high-contrast', 'pref-btn-high-contrast'], () => this.toggleHighContrast());
    wireAll(['btn-theme-toggle', 'pref-btn-theme-toggle'], () => this.toggleTheme());
    wireAll(['btn-font-small', 'pref-btn-font-small'], () => this.applyFontSize('small'));
    wireAll(['btn-font-medium', 'pref-btn-font-medium'], () => this.applyFontSize('medium'));
    wireAll(['btn-font-large', 'pref-btn-font-large'], () => this.applyFontSize('large'));
    wireAll(['btn-font-xlarge', 'pref-btn-font-xlarge'], () => this.applyFontSize('xlarge'));
  }

  setupKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
      // Check for Alt modifier
      if (e.altKey) {
        switch (e.key.toLowerCase()) {
          case 't':
            e.preventDefault();
            this.toggleHighContrast();
            break;
          case 'u':
          case 'd':
            e.preventDefault();
            if (window.appRouter) window.appRouter.openUploadModal();
            break;
          case 'h':
            e.preventDefault();
            if (window.appRouter) window.appRouter.showEmptyState();
            break;
        }
      }
    });
  }
}

// Global Accessibility Engine Instance
window.a11y = new AccessibilityEngine();
