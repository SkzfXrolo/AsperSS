# 🤖 Sistema de Aprendizaje Progresivo - ASPERS Projects

## 📋 Resumen

El sistema de **Aprendizaje Progresivo** permite que la IA mejore continuamente mediante el feedback del staff. Cuando el staff marca un resultado como "hack" o "legítimo", el sistema:

1. **Extrae características** del archivo marcado
2. **Aprende patrones** nuevos automáticamente
3. **Actualiza el modelo de IA** con los nuevos conocimientos
4. **Regenera el ejecutable** con las mejoras incorporadas

**Resultado**: Un sistema que se vuelve **INBYPASSEABLE** con el tiempo, ya que aprende de cada hack confirmado.

---

## 🔄 Flujo Completo del Sistema

```
┌─────────────────────────────────────────────────────────────┐
│                    FLUJO DE APRENDIZAJE                      │
└─────────────────────────────────────────────────────────────┘

1. ESCANEO INICIAL
   └─> Cliente ejecuta escaneo
   └─> Resultados enviados a API
   └─> Almacenados en BD

2. REVISIÓN DEL STAFF
   └─> Staff revisa resultados en panel web
   └─> Marca resultados como "hack" o "legítimo"
   └─> Feedback enviado a API (/api/feedback)

3. EXTRACCIÓN DE CARACTERÍSTICAS
   └─> Sistema extrae patrones del nombre/ruta
   └─> Guarda hash SHA256 del archivo
   └─> Identifica características (ofuscación, ubicación, etc.)
   └─> Almacena en tablas: learned_patterns, learned_hashes

4. ACTUALIZACIÓN DEL MODELO
   └─> Cuando hay 10+ hacks confirmados
   └─> Staff ejecuta "Actualizar Modelo" (/api/update-model)
   └─> Sistema genera nueva versión del modelo
   └─> Actualiza patrones en ai_analyzer.py
   └─> Actualiza hashes en main.py

5. REGENERACIÓN DEL EJECUTABLE
   └─> Sistema ejecuta COMPILAR_FINAL.bat
   └─> Nueva versión compilada con patrones aprendidos
   └─> Versión disponible para descarga

6. PRÓXIMOS ESCANEOS
   └─> Nuevos clientes usan versión actualizada
   └─> Detectan hacks que antes no detectaban
   └─> Sistema se vuelve más efectivo
```

---

## 🗄️ Estructura de Base de Datos

### **Tabla: `staff_feedback`**
Almacena el feedback del staff sobre cada resultado.

```sql
CREATE TABLE staff_feedback (
    id INTEGER PRIMARY KEY,
    result_id INTEGER,              -- ID del resultado escaneado
    scan_id INTEGER,                 -- ID del escaneo
    staff_verification TEXT,         -- 'hack' o 'legitimate'
    staff_notes TEXT,                -- Notas del staff
    verified_by TEXT,                -- Usuario que verificó
    verified_at TIMESTAMP,           -- Fecha de verificación
    file_hash TEXT,                  -- Hash SHA256 del archivo
    issue_name TEXT,                 -- Nombre del archivo
    issue_path TEXT,                 -- Ruta del archivo
    extracted_patterns TEXT,          -- JSON: patrones extraídos
    extracted_features TEXT          -- JSON: características extraídas
)
```

### **Tabla: `learned_patterns`**
Almacena patrones aprendidos automáticamente.

```sql
CREATE TABLE learned_patterns (
    id INTEGER PRIMARY KEY,
    pattern_type TEXT,               -- 'keyword', 'path', etc.
    pattern_value TEXT,               -- Valor del patrón (ej: 'vape')
    pattern_category TEXT,            -- 'high_risk', 'medium_risk', 'low_risk'
    confidence REAL,                  -- Confianza del patrón (0-1)
    source_feedback_id INTEGER,      -- ID del feedback que lo generó
    learned_from_count INTEGER,      -- Cuántas veces se aprendió
    first_learned_at TIMESTAMP,      -- Primera vez que se aprendió
    last_updated_at TIMESTAMP,        -- Última actualización
    is_active BOOLEAN                -- Si está activo
)
```

### **Tabla: `learned_hashes`**
Almacena hashes SHA256 de archivos confirmados.

```sql
CREATE TABLE learned_hashes (
    id INTEGER PRIMARY KEY,
    file_hash TEXT UNIQUE,           -- Hash SHA256
    is_hack BOOLEAN,                 -- True si es hack, False si es legítimo
    confirmed_count INTEGER,          -- Cuántas veces se confirmó
    first_confirmed_at TIMESTAMP,     -- Primera confirmación
    last_confirmed_at TIMESTAMP,     -- Última confirmación
    source_feedback_id INTEGER       -- ID del feedback que lo generó
)
```

### **Tabla: `ai_model_versions`**
Control de versiones del modelo de IA.

```sql
CREATE TABLE ai_model_versions (
    id INTEGER PRIMARY KEY,
    version TEXT UNIQUE,             -- Versión del modelo (ej: '1.20241201120000')
    patterns_count INTEGER,           -- Cantidad de patrones
    hashes_count INTEGER,             -- Cantidad de hashes
    feedback_count INTEGER,           -- Cantidad de feedbacks
    created_at TIMESTAMP,            -- Fecha de creación
    is_active BOOLEAN,               -- Si es la versión activa
    model_file_path TEXT,            -- Ruta al archivo JSON del modelo
    changelog TEXT                   -- Descripción de cambios
)
```

---

## 🔌 Endpoints API

### **1. POST `/api/feedback`**
El staff marca un resultado como hack o legítimo.

**Request:**
```json
{
    "result_id": 123,
    "verification": "hack",  // o "legitimate"
    "notes": "Confirmado como vape v4",
    "verified_by": "admin_user"
}
```

**Response:**
```json
{
    "success": true,
    "feedback_id": 456,
    "extracted_patterns": ["vape", "inject"],
    "extracted_features": {
        "obfuscation": true,
        "confidence": 85,
        "location_suspicious": true
    },
    "should_update_model": true,
    "message": "Feedback guardado. Patrones extraídos y aprendidos."
}
```

**Funcionalidad:**
- Extrae patrones del nombre/ruta del archivo
- Guarda hash SHA256 si existe
- Almacena características extraídas
- Sugiere actualización si hay 10+ hacks confirmados

---

### **2. POST `/api/update-model`**
Actualiza el modelo de IA y regenera el ejecutable.

**Request:**
```json
{}
```

**Response:**
```json
{
    "success": true,
    "version": "1.20241201120000",
    "patterns_count": 45,
    "hashes_count": 120,
    "model_file": "models/ai_model_1.20241201120000.json",
    "message": "Modelo actualizado. Nueva versión generada."
}
```

**Funcionalidad:**
- Obtiene todos los patrones aprendidos
- Obtiene todos los hashes aprendidos
- Genera archivo JSON del modelo actualizado
- Inicia compilación automática del ejecutable
- Crea nueva versión en `ai_model_versions`

---

### **3. GET `/api/learned-patterns`**
Obtiene todos los patrones aprendidos.

**Response:**
```json
{
    "patterns": [
        {
            "type": "keyword",
            "value": "vape",
            "category": "high_risk",
            "confidence": 1.0,
            "learned_from_count": 15,
            "first_learned_at": "2024-12-01T10:00:00",
            "is_active": true
        }
    ],
    "total": 45
}
```

---

### **4. GET `/api/learned-hashes`**
Obtiene todos los hashes aprendidos.

**Response:**
```json
{
    "hashes": [
        {
            "hash": "abc123def456...",
            "is_hack": true,
            "confirmed_count": 5,
            "first_confirmed_at": "2024-12-01T10:00:00"
        }
    ],
    "total": 120
}
```

---

## 🧠 Cómo Funciona el Aprendizaje

### **1. Extracción de Patrones**

Cuando el staff marca un archivo como "hack", el sistema:

```python
# Extrae palabras clave del nombre y ruta
hack_keywords = re.findall(
    r'\b(vape|entropy|inject|bypass|killaura|...)\w*\b',
    name_lower + ' ' + path_lower
)

# Guarda cada patrón en learned_patterns
for pattern in extracted_patterns:
    INSERT INTO learned_patterns (
        pattern_value, pattern_category, learned_from_count
    ) VALUES (pattern, 'high_risk', count + 1)
```

**Ejemplo:**
- Archivo: `vape-injector-v4.jar` en `C:\Users\Downloads\temp`
- Patrones extraídos: `['vape', 'inject']`
- Categoría: `high_risk`

---

### **2. Almacenamiento de Hashes**

```python
# Calcula hash SHA256 del archivo
file_hash = hashlib.sha256(file_content).hexdigest()

# Guarda en learned_hashes
INSERT INTO learned_hashes (
    file_hash, is_hack, confirmed_count
) VALUES (hash, 1, 1)
```

**Ventaja**: Si el mismo archivo aparece en otro escaneo, se detecta **inmediatamente** con 100% de confianza.

---

### **3. Carga de Patrones Aprendidos**

Cuando el escáner inicia:

```python
# En ai_analyzer.py
def load_learned_patterns(self):
    cursor.execute('''
        SELECT pattern_value, pattern_category
        FROM learned_patterns
        WHERE is_active = 1
    ''')
    
    for pattern, category in cursor.fetchall():
        self.suspicious_patterns[category].append(pattern)
```

**Resultado**: El escáner detecta patrones que **nunca había visto antes**, pero que el staff confirmó como hacks.

---

### **4. Detección con Hashes Aprendidos**

```python
# En main.py
def load_known_hack_hashes(self):
    cursor.execute('''
        SELECT file_hash FROM learned_hashes WHERE is_hack = 1
    ''')
    self.known_hack_hashes = set(learned_hashes)

# En analyze_file_content()
if file_hash in self.known_hack_hashes:
    return {'is_hack': True, 'confidence': 100}
```

**Resultado**: Detección **instantánea** y **100% precisa** de hacks confirmados.

---

## 🚀 Proceso de Actualización Automática

### **Paso 1: Staff Marca Hacks**
- Staff revisa resultados en panel web
- Marca 10+ resultados como "hack"
- Sistema extrae patrones y hashes

### **Paso 2: Actualizar Modelo**
- Staff hace clic en "Actualizar Modelo" en panel web
- Sistema ejecuta `/api/update-model`
- Genera archivo JSON con todos los patrones/hashes

### **Paso 3: Regenerar Ejecutable**
- Sistema ejecuta `COMPILAR_FINAL.bat`
- Compila nueva versión con patrones aprendidos
- Nueva versión disponible para descarga

### **Paso 4: Distribución**
- Clientes descargan nueva versión
- Próximos escaneos usan patrones aprendidos
- Sistema detecta hacks que antes no detectaba

---

## 📊 Ejemplo de Evolución

### **Semana 1:**
- Patrones iniciales: 20
- Hashes conocidos: 0
- Hacks detectados: 50

### **Semana 2 (después de feedback):**
- Patrones aprendidos: +15 (total: 35)
- Hashes aprendidos: +30
- Hacks detectados: 85 (+70% mejora)

### **Semana 3 (después de más feedback):**
- Patrones aprendidos: +25 (total: 60)
- Hashes aprendidos: +50 (total: 80)
- Hacks detectados: 120 (+140% mejora desde inicio)

**Resultado**: Sistema se vuelve **exponencialmente más efectivo** con el tiempo.

---

## ✅ Ventajas del Sistema

1. **Aprendizaje Continuo**: Cada hack confirmado mejora el sistema
2. **Detección Instantánea**: Hashes aprendidos = 100% confianza
3. **Reducción de Falsos Positivos**: Hashes legítimos se whitelistean
4. **Escalabilidad**: Sistema mejora sin intervención manual
5. **Trazabilidad**: Cada patrón tiene origen (feedback_id)
6. **Versionado**: Control de versiones del modelo de IA

---

## 🔒 Seguridad

- Solo el staff puede marcar resultados (requiere API key)
- Cada feedback tiene `verified_by` para auditoría
- Patrones aprendidos tienen `learned_from_count` para confianza
- Hashes legítimos se almacenan para evitar falsos positivos

---

## 📝 Notas Importantes

1. **Umbral de Actualización**: Se sugiere actualizar cuando hay 10+ hacks confirmados
2. **Compilación Automática**: El sistema inicia la compilación en segundo plano
3. **Versiones del Modelo**: Cada actualización genera una nueva versión
4. **Compatibilidad**: El sistema carga patrones aprendidos al iniciar

---

## 🎯 Objetivo Final

**Sistema INBYPASSEABLE**: Con el tiempo, el sistema aprende de **todos** los hacks confirmados, haciendo que sea **imposible** evadirlo, ya que:

- Detecta por **hash** (100% preciso)
- Detecta por **patrones aprendidos** (nuevos hacks similares)
- Detecta por **características** (ofuscación, ubicación, etc.)
- Se **actualiza automáticamente** con cada hack confirmado

**El sistema se vuelve más inteligente con cada escaneo.**

