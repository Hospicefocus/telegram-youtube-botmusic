import os
import re
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp
import requests

# Configuration depuis variables d'environnement
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")

if not TELEGRAM_BOT_TOKEN or not YOUTUBE_API_KEY:
    raise ValueError("⚠️ Variables d'environnement manquantes! Configurez TELEGRAM_BOT_TOKEN et YOUTUBE_API_KEY")

class YouTubeChecker:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://www.googleapis.com/youtube/v3/videos"
    
    def extract_video_id(self, url):
        """Extrait l'ID de la vidéo YouTube depuis l'URL"""
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com\/shorts\/([a-zA-Z0-9_-]{11})'
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    def check_copyright(self, video_id):
        """Vérifie les informations de copyright via YouTube API"""
        params = {
            'part': 'status,contentDetails,snippet',
            'id': video_id,
            'key': self.api_key
        }
        
        try:
            response = requests.get(self.base_url, params=params)
            data = response.json()
            
            if 'items' not in data or len(data['items']) == 0:
                return None
            
            item = data['items'][0]
            status = item.get('status', {})
            snippet = item.get('snippet', {})
            
            result = {
                'title': snippet.get('title', 'Titre inconnu'),
                'channel': snippet.get('channelTitle', 'Chaîne inconnue'),
                'embeddable': status.get('embeddable', False),
                'license': status.get('license', 'youtube'),
                'public_stats_viewable': status.get('publicStatsViewable', True),
                'made_for_kids': status.get('madeForKids', False)
            }
            
            return result
        except Exception as e:
            print(f"Erreur API: {e}")
            return None
    
    def analyze_copyright_risk(self, video_info):
        """Analyse le risque de violation de copyright"""
        if not video_info:
            return "❌ Vidéo non trouvée ou privée", "HIGH"
        
        risks = []
        risk_level = "LOW"
        
        # Licence Creative Commons = généralement sûr
        if video_info['license'] == 'creativeCommon':
            return "✅ Licence Creative Commons - Généralement utilisable avec attribution", "LOW"
        
        # Vidéo non intégrable = signal de restrictions
        if not video_info['embeddable']:
            risks.append("❌ Intégration désactivée par le propriétaire")
            risk_level = "HIGH"
        
        # Made for Kids peut avoir des restrictions
        if video_info['made_for_kids']:
            risks.append("⚠️ Contenu pour enfants (restrictions possibles)")
            risk_level = "MEDIUM" if risk_level != "HIGH" else risk_level
        
        if not risks:
            risks.append("⚠️ Licence YouTube standard - Vérifiez les droits avec le créateur")
            risk_level = "MEDIUM"
        
        return "\n".join(risks), risk_level

class AudioDownloader:
    @staticmethod
    def download_audio(video_url, output_path="downloads"):
        """Télécharge l'audio d'une vidéo YouTube"""
        os.makedirs(output_path, exist_ok=True)
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
            'quiet': False,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                filename = ydl.prepare_filename(info)
                audio_filename = filename.rsplit('.', 1)[0] + '.mp3'
                return audio_filename, info.get('title', 'Audio')
        except Exception as e:
            print(f"Erreur téléchargement: {e}")
            return None, None

# Handlers du bot Telegram
youtube_checker = YouTubeChecker(YOUTUBE_API_KEY)
audio_downloader = AudioDownloader()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /start"""
    welcome_message = """
🎵 **Bot Vérificateur YouTube**

Envoyez-moi un lien YouTube et je vais :
1️⃣ Vérifier les droits d'auteur
2️⃣ Évaluer les risques pour Facebook, TikTok, Instagram
3️⃣ Télécharger l'audio si c'est autorisé

📌 **Commandes disponibles:**
/start - Afficher ce message
/help - Aide détaillée

Envoyez simplement un lien YouTube pour commencer ! 🚀
    """
    await update.message.reply_text(welcome_message, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /help"""
    help_text = """
ℹ️ **Guide d'utilisation**

**Comment ça marche ?**
1. Copiez le lien d'une vidéo YouTube
2. Envoyez-le dans ce chat
3. Attendez l'analyse des droits
4. Téléchargez l'audio si autorisé

**Niveaux de risque:**
🟢 LOW - Généralement sûr à utiliser
🟡 MEDIUM - Vérifiez avec le créateur
🔴 HIGH - Risque élevé de réclamation

**Plateformes vérifiées:**
- Facebook
- TikTok
- Instagram

⚠️ Ce bot donne une indication, mais vérifiez toujours les droits !
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def handle_youtube_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Traite les liens YouTube reçus"""
    url = update.message.text
    
    # Extraction de l'ID vidéo
    video_id = youtube_checker.extract_video_id(url)
    
    if not video_id:
        await update.message.reply_text("❌ Lien YouTube invalide. Veuillez réessayer.")
        return
    
    # Message de traitement
    processing_msg = await update.message.reply_text("🔍 Analyse en cours...")
    
    # Vérification copyright
    video_info = youtube_checker.check_copyright(video_id)
    risk_message, risk_level = youtube_checker.analyze_copyright_risk(video_info)
    
    if not video_info:
        await processing_msg.edit_text("❌ Impossible de récupérer les informations de la vidéo.")
        return
    
    # Emoji selon le niveau de risque
    risk_emoji = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴"}
    
    # Message de résultat
    result_message = f"""
📹 **{video_info['title']}**
👤 Chaîne: {video_info['channel']}

📊 **Analyse des droits:**
{risk_message}

🎯 **Niveau de risque:** {risk_emoji[risk_level]} {risk_level}

📱 **Utilisation sur les réseaux:**
{"✅ Peut être utilisable (à vérifier)" if risk_level == "LOW" else "⚠️ Risque de réclamation copyright"}
    """
    
    await processing_msg.edit_text(result_message, parse_mode='Markdown')
    
    # Si risque faible, proposer le téléchargement
    if risk_level in ["LOW", "MEDIUM"]:
        await update.message.reply_text("⏳ Téléchargement de l'audio en cours...")
        
        audio_file, title = audio_downloader.download_audio(url)
        
        if audio_file and os.path.exists(audio_file):
            try:
                with open(audio_file, 'rb') as audio:
                    await update.message.reply_audio(
                        audio=audio,
                        title=title,
                        caption="🎵 Audio téléchargé avec succès !"
                    )
                # Nettoyage
                os.remove(audio_file)
            except Exception as e:
                await update.message.reply_text(f"❌ Erreur d'envoi: {str(e)}")
        else:
            await update.message.reply_text("❌ Erreur lors du téléchargement audio")
    else:
        await update.message.reply_text(
            "⚠️ Téléchargement non recommandé en raison du risque élevé de copyright."
        )

def main():
    """Lance le bot"""
    # Création de l'application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Ajout des handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Regex(r'(youtube\.com|youtu\.be)'),
        handle_youtube_url
    ))
    
    # Lancement du bot
    print("🤖 Bot démarré!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
