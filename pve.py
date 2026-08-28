"""Proxmox API calls: VM power control + host status. Same token/permissions
as the Discord version (shiokazebot@pve!botapi), unchanged by this port."""

import requests


def _pve_get(cfg, path):
    r = requests.get(
        f"https://{cfg.proxmox_host}:8006/api2/json{path}",
        headers={"Authorization": f"PVEAPIToken={cfg.proxmox_token_id}={cfg.proxmox_token_secret}"},
        verify=cfg.proxmox_ca_path, timeout=10,
    )
    r.raise_for_status()
    return r.json()["data"]


def _pve_post(cfg, path):
    r = requests.post(
        f"https://{cfg.proxmox_host}:8006/api2/json{path}",
        headers={"Authorization": f"PVEAPIToken={cfg.proxmox_token_id}={cfg.proxmox_token_secret}"},
        verify=cfg.proxmox_ca_path, timeout=10,
    )
    r.raise_for_status()
    return r.json()["data"]


def vm_status(cfg):
    """{'status': 'running'|'stopped', 'uptime': int}"""
    return _pve_get(cfg, f"/nodes/{cfg.realm_node}/qemu/{cfg.realm_vmid}/status/current")


def vm_start(cfg):
    return _pve_post(cfg, f"/nodes/{cfg.realm_node}/qemu/{cfg.realm_vmid}/status/start")


def vm_shutdown(cfg):
    return _pve_post(cfg, f"/nodes/{cfg.realm_node}/qemu/{cfg.realm_vmid}/status/shutdown")


def node_status(cfg):
    """Global RAM/CPU for the Proxmox host (read-only, Sys.Audit)."""
    return _pve_get(cfg, f"/nodes/{cfg.realm_node}/status")
