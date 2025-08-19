# moviesdb
![workflow](https://github.com/rayannott/moviesdb/actions/workflows/ci.yml/badge.svg)

## What is this?
This is my personal movies and series database, with CLI and TUI (using `textual` interfaces). It used to be a private repository that stored the entries and the watch list in a json file, but now they are kept safe in a MongoDB document database. So... I can finally share the code with you!

## What can this thing do?
It can
- access the movies and series data from the `MongoDB` store;
- modify the database by adding, removing or modifying entries
- chat with the database via an openai model;
- request relevant information from the OMDB online database;
- run a telegram bot that mirrors the functionality of the terminal app;
- and much more!

### A Telegram Bot?
Yes, you can try it out [here](https://t.me/mymoviesdbbot) in the read-only mode.

## Who is it for?
<s>For me.</s> For me and maybe for you, but you'd need to do some setting up.

Here's the
### Minimal setup

First of all, in the `src/utils/env.py`, comment out the `assert` statements associated with the optional features (`TELEGRAM_TOKEN`, `OPENAI_API_KEY`, `OPENAI_PROJECT_ID`, `OMDB_API_KEY`) and define `MONGODB_PASSWORD` in the `.env` file. Then, in your free tier MongoDB Atlas, create an app (`MoviesSeries`) and collections (`entries`, `watchlist`). Replace the `uri` variable in `src/mongo.py` with your own MongoDB URI.
