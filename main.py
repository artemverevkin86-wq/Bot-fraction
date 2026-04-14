import discord
from discord import app_commands
from discord.ext import commands
import json
import os

# Настройки бота
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# ID роли разработчика (замените на ваш ID роли)
DEVELOPER_ROLE_ID = 1482416918957785290  # ⚠️ ЗАМЕНИТЕ НА РЕАЛЬНЫЙ ID РОЛИ

# Файл для хранения данных
DATA_FILE = 'factions_data.json'

# Загрузка данных
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "users": {},  # {user_id: {"faction": "Арбузы", "reputation": 0, "rank": "Новичок"}}
        "factions": ["Арбузы"],  # Список всех фракций
        "faction_ranks": {  # Ступени иерархии для каждой фракции
            "Арбузы": ["Новичок", "Садовод", "Арбузный барон", "Король арбузов"]
        }
    }

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# Инициализация данных
data = load_data()

# Проверка на разработчика
def is_developer(interaction: discord.Interaction) -> bool:
    if interaction.user.guild_permissions.administrator:
        return True
    role = discord.utils.get(interaction.user.roles, id=DEVELOPER_ROLE_ID)
    return role is not None

# Получение данных пользователя
def get_user_data(user_id: str):
    if user_id not in data["users"]:
        data["users"][user_id] = {
            "faction": "Арбузы",
            "reputation": 0,
            "rank": "Новичок"
        }
        save_data(data)
    return data["users"][user_id]

# Обновление ранга на основе репутации
def update_rank(user_id: str):
    user_data = get_user_data(user_id)
    faction = user_data["faction"]
    rep = user_data["reputation"]
    ranks = data["faction_ranks"].get(faction, ["Новичок"])
    
    # Определяем ранг по репутации
    if rep >= 100:
        user_data["rank"] = ranks[3] if len(ranks) > 3 else ranks[-1]
    elif rep >= 50:
        user_data["rank"] = ranks[2] if len(ranks) > 2 else ranks[-1]
    elif rep >= 10:
        user_data["rank"] = ranks[1] if len(ranks) > 1 else ranks[-1]
    else:
        user_data["rank"] = ranks[0]
    
    save_data(data)

# Главное меню (View с кнопками)
class MainMenu(discord.ui.View):
    def __init__(self, user_id: str):
        super().__init__(timeout=None)
        self.user_id = user_id
    
    @discord.ui.button(label="Об игроке", style=discord.ButtonStyle.primary)
    async def about_player(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Эта кнопка не для вас!", ephemeral=True)
            return
        await interaction.response.send_message("🚧 **В разработке**\nФункция 'Об игроке' появится скоро!", ephemeral=True)
    
    @discord.ui.button(label="Магазин фракций", style=discord.ButtonStyle.success)
    async def faction_shop(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Эта кнопка не для вас!", ephemeral=True)
            return
        await interaction.response.send_message("🚧 **В разработке**\nМагазин фракций скоро откроется!", ephemeral=True)
    
    @discord.ui.button(label="Выйти из фракции", style=discord.ButtonStyle.danger)
    async def leave_faction(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Эта кнопка не для вас!", ephemeral=True)
            return
        
        # Сброс фракции на "Арбузы"
        data["users"][self.user_id]["faction"] = "Арбузы"
        data["users"][self.user_id]["reputation"] = 0
        update_rank(self.user_id)
        save_data(data)
        
        await interaction.response.send_message("🍉 Вы вышли из фракции и присоединились к 'Арбузы'!", ephemeral=True)

# Команда /меню
@bot.tree.command(name="меню", description="Показать главное меню фракций")
async def menu(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    user_data = get_user_data(user_id)
    
    embed = discord.Embed(
        title="**ВАШИ ФРАКЦИИ**",
        color=discord.Color.green()
    )
    embed.description = f"```\nВаша фракция: {user_data['faction']}\nВаша репутация: {user_data['reputation']}\nСтупень в иерархии: {user_data['rank']}\n```"
    
    view = MainMenu(user_id)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# АДМИН ПАНЕЛЬ
class AdminPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Добавить фракцию", style=discord.ButtonStyle.primary, row=0)
    async def add_faction(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_developer(interaction):
            await interaction.response.send_message("❌ У вас нет прав разработчика!", ephemeral=True)
            return
        
        modal = AddFactionModal()
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Изменить репутацию", style=discord.ButtonStyle.success, row=0)
    async def change_reputation(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_developer(interaction):
            await interaction.response.send_message("❌ У вас нет прав разработчика!", ephemeral=True)
            return
        
        modal = ChangeReputationModal()
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Сменить фракцию игроку", style=discord.ButtonStyle.secondary, row=0)
    async def change_faction(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_developer(interaction):
            await interaction.response.send_message("❌ У вас нет прав разработчика!", ephemeral=True)
            return
        
        modal = ChangeFactionModal()
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Список фракций", style=discord.ButtonStyle.secondary, row=1)
    async def list_factions(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_developer(interaction):
            await interaction.response.send_message("❌ У вас нет прав разработчика!", ephemeral=True)
            return
        
        factions_list = "\n".join([f"🍉 {f}" for f in data["factions"]])
        await interaction.response.send_message(f"**Существующие фракции:**\n{factions_list}", ephemeral=True)
    
    @discord.ui.button(label="Статистика игроков", style=discord.ButtonStyle.secondary, row=1)
    async def player_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_developer(interaction):
            await interaction.response.send_message("❌ У вас нет прав разработчика!", ephemeral=True)
            return
        
        stats = "**Статистика игроков:**\n"
        for uid, udata in data["users"].items():
            user = await bot.fetch_user(int(uid))
            name = user.name if user else uid
            stats += f"• {name}: {udata['faction']} | Реп: {udata['reputation']} | Ранг: {udata['rank']}\n"
        
        if len(stats) > 2000:
            stats = stats[:1990] + "..."
        
        await interaction.response.send_message(stats, ephemeral=True)

# Модальные окна для админ-панели
class AddFactionModal(discord.ui.Modal, title="Добавить фракцию"):
    faction_name = discord.ui.TextInput(label="Название фракции", placeholder="Например: Арбузы", required=True)
    ranks = discord.ui.TextInput(label="Ступени иерархии (через запятую)", placeholder="Новичок,Садовод,Барон,Король", required=True)
    
    async def on_submit(self, interaction: discord.Interaction):
        if not is_developer(interaction):
            await interaction.response.send_message("❌ Нет прав!", ephemeral=True)
            return
        
        name = self.faction_name.value.strip()
        if name in data["factions"]:
            await interaction.response.send_message("❌ Такая фракция уже существует!", ephemeral=True)
            return
        
        data["factions"].append(name)
        ranks_list = [r.strip() for r in self.ranks.value.split(",")]
        data["faction_ranks"][name] = ranks_list
        save_data(data)
        
        await interaction.response.send_message(f"✅ Фракция **{name}** добавлена с рангами: {', '.join(ranks_list)}", ephemeral=True)

class ChangeReputationModal(discord.ui.Modal, title="Изменить репутацию"):
    user_id = discord.ui.TextInput(label="ID пользователя", placeholder="123456789012345678", required=True)
    amount = discord.ui.TextInput(label="Количество (+/-)", placeholder="+10 или -5", required=True)
    
    async def on_submit(self, interaction: discord.Interaction):
        if not is_developer(interaction):
            await interaction.response.send_message("❌ Нет прав!", ephemeral=True)
            return
        
        try:
            uid = self.user_id.value
            amount = int(self.amount.value)
            
            if uid not in data["users"]:
                get_user_data(uid)
            
            data["users"][uid]["reputation"] += amount
            if data["users"][uid]["reputation"] < 0:
                data["users"][uid]["reputation"] = 0
            
            update_rank(uid)
            save_data(data)
            
            await interaction.response.send_message(f"✅ Репутация игрока <@{uid}> изменена на {amount} (теперь: {data['users'][uid]['reputation']})", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Неверное количество! Используйте число.", ephemeral=True)

class ChangeFactionModal(discord.ui.Modal, title="Сменить фракцию"):
    user_id = discord.ui.TextInput(label="ID пользователя", placeholder="123456789012345678", required=True)
    faction = discord.ui.TextInput(label="Название фракции", placeholder="Арбузы", required=True)
    
    async def on_submit(self, interaction: discord.Interaction):
        if not is_developer(interaction):
            await interaction.response.send_message("❌ Нет прав!", ephemeral=True)
            return
        
        uid = self.user_id.value
        new_faction = self.faction.value.strip()
        
        if new_faction not in data["factions"]:
            await interaction.response.send_message(f"❌ Фракция '{new_faction}' не существует!", ephemeral=True)
            return
        
        if uid not in data["users"]:
            get_user_data(uid)
        
        data["users"][uid]["faction"] = new_faction
        data["users"][uid]["reputation"] = 0
        update_rank(uid)
        save_data(data)
        
        await interaction.response.send_message(f"✅ Игрок <@{uid}> переведен во фракцию {new_faction}", ephemeral=True)

# Команда /админ
@bot.tree.command(name="админ", description="Админ-панель управления фракциями")
async def admin_panel(interaction: discord.Interaction):
    if not is_developer(interaction):
        await interaction.response.send_message("❌ У вас нет доступа к админ-панели!", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="🛠️ **Админ-панель фракций**",
        description="Управляйте фракциями и игроками",
        color=discord.Color.purple()
    )
    view = AdminPanel()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# Команда для теста
@bot.tree.command(name="тест", description="Проверка работы бота")
async def test(interaction: discord.Interaction):
    await interaction.response.send_message("✅ Бот работает!", ephemeral=True)

# Событие при запуске
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Бот {bot.user} запущен!")
    print(f"📁 Загружено фракций: {len(data['factions'])}")
    print(f"👥 Загружено игроков: {len(data['users'])}")

# Запуск бота
TOKEN = "ВАШ_ТОКЕН_БОТА"  # ⚠️ ЗАМЕНИТЕ НА РЕАЛЬНЫЙ ТОКЕН
bot.run(TOKEN)
