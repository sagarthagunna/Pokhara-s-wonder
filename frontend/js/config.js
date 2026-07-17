// js/config.js
//
// One switch: point the frontend at your backend.
// - Local dev (running backend directly with uvicorn): http://localhost:8000
// - Docker Compose (see docker-compose.yml service name "backend"): the
//   browser still talks to whatever port you've published on the host,
//   so this usually stays localhost:8000 even in Docker, unless you
//   change the published port in docker-compose.yml.
const API_BASE = "http://localhost:8001";
