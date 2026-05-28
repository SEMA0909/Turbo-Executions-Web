// Configuration for API endpoints
// This allows the frontend to work with different backend deployments

const API_BASE_URL = window.location.hostname === 'localhost' 
  ? 'http://localhost:8000'  // Local development
  : 'https://YOUR_RENDER_URL.onrender.com';  // Production - update this with your Render URL

export const API_ENDPOINTS = {
  login: `${API_BASE_URL}/api/login`,
  snapshot: `${API_BASE_URL}/api/snapshot`,
  ws: `${API_BASE_URL.replace('http', 'ws')}/ws`,
  health: `${API_BASE_URL}/api/health`
};

export default API_ENDPOINTS;
