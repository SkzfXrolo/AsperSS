# 🌐 Cómo Iniciar la Aplicación Web - ASPERS Projects

## 📋 Requisitos Previos

1. **Python instalado** (3.8 o superior)
2. **Dependencias instaladas**:
   ```bash
   pip install flask flask-cors requests
   ```

## 🚀 Método 1: Script Automático (Recomendado)

### **Windows:**
1. Ejecuta `INICIAR_SISTEMA_COMPLETO.bat` desde la raíz del proyecto
2. Se abrirán 2 ventanas:
   - **API REST** (puerto 5000)
   - **Aplicación Web** (puerto 8080)
3. Abre tu navegador en: **http://localhost:8080**

---

## 🚀 Método 2: Manual

### **Paso 1: Iniciar API REST**

Abre una terminal y ejecuta:

```bash
cd "C:\Users\robin\Desktop\Tareas\Aplicación de SS"
python source/api_server.py
```

Deberías ver:
```
🚀 Iniciando API REST de Aspers Projects Security Scanner...
✅ Base de datos inicializada
📡 API disponible en http://localhost:5000
```

**Mantén esta ventana abierta.**

---

### **Paso 2: Iniciar Aplicación Web**

Abre **otra terminal** (nueva ventana) y ejecuta:

```bash
cd "C:\Users\robin\Desktop\Tareas\Aplicación de SS"
python web_app/app.py
```

Deberías ver:
```
🌐 Iniciando aplicación web de ASPERS Projects...
📡 Conectado a API: http://localhost:5000
🌐 * Running on http://0.0.0.0:8080
```

**Mantén esta ventana también abierta.**

---

### **Paso 3: Abrir en el Navegador**

Abre tu navegador y ve a:

- **Página Principal**: http://localhost:8080
- **Panel Staff**: http://localhost:8080/panel

---

## 📍 URLs Importantes

| URL | Descripción |
|-----|-------------|
| http://localhost:8080 | Página principal (About ASPERS) |
| http://localhost:8080/panel | Panel del Staff |
| http://localhost:5000 | API REST (solo JSON) |

---

## 🔧 Solución de Problemas

### **Error: "No se pudo conectar a la API"**

**Causa**: La API no está corriendo.

**Solución**:
1. Verifica que `api_server.py` esté corriendo en el puerto 5000
2. Abre http://localhost:5000 en tu navegador
3. Deberías ver un error JSON (eso significa que la API está funcionando)

---

### **Error: "ModuleNotFoundError: No module named 'flask'"**

**Causa**: Flask no está instalado.

**Solución**:
```bash
pip install flask flask-cors requests
```

---

### **Error: "Address already in use"**

**Causa**: El puerto 5000 o 8080 ya está en uso.

**Solución**:
1. Cierra otras aplicaciones que usen esos puertos
2. O cambia los puertos en los archivos:
   - `source/api_server.py` (línea 642): `app.run(host='0.0.0.0', port=5000)`
   - `web_app/app.py` (línea 205): `app.run(host='0.0.0.0', port=8080)`

---

### **La página carga pero no muestra datos**

**Causa**: La API no está respondiendo correctamente.

**Solución**:
1. Abre la consola del navegador (F12)
2. Revisa los errores en la pestaña "Console"
3. Verifica que la API esté corriendo en http://localhost:5000

---

## ✅ Verificación

Para verificar que todo funciona:

1. **API REST**: Abre http://localhost:5000/api/statistics
   - Deberías ver un JSON con estadísticas

2. **Web App**: Abre http://localhost:8080
   - Deberías ver la página principal de ASPERS Projects

3. **Panel Staff**: Abre http://localhost:8080/panel
   - Deberías ver el panel con Dashboard, Tokens, Resultados, etc.

---

## 🎯 Uso Rápido

1. **Inicia el sistema**: Ejecuta `INICIAR_SISTEMA_COMPLETO.bat`
2. **Abre el panel**: http://localhost:8080/panel
3. **Ve a "Resultados"**: Haz clic en "Ver Detalles" de un escaneo
4. **Marca resultados**: Usa los botones "Marcar como Hack" o "Marcar como Legítimo"
5. **Ve a "Aprendizaje IA"**: Observa los patrones aprendidos
6. **Actualiza el modelo**: Haz clic en "Actualizar Modelo de IA"

---

## 📝 Notas

- **Mantén ambas ventanas abiertas** mientras uses la aplicación
- **La API debe iniciarse primero** antes que la Web App
- **Los datos se guardan en** `scanner_db.sqlite` (se crea automáticamente)
- **Para detener**: Cierra las ventanas de la API y Web App

---

## 🔒 Seguridad

En producción, deberías:
- Configurar una API Key real en `web_app/app.py`
- Usar HTTPS
- Configurar autenticación para el panel staff
- Cambiar los puertos si es necesario

---

¡Listo! Ya puedes usar el sistema completo de ASPERS Projects. 🚀

