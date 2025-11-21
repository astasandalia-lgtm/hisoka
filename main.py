import os
import discord
from discord import app_commands
from discord.ui import Button, View
import asyncio
import json
import random

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

GUILD_ID = 1420347024376725526
active_games = {}

# Sistema de economia simples
economy_file = 'economy.json'

def load_economy():
    if os.path.exists(economy_file):
        with open(economy_file, 'r') as f:
            return json.load(f)
    return {}

def save_economy(economy_data):
    with open(economy_file, 'w') as f:
        json.dump(economy_data, f)

def get_user_money(user_id):
    economy_data = load_economy()
    user_id_str = str(user_id)
    
    if user_id_str not in economy_data:
        economy_data[user_id_str] = 100  # Saldo inicial
        save_economy(economy_data)
    
    return economy_data[user_id_str]

def update_user_money(user_id, amount):
    economy_data = load_economy()
    user_id_str = str(user_id)
    
    if user_id_str not in economy_data:
        economy_data[user_id_str] = 100
    
    economy_data[user_id_str] += amount
    save_economy(economy_data)
    return economy_data[user_id_str]

# ========== JOGO DA VELHA ==========

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
            await interaction.response.send_message("❌ Não é sua vez!", ephemeral=True)
            return
        
        if game['board'][self.y][self.x] != ' ':
            await interaction.response.send_message("❌ Posição já ocupada!", ephemeral=True)
            return
        
        player_symbol = '❌' if game['current_player'] == game['players'][0] else '⭕'
        game['board'][self.y][self.x] = player_symbol
        
        winner = check_winner(game['board'])
        if winner:
            # Dar recompensa ao vencedor
            reward = 50
            update_user_money(game['players'][0] if winner == '❌' else game['players'][1], reward)
            
            winner_id = game['players'][0] if winner == '❌' else game['players'][1]
            await end_game(interaction, game, winner, winner_id, reward)
            return
        
        if all(cell != ' ' for row in game['board'] for cell in row):
            # Empate - dar recompensa menor para ambos
            reward = 10
            update_user_money(game['players'][0], reward)
            update_user_money(game['players'][1], reward)
            await end_game(interaction, game, 'tie', None, reward)
            return
        
        game['current_player'] = game['players'][1] if game['current_player'] == game['players'][0] else game['players'][0]
        
        current_player_mention = f"<@{game['current_player']}>"
        await update_board(interaction, game, f"🎮 Vez de {current_player_mention}")

class TicTacToeView(View):
    def __init__(self, game):
        super().__init__(timeout=30)
        self.game = game
        self.update_buttons()
    
    def update_buttons(self):
        self.clear_items()
        for y in range(3):
            for x in range(3):
                emoji = self.game['board'][y][x] if self.game['board'][y][x] != ' ' else '➖'
                button = TicTacToeButton(x, y, emoji)
                self.add_item(button)

def check_winner(board):
    # Linhas
    for i in range(3):
        if board[i][0] == board[i][1] == board[i][2] != ' ':
            return board[i][0]
    # Colunas
    for i in range(3):
        if board[0][i] == board[1][i] == board[2][i] != ' ':
            return board[0][i]
    # Diagonais
    if board[0][0] == board[1][1] == board[2][2] != ' ':
        return board[0][0]
    if board[0][2] == board[1][1] == board[2][0] != ' ':
        return board[0][2]
    return None

async def update_board(interaction, game, message):
    view = TicTacToeView(game)
    await interaction.response.edit_message(content=message, view=view)

async def end_game(interaction, game, result, winner_id=None, reward=0):
    if game['channel_id'] in active_games:
        del active_games[game['channel_id']]
    
    if result == 'tie':
        final_message = f"🤝 **Empate!** Ambos ganharam `{reward}` moedas!"
    else:
        winner_mention = f"<@{winner_id}>"
        final_message = f"🎉 **Vitória!** {winner_mention} ganhou o jogo! {result}\n💰 Recebeu `{reward}` moedas!"
    
    view = TicTacToeView(game)
    await interaction.response.edit_message(content=final_message, view=view)
    
    # Deletar canal após 10 segundos
    await asyncio.sleep(10)
    try:
        channel = bot.get_channel(game['channel_id'])
        if channel:
            await channel.delete()
    except:
        pass

# ========== JOGO DE DADOS ==========

class DiceView(View):
    def __init__(self, player1, player2, bet):
        super().__init__(timeout=30)
        self.player1 = player1
        self.player2 = player2
        self.bet = bet
        self.rolls = {}
    
    @discord.ui.button(label="🎲 Rolar Dado", style=discord.ButtonStyle.primary)
    async def roll_dice(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id not in [self.player1.id, self.player2.id]:
            await interaction.response.send_message("❌ Você não está neste jogo!", ephemeral=True)
            return
        
        if interaction.user.id in self.rolls:
            await interaction.response.send_message("❌ Você já rolou o dado!", ephemeral=True)
            return
        
        # Rolar dado
        dice_roll = random.randint(1, 6)
        self.rolls[interaction.user.id] = dice_roll
        
        await interaction.response.send_message(f"🎲 {interaction.user.mention} rolou: **{dice_roll}**", ephemeral=True)
        
        # Verificar se ambos jogaram
        if len(self.rolls) == 2:
            roll1 = self.rolls[self.player1.id]
            roll2 = self.rolls[self.player2.id]
            
            if roll1 > roll2:
                winner = self.player1
                loser = self.player2
            elif roll2 > roll1:
                winner = self.player2
                loser = self.player1
            else:
                # Empate
                update_user_money(self.player1.id, self.bet)
                update_user_money(self.player2.id, self.bet)
                embed = discord.Embed(title="🎲 **Empate nos Dados!**", color=0xffff00)
                embed.add_field(name=f"🎯 {self.player1.display_name}", value=f"**{roll1}**", inline=True)
                embed.add_field(name=f"🎯 {self.player2.display_name}", value=f"**{roll2}**", inline=True)
                embed.add_field(name="💰 Resultado", value=f"Ambos receberam `{self.bet}` moedas de volta!", inline=False)
                await interaction.message.edit(embed=embed, view=None)
                return
            
            # Dar recompensa ao vencedor
            update_user_money(winner.id, self.bet)
            update_user_money(loser.id, -self.bet)
            
            embed = discord.Embed(title="🎲 **Resultado dos Dados**", color=0x00ff00)
            embed.add_field(name=f"🎯 {self.player1.display_name}", value=f"**{roll1}**", inline=True)
            embed.add_field(name=f"🎯 {self.player2.display_name}", value=f"**{roll2}**", inline=True)
            embed.add_field(name="🏆 Vencedor", value=f"{winner.mention}", inline=False)
            embed.add_field(name="💰 Prêmio", value=f"`{self.bet}` moedas", inline=False)
            
            await interaction.message.edit(embed=embed, view=None)

# ========== CARA OU COROA ==========

class CoinFlipView(View):
    def __init__(self, player1, player2, bet):
        super().__init__(timeout=30)
        self.player1 = player1
        self.player2 = player2
        self.bet = bet
        self.choices = {}
    
    @discord.ui.button(label="🥚 Cara", style=discord.ButtonStyle.primary)
    async def heads(self, interaction: discord.Interaction, button: Button):
        await self.choose_side(interaction, "cara")
    
    @discord.ui.button(label="🪙 Coroa", style=discord.ButtonStyle.primary)
    async def tails(self, interaction: discord.Interaction, button: Button):
        await self.choose_side(interaction, "coroa")
    
    async def choose_side(self, interaction: discord.Interaction, choice):
        if interaction.user.id not in [self.player1.id, self.player2.id]:
            await interaction.response.send_message("❌ Você não está neste jogo!", ephemeral=True)
            return
        
        if interaction.user.id in self.choices:
            await interaction.response.send_message("❌ Você já escolheu!", ephemeral=True)
            return
        
        self.choices[interaction.user.id] = choice
        await interaction.response.send_message(f"✅ Você escolheu: **{choice}**", ephemeral=True)
        
        # Verificar se ambos escolheram
        if len(self.choices) == 2:
            # Sortear resultado
            result = random.choice(["cara", "coroa"])
            
            # Determinar vencedores
            winners = []
            for user_id, choice in self.choices.items():
                if choice == result:
                    winners.append(user_id)
            
            embed = discord.Embed(title="🪙 **Resultado - Cara ou Coroa**", color=0xffd700)
            embed.add_field(name="🎯 Resultado", value=f"**{result.upper()}**", inline=False)
            embed.add_field(name=f"🥚 {self.player1.display_name}", value=f"`{self.choices.get(self.player1.id, 'Não escolheu')}`", inline=True)
            embed.add_field(name=f"🪙 {self.player2.display_name}", value=f"`{self.choices.get(self.player2.id, 'Não escolheu')}`", inline=True)
            
            if winners:
                if len(winners) == 1:
                    # Apenas um vencedor
                    winner_id = winners[0]
                    winner = self.player1 if winner_id == self.player1.id else self.player2
                    update_user_money(winner_id, self.bet)
                    embed.add_field(name="🏆 Vencedor", value=f"{winner.mention}", inline=False)
                    embed.add_field(name="💰 Prêmio", value=f"`{self.bet}` moedas", inline=False)
                else:
                    # Empate - ambos ganham metade
                    half_bet = self.bet // 2
                    update_user_money(self.player1.id, half_bet)
                    update_user_money(self.player2.id, half_bet)
                    embed.add_field(name="🤝 Empate", value=f"Ambos ganharam `{half_bet}` moedas!", inline=False)
            else:
                # Ninguém acertou - devolver apostas
                update_user_money(self.player1.id, self.bet)
                update_user_money(self.player2.id, self.bet)
                embed.add_field(name="😔 Resultado", value="Ninguém acertou! Apostas devolvidas.", inline=False)
            
            await interaction.message.edit(embed=embed, view=None)

# ========== PEDRA, PAPEL, TESOURA ==========

class RPSView(View):
    def __init__(self, player1, player2, bet):
        super().__init__(timeout=30)
        self.player1 = player1
        self.player2 = player2
        self.bet = bet
        self.choices = {}
    
    @discord.ui.button(label="🪨 Pedra", style=discord.ButtonStyle.primary)
    async def rock(self, interaction: discord.Interaction, button: Button):
        await self.make_choice(interaction, "pedra")
    
    @discord.ui.button(label="📄 Papel", style=discord.ButtonStyle.success)
    async def paper(self, interaction: discord.Interaction, button: Button):
        await self.make_choice(interaction, "papel")
    
    @discord.ui.button(label="✂️ Tesoura", style=discord.ButtonStyle.danger)
    async def scissors(self, interaction: discord.Interaction, button: Button):
        await self.make_choice(interaction, "tesoura")
    
    async def make_choice(self, interaction: discord.Interaction, choice):
        if interaction.user.id not in [self.player1.id, self.player2.id]:
            await interaction.response.send_message("❌ Você não está neste jogo!", ephemeral=True)
            return
        
        if interaction.user.id in self.choices:
            await interaction.response.send_message("❌ Você já escolheu!", ephemeral=True)
            return
        
        self.choices[interaction.user.id] = choice
        await interaction.response.send_message(f"✅ Você escolheu: **{choice}**", ephemeral=True)
        
        # Verificar se ambos escolheram
        if len(self.choices) == 2:
            choice1 = self.choices[self.player1.id]
            choice2 = self.choices[self.player2.id]
            
            # Determinar vencedor
            if choice1 == choice2:
                result = "empate"
            elif (choice1 == "pedra" and choice2 == "tesoura") or \
                 (choice1 == "papel" and choice2 == "pedra") or \
                 (choice1 == "tesoura" and choice2 == "papel"):
                result = "player1"
            else:
                result = "player2"
            
            embed = discord.Embed(title="👊 **Resultado - Pedra, Papel, Tesoura**", color=0x00ff00)
            embed.add_field(name=f"🎯 {self.player1.display_name}", value=f"`{choice1}`", inline=True)
            embed.add_field(name=f"🎯 {self.player2.display_name}", value=f"`{choice2}`", inline=True)
            
            if result == "empate":
                update_user_money(self.player1.id, self.bet)
                update_user_money(self.player2.id, self.bet)
                embed.add_field(name="🤝 Empate", value=f"Ambos receberam `{self.bet}` moedas de volta!", inline=False)
            else:
                winner = self.player1 if result == "player1" else self.player2
                loser = self.player2 if result == "player1" else self.player1
                update_user_money(winner.id, self.bet)
                update_user_money(loser.id, -self.bet)
                embed.add_field(name="🏆 Vencedor", value=f"{winner.mention}", inline=False)
                embed.add_field(name="💰 Prêmio", value=f"`{self.bet}` moedas", inline=False)
            
            await interaction.message.edit(embed=embed, view=None)

# ========== ADIVINHAÇÃO DE NÚMERO ==========

class NumberGuessView(View):
    def __init__(self, player1, player2, bet):
        super().__init__(timeout=30)
        self.player1 = player1
        self.player2 = player2
        self.bet = bet
        self.number = random.randint(1, 10)
        self.guesses = {}
    
    @discord.ui.button(label="1", style=discord.ButtonStyle.secondary)
    async def num1(self, interaction: discord.Interaction, button: Button):
        await self.make_guess(interaction, 1)
    
    @discord.ui.button(label="2", style=discord.ButtonStyle.secondary)
    async def num2(self, interaction: discord.Interaction, button: Button):
        await self.make_guess(interaction, 2)
    
    @discord.ui.button(label="3", style=discord.ButtonStyle.secondary)
    async def num3(self, interaction: discord.Interaction, button: Button):
        await self.make_guess(interaction, 3)
    
    @discord.ui.button(label="4", style=discord.ButtonStyle.secondary)
    async def num4(self, interaction: discord.Interaction, button: Button):
        await self.make_guess(interaction, 4)
    
    @discord.ui.button(label="5", style=discord.ButtonStyle.secondary)
    async def num5(self, interaction: discord.Interaction, button: Button):
        await self.make_guess(interaction, 5)
    
    @discord.ui.button(label="6", style=discord.ButtonStyle.secondary)
    async def num6(self, interaction: discord.Interaction, button: Button):
        await self.make_guess(interaction, 6)
    
    @discord.ui.button(label="7", style=discord.ButtonStyle.secondary)
    async def num7(self, interaction: discord.Interaction, button: Button):
        await self.make_guess(interaction, 7)
    
    @discord.ui.button(label="8", style=discord.ButtonStyle.secondary)
    async def num8(self, interaction: discord.Interaction, button: Button):
        await self.make_guess(interaction, 8)
    
    @discord.ui.button(label="9", style=discord.ButtonStyle.secondary)
    async def num9(self, interaction: discord.Interaction, button: Button):
        await self.make_guess(interaction, 9)
    
    @discord.ui.button(label="10", style=discord.ButtonStyle.secondary)
    async def num10(self, interaction: discord.Interaction, button: Button):
        await self.make_guess(interaction, 10)
    
    async def make_guess(self, interaction: discord.Interaction, guess):
        if interaction.user.id not in [self.player1.id, self.player2.id]:
            await interaction.response.send_message("❌ Você não está neste jogo!", ephemeral=True)
            return
        
        if interaction.user.id in self.guesses:
            await interaction.response.send_message("❌ Você já palpitou!", ephemeral=True)
            return
        
        self.guesses[interaction.user.id] = guess
        await interaction.response.send_message(f"✅ Você palpitou: **{guess}**", ephemeral=True)
        
        # Verificar se ambos palpitarem
        if len(self.guesses) == 2:
            guess1 = self.guesses[self.player1.id]
            guess2 = self.guesses[self.player2.id]
            
            # Calcular diferenças
            diff1 = abs(guess1 - self.number)
            diff2 = abs(guess2 - self.number)
            
            embed = discord.Embed(title="🎯 **Resultado - Adivinhe o Número**", color=0x00ff00)
            embed.add_field(name="🔢 Número Secreto", value=f"**{self.number}**", inline=False)
            embed.add_field(name=f"🎯 {self.player1.display_name}", value=f"Palpite: `{guess1}` (diferença: {diff1})", inline=True)
            embed.add_field(name=f"🎯 {self.player2.display_name}", value=f"Palpite: `{guess2}` (diferença: {diff2})", inline=True)
            
            if diff1 < diff2:
                winner = self.player1
            elif diff2 < diff1:
                winner = self.player2
            else:
                # Empate
                update_user_money(self.player1.id, self.bet)
                update_user_money(self.player2.id, self.bet)
                embed.add_field(name="🤝 Empate", value=f"Ambos receberam `{self.bet}` moedas de volta!", inline=False)
                await interaction.message.edit(embed=embed, view=None)
                return
            
            update_user_money(winner.id, self.bet)
            update_user_money(self.player2.id if winner.id == self.player1.id else self.player1.id, -self.bet)
            embed.add_field(name="🏆 Vencedor", value=f"{winner.mention}", inline=False)
            embed.add_field(name="💰 Prêmio", value=f"`{self.bet}` moedas", inline=False)
            
            await interaction.message.edit(embed=embed, view=None)

# ========== COMANDOS ==========

@tree.command(name="velha", description="🎮 Desafie alguém para um jogo da velha!", guild=discord.Object(id=GUILD_ID))
async def velha(interaction: discord.Interaction, pessoa: discord.Member):
    if pessoa == interaction.user:
        await interaction.response.send_message("❌ Você não pode desafiar a si mesmo!", ephemeral=True)
        return
    
    if pessoa.bot:
        await interaction.response.send_message("❌ Você não pode desafiar um bot!", ephemeral=True)
        return
    
    # Criar canal privado
    guild = interaction.guild
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        pessoa: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True)
    }
    
    channel_name = f'velha-{interaction.user.display_name}-vs-{pessoa.display_name}'.lower()[:100]
    channel = await guild.create_text_channel(channel_name, overwrites=overwrites)
    
    # Criar jogo
    game = {
        'players': [interaction.user.id, pessoa.id],
        'current_player': interaction.user.id,
        'board': [[' ' for _ in range(3)] for _ in range(3)],
        'channel_id': channel.id
    }
    
    active_games[channel.id] = game
    
    challenger_mention = f"<@{interaction.user.id}>"
    challenged_mention = f"<@{pessoa.id}>"
    
    view = TicTacToeView(game)
    await channel.send(f"🎯 **Jogo da Velha Iniciado!**\n\n⚔️ {challenger_mention} ❌ vs ⭕ {challenged_mention}\n\n🎮 Vez de {challenger_mention}", view=view)
    await interaction.response.send_message(f"🎮 Canal criado: {channel.mention}", ephemeral=True)

@tree.command(name="dados", description="🎲 Jogue dados contra alguém", guild=discord.Object(id=GUILD_ID))
async def dados(interaction: discord.Interaction, pessoa: discord.Member, aposta: int = 10):
    if pessoa == interaction.user:
        await interaction.response.send_message("❌ Você não pode jogar contra si mesmo!", ephemeral=True)
        return
    
    if pessoa.bot:
        await interaction.response.send_message("❌ Você não pode jogar contra um bot!", ephemeral=True)
        return
    
    # Verificar saldo
    user1_money = get_user_money(interaction.user.id)
    user2_money = get_user_money(pessoa.id)
    
    if user1_money < aposta:
        await interaction.response.send_message("❌ Você não tem moedas suficientes!", ephemeral=True)
        return
    
    if user2_money < aposta:
        await interaction.response.send_message("❌ O outro jogador não tem moedas suficientes!", ephemeral=True)
        return
    
    embed = discord.Embed(title="🎲 **Jogo de Dados**", color=0x00ff00)
    embed.add_field(name="👥 Jogadores", value=f"{interaction.user.mention} vs {pessoa.mention}", inline=False)
    embed.add_field(name="💰 Aposta", value=f"`{aposta}` moedas cada", inline=False)
    embed.add_field(name="🎯 Como Jogar", value="Cada um rola um dado. Quem tirar o número maior ganha!", inline=False)
    
    view = DiceView(interaction.user, pessoa, aposta)
    await interaction.response.send_message(embed=embed, view=view)

@tree.command(name="cara_coroa", description="🪙 Cara ou coroa contra alguém", guild=discord.Object(id=GUILD_ID))
async def cara_coroa(interaction: discord.Interaction, pessoa: discord.Member, aposta: int = 10):
    if pessoa == interaction.user:
        await interaction.response.send_message("❌ Você não pode jogar contra si mesmo!", ephemeral=True)
        return
    
    if pessoa.bot:
        await interaction.response.send_message("❌ Você não pode jogar contra um bot!", ephemeral=True)
        return
    
    # Verificar saldo
    user1_money = get_user_money(interaction.user.id)
    user2_money = get_user_money(pessoa.id)
    
    if user1_money < aposta:
        await interaction.response.send_message("❌ Você não tem moedas suficientes!", ephemeral=True)
        return
    
    if user2_money < aposta:
        await interaction.response.send_message("❌ O outro jogador não tem moedas suficientes!", ephemeral=True)
        return
    
    embed = discord.Embed(title="🪙 **Cara ou Coroa**", color=0xffd700)
    embed.add_field(name="👥 Jogadores", value=f"{interaction.user.mention} vs {pessoa.mention}", inline=False)
    embed.add_field(name="💰 Aposta", value=f"`{aposta}` moedas cada", inline=False)
    embed.add_field(name="🎯 Como Jogar", value="Escolham cara ou coroa. Quem acertar o resultado ganha!", inline=False)
    
    view = CoinFlipView(interaction.user, pessoa, aposta)
    await interaction.response.send_message(embed=embed, view=view)

@tree.command(name="ppt", description="👊 Pedra, papel ou tesoura contra alguém", guild=discord.Object(id=GUILD_ID))
async def ppt(interaction: discord.Interaction, pessoa: discord.Member, aposta: int = 10):
    if pessoa == interaction.user:
        await interaction.response.send_message("❌ Você não pode jogar contra si mesmo!", ephemeral=True)
        return
    
    if pessoa.bot:
        await interaction.response.send_message("❌ Você não pode jogar contra um bot!", ephemeral=True)
        return
    
    # Verificar saldo
    user1_money = get_user_money(interaction.user.id)
    user2_money = get_user_money(pessoa.id)
    
    if user1_money < aposta:
        await interaction.response.send_message("❌ Você não tem moedas suficientes!", ephemeral=True)
        return
    
    if user2_money < aposta:
        await interaction.response.send_message("❌ O outro jogador não tem moedas suficientes!", ephemeral=True)
        return
    
    embed = discord.Embed(title="👊 **Pedra, Papel, Tesoura**", color=0x00ff00)
    embed.add_field(name="👥 Jogadores", value=f"{interaction.user.mention} vs {pessoa.mention}", inline=False)
    embed.add_field(name="💰 Aposta", value=f"`{aposta}` moedas cada", inline=False)
    embed.add_field(name="🎯 Como Jogar", value="Escolham entre pedra, papel ou tesoura. Pedra > Tesoura > Papel > Pedra", inline=False)
    
    view = RPSView(interaction.user, pessoa, aposta)
    await interaction.response.send_message(embed=embed, view=view)

@tree.command(name="adivinhar", description="🎯 Adivinhe o número contra alguém", guild=discord.Object(id=GUILD_ID))
async def adivinhar(interaction: discord.Interaction, pessoa: discord.Member, aposta: int = 10):
    if pessoa == interaction.user:
        await interaction.response.send_message("❌ Você não pode jogar contra si mesmo!", ephemeral=True)
        return
    
    if pessoa.bot:
        await interaction.response.send_message("❌ Você não pode jogar contra um bot!", ephemeral=True)
        return
    
    # Verificar saldo
    user1_money = get_user_money(interaction.user.id)
    user2_money = get_user_money(pessoa.id)
    
    if user1_money < aposta:
        await interaction.response.send_message("❌ Você não tem moedas suficientes!", ephemeral=True)
        return
    
    if user2_money < aposta:
        await interaction.response.send_message("❌ O outro jogador não tem moedas suficientes!", ephemeral=True)
        return
    
    embed = discord.Embed(title="🎯 **Adivinhe o Número**", color=0x00ff00)
    embed.add_field(name="👥 Jogadores", value=f"{interaction.user.mention} vs {pessoa.mention}", inline=False)
    embed.add_field(name="💰 Aposta", value=f"`{aposta}` moedas cada", inline=False)
    embed.add_field(name="🎯 Como Jogar", value="Escolham um número de 1 a 10. Quem chegar mais perto do número secreto ganha!", inline=False)
    
    view = NumberGuessView(interaction.user, pessoa, aposta)
    await interaction.response.send_message(embed=embed, view=view)

@tree.command(name="saldo", description="💰 Veja seu saldo de moedas", guild=discord.Object(id=GUILD_ID))
async def saldo(interaction: discord.Interaction):
    money = get_user_money(interaction.user.id)
    await interaction.response.send_message(f"💰 **Seu saldo:** `{money}` moedas")

@tree.command(name="daily", description="🎁 Receba moedas grátis todo dia", guild=discord.Object(id=GUILD_ID))
async def daily(interaction: discord.Interaction):
    daily_coins = 50
    update_user_money(interaction.user.id, daily_coins)
    new_balance = get_user_money(interaction.user.id)
    await interaction.response.send_message(f"🎁 **Daily coletado!** +{daily_coins} moedas\n💰 **Saldo atual:** `{new_balance}` moedas")

@bot.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    print(f'✅ Bot conectado como {bot.user}')
    print('🎮 Sistema de jogos x1 carregado!')
    print('🎯 Jogos disponíveis:')
    print('   ✅ Jogo da Velha (/velha)')
    print('   ✅ Dados (/dados)') 
    print('   ✅ Cara ou Coroa (/cara_coroa)')
    print('   ✅ Pedra/Papel/Tesoura (/ppt)')
    print('   ✅ Adivinhe o Número (/adivinhar)')

token = os.getenv('TOKEN')
if token:
    bot.run(token)
else:
    print("❌ Token não encontrado!")
