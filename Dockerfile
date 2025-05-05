FROM python:3.13

WORKDIR /app

COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
# or CMD ["python", "bot.py"]  # for the tg bot


# build new image with:
# docker build -t moviesdb .

# run the container with:
# docker run -it --env-file .env moviesdb
# docker run -it --env-file .env moviesdb /bin/bash
