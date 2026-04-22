import discord
from discord import app_commands
from discord.ui import Button, View, Modal, TextInput, Select
import json
import os
import asyncio
import random
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
            "npcs": {},
            "deposits": {}
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
                "joined_at": None,
                "deposits": []
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
            "created_at": datetime.now().isoformat(),
            "assigned_deposit": None
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
    
    def add_deposit(self, user_id: str, deposit_type: str, amount: int):
        deposit_id = str(int(datetime.now().timestamp() * 1000))
        self.data["deposits"][deposit_id] = {
            "owner_id": str(user_id),
            "type": deposit_type,
            "amount": amount,
            "assigned_npcs": [],
            "discovered_at": datetime.now().isoformat(),
            "is_active": True
        }
        
        user = self.get_user(user_id)
        if "deposits" not in user:
            user["deposits"] = []
        user["deposits"].append(deposit_id)
        self.save()
        return deposit_id
    
    def get_user_deposits(self, user_id: str) -> list:
        user = self.get_user(user_id)
        deposits = []
        for dep_id in user.get("deposits", []):
            if dep_id in self.data["deposits"] and self.data["deposits"][dep_id].get("is_active", True):
                deposits.append((dep_id, self.data["deposits"][dep_id]))
        return deposits
    
    def check_completed_works(self):
        completed = []
        now = datetime.now()
        for nid, npc in self.data["npcs"].items():
            if npc.get("is_working") and npc.get("work_end_time") and not npc.get("assigned_deposit"):
                end_time = datetime.fromisoformat(npc["work_end_time"])
                if now >= end_time:
                    npc["is_working"] = False
                    reward = npc.get("work_reward", {"gold": 10, "wood": 5, "stone": 2})
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
    user_data = db.get_user(target_user.id)
    faction = db.get_user_faction(target_user.id)
    
    embed = discord.Embed(
        title=f"📊 ИГРОК: {target_user.display_name}",
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
        deposits = db.get_user_deposits(target_user.id)
        embed.add_field(name="⛏️ Залежей найдено", value=str(len(deposits)), inline=True)
    else:
        embed.description = "```\n🚫 Не состоит ни в одной фракции\n```"
    
    await interaction.response.send_message(embed=embed, ephemeral=False)

async def show_faction_members(interaction: discord.Interaction, faction_id: str):
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
        deposit_info = f" [⛏️ Залежа]" if npc.get("assigned_deposit") else ""
        description += f"**{npc['name']}** — {work_status}{work_info}{deposit_info}, лояльность: {npc.get('loyalty', 50)}%\n"
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
    faction = db.get_faction(faction_id)
    members = db.get_faction_members(faction_id)
    npcs = db.get_faction_npcs(faction_id)
    
    embed = discord.Embed(
        title=f"💰 Экономика {faction['name']}",
        color=discord.Color.gold()
    )
    
    resources = faction.get("resources", {"gold": 0, "wood": 0, "stone": 0})
    
    embed.add_field(name="👥 Игроки", value=str(len(members)), inline=True)
    embed.add_field(name="🤖 NPC", value=str(len(npcs)), inline=True)
    embed.add_field(name="📊 Налог", value=f"{faction['tax']}%", inline=True)
    embed.add_field(name="💰 Золото", value=resources.get("gold", 0), inline=True)
    embed.add_field(name="🪵 Древесина", value=resources.get("wood", 0), inline=True)
    embed.add_field(name="🪨 Камень", value=resources.get("stone", 0), inline=True)
    
    total_resources = resources.get("wood", 0) + resources.get("stone", 0)
    embed.add_field(name="📦 Всего ресурсов", value=str(total_resources), inline=True)
    
    power = len(members) * 10 + len(npcs) * 5 + (resources.get("gold", 0) // 100)
    embed.add_field(name="⚔️ Сила фракции", value=str(power), inline=True)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

async def show_faction_menu(interaction: discord.Interaction, target_user: discord.User):
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
    
    resources = faction.get("resources", {"wood": 0, "stone": 0})
    
    embed.add_field(name="👑 Лидер", value=f"<@{faction['leader_id']}>", inline=True)
    embed.add_field(name="📊 Тип", value=faction.get("type", "торговая").capitalize(), inline=True)
    embed.add_field(name="💰 Налог", value=f"{faction['tax']}%", inline=True)
    embed.add_field(name="👥 Игроков", value=str(len(members)), inline=True)
    embed.add_field(name="🤖 NPC", value=str(len(npcs)), inline=True)
    embed.add_field(name="🪵 Древесина", value=resources.get("wood", 0), inline=True)
    embed.add_field(name="🪨 Камень", value=resources.get("stone", 0), inline=True)
    embed.add_field(name="💎 Валюта", value=faction["currency"], inline=True)
    embed.add_field(name="🏠 База", value=f"<#{faction['base_channel']}>", inline=True)
    embed.add_field(name="📜 Иерархия", value=" → ".join(faction["hierarchy"]), inline=False)
    
    if faction.get("description"):
        embed.add_field(name="📝 Описание", value=faction["description"][:1024], inline=False)
    
    if interaction.user.id == target_user.id:
        view = FactionMenuView(interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=False)
    else:
        await interaction.response.send_message(embed=embed, ephemeral=False)

async def show_deposits_list(interaction: discord.Interaction, target_user: discord.User):
    deposits = db.get_user_deposits(target_user.id)
    
    if not deposits:
        embed = discord.Embed(
            title="⛏️ ВАШИ ЗАЛЕЖИ",
            description="```\n🚫 У вас нет найденных залежей\nИспользуйте /найти [камень/дерево]\n```",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    description = ""
    deposit_list = []
    for dep_id, deposit in deposits:
        resource_icon = "🪵" if deposit["type"] == "дерево" else "🪨"
        assigned_npcs = len(deposit.get("assigned_npcs", []))
        description += f"{resource_icon} **{deposit['type'].capitalize()}** — осталось: {deposit['amount']}, 👷 рабочих: {assigned_npcs}/5\n"
        deposit_list.append((dep_id, deposit))
    
    embed = discord.Embed(
        title="⛏️ ВАШИ ЗАЛЕЖИ",
        description=description[:4000],
        color=discord.Color.blue()
    )
    
    view = DepositsView(target_user.id, deposit_list)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# ==================== КНОПКИ И МЕНЮ ====================
class DepositsView(View):
    def __init__(self, user_id: int, deposits: list):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.deposits = deposits
        
        if deposits:
            options = []
            for dep_id, deposit in deposits[:25]:
                icon = "🪵" if deposit["type"] == "дерево" else "🪨"
                options.append(discord.SelectOption(
                    label=f"{icon} {deposit['type'].capitalize()}", 
                    value=dep_id,
                    description=f"Осталось: {deposit['amount']}"
                ))
            
            select = Select(placeholder="Выберите залежу для управления", options=options)
            select.callback = self.deposit_selected
            self.add_item(select)
    
    async def deposit_selected(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это не ваши залежи!", ephemeral=True)
            return
        
        deposit_id = interaction.data["values"][0]
        deposit = db.data["deposits"].get(deposit_id)
        
        if not deposit or not deposit.get("is_active", True):
            await interaction.response.send_message("❌ Эта залежа уже истощена!", ephemeral=True)
            return
        
        view = DepositManageView(self.user_id, deposit_id, deposit)
        embed = discord.Embed(
            title=f"⛏️ Управление залежью: {deposit['type'].capitalize()}",
            description=f"📦 Осталось ресурсов: {deposit['amount']}\n👷 Рабочих NPC: {len(deposit.get('assigned_npcs', []))}/5\n\nВыберите действие:",
            color=discord.Color.gold()
        )
        await interaction.response.edit_message(embed=embed, view=view)

class DepositManageView(View):
    def __init__(self, user_id: int, deposit_id: str, deposit: dict):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.deposit_id = deposit_id
        self.deposit = deposit
    
    @discord.ui.button(label="👷 Назначить NPC", style=discord.ButtonStyle.primary)
    async def assign_npc(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это не ваша залежа!", ephemeral=True)
            return
        
        user = db.get_user(self.user_id)
        if not user["faction_id"]:
            await interaction.response.send_message("❌ Вы не состоите во фракции!", ephemeral=True)
            return
        
        faction_npcs = db.get_faction_npcs(user["faction_id"])
        free_npcs = []
        for nid in faction_npcs:
            npc = db.data["npcs"][nid]
            if not npc.get("is_working") and not npc.get("assigned_deposit"):
                free_npcs.append(nid)
        
        if not free_npcs:
            await interaction.response.send_message("❌ Нет свободных NPC для работы!", ephemeral=True)
            return
        
        current_assigned = len(self.deposit.get("assigned_npcs", []))
        if current_assigned >= 5:
            await interaction.response.send_message("❌ На этой залеже уже работает максимальное количество NPC (5)!", ephemeral=True)
            return
        
        view = AssignNPCToDepositView(self.user_id, self.deposit_id, free_npcs)
        await interaction.response.send_message("Выберите NPC для работы на залеже:", view=view, ephemeral=True)
    
    @discord.ui.button(label="📊 Статистика", style=discord.ButtonStyle.secondary)
    async def stats(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это не ваша залежа!", ephemeral=True)
            return
        
        assigned = self.deposit.get("assigned_npcs", [])
        production_per_hour = len(assigned) * 50
        
        embed = discord.Embed(
            title=f"📊 Статистика залежи {self.deposit['type'].capitalize()}",
            color=discord.Color.blue()
        )
        embed.add_field(name="📦 Остаток ресурсов", value=self.deposit['amount'], inline=True)
        embed.add_field(name="👷 Рабочих NPC", value=f"{len(assigned)}/5", inline=True)
        embed.add_field(name="⚙️ Добыча в час", value=f"{production_per_hour} ед.", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class AssignNPCToDepositView(View):
    def __init__(self, user_id: int, deposit_id: str, npc_ids: list):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.deposit_id = deposit_id
        
        options = []
        for nid in npc_ids[:25]:
            npc = db.data["npcs"][nid]
            options.append(discord.SelectOption(label=npc['name'], value=nid))
        
        select = Select(placeholder="Выберите NPC для работы", options=options)
        select.callback = self.npc_selected
        self.add_item(select)
    
    async def npc_selected(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это не ваше меню!", ephemeral=True)
            return
        
        npc_id = interaction.data["values"][0]
        npc = db.data["npcs"][npc_id]
        deposit = db.data["deposits"].get(self.deposit_id)
        
        if not deposit or not deposit.get("is_active", True):
            await interaction.response.send_message("❌ Залежа уже истощена!", ephemeral=True)
            return
        
        if len(deposit.get("assigned_npcs", [])) >= 5:
            await interaction.response.send_message("❌ Максимум NPC на залеже достигнут!", ephemeral=True)
            return
        
        if "assigned_npcs" not in deposit:
            deposit["assigned_npcs"] = []
        
        deposit["assigned_npcs"].append(npc_id)
        npc["assigned_deposit"] = self.deposit_id
        npc["is_working"] = True
        npc["work_end_time"] = (datetime.now() + timedelta(hours=1)).isoformat()
        db.save()
        
        await interaction.response.send_message(f"✅ {npc['name']} назначен на работу на залежу! Он будет приносить 50 ресурсов в час.", ephemeral=True)

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
            await interaction.response.send_message("❌ Лидер не может выйти! Используйте /передать_лидерство", ephemeral=True)
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
            "⛏️ Шахтёр": {"hours": 2, "reward": {"stone": 8}},
            "💰 Сборщик налогов": {"hours": 3, "reward": {"gold": 15}},
            "🏛️ Строитель": {"hours": 4, "reward": {"wood": 5, "stone": 5}}
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
        
        await interaction.response.send_message(f"✅ NPC **{name}** уволен!", ephemeral=True)# ==================== МОДАЛЬНЫЕ ОКНА ====================
class CreateFactionModal(Modal, title="Создание фракции"):
    name = TextInput(label="Название фракции", placeholder="3-30 символов", max_length=30, min_length=3)
    max_players = TextInput(label="Максимум игроков", placeholder="5-100", default="20")
    base_channel = TextInput(label="Название канала базы", placeholder="название-канала", required=True)
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
        
        channel_name = self.base_channel.value.strip().lstrip('#')
        channel = None
        for ch in interaction.guild.text_channels:
            if ch.name == channel_name:
                channel = ch
                break
        
        if not channel:
            await interaction.response.send_message(f"❌ Канал #{channel_name} не найден на сервере!", ephemeral=True)
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
            "base_channel": str(channel.id),
            "currency": self.currency.value,
            "flag": self.flag.value or "🏛️",
            "tax": tax,
            "type": faction_type,
            "color": self.color.value,
            "description": "Новая фракция",
            "created_at": datetime.now().isoformat(),
            "resources": {"gold": 100, "wood": 50, "stone": 50},
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
        
        db.add_npc(user["faction_id"], self.name.value, None, loyalty, skill)
        
        await interaction.response.send_message(f"✅ NPC **{self.name.value}** нанят за {hire_cost} {faction['currency']}!\nЛояльность: {loyalty}, Навык: {skill}", ephemeral=True)

class InvitePlayerModal(Modal, title="Пригласить игрока"):
    user_mention = TextInput(label="Упоминание игрока", placeholder="@Игрок или никнейм", required=True)

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
        
        target = None
        mention = self.user_mention.value.strip()
        
        if mention.startswith('<@') and mention.endswith('>'):
            user_id = mention.strip('<@!>')
            try:
                target = await interaction.client.fetch_user(int(user_id))
            except:
                pass
        
        if not target:
            for member in interaction.guild.members:
                if member.name.lower() == mention.lower() or member.display_name.lower() == mention.lower():
                    target = member
                    break
        
        if not target:
            await interaction.response.send_message("❌ Пользователь не найден! Укажите @упоминание или никнейм.", ephemeral=True)
            return
        
        target_data = db.get_user(target.id)
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
            await target.send(embed=embed, view=view)
            await interaction.response.send_message(f"✅ Приглашение отправлено {target.mention}!", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(f"❌ Не могу отправить сообщение {target.mention}! У него закрыты ЛС.", ephemeral=True)

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
    user_mention = TextInput(label="Игрок", placeholder="@Игрок или никнейм", required=True)
    new_rank = TextInput(label="Новая ступень", placeholder="Новичок/Боец/Советник/Лидер", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        if not db.is_faction_leader(interaction.user.id):
            await interaction.response.send_message("❌ Только лидер может менять ступени!", ephemeral=True)
            return
        
        target = None
        mention = self.user_mention.value.strip()
        
        if mention.startswith('<@') and mention.endswith('>'):
            user_id = mention.strip('<@!>')
            try:
                target = await interaction.client.fetch_user(int(user_id))
            except:
                pass
        
        if not target:
            for member in interaction.guild.members:
                if member.name.lower() == mention.lower() or member.display_name.lower() == mention.lower():
                    target = member
                    break
        
        if not target:
            await interaction.response.send_message("❌ Пользователь не найден!", ephemeral=True)
            return
        
        target_data = db.get_user(target.id)
        if not target_data["faction_id"]:
            await interaction.response.send_message("❌ Игрок не состоит во фракции!", ephemeral=True)
            return
        
        faction = db.get_faction(target_data["faction_id"])
        if faction["leader_id"] != str(interaction.user.id):
            await interaction.response.send_message("❌ Это не ваш подчинённый!", ephemeral=True)
            return
        
        if self.new_rank.value not in faction["hierarchy"]:
            await interaction.response.send_message(f"❌ Ступень '{self.new_rank.value}' не найдена в иерархии!", ephemeral=True)
            return
        
        db.update_user(target.id, rank=self.new_rank.value)
        await interaction.response.send_message(f"✅ Игроку {target.mention} назначена ступень **{self.new_rank.value}**", ephemeral=True)

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
    new_leader = TextInput(label="Новый лидер", placeholder="@Игрок или никнейм", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        if not db.is_faction_leader(interaction.user.id):
            await interaction.response.send_message("❌ Только лидер может передать лидерство!", ephemeral=True)
            return
        
        target = None
        mention = self.new_leader.value.strip()
        
        if mention.startswith('<@') and mention.endswith('>'):
            user_id = mention.strip('<@!>')
            try:
                target = await interaction.client.fetch_user(int(user_id))
            except:
                pass
        
        if not target:
            for member in interaction.guild.members:
                if member.name.lower() == mention.lower() or member.display_name.lower() == mention.lower():
                    target = member
                    break
        
        if not target:
            await interaction.response.send_message("❌ Пользователь не найден!", ephemeral=True)
            return
        
        user = db.get_user(interaction.user.id)
        faction = db.get_faction(user["faction_id"])
        
        target_data = db.get_user(target.id)
        if target_data["faction_id"] != user["faction_id"]:
            await interaction.response.send_message("❌ Игрок не состоит в вашей фракции!", ephemeral=True)
            return
        
        faction["leader_id"] = str(target.id)
        db.update_user(interaction.user.id, rank="Советник")
        db.update_user(target.id, rank="Лидер")
        db.save()
        
        await interaction.response.send_message(f"✅ Лидерство передано {target.mention}!", ephemeral=True)

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
    user_mention = TextInput(label="Игрок", placeholder="@Игрок или никнейм", required=True)
    amount = TextInput(label="Количество", placeholder="Положительное или отрицательное число", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.amount.value)
            
            target = None
            mention = self.user_mention.value.strip()
            
            if mention.startswith('<@') and mention.endswith('>'):
                user_id = mention.strip('<@!>')
                try:
                    target = await interaction.client.fetch_user(int(user_id))
                except:
                    pass
            
            if not target:
                for member in interaction.guild.members:
                    if member.name.lower() == mention.lower() or member.display_name.lower() == mention.lower():
                        target = member
                        break
            
            if not target:
                await interaction.response.send_message("❌ Пользователь не найден!", ephemeral=True)
                return
            
            user = db.get_user(target.id)
            new_rep = user["reputation"] + amount
            db.update_user(target.id, reputation=new_rep)
            await interaction.response.send_message(f"✅ Репутация {target.mention} изменена на {new_rep}", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Количество должно быть числом!", ephemeral=True)

# ==================== ФОНОВЫЕ ЗАДАЧИ ====================
async def deposit_harvesting_background(bot_instance):
    await bot_instance.wait_until_ready()
    while not bot_instance.is_closed():
        for dep_id, deposit in list(db.data["deposits"].items()):
            if not deposit.get("is_active", True):
                continue
            
            assigned_npcs = deposit.get("assigned_npcs", [])
            if assigned_npcs:
                harvested = len(assigned_npcs) * 50
                deposit["amount"] -= harvested
                
                owner_id = deposit["owner_id"]
                user = db.get_user(owner_id)
                if user["faction_id"]:
                    faction = db.get_faction(user["faction_id"])
                    if faction:
                        resources = faction.get("resources", {"wood": 0, "stone": 0})
                        resource_key = "wood" if deposit["type"] == "дерево" else "stone"
                        resources[resource_key] = resources.get(resource_key, 0) + harvested
                        faction["resources"] = resources
                
                if deposit["amount"] <= 0:
                    deposit["is_active"] = False
        
        db.save()
        
        now = datetime.now()
        for nid, npc in db.data["npcs"].items():
            if npc.get("assigned_deposit") and npc.get("work_end_time"):
                end_time = datetime.fromisoformat(npc["work_end_time"])
                if now >= end_time:
                    npc["is_working"] = False
                    npc["assigned_deposit"] = None
                    npc["work_end_time"] = None
        
        db.save()
        await asyncio.sleep(3600)

async def complete_deposit_search(bot_instance, user_id: int, resource_type: str, npc_ids: list):
    await asyncio.sleep(3600)
    
    for nid in npc_ids:
        npc = db.data["npcs"].get(nid)
        if npc:
            npc["is_working"] = False
            npc["job"] = None
            npc["work_end_time"] = None
    
    if random.random() < 0.3:
        amount = random.randint(50, 300)
        if random.random() < 0.2:
            amount = random.randint(500, 1000)
        
        db.add_deposit(user_id, resource_type, amount)
        
        user = await bot_instance.fetch_user(user_id)
        if user:
            embed = discord.Embed(
                title="✅ ПОИСК ЗАВЕРШЁН!",
                description=f"Твои NPC нашли залежь **{resource_type}**!\n📦 Количество ресурсов: {amount}\nИспользуй `/залежи` чтобы управлять.",
                color=discord.Color.green()
            )
            await user.send(embed=embed)
    else:
        user = await bot_instance.fetch_user(user_id)
        if user:
            embed = discord.Embed(
                title="❌ ПОИСК ЗАВЕРШЁН",
                description=f"К сожалению, NPC не нашли залежей {resource_type}. Попробуй снова!",
                color=discord.Color.red()
            )
            await user.send(embed=embed)
    
    db.save()

# ==================== КОМАНДЫ БОТА ====================
class FactionBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        print("✅ Команды синхронизированы")
        asyncio.create_task(self.check_npc_work_background())
        asyncio.create_task(deposit_harvesting_background(self))

    async def check_npc_work_background(self):
        await self.wait_until_ready()
        while not self.is_closed():
            completed = db.check_completed_works()
            for npc_id, reward in completed:
                npc = db.data["npcs"].get(npc_id)
                if npc:
                    faction = db.get_faction(npc["faction_id"])
                    if faction:
                        resources = faction.get("resources", {"gold": 0, "wood": 0, "stone": 0})
                        resources["gold"] = resources.get("gold", 0) + reward.get("gold", 0)
                        resources["wood"] = resources.get("wood", 0) + reward.get("wood", 0)
                        resources["stone"] = resources.get("stone", 0) + reward.get("stone", 0)
                        faction["resources"] = resources
                        db.save()
                        
                        try:
                            channel_id = int(faction["base_channel"])
                            channel = self.get_channel(channel_id)
                            if channel:
                                await channel.send(f"✅ {npc['name']} завершил работу и принёс ресурсы: {reward}")
                        except:
                            pass
            await asyncio.sleep(60)

bot = FactionBot()

# ==================== КОМАНДЫ ====================
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

@bot.tree.command(name="найти", description="Найти залежи ресурсов (требует 3 NPC и 1 час)")
@app_commands.describe(тип="Тип ресурса: дерево или камень")
async def find_deposit_command(interaction: discord.Interaction, тип: str):
    user = db.get_user(interaction.user.id)
    
    if not user["faction_id"]:
        await interaction.response.send_message("❌ Вы не состоите во фракции!", ephemeral=True)
        return
    
    тип = тип.lower()
    if тип not in ["дерево", "камень"]:
        await interaction.response.send_message("❌ Тип должен быть 'дерево' или 'камень'!", ephemeral=True)
        return
    
    faction_npcs = db.get_faction_npcs(user["faction_id"])
    free_npcs = []
    for nid in faction_npcs:
        npc = db.data["npcs"][nid]
        if not npc.get("is_working") and not npc.get("assigned_deposit"):
            free_npcs.append(nid)
    
    if len(free_npcs) < 3:
        await interaction.response.send_message(f"❌ Недостаточно свободных NPC! Нужно 3, есть {len(free_npcs)}", ephemeral=True)
        return
    
    for nid in free_npcs[:3]:
        npc = db.data["npcs"][nid]
        npc["is_working"] = True
        npc["job"] = f"Поиск {тип}"
        npc["work_end_time"] = (datetime.now() + timedelta(hours=1)).isoformat()
    
    db.save()
    
    asyncio.create_task(complete_deposit_search(bot, interaction.user.id, тип, free_npcs[:3]))
    
    await interaction.response.send_message(f"🔍 Отправлены 3 NPC на поиск залежей {типа}! Они вернутся через 1 час.", ephemeral=True)

@bot.tree.command(name="залежи", description="Показать ваши залежи ресурсов")
@app_commands.describe(игрок="Игрок для просмотра (только для себя)")
async def deposits_command(interaction: discord.Interaction, игрок: Optional[discord.User] = None):
    target = игрок or interaction.user
    
    if target.id != interaction.user.id:
        await interaction.response.send_message("❌ Только владелец может смотреть свои залежи!", ephemeral=True)
        return
    
    await show_deposits_list(interaction, target)

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
