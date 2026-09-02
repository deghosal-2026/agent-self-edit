FROM python:3.12-slim AS builder
WORKDIR /app
COPY pyproject.toml .
COPY src/ src/
RUN pip install build && python -m build --wheel

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /app/dist/*.whl .
RUN pip install *.whl 'agent-self-edit[llm]' && rm *.whl
ENTRYPOINT ["agent-self-edit"]