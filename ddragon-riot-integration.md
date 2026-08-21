# Documentación: Integración de Datos de Objetos de League of Legends (Riot Games API)

## 📋 Descripción

Esta documentación describe la implementación de un módulo Python para obtener y mapear información de objetos (items) de League of Legends usando la API **Data Dragon** de Riot Games. El módulo permite convertir los `itemID` numéricos obtenidos de la API de partidas (match-v5) en información legible como nombres, descripciones, estadísticas e imágenes de los objetos.

## 🎯 Objetivos

- Descargar y cachear localmente los datos estáticos de objetos desde Data Dragon
- Mapear los IDs de objetos (ej. `3866`, `2524`) a nombres y propiedades legibles
- Proporcionar una interfaz simple para consultar objetos por ID
- Soportar múltiples versiones de patch y localizaciones (idiomas)

## 📚 Referencias

- **Data Dragon API**: [https://developer.riotgames.com/docs/lol#data-dragon](https://developer.riotgames.com/docs/lol#data-dragon) [developer.riotgames](https://developer.riotgames.com/docs/lol)
- **Endpoint de objetos**: `https://ddragon.leagueoflegends.com/cdn/{version}/data/{locale}/item.json` [developer.riotgames](https://developer.riotgames.com/docs/lol)
- **CDN de imágenes**: `https://ddragon.leagueoflegends.com/cdn/{version}/img/item/{itemID}.png` [developer.riotgames](https://developer.riotgames.com/docs/lol)
- **Lista de versiones**: `https://ddragon.leagueoflegends.com/api/versions.json` 

## 🏗️ Arquitectura

### Endpoints Data Dragon

| Recurso | URL | Descripción |
|---------|-----|-------------|
| Versiones | `https://ddragon.leagueoflegends.com/api/versions.json` | Lista de versiones de patch disponibles  |
| Objetos (JSON) | `https://ddragon.leagueoflegends.com/cdn/{version}/data/{locale}/item.json` | Información completa de todos los objetos  [mintlify](https://www.mintlify.com/Jordavid/Craffter_lol/api-reference/models/item) |
| Imagen objeto | `https://ddragon.leagueoflegends.com/cdn/{version}/img/item/{itemID}.png` | Imagen del objeto específico  [mintlify](https://www.mintlify.com/Jordavid/Craffter_lol/api-reference/models/item) |

### Estructura del JSON (item.json)

```json
{
  "type": "item",
  "version": "14.1.1",
  "data": {
    "3866": {
      "name": "Guantes de Bruja",
      "description": "<mainText>...</mainText>",
      "plaintext": "Botas de hechicero",
      "gold": {
        "total": 1100,
        "base": 700,
        "sell": 770,
        "purchasable": true
      },
      "from": ["1001", "1052"],
      "into": ["3020", "3089"],
      "stats": {
        "FlatMagicDamageMod": 18,
        "PercentMovementSpeedMod": 0.045
      },
      "tags": ["Boots", "MagicDamage"],
      "image": {
        "full": "3866.png",
        "sprite": "item0.png",
        "group": "item",
        "x": 0,
        "y": 0,
        "w": 48,
        "h": 48
      }
    }
  }
}
```



### Campos principales del objeto

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `name` | String | Nombre del objeto (ej. "Guantes de Bruja")  [mintlify](https://www.mintlify.com/Jordavid/Craffter_lol/api-reference/models/item) |
| `description` | String | Descripción HTML con efectos y pasivas  [mintlify](https://www.mintlify.com/Jordavid/Craffter_lol/api-reference/models/item) |
| `plaintext` | String | Descripción corta en texto plano  [developer.riotgames](https://developer.riotgames.com/docs/lol) |
| `gold.total` | Integer | Costo total en oro  [mintlify](https://www.mintlify.com/Jordavid/Craffter_lol/api-reference/models/item) |
| `from` | List[String] | IDs de objetos componentes para craftar  [mintlify](https://www.mintlify.com/Jordavid/Craffter_lol/api-reference/models/item) |
| `into` | List[String] | IDs de objetos que usan este como componente  [mintlify](https://www.mintlify.com/Jordavid/Craffter_lol/api-reference/models/item) |
| `stats` | Map[String, Object] | Estadísticas que otorga el objeto  [mintlify](https://www.mintlify.com/Jordavid/Craffter_lol/api-reference/models/item) |
| `tags` | List[String] | Categorías del objeto (ej. "Boots", "Damage")  [mintlify](https://www.mintlify.com/Jordavid/Craffter_lol/api-reference/models/item) |
| `image.full` | String | Nombre del archivo de imagen (ej. "3866.png")  [mintlify](https://www.mintlify.com/Jordavid/Craffter_lol/api-reference/models/item) |

## 📁 Estructura del Proyecto

```
tu_proyecto/
├── riot_items/
│   ├── __init__.py
│   ├── data_dragon.py          # Cliente Data Dragon
│   ├── item_cache.py           # Gestión de caché local
│   └── models.py               # Modelos de datos (Item, etc.)
├── tests/
│   └── test_riot_items.py
├── requirements.txt
└── README.md
```

## 🔧 Implementación

### 1. Dependencias

Crea un archivo `requirements.txt`:

```txt
requests>=2.31.0
pydantic>=2.0.0
```

### 2. Modelos de Datos (`models.py`)

```python
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class ItemImage(BaseModel):
    full: str
    sprite: str
    group: str
    x: int
    y: int
    w: int
    h: int


class ItemGold(BaseModel):
    total: int
    base: int
    sell: int
    purchasable: bool


class Item(BaseModel):
    name: str
    description: str
    plaintext: Optional[str] = None
    gold: ItemGold
    from_: List[str] = Field(default_factory=list, alias="from")
    into: List[str] = Field(default_factory=list, alias="into")
    stats: Dict[str, float] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    image: ItemImage
    
    @property
    def is_craftable(self) -> bool:
        return len(self.from_) > 0
    
    @property
    def component_count(self) -> int:
        return len(self.from_)
    
    def get_image_url(self, version: str) -> str:
        return f"https://ddragon.leagueoflegends.com/cdn/{version}/img/item/{self.image.full}"


class ItemData(BaseModel):
    type: str
    version: str
    data: Dict[str, Item]
```

### 3. Cliente Data Dragon (`data_dragon.py`)

```python
import requests
from typing import List, Optional, Dict
from .models import ItemData, Item


class DataDragonClient:
    BASE_URL = "https://ddragon.leagueoflegends.com/cdn"
    VERSIONS_URL = "https://ddragon.leagueoflegends.com/api/versions.json"
    
    def __init__(self, locale: str = "es_ES", version: Optional[str] = None):
        self.locale = locale
        self.version = version or self.get_latest_version()
        self._items_cache: Optional[Dict[str, Item]] = None
    
    def get_latest_version(self) -> str:
        response = requests.get(self.VERSIONS_URL)
        response.raise_for_status()
        versions: List[str] = response.json()
        return versions[0]
    
    def get_items_url(self) -> str:
        return f"{self.BASE_URL}/{self.version}/data/{self.locale}/item.json"
    
    def get_item_image_url(self, item_id: str) -> str:
        return f"{self.BASE_URL}/{self.version}/img/item/{item_id}.png"
    
    def fetch_items(self) -> Dict[str, Item]:
        if self._items_cache is not None:
            return self._items_cache
        
        url = self.get_items_url()
        response = requests.get(url)
        response.raise_for_status()
        
        data = ItemData(**response.json())
        self._items_cache = data.data
        return self._items_cache
    
    def get_item_by_id(self, item_id: int) -> Optional[Item]:
        items = self.fetch_items()
        return items.get(str(item_id))
    
    def get_items_by_ids(self, item_ids: List[int]) -> Dict[int, Optional[Item]]:
        items = self.fetch_items()
        return {
            item_id: items.get(str(item_id))
            for item_id in item_ids
        }
    
    def refresh_cache(self):
        self._items_cache = None
        self.fetch_items()
```

### 4. Gestión de Caché Local (`item_cache.py`)

```python
import json
import os
from pathlib import Path
from typing import Dict, Optional
from .models import Item


class ItemCache:
    CACHE_DIR = Path("cache/riot_items")
    
    def __init__(self, version: str, locale: str):
        self.version = version
        self.locale = locale
        self.cache_file = self.CACHE_DIR / f"{version}_{locale}.json"
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    def load(self) -> Optional[Dict[str, Item]]:
        if not self.cache_file.exists():
            return None
        
        with open(self.cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return {
            item_id: Item(**item_data)
            for item_id, item_data in data.items()
        }
    
    def save(self, items: Dict[str, Item]):
        data = {
            item_id: item.model_dump(by_alias=True)
            for item_id, item in items.items()
        }
        
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def exists(self) -> bool:
        return self.cache_file.exists()
    
    def clear(self):
        if self.cache_file.exists():
            self.cache_file.unlink()
```

### 5. Módulo Principal (`__init__.py`)

```python
from .data_dragon import DataDragonClient
from .item_cache import ItemCache
from .models import Item, ItemGold, ItemImage

__all__ = [
    "DataDragonClient",
    "ItemCache",
    "Item",
    "ItemGold",
    "ItemImage",
]
```

## 🚀 Uso

### Ejemplo Básico

```python
from riot_items import DataDragonClient

# Inicializar cliente (por defecto usa la última versión y español)
client = DataDragonClient(locale="es_ES")

# Obtener un objeto por ID
item = client.get_item_by_id(3866)
if item:
    print(f"Nombre: {item.name}")
    print(f"Costo: {item.gold.total} oro")
    print(f"Imagen: {item.get_image_url(client.version)}")

# Mapear múltiples IDs de una partida
player_items = [3866, 2524, 3009, 3067, 1028, 0]
items_data = client.get_items_by_ids([i for i in player_items if i != 0])

for item_id, item in items_data.items():
    if item:
        print(f"{item_id}: {item.name} - {item.plaintext}")
    else:
        print(f"{item_id}: Desconocido")
```

### Ejemplo con Caché

```python
from riot_items import DataDragonClient, ItemCache

version = "14.1.1"
locale = "es_ES"
cache = ItemCache(version, locale)

# Intentar cargar desde caché
cached_items = cache.load()

if cached_items:
    print("✅ Datos cargados desde caché local")
    client = DataDragonClient(locale=locale, version=version)
    client._items_cache = cached_items
else:
    print("🔄 Descargando datos desde Data Dragon...")
    client = DataDragonClient(locale=locale, version=version)
    items = client.fetch_items()
    cache.save(items)
    print("✅ Datos guardados en caché")

# Usar cliente (ya tiene caché)
item = client.get_item_by_id(3866)
print(f"{item.name}: {item.gold.total} oro")
```

### Ejemplo con Match Data

```python
from riot_items import DataDragonClient

client = DataDragonClient()

# Simulación de datos de partida (match-v5)
participant = {
    "item0": 3866,
    "item1": 2524,
    "item2": 3009,
    "item3": 3067,
    "item4": 1028,
    "item5": 0,
    "item6": 3364,  # Trinket
}

# Extraer IDs
item_ids = [participant[f"item{i}"] for i in range(7)]

# Mapear a nombres
items_data = client.get_items_by_ids([i for i in item_ids if i != 0])

print("Objetos del jugador:")
for i in range(7):
    item_id = participant[f"item{i}"]
    if item_id == 0:
        print(f"  Slot {i}: Vacío")
    else:
        item = items_data.get(item_id)
        if item:
            print(f"  Slot {i}: {item.name} ({item.gold.total} oro)")
        else:
            print(f"  Slot {i}: ID {item_id} (desconocido)")
```

## 🧪 Testing

```python
# tests/test_riot_items.py
import pytest
from riot_items import DataDragonClient, ItemCache


def test_fetch_items():
    client = DataDragonClient(locale="es_ES")
    items = client.fetch_items()
    assert len(items) > 0
    assert "3866" in items


def test_get_item_by_id():
    client = DataDragonClient(locale="es_ES")
    item = client.get_item_by_id(3866)
    assert item is not None
    assert item.name is not None
    assert item.gold.total > 0


def test_cache_functionality():
    version = "14.1.1"
    locale = "es_ES"
    cache = ItemCache(version, locale)
    
    # Limpiar caché si existe
    if cache.exists():
        cache.clear()
    
    # Cargar debe retornar None
    assert cache.load() is None
    
    # Crear cliente y guardar
    client = DataDragonClient(version=version, locale=locale)
    items = client.fetch_items()
    cache.save(items)
    
    # Cargar debe retornar datos
    cached = cache.load()
    assert cached is not None
    assert len(cached) > 0
```

## 📝 Consideraciones

### 1. Versiones de Patch

- Los datos de objetos cambian con cada patch. Asegúrate de usar la versión correcta del patch de tu partida. [developer.riotgames](https://developer.riotgames.com/docs/lol)
- Obtén la lista de versiones con: `https://ddragon.leagueoflegends.com/api/versions.json` 

### 2. Caché

- **Recomendación**: Descarga `item.json` una vez por patch y úsalo localmente. No necesitas llamar a Data Dragon en cada request. 
- Implementa un sistema de caché con expiración (ej. 24h o cuando cambie el patch).

### 3. Localización

- Data Dragon soporta 28+ idiomas. 
- Códigos comunes: `es_ES`, `en_US`, `en_GB`, `fr_FR`, `de_DE`, `pt_BR`

### 4. IDs Especiales

- `0`: Slot vacío (el jugador no tiene objeto en esa posición) 
- `3364`: Trinket (objeto especial de ward)

### 5. Rate Limiting

- Data Dragon no requiere API key y tiene límites generosos.
- No necesitas autenticación para acceder a datos estáticos. [developer.riotgames](https://developer.riotgames.com/docs/lol)

## 🔗 Recursos Adicionales

- **Documentación oficial**: [https://developer.riotgames.com/docs/lol](https://developer.riotgames.com/docs/lol) [developer.riotgames](https://developer.riotgames.com/)
- **Lista de item IDs**: [https://darkintaqt.com/blog/lol-items/](https://darkintaqt.com/blog/lol-items/) 
- **Repositorio con diccionarios**: [https://github.com/ntrllog/LoL-Data](https://github.com/ntrllog/LoL-Data) 
- **Wrapper Python (RiotWatcher)**: [https://github.com/pseudonym117/Riot-Watcher](https://github.com/pseudonym117/Riot-Watcher) [github](https://github.com/ntrllog/LoL-Data)
- **Framework Python (Pyot)**: [https://meraki.dev/docs/pyot/](https://meraki.dev/docs/pyot/) [github](https://github.com/pseudonym117/Riot-Watcher)

***

**Nota para el agente**: Esta documentación está diseñada para ser implementada en un proyecto Python existente. Asegúrate de:
1. Añadir las dependencias en `requirements.txt`
2. Crear el paquete `riot_items/` en la raíz del proyecto
3. Usar el caché local para evitar requests innecesarios    