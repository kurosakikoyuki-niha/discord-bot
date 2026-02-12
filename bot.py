import discord
from discord import app_commands
import aiohttp
import random
import os

TOKEN = os.getenv("DISCORD_TOKEN")
RULE34_API_KEY = os.getenv("RULE34_API_KEY")
RULE34_USER_ID = os.getenv("RULE34_USER_ID")

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

def normalize_tag(tag: str | None) -> str:
    if not tag:
        return ""
    return tag.strip().replace(" ", "_")

async def fetch_images(site: str, tags: str, count: int):
    try:
        if site == "danbooru":
            url = "https://danbooru.donmai.us/posts.json"
            params = {
                "tags": tags,
                "limit": count,
                "random": "true"
            }

        elif site == "safebooru":
            url = "https://safebooru.org/index.php"
            params = {
                "page": "dapi",
                "s": "post",
                "q": "index",
                "json": 1,
                "limit": count,
                "tags": tags
            }

        elif site == "rule34":
            url = "https://api.rule34.xxx/index.php"
            params = {
                "page": "dapi",
                "s": "post",
                "q": "index",
                "json": 1,
                "limit": count,
                "tags": tags,
                "api_key": RULE34_API_KEY,
                "user_id": RULE34_USER_ID
            }

        headers = {
            "User-Agent": "Mozilla/5.0 (Discord Image Bot)"
        }

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, params=params) as resp:
                status = resp.status
                if status != 200:
                    return [], status

                data = await resp.json()

                # 🔥 사이트별 응답 구조 처리
                if site == "danbooru":
                    posts = data

                elif site == "safebooru":
                    posts = data.get("post", [])

                elif site == "rule34":
                    # rule34는 list 또는 dict 둘 다 올 수 있음
                    if isinstance(data, list):
                        posts = data
                    else:
                        posts = data.get("post", [])

                valid_urls = []

                for post in posts:
                    if post.get("file_url"):
                        valid_urls.append(post["file_url"])

                if not valid_urls:
                    return [], None

                # 🔥 count 개수 최대한 맞추기
                if len(valid_urls) <= count:
                    return valid_urls, None
                else:
                    return random.sample(valid_urls, count), None

    except Exception as e:
        print("Fetch error:", e)
        return [], str(e)

# 🔥 /image 그룹
image_group = app_commands.Group(name="image", description="이미지 관련 명령어")

@image_group.command(name="search", description="danbooru / safebooru / rule34 에서 랜덤 이미지 검색")
@app_commands.describe(
    tag1="첫 번째 태그 (예: yuzu (blue archive))",
    tag2="두 번째 태그 (선택)",
    site="이미지를 가져올 사이트",
    count="가져올 이미지 개수 (1 ~ 10)"
)
@app_commands.choices(site=[
    app_commands.Choice(name="danbooru", value="danbooru"),
    app_commands.Choice(name="safebooru", value="safebooru"),
    app_commands.Choice(name="rule34", value="rule34")
])
async def image_search(
    interaction: discord.Interaction,
    tag1: str,
    tag2: str | None = None,
    site: app_commands.Choice[str] = None,
    count: int = 1
):
    await interaction.response.defer()

    site_value = site.value if site else "danbooru"

    t1 = normalize_tag(tag1)
    t2 = normalize_tag(tag2)

    tag_query = t1
    if t2:
        tag_query = f"{t1} {t2}"
        
    # 🔥 Rule34에서만 AI 생성 이미지 제외
    if site_value == "rule34":
        tag_query += " -ai_generated"


    if count < 1 or count > 10:
        await interaction.followup.send("Count: should be under 10.")
        return

    image_urls, error = await fetch_images(site_value, tag_query, count)

    if not image_urls:
        msg = f"Image not found.\nsearched tags: {tag_query}"
        if error:
            msg += f"\nHTTP Error: {error}"
        await interaction.followup.send(msg)
        return

    await interaction.followup.send("\n".join(image_urls))

tree.add_command(image_group)

# 🧹 /purge 명령어
@tree.command(name="purge", description="메시지를 대량 삭제합니다")
@app_commands.describe(
    start_message_id="삭제 시작할 메시지 ID",
    end_message_id="삭제 끝낼 메시지 ID",
    author_id="특정 사용자의 메시지만 삭제 (선택)"
)
async def purge(
    interaction: discord.Interaction,
    start_message_id: str,
    end_message_id: str,
    author_id: str | None = None
):
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message("❌ 메시지 관리 권한이 필요합니다.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    channel = interaction.channel

    try:
        start_id = int(start_message_id)
        end_id = int(end_message_id)
    except ValueError:
        await interaction.followup.send("❌ 메시지 ID는 숫자여야 합니다.")
        return

    deleted = 0
    failed = 0

    async for msg in channel.history(limit=500, after=discord.Object(id=min(start_id, end_id)-1)):
        if msg.id > max(start_id, end_id):
            continue
        if author_id and str(msg.author.id) != author_id:
            continue

        try:
            await msg.delete()
            deleted += 1
        except:
            failed += 1

    await interaction.followup.send(
        f"🧹 삭제 완료\n삭제된 메시지: {deleted}개\n실패: {failed}개"
    )

@client.event
async def on_ready():
    await tree.sync()
    print(f"✅ 봇 로그인 완료: {client.user}")


client.run(TOKEN)

client.run(TOKEN)

