# moviesdb
![workflow](https://github.com/rayannott/moviesdb/actions/workflows/ci.yml/badge.svg)

Some change here

## Get started
Use `uv`!

```sh
uv venv
uv sync
uv run main.py
```

## What is this?
This is my personal movies and series database, with CLI and TUI (using `textual` interfaces). It used to be a private repository that stored the entries and the watch list in a json file, but now they are kept safe in a MongoDB document database. So... I can finally share the code with you!

## What can this thing do?
It can
- access the movies and series data from the `MongoDB` store;
- modify the database by adding, removing or modifying entries
- chat with the database via an openai model;
- request relevant information from the OMDB online database;
- run a telegram bot that (almost) mirrors the functionality of the terminal app;
- store images and attach them to entries;
- and much more!

## Who is it for?
For me.
