# 📄 Paperless-ngx Integration for OpenWebUI

<div align="center">

[![OpenWebUI](https://img.shields.io/badge/OpenWebUI-Tool-0056b3?style=for-the-badge&logo=openai)](https://github.com/open-webui/open-webui)
[![Paperless-ngx](https://img.shields.io/badge/Paperless--ngx-API-2ea44f?style=for-the-badge&logo=paperless)](https://docs.paperless-ngx.com/)
[![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)](LICENSE)

**Herramienta completa para gestionar documentos de Paperless-ngx directamente desde tu chat con IA**

</div>

---

## 🌍 Leer en otros idiomas

- [English](README.md)
- [Русский](README.ru.md)
- [Español](README.es.md) (Estás aquí)

---

## 📖 Acerca del proyecto

Esta herramienta convierte OpenWebUI en una potente interfaz para gestionar tu sistema de gestión de documentos Paperless-ngx. Todo lo que hacías a través de la interfaz web ahora está disponible mediante simples comandos en el chat.

---

## ✨ Características

### 📄 Gestión de documentos

- **Búsqueda de texto** — Búsqueda en el contenido con resaltado de coincidencias
- **Búsqueda por etiquetas** — Filtrar documentos (modos AND/OR)
- **Búsqueda exacta** — Encontrar documentos que contengan TODAS las etiquetas especificadas
- **Obtención de documentos** — Ver información completa y contenido
- **Citación automática** — Creación automática de citas con atribución de fuente

### 🏷️ Gestión de etiquetas

- **Jerarquía** — Ver estructura de árbol de etiquetas
- **Añadir** — Asignar etiquetas a documentos
- **Eliminar** — Quitar etiquetas de documentos
- **Caché** — Acceso rápido a etiquetas para mejor rendimiento

### 📝 Gestión de notas

- **Ver** — Leer todas las notas del documento
- **Añadir** — Crear nuevas notas
- **Editar** — Actualizar notas existentes
- **Eliminar** — Eliminar notas por índice

### 📋 Campos personalizados

- **Crear** — 9 tipos de datos (texto, número, fecha, selección, etc.)
- **Gestionar** — Leer, actualizar y eliminar campos
- **Rellenar** — Establecer valores para documentos

---

## 🚀 Inicio rápido

### 1. Instalación

1. Abre **OpenWebUI** → `Admin Panel` → `Tools`
2. Haz clic en **Create New Tool**
3. Pega el código de la herramienta
4. Configura los parámetros

### 2. Configuración de la herramienta

```yaml
Title: Paperless-ngx Document Search
Author: Your Name
Version: 0.1.0
License: MIT
Description: Herramienta para buscar, obtener y editar documentos en Paperless-ngx a través de la API REST
Requirements: httpx
```

### 3. Configuración de conexión

En la sección **Valves**, especifica:

| Parámetro | Descripción | Ejemplo |
|-----------|-------------|---------|
| `paperless_url` | URL de tu servidor Paperless-ngx | `http://localhost:8000` |
| `api_token` | Token API de Paperless-ngx | `your-secret-token` |
| `max_results` | Máximo de documentos en respuesta (1-20) | `5` |
| `search_limit` | Límite de búsqueda (1-100) | `50` |

### 4. Obtención del token API

1. Inicia sesión en Paperless-ngx
2. Ve a **Profile** → **API Tokens**
3. Crea un nuevo token
4. Cópialo y pégalo en la configuración

---

## 💡 Ejemplos de uso

### Búsqueda de documentos

```
🔍 Encuentra todos los contratos de febrero 2025
```

```
🏷️ Muestra documentos con etiquetas "Herencia, Tarifas"
```

```
📄 Obtén el documento 12345 con información completa
```

### Gestión de etiquetas

```
➕ Añade etiqueta "Importante" al documento 12345
```

```
🗑️ Elimina etiqueta "Borrador" del documento 12345
```

```
🌳 Muestra todas las etiquetas con jerarquía
```

### Notas y campos

```
📝 Muestra notas del documento 12345
```

```
📋 Muestra campos personalizados del documento 12345
```

### Creación de campos

```
📋 Crea campo "Responsable" de tipo string
```

```
📋 Crea campo "Estado" de tipo select con opciones: Nuevo, En progreso, Completado
```

---

## 🛠️ Todas las funciones

### 📄 Documentos

| Función | Parámetros | Descripción |
|---------|------------|-------------|
| `search_documents` | `query: str` | Búsqueda de texto con resaltado |
| `search_by_tags` | `tags: str, match_all: bool` | Búsqueda por etiquetas (AND/OR) |
| `search_by_tags_exact` | `tags: str` | Coincidencia exacta de TODAS las etiquetas |
| `get_document_by_id` | `doc_id: int` | Información completa del documento |
| `get_document_tags` | `doc_id: int` | Solo etiquetas del documento |

### 🏷️ Etiquetas

| Función | Parámetros | Descripción |
|---------|------------|-------------|
| `list_tags` | `-` | Lista de todas las etiquetas |
| `list_tags_hierarchical` | `-` | Árbol jerárquico de etiquetas |
| `get_tag_hierarchy` | `tag_name: str` | Jerarquía de una etiqueta específica |
| `get_tags_with_parents` | `doc_id: int` | Etiquetas del documento con jerarquía |
| `add_tag_to_document` | `doc_id: int, tag_name: str` | Añadir etiqueta al documento |
| `remove_tag_from_document` | `doc_id: int, tag_name: str` | Eliminar etiqueta del documento |
| `clear_tag_cache` | `-` | Actualizar caché de etiquetas |

### 📝 Notas

| Función | Parámetros | Descripción |
|---------|------------|-------------|
| `get_document_notes` | `doc_id: int` | Lista de notas |
| `add_document_note` | `doc_id: int, note: str` | Añadir una nota |
| `update_document_note` | `doc_id: int, note_index: int, new_note: str` | Actualizar una nota |
| `delete_document_note` | `doc_id: int, note_index: int` | Eliminar una nota |

### 📋 Campos personalizados

| Función | Parámetros | Descripción |
|---------|------------|-------------|
| `list_custom_fields` | `-` | Lista de todos los campos |
| `get_document_custom_fields` | `doc_id: int` | Campos del documento |
| `set_document_custom_field` | `doc_id: int, field_name: str, value: str` | Establecer valor de campo |
| `remove_document_custom_field` | `doc_id: int, field_name: str` | Eliminar valor de campo |
| `create_custom_field` | `name, field_type, required, options` | Crear un campo |
| `delete_custom_field` | `field_id_or_name: str` | Eliminar un campo |
| `update_custom_field` | `field_id_or_name, new_name, required, options` | Actualizar un campo |

### 🐛 Diagnóstico

| Función | Parámetros | Descripción |
|---------|------------|-------------|
| `debug_document_tags` | `doc_id: int` | Diagnóstico de etiquetas del documento |

---

## 📋 Tipos de campos personalizados

| Tipo | Descripción | Ejemplo de valor |
|------|-------------|------------------|
| `string` | Texto | `"Juan Pérez"` |
| `integer` | Número entero | `42` |
| `float` | Número decimal | `3.14` |
| `boolean` | Sí/No | `true` |
| `date` | Fecha | `2025-03-15` |
| `datetime` | Fecha y hora | `2025-03-15T14:30:00` |
| `monetary` | Valor monetario | `1000.50` |
| `documentlink` | Enlace a documento | `12345` |
| `select` | Selección de lista | `"Nuevo"` |

---

## ⚙️ Configuración del entorno

### Docker

Si Paperless-ngx se ejecuta en Docker:

```yaml
# Para Windows/Mac
paperless_url: http://host.docker.internal:8000

# Para Linux
paperless_url: http://172.17.0.1:8000
```

### Caché de etiquetas

La herramienta almacena en caché las etiquetas para un rendimiento más rápido. Cuando crees nuevas etiquetas en Paperless-ngx, actualiza la caché:

```
🔄 Actualizar caché de etiquetas
```

---

## 🏗️ Arquitectura

### Componentes del sistema

**1. OpenWebUI Chat**
Interfaz de usuario que recibe comandos y muestra resultados.

**2. Paperless-ngx Tool**
Módulo principal que procesa solicitudes y gestiona interacciones con la API.

**3. Caché de etiquetas**
Almacena lista de etiquetas para acceso rápido, evitando llamadas innecesarias a la API.

**4. Módulos de la herramienta**
- Módulo de documentos — buscar, ver, obtener documentos
- Módulo de etiquetas — gestionar etiquetas y jerarquía
- Módulo de notas — operaciones CRUD con notas
- Módulo de campos — crear y gestionar campos personalizados

**5. HTTPX Client**
Maneja solicitudes HTTP a la API de Paperless-ngx.

**6. Paperless-ngx REST API**
Sistema backend que proporciona endpoints para operaciones de datos:
- `/api/documents/` — gestión de documentos
- `/api/tags/` — gestión de etiquetas
- `/api/custom_fields/` — gestión de campos personalizados
- `/api/documents/{id}/notes/` — gestión de notas

### Flujo de interacción

1. El usuario envía un comando en el chat
2. La herramienta identifica el tipo de operación
3. Se forma una solicitud HTTP al endpoint correspondiente
4. La API devuelve los datos
5. El resultado se formatea y se muestra en el chat

---

## 🔧 Solución de problemas

### ❌ Error 401 (No autorizado)

**Problema:** Token API inválido

**Solución:**
- Verifica la corrección del token en la configuración
- Asegúrate de que el token tenga los permisos necesarios
- Crea un nuevo token en Paperless-ngx

### ❌ Error de conexión

**Problema:** Servidor Paperless-ngx no disponible

**Solución:**
- Verifica la URL en la configuración
- Asegúrate de que el servidor esté ejecutándose
- Verifica la configuración de red (especialmente en Docker)
- Verifica el firewall

### ❌ Las etiquetas no se muestran

**Problema:** Caché de etiquetas desactualizada

**Solución:**
```
🔄 Actualizar caché de etiquetas
```

### ❌ Documento no encontrado

**Problema:** ID de documento incorrecto

**Solución:**
- Verifica que el ID sea correcto
- Usa la búsqueda para obtener IDs correctos
- Asegúrate de que el documento exista

---

## 🔒 Seguridad

- El token API se almacena cifrado en la configuración de OpenWebUI
- Soporte HTTPS para conexiones seguras
- El token se pasa en el encabezado `Authorization`
- Todas las solicitudes están autenticadas

---

## 📝 Licencia

MIT License — libre de usar para cualquier propósito.

---

## 🤝 Contribuir

¡Agradecemos ideas, informes de errores y pull requests!

**Cómo ayudar:**
1. Haz fork del repositorio
2. Crea una rama con la funcionalidad
3. Envía un pull request

---

## 🙏 Agradecimientos

- [Paperless-ngx](https://docs.paperless-ngx.com/) — por el excelente sistema de gestión de documentos
- [OpenWebUI](https://openwebui.com/) — por la interfaz IA extensible
- [httpx](https://www.python-httpx.org/) — por el cliente HTTP conveniente

---

<div align="center">

**[⬆ Volver arriba](#-paperless-ngx-integration-for-openwebui)**

---

**Hecho con ❤️ para la comunidad de Paperless-ngx**

</div>
