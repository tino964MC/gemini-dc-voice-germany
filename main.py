import os
import discord
from discord.ext import commands, voice_recv
from src.record import AudioProcessor
from src.gemini import GeminiWebSocket
from dotenv import load_dotenv
load_dotenv()

##### Options #####

# Persona examples:
# "You are a helpful assistant"
# "Take on the persona of a fun goofy robot"
# "Take on the persona of a grumpy old man"
# "Take on the persona of an overly excited motivational speaker"


# Voice options: puck, charon, kore, fenrin, aoede

gemini_ws: GeminiWebSocket = GeminiWebSocket(
# Voice options: puck, charon, kore, fenrin, aoede
    voice="charon", 
    persona="Du bist ein hilfreicher Assistent. Antworte ausschließlich auf Deutsch. Verwende niemals Englisch, auch nicht für Zahlen, Begriffe oder Namen. Alles soll deutsch sein und hast eine und du darfts nich mit emojs antworten Dein Name ist nano",
)

intents: discord.Intents = discord.Intents.default()
intents.message_content = True
bot: commands.Bot = commands.Bot(command_prefix="!", intents=intents)

@bot.tree.command(name="chat")
async def chat(interaction: discord.Interaction) -> None:
    if not interaction.user.voice:
        await interaction.response.send_message("Du musst in eine sprachkannal sein")
        return
    
    voice_client: voice_recv.VoiceRecvClient = await interaction.user.voice.channel.connect(
        cls=voice_recv.VoiceRecvClient
    )
    sink: AudioProcessor = AudioProcessor(
        interaction.user, 
        interaction.channel, 
        bot, 
        gemini_ws
    )
    voice_client.listen(sink)
    
    await interaction.response.send_message("Nano hört zu")

@bot.tree.command(name="exit")
async def exit(interaction: discord.Interaction) -> None:
    if not interaction.guild.voice_client:
        await interaction.response.send_message("ich bin in kein sprachkanal")
        return
        
    if not interaction.user.voice:
        await interaction.response.send_message("Du musst in eine sprachkannal sein")
        return
        
    if interaction.user.voice.channel != interaction.guild.voice_client.channel:
        await interaction.response.send_message("Du musst im gleichen sprach kanal wie ich sein")
        return
        
    await interaction.guild.voice_client.disconnect()
    await interaction.response.send_message("Ciao")

@bot.event
async def on_ready() -> None:
    print(f'Logged in as {bot.user}')
    await bot.tree.sync()
    print('------')
    
    await gemini_ws.connect()

bot.run(os.getenv('DISCORD_TOKEN'))
