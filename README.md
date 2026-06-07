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

## Processus Xiaomi Home observés

Pendant les tests, Xiaomi Home lance plusieurs processus Android distincts.

Exemple observé :

```txt
com.xiaomi.smarthome
com.xiaomi.smarthome:plugin0
com.xiaomi.smarthome:pushservice
com.xiaomi.smarthome:plugin1
```

Exemple de PIDs observés lors d’une capture :

```txt
MAIN=2618
PLUGIN0=3288
PLUGIN1=3984
```

Puis, après relance de l’application, les PIDs ont changé :

```txt
3012 = com.xiaomi.smarthome
3518 = com.xiaomi.smarthome:plugin0
```

Les PIDs sont donc volatiles et doivent être récupérés à chaque nouvelle session avec :

```bash
adb shell ps -A | grep -iE "xiaomi|smarthome|plugin|arthome"
```

ou :

```bash
adb shell pidof -s com.xiaomi.smarthome
adb shell pidof -s com.xiaomi.smarthome:plugin0
adb shell pidof -s com.xiaomi.smarthome:plugin1
```

---

## Observations logcat côté Xiaomi Home

Des captures `logcat` ont été réalisées pour voir si Xiaomi Home affichait directement les données batterie déjà déchiffrées.

Deux approches ont été testées :

1. filtrage large par mots-clés ;
2. capture globale puis filtrage par PID Xiaomi.

### Résultat du filtrage large

Le premier filtrage avec des mots-clés comme :

```txt
battery
batt
bms
voltage
volt
current
soc
cell
charge
capacity
temperature
power
miio
miot
scooter
```

a surtout retourné beaucoup de bruit Android :

```txt
TrafficStats
Conscrypt
Firebase
Gms
InetDiag
BatteryService
GC freed
```

Le mot `soc`, par exemple, peut aussi matcher dans `Socket`, ce qui crée des faux positifs.

La seule information vraiment intéressante dans ce premier log était la présence du plugin :

```txt
INFO: OLD PLUGIN INFO OF xiaomi.scooter.5pro
```

Conclusion : le filtrage large ne donne pas les données batterie en clair.

---

## Observations logcat filtrées par PID

Une capture plus propre a été faite avec `adb logcat -v threadtime`, puis filtrée par PID.

Commande utilisée :

```bash
PID_MAIN=$(adb shell pidof -s com.xiaomi.smarthome | tr -d '\r')
PID_PLUGIN0=$(adb shell pidof -s com.xiaomi.smarthome:plugin0 | tr -d '\r')
PID_PLUGIN1=$(adb shell pidof -s com.xiaomi.smarthome:plugin1 | tr -d '\r')

echo "MAIN=$PID_MAIN PLUGIN0=$PID_PLUGIN0 PLUGIN1=$PID_PLUGIN1"

adb logcat -c
adb logcat -v threadtime > ~/xiaomi_all_threadtime.txt
```

Après la capture :

```bash
awk -v p1="$PID_MAIN" -v p2="$PID_PLUGIN0" -v p3="$PID_PLUGIN1" \
'$3==p1 || $3==p2 || $3==p3' \
~/xiaomi_all_threadtime.txt > ~/xiaomi_pid_only.txt
```

Nettoyage :

```bash
grep -viE "TrafficStats|InetDiag|GC freed|ImeTracker|WindowManager|GraphicsEnvironment|InputMethod|artd|Bugle|Rcs|Firebase|Gms" \
~/xiaomi_pid_only.txt > ~/xiaomi_pid_only_clean.txt
```

Cette capture a confirmé plusieurs éléments importants côté Xiaomi Home.

---

## Cycle GATT confirmé côté Xiaomi Home

Le logcat filtré par PID montre que Xiaomi Home se connecte bien à la trottinette via GATT.

Exemples observés :

```txt
BluetoothGatt: connect() - device: XX:XX:XX:XX:1D:E9, auto: false
BluetoothGatt: registerApp()
BluetoothGatt: onClientRegistered() - status=0 clientIf=6
BluetoothGatt: onClientConnectionState() - status=0 clientIf=6 connected=true device=E8:4A:54:53:1D:E9
BluetoothGatt: discoverServices() - device: XX:XX:XX:XX:1D:E9
BluetoothGatt: onSearchComplete() = Device=E8:4A:54:53:1D:E9 Status=0
```

Cela confirme que Xiaomi Home utilise bien l’API Android `BluetoothGatt` classique.

---

## Notifications BLE activées par Xiaomi Home

Après découverte des services, Xiaomi Home active les notifications sur plusieurs caractéristiques :

```txt
setCharacteristicNotification() - uuid: 0000001b-0000-1000-8000-00805f9b34fb enable: true
setCharacteristicNotification() - uuid: 0000001a-0000-1000-8000-00805f9b34fb enable: true
setCharacteristicNotification() - uuid: 0000001c-0000-1000-8000-00805f9b34fb enable: true
setCharacteristicNotification() - uuid: 00000016-0000-1000-8000-00805f9b34fb enable: true
setCharacteristicNotification() - uuid: 00000010-0000-1000-8000-00805f9b34fb enable: true
```

Cela confirme le rôle important des UUID suivants :

| UUID       | Rôle confirmé / supposé              |
| ---------- | ------------------------------------ |
| `0000001a` | commandes principales app vers trott |
| `0000001b` | réponses principales trott vers app  |
| `0000001c` | infos simples en clair               |
| `00000016` | handshake / authentification         |
| `00000010` | canal Xiaomi secondaire              |

---

## MTU BLE confirmé

Xiaomi Home demande un MTU de 247 :

```txt
BluetoothGatt: configureMTU() - device: XX:XX:XX:XX:1D:E9 mtu: 247
BluetoothGatt: onConfigureMTU() - Device=E8:4A:54:53:1D:E9 mtu=247 status=0
```

Cela confirme que l’application prépare des échanges BLE avec des paquets plus grands que le MTU BLE par défaut.

Cette observation colle avec les captures Bumble, où certains paquets `0x0021` et `0x0024` sont longs.

---

## Problèmes / warnings observés dans l’émulateur

Plusieurs erreurs apparaissent dans logcat, mais elles ne semblent pas bloquer le fonctionnement principal.

### Environnement non-MIUI

Xiaomi Home essaie d’accéder à des classes MIUI absentes dans l’émulateur Android standard :

```txt
java.lang.NoClassDefFoundError: Failed resolution of: Lmiui/os/SystemProperties;
Caused by: java.lang.ClassNotFoundException: miui.os.SystemProperties
```

Autre exemple :

```txt
ClassNotFoundException: miui.os.Build
```

Interprétation : Xiaomi Home vérifie probablement si l’app tourne sur MIUI / HyperOS. Comme l’émulateur est un Android standard, ces classes n’existent pas. L’erreur est visible, mais l’app continue de fonctionner.

### Services Xiaomi absents

On observe aussi :

```txt
Failed to find provider info for com.milink.service.device
Failed to find provider info for com.xiaomi.iot.spec
```

Interprétation : certains services Xiaomi/MiLink ne sont pas présents dans l’émulateur. Cela peut casser certaines fonctions annexes, mais pas forcément la connexion BLE à la trott.

### Classes générées introuvables

On observe :

```txt
MiJiaRouter: not found class com.xiaomi.smarthome.generated.ServiceInit_...
ClassNotFoundException
```

Interprétation : Xiaomi Home essaie de charger dynamiquement des modules/services. Certaines classes ne sont pas trouvées, mais le plugin de la trottinette continue malgré tout à fonctionner.

---

## Ce que les logs n’ont PAS donné

Malgré les captures logcat :

* aucune ligne claire avec `voltage` ;
* aucune ligne claire avec `battery voltage` ;
* aucun JSON évident contenant les infos BMS ;
* aucune donnée batterie directement lisible ;
* aucune structure claire du type `cell_voltage`, `current`, `capacity`, `temperature`.

Conclusion : Xiaomi Home ne log pas les données batterie en clair dans logcat, ou alors elles passent dans une couche non visible avec les filtres actuels.

---

## Mise à jour de l’état actuel de la recherche

Ce qui est maintenant confirmé :

1. Le BLE fonctionne depuis Linux via Bumble.
2. L’émulateur Android peut utiliser le contrôleur Bluetooth physique du PC.
3. Xiaomi Home fonctionne dans l’émulateur avec Android 13 API 33.
4. Xiaomi Home utilise bien `BluetoothGatt`.
5. Xiaomi Home se connecte bien à `E8:4A:54:53:1D:E9`.
6. Xiaomi Home découvre les services GATT sans erreur.
7. Xiaomi Home active les notifications sur `0000001a`, `0000001b`, `0000001c`, `00000016` et `00000010`.
8. Xiaomi Home configure un MTU de 247.
9. Le protocole principal passe bien par `0x0021` et `0x0024`.
10. Les petites commandes sur `0000001c` fonctionnent hors Xiaomi Home.
11. Les réponses batterie ne sont pas visibles en clair dans le BLE brut.
12. Les réponses batterie ne sont pas visibles en clair dans logcat classique.
13. Le voltage batterie est donc probablement déchiffré ou interprété plus haut dans le code de Xiaomi Home/plugin.

---

## Mise à jour de la limite actuelle

Le blocage principal n’est plus la connexion BLE.

Le blocage actuel est la récupération du contenu décodé.

On sait maintenant que :

```txt
BLE brut -> paquets sessionnés/chiffrés
logcat classique -> pas de plaintext batterie
```

Le voltage existe forcément quelque part, car Xiaomi Home l’affiche ou l’utilise dans l’onglet batterie, mais il n’est pas exposé directement dans les logs.

Il faut donc trouver l’endroit où Xiaomi Home :

1. reçoit les notifications BLE ;
2. déchiffre ou dépaquette la réponse ;
3. transforme les données en objet interne / JSON ;
4. transmet ces données au plugin ou à l’interface React Native ;
5. affiche les valeurs batterie.

---

## Prochaine étape recommandée

### Étape 1 : conserver les captures actuelles

Les fichiers importants à garder sont :

```txt
~/xiaomi_ble_battery_capture.txt
~/xiaomi_ble_battery_clean.txt
~/battery_interesting_writes.txt
~/battery_pairs.txt
~/xiaomi_logcat_battery_clean.txt
~/xiaomi_logcat_real.txt
~/xiaomi_pid_only_clean.txt
```

Ces fichiers documentent :

* le BLE brut ;
* les requêtes candidates batterie ;
* les réponses associées ;
* le comportement GATT de Xiaomi Home ;
* les limites de logcat.

### Étape 2 : refaire une capture synchronisée BLE + logcat

Pour mieux corréler les actions :

1. lancer Bumble avec `tee` ;
2. lancer `adb logcat -v threadtime` ;
3. noter précisément l’heure de chaque clic ;
4. ouvrir uniquement l’onglet batterie ;
5. arrêter les deux captures.

Objectif : relier précisément :

```txt
clic onglet batterie
↓
requête 0x0021
↓
réponse 0x0024
↓
éventuels logs Xiaomi
```

### Étape 3 : passer à l’analyse applicative

Comme logcat ne donne pas les données en clair, il faudra probablement analyser Xiaomi Home côté app.

Pistes :

* chercher dans l’APK les chaînes :

  * `battery`
  * `bms`
  * `voltage`
  * `cell`
  * `capacity`
  * `current`
  * `temperature`
  * `scooter`
  * `0000001a`
  * `0000001b`
  * `00000016`
  * `0000001c`
* chercher les classes autour de :

  * `BluetoothGattCallback`
  * `onCharacteristicChanged`
  * `BluetoothGattCharacteristic.getValue`
  * `PluginRNActivity`
  * `IPluginRequest`
  * `processResponse`
  * `miot`
  * `miio`

### Étape 4 : hooking local avec Frida

La prochaine piste sérieuse est d’utiliser Frida pour hooker les fonctions Android/Java côté Xiaomi Home.

Fonctions candidates :

```txt
android.bluetooth.BluetoothGattCallback.onCharacteristicChanged
android.bluetooth.BluetoothGattCharacteristic.getValue
android.bluetooth.BluetoothGatt.writeCharacteristic
org.json.JSONObject
org.json.JSONArray
com.xiaomi.router.miio.miioplugin.IPluginRequest$Stub.onTransact
```

Objectif : récupérer les données après réception BLE et, si possible, après déchiffrement.

L’idée n’est pas de modifier le comportement de l’app, seulement d’observer ce qui transite en mémoire.

### Étape 5 : ne pas rejouer les gros paquets pour l’instant

Même si les requêtes `01000400` à `01001000` ont été identifiées, il ne faut pas encore les rejouer directement en Python.

Raison :

* elles semblent dépendre d’une session ;
* elles utilisent des compteurs ;
* elles sont probablement chiffrées ;
* elles dépendent peut-être de clés générées pendant le handshake ;
* elles peuvent être invalides hors contexte.

Pour l’instant, seules les commandes simples sur `0000001c` sont considérées comme sûres.


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
