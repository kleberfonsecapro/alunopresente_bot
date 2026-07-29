# Usamos a imagem oficial do Python 3.11 slim para reduzir o tamanho do container
FROM python:3.11-slim

# Variáveis de ambiente para otimizar o Python no Docker
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Diretório de trabalho dentro do container
WORKDIR /app

# Instala dependências do sistema para o PostgreSQL (psycopg2) e utilitários básicos
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Instala as dependências Python (Django, Ninja, Pydantic, Playwright, etc.)
# Nota: O requirements.txt deve conter 'playwright' e os demais pacotes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instala os binários do navegador (Chromium) e suas dependências de sistema (OS deps)
RUN playwright install --with-deps chromium

# Copia o entrypoint e o backend
COPY ./entrypoint.sh /entrypoint.sh
COPY ./backend /app/

RUN chmod +x /entrypoint.sh

# Expõe a porta que o Django Ninja vai escutar
EXPOSE 8000

# Entrypoint que executa migrações antes de iniciar
ENTRYPOINT ["/entrypoint.sh"]

# Comando padrão de inicialização
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
