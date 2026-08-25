FROM python:3.12-slim

WORKDIR /app

# libpq no hace falta: asyncpg es puro Python + wheels precompilados.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# No correr como root: si algún día aparece un RCE (dependencia vulnerable,
# deserialización insegura, etc.), que el atacante herede un usuario sin
# privilegios adentro del contenedor, no root.
RUN useradd --create-home --shell /usr/sbin/nologin appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
