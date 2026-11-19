/* API boundary. Talks to the Django backend on the same origin (cookie session + CSRF token). */
const api = (() => {
  const BASE = '/api';

  function csrfToken() {
    const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }

  async function request(method, path, body) {
    const options = { method, credentials: 'same-origin', headers: { Accept: 'application/json' } };
    if (method !== 'GET') {
      options.headers['Content-Type'] = 'application/json';
      options.headers['X-CSRFToken'] = csrfToken();
    }
    if (body !== undefined) options.body = JSON.stringify(body);
    let response;
    try {
      response = await fetch(BASE + path, options);
    } catch (networkError) {
      throw new Error('Cannot reach the server. Check that it is running and try again.');
    }
    let data = null;
    try { data = await response.json(); } catch (parseError) { /* non-JSON response */ }
    if (!response.ok) {
      const err = new Error((data && data.error && data.error.message) || 'Request failed (' + response.status + ').');
      err.status = response.status;
      err.code = data && data.error && data.error.code;
      err.fields = (data && data.error && data.error.fields) || {};
      throw err;
    }
    return data;
  }

  return {
    auth: {
      async currentUser() {
        try { return (await request('GET', '/auth/me')).item; }
        catch (err) { if (err.status === 401) return null; throw err; }
      },
      async login({ identity, password }) {
        const data = await request('POST', '/auth/login', { identity, password });
        return { user: data.item };
      },
      async logout() {
        try { await request('POST', '/auth/logout', {}); } catch (err) { /* already signed out */ }
        return { ok: true };
      },
      async forgotPassword() {
        throw new Error('Online password recovery is not available. Please contact the university administration to reset your password.');
      }
    },
    list: (resource, query) => request('GET', '/' + resource + (query ? '?' + query : '')),
    create: (resource, record) => request('POST', '/' + resource, record),
    update: (resource, id, patch) => request('PATCH', '/' + resource + '/' + encodeURIComponent(id), patch),
    remove: (resource, id) => request('DELETE', '/' + resource + '/' + encodeURIComponent(id)),
    reports: () => request('GET', '/reports/overview')
  };
})();
