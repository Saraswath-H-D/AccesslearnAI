/**
 * AccessLearn AI - Interactive Accessible MCQ Quiz Component
 */
class QuizComponent {
  constructor() {
    this.lectureId = null;
    this.questions = [];
    this.answers = {}; // questionId -> selected option index
    this.checked = {}; // questionId -> true once answer revealed
    this.container = document.getElementById('quiz-body-box');
    this.resultBox = document.getElementById('quiz-result-box');
  }

  async loadQuiz(lectureId) {
    this.lectureId = lectureId;
    this.answers = {};
    this.checked = {};
    if (!this.container) return;

    this.container.innerHTML = `<p class="muted-text">🧩 Building your quiz from this lecture...</p>`;
    if (this.resultBox) this.resultBox.innerHTML = '';

    try {
      const response = await fetch(`/api/quiz/${lectureId}`);
      if (!response.ok) throw new Error('Quiz not available yet.');
      const data = await response.json();
      this.questions = data.questions || [];
      this.render();
    } catch (err) {
      this.container.innerHTML = `<p class="muted-text">Could not load a quiz for this lecture yet. Please try again shortly.</p>`;
      console.error('Quiz load error:', err);
    }
  }

  render() {
    if (!this.container) return;
    if (this.questions.length === 0) {
      this.container.innerHTML = `<p class="muted-text">No quiz questions could be generated for this lecture.</p>`;
      return;
    }

    let html = '';
    this.questions.forEach((q, qi) => {
      html += `
        <fieldset class="quiz-question-card" data-qid="${q.id}">
          <legend>Question ${qi + 1} of ${this.questions.length}</legend>
          <p class="quiz-question-text">${q.question}</p>
          <div class="quiz-options" role="radiogroup">
      `;
      q.options.forEach((opt, oi) => {
        html += `
            <label class="quiz-option" data-qid="${q.id}" data-oi="${oi}">
              <input type="radio" name="${q.id}" value="${oi}">
              <span>${opt}</span>
            </label>
        `;
      });
      html += `
          </div>
          <div class="quiz-feedback" id="feedback-${q.id}" aria-live="polite"></div>
        </fieldset>
      `;
    });

    html += `
      <div class="quiz-actions">
        <button type="button" id="quiz-submit-btn" class="btn btn-primary">✅ Submit Quiz</button>
        <button type="button" id="quiz-retry-btn" class="btn btn-outline" hidden>🔄 Retake Quiz</button>
      </div>
    `;

    this.container.innerHTML = html;
    this.attachListeners();
  }

  attachListeners() {
    this.container.querySelectorAll('input[type="radio"]').forEach(input => {
      input.addEventListener('change', (e) => {
        const qid = e.target.name;
        this.answers[qid] = parseInt(e.target.value, 10);
        this.container.querySelectorAll(`label.quiz-option[data-qid="${qid}"]`).forEach(l => l.classList.remove('selected'));
        e.target.closest('label').classList.add('selected');
      });
    });

    const submitBtn = document.getElementById('quiz-submit-btn');
    if (submitBtn) submitBtn.addEventListener('click', () => this.submitQuiz());

    const retryBtn = document.getElementById('quiz-retry-btn');
    if (retryBtn) retryBtn.addEventListener('click', () => {
      this.answers = {};
      this.checked = {};
      this.render();
      if (this.resultBox) this.resultBox.innerHTML = '';
    });
  }

  submitQuiz() {
    const unanswered = this.questions.filter(q => this.answers[q.id] === undefined);
    if (unanswered.length > 0) {
      if (window.a11y) window.a11y.announceToScreenReader(`Please answer all questions. ${unanswered.length} remaining.`);
      const firstCard = this.container.querySelector(`fieldset[data-qid="${unanswered[0].id}"]`);
      if (firstCard) firstCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
      return;
    }

    let score = 0;
    this.questions.forEach(q => {
      const selected = this.answers[q.id];
      const isCorrect = selected === q.correct_index;
      if (isCorrect) score++;

      const card = this.container.querySelector(`fieldset[data-qid="${q.id}"]`);
      const feedback = document.getElementById(`feedback-${q.id}`);
      card.querySelectorAll('label.quiz-option').forEach(label => {
        const oi = parseInt(label.getAttribute('data-oi'), 10);
        label.querySelector('input').disabled = true;
        if (oi === q.correct_index) label.classList.add('correct');
        else if (oi === selected) label.classList.add('incorrect');
      });

      if (feedback) {
        feedback.innerHTML = isCorrect
          ? `✅ Correct! ${q.explanation || ''}`
          : `❌ Not quite. ${q.explanation || ''}`;
        feedback.classList.add(isCorrect ? 'correct-text' : 'incorrect-text');
      }
    });

    const pct = Math.round((score / this.questions.length) * 100);
    if (this.resultBox) {
      this.resultBox.innerHTML = `
        <div class="quiz-score-card">
          <div class="quiz-score-value">${score} / ${this.questions.length}</div>
          <div class="quiz-score-label">${pct}% correct — ${this.scoreMessage(pct)}</div>
        </div>
      `;
    }

    document.getElementById('quiz-submit-btn').hidden = true;
    const retryBtn = document.getElementById('quiz-retry-btn');
    if (retryBtn) retryBtn.hidden = false;

    if (window.a11y) window.a11y.announceToScreenReader(`Quiz submitted. You scored ${score} out of ${this.questions.length}.`);
  }

  scoreMessage(pct) {
    if (pct === 100) return "Perfect score! Great job! 🎉";
    if (pct >= 70) return "Nice work — you understood most of it!";
    if (pct >= 40) return "Good start — review the Simplified Notes tab and try again.";
    return "Keep going — rewatch the Simplified Notes and Transcript, then retake the quiz.";
  }
}

window.quizComponent = new QuizComponent();
