import discord
from discord import app_commands
from discord.ui import Button, View, Select
import json
import os
import asyncio
from typing import Optional, List

# ==================== КОНФИГУРАЦИЯ ====================
TOKEN = os.getenv('TOKEN')  # ИСПРАВЛЕНО: теперь TOKEN, а не DISCORD_TOKEN
ADMIN_ROLE_NAME = "Разработчик"

# ==================== ПРОВЕРКА ТОКЕНА ====================
if not TOKEN:
    print("❌ ОШИБКА: TOKEN не найден в переменных окружения!")
    print("Добавьте переменную TOKEN на Railway и перезапустите проект")
    exit(1)

# ==================== НАСТРОЙКА INTENTS ====================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# ==================== БАЗА ДАННЫХ (JSON) ====================
class Database:
    def __init__(self, filename: str = "data.json"):
        self.filename = filename
        self.data = self.load()

    def load(self):
        if os.path.exists(self.filename):
            with open(self.filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "users": {},
            "factions": ["Арбузы"],
            "hierarchy_levels": {
                "Арбузы": ["Семечко", "Корочка", "Мякоть", "Арбузный лорд"]
            }
        }

    def save(self):
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def get_user(self, user_id: str) -> dict:
        user_id = str(user_id)
        if user_id not in self.data["users"]:
            self.data["users"][user_id] = {
                "faction": None,
                "reputation": 0,
                "hierarchy_level": "Нет"
            }
            self.save()
        return self.data["users"][user_id]

    def update_user(self, user_id: str, **kwargs):
        user_id = str(user_id)
        if user_id not in self.data["users"]:
            self.get_user(user_id)
        self.data["users"][user_id].update(kwargs)
        self.save()

db = Database()

# ==================== ПРОВЕРКА АДМИНА ====================
def is_admin(interaction: discord.Interaction) -> bool:
    if not interaction.guild:
        return False
    member = interaction.guild.get_member(interaction.user.id)
    if not member:
        return False
    return any(role.name == ADMIN_ROLE_NAME for role in member.roles)

# ==================== ГЛАВНОЕ МЕНЮ ====================
class MainMenuView(View):
    def __init__(self, user_id: int):
        super().__init__(timeout=60)
        self.user_id = user_id

    @discord.ui.button(label="Об игроке", style=discord.ButtonStyle.primary)
    async def about_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это меню не для вас!", ephemeral=True)
            return
        await interaction.response.send_message("🚧 В разработке", ephemeral=True)

    @discord.ui.button(label="Магазин фракций", style=discord.ButtonStyle.success)
    async def shop_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это меню не для вас!", ephemeral=True)
            return
        await interaction.response.send_message("🚧 В разработке", ephemeral=True)

    @discord.ui.button(label="Выйти из фракции", style=discord.ButtonStyle.danger)
    async def leave_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это меню не для вас!", ephemeral=True)
            return
        
        user_data = db.get_user(self.user_id)
        if not user_data.get("faction"):
            await interaction.response.send_message("❌ Вы не состоите ни в какой фракции!", ephemeral=True)
            return
        
        db.update_user(self.user_id, faction=None, reputation=0, hierarchy_level="Нет")
        await interaction.response.send_message("✅ Вы вышли из фракции!", ephemeral=True)
        print(f"📤 Игрок {interaction.user.name} вышел из фракции")

# ==================== АДМИН ПАНЕЛЬ ====================
class AdminPanelView(View):
    def __init__(self):
        super().__init__(timeout=120)
    
    @discord.ui.button(label="➕ Добавить фракцию", style=discord.ButtonStyle.success, row=0)
    async def add_faction(self, interaction: discord.Interaction, button: Button):
        modal = AddFactionModal()
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🗑️ Удалить фракцию", style=discord.ButtonStyle.danger, row=0)
    async def remove_faction(self, interaction: discord.Interaction, button: Button):
        if not db.data["factions"]:
            await interaction.response.send_message("❌ Нет фракций для удаления", ephemeral=True)
            return
        
        view = FactionSelectView("delete")
        await interaction.response.send_message("Выберите фракцию для удаления:", view=view, ephemeral=True)
    
    @discord.ui.button(label="⭐ Изменить репутацию", style=discord.ButtonStyle.primary, row=1)
    async def edit_reputation(self, interaction: discord.Interaction, button: Button):
        modal = ReputationModal()
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📊 Сменить ступень", style=discord.ButtonStyle.primary, row=1)
    async def change_rank(self, interaction: discord.Interaction, button: Button):
        modal = RankModal()
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🔄 Перевести игрока", style=discord.ButtonStyle.primary, row=2)
    async def transfer_player(self, interaction: discord.Interaction, button: Button):
        modal = TransferModal()
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📋 Список игроков", style=discord.ButtonStyle.secondary, row=2)
    async def list_players(self, interaction: discord.Interaction, button: Button):
        await show_players_list(interaction)
    
    @discord.ui.button(label="🏛️ Список фракций", style=discord.ButtonStyle.secondary, row=3)
    async def list_factions(self, interaction: discord.Interaction, button: Button):
        factions = "\n".join([f"• {f}" for f in db.data["factions"]])
        embed = discord.Embed(title="🏛️ Список фракций", description=factions, color=discord.Color.blue())
        await interaction.response.send_message(embed=embed, ephemeral=True)

class FactionSelectView(View):
    def __init__(self, action: str, user_id: str = None):
        super().__init__(timeout=60)
        self.action = action
        self.user_id = user_id
        
        select = Select(
            placeholder="Выберите фракцию",
            options=[discord.SelectOption(label=f, value=f) for f in db.data["factions"][:25]]
        )
        select.callback = self.callback
        self.add_item(select)
    
    async def callback(self, interaction: discord.Interaction):
        faction = interaction.data["values"][0]
        
        if self.action == "delete":
            users_in_faction = [uid for uid, data in db.data["users"].items() if data.get("faction") == faction]
            if users_in_faction:
                await interaction.response.send_message(f"❌ Нельзя удалить фракцию **{faction}**, в ней есть {len(users_in_faction)} игроков!", ephemeral=True)
                return
            
            db.data["factions"].remove(faction)
            if faction in db.data["hierarchy_levels"]:
                del db.data["hierarchy_levels"][faction]
            db.save()
            await interaction.response.send_message(f"✅ Фракция **{faction}** удалена!", ephemeral=True)
            print(f"🗑️ Админ {interaction.user.name} удалил фракцию {faction}")
        
        elif self.action == "transfer" and self.user_id:
            hierarchy = db.data["hierarchy_levels"].get(faction, ["Новичок"])
            db.update_user(self.user_id, faction=faction, reputation=0, hierarchy_level=hierarchy[0])
            await interaction.response.send_message(f"✅ Игрок переведён во фракцию **{faction}**!", ephemeral=True)
            print(f"🔄 Админ {interaction.user.name} перевёл игрока во фракцию {faction}")

class AddFactionModal(discord.ui.Modal, title="Добавить фракцию"):
    name = discord.ui.TextInput(label="Название", placeholder="Введите название фракции", max_length=50)
    hierarchy = discord.ui.TextInput(label="Иерархия", placeholder="Ступени через запятую: Новичок,Боец,Лидер", required=True)
    description = discord.ui.TextInput(label="Описание", placeholder="Описание фракции", required=False, style=discord.TextStyle.paragraph)
    
    async def on_submit(self, interaction: discord.Interaction):
        if self.name.value in db.data["factions"]:
            await interaction.response.send_message("❌ Фракция с таким названием уже существует!", ephemeral=True)
            return
        
        hierarchy_list = [h.strip() for h in self.hierarchy.value.split(",") if h.strip()]
        if not hierarchy_list:
            hierarchy_list = ["Новичок"]
        
        db.data["factions"].append(self.name.value)
        db.data["hierarchy_levels"][self.name.value] = hierarchy_list
        db.save()
        
        await interaction.response.send_message(f"✅ Фракция **{self.name.value}** создана!", ephemeral=True)
        print(f"➕ Админ {interaction.user.name} создал фракцию {self.name.value}")

class ReputationModal(discord.ui.Modal, title="Изменить репутацию"):
    user_id = discord.ui.TextInput(label="ID пользователя", placeholder="Введите Discord ID", required=True)
    amount = discord.ui.TextInput(label="Количество", placeholder="Положительное или отрицательное число", required=True)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.amount.value)
            user_data = db.get_user(self.user_id.value)
            
            if not user_data.get("faction"):
                await interaction.response.send_message("❌ Игрок не состоит во фракции!", ephemeral=True)
                return
            
            new_rep = user_data.get("reputation", 0) + amount
            db.update_user(self.user_id.value, reputation=new_rep)
            
            await interaction.response.send_message(f"✅ Репутация игрока изменена на {new_rep}", ephemeral=True)
            print(f"⭐ Админ {interaction.user.name} изменил репутацию игрока {self.user_id.value} на {amount}")
        except ValueError:
            await interaction.response.send_message("❌ Количество должно быть числом!", ephemeral=True)

class RankModal(discord.ui.Modal, title="Сменить ступень"):
    user_id = discord.ui.TextInput(label="ID пользователя", placeholder="Введите Discord ID", required=True)
    new_rank = discord.ui.TextInput(label="Новая ступень", placeholder="Название ступени", required=True)
    
    async def on_submit(self, interaction: discord.Interaction):
        user_data = db.get_user(self.user_id.value)
        faction = user_data.get("faction")
        
        if not faction:
            await interaction.response.send_message("❌ Игрок не состоит во фракции!", ephemeral=True)
            return
        
        hierarchy = db.data["hierarchy_levels"].get(faction, [])
        if self.new_rank.value not in hierarchy:
            await interaction.response.send_message(f"❌ Ступень '{self.new_rank.value}' не найдена в иерархии фракции {faction}!", ephemeral=True)
            return
        
        db.update_user(self.user_id.value, hierarchy_level=self.new_rank.value)
        await interaction.response.send_message(f"✅ Ступень игрока изменена на **{self.new_rank.value}**", ephemeral=True)
        print(f"📊 Админ {interaction.user.name} изменил ступень игрока {self.user_id.value}")

class TransferModal(discord.ui.Modal, title="Перевести игрока"):
    user_id = discord.ui.TextInput(label="ID пользователя", placeholder="Введите Discord ID", required=True)
    
    async def on_submit(self, interaction: discord.Interaction):
        if not db.data["factions"]:
            await interaction.response.send_message("❌ Нет доступных фракций!", ephemeral=True)
            return
        
        view = FactionSelectView("transfer", self.user_id.value)
        await interaction.response.send_message("Выберите новую фракцию:", view=view, ephemeral=True)

async def show_players_list(interaction: discord.Interaction):
    if not db.data["users"]:
        await interaction.response.send_message("📭 Нет зарегистрированных игроков", ephemeral=True)
        return
    
    players_list = []
    for uid, data in db.data["users"].items():
        faction = data.get("faction") or "Нет"
        rep = data.get("reputation", 0)
        rank = data.get("hierarchy_level", "Нет")
        players_list.append(f"<@{uid}> | {faction} | Реп: {rep} | {rank}")
    
    pages = [players_list[i:i+10] for i in range(0, len(players_list), 10)]
    view = PaginationView(pages)
    
    embed = discord.Embed(title="📋 Список игроков", description="\n".join(pages[0]), color=discord.Color.blue())
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class PaginationView(View):
    def __init__(self, pages: List[List[str]]):
        super().__init__(timeout=60)
        self.pages = pages
        self.current = 0
    
    @discord.ui.button(label="◀️", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, button: Button):
        if self.current > 0:
            self.current -= 1
            embed = discord.Embed(title="📋 Список игроков", description="\n".join(self.pages[self.current]), color=discord.Color.blue())
            await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="▶️", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: Button):
        if self.current < len(self.pages) - 1:
            self.current += 1
            embed = discord.Embed(title="📋 Список игроков", description="\n".join(self.pages[self.current]), color=discord.Color.blue())
            await interaction.response.edit_message(embed=embed, view=self)

# ==================== КЛИЕНТ БОТА ====================
class FactionBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        print("✅ Слэш-команды синхронизированы")

bot = FactionBot()

# ==================== СОБЫТИЯ ====================
@bot.event
async def on_ready():
    print(f"✅ Бот {bot.user} успешно запущен!")
    print(f"📡 На серверах: {len(bot.guilds)}")
    for guild in bot.guilds:
        print(f"   - {guild.name}")
    print("🎮 Бот готов к работе!")

# ==================== КОМАНДЫ ====================
@bot.tree.command(name="menu", description="Открыть главное меню фракций")
async def menu_command(interaction: discord.Interaction):
    user_data = db.get_user(interaction.user.id)
    faction = user_data.get("faction") or "Нет"
    reputation = user_data.get("reputation", 0)
    hierarchy = user_data.get("hierarchy_level") or "Нет"
    
    embed = discord.Embed(title="**ВАШИ ФРАКЦИИ**", color=discord.Color.green())
    embed.description = f"```\nФракция: {faction}\nРепутация: {reputation}\nСтупень: {hierarchy}\n```"
    
    view = MainMenuView(user_id=interaction.user.id)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

@bot.tree.command(name="admin", description="Админ-панель (только для разработчиков)")
async def admin_command(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ У вас нет доступа к админ-панели!", ephemeral=True)
        return
    
    embed = discord.Embed(title="🛠️ Админ-панель", description="Управление фракциями и игроками", color=discord.Color.red())
    await interaction.response.send_message(embed=embed, view=AdminPanelView(), ephemeral=True)

@bot.tree.command(name="join", description="Вступить в фракцию")
@app_commands.describe(faction="Название фракции")
async def join_command(interaction: discord.Interaction, faction: str):
    user_data = db.get_user(interaction.user.id)
    
    if user_data.get("faction"):
        await interaction.response.send_message(f"❌ Вы уже во фракции **{user_data['faction']}**! Сначала выйдите.", ephemeral=True)
        return
    
    if faction not in db.data["factions"]:
        await interaction.response.send_message(f"❌ Фракция '{faction}' не найдена!", ephemeral=True)
        return
    
    hierarchy = db.data["hierarchy_levels"].get(faction, ["Новичок"])
    db.update_user(interaction.user.id, faction=faction, reputation=0, hierarchy_level=hierarchy[0])
    await interaction.response.send_message(f"✅ Вы вступили во фракцию **{faction}**! Ваша ступень: **{hierarchy[0]}**", ephemeral=True)
    print(f"📥 Игрок {interaction.user.name} вступил во фракцию {faction}")

@bot.tree.command(name="leave", description="Выйти из фракции")
async def leave_command(interaction: discord.Interaction):
    user_data = db.get_user(interaction.user.id)
    
    if not user_data.get("faction"):
        await interaction.response.send_message("❌ Вы не состоите ни в какой фракции!", ephemeral=True)
        return
    
    db.update_user(interaction.user.id, faction=None, reputation=0, hierarchy_level="Нет")
    await interaction.response.send_message("✅ Вы вышли из фракции!", ephemeral=True)
    print(f"📤 Игрок {interaction.user.name} вышел из фракции")

# ==================== ЗАПУСК ====================
async def main():
    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
