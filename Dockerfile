FROM python:3.12

COPY hippometa hippo/hippometa
COPY hipposerve hippo/hipposerve
COPY hippoclient hippo/hippoclient
COPY pyproject.toml hippo/pyproject.toml

RUN pip install uv
RUN uv pip install --system --upgrade /hippo

CMD ["uvicorn", "hipposerve.api.app:app", "--host", "0.0.0.0", "--port", "44776"]