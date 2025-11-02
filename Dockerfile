FROM python:3.11-slim

RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py .

RUN mkdir -p downloads

CMD ["python", "bot.py"]
```

4. Cliquez **"Commit changes..."** → **"Commit changes"**

---

### **Fichier 4 : .gitignore**

1. Cliquez sur **"Add file"** → **"Create new file"**
2. Nom du fichier : `.gitignore`
3. Copiez-collez ce contenu :
```
.env
__pycache__/
downloads/
*.mp3
*.m4a
venv/
.DS_Store
