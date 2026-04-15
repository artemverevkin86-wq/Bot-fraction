import discord
from discord import app_commands
from discord.ui import Button, View, Modal, TextInput, Select
import json
import os
import asyncio
from typing import Optional, List, Dict
from datetime import datetime, timedelta

# ==================== КОНФИГУРАЦИЯ ====================
TOKEN = os.getenv('TOKEN')
ADMIN_ROLE_NAME = "."

if not TOKEN:
    print("❌ ОШИБКА: TOKEN не найден!")
    exit(1)

# ==================== НАСТРОЙКА INTENTS ====================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# ==================== БАЗА ДАННЫХ ====================
class Database:
    def __init__(self, filename: str = "factions.json"):
        self.filename = filename
        self.data = self.load()

    def load(self):
        if os.path.exists(self.filename):
            with open(self.filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "users": {},
            "factions": {},
            "npcs": {}
        }

    def save(self):
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def get_user(self, user_id: str) -> dict:
        user_id = str(user_id)
        if user_id not in self.data["users"]:
            self.data["users"][user_id] = {
                "faction_id": None,
                "reputation": 0,
                "rank": "Новичок",
                "joined_at": None
            }
            self.save()
        return self.data["users"][user_id]

    def update_user(self, user_id: str, **kwargs):
        user_id = str(user_id)
        if user_id not in self.data["users"]:
            self.get_user(user_id)
        self.data["users"][user_id].update(kwargs)
        self.save()

    def get_faction(self, faction_id: str) -> dict:
        return self.data["factions"].get(faction_id)

    def get_faction_by_name(self, name: str):
        for fid, data in self.data["factions"].items():
            if data["name"] == name:
                return fid, data
        return None, None

    def get_user_faction(self, user_id: str):
        user = self.get_user(user_id)
        if user["faction_id"]:
            return self.get_faction(user["faction_id"])
        return None

    def is_faction_leader(self, user_id: str) -> bool:
        user = self.get_user(user_id)
        if not user["faction_id"]:
            return False
        faction = self.get_faction(user["faction_id"])
        return faction and faction["leader_id"] == str(user_id)

    def get_faction_members(self, faction_id: str) -> list:
        members = []
        for uid, user in self.data["users"].items():
            if user.get("faction_id") == faction_id:
                members.append(uid)
        return members

    def get_faction_npcs(self, faction_id: str) -> list:
        npcs = []
        for nid, npc in self.data["npcs"].items():
            if npc.get("faction_id") == faction_id:
                npcs.append(nid)
        return npcs
    
    def add_npc(self, faction_id: str, name: str, job: str = None, loyalty: int = 50, skill_level: int = 1):
        npc_id = str(int(datetime.now().timestamp() * 1000))
        self.data["npcs"][npc_id] = {
            "name": name,
            "faction_id": faction_id,
            "job": job,
            "is_working": False,
            "work_end_time": None,
            "loyalty": loyalty,
            "skill_level": skill_level,
            "created_at": datetime.now().isoformat()
        }
        self.save()
        return npc_id
    
    def assign_npc_work(self, npc_id: str, job: str, hours: int, reward: dict):
        npc = self.data["npcs"].get(npc_id)
        if npc:
            npc["job"] = job
            npc["is_working"] = True
            npc["work_end_time"] = (datetime.now() + timedelta(hours=hours)).isoformat()
            npc["work_reward"] = reward
            self.save()
            return True
        return False
    
    def check_completed_works(self):
        """Проверяет завершённые работы NPC и выдаёт награды"""
        completed = []
        now = datetime.now()
        for nid, npc in self.data["npcs"].items():
            if npc.get("is_working") and npc.get("work_end_time"):
                end_time = datetime.fromisoformat(npc["work_end_time"])
                if now >= end_time:
                    npc["is_working"] = False
                    reward = npc.get("work_reward", {"gold": 10, "wood": 5, "ore": 2})
                    npc["job"] = None
                    npc["work_end_time"] = None
                    npc["work_reward"] = None
                    completed.append((nid, reward))
        if completed:
            self.save()
        return completed

db = Database()

# ==================== ПРОВЕРКА АДМИНА ====================
def is_admin(interaction: discord.Interaction) -> bool:
    if not interaction.guild:
        return False
    return any(role.name == ADMIN_ROLE_NAME for role in interaction.user.roles)

# ==================== ФУНКЦИИ ДЛЯ ОТОБРАЖЕНИЯ ====================
async def show_player_stats(interaction: discord.Interaction, target_user: discord.User):
    """Публичная статистика игрока (без кнопок)"""
    user_data = db.get_user(target_user.id)
    faction = db.get_user_faction(target_user.id)
    
    embed = discord.Embed(
        title=f"📊 ИГРОК: {target_user.name}",
        color=discord.Color.green()
    )
    
    if faction:
        joined = user_data.get("joined_at", "")
        joined_str = joined[:10] if joined and len(joined) >= 10 else (joined or "Неизвестно")
        embed.add_field(name="🏛️ Фракция", value=faction["name"], inline=True)
        embed.add_field(name="⭐ Репутация", value=user_data["reputation"], inline=True)
        embed.add_field(name="📈 Ступень", value=user_data["rank"], inline=True)
        embed.add_field(name="👑 Владеет фракцией?", value="Да" if db.is_faction_leader(target_user.id) else "Нет", inline=True)
        embed.add_field(name="📅 Вступил", value=joined_str, inline=True)
    else:
        embed.description = "```\n🚫 Не состоит ни в одной фракции\n```"
    
    await interaction.response.send_message(embed=embed, ephemeral=False)

async def show_faction_members(interaction: discord.Interaction, faction_id: str):
    """Список членов фракции"""
    faction = db.get_faction(faction_id)
    members = db.get_faction_members(faction_id)
    
    if not members:
        await interaction.response.send_message("📭 В фракции нет игроков", ephemeral=True)
        return
    
    description = ""
    for uid in members:
        user = db.get_user(uid)
        description += f"<@{uid}> — {user['rank']} (реп: {user['reputation']})\n"
        if len(description) > 3900:
            description += "..."
            break
    
    embed = discord.Embed(
        title=f"👥 Члены фракции {faction['name']}",
        description=description[:4000],
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

async def show_faction_npcs(interaction: discord.Interaction, faction_id: str):
    """Список NPC фракции"""
    faction = db.get_faction(faction_id)
    npcs = db.get_faction_npcs(faction_id)
    
    if not npcs:
        await interaction.response.send_message("📭 У фракции нет NPC", ephemeral=True)
        return
    
    description = ""
    for nid in npcs:
        npc = db.data["npcs"][nid]
        work_status = "🔨 Работает" if npc.get("is_working") else "💤 Свободен"
        work_info = f" ({npc.get('job', 'Нет работы')})" if npc.get("job") else ""
        description += f"**{npc['name']}** — {work_status}{work_info}, лояльность: {npc.get('loyalty', 50)}%\n"
        if len(description) > 3900:
            description += "..."
            break
    
    embed = discord.Embed(
        title=f"🤖 NPC фракции {faction['name']}",
        description=description[:4000],
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

async def show_faction_economy(interaction: discord.Interaction, faction_id: str):
    """Экономика фракции"""
    faction = db.get_faction(faction_id)
    
    embed = discord.Embed(
        title=f"💰 Экономика {faction['name']}",
        color=discord.Color.gold()
    )
    
    resources = faction.get("resources", {"gold": 0, "wood": 0, "ore": 0})
    embed.add_field(name="💰 Золото", value=resources.get("gold", 0), inline=True)
    embed.add_field(name="🪵 Древесина", value=resources.get("wood", 0), inline=True)
    embed.add_field(name="⛏️ Руда", value=resources.get("ore", 0), inline=True)
    embed.add_field(name="📊 Налог", value=f"{faction['tax']}%", inline=True)
    embed.add_field(name="💎 Валюта", value=faction["currency"], inline=True)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

async def show_faction_menu(interaction: discord.Interaction, target_user: discord.User):
    """Публичная информация о фракции игрока (с кнопками для владельца)"""
    user_data = db.get_user(target_user.id)
    
    if not user_data["faction_id"]:
        embed = discord.Embed(
            title="🏛️ ФРАКЦИЯ",
            description="```\n🚫 Игрок не состоит во фракции\n```",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=False)
        return
    
    faction = db.get_faction(user_data["faction_id"])
    members = db.get_faction_members(user_data["faction_id"])
    npcs = db.get_faction_npcs(user_data["faction_id"])
    
    hex_color = faction.get("color", "#2b2d31")
    if hex_color.startswith("#"):
        try:
            color = int(hex_color.lstrip("#"), 16)
        except:
            color = 0x2b2d31
    else:
        color = 0x2b2d31
    
    embed = discord.Embed(
        title=f"{faction.get('flag', '🏛️')} {faction['name']} {faction.get('flag', '🏛️')}",
        color=color
    )
    
    embed.add_field(name="👑 Лидер", value=f"<@{faction['leader_id']}>", inline=True)
    embed.add_field(name="📊 Тип", value=faction.get("type", "торговая").capitalize(), inline=True)
    embed.add_field(name="💰 Налог", value=f"{faction['tax']}%", inline=True)
    embed.add_field(name="👥 Игроков", value=f"{len(members)}/{faction['max_players']}", inline=True)
    embed.add_field(name="🤖 NPC", value=str(len(npcs)), inline=True)
    embed.add_field(name="💎 Валюта", value=faction["currency"], inline=True)
    embed.add_field(name="🏠 База", value=f"<#{faction['base_channel']}>" if faction['base_channel'].isdigit() else faction['base_channel'], inline=True)
    embed.add_field(name="📜 Иерархия", value=" → ".join(faction["hierarchy"]), inline=False)
    
    if faction.get("description"):
        embed.add_field(name="📝 Описание", value=faction["description"][:1024], inline=False)
    
    if interaction.user.id == target_user.id:
        view = FactionMenuView(interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=False)
    else:
        await interaction.response.send_message(embed=embed, ephemeral=False)

# ==================== КНОПКИ И МЕНЮ ====================
class MainMenuView(View):
    def __init__(self, user_id: int):
        super().__init__(timeout=60)
        self.user_id = user_id

    @discord.ui.button(label="📊 Моя статистика", style=discord.ButtonStyle.primary)
    async def my_stats(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это не ваше меню!", ephemeral=True)
            return
        await show_player_stats(interaction, interaction.user)

    @discord.ui.button(label="🏛️ Моя фракция", style=discord.ButtonStyle.success)
    async def my_faction(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это не ваше меню!", ephemeral=True)
            return
        await show_faction_menu(interaction, interaction.user)

    @discord.ui.button(label="⚙️ Действия", style=discord.ButtonStyle.secondary)
    async def actions(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это не ваше меню!", ephemeral=True)
            return
        view = ActionsView(self.user_id)
        embed = discord.Embed(title="⚙️ Действия", description="Выберите действие:", color=discord.Color.blue())
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class ActionsView(View):
    def __init__(self, user_id: int):
        super().__init__(timeout=60)
        self.user_id = user_id

    @discord.ui.button(label="🚪 Выйти из фракции", style=discord.ButtonStyle.danger)
    async def leave_faction(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это не ваше меню!", ephemeral=True)
            return
        
        user = db.get_user(self.user_id)
        if not user["faction_id"]:
            await interaction.response.send_message("❌ Вы не состоите во фракции!", ephemeral=True)
            return
        
        if db.is_faction_leader(self.user_id):
            await interaction.response.send_message("❌ Лидер не может выйти! Используйте /передать_лидерство или /распустить", ephemeral=True)
            return
        
        faction = db.get_faction(user["faction_id"])
        db.update_user(self.user_id, faction_id=None, reputation=0, rank="Новичок", joined_at=None)
        await interaction.response.send_message(f"✅ Вы вышли из фракции **{faction['name']}**", ephemeral=True)

    @discord.ui.button(label="📢 Пригласить игрока", style=discord.ButtonStyle.primary)
    async def invite_player(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это не ваше меню!", ephemeral=True)
            return
        
        user = db.get_user(self.user_id)
        if not user["faction_id"]:
            await interaction.response.send_message("❌ Вы не состоите во фракции!", ephemeral=True)
            return
        
        modal = InvitePlayerModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="👑 Передать лидерство", style=discord.ButtonStyle.secondary)
    async def transfer_leadership(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это не ваше меню!", ephemeral=True)
            return
        
        if not db.is_faction_leader(self.user_id):
            await interaction.response.send_message("❌ Только лидер может передать лидерство!", ephemeral=True)
            return
        
        modal = TransferLeadershipModal()
        await interaction.response.send_modal(modal)

class FactionMenuView(View):
    def __init__(self, user_id: int):
        super().__init__(timeout=60)
        self.user_id = user_id

    @discord.ui.button(label="📜 Список членов", style=discord.ButtonStyle.primary)
    async def members_list(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это не ваше меню!", ephemeral=True)
            return
        
        user = db.get_user(self.user_id)
        if not user["faction_id"]:
            await interaction.response.send_message("❌ Вы не состоите во фракции!", ephemeral=True)
            return
        
        await show_faction_members(interaction, user["faction_id"])

    @discord.ui.button(label="🤖 Список NPC", style=discord.ButtonStyle.success)
    async def npcs_list(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это не ваше меню!", ephemeral=True)
            return
        
        user = db.get_user(self.user_id)
        if not user["faction_id"]:
            await interaction.response.send_message("❌ Вы не состоите во фракции!", ephemeral=True)
            return
        
        await show_faction_npcs(interaction, user["faction_id"])

    @discord.ui.button(label="💰 Налоги и ресурсы", style=discord.ButtonStyle.secondary)
    async def taxes(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это не ваше меню!", ephemeral=True)
            return
        
        user = db.get_user(self.user_id)
        if not user["faction_id"]:
            await interaction.response.send_message("❌ Вы не состоите во фракции!", ephemeral=True)
            return
        
        await show_faction_economy(interaction, user["faction_id"])

    @discord.ui.button(label="👑 Управление (лидер)", style=discord.ButtonStyle.danger)
    async def leader_controls(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это не ваше меню!", ephemeral=True)
            return
        
        if not db.is_faction_leader(self.user_id):
            await interaction.response.send_message("❌ Только лидер фракции может управлять!", ephemeral=True)
            return
        
        view = LeaderActionsView(self.user_id)
        embed = discord.Embed(title="👑 Управление фракцией", description="Действия лидера:", color=discord.Color.gold())
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class LeaderActionsView(View):
    def __init__(self, user_id: int):
        super().__init__(timeout=60)
        self.user_id = user_id

    @discord.ui.button(label="📊 Повысить/Понизить", style=discord.ButtonStyle.primary)
    async def change_rank(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это не ваше меню!", ephemeral=True)
            return
        
        modal = ChangeRankModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="💰 Изменить налоги", style=discord.ButtonStyle.success)
    async def change_tax(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это не ваше меню!", ephemeral=True)
            return
        
        modal = ChangeTaxModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🤖 Управление NPC", style=discord.ButtonStyle.secondary)
    async def manage_npcs(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это не ваше меню!", ephemeral=True)
            return
        
        view = NPCManageView(self.user_id)
        embed = discord.Embed(title="🤖 Управление NPC", description="Выберите действие:", color=discord.Color.purple())
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class NPCManageView(View):
    def __init__(self, user_id: int):
        super().__init__(timeout=60)
        self.user_id = user_id

    @discord.ui.button(label="➕ Нанять NPC", style=discord.ButtonStyle.success)
    async def hire_npc(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это не ваше меню!", ephemeral=True)
            return
        
        modal = HireNPCModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="📋 Назначить работу", style=discord.ButtonStyle.primary)
    async def assign_work(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это не ваше меню!", ephemeral=True)
            return
        
        user = db.get_user(self.user_id)
        npcs = db.get_faction_npcs(user["faction_id"])
        
        if not npcs:
            await interaction.response.send_message("❌ У вашей фракции нет NPC!", ephemeral=True)
            return
        
        view = AssignWorkSelectView(self.user_id, npcs)
        await interaction.response.send_message("Выберите NPC для назначения работы:", view=view, ephemeral=True)

    @discord.ui.button(label="🗑️ Уволить NPC", style=discord.ButtonStyle.danger)
    async def fire_npc(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это не ваше меню!", ephemeral=True)
            return
        
        user = db.get_user(self.user_id)
        npcs = db.get_faction_npcs(user["faction_id"])
        
        if not npcs:
            await interaction.response.send_message("❌ У вашей фракции нет NPC!", ephemeral=True)
            return
        
        view = FireNPCSelectView(self.user_id, npcs)
        await interaction.response.send_message("Выберите NPC для увольнения:", view=view, ephemeral=True)

class HireNPCModal(Modal, title="Наём NPC"):
    name = TextInput(label="Имя NPC", placeholder="Например: Лесоруб Петя", max_length=30, min_length=2)
    loyalty = TextInput(label="Лояльность (0-100)", placeholder="50", default="50")
    skill = TextInput(label="Уровень навыка (1-10)", placeholder="1", default="1")

    async def on_submit(self, interaction: discord.Interaction):
        user = db.get_user(interaction.user.id)
        if not user["faction_id"]:
            await interaction.response.send_message("❌ Вы не состоите во фракции!", ephemeral=True)
            return
        
        try:
            loyalty = int(self.loyalty.value)
            if loyalty < 0 or loyalty > 100:
                raise ValueError
        except:
            loyalty = 50
        
        try:
            skill = int(self.skill.value)
            if skill < 1 or skill > 10:
                raise ValueError
        except:
            skill = 1
        
        faction = db.get_faction(user["faction_id"])
        resources = faction.get("resources", {"gold": 0})
        
        hire_cost = 50
        if resources.get("gold", 0) < hire_cost:
            await interaction.response.send_message(f"❌ Недостаточно золота! Нужно {hire_cost} {faction['currency']}", ephemeral=True)
            return
        
        resources["gold"] = resources.get("gold", 0) - hire_cost
        faction["resources"] = resources
        
        npc_id = db.add_npc(user["faction_id"], self.name.value, None, loyalty, skill)
        
        await interaction.response.send_message(f"✅ NPC **{self.name.value}** нанят за {hire_cost} {faction['currency']}!\nЛояльность: {loyalty}, Навык: {skill}", ephemeral=True)
        print(f"🤖 {interaction.user.name} нанял NPC {self.name.value}")

class AssignWorkSelectView(View):
    def __init__(self, user_id: int, npcs: list):
        super().__init__(timeout=60)
        self.user_id = user_id
        options = []
        for nid in npcs[:25]:
            npc = db.data["npcs"][nid]
            status = "🔨" if npc.get("is_working") else "💤"
            options.append(discord.SelectOption(label=f"{status} {npc['name']}", value=nid))
        
        select = Select(placeholder="Выберите NPC", options=options)
        select.callback = self.npc_selected
        self.add_item(select)
    
    async def npc_selected(self, interaction: discord.Interaction):
        npc_id = interaction.data["values"][0]
        npc = db.data["npcs"][npc_id]
        
        if npc.get("is_working"):
            await interaction.response.send_message("❌ Этот NPC уже работает!", ephemeral=True)
            return
        
        view = WorkTypeSelectView(self.user_id, npc_id)
        embed = discord.Embed(title=f"📋 Выберите работу для {npc['name']}", color=discord.Color.blue())
        await interaction.response.edit_message(embed=embed, view=view)

class WorkTypeSelectView(View):
    def __init__(self, user_id: int, npc_id: str):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.npc_id = npc_id
        
        self.jobs = {
            "🌲 Лесоруб": {"hours": 2, "reward": {"wood": 10}},
            "⛏️ Шахтёр": {"hours": 2, "reward": {"ore": 8}},
            "💰 Сборщик налогов": {"hours": 3, "reward": {"gold": 15}},
            "🏛️ Строитель": {"hours": 4, "reward": {"wood": 5, "ore": 5}}
        }
        
        select = Select(placeholder="Выберите работу", options=[
            discord.SelectOption(label=name, description=f"{data['hours']} часа(ов)", value=name)
            for name, data in self.jobs.items()
        ])
        select.callback = self.work_selected
        self.add_item(select)
    
    async def work_selected(self, interaction: discord.Interaction):
        job_name = interaction.data["values"][0]
        job = self.jobs[job_name]
        
        db.assign_npc_work(self.npc_id, job_name, job["hours"], job["reward"])
        
        npc = db.data["npcs"][self.npc_id]
        await interaction.response.send_message(f"✅ {npc['name']} отправлен на работу **{job_name}** на {job['hours']} часа(ов)!", ephemeral=True)
        print(f"🔨 {interaction.user.name} отправил NPC {npc['name']} на работу {job_name}")

class FireNPCSelectView(View):
    def __init__(self, user_id: int, npcs: list):
        super().__init__(timeout=60)
        options = []
        for nid in npcs[:25]:
            npc = db.data["npcs"][nid]
            options.append(discord.SelectOption(label=npc['name'], value=nid))
        
        select = Select(placeholder="Выберите NPC для увольнения", options=options)
        select.callback = self.fire_callback
        self.add_item(select)
    
    async def fire_callback(self, interaction: discord.Interaction):
        npc_id = interaction.data["values"][0]
        npc = db.data["npcs"][npc_id]
        name = npc['name']
        
        del db.data["npcs"][npc_id]
        db.save()
        
        await interaction.response.send_message(f"✅ NPC **{name}** уволен!", ephemeral=True)
        print(f"🗑️ {interaction.user.name} уволил NPC {name}")

# ==================== МОДАЛЬНЫЕ ОКНА ====================
class CreateFactionModal(Modal, title="Создание фракции"):
    name = TextInput(label="Название фракции", placeholder="3-30 символов", max_length=30, min_length=3)
    max_players = TextInput(label="Максимум игроков", placeholder="5-100", default="20")
    base_channel = TextInput(label="ID канала базы", placeholder="Введите числовой ID текстового канала", required=True)
    currency = TextInput(label="Название валюты", placeholder="Например: монеты", default="монеты")
    flag = TextInput(label="Флаг (эмодзи)", placeholder="🏴", required=False, max_length=5)
    tax = TextInput(label="Налог %", placeholder="0-15", default="5")
    faction_type = TextInput(label="Тип фракции", placeholder="торговая/военная/строительная", default="торговая")
    color = TextInput(label="Цвет (HEX)", placeholder="#2b2d31", default="#2b2d31", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        
        if db.get_user_faction(user_id):
            await interaction.response.send_message("❌ Вы уже состоите во фракции!", ephemeral=True)
            return
        
        # Проверка существования канала
        try:
            channel_id = int(self.base_channel.value.strip())
            channel = interaction.guild.get_channel(channel_id)
            if not channel or not isinstance(channel, discord.TextChannel):
                await interaction.response.send_message("❌ Канал не найден! Укажите правильный ID текстового канала.", ephemeral=True)
                return
        except ValueError:
            await interaction.response.send_message("❌ Неверный ID канала! Введите числовой ID.", ephemeral=True)
            return
        
        fid, _ = db.get_faction_by_name(self.name.value)
        if fid:
            await interaction.response.send_message("❌ Фракция с таким названием уже существует!", ephemeral=True)
            return
        
        try:
            tax = int(self.tax.value)
            if tax < 0 or tax > 15:
                raise ValueError
        except:
            await interaction.response.send_message("❌ Налог должен быть числом от 0 до 15!", ephemeral=True)
            return
        
        try:
            max_players = int(self.max_players.value)
            if max_players < 5 or max_players > 100:
                raise ValueError
        except:
            await interaction.response.send_message("❌ Максимум игроков должен быть от 5 до 100!", ephemeral=True)
            return
        
        faction_type = self.faction_type.value.lower()
        if faction_type not in ["торговая", "военная", "строительная"]:
            faction_type = "торговая"
        
        faction_id = str(int(datetime.now().timestamp()))
        faction_data = {
            "name": self.name.value,
            "leader_id": user_id,
            "max_players": max_players,
            "base_channel": str(channel_id),
            "currency": self.currency.value,
            "flag": self.flag.value or "🏛️",
            "tax": tax,
            "type": faction_type,
            "color": self.color.value,
            "description": "Новая фракция",
            "created_at": datetime.now().isoformat(),
            "resources": {"gold": 100, "wood": 50, "ore": 50},
            "hierarchy": ["Новичок", "Боец", "Советник", "Лидер"]
        }
        
        db.data["factions"][faction_id] = faction_data
        db.update_user(user_id, faction_id=faction_id, rank="Лидер", joined_at=datetime.now().isoformat())
        db.save()
        
        embed = discord.Embed(
            title=f"✅ Фракция **{self.name.value}** создана!",
            description=f"Ты стал Лидером!\n💰 Валюта: {self.currency.value}\n📊 Налог: {tax}%\n🏛️ Тип: {faction_type}\n🏠 База: {channel.mention}",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        print(f"🏛️ {interaction.user.name} создал фракцию {self.name.value}")

class InvitePlayerModal(Modal, title="Пригласить игрока"):
    user_id = TextInput(label="ID пользователя", placeholder="Введите Discord ID", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        inviter = db.get_user(interaction.user.id)
        if not inviter["faction_id"]:
            await interaction.response.send_message("❌ Вы не состоите во фракции!", ephemeral=True)
            return
        
        faction = db.get_faction(inviter["faction_id"])
        members = db.get_faction_members(inviter["faction_id"])
        
        if len(members) >= faction["max_players"]:
            await interaction.response.send_message(f"❌ Фракция достигла лимита в {faction['max_players']} игроков!", ephemeral=True)
            return
        
        try:
            target_user = await interaction.client.fetch_user(int(self.user_id.value))
        except:
            await interaction.response.send_message("❌ Пользователь не найден! Проверьте ID.", ephemeral=True)
            return
        
        target_data = db.get_user(target_user.id)
        if target_data["faction_id"]:
            await interaction.response.send_message("❌ Этот игрок уже состоит во фракции!", ephemeral=True)
            return
        
        view = InviteConfirmView(inviter["faction_id"], interaction.user.id)
        embed = discord.Embed(
            title=f"📢 Приглашение во фракцию {faction['name']}",
            description=f"Игрок {interaction.user.mention} приглашает тебя!\nНажми ✅ чтобы принять.",
            color=discord.Color.blue()
        )
        
        try:
            await target_user.send(embed=embed, view=view)
            await interaction.response.send_message(f"✅ Приглашение отправлено {target_user.mention}!", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(f"❌ Не могу отправить сообщение {target_user.mention}! У него закрыты ЛС.", ephemeral=True)

class InviteConfirmView(View):
    def __init__(self, faction_id: str, inviter_id: int):
        super().__init__(timeout=120)
        self.faction_id = faction_id
        self.inviter_id = inviter_id

    @discord.ui.button(label="✅ Принять", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: Button):
        faction = db.get_faction(self.faction_id)
        if not faction:
            await interaction.response.send_message("❌ Фракция больше не существует!", ephemeral=True)
            return
        
        members = db.get_faction_members(self.faction_id)
        if len(members) >= faction["max_players"]:
            await interaction.response.send_message(f"❌ Фракция достигла лимита!", ephemeral=True)
            return
        
        db.update_user(interaction.user.id, faction_id=self.faction_id, rank="Новичок", joined_at=datetime.now().isoformat())
        await interaction.response.send_message(f"✅ Вы вступили во фракцию **{faction['name']}**!", ephemeral=True)

    @discord.ui.button(label="❌ Отклонить", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("❌ Вы отклонили приглашение.", ephemeral=True)

class ChangeRankModal(Modal, title="Изменить ступень"):
    user_id = TextInput(label="ID пользователя", placeholder="Discord ID", required=True)
    new_rank = TextInput(label="Новая ступень", placeholder="Новичок/Боец/Советник/Лидер", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        if not db.is_faction_leader(interaction.user.id):
            await interaction.response.send_message("❌ Только лидер может менять ступени!", ephemeral=True)
            return
        
        target = db.get_user(self.user_id.value)
        if not target["faction_id"]:
            await interaction.response.send_message("❌ Игрок не состоит во фракции!", ephemeral=True)
            return
        
        faction = db.get_faction(target["faction_id"])
        if faction["leader_id"] != str(interaction.user.id):
            await interaction.response.send_message("❌ Это не ваш подчинённый!", ephemeral=True)
            return
        
        if self.new_rank.value not in faction["hierarchy"]:
            await interaction.response.send_message(f"❌ Ступень '{self.new_rank.value}' не найдена в иерархии!", ephemeral=True)
            return
        
        db.update_user(self.user_id.value, rank=self.new_rank.value)
        await interaction.response.send_message(f"✅ Игроку <@{self.user_id.value}> назначена ступень **{self.new_rank.value}**", ephemeral=True)

class ChangeTaxModal(Modal, title="Изменить налоги"):
    new_tax = TextInput(label="Новый налог %", placeholder="0-15", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        if not db.is_faction_leader(interaction.user.id):
            await interaction.response.send_message("❌ Только лидер может менять налоги!", ephemeral=True)
            return
        
        try:
            tax = int(self.new_tax.value)
            if tax < 0 or tax > 15:
                raise ValueError
        except:
            await interaction.response.send_message("❌ Налог должен быть числом от 0 до 15!", ephemeral=True)
            return
        
        user = db.get_user(interaction.user.id)
        faction = db.get_faction(user["faction_id"])
        faction["tax"] = tax
        db.save()
        
        await interaction.response.send_message(f"✅ Налог фракции изменён на **{tax}%**", ephemeral=True)

class TransferLeadershipModal(Modal, title="Передать лидерство"):
    new_leader_id = TextInput(label="ID нового лидера", placeholder="Discord ID", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        if not db.is_faction_leader(interaction.user.id):
            await interaction.response.send_message("❌ Только лидер может передать лидерство!", ephemeral=True)
            return
        
        user = db.get_user(interaction.user.id)
        faction = db.get_faction(user["faction_id"])
        
        target = db.get_user(self.new_leader_id.value)
        if target["faction_id"] != user["faction_id"]:
            await interaction.response.send_message("❌ Игрок не состоит в вашей фракции!", ephemeral=True)
            return
        
        faction["leader_id"] = self.new_leader_id.value
        db.update_user(interaction.user.id, rank="Советник")
        db.update_user(self.new_leader_id.value, rank="Лидер")
        db.save()
        
        await interaction.response.send_message(f"✅ Лидерство передано <@{self.new_leader_id.value}>!", ephemeral=True)

# ==================== АДМИН-ПАНЕЛЬ ====================
class AdminPanelView(View):
    def __init__(self):
        super().__init__(timeout=120)
    
    @discord.ui.button(label="📋 Список фракций", style=discord.ButtonStyle.secondary, row=0)
    async def list_factions(self, interaction: discord.Interaction, button: Button):
        if not db.data["factions"]:
            await interaction.response.send_message("📭 Нет созданных фракций", ephemeral=True)
            return
        
        description = ""
        for fid, data in db.data["factions"].items():
            members = db.get_faction_members(fid)
            npcs = db.get_faction_npcs(fid)
            description += f"**{data['name']}** — лидер: <@{data['leader_id']}>, игроков: {len(members)}, NPC: {len(npcs)}, налог: {data['tax']}%\n"
            if len(description) > 3900:
                description += "..."
                break
        
        embed = discord.Embed(title="📋 Все фракции", description=description[:4000], color=discord.Color.blue())
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="👥 Список игроков", style=discord.ButtonStyle.secondary, row=0)
    async def list_players(self, interaction: discord.Interaction, button: Button):
        if not db.data["users"]:
            await interaction.response.send_message("📭 Нет зарегистрированных игроков", ephemeral=True)
            return
        
        description = ""
        for uid, data in db.data["users"].items():
            faction = db.get_faction(data["faction_id"]) if data["faction_id"] else None
            fname = faction["name"] if faction else "Нет"
            description += f"<@{uid}> — {fname}, реп: {data['reputation']}, ступень: {data['rank']}\n"
            if len(description) > 3900:
                description += "..."
                break
        
        embed = discord.Embed(title="👥 Все игроки", description=description[:4000], color=discord.Color.green())
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="🗑️ Удалить фракцию", style=discord.ButtonStyle.danger, row=1)
    async def delete_faction(self, interaction: discord.Interaction, button: Button):
        if not db.data["factions"]:
            await interaction.response.send_message("📭 Нет фракций для удаления", ephemeral=True)
            return
        
        view = DeleteFactionSelectView()
        await interaction.response.send_message("Выберите фракцию для удаления:", view=view, ephemeral=True)
    
    @discord.ui.button(label="⭐ Изменить репутацию", style=discord.ButtonStyle.primary, row=1)
    async def change_reputation(self, interaction: discord.Interaction, button: Button):
        modal = AdminReputationModal()
        await interaction.response.send_modal(modal)

class DeleteFactionSelectView(View):
    def __init__(self):
        super().__init__(timeout=60)
        options = [discord.SelectOption(label=data["name"], value=fid) for fid, data in db.data["factions"].items()]
        select = Select(placeholder="Выберите фракцию", options=options[:25])
        select.callback = self.delete_callback
        self.add_item(select)
    
    async def delete_callback(self, interaction: discord.Interaction):
        faction_id = interaction.data["values"][0]
        faction = db.get_faction(faction_id)
        
        members = db.get_faction_members(faction_id)
        for uid in members:
            db.update_user(uid, faction_id=None, reputation=0, rank="Новичок", joined_at=None)
        
        npcs = db.get_faction_npcs(faction_id)
        for nid in npcs:
            if nid in db.data["npcs"]:
                del db.data["npcs"][nid]
        
        del db.data["factions"][faction_id]
        db.save()
        
        await interaction.response.send_message(f"✅ Фракция **{faction['name']}** удалена!", ephemeral=True)

class AdminReputationModal(Modal, title="Изменить репутацию"):
    user_id = TextInput(label="ID пользователя", placeholder="Discord ID", required=True)
    amount = TextInput(label="Количество", placeholder="Положительное или отрицательное число", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.amount.value)
            user = db.get_user(self.user_id.value)
            new_rep = user["reputation"] + amount
            db.update_user(self.user_id.value, reputation=new_rep)
            await interaction.response.send_message(f"✅ Репутация <@{self.user_id.value}> изменена на {new_rep}", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Количество должно быть числом!", ephemeral=True)

# ==================== КОМАНДЫ БОТА ====================
class FactionBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        print("✅ Команды синхронизированы")
        # Запускаем фоновую задачу ПОСЛЕ создания бота
        asyncio.create_task(self.check_npc_work_background())

    async def check_npc_work_background(self):
        """Фоновая задача для проверки завершения работ NPC"""
        await self.wait_until_ready()
        while not self.is_closed():
            completed = db.check_completed_works()
            for npc_id, reward in completed:
                npc = db.data["npcs"].get(npc_id)
                if npc:
                    faction = db.get_faction(npc["faction_id"])
                    if faction:
                        resources = faction.get("resources", {"gold": 0, "wood": 0, "ore": 0})
                        resources["gold"] = resources.get("gold", 0) + reward.get("gold", 0)
                        resources["wood"] = resources.get("wood", 0) + reward.get("wood", 0)
                        resources["ore"] = resources.get("ore", 0) + reward.get("ore", 0)
                        faction["resources"] = resources
                        db.save()
                        
                        # Отправка уведомления в канал фракции
                        try:
                            channel_id = int(faction["base_channel"])
                            channel = self.get_channel(channel_id)
                            if channel:
                                await channel.send(f"✅ {npc['name']} завершил работу и принёс ресурсы: {reward}")
                        except:
                            pass  # Если канал не найден, просто игнорируем
            await asyncio.sleep(60)

bot = FactionBot()

@bot.event
async def on_ready():
    print(f"✅ Бот {bot.user} запущен!")
    print(f"📡 На серверах: {len(bot.guilds)}")

@bot.tree.command(name="меню", description="Главное меню")
async def menu_command(interaction: discord.Interaction):
    embed = discord.Embed(title="🎮 ГЛАВНОЕ МЕНЮ", description="Выберите действие:", color=discord.Color.blue())
    view = MainMenuView(interaction.user.id)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

@bot.tree.command(name="игрок", description="Просмотр статистики игрока")
@app_commands.describe(пользователь="Пользователь для просмотра")
async def player_command(interaction: discord.Interaction, пользователь: Optional[discord.User] = None):
    target = пользователь or interaction.user
    await show_player_stats(interaction, target)

@bot.tree.command(name="фракция", description="Просмотр информации о фракции")
@app_commands.describe(пользователь="Пользователь, чью фракцию посмотреть")
async def faction_command(interaction: discord.Interaction, пользователь: Optional[discord.User] = None):
    target = пользователь or interaction.user
    await show_faction_menu(interaction, target)

@bot.tree.command(name="создать", description="Создать свою фракцию")
async def create_faction_command(interaction: discord.Interaction):
    if db.get_user_faction(interaction.user.id):
        await interaction.response.send_message("❌ Вы уже состоите во фракции!", ephemeral=True)
        return
    
    modal = CreateFactionModal()
    await interaction.response.send_modal(modal)

@bot.tree.command(name="вступить", description="Вступить во фракцию")
@app_commands.describe(название="Название фракции")
async def join_command(interaction: discord.Interaction, название: str):
    user_data = db.get_user(interaction.user.id)
    
    if user_data["faction_id"]:
        await interaction.response.send_message("❌ Вы уже состоите во фракции!", ephemeral=True)
        return
    
    fid, faction = db.get_faction_by_name(название)
    if not fid:
        await interaction.response.send_message(f"❌ Фракция '{название}' не найдена!", ephemeral=True)
        return
    
    members = db.get_faction_members(fid)
    if len(members) >= faction["max_players"]:
        await interaction.response.send_message(f"❌ Фракция достигла лимита в {faction['max_players']} игроков!", ephemeral=True)
        return
    
    db.update_user(interaction.user.id, faction_id=fid, rank="Новичок", joined_at=datetime.now().isoformat())
    await interaction.response.send_message(f"✅ Вы вступили во фракцию **{faction['name']}**!", ephemeral=True)

@bot.tree.command(name="выйти", description="Выйти из фракции")
async def leave_command(interaction: discord.Interaction):
    user_data = db.get_user(interaction.user.id)
    
    if not user_data["faction_id"]:
        await interaction.response.send_message("❌ Вы не состоите во фракции!", ephemeral=True)
        return
    
    if db.is_faction_leader(interaction.user.id):
        await interaction.response.send_message("❌ Лидер не может выйти! Используйте /передать_лидерство или /распустить", ephemeral=True)
        return
    
    faction = db.get_faction(user_data["faction_id"])
    db.update_user(interaction.user.id, faction_id=None, reputation=0, rank="Новичок", joined_at=None)
    await interaction.response.send_message(f"✅ Вы вышли из фракции **{faction['name']}**", ephemeral=True)

@bot.tree.command(name="распустить", description="Распустить свою фракцию (только лидер)")
async def disband_command(interaction: discord.Interaction):
    if not db.is_faction_leader(interaction.user.id):
        await interaction.response.send_message("❌ Только лидер может распустить фракцию!", ephemeral=True)
        return
    
    user = db.get_user(interaction.user.id)
    faction = db.get_faction(user["faction_id"])
    
    members = db.get_faction_members(user["faction_id"])
    for uid in members:
        db.update_user(uid, faction_id=None, reputation=0, rank="Новичок", joined_at=None)
    
    npcs = db.get_faction_npcs(user["faction_id"])
    for nid in npcs:
        if nid in db.data["npcs"]:
            del db.data["npcs"][nid]
    
    del db.data["factions"][user["faction_id"]]
    db.save()
    
    await interaction.response.send_message(f"✅ Фракция **{faction['name']}** распущена!", ephemeral=True)

@bot.tree.command(name="передать_лидерство", description="Передать лидерство другому игроку")
async def transfer_leader_command(interaction: discord.Interaction, новый_лидер: discord.User):
    if not db.is_faction_leader(interaction.user.id):
        await interaction.response.send_message("❌ Только лидер может передать лидерство!", ephemeral=True)
        return
    
    user = db.get_user(interaction.user.id)
    faction = db.get_faction(user["faction_id"])
    
    target = db.get_user(новый_лидер.id)
    if target["faction_id"] != user["faction_id"]:
        await interaction.response.send_message("❌ Игрок не состоит в вашей фракции!", ephemeral=True)
        return
    
    faction["leader_id"] = str(новый_лидер.id)
    db.update_user(interaction.user.id, rank="Советник")
    db.update_user(новый_лидер.id, rank="Лидер")
    db.save()
    
    await interaction.response.send_message(f"✅ Лидерство передано {новый_лидер.mention}!", ephemeral=True)

@bot.tree.command(name="админ", description="Админ-панель")
async def admin_command(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ У вас нет доступа!", ephemeral=True)
        return
    
    view = AdminPanelView()
    embed = discord.Embed(title="🛠️ АДМИН-ПАНЕЛЬ", description="Управление фракциями", color=discord.Color.red())
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# ==================== ЗАПУСК ====================
async def main():
    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
