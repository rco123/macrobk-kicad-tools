"""Send the Studio multicast protocol without importing/registering the plugin."""
import argparse
import json
import pathlib
import socket


def configured_trigger(config):
    actions = config.get("actions", [])
    selected = next((a for a in actions if a.get("id") == config.get("selected_action_id")), None)
    trigger = (selected or config).get("trigger", {})
    if not trigger.get("enabled", True):
        raise ValueError("Selected Action trigger is disabled")
    modifiers = sorted(name.upper() for name in ("alt", "ctrl", "shift", "win") if trigger.get(name))
    keys = trigger.get("keys") or [trigger.get("key", "F12")]
    keys = sorted(set(str(key).strip().upper() for key in keys if str(key).strip()))
    if not keys:
        raise ValueError("No trigger keys configured")
    return "{}:{}".format("+".join(modifiers), ",".join(keys))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trigger", nargs="?", help="Canonical ID, e.g. CTRL+SHIFT:F12")
    parser.add_argument("--dry-run", action="store_true", help="Show packet without executing an Action")
    parser.add_argument("--config", type=pathlib.Path,
                        default=pathlib.Path(__file__).resolve().parents[1] / "config.json",
                        help="Action configuration file (default: plugin root config.json)")
    args = parser.parse_args()
    if args.trigger:
        trigger = args.trigger
    else:
        config = json.loads(args.config.read_text(encoding="utf-8-sig"))
        trigger = configured_trigger(config)
    payload = ("TRIGGER|" + trigger).encode("utf-8")
    print("PACKET={} DEST=239.255.77.77:47831 INTERFACE=127.0.0.1".format(payload.decode()))
    if args.dry_run:
        print("DRY RUN: no packet sent")
        return
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as sender:
        sender.bind(("127.0.0.1", 0))
        sender.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton("127.0.0.1"))
        sender.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 0)
        sender.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
        sender.sendto(payload, ("239.255.77.77", 47831))
    print("SENT: check macrobk_drc.log for PHONE RX / PHONE matched / ACTION START / SUCCESS")


if __name__ == "__main__":
    main()
