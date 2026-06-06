import asyncio
from bleak import BleakClient

ADDRESS = "E8:4A:54:53:1D:E9"

UUID_INFO = "0000001c-0000-1000-8000-00805f9b34fb"

def dump(data: bytes):
    hex_data = data.hex()
    ascii_data = "".join(chr(b) if 32 <= b <= 126 else "." for b in data)
    return f"{hex_data} | {ascii_data}"

def parse_info(data: bytes):
    if len(data) >= 2:
        cmd = data[0]
        length = data[1]
        payload = data[2:2 + length]
        ascii_payload = "".join(chr(b) if 32 <= b <= 126 else "." for b in payload)
        print(f"  cmd={cmd:02x} len={length} payload={payload.hex()} ascii={ascii_payload}")

async def main():
    async with BleakClient(ADDRESS) as client:
        print("Connecté:", client.is_connected)

        def on_notify(sender, data):
            print(f"[NOTIF] {sender}: {dump(data)}")
            parse_info(bytes(data))

        await client.start_notify(UUID_INFO, on_notify)

        for cmd in ["00", "01", "03"]:
            print(f"\n[WRITE] {cmd}")
            await client.write_gatt_char(UUID_INFO, bytes.fromhex(cmd), response=False)
            await asyncio.sleep(1)

        await client.stop_notify(UUID_INFO)

asyncio.run(main())
