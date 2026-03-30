import axios from 'axios';

const BASE = 'http://localhost:8000/api/v1';

const api = axios.create({ baseURL: BASE });

api.interceptors.request.use(cfg => {
  const token = localStorage.getItem('token');
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  return cfg;
});

api.interceptors.response.use(
  res => res,
  err => {
    if (err.response?.status === 401) {
      localStorage.clear();
      window.location.href = '/login';
    }
    return Promise.reject(err);
  }
);

// ── Auth ──────────────────────────────────────────────────────────
export const authAPI = {
  register: (data) => api.post('/auth/register', data),

  // Sends form-data so Swagger Authorize button also works
  login: (data) => {
    const form = new URLSearchParams();
    form.append('username', data.email);
    form.append('password', data.password);
    return api.post('/auth/login', form, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
  },

  profile:      ()     => api.get('/auth/profile'),
  enrollFace:   (data) => api.post('/auth/enroll-face', data),
  enrollStatus: ()     => api.get('/auth/enroll-status'),

  // P1: verify live face against stored embedding before exam
  verifyFace: (data)   => api.post('/auth/verify-face', data),
};

// ── Exams ─────────────────────────────────────────────────────────
export const examAPI = {
  list:      ()        => api.get('/exams/'),
  get:       (id)      => api.get(`/exams/${id}`),
  create:    (data)    => api.post('/exams/create', data),
  start:     (id)      => api.post(`/exams/${id}/start`),
  submit:    (id)      => api.post(`/exams/${id}/submit`),
  terminate: (id, sid) => api.post(`/exams/${id}/terminate?session_id=${sid}`),
};

// ── Monitoring ────────────────────────────────────────────────────
export const monitorAPI = {
  frame:        (data) => api.post('/monitoring/frame', data),
  audio:        (data) => api.post('/monitoring/audio', data),
  browserEvent: (data) => api.post('/monitoring/browser-event', data),
  sessionRisk:  (sid)  => api.get(`/monitoring/session/${sid}`),
};

// ── Reports ───────────────────────────────────────────────────────
export const reportAPI = {
  get:      (sid) => api.get(`/reports/${sid}`),
  generate: (sid) => api.post(`/reports/generate/${sid}`),
  download: (sid) => `${BASE}/reports/${sid}/download`,
};

export default api;