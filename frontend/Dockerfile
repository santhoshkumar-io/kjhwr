# Pinned so the container does not drift with whatever Node is current.
FROM node:22-slim

WORKDIR /srv

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173

# Dev server, because Phase 3 is about proving the wiring. Production serves the
# static build from Vercel's CDN instead, so there is no need for a runtime
# Node server in production.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
