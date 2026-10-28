# Pinned to the patch version so the container does not drift with whatever Node 22
# upstream happens to publish next.
FROM node:22.23.4-slim

WORKDIR /srv

# The official node image already ships an unprivileged `node` user (uid 1000); it just
# has to be selected. /srv is created by WORKDIR as root, so hand it over before the
# install, because npm needs to write node_modules there.
RUN chown -R node:node /srv
USER node

COPY --chown=node:node package.json package-lock.json ./
RUN npm ci

COPY --chown=node:node . .

EXPOSE 5173

# Dev server, because Phase 3 is about proving the wiring. Production serves the
# static build from Vercel's CDN instead, so there is no need for a runtime
# Node server in production.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
