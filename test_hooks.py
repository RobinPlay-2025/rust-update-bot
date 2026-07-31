import os, requests
from bot import get_carbon_hooks_release, embed_hooks, send_embed, CHANNELS

os.environ.setdefault("LOLKA_TOKEN", "ODE1Nzk5MDQ3Mzc0ODQ5.tv4pKgPD3jhklF-HWRH0YgZ3ZQ3o60tfB6IA2FVQ_8Q")
os.environ.setdefault("CHANNEL_HOOKS", "815797917861888")

hook = get_carbon_hooks_release()
if hook:
    print("protocol:", hook["protocol"])
    print("branch:  ", hook["branch"])
    print("rel_type:", hook["rel_type"])
    print("version: ", hook["version"])
    print("commit:  ", hook["commit"])
    ok = send_embed(CHANNELS["hooks"], embed_hooks(hook))
    print("Отправлено!" if ok else "Ошибка отправки")
else:
    print("Хуки не найдены")
