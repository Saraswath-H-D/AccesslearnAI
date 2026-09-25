/**
 * AccessLearn AI - Main Frontend Application Router & Controller
 */

class AccessLearnApp {
  constructor() {
    this.currentLectureId = null;
    this.statusPollInterval = null;
    this.audioPlayer = null;
    this.uploadMode = 'file'; // 'file' | 'youtube'
    this.currentLanguage = 'en'; // 'en' | 'hi' | 'kn'
    this.init();
  }

  init() {
    this.audioPlayer = new AccessibleAudioPlayer('main-audio-element');
    if (window.mermaid) {
      mermaid.initialize({ startOnLoad: false, theme: 'default' });
    }
    this.setupViewNavigation();
    this.setupUploadModeToggle();
    this.setupFileUpload();
    this.setupYouTubeInput();
    this.setupResultsTabs();
    this.setupLanguageSelector();
    this.setupTranscriptSearch();
    this.setupAudioGeneration();
    this.setupBrailleGeneration();
    this.loadRecentLectures();

    // Default to Landing view
    this.showView('landing-view');
  }

  setupLanguageSelector() {
    const select = document.getElementById('language-select');
    if (!select) return;
    select.addEventListener('change', () => {
      this.currentLanguage = select.value;
      if (this.currentLectureId) {
        this.loadLanguageDependentContent(this.currentLectureId, this.currentLanguage);
      }
    });
  }

  setupTranscriptSearch() {
    const input = document.getElementById('transcript-search');
    if (!input) return;
    input.addEventListener('input', () => {
      const q = input.value.trim().toLowerCase();
      const segments = this._lastTranscriptSegments || [];
      const filtered = q ? segments.filter(s => s.text.toLowerCase().includes(q)) : segments;
      this._renderTranscriptSegments(filtered);
    });
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

      this.currentLectureId = lectureId;
      this.currentLanguage = 'en';
      const langSelect = document.getElementById('language-select');
      if (langSelect) langSelect.value = 'en';

      // Set Lecture Title
      const titleEl = document.getElementById('results-lecture-title');
      if (titleEl) titleEl.textContent = fullData.title;

      // 1. Original uploaded video/audio (seeked by transcript timestamps)
      this.loadSourcePlayer(lectureId, data.video || {});

      // 2. Render Transcript (always English/original -- verbatim ASR, not translated)
      this.renderTranscript(data.transcript || {});

      // 3. Wire up the PDF notes download button
      const pdfBtn = document.getElementById('notes-pdf-download-btn');
      if (pdfBtn) {
        pdfBtn.onclick = () => {
          window.location.href = `/api/notes/pdf/${lectureId}`;
        };
      }

      // 4. Wire up the delete button for this lecture
      const deleteBtn = document.getElementById('results-delete-btn');
      if (deleteBtn) {
        deleteBtn.onclick = () => this.deleteLecture(lectureId, fullData.title || 'this lecture');
      }

      // 5. Simplified Notes / Summary / Key Points (language-aware, fetched
      // via dedicated endpoints so switching language later just re-calls this)
      await this.loadLanguageDependentContent(lectureId, this.currentLanguage);

      // Reset the Audio/Braille tabs to their not-yet-generated state --
      // both are explicit "choose content + language, then Generate" flows.
      const audioStatus = document.getElementById('audio-gen-status');
      if (audioStatus) audioStatus.textContent = '';
      document.getElementById('main-audio-element')?.removeAttribute('src');
      const brailleNotice = document.getElementById('braille-limitation-notice');
      if (brailleNotice) brailleNotice.classList.add('hidden');
      const brailleBox = document.getElementById('braille-display-box');
      if (brailleBox) brailleBox.textContent = 'Choose content and click "Generate Braille".';

      this.loadRecentLectures();

    } catch (err) {
      console.error('Error fetching lecture results:', err);
    }
  }

  loadSourcePlayer(lectureId, videoInfo) {
    const videoEl = document.getElementById('source-video-player');
    const audioEl = document.getElementById('source-audio-player');
    if (!videoEl || !audioEl) return;

    const src = `/api/video/${lectureId}`;
    if (videoInfo.is_video) {
      videoEl.src = src;
      videoEl.style.display = 'block';
      audioEl.style.display = 'none';
      this._sourceMediaEl = videoEl;
    } else {
      audioEl.src = src;
      audioEl.style.display = 'block';
      videoEl.style.display = 'none';
      this._sourceMediaEl = audioEl;
    }
  }

  async loadLanguageDependentContent(lectureId, lang) {
    const statusEl = document.getElementById('language-status');
    if (statusEl) statusEl.textContent = lang === 'en' ? '' : 'Translating with Gemini... this may take a moment on first request.';

    try {
      const [notesResp, summaryResp] = await Promise.all([
        fetch(`/api/simplified/${lectureId}?lang=${lang}`),
        fetch(`/api/summary/${lectureId}?lang=${lang}`),
      ]);
      const notes = notesResp.ok ? await notesResp.json() : {};
      const summaryData = summaryResp.ok ? await summaryResp.json() : {};

      this.renderSimplified(notes);
      this.renderSummary(summaryData.summary || {});
      this.renderKeyPoints(summaryData.key_points || []);
      if (statusEl) statusEl.textContent = '';
    } catch (err) {
      console.error('Failed to load language-dependent content:', err);
      if (statusEl) statusEl.textContent = `Error loading ${lang} content: ${err.message}`;
    }
  }

  renderTranscript(transcriptData) {
    this._lastTranscriptFullText = transcriptData.full_text || '';
    this._lastTranscriptSegments = transcriptData.segments || [];
    this._renderTranscriptSegments(this._lastTranscriptSegments);
  }

  _renderTranscriptSegments(segments) {
    const container = document.getElementById('transcript-content-box');
    if (!container) return;

    if (segments.length === 0) {
      container.innerHTML = `<p>${this._lastTranscriptFullText || 'No matching transcript segments.'}</p>`;
      return;
    }

    let html = '';
    segments.forEach(seg => {
      html += `
        <div class="transcript-segment">
          <span class="timestamp-tag" onclick="window.appRouter.seekSourcePlayer(${seg.start_seconds})">
            ⏱ ${seg.timestamp}
          </span>
          <p>${seg.text}</p>
        </div>
      `;
    });
    container.innerHTML = html;
  }

  seekSourcePlayer(seconds) {
    const el = this._sourceMediaEl;
    if (!el) return;
    el.currentTime = seconds;
    el.play().catch(() => {});
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    if (window.a11y) window.a11y.announceToScreenReader(`Video seeked to ${Math.floor(seconds / 60)} minutes ${Math.floor(seconds % 60)} seconds`);
  }

  renderSimplified(notesData) {
    const titleBox = document.getElementById('simplified-title-box');
    const notesBox = document.getElementById('simplified-notes-box');
    if (titleBox) titleBox.textContent = notesData.title || 'Simplified Notes';
    if (!notesBox) return;

    const sections = notesData.sections || [];
    if (sections.length === 0) {
      notesBox.innerHTML = '<p style="color: var(--text-secondary);">Simplified Notes are not available for this lecture yet.</p>';
      return;
    }

    notesBox.innerHTML = sections.map((s, idx) => this._renderNoteSection(s, idx)).join('');

    // Render each section's flowchart (only sections that actually have one --
    // never forced) with Mermaid, and load real extracted-frame visuals.
    if (window.mermaid) {
      mermaid.run({ querySelector: '.note-mermaid-diagram' }).catch(err => console.warn('Mermaid render error:', err));
    }
    notesBox.querySelectorAll('[data-seek]').forEach(btn => {
      btn.addEventListener('click', () => this.seekSourcePlayer(parseFloat(btn.dataset.seek)));
    });
  }

  _renderNoteSection(section, idx) {
    const escapeHtml = (str) => {
      const div = document.createElement('div');
      div.textContent = str || '';
      return div.innerHTML;
    };

    let html = `<div class="note-section-card">`;
    html += `<div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">`;
    html += `<h3 style="margin:0;">${escapeHtml(section.heading)}</h3>`;
    if (section.startTime !== undefined && section.startTime !== null) {
      html += `<button class="note-timestamp-btn" data-seek="${section.startTime}">⏱ ${this._formatSeconds(section.startTime)} - ${this._formatSeconds(section.endTime)}</button>`;
    }
    html += `</div>`;
    html += `<p style="margin-top:12px; line-height:1.7; white-space:pre-wrap;">${escapeHtml(section.content)}</p>`;

    // Real extracted video frame -- only rendered when the notes generator
    // decided a specific visual genuinely helps this section (Section 11-14
    // of the brief: never a random/forced image).
    if (section.visualUrl) {
      html += `
        <figure class="note-visual-figure">
          <img src="${section.visualUrl}" alt="${escapeHtml(section.visualCaption || 'Relevant visual from the video')}" loading="lazy">
          <figcaption><strong>Related Visual:</strong> ${escapeHtml(section.visualCaption)}</figcaption>
        </figure>`;
    }

    // Dynamic, video-grounded flowchart -- only rendered when this section
    // actually describes a real process (never a generic/forced diagram).
    if (section.flowchart) {
      html += `
        <div class="note-flowchart-box">
          <h4>${escapeHtml(section.flowchart.title || 'Process Flowchart')}</h4>
          <div class="note-mermaid-diagram mermaid">${section.flowchart.mermaid}</div>
          <details>
            <summary>Accessible text description of this flowchart (for screen readers)</summary>
            <div class="note-flowchart-accessible-text">${escapeHtml(section.flowchart.accessibleText)}</div>
          </details>
        </div>`;
    }

    html += `</div>`;
    return html;
  }

  _formatSeconds(seconds) {
    if (seconds === undefined || seconds === null || isNaN(seconds)) return '00:00';
    const m = Math.floor(seconds / 60).toString().padStart(2, '0');
    const s = Math.floor(seconds % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  }

  renderSummary(summaryData) {
    const shortBox = document.getElementById('summary-short-box');
    const detailedBox = document.getElementById('summary-detailed-box');
    if (shortBox) shortBox.textContent = summaryData.shortSummary || 'Summary not available.';
    if (detailedBox) detailedBox.textContent = summaryData.detailedSummary || '';
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

  setupAudioGeneration() {
    const btn = document.getElementById('audio-generate-btn');
    const statusEl = document.getElementById('audio-gen-status');
    const downloadBtn = document.getElementById('audio-download-btn');
    if (!btn) return;

    btn.addEventListener('click', async () => {
      if (!this.currentLectureId) return;
      const source = document.getElementById('audio-source-select').value;
      const lang = this.currentLanguage;
      statusEl.textContent = 'Generating audio narration... this can take a moment.';
      btn.disabled = true;
      try {
        const url = `/api/audio/${this.currentLectureId}?lang=${lang}&source=${source}`;
        // HEAD-equivalent check via a real fetch so a real generation error
        // (e.g. Gemini unavailable for the underlying content) surfaces here
        // instead of failing silently inside the <audio> element.
        const check = await fetch(url);
        if (!check.ok) {
          const err = await check.json().catch(() => ({}));
          throw new Error(err.detail || `HTTP ${check.status}`);
        }
        this.audioPlayer.loadAudio(url);
        if (downloadBtn) downloadBtn.onclick = () => { window.location.href = `${url}&download=true`; };
        statusEl.textContent = `Ready: ${source.replace('_', ' ')} in ${lang.toUpperCase()}.`;
        if (window.a11y) window.a11y.announceToScreenReader('Audio generated and ready to play.');
      } catch (err) {
        statusEl.textContent = `Error: ${err.message}`;
      } finally {
        btn.disabled = false;
      }
    });
  }

  setupBrailleGeneration() {
    const btn = document.getElementById('braille-generate-btn');
    const statusInfo = document.getElementById('braille-stats-info');
    const notice = document.getElementById('braille-limitation-notice');
    const box = document.getElementById('braille-display-box');
    const downloadBtn = document.getElementById('braille-download-btn');
    if (!btn) return;

    btn.addEventListener('click', async () => {
      if (!this.currentLectureId) return;
      const source = document.getElementById('braille-source-select').value;
      const lang = this.currentLanguage;
      notice.classList.add('hidden');
      box.textContent = 'Generating Braille...';

      try {
        const url = `/api/braille/${this.currentLectureId}?lang=${lang}&source=${source}`;
        const response = await fetch(url);
        if (response.status === 422) {
          const err = await response.json();
          notice.textContent = err.detail;
          notice.classList.remove('hidden');
          box.textContent = '';
          statusInfo.textContent = 'Braille not available for this language.';
          return;
        }
        if (!response.ok) {
          const err = await response.json().catch(() => ({}));
          throw new Error(err.detail || `HTTP ${response.status}`);
        }
        const text = await response.text();
        box.textContent = text;
        statusInfo.textContent = `Grade 1/2 English Braille | ${text.split('\n').length} lines | 40-cell format`;
        if (downloadBtn) downloadBtn.onclick = () => { window.location.href = `${url}&download=true`; };
        // Keep the legacy braille_viewer.js Copy button (still wired to its
        // own addEventListener from page load) working against this newly
        // generated text -- only one encoding is available from the on-
        // demand endpoint now, so both its fields get the same value.
        if (window.brailleViewer) {
          window.brailleViewer.unicodeText = text;
          window.brailleViewer.brfText = text;
          window.brailleViewer.lectureId = this.currentLectureId;
        }
        if (window.a11y) window.a11y.announceToScreenReader('Braille generated.');
      } catch (err) {
        box.textContent = `Error generating Braille: ${err.message}`;
      }
    });
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
          <div style="display: flex; justify-content: space-between; align-items: center; padding: 16px; background: var(--bg-surface); border: 1px solid var(--border-color); border-radius: var(--radius-sm); gap: 12px; flex-wrap: wrap;">
            <div>
              <strong style="font-size: 1.1rem;">${lec.title}</strong>
              <div style="font-size: 0.85rem; color: var(--text-muted);">${lec.created_at} &middot; Stored on server</div>
            </div>
            <div style="display: flex; gap: 8px; flex-wrap: wrap;">
              <button class="btn btn-outline" onclick="window.appRouter.openExistingLecture('${lec.id}')">
                View Formats
              </button>
              <button class="btn btn-outline" style="color: var(--danger); border-color: var(--danger);" onclick="window.appRouter.deleteLecture('${lec.id}', '${lec.title.replace(/'/g, "\\'")}')">
                🗑 Delete
              </button>
            </div>
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

  async deleteLecture(lectureId, lectureTitle) {
    const confirmed = confirm(`Delete "${lectureTitle}" permanently? This removes the uploaded file, audio, braille, and notes from the server. This cannot be undone.`);
    if (!confirmed) return;

    try {
      const response = await fetch(`/api/lectures/${lectureId}`, { method: 'DELETE' });
      const res = await response.json();

      if (!response.ok) {
        throw new Error(res.detail || 'Delete failed');
      }

      if (window.a11y) window.a11y.announceToScreenReader(`Lecture "${lectureTitle}" deleted.`);

      // If the deleted lecture is currently open in results view, go back to the dashboard
      if (this.currentLectureId === lectureId) {
        this.currentLectureId = null;
        this.showView('dashboard-view');
      }

      this.loadRecentLectures();
    } catch (err) {
      alert(`Delete Error: ${err.message}`);
    }
  }
}

// Global App Router Instance
document.addEventListener('DOMContentLoaded', () => {
  window.appRouter = new AccessLearnApp();
});
