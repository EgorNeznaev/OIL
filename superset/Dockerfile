FROM apache/superset:4.0.2

USER root
RUN pip install --no-cache-dir psycopg2-binary
USER superset

COPY superset_init.sh /app/superset_init.sh
RUN chmod +x /app/superset_init.sh
COPY superset_config.py /app/pythonpath/superset_config.py

ENV SUPERSET_CONFIG_PATH=/app/pythonpath/superset_config.py

CMD ["/bin/bash", "/app/superset_init.sh"]
