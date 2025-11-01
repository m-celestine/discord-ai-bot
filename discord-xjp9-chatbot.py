import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from openai import OpenAI

# -------------------------------
# Load environment variables (API Keys)
# -------------------------------
load_dotenv()   # Load variables from .env file
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# -------------------------------
# Initialize Discord bot
# -------------------------------
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True  # Required for reading message content
bot = commands.Bot(command_prefix=commands.when_mentioned_or("!"), intents=intents)

# -------------------------------
# Initialize DeepSeek client
# -------------------------------
deepseek_client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

# -------------------------------
# Global state
# -------------------------------
current_character = {
    "name": "XJ-9",
    "description": (
        "XJ-9, aka Jenny Wakeman, is a teenage robot hero. "
        "Energetic, clever, sarcastic, and loves hanging out with friends. "
        "She can be heroic and serious when needed but often injects humor and quirkiness."
    )
}
persona_loading_message = "🤖 Jenny’s gears are spinning… beep boop!"  # Default
persona_greeting_message = "Strikes a dramatic pose, hands on hips. Ready for action! So, what's up?"
ALLOWED_CHANNELS = set()  # Discord channel IDs where the bot is allowed
channel_memory = {}  # Per-channel conversation memory

# -------------------------------
# Helper functions
# -------------------------------
def generate_persona_loading_message():
    """Generate a short loading message in the voice of the current character."""
    try:
        response = deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "Generate a short fun 'loading' message in the persona's voice."},
                {"role": "user", "content": f"Persona: {current_character['name']} - {current_character['description']}"}
            ],
            stream=False
        )
        return response.choices[0].message.content
    except Exception as e:
        print("Error generating loading message:", e)
        return "🤖 Jenny’s gears are spinning… beep boop!"

def generate_persona_greeting_message():
    """Generate a greeting message in the voice of the current character."""
    try:
        response = deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "Generate a fun greeting message in the persona's voice."},
                {"role": "user", "content": f"Persona: {current_character['name']} - {current_character['description']}"}
            ],
            stream=False
        )
        return response.choices[0].message.content
    except Exception as e:
        print("Error generating greeting message:", e)
        return "Strikes a dramatic pose, hands on hips. Ready for action!"

def get_deepseek_response(messages):
    """Call DeepSeek API with a list of messages (conversation history)."""
    try:
        response = deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            stream=False
        )
        return response.choices[0].message.content
    except Exception as e:
        print("DeepSeek API error:", e)
        return "🤖 Oops! I couldn't reach my AI brain..."

def is_message_relevant(channel_id, message_content):
    """Check if a user message is relevant to the ongoing conversation."""
    try:
        memory = channel_memory.get(channel_id, [])
        context_messages = memory[-6:] if memory else []
        messages = context_messages + [
            {"role": "system", "content": "You are a helpful AI. Decide if the next message is related to the current conversation."},
            {"role": "user", "content": f"Message to check: '{message_content}'"}
        ]
        response = deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            stream=False
        )
        answer = response.choices[0].message.content.strip().lower()
        return "yes" in answer
    except Exception as e:
        print("Relevance check error:", e)
        return True  # Default True if API fails

# -------------------------------
# Bot Events
# -------------------------------
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Only respond if:
    # 1️⃣ The message mentions the bot alone
    # 2️⃣ Or the message starts with the command prefix
    if (bot.user in message.mentions and len(message.mentions) == 1) or message.content.startswith(bot.command_prefix):
        if message.channel.id in ALLOWED_CHANNELS:
            user_message = message.content

            # Check relevance
            if not is_message_relevant(message.channel.id, user_message):
                channel_memory[message.channel.id] = []  # reset memory
                await message.channel.send("🧹 Resetting conversation due to off-topic message...")

            # Add user message to memory
            channel_memory.setdefault(message.channel.id, []).append({"role": "user", "content": user_message})

            async with message.channel.typing():
                loading_msg = await message.channel.send(persona_loading_message)
                bot_response = get_deepseek_response(
                    [{"role": "system", "content": f"You are {current_character['name']}, {current_character['description']}."}] + 
                    channel_memory[message.channel.id]
                )
                channel_memory[message.channel.id].append({"role": "assistant", "content": bot_response})
                await loading_msg.edit(content=bot_response)

    await bot.process_commands(message)

# -------------------------------
# Commands
# -------------------------------
@bot.command(name="setcharacter")
async def set_character(ctx, name: str, *, description: str):
    global current_character, persona_loading_message, persona_greeting_message
    current_character["name"] = name
    current_character["description"] = description

    # Generate persona-specific messages
    persona_loading_message = generate_persona_loading_message()
    persona_greeting_message = generate_persona_greeting_message()

    await ctx.send(f"✨ Persona changed! Now speaking as **{name}**.\n{description}")
    await ctx.send(f"_Loading message set to: {persona_loading_message}_")
    await ctx.send(f"_Greeting message updated: {persona_greeting_message}_")

@bot.command(name="allowchannel")
@commands.has_permissions(administrator=True)
async def allow_channel(ctx, channel: discord.TextChannel):
    ALLOWED_CHANNELS.add(channel.id)
    await ctx.send(f"✅ {channel.mention} has been added to allowed AI channels.")
    await channel.send(persona_greeting_message)

@bot.command(name="removechannel")
@commands.has_permissions(administrator=True)
async def remove_channel(ctx, channel: discord.TextChannel):
    ALLOWED_CHANNELS.discard(channel.id)
    await ctx.send(f"❌ {channel.mention} has been removed from allowed AI channels.")

# -------------------------------
# Run bot
# -------------------------------
bot.run(DISCORD_TOKEN)
