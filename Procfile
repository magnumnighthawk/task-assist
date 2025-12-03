web: gunicorn -b 0.0.0.0:9000 application:app
streamlit: streamlit run streamlit_app.py --server.headless=true
celery: celery -A celery_app worker --loglevel=info
schedule: python schedule.py
slack: python slack_interactive.py
redis: redis-server
agent: adk web --port 3000 --reload_agents agents