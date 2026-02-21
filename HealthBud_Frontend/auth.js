const API_BASE = "http://127.0.0.1:8000";

function saveSession(data) {
  localStorage.setItem("hb_token", data.access_token);
  localStorage.setItem("hb_user", JSON.stringify(data.user));
}

async function signup(name, email, password) {
  const res = await fetch(`${API_BASE}/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, email, password })
  });

  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Signup failed");

  saveSession(data);

  // redirect
  window.location.href = "./homepage.html";
}

async function login(email, password) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password })
  });

  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Login failed");

  saveSession(data);

  // redirect
  window.location.href = "./homepage.html";
}