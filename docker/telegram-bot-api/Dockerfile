FROM aiogram/telegram-bot-api:latest

COPY entrypoint-railway.sh /entrypoint-railway.sh
RUN chmod +x /entrypoint-railway.sh

ENTRYPOINT ["/entrypoint-railway.sh"]