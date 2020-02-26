web: gunicorn app:app
web: python setup.py install
worker: rq worker -u redis://127.0.0.1:6379/
web: python portal.py
