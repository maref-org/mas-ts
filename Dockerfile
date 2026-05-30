FROM python:3.11-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --user -r requirements.txt

FROM python:3.11-slim

RUN groupadd -r mas-eval && useradd -r -g mas-eval mas-eval

WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY . .

ENV PATH=/root/.local/bin:$PATH

RUN chown -R mas-eval:mas-eval /app
USER mas-eval

ENTRYPOINT ["python"]
CMD ["mas_fast_screen.py", "--help"]
