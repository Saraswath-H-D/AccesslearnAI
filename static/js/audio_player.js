/**
 * AccessLearn AI - Accessible Audio Player Component
 */

class AccessibleAudioPlayer {
  constructor(audioElementId) {
    this.audio = document.getElementById(audioElementId);
    this.isPlaying = false;
    this.setupPlayerControls();
  }

  loadAudio(url) {
    if (!this.audio) return;
    this.audio.src = url;
    this.audio.load();
    this.updateProgressUI(0, 0);
  }

  setupPlayerControls() {
    this.playBtn = document.getElementById('audio-play-btn');
    this.seekSlider = document.getElementById('audio-seek-slider');
    this.currentTimeEl = document.getElementById('audio-current-time');
    this.totalTimeEl = document.getElementById('audio-total-time');
    this.speedSelect = document.getElementById('audio-speed-select');
    this.rewindBtn = document.getElementById('audio-rewind-btn');
    this.forwardBtn = document.getElementById('audio-forward-btn');

    if (this.playBtn) {
      this.playBtn.addEventListener('click', () => this.togglePlay());
    }

    if (this.rewindBtn) {
      this.rewindBtn.addEventListener('click', () => this.skip(-10));
    }

    if (this.forwardBtn) {
      this.forwardBtn.addEventListener('click', () => this.skip(10));
    }

    if (this.speedSelect) {
      this.speedSelect.addEventListener('change', (e) => {
        if (this.audio) this.audio.playbackRate = parseFloat(e.target.value);
        if (window.a11y) window.a11y.announceToScreenReader(`Playback speed set to ${e.target.value} times`);
      });
    }

    if (this.audio) {
      this.audio.addEventListener('timeupdate', () => {
        const cur = this.audio.currentTime;
        const dur = this.audio.duration || 1;
        this.updateProgressUI(cur, dur);
      });

      this.audio.addEventListener('ended', () => {
        this.isPlaying = false;
        if (this.playBtn) {
          this.playBtn.innerHTML = '▶ <span class="sr-only">Play Audio</span>';
        }
      });
    }

    if (this.seekSlider) {
      this.seekSlider.addEventListener('input', (e) => {
        if (this.audio && this.audio.duration) {
          const targetTime = (parseFloat(e.target.value) / 100) * this.audio.duration;
          this.audio.currentTime = targetTime;
        }
      });
    }
  }

  togglePlay() {
    if (!this.audio) return;
    if (this.isPlaying) {
      this.audio.pause();
      this.isPlaying = false;
      if (this.playBtn) this.playBtn.innerHTML = '▶ <span class="sr-only">Play Audio</span>';
      if (window.a11y) window.a11y.announceToScreenReader('Audio paused');
    } else {
      this.audio.play().then(() => {
        this.isPlaying = true;
        if (this.playBtn) this.playBtn.innerHTML = '⏸ <span class="sr-only">Pause Audio</span>';
        if (window.a11y) window.a11y.announceToScreenReader('Audio playing');
      }).catch(err => {
        console.warn('Audio playback error:', err);
      });
    }
  }

  skip(seconds) {
    if (!this.audio) return;
    this.audio.currentTime = Math.max(0, Math.min(this.audio.duration || 0, this.audio.currentTime + seconds));
    if (window.a11y) window.a11y.announceToScreenReader(`Skipped ${seconds > 0 ? 'forward' : 'backward'} ${Math.abs(seconds)} seconds`);
  }

  seekToSeconds(seconds) {
    if (!this.audio) return;
    this.audio.currentTime = seconds;
    if (!this.isPlaying) {
      this.togglePlay();
    }
  }

  updateProgressUI(current, duration) {
    if (this.currentTimeEl) this.currentTimeEl.textContent = this.formatTime(current);
    if (this.totalTimeEl) this.totalTimeEl.textContent = this.formatTime(duration);
    if (this.seekSlider && duration > 0) {
      const pct = (current / duration) * 100;
      this.seekSlider.value = pct;
      this.seekSlider.setAttribute('aria-valuenow', Math.round(pct));
    }
  }

  formatTime(seconds) {
    if (isNaN(seconds)) return '00:00';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m < 10 ? '0' : ''}${m}:${s < 10 ? '0' : ''}${s}`;
  }
}
