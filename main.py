import discord
from discord import app_commands
from discord.ui import Button, View
import json
import os
from typing import Optional, Dict, List

# ==================== КОНФИГУРАЦИЯ ====================
TOKEN = os.getenv('DISCORD_TOKEN')  # Railway сам подставит переменную окружения
ADMIN_ROLE_NAME = "Разработчик"

# ==================== БАЗА ДАННЫХ ====================
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
                "Арбузы": ["Новичок", "Садовод", "Старший садовод", "Хранитель семян", "Арбузный лорд"]
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

# ==================== ГЛАВНОЕ МЕНЮ (VIEW) ====================
class MainMenuView(View):
    def __init__(self, user_id: int):
        super().__init__(timeout=None)
        self.user_id = user_id

    @discord.ui.button(label="Об игроке", style=discord.ButtonStyle.primary, custom_id="about_player")
    async def about_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это меню не для вас! Используйте `/menu`", ephemeral=True)
            return
        await interaction.response.send_message("🚧 В разработке", ephemeral=True)

    @discord.ui.button(label="Магазин фракций", style=discord.ButtonStyle.success, custom_id="shop")
    async def shop_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это меню не для вас! Используйте `/menu`", ephemeral=True)
            return
        await interaction.response.send_message("🚧 В разработке", ephemeral=True)

    @discord.ui.button(label="Выйти из фракции", style=discord.ButtonStyle.danger, custom_id="leave_faction")
    async def leave_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это меню не для вас! Используйте `/menu`", ephemeral=True)
            return
        await interaction.response.send_message("🚧 В разработке", ephemeral=True)

# ==================== АДМИН ПАНЕЛЬ (VIEW) ====================
class AdminFactionSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=f, value=f) for f in db.data["factions"]]
        super().__init__(placeholder="Выберите фракцию...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"Выбрана фракция: **{self.values[0]}**", ephemeral=True)

class AdminPanelView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(AdminFactionSelect())

    @discord.ui.button(label="➕ Добавить фракцию", style=discord.ButtonStyle.green, row=1)
    async def add_faction_btn(self, interaction: discord.Interaction, button: Button):
        modal = AddFactionModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="📊 Редактировать игрока", style=discord.ButtonStyle.blurple, row=1)
    async def edit_player_btn(self, interaction: discord.Interaction, button: Button):
        modal = EditPlayerModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="📋 Список фракций", style=discord.ButtonStyle.gray, row=2)
    async def list_factions_btn(self, interaction: discord.Interaction, button: Button):
        factions = "\n".join([f"• {f}" for f in db.data["factions"]])
        await interaction.response.send_message(f"**Все фракции:**\n{factions}", ephemeral=True)

# ==================== МОДАЛЬНЫЕ ОКНА ====================
class AddFactionModal(discord.ui.Modal, title="Добавить новую фракцию"):
    name = discord.ui.TextInput(label="Название фракции", placeholder="Например: Арбузы", max_length=50)

    async def on_submit(self, interaction: discord.Interaction):
        if self.name.value not in db.data["factions"]:
            db.data["factions"].append(self.name.value)
            db.data["hierarchy_levels"][self.name.value] = ["Новичок", "Участник", "Ветеран", "Лидер"]
            db.save()
            await interaction.response.send_message(f"✅ Фракция **{self.name.value}** добавлена!", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Фракция уже существует!", ephemeral=True)

class EditPlayerModal(discord.ui.Modal, title="Редактировать игрока"):
    user_id = discord.ui.TextInput(label="ID пользователя Discord", placeholder="Например: 123456789012345678")
    faction = discord.ui.TextInput(label="Фракция", placeholder="Название фракции", required=False)
    reputation = discord.ui.TextInput(label="Репутация", placeholder="Число", required=False)
    hierarchy = discord.ui.TextInput(label="Ступень в иерархии", placeholder="Название ступени", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            uid = str(int(self.user_id.value))
        except ValueError:
            await interaction.response.send_message("❌ Неверный ID пользователя!", ephemeral=True)
            return

        updates = {}
        if self.faction.value:
            if self.faction.value in db.data["factions"]:
                updates["faction"] = self.faction.value
            else:
                await interaction.response.send_message(f"❌ Фракция '{self.faction.value}' не найдена!", ephemeral=True)
                return

        if self.reputation.value:
            try:
                updates["reputation"] = int(self.reputation.value)
            except ValueError:
                await interaction.response.send_message("❌ Репутация должна быть числом!", ephemeral=True)
                return

        if self.hierarchy.value:
            updates["hierarchy_level"] = self.hierarchy.value

        if updates:
            db.update_user(uid, **updates)
            await interaction.response.send_message(f"✅ Данные пользователя <@{uid}> обновлены!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Не указано ни одного поля для обновления!", ephemeral=True)

# ==================== КЛИЕНТ ====================
class FactionBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        print(f"✅ Бот запущен! Синхронизировано команд.")

client = FactionBot()

# ==================== ПРОВЕРКА АДМИНА ====================
def is_admin(interaction: discord.Interaction) -> bool:
    if not interaction.guild:
        return False
    member = interaction.guild.get_member(interaction.user.id)
    if not member:
        return False
    return any(role.name == ADMIN_ROLE_NAME for role in member.roles)

# ==================== КОМАНДЫ ====================
@client.tree.command(name="menu", description="Открыть главное меню фракций")
async def menu_command(interaction: discord.Interaction):
    user_data = db.get_user(interaction.user.id)

    faction = user_data.get("faction") or "Нет"
    reputation = user_data.get("reputation", 0)
    hierarchy = user_data.get("hierarchy_level") or "Нет"

    embed = discord.Embed(
        title="**ВАШИ ФРАКЦИИ**",
        color=discord.Color.green()
    )
    embed.add_field(
        name="",
        value=f"```Ваша фракция: {faction}\nВаша репутация: {reputation}\nСтупень в иерархии: {hierarchy}```",
        inline=False
    )

    view = MainMenuView(user_id=interaction.user.id)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

@client.tree.command(name="admin", description="Открыть админ-панель (только для разработчиков)")
async def admin_command(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ У вас нет доступа к админ-панели!", ephemeral=True)
        return

    embed = discord.Embed(
        title="⚙️ Админ-панель",
        description="Управление фракциями и игроками",
        color=discord.Color.red()
    )

    factions_list = "\n".join([f"• {f}" for f in db.data["factions"]])
    embed.add_field(name="Доступные фракции:", value=factions_list or "Нет фракций", inline=False)

    view = AdminPanelView()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

@client.tree.command(name="join", description="Вступить в фракцию")
@app_commands.describe(faction="Название фракции")
async def join_command(interaction: discord.Interaction, faction: str):
    if faction not in db.data["factions"]:
        await interaction.response.send_message(f"❌ Фракция '{faction}' не найдена!", ephemeral=True)
        return

    hierarchy_levels = db.data["hierarchy_levels"].get(faction, ["Новичок"])
    db.update_user(
        interaction.user.id,
        faction=faction,
        reputation=0,
        hierarchy_level=hierarchy_levels[0]
    )
    await interaction.response.send_message(f"✅ Вы вступили во фракцию **{faction}**!", ephemeral=True)

@client.tree.command(name="set_reputation", description="Установить репутацию игроку (админ)")
@app_commands.describe(user="Пользователь", reputation="Новая репутация")
async def set_rep_command(interaction: discord.Interaction, user: discord.User, reputation: int):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Нет доступа!", ephemeral=True)
        return

    db.update_user(user.id, reputation=reputation)
    await interaction.response.send_message(f"✅ Репутация {user.mention} установлена на **{reputation}**", ephemeral=True)

@client.tree.command(name="set_faction", description="Установить фракцию игроку (админ)")
@app_commands.describe(user="Пользователь", faction="Название фракции")
async def set_faction_command(interaction: discord.Interaction, user: discord.User, faction: str):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Нет доступа!", ephemeral=True)
        return

    if faction not in db.data["factions"]:
        await interaction.response.send_message(f"❌ Фракция '{faction}' не найдена!", ephemeral=True)
        return

    hierarchy = db.data["hierarchy_levels"].get(faction, ["Новичок"])[0]
    db.update_user(user.id, faction=faction, hierarchy_level=hierarchy)
    await interaction.response.send_message(f"✅ {user.mention} теперь во фракции **{faction}**", ephemeral=True)

# ==================== ЗАПУСК ====================
if __name__ == "__main__":
    if not TOKEN:
        print("❌ Ошибка: DISCORD_TOKEN не найден в переменных окружения!")
    else:
        client.run(TOKEN)
