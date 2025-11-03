FROM python:3.11-slim

# Mettre à jour et installer FFmpeg avec nettoyage
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copier et installer les dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code du bot
COPY bot.py .

# Créer le dossier de téléchargements
RUN mkdir -p downloads

# Lancer le bot
CMD ["python", "-u", "bot.py"]
