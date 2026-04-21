import axios from 'axios';

function readCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
  return match ? decodeURIComponent(match[1]) : null;
}

export const api = axios.create({
  baseURL: '/api/v1',
  withCredentials: true,
});

api.interceptors.request.use((config) => {
  const method = config.method?.toLowerCase();
  if (method && ['post', 'put', 'patch', 'delete'].includes(method)) {
    const csrf = readCookie('prism_csrf');
    if (csrf) {
      config.headers = config.headers ?? {};
      config.headers['X-Prism-Csrf'] = csrf;
    }
  }
  return config;
});
