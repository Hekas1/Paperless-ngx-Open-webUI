"""
title: Paperless-ngx Document Search
author: Your Name
version: 0.1.0
license: MIT
description: Инструмент для поиска, получения и редактирования документов в Paperless-ngx через REST API
requirements: httpx
"""

import json
import re
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
import httpx


class Tools:
    class Valves(BaseModel):
        """Настройки для подключения к Paperless-ngx"""

        paperless_url: str = Field(
            default="http://localhost:8000",
            description="URL вашего Paperless-ngx сервера",
        )
        api_token: str = Field(
            default="",
            description="API токен из Paperless-ngx (получить в Профиле -> Токены API)",
            json_schema_extra={"secret": True},
        )
        max_results: int = Field(
            default=5,
            description="Максимальное количество документов в ответе",
            ge=1,
            le=20,
        )
        search_limit: int = Field(
            default=50, description="Лимит результатов поиска", ge=1, le=100
        )

    def __init__(self):
        self.valves = self.Valves()
        self.citation = False
        self.base_headers = {"Accept": "application/json; version=9"}
        self._tag_cache = {}  # Кэш тегов {id: name}
        self._tag_cache_loaded = False

    # ===== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ =====

    def _get_auth_headers(self) -> Dict[str, str]:
        headers = self.base_headers.copy()
        if self.valves.api_token:
            headers["Authorization"] = f"Token {self.valves.api_token}"
        return headers

    def _clean_highlights(self, text: str) -> str:
        if not text:
            return ""
        return re.sub(r"<[^>]+>", "", text)

    async def _emit_status(
        self, emitter, description: str, done: bool = False, error: bool = False
    ):
        if not emitter:
            return
        await emitter(
            {
                "type": "status",
                "data": {
                    "description": description,
                    "done": done,
                    "hidden": False if error else done,
                },
            }
        )

    async def _emit_notification(self, emitter, content: str):
        """Отправка уведомления в чат"""
        if not emitter:
            return
        await emitter(
            {
                "type": "notification",
                "data": {"content": content},
            }
        )

    async def _emit_citation(
        self,
        emitter,
        document_content: str,
        source_title: str,
        source_id: str,
        created_date: str = "",
        url: str = "",
    ):
        if not emitter:
            return

        metadata = {
            "date_accessed": datetime.now().isoformat(),
            "source": source_title,
            "source_id": source_id,
        }

        if created_date:
            metadata["publication_date"] = created_date

        if url:
            metadata["url"] = url

        await emitter(
            {
                "type": "citation",
                "data": {
                    "document": [
                        document_content[:500]
                        + ("..." if len(document_content) > 500 else "")
                    ],
                    "metadata": [metadata],
                    "source": {
                        "name": source_title,
                        "url": url if url else f"#doc-{source_id}",
                    },
                },
            }
        )

    def _handle_http_error(self, e: httpx.HTTPStatusError) -> str:
        status = e.response.status_code
        if status == 401:
            return "Неверный API токен. Проверьте токен в настройках."
        elif status == 403:
            return "Доступ запрещен."
        elif status == 404:
            return "Ресурс не найден."
        elif status == 429:
            return "Слишком много запросов. Попробуйте позже."
        else:
            return f"HTTP ошибка {status}"

    async def _load_tag_cache(self) -> Dict[int, str]:
        """
        Загружает все теги из Paperless-ngx в кэш.
        Возвращает словарь {id: name}
        """
        if self._tag_cache_loaded and self._tag_cache:
            return self._tag_cache

        url = f"{self.valves.paperless_url}/api/tags/?page_size=100"
        headers = self._get_auth_headers()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()

                for tag in data.get("results", []):
                    tag_id = tag.get("id")
                    tag_name = tag.get("name")
                    if tag_id and tag_name:
                        self._tag_cache[tag_id] = tag_name

                self._tag_cache_loaded = True

        except Exception as e:
            print(f"Ошибка загрузки кэша тегов: {e}")

        return self._tag_cache

    async def _find_tag_id_by_name(self, tag_name: str) -> Optional[int]:
        """
        Находит ID тега по его названию.
        Если тег не найден, возвращает None.
        """
        await self._load_tag_cache()

        # Ищем точное совпадение (регистронезависимо)
        tag_name_lower = tag_name.lower()
        for tag_id, name in self._tag_cache.items():
            if name.lower() == tag_name_lower:
                return tag_id

        # Ищем частичное совпадение
        for tag_id, name in self._tag_cache.items():
            if tag_name_lower in name.lower() or name.lower() in tag_name_lower:
                return tag_id

        return None

    def _extract_tags(self, tags_data: Any) -> List[str]:
        """
        Извлекает названия тегов с использованием кэша.
        Поддерживает: ID (числа), объекты {id, name}, строки.
        """
        doc_tags = []
        if not tags_data:
            return doc_tags

        if isinstance(tags_data, list):
            for tag in tags_data:
                if isinstance(tag, dict):
                    # Объект тега
                    tag_name = tag.get("name")
                    if tag_name:
                        doc_tags.append(tag_name)
                    else:
                        # Есть id, но нет name - ищем в кэше
                        tag_id = tag.get("id")
                        if tag_id and tag_id in self._tag_cache:
                            doc_tags.append(self._tag_cache[tag_id])
                elif isinstance(tag, int):
                    # ID тега - ищем в кэше
                    if tag in self._tag_cache:
                        doc_tags.append(self._tag_cache[tag])
                    else:
                        doc_tags.append(f"тег #{tag}")
                elif isinstance(tag, str):
                    if tag:
                        doc_tags.append(tag)

        return doc_tags

    def _convert_value_by_type(self, value: str, field_type: str):
        """
        Преобразует строковое значение в правильный тип для пользовательского поля.
        """
        if value is None or value == "":
            return None

        if field_type == "integer":
            try:
                return int(value)
            except ValueError:
                return value
        elif field_type == "float" or field_type == "monetary":
            try:
                return float(value.replace(",", "."))
            except ValueError:
                return value
        elif field_type == "boolean":
            if value.lower() in ["true", "да", "yes", "1", "on"]:
                return True
            elif value.lower() in ["false", "нет", "no", "0", "off"]:
                return False
            return value
        elif field_type == "date":
            return value
        elif field_type == "select":
            return value
        else:
            return value

    async def clear_tag_cache(self, __event_emitter__=None) -> str:
        """
        Принудительно очищает кэш тегов и перезагружает его из Paperless-ngx.
        """
        if not self.valves.api_token:
            await self._emit_status(
                __event_emitter__, "❌ API токен не настроен!", done=True, error=True
            )
            return "Ошибка: API токен не настроен."

        await self._emit_status(
            __event_emitter__, "🔄 Очистка кэша тегов...", done=False
        )

        # Очищаем кэш
        self._tag_cache = {}
        self._tag_cache_loaded = False

        # Перезагружаем
        await self._load_tag_cache()

        await self._emit_notification(
            __event_emitter__,
            f"✅ Кэш тегов обновлён! Загружено {len(self._tag_cache)} тегов",
        )
        await self._emit_status(
            __event_emitter__,
            f"✅ Кэш тегов обновлён: {len(self._tag_cache)} тегов",
            done=True,
        )

        return (
            f"## 🔄 Кэш тегов обновлён!\n\n**Загружено тегов:** {len(self._tag_cache)}\n\n**Актуальный список тегов:**\n"
            + "\n".join(
                [
                    f"- `{name}` (ID: {tid})"
                    for tid, name in sorted(self._tag_cache.items(), key=lambda x: x[1])
                ]
            )
        )

    # ===== МЕТОДЫ ДЛЯ РАБОТЫ С ИЕРАРХИЕЙ ТЕГОВ =====

    async def list_tags_hierarchical(self, __event_emitter__=None) -> str:
        """
        Получение иерархического списка тегов (с родительскими связями).
        """
        if not self.valves.api_token:
            await self._emit_status(
                __event_emitter__, "❌ API ключ не настроен!", done=True, error=True
            )
            return "Ошибка: API ключ не настроен."

        await self._emit_status(
            __event_emitter__, "🏷️ Загрузка иерархии тегов...", done=False
        )

        # Принудительно загружаем свежие данные
        self._tag_cache = {}
        self._tag_cache_loaded = False

        url = f"{self.valves.paperless_url}/api/tags/?page_size=100"
        headers = self._get_auth_headers()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()

            tags = data.get("results", [])

            # Обновляем кэш с полными данными о тегах
            self._tag_cache = {}
            self._tag_cache_loaded = True

            for tag in tags:
                tag_id = tag.get("id")
                tag_name = tag.get("name")
                if tag_id and tag_name:
                    self._tag_cache[tag_id] = tag_name

            if not tags:
                await self._emit_status(
                    __event_emitter__, "📭 Теги не найдены", done=True
                )
                return "В системе не найдено ни одного тега."

            # Строим иерархию
            tag_objects = {}
            for tag in tags:
                tag_id = tag.get("id")
                tag_objects[tag_id] = {
                    "id": tag_id,
                    "name": tag.get("name", "Без имени"),
                    "parent_id": tag.get("parent", None),
                    "document_count": tag.get("document_count", 0),
                    "children": [],
                }

            # Строим дерево
            root_tags = []
            for tag_id, tag_data in tag_objects.items():
                parent_id = tag_data["parent_id"]
                if parent_id is None:
                    root_tags.append(tag_data)
                elif parent_id in tag_objects:
                    tag_objects[parent_id]["children"].append(tag_data)

            # Функция для рекурсивного вывода дерева
            def render_tree(tag_data, level=0):
                indent = "  " * level
                if level == 0:
                    prefix = ""
                else:
                    prefix = "├── "

                output = f"{indent}{prefix}**{tag_data['name']}**"
                if tag_data["document_count"] > 0:
                    output += f" ({tag_data['document_count']} документов)"
                output += "\n"

                for child in sorted(tag_data["children"], key=lambda x: x["name"]):
                    output += render_tree(child, level + 1)
                return output

            output = f"## 🌳 Иерархия тегов\n\n"

            if not root_tags:
                # Если нет корневых тегов, значит все теги плоские
                output += "**Все теги находятся на одном уровне (без иерархии):**\n\n"
                for tag in sorted(tags, key=lambda x: x.get("name", "")):
                    tag_name = tag.get("name", "Без имени")
                    doc_count = tag.get("document_count", 0)
                    output += f"- `{tag_name}` — {doc_count} документов\n"
            else:
                for root in sorted(root_tags, key=lambda x: x["name"]):
                    output += render_tree(root, 0)
                    output += "\n"

            await self._emit_status(
                __event_emitter__,
                f"✅ Загружено {len(tags)} тегов в иерархическом виде",
                done=True,
            )
            return output

        except httpx.HTTPStatusError as e:
            error_msg = self._handle_http_error(e)
            await self._emit_status(
                __event_emitter__, f"❌ {error_msg}", done=True, error=True
            )
            return f"Ошибка: {error_msg}"

        except Exception as e:
            await self._emit_status(
                __event_emitter__, f"❌ Ошибка: {str(e)}", done=True, error=True
            )
            return f"Произошла ошибка: {str(e)}"

    async def get_tag_hierarchy(self, tag_name: str, __event_emitter__=None) -> str:
        """
        Получение иерархии для конкретного тега (родители и потомки).

        Args:
            tag_name: Название тега

        Returns:
            str: Иерархия тега (родители → текущий → потомки)
        """
        if not self.valves.api_token:
            await self._emit_status(
                __event_emitter__, "❌ API ключ не настроен!", done=True, error=True
            )
            return "Ошибка: API ключ не настроен."

        await self._emit_status(
            __event_emitter__, f"🔍 Поиск иерархии для тега '{tag_name}'...", done=False
        )

        # Загружаем свежие данные
        self._tag_cache = {}
        self._tag_cache_loaded = False

        url = f"{self.valves.paperless_url}/api/tags/?page_size=100"
        headers = self._get_auth_headers()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()

            tags = data.get("results", [])

            # Обновляем кэш
            self._tag_cache = {}
            self._tag_cache_loaded = True
            for tag in tags:
                tag_id = tag.get("id")
                tag_name_val = tag.get("name")
                if tag_id and tag_name_val:
                    self._tag_cache[tag_id] = tag_name_val

            # Строим словари
            tag_objects = {}
            for tag in tags:
                tag_id = tag.get("id")
                tag_objects[tag_id] = {
                    "id": tag_id,
                    "name": tag.get("name", "Без имени"),
                    "parent_id": tag.get("parent", None),
                    "document_count": tag.get("document_count", 0),
                }

            # Находим нужный тег
            target_tag = None
            target_id = None
            tag_name_lower = tag_name.lower().strip()

            for tid, tag_data in tag_objects.items():
                if tag_data["name"].lower() == tag_name_lower:
                    target_tag = tag_data
                    target_id = tid
                    break

            if target_tag is None:
                return f"❌ Тег **'{tag_name}'** не найден в системе."

            # Строим путь от корня до тега
            path = []
            current_id = target_id
            while current_id is not None:
                current = tag_objects.get(current_id)
                if current is None:
                    break
                path.append(current["name"])
                current_id = current.get("parent_id")

            path.reverse()  # От корня к тегу

            # Находим потомков
            def find_children(parent_id, level=0):
                children = []
                for tid, tag_data in tag_objects.items():
                    if tag_data["parent_id"] == parent_id:
                        children.append((level + 1, tag_data))
                        children.extend(find_children(tid, level + 1))
                return children

            descendants = find_children(target_id)

            output = f"## 🌳 Иерархия тега **'{target_tag['name']}'**\n\n"

            # Путь
            if len(path) > 1:
                output += "**Путь (родители → текущий):**\n"
                output += " → ".join(path) + "\n\n"
            else:
                output += "**Это корневой тег (без родителей)**\n\n"

            output += f"**ID тега:** `{target_id}`\n"
            output += f"**Документов с тегом:** {target_tag['document_count']}\n\n"

            # Потомки
            if descendants:
                output += "**Потомки (дочерние теги):**\n"
                for level, child in descendants:
                    indent = "  " * (level - 1)
                    prefix = "├── " if level > 0 else ""
                    output += f"{indent}{prefix}**{child['name']}** ({child['document_count']} документов)\n"
            else:
                output += "**Потомков нет** (тег не имеет дочерних тегов)\n"

            await self._emit_status(
                __event_emitter__,
                f"✅ Иерархия тега '{target_tag['name']}' загружена",
                done=True,
            )
            return output

        except httpx.HTTPStatusError as e:
            error_msg = self._handle_http_error(e)
            await self._emit_status(
                __event_emitter__, f"❌ {error_msg}", done=True, error=True
            )
            return f"Ошибка: {error_msg}"

        except Exception as e:
            await self._emit_status(
                __event_emitter__, f"❌ Ошибка: {str(e)}", done=True, error=True
            )
            return f"Произошла ошибка: {str(e)}"

    async def get_tags_with_parents(self, doc_id: int, __event_emitter__=None) -> str:
        """
        Получение всех тегов документа с их родительскими тегами.

        Args:
            doc_id: ID документа

        Returns:
            str: Список тегов документа с иерархией
        """
        if not self.valves.api_token:
            await self._emit_status(
                __event_emitter__, "❌ API ключ не настроен!", done=True, error=True
            )
            return "Ошибка: API ключ не настроен."

        await self._emit_status(
            __event_emitter__,
            f"📄 Получение иерархии тегов документа #{doc_id}...",
            done=False,
        )

        # Загружаем свежие данные
        self._tag_cache = {}
        self._tag_cache_loaded = False
        await self._load_tag_cache()

        # Загружаем полные данные о тегах с parent
        url = f"{self.valves.paperless_url}/api/tags/?page_size=100"
        headers = self._get_auth_headers()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Получаем все теги с parent
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()

                # Строим словарь тегов с parent
                all_tags = {}
                for tag in data.get("results", []):
                    tag_id = tag.get("id")
                    all_tags[tag_id] = {
                        "id": tag_id,
                        "name": tag.get("name", ""),
                        "parent_id": tag.get("parent", None),
                    }

                # Получаем документ
                doc_url = (
                    f"{self.valves.paperless_url}/api/documents/{doc_id}/?expand=tags"
                )
                doc_response = await client.get(doc_url, headers=headers)
                doc_response.raise_for_status()
                doc = doc_response.json()

                # Извлекаем ID тегов документа
                doc_tag_ids = []
                tags_data = doc.get("tags", [])
                for tag in tags_data:
                    if isinstance(tag, dict):
                        tag_id = tag.get("id")
                        if tag_id:
                            doc_tag_ids.append(tag_id)
                    elif isinstance(tag, int):
                        doc_tag_ids.append(tag)

                if not doc_tag_ids:
                    await self._emit_status(
                        __event_emitter__,
                        f"📭 У документа #{doc_id} нет тегов",
                        done=True,
                    )
                    return f"## 📄 Документ #{doc_id}\n\n**Название:** {doc.get('title', 'Без названия')}\n\n❌ У документа нет тегов."

                output = f"## 📄 Документ #{doc_id}\n\n"
                output += f"**Название:** {doc.get('title', 'Без названия')}\n\n"
                output += "**🏷️ Теги с иерархией:**\n\n"

                # Для каждого тега документа строим путь
                for tag_id in doc_tag_ids:
                    tag_info = all_tags.get(tag_id)
                    if not tag_info:
                        continue

                    tag_name = tag_info["name"]
                    parent_id = tag_info["parent_id"]

                    # Строим путь от корня
                    path = [tag_name]
                    current_parent_id = parent_id
                    while current_parent_id is not None:
                        parent_tag = all_tags.get(current_parent_id)
                        if parent_tag:
                            path.insert(0, parent_tag["name"])
                            current_parent_id = parent_tag.get("parent_id")
                        else:
                            break

                    output += f"**{tag_name}**"
                    if len(path) > 1:
                        output += f" (путь: {' → '.join(path)})"
                    output += "\n"

                await self._emit_status(
                    __event_emitter__,
                    f"✅ Загружена иерархия для {len(doc_tag_ids)} тегов документа #{doc_id}",
                    done=True,
                )
                return output

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                await self._emit_status(
                    __event_emitter__,
                    f"❌ Документ #{doc_id} не найден",
                    done=True,
                    error=True,
                )
                return f"Документ с ID **{doc_id}** не найден."
            error_msg = self._handle_http_error(e)
            await self._emit_status(
                __event_emitter__, f"❌ {error_msg}", done=True, error=True
            )
            return f"Ошибка: {error_msg}"

        except Exception as e:
            await self._emit_status(
                __event_emitter__, f"❌ Ошибка: {str(e)}", done=True, error=True
            )
            return f"Произошла ошибка: {str(e)}"

    # ===== ОСНОВНЫЕ МЕТОДЫ =====

    async def search_documents(self, query: str, __event_emitter__=None) -> str:
        """
        Поиск документов в Paperless-ngx по текстовому запросу.

        Args:
            query: Поисковый запрос (например, 'счет за март 2025')

        Returns:
            str: Отформатированный список найденных документов
        """
        if not self.valves.api_token:
            await self._emit_status(
                __event_emitter__, "❌ API токен не настроен!", done=True, error=True
            )
            return "Ошибка: API токен не настроен."

        await self._emit_status(
            __event_emitter__, f"🔍 Поиск: '{query}'...", done=False
        )

        # Загружаем кэш тегов
        await self._load_tag_cache()

        url = f"{self.valves.paperless_url}/api/documents/"
        params = {
            "query": query,
            "page_size": self.valves.search_limit,
            "expand": "tags",
        }
        headers = self._get_auth_headers()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()

            results = data.get("results", [])
            total_count = data.get("count", 0)

            if not results:
                await self._emit_status(
                    __event_emitter__, f"📭 Документов не найдено", done=True
                )
                return f"По запросу **'{query}'** документов не найдено."

            output = f"## 📄 Результаты поиска: **'{query}'**\n\n"
            output += f"**Найдено:** {total_count} документов\n\n"

            docs_to_show = results[: self.valves.max_results]

            for i, doc in enumerate(docs_to_show, 1):
                doc_id = doc.get("id")
                title = doc.get("title", "Без названия")
                created = doc.get("created", "Дата неизвестна")

                correspondent_data = doc.get("correspondent")
                if isinstance(correspondent_data, dict):
                    correspondent = correspondent_data.get("name", "Не указан")
                else:
                    correspondent = "Не указан"

                # Извлекаем теги с использованием кэша
                tags_list = self._extract_tags(doc.get("tags", []))
                tags_str = ", ".join(tags_list) if tags_list else "Нет тегов"

                search_hit = doc.get("__search_hit__", {})
                highlights = search_hit.get("highlights", "")
                clean_highlights = self._clean_highlights(highlights)

                if not clean_highlights:
                    content = doc.get("content", "")
                    clean_highlights = content[:300] + (
                        "..." if len(content) > 300 else ""
                    )

                output += f"### {i}. {title}\n"
                output += f"- **ID:** `{doc_id}`\n"
                output += f"- **Дата:** {created}\n"
                output += f"- **Корреспондент:** {correspondent}\n"
                output += f"- **🏷️ Теги:** {tags_str}\n"
                output += f"- **Сниппет:**\n> {clean_highlights}\n\n"

                await self._emit_citation(
                    __event_emitter__,
                    document_content=clean_highlights,
                    source_title=title,
                    source_id=f"doc_{doc_id}",
                    created_date=created,
                    url=f"{self.valves.paperless_url}/documents/{doc_id}/",
                )

            if total_count > self.valves.max_results:
                output += (
                    f"\n*... и еще {total_count - self.valves.max_results} документов.*"
                )

            await self._emit_status(
                __event_emitter__, f"✅ Найдено {total_count} документов", done=True
            )
            return output

        except httpx.HTTPStatusError as e:
            error_msg = self._handle_http_error(e)
            await self._emit_status(
                __event_emitter__, f"❌ {error_msg}", done=True, error=True
            )
            return f"Ошибка: {error_msg}"

        except Exception as e:
            await self._emit_status(
                __event_emitter__, f"❌ Ошибка: {str(e)}", done=True, error=True
            )
            return f"Произошла ошибка: {str(e)}"

    async def search_by_tags(
        self, tags: str, match_all: bool = False, __event_emitter__=None
    ) -> str:
        """
        Поиск документов по тегам (исправленная версия).
        Сначала находит ID тега, затем ищет по ID.

        Args:
            tags: Список тегов через запятую (например, 'Наследство, Тарифы')
            match_all: Если True - нужны все теги (AND), если False - хотя бы один (OR)

        Returns:
            str: Список документов с указанными тегами
        """
        if not self.valves.api_token:
            await self._emit_status(
                __event_emitter__, "❌ API токен не настроен!", done=True, error=True
            )
            return "Ошибка: API токен не настроен."

        tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]

        if not tag_list:
            await self._emit_status(
                __event_emitter__, "❌ Не указаны теги", done=True, error=True
            )
            return "Ошибка: укажите хотя бы один тег."

        # Загружаем кэш тегов
        await self._load_tag_cache()

        # Находим ID тегов
        tag_ids = []
        not_found_tags = []

        for tag_name in tag_list:
            tag_id = await self._find_tag_id_by_name(tag_name)
            if tag_id:
                tag_ids.append(tag_id)
            else:
                not_found_tags.append(tag_name)

        if not tag_ids:
            return f"❌ Теги не найдены: {', '.join(not_found_tags)}. Проверьте список доступных тегов через `list_tags()`."

        mode_text = "все теги (AND)" if match_all else "хотя бы один тег (OR)"

        # Показываем найденные ID
        tag_info = []
        for tag_id in tag_ids:
            tag_name = self._tag_cache.get(tag_id, f"ID#{tag_id}")
            tag_info.append(f"{tag_name} (ID: {tag_id})")

        await self._emit_status(
            __event_emitter__,
            f"🏷️ Поиск по тегам: {', '.join(tag_info)} ({mode_text})...",
            done=False,
        )

        url = f"{self.valves.paperless_url}/api/documents/"

        # ✅ ИСПОЛЬЗУЕМ ID ТЕГОВ для поиска
        if match_all:
            # AND: должны быть все теги
            # Используем tags__id__all
            params = {
                "page_size": self.valves.search_limit,
                "tags__id__all": ",".join(str(tid) for tid in tag_ids),
                "expand": "tags",
            }
        else:
            # OR: хотя бы один тег
            # Используем tags__id__in
            params = {
                "page_size": self.valves.search_limit,
                "tags__id__in": ",".join(str(tid) for tid in tag_ids),
                "expand": "tags",
            }

        headers = self._get_auth_headers()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()

            results = data.get("results", [])
            total_count = data.get("count", 0)

            if not results:
                await self._emit_status(
                    __event_emitter__,
                    f"📭 Документов с {mode_text} не найдено",
                    done=True,
                )
                return f"По тегам **{', '.join(tag_list)}** ({mode_text}) документов не найдено."

            output = f"## 🏷️ Документы по тегам: **{', '.join(tag_list)}**\n\n"
            output += f"**Режим:** {mode_text}\n"
            output += f"**ID тегов:** {', '.join(str(tid) for tid in tag_ids)}\n"
            output += f"**Найдено:** {total_count} документов\n\n"

            for i, doc in enumerate(results[: self.valves.max_results], 1):
                doc_id = doc.get("id")
                title = doc.get("title", "Без названия")
                created = doc.get("created", "Дата неизвестна")

                tags_list = self._extract_tags(doc.get("tags", []))
                tags_str = ", ".join(tags_list) if tags_list else "Нет тегов"

                output += f"### {i}. {title}\n"
                output += f"- **ID:** `{doc_id}`\n"
                output += f"- **Дата:** {created}\n"
                output += f"- **🏷️ Теги:** {tags_str}\n"

                content = doc.get("content", "")
                output += (
                    f"- **Содержание (первые 150 символов):**\n> {content[:150]}...\n\n"
                )

            if total_count > self.valves.max_results:
                output += (
                    f"\n*... и еще {total_count - self.valves.max_results} документов.*"
                )

            await self._emit_status(
                __event_emitter__,
                f"✅ Найдено {total_count} документов ({mode_text})",
                done=True,
            )
            return output

        except httpx.HTTPStatusError as e:
            error_msg = self._handle_http_error(e)
            await self._emit_status(
                __event_emitter__, f"❌ {error_msg}", done=True, error=True
            )
            return f"Ошибка: {error_msg}"

        except Exception as e:
            await self._emit_status(
                __event_emitter__, f"❌ Ошибка: {str(e)}", done=True, error=True
            )
            return f"Ошибка при поиске по тегам: {str(e)}"

    async def search_by_tags_exact(self, tags: str, __event_emitter__=None) -> str:
        """
        ТОЧНЫЙ поиск документов по тегам.
        Сначала получает все документы с любым из тегов,
        затем фильтрует на стороне клиента, оставляя только те,
        у которых есть ВСЕ указанные теги.

        Args:
            tags: Список тегов через запятую (например, 'Наследство, Тарифы')

        Returns:
            str: Список документов с ВСЕМИ указанными тегами
        """
        if not self.valves.api_token:
            await self._emit_status(
                __event_emitter__, "❌ API токен не настроен!", done=True, error=True
            )
            return "Ошибка: API токен не настроен."

        tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]

        if not tag_list:
            await self._emit_status(
                __event_emitter__, "❌ Не указаны теги", done=True, error=True
            )
            return "Ошибка: укажите хотя бы один тег."

        await self._emit_status(
            __event_emitter__,
            f"🏷️ ТОЧНЫЙ поиск документов с ВСЕМИ тегами: {', '.join(tag_list)}...",
            done=False,
        )

        # Загружаем кэш тегов
        await self._load_tag_cache()

        # Находим ID тегов
        tag_ids = []
        not_found_tags = []

        for tag_name in tag_list:
            tag_id = await self._find_tag_id_by_name(tag_name)
            if tag_id:
                tag_ids.append(tag_id)
            else:
                not_found_tags.append(tag_name)

        if not tag_ids:
            return f"❌ Теги не найдены: {', '.join(not_found_tags)}. Проверьте список доступных тегов через `list_tags()`."

        # Получаем ВСЕ документы, у которых есть хотя бы один тег
        url = f"{self.valves.paperless_url}/api/documents/"
        params = {
            "page_size": 200,  # Увеличиваем лимит
            "tags__id__in": ",".join(str(tid) for tid in tag_ids),
            "expand": "tags",
        }
        headers = self._get_auth_headers()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()

            all_results = data.get("results", [])

            # Фильтруем: оставляем только те, у которых есть ВСЕ теги
            exact_results = []
            for doc in all_results:
                doc_tags = self._extract_tags(doc.get("tags", []))
                # Проверяем, что все искомые теги присутствуют
                has_all_tags = True
                for tag in tag_list:
                    if not any(tag.lower() in dt.lower() for dt in doc_tags):
                        has_all_tags = False
                        break
                if has_all_tags:
                    exact_results.append(doc)

            total_count = len(exact_results)

            if not exact_results:
                await self._emit_status(
                    __event_emitter__,
                    f"📭 Документов с ВСЕМИ тегами не найдено",
                    done=True,
                )
                return f"По тегам **{', '.join(tag_list)}** (точное совпадение) документов не найдено."

            output = f"## 🏷️ ТОЧНОЕ совпадение по тегам: **{', '.join(tag_list)}**\n\n"
            output += f"**Найдено:** {total_count} документов\n\n"

            for i, doc in enumerate(exact_results[: self.valves.max_results], 1):
                doc_id = doc.get("id")
                title = doc.get("title", "Без названия")
                created = doc.get("created", "Дата неизвестна")

                tags_list = self._extract_tags(doc.get("tags", []))
                tags_str = ", ".join(tags_list) if tags_list else "Нет тегов"

                output += f"### {i}. {title}\n"
                output += f"- **ID:** `{doc_id}`\n"
                output += f"- **Дата:** {created}\n"
                output += f"- **🏷️ Теги:** {tags_str}\n"

                content = doc.get("content", "")
                output += (
                    f"- **Содержание (первые 150 символов):**\n> {content[:150]}...\n\n"
                )

            if total_count > self.valves.max_results:
                output += (
                    f"\n*... и еще {total_count - self.valves.max_results} документов.*"
                )

            await self._emit_status(
                __event_emitter__,
                f"✅ Найдено {total_count} документов с ВСЕМИ тегами",
                done=True,
            )
            return output

        except httpx.HTTPStatusError as e:
            error_msg = self._handle_http_error(e)
            await self._emit_status(
                __event_emitter__, f"❌ {error_msg}", done=True, error=True
            )
            return f"Ошибка: {error_msg}"

        except Exception as e:
            await self._emit_status(
                __event_emitter__, f"❌ Ошибка: {str(e)}", done=True, error=True
            )
            return f"Произошла ошибка: {str(e)}"

    async def get_document_by_id(self, doc_id: int, __event_emitter__=None) -> str:
        """
        Получение полной информации о документе по его ID, включая все теги и пользовательские поля.

        Args:
            doc_id: ID документа в Paperless-ngx

        Returns:
            str: Полная информация о документе с тегами и пользовательскими полями
        """
        if not self.valves.api_token:
            return "Ошибка: API токен не настроен."

        await self._emit_status(
            __event_emitter__, f"📄 Загрузка документа #{doc_id}...", done=False
        )

        # Загружаем кэш тегов
        await self._load_tag_cache()

        # ОДИН ЗАПРОС — получаем ВСЁ: документ + теги + пользовательские поля
        url = f"{self.valves.paperless_url}/api/documents/{doc_id}/?expand=tags,custom_fields"
        headers = self._get_auth_headers()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                doc = response.json()

            # ===== ОСНОВНАЯ ИНФОРМАЦИЯ =====
            output = f"## 📄 Документ #{doc.get('id')}\n\n"
            output += f"**Название:** {doc.get('title', 'Без названия')}\n"
            output += f"**Дата:** {doc.get('created', 'Неизвестно')}\n"

            # Корреспондент
            correspondent_data = doc.get("correspondent")
            if isinstance(correspondent_data, dict):
                output += f"**Корреспондент:** {correspondent_data.get('name', 'Не указан')}\n"
            elif isinstance(correspondent_data, int):
                output += f"**Корреспондент ID:** {correspondent_data}\n"

            # Тип документа
            doc_type_data = doc.get("document_type")
            if isinstance(doc_type_data, dict):
                output += f"**Тип:** {doc_type_data.get('name', 'Не указан')}\n"
            elif isinstance(doc_type_data, int):
                output += f"**Тип ID:** {doc_type_data}\n"

            # ===== ТЕГИ =====
            tags_list = self._extract_tags(doc.get("tags", []))
            tags_str = ", ".join(tags_list) if tags_list else "❌ Нет тегов"
            output += f"**🏷️ Теги и метки:** {tags_str}\n"

            # ===== ПОЛЬЗОВАТЕЛЬСКИЕ ПОЛЯ =====
            custom_fields = doc.get("custom_fields", [])

            if custom_fields:
                # Получаем названия полей
                fields_url = (
                    f"{self.valves.paperless_url}/api/custom_fields/?page_size=100"
                )
                async with httpx.AsyncClient(timeout=30.0) as client:
                    fields_response = await client.get(fields_url, headers=headers)
                    fields_response.raise_for_status()
                    fields_data = fields_response.json()

                field_names = {}
                for field in fields_data.get("results", []):
                    field_id = field.get("id")
                    field_name = field.get("name")
                    if field_id and field_name:
                        field_names[field_id] = field_name

                output += f"\n**📋 Пользовательские поля:**\n"
                for field in custom_fields:
                    field_id = field.get("field")
                    value = field.get("value")
                    field_name = field_names.get(field_id, f"Поле #{field_id}")

                    # Форматируем значение
                    if value is None or value == "":
                        value_display = "❌ Не заполнено"
                    elif isinstance(value, bool):
                        value_display = "✅ Да" if value else "❌ Нет"
                    elif isinstance(value, list):
                        value_display = ", ".join(str(v) for v in value)
                    else:
                        value_display = str(value)

                    output += f"- **{field_name}:** {value_display}\n"
            else:
                output += f"\n**📋 Пользовательские поля:** ❌ Нет заполненных полей\n"

            # ===== СОДЕРЖАНИЕ =====
            output += (
                f"\n**Содержание:**\n\n{doc.get('content', 'Содержание отсутствует')}\n"
            )
            output += f"\n**📎 Ссылка:** {self.valves.paperless_url}/documents/{doc.get('id')}/"

            # Отправляем цитату
            await self._emit_citation(
                __event_emitter__,
                document_content=doc.get("content", "")[:500],
                source_title=doc.get("title", "Без названия"),
                source_id=f"doc_{doc.get('id')}",
                created_date=doc.get("created", ""),
                url=f"{self.valves.paperless_url}/documents/{doc.get('id')}/",
            )

            await self._emit_status(
                __event_emitter__, f"✅ Документ #{doc_id} загружен", done=True
            )
            return output

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                await self._emit_status(
                    __event_emitter__,
                    f"❌ Документ #{doc_id} не найден",
                    done=True,
                    error=True,
                )
                return f"Документ с ID **{doc_id}** не найден."
            error_msg = self._handle_http_error(e)
            await self._emit_status(
                __event_emitter__, f"❌ {error_msg}", done=True, error=True
            )
            return f"Ошибка: {error_msg}"

        except Exception as e:
            await self._emit_status(
                __event_emitter__, f"❌ Ошибка: {str(e)}", done=True, error=True
            )
            return f"Произошла ошибка: {str(e)}"

    async def get_document_tags(self, doc_id: int, __event_emitter__=None) -> str:
        """
        Получение списка всех тегов/меток конкретного документа.

        Args:
            doc_id: ID документа в Paperless-ngx

        Returns:
            str: Список тегов документа в удобном формате
        """
        if not self.valves.api_token:
            return "Ошибка: API токен не настроен."

        await self._emit_status(
            __event_emitter__, f"🏷️ Получение тегов документа #{doc_id}...", done=False
        )

        # Загружаем кэш тегов
        await self._load_tag_cache()

        url = f"{self.valves.paperless_url}/api/documents/{doc_id}/?expand=tags"
        headers = self._get_auth_headers()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                doc = response.json()

            # Извлекаем теги с использованием кэша
            tags_list = self._extract_tags(doc.get("tags", []))
            title = doc.get("title", "Без названия")

            if not tags_list:
                await self._emit_status(
                    __event_emitter__, f"📭 У документа #{doc_id} нет тегов", done=True
                )
                return (
                    f"## 🏷️ Теги документа #{doc_id}\n\n"
                    f"**Название:** {title}\n"
                    f"**Теги:** ❌ **Нет тегов**\n\n"
                    f"*У этого документа не назначено ни одной метки.*"
                )

            output = f"## 🏷️ Теги документа #{doc_id}\n\n"
            output += f"**Название:** {title}\n\n"
            output += "**Список тегов/меток:**\n\n"

            for i, tag in enumerate(tags_list, 1):
                output += f"{i}. `{tag}`\n"

            output += f"\n**Всего тегов:** {len(tags_list)}"

            await self._emit_status(
                __event_emitter__,
                f"✅ Найдено {len(tags_list)} тегов у документа #{doc_id}",
                done=True,
            )
            return output

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                await self._emit_status(
                    __event_emitter__,
                    f"❌ Документ #{doc_id} не найден",
                    done=True,
                    error=True,
                )
                return f"Документ с ID **{doc_id}** не найден."
            error_msg = self._handle_http_error(e)
            await self._emit_status(
                __event_emitter__, f"❌ {error_msg}", done=True, error=True
            )
            return f"Ошибка: {error_msg}"

        except Exception as e:
            await self._emit_status(
                __event_emitter__, f"❌ Ошибка: {str(e)}", done=True, error=True
            )
            return f"Произошла ошибка: {str(e)}"

    async def list_tags(self, __event_emitter__=None) -> str:
        """
        Получение актуального списка всех тегов в системе (без кэша).
        """
        if not self.valves.api_token:
            return "Ошибка: API токен не настроен."

        await self._emit_status(
            __event_emitter__, "🏷️ Загрузка актуальных тегов...", done=False
        )

        # ⚠️ ПРИНУДИТЕЛЬНО очищаем кэш и загружаем свежие данные
        self._tag_cache = {}
        self._tag_cache_loaded = False

        url = f"{self.valves.paperless_url}/api/tags/?page_size=100"
        headers = self._get_auth_headers()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()

            tags = data.get("results", [])

            # Обновляем кэш
            for tag in tags:
                tag_id = tag.get("id")
                tag_name = tag.get("name")
                if tag_id and tag_name:
                    self._tag_cache[tag_id] = tag_name
            self._tag_cache_loaded = True

            if not tags:
                await self._emit_status(
                    __event_emitter__, "📭 Теги не найдены", done=True
                )
                return "В системе не найдено ни одного тега."

            output = f"## 🏷️ Актуальные теги системы ({len(tags)})\n\n"

            for tag in sorted(tags, key=lambda x: x.get("name", "")):
                tag_name = tag.get("name", "Без имени")
                doc_count = tag.get("document_count", 0)
                tag_id = tag.get("id")
                output += f"- `{tag_name}` (ID: {tag_id}) — {doc_count} документов\n"

            await self._emit_status(
                __event_emitter__, f"✅ Загружено {len(tags)} тегов", done=True
            )
            return output

        except httpx.HTTPStatusError as e:
            error_msg = self._handle_http_error(e)
            await self._emit_status(
                __event_emitter__, f"❌ {error_msg}", done=True, error=True
            )
            return f"Ошибка: {error_msg}"

        except Exception as e:
            await self._emit_status(
                __event_emitter__, f"❌ Ошибка: {str(e)}", done=True, error=True
            )
            return f"Ошибка: {str(e)}"

    # ===== МЕТОДЫ ДЛЯ РАБОТЫ С ТЕГАМИ =====

    async def add_tag_to_document(
        self, doc_id: int, tag_name: str, __event_emitter__=None
    ) -> str:
        """
        Добавляет тег к документу (с принудительной проверкой актуального списка тегов).

        Args:
            doc_id: ID документа в Paperless-ngx
            tag_name: Название тега

        Returns:
            str: Результат операции
        """
        if not self.valves.api_token:
            await self._emit_status(
                __event_emitter__, "❌ API токен не настроен!", done=True, error=True
            )
            return "Ошибка: API токен не настроен."

        await self._emit_status(
            __event_emitter__,
            f"🏷️ Добавление тега '{tag_name}' к документу #{doc_id}...",
            done=False,
        )

        # ⚠️ ПРИНУДИТЕЛЬНО очищаем кэш и загружаем актуальные теги
        self._tag_cache = {}
        self._tag_cache_loaded = False
        await self._load_tag_cache()

        # 1. Ищем тег по названию (строгое совпадение)
        tag_id = None
        tag_name_lower = tag_name.lower().strip()

        for tid, name in self._tag_cache.items():
            if name.lower() == tag_name_lower:
                tag_id = tid
                break

        # Если тег не найден
        if tag_id is None:
            # Проверяем частичное совпадение
            for tid, name in self._tag_cache.items():
                if tag_name_lower in name.lower() or name.lower() in tag_name_lower:
                    tag_id = tid
                    break

        if tag_id is None:
            # Тег не найден — показываем доступные
            tag_list = sorted(self._tag_cache.values())
            return (
                f"❌ Тег **'{tag_name}'** не найден в системе.\n\n"
                f"**Доступные теги ({len(tag_list)}):**\n"
                + "\n".join([f"- `{name}`" for name in tag_list[:20]])
                + (
                    f"\n... и еще {len(tag_list) - 20} тегов."
                    if len(tag_list) > 20
                    else ""
                )
                + "\n\n💡 Создайте тег вручную в Paperless-ngx или используйте существующий."
            )

        # 2. Получаем текущий документ
        url = f"{self.valves.paperless_url}/api/documents/{doc_id}/?expand=tags"
        headers = self._get_auth_headers()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Получаем текущие теги
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                doc = response.json()

                # Получаем текущие ID тегов
                current_tags = doc.get("tags", [])
                current_tag_ids = []
                for tag in current_tags:
                    if isinstance(tag, dict):
                        tag_id_val = tag.get("id")
                        if tag_id_val:
                            current_tag_ids.append(tag_id_val)
                    elif isinstance(tag, int):
                        current_tag_ids.append(tag)

                # Проверяем, есть ли уже такой тег
                if tag_id in current_tag_ids:
                    tag_name_from_cache = self._tag_cache.get(tag_id, tag_name)
                    await self._emit_notification(
                        __event_emitter__,
                        f"ℹ️ Тег '{tag_name_from_cache}' уже есть у документа #{doc_id}",
                    )
                    await self._emit_status(
                        __event_emitter__, f"ℹ️ Тег уже есть", done=True
                    )
                    return (
                        f"## ℹ️ Тег уже существует\n\n"
                        f"Тег **'{tag_name_from_cache}'** уже назначен документу #{doc_id}."
                    )

                # Добавляем новый тег
                new_tag_ids = current_tag_ids + [tag_id]

                # Отправляем PATCH-запрос
                patch_url = f"{self.valves.paperless_url}/api/documents/{doc_id}/"
                patch_data = {"tags": new_tag_ids}

                response = await client.patch(
                    patch_url, headers=headers, json=patch_data
                )
                response.raise_for_status()
                updated_doc = response.json()

                tag_name_from_cache = self._tag_cache.get(tag_id, tag_name)

                await self._emit_notification(
                    __event_emitter__,
                    f"✅ Тег '{tag_name_from_cache}' добавлен к документу #{doc_id}",
                )
                await self._emit_status(
                    __event_emitter__, f"✅ Тег добавлен", done=True
                )

                updated_tags = self._extract_tags(updated_doc.get("tags", []))
                return (
                    f"## ✅ Тег добавлен!\n\n"
                    f"**Документ #{doc_id}**\n"
                    f"**Название:** {updated_doc.get('title', 'Без названия')}\n\n"
                    f"**➕ Добавлен тег:** `{tag_name_from_cache}`\n"
                    f"**🏷️ Все теги:** {', '.join(updated_tags) if updated_tags else 'Нет тегов'}\n\n"
                    f"📎 **Ссылка:** {self.valves.paperless_url}/documents/{doc_id}/"
                )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                await self._emit_status(
                    __event_emitter__,
                    f"❌ Документ #{doc_id} не найден",
                    done=True,
                    error=True,
                )
                return f"Документ с ID **{doc_id}** не найден."
            error_msg = self._handle_http_error(e)
            await self._emit_status(
                __event_emitter__, f"❌ {error_msg}", done=True, error=True
            )
            return f"Ошибка: {error_msg}"

        except Exception as e:
            await self._emit_status(
                __event_emitter__, f"❌ Ошибка: {str(e)}", done=True, error=True
            )
            return f"Произошла ошибка: {str(e)}"

    async def remove_tag_from_document(
        self, doc_id: int, tag_name: str, __event_emitter__=None
    ) -> str:
        """
        Удаляет тег (метку) у документа.

        Args:
            doc_id: ID документа в Paperless-ngx
            tag_name: Название тега (например, 'Наследство', 'Тарифы')

        Returns:
            str: Результат операции
        """
        if not self.valves.api_token:
            await self._emit_status(
                __event_emitter__, "❌ API токен не настроен!", done=True, error=True
            )
            return "Ошибка: API токен не настроен."

        await self._emit_status(
            __event_emitter__,
            f"🗑️ Удаление тега '{tag_name}' у документа #{doc_id}...",
            done=False,
        )

        # Загружаем кэш тегов
        await self._load_tag_cache()

        # 1. Находим ID тега по имени
        tag_id = await self._find_tag_id_by_name(tag_name)

        if tag_id is None:
            tag_list = sorted(self._tag_cache.values())
            return (
                f"❌ Тег **'{tag_name}'** не найден в системе.\n\n"
                f"**Доступные теги ({len(tag_list)}):**\n"
                + "\n".join([f"- `{name}`" for name in tag_list[:20]])
                + (
                    f"\n... и еще {len(tag_list) - 20} тегов."
                    if len(tag_list) > 20
                    else ""
                )
                + "\n\n💡 Уточните название тега."
            )

        # 2. Получаем текущий документ
        url = f"{self.valves.paperless_url}/api/documents/{doc_id}/?expand=tags"
        headers = self._get_auth_headers()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Получаем текущие теги
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                doc = response.json()

                # Получаем текущие ID тегов
                current_tags = doc.get("tags", [])
                current_tag_ids = []
                for tag in current_tags:
                    if isinstance(tag, dict):
                        tag_id_val = tag.get("id")
                        if tag_id_val:
                            current_tag_ids.append(tag_id_val)
                    elif isinstance(tag, int):
                        current_tag_ids.append(tag)

                # Проверяем, есть ли такой тег
                if tag_id not in current_tag_ids:
                    tag_name_from_cache = self._tag_cache.get(tag_id, tag_name)
                    await self._emit_notification(
                        __event_emitter__,
                        f"ℹ️ Тега '{tag_name_from_cache}' нет у документа #{doc_id}",
                    )
                    await self._emit_status(
                        __event_emitter__,
                        f"ℹ️ Тега '{tag_name_from_cache}' нет у документа #{doc_id}",
                        done=True,
                    )
                    return (
                        f"## ℹ️ Тег не найден\n\n"
                        f"Тег **'{tag_name_from_cache}'** не назначен документу #{doc_id}.\n\n"
                        f"**Название:** {doc.get('title', 'Без названия')}\n"
                        f"**Текущие теги:** {', '.join(self._extract_tags(current_tags)) if current_tags else 'Нет тегов'}"
                    )

                # Удаляем тег
                new_tag_ids = [tid for tid in current_tag_ids if tid != tag_id]

                # Отправляем PATCH-запрос
                patch_url = f"{self.valves.paperless_url}/api/documents/{doc_id}/"
                patch_data = {"tags": new_tag_ids}

                response = await client.patch(
                    patch_url, headers=headers, json=patch_data
                )
                response.raise_for_status()
                updated_doc = response.json()

                # Получаем имя удалённого тега
                tag_name_from_cache = self._tag_cache.get(tag_id, tag_name)

                await self._emit_notification(
                    __event_emitter__,
                    f"🗑️ Тег '{tag_name_from_cache}' удалён у документа #{doc_id}",
                )
                await self._emit_status(
                    __event_emitter__,
                    f"✅ Тег '{tag_name_from_cache}' удалён у документа #{doc_id}",
                    done=True,
                )

                # Формируем ответ
                updated_tags = self._extract_tags(updated_doc.get("tags", []))
                return (
                    f"## 🗑️ Тег удалён!\n\n"
                    f"**Документ #{doc_id}**\n"
                    f"**Название:** {updated_doc.get('title', 'Без названия')}\n\n"
                    f"**➖ Удалён тег:** `{tag_name_from_cache}`\n"
                    f"**🏷️ Оставшиеся теги:** {', '.join(updated_tags) if updated_tags else 'Нет тегов'}\n\n"
                    f"📎 **Ссылка:** {self.valves.paperless_url}/documents/{doc_id}/"
                )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                await self._emit_status(
                    __event_emitter__,
                    f"❌ Документ #{doc_id} не найден",
                    done=True,
                    error=True,
                )
                return f"Документ с ID **{doc_id}** не найден."
            error_msg = self._handle_http_error(e)
            await self._emit_status(
                __event_emitter__, f"❌ {error_msg}", done=True, error=True
            )
            return f"Ошибка: {error_msg}"

        except Exception as e:
            await self._emit_status(
                __event_emitter__, f"❌ Ошибка: {str(e)}", done=True, error=True
            )
            return f"Произошла ошибка: {str(e)}"

    # ===== МЕТОДЫ ДЛЯ РАБОТЫ С ПРИМЕЧАНИЯМИ =====

    async def get_document_notes(self, doc_id: int, __event_emitter__=None) -> str:
        """
        Получение всех примечаний документа.

        Args:
            doc_id: ID документа в Paperless-ngx

        Returns:
            str: Список примечаний
        """
        if not self.valves.api_token:
            await self._emit_status(
                __event_emitter__, "❌ API токен не настроен!", done=True, error=True
            )
            return "Ошибка: API токен не настроен."

        await self._emit_status(
            __event_emitter__,
            f"📝 Получение примечаний документа #{doc_id}...",
            done=False,
        )

        url = f"{self.valves.paperless_url}/api/documents/{doc_id}/notes/"
        headers = self._get_auth_headers()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()

            if not data:
                await self._emit_status(
                    __event_emitter__,
                    f"📭 У документа #{doc_id} нет примечаний",
                    done=True,
                )
                return f"## 📝 Примечания документа #{doc_id}\n\n**Название:** {doc_id}\n\n❌ **У этого документа нет примечаний.**"

            output = f"## 📝 Примечания документа #{doc_id}\n\n"
            for i, note in enumerate(data, 1):
                created = note.get("created", "Дата неизвестна")
                content = note.get("note", "")
                user = note.get("user", {}).get("username", "Неизвестный пользователь")
                output += f"### {i}. {user} ({created})\n"
                output += f"{content}\n\n"

            await self._emit_status(
                __event_emitter__,
                f"✅ Найдено {len(data)} примечаний у документа #{doc_id}",
                done=True,
            )
            return output

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                await self._emit_status(
                    __event_emitter__,
                    f"❌ Документ #{doc_id} не найден",
                    done=True,
                    error=True,
                )
                return f"Документ с ID **{doc_id}** не найден."
            error_msg = self._handle_http_error(e)
            await self._emit_status(
                __event_emitter__, f"❌ {error_msg}", done=True, error=True
            )
            return f"Ошибка: {error_msg}"

        except Exception as e:
            await self._emit_status(
                __event_emitter__, f"❌ Ошибка: {str(e)}", done=True, error=True
            )
            return f"Произошла ошибка: {str(e)}"

    async def add_document_note(
        self, doc_id: int, note: str, __event_emitter__=None
    ) -> str:
        """
        Добавляет примечание к документу.

        Args:
            doc_id: ID документа в Paperless-ngx
            note: Текст примечания

        Returns:
            str: Результат операции
        """
        if not self.valves.api_token:
            await self._emit_status(
                __event_emitter__, "❌ API токен не настроен!", done=True, error=True
            )
            return "Ошибка: API токен не настроен."

        if not note or not note.strip():
            await self._emit_status(
                __event_emitter__,
                "❌ Текст примечания не может быть пустым",
                done=True,
                error=True,
            )
            return "Ошибка: текст примечания не может быть пустым."

        await self._emit_status(
            __event_emitter__,
            f"📝 Добавление примечания к документу #{doc_id}...",
            done=False,
        )

        url = f"{self.valves.paperless_url}/api/documents/{doc_id}/notes/"
        headers = self._get_auth_headers()
        data = {"note": note.strip()}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=headers, json=data)
                response.raise_for_status()
                result = response.json()

            note_preview = note[:100] + ("..." if len(note) > 100 else "")
            await self._emit_notification(
                __event_emitter__, f"✅ Примечание добавлено к документу #{doc_id}"
            )
            await self._emit_status(
                __event_emitter__,
                f"✅ Примечание добавлено к документу #{doc_id}",
                done=True,
            )

            return f"## ✅ Примечание добавлено!\n\n**Документ #{doc_id}**\n\n**Добавленное примечание:**\n> {note_preview}\n\n📎 **Ссылка:** {self.valves.paperless_url}/documents/{doc_id}/"

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                await self._emit_status(
                    __event_emitter__,
                    f"❌ Документ #{doc_id} не найден",
                    done=True,
                    error=True,
                )
                return f"Документ с ID **{doc_id}** не найден."
            error_msg = self._handle_http_error(e)
            await self._emit_status(
                __event_emitter__, f"❌ {error_msg}", done=True, error=True
            )
            return f"Ошибка: {error_msg}"

        except Exception as e:
            await self._emit_status(
                __event_emitter__, f"❌ Ошибка: {str(e)}", done=True, error=True
            )
            return f"Произошла ошибка: {str(e)}"

    async def delete_document_note(
        self, doc_id: int, note_index: int = -1, __event_emitter__=None
    ) -> str:
        """
        Удаляет примечание из документа.

        Args:
            doc_id: ID документа в Paperless-ngx
            note_index: Индекс примечания для удаления (начиная с 1).
                        Если -1 (по умолчанию), удаляет последнее примечание.

        Returns:
            str: Результат операции
        """
        if not self.valves.api_token:
            await self._emit_status(
                __event_emitter__, "❌ API токен не настроен!", done=True, error=True
            )
            return "Ошибка: API токен не настроен."

        await self._emit_status(
            __event_emitter__,
            f"🗑️ Удаление примечания из документа #{doc_id}...",
            done=False,
        )

        # Получаем список примечаний
        notes_url = f"{self.valves.paperless_url}/api/documents/{doc_id}/notes/"
        headers = self._get_auth_headers()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(notes_url, headers=headers)
                response.raise_for_status()
                notes = response.json()

            if not notes:
                await self._emit_status(
                    __event_emitter__,
                    f"📭 У документа #{doc_id} нет примечаний",
                    done=True,
                )
                return f"## ℹ️ Нет примечаний\n\nУ документа #{doc_id} нет примечаний для удаления."

            # Определяем, какое примечание удалять
            if note_index == -1:
                note_index = len(notes)  # Последнее

            if note_index < 1 or note_index > len(notes):
                return f"❌ Неверный индекс примечания. Доступны индексы от 1 до {len(notes)}."

            note_to_delete = notes[note_index - 1]
            note_content = note_to_delete.get("note", "")[:50]

            # Удаляем примечание
            delete_url = f"{self.valves.paperless_url}/api/documents/{doc_id}/notes/?note_id={note_to_delete.get('id')}"

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.delete(delete_url, headers=headers)
                response.raise_for_status()

            await self._emit_notification(
                __event_emitter__, f"🗑️ Примечание удалено из документа #{doc_id}"
            )
            await self._emit_status(
                __event_emitter__,
                f"✅ Примечание удалено из документа #{doc_id}",
                done=True,
            )

            return f"## 🗑️ Примечание удалено!\n\n**Документ #{doc_id}**\n\n**Удалённое примечание:**\n> {note_content}...\n\n📎 **Ссылка:** {self.valves.paperless_url}/documents/{doc_id}/"

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                await self._emit_status(
                    __event_emitter__,
                    f"❌ Документ #{doc_id} не найден",
                    done=True,
                    error=True,
                )
                return f"Документ с ID **{doc_id}** не найден."
            error_msg = self._handle_http_error(e)
            await self._emit_status(
                __event_emitter__, f"❌ {error_msg}", done=True, error=True
            )
            return f"Ошибка: {error_msg}"

        except Exception as e:
            await self._emit_status(
                __event_emitter__, f"❌ Ошибка: {str(e)}", done=True, error=True
            )
            return f"Произошла ошибка: {str(e)}"

    async def update_document_note(
        self, doc_id: int, note_index: int, new_note: str, __event_emitter__=None
    ) -> str:
        """
        Обновляет существующее примечание документа.

        Args:
            doc_id: ID документа в Paperless-ngx
            note_index: Индекс примечания для обновления (начиная с 1)
            new_note: Новый текст примечания

        Returns:
            str: Результат операции
        """
        if not self.valves.api_token:
            await self._emit_status(
                __event_emitter__, "❌ API токен не настроен!", done=True, error=True
            )
            return "Ошибка: API токен не настроен."

        if not new_note or not new_note.strip():
            await self._emit_status(
                __event_emitter__,
                "❌ Текст примечания не может быть пустым",
                done=True,
                error=True,
            )
            return "Ошибка: текст примечания не может быть пустым."

        await self._emit_status(
            __event_emitter__,
            f"📝 Обновление примечания #{note_index} в документе #{doc_id}...",
            done=False,
        )

        # Получаем список примечаний
        notes_url = f"{self.valves.paperless_url}/api/documents/{doc_id}/notes/"
        headers = self._get_auth_headers()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(notes_url, headers=headers)
                response.raise_for_status()
                notes = response.json()

            if not notes:
                await self._emit_status(
                    __event_emitter__,
                    f"📭 У документа #{doc_id} нет примечаний",
                    done=True,
                )
                return f"## ℹ️ Нет примечаний\n\nУ документа #{doc_id} нет примечаний для обновления."

            if note_index < 1 or note_index > len(notes):
                return f"❌ Неверный индекс примечания. Доступны индексы от 1 до {len(notes)}."

            note_to_update = notes[note_index - 1]
            note_id = note_to_update.get("id")

            # Обновляем примечание (используем DELETE + POST)
            # Сначала удаляем старую
            delete_url = f"{self.valves.paperless_url}/api/documents/{doc_id}/notes/?note_id={note_id}"
            response = await client.delete(delete_url, headers=headers)
            response.raise_for_status()

            # Затем создаём новую
            create_url = f"{self.valves.paperless_url}/api/documents/{doc_id}/notes/"
            create_data = {"note": new_note.strip()}
            response = await client.post(create_url, headers=headers, json=create_data)
            response.raise_for_status()

            note_preview = new_note[:100] + ("..." if len(new_note) > 100 else "")
            await self._emit_notification(
                __event_emitter__,
                f"✅ Примечание #{note_index} обновлено в документе #{doc_id}",
            )
            await self._emit_status(
                __event_emitter__, f"✅ Примечание обновлено", done=True
            )

            return f"## ✅ Примечание обновлено!\n\n**Документ #{doc_id}**\n\n**Новое примечание:**\n> {note_preview}\n\n📎 **Ссылка:** {self.valves.paperless_url}/documents/{doc_id}/"

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                await self._emit_status(
                    __event_emitter__,
                    f"❌ Документ #{doc_id} не найден",
                    done=True,
                    error=True,
                )
                return f"Документ с ID **{doc_id}** не найден."
            error_msg = self._handle_http_error(e)
            await self._emit_status(
                __event_emitter__, f"❌ {error_msg}", done=True, error=True
            )
            return f"Ошибка: {error_msg}"

        except Exception as e:
            await self._emit_status(
                __event_emitter__, f"❌ Ошибка: {str(e)}", done=True, error=True
            )
            return f"Произошла ошибка: {str(e)}"

    # ===== МЕТОДЫ ДЛЯ РАБОТЫ С ПОЛЬЗОВАТЕЛЬСКИМИ ПОЛЯМИ =====

    async def list_custom_fields(self, __event_emitter__=None) -> str:
        """
        Получение списка всех пользовательских полей в системе.

        Returns:
            str: Список пользовательских полей с их типами и ID
        """
        if not self.valves.api_token:
            await self._emit_status(
                __event_emitter__, "❌ API токен не настроен!", done=True, error=True
            )
            return "Ошибка: API токен не настроен."

        await self._emit_status(
            __event_emitter__, "📋 Загрузка пользовательских полей...", done=False
        )

        url = f"{self.valves.paperless_url}/api/custom_fields/"
        headers = self._get_auth_headers()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()

            fields = data.get("results", [])

            if not fields:
                await self._emit_status(
                    __event_emitter__, "📭 Пользовательские поля не найдены", done=True
                )
                return "## 📋 Пользовательские поля\n\n❌ В системе не настроено ни одного пользовательского поля."

            output = f"## 📋 Пользовательские поля ({len(fields)})\n\n"

            for field in fields:
                field_id = field.get("id")
                name = field.get("name", "Без названия")
                field_type = field.get("data_type", "unknown")
                required = "✅ Да" if field.get("required") else "❌ Нет"

                # Типы полей на русском
                type_map = {
                    "string": "Текст",
                    "integer": "Число",
                    "float": "Дробное число",
                    "boolean": "Да/Нет",
                    "date": "Дата",
                    "datetime": "Дата и время",
                    "monetary": "Денежное",
                    "documentlink": "Ссылка на документ",
                    "select": "Выбор из списка",
                }
                type_ru = type_map.get(field_type, field_type)

                output += f"### {name}\n"
                output += f"- **ID:** `{field_id}`\n"
                output += f"- **Тип:** {type_ru}\n"
                output += f"- **Обязательное:** {required}\n"

                # Для полей с выбором показываем опции
                if field_type == "select":
                    options = field.get("options", [])
                    if options:
                        output += f"- **Опции:** {', '.join(options)}\n"

                output += "\n"

            await self._emit_status(
                __event_emitter__,
                f"✅ Загружено {len(fields)} пользовательских полей",
                done=True,
            )
            return output

        except httpx.HTTPStatusError as e:
            error_msg = self._handle_http_error(e)
            await self._emit_status(
                __event_emitter__, f"❌ {error_msg}", done=True, error=True
            )
            return f"Ошибка: {error_msg}"

        except Exception as e:
            await self._emit_status(
                __event_emitter__, f"❌ Ошибка: {str(e)}", done=True, error=True
            )
            return f"Произошла ошибка: {str(e)}"

    async def get_document_custom_fields(
        self, doc_id: int, __event_emitter__=None
    ) -> str:
        """
        Получение пользовательских полей конкретного документа.
        Использует expand=custom_fields в одном запросе.

        Args:
            doc_id: ID документа в Paperless-ngx

        Returns:
            str: Значения пользовательских полей документа
        """
        if not self.valves.api_token:
            await self._emit_status(
                __event_emitter__, "❌ API токен не настроен!", done=True, error=True
            )
            return "Ошибка: API токен не настроен."

        await self._emit_status(
            __event_emitter__,
            f"📋 Получение пользовательских полей документа #{doc_id}...",
            done=False,
        )

        # ОДИН ЗАПРОС — получаем документ с пользовательскими полями
        url = (
            f"{self.valves.paperless_url}/api/documents/{doc_id}/?expand=custom_fields"
        )
        headers = self._get_auth_headers()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                doc = response.json()

            # Получаем список пользовательских полей для отображения названий
            fields_url = f"{self.valves.paperless_url}/api/custom_fields/?page_size=100"
            async with httpx.AsyncClient(timeout=30.0) as client:
                fields_response = await client.get(fields_url, headers=headers)
                fields_response.raise_for_status()
                fields_data = fields_response.json()

            # Создаём словарь ID -> имя поля
            field_names = {}
            for field in fields_data.get("results", []):
                field_id = field.get("id")
                field_name = field.get("name")
                if field_id and field_name:
                    field_names[field_id] = field_name

            # Извлекаем пользовательские поля
            custom_fields = doc.get("custom_fields", [])

            if not custom_fields:
                await self._emit_status(
                    __event_emitter__,
                    f"📭 У документа #{doc_id} нет пользовательских полей",
                    done=True,
                )
                return f"## 📋 Пользовательские поля документа #{doc_id}\n\n**Название:** {doc.get('title', 'Без названия')}\n\n❌ **У этого документа нет заполненных пользовательских полей.**"

            output = f"## 📋 Пользовательские поля документа #{doc_id}\n\n"
            output += f"**Название:** {doc.get('title', 'Без названия')}\n\n"

            for field in custom_fields:
                field_id = field.get("field")
                value = field.get("value")
                field_name = field_names.get(field_id, f"Поле #{field_id}")

                if value is None or value == "":
                    value_display = "❌ Не заполнено"
                elif isinstance(value, bool):
                    value_display = "✅ Да" if value else "❌ Нет"
                elif isinstance(value, list):
                    value_display = ", ".join(str(v) for v in value)
                else:
                    value_display = str(value)

                output += f"### {field_name}\n"
                output += f"- **Значение:** {value_display}\n\n"

            await self._emit_status(
                __event_emitter__,
                f"✅ Найдено {len(custom_fields)} пользовательских полей у документа #{doc_id}",
                done=True,
            )
            return output

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                await self._emit_status(
                    __event_emitter__,
                    f"❌ Документ #{doc_id} не найден",
                    done=True,
                    error=True,
                )
                return f"Документ с ID **{doc_id}** не найден."
            error_msg = self._handle_http_error(e)
            await self._emit_status(
                __event_emitter__, f"❌ {error_msg}", done=True, error=True
            )
            return f"Ошибка: {error_msg}"

        except Exception as e:
            await self._emit_status(
                __event_emitter__, f"❌ Ошибка: {str(e)}", done=True, error=True
            )
            return f"Произошла ошибка: {str(e)}"

    async def set_document_custom_field(
        self, doc_id: int, field_name: str, value: str, __event_emitter__=None
    ) -> str:
        """
        Устанавливает значение пользовательского поля для документа.

        Args:
            doc_id: ID документа в Paperless-ngx
            field_name: Название пользовательского поля
            value: Значение для установки

        Returns:
            str: Результат операции
        """
        if not self.valves.api_token:
            await self._emit_status(
                __event_emitter__, "❌ API токен не настроен!", done=True, error=True
            )
            return "Ошибка: API токен не настроен."

        await self._emit_status(
            __event_emitter__,
            f"✏️ Установка значения поля '{field_name}' для документа #{doc_id}...",
            done=False,
        )

        headers = self._get_auth_headers()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # 1. Получаем список всех полей, чтобы найти ID по названию
                fields_url = (
                    f"{self.valves.paperless_url}/api/custom_fields/?page_size=100"
                )
                fields_response = await client.get(fields_url, headers=headers)
                fields_response.raise_for_status()
                fields_data = fields_response.json()

                # Ищем поле по названию
                field_id = None
                field_type = None
                for field in fields_data.get("results", []):
                    if field.get("name", "").lower() == field_name.lower():
                        field_id = field.get("id")
                        field_type = field.get("data_type")
                        break

                if field_id is None:
                    return f"❌ Поле **'{field_name}'** не найдено в системе.\n\nИспользуйте `list_custom_fields()` для просмотра доступных полей."

                # 2. Получаем текущий документ
                doc_url = f"{self.valves.paperless_url}/api/documents/{doc_id}/?expand=custom_fields"
                doc_response = await client.get(doc_url, headers=headers)
                doc_response.raise_for_status()
                doc = doc_response.json()

                # 3. Преобразуем значение в правильный тип
                converted_value = self._convert_value_by_type(value, field_type)

                # 4. Обновляем пользовательские поля
                current_fields = doc.get("custom_fields", [])
                # Удаляем старое значение поля, если оно есть
                new_fields = [f for f in current_fields if f.get("field") != field_id]
                # Добавляем новое
                new_fields.append({"field": field_id, "value": converted_value})

                # 5. Отправляем PATCH-запрос
                patch_url = f"{self.valves.paperless_url}/api/documents/{doc_id}/"
                patch_data = {"custom_fields": new_fields}

                response = await client.patch(
                    patch_url, headers=headers, json=patch_data
                )
                response.raise_for_status()
                updated_doc = response.json()

                await self._emit_notification(
                    __event_emitter__,
                    f"✅ Поле '{field_name}' обновлено для документа #{doc_id}",
                )
                await self._emit_status(
                    __event_emitter__, f"✅ Поле обновлено", done=True
                )

                return f"## ✅ Поле обновлено!\n\n**Документ #{doc_id}**\n**Название:** {updated_doc.get('title', 'Без названия')}\n\n**Поле:** `{field_name}`\n**Новое значение:** `{value}`\n\n📎 **Ссылка:** {self.valves.paperless_url}/documents/{doc_id}/"

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                await self._emit_status(
                    __event_emitter__,
                    f"❌ Документ #{doc_id} не найден",
                    done=True,
                    error=True,
                )
                return f"Документ с ID **{doc_id}** не найден."
            error_msg = self._handle_http_error(e)
            await self._emit_status(
                __event_emitter__, f"❌ {error_msg}", done=True, error=True
            )
            return f"Ошибка: {error_msg}"

        except Exception as e:
            await self._emit_status(
                __event_emitter__, f"❌ Ошибка: {str(e)}", done=True, error=True
            )
            return f"Произошла ошибка: {str(e)}"

    async def remove_document_custom_field(
        self, doc_id: int, field_name: str, __event_emitter__=None
    ) -> str:
        """
        Удаляет значение пользовательского поля у документа.

        Args:
            doc_id: ID документа в Paperless-ngx
            field_name: Название пользовательского поля

        Returns:
            str: Результат операции
        """
        if not self.valves.api_token:
            await self._emit_status(
                __event_emitter__, "❌ API токен не настроен!", done=True, error=True
            )
            return "Ошибка: API токен не настроен."

        await self._emit_status(
            __event_emitter__,
            f"🗑️ Удаление поля '{field_name}' у документа #{doc_id}...",
            done=False,
        )

        headers = self._get_auth_headers()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # 1. Получаем список всех полей, чтобы найти ID по названию
                fields_url = (
                    f"{self.valves.paperless_url}/api/custom_fields/?page_size=100"
                )
                fields_response = await client.get(fields_url, headers=headers)
                fields_response.raise_for_status()
                fields_data = fields_response.json()

                field_id = None
                for field in fields_data.get("results", []):
                    if field.get("name", "").lower() == field_name.lower():
                        field_id = field.get("id")
                        break

                if field_id is None:
                    return f"❌ Поле **'{field_name}'** не найдено в системе."

                # 2. Получаем текущий документ
                doc_url = f"{self.valves.paperless_url}/api/documents/{doc_id}/?expand=custom_fields"
                doc_response = await client.get(doc_url, headers=headers)
                doc_response.raise_for_status()
                doc = doc_response.json()

                # 3. Удаляем поле
                current_fields = doc.get("custom_fields", [])
                new_fields = [f for f in current_fields if f.get("field") != field_id]

                # 4. Отправляем PATCH-запрос
                patch_url = f"{self.valves.paperless_url}/api/documents/{doc_id}/"
                patch_data = {"custom_fields": new_fields}

                response = await client.patch(
                    patch_url, headers=headers, json=patch_data
                )
                response.raise_for_status()
                updated_doc = response.json()

                await self._emit_notification(
                    __event_emitter__,
                    f"🗑️ Поле '{field_name}' удалено у документа #{doc_id}",
                )
                await self._emit_status(
                    __event_emitter__, f"✅ Поле удалено", done=True
                )

                return f"## 🗑️ Поле удалено!\n\n**Документ #{doc_id}**\n**Название:** {updated_doc.get('title', 'Без названия')}\n\n**Удалённое поле:** `{field_name}`\n\n📎 **Ссылка:** {self.valves.paperless_url}/documents/{doc_id}/"

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                await self._emit_status(
                    __event_emitter__,
                    f"❌ Документ #{doc_id} не найден",
                    done=True,
                    error=True,
                )
                return f"Документ с ID **{doc_id}** не найден."
            error_msg = self._handle_http_error(e)
            await self._emit_status(
                __event_emitter__, f"❌ {error_msg}", done=True, error=True
            )
            return f"Ошибка: {error_msg}"

        except Exception as e:
            await self._emit_status(
                __event_emitter__, f"❌ Ошибка: {str(e)}", done=True, error=True
            )
            return f"Произошла ошибка: {str(e)}"

    # ===== МЕТОДЫ ДЛЯ УПРАВЛЕНИЯ ПОЛЬЗОВАТЕЛЬСКИМИ ПОЛЯМИ =====

    async def create_custom_field(
        self,
        name: str,
        field_type: str = "string",
        required: bool = False,
        options: Optional[List[str]] = None,
        __event_emitter__=None,
    ) -> str:
        """
        Создаёт новое пользовательское поле в системе.

        Args:
            name: Название поля (обязательно)
            field_type: Тип поля (string, integer, float, boolean, date, datetime, monetary, documentlink, select)
            required: Обязательное ли поле
            options: Список опций для поля типа 'select'

        Returns:
            str: Результат операции
        """
        if not self.valves.api_token:
            await self._emit_status(
                __event_emitter__, "❌ API токен не настроен!", done=True, error=True
            )
            return "Ошибка: API токен не настроен."

        if not name or not name.strip():
            await self._emit_status(
                __event_emitter__,
                "❌ Название поля не может быть пустым",
                done=True,
                error=True,
            )
            return "Ошибка: название поля не может быть пустым."

        # Проверяем допустимые типы полей
        valid_types = [
            "string",
            "integer",
            "float",
            "boolean",
            "date",
            "datetime",
            "monetary",
            "documentlink",
            "select",
        ]
        if field_type not in valid_types:
            return f"❌ Неверный тип поля. Доступные типы: {', '.join(valid_types)}"

        # Для типа 'select' должны быть опции
        if field_type == "select" and not options:
            return "❌ Для типа 'select' необходимо указать список опций (options)."

        await self._emit_status(
            __event_emitter__,
            f"📋 Создание пользовательского поля '{name}'...",
            done=False,
        )

        url = f"{self.valves.paperless_url}/api/custom_fields/"
        headers = self._get_auth_headers()

        # Формируем данные для создания
        data = {"name": name.strip(), "data_type": field_type, "required": required}

        if field_type == "select" and options:
            data["options"] = options

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=headers, json=data)
                response.raise_for_status()
                result = response.json()

            # Обновляем кэш тегов (на всякий случай)
            self._tag_cache_loaded = False

            # Определяем тип на русском
            type_map = {
                "string": "Текст",
                "integer": "Число",
                "float": "Дробное число",
                "boolean": "Да/Нет",
                "date": "Дата",
                "datetime": "Дата и время",
                "monetary": "Денежное",
                "documentlink": "Ссылка на документ",
                "select": "Выбор из списка",
            }
            type_ru = type_map.get(field_type, field_type)

            await self._emit_notification(
                __event_emitter__, f"✅ Поле '{name}' создано"
            )
            await self._emit_status(
                __event_emitter__, f"✅ Поле '{name}' создано", done=True
            )

            output = f"## ✅ Пользовательское поле создано!\n\n"
            output += f"**Название:** `{name}`\n"
            output += f"**ID:** `{result.get('id')}`\n"
            output += f"**Тип:** {type_ru}\n"
            output += f"**Обязательное:** {'✅ Да' if required else '❌ Нет'}\n"

            if field_type == "select" and options:
                output += f"**Опции:** {', '.join(options)}\n"

            output += f"\nТеперь вы можете использовать это поле с помощью `set_document_custom_field`."

            return output

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                try:
                    error_data = e.response.json()
                    if "name" in error_data:
                        return f"❌ Поле с названием '{name}' уже существует."
                    error_msg = error_data.get("detail", "Неверные данные")
                except:
                    error_msg = "Неверные данные"
                await self._emit_status(
                    __event_emitter__, f"❌ {error_msg}", done=True, error=True
                )
                return f"Ошибка: {error_msg}"
            error_msg = self._handle_http_error(e)
            await self._emit_status(
                __event_emitter__, f"❌ {error_msg}", done=True, error=True
            )
            return f"Ошибка: {error_msg}"

        except Exception as e:
            await self._emit_status(
                __event_emitter__, f"❌ Ошибка: {str(e)}", done=True, error=True
            )
            return f"Произошла ошибка: {str(e)}"

    async def delete_custom_field(
        self, field_id_or_name: str, __event_emitter__=None
    ) -> str:
        """
        Удаляет пользовательское поле из системы.

        Args:
            field_id_or_name: ID или название поля для удаления

        Returns:
            str: Результат операции
        """
        if not self.valves.api_token:
            await self._emit_status(
                __event_emitter__, "❌ API токен не настроен!", done=True, error=True
            )
            return "Ошибка: API токен не настроен."

        await self._emit_status(
            __event_emitter__, f"🗑️ Удаление пользовательского поля...", done=False
        )

        headers = self._get_auth_headers()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Получаем список всех полей
                fields_url = (
                    f"{self.valves.paperless_url}/api/custom_fields/?page_size=100"
                )
                response = await client.get(fields_url, headers=headers)
                response.raise_for_status()
                fields_data = response.json()

                # Ищем поле по ID или названию
                field_id = None
                field_name = None

                # Проверяем, может быть это ID
                if field_id_or_name.isdigit():
                    field_id = int(field_id_or_name)
                    for field in fields_data.get("results", []):
                        if field.get("id") == field_id:
                            field_name = field.get("name")
                            break
                else:
                    # Ищем по названию
                    for field in fields_data.get("results", []):
                        if field.get("name", "").lower() == field_id_or_name.lower():
                            field_id = field.get("id")
                            field_name = field.get("name")
                            break

                if field_id is None:
                    return f"❌ Поле **'{field_id_or_name}'** не найдено в системе."

                # Удаляем поле
                delete_url = (
                    f"{self.valves.paperless_url}/api/custom_fields/{field_id}/"
                )
                response = await client.delete(delete_url, headers=headers)
                response.raise_for_status()

            await self._emit_notification(
                __event_emitter__, f"🗑️ Поле '{field_name}' удалено"
            )
            await self._emit_status(
                __event_emitter__, f"✅ Поле '{field_name}' удалено", done=True
            )

            return f"## 🗑️ Поле удалено!\n\n**Название:** `{field_name}`\n**ID:** `{field_id}`\n\nПоле успешно удалено из системы."

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                await self._emit_status(
                    __event_emitter__, f"❌ Поле не найдено", done=True, error=True
                )
                return f"Поле с ID/названием **'{field_id_or_name}'** не найдено."
            error_msg = self._handle_http_error(e)
            await self._emit_status(
                __event_emitter__, f"❌ {error_msg}", done=True, error=True
            )
            return f"Ошибка: {error_msg}"

        except Exception as e:
            await self._emit_status(
                __event_emitter__, f"❌ Ошибка: {str(e)}", done=True, error=True
            )
            return f"Произошла ошибка: {str(e)}"

    async def update_custom_field(
        self,
        field_id_or_name: str,
        new_name: Optional[str] = None,
        required: Optional[bool] = None,
        options: Optional[List[str]] = None,
        __event_emitter__=None,
    ) -> str:
        """
        Обновляет пользовательское поле.

        Args:
            field_id_or_name: ID или текущее название поля
            new_name: Новое название (опционально)
            required: Новое значение обязательности (опционально)
            options: Новые опции для типа 'select' (опционально)

        Returns:
            str: Результат операции
        """
        if not self.valves.api_token:
            await self._emit_status(
                __event_emitter__, "❌ API токен не настроен!", done=True, error=True
            )
            return "Ошибка: API токен не настроен."

        await self._emit_status(
            __event_emitter__, f"✏️ Обновление пользовательского поля...", done=False
        )

        headers = self._get_auth_headers()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Получаем список всех полей
                fields_url = (
                    f"{self.valves.paperless_url}/api/custom_fields/?page_size=100"
                )
                response = await client.get(fields_url, headers=headers)
                response.raise_for_status()
                fields_data = response.json()

                # Ищем поле по ID или названию
                field_id = None
                field_name = None
                field_type = None

                if field_id_or_name.isdigit():
                    field_id = int(field_id_or_name)
                    for field in fields_data.get("results", []):
                        if field.get("id") == field_id:
                            field_name = field.get("name")
                            field_type = field.get("data_type")
                            break
                else:
                    for field in fields_data.get("results", []):
                        if field.get("name", "").lower() == field_id_or_name.lower():
                            field_id = field.get("id")
                            field_name = field.get("name")
                            field_type = field.get("data_type")
                            break

                if field_id is None:
                    return f"❌ Поле **'{field_id_or_name}'** не найдено в системе."

                # Формируем данные для обновления
                update_data = {}
                if new_name is not None:
                    update_data["name"] = new_name.strip()
                if required is not None:
                    update_data["required"] = required
                if options is not None and field_type == "select":
                    update_data["options"] = options

                if not update_data:
                    return "⚠️ Не указано ни одного параметра для обновления."

                # Обновляем поле
                update_url = (
                    f"{self.valves.paperless_url}/api/custom_fields/{field_id}/"
                )
                response = await client.patch(
                    update_url, headers=headers, json=update_data
                )
                response.raise_for_status()
                result = response.json()

            await self._emit_notification(
                __event_emitter__, f"✅ Поле '{field_name}' обновлено"
            )
            await self._emit_status(__event_emitter__, f"✅ Поле обновлено", done=True)

            output = f"## ✅ Поле обновлено!\n\n"
            output += f"**Старое название:** `{field_name}`\n"
            if new_name:
                output += f"**Новое название:** `{new_name}`\n"
            if required is not None:
                output += f"**Обязательное:** {'✅ Да' if required else '❌ Нет'}\n"
            if options is not None and field_type == "select":
                output += f"**Новые опции:** {', '.join(options)}\n"

            output += f"\n**ID поля:** `{field_id}`"

            return output

        except httpx.HTTPStatusError as e:
            error_msg = self._handle_http_error(e)
            await self._emit_status(
                __event_emitter__, f"❌ {error_msg}", done=True, error=True
            )
            return f"Ошибка: {error_msg}"

        except Exception as e:
            await self._emit_status(
                __event_emitter__, f"❌ Ошибка: {str(e)}", done=True, error=True
            )
            return f"Произошла ошибка: {str(e)}"

    # ===== ДИАГНОСТИЧЕСКИЙ МЕТОД =====

    async def debug_document_tags(self, doc_id: int, __event_emitter__=None) -> str:
        """
        ДИАГНОСТИКА: показывает сырые данные о тегах из API.
        Используется для отладки.
        """
        if not self.valves.api_token:
            return "Ошибка: API токен не настроен."

        await self._emit_status(
            __event_emitter__, f"🔍 Диагностика документа #{doc_id}...", done=False
        )

        # Загружаем кэш тегов
        await self._load_tag_cache()

        url = f"{self.valves.paperless_url}/api/documents/{doc_id}/?expand=tags"
        headers = self._get_auth_headers()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                doc = response.json()

            output = f"## 🔍 Диагностика документа #{doc_id}\n\n"
            output += f"**Название:** {doc.get('title', 'Без названия')}\n\n"

            tags_data = doc.get("tags", [])
            output += f"**Тип данных тегов:** {type(tags_data).__name__}\n"
            output += f"**Значение:** ```json\n{json.dumps(tags_data, indent=2, ensure_ascii=False)}\n```\n"

            output += "**Сопоставление с кэшем:**\n"
            if isinstance(tags_data, list):
                for tag in tags_data:
                    if isinstance(tag, int):
                        tag_name = self._tag_cache.get(tag, f"❌ НЕИЗВЕСТНО")
                        output += f"- ID `{tag}` → `{tag_name}`\n"
                    elif isinstance(tag, dict):
                        tag_id = tag.get("id")
                        tag_name = tag.get("name")
                        if tag_name:
                            output += f"- Объект `{tag_name}` (ID: {tag_id})\n"
                        elif tag_id and tag_id in self._tag_cache:
                            output += f"- ID `{tag_id}` → `{self._tag_cache[tag_id]}`\n"

            output += f"\n**Кэш тегов (первые 15):**\n"
            for i, (tid, tname) in enumerate(list(self._tag_cache.items())[:15]):
                output += f"- {tid} → {tname}\n"
            if len(self._tag_cache) > 15:
                output += f"- ... и еще {len(self._tag_cache) - 15} тегов\n"

            await self._emit_status(
                __event_emitter__, f"✅ Диагностика завершена", done=True
            )
            return output

        except Exception as e:
            await self._emit_status(
                __event_emitter__, f"❌ Ошибка: {str(e)}", done=True, error=True
            )
            return f"Ошибка: {str(e)}"
