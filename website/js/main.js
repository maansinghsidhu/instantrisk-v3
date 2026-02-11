/* InstantRisk Marketing Website - Main JavaScript */

// Scroll-based navigation styling
const nav = document.querySelector('.nav');
window.addEventListener('scroll', () => {
  if (window.scrollY > 50) {
    nav.classList.add('scrolled');
  } else {
    nav.classList.remove('scrolled');
  }
});

// Reveal animations on scroll
const revealElements = document.querySelectorAll('.reveal');
const revealObserver = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.classList.add('visible');
    }
  });
}, { threshold: 0.1, rootMargin: '0px 0px -50px 0px' });

revealElements.forEach(el => revealObserver.observe(el));

// Animated counter for stats
function animateCounter(element, target, suffix = '') {
  const duration = 2000;
  const step = target / (duration / 16);
  let current = 0;

  const timer = setInterval(() => {
    current += step;
    if (current >= target) {
      current = target;
      clearInterval(timer);
    }
    element.textContent = Math.floor(current).toLocaleString() + suffix;
  }, 16);
}

// Observe stat numbers for animation
const statNumbers = document.querySelectorAll('.stat-number[data-target]');
const statObserver = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      const target = parseInt(entry.target.dataset.target);
      const suffix = entry.target.dataset.suffix || '';
      animateCounter(entry.target, target, suffix);
      statObserver.unobserve(entry.target);
    }
  });
}, { threshold: 0.5 });

statNumbers.forEach(el => statObserver.observe(el));

// Terminal typing animation - re-trigger on scroll
const terminalBodies = document.querySelectorAll('.terminal-body');
const terminalObserver = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      const lines = entry.target.querySelectorAll('.line');
      lines.forEach((line, i) => {
        line.style.animation = 'none';
        line.offsetHeight; // Force reflow
        line.style.animation = `typeLine 0.3s ease ${0.2 + i * 0.3}s forwards`;
      });
    }
  });
}, { threshold: 0.3 });

terminalBodies.forEach(el => terminalObserver.observe(el));

// Clause confidence bar animation
const confidenceBars = document.querySelectorAll('.bar-fill[data-width]');
const barObserver = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.style.width = entry.target.dataset.width;
      barObserver.unobserve(entry.target);
    }
  });
}, { threshold: 0.5 });

confidenceBars.forEach(el => {
  el.style.width = '0';
  barObserver.observe(el);
});

// Floating particles generator
function createParticles(container, count = 20) {
  if (!container) return;
  for (let i = 0; i < count; i++) {
    const particle = document.createElement('div');
    particle.className = 'particle';
    particle.style.left = Math.random() * 100 + '%';
    particle.style.animationDuration = (8 + Math.random() * 12) + 's';
    particle.style.animationDelay = Math.random() * 5 + 's';
    particle.style.width = (2 + Math.random() * 3) + 'px';
    particle.style.height = particle.style.width;
    container.appendChild(particle);
  }
}

document.querySelectorAll('.particles').forEach(p => createParticles(p));

// Mobile navigation toggle
const mobileToggle = document.querySelector('.nav-mobile-toggle');
const navLinks = document.querySelector('.nav-links');

if (mobileToggle && navLinks) {
  mobileToggle.addEventListener('click', () => {
    navLinks.style.display = navLinks.style.display === 'flex' ? 'none' : 'flex';
    navLinks.style.flexDirection = 'column';
    navLinks.style.position = 'absolute';
    navLinks.style.top = '100%';
    navLinks.style.left = '0';
    navLinks.style.right = '0';
    navLinks.style.background = 'rgba(10, 22, 40, 0.98)';
    navLinks.style.padding = '1rem 2rem';
    navLinks.style.borderBottom = '1px solid var(--border-dark)';
  });
}

// Smooth scroll for anchor links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
  anchor.addEventListener('click', function(e) {
    e.preventDefault();
    const target = document.querySelector(this.getAttribute('href'));
    if (target) {
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  });
});

// Active nav link based on current page
const currentPath = window.location.pathname;
document.querySelectorAll('.nav-links a').forEach(link => {
  if (link.getAttribute('href') === currentPath ||
      (currentPath.endsWith('/') && link.getAttribute('href') === 'index.html') ||
      (currentPath.includes(link.getAttribute('href')) && link.getAttribute('href') !== 'index.html')) {
    link.classList.add('active');
  }
});

// Parallax effect for hero glows
window.addEventListener('scroll', () => {
  const scrollY = window.scrollY;
  document.querySelectorAll('.hero-glow').forEach((glow, i) => {
    const speed = 0.15 + (i * 0.05);
    glow.style.transform = `translateY(${scrollY * speed}px)`;
  });
});

console.log('%c InstantRisk ', 'background: linear-gradient(135deg, #00b894, #0984e3); color: white; font-size: 16px; padding: 8px 16px; border-radius: 4px; font-weight: bold;');
console.log('%c Powered by Zeus Engine ', 'color: #00b894; font-size: 12px;');
