FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl \
  && curl -LsSf https://astral.sh/uv/install.sh | sh \
  && apt-get purge -y --auto-remove curl \
  && rm -rf /var/lib/apt/lists/*
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock* ./

CMD ["uv", "sync"]

COPY . .

# Option A: run via uv (no PATH juggling)
# CMD ["uv", "run", "python", "main.py"]
# or CMD ["uv", "run", "python", "bot.py"]  # for the tg bot


# build new image with:
# docker build -t moviesdb .

# run the container with:
# docker run -it --env-file .env moviesdb
# docker run -it --env-file .env moviesdb /bin/bash
