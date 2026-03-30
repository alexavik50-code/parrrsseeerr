# Берем готовую систему от создателей Playwright, где УЖЕ есть все нужные библиотеки
FROM mcr.microsoft.com/playwright/python:v1.41.0-jammy

# Создаем папку для нашего бота
WORKDIR /app

# Копируем файл с библиотеками и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем сам код бота
COPY bot.py .

# Команда для запуска
CMD ["python", "bot.py"]
