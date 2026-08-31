FROM python:3.12-slim AS builder
WORKDIR /app
COPY pyproject.toml .
RUN pip install build && python -m build --wheel

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /app/dist/*.whl .
RUN pip install *.whl && rm *.whl
COPY docs/ docs/
COPY scripts/ scripts/
ENTRYPOINT ["agent-self-edit"]
CMD ["--help"]