import discord
import requests
import asyncio
import logging
import time

TOKEN = ''

SCHOOL_ID = ''

# 設定多個頻道 ID
CHANNEL_IDS = []

# 設定 Discord 客戶端
intents = discord.Intents.default()
intents.message_content = True  # 確保能讀取訊息內容
client = discord.Client(intents=intents)

# 設定日誌
logging.basicConfig(level=logging.INFO)

BASE_URL = "https://fatraceschool.k12ea.gov.tw"

def get_today_date():
    """獲取今天的日期"""
    return time.strftime("%Y-%m-%d")

def fetch_data(url, params=None):
    """通用的數據抓取函數"""
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json().get('data', [])
    except requests.RequestException as e:
        logging.error(f"Error fetching data from {url}: {e}")
        return []

async def send_lunch_menu(channel, batch_data_id, provider_name=None, menu_message=None):
    """發送或更新午餐菜單訊息"""
    dishes = fetch_data(f"{BASE_URL}/dish", params={"BatchDataId": batch_data_id})
    dish_names = "\n".join([f"- {dish['DishName']}" for dish in dishes]) if dishes else "沒有可用的午餐菜單"

    provider_text = f"供應商：{provider_name}" if provider_name else "未選擇供應商"

    message_content = (
        f"{get_today_date()}午餐菜單：\n{provider_text}\n{dish_names}\n\n"
        f"[查看詳細資料]({BASE_URL}/frontend/search.html?school={SCHOOL_ID}&period={get_today_date()})"
    )

    if menu_message:
        try:
            await menu_message.edit(content=message_content)
        except discord.errors.NotFound:
            # 如果消息未找到或編輯失敗，則重新發送
            menu_message = await channel.send(message_content)
    else:
        menu_message = await channel.send(message_content)
    return menu_message

class ProviderSelect(discord.ui.Select):
    def __init__(self, providers, menu_message):
        self.menu_message = menu_message
        options = [discord.SelectOption(label=p['KitchenName'], value=p['BatchDataId']) for p in providers]
        super().__init__(placeholder="選擇午餐供應商...", options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_provider = next((p for p in self.options if p.value == self.values[0]), None)
        provider_name = selected_provider.label if selected_provider else "未知供應商"
        await interaction.response.defer()  # 延遲響應以避免超時
        await send_lunch_menu(interaction.channel, self.values[0], provider_name, self.menu_message)

class ProviderSelectView(discord.ui.View):
    def __init__(self, providers, menu_message):
        super().__init__(timeout=900)  # 選單的有效期 15 分鐘
        self.add_item(ProviderSelect(providers, menu_message))

    async def on_timeout(self):
        """禁用選單保留菜單內容"""
        for child in self.children:
            child.disabled = True  # 禁用選單
        if self.message:
            await self.message.edit(view=self)

async def scheduled_task():
    """特定時間自動發送午餐菜單到多個頻道"""
    while True:
        now = time.gmtime()
        if now.tm_wday < 5 and now.tm_hour == 3 and now.tm_min == 0:
            for channel_id in CHANNEL_IDS:
                channel = client.get_channel(channel_id)
                if channel:
                    await post_lunch_menu(channel)
            await asyncio.sleep(60)
        await asyncio.sleep(30)

async def post_lunch_menu(channel):
    """發送午餐選擇訊息"""
    providers = fetch_data(f"{BASE_URL}/offered/meal", params={
        "KitchenId": "all", 
        "MenuType": 1, 
        "period": get_today_date(), 
        "SchoolId": SCHOOL_ID
    })
    if providers:
        menu_message = await channel.send("選擇今天的午餐供應商：")
        view = ProviderSelectView(providers, menu_message)
        view.message = menu_message
        await menu_message.edit(view=view)
    else:
        await channel.send("沒有可用的午餐菜單")

@client.event
async def on_ready():
    logging.info(f'機器人已登入為 {client.user}')
    asyncio.create_task(scheduled_task())

@client.event
async def on_message(message):
    """處理收到的訊息"""
    if message.author == client.user:
        return

    if message.content.lower() == '!test':
        logging.info('收到 !test 指令')
        await message.channel.send('機器人正在運行!')

    elif message.content.lower() == '!lunch':
        logging.info('收到 !lunch 指令')
        await post_lunch_menu(message.channel)

client.run(TOKEN)