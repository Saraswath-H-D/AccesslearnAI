/**
 * AccessLearn AI - Main Frontend Application Router & Controller
 */

class AccessLearnApp {
  constructor() {
    this.currentLectureId = null;
    this.currentLectureTitle = null;
    this.statusPollInterval = null;
    this.audioPlayer = null;
    this.chatStarted = {}; // lectureId -> bool, so chat greeting only shows once per open
    this.speakTextRegistry = []; // index -> raw text, used by picture-card "listen" buttons
    this.init();
  }

  init() {
    this.audioPlayer = new AccessibleAudioPlayer('main-audio-element');
    this.setupUserCard();
    this.setupUploadModal();
    this.setupPreferencesModal();
    this.setupResultsTabs();
    this.setupDemoButtons();
    this.setupCloseWorkspace();
    this.setupPdfDownloadButtons();
    this.loadRecentLectures();

    this.showEmptyState();
  }

  // ------------------------------------------------------------------
  // Workspace State Management
  // ------------------------------------------------------------------
  showState(stateId) {
    document.querySelectorAll('.workspace-state').forEach(s => s.classList.remove('active-state'));
    const target = document.getElementById(stateId);
    if (target) {
      target.classList.add('active-state');
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  }

  showEmptyState() {
    this.currentLectureId = null;
    document.getElementById('main-topbar').hidden = true;
    this.showState('state-empty');
    this.highlightActiveLectureInSidebar(null);
  }

  showProcessingState() {
    document.getElementById('main-topbar').hidden = true;
    this.showState('state-processing');
  }

  showResultsState() {
    const topbar = document.getElementById('main-topbar');
    topbar.hidden = false;
    document.getElementById('topbar-lecture-title').textContent = this.currentLectureTitle || 'Lecture';
    this.showState('state-results');
  }

  setupCloseWorkspace() {
    const btn = document.getElementById('btn-close-workspace');
    if (btn) btn.addEventListener('click', () => this.showEmptyState());
  }

  // ------------------------------------------------------------------
  // User Card (local display name only, stored per-browser)
  // ------------------------------------------------------------------
  setupUserCard() {
    const nameInput = document.getElementById('user-name-input');
    const avatar = document.getElementById('user-avatar-initial');
    if (!nameInput) return;

    const saved = localStorage.getItem('accesslearn_user_name');
    if (saved) nameInput.value = saved;
    if (avatar) avatar.textContent = (nameInput.value.trim()[0] || 'G').toUpperCase();

    nameInput.addEventListener('change', () => {
      const val = nameInput.value.trim() || 'Guest Learner';
      nameInput.value = val;
      localStorage.setItem('accesslearn_user_name', val);
      if (avatar) avatar.textContent = val[0].toUpperCase();
    });

    const prefsBtn = document.getElementById('btn-open-preferences');
    if (prefsBtn) prefsBtn.addEventListener('click', () => this.togglePreferencesModal(true));
  }

  setupPreferencesModal() {
    const overlay = document.getElementById('preferences-modal-overlay');
    const closeBtn = document.getElementById('btn-close-preferences');
    if (closeBtn) closeBtn.addEventListener('click', () => this.togglePreferencesModal(false));
    if (overlay) {
      overlay.addEventListener('click', (e) => {
        if (e.target === overlay) this.togglePreferencesModal(false);
      });
    }
  }

  togglePreferencesModal(show) {
    const overlay = document.getElementById('preferences-modal-overlay');
    if (overlay) overlay.hidden = !show;
  }

  // ------------------------------------------------------------------
  // Upload Modal & File Handling
  // ------------------------------------------------------------------
  setupUploadModal() {
    const openBtns = [document.getElementById('btn-open-upload-modal'), document.getElementById('btn-empty-upload')];
    const overlay = document.getElementById('upload-modal-overlay');
    const closeBtn = document.getElementById('btn-close-upload-modal');

    openBtns.forEach(btn => {
      if (btn) btn.addEventListener('click', () => this.openUploadModal());
    });
    if (closeBtn) closeBtn.addEventListener('click', () => this.closeUploadModal());
    if (overlay) {
      overlay.addEventListener('click', (e) => {
        if (e.target === overlay) this.closeUploadModal();
      });
    }

    this.uploadSource = 'file'; // 'file' | 'url'
    const fileTabBtn = document.getElementById('btn-source-file');
    const urlTabBtn = document.getElementById('btn-source-url');
    if (fileTabBtn && urlTabBtn) {
      fileTabBtn.addEventListener('click', () => this.setUploadSource('file'));
      urlTabBtn.addEventListener('click', () => this.setUploadSource('url'));
    }

    const dropZone = document.getElementById('file-drop-zone');
    const fileInput = document.getElementById('lecture-file-input');
    const uploadForm = document.getElementById('upload-lecture-form');

    if (dropZone && fileInput) {
      dropZone.addEventListener('click', () => fileInput.click());
      dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
      dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
      dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
          fileInput.files = e.dataTransfer.files;
          this.handleFileSelected(e.dataTransfer.files[0]);
        }
      });
      fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) this.handleFileSelected(e.target.files[0]);
      });
    }

    if (uploadForm) {
      uploadForm.addEventListener('submit', (e) => {
        e.preventDefault();
        if (this.uploadSource === 'url') this.submitUrlUpload();
        else this.submitFileUpload();
      });
    }
  }

  setUploadSource(source) {
    this.uploadSource = source;
    document.getElementById('btn-source-file').classList.toggle('active', source === 'file');
    document.getElementById('btn-source-file').setAttribute('aria-selected', source === 'file');
    document.getElementById('btn-source-url').classList.toggle('active', source === 'url');
    document.getElementById('btn-source-url').setAttribute('aria-selected', source === 'url');
    document.getElementById('upload-source-file-panel').hidden = source !== 'file';
    document.getElementById('upload-source-url-panel').hidden = source !== 'url';
  }

  openUploadModal() {
    const overlay = document.getElementById('upload-modal-overlay');
    if (overlay) overlay.hidden = false;
  }

  closeUploadModal() {
    const overlay = document.getElementById('upload-modal-overlay');
    if (overlay) overlay.hidden = true;
    // Reset the URL/auth sub-flow so a reopened modal starts clean.
    const authPanel = document.getElementById('url-auth-panel');
    if (authPanel) authPanel.hidden = true;
    const statusEl = document.getElementById('url-fetch-status');
    if (statusEl) statusEl.textContent = '';
    const browserSelect = document.getElementById('lecture-url-browser-select');
    if (browserSelect) browserSelect.value = '';
  }

  handleFileSelected(file) {
    const infoEl = document.getElementById('selected-file-info');
    if (infoEl) {
      const mb = (file.size / (1024 * 1024)).toFixed(2);
      infoEl.innerHTML = `Selected: ${file.name} (${mb} MB)`;
    }
  }

  async submitFileUpload() {
    const fileInput = document.getElementById('lecture-file-input');
    const titleInput = document.getElementById('lecture-title-input');
    const submitBtn = document.getElementById('start-upload-btn');

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

    try {
      if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = 'Uploading…'; }

      const response = await fetch('/api/upload', { method: 'POST', body: formData });
      const res = await response.json();
      if (!response.ok) throw new Error(res.detail || 'Upload failed');

      this.beginProcessing(res.lecture_id, res.title);

    } catch (err) {
      alert(`Upload Error: ${err.message}`);
    } finally {
      if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = 'Start AI Accessibility Conversion'; }
    }
  }

  async submitUrlUpload() {
    const urlInput = document.getElementById('lecture-url-input');
    const titleInput = document.getElementById('lecture-title-input');
    const submitBtn = document.getElementById('start-upload-btn');
    const authPanel = document.getElementById('url-auth-panel');
    const browserSelect = document.getElementById('lecture-url-browser-select');
    const statusEl = document.getElementById('url-fetch-status');

    const url = (urlInput && urlInput.value.trim()) || '';
    if (!url) {
      alert('Please paste a video link (YouTube or another educational video site).');
      return;
    }

    // Once the auth panel is showing, a browser choice is required to retry.
    const authPanelVisible = authPanel && !authPanel.hidden;
    const browser = authPanelVisible ? (browserSelect && browserSelect.value) : '';
    if (authPanelVisible && !browser) {
      if (statusEl) statusEl.textContent = 'Please choose which browser you\'re signed in with, then try again.';
      return;
    }

    const body = { url };
    if (titleInput && titleInput.value.trim()) body.title = titleInput.value.trim();
    if (browser) body.browser = browser;

    try {
      if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = 'Fetching video…'; }
      if (statusEl) statusEl.textContent = 'Fetching audio from the link — this can take a moment…';

      const response = await fetch('/api/upload-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      const res = await response.json();

      if (response.status === 401 && res.detail && res.detail.auth_required) {
        if (authPanel) authPanel.hidden = false;
        if (statusEl) statusEl.textContent = res.detail.message || 'Sign-in required.';
        if (window.a11y) window.a11y.announceToScreenReader('This video needs sign-in. Choose a browser to continue.');
        return;
      }

      if (!response.ok) throw new Error((typeof res.detail === 'string' && res.detail) || 'Could not fetch that video.');

      if (statusEl) statusEl.textContent = '';
      this.beginProcessing(res.lecture_id, res.title);

    } catch (err) {
      if (statusEl) statusEl.textContent = '';
      alert(`Video Fetch Error: ${err.message}`);
    } finally {
      if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = 'Start AI Accessibility Conversion'; }
    }
  }

  beginProcessing(lectureId, title) {
    this.currentLectureId = lectureId;
    this.currentLectureTitle = title;

    fetch(`/api/process/${lectureId}`, { method: 'POST' });

    this.closeUploadModal();
    this.showProcessingState();
    this.startStatusPolling(lectureId);
    this.loadRecentLectures();
  }

  setupDemoButtons() {
    const demoBtn1 = document.getElementById('btn-demo-quantum');
    const demoBtn2 = document.getElementById('btn-demo-neural');
    if (demoBtn1) demoBtn1.addEventListener('click', () => this.loadDemo('quantum'));
    if (demoBtn2) demoBtn2.addEventListener('click', () => this.loadDemo('neural'));
  }

  async loadDemo(demoKey) {
    try {
      if (window.a11y) window.a11y.announceToScreenReader('Loading demo lecture…');
      const response = await fetch(`/api/demo/load/${demoKey}`, { method: 'POST' });
      const res = await response.json();
      if (response.ok && res.lecture_id) {
        this.openExistingLecture(res.lecture_id, res.title);
        this.loadRecentLectures();
      }
    } catch (err) {
      console.error('Demo loading failed:', err);
    }
  }

  // ------------------------------------------------------------------
  // Processing Pipeline Polling
  // ------------------------------------------------------------------
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
            this.currentLectureTitle = statusData.title;
            this.fetchAndDisplayResults(lectureId);
            this.showResultsState();
            this.loadRecentLectures();
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
    if (stageText) stageText.textContent = statusData.current_stage || 'Processing…';
    if (titleText) titleText.textContent = statusData.title || 'Lecture Processing';

    const steps = document.querySelectorAll('.pipeline-step');
    if (statusData.stages && steps.length > 0) {
      statusData.stages.forEach((stg, idx) => {
        if (steps[idx]) steps[idx].className = `pipeline-step ${stg.status}`;
      });
    }
  }

  // ------------------------------------------------------------------
  // Results Rendering
  // ------------------------------------------------------------------
  async fetchAndDisplayResults(lectureId) {
    try {
      const response = await fetch(`/api/status/${lectureId}`);
      if (!response.ok) return;
      const fullData = await response.json();
      const data = fullData.data || {};

      this.currentLectureId = lectureId;
      this.currentLectureTitle = fullData.title;
      document.getElementById('topbar-lecture-title').textContent = fullData.title;
      this.highlightActiveLectureInSidebar(lectureId);

      window.NoteIcons && window.NoteIcons.reset();

      this.renderTranscript(data.transcript || {});
      this.renderNotes(data.simplified || {}, data.summary || {}, data.key_points || []);

      if (data.audio && data.audio.url) {
        this.audioPlayer.loadAudio(data.audio.url);
        const downloadAudioBtn = document.getElementById('audio-download-btn');
        if (downloadAudioBtn) {
          downloadAudioBtn.onclick = () => { window.location.href = `/api/audio/${lectureId}?download=true`; };
        }
      }

      if (data.braille && window.brailleViewer) {
        window.brailleViewer.loadBrailleData(data.braille, lectureId);
      }

      // Quiz + Chat load lazily the first time their tab is opened (see setupResultsTabs)
      this._quizLoadedFor = null;
      window.chatComponent.startSession(lectureId, fullData.title);

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
          <span class="timestamp-tag" onclick="window.appRouter.audioPlayer.seekToSeconds(${seg.start_seconds})">⏱ ${seg.timestamp}</span>
          <p>${seg.text}</p>
        </div>
      `;
    });
    container.innerHTML = html;
  }

  renderNotes(simplifiedData, summaryData, keyPointsList) {
    const easyBox = document.getElementById('notes-easy-box');
    const studyGrid = document.getElementById('notes-study-grid');
    const keypointsGrid = document.getElementById('notes-keypoints-grid');
    const keywordsGrid = document.getElementById('notes-keywords-grid');

    this.speakTextRegistry = [];

    if (easyBox) {
      easyBox.innerHTML = `
        <div class="notes-easy-card">
          <h3>✨ Easy Explanation</h3>
          <p>${this.escapeHtml(simplifiedData.easy_explanation || '')}</p>
          ${simplifiedData.simplified_content ? `<div style="margin-top:14px; white-space:pre-wrap;">${this.escapeHtml(simplifiedData.simplified_content)}</div>` : ''}
        </div>
      `;
    }

    if (studyGrid) {
      studyGrid.innerHTML = (simplifiedData.study_notes || []).map(note =>
        this.buildPictureCard(note.heading, note.content, `${note.heading} ${note.content}`)
      ).join('') || '<p class="muted-text">No structured notes for this lecture.</p>';
    }

    if (keypointsGrid) {
      keypointsGrid.innerHTML = (keyPointsList || []).map((kp, i) =>
        this.buildPictureCard(`Key Point ${i + 1}`, kp, kp)
      ).join('') || '<p class="muted-text">No key points extracted.</p>';
    }

    if (keywordsGrid) {
      keywordsGrid.innerHTML = (summaryData.keywords || []).map(kw =>
        this.buildPictureCard(kw.term, kw.definition, kw.term)
      ).join('') || '<p class="muted-text">No keywords extracted.</p>';
    }

    // Attach "listen aloud" handlers once per render, via delegation-safe lookup
    // (avoids embedding raw note text inside HTML attributes).
    document.querySelectorAll('#tab-notes .listen-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const idx = parseInt(btn.getAttribute('data-speak-idx'), 10);
        this.speakText(this.speakTextRegistry[idx]);
      });
    });
  }

  buildPictureCard(heading, bodyText, iconSeedText) {
    const picture = window.NoteIcons ? window.NoteIcons.pictureFor(iconSeedText || heading) : '';
    const idx = this.speakTextRegistry.length;
    this.speakTextRegistry.push(`${heading}. ${bodyText || ''}`);
    return `
      <div class="note-picture-card">
        ${picture}
        <div class="note-card-body">
          <div class="note-card-heading">
            <strong>${this.escapeHtml(heading)}</strong>
            <button type="button" class="listen-btn" data-speak-idx="${idx}" aria-label="Listen to this note aloud">🔊</button>
          </div>
          <p>${this.escapeHtml(bodyText || '')}</p>
        </div>
      </div>
    `;
  }

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text == null ? '' : String(text);
    return div.innerHTML;
  }

  speakText(text) {
    if (!('speechSynthesis' in window) || !text) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 0.95;
    window.speechSynthesis.speak(utterance);
  }

  // ------------------------------------------------------------------
  // Download-as-PDF (browser print, scoped to a single tab at a time)
  // ------------------------------------------------------------------
  setupPdfDownloadButtons() {
    const configs = [
      { btnId: 'btn-download-notes-pdf', tabId: 'tab-notes', headerId: 'print-notes-header', label: 'Simplified Notes' },
      { btnId: 'btn-download-braille-pdf', tabId: 'tab-braille', headerId: 'print-braille-header', label: 'Braille Ready Format' }
    ];

    configs.forEach(cfg => {
      const btn = document.getElementById(cfg.btnId);
      if (btn) btn.addEventListener('click', () => this.downloadTabAsPdf(cfg));
    });

    // Safety net: if the browser never fires 'afterprint' (rare, some
    // mobile browsers), make sure we don't leave the page stuck in print mode.
    window.addEventListener('afterprint', () => this.exitPdfPrintMode());
  }

  downloadTabAsPdf({ tabId, headerId, label }) {
    const header = document.getElementById(headerId);
    if (header) {
      const title = this.currentLectureTitle || 'Lecture';
      const dateStr = new Date().toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' });
      header.innerHTML = `
        <h1>AccessLearn AI — ${this.escapeHtml(label)}</h1>
        <p>${this.escapeHtml(title)} · Generated ${dateStr}</p>
      `;
    }

    const tabEl = document.getElementById(tabId);
    if (tabEl) tabEl.classList.add('print-target');
    document.body.classList.add('printing-pdf');
    if (window.a11y) window.a11y.announceToScreenReader(`Opening print dialog. Choose "Save as PDF" to download your ${label}.`);

    // Give the browser a frame to apply print styles before the dialog opens.
    setTimeout(() => {
      window.print();
      // Some browsers (older Safari) don't reliably fire 'afterprint'.
      setTimeout(() => this.exitPdfPrintMode(), 1000);
    }, 50);
  }

  exitPdfPrintMode() {
    document.body.classList.remove('printing-pdf');
    document.querySelectorAll('.print-target').forEach(el => el.classList.remove('print-target'));
  }

  setupResultsTabs() {
    const tabBtns = document.querySelectorAll('.tab-btn');
    tabBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        const targetTab = btn.getAttribute('data-tab');

        tabBtns.forEach(b => { b.classList.remove('active'); b.setAttribute('aria-selected', 'false'); });
        btn.classList.add('active');
        btn.setAttribute('aria-selected', 'true');

        document.querySelectorAll('.tab-content').forEach(content => {
          content.classList.toggle('active', content.id === targetTab);
        });

        if (targetTab === 'tab-quiz' && this.currentLectureId && this._quizLoadedFor !== this.currentLectureId) {
          this._quizLoadedFor = this.currentLectureId;
          window.quizComponent.loadQuiz(this.currentLectureId);
        }

        if (window.a11y) window.a11y.announceToScreenReader(`Switched to tab ${btn.textContent.trim()}`);
      });
    });
  }

  // ------------------------------------------------------------------
  // Sidebar Lecture List
  // ------------------------------------------------------------------
  async loadRecentLectures() {
    const listEl = document.getElementById('sidebar-lectures-list');
    if (!listEl) return;

    try {
      const response = await fetch('/api/lectures');
      const data = await response.json();
      const lectures = data.lectures || [];

      if (lectures.length === 0) {
        listEl.innerHTML = '<p class="empty-lectures-note">No lectures yet. Upload one to begin.</p>';
        return;
      }

      const statusIcon = { completed: '✔', processing: '⏳', queued: '⏳' };

      listEl.innerHTML = lectures.map(lec => {
        const isDemo = lec.id.startsWith('demo-');
        return `
          <div class="lecture-list-item${lec.id === this.currentLectureId ? ' active' : ''}" data-lecture-id="${lec.id}" role="listitem">
            <div class="lecture-item-icon" aria-hidden="true">${statusIcon[lec.status] || '📄'}</div>
            <div class="lecture-item-body">
              <div class="lecture-item-title">${lec.title}</div>
              <div class="lecture-item-meta">${lec.status} · ${lec.created_at}</div>
            </div>
            ${isDemo ? '' : `<button type="button" class="icon-btn lecture-delete-btn" data-lecture-id="${lec.id}" aria-label="Delete lecture ${lec.title}" title="Delete lecture">🗑</button>`}
          </div>
        `;
      }).join('');

      listEl.querySelectorAll('.lecture-list-item').forEach(item => {
        item.addEventListener('click', (e) => {
          if (e.target.closest('.lecture-delete-btn')) return;
          const id = item.getAttribute('data-lecture-id');
          const lec = lectures.find(l => l.id === id);
          if (!lec) return;
          if (lec.status === 'completed') {
            this.openExistingLecture(id, lec.title);
          } else {
            this.currentLectureId = id;
            this.showProcessingState();
            this.startStatusPolling(id);
          }
        });
      });

      listEl.querySelectorAll('.lecture-delete-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
          e.stopPropagation();
          this.deleteLecture(btn.getAttribute('data-lecture-id'));
        });
      });

    } catch (err) {
      console.error('Failed loading recent lectures:', err);
    }
  }

  async deleteLecture(lectureId) {
    const confirmed = window.confirm('Delete this lecture and its uploaded file permanently? This cannot be undone.');
    if (!confirmed) return;

    try {
      const response = await fetch(`/api/lectures/${lectureId}`, { method: 'DELETE' });
      const res = await response.json();
      if (!response.ok) throw new Error(res.detail || 'Delete failed');

      if (this.currentLectureId === lectureId) this.showEmptyState();
      this.loadRecentLectures();
      if (window.a11y) window.a11y.announceToScreenReader('Lecture deleted.');
    } catch (err) {
      alert(`Could not delete lecture: ${err.message}`);
    }
  }

  highlightActiveLectureInSidebar(lectureId) {
    document.querySelectorAll('.lecture-list-item').forEach(item => {
      item.classList.toggle('active', item.getAttribute('data-lecture-id') === lectureId);
    });
  }

  openExistingLecture(lectureId, title) {
    this.currentLectureId = lectureId;
    this.currentLectureTitle = title;
    this.fetchAndDisplayResults(lectureId);
    this.showResultsState();
  }
}

// Global App Router Instance
document.addEventListener('DOMContentLoaded', () => {
  window.appRouter = new AccessLearnApp();
});
