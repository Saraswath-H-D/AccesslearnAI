/**
 * AccessLearn AI - Main Frontend Application Router & Controller
 */

class AccessLearnApp {
  constructor() {
    this.currentLectureId = null;
    this.statusPollInterval = null;
    this.audioPlayer = null;
    this.uploadMode = 'file'; // 'file' | 'youtube'
    this.init();
  }

  init() {
    this.audioPlayer = new AccessibleAudioPlayer('main-audio-element');
    this.setupViewNavigation();
    this.setupUploadModeToggle();
    this.setupFileUpload();
    this.setupYouTubeInput();
    this.setupResultsTabs();
    this.setupDemoButtons();
    this.loadRecentLectures();

    // Default to Landing view
    this.showView('landing-view');
  }

  setupUploadModeToggle() {
    const modeBtns = document.querySelectorAll('.upload-mode-btn');
    const filePanel = document.getElementById('upload-mode-file');
    const youtubePanel = document.getElementById('upload-mode-youtube');
    const submitBtn = document.getElementById('start-upload-btn');

    modeBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        const mode = btn.getAttribute('data-mode');
        this.uploadMode = mode;

        modeBtns.forEach(b => {
          b.classList.toggle('active', b === btn);
          b.setAttribute('aria-selected', b === btn ? 'true' : 'false');
        });

        if (filePanel) filePanel.hidden = mode !== 'file';
        if (youtubePanel) youtubePanel.hidden = mode !== 'youtube';

        if (submitBtn) {
          submitBtn.textContent = mode === 'youtube'
            ? 'Fetch YouTube Audio & Convert'
            : 'Start AI Accessibility Conversion';
        }

        if (window.a11y) {
          window.a11y.announceToScreenReader(
            mode === 'youtube' ? 'Switched to YouTube link input.' : 'Switched to file upload.'
          );
        }
      });
    });
  }

  setupYouTubeInput() {
    const urlInput = document.getElementById('youtube-url-input');
    const infoEl = document.getElementById('youtube-url-info');
    if (!urlInput) return;

    urlInput.addEventListener('input', () => {
      const value = urlInput.value.trim();
      if (!infoEl) return;
      if (!value) {
        infoEl.textContent = '';
      } else if (this.isValidYouTubeUrl(value)) {
        infoEl.innerHTML = '✅ Valid YouTube link detected.';
      } else {
        infoEl.innerHTML = '⚠️ This does not look like a valid YouTube link yet.';
      }
    });
  }

  isValidYouTubeUrl(url) {
    return /(?:youtube\.com\/(?:watch\?v=|shorts\/|embed\/|live\/)|youtu\.be\/)([A-Za-z0-9_-]{11})/.test(url);
  }

  showView(viewId) {
    const views = document.querySelectorAll('.view-section');
    views.forEach(v => v.classList.remove('active-view'));

    const targetView = document.getElementById(viewId);
    if (targetView) {
      targetView.classList.add('active-view');
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    // Update Nav bar links
    const navLinks = document.querySelectorAll('.nav-link');
    navLinks.forEach(link => {
      if (link.getAttribute('data-target') === viewId) {
        link.classList.add('active');
      } else {
        link.classList.remove('active');
      }
    });

    if (window.a11y) {
      const pageName = viewId.replace('-view', '').replace('-', ' ');
      window.a11y.announceToScreenReader(`Navigated to ${pageName}`);
    }
  }

  setupViewNavigation() {
    const navLinks = document.querySelectorAll('[data-target]');
    navLinks.forEach(link => {
      link.addEventListener('click', (e) => {
        e.preventDefault();
        const targetView = link.getAttribute('data-target');
        this.showView(targetView);
      });
    });
  }

  setupFileUpload() {
    const dropZone = document.getElementById('file-drop-zone');
    const fileInput = document.getElementById('lecture-file-input');
    const uploadForm = document.getElementById('upload-lecture-form');

    if (dropZone && fileInput) {
      dropZone.addEventListener('click', () => fileInput.click());

      dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
      });

      dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
      });

      dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
          fileInput.files = e.dataTransfer.files;
          this.handleFileSelected(e.dataTransfer.files[0]);
        }
      });

      fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
          this.handleFileSelected(e.target.files[0]);
        }
      });
    }

    if (uploadForm) {
      uploadForm.addEventListener('submit', (e) => {
        e.preventDefault();
        this.submitLectureUpload();
      });
    }
  }

  handleFileSelected(file) {
    const infoEl = document.getElementById('selected-file-info');
    if (infoEl) {
      const mb = (file.size / (1024 * 1024)).toFixed(2);
      infoEl.innerHTML = `<strong>Selected File:</strong> ${file.name} (${mb} MB)`;
    }
  }

  async submitLectureUpload() {
    const submitBtn = document.getElementById('start-upload-btn');
    const titleInput = document.getElementById('lecture-title-input');
    const originalLabel = this.uploadMode === 'youtube'
      ? 'Fetch YouTube Audio & Convert'
      : 'Start AI Accessibility Conversion';

    let response;
    try {
      if (this.uploadMode === 'youtube') {
        const urlInput = document.getElementById('youtube-url-input');
        const url = urlInput ? urlInput.value.trim() : '';

        if (!url) {
          alert('Please paste a YouTube lecture link.');
          return;
        }
        if (!this.isValidYouTubeUrl(url)) {
          alert('That does not look like a valid YouTube link. Please check the URL and try again.');
          return;
        }

        if (submitBtn) {
          submitBtn.disabled = true;
          submitBtn.textContent = 'Downloading & Scanning Audio...';
        }
        if (window.a11y) window.a11y.announceToScreenReader('Downloading and scanning YouTube audio.');

        response = await fetch('/api/upload/youtube', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            url,
            title: titleInput && titleInput.value.trim() ? titleInput.value.trim() : null
          })
        });
      } else {
        const fileInput = document.getElementById('lecture-file-input');
        if (!fileInput || fileInput.files.length === 0) {
          alert('Please select an audio or video file to upload.');
          return;
        }

        const file = fileInput.files[0];
        const formData = new FormData();
        formData.append('file', file);
        if (titleInput && titleInput.value.trim()) {
          formData.append('title', titleInput.value.trim());
        }

        if (submitBtn) {
          submitBtn.disabled = true;
          submitBtn.textContent = 'Uploading & Scanning...';
        }

        response = await fetch('/api/upload', {
          method: 'POST',
          body: formData
        });
      }

      const res = await response.json();
      if (!response.ok) {
        throw new Error(res.detail || 'Upload failed');
      }

      this.currentLectureId = res.lecture_id;

      // Start processing backend
      await fetch(`/api/process/${this.currentLectureId}`, { method: 'POST' });

      // Switch to Processing View & Poll Status
      this.showView('processing-view');
      this.startStatusPolling(this.currentLectureId);

    } catch (err) {
      alert(`Upload Error: ${err.message}`);
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = originalLabel;
      }
    }
  }

  setupDemoButtons() {
    const demoBtn1 = document.getElementById('btn-demo-quantum');
    const demoBtn2 = document.getElementById('btn-demo-neural');

    if (demoBtn1) {
      demoBtn1.addEventListener('click', () => this.loadDemo('quantum'));
    }
    if (demoBtn2) {
      demoBtn2.addEventListener('click', () => this.loadDemo('neural'));
    }
  }

  async loadDemo(demoKey) {
    try {
      if (window.a11y) window.a11y.announceToScreenReader('Loading demo lecture...');
      const response = await fetch(`/api/demo/load/${demoKey}`, { method: 'POST' });
      const res = await response.json();
      
      if (response.ok && res.lecture_id) {
        this.currentLectureId = res.lecture_id;
        this.fetchAndDisplayResults(this.currentLectureId);
        this.showView('results-view');
      }
    } catch (err) {
      console.error('Demo loading failed:', err);
    }
  }

  startStatusPolling(lectureId) {
    if (this.statusPollInterval) clearInterval(this.statusPollInterval);

    this.statusPollInterval = setInterval(async () => {
      try {
        const response = await fetch(`/api/status/${lectureId}`);
        if (!response.ok) return;
        const statusData = await response.json();

        this.updatePipelineProgressUI(statusData);

        if (statusData.status === 'completed') {
          clearInterval(this.statusPollInterval);
          setTimeout(() => {
            this.fetchAndDisplayResults(lectureId);
            this.showView('results-view');
            if (window.a11y) window.a11y.announceToScreenReader('Lecture processing complete. Displaying results.');
          }, 800);
        }
      } catch (err) {
        console.error('Status polling error:', err);
      }
    }, 1000);
  }

  updatePipelineProgressUI(statusData) {
    const progressBar = document.getElementById('pipeline-progress-bar');
    const stageText = document.getElementById('pipeline-stage-text');
    const titleText = document.getElementById('processing-lecture-title');

    if (progressBar) progressBar.style.width = `${statusData.progress}%`;
    if (stageText) stageText.textContent = statusData.current_stage || 'Processing...';
    if (titleText) titleText.textContent = statusData.title || 'Lecture Processing';

    // Update Pipeline Badge Step Highlights
    const steps = document.querySelectorAll('.pipeline-step');
    if (statusData.stages && steps.length > 0) {
      statusData.stages.forEach((stg, idx) => {
        if (steps[idx]) {
          steps[idx].className = `pipeline-step ${stg.status}`;
        }
      });
    }
  }

  async fetchAndDisplayResults(lectureId) {
    try {
      const response = await fetch(`/api/status/${lectureId}`);
      if (!response.ok) return;
      const fullData = await response.json();
      const data = fullData.data || {};

      // Set Lecture Title
      const titleEl = document.getElementById('results-lecture-title');
      if (titleEl) titleEl.textContent = fullData.title;

      // 1. Render Transcript
      this.renderTranscript(data.transcript || {});

      // 2. Render Simplified Content
      this.renderSimplified(data.simplified || {});

      // 3. Render Summary & Keywords
      this.renderSummary(data.summary || {});

      // 4. Render Key Points
      this.renderKeyPoints(data.key_points || []);

      // 5. Load Audio Player
      if (data.audio && data.audio.url) {
        this.audioPlayer.loadAudio(data.audio.url);
        const downloadAudioBtn = document.getElementById('audio-download-btn');
        if (downloadAudioBtn) {
          downloadAudioBtn.onclick = () => {
            window.location.href = `/api/audio/${lectureId}?download=true`;
          };
        }
      }

      // 6. Load Braille Display
      if (data.braille && window.brailleViewer) {
        window.brailleViewer.loadBrailleData(data.braille, lectureId);
      }

      this.loadRecentLectures();

    } catch (err) {
      console.error('Error fetching lecture results:', err);
    }
  }

  renderTranscript(transcriptData) {
    const container = document.getElementById('transcript-content-box');
    if (!container) return;

    const segments = transcriptData.segments || [];
    if (segments.length === 0) {
      container.innerHTML = `<p>${transcriptData.full_text || 'No transcript text available.'}</p>`;
      return;
    }

    let html = '';
    segments.forEach(seg => {
      html += `
        <div class="transcript-segment">
          <span class="timestamp-tag" onclick="window.appRouter.audioPlayer.seekToSeconds(${seg.start_seconds})">
            ⏱ ${seg.timestamp}
          </span>
          <p>${seg.text}</p>
        </div>
      `;
    });
    container.innerHTML = html;
  }

  renderSimplified(simplifiedData) {
    const easyBox = document.getElementById('simplified-easy-box');
    const notesBox = document.getElementById('simplified-notes-box');

    if (easyBox) {
      easyBox.innerHTML = `
        <h3>Easy Explanation</h3>
        <p>${simplifiedData.easy_explanation || ''}</p>
        <div style="margin-top: 16px; white-space: pre-wrap;">${simplifiedData.simplified_content || ''}</div>
      `;
    }

    if (notesBox && simplifiedData.study_notes) {
      let notesHtml = '<h3>Structured Study Notes</h3>';
      simplifiedData.study_notes.forEach(note => {
        notesHtml += `
          <div style="margin-bottom: 16px; padding: 12px; background: var(--bg-primary); border-radius: var(--radius-sm);">
            <h4 style="color: var(--primary); margin-bottom: 6px;">${note.heading}</h4>
            <p>${note.content}</p>
          </div>
        `;
      });
      notesBox.innerHTML = notesHtml;
    }
  }

  renderSummary(summaryData) {
    const summaryText = document.getElementById('summary-text-box');
    const keywordsBox = document.getElementById('keywords-grid-box');

    if (summaryText) {
      summaryText.textContent = summaryData.short_summary || '';
    }

    if (keywordsBox && summaryData.keywords) {
      let kwHtml = '';
      summaryData.keywords.forEach(kw => {
        kwHtml += `
          <div style="padding: 14px; background: var(--bg-primary); border: 1px solid var(--border-color); border-radius: var(--radius-sm);">
            <strong style="color: var(--primary); font-size: 1.05rem;">${kw.term}</strong>
            <p style="margin-top: 4px; font-size: 0.95rem;">${kw.definition}</p>
          </div>
        `;
      });
      keywordsBox.innerHTML = kwHtml;
    }
  }

  renderKeyPoints(keyPointsList) {
    const container = document.getElementById('keypoints-list-box');
    if (!container) return;

    let html = '<ul style="list-style-type: none; padding: 0;">';
    keyPointsList.forEach(kp => {
      html += `
        <li style="padding: 12px 16px; margin-bottom: 10px; background: var(--bg-primary); border-left: 4px solid var(--accent-purple); border-radius: var(--radius-sm); font-size: 1.05rem;">
          📌 ${kp}
        </li>
      `;
    });
    html += '</ul>';
    container.innerHTML = html;
  }

  setupResultsTabs() {
    const tabBtns = document.querySelectorAll('.tab-btn');
    tabBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        const targetTab = btn.getAttribute('data-tab');

        tabBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        const tabContents = document.querySelectorAll('.tab-content');
        tabContents.forEach(content => {
          if (content.id === targetTab) {
            content.classList.add('active');
          } else {
            content.classList.remove('active');
          }
        });

        if (window.a11y) window.a11y.announceToScreenReader(`Switched to tab ${btn.textContent.trim()}`);
      });
    });
  }

  async loadRecentLectures() {
    const listEl = document.getElementById('recent-lectures-list');
    if (!listEl) return;

    try {
      const response = await fetch('/api/lectures');
      const data = await response.json();
      const lectures = data.lectures || [];

      if (lectures.length === 0) {
        listEl.innerHTML = '<p style="color: var(--text-muted);">No processed lectures yet.</p>';
        return;
      }

      let html = '<div style="display: grid; gap: 12px;">';
      lectures.forEach(lec => {
        html += `
          <div style="display: flex; justify-content: space-between; align-items: center; padding: 16px; background: var(--bg-surface); border: 1px solid var(--border-color); border-radius: var(--radius-sm);">
            <div>
              <strong style="font-size: 1.1rem;">${lec.title}</strong>
              <div style="font-size: 0.85rem; color: var(--text-muted);">${lec.created_at}</div>
            </div>
            <button class="btn btn-outline" onclick="window.appRouter.openExistingLecture('${lec.id}')">
              View Formats
            </button>
          </div>
        `;
      });
      html += '</div>';
      listEl.innerHTML = html;
    } catch (err) {
      console.error('Failed loading recent lectures:', err);
    }
  }

  openExistingLecture(lectureId) {
    this.currentLectureId = lectureId;
    this.fetchAndDisplayResults(lectureId);
    this.showView('results-view');
  }
}

// Global App Router Instance
document.addEventListener('DOMContentLoaded', () => {
  window.appRouter = new AccessLearnApp();
});
