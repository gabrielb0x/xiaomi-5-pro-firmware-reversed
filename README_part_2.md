# Reverse engineering BLE Xiaomi Scooter 5 Pro — README #2

## Rôle de ce document

Ce document est la suite du premier README du projet de reverse engineering BLE de la **Xiaomi Scooter 5 Pro**.

Le premier document résumait principalement :

- la mise en place de l’environnement Linux / Android Emulator / Bumble ;
- la validation du Bluetooth via l’émulateur ;
- le mapping des services BLE ;
- les premières captures BLE ;
- les commandes simples sur `0000001c` ;
- les premières hypothèses sur le canal principal `0x0021` / `0x0024`.

Ce second document reprend la suite des recherches :

- analyse statique avec JADX ;
- compréhension de la pile BLE Xiaomi Home ;
- identification du pont React Native utilisé par les plugins ;
- test d’un script Python naïf pour le voltage ;
- essais Frida et raisons de leur abandon temporaire ;
- nouvelle stratégie recommandée pour arriver à un script Python autonome.

L’objectif final reste le même : créer un script Python capable de récupérer les données batterie de la trottinette, idéalement via `bleak`, sans dépendre de Xiaomi Home.

---

## État général du projet à ce stade

On sait maintenant que la connexion BLE n’est plus le problème principal.

Le problème réel est la compréhension de la couche applicative Xiaomi :

```txt
BLE brut
↓
canal Xiaomi sessionné / probablement chiffré
↓
Xiaomi Home Java/Kotlin
↓
bridge React Native
↓
plugin scooter
↓
décodage batterie / UI
```

Le voltage n’est pas exposé en clair dans les lectures BLE simples, ni dans les logs Android classiques. Il faut donc comprendre comment Xiaomi Home construit les requêtes et décode les réponses.

---

## Rappel des éléments confirmés avant ce document

### Trottinette

```txt
Modèle visible : xiaomi.scooter.5pro
Adresse BLE utilisée : E8:4A:54:53:1D:E9
Nom BLE lu : dreame scooter
Firmware lu : 2.7.0_0015
```

### Service BLE principal

```txt
0000fe95-0000-1000-8000-00805f9b34fb
```

### Caractéristiques importantes

| UUID court | Rôle observé / supposé |
|---|---|
| `00000004` | lecture firmware |
| `00000005` | lecture / notify secondaire |
| `00000010` | canal Xiaomi secondaire |
| `00000016` | handshake / sécurité |
| `00000017` | canal secondaire avec write |
| `00000018` | canal secondaire |
| `0000001a` | commandes principales app vers trott |
| `0000001b` | réponses principales trott vers app |
| `0000001c` | infos simples en clair |

### Handles ATT utiles

| Handle ATT Bumble | UUID BLE | Rôle |
|---:|---|---|
| `0x0010` | `00000004` | firmware |
| `0x0015` | `00000010` | canal secondaire |
| `0x0018` | `00000016` | handshake / auth |
| `0x001B` | `00000017` | secondaire |
| `0x001E` | `00000018` | secondaire |
| `0x0021` | `0000001a` | commandes principales |
| `0x0024` | `0000001b` | réponses principales |
| `0x0027` | `0000001c` | infos simples |

---

## Partie 1 — Analyse JADX : début de la vraie avancée

Après les captures BLE et logcat, l’analyse statique avec **JADX** a été reprise.

L’objectif était de trouver où Xiaomi Home :

1. reçoit les notifications BLE ;
2. écrit dans les caractéristiques BLE ;
3. transforme les `byte[]` en format exploitable ;
4. transmet les données au plugin scooter.

---

## Recherche initiale : `onCharacteristicChanged`

Une recherche dans JADX sur :

```txt
onCharacteristicChanged
```

a permis de trouver l’interface suivante :

```java
package com.xiaomi.smarthome.library.bluetooth.connect;

import android.bluetooth.BluetoothGattCharacteristic;
import android.bluetooth.BluetoothGattDescriptor;

public interface IBluetoothGattResponse {
    void onCharacteristicChanged(BluetoothGattCharacteristic bluetoothGattCharacteristic, byte[] bArr);

    void onCharacteristicRead(BluetoothGattCharacteristic bluetoothGattCharacteristic, int i, byte[] bArr);

    void onCharacteristicWrite(BluetoothGattCharacteristic bluetoothGattCharacteristic, int i, byte[] bArr);

    void onConnectionStateChange(int i, int i2);

    void onDescriptorWrite(BluetoothGattDescriptor bluetoothGattDescriptor, int i);

    void onMtuChanged(int i, int i2);

    void onReadRemoteRssi(int i, int i2);

    void onServicesDiscovered(int i);
}
```

Conclusion : cette interface ne parse pas les données directement. Elle définit uniquement le contrat des callbacks BLE.

Elle confirme cependant que Xiaomi Home transporte bien les données BLE sous forme de `byte[]`.

---

## Interface `IBleConnectWorker`

En remontant depuis les méthodes d’écriture BLE, l’interface suivante a été trouvée :

```java
package com.xiaomi.smarthome.library.bluetooth.connect;

import com.xiaomi.smarthome.library.bluetooth.connect.listener.GattResponseListener;
import com.xiaomi.smarthome.library.bluetooth.connect.response.BleResponse;
import java.util.UUID;

public interface IBleConnectWorker {
    void clearGattResponseListener(GattResponseListener gattResponseListener);

    void closeGatt();

    boolean discoverService();

    int getCurrentStatus();

    BleGattProfile getGattProfile();

    void isCharacterExist(UUID uuid, UUID uuid2, BleResponse<Void> bleResponse);

    boolean openGatt();

    boolean readCharacteristic(UUID uuid, UUID uuid2);

    boolean readRemoteRssi();

    boolean refreshDeviceCache();

    void registerGattResponseListener(GattResponseListener gattResponseListener);

    boolean requestConnectionPriority(int i);

    boolean requestMtu(int i);

    boolean setCharacteristicIndication(UUID uuid, UUID uuid2, boolean z);

    boolean setCharacteristicNotification(UUID uuid, UUID uuid2, boolean z);

    boolean writeCharacteristic(UUID uuid, UUID uuid2, byte[] bArr);

    boolean writeCharacteristicWithNoRsp(UUID uuid, UUID uuid2, byte[] bArr);
}
```

Conclusion : cette interface décrit les actions BLE possibles, mais elle ne construit pas les paquets batterie.

---

## Classe abstraite `mr0`

La classe `_m_j.mr0` a été ouverte.

Elle est importante car elle représente une base commune pour les requêtes BLE Xiaomi.

```java
public abstract class mr0 implements IBleConnectWorker, IBleRequest, Handler.Callback, GattResponseListener, RuntimeChecker {
    public UUID Oooooo;
    public UUID Oooooo0;
    public byte[] OoooooO;
    ...

    public abstract void OooO0Oo();

    @Override
    public final boolean writeCharacteristic(UUID uuid, UUID uuid2, byte[] bArr) {
        return this.o00Oo0.writeCharacteristic(uuid, uuid2, bArr);
    }

    @Override
    public final boolean writeCharacteristicWithNoRsp(UUID uuid, UUID uuid2, byte[] bArr) {
        return this.o00Oo0.writeCharacteristicWithNoRsp(uuid, uuid2, bArr);
    }
}
```

Interprétation des champs :

```txt
Oooooo0 = probablement UUID service
Oooooo  = probablement UUID caractéristique
OoooooO = payload byte[] envoyé
```

Conclusion : `mr0` ne construit pas lui-même les paquets. Il sert de classe abstraite pour les requêtes BLE.

---

## Classes `qu0` et `ru0`

Deux classes concrètes ont été analysées.

### `qu0`

```java
public final class qu0 extends mr0 implements IFastSchedule, WriteCharacterListener {
    @Override
    public final void OooO0Oo() {
        if (this.o00Oo0.writeCharacteristicWithNoRsp(this.Oooooo0, this.Oooooo, this.OoooooO)) {
            OooO0o0();
        } else {
            OooO0O0(-1);
        }
    }
}
```

`qu0` envoie donc un payload déjà préparé via :

```txt
writeCharacteristicWithNoRsp(serviceUUID, charUUID, payload)
```

### `ru0`

```java
public final class ru0 extends mr0 implements WriteCharacterListener {
    public final void OooO0Oo() {
        switch (this.o0ooOO0) {
            case 0:
                this.o00Oo0.writeCharacteristicWithNoRsp(this.Oooooo0, this.Oooooo, this.OoooooO);
                break;
            default:
                this.o00Oo0.writeCharacteristic(this.Oooooo0, this.Oooooo, this.OoooooO);
                break;
        }
    }
}
```

`ru0` peut envoyer avec ou sans réponse selon le mode.

Conclusion : `qu0` et `ru0` sont des exécuteurs BLE. Ils ne construisent pas encore la requête batterie.

---

## Classe `tk0` : dispatcher BLE central

La classe `_m_j.tk0` a été analysée.

Elle implémente :

```java
IBleConnectMaster
```

Les méthodes importantes :

```java
public final void write(UUID uuid, UUID uuid2, byte[] bArr, BleWriteResponse bleWriteResponse) {
    ru0 ru0Var = new ru0(pr0VarOooO00o, 1);
    ru0Var.Oooooo0 = uuid;
    ru0Var.Oooooo = uuid2;
    ru0Var.OoooooO = bArr;
    qk0Var.OooO00o(ru0Var);
}

public final void writeNoRsp(UUID uuid, UUID uuid2, byte[] bArr, BleWriteResponse bleWriteResponse) {
    ru0 ru0Var = new ru0(pr0VarOooO00o, 0);
    ru0Var.Oooooo0 = uuid;
    ru0Var.Oooooo = uuid2;
    ru0Var.OoooooO = bArr;
    qk0Var.OooO00o(ru0Var);
}

public final void writeNoRspFast(UUID uuid, UUID uuid2, byte[] bArr, BleWriteResponse bleWriteResponse) {
    qu0 qu0Var = new qu0(pr0VarOooO00o);
    qu0Var.Oooooo0 = uuid;
    qu0Var.Oooooo = uuid2;
    qu0Var.OoooooO = bArr;
    qk0Var.OooO00o(qu0Var);
}
```

Conclusion : `tk0` reçoit déjà le `byte[]` final. Il ne le construit pas.

Chaîne confirmée :

```txt
payload byte[]
↓
tk0.writeNoRspFast(...)
↓
qu0
↓
BluetoothGatt
```

---

## Classe `rk0` : manager BLE global

La classe `_m_j.rk0` a été analysée.

Elle implémente :

```java
IBleConnectManager
```

Elle expose les méthodes haut niveau :

```java
connect(...)
disconnect(...)
notify(...)
read(...)
write(...)
writeNoRsp(...)
writeNoRspFast(...)
```

Exemple :

```java
public final void writeNoRspFast(String str, UUID uuid, UUID uuid2, byte[] bArr, BleWriteResponse bleWriteResponse) {
    if (TextUtils.isEmpty(str) || uuid == null || uuid2 == null || bArr == null) {
        return;
    }
    OooO0O0(str).writeNoRspFast(uuid, uuid2, bArr, bleWriteResponse);
}
```

Interprétation :

```txt
str   = adresse MAC / identifiant périphérique
uuid  = UUID service
uuid2 = UUID caractéristique
bArr  = payload BLE
```

Conclusion : `rk0` est une façade globale. Elle route les appels vers `tk0`.

Chaîne complète côté écriture :

```txt
code haut niveau Xiaomi / plugin
↓
rk0.writeNoRspFast(mac, service, char, payload, callback)
↓
tk0.writeNoRspFast(service, char, payload, callback)
↓
qu0
↓
BluetoothGatt.writeCharacteristic
```

---

## Limite des `Find Usage` sur `rk0`

Les recherches `Find Usage` sur `writeNoRspFast` dans `rk0` ne donnent pas toujours de résultat utile.

Cause probable : Xiaomi Home utilise des proxys dynamiques / reflection.

Dans `rk0`, on observe :

```java
dürze.OooOo(...)
```

et des appels indirects via interfaces. JADX ne peut donc pas toujours relier proprement les usages.

Conclusion : il faut chercher aussi les points d’entrée plus hauts, notamment côté React Native.

---

## Partie 2 — Bridge React Native Xiaomi

La grosse avancée a été de trouver que Xiaomi Home utilise un bridge React Native pour communiquer avec les plugins.

La classe importante est :

```txt
com.xiaomi.smarthome.framework.api.provider.core.RnBluetoothProviderImpl
```

Cette classe expose des méthodes BLE au plugin RN.

Méthodes intéressantes observées :

```txt
write
writeNoRsp
notify
registerBlockListener
miotBleEncrypt
miotBleDecrypt
securityChipEncrypt
securityChipDecrypt
```

Conclusion : les plugins Xiaomi, dont le plugin scooter, parlent au Bluetooth via ce provider React Native.

---

## `registerBlockListener` et classe `i8b`

Une méthode très importante a été trouvée :

```java
XmBluetoothManager.getInstance().registerBlockListener(str, new i8b(this, callback));
```

La classe `_m_j.i8b` a été ouverte :

```java
package _m_j;

import android.os.Bundle;
import com.facebook.react.bridge.Callback;
import com.xiaomi.smarthome.bluetooth.Response;
import com.xiaomi.smarthome.framework.api.provider.core.RnBluetoothProviderImpl;

public final class i8b implements Response.BleReadResponse {
    public final RnBluetoothProviderImpl Oooooo;
    public final Callback Oooooo0;

    public i8b(RnBluetoothProviderImpl rnBluetoothProviderImpl, Callback callback) {
        this.Oooooo = rnBluetoothProviderImpl;
        this.Oooooo0 = callback;
    }

    @Override
    public final void onResponse(int i, byte[] bArr) {
        byte[] bArr2 = bArr;
        Callback callback = this.Oooooo0;
        if (callback != null) {
            if (i == 0) {
                callback.invoke(Boolean.TRUE, com.xiaomi.smarthome.framework.plugin.rn.nativemodule.OooO0O0.OooO0O0(bArr2));
            } else {
                this.Oooooo.o00o0o0o(i, new Bundle(), callback);
            }
        }
    }
}
```

Conclusion très importante :

```txt
notification / block BLE reçu
↓
byte[] bArr
↓
OooO0O0.OooO0O0(bArr2)
↓
conversion en string
↓
callback React Native
↓
plugin JS
```

Cela confirme que les réponses BLE principales sont probablement renvoyées au plugin sous forme de chaîne hexadécimale.

---

## Conversion `byte[]` vers hex string

La méthode suivante a été analysée :

```java
com.xiaomi.smarthome.framework.plugin.rn.nativemodule.OooO0O0.OooO0O0(byte[]) String
```

Elle ressemble à :

```java
public static String OooO0O0(byte[] bArr) {
    if (bArr == null) {
        return null;
    }
    return zv6.Oooo0o(bArr);
}
```

Conclusion : les `byte[]` reçus côté BLE sont convertis en string, probablement hex.

---

## Conversion inverse hex string vers `byte[]`

La méthode inverse a aussi été identifiée :

```java
OooOo0O(String str)
```

Elle reconstruit un tableau de bytes depuis une string hex.

Conclusion : le flux côté React Native est probablement :

```txt
JS/plugin → hex string → OooOo0O(str) → byte[] → write/writeNoRsp → BLE
BLE/block → byte[] → OooO0O0(bArr) → hex string → JS/plugin
```

C’est une conclusion centrale.

---

## Architecture applicative désormais supposée

```txt
Plugin scooter React Native / JS / Hermes
↓
MIOTBluetoothModuleCore / MIOTBluetoothModuleTiny
↓
RnBluetoothProviderImpl
↓
OooOo0O(String) : hex -> byte[]
↓
rk0 / tk0 / qu0 / ru0
↓
BluetoothGatt
↓
Trottinette
```

Flux retour :

```txt
Trottinette
↓
BluetoothGatt notification
↓
registerBlockListener
↓
i8b.onResponse(int, byte[])
↓
OooO0O0(byte[]) : byte[] -> hex
↓
callback React Native
↓
Plugin scooter
↓
parsing batterie
```

---

## Hypothèse principale actuelle

Le voltage batterie n’est probablement pas décodé dans le Java principal de Xiaomi Home.

Il est probablement décodé dans le plugin React Native / JavaScript / Hermes de la trottinette.

Le Java principal sert surtout à :

- gérer le Bluetooth bas niveau ;
- convertir hex <-> byte[] ;
- exposer des APIs au plugin ;
- faire le transport des données.

Le plugin, lui, contient probablement :

- la liste des commandes MIOT / scooter ;
- la logique de requête batterie ;
- le parsing BMS ;
- les labels UI ;
- la conversion tension / courant / cellules.

---

## Partie 3 — Test Python direct du voltage

Un script Python de test a été créé pour voir si le voltage pouvait être récupéré directement par lecture ou notification simple.

Le script :

- se connecte à la trott ;
- liste les services ;
- lit quelques caractéristiques ;
- active les notifications ;
- envoie les commandes connues sur `0000001c` ;
- cherche naïvement des valeurs numériques ressemblant à des tensions.

Résultat : le script fonctionne techniquement, mais ne trouve pas le vrai voltage.

---

## Résultat du script Python direct

Services observés :

```txt
SERVICE 00001801-0000-1000-8000-00805f9b34fb
  00002a05 indicate

SERVICE 0000fe95-0000-1000-8000-00805f9b34fb
  00000005 read notify
  0000001a write-without-response notify
  0000001b write-without-response notify
  00000017 write notify
  0000001c write-without-response notify
  00000016 write-without-response notify
  00000010 write-without-response notify
  00000004 read
  00000018 write-without-response notify
```

Lecture firmware :

```txt
00000004 -> 32 2E 37 2E 30 5F 30 30 31 35 ... = 2.7.0_0015
```

Commandes `0000001c` :

```txt
write 00 -> 00 02 01 03
write 01 -> 01 04 30 30 30 37 = "0007"
write 03 -> 03 08 52 54 4C 38 37 36 32 43 = "RTL8762C"
```

Le script a affiché des “possibles voltages”, mais ce sont des faux positifs.

Exemple :

```txt
00 02 01 03 -> 51.20 V supposé
```

Cette valeur n’est pas un voltage, c’est juste une interprétation numérique naïve de bytes courts.

Conclusion : le voltage n’est pas exposé en clair via ces lectures simples.

---

## Amélioration du script Python direct

Pour éviter les faux positifs, il faut ignorer les réponses connues de `0000001c` :

```python
known_info = [
    bytes.fromhex("00020103"),
    bytes.fromhex("010430303037"),
    bytes.fromhex("030852544c3837363243"),
]

if data in known_info:
    return

candidates = find_voltage_candidates(data)
if candidates and len(data) >= 8:
    ...
```

Conclusion : le script Python direct est utile pour tester les couches simples, mais il ne suffit pas à récupérer la batterie.

---

## Partie 4 — Tentative Frida : pourquoi ça a été tenté

Frida a été tenté car c’est normalement une méthode très efficace pour obtenir un script Python final.

L’idée était :

```txt
Xiaomi Home sait déjà construire les requêtes
Xiaomi Home sait déjà déchiffrer les réponses
Xiaomi Home sait déjà parser les données batterie

Donc :
1. on hooke Xiaomi Home ;
2. on capture plaintext + ciphertext ;
3. on comprend le protocole ;
4. on recode en Python.
```

En théorie, c’est la meilleure méthode.

En pratique, dans cet environnement, ça a bloqué.

---

## Tentative Frida server classique

Frida côté PC a été installé dans un venv :

```bash
python3 -m venv ~/.venvs/frida
source ~/.venvs/frida/bin/activate
pip install --upgrade pip
pip install --upgrade frida-tools
```

`frida-server` a été poussé dans l’émulateur :

```bash
adb push frida-server /data/local/tmp/frida-server
adb shell chmod 755 /data/local/tmp/frida-server
adb shell "/data/local/tmp/frida-server >/dev/null 2>&1 &"
```

`frida-ps -U` fonctionnait.

Mais l’attachement à Xiaomi Home échouait :

```txt
Failed to attach: unable to access process with pid XXXX
```

Conclusion : l’émulateur Pixel_7 Google Play n’est pas rootable et ne permet pas l’attachement à un process non-debuggable.

---

## Problème des AVD rootables

Un AVD rootable API 33 Google APIs x86_64 a été créé.

Root OK :

```txt
adb root
uid=0(root)
```

Mais l’installation de Xiaomi Home échoue car l’APK extrait est ARM64 :

```txt
INSTALL_FAILED_NO_MATCHING_ABIS
```

L’AVD rootable est :

```txt
ro.product.cpu.abilist = x86_64
```

Alors que Xiaomi Home contient :

```txt
lib/arm64-v8a/...
```

Un AVD ARM64 a été tenté, mais l’émulateur Android refuse ARM64 sur hôte x86_64 :

```txt
Avd's CPU Architecture 'arm64' is not supported by the QEMU2 emulator on x86_64 host.
System image must match the host architecture.
```

Conclusion : impossible d’avoir à la fois :

- Xiaomi Home ARM64 fonctionnel ;
- AVD rootable ;
- hôte PC x86_64 ;
- Frida server classique.

---

## Tentative de dump offline du userdata AVD

Une tentative a été faite pour monter l’image disque de l’AVD Pixel_7 afin de récupérer les fichiers privés Xiaomi Home.

Fichiers observés :

```txt
~/.android/avd/Pixel_7.avd/userdata-qemu.img
~/.android/avd/Pixel_7.avd/userdata-qemu.img.qcow2
```

Conversion :

```bash
qemu-img convert -O raw userdata-qemu.img.qcow2 ~/avd_dump/pixel7_userdata.raw
```

Mais le montage a échoué :

```txt
mauvais type de système de fichiers
```

`file` et `blkid` ne détectaient pas de système ext4/f2fs évident :

```txt
pixel7_userdata.raw: data
/dev/loop0: data
```

Conclusion : ce chemin n’a pas abouti rapidement. Il est abandonné temporairement.

---

## Tentative Frida Gadget avec apktool

Une tentative de patch APK avec Frida Gadget a été faite.

Méthode :

- décompiler `base.apk` avec apktool ;
- ajouter `libfrida-gadget.so` ;
- ajouter un `ContentProvider` `FridaInit` ;
- rebuild ;
- signer ;
- installer.

Problèmes rencontrés :

1. apktool 2.7.0 a crashé sur des smali existants ;
2. apktool 3.0.1 a corrigé ce problème ;
3. `aapt2` a ensuite cassé sur de nombreuses ressources modernes ;
4. les patches XML ont déclenché de nouvelles erreurs de ressources ;
5. la méthode est devenue trop coûteuse et instable.

Conclusion : apktool est abandonné pour ce projet à court terme.

---

## Tentative Frida Gadget avec `patchelf`

Une autre méthode a été essayée pour éviter apktool : patcher directement une bibliothèque native déjà chargée.

Lib candidate trouvée :

```txt
work/split/lib/arm64-v8a/librnsdk.so
```

Autres libs RN présentes :

```txt
libyrnbridge.so
libyrnv8executor.so
libhiarplugin.so
librnsdk.so
libhermes.so
libreactnativejni.so
```

Patch effectué :

```bash
patchelf --add-needed libfrida-gadget.so work/split/lib/arm64-v8a/librnsdk.so
```

Résultat :

```txt
Avant :
liblog.so
libm.so
libdl.so
libc.so

Après :
libfrida-gadget.so
liblog.so
libm.so
libdl.so
libc.so
```

L’APK a pu être repacké, aligné, signé et installé après correction de `resources.arsc` non compressé.

Mais Xiaomi Home crashait au démarrage.

Conclusion : la méthode native est intéressante, mais pas assez stable actuellement. Le crash peut venir de :

- `librnsdk.so` chargée trop tôt ;
- Frida Gadget initialisé trop tôt ;
- détection de modification ;
- incompatibilité linker ;
- dépendance manquante ;
- signature modifiée ;
- side effect du repack.

Frida est donc mis en pause.

---

## Décision actuelle : abandon temporaire de Frida

À ce stade, Frida n’a pas produit de données exploitables.

Ce n’est pas parce que Frida est une mauvaise idée. C’est parce que l’environnement actuel bloque trop :

```txt
Pixel_7 fonctionnel = pas rootable
Pixel_7 rootable = x86_64, incompatible Xiaomi Home ARM64
Patch APK = crash / instable
```

Conclusion : Frida reste une bonne piste théorique, mais elle n’est pas la meilleure piste pratique maintenant.

---

## Pourquoi revenir à JADX

L’analyse avec JADX a réellement permis de progresser.

Elle a confirmé :

- les wrappers BLE ;
- les méthodes d’écriture ;
- les callbacks de réception ;
- le pont React Native ;
- la conversion hex <-> bytes ;
- la probabilité que le parsing batterie soit côté plugin.

C’est actuellement la piste la plus stable.

Nouvelle direction :

```txt
JADX statique profond
↓
identifier plugin RN / Hermes
↓
trouver les appels writeNoRsp / registerBlockListener / decrypt
↓
extraire la logique batterie
↓
réimplémenter en Python
```

---

## Partie 5 — Plan de reprise propre avec JADX

### Objectif immédiat

Trouver où le plugin scooter :

1. active `registerBlockListener` ;
2. envoie les commandes via `writeNoRsp` / `write` ;
3. appelle `miotBleDecrypt` ou `securityChipDecrypt` ;
4. parse la réponse batterie ;
5. affiche ou stocke le voltage.

---

## Recherches JADX prioritaires

Dans JADX, chercher dans cet ordre :

```txt
registerBlockListener
MIOTBluetoothModuleCore
MIOTBluetoothModuleTiny
writeNoRsp
writeNoRspFast
miotBleDecrypt
miotBleDecryptSync
miotBleEncrypt
securityChipDecrypt
securityChipEncrypt
bleStandardAuthDecrypt
bleStandardAuthEncrypt
OooO0O0(byte[])
OooOo0O(String)
```

Puis chercher les mots métier :

```txt
battery
batt
bms
voltage
volt
current
capacity
cell
temperature
power
scooter
vehicle
ride
mijia
dreame
ninebot
```

Ne pas chercher uniquement `xiaomi.scooter.5pro`, car le plugin peut être nommé autrement ou chargé dynamiquement.

---

## Recherches terminal dans les sources JADX

Si JADX exporte les sources :

```bash
mkdir -p ~/xiaomi_apk/jadx_src
jadx -d ~/xiaomi_apk/jadx_src ~/xiaomi_apk/base.apk
```

Recherche :

```bash
cd ~/xiaomi_apk/jadx_src

grep -RIn "registerBlockListener" sources | head -100
grep -RIn "MIOTBluetoothModule" sources | head -100
grep -RIn "writeNoRsp" sources | head -100
grep -RIn "miotBleDecrypt" sources | head -100
grep -RIn "securityChipDecrypt" sources | head -100
grep -RIn "battery\|voltage\|bms\|cell\|capacity\|current" sources | head -100
```

Si `jadx` CLI n’est pas disponible, utiliser `jadx-gui` et ses recherches globales.

---

## Recherche dans les APK sans décompiler

Lister les fichiers :

```bash
unzip -l ~/xiaomi_apk/base.apk | grep -iE "bundle|hbc|js|hermes|plugin|rn|scooter|5pro"
unzip -l ~/xiaomi_apk/split_config.arm64_v8a.apk | grep -iE "bundle|hbc|js|hermes|plugin|rn|scooter|5pro"
```

Chercher les strings dans les APK :

```bash
strings -a ~/xiaomi_apk/base.apk | grep -iE "registerBlockListener|miotBleDecrypt|securityChipDecrypt|battery|voltage|bms|scooter" | head -100
strings -a ~/xiaomi_apk/split_config.arm64_v8a.apk | grep -iE "registerBlockListener|miotBleDecrypt|securityChipDecrypt|battery|voltage|bms|scooter" | head -100
```

---

## Piste Hermes / React Native

Les libs suivantes indiquent un environnement React Native / Hermes :

```txt
libhermes.so
libreactnativejni.so
librnsdk.so
libyrnbridge.so
libyrnv8executor.so
```

Il faut donc chercher :

```txt
*.bundle
*.jsbundle
*.hbc
Hermes bytecode
plugin package
rn package
```

Si un bundle Hermes est trouvé, il faudra ensuite essayer :

- `hbctool` ;
- `hermes-dec` ;
- `strings` ;
- recherche de noms de fonctions ;
- extraction approximative des constantes.

Même sans décompilation parfaite, les strings peuvent révéler :

- noms de méthodes ;
- IDs MIOT ;
- commandes batterie ;
- labels UI ;
- structures JSON ;
- unités `V`, `A`, `mAh`, `°C`.

---

## Hypothèse sur le format des commandes

Les paquets capturés vers `0x0021` après ouverture de l’onglet batterie ressemblent à :

```txt
01000400...
01000500...
01000600...
01000700...
...
01001000...
```

Le préfixe peut être interprété comme :

```txt
01 00 XX 00 ...
```

Hypothèse :

```txt
01 00 = type / direction / frame
XX 00 = compteur little-endian
reste = payload chiffré ou encapsulé
```

Côté réponse :

```txt
00000200 YY00 ...
```

Hypothèse :

```txt
00 00 02 00 = type réponse / notification data
YY 00       = compteur
reste       = payload chiffré ou encapsulé
```

Les paquets ACK :

```txt
00000300
00000100
00000101
```

semblent être des contrôles de flux.

---

## Ce qu’il ne faut toujours pas faire

Ne pas rejouer les gros paquets `0x0021` hors contexte.

Raisons :

- session active nécessaire ;
- compteur dynamique ;
- handshake préalable ;
- chiffrement probable ;
- risque d’envoyer une commande invalide ;
- on ne sait pas encore distinguer lecture / écriture / action.

Pour l’instant, seules les commandes suivantes sont considérées comme sûres :

```txt
0000001c write 00
0000001c write 01
0000001c write 03
```

---

## Stratégie pour arriver au script Python final

Le futur script Python devra probablement reproduire ces étapes :

```txt
1. scan BLE
2. connexion à E8:4A:54:53:1D:E9
3. request MTU proche de 247 si possible
4. enable notify sur 0000001a, 0000001b, 00000016, 00000010, 0000001c
5. handshake / auth
6. génération des paquets de requête
7. envoi sur 0000001a ou 00000016
8. réception sur 0000001b ou 00000016
9. ACK sur 0000001b / 0000001a selon le flux
10. déchiffrement / décapsulation
11. parsing batterie
12. affichage voltage / courant / cellules / température
```

Le script Python actuel ne couvre que :

```txt
1. connexion
2. lecture firmware
3. commandes simples sur 0000001c
4. notifications simples
```

Il faudra donc découvrir la partie session/chiffrement/parsing.

---

## Script Python actuel : rôle réel

Le script Python direct ne doit pas être considéré comme un échec.

Il sert à valider :

- que `bleak` fonctionne ;
- que le PC peut parler directement à la trott ;
- que les UUID sont corrects ;
- que les commandes simples fonctionnent ;
- que le voltage n’est pas disponible en clair.

Il ferme donc une hypothèse :

```txt
Le voltage n’est pas juste une caractéristique BLE lisible directement.
```

---

## Commande de rollback Xiaomi Home normal

Après les essais Frida/Patch, il faut remettre Xiaomi Home original sur l’émulateur :

```bash
adb uninstall com.xiaomi.smarthome

adb install-multiple --no-incremental \
~/xiaomi_apk/base.apk \
~/xiaomi_apk/split_config.arm64_v8a.apk
```

Si l’installation réussit :

```txt
Success
```

Ensuite relancer l’app normalement.

---

## Nettoyage des dossiers de tests Frida

Dossiers temporaires pouvant être supprimés :

```bash
rm -rf ~/xiaomi_gadget_patch
rm -rf ~/xiaomi_native_gadget_patch
rm -rf ~/avd_dump
rm -rf ~/xiaomi_private_dump
rm -f ~/apktool_build.log
rm -f ~/arm64_avd_bootlog.txt
rm -f ~/xiaomi_frida_ble.log
rm -f ~/xiaomi_frida_ble_clean.log
```

À garder :

```txt
~/xiaomi_apk
~/.venvs/bumble
captures BLE utiles
captures logcat utiles
scripts Python BLE
```

Le venv Frida peut être gardé, mais il n’est plus prioritaire :

```txt
~/.venvs/frida
```

---

## État des méthodes testées

| Méthode | Résultat | Statut |
|---|---|---|
| BLE direct commandes simples | fonctionne | à garder |
| BLE direct voltage naïf | pas de voltage | hypothèse fermée |
| Bumble + Xiaomi Home | fonctionne | très utile |
| logcat large | trop de bruit | secondaire |
| logcat PID | confirme GATT, pas plaintext | utile |
| JADX Java principal | très utile | priorité actuelle |
| Frida server | attach impossible sans root | pause |
| AVD root x86_64 | root OK, APK incompatible | inutilisable pour Xiaomi Home |
| AVD ARM64 | impossible sur host x86_64 | abandonné |
| dump userdata AVD | montage échoué | pause |
| apktool + Frida Gadget | enfer ressources XML | abandonné |
| patchelf + Frida Gadget | install OK mais crash app | pause |
| recherche plugin RN/Hermes | pas encore terminée | priorité actuelle |

---

## Nouvelle feuille de route

### Phase A — Revenir à un environnement stable

1. Supprimer l’app patchée si présente.
2. Réinstaller Xiaomi Home original.
3. Vérifier que l’app se lance.
4. Vérifier que la trott est visible.
5. Garder Bumble fonctionnel.

### Phase B — Reprendre JADX

1. Ouvrir `base.apk` dans JADX.
2. Ouvrir aussi le split si possible.
3. Rechercher `RnBluetoothProviderImpl`.
4. Rechercher `MIOTBluetoothModuleCore`.
5. Rechercher `registerBlockListener`.
6. Rechercher `miotBleDecrypt`.
7. Rechercher les usages de `OooOo0O(String)`.
8. Identifier quelles méthodes reçoivent ou renvoient les hex strings.

### Phase C — Trouver le plugin scooter

Chercher :

```txt
scooter
vehicle
dreame
5pro
battery
bms
voltage
capacity
current
cell
```

Et aussi :

```txt
OLD PLUGIN INFO
plugin info
PluginPackage
rn package
bundle
hbc
jsbundle
```

### Phase D — Corrélation avec captures BLE

Une fois une fonction candidate trouvée, comparer avec les paquets déjà capturés :

```txt
01000400
01000500
01000600
...
01001000
```

Si une fonction construit des hex strings ressemblant à ces préfixes, c’est probablement la bonne.

### Phase E — Script Python progressif

Le script Python final doit être construit par étapes :

1. scanner ;
2. connecter ;
3. activer notify ;
4. reproduire handshake ;
5. générer paquets ;
6. envoyer requête batterie ;
7. recevoir réponse ;
8. parser.

Pas tout coder d’un coup.

---

## Ce qu’il faut envoyer à l’analyse quand trouvé dans JADX

Quand un résultat intéressant est trouvé dans JADX, envoyer uniquement les morceaux autour de :

```java
registerBlockListener(...)
writeNoRsp(...)
write(...)
miotBleDecrypt(...)
securityChipDecrypt(...)
callback.invoke(...)
OooO0O0(...)
OooOo0O(...)
```

Et surtout les endroits où on voit :

```java
String hex
byte[]
Callback
ReadableMap
ReadableArray
Promise
JSONObject
JSONArray
battery
voltage
bms
```

---

## Résumé court README #2

Depuis le premier README, les avancées principales sont :

1. Identification de la pile BLE Java Xiaomi : `rk0 -> tk0 -> qu0/ru0 -> BluetoothGatt`.
2. Confirmation que les payloads BLE sont déjà construits avant `rk0/tk0`.
3. Découverte du bridge React Native `RnBluetoothProviderImpl`.
4. Découverte de `registerBlockListener` comme voie probable de réception des données BLE vers le plugin.
5. Découverte de `i8b`, qui reçoit `byte[]` et renvoie une string au callback RN.
6. Confirmation de la conversion `byte[] <-> hex string`.
7. Hypothèse forte : la logique batterie est dans le plugin React Native / Hermes, pas dans le Java principal.
8. Test Python direct : pas de voltage en clair.
9. Frida essayé mais bloqué par l’environnement, mis en pause.
10. Nouvelle priorité : reprendre JADX et trouver le plugin scooter / bundle RN / logique batterie.

---

## Conclusion actuelle

Le projet n’est pas bloqué côté BLE.

Le projet est maintenant dans une phase de reverse applicatif.

La meilleure piste actuelle est :

```txt
JADX approfondi
↓
bridge React Native
↓
plugin scooter / Hermes
↓
requêtes batterie
↓
Python bleak
```

Frida reste une option future, mais seulement si un environnement plus adapté est disponible :

- appareil Android rooté ARM64 ;
- émulateur ARM64 sur machine ARM ;
- APK patchable sans crash ;
- ou autre méthode d’instrumentation plus stable.

Pour l’instant, la suite logique est de continuer l’analyse JADX, car c’est la méthode qui a produit les informations les plus solides jusqu’à présent.
