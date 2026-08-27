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
    // High contrast toggle button
    const contrastBtn = document.getElementById('btn-high-contrast');
    if (contrastBtn) {
      contrastBtn.addEventListener('click', () => this.toggleHighContrast());
    }

    // Theme cycle button
    const themeBtn = document.getElementById('btn-theme-toggle');
    if (themeBtn) {
      themeBtn.addEventListener('click', () => this.toggleTheme());
    }

    // Font size controls
    const fontSmall = document.getElementById('btn-font-small');
    const fontMedium = document.getElementById('btn-font-medium');
    const fontLarge = document.getElementById('btn-font-large');
    const fontXLarge = document.getElementById('btn-font-xlarge');

    if (fontSmall) fontSmall.addEventListener('click', () => this.applyFontSize('small'));
    if (fontMedium) fontMedium.addEventListener('click', () => this.applyFontSize('medium'));
    if (fontLarge) fontLarge.addEventListener('click', () => this.applyFontSize('large'));
    if (fontXLarge) fontXLarge.addEventListener('click', () => this.applyFontSize('xlarge'));
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
            e.preventDefault();
            if (window.appRouter) window.appRouter.showView('dashboard-view');
            break;
          case 'd':
            e.preventDefault();
            if (window.appRouter) window.appRouter.showView('dashboard-view');
            break;
          case 'h':
            e.preventDefault();
            if (window.appRouter) window.appRouter.showView('landing-view');
            break;
        }
      }
    });
  }
}

// Global Accessibility Engine Instance
window.a11y = new AccessibilityEngine();
