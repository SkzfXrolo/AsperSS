# 🚀 Cómo Iniciar la API

## Opción 1: Script Automático (Recomendado)

1. **Ejecuta el script:**
   ```
   INICIAR_API.bat
   ```

2. **La API se iniciará automáticamente en:**
   - URL: `http://localhost:5000`
   - La API Key se mostrará en la consola

## Opción 2: Manualmente

### Desde la línea de comandos:

1. **Abre una terminal/PowerShell**

2. **Navega a la carpeta del proyecto:**
   ```bash
   cd "C:\Users\robin\Desktop\Tareas\Aplicación de SS"
   ```

3. **Inicia la API:**
   ```bash
   python source\api_server.py
   ```

### O desde Python directamente:

```bash
cd source
python api_server.py
```

## Verificar que la API está funcionando

1. **Abre tu navegador** y ve a:
   ```
   http://localhost:5000/api/statistics
   ```

2. **O usa curl:**
   ```bash
   curl http://localhost:5000/api/statistics
   ```

## Configuración

### Puerto
Por defecto, la API corre en el puerto **5000**. 

Para cambiarlo, edita `source/api_server.py` línea 2108:
```python
app.run(host='0.0.0.0', port=5000, ...)
```

### API Key
La API genera una clave automáticamente. Se muestra al iniciar:
```
🔑 API Key: [clave generada]
```

Para usar una clave fija, configura la variable de entorno:
```bash
set API_SECRET_KEY=tu-clave-secreta
```

## Iniciar API + Web App juntos

Si quieres iniciar todo el sistema (API + Web App):

```
INICIAR_SISTEMA_COMPLETO.bat
```

Esto iniciará:
- API REST en `http://localhost:5000`
- Web App en `http://localhost:8080`

## Problemas Comunes

### "Python no encontrado"
- Instala Python 3.8 o superior
- Asegúrate de agregar Python al PATH durante la instalación

### "No se puede conectar a la API"
- Verifica que la API esté corriendo
- Verifica que el puerto 5000 no esté en uso por otro programa
- Revisa el firewall de Windows

### "Error al inicializar base de datos"
- Verifica que tengas permisos de escritura en la carpeta del proyecto
- La base de datos `scanner_db.sqlite` se creará automáticamente

## Detener la API

Presiona `Ctrl+C` en la ventana donde está corriendo la API.

