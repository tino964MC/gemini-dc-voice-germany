import traceback
import discord
import asyncio
import speech_recognition as sr
from discord.ext import commands, voice_recv
from src.gemini import GeminiWebSocket

# ---- HIER EINSTELLEN ----
WAKE_WORD = "nano"    # Dein gewünschtes Wake-Word, z.B. "gemini", "marvin", "bot"
USE_WAKE_WORD = True  # Wenn False, antwortet der Bot IMMER, egal ob Wake-Word gesagt wurde
# -------------------------

recognizer = sr.Recognizer()

def convert_audio_to_text_using_google_speech(audio: sr.AudioData) -> str:
    print("Converting audio to text...")
    try:
        command_text: str = recognizer.recognize_google(audio, language="de-DE")
        return command_text.lower()
    except sr.UnknownValueError:
        print("Speech recognition could not understand the audio")
        return "could_not_understand"
    except sr.RequestError as e:
        print(f"Could not request results from speech recognition service; {e}")
        # Rate Limit erkennen!
        if "429" in str(e) or "rate limit" in str(e).lower() or "too many requests" in str(e).lower():
            return "rate_limit"
        return "service_error"
    except Exception as e:
        print(f"Error in speech recognition: {e}")
        return "error"

class AudioProcessor(voice_recv.AudioSink):
    def __init__(self,
                 user: discord.User,
                 channel: discord.TextChannel,
                 bot: commands.Bot,
                 gemini_ws: GeminiWebSocket) -> None:
        super().__init__()
        self.buffer: bytes = b""
        self.target_user: discord.User = user
        self.recording_active: bool = False
        self.channel: discord.TextChannel = channel
        self.bot: commands.Bot = bot
        self.gemini_ws: GeminiWebSocket = gemini_ws
        self.known_ssrcs = set()
        self._voice_client = None  # Eigener Name, um Konflikte zu vermeiden

    def wants_opus(self) -> bool:
        return False

    def write(self, user, audio_data):
        if hasattr(audio_data, 'ssrc') and audio_data.ssrc not in self.known_ssrcs:
            self.known_ssrcs.add(audio_data.ssrc)
            print(f"Registered new SSRC: {audio_data.ssrc} from user {user}")
        if self.recording_active and audio_data.pcm:
            if user == self.target_user:
                self.buffer += audio_data.pcm

    @voice_recv.AudioSink.listener()
    def on_voice_member_speaking_start(self, member: discord.Member) -> None:
        print(f"User {member} started speaking.")
        if member == self.target_user:
            if self._voice_client and self._voice_client.is_playing():
                self._voice_client.stop_playing()
            self.recording_active = True

    @voice_recv.AudioSink.listener()
    def on_voice_member_speaking_stop(self, member: discord.Member) -> None:
        print(f"User {member.name} stopped speaking.")
        if member == self.target_user:
            self.recording_active = False

            if self.buffer:
                try:
                    print("Audio capture stopped")
                    sample_rate = 48000
                    sample_width = 4

                    audio_data = sr.AudioData(self.buffer, sample_rate, sample_width)
                    wav_data = audio_data.get_wav_data()

                    if not wav_data or not wav_data.strip():
                        print("No words captured - audio appears to be silence")
                        self.buffer = b""
                        return

                    audio_length = len(self.buffer) / (sample_rate * sample_width)
                    if audio_length < 0.3:
                        print("Audio too short - likely not a complete word")
                        self.buffer = b""
                        return

                    self.buffer = b""

                    if audio_data.get_wav_data().strip():
                        result = convert_audio_to_text_using_google_speech(audio_data)
                        # Fehlerbehandlung:
                        if result in ["rate_limit", "service_error", "error"]:
                            if result == "rate_limit":
                                future = asyncio.run_coroutine_threadsafe(
                                    self.channel.send("Google Speech API: Rate Limit erreicht. Bitte warte einen Moment, bevor du es erneut versuchst."),
                                    self.bot.loop
                                )
                            elif result == "service_error":
                                future = asyncio.run_coroutine_threadsafe(
                                    self.channel.send("Probleme mit dem Sprachservice. Bitte später erneut versuchen."),
                                    self.bot.loop
                                )
                            else:
                                future = asyncio.run_coroutine_threadsafe(
                                    self.channel.send("Etwas ist schiefgelaufen. Ich bin bereit zuzuhören."),
                                    self.bot.loop
                                )
                            try:
                                future.result(timeout=5)
                            except Exception as e:
                                print(f"Fehler beim senden der nachricht: {e}")
                            return
                        # Kein "Ich konnte dich nicht verstehen." mehr!

                        print(f"Text: {result}")

                        # ---- WAKE-WORD LOGIK ----
                        antworten = True
                        frage = result
                        if USE_WAKE_WORD and WAKE_WORD:
                            if result.startswith(WAKE_WORD):
                                frage = result[len(WAKE_WORD):].strip()
                                if not frage:
                                    frage = "hallo"
                                print(f"Wake-Word erkannt! Frage an Gemini: {frage}")
                            else:
                                antworten = False
                                print(f"Wake-Word '{WAKE_WORD}' nicht erkannt, keine Antwort!")
                                # Optional: Discord-Hinweis
                                # asyncio.run_coroutine_threadsafe(
                                #     self.channel.send(f"bitte beginne deinen Satz mit '{WAKE_WORD}', damit ich antworte."),
                                #     self.bot.loop
                                # )
                        else:
                            print("Wake-Word deaktiviert oder leer – Bot antwortet immer.")

                        if antworten:
                            asyncio.run_coroutine_threadsafe(self.gemini_ws.process_text(frage, self._voice_client), self.bot.loop)
                except Exception as e:
                    print(f"Error processing audio: {e}")
                    traceback.print_exc()

    def cleanup(self) -> None:
        pass
