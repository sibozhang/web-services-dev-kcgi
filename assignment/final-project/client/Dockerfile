FROM python:3.11-alpine

RUN addgroup -S app && adduser -S -G app app

WORKDIR /app
COPY server.py entrypoint.sh /app/
COPY index.html app.css app.js /srv/
RUN chmod +x /app/entrypoint.sh && chown -R app:app /app /srv

USER app

EXPOSE 2027
ENTRYPOINT ["/app/entrypoint.sh"]
