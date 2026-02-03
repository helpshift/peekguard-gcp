# Peek Guard

## Brief introduction

This service is used to redact, mask and unmask PIIs.

## One-time Setup

> Note: Make sure pyenv is installed before doing the setup

```shell
make dev
```

### Usage

To start the service locally, run the following:

```shell
make run
```

## Running tests

```shell
make test
```

## Important notes

### FAST API documentation links for used code

- [exception_handler](https://fastapi.tiangolo.com/reference/fastapi/?h=exception_handler#fastapi.FastAPI.exception_handler)
- [Testing FAST Api with Pytest using TestClient](https://fastapi.tiangolo.com/tutorial/testing/?h=testclient#using-testclient)
- [Lifespan Events](https://fastapi.tiangolo.com/advanced/events/?h=lifespa#lifespan-events)

## Contributing to this repo

- Setup linters & formatters for consistency across the codebase. Recommendation: Ruff

