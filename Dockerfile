FROM python:3.12-slim AS builder
WORKDIR /app
COPY pyproject.toml .
COPY src/ src/
RUN pip install build && python -m build --wheel

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /app/dist/*.whl .
RUN pip install *.whl 'openai>=1.0' && rm *.whl
COPY docs/ docs/
COPY field-test/ field-test/
ENTRYPOINT ["agent-self-edit"]