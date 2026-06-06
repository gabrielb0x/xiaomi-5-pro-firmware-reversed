# Reverse engineering BLE Xiaomi Scooter 5 Pro

## Objectif du projet

Le but est de comprendre le protocole BLE utilisé par une trottinette **Xiaomi Scooter 5 Pro**, afin de pouvoir récupérer certaines informations sans passer par l’application officielle Xiaomi Home.

L’objectif principal actuel est de récupérer les informations batterie, notamment :

* tension batterie ;
* pourcentage batterie ;
* état batterie ;
* températures éventuelles ;
* infos BMS ;
* cycles / capacité / cellules si disponibles.

Le but n’est pas de modifier les limites de vitesse, flasher le firmware ou envoyer des commandes risquées. On travaille uniquement sur de l’observation et des requêtes de lecture.

---

## Matériel utilisé

### PC

* PC portable sous Linux Mint
* CPU : AMD Ryzen 5 7520U
* RAM : 8 Go
* Bluetooth interne Realtek exposé comme périphérique USB

Contrôleur Bluetooth détecté :

```txt
Bus 001 Device 003: ID 13d3:3556 IMC Networks Bluetooth Radio
Manufacturer: Realtek Semiconductor Corporation
HCI Version: Bluetooth Core 4.2
Public Address: F8:54:F6:64:55:70
```

Le contrôleur apparaît sous Linux comme :

```txt
hci0: Type: Primary Bus: USB
```

Ce point est important, car Bumble peut prendre le contrôle d’un contrôleur Bluetooth exposé en USB.

---

## Trottinette ciblée

Trottinette :

```txt
xiaomi.scooter.5pro
```

Adresse BLE observée depuis le PC :

```txt
E8:4A:54:53:1D:E9
```

Nom interne lu via BLE :

```txt
dreame scooter
```

Version firmware lue directement en BLE :

```txt
2.7.0_0015
```

---

## Logiciels utilisés

### Linux

Paquets installés :

```bash
sudo apt update
sudo apt install python3-venv python3-pip libusb-1.0-0 adb wireshark
```

### Python

Un environnement virtuel dédié a été créé pour Bumble :

```bash
python3 -m venv ~/.venvs/bumble
source ~/.venvs/bumble/bin/activate
pip install --upgrade pip
pip install bumble pyusb
```

Bumble est utilisé pour faire un pont entre l’émulateur Android et le contrôleur Bluetooth physique du PC.

### Android Studio

Android Studio est utilisé pour lancer un émulateur Android avec Google Play.

AVD fonctionnel :

```txt
Pixel_4
Android 13 / API 33
Google Play
x86_64
```

Important : éviter les images Android avec `16 KB Page Size`.

Une image Android 37 / API 37 avec `ps16k` a provoqué un crash Xiaomi Home à cause de cette erreur :

```txt
librnsdk.so program alignment (4096) cannot be smaller than system page size (16384)
```

Conclusion : Xiaomi Home ne fonctionne pas correctement avec cette image système. Android 13 API 33 x86_64 sans `ps16k` fonctionne.

---

## Architecture utilisée

Le montage actuel est :

```txt
Xiaomi Home dans Android Emulator
        ↓
Bluetooth Android émulé
        ↓
Bumble HCI bridge
        ↓
Bluetooth Realtek interne du PC
        ↓
Xiaomi Scooter 5 Pro
```

Commande Bumble :

```bash
BUMBLE_LOGLEVEL=debug sudo -E ~/.venvs/bumble/bin/bumble-hci-bridge \
'android-netsim:_:8877,mode=controller' \
'usb:0'
```

Commande émulateur :

```bash
~/Android/Sdk/emulator/emulator -avd Pixel_4 \
-packet-streamer-endpoint localhost:8877 \
-no-snapshot-load \
-no-snapshot-save \
-no-boot-anim \
-gpu swiftshader_indirect
```

---

## Validation du Bluetooth

Le Bluetooth Android a été activé via ADB :

```bash
adb shell cmd bluetooth_manager enable
```

Vérification :

```bash
adb shell settings get global bluetooth_on
```

Résultat attendu :

```txt
1
```

État Bluetooth observé :

```txt
Bluetooth Status:
  State: ON
  Name: sdk_gphone16k_x86_64
```

nRF Connect Mobile dans l’émulateur arrive à voir la trottinette, ce qui confirme que le pont BLE fonctionne.

Xiaomi Home fonctionne aussi dans l’émulateur avec l’AVD Android 13 API 33.

---

## Services BLE détectés

Un scan GATT avec Python/Bleak donne :

```txt
SERVICE 00001801-0000-1000-8000-00805f9b34fb
handle=0x0002 uuid=00002a05-0000-1000-8000-00805f9b34fb props=['indicate']

SERVICE 0000fe95-0000-1000-8000-00805f9b34fb
handle=0x0014 uuid=00000010-0000-1000-8000-00805f9b34fb props=['write-without-response', 'notify']
handle=0x0011 uuid=00000005-0000-1000-8000-00805f9b34fb props=['read', 'notify']
handle=0x0017 uuid=00000016-0000-1000-8000-00805f9b34fb props=['write-without-response', 'notify']
handle=0x001a uuid=00000017-0000-1000-8000-00805f9b34fb props=['write', 'notify']
handle=0x0026 uuid=0000001c-0000-1000-8000-00805f9b34fb props=['write-without-response', 'notify']
handle=0x0020 uuid=0000001a-0000-1000-8000-00805f9b34fb props=['write-without-response', 'notify']
handle=0x001d uuid=00000018-0000-1000-8000-00805f9b34fb props=['write-without-response', 'notify']
handle=0x000f uuid=00000004-0000-1000-8000-00805f9b34fb props=['read']
handle=0x0023 uuid=0000001b-0000-1000-8000-00805f9b34fb props=['write-without-response', 'notify']
```

Service Xiaomi principal :

```txt
0000fe95-0000-1000-8000-00805f9b34fb
```

---

## Mapping handles ATT vers UUID

Dans les logs Bumble, les handles ATT observés sont légèrement décalés par rapport aux handles affichés par Bleak. Bleak affiche souvent le handle de déclaration, tandis que les logs ATT utilisent le handle de valeur.

Mapping utile :

| Handle ATT Bumble | UUID BLE   | Rôle supposé                 |
| ----------------: | ---------- | ---------------------------- |
|          `0x0010` | `00000004` | version firmware en lecture  |
|          `0x0015` | `00000010` | canal Xiaomi secondaire      |
|          `0x0018` | `00000016` | handshake / authentification |
|          `0x001B` | `00000017` | canal secondaire             |
|          `0x001E` | `00000018` | canal secondaire             |
|          `0x0021` | `0000001a` | commandes app vers trott     |
|          `0x0024` | `0000001b` | réponses trott vers app      |
|          `0x0027` | `0000001c` | infos simples en clair       |

---

## Informations récupérées sans Xiaomi Home

La caractéristique :

```txt
0000001c-0000-1000-8000-00805f9b34fb
```

répond à des commandes simples.

Script Python testé :

```python
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
```

Résultats obtenus :

```txt
write 00 -> 00020103
write 01 -> 010430303037 -> "0007"
write 03 -> 030852544c3837363243 -> "RTL8762C"
```

Interprétation :

* `03` retourne la puce BLE : `RTL8762C`
* `01` retourne probablement une version ou un identifiant : `0007`
* `00` retourne une petite réponse binaire : `01 03`

Ces commandes sont simples, lisibles, et ne semblent pas liées au canal chiffré principal.

---

## Protocole observé avec Xiaomi Home

Une fois Xiaomi Home connecté, les échanges importants passent surtout par :

```txt
0x0021 : app -> trott
0x0024 : trott -> app
```

Pattern observé :

```txt
HOST -> 0x0021 : 000000000100
CONTROLLER -> 0x0021 : 00000101
HOST -> 0x0021 : 0100XX00...
CONTROLLER -> 0x0021 : 00000100
CONTROLLER -> 0x0024 : 00000200YY00...
HOST -> 0x0024 : 00000300
```

Interprétation probable :

* `000000000100` : début d’envoi / préparation
* `00000101` : acceptation / prêt à recevoir
* `0100XX00...` : paquet envoyé par l’app, avec compteur `XX`
* `00000100` : ACK de la trott
* `00000200YY00...` : réponse de la trott, avec compteur `YY`
* `00000300` : ACK envoyé par l’app après réception

Le protocole semble donc :

* sessionné ;
* avec compteurs ;
* probablement chiffré ;
* probablement lié à une authentification préalable.

Les gros paquets ne doivent pas être rejoués hors contexte sans comprendre la session.

---

## Phase de handshake observée

Avant les échanges principaux, Xiaomi Home effectue une phase de handshake sur `0x0018`.

On observe notamment :

```txt
HOST -> 0x0015 : a4
CONTROLLER -> 0x0018 : 0000040006f2
HOST -> 0x0018 : 0000050006f2
CONTROLLER -> 0x0018 : 00000401 f2f2f2...
HOST -> 0x0018 : 00000501 f2f2f2...
HOST -> 0x0018 : 000000030100
CONTROLLER -> 0x0018 : 00000101
HOST -> 0x0018 : 0100...
CONTROLLER -> 0x0018 : 00000100
CONTROLLER -> 0x0018 : 00000203...
HOST -> 0x0018 : 00000300
```

Ce flux ressemble fortement à une initialisation de session ou d’authentification.

---

## Capture batterie

Une capture a été faite à partir du timecode :

```txt
00:53:10
```

Le but était d’ouvrir l’onglet batterie dans Xiaomi Home, qui déclenche des requêtes vers la trottinette.

Fichier brut utilisé :

```txt
/home/gabrieb0x/xiaomi_ble_battery_capture.txt
```

Fichier nettoyé :

```txt
/home/gabrieb0x/xiaomi_ble_battery_clean.txt
```

Fichier des requêtes candidates :

```txt
/home/gabrieb0x/battery_interesting_writes.txt
```

Fichier des paires requête/réponse :

```txt
/home/gabrieb0x/battery_pairs.txt
```

---

## Requêtes candidates batterie

Les requêtes utiles extraites sont les paquets envoyés vers `0x0021` après `00:53:10`, en retirant les ACK et doublons.

Exemples :

```txt
00:53:25.574 HANDLE 0x0021 LEN 44 VALUE 01000400...
00:53:26.145 HANDLE 0x0021 LEN 44 VALUE 01000500...
00:53:29.897 HANDLE 0x0021 LEN 53 VALUE 01000600...
00:53:30.566 HANDLE 0x0021 LEN 56 VALUE 01000700...
00:53:35.237 HANDLE 0x0021 LEN 44 VALUE 01000800...
00:53:36.873 HANDLE 0x0021 LEN 23 VALUE 01000900...
00:53:37.176 HANDLE 0x0021 LEN 20 VALUE 01000a00...
00:53:39.679 HANDLE 0x0021 LEN 44 VALUE 01000b00...
00:53:41.159 HANDLE 0x0021 LEN 62 VALUE 01000c00...
00:53:41.904 HANDLE 0x0021 LEN 29 VALUE 01000d00...
00:53:42.134 HANDLE 0x0021 LEN 74 VALUE 01000e00...
00:53:43.670 HANDLE 0x0021 LEN 20 VALUE 01000f00...
00:53:45.177 HANDLE 0x0021 LEN 20 VALUE 01001000...
```

Ces requêtes déclenchent des réponses sur `0x0024`.

---

## État actuel de la recherche

Ce qui est confirmé :

1. Le BLE fonctionne depuis un PC Linux via Bumble.
2. L’émulateur Android peut utiliser le Bluetooth physique du PC.
3. Xiaomi Home fonctionne dans l’émulateur avec Android 13 API 33.
4. La trottinette expose un service Xiaomi `FE95`.
5. Certaines infos simples sont lisibles en clair.
6. Les infos principales passent par un canal sessionné/chiffré entre `0x0021` et `0x0024`.
7. Les requêtes batterie sont probablement parmi les requêtes `01000400` à `01001000`.
8. Le voltage batterie n’est pas directement visible en clair dans la capture BLE brute.

---

## Limite actuelle

Le voltage batterie n’est pas encore décodé.

La raison probable est que les réponses `0x0024` sont chiffrées ou encapsulées dans une session.

Exemple de réponse :

```txt
000002003700fbd36f035e584803f398dac9e995...
```

Le préfixe semble structuré :

```txt
00000200 3700 ...
```

Mais le contenu utile après le compteur semble chiffré ou compressé.

---

## Prochaine étape recommandée

### Étape 1 : logcat Xiaomi Home

Le BLE brut ne donne pas encore le plaintext. Il faut maintenant voir si Xiaomi Home log les données déjà déchiffrées côté app.

Commandes :

```bash
adb logcat -c
adb logcat -v time > ~/xiaomi_logcat_battery.txt
```

Pendant que `logcat` tourne :

1. ouvrir Xiaomi Home ;
2. ouvrir la page de la trott ;
3. aller dans l’onglet batterie ;
4. attendre 10 à 15 secondes ;
5. arrêter logcat avec `Ctrl+C`.

Filtrage :

```bash
grep -iE "battery|batt|bms|voltage|volt|current|soc|cell|charge|capacity|temperature|power|miio|miot|scooter" \
~/xiaomi_logcat_battery.txt > ~/xiaomi_logcat_battery_clean.txt
```

Objectif : trouver un JSON, une structure, ou une ligne de log contenant la tension batterie ou les infos BMS décodées.

### Étape 2 : comparer deux captures

Faire deux captures propres :

* capture sans ouvrir l’onglet batterie ;
* capture en ouvrant l’onglet batterie.

Comparer les paquets `0x0021` et `0x0024`.

Objectif : isoler précisément quelle requête correspond à l’onglet batterie.

### Étape 3 : chercher côté app

Si logcat ne donne rien, il faudra probablement analyser Xiaomi Home côté Android :

* regarder les classes liées à `battery`, `bms`, `scooter`, `miot`, `rn`, `plugin` ;
* identifier où les données sont déchiffrées ;
* éventuellement hooker les fonctions qui reçoivent les données déjà décodées.

### Étape 4 : rejouer uniquement les commandes sûres

Pour l’instant, seules les petites commandes sur `0000001c` ont été rejouées avec succès.

Les gros paquets `0x0021` ne doivent pas encore être rejoués directement, car ils semblent dépendre de :

* la session ;
* un compteur ;
* une clé ;
* une authentification ;
* un état interne de Xiaomi Home.

---

## Commandes utiles

### Scanner la trottinette avec Python

```python
import asyncio
from bleak import BleakScanner

async def main():
    devices = await BleakScanner.discover()
    for d in devices:
        print(d)

asyncio.run(main())
```

### Dump services BLE

```python
import asyncio
from bleak import BleakClient

ADDRESS = "E8:4A:54:53:1D:E9"

async def main():
    async with BleakClient(ADDRESS) as client:
        print("Connecté:", client.is_connected)

        for service in client.services:
            print(f"\nSERVICE {service.uuid}")
            for char in service.characteristics:
                print(
                    f"handle=0x{char.handle:04x} "
                    f"uuid={char.uuid} "
                    f"props={char.properties}"
                )

asyncio.run(main())
```

### Nettoyer une capture Bumble

```bash
perl -pe 's/\e\[[0-9;]*m//g' ~/xiaomi_ble_battery_capture.txt \
| grep -E "ATT_WRITE_COMMAND|ATT_HANDLE_VALUE_NOTIFICATION|attribute_handle:|attribute_value:" \
> ~/xiaomi_ble_battery_clean.txt
```

### Extraire uniquement après un timecode

```bash
awk '/00:53:10/{flag=1} flag' ~/xiaomi_ble_battery_clean.txt \
> ~/xiaomi_ble_battery_after_005310.txt
```

---

## Précautions

Ne pas envoyer de commandes aléatoires.

Ne pas toucher aux mises à jour firmware.

Ne pas envoyer de commandes de reset.

Ne pas tenter de modifier les limites de vitesse.

Ne pas rejouer les gros paquets `0x0021` tant que le système de session n’est pas compris.

Toujours faire les tests trottinette immobile, roue libre si possible, et sans situation dangereuse.

---

## Résumé court

On a réussi à :

* utiliser le Bluetooth réel du PC dans un émulateur Android ;
* lancer Xiaomi Home dans cet émulateur ;
* connecter la Xiaomi Scooter 5 Pro ;
* capturer les échanges BLE ;
* mapper les handles BLE ;
* rejouer des commandes simples en Python ;
* identifier les canaux principaux du protocole ;
* capturer les requêtes candidates liées à l’onglet batterie.

Il reste à comprendre ou contourner la couche chiffrée/sessionnée pour récupérer le voltage batterie en clair.
