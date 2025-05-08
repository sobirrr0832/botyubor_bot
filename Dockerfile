FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Vaqt zonasini O'zbekiston vaqti bo'yicha sozlash
ENV TZ=Asia/Tashkent
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# SQLite ma'lumotlar bazasini saqlash uchun volume
VOLUME ["/app/data"]

CMD ["python", "telegram_bot.py"]
