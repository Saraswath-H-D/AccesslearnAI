/**
 * AccessLearn AI - AI Doubt-Solving Chat Component
 */
class ChatComponent {
  constructor() {
    this.lectureId = null;
    this.messagesBox = document.getElementById('chat-messages-box');
    this.form = document.getElementById('chat-input-form');
    this.input = document.getElementById('chat-input-field');
    this.suggestionsBox = document.getElementById('chat-suggestions-box');
    this.setupListeners();
  }

  setupListeners() {
    if (this.form) {
      this.form.addEventListener('submit', (e) => {
        e.preventDefault();
        this.sendMessage(this.input.value);
      });
    }
    if (this.input) {
      this.input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          this.sendMessage(this.input.value);
        }
      });
    }
    if (this.suggestionsBox) {
      this.suggestionsBox.addEventListener('click', (e) => {
        const chip = e.target.closest('.chat-chip');
        if (chip) this.sendMessage(chip.textContent.trim());
      });
    }
  }

  startSession(lectureId, lectureTitle) {
    this.lectureId = lectureId;
    if (this.messagesBox) {
      this.messagesBox.innerHTML = `
        <div class="chat-bubble ai">
          👋 Hi! I'm your AI study buddy for <strong>${lectureTitle}</strong>. Ask me anything about this
          lecture — I'll answer using only what's in it, in simple language.
        </div>
      `;
    }
    if (this.input) this.input.value = '';
  }

  async sendMessage(text) {
    text = (text || '').trim();
    if (!text || !this.lectureId) return;

    this.appendBubble(text, 'user');
    if (this.input) this.input.value = '';

    const typingId = this.appendBubble('Thinking…', 'ai', true);

    try {
      const response = await fetch(`/api/chat/${this.lectureId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text })
      });
      const data = await response.json();
      this.updateBubble(typingId, response.ok ? data.answer : (data.detail || "Sorry, I couldn't process that right now."));
    } catch (err) {
      this.updateBubble(typingId, "Sorry, something went wrong reaching the AI assistant. Please try again.");
      console.error('Chat send error:', err);
    }

    if (window.a11y) window.a11y.announceToScreenReader('AI assistant replied.');
  }

  appendBubble(text, who, isTyping = false) {
    if (!this.messagesBox) return null;
    const id = `msg-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const bubble = document.createElement('div');
    bubble.id = id;
    bubble.className = `chat-bubble ${who}${isTyping ? ' typing' : ''}`;
    bubble.textContent = text;
    this.messagesBox.appendChild(bubble);
    this.messagesBox.scrollTop = this.messagesBox.scrollHeight;
    return id;
  }

  updateBubble(id, text) {
    if (!id) return;
    const el = document.getElementById(id);
    if (el) {
      el.classList.remove('typing');
      el.textContent = text;
      this.messagesBox.scrollTop = this.messagesBox.scrollHeight;
    }
  }
}

window.chatComponent = new ChatComponent();
