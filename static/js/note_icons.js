/**
 * AccessLearn AI - Simple Picture Icon Library
 *
 * Pairs a small, friendly line-drawing with each note/keyword card so
 * students who find dense text hard to process (cognitive disabilities,
 * lower literacy, ESL) get a visual anchor alongside the plain-language
 * text. Pure inline SVG - no network image requests, works offline,
 * themeable via currentColor.
 */
(function () {
  const ICONS = {
    brain: `<path d="M9 3.5c-2 0-3.6 1.6-3.6 3.6 0 .5.1 1 .3 1.4C4.6 9 4 10.1 4 11.4c0 1.5.9 2.7 2.2 3.3-.1.4-.2.8-.2 1.3 0 2 1.6 3.6 3.6 3.6.6 0 1.1-.1 1.6-.4"/><path d="M15 3.5c2 0 3.6 1.6 3.6 3.6 0 .5-.1 1-.3 1.4 1.1.5 1.7 1.6 1.7 2.9 0 1.5-.9 2.7-2.2 3.3.1.4.2.8.2 1.3 0 2-1.6 3.6-3.6 3.6-.6 0-1.1-.1-1.6-.4"/><path d="M12 4v15.5"/><path d="M9 8.5c1 .8 2 .8 3 0M9 12.5c1 .8 2 .8 3 0M15 8.5c-1 .8-2 .8-3 0M15 12.5c-1 .8-2 .8-3 0"/>`,
    atom: `<circle cx="12" cy="12" r="1.8" fill="currentColor" stroke="none"/><ellipse cx="12" cy="12" rx="9" ry="3.6"/><ellipse cx="12" cy="12" rx="9" ry="3.6" transform="rotate(60 12 12)"/><ellipse cx="12" cy="12" rx="9" ry="3.6" transform="rotate(120 12 12)"/>`,
    bulb: `<path d="M9 18h6"/><path d="M10 21h4"/><path d="M12 3a6 6 0 0 0-3.6 10.8c.6.5 1 1.2 1.1 2h5c.1-.8.5-1.5 1.1-2A6 6 0 0 0 12 3Z"/><path d="M12 7.5v3M10 9.5h4"/>`,
    book: `<path d="M4 5.5c2.5-1 5-1 7 0v14c-2-1-4.5-1-7 0Z"/><path d="M20 5.5c-2.5-1-5-1-7 0v14c2-1 4.5-1 7 0Z"/>`,
    gear: `<circle cx="12" cy="12" r="3"/><path d="M12 3.5v2M12 18.5v2M20.5 12h-2M5.5 12h-2M17.8 6.2l-1.4 1.4M7.6 16.4l-1.4 1.4M17.8 17.8l-1.4-1.4M7.6 7.6 6.2 6.2"/>`,
    chart: `<path d="M4 20V4"/><path d="M4 20h16"/><rect x="7" y="12" width="2.6" height="8" rx="0.5"/><rect x="12" y="8" width="2.6" height="12" rx="0.5"/><rect x="17" y="14" width="2.6" height="6" rx="0.5"/>`,
    network: `<circle cx="6" cy="6" r="2"/><circle cx="18" cy="6" r="2"/><circle cx="6" cy="18" r="2"/><circle cx="18" cy="18" r="2"/><circle cx="12" cy="12" r="2.4"/><path d="M7.6 7.2 10 10.5M16.4 7.2 14 10.5M7.6 16.8 10 13.5M16.4 16.8 14 13.5"/>`,
    computer: `<rect x="3.5" y="5" width="17" height="11" rx="1.4"/><path d="M8 20h8M12 16v4"/><path d="M7.5 9.5l2 2-2 2M12.5 13.5h2.5"/>`,
    dna: `<path d="M7 3c0 5 10 6 10 11 0 4-3 6-3 6"/><path d="M17 3c0 5-10 6-10 11 0 4 3 6 3 6"/><path d="M8 7h8M7.3 11h9.4M8 15h8"/>`,
    formula: `<path d="M6 4h5l-2 8 2 8H6"/><circle cx="17" cy="8" r="2"/><path d="M14.5 18.5l5-6M14.5 12.5l5 6"/>`,
    globe: `<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.6 2.4 4 5.3 4 8.5s-1.4 6.1-4 8.5c-2.6-2.4-4-5.3-4-8.5s1.4-6.1 4-8.5Z"/>`,
    drop: `<path d="M12 3.5C9 8 5.5 12 5.5 15.5a6.5 6.5 0 0 0 13 0C18.5 12 15 8 12 3.5Z"/>`,
    leaf: `<path d="M5 19C4 11 9 4.5 19 4.5 19 13.5 13 19 5 19Z"/><path d="M5 19c2-3.5 5-6.5 9.5-9"/>`,
    clock: `<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3.2 2"/>`,
    scale: `<path d="M12 3.5v17M7 6.5h10"/><path d="M4.5 6.5 7 12a2.5 2.5 0 0 1-5 0Z"/><path d="M19.5 6.5 17 12a2.5 2.5 0 0 0 5 0Z"/><path d="M9 20.5h6"/>`,
    coin: `<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5v9M9.5 9.5c0-1.1 1.1-2 2.5-2s2.5.9 2.5 2c0 2.5-5 1.5-5 4 0 1.1 1.1 2 2.5 2s2.5-.9 2.5-2"/>`,
    heart: `<path d="M12 20s-7.5-4.7-9.7-9.4C.9 7 2.4 4 5.6 3.4c2-.4 3.8.6 4.9 2.2 1.1-1.6 2.9-2.6 4.9-2.2 3.2.6 4.7 3.6 3.3 7.2C19.5 15.3 12 20 12 20Z"/>`,
    rocket: `<path d="M12 3.5c3 1.5 5 5 4.5 9.5l-2.2 2.2h-4.6l-2.2-2.2C7 8.5 9 5 12 3.5Z"/><circle cx="12" cy="10" r="1.6"/><path d="M9.5 15 7 20l3-1.5M14.5 15l2.5 5-3-1.5"/>`,
    shield: `<path d="M12 3.5 19 6v6c0 4.5-3 7.5-7 8.5-4-1-7-4-7-8.5V6Z"/><path d="M9 12l2 2 4-4.5"/>`,
    puzzle: `<path d="M9 4.5h4v2.2a1.6 1.6 0 0 0 3.2 0V4.5H19v4h-2.2a1.6 1.6 0 0 0 0 3.2H19v4h-4v-2.2a1.6 1.6 0 0 0-3.2 0v2.2H9v-4H6.8a1.6 1.6 0 0 1 0-3.2H9v-4Z"/>`,
    chat: `<path d="M4 5.5h16v10H10l-4 3.5v-3.5H4Z"/><path d="M8 9.5h8M8 12.5h5"/>`,
    magnet: `<path d="M6 4v7a6 6 0 0 0 12 0V4"/><path d="M6 4H4v7a8 8 0 0 0 16 0V4h-2"/><path d="M6 8h2M16 8h2"/>`,
    eye: `<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z"/><circle cx="12" cy="12" r="2.6"/>`,
    target: `<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.6" fill="currentColor" stroke="none"/>`,
    question: `<path d="M9 9a3 3 0 1 1 4.5 2.6C12.6 12.1 12 12.8 12 14"/><circle cx="12" cy="17.5" r="0.9" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="9.5"/>`
  };

  // Keyword -> icon key heuristics (checked in order, first match wins)
  const RULES = [
    [/\b(brain|cogniti|memory|neuron(?!al network)|think)/i, 'brain'],
    [/\b(quantum|atom|particle|physics|electron)/i, 'atom'],
    [/\b(idea|concept|innovat|creativ)/i, 'bulb'],
    [/\b(network|graph|node|connect|internet|web)/i, 'network'],
    [/\b(neural|deep learning|layer|weight|backpropagation|model|ai\b|algorithm)/i, 'computer'],
    [/\b(gene|dna|biology|cell|organism)/i, 'dna'],
    [/\b(equation|formula|math|calculat|number|algebra)/i, 'formula'],
    [/\b(world|global|geograph|earth|country)/i, 'globe'],
    [/\b(chemi|liquid|water|solution|acid)/i, 'drop'],
    [/\b(nature|plant|environment|ecolog|climate)/i, 'leaf'],
    [/\b(history|time|era|century|date)/i, 'clock'],
    [/\b(law|legal|justice|rule|policy|ethic)/i, 'scale'],
    [/\b(econom|money|finance|market|cost|price)/i, 'coin'],
    [/\b(health|medic|disease|body|patient)/i, 'heart'],
    [/\b(space|rocket|planet|astro)/i, 'rocket'],
    [/\b(secur|protect|privacy|risk|threat|encrypt)/i, 'shield'],
    [/\b(problem|solve|solution|puzzle|logic)/i, 'puzzle'],
    [/\b(language|communicat|speak|grammar|word)/i, 'chat'],
    [/\b(force|magnet|energy|attract)/i, 'magnet'],
    [/\b(observ|experiment|research|study|analy)/i, 'eye'],
    [/\b(goal|target|objective|aim)/i, 'target'],
    [/\b(chart|data|statistic|graph|trend|growth)/i, 'chart'],
    [/\b(gear|system|mechanism|process|engine)/i, 'gear'],
    [/\b(book|read|text|literature|note)/i, 'book']
  ];

  const FALLBACK_ORDER = ['bulb', 'book', 'gear', 'chart', 'puzzle', 'target', 'network', 'question'];
  let fallbackCounter = 0;

  function pickIconKey(text) {
    const t = (text || '').toLowerCase();
    for (const [regex, key] of RULES) {
      if (regex.test(t)) return key;
    }
    const key = FALLBACK_ORDER[fallbackCounter % FALLBACK_ORDER.length];
    fallbackCounter++;
    return key;
  }

  function svgFor(iconKey, colorVar) {
    const inner = ICONS[iconKey] || ICONS.bulb;
    const color = colorVar || 'currentColor';
    return `<svg viewBox="0 0 24 24" fill="none" stroke="${color}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${inner}</svg>`;
  }

  const PALETTE = ['#3b82f6', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316', '#06b6d4'];
  let paletteCounter = 0;

  function nextColor() {
    const c = PALETTE[paletteCounter % PALETTE.length];
    paletteCounter++;
    return c;
  }

  window.NoteIcons = {
    /** Returns an inline <svg> markup string chosen for the given text. */
    iconFor(text) {
      return svgFor(pickIconKey(text));
    },
    /** Returns a full picture-card markup: colored circle + icon, for pairing with a note/keyword. */
    pictureFor(text) {
      const color = nextColor();
      return `<div class="note-picture" style="--picture-color:${color}22; --picture-icon-color:${color};">${svgFor(pickIconKey(text), color)}</div>`;
    },
    reset() {
      fallbackCounter = 0;
      paletteCounter = 0;
    }
  };
})();
