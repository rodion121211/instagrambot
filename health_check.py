
import os
from dotenv import load_dotenv

def check_environment():
    """Verifica se todas as variáveis de ambiente estão configuradas"""
    load_dotenv()
    
    required_vars = ['DISCORD_BOT_TOKEN', 'MONGODB_TOKEN']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("❌ Variáveis de ambiente faltando:")
        for var in missing_vars:
            print(f"   - {var}")
        return False
    
    print("✅ Todas as variáveis de ambiente estão configuradas!")
    return True

if __name__ == "__main__":
    check_environment()
