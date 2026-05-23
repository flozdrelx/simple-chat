import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config", "config.json")

def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)

def get_client_host(config):
    host = config.get("connect_host", config["host"])

    if host == "0.0.0.0":
        return "127.0.0.1"

    return host