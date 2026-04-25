// Wordle Web App — Plain ES Module
// All three tabs: Play, Auto Solve, Puzzle State

const API = '/api';
const ROWS = 6, COLS = 5;
const KEYBOARD_ROWS = [
  ['q','w','e','r','t','y','u','i','o','p'],
  ['a','s','d','f','g','h','j','k','l'],
  ['Enter','z','x','c','v','b','n','m','Backspace'],
];
const SCORE_COLOR = { 2: 'green', 1: 'yellow', 0: 'grey' };
const FLIP_DELAY = 300; // ms per tile
const PLAY_DELAY = 600; // ms between solver turns during playback

// ── Utilities ─────────────────────────────────────────────────────────────────

async function apiFetch(path, opts = {}) {
  const res = await fetch(API + path, {
    headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
    ...opts,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = data?.detail?.message || data?.detail || 'Request failed';
    throw new Error(msg);
  }
  return data;
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function showToast(el, msg, type = '', duration = 2500) {
  el.textContent = msg;
  el.className = 'toast visible' + (type ? ' ' + type : '');
  clearTimeout(el._timer);
  el._timer = setTimeout(() => {
    el.classList.remove('visible');
    el.className = 'toast';
  }, duration);
}

function scoreClass(score) { return SCORE_COLOR[score] ?? ''; }

// ── Tab routing ───────────────────────────────────────────────────────────────

function initTabs() {
  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(t => {
        t.classList.remove('active');
        t.setAttribute('aria-selected', 'false');
      });
      document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
      tab.classList.add('active');
      tab.setAttribute('aria-selected', 'true');
      const panel = document.getElementById('tab-' + tab.dataset.tab);
      if (panel) panel.classList.add('active');
    });
  });
}

// ── Play Tab ──────────────────────────────────────────────────────────────────

class PlayGame {
  constructor() {
    this.gameId = null;
    this.currentRow = 0;
    this.currentCol = 0;
    this.currentInput = [];
    this.status = 'idle';
    this._busy = false;        // locks input during API call + animation
    this.keyMap = {};           // letter -> best score seen

    this.board = document.getElementById('play-board');
    this.toast = document.getElementById('play-toast');
    this.kbEl  = document.getElementById('play-keyboard');
    this.newBtn = document.getElementById('play-new');
    this.shareBtn = document.getElementById('play-share');

    this._buildBoard();
    this._buildKeyboard();
    this._bindKeys();

    this.newBtn.addEventListener('click', () => this.newGame());
    this.shareBtn.addEventListener('click', () => this._share());
    this.newGame();
  }

  _isPlayTabActive() {
    const panel = document.getElementById('tab-play');
    return panel && panel.classList.contains('active');
  }

  _buildBoard() {
    this.board.innerHTML = '';
    this.tiles = [];
    for (let r = 0; r < ROWS; r++) {
      const row = [];
      for (let c = 0; c < COLS; c++) {
        const tile = document.createElement('div');
        tile.className = 'tile';
        tile.setAttribute('aria-label', `Row ${r+1} tile ${c+1}`);
        this.board.appendChild(tile);
        row.push(tile);
      }
      this.tiles.push(row);
    }
    this._highlightActiveRow();
  }

  _highlightActiveRow() {
    for (let r = 0; r < ROWS; r++) {
      this.tiles[r].forEach(t => t.classList.remove('active-row'));
    }
    if (this.currentRow < ROWS && this.status === 'in_progress') {
      this.tiles[this.currentRow].forEach(t => t.classList.add('active-row'));
    }
  }

  _buildKeyboard() {
    this.kbEl.innerHTML = '';
    this.keyEls = {};
    KEYBOARD_ROWS.forEach(row => {
      const rowEl = document.createElement('div');
      rowEl.className = 'key-row';
      row.forEach(k => {
        const btn = document.createElement('button');
        btn.className = 'key' + (k.length > 1 ? ' wide' : '');
        btn.textContent = k === 'Backspace' ? '⌫' : k.toUpperCase();
        btn.dataset.key = k;
        btn.addEventListener('click', () => this._handleKey(k));
        rowEl.appendChild(btn);
        if (k.length === 1) this.keyEls[k] = btn;
      });
      this.kbEl.appendChild(rowEl);
    });
  }

  _bindKeys() {
    this._kbHandler = (e) => {
      // Only handle keys when Play tab is active
      if (!this._isPlayTabActive()) return;
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      // Don't capture if user is focused on an input/textarea
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      const key = e.key;
      if (key === 'Enter' || key === 'Backspace') {
        e.preventDefault();
        this._handleKey(key);
      } else if (/^[a-zA-Z]$/.test(key)) {
        e.preventDefault();
        this._handleKey(key.toLowerCase());
      }
    };
    document.addEventListener('keydown', this._kbHandler);
  }

  _handleKey(key) {
    if (this._busy) return;
    if (this.status !== 'in_progress') return;
    if (key === 'Backspace') {
      if (this.currentCol > 0) {
        this.currentCol--;
        this.currentInput.pop();
        const tile = this.tiles[this.currentRow][this.currentCol];
        tile.textContent = '';
        tile.classList.remove('filled');
      }
    } else if (key === 'Enter') {
      this._submitGuess();
    } else if (this.currentCol < COLS && /^[a-z]$/.test(key)) {
      const tile = this.tiles[this.currentRow][this.currentCol];
      tile.textContent = key.toUpperCase();
      tile.classList.add('filled');
      // Pop animation
      tile.classList.remove('pop');
      void tile.offsetWidth;
      tile.classList.add('pop');
      this.currentInput.push(key);
      this.currentCol++;
    }
  }

  async newGame() {
    this._busy = true;
    this.newBtn.disabled = true;
    try {
      const data = await apiFetch('/games', { method: 'POST' });
      this.gameId = data.game_id;
      this.status = 'in_progress';
      this.currentRow = 0;
      this.currentCol = 0;
      this.currentInput = [];
      this.keyMap = {};
      this._buildBoard();
      this._buildKeyboard();
      this.shareBtn.style.display = 'none';
      showToast(this.toast, 'New game started', 'success', 1500);
    } catch (e) {
      showToast(this.toast, e.message, 'error');
    } finally {
      this._busy = false;
      this.newBtn.disabled = false;
    }
  }

  async _submitGuess() {
    if (this.currentCol < COLS) {
      this._shakeRow(this.currentRow);
      showToast(this.toast, 'Not enough letters', 'error', 1500);
      return;
    }

    this._busy = true;  // lock all input
    const guess = this.currentInput.join('');

    try {
      const data = await apiFetch(`/games/${this.gameId}/guesses`, {
        method: 'POST',
        body: JSON.stringify({ guess }),
      });
      await this._revealRow(this.currentRow, guess, data.score);
      this._updateKeyboard(guess, data.score);

      this.currentRow++;
      this.currentCol = 0;
      this.currentInput = [];
      this.status = data.status;

      if (data.status === 'solved') {
        await this._bounceRow(this.currentRow - 1);
        const turns = this.currentRow;
        const messages = ['Genius', 'Magnificent', 'Impressive', 'Splendid', 'Great', 'Phew'];
        showToast(this.toast, messages[turns - 1] || 'Solved!', 'success', 4000);
        this.shareBtn.style.display = '';
        this._storeSolved(data.history, data.secret);
      } else if (data.status === 'failed') {
        showToast(this.toast, (data.secret || '?').toUpperCase(), 'error', 5000);
      }

      this._highlightActiveRow();
    } catch (e) {
      this._shakeRow(this.currentRow);
      showToast(this.toast, e.message, 'error');
    } finally {
      this._busy = false;
    }
  }

  async _revealRow(row, guess, scores) {
    const FLIP_DURATION = 500;
    const STAGGER = 250;  // delay between each tile starting its flip
    const COLOR_CLASS = ['grey', 'yellow', 'green'];

    for (let c = 0; c < COLS; c++) {
      const tile = this.tiles[row][c];
      tile.textContent = guess[c].toUpperCase();
      // data-score drives --flip-color CSS variable during animation
      tile.dataset.score = scores[c];
      // Stagger: wait before starting each tile's flip
      if (c > 0) await sleep(STAGGER);
      tile.classList.add('flip');
    }
    // Wait for the last tile to finish its flip animation
    await sleep(FLIP_DURATION);
    // Permanently apply color classes so state persists after animation
    // (animation-fill-mode:forwards with CSS vars is unreliable across browsers)
    for (let c = 0; c < COLS; c++) {
      const tile = this.tiles[row][c];
      tile.classList.remove('filled', 'active-row');
      tile.classList.add(COLOR_CLASS[scores[c]]);
    }
  }

  async _bounceRow(row) {
    const BOUNCE_STAGGER = 80;
    for (let c = 0; c < COLS; c++) {
      const tile = this.tiles[row][c];
      tile.classList.add('bounce');
      await sleep(BOUNCE_STAGGER);
    }
    await sleep(500);
  }

  _shakeRow(row) {
    this.tiles[row].forEach(t => {
      t.classList.remove('shake');
      void t.offsetWidth; // reflow
      t.classList.add('shake');
    });
  }

  _updateKeyboard(guess, scores) {
    for (let i = 0; i < guess.length; i++) {
      const letter = guess[i];
      const score = scores[i];
      const prev = this.keyMap[letter] ?? -1;
      if (score > prev) {
        this.keyMap[letter] = score;
        const el = this.keyEls[letter];
        if (el) {
          el.classList.remove('green', 'yellow', 'grey');
          el.classList.add(scoreClass(score));
        }
      }
    }
  }

  _storeSolved(history, secret) {
    this._lastHistory = history;
    this._lastSecret = secret;
  }

  _share() {
    if (!this._lastHistory) return;
    const blocks = this._lastHistory.map(item =>
      item.score.map(s => s === 2 ? '🟩' : s === 1 ? '🟨' : '⬛').join('')
    ).join('\n');
    const text = `Wordle ${this._lastHistory.length}/6\n\n${blocks}`;
    navigator.clipboard?.writeText(text).then(() =>
      showToast(this.toast, 'Copied to clipboard', 'success', 1500)
    );
  }
}

// ── Auto Solve Tab ────────────────────────────────────────────────────────────

class AutoSolve {
  constructor() {
    this.mode = 'a';
    this.secretInput = document.getElementById('as-secret');
    this.runBtn      = document.getElementById('as-run');
    this.resultDiv   = document.getElementById('as-result');
    this.boardEl     = document.getElementById('as-board');
    this.summaryEl   = document.getElementById('as-summary');
    this.toast       = document.getElementById('as-toast');

    document.querySelectorAll('#tab-autosolve .toggle').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('#tab-autosolve .toggle').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        this.mode = btn.dataset.mode;
      });
    });

    this.secretInput.addEventListener('keydown', e => { if (e.key === 'Enter') this.run(); });
    this.runBtn.addEventListener('click', () => this.run());
  }

  async run() {
    const secret = this.secretInput.value.trim().toLowerCase();
    if (!secret || secret.length !== 5 || !/^[a-z]+$/.test(secret)) {
      showToast(this.toast, 'Enter a valid 5-letter word', 'error');
      return;
    }
    this.runBtn.disabled = true;
    this.resultDiv.style.display = 'none';

    try {
      const data = await apiFetch('/solver/run', {
        method: 'POST',
        body: JSON.stringify({ secret, mode: this.mode }),
      });
      this.resultDiv.style.display = '';
      await this._renderResult(data);
    } catch (e) {
      showToast(this.toast, e.message, 'error');
    } finally {
      this.runBtn.disabled = false;
    }
  }

  async _renderResult(data) {
    // build a 6-row board, animate row by row
    this.boardEl.innerHTML = '';
    const allTiles = [];
    for (let r = 0; r < ROWS; r++) {
      const row = [];
      for (let c = 0; c < COLS; c++) {
        const tile = document.createElement('div');
        tile.className = 'tile';
        this.boardEl.appendChild(tile);
        row.push(tile);
      }
      allTiles.push(row);
    }

    for (let i = 0; i < data.turns.length; i++) {
      const turn = data.turns[i];
      const row = allTiles[i];
      for (let c = 0; c < COLS; c++) {
        row[c].textContent = turn.guess[c].toUpperCase();
      }
      await sleep(PLAY_DELAY);
      for (let c = 0; c < COLS; c++) {
        row[c].dataset.score = turn.score[c];
        await sleep(FLIP_DELAY * c);
        row[c].classList.add('flip');
      }
      await sleep(FLIP_DELAY * COLS);
    }

    // summary
    const modeLabel = data.mode === 'a' ? 'Investigation + Hail-Mary' : 'Hail-Mary Only';
    const outcomeClass = data.solved ? 'green' : 'yellow';
    const outcome = data.solved ? 'Solved' : 'Failed';
    const turnsList = data.turns.map((t, i) =>
      `<div class="summary-stat">
        <span class="label">Turn ${t.turn}: <strong>${t.guess.toUpperCase()}</strong></span>
        <span><span class="mode-badge ${t.mode}">${t.mode.replace('_',' ')}</span>${t.candidates_remaining != null ? ` <span style="color:var(--muted);font-size:12px">${t.candidates_remaining} left</span>` : ''}</span>
      </div>`
    ).join('');

    this.summaryEl.innerHTML = `
      <h3>Result</h3>
      <div class="summary-stat">
        <span class="label">Secret</span>
        <span class="value">${data.secret.toUpperCase()}</span>
      </div>
      <div class="summary-stat">
        <span class="label">Outcome</span>
        <span class="value ${outcomeClass}">${outcome}</span>
      </div>
      <div class="summary-stat">
        <span class="label">Turns</span>
        <span class="value">${data.turns_taken}</span>
      </div>
      <div class="summary-stat">
        <span class="label">Mode</span>
        <span class="value">${modeLabel}</span>
      </div>
      <div style="margin-top:12px">${turnsList}</div>
    `;
  }
}

// ── Puzzle State (Analyze) Tab ────────────────────────────────────────────────

class PuzzleAnalyzer {
  constructor() {
    this.mode = 'a';
    this.rows = [];

    this.rowsEl     = document.getElementById('az-rows');
    this.addBtn     = document.getElementById('az-add-row');
    this.analyzeBtn = document.getElementById('az-analyze');
    this.resultEl   = document.getElementById('az-result');
    this.summaryEl  = document.getElementById('az-summary');
    this.finishBoard= document.getElementById('az-finish-board');
    this.secretEl   = document.getElementById('az-secret');
    this.toast      = document.getElementById('az-toast');

    document.querySelectorAll('#az-mode-group .toggle').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('#az-mode-group .toggle').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        this.mode = btn.dataset.mode;
      });
    });

    this.addBtn.addEventListener('click', () => this._addRow());
    this.analyzeBtn.addEventListener('click', () => this.analyze());

    // start with one empty row
    this._addRow();
  }

  _addRow() {
    if (this.rows.length >= 5) return; // max 5 prior guesses
    const rowEl = document.createElement('div');
    rowEl.className = 'az-row';

    const input = document.createElement('input');
    input.className = 'az-word-input';
    input.maxLength = 5;
    input.placeholder = 'guess';
    input.autocomplete = 'off';
    input.spellcheck = false;

    const tilesWrap = document.createElement('div');
    tilesWrap.style.display = 'flex';
    tilesWrap.style.gap = '5px';

    const tileCells = [];
    for (let c = 0; c < COLS; c++) {
      const tile = document.createElement('div');
      tile.className = 'az-tile';
      tile.dataset.score = '0';
      tile.addEventListener('click', () => {
        const s = ((parseInt(tile.dataset.score) + 1) % 3).toString();
        tile.dataset.score = s;
        const letter = input.value[c] || '';
        tile.textContent = letter.toUpperCase();
      });
      tilesWrap.appendChild(tile);
      tileCells.push(tile);
    }

    // sync letters from input to tiles
    input.addEventListener('input', () => {
      const val = input.value.toUpperCase();
      tileCells.forEach((t, i) => { t.textContent = val[i] || ''; });
    });

    const removeBtn = document.createElement('button');
    removeBtn.className = 'az-remove';
    removeBtn.textContent = '×';
    removeBtn.title = 'Remove row';
    removeBtn.addEventListener('click', () => {
      const idx = this.rows.indexOf(rowData);
      if (idx >= 0) this.rows.splice(idx, 1);
      rowEl.remove();
      if (this.rows.length === 0) this._addRow();
    });

    rowEl.appendChild(input);
    rowEl.appendChild(tilesWrap);
    rowEl.appendChild(removeBtn);
    this.rowsEl.appendChild(rowEl);

    const rowData = { input, tiles: tileCells };
    this.rows.push(rowData);
  }

  async analyze() {
    const history = [];
    for (const row of this.rows) {
      const guess = row.input.value.trim().toLowerCase();
      if (!guess) continue;
      if (guess.length !== 5) {
        showToast(this.toast, `Guess "${guess}" is not 5 letters`, 'error');
        return;
      }
      const score = row.tiles.map(t => parseInt(t.dataset.score));
      history.push({ guess, score });
    }

    if (history.length === 0) {
      showToast(this.toast, 'Enter at least one guess', 'error');
      return;
    }

    const secret = this.secretEl.value.trim().toLowerCase() || null;
    if (secret && (secret.length !== 5 || !/^[a-z]+$/.test(secret))) {
      showToast(this.toast, 'Secret must be a 5-letter word or left blank', 'error');
      return;
    }

    this.analyzeBtn.disabled = true;
    this.resultEl.style.display = 'none';

    try {
      const data = await apiFetch('/solver/analyze', {
        method: 'POST',
        body: JSON.stringify({ history, mode: this.mode, secret }),
      });
      this.resultEl.style.display = '';
      this._renderAnalysis(data, history, secret);
    } catch (e) {
      showToast(this.toast, e.message, 'error');
    } finally {
      this.analyzeBtn.disabled = false;
    }
  }

  _renderAnalysis(data, history, secret) {
    const suggMode = data.suggestion_mode ? `<span class="mode-badge ${data.suggestion_mode}">${data.suggestion_mode.replace('_',' ')}</span>` : '';
    const suggText = data.suggestion
      ? `<span class="value">${data.suggestion.toUpperCase()}</span> ${suggMode}`
      : `<span class="value" style="color:var(--muted)">—</span>`;

    const candClass = data.candidates_remaining <= 5 ? 'green' : data.candidates_remaining <= 18 ? 'yellow' : '';

    this.summaryEl.innerHTML = `
      <h3>Analysis</h3>
      <div class="summary-stat">
        <span class="label">Candidates remaining</span>
        <span class="value ${candClass}">${data.candidates_remaining}</span>
      </div>
      <div class="summary-stat">
        <span class="label">Best next guess</span>
        <span style="display:flex;align-items:center;gap:8px">${suggText}</span>
      </div>
      ${secret ? `<div class="summary-stat"><span class="label">Auto-finish from here</span><span class="value">${data.auto_finish ? (data.auto_finish.solved ? `Solved in ${data.auto_finish.turns_taken} total turns` : 'Could not finish') : 'N/A'}</span></div>` : ''}
    `;

    // render auto-finish board
    if (data.auto_finish && data.auto_finish.turns && secret) {
      this.finishBoard.style.display = '';
      this.finishBoard.innerHTML = '';

      const totalRows = history.length + data.auto_finish.turns.length;
      this.finishBoard.style.gridTemplateRows = `repeat(${Math.max(totalRows, 1)}, var(--tile-size))`;

      // prior history rows (greyed border already scored)
      for (const h of history) {
        for (let c = 0; c < COLS; c++) {
          const tile = document.createElement('div');
          tile.className = 'tile';
          tile.textContent = h.guess[c].toUpperCase();
          tile.dataset.score = h.score[c];
          // instant reveal — already known
          tile.style.background = tileColor(h.score[c]);
          tile.style.borderColor = tileColor(h.score[c]);
          this.finishBoard.appendChild(tile);
        }
      }

      // auto-finish rows with flip animation
      (async () => {
        for (const turn of data.auto_finish.turns) {
          const tiles = [];
          for (let c = 0; c < COLS; c++) {
            const tile = document.createElement('div');
            tile.className = 'tile';
            tile.textContent = turn.guess[c].toUpperCase();
            this.finishBoard.appendChild(tile);
            tiles.push(tile);
          }
          await sleep(PLAY_DELAY);
          for (let c = 0; c < COLS; c++) {
            tiles[c].dataset.score = turn.score[c];
            await sleep(FLIP_DELAY * c);
            tiles[c].classList.add('flip');
          }
          await sleep(FLIP_DELAY * COLS);
        }
      })();
    } else {
      this.finishBoard.style.display = 'none';
    }
  }
}

function tileColor(score) {
  if (score === 2) return 'var(--green)';
  if (score === 1) return 'var(--yellow)';
  return 'var(--grey-tile)';
}

// ── Boot ──────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  new PlayGame();
  new AutoSolve();
  new PuzzleAnalyzer();

  // fetch and display version
  fetch('/api/version')
    .then(r => r.json())
    .then(d => {
      const el = document.getElementById('version-badge');
      if (el && d.version) el.textContent = `v${d.version}`;
    })
    .catch(() => {});
});
