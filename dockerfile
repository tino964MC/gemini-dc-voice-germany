# Basis-Image mit Python
FROM python:3.11-slim

# Arbeitsverzeichnis im Container
WORKDIR /main

# Dependencies installieren (falls du requirements.txt hast)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code kopieren
COPY . .

# Standard-Befehl (z. B. wenn main.py die App startet)
CMD ["python", "main.py"]


