# CircuitQuest — one small container: the Python engine + web app, and the
# Claude Code CLI so "Create my own lesson" can use a CLAUDE_CODE_OAUTH_TOKEN
# (set it as a secret on the host — never bake it into the image).
FROM node:22-bookworm-slim AS node

FROM python:3.13-slim
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && npm install -g @anthropic-ai/claude-code \
 && npm cache clean --force

RUN useradd --create-home app
WORKDIR /app
COPY --chown=app:app . .
USER app

ENV CQ_HOST=0.0.0.0 \
    PORT=8765 \
    PYTHONUNBUFFERED=1
EXPOSE 8765
CMD ["python3", "bench_server.py"]
