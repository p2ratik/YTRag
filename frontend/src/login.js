const API_BASE = 'http://localhost:8000/api';

const tabLogin = document.getElementById('tabLogin');
const tabSignup = document.getElementById('tabSignup');
const indicator = document.querySelector('.tab-indicator');
const loginForm = document.getElementById('loginForm');
const signupForm = document.getElementById('signupForm');
const loginError = document.getElementById('loginError');
const signupError = document.getElementById('signupError');
const card = document.getElementById('authCard');
const pullCord = document.getElementById('lampPull');

let activeMode = 'login';
let lampOn = false;
let pullStartY = null;
let suppressClickToggle = false;

function setActiveTab(mode) {
  activeMode = mode;
  const showLogin = mode === 'login';

  tabLogin.classList.toggle('active', showLogin);
  tabSignup.classList.toggle('active', !showLogin);
  indicator.style.transform = showLogin ? 'translateX(0)' : 'translateX(100%)';

  loginForm.classList.remove('active', 'slide-left');
  signupForm.classList.remove('active', 'slide-left');

  if (showLogin) {
    signupForm.classList.add('slide-left');
    requestAnimationFrame(() => loginForm.classList.add('active'));
  } else {
    loginForm.classList.add('slide-left');
    requestAnimationFrame(() => signupForm.classList.add('active'));
  }
}

tabLogin.addEventListener('click', () => setActiveTab('login'));
tabSignup.addEventListener('click', () => setActiveTab('signup'));

document.addEventListener('mousemove', (event) => {
  if (window.innerWidth < 981) {
    card.style.transform = '';
    return;
  }

  const bounds = card.getBoundingClientRect();
  const relativeX = (event.clientX - bounds.left) / bounds.width - 0.5;
  const relativeY = (event.clientY - bounds.top) / bounds.height - 0.5;
  const rotateY = relativeX * 6;
  const rotateX = relativeY * -5;
  card.style.transform = `perspective(1200px) rotateX(${rotateX}deg) rotateY(${rotateY}deg)`;
});

document.addEventListener('mouseleave', () => {
  card.style.transform = '';
});

function setLampState(nextState) {
  lampOn = nextState;
  document.body.classList.toggle('lamp-on', lampOn);
}

function triggerLampToggle() {
  setLampState(!lampOn);
}

function resetCordPosition() {
  pullCord.classList.remove('is-pulling');
  pullCord.style.setProperty('--pull-distance', '0px');
  pullStartY = null;
}

pullCord.addEventListener('pointerdown', (event) => {
  pullStartY = event.clientY;
  pullCord.classList.add('is-pulling');
  pullCord.setPointerCapture(event.pointerId);
});

pullCord.addEventListener('pointermove', (event) => {
  if (pullStartY === null) {
    return;
  }

  const distance = Math.max(0, Math.min(42, event.clientY - pullStartY));
  pullCord.style.setProperty('--pull-distance', `${distance}px`);
});

pullCord.addEventListener('pointerup', (event) => {
  if (pullStartY !== null) {
    const distance = event.clientY - pullStartY;
    if (distance > 26) {
      suppressClickToggle = true;
      triggerLampToggle();
    }
  }

  resetCordPosition();
});

pullCord.addEventListener('pointercancel', resetCordPosition);
pullCord.addEventListener('click', () => {
  if (suppressClickToggle) {
    suppressClickToggle = false;
    return;
  }

  if (pullStartY === null) {
    triggerLampToggle();
  }
});

loginForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const username = document.getElementById('loginUsername').value;
  const password = document.getElementById('loginPassword').value;
  const btn = document.getElementById('loginBtn');

  setLoading(btn, true);
  loginError.textContent = '';

  try {
    const formData = new FormData();
    formData.append('username', username);
    formData.append('password', password);

    const res = await fetch(`${API_BASE}/login`, {
      method: 'POST',
      body: formData
    });
    const data = await res.json();

    if (res.ok) {
      localStorage.setItem('access_token', data.access_token);
      window.location.href = '/index.html';
    } else {
      loginError.textContent = data.detail || 'Login failed';
    }
  } catch (error) {
    loginError.textContent = 'Server connection failed';
  } finally {
    setLoading(btn, false);
  }
});

signupForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const email = document.getElementById('signupEmail').value;
  const username = document.getElementById('signupUsername').value;
  const password = document.getElementById('signupPassword').value;
  const btn = document.getElementById('signupBtn');

  setLoading(btn, true);
  signupError.textContent = '';

  try {
    const formData = new FormData();
    formData.append('email', email);
    formData.append('username', username);
    formData.append('password', password);

    const res = await fetch(`${API_BASE}/signup`, {
      method: 'POST',
      body: formData
    });
    const data = await res.json();

    if (res.ok) {
      setActiveTab('login');
      document.getElementById('loginUsername').value = username;
      loginError.style.color = 'var(--green-1)';
      loginError.textContent = 'Account created. Log in to continue.';
      setTimeout(() => {
        loginError.style.color = '';
      }, 3000);
    } else {
      signupError.textContent = data.detail || 'Signup failed';
    }
  } catch (error) {
    signupError.textContent = 'Server connection failed';
  } finally {
    setLoading(btn, false);
  }
});

function setLoading(btn, isLoading) {
  btn.classList.toggle('loading', isLoading);
  btn.disabled = isLoading;
}

setActiveTab(activeMode);
