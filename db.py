"""Read-only realm character DB queries (SELECT-only MySQL user), unchanged by this port."""

import pymysql


def fetch_character(cfg, name):
    """Returns the character row or None."""
    conn = pymysql.connect(
        host=cfg.realm_host, user=cfg.mysql_user, password=cfg.mysql_pass,
        database="acore_characters", connect_timeout=5,
    )
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(
                "SELECT name, level, money, zone, totaltime FROM characters WHERE name=%s",
                (name,),
            )
            return cur.fetchone()
    finally:
        conn.close()


def count_online(cfg):
    conn = pymysql.connect(
        host=cfg.realm_host, user=cfg.mysql_user, password=cfg.mysql_pass,
        database="acore_characters", connect_timeout=5,
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM characters WHERE online=1")
            return cur.fetchone()[0]
    finally:
        conn.close()
