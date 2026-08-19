#!/bin/bash
set -e

echo "Aguardando banco de dados..."
until python -c "import psycopg2; psycopg2.connect(host='$POSTGRES_HOST', dbname='$POSTGRES_DB', user='$POSTGRES_USER', password='$POSTGRES_PASSWORD')" 2>/dev/null; do
  sleep 1
done
echo "Banco de dados pronto!"

echo "Criando migrations..."
python manage.py makemigrations aluno_presente_sme --noinput

echo "Executando migrações..."
python manage.py migrate --noinput

echo "Criando superusuário (se não existir)..."
python manage.py shell -c "
import os
from django.contrib.auth.models import User
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
if not password:
    import secrets
    password = secrets.token_urlsafe(32)
    print(f'WARNING: DJANGO_SUPERUSER_PASSWORD não definida. Gerando senha aleatória.')
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', password)
    print(f'Superusuário admin criado com senha segura.')
else:
    u = User.objects.get(username='admin')
    u.set_password(password)
    u.save()
    print(f'Senha do superusuário admin atualizada.')
"

echo "Iniciando servidor..."
exec "$@"
