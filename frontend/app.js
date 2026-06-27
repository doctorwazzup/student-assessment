
const SECTIONS = [
  { key: 'q1', title: 'What did you learn today?' },
  { key: 'q2', title: 'What did you find easy?' },
  { key: 'q3', title: 'What was challenging?' },
  { key: 'q4', title: 'What questions do you still have?' },
  { key: 'q5', title: 'What can you improve next time?' },
];

const ANSWER_LABELS = {
  A: 'Option A', B: 'Option B', C: 'Option C', D: 'Option D',
};

const answers = {};

// Wire up option clicks
document.querySelectorAll('.option').forEach(label => {
  label.addEventListener('click', () => {
    const input = label.querySelector('input[type="radio"]');
    if (!input) return;

    const name = input.name;

    // Deselect siblings
    document.querySelectorAll(`input[name="${name}"]`).forEach(r => {
      r.closest('.option').classList.remove('selected');
    });

    input.checked = true;
    label.classList.add('selected');
    answers[name] = input.value;

    // Mark card as answered
    const card = label.closest('.card');
    card.classList.add('answered');

    updateProgress();
  });
});

function countAnswered() {
  return SECTIONS.filter(s => answers[s.key]).length;
}

function updateProgress() {
  const done = countAnswered();
  const pct  = (done / 5) * 100;

  document.getElementById('progressBar').style.width = pct + '%';
  document.getElementById('progressLabel').textContent = `${done} / 5 completed`;

  const btn  = document.getElementById('submitBtn');
  const hint = document.getElementById('submitHint');

  if (done === 5) {
    btn.disabled = false;
    hint.textContent = 'All done! You\'re ready to submit.';
    hint.classList.add('ready');
  } else {
    btn.disabled = true;
    hint.textContent = `Please answer all 5 sections to submit. (${5 - done} remaining)`;
    hint.classList.remove('ready');
  }
}

// Submit
document.getElementById('assessmentForm').addEventListener('submit', e => {
  e.preventDefault();
  if (countAnswered() < 5) return;

  buildResultSummary();
  document.getElementById('modalOverlay').classList.add('show');
  document.body.style.overflow = 'hidden';
});

function buildResultSummary() {
  const container = document.getElementById('resultSummary');
  container.innerHTML = '';

  SECTIONS.forEach((s, i) => {
    const val  = answers[s.key] || '—';
    const text = getOptionText(s.key, val);

    const item = document.createElement('div');
    item.className = 'result-item';
    item.innerHTML = `
      <div class="sec-label">0${i + 1}</div>
      <div>
        <div class="sec-title">${s.title}</div>
        <div class="sec-ans">${val}: ${text}</div>
      </div>`;
    container.appendChild(item);
  });
}

function getOptionText(name, val) {
  const input = document.querySelector(`input[name="${name}"][value="${val}"]`);
  if (!input) return '';
  return input.closest('.option').querySelector('.option-text').textContent.trim();
}

// Reset
document.getElementById('resetBtn').addEventListener('click', () => {
  // Clear answers
  Object.keys(answers).forEach(k => delete answers[k]);

  // Uncheck all radios & remove classes
  document.querySelectorAll('input[type="radio"]').forEach(r => { r.checked = false; });
  document.querySelectorAll('.option').forEach(o => o.classList.remove('selected'));
  document.querySelectorAll('.card').forEach(c => c.classList.remove('answered'));

  // Reset progress
  updateProgress();

  // Close modal
  document.getElementById('modalOverlay').classList.remove('show');
  document.body.style.overflow = '';

  // Scroll to top
  window.scrollTo({ top: 0, behavior: 'smooth' });
});

// Close modal on overlay click
document.getElementById('modalOverlay').addEventListener('click', e => {
  if (e.target === e.currentTarget) {
    document.getElementById('modalOverlay').classList.remove('show');
    document.body.style.overflow = '';
  }
});

// Init
updateProgress();
