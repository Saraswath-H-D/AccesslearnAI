/**
 * AccessLearn AI - Interactive Braille Viewer Component
 */

class BrailleViewerComponent {
  constructor() {
    this.unicodeText = "";
    this.brfText = "";
    this.lectureId = "";
    this.displayMode = "unicode"; // "unicode" or "ascii"
    this.setupListeners();
  }

  loadBrailleData(brailleData, lectureId) {
    this.unicodeText = brailleData.unicode_braille || "";
    this.brfText = brailleData.brf_text || "";
    this.lectureId = lectureId;
    this.render();
  }

  setupListeners() {
    const modeToggle = document.getElementById('braille-mode-toggle');
    if (modeToggle) {
      modeToggle.addEventListener('click', () => {
        this.displayMode = this.displayMode === 'unicode' ? 'ascii' : 'unicode';
        modeToggle.textContent = this.displayMode === 'unicode' ? 'Switch to ASCII BRF' : 'Switch to Visual Braille';
        this.render();
        if (window.a11y) window.a11y.announceToScreenReader(`Braille view switched to ${this.displayMode}`);
      });
    }

    const downloadBtn = document.getElementById('braille-download-btn');
    if (downloadBtn) {
      downloadBtn.addEventListener('click', () => {
        if (this.lectureId) {
          window.location.href = `/api/braille/${this.lectureId}?download=true`;
          if (window.a11y) window.a11y.announceToScreenReader('Downloading Braille BRF file');
        }
      });
    }

    const copyBtn = document.getElementById('braille-copy-btn');
    if (copyBtn) {
      copyBtn.addEventListener('click', () => {
        const textToCopy = this.displayMode === 'unicode' ? this.unicodeText : this.brfText;
        navigator.clipboard.writeText(textToCopy).then(() => {
          if (window.a11y) window.a11y.announceToScreenReader('Braille text copied to clipboard');
          copyBtn.textContent = 'Copied!';
          setTimeout(() => { copyBtn.textContent = 'Copy Braille'; }, 2000);
        });
      });
    }
  }

  render() {
    const container = document.getElementById('braille-display-box');
    const statsEl = document.getElementById('braille-stats-info');
    if (!container) return;

    const activeText = this.displayMode === 'unicode' ? this.unicodeText : this.brfText;
    container.textContent = activeText || 'No Braille data available.';

    if (statsEl) {
      const lines = activeText.split('\n').length;
      const totalCells = activeText.length;
      statsEl.textContent = `Formatted 40-cell grid | Total Lines: ${lines} | Standard Grade 2 BRF`;
    }
  }
}

window.brailleViewer = new BrailleViewerComponent();
