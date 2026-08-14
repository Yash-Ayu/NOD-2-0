/* NOD Auth Utilities */
const NODAuth = {
  async logout() {
    try {
      await fetch('/api/auth/logout', { method: 'POST' });
    } catch (e) {}
    window.location.href = '/login';
  },

  async getUser() {
    try {
      const res = await fetch('/api/auth/me');
      if (res.ok) return await res.json();
    } catch (e) {}
    return null;
  }
};