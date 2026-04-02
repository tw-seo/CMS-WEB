docker-compose --env-file .env.prod down
docker-compose --env-file .env.prod up -d --build
docker-compose --env-file .env.prod exec web python manage.py makemigrations
docker-compose --env-file .env.prod exec web python manage.py migrate
docker-compose --env-file .env.prod logs -f web
