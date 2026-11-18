/* API boundary. Replace these mock repository calls with fetch() when backend endpoints are agreed. */
const api = {
 auth: {
  async currentUser() { return null; /* Replace with GET /api/auth/me; return null when unauthenticated. */ },
  async login(credentials) { throw new Error('Authentication is not connected. Ask the backend team to configure POST /api/auth/login.'); },
  async logout() { return {ok:true}; },
  async forgotPassword(identity) { throw new Error('Password recovery is not connected. Contact university IT support.'); }
 },
 async list(resource) { return repository.list(resource); },
 async create(resource,record) { return repository.add(resource,record); },
 async update(resource,id,patch) { return repository.update(resource,id,patch); },
 async remove(resource,id) { return repository.remove(resource,id); }
};
