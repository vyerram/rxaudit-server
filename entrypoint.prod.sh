python manage.py collectstatic --noinput;
python manage.py migrate --no-input;
python manage.py initadmin;
python manage.py compile_code;