"""Environment-driven configuration. No secrets hardcoded."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    matrix_homeserver_url: str
    matrix_access_token: str
    matrix_realm_room_id: str
    matrix_events_room_id: str
    matrix_owner_id: str
    proxmox_host: str
    proxmox_token_id: str
    proxmox_token_secret: str
    proxmox_ca_path: str
    realm_node: str
    realm_vmid: str
    realm_host: str
    world_port: int
    start_timeout: int
    stop_timeout: int
    mysql_user: str
    mysql_pass: str
    main_character: str
    state_path: str
    backup_key_path: str
    backup_timeout: int
    gh_repo: str
    gh_branch: str


def load_config() -> Config:
    return Config(
        matrix_homeserver_url=os.environ["MATRIX_HOMESERVER_URL"],
        matrix_access_token=os.environ["MATRIX_ACCESS_TOKEN"],
        matrix_realm_room_id=os.environ["MATRIX_REALM_ROOM_ID"],
        matrix_events_room_id=os.environ["MATRIX_EVENTS_ROOM_ID"],
        matrix_owner_id=os.environ["MATRIX_OWNER_ID"],
        proxmox_host=os.environ["PROXMOX_HOST"],
        proxmox_token_id=os.environ["PROXMOX_TOKEN_ID"],
        proxmox_token_secret=os.environ["PROXMOX_TOKEN_SECRET"],
        proxmox_ca_path=os.environ.get("PROXMOX_CA_PATH", "/etc/shiokaze-bot/proxmox-ca.pem"),
        realm_node=os.environ["REALM_NODE"],
        realm_vmid=os.environ["REALM_VMID"],
        realm_host=os.environ["REALM_HOST"],
        world_port=int(os.environ.get("REALM_WORLD_PORT", "8085")),
        start_timeout=int(os.environ.get("REALM_START_TIMEOUT", "420")),
        stop_timeout=int(os.environ.get("REALM_STOP_TIMEOUT", "90")),
        mysql_user=os.environ["MYSQL_RO_USER"],
        mysql_pass=os.environ["MYSQL_RO_PASS"],
        main_character=os.environ.get("REALM_MAIN_CHARACTER", "Kushette"),
        state_path=os.environ.get("REALM_STATE_PATH", "/opt/shiokaze-bot/state.json"),
        backup_key_path=os.environ.get("REALM_BACKUP_KEY_PATH", "/etc/shiokaze-bot/backup_key"),
        backup_timeout=int(os.environ.get("REALM_BACKUP_TIMEOUT", "300")),
        gh_repo=os.environ.get("REALM_GH_REPO", "mod-playerbots/azerothcore-wotlk"),
        gh_branch=os.environ.get("REALM_GH_BRANCH", "Playerbot"),
    )
