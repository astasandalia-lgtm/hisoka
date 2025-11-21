import os
import discord
from discord import app_commands
from discord.ui import Button, View
import asyncio
import json
import os

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

GUILD_ID = 1420347024376725526
active_games = {}
rank_file = 'rank.json'

def load_rank():
    if os.path.exists(rank_file):
        with open(rank_file, 'r') as f:
            return json.load(f)
    return {}

def save_rank(rank_data):
    with open(rank_file, 'w') as f:
        json.dump(rank_data, f)

def update_rank(winner_id):
    rank_data = load_rank()
    if str(winner_id) not in rank_data:
        rank_data[str(winner_id)] = 0
    rank_data[str(winner_id)] += 1
    save_rank(rank_data)

class TicTacToeButton(Button):
    def __init__(self, x, y, emoji):
        super().__init__(style=discord.ButtonStyle.secondary, emoji=emoji, row=y)
        self.x = x
        self.y = y

    async def callback(self, interaction):
        game = active_games.get(interaction.channel.id)
        if not game:
            return
        
        if interaction.user.id != game['current_player']:
            await interaction.response.defer()
            return
        
        if game['board'][self.y][self.x] != ' ':
            await interaction.response.defer()
            return
        
        player_symbol = '❌' if game['current_player'] == game['players'][0] else '⭕'
        game['board'][self.y][self.x] = player_symbol
        game['moves'] += 1
        
        winner = check_winner(game['board'])
        if winner:
            await end_game(interaction, game, winner)
            return
        
        if game['moves'] >= 9:
            await end_game(interaction, game, 'tie')
            return
        
        game['current_player'] = game['players'][1] if game['current_player'] == game['players'][0] else game['players'][0]
        game['last_move_time'] = asyncio.get_event_loop().time()
        
        current_player_mention = f"<@{game['current_player']}>"
        await update_board(interaction, game, f"🎮 vez de {current_player_mention}!")

class TicTacToeView(View):
    def __init__(self, game):
        super().__init__(timeout=20)
        self.game = game
        self.update_buttons()
    
    def update_buttons(self):
        self.clear_items()
        for y in range(3):
            for x in range(3):
                emoji = self.game['board'][y][x] if self.game['board'][y][x] != ' ' else '➖'
                button = TicTacToeButton(x, y, emoji)
                self.add_item(button)

class ChallengeView(View):
    def __init__(self, challenger, challenged):
        super().__init__(timeout=60)
        self.challenger = challenger
        self.challenged = challenged
    
    @discord.ui.button(style=discord.ButtonStyle.success, emoji='✅')
    async def accept(self, interaction, button):
        if interaction.user.id != self.challenged.id:
            await interaction.response.send_message('❌ apenas o jogador desafiado pode aceitar!', ephemeral=True)
            return
        
        await interaction.response.edit_message(content='🎮 x1 aceito!', view=None)
        await asyncio.sleep(5)
        await interaction.delete_original_response()
        
        guild = interaction.guild
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            self.challenger: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            self.challenged: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True)
        }
        
        channel_name = f'velha-{self.challenger.display_name}-vs-{self.challenged.display_name}'.lower()[:100]
        channel = await guild.create_text_channel(channel_name, overwrites=overwrites)
        
        game = {
            'players': [self.challenger.id, self.challenged.id],
            'current_player': self.challenger.id,
            'board': [[' ' for _ in range(3)] for _ in range(3)],
            'channel_id': channel.id,
            'start_time': asyncio.get_event_loop().time(),
            'last_move_time': asyncio.get_event_loop().time(),
            'moves': 0,
            'task': None
        }
        
        active_games[channel.id] = game
        game['task'] = asyncio.create_task(game_timeout(game))
        
        challenger_mention = f"<@{self.challenger.id}>"
        challenged_mention = f"<@{self.challenged.id}>"
        
        view = TicTacToeView(game)
        await channel.send(f"🎯 **jogo da velha iniciado!**\n\n⚔️ {challenger_mention} ❌ vs ⭕ {challenged_mention}\n\n🎮 vez de {challenger_mention}!", view=view)
    
    @discord.ui.button(style=discord.ButtonStyle.danger, emoji='❌')
    async def decline(self, interaction, button):
        if interaction.user.id != self.challenged.id:
            await interaction.response.send_message('❌ apenas o jogador desafiado pode recusar!', ephemeral=True)
            return
        
        await interaction.response.edit_message(content='😔 convite recusado', view=None)
        await asyncio.sleep(5)
        await interaction.delete_original_response()

def check_winner(board):
    for i in range(3):
        if board[i][0] == board[i][1] == board[i][2] != ' ':
            return board[i][0]
        if board[0][i] == board[1][i] == board[2][i] != ' ':
            return board[0][i]
    
    if board[0][0] == board[1][1] == board[2][2] != ' ':
        return board[0][0]
    if board[0][2] == board[1][1] == board[2][0] != ' ':
        return board[0][2]
    
    return None

async def update_board(interaction, game, message):
    view = TicTacToeView(game)
    await interaction.response.edit_message(content=message, view=view)

async def end_game(interaction, game, result):
    if game['channel_id'] in active_games:
        del active_games[game['channel_id']]
    
    if game['task']:
        game['task'].cancel()
    
    channel = bot.get_channel(game['channel_id'])
    if not channel:
        return
    
    await channel.purge()
    
    overwrites = {
        channel.guild.default_role: discord.PermissionOverwrite(read_messages=False),
        channel.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }
    await channel.edit(overwrites=overwrites)
    
    if result == 'tie':
        final_message = "🤝 **empate!** ninguém venceu desta vez."
    else:
        winner_id = game['players'][0] if result == '❌' else game['players'][1]
        winner_mention = f"<@{winner_id}>"
        final_message = f"🎉 **vitória!** {winner_mention} ganhou o jogo! {result}"
        update_rank(winner_id)
    
    await channel.send(final_message)
    await asyncio.sleep(7)
    await channel.delete()

async def game_timeout(game):
    try:
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < 120:
            elapsed = asyncio.get_event_loop().time() - game['last_move_time']
            if elapsed > 20:
                channel = bot.get_channel(game['channel_id'])
                if channel:
                    game['current_player'] = game['players'][1] if game['current_player'] == game['players'][0] else game['players'][0]
                    game['last_move_time'] = asyncio.get_event_loop().time()
                    current_player_mention = f"<@{game['current_player']}>"
                    view = TicTacToeView(game)
                    await channel.send(f"⏰ tempo esgotado! passando a vez para {current_player_mention}", view=view)
            await asyncio.sleep(1)
        
        channel = bot.get_channel(game['channel_id'])
        if channel and game['channel_id'] in active_games:
            await channel.purge()
            await channel.send("⏰ **tempo total do jogo esgotado!** o jogo foi cancelado.")
            await asyncio.sleep(7)
            await channel.delete()
            del active_games[game['channel_id']]
            
    except asyncio.CancelledError:
        pass

@tree.command(name="velha", description="desafie alguém para um jogo da velha!", guild=discord.Object(id=GUILD_ID))
async def velha(interaction: discord.Interaction, pessoa: discord.Member):
    if pessoa == interaction.user:
        await interaction.response.send_message("❌ você não pode desafiar a si mesmo!", ephemeral=True)
        return
    
    if pessoa.bot:
        await interaction.response.send_message("❌ você não pode desafiar um bot!", ephemeral=True)
        return
    
    view = ChallengeView(interaction.user, pessoa)
    await interaction.response.send_message(f"🎯 {interaction.user.mention} desafiou {pessoa.mention} para um jogo da velha!", view=view)

@tree.command(name="rank", description="mostra o ranking de vitórias no jogo da velha", guild=discord.Object(id=GUILD_ID))
async def rank(interaction: discord.Interaction):
    rank_data = load_rank()
    
    if not rank_data:
        await interaction.response.send_message("📊 **ranking do jogo da velha**\n\n🥺 ainda não há vitórias registradas!")
        return
    
    sorted_rank = sorted(rank_data.items(), key=lambda x: x[1], reverse=True)
    
    embed = discord.Embed(title="🏆 **ranking do jogo da velha**", color=0x00ff00)
    
    for i, (user_id, wins) in enumerate(sorted_rank[:10], 1):
        try:
            user = await bot.fetch_user(int(user_id))
            username = user.display_name
        except:
            username = f"usuário {user_id}"
        
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        
        embed.add_field(
            name=f"{medal} {username}",
            value=f"**{wins}** vitória{'s' if wins > 1 else ''}",
            inline=False
        )
    
    await interaction.response.send_message(embed=embed)

@bot.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    print(f'✅ bot conectado como {bot.user}')

token = os.getenv('TOKEN')
if token:
    bot.run(token)
else:
    print("❌ token não encontrado!")
