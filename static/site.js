const FOOTER_LINKS = [
  { href: '/terms', label: 'Terms' },
  { href: '/privacy', label: 'Privacy' },
  { href: '/faqs', label: 'FAQs' },
  { href: '/changelog', label: 'Changelog' },
];

function renderFooter(container, versionLabel) {
  const links = FOOTER_LINKS.map(
    item => `<a class="footer-link" href="${item.href}">${item.label}</a>`
  ).join('');

  container.innerHTML = `
    <div class="footer-panel">
      <p class="footer-kicker">Public Build</p>
      <div class="footer-links">${links}</div>
      <div class="footer-meta">
        <a class="footer-badge" href="https://github.com/dev-kasibhatla/wordle" target="_blank" rel="noreferrer">
          <img src="https://img.shields.io/badge/GitHub-Open%20Source-111827?logo=github&logoColor=white" alt="Open source on GitHub" />
        </a>
        <span class="version-badge">${versionLabel}</span>
      </div>
    </div>
  `;
}

async function fetchVersionLabel() {
  try {
    const response = await fetch('/api/version');
    const payload = await response.json();
    return payload?.version ? `Version v${payload.version}` : 'Version unavailable';
  } catch {
    return 'Version unavailable';
  }
}

document.addEventListener('DOMContentLoaded', async () => {
  const footers = [...document.querySelectorAll('[data-site-footer]')];
  if (!footers.length) {
    return;
  }

  const versionLabel = await fetchVersionLabel();
  footers.forEach(footer => renderFooter(footer, versionLabel));
});