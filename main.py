import discord
from discord.ext import commands, tasks
import os
import random
from dotenv import load_dotenv
import json
import asyncio
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import datetime
import ssl

# Carrega variáveis do arquivo .env
load_dotenv()

# Configuração do MongoDB
MONGODB_CONNECTION_STRING = os.getenv('MONGODB_TOKEN')

# String alternativa sem SRV (caso SRV falhe) - será gerada dinamicamente se necessário
MONGODB_CONNECTION_STRING_ALT = None

# Cliente MongoDB
mongo_client = None
db = None

def init_mongodb():
    """Inicializa a conexão com MongoDB com timeout rápido"""
    global mongo_client, db
    
    if not MONGODB_CONNECTION_STRING:
        print("❌ MONGODB_TOKEN não encontrado nas variáveis de ambiente!")
        print("🔧 Configure MONGODB_TOKEN nos Secrets do Replit com sua connection string do MongoDB Atlas")
        return False
    
    # Configurações otimizadas e simplificadas
    connection_configs = [
        {
            "uri": MONGODB_CONNECTION_STRING,
            "options": {
                "serverSelectionTimeoutMS": 5000,
                "connectTimeoutMS": 3000,
                "socketTimeoutMS": 5000,
                "maxPoolSize": 1,
                "retryWrites": True,
                "w": 'majority'
            },
            "name": "MongoDB Atlas SRV (Simplificado)"
        },
        {
            "uri": MONGODB_CONNECTION_STRING.replace("mongodb+srv://", "mongodb://").replace("cluster0.9dbl7a5.mongodb.net", "cluster0-shard-00-00.9dbl7a5.mongodb.net:27017,cluster0-shard-00-01.9dbl7a5.mongodb.net:27017,cluster0-shard-00-02.9dbl7a5.mongodb.net:27017").replace("/?", "/instagram_mxp?ssl=true&replicaSet=atlas-rs0-shard-0&authSource=admin&"),
            "options": {
                "serverSelectionTimeoutMS": 3000,
                "connectTimeoutMS": 2000,
                "socketTimeoutMS": 3000,
                "maxPoolSize": 1,
                "retryWrites": False
            },
            "name": "MongoDB Atlas Direto (Sem SRV)"
        }
    ]
    
    for config in connection_configs:
        try:
            print(f"🔄 Tentando: {config['name']}")
            mongo_client = MongoClient(config["uri"], **config["options"])
            
            # Testa a conexão com timeout rápido
            mongo_client.admin.command('ping')
            
            # Pega o nome do banco
            if "mongodb+srv://" in config["uri"] or "mongodb://" in config["uri"]:
                if "/" in config["uri"].split("@")[1] and "?" in config["uri"]:
                    db_name = config["uri"].split("/")[-1].split("?")[0]
                    if db_name and db_name != "":
                        db = mongo_client[db_name]
                    else:
                        db = mongo_client.instagram_mxp
                else:
                    db = mongo_client.instagram_mxp
            else:
                db = mongo_client.instagram_mxp
            
            print(f"✅ MongoDB conectado: {config['name']}")
            print(f"📊 Banco: {db.name}")
            return True
            
        except Exception as e:
            print(f"❌ Falha em {config['name']}: {str(e)[:50]}...")
            if mongo_client:
                try:
                    mongo_client.close()
                except:
                    pass
            continue
    
    print("❌ MongoDB indisponível - bot funcionará apenas localmente")
    print("💡 Para resolver:")
    print("   1. Verifique MONGODB_TOKEN nos Secrets")
    print("   2. Use connection string sem SRV se possível")
    print("   3. Whitelist IP 0.0.0.0/0 no MongoDB Atlas")
    return False

class ProfileUpdateModal(discord.ui.Modal, title='Atualizar Perfil'):
    def __init__(self, current_username="", current_profession=""):
        super().__init__()
        
        self.username = discord.ui.TextInput(
            label='Nome de usuário',
            placeholder='Digite seu nome de usuário...',
            required=True,
            max_length=20,
            default=current_username
        )
        
        self.profession = discord.ui.TextInput(
            label='Profissão',
            placeholder='Digite sua profissão...',
            required=True,
            max_length=50,
            default=current_profession
        )
        
        self.add_item(self.username)
        self.add_item(self.profession)

    async def on_submit(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)

        # Inicializa dados do usuário se não existir
        if user_id not in user_data:
            user_data[user_id] = {
                'username': None,
                'total_likes': 0,
                'posts_count': 0,
                'followers': 0,
                'profession': None,
                'thumbnail_url': None,
                'embed_image_url': None,
                'profile_color': 0x9932CC
            }

        # Atualiza os dados
        user_data[user_id]['username'] = str(self.username.value)
        user_data[user_id]['profession'] = str(self.profession.value)
        
        # Salva imediatamente
        save_user_data()
        print(f"💾 Dados salvos após atualização de perfil: {user_id}")

        # Embed de confirmação
        embed = discord.Embed(
            title="✅ Perfil Atualizado!",
            description="Suas informações foram atualizadas com sucesso!",
            color=0x00FF00
        )
        embed.add_field(
            name="👤 Nome de usuário",
            value=f"@{self.username.value}",
            inline=True
        )
        embed.add_field(
            name="💼 Profissão",
            value=f"{self.profession.value}",
            inline=True
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"Atualizado por {interaction.user.display_name}")

        # Responde com confirmação
        await interaction.response.send_message(embed=embed, ephemeral=True)

class BioUpdateModal(discord.ui.Modal, title='Atualizar Bio e Status'):
    def __init__(self, current_bio="", current_status=""):
        super().__init__()
        
        self.bio = discord.ui.TextInput(
            label='Bio/Descrição',
            placeholder='Conte um pouco sobre você...',
            required=False,
            max_length=200,
            style=discord.TextStyle.paragraph,
            default=current_bio
        )
        
        self.status = discord.ui.TextInput(
            label='Status Personalizado',
            placeholder='Ex: Trabalhando duro 💪',
            required=False,
            max_length=50,
            default=current_status
        )
        
        self.add_item(self.bio)
        self.add_item(self.status)

    async def on_submit(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)

        # Inicializa dados do usuário se não existir
        if user_id not in user_data:
            user_data[user_id] = {
                'username': None,
                'total_likes': 0,
                'posts_count': 0,
                'followers': 0,
                'profession': None,
                'thumbnail_url': None,
                'embed_image_url': None,
                'profile_color': 0x9932CC,
                'bio': None,
                'status': None
            }

        # Atualiza os dados
        user_data[user_id]['bio'] = str(self.bio.value) if self.bio.value else None
        user_data[user_id]['status'] = str(self.status.value) if self.status.value else None
        
        # Salva imediatamente
        save_user_data()
        print(f"💾 Bio e status salvos para: {user_id}")

        # Embed de confirmação
        embed = discord.Embed(
            title="✅ Bio e Status Atualizados!",
            description="Suas informações foram atualizadas com sucesso!",
            color=user_data[user_id].get('profile_color', 0x9932CC)
        )
        
        if self.bio.value:
            embed.add_field(
                name="📝 Nova Bio",
                value=f"{self.bio.value}",
                inline=False
            )
        
        if self.status.value:
            embed.add_field(
                name="💫 Novo Status",
                value=f"{self.status.value}",
                inline=False
            )
        
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"Atualizado por {interaction.user.display_name}")

        # Responde com confirmação
        await interaction.response.send_message(embed=embed, ephemeral=True)

class LinksUpdateModal(discord.ui.Modal, title='Atualizar Links Sociais'):
    def __init__(self, current_instagram="", current_youtube="", current_tiktok=""):
        super().__init__()
        
        self.instagram = discord.ui.TextInput(
            label='Instagram (@username)',
            placeholder='@seu_instagram',
            required=False,
            max_length=30,
            default=current_instagram
        )
        
        self.youtube = discord.ui.TextInput(
            label='YouTube (Canal)',
            placeholder='Nome do seu canal',
            required=False,
            max_length=50,
            default=current_youtube
        )
        
        self.tiktok = discord.ui.TextInput(
            label='TikTok (@username)',
            placeholder='@seu_tiktok',
            required=False,
            max_length=30,
            default=current_tiktok
        )
        
        self.add_item(self.instagram)
        self.add_item(self.youtube)
        self.add_item(self.tiktok)

    async def on_submit(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)

        # Inicializa dados do usuário se não existir
        if user_id not in user_data:
            user_data[user_id] = {
                'username': None,
                'total_likes': 0,
                'posts_count': 0,
                'followers': 0,
                'profession': None,
                'thumbnail_url': None,
                'embed_image_url': None,
                'profile_color': 0x9932CC,
                'social_links': {}
            }

        # Inicializa links sociais se não existir
        if 'social_links' not in user_data[user_id]:
            user_data[user_id]['social_links'] = {}

        # Atualiza os links
        user_data[user_id]['social_links']['instagram'] = str(self.instagram.value) if self.instagram.value else None
        user_data[user_id]['social_links']['youtube'] = str(self.youtube.value) if self.youtube.value else None
        user_data[user_id]['social_links']['tiktok'] = str(self.tiktok.value) if self.tiktok.value else None
        
        # Salva imediatamente
        save_user_data()
        print(f"💾 Links sociais salvos para: {user_id}")

        # Embed de confirmação
        embed = discord.Embed(
            title="✅ Links Sociais Atualizados!",
            description="Seus links foram atualizados com sucesso!",
            color=user_data[user_id].get('profile_color', 0x9932CC)
        )
        
        links_text = ""
        if self.instagram.value:
            links_text += f"📷 Twitter: {self.instagram.value}\n"
        if self.youtube.value:
            links_text += f"🎥 YouTube: {self.youtube.value}\n"
        if self.tiktok.value:
            links_text += f"🎵 TikTok: {self.tiktok.value}\n"
        
        if links_text:
            embed.add_field(
                name="🔗 Seus Links",
                value=links_text,
                inline=False
            )
        else:
            embed.add_field(
                name="🔗 Links Removidos",
                value="Todos os links sociais foram removidos do seu perfil.",
                inline=False
            )
        
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"Atualizado por {interaction.user.display_name}")

        # Responde com confirmação
        await interaction.response.send_message(embed=embed, ephemeral=True)

class ImageTypeView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=300)
        self.user_id = user_id

    @discord.ui.button(label='📸 Thumbnail (Imagem Pequena)', style=discord.ButtonStyle.primary)
    async def thumbnail_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="📸 Enviar Thumbnail",
            description="Envie a imagem que será usada como **thumbnail** (imagem pequena) do seu perfil.",
            color=0x00FF00
        )
        embed.add_field(
            name="📝 Instruções:",
            value="• Envie apenas **1 imagem**\n• A imagem será automaticamente salva\n• Você tem **60 segundos** para enviar",
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

        # Aguarda a imagem
        def check(m):
            return m.author.id == interaction.user.id and len(m.attachments) > 0

        try:
            message = await bot.wait_for('message', check=check, timeout=60.0)

            if message.attachments:
                image_url = message.attachments[0].url

                # Inicializa dados do usuário se não existir
                if self.user_id not in user_data:
                    user_data[self.user_id] = {
                        'username': None,
                        'total_likes': 0,
                        'posts_count': 0,
                        'followers': 0,
                        'profession': None,
                        'thumbnail_url': None,
                        'embed_image_url': None
                    }

                # Salva a URL da thumbnail
                user_data[self.user_id]['thumbnail_url'] = image_url
                save_user_data()

                success_embed = discord.Embed(
                    title="✅ Thumbnail Atualizada!",
                    description="Sua thumbnail foi salva com sucesso!",
                    color=0x00FF00
                )
                success_embed.set_thumbnail(url=image_url)

                await message.reply(embed=success_embed)

        except asyncio.TimeoutError:
            timeout_embed = discord.Embed(
                title="⏰ Tempo Esgotado",
                description="Você demorou muito para enviar a imagem. Tente novamente.",
                color=0xFF0000
            )
            channel = bot.get_channel(interaction.channel_id) or interaction.user
            await channel.send(embed=timeout_embed)

    @discord.ui.button(label='🖼️ Imagem do Embed (Imagem Grande)', style=discord.ButtonStyle.secondary)
    async def embed_image_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🖼️ Enviar Imagem do Embed",
            description="Envie a imagem que será usada como **imagem do embed** (imagem grande) do seu perfil.",
            color=0x0099FF
        )
        embed.add_field(
            name="📝 Instruções:",
            value="• Envie apenas **1 imagem**\n• A imagem será automaticamente salva\n• Você tem **60 segundos** para enviar",
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

        # Aguarda a imagem
        def check(m):
            return m.author.id == interaction.user.id and len(m.attachments) > 0

        try:
            message = await bot.wait_for('message', check=check, timeout=60.0)

            if message.attachments:
                image_url = message.attachments[0].url

                # Inicializa dados do usuário se não existir
                if self.user_id not in user_data:
                    user_data[self.user_id] = {
                        'username': None,
                        'total_likes': 0,
                        'posts_count': 0,
                        'followers': 0,
                        'profession': None,
                        'thumbnail_url': None,
                        'embed_image_url': None
                    }

                # Salva a URL da imagem do embed
                user_data[self.user_id]['embed_image_url'] = image_url
                save_user_data()

                success_embed = discord.Embed(
                    title="✅ Imagem do Embed Atualizada!",
                    description="Sua imagem do embed foi salva com sucesso!",
                    color=0x00FF00
                )
                success_embed.set_image(url=image_url)

                await message.reply(embed=success_embed)

        except asyncio.TimeoutError:
            timeout_embed = discord.Embed(
                title="⏰ Tempo Esgotado",
                description="Você demorou muito para enviar a imagem. Tente novamente.",
                color=0xFF0000
            )
            channel = bot.get_channel(interaction.channel_id) or interaction.user
            await channel.send(embed=timeout_embed)

class ThemeSelectView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=300)
        self.user_id = user_id
        
        # Adiciona select menu com temas
        self.add_item(ThemeSelect(user_id))

    @discord.ui.button(label='🔙 Voltar', style=discord.ButtonStyle.secondary, row=1)
    async def voltar_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Este menu não é seu!", ephemeral=True)
            return
        
        # Volta ao menu principal de atualização
        await show_main_update_menu(interaction, self.user_id)

class BadgeSelectView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=300)
        self.user_id = user_id
        
        # Adiciona select menu com badges
        self.add_item(BadgeSelect(user_id))

    @discord.ui.button(label='🔙 Voltar', style=discord.ButtonStyle.secondary, row=1)
    async def voltar_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Este menu não é seu!", ephemeral=True)
            return
        
        # Volta ao menu principal de atualização
        await show_main_update_menu(interaction, self.user_id)

class ColorSelectView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=300)
        self.user_id = user_id
        
        # Adiciona select menu com cores
        self.add_item(ColorSelect(user_id))

    @discord.ui.button(label='🔙 Voltar', style=discord.ButtonStyle.secondary, row=1)
    async def voltar_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Este menu não é seu!", ephemeral=True)
            return
        
        # Volta ao menu principal de atualização
        await show_main_update_menu(interaction, self.user_id)

class ThemeSelect(discord.ui.Select):
    def __init__(self, user_id):
        self.user_id = user_id
        
        # Temas disponíveis
        themes = [
            ("🌟 Clássico", "classico", "Tema padrão e elegante"),
            ("🔥 Gamer", "gamer", "Para os apaixonados por games"),
            ("💼 Profissional", "profissional", "Sério e corporativo"),
            ("🎨 Artista", "artista", "Criativo e colorido"),
            ("🌸 Kawaii", "kawaii", "Fofo e adorável"),
            ("🖤 Dark Mode", "dark", "Escuro e minimalista"),
            ("🌈 Pride", "pride", "Colorido e inclusivo"),
            ("⚡ Neon", "neon", "Vibrante e futurístico"),
            ("🌿 Natural", "natural", "Verde e orgânico"),
            ("👑 Luxo", "luxo", "Dourado e premium")
        ]
        
        options = []
        for name, value, description in themes:
            options.append(discord.SelectOption(
                label=name,
                description=description,
                value=value
            ))
        
        super().__init__(
            placeholder="🎭 Escolha um tema para seu perfil...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Este menu não é seu!", ephemeral=True)
            return
        
        selected_theme = self.values[0]
        
        # Atualiza o tema do perfil
        user_data[self.user_id]['profile_theme'] = selected_theme
        save_user_data()
        
        # Mapeia nomes dos temas
        theme_names = {
            "classico": "🌟 Clássico",
            "gamer": "🔥 Gamer",
            "profissional": "💼 Profissional",
            "artista": "🎨 Artista",
            "kawaii": "🌸 Kawaii",
            "dark": "🖤 Dark Mode",
            "pride": "🌈 Pride",
            "neon": "⚡ Neon",
            "natural": "🌿 Natural",
            "luxo": "👑 Luxo"
        }
        
        theme_name = theme_names.get(selected_theme, "Tema Personalizado")
        
        # Embed de confirmação
        embed = discord.Embed(
            title="🎭 Tema Atualizado!",
            description=f"Seu tema do perfil foi alterado para **{theme_name}**!",
            color=user_data[self.user_id].get('profile_color', 0x9932CC)
        )
        embed.add_field(
            name="✨ Novo Tema",
            value=f"🎯 **{theme_name}**\n📝 Este tema influencia a aparência do seu perfil",
            inline=False
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"Tema alterado por {interaction.user.display_name}")
        
        await interaction.response.edit_message(embed=embed, view=None)

class BadgeSelect(discord.ui.Select):
    def __init__(self, user_id):
        self.user_id = user_id
        
        # Badges disponíveis
        badges = [
            ("🎮 Gamer", "gamer", "Para os viciados em jogos"),
            ("🎨 Artista", "artista", "Para os criativos"),
            ("📚 Estudante", "estudante", "Para quem ama estudar"),
            ("💼 Trabalhador", "trabalhador", "Para os profissionais"),
            ("🌟 Streamer", "streamer", "Para os criadores de conteúdo"),
            ("🎵 Músico", "musico", "Para os amantes da música"),
            ("📷 Fotógrafo", "fotografo", "Para quem ama fotografar"),
            ("⚽ Esportista", "esportista", "Para os atletas"),
            ("🍕 Foodie", "foodie", "Para os amantes da comida"),
            ("🌍 Viajante", "viajante", "Para os exploradores"),
            ("❌ Remover Badge", "remove", "Remove o badge atual")
        ]
        
        options = []
        for name, value, description in badges:
            options.append(discord.SelectOption(
                label=name,
                description=description,
                value=value
            ))
        
        super().__init__(
            placeholder="🏆 Escolha um badge para seu perfil...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Este menu não é seu!", ephemeral=True)
            return
        
        selected_badge = self.values[0]
        
        # Atualiza o badge do perfil
        if selected_badge == "remove":
            user_data[self.user_id]['profile_badge'] = None
        else:
            user_data[self.user_id]['profile_badge'] = selected_badge
        
        save_user_data()
        
        # Mapeia nomes dos badges
        badge_names = {
            "gamer": "🎮 Gamer",
            "artista": "🎨 Artista",
            "estudante": "📚 Estudante",
            "trabalhador": "💼 Trabalhador",
            "streamer": "🌟 Streamer",
            "musico": "🎵 Músico",
            "fotografo": "📷 Fotógrafo",
            "esportista": "⚽ Esportista",
            "foodie": "🍕 Foodie",
            "viajante": "🌍 Viajante"
        }
        
        # Embed de confirmação
        embed = discord.Embed(
            title="🏆 Badge Atualizado!",
            color=user_data[self.user_id].get('profile_color', 0x9932CC)
        )
        
        if selected_badge == "remove":
            embed.description = "Seu badge foi removido do perfil!"
            embed.add_field(
                name="❌ Badge Removido",
                value="Agora você não possui nenhum badge especial",
                inline=False
            )
        else:
            badge_name = badge_names.get(selected_badge, "Badge Personalizado")
            embed.description = f"Seu badge foi alterado para **{badge_name}**!"
            embed.add_field(
                name="✨ Novo Badge",
                value=f"🎯 **{badge_name}**\n📝 Este badge aparece no seu perfil",
                inline=False
            )
        
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"Badge alterado por {interaction.user.display_name}")
        
        await interaction.response.edit_message(embed=embed, view=None)

class ColorSelect(discord.ui.Select):
    def __init__(self, user_id):
        self.user_id = user_id
        
        # Cores disponíveis
        colors = [
            ("🔵 Azul Marinho", "azul_marinho", 0x1E3A8A),
            ("⚫ Cinza Escuro", "cinza_escuro", 0x374151),
            ("🟢 Verde Escuro", "verde_escuro", 0x4B5563),
            ("🔷 Azul Petróleo", "azul_petroleo", 0x0F766E),
            ("🍷 Vinho", "vinho", 0x7F1D1D),
            ("🌸 Rosa Claro", "rosa_claro", 0xF9A8D4),
            ("💜 Lavanda", "lavanda", 0xC084FC),
            ("🪸 Coral", "coral", 0xFB7185),
            ("☁️ Azul Céu", "azul_ceu", 0x38BDF8),
            ("🦄 Lilás", "lilas", 0xE9D5FF)
        ]
        
        options = []
        for name, value, hex_color in colors:
            options.append(discord.SelectOption(
                label=name,
                description=f"Cor hexadecimal: #{hex_color:06X}",
                value=value
            ))
        
        super().__init__(
            placeholder="🎨 Escolha uma cor para seu perfil...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Este menu não é seu!", ephemeral=True)
            return
        
        # Mapeamento das cores
        color_map = {
            "azul_marinho": 0x1E3A8A,
            "cinza_escuro": 0x374151,
            "verde_escuro": 0x4B5563,
            "azul_petroleo": 0x0F766E,
            "vinho": 0x7F1D1D,
            "rosa_claro": 0xF9A8D4,
            "lavanda": 0xC084FC,
            "coral": 0xFB7185,
            "azul_ceu": 0x38BDF8,
            "lilas": 0xE9D5FF
        }
        
        selected_color = self.values[0]
        color_hex = color_map[selected_color]
        color_name = get_color_name(color_hex)
        
        # Atualiza a cor do perfil
        user_data[self.user_id]['profile_color'] = color_hex
        save_user_data()
        
        # Embed de confirmação
        embed = discord.Embed(
            title="🎨 Cor Atualizada!",
            description=f"Sua cor do perfil foi alterada para **{color_name}**!",
            color=color_hex
        )
        embed.add_field(
            name="✨ Nova Cor",
            value=f"🎯 **{color_name}**\n📝 Código: `#{color_hex:06X}`",
            inline=False
        )
        embed.add_field(
            name="💡 Onde aparece:",
            value="• Embed do seu perfil (`m!perfil`)\n• Embed de atualização\n• Outros embeds relacionados ao seu perfil",
            inline=False
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"Cor alterada por {interaction.user.display_name}")
        
        await interaction.response.edit_message(embed=embed, view=None)

def get_color_name(color_hex):
    """Retorna o nome da cor baseado no valor hexadecimal"""
    color_names = {
        0x1E3A8A: "Azul Marinho",
        0x374151: "Cinza Escuro", 
        0x4B5563: "Verde Escuro",
        0x0F766E: "Azul Petróleo",
        0x7F1D1D: "Vinho",
        0xF9A8D4: "Rosa Claro",
        0xC084FC: "Lavanda",
        0xFB7185: "Coral",
        0x38BDF8: "Azul Céu",
        0xE9D5FF: "Lilás",
        0x9932CC: "Roxo (Padrão)"
    }
    return color_names.get(color_hex, "Cor Personalizada")

async def show_main_update_menu(interaction, user_id):
    """Mostra o menu principal de atualização de perfil"""
    user_data_info = user_data[user_id]
    current_username = user_data_info.get('username', '')
    current_profession = user_data_info.get('profession', '')
    current_bio = user_data_info.get('bio', '')
    current_status = user_data_info.get('status', '')
    current_theme = user_data_info.get('profile_theme', 'classico')
    current_badge = user_data_info.get('profile_badge', None)
    
    embed = discord.Embed(
        title="⚙️ Central de Personalização",
        description="Personalize seu perfil do Instagram MXP com várias opções!",
        color=user_data_info.get('profile_color', 0x9932CC)
    )
    
    # Informações básicas
    embed.add_field(
        name="📋 Informações Básicas",
        value=f"**Nome:** {current_username or 'Não definido'}\n**Profissão:** {current_profession or 'Não definido'}",
        inline=False
    )
    
    # Bio e Status
    bio_text = current_bio[:50] + "..." if current_bio and len(current_bio) > 50 else current_bio or "Não definida"
    status_text = current_status or "Não definido"
    embed.add_field(
        name="💭 Bio e Status",
        value=f"**Bio:** {bio_text}\n**Status:** {status_text}",
        inline=False
    )
    
    # Tema e Badge
    theme_names = {
        "classico": "🌟 Clássico", "gamer": "🔥 Gamer", "profissional": "💼 Profissional",
        "artista": "🎨 Artista", "kawaii": "🌸 Kawaii", "dark": "🖤 Dark Mode",
        "pride": "🌈 Pride", "neon": "⚡ Neon", "natural": "🌿 Natural", "luxo": "👑 Luxo"
    }
    badge_names = {
        "gamer": "🎮 Gamer", "artista": "🎨 Artista", "estudante": "📚 Estudante",
        "trabalhador": "💼 Trabalhador", "streamer": "🌟 Streamer", "musico": "🎵 Músico",
        "fotografo": "📷 Fotógrafo", "esportista": "⚽ Esportista", "foodie": "🍕 Foodie", "viajante": "🌍 Viajante"
    }
    
    current_theme_name = theme_names.get(current_theme, "🌟 Clássico")
    current_badge_name = badge_names.get(current_badge, "Nenhum") if current_badge else "Nenhum"
    
    embed.add_field(
        name="🎭 Aparência",
        value=f"**Tema:** {current_theme_name}\n**Badge:** {current_badge_name}\n**Cor:** {get_color_name(user_data_info.get('profile_color', 0x9932CC))}",
        inline=False
    )
    
    # Links sociais
    social_links = user_data_info.get('social_links', {})
    links_text = ""
    if social_links.get('instagram'): links_text += f"📷 {social_links['instagram']}\n"
    if social_links.get('youtube'): links_text += f"🎥 {social_links['youtube']}\n"
    if social_links.get('tiktok'): links_text += f"🎵 {social_links['tiktok']}\n"
    if not links_text: links_text = "Nenhum link definido"
    
    embed.add_field(
        name="🔗 Links Sociais",
        value=links_text,
        inline=False
    )
    
    embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1387842927602172125.png")
    embed.set_footer(text="Use os botões abaixo para personalizar seu perfil")
    
    view = UpdateProfileView(current_username, current_profession, user_id)
    await interaction.response.edit_message(embed=embed, view=view)

class UpdateProfileView(discord.ui.View):
    def __init__(self, current_username="", current_profession="", user_id=None):
        super().__init__(timeout=300)
        self.current_username = current_username
        self.current_profession = current_profession
        self.user_id = user_id

    @discord.ui.button(label='Nome/Profissão', style=discord.ButtonStyle.primary, emoji='📝')
    async def open_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ProfileUpdateModal(self.current_username, self.current_profession)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='Bio/Status', style=discord.ButtonStyle.secondary, emoji='💭')
    async def bio_status_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        current_bio = user_data[self.user_id].get('bio', '')
        current_status = user_data[self.user_id].get('status', '')
        modal = BioUpdateModal(current_bio, current_status)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='Links Sociais', style=discord.ButtonStyle.success, emoji='🔗')
    async def links_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        social_links = user_data[self.user_id].get('social_links', {})
        current_instagram = social_links.get('instagram', '')
        current_youtube = social_links.get('youtube', '')
        current_tiktok = social_links.get('tiktok', '')
        modal = LinksUpdateModal(current_instagram, current_youtube, current_tiktok)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='Tema', style=discord.ButtonStyle.secondary, emoji='🎭', row=1)
    async def change_theme(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Este menu não é seu!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🎭 Escolher Tema do Perfil",
            description="Selecione um tema para personalizar a aparência do seu perfil:",
            color=user_data[self.user_id].get('profile_color', 0x9932CC)
        )
        
        embed.add_field(
            name="🎨 Temas Disponíveis",
            value="🌟 **Clássico** - Elegante e atemporal\n🔥 **Gamer** - Para os viciados em jogos\n💼 **Profissional** - Sério e corporativo\n🎨 **Artista** - Criativo e colorido\n🌸 **Kawaii** - Fofo e adorável",
            inline=False
        )
        
        embed.add_field(
            name="🌈 Temas Especiais",
            value="🖤 **Dark Mode** - Escuro e minimalista\n🌈 **Pride** - Colorido e inclusivo\n⚡ **Neon** - Vibrante e futurístico\n🌿 **Natural** - Verde e orgânico\n👑 **Luxo** - Dourado e premium",
            inline=False
        )
        
        view = ThemeSelectView(self.user_id)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label='🏆 Badge', style=discord.ButtonStyle.secondary, emoji='🏆', row=1)
    async def change_badge(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Este menu não é seu!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🏆 Escolher Badge do Perfil",
            description="Selecione um badge para mostrar sua personalidade:",
            color=user_data[self.user_id].get('profile_color', 0x9932CC)
        )
        
        embed.add_field(
            name="🎯 Badges Disponíveis",
            value="🎮 **Gamer** - Para os viciados em jogos\n🎨 **Artista** - Para os criativos\n📚 **Estudante** - Para quem ama estudar\n💼 **Trabalhador** - Para os profissionais\n🌟 **Streamer** - Para criadores de conteúdo",
            inline=False
        )
        
        embed.add_field(
            name="🌟 Mais Badges",
            value="🎵 **Músico** - Para os amantes da música\n📷 **Fotógrafo** - Para quem ama fotografar\n⚽ **Esportista** - Para os atletas\n🍕 **Foodie** - Para os amantes da comida\n🌍 **Viajante** - Para os exploradores",
            inline=False
        )
        
        view = BadgeSelectView(self.user_id)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label='Cor', style=discord.ButtonStyle.secondary, emoji='🎨', row=1)
    async def change_color(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Este menu não é seu!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🎨 Escolher Cor do Perfil",
            description="Selecione uma cor para personalizar seus embeds de perfil:",
            color=user_data[self.user_id].get('profile_color', 0x9932CC)
        )
        
        embed.add_field(
            name="🌈 Cores Disponíveis",
            value="🔵 **Azul Marinho** - Elegante e profissional\n⚫ **Cinza Escuro** - Sóbrio e moderno\n🟢 **Verde Escuro** - Natural e confiável\n🔷 **Azul Petróleo** - Sofisticado e único\n🍷 **Vinho** - Luxuoso e marcante",
            inline=False
        )
        
        embed.add_field(
            name="🎀 Cores Vibrantes",
            value="🌸 **Rosa Claro** - Doce e delicado\n💜 **Lavanda** - Suave e relaxante\n🪸 **Coral** - Energético e caloroso\n☁️ **Azul Céu** - Fresco e livre\n🦄 **Lilás** - Mágico e criativo",
            inline=False
        )
        
        view = ColorSelectView(self.user_id)
        await interaction.response.edit_message(embed=embed, view=view)

class ProfileView(discord.ui.View):
    def __init__(self, user_id, member):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.member = member

    @discord.ui.button(label='Mudar Imagem', style=discord.ButtonStyle.secondary, emoji='🖼️')
    async def change_image(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)

        embed = discord.Embed(
            title="🖼️ Escolha o Tipo de Imagem",
            description="Selecione qual tipo de imagem você deseja alterar:",
            color=0x9932CC
        )
        embed.add_field(
            name="📸 Thumbnail",
            value="Imagem pequena que aparece ao lado do nome",
            inline=True
        )
        embed.add_field(
            name="🖼️ Imagem do Embed",
            value="Imagem grande que aparece no perfil",
            inline=True
        )

        view = ImageTypeView(user_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    

# Sistema de dados dos usuários (em memória - em produção use banco de dados)
user_data = {}

# Sistema de relacionamentos sociais
follow_data = {
    # "user_id": {
    #     "following": ["user_id1", "user_id2"],  # quem o usuário segue
    #     "followers": ["user_id3", "user_id4"]   # quem segue o usuário
    # }
}

# Sistema de rastreamento de resets (quem já usou o comando m!reset)
reset_data = {
    # "user_id": True  # True = já usou o reset
}

# Sistema de economia (dinheiro e fama)
economy_data = {
    # "user_id": {
    #     "money": 0,    # Dinheiro em reais
    #     "fame": 0      # Pontos de fama ganhos com publicidade
    # }
}

# Sistema de tracking de posts com marcas (para evitar spam de m!publi)
brand_posts_data = {
    # "user_id": {
    #     "message_123456": {
    #         "brands": ["Nike", "Adidas"],
    #         "rewarded": False,
    #         "timestamp": "2024-01-01T12:00:00"
    #     }
    # }
}

# Sistema de inventário dos usuários
inventory_data = {
    # "user_id": {
    #     "carros": [{"nome": "BMW M3", "preco": 50000, "data_compra": "2024-01-01"}],
    #     "mansoes": [],
    #     "itens_diarios": []
    # }
}

# Catálogo da lojinha
LOJA_ITEMS = {
    "carros": {
        "🚗 Volkswagen Gol": {"preco": 35000, "categoria": "Carros Populares"},
        "🚙 Honda Civic": {"preco": 85000, "categoria": "Carros Médios"},
        "🚘 Toyota Corolla": {"preco": 95000, "categoria": "Carros Médios"},
        "🚗 Hyundai HB20": {"preco": 65000, "categoria": "Carros Populares"},
        "🚙 Nissan Sentra": {"preco": 88000, "categoria": "Carros Médios"},
        "🏎️ BMW M3": {"preco": 250000, "categoria": "Carros Esportivos"},
        "🏎️ Audi RS4": {"preco": 280000, "categoria": "Carros Esportivos"},
        "🏎️ Porsche 911": {"preco": 350000, "categoria": "Carros Esportivos"},
        "🚘 Mercedes-Benz C-Class": {"preco": 320000, "categoria": "Carros Luxo"},
        "🚘 BMW Série 5": {"preco": 380000, "categoria": "Carros Luxo"},
        "🚘 Audi A6": {"preco": 360000, "categoria": "Carros Luxo"},
        "🔥 Lamborghini Huracán": {"preco": 1200000, "categoria": "Supercars"},
        "🔥 Ferrari F8": {"preco": 1400000, "categoria": "Supercars"},
        "🔥 McLaren 570S": {"preco": 900000, "categoria": "Supercars"},
        "👑 Bugatti Chiron": {"preco": 15000000, "categoria": "Hipercars"},
        "👑 Koenigsegg Agera": {"preco": 12000000, "categoria": "Hipercars"},
        "⚡ Tesla Model S": {"preco": 450000, "categoria": "Carros Elétricos"},
        "⚡ Tesla Model 3": {"preco": 280000, "categoria": "Carros Elétricos"},
        "⚡ BMW iX": {"preco": 520000, "categoria": "Carros Elétricos"},
        "🌟 Ferrari 488": {"preco": 1800000, "categoria": "Supercars"},
        "💎 Rolls-Royce Phantom": {"preco": 2500000, "categoria": "Ultra Luxo"},
        "💎 Bentley Mulsanne": {"preco": 1800000, "categoria": "Ultra Luxo"},
        "🚀 McLaren 720S": {"preco": 1500000, "categoria": "Supercars"}
    },
    "mansoes": {
        "🏠 Casa Simples": {"preco": 150000, "categoria": "Residências Básicas"},
        "🏠 Apartamento Studio": {"preco": 80000, "categoria": "Residências Básicas"},
        "🏠 Casa Geminada": {"preco": 120000, "categoria": "Residências Básicas"},
        "🏡 Casa de Classe Média": {"preco": 500000, "categoria": "Residências Médias"},
        "🏡 Sobrado": {"preco": 650000, "categoria": "Residências Médias"},
        "🏡 Casa com Piscina": {"preco": 750000, "categoria": "Residências Médias"},
        "🏘️ Casa de Luxo": {"preco": 1200000, "categoria": "Residências de Luxo"},
        "🏘️ Casa no Condomínio": {"preco": 1500000, "categoria": "Residências de Luxo"},
        "🏘️ Casa com Vista": {"preco": 1800000, "categoria": "Residências de Luxo"},
        "🏰 Mansão Clássica": {"preco": 5000000, "categoria": "Mansões"},
        "🏰 Mansão Moderna": {"preco": 6000000, "categoria": "Mansões"},
        "🏰 Mansão Vitoriana": {"preco": 7500000, "categoria": "Mansões"},
        "🌴 Mansão na Praia": {"preco": 8000000, "categoria": "Mansões Premium"},
        "🌴 Casa de Praia": {"preco": 4500000, "categoria": "Mansões Premium"},
        "🏔️ Chalé nas Montanhas": {"preco": 3500000, "categoria": "Propriedades Especiais"},
        "🏔️ Cabana Alpina": {"preco": 2800000, "categoria": "Propriedades Especiais"},
        "🌆 Penthouse": {"preco": 6500000, "categoria": "Apartamentos de Luxo"},
        "🌆 Cobertura Duplex": {"preco": 5200000, "categoria": "Apartamentos de Luxo"},
        "🏛️ Mansão Histórica": {"preco": 12000000, "categoria": "Propriedades Únicas"},
        "🏛️ Castelo Medieval": {"preco": 15000000, "categoria": "Propriedades Únicas"},
        "🌟 Mansão dos Sonhos": {"preco": 25000000, "categoria": "Ultra Premium"},
        "🌟 Villa Italiana": {"preco": 30000000, "categoria": "Ultra Premium"},
        "👑 Palácio Real": {"preco": 50000000, "categoria": "Realeza"},
        "👑 Palácio de Versalhes": {"preco": 100000000, "categoria": "Realeza"}
    },
    "itens_diarios": {
        "☕ Café Starbucks": {"preco": 15, "categoria": "Bebidas"},
        "☕ Cappuccino": {"preco": 12, "categoria": "Bebidas"},
        "🥤 Coca-Cola": {"preco": 8, "categoria": "Bebidas"},
        "🥤 Red Bull": {"preco": 18, "categoria": "Bebidas"},
        "🥤 Água Mineral": {"preco": 5, "categoria": "Bebidas"},
        "🍔 Big Mac": {"preco": 25, "categoria": "Comidas"},
        "🍕 Pizza Grande": {"preco": 45, "categoria": "Comidas"},
        "🍗 KFC Bucket": {"preco": 55, "categoria": "Comidas"},
        "🌮 Taco Bell": {"preco": 20, "categoria": "Comidas"},
        "🍜 Ramen": {"preco": 30, "categoria": "Comidas"},
        "👕 Camiseta Nike": {"preco": 120, "categoria": "Roupas"},
        "👕 Camiseta Adidas": {"preco": 110, "categoria": "Roupas"},
        "👖 Calça Jeans": {"preco": 180, "categoria": "Roupas"},
        "🧥 Jaqueta Couro": {"preco": 450, "categoria": "Roupas"},
        "👗 Vestido": {"preco": 200, "categoria": "Roupas"},
        "👟 Tênis Adidas": {"preco": 350, "categoria": "Calçados"},
        "👟 Tênis Nike": {"preco": 380, "categoria": "Calçados"},
        "👞 Sapato Social": {"preco": 280, "categoria": "Calçados"},
        "📱 iPhone 15": {"preco": 8500, "categoria": "Eletrônicos"},
        "📱 Samsung Galaxy": {"preco": 6500, "categoria": "Eletrônicos"},
        "💻 MacBook Pro": {"preco": 15000, "categoria": "Eletrônicos"},
        "💻 Dell Inspiron": {"preco": 4500, "categoria": "Eletrônicos"},
        "📺 TV 75\" OLED": {"preco": 18000, "categoria": "Eletrônicos"},
        "📺 TV 55\" 4K": {"preco": 3500, "categoria": "Eletrônicos"},
        "🎧 AirPods Pro": {"preco": 2200, "categoria": "Eletrônicos"},
        "🎧 Fone JBL": {"preco": 800, "categoria": "Eletrônicos"},
        "🎮 PlayStation 5": {"preco": 4500, "categoria": "Games"},
        "🎮 Xbox Series X": {"preco": 4200, "categoria": "Games"},
        "🎮 Nintendo Switch": {"preco": 2800, "categoria": "Games"},
        "⌚ Apple Watch": {"preco": 3500, "categoria": "Acessórios"},
        "⌚ Smartwatch Samsung": {"preco": 1800, "categoria": "Acessórios"},
        "🕶️ Óculos Ray-Ban": {"preco": 800, "categoria": "Acessórios"},
        "🕶️ Óculos Oakley": {"preco": 650, "categoria": "Acessórios"},
        "⌚ Rolex": {"preco": 85000, "categoria": "Joias"},
        "👜 Bolsa Louis Vuitton": {"preco": 12000, "categoria": "Acessórios de Luxo"},
        "👜 Bolsa Gucci": {"preco": 8500, "categoria": "Acessórios de Luxo"},
        "💍 Anel de Diamante": {"preco": 25000, "categoria": "Joias"},
        "💍 Anel de Ouro": {"preco": 3500, "categoria": "Joias"},
        "💎 Colar de Pérolas": {"preco": 15000, "categoria": "Joias"}
    }
}

# Biblioteca extensa de marcas famosas para detecção de publicidade
FAMOUS_BRANDS = [
    # Tecnologia
    "Apple", "Microsoft", "Google", "Samsung", "Sony", "LG", "Xiaomi", "Huawei", 
    "Intel", "AMD", "NVIDIA", "Tesla", "SpaceX", "Meta", "Facebook", 
    "Twitter", "TikTok", "YouTube", "Netflix", "Amazon", "Spotify", "Discord",
    "WhatsApp", "Telegram", "LinkedIn", "Snapchat", "Pinterest", "Reddit",
    "Adobe", "Oracle", "IBM", "HP", "Dell", "Lenovo", "Asus", "Acer",
    "OnePlus", "Realme", "Oppo", "Vivo", "Motorola", "Nokia", "BlackBerry",
    
    # Esportes e Vestuário
    "Nike", "Adidas", "Puma", "Under Armour", "Reebok", "Converse", "Vans",
    "New Balance", "Jordan", "Supreme", "Off-White", "Balenciaga", "Gucci",
    "Louis Vuitton", "Prada", "Versace", "Armani", "Calvin Klein", "Tommy Hilfiger",
    "Lacoste", "Polo Ralph Lauren", "Hugo Boss", "Diesel", "Levi's", "Gap",
    "H&M", "Zara", "Uniqlo", "Forever 21", "Victoria's Secret", "Chanel",
    
    # Alimentação e Bebidas
    "Coca-Cola", "Pepsi", "McDonald's", "KFC", "Burger King", "Subway",
    "Pizza Hut", "Domino's", "Starbucks", "Red Bull", "Monster Energy",
    "Nestlé", "Ferrero", "Mars", "Hershey's", "Cadbury", "Oreo", "Pringles",
    "Lay's", "Doritos", "Cheetos", "Skittles", "M&M's", "Snickers",
    "Kit Kat", "Nutella", "Kinder", "Heinz", "Ketchup", "Maggi",
    
    # Automóveis
    "Toyota", "Ford", "Chevrolet", "BMW", "Mercedes-Benz", "Audi", "Volkswagen",
    "Honda", "Nissan", "Hyundai", "Kia", "Mazda", "Subaru", "Mitsubishi",
    "Lexus", "Infiniti", "Acura", "Porsche", "Ferrari", "Lamborghini",
    "Bentley", "Rolls-Royce", "Maserati", "Bugatti", "McLaren", "Aston Martin",
    "Jaguar", "Land Rover", "Volvo", "MINI", "Fiat", "Alfa Romeo",
    
    # Cosméticos e Beleza
    "L'Oréal", "Maybelline", "MAC", "Sephora", "Avon", "Revlon", "CoverGirl",
    "Estée Lauder", "Clinique", "Lancôme", "Dior", "Chanel", "YSL", "Fenty Beauty",
    "Rare Beauty", "Glossier", "Urban Decay", "Too Faced", "Benefit", "NARS",
    "Bobbi Brown", "Shiseido", "Kiehl's", "The Body Shop", "Bath & Body Works",
    
    # Varejo e E-commerce
    "Amazon", "eBay", "Alibaba", "Walmart", "Target", "Best Buy", "IKEA",
    "Home Depot", "Costco", "Sears", "Macy's", "Nordstrom", "Zara", "H&M",
    "Forever 21", "Urban Outfitters", "American Eagle", "Hollister", "Abercrombie",
    
    # Entretenimento e Mídia
    "Disney", "Warner Bros", "Universal Studios", "Paramount", "Sony Pictures",
    "Marvel", "DC Comics", "HBO", "Showtime", "ESPN", "CNN", "BBC", "Fox",
    "MTV", "VH1", "Comedy Central", "Cartoon Network", "Nickelodeon",
    
    # Jogos
    "PlayStation", "Xbox", "Nintendo", "Steam", "Epic Games", "Riot Games",
    "Blizzard", "Activision", "EA Games", "Ubisoft", "Rockstar Games",
    "Valve", "Bethesda", "2K Games", "Square Enix", "Capcom", "Konami",
    "Sega", "Bandai Namco", "CD Projekt", "Mojang", "Minecraft", "Fortnite",
    "League of Legends", "World of Warcraft", "Call of Duty", "FIFA", "GTA",
    
    # Bancos e Finanças
    "Visa", "Mastercard", "American Express", "PayPal", "Bitcoin", "Ethereum",
    "JPMorgan Chase", "Bank of America", "Wells Fargo", "Goldman Sachs",
    "Morgan Stanley", "Citibank", "HSBC", "Deutsche Bank", "Credit Suisse",
    
    # Marcas Brasileiras
    "Globo", "SBT", "Record", "Band", "Bradesco", "Itaú", "Banco do Brasil",
    "Caixa", "Santander", "Nubank", "Inter", "C6 Bank", "PicPay", "Mercado Pago",
    "Magazine Luiza", "Casas Bahia", "Lojas Americanas", "Submarino", "Mercado Livre",
    "Natura", "O Boticário", "Avon", "Eudora", "Quem Disse Berenice",
    "Petrobras", "Vale", "JBS", "Ambev", "Braskem", "Embraer",
    "Gol", "Azul", "LATAM", "Uber", "99", "iFood", "Rappi", "Zé Delivery",
    "Ifood", "Magalu", "B2W", "Via Varejo", "Renner", "Riachuelo", "C&A",
    "Hering", "Osklen", "Farm", "Animale", "Shoulder", "Ellus", "Colcci",
    "Havaianas", "Melissa", "Grendha", "Ipanema", "Rider", "Kenner",
    "Guaraná Antarctica", "Brahma", "Skol", "Heineken", "Corona", "Stella Artois",
    "Budweiser", "Sprite", "Fanta", "Schweppes", "Dolly", "Sukita",
    "Shein", "AliExpress", "Shopee", "Wish", "Temu", "Romwe", "Zaful",
    "McDonald", "Burger", "Pizza", "KFC", "Subway", "Coca", "Pepsi",
    
    # Streaming e Entretenimento
    "Netflix", "Amazon Prime", "Disney+", "HBO Max", "Paramount+", "Apple TV+",
    "Hulu", "Peacock", "Discovery+", "Pluto TV", "Tubi", "Crunchyroll",
    "Globoplay", "Telecine", "Paramount+", "Star+", "Claro Video",
    
    # Redes Sociais Adicionais
    "OnlyFans", "Twitch", "Patreon", "Clubhouse", "BeReal", "VSCO",
    "Tumblr", "Flickr", "Vimeo", "Dailymotion", "WeChat", "Line",
    
    # Marcas de Luxo
    "Rolex", "Cartier", "Tiffany & Co", "Bulgari", "Hermès", "Burberry",
    "Moschino", "Dolce & Gabbana", "Saint Laurent", "Givenchy", "Valentino",
    "Tom Ford", "Bottega Veneta", "Celine", "Loewe", "Jacquemus"
]

def save_user_data():
    """Salva os dados dos usuários no MongoDB"""
    try:
        if db is None:
            print("❌ MongoDB não conectado - salvamento cancelado")
            return
        
        collection = db.user_data
        
        if user_data:
            # Salva cada usuário individualmente usando discord_id como chave primária
            documents_saved = 0
            for user_id, data in user_data.items():
                try:
                    # Cria documento com discord_id como _id
                    doc = data.copy()
                    doc['_id'] = user_id  # Usa discord_id como _id principal
                    doc['updated_at'] = datetime.datetime.utcnow()
                    
                    # Usa upsert para evitar conflitos
                    result = collection.replace_one(
                        {'_id': user_id}, 
                        doc, 
                        upsert=True
                    )
                    
                    documents_saved += 1
                    username = data.get('username', 'sem_nome')
                    followers = data.get('followers', 0)
                    print(f"💾 Salvou: {user_id} -> @{username} ({followers} seguidores)")
                    
                except Exception as doc_error:
                    print(f"❌ Erro ao salvar usuário {user_id}: {doc_error}")
                    continue
            
            print(f"✅ MongoDB: {documents_saved}/{len(user_data)} usuários salvos com sucesso!")
            
            # Confirma dados salvos
            saved_count = collection.count_documents({})
            print(f"🔍 Total no MongoDB: {saved_count} documentos")
            
        else:
            print("⚠️ Nenhum dado de usuário para salvar")
        
    except Exception as e:
        print(f"❌ Erro geral no save_user_data: {str(e)}")
        import traceback
        traceback.print_exc()

def save_follow_data():
    """Salva os dados de relacionamentos no MongoDB"""
    try:
        if db is None:
            print("❌ Conexão com MongoDB não estabelecida")
            return
        
        collection = db.follow_data
        collection.delete_many({})
        
        if follow_data:
            documents = []
            for user_id, data in follow_data.items():
                doc = data.copy()
                doc['_id'] = user_id
                doc['updated_at'] = datetime.datetime.utcnow()
                documents.append(doc)
            
            collection.insert_many(documents)
        
        print(f"✅ Dados de relacionamentos salvos no MongoDB! Total: {len(follow_data)}")
    except Exception as e:
        print(f"❌ Erro ao salvar dados de relacionamentos no MongoDB: {e}")

def save_reset_data():
    """Salva os dados de resets no MongoDB"""
    try:
        if db is None:
            return
        
        collection = db.reset_data
        collection.delete_many({})
        
        if reset_data:
            documents = []
            for user_id, used in reset_data.items():
                documents.append({
                    '_id': user_id,
                    'used_reset': used,
                    'updated_at': datetime.datetime.utcnow()
                })
            
            collection.insert_many(documents)
        
        print(f"✅ Dados de reset salvos no MongoDB! Total: {len(reset_data)}")
    except Exception as e:
        print(f"❌ Erro ao salvar dados de reset no MongoDB: {e}")

def save_economy_data():
    """Salva os dados de economia no MongoDB"""
    try:
        if db is None or not economy_data:
            return
        
        collection = db.economy_data
        collection.delete_many({})
        
        documents = []
        for user_id, data in economy_data.items():
            doc = data.copy()
            doc['_id'] = user_id
            doc['updated_at'] = datetime.datetime.utcnow()
            documents.append(doc)
        
        collection.insert_many(documents)
    except Exception as e:
        pass  # Silencioso

def save_brand_posts_data():
    """Salva os dados de posts com marcas no MongoDB"""
    try:
        if db is None:
            return
        
        collection = db.brand_posts_data
        collection.delete_many({})
        
        if brand_posts_data:
            documents = []
            for user_id, posts in brand_posts_data.items():
                documents.append({
                    '_id': user_id,
                    'posts': posts,
                    'updated_at': datetime.datetime.utcnow()
                })
            
            collection.insert_many(documents)
        
        print(f"✅ Dados de posts com marcas salvos no MongoDB! Total: {len(brand_posts_data)}")
    except Exception as e:
        print(f"❌ Erro ao salvar dados de posts no MongoDB: {e}")

def save_inventory_data():
    """Salva os dados de inventário no MongoDB"""
    try:
        if db is None:
            return
        
        collection = db.inventory_data
        collection.delete_many({})
        
        if inventory_data:
            documents = []
            for user_id, data in inventory_data.items():
                doc = data.copy()
                doc['_id'] = user_id
                doc['updated_at'] = datetime.datetime.utcnow()
                documents.append(doc)
            
            collection.insert_many(documents)
        
        print(f"✅ Dados de inventário salvos no MongoDB! Total: {len(inventory_data)}")
    except Exception as e:
        print(f"❌ Erro ao salvar dados de inventário no MongoDB: {e}")

def load_user_data():
    """Carrega os dados dos usuários do MongoDB"""
    global user_data
    try:
        if db is None:
            print("❌ MongoDB não conectado - carregamento cancelado")
            user_data = {}
            return
        
        collection = db.user_data
        document_count = collection.count_documents({})
        print(f"🔍 MongoDB: Encontrados {document_count} documentos na coleção user_data")
        
        documents = collection.find({})
        
        user_data = {}
        loaded_count = 0
        
        for doc in documents:
            try:
                discord_id = doc['_id']  # Agora _id é sempre discord_id
                
                # Remove campos do MongoDB antes de salvar na memória
                doc_clean = doc.copy()
                doc_clean.pop('_id', None)
                doc_clean.pop('updated_at', None)
                
                user_data[discord_id] = doc_clean
                loaded_count += 1
                
                username = doc_clean.get('username', 'sem_nome')
                followers = doc_clean.get('followers', 0)
                print(f"📥 Carregado: {discord_id} -> @{username} ({followers} seguidores)")
                
            except Exception as doc_error:
                print(f"❌ Erro ao carregar documento: {doc_error}")
                continue
        
        print(f"✅ User data loaded: {loaded_count} users carregados com sucesso")
            
    except Exception as e:
        print(f"❌ Erro ao carregar do MongoDB: {str(e)}")
        import traceback
        traceback.print_exc()
        user_data = {}

def load_follow_data():
    """Carrega os dados de relacionamentos do MongoDB"""
    global follow_data
    try:
        if db is None:
            print("❌ Conexão com MongoDB não estabelecida")
            follow_data = {}
            return
        
        collection = db.follow_data
        documents = collection.find({})
        
        follow_data = {}
        for doc in documents:
            user_id = doc['_id']
            doc.pop('_id', None)
            doc.pop('updated_at', None)
            follow_data[user_id] = doc
        
        print(f"✅ Dados de relacionamentos carregados do MongoDB! Total: {len(follow_data)}")
    except Exception as e:
        print(f"❌ Erro ao carregar dados de relacionamentos do MongoDB: {e}")
        follow_data = {}

def load_reset_data():
    """Carrega os dados de resets do MongoDB"""
    global reset_data
    try:
        if db is None:
            reset_data = {}
            return
        
        collection = db.reset_data
        documents = collection.find({})
        
        reset_data = {}
        for doc in documents:
            user_id = doc['_id']
            reset_data[user_id] = doc.get('used_reset', True)
        
        print(f"✅ Dados de reset carregados do MongoDB! Total: {len(reset_data)}")
    except Exception as e:
        print(f"❌ Erro ao carregar dados de reset do MongoDB: {e}")
        reset_data = {}

def load_economy_data():
    """Carrega os dados de economia do MongoDB"""
    global economy_data
    try:
        if db is None:
            print("❌ Conexão com MongoDB não estabelecida")
            economy_data = {}
            return
        
        collection = db.economy_data
        documents = collection.find({})
        
        economy_data = {}
        for doc in documents:
            user_id = doc['_id']
            doc.pop('_id', None)
            doc.pop('updated_at', None)
            economy_data[user_id] = doc
        
        print(f"✅ Dados de economia carregados do MongoDB! Total: {len(economy_data)}")
    except Exception as e:
        print(f"❌ Erro ao carregar dados de economia do MongoDB: {e}")
        economy_data = {}

def load_brand_posts_data():
    """Carrega os dados de posts com marcas do MongoDB"""
    global brand_posts_data
    try:
        if db is None:
            brand_posts_data = {}
            return
        
        collection = db.brand_posts_data
        documents = collection.find({})
        
        brand_posts_data = {}
        for doc in documents:
            user_id = doc['_id']
            brand_posts_data[user_id] = doc.get('posts', {})
        
        print(f"✅ Dados de posts carregados do MongoDB! Total: {len(brand_posts_data)}")
    except Exception as e:
        print(f"❌ Erro ao carregar dados de posts do MongoDB: {e}")
        brand_posts_data = {}

def load_inventory_data():
    """Carrega os dados de inventário do MongoDB"""
    global inventory_data
    try:
        if db is None:
            inventory_data = {}
            return
        
        collection = db.inventory_data
        documents = collection.find({})
        
        inventory_data = {}
        for doc in documents:
            user_id = doc['_id']
            doc.pop('_id', None)
            doc.pop('updated_at', None)
            inventory_data[user_id] = doc
        
        print(f"✅ Dados de inventário carregados do MongoDB! Total: {len(inventory_data)}")
    except Exception as e:
        print(f"❌ Erro ao carregar dados de inventário do MongoDB: {e}")
        inventory_data = {}

# Configuração do bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='m!', intents=intents)

# --- CONFIGURAÇÕES MODIFICADAS ---

# 1. Emojis que serão adicionados às mensagens
EMOJIS = [
    "<:mxplike1:1381003788135174316>"
]

# 2. IDs dos canais onde o bot deve reagir.
#    O bot SÓ vai funcionar nestes canais.
ALLOWED_CHANNEL_IDS = [
    1375957391706689690,
    1375957390062780604,
    1375957388498047046
]

# --- FIM DAS CONFIGURAÇÕES ---

@bot.event
async def on_ready():
    print(f'✅ {bot.user} está online!')
    print(f'📡 Bot configurado para reagir nos canais: {ALLOWED_CHANNEL_IDS}')
    
    # Inicializa dados globais primeiro
    global user_data, follow_data, reset_data, economy_data, brand_posts_data, inventory_data
    user_data = {}
    follow_data = {}
    reset_data = {}
    economy_data = {}
    brand_posts_data = {}
    inventory_data = {}
    
    # Inicia sistemas em background primeiro (para o bot funcionar imediatamente)
    try:
        rotate_status.start()
        auto_save.start()
        print("✅ Sistemas auxiliares iniciados!")
    except Exception as e:
        print(f"⚠️ Erro sistemas: {e}")
    
    print("🚀 Bot operacional!")
    
    # Conecta MongoDB de forma assíncrona em background (não bloqueia o bot)
    async def connect_mongodb():
        await asyncio.sleep(2)  # Espera 2 segundos antes de tentar
        try:
            print("🔄 Conectando MongoDB em background...")
            if init_mongodb():
                load_user_data()
                load_follow_data()
                load_reset_data()
                load_economy_data()
                load_brand_posts_data()
                load_inventory_data()
                print("✅ MongoDB conectado e dados carregados!")
            else:
                print("⚠️ MongoDB indisponível - usando dados locais")
        except Exception as e:
            print(f"⚠️ Erro MongoDB: {str(e)[:50]} - continuando sem BD")
    
    # Executa conexão MongoDB em background
    asyncio.create_task(connect_mongodb())

@tasks.loop(minutes=3)  # Auto-save a cada 3 minutos (mais frequente)
async def auto_save():
    """Salva automaticamente todos os dados a cada 3 minutos"""
    if db is None:
        return  # Não faz nada se MongoDB não estiver conectado
    
    try:
        save_user_data()
        save_economy_data()
        save_follow_data()
        save_brand_posts_data()
        save_inventory_data()
        save_reset_data()
        print(f"💾 Auto-save executado em {datetime.datetime.now().strftime('%H:%M:%S')}")
    except Exception as e:
        print(f"❌ Erro no auto-save: {e}")

# Sistema de status rotativo com dicas de comandos
from discord.ext import tasks

@tasks.loop(minutes=3)  # Mudou para 3 minutos para reduzir spam
async def rotate_status():
    """Rotaciona o status do bot com dicas de comandos"""
    status_list = [
        "🎯 Use m!ajudainsta para ver comandos!",
        "👤 Use m!perfil para ver seu Instagram!",
        "📊 Use m!seguidores para se registrar!",
        "🏆 Use m!curtidas para ver ranking!",
        "👥 Use m!seguir @usuario para seguir!",
        "📝 Use m!atualizar para editar perfil!",
        "💖 Reaja nas mensagens para curtir!",
        "📱 Simule Instagram no Discord!"
    ]

    import random
    status = random.choice(status_list)
    try:
        await bot.change_presence(
            activity=discord.Game(name=status)
        )
    except Exception as e:
        pass  # Ignora erros de status silenciosamente

@bot.event
async def on_message(message):
    # Ignora mensagens do próprio bot
    if message.author == bot.user:
        return

    # 3. VERIFICA SE A MENSAGEM ESTÁ EM UM CANAL PERMITIDO
    if message.channel.id in ALLOWED_CHANNEL_IDS:
        try:
            # Adiciona cada emoji na ordem especificada
            for emoji in EMOJIS:
                await message.add_reaction(emoji)
            print(f'Emojis adicionados à mensagem de {message.author} no canal #{message.channel.name}')
            
            # SISTEMA DE DETECÇÃO AUTOMÁTICA DE PUBLICIDADE (igual ao m!publi mas automático)
            user_id = str(message.author.id)
            
            # Verifica se o usuário está registrado
            if user_id in user_data:
                message_content = message.content.lower()
                detected_brands = []
                
                # Procura por marcas famosas na mensagem (detecção simplificada e mais eficaz)
                import re
                
                print(f"🔍 Analisando mensagem: '{message.content}'")
                print(f"🔍 Texto em minúsculas: '{message_content}'")
                
                for brand in FAMOUS_BRANDS:
                    brand_lower = brand.lower()
                    
                    # Método mais simples e eficaz - busca direta na string
                    if brand_lower in message_content:
                        # Verifica se não é parte de outra palavra (opcional)
                        # Usa regex simples apenas para verificar se é palavra completa
                        word_pattern = r'\b' + re.escape(brand_lower) + r'\b'
                        
                        # Primeiro tenta match exato (palavra completa)
                        if re.search(word_pattern, message_content, re.IGNORECASE):
                            if brand not in detected_brands:
                                detected_brands.append(brand)
                                print(f"✅ Marca detectada (palavra completa): {brand}")
                        # Se não encontrou como palavra completa, aceita como substring
                        elif brand_lower in message_content:
                            if brand not in detected_brands:
                                detected_brands.append(brand)
                                print(f"✅ Marca detectada (substring): {brand}")
                
                # Log para debug
                print(f"📝 Analisando: {message.author.display_name} ({len(message.content)} chars)")
                print(f"📝 Mensagem completa: '{message.content}'")
                print(f"📝 Usuário registrado: {user_id in user_data}")
                print(f"📝 Marcas detectadas: {detected_brands}")
                print(f"📝 Tamanho da mensagem: {len(message.content)} chars (mínimo: 40)")
                
                # RESPOSTA AUTOMÁTICA IGUAL AO m!publi (sem comando necessário)
                if detected_brands and len(message.content) >= 40:
                    message_id = str(message.id)
                    
                    # Inicializa dados se necessário
                    if user_id not in brand_posts_data:
                        brand_posts_data[user_id] = {}
                    
                    if user_id not in economy_data:
                        economy_data[user_id] = {"money": 0, "fame": 0}
                    
                    # Evita spam - só recompensa uma vez por post
                    if message_id not in brand_posts_data[user_id]:
                        # CÁLCULO DE RECOMPENSAS (igual ao sistema do m!publi)
                        base_money = random.randint(2000, 8000)  # Base melhorada
                        brand_multiplier = len(detected_brands) * 300  # Bônus por marca
                        
                        # Bônus especial por marcas populares
                        premium_brands = ["Apple", "Nike", "Coca-Cola", "Samsung", "Google", "Microsoft", "Amazon"]
                        premium_bonus = sum(500 for brand in detected_brands if brand in premium_brands)
                        
                        total_money = base_money + brand_multiplier + premium_bonus
                        
                        # Fama baseada nos seguidores atuais
                        current_followers = user_data[user_id].get('followers', 0)
                        base_fame = int(current_followers * 0.01)  # 1% dos seguidores
                        
                        # Bônus de fama por múltiplas marcas
                        if len(detected_brands) > 1:
                            base_fame = int(base_fame * (1 + (len(detected_brands) - 1) * 0.15))
                        
                        # Bônus extra para mensagens mais longas (conteúdo de qualidade)
                        if len(message.content) >= 100:
                            length_bonus = int(total_money * 0.2)
                            total_money += length_bonus
                            base_fame = int(base_fame * 1.3)
                        
                        # ATUALIZA OS DADOS
                        economy_data[user_id]["money"] += total_money
                        economy_data[user_id]["fame"] += base_fame
                        user_data[user_id]['followers'] += base_fame  # Seguidores ganhos
                        
                        # Registra o post como recompensado
                        import datetime
                        brand_posts_data[user_id][message_id] = {
                            "brands": detected_brands,
                            "rewarded": True,
                            "timestamp": datetime.datetime.now().isoformat(),
                            "content_preview": message.content[:100],
                            "money_gained": total_money,
                            "fame_gained": base_fame,
                            "is_premium": any(brand in premium_brands for brand in detected_brands)
                        }
                        
                        # Salva tudo
                        save_economy_data()
                        save_user_data()
                        save_brand_posts_data()
                        
                        # RESPOSTA AUTOMÁTICA ESTILIZADA (igual ao m!publi)
                        main_brand = detected_brands[0]
                        is_premium = main_brand in premium_brands
                        
                        embed = discord.Embed(
                            title="🎯 Patrocínio Registrado Automaticamente!" if not is_premium else "⭐ Patrocínio Premium Registrado!",
                            description=f"**{message.author.display_name}** fez uma publicidade para **{main_brand}**{' e outras marcas' if len(detected_brands) > 1 else ''}!\n\n✅ **Patrocínio detectado e registrado com sucesso!**",
                            color=0x00FF00 if not is_premium else 0xFFD700
                        )
                        
                        # Mostra ganhos detalhados
                        money_details = f"**R$ {total_money:,}**".replace(",", ".")
                        if brand_multiplier > 0:
                            money_details += f"\n+R$ {brand_multiplier:,} (bônus marcas)".replace(",", ".")
                        if premium_bonus > 0:
                            money_details += f"\n+R$ {premium_bonus:,} (marcas premium)".replace(",", ".")
                        
                        embed.add_field(
                            name="🤑 Dinheiro Ganho",
                            value=money_details,
                            inline=True
                        )
                        
                        embed.add_field(
                            name="📈 Seguidores Ganhos",
                            value=f"**+{base_fame:,}** seguidores".replace(",", "."),
                            inline=True
                        )
                        
                        # Saldo total atualizado
                        embed.add_field(
                            name="💰 Saldo Total",
                            value=f"💵 R$ {economy_data[user_id]['money']:,}\n👥 {user_data[user_id]['followers']:,} seguidores\n⭐ {economy_data[user_id]['fame']:,} pontos de fama".replace(",", "."),
                            inline=False
                        )
                        
                        # Lista todas as marcas se múltiplas
                        if len(detected_brands) > 1:
                            brands_text = ", ".join(detected_brands)
                            embed.add_field(
                                name="🏷️ Todas as Marcas Detectadas",
                                value=f"{brands_text} ({len(detected_brands)} marcas)",
                                inline=False
                            )
                        
                        # Bônus especiais
                        bonuses = []
                        if len(message.content) >= 100:
                            bonuses.append("📝 Conteúdo longo (+30% bônus)")
                        if is_premium:
                            bonuses.append("⭐ Marca premium detectada")
                        if len(detected_brands) >= 3:
                            bonuses.append("🔥 Múltiplas marcas (+50% fama)")
                            
                        if bonuses:
                            embed.add_field(
                                name="🎉 Bônus Especiais",
                                value="\n".join(bonuses),
                                inline=False
                            )
                        
                        embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1381003788135174316.png")
                        embed.set_footer(
                            text="🤖 Sistema Automático • Patrocínio detectado e registrado instantaneamente!",
                            icon_url=message.author.display_avatar.url
                        )
                        
                        # Responde ao post automaticamente e agenda para deletar em 15 segundos
                        response_message = await message.reply(embed=embed)
                        
                        # Agenda a exclusão da mensagem após 15 segundos
                        async def delete_after_delay():
                            await asyncio.sleep(15)
                            try:
                                await response_message.delete()
                                print(f"💼 Embed de patrocínio deletado automaticamente: {message.author.display_name}")
                            except discord.NotFound:
                                print(f"⚠️ Mensagem já foi deletada: {message.author.display_name}")
                            except discord.Forbidden:
                                print(f"❌ Sem permissão para deletar mensagem: {message.author.display_name}")
                            except Exception as e:
                                print(f"❌ Erro ao deletar embed: {e}")
                        
                        # Executa a função de delay em background
                        asyncio.create_task(delete_after_delay())
                        
                        print(f"💼 Publicidade automática processada: {message.author.display_name} | +R${total_money} +{base_fame} seguidores | Marcas: {detected_brands}")
                    
                    else:
                        print(f"🔄 Post já recompensado: {message.author.display_name}")
                
                # Logs informativos para debug
                elif detected_brands and len(message.content) < 40:
                    print(f"❌ Marcas encontradas mas texto muito curto ({len(message.content)} chars): {message.author.display_name}")
                    print(f"❌ Marcas encontradas: {detected_brands}")
                elif len(message.content) >= 40 and not detected_brands:
                    print(f"ℹ️ Texto longo mas sem marcas: {message.author.display_name}")
                    print(f"ℹ️ Algumas marcas para teste: Nike, Apple, Coca-Cola estão na mensagem? {any(brand.lower() in message_content for brand in ['Nike', 'Apple', 'Coca-Cola'])}")
                elif not detected_brands and len(message.content) < 40:
                    print(f"ℹ️ Mensagem normal: {message.author.display_name}")
                    
                # Teste adicional para debug
                test_brands = ['Nike', 'Apple', 'Coca-Cola', 'Instagram', 'McDonald']
                found_test = [brand for brand in test_brands if brand.lower() in message_content]
                if found_test:
                    print(f"🧪 TESTE: Marcas encontradas manualmente: {found_test}")
                    
        except discord.HTTPException as e:
            # Este erro pode acontecer se o bot não tiver acesso ao emoji (não está no servidor)
            # ou não tiver permissão para adicionar reações.
            print(f'Erro ao adicionar emoji: {e}')
        except Exception as e:
            print(f'Erro inesperado: {e}')

    # Processa outros comandos do bot (como m!teste) em qualquer canal
    await bot.process_commands(message)

@bot.event
async def on_reaction_add(reaction, user):
    """Rastreia quando alguém adiciona uma reação"""
    # Ignora reações do próprio bot
    if user == bot.user:
        return

    # Verifica se a reação é um dos emojis do Instagram
    if str(reaction.emoji) in EMOJIS:
        # Pega o ID do autor da mensagem original
        message_author_id = str(reaction.message.author.id)

        # Inicializa dados do usuário se não existir
        if message_author_id not in user_data:
            user_data[message_author_id] = {
                'username': None,
                'total_likes': 0,
                'posts_count': 0,
                'followers': 0,
                'profession': None,
                'thumbnail_url': None,
                'embed_image_url': None
            }

        # Adiciona uma curtida
        user_data[message_author_id]['total_likes'] += 1

        # Verifica se a curtida foi no canal específico (1375957388498047046)
        if reaction.message.channel.id == 1375957388498047046:
            current_followers = user_data[message_author_id]['followers']
            
            # Calcula 0.5% dos seguidores atuais
            if current_followers > 0:
                followers_gain = int(current_followers * 0.005)  # 0.5% = 0.005
                
                # Adiciona os seguidores ganhos
                user_data[message_author_id]['followers'] += followers_gain
                
                print(f"🎉 {reaction.message.author} ganhou {followers_gain:,} seguidores! (0.5% de {current_followers:,})")
                print(f"   Total de seguidores agora: {user_data[message_author_id]['followers']:,}")

        # Salva os dados imediatamente
        save_user_data()
        print(f"💾 Curtida salva no MongoDB para {reaction.message.author}")

        print(f"Curtida adicionada para {reaction.message.author}. Total: {user_data[message_author_id]['total_likes']}")

@bot.event
async def on_reaction_remove(reaction, user):
    """Rastreia quando alguém remove uma reação"""
    # Ignora reações do próprio bot
    if user == bot.user:
        print(f"Ignorando remoção de reação do próprio bot")
        return

    # Verifica se a mensagem está em um canal permitido
    if reaction.message.channel.id not in ALLOWED_CHANNEL_IDS:
        print(f"Reação removida em canal não permitido: #{reaction.message.channel.name}")
        return

    print(f"🔍 Reação removida detectada: {reaction.emoji} por {user} na mensagem de {reaction.message.author}")

    # Verifica se a reação é um dos emojis do Instagram
    if str(reaction.emoji) in EMOJIS:
        # Pega o ID do autor da mensagem original
        message_author_id = str(reaction.message.author.id)

        print(f"✅ Emoji válido detectado. Processando remoção para usuário ID: {message_author_id}")

        # Se o usuário existe nos dados
        if message_author_id in user_data:
            likes_antes = user_data[message_author_id]['total_likes']

            # Remove uma curtida (mínimo 0)
            user_data[message_author_id]['total_likes'] = max(0, user_data[message_author_id]['total_likes'] - 1)

            # Verifica se a curtida removida foi no canal específico (1375957388498047046)
            if reaction.message.channel.id == 1375957388498047046:
                current_followers = user_data[message_author_id]['followers']
                
                # Calcula 0.5% dos seguidores atuais para remover
                if current_followers > 0:
                    followers_loss = int(current_followers * 0.005)  # 0.5% = 0.005
                    
                    # Remove os seguidores (mínimo 0)
                    user_data[message_author_id]['followers'] = max(0, user_data[message_author_id]['followers'] - followers_loss)
                    
                    print(f"📉 {reaction.message.author} perdeu {followers_loss:,} seguidores pela remoção da curtida!")
                    print(f"   Total de seguidores agora: {user_data[message_author_id]['followers']:,}")

            likes_depois = user_data[message_author_id]['total_likes']

            # Salva os dados
            save_user_data()

            print(f"✅ Curtida removida de {reaction.message.author.display_name}!")
            print(f"   Likes antes: {likes_antes} → Likes depois: {likes_depois}")
            print(f"   Total atual: {user_data[message_author_id]['total_likes']} curtidas")
        else:
            print(f"❌ Tentativa de remover curtida de usuário não registrado: {reaction.message.author.display_name} (ID: {message_author_id})")
    else:
        print(f"❌ Reação removida não é do tipo Instagram: {reaction.emoji}")

# Comando de teste
@bot.command(name='teste')
async def teste(ctx):
    await ctx.reply('Bot está funcionando!')

# Comando de seguidores do Instagram
@bot.command(name='seguidores')
async def seguidores(ctx):
    user_id = str(ctx.author.id)

    # Inicializa dados do usuário se não existir
    if user_id not in user_data:
        user_data[user_id] = {
            'username': None,
            'total_likes': 0,
            'posts_count': 0,
            'followers': 0,
            'profession': None,
            'thumbnail_url': None,
            'embed_image_url': None
        }

    # Verifica se o usuário já tem seguidores (já usou o comando)
    if user_data[user_id]['followers'] > 0:
        followers_atual = user_data[user_id]['followers']
        followers_formatado = f"{followers_atual:,}".replace(",", ".")

        embed = discord.Embed(
            title="❌ Comando já utilizado!",
            description=f"Você já possui **{followers_formatado}** seguidores permanentes.",
            color=0xFF0000
        )
        embed.add_field(
            name="ℹ️ Informação",
            value="O comando `m!seguidores` só pode ser usado uma vez por pessoa.",
            inline=False
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        embed.set_footer(text=f"Solicitado por {ctx.author.display_name}")

        await ctx.reply(embed=embed)
        return

    # ID do dono do bot (substitua pelo seu ID do Discord)
    OWNER_ID = "983196900910039090"  # Substitua pelo seu ID do Discord
    
    # ID especial que sempre terá 2 seguidores
    SPECIAL_ID = "1380743682944139265"

    # Verifica se é o dono do bot
    if user_id == OWNER_ID:
        num_seguidores = 250000000  # 25 milhões fixos para o dono
        # Define curtidas e dados especiais para o owner
        user_data[user_id]['total_likes'] = 15000  # 15k curtidas fixas
    elif user_id == SPECIAL_ID:
        num_seguidores = 120000000  # Sempre 2 seguidores para este ID específico
    else:
        # Gera número aleatório de seguidores entre 20.000 e 2.000.000
        num_seguidores = random.randint(20000, 2000000)

    # Salva o número de seguidores para o usuário
    user_data[user_id]['followers'] = num_seguidores
    user_data[user_id]['username'] = ctx.author.display_name  # Garante que username está definido
    
    print(f"🔍 DEBUG: Salvando usuário {user_id} com {num_seguidores} seguidores e username '{ctx.author.display_name}'")
    save_user_data()
    print(f"💾 Dados de registro salvos para: {ctx.author.display_name}")

    # Calcula pontos de fama por like baseado na quantidade de seguidores
    if user_id == SPECIAL_ID:
        pontos_por_like = 1  # Pontos muito baixos para quem tem apenas 2 seguidores
    elif num_seguidores >= 800000:
        pontos_por_like = random.randint(80, 100)
    elif num_seguidores >= 600000:
        pontos_por_like = random.randint(60, 79)
    elif num_seguidores >= 400000:
        pontos_por_like = random.randint(45, 59)
    elif num_seguidores >= 200000:
        pontos_por_like = random.randint(30, 44)
    elif num_seguidores >= 100000:
        pontos_por_like = random.randint(20, 29)
    elif num_seguidores >= 50000:
        pontos_por_like = random.randint(15, 19)
    else:
        pontos_por_like = random.randint(10, 14)

    # Formata o número de seguidores com pontos
    seguidores_formatado = f"{num_seguidores:,}".replace(",", ".")

    # Define o username automaticamente como o display name do Discord
    user_data[user_id]['username'] = ctx.author.display_name

    # Verifica níveis de verificação baseado nos seguidores
    username_display = ctx.author.display_name
    if user_id == OWNER_ID:
        username_display = f"{username_display} <:extremomxp:1387842927602172125>"
    elif user_id == SPECIAL_ID:
        username_display = f"{username_display}"  # Sem verificação para quem tem apenas 2 seguidores
    elif num_seguidores >= 1000000:
        username_display = f"{username_display} <:abudabimxp:1387843390506405922>"
    elif num_seguidores >= 500000:
        username_display = f"{username_display} <:verificadomxp:1387605173886783620>"
    else:
        username_display = f"{username_display} <:verificiadinmxp:1387842858912055428>"

    # Cria o embed
    embed = discord.Embed(
        title="📊 Estatísticas do Instagram",
        description=f"Informações do perfil de {username_display}",
        color=0xE4405F  # Cor do Instagram
    )

    embed.add_field(
        name=f"<:membromxp:1384773599046537257> Seguidores",
        value=f"**{seguidores_formatado}** seguidores",
        inline=False
    )

    embed.add_field(
        name="⭐ Pontos de Fama por Like",
        value=f"**{pontos_por_like}** pontos por like",
        inline=False
    )

    # Adiciona informação extra baseada na quantidade de seguidores
    if num_seguidores >= 25000000:
        status = "👑 **DONO DO BOT!** Perfil supremo!"
    elif user_id == SPECIAL_ID:
        status = "😅 **PERFIL ESPECIAL!** Começando humildemente!"
    elif num_seguidores >= 800000:
        status = "🔥 **MEGA VIRAL!** Perfil lendário!"
    elif num_seguidores >= 500000:
        status = "✅ **VERIFICADO!** Perfil oficial!"
    elif num_seguidores >= 200000:
        status = "🚀 **VIRAL!** Perfil em alta!"
    elif num_seguidores >= 100000:
        status = "📈 **CRESCENDO RAPIDAMENTE!**"
    elif num_seguidores >= 50000:
        status = "⭐ **BOM CRESCIMENTO!**"
    else:
        status = "🌱 **INICIANTE PROMISSOR!**"

    embed.add_field(
        name="📊 Status",
        value=status,
        inline=False
    )

    embed.set_footer(text=f"Comandado por {ctx.author.display_name}")
    embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/thumb/a/a5/Instagram_icon.png/1024px-Instagram_icon.png")

    print(f"✅ Seguidores salvos para {ctx.author.display_name}: {num_seguidores}")

    view = ProfileView(user_id, ctx.author)
    await ctx.reply(embed=embed, view=view)



# Comando de perfil
@bot.command(name='perfil')
async def perfil(ctx, member: discord.Member = None):
    # Se não especificar membro, mostra o próprio perfil
    if member is None:
        member = ctx.author

    user_id = str(member.id)

    # Verifica se o usuário tem dados
    if user_id not in user_data:
        if member == ctx.author:
            embed = discord.Embed(
                title="❌ Registro Necessário",
                description="Você precisa se registrar antes de usar o perfil!",
                color=0xFF0000
            )
            embed.add_field(
                name="📝 Como se registrar:",
                value="Use o comando `m!seguidores` para criar seu perfil",
                inline=False
            )
            await ctx.reply(embed=embed)
        else:
            await ctx.reply(f"❌ {member.display_name} ainda não se registrou!")
        return

    # Se chegou até aqui, o usuário está registrado e tem username
    user_info = user_data[user_id]
    username = user_info['username']
    total_likes = user_info.get('total_likes', 0)
    followers = user_info.get('followers', 0)

    # Adiciona verificação baseada nos níveis de seguidores
    username_display = username
    if user_id == "983196900910039090":  # Owner ID
        username_display = f"{username} <:extremomxp:1387842927602172125>"
    elif followers >= 1000000:
        username_display = f"{username} <:abudabimxp:1387843390506405922>"
    elif followers >= 500000:
        username_display = f"{username} <:verificadomxp:1387605173886783620>"
    else:
        username_display = f"{username} <:verificiadinmxp:1387842858912055428>"

    # Calcula level baseado nas curtidas (especial para o owner)
    if user_id == "983196900910039090":  # Owner ID
        level = 500  # Level fixo 500 para o dono
        status = "👑 **LENDA GLOBAL!**"
        cor = user_info.get('profile_color', 0xFFD700)  # Usa cor personalizada ou dourado para lenda
    else:
        level = min(total_likes // 10, 100)  # 1 level a cada 10 curtidas, máximo 100
        
        # Define status baseado nas curtidas
        if total_likes >= 500:
            status = "🔥 **INFLUENCER!**"
        elif total_likes >= 200:
            status = "⭐ **POPULAR!**"
        elif total_likes >= 100:
            status = "📈 **EM ALTA!**"
        elif total_likes >= 50:
            status = "🌟 **CRESCENDO!**"
        else:
            status = "🌱 **INICIANTE**"
        
        # Usa cor personalizada do usuário ou cor padrão
        cor = user_info.get('profile_color', 0x9932CC)

    # Cria o embed do perfil
    embed = discord.Embed(
        title=f"📱 Perfil do Instagram",
        description=f"Perfil de **{username_display}**",
        color=cor
    )

    embed.add_field(
        name="👤 Nome de Usuário",
        value=f"@{username_display}",
        inline=True
    )

    embed.add_field(
        name=f"<:mxplike1:1381003788135174316> Total de Curtidas",
        value=f"**{total_likes:,}** curtidas".replace(",", "."),
        inline=True
    )

    embed.add_field(
        name="<:coroamxp:1376731577106567319> Level",
        value=f"**Level {level}**",
        inline=True
    )

    # Adiciona campo de profissão se existir
    profession = user_info.get('profession')
    if profession:
        embed.add_field(
            name="<:profmxp:1387539539169509456> Profissão",
            value=f"**{profession}**",
            inline=True
        )

    # Adiciona badge se existir
    profile_badge = user_info.get('profile_badge')
    if profile_badge:
        badge_names = {
            "gamer": "🎮 Gamer", "artista": "🎨 Artista", "estudante": "📚 Estudante",
            "trabalhador": "💼 Trabalhador", "streamer": "🌟 Streamer", "musico": "🎵 Músico",
            "fotografo": "📷 Fotógrafo", "esportista": "⚽ Esportista", "foodie": "🍕 Foodie", "viajante": "🌍 Viajante"
        }
        badge_name = badge_names.get(profile_badge, "🏆 Especial")
        embed.add_field(
            name="🏆 Badge",
            value=f"**{badge_name}**",
            inline=True
        )

    # Adiciona campo de seguidores se existir
    followers = user_info.get('followers', 0)
    if followers > 0:
        followers_formatado = f"{followers:,}".replace(",", ".")
        embed.add_field(
            name=f"<:membromxp:1384773599046537257> Seguidores",
            value=f"**{followers_formatado}** seguidores",
            inline=True
        )

    # Adiciona campo de seguidores reais (famosos)
    real_followers = follow_data.get(user_id, {}).get("followers", [])
    real_followers_count = len(real_followers)
    embed.add_field(
        name=f"<:reaismxp:1387842813084831936> Seguidores Famosos",
        value=f"**{real_followers_count}** seguidores reais",
        inline=True
    )

    # Adiciona bio se existir
    bio = user_info.get('bio')
    if bio:
        embed.add_field(
            name="📝 Bio",
            value=f"*{bio}*",
            inline=False
        )

    # Adiciona status se existir
    status = user_info.get('status')
    if status:
        embed.add_field(
            name="💫 Status",
            value=f"**{status}**",
            inline=False
        )

    # Adiciona links sociais se existirem
    social_links = user_info.get('social_links', {})
    if any(social_links.values()):
        links_text = ""
        if social_links.get('instagram'): 
            links_text += f"📷 **Instagram:** {social_links['instagram']}\n"
        if social_links.get('youtube'): 
            links_text += f"<:youtubemxp:1388210526202495116> **YouTube:** {social_links['youtube']}\n"
        if social_links.get('tiktok'): 
            links_text += f"<:mxptiktok:1381007602892275824> **TikTok:** {social_links['tiktok']}\n"
        
        if links_text:
            embed.add_field(
                name="🔗 Links Sociais",
                value=links_text.strip(),
                inline=False
            )

    embed.add_field(
        name=f"<:mxpinstagram:1381002235462287452> Status",
        value=status,
        inline=False
    )

    # Adiciona barra de progresso para o próximo level (não para o owner)
    if user_id != "983196900910039090":  # Não mostra progresso para o owner (já é level máximo)
        progress_to_next = (total_likes % 10) * 10  # Porcentagem para próximo level
        progress_bar = "▓" * (progress_to_next // 10) + "░" * (10 - (progress_to_next // 10))

        embed.add_field(
            name="📈 Progresso para próximo level",
            value=f"`{progress_bar}` {total_likes % 10}/10",
            inline=False
        )
    else:
        embed.add_field(
            name="👑 Status de Lenda",
            value="**Level máximo atingido!** Você é uma lenda no Instagram MXP!",
            inline=False
        )

    # Define thumbnail (personalizada ou avatar padrão)
    thumbnail_url = user_info.get('thumbnail_url')
    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)
    else:
        embed.set_thumbnail(url=member.display_avatar.url)

    # Define imagem do embed se personalizada
    embed_image_url = user_info.get('embed_image_url')
    if embed_image_url:
        embed.set_image(url=embed_image_url)

    # Footer com informações extras
    if member == ctx.author:
        footer_text = f"ID: {member.id} • Use m!atualizar para editar nome/profissão"
    else:
        footer_text = f"ID: {member.id} • Perfil visualizado por {ctx.author.display_name}"

    embed.set_footer(
        text=footer_text,
        icon_url=ctx.author.display_avatar.url
    )

    view = ProfileView(user_id, member)
    await ctx.reply(embed=embed, view=view)

# Comando para ver ranking de curtidas
@bot.command(name='curtidas')
async def curtidas(ctx):
    # Ordena usuários por curtidas
    sorted_users = sorted(user_data.items(), key=lambda x: x[1]['total_likes'], reverse=True)

    if not sorted_users:
        await ctx.reply("❌ Nenhum usuário encontrado no ranking!")
        return

    embed = discord.Embed(
        title="🏆 Ranking de Curtidas",
        description="Top usuários com mais curtidas",
        color=0xFFD700
    )

    # Mostra top 10
    for i, (user_id, data) in enumerate(sorted_users[:10]):
        try:
            user = bot.get_user(int(user_id))
            username = data.get('username', 'Sem nome')
            likes = data.get('total_likes', 0)

            if user:
                if i == 0:
                    medal = "🥇"
                elif i == 1:
                    medal = "🥈"
                elif i == 2:
                    medal = "🥉"
                else:
                    medal = f"{i+1}º"

                embed.add_field(
                    name=f"{medal} @{username}",
                    value=f"<:mxplike1:1381003788135174316> **{likes:,}** curtidas".replace(",", "."),
                    inline=False
                )
        except:
            continue

    await ctx.reply(embed=embed)

# Comando para migrar dados JSON para MongoDB (apenas para o dono)
@bot.command(name='migrar_dados')
async def migrar_dados(ctx):
    # Só o dono do bot pode usar
    if str(ctx.author.id) != "983196900910039090":
        await ctx.reply("❌ Apenas o dono do bot pode usar este comando!")
        return
    
    if db is None:
        await ctx.reply("❌ Conexão com MongoDB não estabelecida!")
        return
    
    embed = discord.Embed(
        title="🔄 Migrando Dados para MongoDB",
        description="Iniciando migração dos arquivos JSON...",
        color=0xFFD700
    )
    await ctx.reply(embed=embed)
    
    try:
        # Carrega dados dos arquivos JSON existentes
        migrated_collections = []
        
        # Migra user_data
        try:
            with open('user_data.json', 'r') as f:
                json_user_data = json.load(f)
            if json_user_data:
                collection = db.user_data
                collection.delete_many({})
                documents = []
                for user_id, data in json_user_data.items():
                    doc = data.copy()
                    doc['_id'] = user_id
                    doc['migrated_at'] = datetime.datetime.utcnow()
                    documents.append(doc)
                collection.insert_many(documents)
                migrated_collections.append(f"✅ user_data: {len(documents)} documentos")
        except FileNotFoundError:
            migrated_collections.append("⚠️ user_data: arquivo não encontrado")
        except Exception as e:
            migrated_collections.append(f"❌ user_data: erro - {str(e)[:50]}")
        
        # Migra economy_data
        try:
            with open('economy_data.json', 'r') as f:
                json_economy_data = json.load(f)
            if json_economy_data:
                collection = db.economy_data
                collection.delete_many({})
                documents = []
                for user_id, data in json_economy_data.items():
                    doc = data.copy()
                    doc['_id'] = user_id
                    doc['migrated_at'] = datetime.datetime.utcnow()
                    documents.append(doc)
                collection.insert_many(documents)
                migrated_collections.append(f"✅ economy_data: {len(documents)} documentos")
        except FileNotFoundError:
            migrated_collections.append("⚠️ economy_data: arquivo não encontrado")
        except Exception as e:
            migrated_collections.append(f"❌ economy_data: erro - {str(e)[:50]}")
        
        # Migra follow_data
        try:
            with open('follow_data.json', 'r') as f:
                json_follow_data = json.load(f)
            if json_follow_data:
                collection = db.follow_data
                collection.delete_many({})
                documents = []
                for user_id, data in json_follow_data.items():
                    doc = data.copy()
                    doc['_id'] = user_id
                    doc['migrated_at'] = datetime.datetime.utcnow()
                    documents.append(doc)
                collection.insert_many(documents)
                migrated_collections.append(f"✅ follow_data: {len(documents)} documentos")
        except FileNotFoundError:
            migrated_collections.append("⚠️ follow_data: arquivo não encontrado")
        except Exception as e:
            migrated_collections.append(f"❌ follow_data: erro - {str(e)[:50]}")
        
        # Migra outros dados...
        # (brand_posts_data, inventory_data, etc.)
        
        # Recarrega dados do MongoDB
        load_user_data()
        load_economy_data()
        load_follow_data()
        load_brand_posts_data()
        load_inventory_data()
        load_reset_data()
        
        success_embed = discord.Embed(
            title="✅ Migração Concluída!",
            description="Dados migrados do JSON para MongoDB com sucesso!",
            color=0x00FF00
        )
        
        success_embed.add_field(
            name="📊 Resultado da Migração",
            value="\n".join(migrated_collections),
            inline=False
        )
        
        success_embed.add_field(
            name="🔄 Dados Recarregados",
            value=f"👥 {len(user_data)} usuários\n💰 {len(economy_data)} economias\n🤝 {len(follow_data)} relacionamentos",
            inline=False
        )
        
        success_embed.set_footer(text="Migração realizada com sucesso!")
        await ctx.reply(embed=success_embed)
        
    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Erro na Migração",
            description=f"Ocorreu um erro durante a migração: {str(e)}",
            color=0xFF0000
        )
        await ctx.reply(embed=error_embed)



# Comando para seguir usuário
@bot.command(name='seguir')
async def seguir(ctx, member: discord.Member = None):
    if member is None:
        embed = discord.Embed(
            title="❌ Erro",
            description="Você precisa mencionar um usuário para seguir!",
            color=0xFF0000
        )
        embed.add_field(
            name="📝 Uso correto:",
            value="`m!seguir @usuario`",
            inline=False
        )
        await ctx.reply(embed=embed)
        return

    follower_id = str(ctx.author.id)
    followed_id = str(member.id)

    # Não pode seguir a si mesmo
    if follower_id == followed_id:
        embed = discord.Embed(
            title="❌ Ação inválida",
            description="Você não pode seguir a si mesmo!",
            color=0xFF0000
        )
        await ctx.reply(embed=embed)
        return

    # Verifica se ambos os usuários estão registrados
    if follower_id not in user_data:
        embed = discord.Embed(
            title="❌ Registro necessário",
            description="Você precisa se registrar primeiro!",
            color=0xFF0000
        )
        embed.add_field(
            name="📝 Como se registrar:",
            value="Use o comando `m!seguidores` para criar seu perfil",
            inline=False
        )
        await ctx.reply(embed=embed)
        return

    if followed_id not in user_data:
        embed = discord.Embed(
            title="❌ Usuário não registrado",
            description=f"{member.display_name} ainda não se registrou!",
            color=0xFF0000
        )
        await ctx.reply(embed=embed)
        return

    # Inicializa dados de relacionamento se não existir
    if follower_id not in follow_data:
        follow_data[follower_id] = {"following": [], "followers": []}
    if followed_id not in follow_data:
        follow_data[followed_id] = {"following": [], "followers": []}

    # Verifica se já segue
    if followed_id in follow_data[follower_id]["following"]:
        embed = discord.Embed(
            title="❌ Já seguindo",
            description=f"Você já segue {member.display_name}!",
            color=0xFF0000
        )
        await ctx.reply(embed=embed)
        return

    # Adiciona o relacionamento
    follow_data[follower_id]["following"].append(followed_id)
    follow_data[followed_id]["followers"].append(follower_id)

    save_follow_data()

    # RECOMPENSA ESPECIAL: Se seguiu o dono do bot, ganha 250k seguidores
    followers_bonus = 0
    if followed_id == "983196900910039090":  # ID do dono do bot
        followers_bonus = 250000
        user_data[follower_id]['followers'] += followers_bonus
        save_user_data()
        print(f"🎉 RECOMPENSA ESPECIAL: {ctx.author.display_name} ganhou {followers_bonus:,} seguidores por seguir o dono!")

    # Verifica se agora são amigos mútuos (se seguem mutuamente)
    is_mutual = followed_id in follow_data[follower_id]["following"] and follower_id in follow_data[followed_id]["following"]

    if followers_bonus > 0:
        # Embed especial para quem seguiu o dono do bot
        embed = discord.Embed(
            title="👑 RECOMPENSA ESPECIAL DO DONO!",
            description=f"**{ctx.author.display_name}** seguiu o **Dono do Bot** e recebeu uma recompensa épica!",
            color=0xFFD700  # Dourado para recompensa especial
        )
        embed.add_field(
            name="🎉 Recompensa Obtida",
            value=f"**+{followers_bonus:,}** seguidores extras por seguir o dono!".replace(",", "."),
            inline=False
        )
        embed.add_field(
            name="👑 Status Especial",
            value="Você agora faz parte do círculo VIP do dono do bot!",
            inline=False
        )
        embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1387842927602172125.png")
    elif is_mutual:
        # Embed especial para amigos mútuos
        embed = discord.Embed(
            title="🤝 Vocês agora são amigos!",
            description=f"**{ctx.author.display_name}** e **{member.display_name}** agora se seguem mutuamente!",
            color=0xFF69B4  # Rosa para amizade
        )
        embed.add_field(
            name="💕 Amizade Confirmada",
            value="Vocês dois se seguem mutuamente e agora são amigos no Instagram!",
            inline=False
        )
        embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1387605173886783620.png")  # Emoji de coração ou amizade
    else:
        # Embed normal
        embed = discord.Embed(
            title="✅ Agora seguindo!",
            description=f"Você agora segue **{member.display_name}**!",
            color=0x00FF00
        )
        embed.set_thumbnail(url=member.display_avatar.url)

    # Estatísticas atualizadas incluindo a recompensa
    stats_text = f"Você segue **{len(follow_data[follower_id]['following'])}** pessoas\n{member.display_name} tem **{len(follow_data[followed_id]['followers'])}** seguidores"
    
    if followers_bonus > 0:
        current_followers = user_data[follower_id]['followers']
        stats_text += f"\n\n🎉 **Seus seguidores agora:** {current_followers:,}".replace(",", ".")
        stats_text += f"\n👑 **Recompensa especial:** +{followers_bonus:,} seguidores!".replace(",", ".")
    
    embed.add_field(
        name="📊 Estatísticas:",
        value=stats_text,
        inline=False
    )
    embed.set_footer(text=f"Comando usado por {ctx.author.display_name}")

    await ctx.reply(embed=embed)

# Comando para deixar de seguir usuário
@bot.command(name='desseguir')
async def desseguir(ctx, member: discord.Member = None):
    if member is None:
        embed = discord.Embed(
            title="❌ Erro",
            description="Você precisa mencionar um usuário para deixar de seguir!",
            color=0xFF0000
        )
        embed.add_field(
            name="📝 Uso correto:",
            value="`m!desseguir @usuario`",
            inline=False
        )
        await ctx.reply(embed=embed)
        return

    follower_id = str(ctx.author.id)
    followed_id = str(member.id)

    # Não pode deixar de seguir a si mesmo
    if follower_id == followed_id:
        embed = discord.Embed(
            title="❌ Ação inválida",
            description="Você não pode deixar de seguir a si mesmo!",
            color=0xFF0000
        )
        await ctx.reply(embed=embed)
        return

    # Verifica se o usuário está registrado
    if follower_id not in user_data:
        embed = discord.Embed(
            title="❌ Registro necessário",
            description="Você precisa se registrar primeiro!",
            color=0xFF0000
        )
        embed.add_field(
            name="📝 Como se registrar:",
            value="Use o comando `m!seguidores` para criar seu perfil",
            inline=False
        )
        await ctx.reply(embed=embed)
        return

    # Verifica se tem dados de relacionamento
    if follower_id not in follow_data or followed_id not in follow_data[follower_id]["following"]:
        embed = discord.Embed(
            title="❌ Não está seguindo",
            description=f"Você não segue {member.display_name}!",
            color=0xFF0000
        )
        await ctx.reply(embed=embed)
        return

    # Remove o relacionamento
    follow_data[follower_id]["following"].remove(followed_id)
    if followed_id in follow_data:
        if follower_id in follow_data[followed_id]["followers"]:
            follow_data[followed_id]["followers"].remove(follower_id)

    save_follow_data()

    # Embed de sucesso
    embed = discord.Embed(
        title="✅ Deixou de seguir!",
        description=f"Você deixou de seguir **{member.display_name}**!",
        color=0x00FF00
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(
        name="📊 Estatísticas:",
        value=f"Você agora segue **{len(follow_data[follower_id]['following'])}** pessoas",
        inline=False
    )
    embed.set_footer(text=f"Comando usado por {ctx.author.display_name}")

    await ctx.reply(embed=embed)

# Comando para ver seguidores
@bot.command(name='seguidores_lista')
async def seguidores_lista(ctx, member: discord.Member = None):
    if member is None:
        member = ctx.author

    user_id = str(member.id)

    # Verifica se o usuário está registrado
    if user_id not in user_data:
        if member == ctx.author:
            embed = discord.Embed(
                title="❌ Registro necessário",
                description="Você precisa se registrar primeiro!",
                color=0xFF0000
            )
            embed.add_field(
                name="📝 Como se registrar:",
                value="Use o comando `m!seguidores` para criar seu perfil",
                inline=False
            )
            await ctx.reply(embed=embed)
        else:
            await ctx.reply(f"❌ {member.display_name} ainda não se registrou!")
        return

    # Pega a lista de seguidores
    followers_list = follow_data.get(user_id, {}).get("followers", [])

    embed = discord.Embed(
        title=f"👥 Seguidores de {member.display_name}",
        color=0x1DA1F2
    )
    embed.set_thumbnail(url=member.display_avatar.url)

    if not followers_list:
        embed.description = f"**{member.display_name}** ainda não tem seguidores."
    else:
        followers_text = ""
        for i, follower_id in enumerate(followers_list[:10]):  # Mostra até 10
            try:
                follower_user = bot.get_user(int(follower_id))
                if follower_user and follower_id in user_data:
                    username = user_data[follower_id].get('username', follower_user.display_name)
                    followers_text += f"{i+1}. **@{username}**\n"
            except:
                continue

        if followers_text:
            embed.add_field(
                name=f"📋 Lista de Seguidores ({len(followers_list)} total)",
                value=followers_text,
                inline=False
            )

        if len(followers_list) > 10:
            embed.add_field(
                name="ℹ️ Informação",
                value=f"Mostrando apenas os primeiros 10 de {len(followers_list)} seguidores.",
                inline=False
            )

    embed.set_footer(text=f"Consultado por {ctx.author.display_name}")
    await ctx.reply(embed=embed)

# Comando para ver quem está seguindo
@bot.command(name='seguindo')
async def seguindo(ctx, member: discord.Member = None):
    if member is None:
        member = ctx.author

    user_id = str(member.id)

    # Verifica se o usuário está registrado
    if user_id not in user_data:
        if member == ctx.author:
            embed = discord.Embed(
                title="❌ Registro necessário",
                description="Você precisa se registrar primeiro!",
                color=0xFF0000
            )
            embed.add_field(
                name="📝 Como se registrar:",
                value="Use o comando `m!seguidores` para criar seu perfil",
                inline=False
            )
            await ctx.reply(embed=embed)
        else:
            await ctx.reply(f"❌ {member.display_name} ainda não se registrou!")
        return

    # Pega a lista de quem está seguindo
    following_list = follow_data.get(user_id, {}).get("following", [])

    embed = discord.Embed(
        title=f"👤 {member.display_name} está seguindo",
        color=0x9146FF
    )
    embed.set_thumbnail(url=member.display_avatar.url)

    if not following_list:
        embed.description = f"**{member.display_name}** ainda não segue ninguém."
    else:
        following_text = ""
        for i, following_id in enumerate(following_list[:10]):  # Mostra até 10
            try:
                following_user = bot.get_user(int(following_id))
                if following_user and following_id in user_data:
                    username = user_data[following_id].get('username', following_user.display_name)
                    # Adiciona verificação baseada nos níveis de seguidores
                    followers_count = user_data[following_id].get('followers', 0)
                    if following_id == "983196900910039090":  # Owner ID
                        username += " <:extremomxp:1387842927602172125>"
                    elif followers_count >= 1000000:
                        username += " <:abudabimxp:1387843390506405922>"
                    elif followers_count >= 500000:
                        username += " <:verificadomxp:1387605173886783620>"
                    else:
                        username += " <:verificiadinmxp:1387842858912055428>"
                    following_text += f"{i+1}. **@{username}**\n"
            except:
                continue

        if following_text:
            embed.add_field(
                name=f"📋 Lista de Seguindo ({len(following_list)} total)",
                value=following_text,
                inline=False
            )

        if len(following_list) > 10:
            embed.add_field(
                name="ℹ️ Informação",
                value=f"Mostrando apenas os primeiros 10 de {len(following_list)} pessoas.",
                inline=False
            )

    embed.set_footer(text=f"Consultado por {ctx.author.display_name}")
    await ctx.reply(embed=embed)

# Comando para atualizar perfil (nome e profissão) usando modal
@bot.command(name='atualizar')
async def atualizar(ctx):
    user_id = str(ctx.author.id)

    # Verifica se o usuário está registrado
    if user_id not in user_data:
        embed = discord.Embed(
            title="❌ Registro necessário",
            description="Você precisa se registrar primeiro!",
            color=0xFF0000
        )
        embed.add_field(
            name="📝 Como se registrar:",
            value="Use o comando `m!seguidores` para criar seu perfil",
            inline=False
        )
        await ctx.reply(embed=embed)
        return

    # Inicializa novos campos se não existirem
    if 'bio' not in user_data[user_id]:
        user_data[user_id]['bio'] = None
    if 'status' not in user_data[user_id]:
        user_data[user_id]['status'] = None
    if 'profile_theme' not in user_data[user_id]:
        user_data[user_id]['profile_theme'] = 'classico'
    if 'profile_badge' not in user_data[user_id]:
        user_data[user_id]['profile_badge'] = None
    if 'social_links' not in user_data[user_id]:
        user_data[user_id]['social_links'] = {}

    # Pega os dados atuais do usuário
    user_data_info = user_data[user_id]
    current_username = user_data_info.get('username', '')
    current_profession = user_data_info.get('profession', '')
    current_bio = user_data_info.get('bio', '')
    current_status = user_data_info.get('status', '')
    current_theme = user_data_info.get('profile_theme', 'classico')
    current_badge = user_data_info.get('profile_badge', None)
    
    embed = discord.Embed(
        title="⚙️ Central de Personalização",
        description="Personalize seu perfil do Instagram MXP com várias opções!",
        color=user_data_info.get('profile_color', 0x9932CC)
    )
    
    # Informações básicas
    embed.add_field(
        name="📋 Informações Básicas",
        value=f"**Nome:** {current_username or 'Não definido'}\n**Profissão:** {current_profession or 'Não definido'}",
        inline=False
    )
    
    # Bio e Status
    bio_text = current_bio[:50] + "..." if current_bio and len(current_bio) > 50 else current_bio or "Não definida"
    status_text = current_status or "Não definido"
    embed.add_field(
        name="💭 Bio e Status",
        value=f"**Bio:** {bio_text}\n**Status:** {status_text}",
        inline=False
    )
    
    # Tema e Badge
    theme_names = {
        "classico": "🌟 Clássico", "gamer": "🔥 Gamer", "profissional": "💼 Profissional",
        "artista": "🎨 Artista", "kawaii": "🌸 Kawaii", "dark": "🖤 Dark Mode",
        "pride": "🌈 Pride", "neon": "⚡ Neon", "natural": "🌿 Natural", "luxo": "👑 Luxo"
    }
    badge_names = {
        "gamer": "🎮 Gamer", "artista": "🎨 Artista", "estudante": "📚 Estudante",
        "trabalhador": "💼 Trabalhador", "streamer": "🌟 Streamer", "musico": "🎵 Músico",
        "fotografo": "📷 Fotógrafo", "esportista": "⚽ Esportista", "foodie": "🍕 Foodie", "viajante": "🌍 Viajante"
    }
    
    current_theme_name = theme_names.get(current_theme, "🌟 Clássico")
    current_badge_name = badge_names.get(current_badge, "Nenhum") if current_badge else "Nenhum"
    
    embed.add_field(
        name="🎭 Aparência",
        value=f"**Tema:** {current_theme_name}\n**Badge:** {current_badge_name}\n**Cor:** {get_color_name(user_data_info.get('profile_color', 0x9932CC))}",
        inline=False
    )
    
    # Links sociais
    social_links = user_data_info.get('social_links', {})
    links_text = ""
    if social_links.get('instagram'): links_text += f"📷 {social_links['instagram']}\n"
    if social_links.get('youtube'): links_text += f"🎥 {social_links['youtube']}\n"
    if social_links.get('tiktok'): links_text += f"🎵 {social_links['tiktok']}\n"
    if not links_text: links_text = "Nenhum link definido"
    
    embed.add_field(
        name="🔗 Links Sociais",
        value=links_text,
        inline=False
    )
    
    embed.add_field(
        name="✨ Opções de Personalização",
        value="**Nome/Profissão** - Informações básicas\n **Bio/Status** - Descrição e status atual\n **Links Sociais** - Instagram, YouTube, TikTok\n **Tema** - Aparência do perfil\n **Badge** - Badge especial\n **Cor** - Cor dos embeds",
        inline=False
    )
    
    embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1387842927602172125.png")
    embed.set_footer(text="Use os botões abaixo para personalizar seu perfil")

    # View com botões de atualização
    view = UpdateProfileView(current_username, current_profession, user_id)
    await ctx.reply(embed=embed, view=view)

# Classes para o sistema de lojinha
class LojaMainView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=300)
        self.user_id = user_id

    @discord.ui.button(label='🚗 Carros', style=discord.ButtonStyle.primary, emoji='🚗')
    async def carros_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Esta loja não é sua!", ephemeral=True)
            return
        
        view = LojaCarrosView(self.user_id)
        embed = discord.Embed(
            title="🚗 Carros Disponíveis",
            description="Escolha a categoria de carros que deseja ver:",
            color=0x3498DB
        )
        embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1387842927602172125.png")
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label='🏰 Mansões', style=discord.ButtonStyle.secondary, emoji='🏰')
    async def mansoes_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Esta loja não é sua!", ephemeral=True)
            return
        
        view = LojaMansoesView(self.user_id)
        embed = discord.Embed(
            title="🏰 Mansões Disponíveis",
            description="Escolha a categoria de mansões que deseja ver:",
            color=0xE67E22
        )
        embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1387842927602172125.png")
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label='🛍️ Itens do Dia a Dia', style=discord.ButtonStyle.success, emoji='🛍️')
    async def itens_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Esta loja não é sua!", ephemeral=True)
            return
        
        view = LojaItensView(self.user_id)
        embed = discord.Embed(
            title="🛍️ Itens do Dia a Dia",
            description="Escolha a categoria de itens que deseja ver:",
            color=0x27AE60
        )
        embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1387842927602172125.png")
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label='📦 Meu Inventário', style=discord.ButtonStyle.blurple, emoji='📦')
    async def inventario_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Esta loja não é sua!", ephemeral=True)
            return
        
        # Inicializa inventário se não existir
        if self.user_id not in inventory_data:
            inventory_data[self.user_id] = {"carros": [], "mansoes": [], "itens_diarios": []}
        
        user_inventory = inventory_data[self.user_id]
        
        embed = discord.Embed(
            title="📦 Meu Inventário",
            description=f"Todos os seus itens comprados:",
            color=0x9B59B6
        )
        
        # Carros
        if user_inventory["carros"]:
            carros_text = ""
            for i, carro in enumerate(user_inventory["carros"][:5]):  # Mostra até 5
                carros_text += f"🚗 **{carro['nome']}** - R$ {carro['preco']:,}\n".replace(",", ".")
            embed.add_field(
                name=f"🚗 Carros ({len(user_inventory['carros'])})",
                value=carros_text,
                inline=False
            )
        
        # Mansões
        if user_inventory["mansoes"]:
            mansoes_text = ""
            for i, mansao in enumerate(user_inventory["mansoes"][:3]):  # Mostra até 3
                mansoes_text += f"🏰 **{mansao['nome']}** - R$ {mansao['preco']:,}\n".replace(",", ".")
            embed.add_field(
                name=f"🏰 Mansões ({len(user_inventory['mansoes'])})",
                value=mansoes_text,
                inline=False
            )
        
        # Itens do dia a dia
        if user_inventory["itens_diarios"]:
            itens_text = ""
            for i, item in enumerate(user_inventory["itens_diarios"][:8]):  # Mostra até 8
                itens_text += f"🛍️ **{item['nome']}** - R$ {item['preco']:,}\n".replace(",", ".")
            embed.add_field(
                name=f"🛍️ Itens do Dia a Dia ({len(user_inventory['itens_diarios'])})",
                value=itens_text,
                inline=False
            )
        
        if not any([user_inventory["carros"], user_inventory["mansoes"], user_inventory["itens_diarios"]]):
            embed.add_field(
                name="😢 Inventário Vazio",
                value="Você ainda não comprou nenhum item! Use os botões acima para fazer compras.",
                inline=False
            )
        
        embed.set_footer(text="Use os botões para navegar pela loja")
        await interaction.response.edit_message(embed=embed, view=self)

class LojaCarrosView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=300)
        self.user_id = user_id

    @discord.ui.button(label='🚗 Populares', style=discord.ButtonStyle.secondary)
    async def populares_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Esta loja não é sua!", ephemeral=True)
            return
        await self.show_cars_category(interaction, "Carros Populares")

    @discord.ui.button(label='🏎️ Esportivos', style=discord.ButtonStyle.primary)
    async def esportivos_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Esta loja não é sua!", ephemeral=True)
            return
        await self.show_cars_category(interaction, "Carros Esportivos")

    @discord.ui.button(label='💎 Luxo', style=discord.ButtonStyle.success)
    async def luxo_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Esta loja não é sua!", ephemeral=True)
            return
        await self.show_cars_category(interaction, "Carros Luxo")

    @discord.ui.button(label='🔥 Supercars', style=discord.ButtonStyle.danger)
    async def supercars_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Esta loja não é sua!", ephemeral=True)
            return
        await self.show_cars_category(interaction, "Supercars")

    @discord.ui.button(label='⬅️ Voltar', style=discord.ButtonStyle.blurple)
    async def voltar_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Esta loja não é sua!", ephemeral=True)
            return
        
        view = LojaMainView(self.user_id)
        embed = discord.Embed(
            title="🛒 Instagram MXP - Lojinha",
            description="Bem-vindo à lojinha! Escolha uma categoria:",
            color=0xE4405F
        )
        embed.add_field(
            name="💰 Dinheiro Disponível",
            value=f"R$ {economy_data.get(self.user_id, {}).get('money', 0):,}".replace(",", "."),
            inline=False
        )
        embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/thumb/a/a5/Instagram_icon.png/1024px-Instagram_icon.png")
        await interaction.response.edit_message(embed=embed, view=view)

    async def show_cars_category(self, interaction, categoria):
        cars = {nome: info for nome, info in LOJA_ITEMS["carros"].items() if info["categoria"] == categoria}
        
        embed = discord.Embed(
            title=f"🚗 {categoria}",
            description="Escolha um carro para comprar:",
            color=0x3498DB
        )
        
        view = CompraItemView(self.user_id, "carros", cars)
        
        for nome, info in list(cars.items())[:10]:  # Mostra até 10 carros
            embed.add_field(
                name=nome,
                value=f"💰 R$ {info['preco']:,}".replace(",", "."),
                inline=True
            )
        
        embed.set_footer(text="Selecione um carro no menu abaixo para comprar")
        await interaction.response.edit_message(embed=embed, view=view)

class LojaMansoesView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=300)
        self.user_id = user_id

    @discord.ui.button(label='🏠 Básicas', style=discord.ButtonStyle.secondary)
    async def basicas_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Esta loja não é sua!", ephemeral=True)
            return
        await self.show_mansoes_category(interaction, "Residências Básicas")

    @discord.ui.button(label='🏡 Médias', style=discord.ButtonStyle.primary)
    async def medias_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Esta loja não é sua!", ephemeral=True)
            return
        await self.show_mansoes_category(interaction, "Residências Médias")

    @discord.ui.button(label='🏰 Mansões', style=discord.ButtonStyle.success)
    async def mansoes_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Esta loja não é sua!", ephemeral=True)
            return
        await self.show_mansoes_category(interaction, "Mansões")

    @discord.ui.button(label='👑 Ultra Premium', style=discord.ButtonStyle.danger)
    async def ultra_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Esta loja não é sua!", ephemeral=True)
            return
        await self.show_mansoes_category(interaction, "Ultra Premium")

    @discord.ui.button(label='🏛️ Únicas', style=discord.ButtonStyle.secondary, row=1)
    async def unicas_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Esta loja não é sua!", ephemeral=True)
            return
        await self.show_mansoes_category(interaction, "Propriedades Únicas")

    @discord.ui.button(label='⬅️ Voltar', style=discord.ButtonStyle.blurple, row=1)
    async def voltar_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Esta loja não é sua!", ephemeral=True)
            return
        
        view = LojaMainView(self.user_id)
        embed = discord.Embed(
            title="🛒 Instagram MXP - Lojinha",
            description="Bem-vindo à lojinha! Escolha uma categoria:",
            color=0xE4405F
        )
        embed.add_field(
            name="💰 Dinheiro Disponível",
            value=f"R$ {economy_data.get(self.user_id, {}).get('money', 0):,}".replace(",", "."),
            inline=False
        )
        embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/thumb/a/a5/Instagram_icon.png/1024px-Instagram_icon.png")
        await interaction.response.edit_message(embed=embed, view=view)

    async def show_mansoes_category(self, interaction, categoria):
        mansoes = {nome: info for nome, info in LOJA_ITEMS["mansoes"].items() if info["categoria"] == categoria}
        
        embed = discord.Embed(
            title=f"🏰 {categoria}",
            description="Escolha uma mansão para comprar:",
            color=0xE67E22
        )
        
        view = CompraItemView(self.user_id, "mansoes", mansoes)
        
        for nome, info in list(mansoes.items())[:10]:  # Mostra até 10 mansões
            embed.add_field(
                name=nome,
                value=f"💰 R$ {info['preco']:,}".replace(",", "."),
                inline=True
            )
        
        embed.set_footer(text="Selecione uma mansão no menu abaixo para comprar")
        await interaction.response.edit_message(embed=embed, view=view)

class LojaItensView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=300)
        self.user_id = user_id

    @discord.ui.button(label='☕ Bebidas', style=discord.ButtonStyle.secondary)
    async def bebidas_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Esta loja não é sua!", ephemeral=True)
            return
        await self.show_itens_category(interaction, "Bebidas")

    @discord.ui.button(label='📱 Eletrônicos', style=discord.ButtonStyle.primary)
    async def eletronicos_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Esta loja não é sua!", ephemeral=True)
            return
        await self.show_itens_category(interaction, "Eletrônicos")

    @discord.ui.button(label='👕 Roupas', style=discord.ButtonStyle.success)
    async def roupas_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Esta loja não é sua!", ephemeral=True)
            return
        await self.show_itens_category(interaction, "Roupas")

    @discord.ui.button(label='💎 Luxo', style=discord.ButtonStyle.danger)
    async def luxo_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Esta loja não é sua!", ephemeral=True)
            return
        await self.show_itens_category(interaction, "Acessórios de Luxo")

    @discord.ui.button(label='🎮 Games', style=discord.ButtonStyle.primary, row=1)
    async def games_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Esta loja não é sua!", ephemeral=True)
            return
        await self.show_itens_category(interaction, "Games")

    @discord.ui.button(label='💍 Joias', style=discord.ButtonStyle.success, row=1)
    async def joias_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Esta loja não é sua!", ephemeral=True)
            return
        await self.show_itens_category(interaction, "Joias")

    @discord.ui.button(label='⬅️ Voltar', style=discord.ButtonStyle.blurple, row=1)
    async def voltar_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Esta loja não é sua!", ephemeral=True)
            return
        
        view = LojaMainView(self.user_id)
        embed = discord.Embed(
            title="🛒 Instagram MXP - Lojinha",
            description="Bem-vindo à lojinha! Escolha uma categoria:",
            color=0xE4405F
        )
        embed.add_field(
            name="💰 Dinheiro Disponível",
            value=f"R$ {economy_data.get(self.user_id, {}).get('money', 0):,}".replace(",", "."),
            inline=False
        )
        embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/thumb/a/a5/Instagram_icon.png/1024px-Instagram_icon.png")
        await interaction.response.edit_message(embed=embed, view=view)

    async def show_itens_category(self, interaction, categoria):
        itens = {nome: info for nome, info in LOJA_ITEMS["itens_diarios"].items() if info["categoria"] == categoria}
        
        embed = discord.Embed(
            title=f"🛍️ {categoria}",
            description="Escolha um item para comprar:",
            color=0x27AE60
        )
        
        view = CompraItemView(self.user_id, "itens_diarios", itens)
        
        for nome, info in list(itens.items())[:10]:  # Mostra até 10 itens
            embed.add_field(
                name=nome,
                value=f"💰 R$ {info['preco']:,}".replace(",", "."),
                inline=True
            )
        
        embed.set_footer(text="Selecione um item no menu abaixo para comprar")
        await interaction.response.edit_message(embed=embed, view=view)

class CompraItemView(discord.ui.View):
    def __init__(self, user_id, tipo, items):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.tipo = tipo
        self.items = items
        
        # Adiciona select menu com os itens
        self.add_item(ItemSelect(user_id, tipo, items))

    @discord.ui.button(label='⬅️ Voltar', style=discord.ButtonStyle.blurple, row=1)
    async def voltar_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Esta loja não é sua!", ephemeral=True)
            return
        
        # Volta para a categoria apropriada baseada no tipo
        if self.tipo == "carros":
            view = LojaCarrosView(self.user_id)
            embed = discord.Embed(
                title="🚗 Carros Disponíveis",
                description="Escolha a categoria de carros que deseja ver:",
                color=0x3498DB
            )
        elif self.tipo == "mansoes":
            view = LojaMansoesView(self.user_id)
            embed = discord.Embed(
                title="🏰 Mansões Disponíveis",
                description="Escolha a categoria de mansões que deseja ver:",
                color=0xE67E22
            )
        else:  # itens_diarios
            view = LojaItensView(self.user_id)
            embed = discord.Embed(
                title="🛍️ Itens do Dia a Dia",
                description="Escolha a categoria de itens que deseja ver:",
                color=0x27AE60
            )
        
        embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1387842927602172125.png")
        await interaction.response.edit_message(embed=embed, view=view)

class ItemSelect(discord.ui.Select):
    def __init__(self, user_id, tipo, items):
        self.user_id = user_id
        self.tipo = tipo
        self.items = items
        
        options = []
        for nome, info in list(items.items())[:25]:  # Discord limita a 25 opções
            options.append(discord.SelectOption(
                label=nome,
                description=f"R$ {info['preco']:,} - {info['categoria']}".replace(",", "."),
                value=nome
            ))
        
        super().__init__(placeholder="Escolha um item para comprar...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Esta loja não é sua!", ephemeral=True)
            return
        
        selected_item = self.values[0]
        item_info = self.items[selected_item]
        preco = item_info["preco"]
        
        # Verifica se tem dinheiro suficiente
        user_money = economy_data.get(self.user_id, {}).get("money", 0)
        
        if user_money < preco:
            embed = discord.Embed(
                title="❌ Dinheiro Insuficiente",
                description=f"Você não tem dinheiro suficiente para comprar **{selected_item}**!",
                color=0xFF0000
            )
            embed.add_field(
                name="💰 Preço do Item",
                value=f"R$ {preco:,}".replace(",", "."),
                inline=True
            )
            embed.add_field(
                name="💵 Seu Dinheiro",
                value=f"R$ {user_money:,}".replace(",", "."),
                inline=True
            )
            embed.add_field(
                name="💡 Como Ganhar Dinheiro",
                value="Use `m!publi` após mencionar marcas famosas em posts longos!",
                inline=False
            )
            await interaction.response.edit_message(embed=embed, view=None)
            return
        
        # Realiza a compra
        economy_data[self.user_id]["money"] -= preco
        
        # Inicializa inventário se não existir
        if self.user_id not in inventory_data:
            inventory_data[self.user_id] = {"carros": [], "mansoes": [], "itens_diarios": []}
        
        # Adiciona item ao inventário
        import datetime
        item_data = {
            "nome": selected_item,
            "preco": preco,
            "categoria": item_info["categoria"],
            "data_compra": datetime.datetime.now().isoformat()
        }
        inventory_data[self.user_id][self.tipo].append(item_data)
        
        # Salva os dados
        save_economy_data()
        save_inventory_data()
        
        # Embed de sucesso
        embed = discord.Embed(
            title="✅ Compra Realizada!",
            description=f"Você comprou **{selected_item}** com sucesso!",
            color=0x00FF00
        )
        
        embed.add_field(
            name="🛒 Item Comprado",
            value=f"**{selected_item}**\n{item_info['categoria']}",
            inline=True
        )
        
        embed.add_field(
            name="💰 Valor Pago",
            value=f"R$ {preco:,}".replace(",", "."),
            inline=True
        )
        
        embed.add_field(
            name="💵 Dinheiro Restante",
            value=f"R$ {economy_data[self.user_id]['money']:,}".replace(",", "."),
            inline=True
        )
        
        # Tipo de item específico
        if self.tipo == "carros":
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1387842927602172125.png")
            embed.add_field(
                name="🚗 Novo Carro!",
                value="Seu novo carro foi adicionado à sua garagem!",
                inline=False
            )
        elif self.tipo == "mansoes":
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1387842927602172125.png")
            embed.add_field(
                name="🏰 Nova Propriedade!",
                value="Sua nova mansão foi adicionada ao seu portfólio imobiliário!",
                inline=False
            )
        else:
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1381003788135174316.png")
            embed.add_field(
                name="🛍️ Novo Item!",
                value="Seu item foi adicionado ao inventário!",
                inline=False
            )
        
        # Botão para voltar à loja
        view = discord.ui.View()
        voltar_button = discord.ui.Button(label="🛒 Voltar à Loja", style=discord.ButtonStyle.primary)
        
        async def voltar_callback(button_interaction):
            if str(button_interaction.user.id) != self.user_id:
                await button_interaction.response.send_message("❌ Esta loja não é sua!", ephemeral=True)
                return
            
            main_view = LojaMainView(self.user_id)
            main_embed = discord.Embed(
                title="🛒 Instagram MXP - Lojinha",
                description="Bem-vindo à lojinha! Escolha uma categoria:",
                color=0xE4405F
            )
            main_embed.add_field(
                name="💰 Dinheiro Disponível",
                value=f"R$ {economy_data.get(self.user_id, {}).get('money', 0):,}".replace(",", "."),
                inline=False
            )
            main_embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/thumb/a/a5/Instagram_icon.png/1024px-Instagram_icon.png")
            await button_interaction.response.edit_message(embed=main_embed, view=main_view)
        
        voltar_button.callback = voltar_callback
        view.add_item(voltar_button)
        
        embed.set_footer(text=f"Compra realizada por {interaction.user.display_name}")
        await interaction.response.edit_message(embed=embed, view=view)
        
        print(f"💰 Compra realizada: {interaction.user.display_name} comprou {selected_item} por R${preco:,}")

class HelpView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=300)
        self.ctx = ctx

    @discord.ui.button(label='🎯 Comandos Básicos', style=discord.ButtonStyle.primary)
    async def comandos_basicos(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🎯 Comandos Básicos - Instagram MXP",
            description="Comandos essenciais para começar",
            color=0x00FF00
        )
        embed.add_field(
            name="`m!seguidores`",
            value="📊 Registra seu perfil e ganha seguidores aleatórios",
            inline=False
        )
        embed.add_field(
            name="`m!perfil [@usuário]`",
            value="👤 Mostra perfil do Instagram (seu ou de outro usuário)",
            inline=False
        )
        embed.add_field(
            name="`m!atualizar`",
            value="📝 Atualiza nome e profissão via formulário modal",
            inline=False
        )
        embed.add_field(
            name="`m!publi`",
            value="💼 Ganha dinheiro fazendo publicidade (mencione marcas!)",
            inline=False
        )
        embed.add_field(
            name="`m!economia [@usuário]`",
            value="💰 Vê saldo de dinheiro e pontos de fama",
            inline=False
        )
        embed.add_field(
            name="`m!lojinha`",
            value="🛒 Loja com carros, mansões e itens do dia a dia",
            inline=False
        )
        embed.add_field(
            name="`m!teste`",
            value="🔧 Testa se o bot está funcionando",
            inline=False
        )
        embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/thumb/a/a5/Instagram_icon.png/1024px-Instagram_icon.png")
        embed.set_footer(text=f"Ajuda solicitada por {self.ctx.author.display_name}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label='👥 Comandos Sociais', style=discord.ButtonStyle.secondary)
    async def comandos_sociais(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="👥 Comandos Sociais - Instagram MXP",
            description="Interaja com outros usuários",
            color=0x1DA1F2
        )
        embed.add_field(
            name="`m!seguir @usuário`",
            value="➕ Segue um usuário (pode virar amigo mútuo!)",
            inline=False
        )
        embed.add_field(
            name="`m!desseguir @usuário`",
            value="➖ Para de seguir um usuário",
            inline=False
        )
        embed.add_field(
            name="`m!seguidores_lista [@usuário]`",
            value="📋 Lista completa dos seguidores",
            inline=False
        )
        embed.add_field(
            name="`m!seguindo [@usuário]`",
            value="📋 Lista quem está seguindo",
            inline=False
        )
        embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1387605173886783620.png")
        embed.set_footer(text=f"Ajuda solicitada por {self.ctx.author.display_name}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label='🏆 Rankings & Stats', style=discord.ButtonStyle.success)
    async def comandos_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🏆 Rankings & Estatísticas - Instagram MXP",
            description="Veja os melhores e estatísticas globais",
            color=0xFFD700
        )
        embed.add_field(
            name="`m!curtidas`",
            value="🏆 Top 10 usuários com mais curtidas",
            inline=False
        )
        embed.add_field(
            name="`m!stats`",
            value="📊 Estatísticas globais do bot",
            inline=False
        )
        embed.add_field(
            name="`m!reset`",
            value="🗑️ Reseta todos os seus dados (irreversível)",
            inline=False
        )
        embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1376731577106567319.png")
        embed.set_footer(text=f"Ajuda solicitada por {self.ctx.author.display_name}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label='ℹ️ Informações', style=discord.ButtonStyle.blurple)
    async def comandos_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="ℹ️ Informações & Outros - Instagram MXP",
            description="Informações sobre o bot e como funciona",
            color=0x9932CC
        )
        embed.add_field(
            name="`m!sobre`",
            value="📱 Informações detalhadas sobre o bot",
            inline=False
        )
        embed.add_field(
            name="`m!ajuda`",
            value="📚 Mostra este menu de ajuda",
            inline=False
        )
        embed.add_field(
            name="💡 Como Funciona:",
            value="• Reaja com <:mxplike1:1381003788135174316> nas mensagens para dar curtidas\n• Cada 10 curtidas = 1 level\n• Use botões no perfil para personalizar imagens\n• Seguidores são ganhos aleatoriamente no primeiro uso\n• 500k+ seguidores = verificação automática",
            inline=False
        )
        embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/thumb/c/ce/Circle-icons-info.svg/1024px-Circle-icons-info.svg.png")
        embed.set_footer(text=f"Ajuda solicitada por {self.ctx.author.display_name}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

# Comando de ajuda
@bot.command(name='ajuda', aliases=['ajudainsta'])
async def ajuda(ctx):
    embed = discord.Embed(
        title="📚 Central de Ajuda - Instagram MXP",
        description="Selecione uma categoria para ver os comandos disponíveis:",
        color=0xE4405F
    )

    embed.add_field(
        name="🎯 Comandos Básicos",
        value="Registro, perfil e personalização",
        inline=True
    )

    embed.add_field(
        name="👥 Comandos Sociais",
        value="Seguir, seguidores e relacionamentos",
        inline=True
    )

    embed.add_field(
        name="🏆 Rankings & Stats",
        value="Rankings e estatísticas globais",
        inline=True
    )

    embed.add_field(
        name="ℹ️ Informações",
        value="Sobre o bot e como funciona",
        inline=True
    )

    embed.add_field(
        name="💡 Dica Rápida:",
        value="Clique nos botões abaixo para ver os comandos de cada categoria!",
        inline=False
    )

    embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/thumb/a/a5/Instagram_icon.png/1024px-Instagram_icon.png")
    embed.set_footer(text=f"Solicitado por {ctx.author.display_name} • Use os botões para navegar")

    view = HelpView(ctx)
    await ctx.reply(embed=embed, view=view)

# Comando de estatísticas globais
@bot.command(name='stats', aliases=['status'])
async def stats(ctx):
    total_users = len(user_data)
    total_likes = sum(user.get('total_likes', 0) for user in user_data.values())
    total_followers = sum(user.get('followers', 0) for user in user_data.values())
    total_relationships = len(follow_data)

    # Calcula relacionamentos ativos
    active_following = sum(len(data.get('following', [])) for data in follow_data.values())

    embed = discord.Embed(
        title="📊 Estatísticas Globais do Instagram MXP",
        description="Dados gerais da plataforma",
        color=0x9932CC
    )

    embed.add_field(
        name="👥 Usuários",
        value=f"**{total_users:,}** usuários registrados".replace(",", "."),
        inline=True
    )

    embed.add_field(
        name="💖 Curtidas Totais",
        value=f"**{total_likes:,}** curtidas dadas".replace(",", "."),
        inline=True
    )

    embed.add_field(
        name="📈 Seguidores Totais",
        value=f"**{total_followers:,}** seguidores".replace(",", "."),
        inline=True
    )

    embed.add_field(
        name="🤝 Relacionamentos",
        value=f"**{active_following:,}** conexões ativas".replace(",", "."),
        inline=True
    )

    # Top usuário
    if user_data:
        top_user_id = max(user_data, key=lambda x: user_data[x].get('total_likes', 0))
        top_user = bot.get_user(int(top_user_id))
        top_likes = user_data[top_user_id].get('total_likes', 0)

        if top_user:
            embed.add_field(
                name="👑 Usuário com Mais Curtidas",
                value=f"**{top_user.display_name}** - {top_likes:,} curtidas".replace(",", "."),
                inline=False
            )

    embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
    embed.set_footer(text=f"Dev: YevgennyMXP • Consultado por {ctx.author.display_name}")

    await ctx.reply(embed=embed)

# Comando para resetar dados do usuário
@bot.command(name='reset')
async def reset_user(ctx):
    user_id = str(ctx.author.id)

    # Verifica se o usuário já usou o reset
    if user_id in reset_data:
        embed = discord.Embed(
            title="❌ Reset já utilizado!",
            description="Você já usou o comando `m!reset` anteriormente.",
            color=0xFF0000
        )
        embed.add_field(
            name="🚫 Limitação:",
            value="O comando `m!reset` só pode ser usado **uma vez por pessoa** para evitar abusos.",
            inline=False
        )
        embed.add_field(
            name="💡 Alternativa:",
            value="Se você quiser alterar apenas algumas informações, use:\n• `m!atualizar` - para nome e profissão\n• Botões no `m!perfil` - para imagens",
            inline=False
        )
        embed.set_footer(text="Dev: YevgennyMXP • Esta limitação é permanente")
        await ctx.reply(embed=embed)
        return

    if user_id not in user_data:
        embed = discord.Embed(
            title="❌ Nada para resetar",
            description="Você não possui dados registrados!",
            color=0xFF0000
        )
        await ctx.reply(embed=embed)
        return

    # Confirma a ação
    embed = discord.Embed(
        title="⚠️ Confirmação de Reset",
        description="Tem certeza que deseja **DELETAR TODOS** os seus dados?",
        color=0xFF8C00
    )
    embed.add_field(
        name="🗑️ Dados que serão removidos:",
        value="• Nome de usuário e profissão\n• Total de curtidas e level\n• Seguidores do Instagram\n• Imagens personalizadas\n• Todos os relacionamentos (seguir/seguidores)",
        inline=False
    )
    embed.add_field(
        name="❗ ATENÇÃO:",
        value="**Esta ação é IRREVERSÍVEL!**\nVocê precisará usar `m!seguidores` novamente para se registrar.\n\n**⚠️ IMPORTANTE:** Você só pode usar este comando **UMA VEZ**!",
        inline=False
    )

    # Botões de confirmação
    view = discord.ui.View(timeout=60)

    # Botão de confirmar
    confirm_button = discord.ui.Button(
        label="✅ Sim, deletar tudo",
        style=discord.ButtonStyle.danger,
        emoji="🗑️"
    )

    async def confirm_callback(interaction):
        if interaction.user.id != ctx.author.id:
            await interaction.response.send_message("❌ Apenas quem solicitou pode confirmar!", ephemeral=True)
            return

        # Remove dados do usuário
        if user_id in user_data:
            del user_data[user_id]

        # Remove relacionamentos
        if user_id in follow_data:
            # Remove das listas de following de outros usuários
            for other_user_id in follow_data[user_id].get("following", []):
                if other_user_id in follow_data and user_id in follow_data[other_user_id].get("followers", []):
                    follow_data[other_user_id]["followers"].remove(user_id)

            # Remove das listas de followers de outros usuários
            for other_user_id in follow_data[user_id].get("followers", []):
                if other_user_id in follow_data and user_id in follow_data[other_user_id].get("following", []):
                    follow_data[other_user_id]["following"].remove(user_id)

            del follow_data[user_id]

        # Marca que o usuário usou o reset
        reset_data[user_id] = True

        save_user_data()
        save_follow_data()
        save_reset_data()

        success_embed = discord.Embed(
            title="✅ Dados Resetados!",
            description="Todos os seus dados foram removidos com sucesso.",
            color=0x00FF00
        )
        success_embed.add_field(
            name="🔄 Próximos Passos:",
            value="Use `m!seguidores` para se registrar novamente e começar do zero!",
            inline=False
        )
        success_embed.add_field(
            name="⚠️ Importante:",
            value="Você **não poderá usar** o comando `m!reset` novamente. Este era seu único uso!",
            inline=False
        )
        success_embed.set_footer(text="Reset realizado com sucesso • Uma vez por usuário")

        await interaction.response.edit_message(embed=success_embed, view=None)

    # Botão de cancelar
    cancel_button = discord.ui.Button(
        label="❌ Cancelar",
        style=discord.ButtonStyle.secondary,
        emoji="🚫"
    )

    async def cancel_callback(interaction):
        if interaction.user.id != ctx.author.id:
            await interaction.response.send_message("❌ Apenas quem solicitou pode cancelar!", ephemeral=True)
            return

        cancel_embed = discord.Embed(
            title="❌ Reset Cancelado",
            description="Seus dados estão seguros! Nenhuma alteração foi feita.",
            color=0x00FF00
        )
        await interaction.response.edit_message(embed=cancel_embed, view=None)

    confirm_button.callback = confirm_callback
    cancel_button.callback = cancel_callback

    view.add_item(confirm_button)
    view.add_item(cancel_button)

    await ctx.reply(embed=embed, view=view)

# Comando sobre o bot
@bot.command(name='sobre', aliases=['info'])
async def sobre(ctx):
    embed = discord.Embed(
        title="📱 Instagram MXP Bot",
        description="Simulador de Instagram para Discord",
        color=0xE4405F
    )

    embed.add_field(
        name="🎯 Funcionalidades Principais",
        value="• Sistema de perfis personalizados\n• Curtidas automáticas nas mensagens\n• Relacionamentos sociais (seguir/seguidores)\n• Rankings e estatísticas\n• Modals para atualização de dados",
        inline=False
    )

    embed.add_field(
        name="🔧 Recursos Técnicos",
        value="• Armazenamento em JSON\n• Sistema de levels baseado em curtidas\n• Verificação automática (500k+ seguidores)\n• Botões e modals interativos\n• Sistema de relacionamentos em tempo real",
        inline=False
    )

    embed.add_field(
        name="📊 Como Usar",
        value="1. Use `m!seguidores` para se registrar\n2. Customize seu perfil com `m!atualizar`\n3. Interaja reagindo às mensagens\n4. Siga outros usuários com `m!seguir`\n5. Veja seu progresso com `m!perfil`",
        inline=False
    )

    embed.add_field(
        name="💻 Desenvolvido em",
        value="Python + Node.JS + Discord.py",
        inline=True
    )

    embed.add_field(
        name="🏆 Versão",
        value="2.0 - Sistema Social",
        inline=True
    )

    embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/thumb/a/a5/Instagram_icon.png/1024px-Instagram_icon.png")
    embed.set_footer(text=f"Dev: YevgennyMXP • Consultado por {ctx.author.display_name}")

    await ctx.reply(embed=embed)

# Comando para verificar engajamento
@bot.command(name='engajamento')
async def engajamento(ctx, member: discord.Member = None):
    if member is None:
        member = ctx.author

    user_id = str(member.id)

    if user_id not in user_data:
        embed = discord.Embed(
            title="❌ Usuário não registrado",
            description=f"{member.display_name} precisa se registrar primeiro!",
            color=0xFF0000
        )
        await ctx.reply(embed=embed)
        return

    likes = user_data[user_id].get('total_likes', 0)
    followers = user_data[user_id].get('followers', 0)

    if followers == 0:
        taxa_engajamento = 0
    else:
        taxa_engajamento = (likes / followers) * 100

    # Classifica o engajamento
    if taxa_engajamento >= 10:
        classificacao = "🔥 EXTRAORDINÁRIO"
        cor = 0xFF0000
    elif taxa_engajamento >= 5:
        classificacao = "⭐ EXCELENTE"
        cor = 0xFF6B35
    elif taxa_engajamento >= 2:
        classificacao = "📈 BOM"
        cor = 0xFFD23F
    elif taxa_engajamento >= 1:
        classificacao = "📊 MÉDIO"
        cor = 0x06FFA5
    else:
        classificacao = "📉 BAIXO"
        cor = 0x95E1D3

    embed = discord.Embed(
        title="📊 Análise de Engajamento",
        description=f"Taxa de engajamento de **{member.display_name}**",
        color=cor
    )

    embed.add_field(
        name="📈 Taxa de Engajamento",
        value=f"**{taxa_engajamento:.2f}%**",
        inline=True
    )

    embed.add_field(
        name="🏆 Classificação",
        value=classificacao,
        inline=True
    )

    embed.add_field(
        name="📊 Dados Base",
        value=f"💖 {likes:,} curtidas\n👥 {followers:,} seguidores".replace(",", "."),
        inline=False
    )

    # Dicas para melhorar
    if taxa_engajamento < 2:
        embed.add_field(
            name="💡 Dica para Melhorar",
            value="Interaja mais no servidor! Envie mensagens nos canais permitidos para ganhar mais curtidas.",
            inline=False
        )

    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text=f"Dev: YevgennyMXP • Consultado por {ctx.author.display_name}")

    await ctx.reply(embed=embed)

# Comando para sugerir perfis para seguir
@bot.command(name='sugestoes')
async def sugestoes(ctx):
    user_id = str(ctx.author.id)

    if user_id not in user_data:
        embed = discord.Embed(
            title="❌ Registro necessário",
            description="Você precisa se registrar primeiro!",
            color=0xFF0000
        )
        await ctx.reply(embed=embed)
        return

    # Pega usuários que o autor não segue
    following = follow_data.get(user_id, {}).get("following", [])
    suggestions = []

    for other_user_id, data in user_data.items():
        if other_user_id != user_id and other_user_id not in following:
            try:
                user = bot.get_user(int(other_user_id))
                if user:
                    followers_count = data.get('followers', 0)
                    likes_count = data.get('total_likes', 0)
                    suggestions.append((other_user_id, user, followers_count, likes_count))
            except:
                continue

    if not suggestions:
        embed = discord.Embed(
            title="😅 Nenhuma Sugestão",
            description="Você já segue todos os usuários registrados!",
            color=0x9932CC
        )
        await ctx.reply(embed=embed)
        return

    # Ordena por seguidores e pega os top 5
    suggestions.sort(key=lambda x: x[2], reverse=True)
    top_suggestions = suggestions[:5]

    embed = discord.Embed(
        title="👥 Sugestões para Seguir",
        description="Perfis populares que você ainda não segue:",
        color=0x1DA1F2
    )

    for i, (user_id_sug, user, followers, likes) in enumerate(top_suggestions):
        username = user_data[user_id_sug].get('username', user.display_name)

        # Adiciona verificação baseada nos níveis de seguidores
        if user_id_sug == "983196900910039090":  # Owner ID
            username += " <:extremomxp:1387842927602172125>"
        elif followers >= 1000000:
            username += " <:abudabimxp:1387843390506405922>"
        elif followers >= 500000:
            username += " <:verificadomxp:1387605173886783620>"
        else:
            username += " <:verificiadinmxp:1387842858912055428>"

        # Adiciona emoji baseado nos seguidores
        if followers >= 5000000:
            emoji = "💎"
            status = " (Mega Influencer)"
        elif followers >= 1000000:
            emoji = "🔥"
            status = " (Influencer)"
        elif followers >= 500000:
            emoji = "⭐"
            status = " (Verificado)"
        else:
            emoji = "👤"
            status = ""

        embed.add_field(
            name=f"{emoji} @{username}{status}",
            value=f"👥 {followers:,} seguidores\n💖 {likes:,} curtidas".replace(",", "."),
            inline=True
        )

    embed.add_field(
        name="💡 Como Seguir",
        value="Use `m!seguir @usuario` para seguir alguém da lista!",
        inline=False
    )

    embed.set_footer(text=f"Dev: YevgennyMXP • Sugestões para {ctx.author.display_name}")
    await ctx.reply(embed=embed)

# Comando para publicidade (m!publi)
@bot.command(name='publi')
async def publicidade(ctx):
    user_id = str(ctx.author.id)

    # Verifica se o usuário está registrado
    if user_id not in user_data:
        embed = discord.Embed(
            title="❌ Registro necessário",
            description="Você precisa se registrar primeiro!",
            color=0xFF0000
        )
        embed.add_field(
            name="📝 Como se registrar:",
            value="Use o comando `m!seguidores` para criar seu perfil",
            inline=False
        )
        await ctx.reply(embed=embed)
        return

    # Verifica se o usuário tem posts com marcas detectadas
    if user_id not in brand_posts_data or not brand_posts_data[user_id]:
        embed = discord.Embed(
            title="💡 Sistema de Publicidade Automática",
            description="As recompensas agora são **automáticas**! Não é mais necessário usar comandos.",
            color=0x00D2FF
        )
        embed.add_field(
            name="🤖 Como Funciona Agora:",
            value="1. Poste uma mensagem (40+ caracteres) mencionando uma marca famosa nos canais do Instagram\n2. O bot **detecta automaticamente** e responde com suas recompensas\n3. Não é mais necessário usar `m!publi`!",
            inline=False
        )
        embed.add_field(
            name="🏷️ Exemplos de marcas:",
            value="Nike, Apple, Coca-Cola, Samsung, Instagram, etc.",
            inline=False
        )
        embed.add_field(
            name="✨ Vantagens:",
            value="• Recompensas instantâneas\n• Sem necessidade de comandos\n• Detecção automática de marcas\n• Resposta imediata ao seu post",
            inline=False
        )
        await ctx.reply(embed=embed)
        return

    # Conta posts já recompensados automaticamente
    rewarded_posts = sum(1 for post_data in brand_posts_data[user_id].values() if post_data.get("rewarded", False))
    total_money_earned = sum(post_data.get("money_gained", 0) for post_data in brand_posts_data[user_id].values() if post_data.get("rewarded", False))
    total_fame_earned = sum(post_data.get("fame_gained", 0) for post_data in brand_posts_data[user_id].values() if post_data.get("rewarded", False))

    embed = discord.Embed(
        title="📊 Relatório de Publicidade Automática",
        description="Suas recompensas automáticas de publicidade:",
        color=0x00FF00
    )

    embed.add_field(
        name="📱 Posts Recompensados",
        value=f"**{rewarded_posts}** posts com marcas detectadas",
        inline=True
    )

    embed.add_field(
        name="💰 Total Ganho",
        value=f"💵 R$ {total_money_earned:,}\n⭐ {total_fame_earned:,} pontos de fama".replace(",", "."),
        inline=True
    )

    embed.add_field(
        name="💡 Sistema Automático",
        value="✅ **Ativo** - Suas publicidades são detectadas automaticamente!",
        inline=False
    )

    # Mostra as últimas 3 recompensas
    recent_posts = []
    for message_id, post_data in brand_posts_data[user_id].items():
        if post_data.get("rewarded", False):
            recent_posts.append((message_id, post_data))
    
    if recent_posts:
        recent_posts.sort(key=lambda x: x[1]["timestamp"], reverse=True)
        recent_text = ""
        for i, (msg_id, post_data) in enumerate(recent_posts[:3]):
            brands = ", ".join(post_data["brands"][:2])  # Mostra até 2 marcas
            money_gained = post_data.get("money_gained", 0)
            recent_text += f"**{i+1}.** {brands} - R$ {money_gained:,}\n".replace(",", ".")
        
        embed.add_field(
            name="🕐 Últimas Recompensas",
            value=recent_text,
            inline=False
        )

    embed.add_field(
        name="🎯 Próximos Passos:",
        value="Continue postando sobre marcas (40+ caracteres) para ganhar mais recompensas automáticas!",
        inline=False
    )

    embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1381003788135174316.png")
    embed.set_footer(text=f"Relatório gerado para {ctx.author.display_name}")

    await ctx.reply(embed=embed)

    print(f"📊 Relatório de publicidade mostrado para {ctx.author.display_name}: {rewarded_posts} posts, R${total_money_earned} total")

# Comando para verificar status dos dados
@bot.command(name='debug_dados')
async def debug_dados(ctx):
    """Comando para debug detalhado dos dados"""
    # Só o dono do bot pode usar
    if str(ctx.author.id) != "983196900910039090":
        await ctx.reply("❌ Apenas o dono do bot pode usar este comando!")
        return
    
    print(f"🔍 DEBUG DADOS: Comando executado por {ctx.author.display_name}")
    
    # Debug dos dados em memória
    print(f"🔍 DEBUG: user_data em memória: {len(user_data)} usuários")
    for user_id, data in user_data.items():
        username = data.get('username')
        followers = data.get('followers', 0)
        print(f"📝 Memória: {user_id} | username: '{username}' | followers: {followers}")
    
    # Debug do MongoDB
    if db is not None:
        collection = db.user_data
        mongo_count = collection.count_documents({})
        print(f"🔍 DEBUG: MongoDB user_data: {mongo_count} documentos")
        
        docs = collection.find({}).limit(10)
        for doc in docs:
            user_id = doc['_id']
            username = doc.get('username')
            followers = doc.get('followers', 0)
            print(f"📊 MongoDB: {user_id} | username: '{username}' | followers: {followers}")
    
    # Testa o ranking
    print(f"🔍 DEBUG: Testando get_ranking_data('seguidores')...")
    ranking_result = get_ranking_data('seguidores')
    print(f"🔍 DEBUG: Resultado do ranking: {len(ranking_result)} usuários")
    
    embed = discord.Embed(
        title="🔍 Debug de Dados Completo",
        description="Verificação detalhada dos dados (check console)",
        color=0x00FF00
    )
    embed.add_field(
        name="📊 Dados em Memória",
        value=f"**{len(user_data)}** usuários carregados",
        inline=True
    )
    
    if db is not None:
        mongo_count = db.user_data.count_documents({})
        embed.add_field(
            name="🍃 MongoDB",
            value=f"**{mongo_count}** documentos salvos",
            inline=True
        )
    
    embed.add_field(
        name="🏆 Ranking",
        value=f"**{len(ranking_result)}** usuários válidos para ranking",
        inline=True
    )
    
    embed.add_field(
        name="📋 Detalhes no Console",
        value="Verifique o console para logs detalhados de cada usuário",
        inline=False
    )
    
    await ctx.reply(embed=embed)

@bot.command(name='recarregar_dados')
async def recarregar_dados(ctx):
    # Só o dono do bot pode usar
    if str(ctx.author.id) != "983196900910039090":
        await ctx.reply("❌ Apenas o dono do bot pode usar este comando!")
        return
    
    embed = discord.Embed(
        title="🔄 Recarregando Dados...",
        description="Forçando recarregamento dos dados do MongoDB",
        color=0xFFD700
    )
    
    msg = await ctx.reply(embed=embed)
    
    try:
        # Recarrega todos os dados
        load_user_data()
        load_follow_data()
        load_economy_data()
        load_brand_posts_data()
        load_inventory_data()
        load_reset_data()
        
        success_embed = discord.Embed(
            title="✅ Dados Recarregados!",
            description="Todos os dados foram recarregados do MongoDB",
            color=0x00FF00
        )
        
        success_embed.add_field(
            name="📊 Dados Carregados",
            value=f"👥 {len(user_data)} usuários\n💰 {len(economy_data)} economias\n🤝 {len(follow_data)} relacionamentos\n📦 {len(inventory_data)} inventários\n📝 {len(brand_posts_data)} posts\n🔄 {len(reset_data)} resets",
            inline=False
        )
        
        # Mostra alguns usuários carregados
        if user_data:
            usuarios_info = ""
            for i, (user_id, data) in enumerate(list(user_data.items())[:5]):
                username = data.get('username')
                followers = data.get('followers', 0)
                usuarios_info += f"{i+1}. @{username} ({user_id[:8]}...) - {followers:,} seg\n".replace(",", ".")
            
            success_embed.add_field(
                name="👥 Usuários Carregados (amostra)",
                value=usuarios_info or "Nenhum usuário encontrado",
                inline=False
            )
        
        await msg.edit(embed=success_embed)
        
    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Erro ao Recarregar",
            description=f"Erro: {str(e)}",
            color=0xFF0000
        )
        await msg.edit(embed=error_embed)

@bot.command(name='corrigir_dados')
async def corrigir_dados(ctx):
    """Corrige documentos no MongoDB que não têm discord_id"""
    # Só o dono do bot pode usar
    if str(ctx.author.id) != "983196900910039090":
        await ctx.reply("❌ Apenas o dono do bot pode usar este comando!")
        return
    
    if db is None:
        await ctx.reply("❌ MongoDB não conectado!")
        return
    
    embed = discord.Embed(
        title="🔧 Corrigindo Dados MongoDB",
        description="Procurando documentos sem discord_id...",
        color=0xFFD700
    )
    msg = await ctx.reply(embed=embed)
    
    try:
        collection = db.user_data
        documents_without_discord_id = collection.find({"discord_id": {"$exists": False}})
        
        corrected = 0
        failed = 0
        
        for doc in documents_without_discord_id:
            username = doc['_id']
            print(f"🔧 Tentando corrigir documento: @{username}")
            
            # Se o username parece ser um ID do Discord
            if username.isdigit() and len(username) >= 17:
                # Atualiza o documento adicionando discord_id
                collection.update_one(
                    {"_id": username},
                    {"$set": {"discord_id": username}}
                )
                corrected += 1
                print(f"✅ Corrigido: {username} agora tem discord_id")
            else:
                # Tenta encontrar o usuário no servidor
                found = False
                for member in bot.get_all_members():
                    if member.display_name.lower() == username.lower() or member.name.lower() == username.lower():
                        # Encontrou! Adiciona o discord_id
                        collection.update_one(
                            {"_id": username},
                            {"$set": {"discord_id": str(member.id)}}
                        )
                        corrected += 1
                        found = True
                        print(f"✅ Corrigido: @{username} -> discord_id: {member.id}")
                        break
                
                if not found:
                    failed += 1
                    print(f"❌ Não encontrado: @{username}")
        
        # Recarrega os dados
        load_user_data()
        
        success_embed = discord.Embed(
            title="✅ Correção Concluída!",
            description="Dados do MongoDB foram corrigidos",
            color=0x00FF00
        )
        
        success_embed.add_field(
            name="📊 Resultado",
            value=f"✅ **{corrected}** documentos corrigidos\n❌ **{failed}** documentos não encontrados\n🔄 **{len(user_data)}** usuários carregados",
            inline=False
        )
        
        success_embed.add_field(
            name="🎯 Próximos Passos",
            value="Os rankings agora devem mostrar os usuários corretamente!",
            inline=False
        )
        
        await msg.edit(embed=success_embed)
        
    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Erro na Correção",
            description=f"Erro: {str(e)}",
            color=0xFF0000
        )
        await msg.edit(embed=error_embed)

@bot.command(name='status_dados')
async def status_dados(ctx):
    # Só o dono do bot pode usar
    if str(ctx.author.id) != "983196900910039090":
        await ctx.reply("❌ Apenas o dono do bot pode usar este comando!")
        return
    
    embed = discord.Embed(
        title="📊 Status dos Dados do Bot",
        description="Informações sobre persistência de dados no MongoDB",
        color=0x00FF00
    )
    
    embed.add_field(
        name="👥 Usuários Registrados",
        value=f"**{len(user_data)}** usuários",
        inline=True
    )
    
    embed.add_field(
        name="💰 Dados de Economia",
        value=f"**{len(economy_data)}** usuários",
        inline=True
    )
    
    embed.add_field(
        name="🤝 Relacionamentos",
        value=f"**{len(follow_data)}** usuários",
        inline=True
    )
    
    embed.add_field(
        name="📦 Inventários",
        value=f"**{len(inventory_data)}** usuários",
        inline=True
    )
    
    embed.add_field(
        name="📝 Posts com Marcas",
        value=f"**{len(brand_posts_data)}** usuários",
        inline=True
    )
    
    embed.add_field(
        name="🔄 Sistema de Reset",
        value=f"**{len(reset_data)}** usuários usaram",
        inline=True
    )
    
    # Status da conexão MongoDB
    mongodb_status = "✅ Conectado" if db is not None else "❌ Desconectado"
    
    embed.add_field(
        name="🍃 Status MongoDB",
        value=mongodb_status,
        inline=False
    )
    
    try:
        if db is not None:
            # Verifica quantos documentos existem em cada coleção
            collections_info = []
            collections_info.append(f"👥 user_data: {db.user_data.count_documents({})} docs")
            collections_info.append(f"💰 economy_data: {db.economy_data.count_documents({})} docs")
            collections_info.append(f"🤝 follow_data: {db.follow_data.count_documents({})} docs")
            collections_info.append(f"📦 inventory_data: {db.inventory_data.count_documents({})} docs")
            collections_info.append(f"📝 brand_posts_data: {db.brand_posts_data.count_documents({})} docs")
            collections_info.append(f"🔄 reset_data: {db.reset_data.count_documents({})} docs")
            
            embed.add_field(
                name="📚 Coleções MongoDB",
                value="\n".join(collections_info),
                inline=False
            )
    except Exception as e:
        embed.add_field(
            name="⚠️ Erro ao verificar MongoDB",
            value=f"Erro: {str(e)[:100]}...",
            inline=False
        )
    
    embed.set_footer(text="Sistema MongoDB v3.0")
    await ctx.reply(embed=embed)

# Comando para verificar atividade recente
@bot.command(name='atividade')
async def atividade(ctx):
    user_id = str(ctx.author.id)

    if user_id not in user_data:
        embed = discord.Embed(
            title="❌ Registro necessário",
            description="Você precisa se registrar primeiro!",
            color=0xFF0000
        )
        await ctx.reply(embed=embed)
        return

    # Pega dados do usuário
    user_info = user_data[user_id]
    likes = user_info.get('total_likes', 0)
    followers = user_info.get('followers', 0)
    following_count = len(follow_data.get(user_id, {}).get("following", []))
    followers_count = len(follow_data.get(user_id, {}).get("followers", []))

    # Calcula pontuação de atividade
    activity_score = (likes * 2) + (following_count * 5) + (followers_count * 3)

    # Classifica atividade
    if activity_score >= 1000:
        status = "🔥 SUPER ATIVO"
        cor = 0xFF0000
    elif activity_score >= 500:
        status = "⚡ MUITO ATIVO"
        cor = 0xFF6B35
    elif activity_score >= 200:
        status = "📈 ATIVO"
        cor = 0xFFD23F
    elif activity_score >= 50:
        status = "📊 MODERADO"
        cor = 0x06FFA5
    else:
        status = "😴 POUCO ATIVO"
        cor = 0x95E1D3

    embed = discord.Embed(
        title="📱 Relatório de Atividade",
        description=f"Análise da atividade de **{ctx.author.display_name}**",
        color=cor
    )

    embed.add_field(
        name="🏆 Pontuação de Atividade",
        value=f"**{activity_score:,}** pontos".replace(",", "."),
        inline=True
    )

    embed.add_field(
        name="📊 Status",
        value=status,
        inline=True
    )

    embed.add_field(
        name="📈 Estatísticas Detalhadas",
        value=f"💖 **{likes:,}** curtidas recebidas\n👥 **{following_count}** pessoas seguindo\n👤 **{followers_count}** seguidores reais\n📊 **{followers:,}** seguidores totais".replace(",", "."),
        inline=False
    )

    # Dicas baseadas na atividade
    if activity_score < 100:
        embed.add_field(
            name="💡 Dicas para Aumentar Atividade",
            value="• Envie mais mensagens nos canais\n• Siga mais pessoas com `m!seguir`\n• Interaja mais com a comunidade",
            inline=False
        )

    embed.set_thumbnail(url=ctx.author.display_avatar.url)
    embed.set_footer(text=f"Dev: YevgennyMXP • Relatório gerado para {ctx.author.display_name}")

    await ctx.reply(embed=embed)

# Comando para mostrar amigos mútuos de um usuário
@bot.command(name='amigos')
async def amigos(ctx, member: discord.Member = None):
    if member is None:
        member = ctx.author

    user_id = str(member.id)

    # Verifica se o usuário está registrado
    if user_id not in user_data:
        if member == ctx.author:
            embed = discord.Embed(
                title="❌ Registro necessário",
                description="Você precisa se registrar primeiro!",
                color=0xFF0000
            )
            embed.add_field(
                name="📝 Como se registrar:",
                value="Use o comando `m!seguidores` para criar seu perfil",
                inline=False
            )
            await ctx.reply(embed=embed)
        else:
            await ctx.reply(f"❌ {member.display_name} ainda não se registrou!")
        return

    # Pega dados de relacionamentos
    user_following = follow_data.get(user_id, {}).get("following", [])
    user_followers = follow_data.get(user_id, {}).get("followers", [])

    # Encontra amigos mútuos (pessoas que seguem e são seguidas de volta)
    mutual_friends = []
    for friend_id in user_following:
        if friend_id in user_followers:  # Se está nas duas listas = amigo mútuo
            try:
                friend_user = bot.get_user(int(friend_id))
                if friend_user and friend_id in user_data:
                    friend_followers = user_data[friend_id].get('followers', 0)
                    mutual_friends.append((friend_id, friend_user, friend_followers))
            except:
                continue

    embed = discord.Embed(
        title=f"🤝 Amigos de {member.display_name}",
        description="Pessoas que vocês se seguem mutuamente",
        color=0xFF69B4
    )
    embed.set_thumbnail(url=member.display_avatar.url)

    if not mutual_friends:
        embed.add_field(
            name="😢 Nenhum Amigo Mútuo",
            value=f"**{member.display_name}** ainda não tem amigos mútuos.\n\n💡 Para fazer amigos, use `m!seguir @usuario` e peça para te seguirem de volta!",
            inline=False
        )
    else:
        # Ordena amigos por quantidade de seguidores (mais influentes primeiro)
        mutual_friends.sort(key=lambda x: x[2], reverse=True)

        friends_text = ""
        for i, (friend_id, friend_user, friend_followers) in enumerate(mutual_friends[:10]):  # Mostra até 10
            try:
                # Pega o username do Instagram
                username = user_data[friend_id].get('username', friend_user.display_name)

                # Adiciona verificação baseada nos níveis de seguidores
                verification = ""
                if friend_id == "983196900910039090":  # Owner ID
                    verification = " <:extremomxp:1387842927602172125>"
                elif friend_followers >= 1000000:
                    verification = " <:abudabimxp:1387843390506405922>"
                elif friend_followers >= 500000:
                    verification = " <:verificadomxp:1387605173886783620>"
                else:
                    verification = " <:verificiadinmxp:1387842858912055428>"

                # Adiciona emoji baseado na quantidade de seguidores
                if friend_followers >= 25000000:
                    emoji = "👑"
                    status = " (Dono do Bot)"
                elif friend_followers >= 5000000:
                    emoji = "💎"
                    status = " (Mega Influencer)"
                elif friend_followers >= 1000000:
                    emoji = "🔥"
                    status = " (Influencer)"
                elif friend_followers >= 500000:
                    emoji = "⭐"
                    status = " (Verificado)"
                elif friend_followers >= 100000:
                    emoji = "📈"
                    status = " (Em Alta)"
                elif friend_followers >= 50000:
                    emoji = "🌟"
                    status = " (Popular)"
                else:
                    emoji = "💕"
                    status = " (Amigo)"

                # Formata os seguidores
                if friend_followers > 0:
                    followers_formatted = f"{friend_followers:,}".replace(",", ".")
                    followers_info = f" • {followers_formatted} seguidores"
                else:
                    followers_info = " • Sem seguidores"

                friends_text += f"`{i+1:2d}.` {emoji} **@{username}**{verification}{status}\n      {followers_info}\n"

            except Exception as e:
                print(f"Erro ao processar amigo {friend_id}: {e}")
                continue

        if friends_text:
            embed.add_field(
                name=f"💕 Lista de Amigos ({len(mutual_friends)} total)",
                value=friends_text,
                inline=False
            )

        if len(mutual_friends) > 10:
            remaining = len(mutual_friends) - 10
            embed.add_field(
                name="📋 Lista Completa",
                value=f"➕ **{remaining}** amigos a mais não mostrados.",
                inline=False
            )

        # Estatísticas de amizade
        total_following = len(user_following)
        total_followers = len(user_followers)
        friendship_rate = (len(mutual_friends) / max(total_following, 1)) * 100

        embed.add_field(
            name="📊 Estatísticas de Amizade",
            value=f"• **{len(mutual_friends)}** amigos mútuos\n• **{total_following}** pessoas seguindo\n• **{total_followers}** seguidores reais\n• **{friendship_rate:.1f}%** taxa de reciprocidade",
            inline=False
        )

    

    embed.set_footer(
        text=f"Consultado por {ctx.author.display_name} • Sistema de Amizades v2.0",
        icon_url=ctx.author.display_avatar.url
    )

    await ctx.reply(embed=embed)

# Comando para top amizades (relacionamentos mútuos)
@bot.command(name='amizades')
async def amizades(ctx):
    mutual_friends = []

    # Procura por relacionamentos mútuos
    for user_id, data in follow_data.items():
        following = data.get("following", [])
        followers = data.get("followers", [])

        for friend_id in following:
            if friend_id in followers:  # Se estão nas duas listas, são amigos mútuos
                # Evita duplicatas ordenando os IDs
                pair = tuple(sorted([user_id, friend_id]))
                if pair not in [tuple(sorted([u1, u2])) for u1, u2, _ in mutual_friends]:
                    try:
                        user1 = bot.get_user(int(user_id))
                        user2 = bot.get_user(int(friend_id))
                        if user1 and user2 and user_id in user_data and friend_id in user_data:
                            # Calcula "força da amizade" baseada na soma dos seguidores
                            strength = user_data[user_id].get('followers', 0) + user_data[friend_id].get('followers', 0)
                            mutual_friends.append((user_id, friend_id, strength))
                    except:
                        continue

    if not mutual_friends:
        embed = discord.Embed(
            title="😢 Nenhuma Amizade Encontrada",
            description="Ainda não há amizades mútuas no servidor!",
            color=0x9932CC
        )
        embed.add_field(
            name="💡 Como Fazer Amizades",
            value="Use `m!seguir @usuario` e peça para te seguirem de volta!",
            inline=False
        )
        await ctx.reply(embed=embed)
        return

    # Ordena por força da amizade
    mutual_friends.sort(key=lambda x: x[2], reverse=True)

    embed = discord.Embed(
        title="🤝 Top Amizades do Servidor",
        description="Relacionamentos mútuos mais fortes:",
        color=0xFF69B4
    )

    for i, (user_id1, user_id2, strength) in enumerate(mutual_friends[:10]):
        try:
            user1 = bot.get_user(int(user_id1))
            user2 = bot.get_user(int(user_id2))

            username1 = user_data[user_id1].get('username', user1.display_name)
            username2 = user_data[user_id2].get('username', user2.display_name)

            # Adiciona verificação baseada nos níveis de seguidores
            followers1 = user_data[user_id1].get('followers', 0)
            followers2 = user_data[user_id2].get('followers', 0)
            
            if user_id1 == "983196900910039090":
                username1 += " <:extremomxp:1387842927602172125>"
            elif followers1 >= 1000000:
                username1 += " <:abudabimxp:1387843390506405922>"
            elif followers1 >= 500000:
                username1 += " <:verificadomxp:1387605173886783620>"
            else:
                username1 += " <:verificiadinmxp:1387842858912055428>"
                
            if user_id2 == "983196900910039090":
                username2 += " <:extremomxp:1387842927602172125>"
            elif followers2 >= 1000000:
                username2 += " <:abudabimxp:1387843390506405922>"
            elif followers2 >= 500000:
                username2 += " <:verificadomxp:1387605173886783620>"
            else:
                username2 += " <:verificiadinmxp:1387842858912055428>"

            # Emoji baseado na posição
            if i == 0:
                emoji = "👑"
            elif i == 1:
                emoji = "💎"
            elif i == 2:
                emoji = "🔥"
            else:
                emoji = "💕"

            embed.add_field(
                name=f"{emoji} Amizade #{i+1}",
                value=f"**@{username1}** ↔️ **@{username2}**\n💪 Força: {strength:,}".replace(",", "."),
                inline=False
            )
        except:
            continue

    embed.set_footer(text=f"Dev: YevgennyMXP • Consultado por {ctx.author.display_name}")
    await ctx.reply(embed=embed)

# Comando da lojinha
@bot.command(name='lojinha', aliases=['loja', 'shop'])
async def lojinha(ctx):
    user_id = str(ctx.author.id)

    # Verifica se o usuário está registrado
    if user_id not in user_data:
        embed = discord.Embed(
            title="❌ Registro necessário",
            description="Você precisa se registrar primeiro!",
            color=0xFF0000
        )
        embed.add_field(
            name="📝 Como se registrar:",
            value="Use o comando `m!seguidores` para criar seu perfil",
            inline=False
        )
        await ctx.reply(embed=embed)
        return

    # Inicializa dados de economia se não existir
    if user_id not in economy_data:
        economy_data[user_id] = {"money": 0, "fame": 0}

    # Inicializa inventário se não existir
    if user_id not in inventory_data:
        inventory_data[user_id] = {"carros": [], "mansoes": [], "itens_diarios": []}

    # Embed principal da loja
    embed = discord.Embed(
        title="🛒 Instagram MXP - Lojinha",
        description="Bem-vindo à lojinha! Use seu dinheiro ganho com publicidade para comprar itens incríveis!",
        color=0xE4405F
    )

    user_money = economy_data[user_id].get("money", 0)
    embed.add_field(
        name="💰 Seu Dinheiro",
        value=f"R$ {user_money:,}".replace(",", "."),
        inline=True
    )

    # Mostra quantos itens possui
    user_inventory = inventory_data[user_id]
    total_items = len(user_inventory["carros"]) + len(user_inventory["mansoes"]) + len(user_inventory["itens_diarios"])
    
    embed.add_field(
        name="📦 Seus Itens",
        value=f"{total_items} itens no inventário",
        inline=True
    )

    embed.add_field(
        name="🛍️ Categorias Disponíveis",
        value="🚗 **Carros** - Do Gol ao Bugatti\n🏰 **Mansões** - De casas simples a palácios\n🛍️ **Itens do Dia a Dia** - Comida, eletrônicos e mais!",
        inline=False
    )

    if user_money < 15:  # Preço do item mais barato
        embed.add_field(
            name="💡 Como Ganhar Dinheiro",
            value="• Mencione marcas famosas em posts longos (40+ caracteres)\n• Use `m!publi` para ver seu histórico\n• Quanto mais marcas, mais dinheiro!",
            inline=False
        )

    embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/thumb/a/a5/Instagram_icon.png/1024px-Instagram_icon.png")
    embed.set_footer(text=f"Loja aberta por {ctx.author.display_name} • Use os botões para navegar")

    # View com botões principais
    view = LojaMainView(user_id)
    await ctx.reply(embed=embed, view=view)

# Comando para verificar compatibilidade entre usuários
@bot.command(name='compatibilidade')
async def compatibilidade(ctx, member: discord.Member = None):
    if member is None:
        embed = discord.Embed(
            title="❌ Erro",
            description="Você precisa mencionar um usuário para verificar compatibilidade!",
            color=0xFF0000
        )
        embed.add_field(
            name="📝 Uso correto:",
            value="`m!compatibilidade @usuario`",
            inline=False
        )
        await ctx.reply(embed=embed)
        return

    if member.id == ctx.author.id:
        embed = discord.Embed(
            title="😅 Autocompatibilidade",
            description="Você é 100% compatível consigo mesmo! 🤔",
            color=0x9932CC
        )
        await ctx.reply(embed=embed)
        return

    user1_id = str(ctx.author.id)
    user2_id = str(member.id)

    if user1_id not in user_data or user2_id not in user_data:
        embed = discord.Embed(
            title="❌ Usuários não registrados",
            description="Ambos os usuários precisam estar registrados!",
            color=0xFF0000
        )
        await ctx.reply(embed=embed)
        return

    # Dados dos usuários
    user1_data = user_data[user1_id]
    user2_data = user_data[user2_id]

    # Calcula compatibilidade baseada em vários fatores
    factors = []

    # Fator 1: Diferença de seguidores (quanto mais próximo, maior compatibilidade)
    followers1 = user1_data.get('followers', 0)
    followers2 = user2_data.get('followers', 0)
    if max(followers1, followers2) > 0:
        followers_compatibility = min(followers1, followers2) / max(followers1, followers2) * 100
    else:
        followers_compatibility = 100
    factors.append(followers_compatibility)

    # Fator 2: Diferença de curtidas
    likes1 = user1_data.get('total_likes', 0)
    likes2 = user2_data.get('total_likes', 0)
    if max(likes1, likes2) > 0:
        likes_compatibility = min(likes1, likes2) / max(likes1, likes2) * 100
    else:
        likes_compatibility = 100
    factors.append(likes_compatibility)

    # Fator 3: Se já se seguem mutuamente (+30 pontos)
    mutual_following = 0
    if user1_id in follow_data and user2_id in follow_data:
        if user2_id in follow_data[user1_id].get("following", []) and user1_id in follow_data[user2_id].get("following", []):
            mutual_following = 30
    factors.append(mutual_following)

    # Fator 4: Fator aleatório para variedade
    import random
    random_factor = random.randint(0, 20)
    factors.append(random_factor)

    # Calcula compatibilidade final
    final_compatibility = min(100, sum(factors) / len(factors))

    # Define emoji e cor baseado na compatibilidade
    if final_compatibility >= 90:
        emoji = "💕"
        status = "ALMA GÊMEA"
        cor = 0xFF1493
    elif final_compatibility >= 80:
        emoji = "💖"
        status = "SUPER COMPATÍVEIS"
        cor = 0xFF69B4
    elif final_compatibility >= 70:
        emoji = "💝"
        status = "MUITO COMPATÍVEIS"
        cor = 0xFFB6C1
    elif final_compatibility >= 60:
        emoji = "💘"
        status = "BOA COMPATIBILIDADE"
        cor = 0xFFC0CB
    elif final_compatibility >= 40:
        emoji = "💗"
        status = "COMPATIBILIDADE MÉDIA"
        cor = 0xDDA0DD
    else:
        emoji = "💔"
        status = "POUCO COMPATÍVEIS"
        cor = 0x708090

    embed = discord.Embed(
        title=f"{emoji} Teste de Compatibilidade",
        description=f"Compatibilidade entre **{ctx.author.display_name}** e **{member.display_name}**",
        color=cor
    )

    embed.add_field(
        name="💯 Resultado",
        value=f"**{final_compatibility:.1f}%**",
        inline=True
    )

    embed.add_field(
        name="🏆 Status",
        value=f"**{status}**",
        inline=True
    )

    # Análise detalhada
    analysis = []
    if followers_compatibility > 80:
        analysis.append("✅ Seguidores similares")
    if likes_compatibility > 80:
        analysis.append("✅ Curtidas similares")
    if mutual_following > 0:
        analysis.append("✅ Já são amigos mútuos")
    if not analysis:
        analysis.append("📊 Perfis diferentes")

    embed.add_field(
        name="📊 Análise",
        value="\n".join(analysis),
        inline=False
    )

    # Dica baseada no resultado
    if final_compatibility >= 70:
        tip = "🎉 Vocês combinam muito! Que tal colaborarem em algum projeto?"
    elif final_compatibility >= 50:
        tip = "👥 Boa compatibilidade! Sigam um ao outro para se tornarem amigos."
    else:
        tip = "🌱 Relacionamento pode crescer com mais interação!"

    embed.add_field(
        name="💡 Dica",
        value=tip,
        inline=False
    )

    embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1387605173886783620.png")
    embed.set_footer(text=f"Dev: YevgennyMXP • Teste solicitado por {ctx.author.display_name}")

    await ctx.reply(embed=embed)



# Sistema de leaderboard com menu dropdown elegante e paginação
class LeaderboardCategorySelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="👥 Seguidores Totais",
                description="Ranking dos usuários com mais seguidores no Instagram",
                emoji="👥",
                value="seguidores"
            ),
            discord.SelectOption(
                label="💖 Mais Curtidos",
                description="Usuários que receberam mais curtidas nas mensagens",
                emoji="💖",
                value="curtidas"
            ),
            discord.SelectOption(
                label="💰 Mais Ricos",
                description="Ranking dos usuários com mais dinheiro acumulado",
                emoji="💰",
                value="dinheiro"
            ),
            discord.SelectOption(
                label="🤝 Seguidores Reais",
                description="Usuários com mais seguidores do servidor (jogadores reais)",
                emoji="🤝",
                value="reais"
            ),
            discord.SelectOption(
                label="⭐ Pontos de Fama",
                description="Ranking baseado nos pontos de fama acumulados",
                emoji="⭐",
                value="fama"
            ),
            discord.SelectOption(
                label="📊 Mais Ativos",
                description="Usuários com maior pontuação de atividade geral",
                emoji="📊",
                value="atividade"
            ),
            discord.SelectOption(
                label="💎 Level Máximo",
                description="Usuários com os maiores levels (baseado em curtidas)",
                emoji="💎",
                value="level"
            )
        ]
        
        super().__init__(
            placeholder="📋 Selecione uma categoria de ranking...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        await show_ranking_page(interaction, category, 1)

class LeaderboardPaginationView(discord.ui.View):
    def __init__(self, category, page, total_pages, sorted_data):
        super().__init__(timeout=300)
        self.category = category
        self.page = page
        self.total_pages = total_pages
        self.sorted_data = sorted_data
        
        # Adiciona botões de navegação
        if page > 1:
            self.prev_button.disabled = False
        else:
            self.prev_button.disabled = True
            
        if page < total_pages:
            self.next_button.disabled = False
        else:
            self.next_button.disabled = True

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.secondary, disabled=True)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await show_ranking_page(interaction, self.category, self.page - 1)

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.secondary, disabled=True)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await show_ranking_page(interaction, self.category, self.page + 1)

    @discord.ui.button(label="🔙 Voltar ao Menu", style=discord.ButtonStyle.primary, row=1)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await show_main_leaderboard(interaction)

def get_ranking_data(category):
    """Obtém e organiza dados para um ranking específico"""
    print(f"🔍 DEBUG: Executando get_ranking_data para categoria '{category}'")
    print(f"🔍 DEBUG: Total de usuários em user_data: {len(user_data)}")
    
    if category == "seguidores":
        # Filtra usuários com seguidores e que têm username
        valid_users = []
        for user_id, data in user_data.items():
            followers = data.get('followers', 0)
            username = data.get('username')
            print(f"🔍 DEBUG: Analisando user_id {user_id}: username='{username}', followers={followers}")
            
            # Debug detalhado da validação
            has_followers = followers > 0
            has_username = username is not None and str(username).strip() != ""
            print(f"🔍 DEBUG: has_followers={has_followers}, has_username={has_username}, username_stripped='{str(username).strip() if username else 'None'}'")
            
            # Só inclui usuários que tem seguidores E tem username definido (não None e não vazio)
            if has_followers and has_username:
                # Formato: (username, data, valor, tem_discord_user)
                valid_users.append((username, data, followers, True))
                print(f"✅ DEBUG: Usuário @{username} INCLUÍDO no ranking")
            else:
                print(f"❌ DEBUG: Usuário {user_id} EXCLUÍDO - followers: {followers}, username: '{username}'")
        
        sorted_users = sorted(valid_users, key=lambda x: x[2], reverse=True)
        print(f"✅ DEBUG: Ranking seguidores final: {len(sorted_users)} usuários válidos")
        for i, (username, data, followers, has_user) in enumerate(sorted_users[:5]):
            print(f"🏆 DEBUG: #{i+1} - @{username} - {followers} seguidores")
        
        return sorted_users
    
    elif category == "curtidas":
        # Inclui apenas usuários que têm username definido
        valid_users = []
        for user_id, data in user_data.items():
            likes = data.get('total_likes', 0)
            username = data.get('username')
            if username and username.strip():
                valid_users.append((username, data, likes, True))
        return sorted(valid_users, key=lambda x: x[2], reverse=True)
    
    elif category == "dinheiro":
        users_with_money = []
        for user_id, data in user_data.items():
            username = data.get('username')
            # Só inclui se tem username
            if not (username and username.strip()):
                continue
            # Inicializa economia se não existir
            if user_id not in economy_data:
                economy_data[user_id] = {"money": 0, "fame": 0}
            money = economy_data[user_id].get('money', 0)
            users_with_money.append((username, data, money, True))
        return sorted(users_with_money, key=lambda x: x[2], reverse=True)
    
    elif category == "reais":
        users_with_real_followers = []
        for user_id, data in user_data.items():
            username = data.get('username')
            # Só inclui se tem username
            if not (username and username.strip()):
                continue
            real_followers = len(follow_data.get(user_id, {}).get("followers", []))
            users_with_real_followers.append((username, data, real_followers, True))
        return sorted(users_with_real_followers, key=lambda x: x[2], reverse=True)
    
    elif category == "fama":
        users_with_fame = []
        for user_id, data in user_data.items():
            username = data.get('username')
            # Só inclui se tem username
            if not (username and username.strip()):
                continue
            # Inicializa economia se não existir
            if user_id not in economy_data:
                economy_data[user_id] = {"money": 0, "fame": 0}
            fame = economy_data[user_id].get('fame', 0)
            users_with_fame.append((username, data, fame, True))
        return sorted(users_with_fame, key=lambda x: x[2], reverse=True)
    
    elif category == "atividade":
        users_with_activity = []
        for user_id, data in user_data.items():
            username = data.get('username')
            # Só inclui se tem username
            if not (username and username.strip()):
                continue
            likes = data.get('total_likes', 0)
            following_count = len(follow_data.get(user_id, {}).get("following", []))
            followers_count = len(follow_data.get(user_id, {}).get("followers", []))
            activity_score = (likes * 2) + (following_count * 5) + (followers_count * 3)
            users_with_activity.append((username, data, activity_score, True))
        return sorted(users_with_activity, key=lambda x: x[2], reverse=True)
    
    elif category == "level":
        users_with_level = []
        for user_id, data in user_data.items():
            username = data.get('username')
            # Só inclui se tem username
            if not (username and username.strip()):
                continue
            likes = data.get('total_likes', 0)
            if user_id == "983196900910039090":  # Owner ID
                level = 500
            else:
                level = min(likes // 10, 100)
            users_with_level.append((username, data, level, True))
        return sorted(users_with_level, key=lambda x: x[2], reverse=True)
    
    return []

def get_ranking_config(category):
    """Retorna configuração específica para cada tipo de ranking"""
    configs = {
        "seguidores": {
            "title": "👥 Top Seguidores Totais",
            "description": "Usuários com mais seguidores no Instagram",
            "color": 0x9932CC,
            "value_key": "followers",
            "value_format": lambda x: f"👥 {x:,} seguidores".replace(",", "."),
            "emoji": "👥"
        },
        "curtidas": {
            "title": "💖 Top Mais Curtidos",
            "description": "Usuários com mais curtidas recebidas",
            "color": 0xFF69B4,
            "value_key": "total_likes",
            "value_format": lambda x: f"💖 {x:,} curtidas".replace(",", "."),
            "emoji": "💖"
        },
        "dinheiro": {
            "title": "💰 Top Mais Ricos",
            "description": "Usuários com mais dinheiro acumulado",
            "color": 0xFFD700,
            "value_key": None,  # Valor vem do terceiro elemento da tupla
            "value_format": lambda x: f"💰 R$ {x:,}".replace(",", "."),
            "emoji": "💰"
        },
        "reais": {
            "title": "🤝 Top Seguidores Reais",
            "description": "Usuários com mais seguidores do servidor",
            "color": 0x1DA1F2,
            "value_key": None,  # Valor vem do terceiro elemento da tupla
            "value_format": lambda x: f"🤝 {x:,} seguidores reais".replace(",", "."),
            "emoji": "🤝"
        },
        "fama": {
            "title": "⭐ Top Pontos de Fama",
            "description": "Usuários com mais pontos de fama",
            "color": 0xFFE135,
            "value_key": None,  # Valor vem do terceiro elemento da tupla
            "value_format": lambda x: f"⭐ {x:,} pontos de fama".replace(",", "."),
            "emoji": "⭐"
        },
        "atividade": {
            "title": "📊 Top Mais Ativos",
            "description": "Usuários com maior atividade no servidor",
            "color": 0x00D2FF,
            "value_key": None,  # Valor vem do terceiro elemento da tupla
            "value_format": lambda x: f"📊 {x:,} pontos de atividade".replace(",", "."),
            "emoji": "📊"
        },
        "level": {
            "title": "💎 Top Levels",
            "description": "Usuários com os maiores levels",
            "color": 0x6A0DAD,
            "value_key": None,  # Valor vem do terceiro elemento da tupla
            "value_format": lambda x: f"💎 Level {x}",
            "emoji": "💎"
        }
    }
    return configs.get(category, configs["seguidores"])

async def show_ranking_page(interaction, category, page):
    """Mostra uma página específica do ranking"""
    print(f"🔍 DEBUG: show_ranking_page chamada - categoria: {category}, página: {page}")
    
    config = get_ranking_config(category)
    sorted_data = get_ranking_data(category)
    
    print(f"🔍 DEBUG: sorted_data retornado: {len(sorted_data)} itens")
    for i, item in enumerate(sorted_data[:3]):
        print(f"🔍 DEBUG: Item {i}: {item}")
    
    # Converte dados para formato padrão - agora usando username diretamente
    valid_users = []
    for item in sorted_data:
        if len(item) == 4:  # Formato (username, data, value, has_user)
            username, data, value, has_user = item
            valid_users.append((username, data, value, None))  # None = não precisa do objeto user
            print(f"✅ DEBUG: Usuário válido adicionado: @{username} - {value}")
        else:
            print(f"❌ DEBUG: Formato inválido: {item}")
            continue
    
    print(f"🔍 DEBUG: valid_users final: {len(valid_users)} usuários")
    
    if not valid_users:
        print(f"❌ DEBUG: Nenhum usuário válido encontrado!")
        embed = discord.Embed(
            title=config["title"],
            description="❌ Nenhum usuário encontrado nesta categoria ainda.\n\nOs usuários aparecerão aqui após se registrarem com `m!seguidores`!",
            color=config["color"]
        )
        embed.add_field(
            name="💡 Como aparecer no ranking:",
            value="1. Use `m!seguidores` para se registrar\n2. Use `m!atualizar` para definir seu nome\n3. Interaja no servidor para ganhar curtidas/seguidores",
            inline=False
        )
        embed.add_field(
            name="🔧 Debug Info:",
            value=f"• Dados encontrados: {len(sorted_data)}\n• Usuários válidos: {len(valid_users)}\n• Categoria: {category}",
            inline=False
        )
        view = discord.ui.View()
        back_button = discord.ui.Button(label="🔙 Voltar ao Menu", style=discord.ButtonStyle.primary)
        back_button.callback = lambda i: show_main_leaderboard(i)
        view.add_item(back_button)
        await interaction.response.edit_message(embed=embed, view=view)
        return
    
    # Paginação
    per_page = 10
    total_pages = (len(valid_users) + per_page - 1) // per_page
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_users = valid_users[start_idx:end_idx]
    
    print(f"🔍 DEBUG: Paginação - total_pages: {total_pages}, page_users: {len(page_users)}")
    
    # Cria embed
    embed = discord.Embed(
        title=config["title"],
        description=f"{config['description']} • Página {page} de {total_pages}",
        color=config["color"]
    )
    
    # Ranking da página
    ranking_text = ""
    for i, (username, data, value, user_obj) in enumerate(page_users):
        global_position = start_idx + i + 1
        # Username já vem direto dos dados
        display_username = username
        followers = data.get('followers', 0)
        
        print(f"🔍 DEBUG: Processando usuário {i+1}: @{username} - valor: {value}")
        
        # Adiciona verificação baseada nos seguidores
        if followers >= 25000000:  # Owner level
            display_username += " <:extremomxp:1387842927602172125>"
        elif followers >= 1000000:
            display_username += " <:abudabimxp:1387843390506405922>"
        elif followers >= 500000:
            display_username += " <:verificadomxp:1387605173886783620>"
        else:
            display_username += " <:verificiadinmxp:1387842858912055428>"
        
        # Medal baseado na posição global
        if global_position == 1:
            medal = "👑"
        elif global_position == 2:
            medal = "🥈"
        elif global_position == 3:
            medal = "🥉"
        else:
            medal = f"`{global_position:2d}`"
        
        value_text = config["value_format"](value)
        ranking_text += f"{medal} **@{display_username}**\n      {value_text}\n\n"
    
    print(f"🔍 DEBUG: ranking_text final length: {len(ranking_text)}")
    print(f"🔍 DEBUG: ranking_text preview: {ranking_text[:200]}...")
    
    if ranking_text.strip():
        embed.add_field(name="🏅 Ranking", value=ranking_text.strip(), inline=False)
    else:
        embed.add_field(name="🏅 Ranking", value="⚠️ Erro ao gerar ranking - debug ativo", inline=False)
        embed.add_field(name="🔧 Debug", value=f"Usuários: {len(page_users)}\nCategoria: {category}\nValores: {[u[2] for u in page_users]}", inline=False)
    
    # Estatísticas da categoria
    if valid_users:
        leader_value = valid_users[0][2]
        total_users = len(valid_users)
        average_value = sum(item[2] for item in valid_users) / total_users
        
        stats_text = f"👑 **Líder:** {config['value_format'](leader_value)}\n"
        stats_text += f"📊 **Média:** {config['value_format'](int(average_value))}\n"
        stats_text += f"👥 **Total ativo:** {total_users} usuários"
        
        embed.add_field(name="📈 Estatísticas", value=stats_text, inline=False)
    
    embed.set_thumbnail(url=f"https://cdn.discordapp.com/emojis/1376731577106567319.png")
    embed.set_footer(text=f"Página {page} de {total_pages} • Solicitado por {interaction.user.display_name}")
    
    # View com botões de navegação
    view = LeaderboardPaginationView(category, page, total_pages, valid_users)
    
    print(f"🔍 DEBUG: Enviando embed para Discord...")
    print(f"🔍 DEBUG: Embed title: {embed.title}")
    print(f"🔍 DEBUG: Embed fields: {len(embed.fields)}")
    
    try:
        await interaction.response.edit_message(embed=embed, view=view)
        print(f"✅ DEBUG: Embed enviado com sucesso!")
    except Exception as e:
        print(f"❌ DEBUG: Erro ao enviar embed: {e}")
        # Fallback embed mais simples
        fallback_embed = discord.Embed(
            title="🔧 Debug Mode - Rankings",
            description=f"Categoria: {category}\nDados encontrados: {len(valid_users)} usuários",
            color=0xFF0000
        )
        
        # Mostra dados de forma mais simples
        simple_ranking = ""
        for i, (user_id, data, value, user) in enumerate(page_users[:5]):
            username = data.get('username') or user.display_name
            simple_ranking += f"{i+1}. {username}: {value}\n"
        
        if simple_ranking:
            fallback_embed.add_field(name="Top Usuários", value=simple_ranking, inline=False)
        
        await interaction.response.edit_message(embed=fallback_embed, view=view)

async def show_main_leaderboard(interaction):
    """Mostra o menu principal do leaderboard"""
    embed = discord.Embed(
        title="🏆 Leaderboard do Instagram MXP",
        description="**Menu Dropdown Elegante** 📋\n\nSelecione uma categoria no menu abaixo para ver os rankings organizados por páginas.",
        color=0xFFD700
    )
    
    total_users = len(user_data)
    total_registered = len([u for u in user_data.values() if u.get('username')])
    
    embed.add_field(
        name="📊 Rankings Disponíveis",
        value="👥 **Seguidores Totais** - Ranking principal por seguidores\n💖 **Mais Curtidos** - Quem recebe mais likes\n💰 **Mais Ricos** - Patrimônio acumulado\n🤝 **Seguidores Reais** - Conexões no servidor\n⭐ **Pontos de Fama** - Fama por publicidade\n📊 **Mais Ativos** - Atividade geral\n💎 **Level Máximo** - Progressão por curtidas",
        inline=False
    )
    
    embed.add_field(
        name="📈 Estatísticas Gerais",
        value=f"📊 **{total_users}** usuários no sistema\n✅ **{total_registered}** usuários ativos\n🏆 Rankings atualizados em tempo real\n📄 **10 usuários** por página",
        inline=False
    )
    
    embed.add_field(
        name="🎯 Como Usar",
        value="1️⃣ Selecione categoria no menu dropdown\n2️⃣ Navegue com ⬅️ ➡️ entre páginas\n3️⃣ Use 🔙 para voltar ao menu principal\n4️⃣ Rankings atualizados automaticamente",
        inline=False
    )
    
    embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1376731577106567319.png")
    embed.set_footer(text=f"Sistema de Rankings v3.0 • Solicitado por {interaction.user.display_name}")
    
    # View com select menu
    view = discord.ui.View(timeout=300)
    view.add_item(LeaderboardCategorySelect())
    
    await interaction.response.edit_message(embed=embed, view=view)

class MainLeaderboardView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(LeaderboardCategorySelect())

# ===== ADMIN-ONLY COMMANDS (HIDDEN) =====
@bot.command(name='addseguidores', hidden=True)
async def add_seguidores(ctx, member: discord.Member = None, quantidade: int = None):
    """Comando secreto para adicionar seguidores (apenas owner)"""
    # Verifica se é o owner
    if str(ctx.author.id) != "983196900910039090":
        return  # Silenciosamente ignora se não for o owner
    
    if member is None or quantidade is None:
        await ctx.reply("❌ Uso: `m!addseguidores @usuario quantidade`", ephemeral=True)
        return
    
    user_id = str(member.id)
    
    # Verifica se o usuário está registrado
    if user_id not in user_data:
        await ctx.reply("❌ Usuário não registrado!", ephemeral=True)
        return
    
    # Adiciona seguidores
    user_data[user_id]['followers'] += quantidade
    save_user_data()
    
    embed = discord.Embed(
        title="✅ Seguidores Adicionados",
        description=f"**+{quantidade:,}** seguidores adicionados para {member.display_name}".replace(",", "."),
        color=0x00FF00
    )
    embed.add_field(
        name="📊 Total Atual",
        value=f"{user_data[user_id]['followers']:,} seguidores".replace(",", "."),
        inline=False
    )
    embed.set_footer(text="🔒 Comando de Administração")
    await ctx.reply(embed=embed, ephemeral=True)

@bot.command(name='removeseguidores', hidden=True)
async def remove_seguidores(ctx, member: discord.Member = None, quantidade: int = None):
    """Comando secreto para remover seguidores (apenas owner)"""
    # Verifica se é o owner
    if str(ctx.author.id) != "983196900910039090":
        return  # Silenciosamente ignora se não for o owner
    
    if member is None or quantidade is None:
        await ctx.reply("❌ Uso: `m!removeseguidores @usuario quantidade`", ephemeral=True)
        return
    
    user_id = str(member.id)
    
    # Verifica se o usuário está registrado
    if user_id not in user_data:
        await ctx.reply("❌ Usuário não registrado!", ephemeral=True)
        return
    
    # Remove seguidores (mínimo 0)
    user_data[user_id]['followers'] = max(0, user_data[user_id]['followers'] - quantidade)
    save_user_data()
    
    embed = discord.Embed(
        title="✅ Seguidores Removidos",
        description=f"**-{quantidade:,}** seguidores removidos de {member.display_name}".replace(",", "."),
        color=0xFF6B35
    )
    embed.add_field(
        name="📊 Total Atual",
        value=f"{user_data[user_id]['followers']:,} seguidores".replace(",", "."),
        inline=False
    )
    embed.set_footer(text="🔒 Comando de Administração")
    await ctx.reply(embed=embed, ephemeral=True)

@bot.command(name='addmoney', hidden=True)
async def add_money(ctx, member: discord.Member = None, quantidade: int = None):
    """Comando secreto para adicionar dinheiro (apenas owner)"""
    # Verifica se é o owner
    if str(ctx.author.id) != "983196900910039090":
        return  # Silenciosamente ignora se não for o owner
    
    if member is None or quantidade is None:
        await ctx.reply("❌ Uso: `m!addmoney @usuario quantidade`", ephemeral=True)
        return
    
    user_id = str(member.id)
    
    # Verifica se o usuário está registrado
    if user_id not in user_data:
        await ctx.reply("❌ Usuário não registrado!", ephemeral=True)
        return
    
    # Inicializa economia se não existir
    if user_id not in economy_data:
        economy_data[user_id] = {"money": 0, "fame": 0}
    
    # Adiciona dinheiro
    economy_data[user_id]["money"] += quantidade
    save_economy_data()
    
    embed = discord.Embed(
        title="✅ Dinheiro Adicionado",
        description=f"**+R$ {quantidade:,}** adicionados para {member.display_name}".replace(",", "."),
        color=0x00FF00
    )
    embed.add_field(
        name="💰 Total Atual",
        value=f"R$ {economy_data[user_id]['money']:,}".replace(",", "."),
        inline=False
    )
    embed.set_footer(text="🔒 Comando de Administração")
    await ctx.reply(embed=embed, ephemeral=True)

@bot.command(name='removemoney', hidden=True)
async def remove_money(ctx, member: discord.Member = None, quantidade: int = None):
    """Comando secreto para remover dinheiro (apenas owner)"""
    # Verifica se é o owner
    if str(ctx.author.id) != "983196900910039090":
        return  # Silenciosamente ignora se não for o owner
    
    if member is None or quantidade is None:
        await ctx.reply("❌ Uso: `m!removemoney @usuario quantidade`", ephemeral=True)
        return
    
    user_id = str(member.id)
    
    # Verifica se o usuário está registrado
    if user_id not in user_data:
        await ctx.reply("❌ Usuário não registrado!", ephemeral=True)
        return
    
    # Inicializa economia se não existir
    if user_id not in economy_data:
        economy_data[user_id] = {"money": 0, "fame": 0}
    
    # Remove dinheiro (mínimo 0)
    economy_data[user_id]["money"] = max(0, economy_data[user_id]["money"] - quantidade)
    save_economy_data()
    
    embed = discord.Embed(
        title="✅ Dinheiro Removido",
        description=f"**-R$ {quantidade:,}** removidos de {member.display_name}".replace(",", "."),
        color=0xFF6B35
    )
    embed.add_field(
        name="💰 Total Atual",
        value=f"R$ {economy_data[user_id]['money']:,}".replace(",", "."),
        inline=False
    )
    embed.set_footer(text="🔒 Comando de Administração")
    await ctx.reply(embed=embed, ephemeral=True)

@bot.command(name='addcurtidas', hidden=True)
async def add_curtidas(ctx, member: discord.Member = None, quantidade: int = None):
    """Comando secreto para adicionar curtidas (apenas owner)"""
    # Verifica se é o owner
    if str(ctx.author.id) != "983196900910039090":
        return  # Silenciosamente ignora se não for o owner
    
    if member is None or quantidade is None:
        await ctx.reply("❌ Uso: `m!addcurtidas @usuario quantidade`", ephemeral=True)
        return
    
    user_id = str(member.id)
    
    # Verifica se o usuário está registrado
    if user_id not in user_data:
        await ctx.reply("❌ Usuário não registrado!", ephemeral=True)
        return
    
    # Adiciona curtidas
    user_data[user_id]['total_likes'] += quantidade
    save_user_data()
    
    embed = discord.Embed(
        title="✅ Curtidas Adicionadas",
        description=f"**+{quantidade:,}** curtidas adicionadas para {member.display_name}".replace(",", "."),
        color=0x00FF00
    )
    embed.add_field(
        name="💖 Total Atual",
        value=f"{user_data[user_id]['total_likes']:,} curtidas".replace(",", "."),
        inline=False
    )
    embed.set_footer(text="🔒 Comando de Administração")
    await ctx.reply(embed=embed, ephemeral=True)

@bot.command(name='removecurtidas', hidden=True)
async def remove_curtidas(ctx, member: discord.Member = None, quantidade: int = None):
    """Comando secreto para remover curtidas (apenas owner)"""
    # Verifica se é o owner
    if str(ctx.author.id) != "983196900910039090":
        return  # Silenciosamente ignora se não for o owner
    
    if member is None or quantidade is None:
        await ctx.reply("❌ Uso: `m!removecurtidas @usuario quantidade`", ephemeral=True)
        return
    
    user_id = str(member.id)
    
    # Verifica se o usuário está registrado
    if user_id not in user_data:
        await ctx.reply("❌ Usuário não registrado!", ephemeral=True)
        return
    
    # Remove curtidas (mínimo 0)
    user_data[user_id]['total_likes'] = max(0, user_data[user_id]['total_likes'] - quantidade)
    save_user_data()
    
    embed = discord.Embed(
        title="✅ Curtidas Removidas",
        description=f"**-{quantidade:,}** curtidas removidas de {member.display_name}".replace(",", "."),
        color=0xFF6B35
    )
    embed.add_field(
        name="💖 Total Atual",
        value=f"{user_data[user_id]['total_likes']:,} curtidas".replace(",", "."),
        inline=False
    )
    embed.set_footer(text="🔒 Comando de Administração")
    await ctx.reply(embed=embed, ephemeral=True)

@bot.command(name='resetall', hidden=True)
async def reset_all_profiles(ctx):
    """Comando secreto para resetar todos os perfis (apenas owner)"""
    # Verifica se é o owner
    if str(ctx.author.id) != "983196900910039090":
        return  # Silenciosamente ignora se não for o owner
    
    # Confirma a ação
    embed = discord.Embed(
        title="⚠️ CONFIRMAÇÃO DE RESET TOTAL",
        description="**ATENÇÃO:** Você está prestes a **DELETAR TODOS OS DADOS** de todos os usuários!",
        color=0xFF0000
    )
    embed.add_field(
        name="🗑️ Dados que serão removidos:",
        value="• **TODOS** os perfis de usuários\n• **TODOS** os relacionamentos (seguir/seguidores)\n• **TODA** a economia (dinheiro e fama)\n• **TODOS** os inventários\n• **TODOS** os posts com marcas\n• **TODOS** os dados de reset",
        inline=False
    )
    embed.add_field(
        name="❗ ATENÇÃO EXTREMA:",
        value="**Esta ação é IRREVERSÍVEL e afetará TODOS os usuários!**\nTodos terão que se registrar novamente do zero.\n\n**⚠️ USE COM EXTREMA CAUTELA!**",
        inline=False
    )
    embed.add_field(
        name="📊 Dados Atuais:",
        value=f"👥 **{len(user_data)}** usuários registrados\n💰 **{len(economy_data)}** perfis de economia\n🤝 **{len(follow_data)}** relacionamentos\n📦 **{len(inventory_data)}** inventários\n📝 **{len(brand_posts_data)}** posts\n🔄 **{len(reset_data)}** resets usados",
        inline=False
    )

    # Botões de confirmação
    view = discord.ui.View(timeout=60)

    # Botão de confirmar
    confirm_button = discord.ui.Button(
        label="🗑️ SIM, DELETAR TUDO",
        style=discord.ButtonStyle.danger,
        emoji="⚠️"
    )

    async def confirm_callback(interaction):
        if interaction.user.id != ctx.author.id:
            await interaction.response.send_message("❌ Apenas o owner pode confirmar!", ephemeral=True)
            return

        # Salva estatísticas antes do reset
        stats_before = {
            "users": len(user_data),
            "economy": len(economy_data),
            "follow": len(follow_data),
            "inventory": len(inventory_data),
            "brand_posts": len(brand_posts_data),
            "resets": len(reset_data)
        }

        # RESETA TODOS OS DADOS
        user_data.clear()
        economy_data.clear()
        follow_data.clear()
        inventory_data.clear()
        brand_posts_data.clear()
        reset_data.clear()

        # Salva tudo vazio no MongoDB
        try:
            save_user_data()
            save_economy_data()
            save_follow_data()
            save_inventory_data()
            save_brand_posts_data()
            save_reset_data()
        except Exception as e:
            print(f"❌ Erro ao salvar dados zerados: {e}")

        success_embed = discord.Embed(
            title="💥 RESET TOTAL EXECUTADO!",
            description="**TODOS os dados foram completamente removidos!**",
            color=0xFF0000
        )
        
        success_embed.add_field(
            name="📊 Dados Removidos",
            value=f"👥 **{stats_before['users']}** usuários deletados\n💰 **{stats_before['economy']}** economias deletadas\n🤝 **{stats_before['follow']}** relacionamentos deletados\n📦 **{stats_before['inventory']}** inventários deletados\n📝 **{stats_before['brand_posts']}** posts deletados\n🔄 **{stats_before['resets']}** resets deletados",
            inline=False
        )
        
        success_embed.add_field(
            name="🔄 Sistema Resetado",
            value="• MongoDB completamente limpo\n• Todos os usuários precisarão usar `m!seguidores` novamente\n• Todos os relacionamentos foram perdidos\n• Toda economia foi zerada",
            inline=False
        )
        
        success_embed.add_field(
            name="⚠️ Importante",
            value="**O bot está funcionando normalmente**, mas todos os dados foram perdidos permanentemente.",
            inline=False
        )
        
        success_embed.set_footer(text="Reset total realizado pelo owner • Ação irreversível")

        await interaction.response.edit_message(embed=success_embed, view=None)
        
        print(f"💥 RESET TOTAL executado pelo owner! {stats_before['users']} usuários deletados")

    # Botão de cancelar
    cancel_button = discord.ui.Button(
        label="❌ CANCELAR",
        style=discord.ButtonStyle.secondary,
        emoji="🚫"
    )

    async def cancel_callback(interaction):
        if interaction.user.id != ctx.author.id:
            await interaction.response.send_message("❌ Apenas o owner pode cancelar!", ephemeral=True)
            return

        cancel_embed = discord.Embed(
            title="✅ Reset Cancelado",
            description="**Todos os dados estão seguros!** Nenhuma alteração foi feita.",
            color=0x00FF00
        )
        cancel_embed.add_field(
            name="📊 Dados Preservados",
            value=f"👥 **{len(user_data)}** usuários mantidos\n💰 **{len(economy_data)}** economias preservadas\n🤝 **{len(follow_data)}** relacionamentos intactos",
            inline=False
        )
        cancel_embed.set_footer(text="Reset cancelado com segurança")
        await interaction.response.edit_message(embed=cancel_embed, view=None)

    confirm_button.callback = confirm_callback
    cancel_button.callback = cancel_callback

    view.add_item(confirm_button)
    view.add_item(cancel_button)

    await ctx.reply(embed=embed, view=view, ephemeral=True)

# ===== FIM DOS COMANDOS ADMIN =====

# Comando principal de leaderboard
@bot.command(name='leaderboard', aliases=['lb', 'top'])
async def leaderboard(ctx):
    embed = discord.Embed(
        title="🏆 Leaderboard do Instagram MXP",
        description="**Menu Dropdown Elegante** 📋\n\nSelecione uma categoria no menu abaixo para ver os rankings organizados por páginas.",
        color=0xFFD700
    )
    
    total_users = len(user_data)
    total_registered = len([u for u in user_data.values() if u.get('username')])
    
    embed.add_field(
        name="📊 Rankings Disponíveis",
        value="👥 **Seguidores Totais** - Ranking principal por seguidores\n💖 **Mais Curtidos** - Quem recebe mais likes\n💰 **Mais Ricos** - Patrimônio acumulado\n🤝 **Seguidores Reais** - Conexões no servidor\n⭐ **Pontos de Fama** - Fama por publicidade\n📊 **Mais Ativos** - Atividade geral\n💎 **Level Máximo** - Progressão por curtidas",
        inline=False
    )
    
    embed.add_field(
        name="📈 Estatísticas Gerais",
        value=f"📊 **{total_users}** usuários no sistema\n✅ **{total_registered}** usuários ativos\n🏆 Rankings atualizados em tempo real\n📄 **10 usuários** por página",
        inline=False
    )
    
    embed.add_field(
        name="🎯 Como Usar",
        value="1️⃣ Selecione categoria no menu dropdown\n2️⃣ Navegue com ⬅️ ➡️ entre páginas\n3️⃣ Use 🔙 para voltar ao menu principal\n4️⃣ Rankings atualizados automaticamente",
        inline=False
    )
    
    embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1376731577106567319.png")
    embed.set_footer(text=f"Sistema de Rankings v3.0 • Solicitado por {ctx.author.display_name}")
    
    view = MainLeaderboardView()
    await ctx.reply(embed=embed, view=view)



# Comando para verificar economia (dinheiro e fama)
@bot.command(name='economia', aliases=['saldo', 'money'])
async def economia(ctx, member: discord.Member = None):
    if member is None:
        member = ctx.author

    user_id = str(member.id)

    # Verifica se o usuário está registrado
    if user_id not in user_data:
        if member == ctx.author:
            embed = discord.Embed(
                title="❌ Registro necessário",
                description="Você precisa se registrar primeiro!",
                color=0xFF0000
            )
            embed.add_field(
                name="📝 Como se registrar:",
                value="Use o comando `m!seguidores` para criar seu perfil",
                inline=False
            )
            await ctx.reply(embed=embed)
        else:
            await ctx.reply(f"❌ {member.display_name} ainda não se registrou!")
        return

    # Inicializa dados de economia se não existir
    if user_id not in economy_data:
        economy_data[user_id] = {
            "money": 0,
            "fame": 0
        }

    # Pega dados do usuário
    money = economy_data[user_id].get("money", 0)
    fame = economy_data[user_id].get("fame", 0)
    followers = user_data[user_id].get('followers', 0)

    # Define status baseado no dinheiro
    if money >= 100000:
        status = "💎 MAGNATA"
        cor = 0xFFD700
    elif money >= 50000:
        status = "🤑 RICO"
        cor = 0xFF6B35
    elif money >= 20000:
        status = "💰 BEM SUCEDIDO"
        cor = 0x00FF00
    elif money >= 5000:
        status = "📈 CRESCENDO"
        cor = 0xFFD23F
    else:
        status = "🌱 INICIANTE"
        cor = 0x9932CC

    embed = discord.Embed(
        title="💼 Economia do Instagram",
        description=f"Finanças de **{member.display_name}**",
        color=cor
    )

    embed.add_field(
        name="💵 Dinheiro",
        value=f"**R$ {money:,}**".replace(",", "."),
        inline=True
    )

    embed.add_field(
        name="⭐ Pontos de Fama",
        value=f"**{fame:,}** pontos".replace(",", "."),
        inline=True
    )

    embed.add_field(
        name="🏆 Status Financeiro",
        value=status,
        inline=True
    )

    embed.add_field(
        name="📊 Seguidores Totais",
        value=f"**{followers:,}** seguidores".replace(",", "."),
        inline=True
    )

    # Calcula poder de compra
    if money >= 50000:
        poder_compra = "🔥 Pode comprar qualquer coisa!"
    elif money >= 20000:
        poder_compra = "💪 Ótimo poder de compra"
    elif money >= 5000:
        poder_compra = "📈 Poder de compra moderado"
    else:
        poder_compra = "🌱 Construindo patrimônio"

    embed.add_field(
        name="💳 Poder de Compra",
        value=poder_compra,
        inline=True
    )

    # Dicas para ganhar dinheiro
    if money < 10000:
        embed.add_field(
            name="💡 Como Ganhar Dinheiro",
            value="• Use `m!publi` após mencionar marcas famosas\n• Faça parcerias com influencers\n• Crie conteúdo patrocinado",
            inline=False
        )

    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text=f"Dev: YevgennyMXP • Consultado por {ctx.author.display_name}")

    await ctx.reply(embed=embed)

# Sistema de inventário com menus
class InventoryView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=300)
        self.user_id = user_id

    @discord.ui.button(label='🚗 Ver Carros', style=discord.ButtonStyle.primary)
    async def ver_carros(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Este inventário não é seu!", ephemeral=True)
            return
        
        user_inventory = inventory_data.get(self.user_id, {"carros": [], "mansoes": [], "itens_diarios": []})
        carros = user_inventory["carros"]
        
        embed = discord.Embed(
            title="🚗 Meus Carros",
            description=f"Você possui {len(carros)} carros",
            color=0x3498DB
        )
        
        if not carros:
            embed.add_field(
                name="😢 Nenhum Carro",
                value="Você ainda não possui carros! Use `m!lojinha` para comprar.",
                inline=False
            )
        else:
            carros_text = ""
            for i, carro in enumerate(carros[:10]):  # Mostra até 10
                carros_text += f"`{i+1:2d}.` **{carro['nome']}**\n      💰 R$ {carro['preco']:,}\n".replace(",", ".")
            embed.add_field(
                name=f"🚗 Lista de Carros ({len(carros)})",
                value=carros_text,
                inline=False
            )
        
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label='🏰 Ver Mansões', style=discord.ButtonStyle.secondary)
    async def ver_mansoes(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Este inventário não é seu!", ephemeral=True)
            return
        
        user_inventory = inventory_data.get(self.user_id, {"carros": [], "mansoes": [], "itens_diarios": []})
        mansoes = user_inventory["mansoes"]
        
        embed = discord.Embed(
            title="🏰 Minhas Mansões",
            description=f"Você possui {len(mansoes)} propriedades",
            color=0xE67E22
        )
        
        if not mansoes:
            embed.add_field(
                name="😢 Nenhuma Mansão",
                value="Você ainda não possui mansões! Use `m!lojinha` para comprar.",
                inline=False
            )
        else:
            mansoes_text = ""
            for i, mansao in enumerate(mansoes[:10]):  # Mostra até 10
                mansoes_text += f"`{i+1:2d}.` **{mansao['nome']}**\n      💰 R$ {mansao['preco']:,}\n".replace(",", ".")
            embed.add_field(
                name=f"🏰 Lista de Mansões ({len(mansoes)})",
                value=mansoes_text,
                inline=False
            )
        
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label='🛍️ Ver Itens', style=discord.ButtonStyle.success)
    async def ver_itens(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Este inventário não é seu!", ephemeral=True)
            return
        
        user_inventory = inventory_data.get(self.user_id, {"carros": [], "mansoes": [], "itens_diarios": []})
        itens = user_inventory["itens_diarios"]
        
        embed = discord.Embed(
            title="🛍️ Meus Itens",
            description=f"Você possui {len(itens)} itens",
            color=0x27AE60
        )
        
        if not itens:
            embed.add_field(
                name="😢 Nenhum Item",
                value="Você ainda não possui itens! Use `m!lojinha` para comprar.",
                inline=False
            )
        else:
            itens_text = ""
            for i, item in enumerate(itens[:15]):  # Mostra até 15
                itens_text += f"`{i+1:2d}.` **{item['nome']}** - R$ {item['preco']:,}\n".replace(",", ".")
            embed.add_field(
                name=f"🛍️ Lista de Itens ({len(itens)})",
                value=itens_text,
                inline=False
            )
        
        await interaction.response.edit_message(embed=embed, view=self)

class UseItemView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=300)
        self.user_id = user_id
        
        # Adiciona select menu com os itens disponíveis para usar
        user_inventory = inventory_data.get(user_id, {"carros": [], "mansoes": [], "itens_diarios": []})
        all_items = []
        
        # Adiciona carros
        for carro in user_inventory["carros"][:10]:  # Limita a 10
            all_items.append((carro["nome"], "carro", carro))
        
        # Adiciona mansões
        for mansao in user_inventory["mansoes"][:5]:  # Limita a 5
            all_items.append((mansao["nome"], "mansao", mansao))
        
        # Adiciona itens (apenas eletrônicos, games e bebidas são "usáveis")
        for item in user_inventory["itens_diarios"][:10]:  # Limita a 10
            if any(cat in item.get("categoria", "") for cat in ["Eletrônicos", "Games", "Bebidas", "Comidas"]):
                all_items.append((item["nome"], "item", item))
        
        if all_items:
            self.add_item(UseItemSelect(user_id, all_items))

class UseItemSelect(discord.ui.Select):
    def __init__(self, user_id, items):
        self.user_id = user_id
        self.items = items
        
        options = []
        for nome, tipo, item_data in items[:25]:  # Discord limita a 25
            emoji = "🚗" if tipo == "carro" else "🏰" if tipo == "mansao" else "🛍️"
            options.append(discord.SelectOption(
                label=f"{emoji} {nome}",
                description=f"Usar {nome}",
                value=f"{tipo}:{nome}"
            ))
        
        super().__init__(placeholder="Escolha um item para usar...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Este inventário não é seu!", ephemeral=True)
            return
        
        tipo, nome = self.values[0].split(":", 1)
        
        # Simula o uso do item
        embed = discord.Embed(
            title="✅ Item Usado!",
            color=0x00FF00
        )
        
        if tipo == "carro":
            embed.description = f"🚗 Você saiu para dirigir seu **{nome}**!"
            embed.add_field(
                name="🏁 Experiência de Dirigir",
                value="Que passeio incrível! Você se sentiu como um verdadeiro piloto.",
                inline=False
            )
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1387842927602172125.png")
        
        elif tipo == "mansao":
            embed.description = f"🏰 Você relaxou em sua **{nome}**!"
            embed.add_field(
                name="🛋️ Momento de Relaxamento",
                value="Que casa incrível! Você se sentiu como um verdadeiro rei/rainha.",
                inline=False
            )
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1387842927602172125.png")
        
        else:  # item
            if "Bebidas" in nome or "Coca" in nome or "Café" in nome:
                embed.description = f"☕ Você bebeu seu **{nome}**!"
                embed.add_field(
                    name="😋 Que Delícia!",
                    value="Você se sentiu refreshed e energizado!",
                    inline=False
                )
            elif "Comidas" in nome or "Pizza" in nome or "Big Mac" in nome:
                embed.description = f"🍔 Você comeu seu **{nome}**!"
                embed.add_field(
                    name="😋 Que Sabor!",
                    value="Você matou a fome e ficou satisfeito!",
                    inline=False
                )
            elif "Games" in nome or "PlayStation" in nome or "Xbox" in nome:
                embed.description = f"🎮 Você jogou no seu **{nome}**!"
                embed.add_field(
                    name="🕹️ Diversão Garantida",
                    value="Que sessão de jogos incrível! Você se divertiu muito.",
                    inline=False
                )
            else:  # Eletrônicos
                embed.description = f"📱 Você usou seu **{nome}**!"
                embed.add_field(
                    name="📲 Experiência Tech",
                    value="Que tecnologia avançada! Você se sentiu conectado.",
                    inline=False
                )
        
        embed.set_footer(text=f"Item usado por {interaction.user.display_name}")
        await interaction.response.edit_message(embed=embed, view=None)

# Comando para daily reward (recompensa diária)
daily_rewards = {}

@bot.command(name='inv', aliases=['inventario'])
async def inventario(ctx):
    user_id = str(ctx.author.id)
    
    if user_id not in user_data:
        embed = discord.Embed(
            title="❌ Registro necessário",
            description="Você precisa se registrar primeiro!",
            color=0xFF0000
        )
        embed.add_field(
            name="📝 Como se registrar:",
            value="Use o comando `m!seguidores` para criar seu perfil",
            inline=False
        )
        await ctx.reply(embed=embed)
        return
    
    # Inicializa inventário se não existir
    if user_id not in inventory_data:
        inventory_data[user_id] = {"carros": [], "mansoes": [], "itens_diarios": []}
    
    user_inventory = inventory_data[user_id]
    total_items = len(user_inventory["carros"]) + len(user_inventory["mansoes"]) + len(user_inventory["itens_diarios"])
    
    embed = discord.Embed(
        title="📦 Meu Inventário",
        description=f"Você possui **{total_items}** itens no total",
        color=0x9B59B6
    )
    
    embed.add_field(
        name="🚗 Carros",
        value=f"**{len(user_inventory['carros'])}** carros",
        inline=True
    )
    
    embed.add_field(
        name="🏰 Mansões",
        value=f"**{len(user_inventory['mansoes'])}** propriedades",
        inline=True
    )
    
    embed.add_field(
        name="🛍️ Itens",
        value=f"**{len(user_inventory['itens_diarios'])}** itens",
        inline=True
    )
    
    if total_items == 0:
        embed.add_field(
            name="😢 Inventário Vazio",
            value="Você ainda não possui itens! Use `m!lojinha` para fazer compras.",
            inline=False
        )
    else:
        embed.add_field(
            name="🔍 Navegação",
            value="Use os botões abaixo para ver detalhes de cada categoria!",
            inline=False
        )
    
    embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1387842927602172125.png")
    embed.set_footer(text=f"Inventário de {ctx.author.display_name}")
    
    view = InventoryView(user_id)
    await ctx.reply(embed=embed, view=view)

@bot.command(name='usar', aliases=['use'])
async def usar_item(ctx):
    user_id = str(ctx.author.id)
    
    if user_id not in user_data:
        embed = discord.Embed(
            title="❌ Registro necessário",
            description="Você precisa se registrar primeiro!",
            color=0xFF0000
        )
        await ctx.reply(embed=embed)
        return
    
    # Inicializa inventário se não existir
    if user_id not in inventory_data:
        inventory_data[user_id] = {"carros": [], "mansoes": [], "itens_diarios": []}
    
    user_inventory = inventory_data[user_id]
    total_items = len(user_inventory["carros"]) + len(user_inventory["mansoes"]) + len(user_inventory["itens_diarios"])
    
    if total_items == 0:
        embed = discord.Embed(
            title="😢 Inventário Vazio",
            description="Você não possui itens para usar!",
            color=0xFF0000
        )
        embed.add_field(
            name="🛒 Como Obter Itens",
            value="Use `m!lojinha` para comprar carros, mansões e itens!",
            inline=False
        )
        await ctx.reply(embed=embed)
        return
    
    embed = discord.Embed(
        title="🎮 Usar Item",
        description="Escolha um item do seu inventário para usar:",
        color=0x9B59B6
    )
    
    embed.add_field(
        name="📋 Itens Disponíveis",
        value=f"🚗 **{len(user_inventory['carros'])}** carros para dirigir\n🏰 **{len(user_inventory['mansoes'])}** mansões para relaxar\n🛍️ **{len([i for i in user_inventory['itens_diarios'] if any(cat in i.get('categoria', '') for cat in ['Eletrônicos', 'Games', 'Bebidas', 'Comidas'])])}** itens usáveis",
        inline=False
    )
    
    embed.add_field(
        name="💡 Como Funciona",
        value="• **Carros**: Saia para dirigir e se divertir\n• **Mansões**: Relaxe em suas propriedades\n• **Itens**: Use eletrônicos, games, bebidas e comidas",
        inline=False
    )
    
    embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1381003788135174316.png")
    embed.set_footer(text=f"Solicitado por {ctx.author.display_name}")
    
    view = UseItemView(user_id)
    await ctx.reply(embed=embed, view=view)

@bot.command(name='daily')
async def daily_reward(ctx):
    user_id = str(ctx.author.id)

    if user_id not in user_data:
        embed = discord.Embed(
            title="❌ Registro necessário",
            description="Você precisa se registrar primeiro!",
            color=0xFF0000
        )
        embed.add_field(
            name="📝 Como se registrar:",
            value="Use o comando `m!seguidores` para criar seu perfil",
            inline=False
        )
        await ctx.reply(embed=embed)
        return

    import datetime
    today = datetime.date.today().isoformat()

    # Verifica se já coletou hoje
    if user_id in daily_rewards and daily_rewards[user_id] == today:
        embed = discord.Embed(
            title="⏰ Já coletado hoje!",
            description="Você já coletou sua recompensa diária!",
            color=0xFF0000
        )
        embed.add_field(
            name="🕐 Próxima recompensa:",
            value="Volte amanhã para coletar novamente!",
            inline=False
        )
        await ctx.reply(embed=embed)
        return

    # Calcula recompensa baseada nos seguidores
    followers = user_data[user_id].get('followers', 0)
    
    if followers >= 5000000:
        likes_reward = random.randint(15, 25)
        bonus = "💎 Mega Influencer"
    elif followers >= 1000000:
        likes_reward = random.randint(10, 20)
        bonus = "🔥 Influencer"
    elif followers >= 500000:
        likes_reward = random.randint(8, 15)
        bonus = "⭐ Verificado"
    elif followers >= 100000:
        likes_reward = random.randint(5, 12)
        bonus = "📈 Popular"
    else:
        likes_reward = random.randint(3, 8)
        bonus = "🌱 Crescendo"

    # Adiciona as curtidas
    user_data[user_id]['total_likes'] += likes_reward
    daily_rewards[user_id] = today
    save_user_data()

    embed = discord.Embed(
        title="🎁 Recompensa Diária Coletada!",
        description=f"Você ganhou **{likes_reward}** curtidas!",
        color=0x00FF00
    )

    embed.add_field(
        name="💖 Curtidas Recebidas",
        value=f"+{likes_reward} curtidas",
        inline=True
    )

    embed.add_field(
        name="🏆 Bônus de Status",
        value=bonus,
        inline=True
    )

    embed.add_field(
        name="📊 Total Atual",
        value=f"{user_data[user_id]['total_likes']:,} curtidas".replace(",", "."),
        inline=False
    )

    embed.add_field(
        name="⏰ Próxima Recompensa",
        value="Volte amanhã para coletar novamente!",
        inline=False
    )

    embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1381003788135174316.png")
    embed.set_footer(text=f"Recompensa coletada por {ctx.author.display_name}")

    await ctx.reply(embed=embed)



# Inicia o bot
if __name__ == "__main__":
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        print("ERRO: Token do Discord não encontrado!")
        print("Configure a variável DISCORD_BOT_TOKEN nas Secrets do Replit")
    else:
        bot.run(token)