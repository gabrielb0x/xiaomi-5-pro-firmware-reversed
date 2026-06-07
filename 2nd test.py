import asyncio
import struct
from bleak import BleakClient

ADDRESS = "E8:4A:54:53:1D:E9"

UUID_INFO = "0000001c-0000-1000-8000-00805f9b34fb"
UUID_MAIN_TX = "0000001a-0000-1000-8000-00805f9b34fb"
UUID_MAIN_RX = "0000001b-0000-1000-8000-00805f9b34fb"
UUID_AUTH = "00000016-0000-1000-8000-00805f9b34fb"
UUID_FW = "00000004-0000-1000-8000-00805f9b34fb"
UUID_TCS = "00000005-0000-1000-8000-00805f9b34fb"

NOTIFY_UUIDS = [
    UUID_INFO,
    UUID_MAIN_TX,
    UUID_MAIN_RX,
    UUID_AUTH,
    "00000010-0000-1000-8000-00805f9b34fb",
    "00000017-0000-1000-8000-00805f9b34fb",
    "00000018-0000-1000-8000-00805f9b34fb",
]

READ_UUIDS = [
    "00002a00-0000-1000-8000-00805f9b34fb",
    UUID_FW,
    UUID_TCS,
    UUID_INFO,
]

def hx(data: bytes) -> str:
    return data.hex(" ").upper()

def asc(data: bytes) -> str:
    return "".join(chr(b) if 32 <= b <= 126 else "." for b in data)

def find_voltage_candidates(data: bytes):
    """
    Cherche naïvement des valeurs plausibles de tension batterie.
    Exemple :
    - 5460 / 100 = 54.60 V
    - 42000 / 1000 = 42.00 V
    - 540 / 10 = 54.0 V
    """
    candidates = []

    for offset in range(len(data) - 1):
        u16_le = struct.unpack_from("<H", data, offset)[0]
        u16_be = struct.unpack_from(">H", data, offset)[0]

        for name, value in [("u16_le", u16_le), ("u16_be", u16_be)]:
            for scale in [10, 100, 1000]:
                volts = value / scale
                if 24.0 <= volts <= 70.0:
                    candidates.append((offset, name, scale, volts, value))

    for offset in range(len(data) - 3):
        u32_le = struct.unpack_from("<I", data, offset)[0]
        u32_be = struct.unpack_from(">I", data, offset)[0]

        for name, value in [("u32_le", u32_le), ("u32_be", u32_be)]:
            for scale in [1000, 10000]:
                volts = value / scale
                if 24.0 <= volts <= 70.0:
                    candidates.append((offset, name, scale, volts, value))

    return candidates

def notify_handler(sender, data: bytearray):
    data = bytes(data)

    print(f"\n[NOTIF] {sender}")
    print(f"HEX   : {hx(data)}")
    print(f"ASCII : {asc(data)}")

    known_info = [
        bytes.fromhex("00020103"),
        bytes.fromhex("010430303037"),
        bytes.fromhex("030852544c3837363243"),
    ]

    if data in known_info:
        return

    candidates = find_voltage_candidates(data)
    if candidates and len(data) >= 8:
        print("POSSIBLES VOLTAGES:")
        for offset, name, scale, volts, raw in candidates[:20]:
            print(f"  offset={offset:02d} {name} raw={raw} /{scale} = {volts:.2f} V")

async def main():
    print("[*] Connexion à la trott...")
    async with BleakClient(ADDRESS, timeout=20.0) as client:
        print("[+] Connecté:", client.is_connected)

        print("\n=== SERVICES ===")
        for service in client.services:
            print(f"\n[SERVICE] {service.uuid}")
            for char in service.characteristics:
                print(f"  [CHAR] {char.uuid} props={char.properties}")

        print("\n=== READ TEST ===")
        for uuid in READ_UUIDS:
            try:
                data = await client.read_gatt_char(uuid)
                print(f"{uuid} -> {hx(data)} | {asc(data)}")
                candidates = find_voltage_candidates(bytes(data))
                if candidates:
                    print("  voltage candidates:", candidates[:5])
            except Exception as e:
                print(f"{uuid} -> READ FAIL: {e}")

        print("\n=== NOTIFY ON ===")
        for uuid in NOTIFY_UUIDS:
            try:
                await client.start_notify(uuid, notify_handler)
                print(f"Notify ON: {uuid}")
            except Exception as e:
                print(f"Notify FAIL {uuid}: {e}")

        print("\n=== COMMANDES INFO SAFE SUR 0000001c ===")
        for cmd in ["00", "01", "03"]:
            try:
                print(f"[WRITE INFO] {cmd}")
                await client.write_gatt_char(UUID_INFO, bytes.fromhex(cmd), response=False)
                await asyncio.sleep(1.0)
            except Exception as e:
                print(f"WRITE FAIL {cmd}: {e}")

        print("\n[*] Attente 30s des notifications...")
        print("[*] Si une valeur plausible apparaît, elle sera affichée.")
        await asyncio.sleep(30)

        print("\n=== NOTIFY OFF ===")
        for uuid in NOTIFY_UUIDS:
            try:
                await client.stop_notify(uuid)
            except Exception:
                pass

        print("[+] Terminé.")

asyncio.run(main())
