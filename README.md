Paperless-ngx Integration for OpenWebUI

<div align="center"> <img src="https://img.shields.io/badge/OpenWebUI-Tool-blue?style=for-the-badge&logo=github" alt="OpenWebUI Tool"> <img src="https://img.shields.io/badge/Paperless--ngx-API-green?style=for-the-badge&logo=paperless" alt="Paperless-ngx"> <img src="https://img.shields.io/badge/Python-3.8+-yellow?style=for-the-badge&logo=python" alt="Python"> <img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge" alt="License"> </div>

📖 About

Paperless-ngx Integration — это мощный инструмент для OpenWebUI, который предоставляет полный доступ к вашему экземпляру Paperless-ngx через REST API. Инструмент позволяет искать, просматривать и управлять документами, тегами, примечаниями и пользовательскими полями прямо из чата с AI-ассистентом.

✨ Key Features

<details> <summary><b>🔍 Поиск и просмотр документов</b></summary>
Текстовый поиск — поиск по содержимому документов с подсветкой совпадений
Поиск по тегам — фильтрация документов по тегам (AND/OR режимы)
Точный поиск по тегам — поиск документов, содержащих ВСЕ указанные теги
Получение документа — просмотр полной информации, включая все поля и содержимое
Цитирование — автоматическое создание цитат с указанием источника
</details><details> <summary><b>🏷️ Управление тегами</b></summary>
Иерархия тегов — просмотр древовидной структуры тегов
Добавление тегов — назначение существующих тегов документам
Удаление тегов — снятие меток с документов
Информация о тегах — получение иерархии конкретного тега
</details><details> <summary><b>📝 Работа с примечаниями</b></summary>
Просмотр — чтение всех примечаний документа
Добавление — создание новых примечаний
Редактирование — обновление существующих примечаний
Удаление — удаление примечаний по индексу
</details><details> <summary><b>📋 Пользовательские поля</b></summary>
Создание — создание полей с разными типами данных
Управление — чтение, обновление и удаление пользовательских полей
Заполнение — установка значений полей для документов
</details>
🚀 Installation

1. Скачайте файл

Скопируйте содержимое файла paperless_ngx_tool.py в новый инструмент OpenWebUI.

2. Настройте подключение

Перейдите в Admin Panel → Tools и создайте новый инструмент со следующими настройками:

yaml
Title: Paperless-ngx Document Search
Author: Your Name
Version: 1.1.0
License: MIT
Description: Инструмент для поиска, получения и редактирования документов в Paperless-ngx через REST API
Requirements: httpx
3. Настройте переменные

В разделе Valves укажите:

Настройка	Описание	Пример
paperless_url	URL вашего Paperless-ngx сервера	http://192.168.1.100:8000
api_token	API токен из Paperless-ngx (Профиль → Токены API)	your-api-token-here
max_results	Максимум документов в ответе (1-20)	5
search_limit	Лимит поиска (1-100)	50
🛠️ Available Functions

📄 Документы

Функция	Описание	Параметры
search_documents(query)	Поиск по тексту	query — поисковый запрос
search_by_tags(tags, match_all=False)	Поиск по тегам	tags — список через запятую, match_all — AND/OR
search_by_tags_exact(tags)	Точный поиск по тегам (AND)	tags — список через запятую
get_document_by_id(doc_id)	Полная информация о документе	doc_id — ID документа
get_document_tags(doc_id)	Теги документа	doc_id — ID документа
🏷️ Теги

Функция	Описание	Параметры
list_tags()	Список всех тегов	—
list_tags_hierarchical()	Иерархический список тегов	—
get_tag_hierarchy(tag_name)	Иерархия конкретного тега	tag_name — название тега
get_tags_with_parents(doc_id)	Теги документа с иерархией	doc_id — ID документа
add_tag_to_document(doc_id, tag_name)	Добавить тег документу	doc_id, tag_name
remove_tag_from_document(doc_id, tag_name)	Удалить тег у документа	doc_id, tag_name
clear_tag_cache()	Обновить кэш тегов	—
📝 Примечания

Функция	Описание	Параметры
get_document_notes(doc_id)	Список примечаний	doc_id
add_document_note(doc_id, note)	Добавить примечание	doc_id, note
update_document_note(doc_id, note_index, new_note)	Обновить примечание	doc_id, note_index, new_note
delete_document_note(doc_id, note_index=-1)	Удалить примечание	doc_id, note_index
📋 Пользовательские поля

Функция	Описание	Параметры
list_custom_fields()	Список всех полей	—
get_document_custom_fields(doc_id)	Поля документа	doc_id
set_document_custom_field(doc_id, field_name, value)	Установить значение	doc_id, field_name, value
remove_document_custom_field(doc_id, field_name)	Удалить значение	doc_id, field_name
create_custom_field(name, field_type='string', required=False, options=None)	Создать поле	См. параметры
delete_custom_field(field_id_or_name)	Удалить поле	field_id_or_name
update_custom_field(field_id_or_name, new_name=None, required=None, options=None)	Обновить поле	См. параметры
🐛 Диагностика

Функция	Описание	Параметры
debug_document_tags(doc_id)	Диагностика тегов документа	doc_id
💡 Usage Examples

Поиск документов

text
🔍 Найди все счета за март 2025 года
text
🏷️ Покажи документы с тегами "Наследство, Тарифы"
text
📄 Получи документ #12345 с полной информацией
Управление тегами

text
➕ Добавь тег "Важно" к документу #12345
text
🗑️ Удали тег "Черновик" у документа #12345
text
🌳 Покажи все теги с иерархией
Примечания и поля

text
📝 Покажи примечания документа #12345
text
📋 Покажи пользовательские поля документа #12345
Создание полей

text
📋 Создай пользовательское поле "Ответственный" типа string
text
📋 Создай поле "Статус" типа select с опциями: Новый, В работе, Завершён
📋 Типы пользовательских полей

Тип	Описание	Пример значения
string	Текст	"Иванов Иван"
integer	Целое число	42
float	Дробное число	3.14
boolean	Да/Нет	true / false
date	Дата	2025-03-15
datetime	Дата и время	2025-03-15T14:30:00
monetary	Денежное значение	1000.50
documentlink	Ссылка на документ	12345
select	Выбор из списка	"Новый"
🔧 Configuration Tips

1. Получение API токена

Войдите в Paperless-ngx
Перейдите в Профиль → Токены API
Создайте новый токен с правами на чтение/запись
Скопируйте токен и вставьте в настройки инструмента
2. Настройка сети

Если Paperless-ngx работает в Docker:

yaml
paperless_url: http://host.docker.internal:8000  # Windows/Mac
paperless_url: http://172.17.0.1:8000            # Linux
3. Кэширование тегов

Инструмент кэширует теги для ускорения работы. Если вы создали новые теги в Paperless-ngx, обновите кэш:

text
🔄 Обнови кэш тегов
🏗️ Architecture

text
┌─────────────────────────────────────────────────────────────┐
│                     OpenWebUI Chat                         │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Paperless-ngx Tool                     │   │
│  │  ┌─────────┐ ┌──────────┐ ┌───────────┐           │   │
│  │  │ Документы│ │  Теги    │ │   Поля    │           │   │
│  │  └─────────┘ └──────────┘ └───────────┘           │   │
│  │         │          │            │                  │   │
│  │         └──────────┼────────────┘                  │   │
│  │                    ▼                                │   │
│  │            HTTPX Client                            │   │
│  └─────────────────────────────────────────────────────┘   │
│                          │                                  │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │          Paperless-ngx REST API                    │   │
│  │  /api/documents/  /api/tags/  /api/custom_fields/  │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘

<details> <summary><b>Ошибка 401: Неверный API токен</b></summary>
Проверьте корректность API токена в настройках. Убедитесь, что у токена есть необходимые права.

</details><details> <summary><b>Ошибка подключения</b></summary>
Проверьте URL Paperless-ngx сервера
Убедитесь, что сервер доступен из сети
Если используется Docker, проверьте настройки сети
</details><details> <summary><b>Теги не отображаются</b></summary>
Используйте функцию clear_tag_cache() для обновления кэша тегов.

</details>
🔒 Security

API токен хранится в зашифрованном виде в настройках OpenWebUI
Все запросы используют HTTPS при наличии
Токен передаётся через заголовок Authorization
📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

🤝 Contributing

Contributions, issues, and feature requests are welcome! Feel free to check the issues page.

🙏 Acknowledgements

Paperless-ngx — for the amazing document management system
OpenWebUI — for the extensible AI interface
httpx — for the HTTP client
<div align="center"> Made with ❤️ for the Paperless-ngx community </div>
