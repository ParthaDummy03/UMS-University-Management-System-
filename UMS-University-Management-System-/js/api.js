const resourcePath = {
  schedule: 'schedules',
  grades: 'results'
};

async function requestApi(path, options = {}) {
  const response = await fetch(path, {
    credentials: 'same-origin',
    cache: 'no-store',
    ...options,
    headers: {
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...options.headers
    }
  });
  const payload = response.status === 204 ? null : await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401 && path.startsWith('/api/') && !path.startsWith('/api/auth/')) {
      window.dispatchEvent(new Event('ums-auth-expired'));
    }
    const error = new Error(payload?.error?.message || `Request failed (${response.status}).`);
    error.status = response.status;
    error.code = payload?.error?.code;
    error.fields = payload?.error?.fields || {};
    throw error;
  }
  return payload;
}

const api = {
  auth: {
    async setupStatus() {
      return requestApi('/api/auth/setup-status');
    },
    async setupAdmin(credentials) {
      return requestApi('/api/auth/setup-admin', { method: 'POST', body: JSON.stringify(credentials) });
    },
    async currentUser() {
      try {
        const result = await requestApi('/api/auth/me');
        return result.user;
      } catch (error) {
        if (error.status === 401) return null;
        throw error;
      }
    },
    async login(credentials) {
      return requestApi('/api/auth/login', { method: 'POST', body: JSON.stringify(credentials) });
    },
    async logout() {
      return requestApi('/api/auth/logout', { method: 'POST', body: '{}' });
    }
  },
  async bootstrap() {
    return requestApi('/api/bootstrap');
  },
  async list(resource) {
    const path = resourcePath[resource] || resource;
    const result = await requestApi(`/api/${path}`);
    return result.items || [];
  },
  async create(resource, record) {
    const path = resourcePath[resource] || resource;
    return requestApi(`/api/${path}`, { method: 'POST', body: JSON.stringify(record) });
  },
  async update(resource, id, patch) {
    const path = resourcePath[resource] || resource;
    return requestApi(`/api/${path}/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(patch) });
  },
  async remove(resource, id) {
    const path = resourcePath[resource] || resource;
    return requestApi(`/api/${path}/${encodeURIComponent(id)}`, { method: 'DELETE' });
  }
};
