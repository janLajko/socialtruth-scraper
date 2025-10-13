FROM python:3.13
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY truthsocial_scraper.py .
CMD ["python", "truthsocial_scraper.py", "--limit", "1"]