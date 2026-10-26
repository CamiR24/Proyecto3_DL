FROM python:3.12-slim
RUN pip install --no-cache-dir antlr4-python3-runtime==4.13.2
COPY harness.py case.py /opt/
ENV PYTHONDONTWRITEBYTECODE=1
USER 65534:65534
ENTRYPOINT ["python", "-I", "/opt/harness.py"]
