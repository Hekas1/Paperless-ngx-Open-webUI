# 📄 Paperless-ngx Integration for OpenWebUI

<div align="center">

[![OpenWebUI](https://img.shields.io/badge/OpenWebUI-Tool-0056b3?style=for-the-badge&logo=openai)](https://github.com/open-webui/open-webui)
[![Paperless-ngx](https://img.shields.io/badge/Paperless--ngx-API-2ea44f?style=for-the-badge&logo=paperless)](https://docs.paperless-ngx.com/)
[![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)](LICENSE)

**Full-featured tool for managing Paperless-ngx documents directly from your AI chat**

</div>

---

## 🌍 Read this in other languages

- [English](README.md) (You are here)
- [Русский](README.ru.md)
- [Español](README.es.md)

---

## 📖 About

This tool transforms OpenWebUI into a powerful interface for managing your Paperless-ngx document management system. Everything you used to do through the web interface is now available through simple chat commands.

---

## ✨ Features

### 📄 Document Management

- **Text Search** — Full-text search with highlighted matches
- **Tag Search** — Filter documents by tags (AND/OR modes)
- **Exact Search** — Find documents containing ALL specified tags
- **Document Retrieval** — View full information and content
- **Auto-citation** — Automatic citations with source attribution

### 🏷️ Tag Management

- **Hierarchy** — View tree structure of tags
- **Add Tags** — Assign tags to documents
- **Remove Tags** — Remove tags from documents
- **Caching** — Fast tag access for better performance

### 📝 Notes Management

- **View** — Read all document notes
- **Add** — Create new notes
- **Edit** — Update existing notes
- **Delete** — Remove notes by index

### 📋 Custom Fields

- **Create** — 9 data types (text, number, date, select, etc.)
- **Manage** — Read, update, and delete fields
- **Fill** — Set values for documents

---

## 🚀 Quick Start

### 1. Installation

1. Open **OpenWebUI** → `Admin Panel` → `Tools`
2. Click **Create New Tool**
3. Paste the tool code
4. Configure the parameters

### 2. Tool Configuration

```yaml
Title: Paperless-ngx Document Search
Author: Your Name
Version: 0.1.0
License: MIT
Description: Tool for searching, retrieving and editing documents in Paperless-ngx via REST API
Requirements: httpx
```

### 3. Connection Setup

In the **Valves** section, specify:

| Parameter | Description | Example |
|-----------|-------------|---------|
| `paperless_url` | Your Paperless-ngx server URL | `http://localhost:8000` |
| `api_token` | API token from Paperless-ngx | `your-secret-token` |
| `max_results` | Maximum documents in response (1-20) | `5` |
| `search_limit` | Search limit (1-100) | `50` |

### 4. Getting an API Token

1. Log in to Paperless-ngx
2. Go to **Profile** → **API Tokens**
3. Create a new token
4. Copy and paste it into the settings

---

## 💡 Usage Examples

### Document Search

```
🔍 Find all contracts from February 2025
```

```
🏷️ Show documents with tags "Invoices, Urgent"
```

```
📄 Get document 12345 with full details
```

### Tag Management

```
➕ Add tag "Important" to document 12345
```

```
🗑️ Remove tag "Draft" from document 12345
```

```
🌳 Show all tags with hierarchy
```

### Notes and Fields

```
📝 Show notes for document 12345
```

```
📋 Show custom fields for document 12345
```

### Creating Fields

```
📋 Create field "Responsible" of type string
```

```
📋 Create field "Status" of type select with options: New, In Progress, Done
```

---

## 🛠️ All Functions

### 📄 Documents

| Function | Parameters | Description |
|----------|------------|-------------|
| `search_documents` | `query: str` | Full-text search with highlights |
| `search_by_tags` | `tags: str, match_all: bool` | Search by tags (AND/OR) |
| `search_by_tags_exact` | `tags: str` | Exact match of ALL tags |
| `get_document_by_id` | `doc_id: int` | Full document information |
| `get_document_tags` | `doc_id: int` | Only document tags |

### 🏷️ Tags

| Function | Parameters | Description |
|----------|------------|-------------|
| `list_tags` | `-` | List all tags |
| `list_tags_hierarchical` | `-` | Hierarchical tag tree |
| `get_tag_hierarchy` | `tag_name: str` | Hierarchy of a specific tag |
| `get_tags_with_parents` | `doc_id: int` | Document tags with hierarchy |
| `add_tag_to_document` | `doc_id: int, tag_name: str` | Add tag to document |
| `remove_tag_from_document` | `doc_id: int, tag_name: str` | Remove tag from document |
| `clear_tag_cache` | `-` | Refresh tag cache |

### 📝 Notes

| Function | Parameters | Description |
|----------|------------|-------------|
| `get_document_notes` | `doc_id: int` | List of notes |
| `add_document_note` | `doc_id: int, note: str` | Add a note |
| `update_document_note` | `doc_id: int, note_index: int, new_note: str` | Update a note |
| `delete_document_note` | `doc_id: int, note_index: int` | Delete a note |

### 📋 Custom Fields

| Function | Parameters | Description |
|----------|------------|-------------|
| `list_custom_fields` | `-` | List all fields |
| `get_document_custom_fields` | `doc_id: int` | Document fields |
| `set_document_custom_field` | `doc_id: int, field_name: str, value: str` | Set field value |
| `remove_document_custom_field` | `doc_id: int, field_name: str` | Remove field value |
| `create_custom_field` | `name, field_type, required, options` | Create a field |
| `delete_custom_field` | `field_id_or_name: str` | Delete a field |
| `update_custom_field` | `field_id_or_name, new_name, required, options` | Update a field |

### 🐛 Diagnostics

| Function | Parameters | Description |
|----------|------------|-------------|
| `debug_document_tags` | `doc_id: int` | Document tag diagnostics |

---

## 📋 Custom Field Types

| Type | Description | Example Value |
|------|-------------|---------------|
| `string` | Text | `"John Doe"` |
| `integer` | Integer number | `42` |
| `float` | Floating point number | `3.14` |
| `boolean` | Yes/No | `true` |
| `date` | Date | `2025-03-15` |
| `datetime` | Date and time | `2025-03-15T14:30:00` |
| `monetary` | Monetary value | `1000.50` |
| `documentlink` | Link to document | `12345` |
| `select` | Selection from list | `"New"` |

---

## ⚙️ Environment Setup

### Docker

If Paperless-ngx is running in Docker:

```yaml
# For Windows/Mac
paperless_url: http://host.docker.internal:8000

# For Linux
paperless_url: http://172.17.0.1:8000
```

### Tag Caching

The tool caches tags for faster performance. When you create new tags in Paperless-ngx, refresh the cache:

```
🔄 Refresh tag cache
```

---

## 🏗️ Architecture

### System Components

**1. OpenWebUI Chat**
User interface that receives commands and displays results.

**2. Paperless-ngx Tool**
Main module that processes requests and manages API interactions.

**3. Tag Cache**
Stores tag list for quick access, avoiding unnecessary API calls.

**4. Tool Modules**
- Documents module — search, view, retrieve documents
- Tags module — manage tags and hierarchy
- Notes module — CRUD operations with notes
- Fields module — create and manage custom fields

**5. HTTPX Client**
Handles HTTP requests to the Paperless-ngx API.

**6. Paperless-ngx REST API**
Backend system providing endpoints for data operations:
- `/api/documents/` — document management
- `/api/tags/` — tag management
- `/api/custom_fields/` — custom field management
- `/api/documents/{id}/notes/` — note management

### Interaction Flow

1. User sends a command in chat
2. Tool identifies the operation type
3. HTTP request is formed to the appropriate endpoint
4. API returns the data
5. Result is formatted and displayed in chat

---

## 🔧 Troubleshooting

### ❌ Error 401 (Unauthorized)

**Problem:** Invalid API token

**Solution:**
- Check token correctness in settings
- Ensure token has necessary permissions
- Create a new token in Paperless-ngx

### ❌ Connection Error

**Problem:** Paperless-ngx server unavailable

**Solution:**
- Check URL in settings
- Ensure server is running
- Check network settings (especially in Docker)
- Check firewall

### ❌ Tags Not Displaying

**Problem:** Outdated tag cache

**Solution:**
```
🔄 Refresh tag cache
```

### ❌ Document Not Found

**Problem:** Incorrect document ID

**Solution:**
- Verify the ID is correct
- Use search to get correct IDs
- Ensure the document exists

---

## 🔒 Security

- API token is stored encrypted in OpenWebUI settings
- HTTPS support for secure connections
- Token is passed in the `Authorization` header
- All requests are authenticated

---

## 📝 License

MIT License — free to use for any purpose.

---

## 🤝 Contributing

We welcome ideas, bug reports, and pull requests!

**How to help:**
1. Fork the repository
2. Create a feature branch
3. Submit a pull request

---

## 🙏 Acknowledgements

- [Paperless-ngx](https://docs.paperless-ngx.com/) — for the excellent document management system
- [OpenWebUI](https://openwebui.com/) — for the extensible AI interface
- [httpx](https://www.python-httpx.org/) — for the convenient HTTP client

---

<div align="center">

**[⬆ Back to top](#-paperless-ngx-integration-for-openwebui)**

---

**Made with ❤️ for the Paperless-ngx community**

</div>
