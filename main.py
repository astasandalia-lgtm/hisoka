import os
import discord
from discord import app_commands
from discord.ui import Button, View, Select
import asyncio
import json
import random
from datetime import datetime, timedelta
import math

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

GUILD_ID = 1420347024376725526

# Arquivos de dados
rank_file = 'rank.json'
economy_file = 'economy.json'
casino_file = 'casino.json'
roles_file = 'roles_shop.json'

# Configurações da economia
COINS_PER_MESSAGE = 10
COINS_PER_MESSAGE_CHANCE = 0.4
DAILY_COINS = 150
WORK_COINS_MIN = 50
WORK_COINS_MAX = 200
WORK_COOLDOWN = 3600  # 1 hora em segundos

# Configurações do Cassino
SLOT_SYMBOLS = ['🍒', '🍋', '🍊', '🍇', '🔔', '💎', '7️⃣']
SLOT_MULTIPLIERS = {
    '🍒': 2, '🍋': 3, '🍊': 4, '🍇': 5, '🔔': 10, '💎': 25, '7️⃣': 50
}

# Preços dos cargos (exemplo - você pode ajustar)
ROLE_PRICES = {
    "VIP Bronze": 1000,
    "VIP Prata": 2500,
    "VIP Ouro": 5000,
    "VIP Diamante": 10000
}

# Duração dos cargos temporários em dias
ROLE_DURATION = {
    "VIP Bronze": 7,
    "VIP Prata": 7,
    "VIP Prata": 7,
    "VIP Ouro": 7,
    "VIP Diamante": 7
}

def load_data(filename):
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_data(data, filename):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

def get_user_economy(user_id):
    economy_data = load_data(economy_file)
    user_id_str = str(user_id)
    
    if user_id_str not in economy_data:
        economy_data[user_id_str] = {
            'wallet': 100,  # Saldo inicial
            'bank': 0,
            'bank_limit': 1000,
            'last_daily': None,
            'last_work': None,
            'total_earned': 0,
            'total_bet': 0,
            'games_won': 0
        }
        save_data(economy_data, economy_file)
    
    return economy_data[user_id_str]

def update_user_economy(user_id, data):
    economy_data = load_data(economy_file)
    economy_data[str(user_id)] = data
    save_data(economy_data, economy_file)

def get_casino_stats():
    return load_data(casino_file)

def update_casino_stats(stats):
    save_data(stats, casino_file)

def get_role_shop():
    return load_data(roles_file)

def update_role_shop(shop_data):
    save_data(shop_data, roles_file)

# ========== SISTEMA DE BANCO ==========

class BankView(View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id
    
    @discord.ui.button(label="💰 Depositar", style=discord.ButtonStyle.primary, emoji="💰")
    async def deposit(self, interaction: discord.Interaction, button: Button):
        modal = DepositModal(self.user_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="💸 Sacar", style=discord.ButtonStyle.primary, emoji="💸")
    async def withdraw(self, interaction: discord.Interaction, button: Button):
        modal = WithdrawModal(self.user_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📊 Saldo", style=discord.ButtonStyle.success, emoji="📊")
    async def balance(self, interaction: discord.Interaction, button: Button):
        user_data = get_user_economy(self.user_id)
        embed = discord.Embed(title="🏦 **Saldo Bancário**", color=0x00ff00)
        embed.add_field(name="💵 Carteira", value=f"`{user_data['wallet']} moedas`", inline=True)
        embed.add_field(name="🏦 Banco", value=f"`{user_data['bank']}/{user_data['bank_limit']} moedas`", inline=True)
        embed.add_field(name="💰 Total", value=f"`{user_data['wallet'] + user_data['bank']} moedas`", inline=True)
        embed.set_footer(text="Use os botões para depositar ou sacar dinheiro")
        await interaction.response.edit_message(embed=embed, view=self)

class DepositModal(discord.ui.Modal, title='💰 Depositar Dinheiro'):
    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id
    
    amount = discord.ui.TextInput(
        label='Quantidade para depositar',
        placeholder='Digite a quantidade...',
        max_length=10
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.amount.value)
            if amount <= 0:
                await interaction.response.send_message("❌ Quantidade deve ser positiva!", ephemeral=True)
                return
            
            user_data = get_user_economy(self.user_id)
            
            if amount > user_data['wallet']:
                await interaction.response.send_message("❌ Saldo insuficiente na carteira!", ephemeral=True)
                return
            
            if user_data['bank'] + amount > user_data['bank_limit']:
                await interaction.response.send_message(f"❌ Limite bancário excedido! Máximo: {user_data['bank_limit']}", ephemeral=True)
                return
            
            user_data['wallet'] -= amount
            user_data['bank'] += amount
            update_user_economy(self.user_id, user_data)
            
            embed = discord.Embed(title="💰 **Depósito Realizado**", color=0x00ff00)
            embed.add_field(name="💵 Sacado da Carteira", value=f"`{amount} moedas`", inline=True)
            embed.add_field(name="🏦 Depositado no Banco", value=f"`{amount} moedas`", inline=True)
            embed.add_field(name="🏦 Saldo Bancário", value=f"`{user_data['bank']}/{user_data['bank_limit']} moedas`", inline=False)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message("❌ Por favor, digite um número válido!", ephemeral=True)

class WithdrawModal(discord.ui.Modal, title='💸 Sacar Dinheiro'):
    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id
    
    amount = discord.ui.TextInput(
        label='Quantidade para sacar',
        placeholder='Digite a quantidade...',
        max_length=10
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.amount.value)
            if amount <= 0:
                await interaction.response.send_message("❌ Quantidade deve ser positiva!", ephemeral=True)
                return
            
            user_data = get_user_economy(self.user_id)
            
            if amount > user_data['bank']:
                await interaction.response.send_message("❌ Saldo insuficiente no banco!", ephemeral=True)
                return
            
            user_data['bank'] -= amount
            user_data['wallet'] += amount
            update_user_economy(self.user_id, user_data)
            
            embed = discord.Embed(title="💸 **Saque Realizado**", color=0x00ff00)
            embed.add_field(name="🏦 Sacado do Banco", value=f"`{amount} moedas`", inline=True)
            embed.add_field(name="💵 Depositado na Carteira", value=f"`{amount} moedas`", inline=True)
            embed.add_field(name="💵 Saldo na Carteira", value=f"`{user_data['wallet']} moedas`", inline=False)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message("❌ Por favor, digite um número válido!", ephemeral=True)

# ========== SISTEMA DE CASSINO ==========

class CasinoView(View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id
    
    @discord.ui.button(label="🎰 Slots", style=discord.ButtonStyle.primary, emoji="🎰")
    async def slots(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(SlotBetModal(self.user_id))
    
    @discord.ui.button(label="🎲 Dados", style=discord.ButtonStyle.success, emoji="🎲")
    async def dice(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(DiceBetModal(self.user_id))
    
    @discord.ui.button(label="👊 Pedra/Papel/Tesoura", style=discord.ButtonStyle.danger, emoji="👊")
    async def rps(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(RPSBetModal(self.user_id))
    
    @discord.ui.button(label="📊 Estatísticas", style=discord.ButtonStyle.secondary, emoji="📊")
    async def stats(self, interaction: discord.Interaction, button: Button):
        user_data = get_user_economy(self.user_id)
        casino_stats = get_casino_stats()
        user_stats = casino_stats.get(str(self.user_id), {})
        
        embed = discord.Embed(title="🎰 **Estatísticas do Cassino**", color=0xffd700)
        embed.add_field(name="💰 Total Ganho", value=f"`{user_data['total_earned']} moedas`", inline=True)
        embed.add_field(name="🎯 Total Apostado", value=f"`{user_data['total_bet']} moedas`", inline=True)
        embed.add_field(name="🏆 Jogos Ganhos", value=f"`{user_data['games_won']} vezes`", inline=True)
        
        if user_stats:
            embed.add_field(name="🎰 Vitórias Slots", value=f"`{user_stats.get('slot_wins', 0)}`", inline=True)
            embed.add_field(name="🎲 Vitórias Dados", value=f"`{user_stats.get('dice_wins', 0)}`", inline=True)
            embed.add_field(name="👊 Vitórias PPT", value=f"`{user_stats.get('rps_wins', 0)}`", inline=True)
        
        await interaction.response.edit_message(embed=embed, view=self)

class SlotBetModal(discord.ui.Modal, title='🎰 Apostar nos Slots'):
    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id
    
    bet = discord.ui.TextInput(
        label='Quantidade para apostar',
        placeholder='Digite sua aposta...',
        max_length=10
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            bet_amount = int(self.bet.value)
            user_data = get_user_economy(self.user_id)
            
            if bet_amount <= 0:
                await interaction.response.send_message("❌ Aposta deve ser positiva!", ephemeral=True)
                return
            
            if bet_amount > user_data['wallet']:
                await interaction.response.send_message("❌ Saldo insuficiente!", ephemeral=True)
                return
            
            # Processar slots
            result = []
            for _ in range(3):
                result.append(random.choice(SLOT_SYMBOLS))
            
            # Calcular vitória
            win_amount = 0
            if result[0] == result[1] == result[2]:
                multiplier = SLOT_MULTIPLIERS[result[0]]
                win_amount = bet_amount * multiplier
            
            # Atualizar saldo
            user_data['wallet'] -= bet_amount
            user_data['total_bet'] += bet_amount
            
            if win_amount > 0:
                user_data['wallet'] += win_amount
                user_data['total_earned'] += win_amount
                user_data['games_won'] += 1
            
            update_user_economy(self.user_id, user_data)
            
            # Atualizar estatísticas
            casino_stats = get_casino_stats()
            user_stats = casino_stats.setdefault(str(self.user_id), {})
            user_stats['slot_plays'] = user_stats.get('slot_plays', 0) + 1
            if win_amount > 0:
                user_stats['slot_wins'] = user_stats.get('slot_wins', 0) + 1
            update_casino_stats(casino_stats)
            
            # Criar embed de resultado
            embed = discord.Embed(title="🎰 **Resultado dos Slots**", color=0xffd700 if win_amount > 0 else 0xff0000)
            embed.add_field(name="🎯 Resultado", value=f"**{result[0]} | {result[1]} | {result[2]}**", inline=False)
            embed.add_field(name="💰 Aposta", value=f"`{bet_amount} moedas`", inline=True)
            
            if win_amount > 0:
                embed.add_field(name="🎉 Ganhos", value=f"`{win_amount} moedas` (x{SLOT_MULTIPLIERS[result[0]]})", inline=True)
                embed.add_field(name="💵 Novo Saldo", value=f"`{user_data['wallet']} moedas`", inline=True)
            else:
                embed.add_field(name="😔 Perdeu", value="Tente novamente!", inline=True)
                embed.add_field(name="💵 Novo Saldo", value=f"`{user_data['wallet']} moedas`", inline=True)
            
            await interaction.response.send_message(embed=embed)
            
        except ValueError:
            await interaction.response.send_message("❌ Por favor, digite um número válido!", ephemeral=True)

class DiceBetModal(discord.ui.Modal, title='🎲 Apostar nos Dados'):
    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id
    
    bet = discord.ui.TextInput(
        label='Quantidade para apostar',
        placeholder='Digite sua aposta...',
        max_length=10
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            bet_amount = int(self.bet.value)
            user_data = get_user_economy(self.user_id)
            
            if bet_amount <= 0:
                await interaction.response.send_message("❌ Aposta deve ser positiva!", ephemeral=True)
                return
            
            if bet_amount > user_data['wallet']:
                await interaction.response.send_message("❌ Saldo insuficiente!", ephemeral=True)
                return
            
            # Jogar dados
            player_dice = random.randint(1, 6)
            bot_dice = random.randint(1, 6)
            
            # Determinar vencedor
            if player_dice > bot_dice:
                win_amount = bet_amount * 2
                result_text = "🎉 **Você ganhou!**"
                color = 0x00ff00
            elif player_dice < bot_dice:
                win_amount = 0
                result_text = "😔 **Você perdeu!**"
                color = 0xff0000
            else:
                win_amount = bet_amount
                result_text = "🤝 **Empate!**"
                color = 0xffff00
            
            # Atualizar saldo
            user_data['wallet'] -= bet_amount
            user_data['total_bet'] += bet_amount
            
            if win_amount > 0:
                user_data['wallet'] += win_amount
                user_data['total_earned'] += (win_amount - bet_amount)
                user_data['games_won'] += 1
            
            update_user_economy(self.user_id, user_data)
            
            # Atualizar estatísticas
            casino_stats = get_casino_stats()
            user_stats = casino_stats.setdefault(str(self.user_id), {})
            user_stats['dice_plays'] = user_stats.get('dice_plays', 0) + 1
            if player_dice > bot_dice:
                user_stats['dice_wins'] = user_stats.get('dice_wins', 0) + 1
            update_casino_stats(casino_stats)
            
            # Criar embed
            embed = discord.Embed(title="🎲 **Resultado dos Dados**", color=color)
            embed.add_field(name="🎯 Seu Dado", value=f"**{player_dice}**", inline=True)
            embed.add_field(name="🤖 Dado do Bot", value=f"**{bot_dice}**", inline=True)
            embed.add_field(name="💰 Aposta", value=f"`{bet_amount} moedas`", inline=False)
            embed.add_field(name="Resultado", value=result_text, inline=False)
            
            if win_amount > 0:
                embed.add_field(name="🎉 Ganhos", value=f"`{win_amount} moedas`", inline=True)
            embed.add_field(name="💵 Novo Saldo", value=f"`{user_data['wallet']} moedas`", inline=True)
            
            await interaction.response.send_message(embed=embed)
            
        except ValueError:
            await interaction.response.send_message("❌ Por favor, digite um número válido!", ephemeral=True)

class RPSBetModal(discord.ui.Modal, title='👊 Pedra/Papel/Tesoura'):
    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id
    
    bet = discord.ui.TextInput(
        label='Quantidade para apostar',
        placeholder='Digite sua aposta...',
        max_length=10
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            bet_amount = int(self.bet.value)
            user_data = get_user_economy(self.user_id)
            
            if bet_amount <= 0:
                await interaction.response.send_message("❌ Aposta deve ser positiva!", ephemeral=True)
                return
            
            if bet_amount > user_data['wallet']:
                await interaction.response.send_message("❌ Saldo insuficiente!", ephemeral=True)
                return
            
            # Criar view para escolha
            view = RPSChoiceView(self.user_id, bet_amount)
            embed = discord.Embed(title="👊 **Pedra, Papel ou Tesoura**", color=0x00ff00)
            embed.add_field(name="💰 Aposta", value=f"`{bet_amount} moedas`", inline=True)
            embed.add_field(name="🎯 Escolha", value="Selecione sua jogada abaixo:", inline=True)
            
            await interaction.response.send_message(embed=embed, view=view)
            
        except ValueError:
            await interaction.response.send_message("❌ Por favor, digite um número válido!", ephemeral=True)

class RPSChoiceView(View):
    def __init__(self, user_id, bet_amount):
        super().__init__(timeout=30)
        self.user_id = user_id
        self.bet_amount = bet_amount
    
    @discord.ui.button(label="🪨 Pedra", style=discord.ButtonStyle.primary)
    async def rock(self, interaction: discord.Interaction, button: Button):
        await self.process_rps(interaction, "pedra")
    
    @discord.ui.button(label="📄 Papel", style=discord.ButtonStyle.success)
    async def paper(self, interaction: discord.Interaction, button: Button):
        await self.process_rps(interaction, "papel")
    
    @discord.ui.button(label="✂️ Tesoura", style=discord.ButtonStyle.danger)
    async def scissors(self, interaction: discord.Interaction, button: Button):
        await self.process_rps(interaction, "tesoura")
    
    async def process_rps(self, interaction: discord.Interaction, player_choice):
        user_data = get_user_economy(self.user_id)
        choices = ["pedra", "papel", "tesoura"]
        bot_choice = random.choice(choices)
        
        # Determinar vencedor
        if player_choice == bot_choice:
            result = "empate"
            win_amount = self.bet_amount  # Devolve a aposta
            result_text = "🤝 **Empate!**"
            color = 0xffff00
        elif ((player_choice == "pedra" and bot_choice == "tesoura") or
              (player_choice == "papel" and bot_choice == "pedra") or
              (player_choice == "tesoura" and bot_choice == "papel")):
            result = "win"
            win_amount = self.bet_amount * 2
            result_text = "🎉 **Você ganhou!**"
            color = 0x00ff00
        else:
            result = "lose"
            win_amount = 0
            result_text = "😔 **Você perdeu!**"
            color = 0xff0000
        
        # Atualizar saldo
        user_data['wallet'] -= self.bet_amount
        user_data['total_bet'] += self.bet_amount
        
        if win_amount > 0:
            user_data['wallet'] += win_amount
            if result == "win":
                user_data['total_earned'] += (win_amount - self.bet_amount)
                user_data['games_won'] += 1
        
        update_user_economy(self.user_id, user_data)
        
        # Atualizar estatísticas
        casino_stats = get_casino_stats()
        user_stats = casino_stats.setdefault(str(self.user_id), {})
        user_stats['rps_plays'] = user_stats.get('rps_plays', 0) + 1
        if result == "win":
            user_stats['rps_wins'] = user_stats.get('rps_wins', 0) + 1
        update_casino_stats(casino_stats)
        
        # Criar embed de resultado
        embed = discord.Embed(title="👊 **Resultado - Pedra/Papel/Tesoura**", color=color)
        embed.add_field(name="🎯 Sua Escolha", value=f"**{self.get_emoji(player_choice)} {player_choice.title()}**", inline=True)
        embed.add_field(name="🤖 Escolha do Bot", value=f"**{self.get_emoji(bot_choice)} {bot_choice.title()}**", inline=True)
        embed.add_field(name="💰 Aposta", value=f"`{self.bet_amount} moedas`", inline=False)
        embed.add_field(name="Resultado", value=result_text, inline=False)
        
        if win_amount > 0:
            if result == "win":
                embed.add_field(name="🎉 Ganhos", value=f"`{win_amount} moedas` (x2)", inline=True)
            else:
                embed.add_field(name="💵 Devolvido", value=f"`{win_amount} moedas`", inline=True)
        embed.add_field(name="💵 Novo Saldo", value=f"`{user_data['wallet']} moedas`", inline=True)
        
        await interaction.response.edit_message(embed=embed, view=None)
    
    def get_emoji(self, choice):
        emojis = {"pedra": "🪨", "papel": "📄", "tesoura": "✂️"}
        return emojis.get(choice, "")

# ========== COMANDOS DO BOT ==========

@tree.command(name="banco", description="🏦 Acesse seu banco para depositar ou sacar dinheiro", guild=discord.Object(id=GUILD_ID))
async def banco(interaction: discord.Interaction):
    user_data = get_user_economy(interaction.user.id)
    
    embed = discord.Embed(title="🏦 **Sistema Bancário**", color=0x0099ff)
    embed.add_field(name="💵 Carteira", value=f"`{user_data['wallet']} moedas`", inline=True)
    embed.add_field(name="🏦 Banco", value=f"`{user_data['bank']}/{user_data['bank_limit']} moedas`", inline=True)
    embed.add_field(name="💰 Total", value=f"`{user_data['wallet'] + user_data['bank']} moedas`", inline=True)
    embed.set_footer(text="Use os botões abaixo para gerenciar seu dinheiro")
    
    view = BankView(interaction.user.id)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

@tree.command(name="cassino", description="🎰 Acesse o cassino para jogar e ganhar dinheiro", guild=discord.Object(id=GUILD_ID))
async def cassino(interaction: discord.Interaction):
    user_data = get_user_economy(interaction.user.id)
    
    embed = discord.Embed(title="🎰 **Cassino do Servidor**", color=0xffd700)
    embed.add_field(name="💵 Seu Saldo", value=f"`{user_data['wallet']} moedas`", inline=True)
    embed.add_field(name="🏆 Vitórias", value=f"`{user_data['games_won']} jogos`", inline=True)
    embed.add_field(name="🎯 Total Apostado", value=f"`{user_data['total_bet']} moedas`", inline=True)
    embed.description = "**Jogos Disponíveis:**\n🎰 Slots - Multiplicadores até 50x\n🎲 Dados - Ganhe 2x sua aposta\n👊 PPT - Ganhe 2x sua aposta"
    
    view = CasinoView(interaction.user.id)
    await interaction.response.send_message(embed=embed, view=view)

@tree.command(name="daily", description="💰 Receba sua recompensa diária de moedas", guild=discord.Object(id=GUILD_ID))
async def daily(interaction: discord.Interaction):
    user_data = get_user_economy(interaction.user.id)
    now = datetime.now()
    
    if user_data['last_daily']:
        last_daily = datetime.fromisoformat(user_data['last_daily'])
        if (now - last_daily) < timedelta(hours=24):
            next_daily = last_daily + timedelta(hours=24)
            wait_time = next_daily - now
            hours = int(wait_time.seconds // 3600)
            minutes = int((wait_time.seconds % 3600) // 60)
            
            embed = discord.Embed(title="⏰ **Daily Já Coletado**", color=0xff0000)
            embed.description = f"Você já coletou seu daily hoje!\nPróximo daily em **{hours}h {minutes}m**"
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
    
    # Dar recompensa diária
    user_data['wallet'] += DAILY_COINS
    user_data['total_earned'] += DAILY_COINS
    user_data['last_daily'] = now.isoformat()
    update_user_economy(interaction.user.id, user_data)
    
    embed = discord.Embed(title="💰 **Daily Coletado!**", color=0x00ff00)
    embed.add_field(name="🎁 Recompensa", value=f"`{DAILY_COINS} moedas`", inline=True)
    embed.add_field(name="💵 Novo Saldo", value=f"`{user_data['wallet']} moedas`", inline=True)
    embed.set_footer(text="Volte em 24 horas para mais!")
    
    await interaction.response.send_message(embed=embed)

@tree.command(name="trabalhar", description="💼 Trabalhe para ganhar moedas", guild=discord.Object(id=GUILD_ID))
async def trabalhar(interaction: discord.Interaction):
    user_data = get_user_economy(interaction.user.id)
    now = datetime.now()
    
    if user_data['last_work']:
        last_work = datetime.fromisoformat(user_data['last_work'])
        if (now - last_work).seconds < WORK_COOLDOWN:
            wait_time = WORK_COOLDOWN - (now - last_work).seconds
            minutes = wait_time // 60
            seconds = wait_time % 60
            
            embed = discord.Embed(title="⏰ **Aguarde para Trabalhar**", color=0xff0000)
            embed.description = f"Você pode trabalhar novamente em **{minutes}m {seconds}s**"
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
    
    # Trabalhos aleatórios
    jobs = [
        "programador", "designer", "cozinheiro", "mecânico", "professor",
        "músico", "artista", "escritor", "cientista", "médico"
    ]
    job = random.choice(jobs)
    earnings = random.randint(WORK_COINS_MIN, WORK_COINS_MAX)
    
    # Atualizar saldo
    user_data['wallet'] += earnings
    user_data['total_earned'] += earnings
    user_data['last_work'] = now.isoformat()
    update_user_economy(interaction.user.id, user_data)
    
    embed = discord.Embed(title="💼 **Trabalho Concluído!**", color=0x00ff00)
    embed.add_field(name="👨‍💼 Trabalho", value=f"`{job.title()}`", inline=True)
    embed.add_field(name="💰 Ganhos", value=f"`{earnings} moedas`", inline=True)
    embed.add_field(name="💵 Novo Saldo", value=f"`{user_data['wallet']} moedas`", inline=True)
    embed.set_footer(text="Volte em 1 hora para trabalhar novamente")
    
    await interaction.response.send_message(embed=embed)

@tree.command(name="saldo", description="💰 Veja seu saldo de moedas", guild=discord.Object(id=GUILD_ID))
async def saldo(interaction: discord.Interaction):
    user_data = get_user_economy(interaction.user.id)
    
    embed = discord.Embed(title="💰 **Seu Saldo**", color=0x00ff00)
    embed.add_field(name="💵 Carteira", value=f"`{user_data['wallet']} moedas`", inline=True)
    embed.add_field(name="🏦 Banco", value=f"`{user_data['bank']} moedas`", inline=True)
    embed.add_field(name="💰 Total", value=f"`{user_data['wallet'] + user_data['bank']} moedas`", inline=True)
    embed.add_field(name="🏆 Vitórias no Cassino", value=f"`{user_data['games_won']} jogos`", inline=True)
    embed.add_field(name="🎯 Total Apostado", value=f"`{user_data['total_bet']} moedas`", inline=True)
    embed.add_field(name="💎 Total Ganho", value=f"`{user_data['total_earned']} moedas`", inline=True)
    
    await interaction.response.send_message(embed=embed)

@tree.command(name="transferir", description="💸 Transfira moedas para outro usuário", guild=discord.Object(id=GUILD_ID))
async def transferir(interaction: discord.Interaction, usuario: discord.Member, quantidade: int):
    if usuario.bot:
        await interaction.response.send_message("❌ Não pode transferir para bots!", ephemeral=True)
        return
    
    if usuario.id == interaction.user.id:
        await interaction.response.send_message("❌ Não pode transferir para si mesmo!", ephemeral=True)
        return
    
    if quantidade <= 0:
        await interaction.response.send_message("❌ Quantidade deve ser positiva!", ephemeral=True)
        return
    
    sender_data = get_user_economy(interaction.user.id)
    receiver_data = get_user_economy(usuario.id)
    
    if quantidade > sender_data['wallet']:
        await interaction.response.send_message("❌ Saldo insuficiente!", ephemeral=True)
        return
    
    # Realizar transferência
    sender_data['wallet'] -= quantidade
    receiver_data['wallet'] += quantidade
    
    update_user_economy(interaction.user.id, sender_data)
    update_user_economy(usuario.id, receiver_data)
    
    embed = discord.Embed(title="💸 **Transferência Realizada**", color=0x00ff00)
    embed.add_field(name="👤 De", value=f"`{interaction.user.display_name}`", inline=True)
    embed.add_field(name="👤 Para", value=f"`{usuario.display_name}`", inline=True)
    embed.add_field(name="💰 Quantidade", value=f"`{quantidade} moedas`", inline=True)
    embed.add_field(name="💵 Seu Novo Saldo", value=f"`{sender_data['wallet']} moedas`", inline=True)
    
    await interaction.response.send_message(embed=embed)

# ========== EVENTO DE MENSAGENS ==========

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    # Ganhar moedas por mensagem (com chance)
    if random.random() < COINS_PER_MESSAGE_CHANCE:
        user_data = get_user_economy(message.author.id)
        user_data['wallet'] += COINS_PER_MESSAGE
        user_data['total_earned'] += COINS_PER_MESSAGE
        update_user_economy(message.author.id, user_data)
    
    await bot.process_commands(message)

@bot.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    print(f'✅ Bot conectado como {bot.user}')
    print('🎰 Sistema de Cassino e Banco carregado!')
    print('💾 Sistemas carregados:')
    print('   ✅ Sistema Bancário')
    print('   ✅ Cassino com 3 jogos')
    print('   ✅ Economia com daily/trabalho')
    print('   ✅ Transferências entre usuários')

# Inicializar arquivos se não existirem
def initialize_files():
    if not os.path.exists(economy_file):
        save_data({}, economy_file)
    if not os.path.exists(casino_file):
        save_data({}, casino_file)
    if not os.path.exists(roles_file):
        save_data({}, roles_file)

initialize_files()

token = os.getenv('TOKEN')
if token:
    bot.run(token)
else:
    print("❌ Token não encontrado!")
