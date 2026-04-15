import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import json
from typing import Optional, List

# Конфигурация
TOKEN = "ВАШ_ТОКЕН_БОТА"  # На Railway используйте переменную окружения

# Настройки бота
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Цвета для Embed
COLOR_NORMAL = 0x2b2d31
COLOR_ERROR = 0xff5555

# ========== РАБОТА С БАЗОЙ ДАННЫХ ==========

def init_db():
    """Инициализация базы данных SQLite"""
    conn = sqlite3.connect('factions.db')
    cursor = conn.cursor()
    
    # Таблица фракций
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS factions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        description TEXT,
        hierarchy TEXT NOT NULL
    )
    ''')
    
    # Таблица игроков
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS players (
        user_id TEXT PRIMARY KEY,
        faction_id INTEGER,
        reputation INTEGER DEFAULT 0,
        rank_index INTEGER DEFAULT 0,
        FOREIGN KEY (faction_id) REFERENCES factions (id)
    )
    ''')
    
    conn.commit()
    
    # Создание тестовой фракции "Арбузы" если её нет
    cursor.execute("SELECT id FROM factions WHERE name = ?", ("Арбузы",))
    if not cursor.fetchone():
        hierarchy = json.dumps(["Семечко", "Корочка", "Мякоть", "Арбузный лорд"])
        cursor.execute(
            "INSERT INTO factions (name, description, hierarchy) VALUES (?, ?, ?)",
            ("Арбузы", "Тестовая фракция", hierarchy)
        )
        conn.commit()
        print("✅ Создана тестовая фракция 'Арбузы'")
    
    conn.close()

def get_player_faction(user_id: str):
    """Получить информацию о фракции игрока"""
    conn = sqlite3.connect('factions.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT f.name, f.hierarchy, p.reputation, p.rank_index, f.description
    FROM players p
    JOIN factions f ON p.faction_id = f.id
    WHERE p.user_id = ?
    ''', (user_id,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        name, hierarchy_json, rep, rank_index, description = result
        hierarchy = json.loads(hierarchy_json)
        rank_name = hierarchy[rank_index] if rank_index < len(hierarchy) else "—"
        return name, rank_name, rep, description
    return None, None, 0, None

def get_all_factions():
    """Получить список всех фракций"""
    conn = sqlite3.connect('factions.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, description, hierarchy FROM factions")
    result = cursor.fetchall()
    conn.close()
    return result

# ========== КОМАНДЫ ДЛЯ ВСЕХ ИГРОКОВ ==========

class MainMenuView(discord.ui.View):
    """Главное меню с кнопками"""
    def __init__(self):
        super().__init__(timeout=60)
    
    @discord.ui.button(label="Об игроке", style=discord.ButtonStyle.primary)
    async def about_player(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🚧 В разработке", ephemeral=True)
    
    @discord.ui.button(label="Магазин фракций", style=discord.ButtonStyle.success)
    async def shop_factions(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🚧 В разработке", ephemeral=True)
    
    @discord.ui.button(label="Выйти из фракции", style=discord.ButtonStyle.danger)
    async def leave_faction(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🚧 В разработке", ephemeral=True)

@bot.tree.command(name="меню", description="Показать главное меню фракций")
async def menu(interaction: discord.Interaction):
    """Главное меню с информацией об игроке"""
    user_id = str(interaction.user.id)
    faction_name, rank_name, rep, _ = get_player_faction(user_id)
    
    # Формируем блок кода с информацией
    if faction_name is None:
        info_text = "Нет\nРепутация: 0\nСтупень: —"
    else:
        info_text = f"{faction_name}\nРепутация: {rep}\nСтупень: {rank_name}"
    
    embed = discord.Embed(
        title="**ВАШИ ФРАКЦИИ**",
        description=f"```\n{info_text}\n```",
        color=COLOR_NORMAL
    )
    
    await interaction.response.send_message(embed=embed, view=MainMenuView())

@bot.tree.command(name="выйти", description="Выйти из текущей фракции")
async def leave(interaction: discord.Interaction):
    """Выход из фракции"""
    user_id = str(interaction.user.id)
    faction_name, _, _, _ = get_player_faction(user_id)
    
    if faction_name is None:
        embed = discord.Embed(
            description="❌ Вы не состоите ни в одной фракции!",
            color=COLOR_ERROR
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # Обнуляем данные игрока
    conn = sqlite3.connect('factions.db')
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE players SET faction_id = NULL, reputation = 0, rank_index = 0 WHERE user_id = ?",
        (user_id,)
    )
    conn.commit()
    conn.close()
    
    embed = discord.Embed(
        description=f"✅ Вы вышли из фракции **{faction_name}**",
        color=COLOR_NORMAL
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)
    print(f"📤 Игрок {interaction.user.name} вышел из фракции {faction_name}")

@bot.tree.command(name="вступить", description="Вступить во фракцию")
@app_commands.describe(название="Название фракции")
async def join(interaction: discord.Interaction, название: str):
    """Вступление во фракцию"""
    user_id = str(interaction.user.id)
    
    # Проверяем, есть ли у игрока уже фракция
    current_faction, _, _, _ = get_player_faction(user_id)
    if current_faction is not None:
        embed = discord.Embed(
            description=f"❌ Вы уже состоите во фракции **{current_faction}**! Сначала выйдите из неё.",
            color=COLOR_ERROR
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # Ищем фракцию
    conn = sqlite3.connect('factions.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, hierarchy FROM factions WHERE name = ?", (название,))
    result = cursor.fetchone()
    
    if not result:
        embed = discord.Embed(
            description=f"❌ Фракция **{название}** не найдена!",
            color=COLOR_ERROR
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        conn.close()
        return
    
    faction_id, hierarchy_json = result
    hierarchy = json.loads(hierarchy_json)
    
    # Добавляем игрока
    cursor.execute(
        "INSERT OR REPLACE INTO players (user_id, faction_id, reputation, rank_index) VALUES (?, ?, ?, ?)",
        (user_id, faction_id, 0, 0)
    )
    conn.commit()
    conn.close()
    
    embed = discord.Embed(
        description=f"✅ Вы вступили во фракцию **{название}**!\nВаша ступень: **{hierarchy[0]}**",
        color=COLOR_NORMAL
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)
    print(f"📥 Игрок {interaction.user.name} вступил во фракцию {название}")

# ========== АДМИН-ПАНЕЛЬ ==========

class AdminPanelView(discord.ui.View):
    """Панель управления для администратора"""
    def __init__(self):
        super().__init__(timeout=120)
    
    @discord.ui.button(label="➕ Добавить фракцию", style=discord.ButtonStyle.success, row=0)
    async def add_faction(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AddFactionModal())
    
    @discord.ui.button(label="🗑️ Удалить фракцию", style=discord.ButtonStyle.danger, row=0)
    async def remove_faction(self, interaction: discord.Interaction, button: discord.ui.Button):
        factions = get_all_factions()
        if not factions:
            await interaction.response.send_message("❌ Нет доступных фракций для удаления", ephemeral=True)
            return
        
        view = FactionSelectView(factions, "remove")
        await interaction.response.send_message("Выберите фракцию для удаления:", view=view, ephemeral=True)
    
    @discord.ui.button(label="⭐ Добавить репутацию", style=discord.ButtonStyle.primary, row=1)
    async def add_reputation(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ReputationModal())
    
    @discord.ui.button(label="📊 Установить ступень", style=discord.ButtonStyle.primary, row=1)
    async def set_rank(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RankModal())
    
    @discord.ui.button(label="🔄 Перевести игрока", style=discord.ButtonStyle.primary, row=2)
    async def transfer_player(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TransferModal())
    
    @discord.ui.button(label="📋 Список игроков", style=discord.ButtonStyle.secondary, row=2)
    async def list_players(self, interaction: discord.Interaction, button: discord.ui.Button):
        await show_players_list(interaction)
    
    @discord.ui.button(label="🏛️ Список фракций", style=discord.ButtonStyle.secondary, row=3)
    async def list_factions(self, interaction: discord.Interaction, button: discord.ui.Button):
        await show_factions_list(interaction)

class AddFactionModal(discord.ui.Modal, title="Добавление фракции"):
    название = discord.ui.TextInput(label="Название фракции", placeholder="Введите название", required=True)
    иерархия = discord.ui.TextInput(
        label="Иерархия (ступени через запятую)",
        placeholder="Новичок,Боец,Советник,Лидер",
        required=True
    )
    описание = discord.ui.TextInput(
        label="Описание (необязательно)",
        placeholder="Введите описание фракции",
        required=False,
        style=discord.TextStyle.paragraph
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        hierarchy_list = [h.strip() for h in self.иерархия.value.split(',') if h.strip()]
        
        if len(hierarchy_list) < 1:
            embed = discord.Embed(description="❌ Иерархия должна содержать минимум 1 ступень!", color=COLOR_ERROR)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        conn = sqlite3.connect('factions.db')
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "INSERT INTO factions (name, description, hierarchy) VALUES (?, ?, ?)",
                (self.название.value, self.описание.value or "", json.dumps(hierarchy_list))
            )
            conn.commit()
            embed = discord.Embed(
                description=f"✅ Фракция **{self.название.value}** успешно создана!",
                color=COLOR_NORMAL
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            print(f"➕ Админ {interaction.user.name} создал фракцию {self.название.value}")
        except sqlite3.IntegrityError:
            embed = discord.Embed(description="❌ Фракция с таким названием уже существует!", color=COLOR_ERROR)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        finally:
            conn.close()

class ReputationModal(discord.ui.Modal, title="Добавление репутации"):
    user_id = discord.ui.TextInput(label="ID игрока", placeholder="Введите ID пользователя", required=True)
    amount = discord.ui.TextInput(label="Количество (можно отрицательное)", placeholder="10 или -5", required=True)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.amount.value)
            user_id = self.user_id.value
            
            conn = sqlite3.connect('factions.db')
            cursor = conn.cursor()
            
            # Проверяем, есть ли игрок во фракции
            cursor.execute("SELECT faction_id FROM players WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            
            if not result or not result[0]:
                embed = discord.Embed(description="❌ Игрок не состоит ни в одной фракции!", color=COLOR_ERROR)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                conn.close()
                return
            
            cursor.execute(
                "UPDATE players SET reputation = reputation + ? WHERE user_id = ?",
                (amount, user_id)
            )
            conn.commit()
            
            # Получаем новую репутацию
            cursor.execute("SELECT reputation FROM players WHERE user_id = ?", (user_id,))
            new_rep = cursor.fetchone()[0]
            
            embed = discord.Embed(
                description=f"✅ Игроку <@{user_id}> изменена репутация на {amount}\nТеперь: **{new_rep}**",
                color=COLOR_NORMAL
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            print(f"⭐ Админ {interaction.user.name} изменил репутацию игрока {user_id} на {amount}")
            conn.close()
        except ValueError:
            embed = discord.Embed(description="❌ Количество должно быть числом!", color=COLOR_ERROR)
            await interaction.response.send_message(embed=embed, ephemeral=True)

class RankModal(discord.ui.Modal, title="Установка ступени"):
    user_id = discord.ui.TextInput(label="ID игрока", placeholder="Введите ID пользователя", required=True)
    
    async def on_submit(self, interaction: discord.Interaction):
        user_id = self.user_id.value
        
        conn = sqlite3.connect('factions.db')
        cursor = conn.cursor()
        
        # Получаем фракцию игрока и иерархию
        cursor.execute('''
        SELECT f.hierarchy, p.faction_id
        FROM players p
        JOIN factions f ON p.faction_id = f.id
        WHERE p.user_id = ?
        ''', (user_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            embed = discord.Embed(description="❌ Игрок не состоит ни в одной фракции!", color=COLOR_ERROR)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        hierarchy = json.loads(result[0])
        
        # Создаем Select меню для выбора ступени
        view = RankSelectView(user_id, hierarchy)
        await interaction.response.send_message("Выберите новую ступень для игрока:", view=view, ephemeral=True)

class TransferModal(discord.ui.Modal, title="Перевод игрока"):
    user_id = discord.ui.TextInput(label="ID игрока", placeholder="Введите ID пользователя", required=True)
    
    async def on_submit(self, interaction: discord.Interaction):
        user_id = self.user_id.value
        
        conn = sqlite3.connect('factions.db')
        cursor = conn.cursor()
        
        # Получаем список фракций
        cursor.execute("SELECT id, name FROM factions")
        factions = cursor.fetchall()
        conn.close()
        
        if not factions:
            embed = discord.Embed(description="❌ Нет доступных фракций!", color=COLOR_ERROR)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        view = FactionSelectView(factions, "transfer", user_id)
        await interaction.response.send_message("Выберите фракцию для перевода:", view=view, ephemeral=True)

class RankSelectView(discord.ui.View):
    def __init__(self, user_id: str, hierarchy: List[str]):
        super().__init__(timeout=60)
        self.user_id = user_id
        
        select = discord.ui.Select(
            placeholder="Выберите ступень",
            options=[
                discord.SelectOption(label=rank, value=str(i))
                for i, rank in enumerate(hierarchy)
            ]
        )
        select.callback = self.rank_callback
        self.add_item(select)
    
    async def rank_callback(self, interaction: discord.Interaction):
        rank_index = int(interaction.data["values"][0])
        
        conn = sqlite3.connect('factions.db')
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE players SET rank_index = ? WHERE user_id = ?",
            (rank_index, self.user_id)
        )
        conn.commit()
        conn.close()
        
        embed = discord.Embed(
            description=f"✅ Ступень игрока <@{self.user_id}> изменена!",
            color=COLOR_NORMAL
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        print(f"📊 Админ {interaction.user.name} изменил ступень игрока {self.user_id}")

class FactionSelectView(discord.ui.View):
    def __init__(self, factions: List[tuple], action: str, user_id: str = None):
        super().__init__(timeout=60)
        self.factions = factions
        self.action = action
        self.user_id = user_id
        
        select = discord.ui.Select(
            placeholder="Выберите фракцию",
            options=[
                discord.SelectOption(label=name, value=str(fid))
                for fid, name in factions
            ][:25]  # Discord ограничивает 25 опциями
        )
        select.callback = self.faction_callback
        self.add_item(select)
    
    async def faction_callback(self, interaction: discord.Interaction):
        faction_id = int(interaction.data["values"][0])
        faction_name = next(name for fid, name in self.factions if fid == faction_id)
        
        if self.action == "remove":
            # Проверяем, есть ли игроки во фракции
            conn = sqlite3.connect('factions.db')
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM players WHERE faction_id = ?", (faction_id,))
            count = cursor.fetchone()[0]
            
            if count > 0:
                embed = discord.Embed(
                    description=f"❌ Нельзя удалить фракцию **{faction_name}**, в ней есть {count} игроков!",
                    color=COLOR_ERROR
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                conn.close()
                return
            
            cursor.execute("DELETE FROM factions WHERE id = ?", (faction_id,))
            conn.commit()
            conn.close()
            
            embed = discord.Embed(
                description=f"✅ Фракция **{faction_name}** удалена!",
                color=COLOR_NORMAL
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            print(f"🗑️ Админ {interaction.user.name} удалил фракцию {faction_name}")
        
        elif self.action == "transfer" and self.user_id:
            conn = sqlite3.connect('factions.db')
            cursor = conn.cursor()
            
            # Получаем иерархию новой фракции
            cursor.execute("SELECT hierarchy FROM factions WHERE id = ?", (faction_id,))
            hierarchy_json = cursor.fetchone()[0]
            hierarchy = json.loads(hierarchy_json)
            
            # Переводим игрока
            cursor.execute(
                "UPDATE players SET faction_id = ?, reputation = 0, rank_index = 0 WHERE user_id = ?",
                (faction_id, self.user_id)
            )
            conn.commit()
            conn.close()
            
            embed = discord.Embed(
                description=f"✅ Игрок <@{self.user_id}> переведён во фракцию **{faction_name}**!\nНовая ступень: **{hierarchy[0]}**",
                color=COLOR_NORMAL
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            print(f"🔄 Админ {interaction.user.name} перевёл игрока {self.user_id} во фракцию {faction_name}")

async def show_players_list(interaction: discord.Interaction):
    """Показать список всех игроков с пагинацией"""
    conn = sqlite3.connect('factions.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT p.user_id, f.name, p.reputation, f.hierarchy, p.rank_index
    FROM players p
    LEFT JOIN factions f ON p.faction_id = f.id
    ORDER BY p.user_id
    ''')
    
    players = cursor.fetchall()
    conn.close()
    
    if not players:
        embed = discord.Embed(description="📭 Нет зарегистрированных игроков", color=COLOR_NORMAL)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # Пагинация по 10 игроков на страницу
    items_per_page = 10
    pages = []
    
    for i in range(0, len(players), items_per_page):
        page_players = players[i:i+items_per_page]
        description = ""
        for user_id, faction_name, rep, hierarchy_json, rank_index in page_players:
            if faction_name:
                hierarchy = json.loads(hierarchy_json)
                rank_name = hierarchy[rank_index] if rank_index < len(hierarchy) else "—"
                description += f"**<@{user_id}>**\n  Фракция: {faction_name}\n  Репутация: {rep}\n  Ступень: {rank_name}\n\n"
            else:
                description += f"**<@{user_id}>**\n  Нет фракции\n\n"
        pages.append(description)
    
    view = PaginationView(pages)
    embed = discord.Embed(
        title="📋 Список игроков",
        description=pages[0][:4000],  # Discord лимит 4096 символов
        color=COLOR_NORMAL
    )
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def show_factions_list(interaction: discord.Interaction):
    """Показать список всех фракций"""
    factions = get_all_factions()
    
    if not factions:
        embed = discord.Embed(description="📭 Нет созданных фракций", color=COLOR_NORMAL)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    description = ""
    for fid, name, desc, hierarchy_json in factions:
        hierarchy = json.loads(hierarchy_json)
        hierarchy_str = " → ".join(hierarchy)
        description += f"**{name}**\n"
        if desc:
            description += f"📝 {desc}\n"
        description += f"📊 Иерархия: {hierarchy_str}\n\n"
    
    embed = discord.Embed(
        title="🏛️ Список фракций",
        description=description[:4000],
        color=COLOR_NORMAL
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

class PaginationView(discord.ui.View):
    """Пагинация для списков"""
    def __init__(self, pages: List[str]):
        super().__init__(timeout=60)
        self.pages = pages
        self.current_page = 0
    
    @discord.ui.button(label="◀️", style=discord.ButtonStyle.secondary)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            embed = discord.Embed(
                title="📋 Список игроков",
                description=self.pages[self.current_page][:4000],
                color=COLOR_NORMAL
            )
            await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="▶️", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            embed = discord.Embed(
                title="📋 Список игроков",
                description=self.pages[self.current_page][:4000],
                color=COLOR_NORMAL
            )
            await interaction.response.edit_message(embed=embed, view=self)

@bot.tree.command(name="admin", description="Админ-панель (только для разработчиков)")
async def admin_panel(interaction: discord.Interaction):
    """Админ-панель"""
    # Проверяем наличие роли "Разработчик"
    role = discord.utils.get(interaction.user.roles, name="Разработчик")
    
    if not role:
        embed = discord.Embed(
            description="❌ У вас нет прав для использования этой команды!",
            color=COLOR_ERROR
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    embed = discord.Embed(
        title="🛠️ Админ-панель",
        description="Управление фракциями и игроками",
        color=COLOR_NORMAL
    )
    await interaction.response.send_message(embed=embed, view=AdminPanelView(), ephemeral=True)

# ========== ЗАПУСК БОТА ==========

@bot.event
async def on_ready():
    print(f"✅ Бот {bot.user} запущен!")
    init_db()
    
    # Синхронизация slash-команд
    try:
        synced = await bot.tree.sync()
        print(f"📡 Синхронизировано {len(synced)} команд")
    except Exception as e:
        print(f"❌ Ошибка синхронизации: {e}")

# Запуск бота
if __name__ == "__main__":
    bot.run(TOKEN)
