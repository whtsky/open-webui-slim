"""
Built-in tools for Open WebUI.

These tools are automatically available when native function calling is enabled.

IMPORTANT: DO NOT IMPORT THIS MODULE DIRECTLY IN OTHER PARTS OF THE CODEBASE.
"""

import json
import logging
import time
import asyncio
from typing import Optional

from fastapi import Request

from open_webui.models.users import UserModel
from open_webui.routers.retrieval import search_web as _search_web
from open_webui.retrieval.utils import get_content_from_url
from open_webui.routers.images import (
    image_generations,
    image_edits,
    CreateImageForm,
    EditImageForm,
)
from open_webui.routers.memories import (
    query_memory,
    add_memory as _add_memory,
    update_memory_by_id,
    QueryMemoryForm,
    AddMemoryForm,
    MemoryUpdateModel,
)
from open_webui.models.chats import Chats
from open_webui.models.messages import Messages, Message
from open_webui.models.groups import Groups
from open_webui.models.memories import Memories
from open_webui.retrieval.vector.factory import VECTOR_DB_CLIENT
from open_webui.utils.sanitize import sanitize_code

log = logging.getLogger(__name__)

MAX_KNOWLEDGE_BASE_SEARCH_ITEMS = 10_000

# =============================================================================
# TIME UTILITIES
# =============================================================================


async def get_current_timestamp(
    __request__: Request = None,
    __user__: dict = None,
) -> str:
    """
    Get the current Unix timestamp in seconds.

    :return: JSON with current_timestamp (seconds) and current_iso (ISO format)
    """
    try:
        import datetime

        now = datetime.datetime.now(datetime.timezone.utc)
        return json.dumps(
            {
                'current_timestamp': int(now.timestamp()),
                'current_iso': now.isoformat(),
            },
            ensure_ascii=False,
        )
    except Exception as e:
        log.exception(f'get_current_timestamp error: {e}')
        return json.dumps({'error': str(e)})


async def calculate_timestamp(
    days_ago: int = 0,
    weeks_ago: int = 0,
    months_ago: int = 0,
    years_ago: int = 0,
    __request__: Request = None,
    __user__: dict = None,
) -> str:
    """
    Get the current Unix timestamp, optionally adjusted by days, weeks, months, or years.
    Use this to calculate timestamps for date filtering in search functions.
    Examples: "last week" = weeks_ago=1, "3 days ago" = days_ago=3, "a year ago" = years_ago=1

    :param days_ago: Number of days to subtract from current time (default: 0)
    :param weeks_ago: Number of weeks to subtract from current time (default: 0)
    :param months_ago: Number of months to subtract from current time (default: 0)
    :param years_ago: Number of years to subtract from current time (default: 0)
    :return: JSON with current_timestamp and calculated_timestamp (both in seconds)
    """
    try:
        import datetime
        from dateutil.relativedelta import relativedelta

        now = datetime.datetime.now(datetime.timezone.utc)
        current_ts = int(now.timestamp())

        # Calculate the adjusted time
        total_days = days_ago + (weeks_ago * 7)
        adjusted = now - datetime.timedelta(days=total_days)

        # Handle months and years separately (variable length)
        if months_ago > 0 or years_ago > 0:
            adjusted = adjusted - relativedelta(months=months_ago, years=years_ago)

        adjusted_ts = int(adjusted.timestamp())

        return json.dumps(
            {
                'current_timestamp': current_ts,
                'current_iso': now.isoformat(),
                'calculated_timestamp': adjusted_ts,
                'calculated_iso': adjusted.isoformat(),
            },
            ensure_ascii=False,
        )
    except ImportError:
        # Fallback without dateutil
        import datetime

        now = datetime.datetime.now(datetime.timezone.utc)
        current_ts = int(now.timestamp())
        total_days = days_ago + (weeks_ago * 7) + (months_ago * 30) + (years_ago * 365)
        adjusted = now - datetime.timedelta(days=total_days)
        adjusted_ts = int(adjusted.timestamp())
        return json.dumps(
            {
                'current_timestamp': current_ts,
                'current_iso': now.isoformat(),
                'calculated_timestamp': adjusted_ts,
                'calculated_iso': adjusted.isoformat(),
            },
            ensure_ascii=False,
        )
    except Exception as e:
        log.exception(f'calculate_timestamp error: {e}')
        return json.dumps({'error': str(e)})


# =============================================================================
# WEB SEARCH TOOLS
# =============================================================================


async def search_web(
    query: str,
    count: int = 5,
    __request__: Request = None,
    __user__: dict = None,
) -> str:
    """
    Search the public web for information. Best for current events, external references,
    or topics not covered in internal documents.

    :param query: The search query to look up
    :param count: Number of results to return (default: 5)
    :return: JSON with search results containing title, link, and snippet for each result
    """
    if __request__ is None:
        return json.dumps({'error': 'Request context not available'})

    try:
        engine = __request__.app.state.config.WEB_SEARCH_ENGINE
        user = UserModel(**__user__) if __user__ else None

        # Enforce maximum result count from config to prevent abuse
        count = (
            count
            if count < __request__.app.state.config.WEB_SEARCH_RESULT_COUNT
            else __request__.app.state.config.WEB_SEARCH_RESULT_COUNT
        )

        results = await asyncio.to_thread(_search_web, __request__, engine, query, user)

        # Limit results
        results = results[:count] if results else []

        return json.dumps(
            [{'title': r.title, 'link': r.link, 'snippet': r.snippet} for r in results],
            ensure_ascii=False,
        )
    except Exception as e:
        log.exception(f'search_web error: {e}')
        return json.dumps({'error': str(e)})


async def fetch_url(
    url: str,
    __request__: Request = None,
    __user__: dict = None,
) -> str:
    """
    Fetch and extract the main text content from a web page URL.

    :param url: The URL to fetch content from
    :return: The extracted text content from the page
    """
    if __request__ is None:
        return json.dumps({'error': 'Request context not available'})

    try:
        content, _ = await asyncio.to_thread(get_content_from_url, __request__, url)

        # Truncate if configured (WEB_FETCH_MAX_CONTENT_LENGTH)
        max_length = getattr(__request__.app.state.config, 'WEB_FETCH_MAX_CONTENT_LENGTH', None)
        if max_length and max_length > 0 and len(content) > max_length:
            content = content[:max_length] + '\n\n[Content truncated...]'

        return content
    except Exception as e:
        log.exception(f'fetch_url error: {e}')
        return json.dumps({'error': str(e)})


# =============================================================================
# IMAGE GENERATION TOOLS
# =============================================================================


async def generate_image(
    prompt: str,
    __request__: Request = None,
    __user__: dict = None,
    __event_emitter__: callable = None,
    __chat_id__: str = None,
    __message_id__: str = None,
) -> str:
    """
    Generate an image based on a text prompt.

    :param prompt: A detailed description of the image to generate
    :return: Confirmation that the image was generated, or an error message
    """
    if __request__ is None:
        return json.dumps({'error': 'Request context not available'})

    try:
        user = UserModel(**__user__) if __user__ else None

        images = await image_generations(
            request=__request__,
            form_data=CreateImageForm(prompt=prompt),
            user=user,
        )

        # Prepare file entries for the images
        image_files = [{'type': 'image', 'url': img['url']} for img in images]

        # Persist files to DB if chat context is available
        if __chat_id__ and __message_id__ and images:
            db_files = Chats.add_message_files_by_id_and_message_id(
                __chat_id__,
                __message_id__,
                image_files,
            )
            if db_files is not None:
                image_files = db_files

        # Emit the images to the UI if event emitter is available
        if __event_emitter__ and image_files:
            await __event_emitter__(
                {
                    'type': 'chat:message:files',
                    'data': {
                        'files': image_files,
                    },
                }
            )
            # Return a message indicating the image is already displayed
            return json.dumps(
                {
                    'status': 'success',
                    'message': 'The image has been successfully generated and is already visible to the user in the chat. You do not need to display or embed the image again - just acknowledge that it has been created.',
                    'images': images,
                },
                ensure_ascii=False,
            )

        return json.dumps({'status': 'success', 'images': images}, ensure_ascii=False)
    except Exception as e:
        log.exception(f'generate_image error: {e}')
        return json.dumps({'error': str(e)})


async def edit_image(
    prompt: str,
    image_urls: list[str],
    __request__: Request = None,
    __user__: dict = None,
    __event_emitter__: callable = None,
    __chat_id__: str = None,
    __message_id__: str = None,
) -> str:
    """
    Edit existing images based on a text prompt.

    :param prompt: A description of the changes to make to the images
    :param image_urls: A list of URLs of the images to edit
    :return: Confirmation that the images were edited, or an error message
    """
    if __request__ is None:
        return json.dumps({'error': 'Request context not available'})

    try:
        user = UserModel(**__user__) if __user__ else None

        images = await image_edits(
            request=__request__,
            form_data=EditImageForm(prompt=prompt, image=image_urls),
            user=user,
        )

        # Prepare file entries for the images
        image_files = [{'type': 'image', 'url': img['url']} for img in images]

        # Persist files to DB if chat context is available
        if __chat_id__ and __message_id__ and images:
            db_files = Chats.add_message_files_by_id_and_message_id(
                __chat_id__,
                __message_id__,
                image_files,
            )
            if db_files is not None:
                image_files = db_files

        # Emit the images to the UI if event emitter is available
        if __event_emitter__ and image_files:
            await __event_emitter__(
                {
                    'type': 'chat:message:files',
                    'data': {
                        'files': image_files,
                    },
                }
            )
            # Return a message indicating the image is already displayed
            return json.dumps(
                {
                    'status': 'success',
                    'message': 'The edited image has been successfully generated and is already visible to the user in the chat. You do not need to display or embed the image again - just acknowledge that it has been created.',
                    'images': images,
                },
                ensure_ascii=False,
            )

        return json.dumps({'status': 'success', 'images': images}, ensure_ascii=False)
    except Exception as e:
        log.exception(f'edit_image error: {e}')
        return json.dumps({'error': str(e)})


# =============================================================================
# MEMORY TOOLS
# =============================================================================


async def search_memories(
    query: str,
    count: int = 5,
    __request__: Request = None,
    __user__: dict = None,
) -> str:
    """
    Search the user's stored memories for relevant information.

    :param query: The search query to find relevant memories
    :param count: Number of memories to return (default 5)
    :return: JSON with matching memories and their dates
    """
    if __request__ is None:
        return json.dumps({'error': 'Request context not available'})

    try:
        user = UserModel(**__user__) if __user__ else None

        results = await query_memory(
            __request__,
            QueryMemoryForm(content=query, k=count),
            user,
        )

        if results and hasattr(results, 'documents') and results.documents:
            memories = []
            for doc_idx, doc in enumerate(results.documents[0]):
                memory_id = None
                if results.ids and results.ids[0]:
                    memory_id = results.ids[0][doc_idx]
                created_at = 'Unknown'
                if results.metadatas and results.metadatas[0][doc_idx].get('created_at'):
                    created_at = time.strftime(
                        '%Y-%m-%d',
                        time.localtime(results.metadatas[0][doc_idx]['created_at']),
                    )
                memories.append({'id': memory_id, 'date': created_at, 'content': doc})
            return json.dumps(memories, ensure_ascii=False)
        else:
            return json.dumps([])
    except Exception as e:
        log.exception(f'search_memories error: {e}')
        return json.dumps({'error': str(e)})


async def add_memory(
    content: str,
    __request__: Request = None,
    __user__: dict = None,
) -> str:
    """
    Store a new memory for the user.

    :param content: The memory content to store
    :return: Confirmation that the memory was stored
    """
    if __request__ is None:
        return json.dumps({'error': 'Request context not available'})

    try:
        user = UserModel(**__user__) if __user__ else None

        memory = await _add_memory(
            __request__,
            AddMemoryForm(content=content),
            user,
        )

        return json.dumps({'status': 'success', 'id': memory.id}, ensure_ascii=False)
    except Exception as e:
        log.exception(f'add_memory error: {e}')
        return json.dumps({'error': str(e)})


async def replace_memory_content(
    memory_id: str,
    content: str,
    __request__: Request = None,
    __user__: dict = None,
) -> str:
    """
    Update the content of an existing memory by its ID.

    :param memory_id: The ID of the memory to update
    :param content: The new content for the memory
    :return: Confirmation that the memory was updated
    """
    if __request__ is None:
        return json.dumps({'error': 'Request context not available'})

    try:
        user = UserModel(**__user__) if __user__ else None

        memory = await update_memory_by_id(
            memory_id=memory_id,
            request=__request__,
            form_data=MemoryUpdateModel(content=content),
            user=user,
        )

        return json.dumps(
            {'status': 'success', 'id': memory.id, 'content': memory.content},
            ensure_ascii=False,
        )
    except Exception as e:
        log.exception(f'replace_memory_content error: {e}')
        return json.dumps({'error': str(e)})


async def delete_memory(
    memory_id: str,
    __request__: Request = None,
    __user__: dict = None,
) -> str:
    """
    Delete a memory by its ID.

    :param memory_id: The ID of the memory to delete
    :return: Confirmation that the memory was deleted
    """
    if __request__ is None:
        return json.dumps({'error': 'Request context not available'})

    try:
        user = UserModel(**__user__) if __user__ else None

        result = Memories.delete_memory_by_id_and_user_id(memory_id, user.id)

        if result:
            VECTOR_DB_CLIENT.delete(collection_name=f'user-memory-{user.id}', ids=[memory_id])
            return json.dumps(
                {'status': 'success', 'message': f'Memory {memory_id} deleted'},
                ensure_ascii=False,
            )
        else:
            return json.dumps({'error': 'Memory not found or access denied'})
    except Exception as e:
        log.exception(f'delete_memory error: {e}')
        return json.dumps({'error': str(e)})


async def list_memories(
    __request__: Request = None,
    __user__: dict = None,
) -> str:
    """
    List all stored memories for the user.

    :return: JSON list of all memories with id, content, and dates
    """
    if __request__ is None:
        return json.dumps({'error': 'Request context not available'})

    try:
        user = UserModel(**__user__) if __user__ else None

        memories = Memories.get_memories_by_user_id(user.id)

        if memories:
            result = [
                {
                    'id': m.id,
                    'content': m.content,
                    'created_at': time.strftime('%Y-%m-%d %H:%M', time.localtime(m.created_at)),
                    'updated_at': time.strftime('%Y-%m-%d %H:%M', time.localtime(m.updated_at)),
                }
                for m in memories
            ]
            return json.dumps(result, ensure_ascii=False)
        else:
            return json.dumps([])
    except Exception as e:
        log.exception(f'list_memories error: {e}')
        return json.dumps({'error': str(e)})


# =============================================================================
# CHATS TOOLS
# =============================================================================


async def search_chats(
    query: str,
    count: int = 5,
    start_timestamp: Optional[int] = None,
    end_timestamp: Optional[int] = None,
    __request__: Request = None,
    __user__: dict = None,
    __chat_id__: str = None,
) -> str:
    """
    Search the user's previous chat conversations by title and message content.

    :param query: The search query to find matching chats
    :param count: Maximum number of results to return (default: 5)
    :param start_timestamp: Only include chats updated after this Unix timestamp (seconds)
    :param end_timestamp: Only include chats updated before this Unix timestamp (seconds)
    :return: JSON with matching chats containing id, title, updated_at, and content snippet
    """
    if __request__ is None:
        return json.dumps({'error': 'Request context not available'})

    if not __user__:
        return json.dumps({'error': 'User context not available'})

    try:
        user_id = __user__.get('id')

        chats = Chats.get_chats_by_user_id_and_search_text(
            user_id=user_id,
            search_text=query,
            include_archived=False,
            skip=0,
            limit=count * 3,  # Fetch more for filtering
        )

        results = []
        for chat in chats:
            # Skip the current chat to avoid showing it in search results
            if __chat_id__ and chat.id == __chat_id__:
                continue

            # Apply date filters (updated_at is in seconds)
            if start_timestamp and chat.updated_at < start_timestamp:
                continue
            if end_timestamp and chat.updated_at > end_timestamp:
                continue

            # Find a matching message snippet
            snippet = ''
            messages = chat.chat.get('history', {}).get('messages', {})
            lower_query = query.lower()

            for msg_id, msg in messages.items():
                content = msg.get('content', '')
                if isinstance(content, str) and lower_query in content.lower():
                    idx = content.lower().find(lower_query)
                    start = max(0, idx - 50)
                    end = min(len(content), idx + len(query) + 100)
                    snippet = ('...' if start > 0 else '') + content[start:end] + ('...' if end < len(content) else '')
                    break

            if not snippet and lower_query in chat.title.lower():
                snippet = f'Title match: {chat.title}'

            results.append(
                {
                    'id': chat.id,
                    'title': chat.title,
                    'snippet': snippet,
                    'updated_at': chat.updated_at,
                }
            )

            if len(results) >= count:
                break

        return json.dumps(results, ensure_ascii=False)
    except Exception as e:
        log.exception(f'search_chats error: {e}')
        return json.dumps({'error': str(e)})


async def view_chat(
    chat_id: str,
    __request__: Request = None,
    __user__: dict = None,
) -> str:
    """
    Get the full conversation history of a chat by its ID.

    :param chat_id: The ID of the chat to retrieve
    :return: JSON with the chat's id, title, and messages
    """
    if __request__ is None:
        return json.dumps({'error': 'Request context not available'})

    if not __user__:
        return json.dumps({'error': 'User context not available'})

    try:
        user_id = __user__.get('id')

        chat = Chats.get_chat_by_id_and_user_id(chat_id, user_id)

        if not chat:
            return json.dumps({'error': 'Chat not found or access denied'})

        # Extract messages from history
        messages = []
        history = chat.chat.get('history', {})
        msg_dict = history.get('messages', {})

        # Build message chain from currentId
        current_id = history.get('currentId')
        visited = set()

        while current_id and current_id not in visited:
            visited.add(current_id)
            msg = msg_dict.get(current_id)
            if msg:
                messages.append(
                    {
                        'role': msg.get('role', ''),
                        'content': msg.get('content', ''),
                    }
                )
            current_id = msg.get('parentId') if msg else None

        # Reverse to get chronological order
        messages.reverse()

        return json.dumps(
            {
                'id': chat.id,
                'title': chat.title,
                'messages': messages,
                'updated_at': chat.updated_at,
                'created_at': chat.created_at,
            },
            ensure_ascii=False,
        )
    except Exception as e:
        log.exception(f'view_chat error: {e}')
        return json.dumps({'error': str(e)})


# =============================================================================
# KNOWLEDGE BASE TOOLS
# =============================================================================


async def list_knowledge_bases(
    count: int = 10,
    skip: int = 0,
    __request__: Request = None,
    __user__: dict = None,
) -> str:
    """
    List the user's accessible knowledge bases.

    :param count: Maximum number of KBs to return (default: 10)
    :param skip: Number of results to skip for pagination (default: 0)
    :return: JSON with KBs containing id, name, description, and file_count
    """
    if __request__ is None:
        return json.dumps({'error': 'Request context not available'})

    if not __user__:
        return json.dumps({'error': 'User context not available'})

    try:
        from open_webui.models.knowledge import Knowledges

        user_id = __user__.get('id')
        user_group_ids = [group.id for group in Groups.get_groups_by_member_id(user_id)]

        result = Knowledges.search_knowledge_bases(
            user_id,
            filter={
                'query': '',
                'user_id': user_id,
                'group_ids': user_group_ids,
            },
            skip=skip,
            limit=count,
        )

        knowledge_bases = []
        for knowledge_base in result.items:
            files = Knowledges.get_files_by_id(knowledge_base.id)
            file_count = len(files) if files else 0

            knowledge_bases.append(
                {
                    'id': knowledge_base.id,
                    'name': knowledge_base.name,
                    'description': knowledge_base.description or '',
                    'file_count': file_count,
                    'updated_at': knowledge_base.updated_at,
                }
            )

        return json.dumps(knowledge_bases, ensure_ascii=False)
    except Exception as e:
        log.exception(f'list_knowledge_bases error: {e}')
        return json.dumps({'error': str(e)})


async def search_knowledge_bases(
    query: str,
    count: int = 5,
    skip: int = 0,
    __request__: Request = None,
    __user__: dict = None,
) -> str:
    """
    Search the user's accessible knowledge bases by name and description.

    :param query: The search query to find matching knowledge bases
    :param count: Maximum number of results to return (default: 5)
    :param skip: Number of results to skip for pagination (default: 0)
    :return: JSON with matching KBs containing id, name, description, and file_count
    """
    if __request__ is None:
        return json.dumps({'error': 'Request context not available'})

    if not __user__:
        return json.dumps({'error': 'User context not available'})

    try:
        from open_webui.models.knowledge import Knowledges

        user_id = __user__.get('id')
        user_group_ids = [group.id for group in Groups.get_groups_by_member_id(user_id)]

        result = Knowledges.search_knowledge_bases(
            user_id,
            filter={
                'query': query,
                'user_id': user_id,
                'group_ids': user_group_ids,
            },
            skip=skip,
            limit=count,
        )

        knowledge_bases = []
        for knowledge_base in result.items:
            files = Knowledges.get_files_by_id(knowledge_base.id)
            file_count = len(files) if files else 0

            knowledge_bases.append(
                {
                    'id': knowledge_base.id,
                    'name': knowledge_base.name,
                    'description': knowledge_base.description or '',
                    'file_count': file_count,
                    'updated_at': knowledge_base.updated_at,
                }
            )

        return json.dumps(knowledge_bases, ensure_ascii=False)
    except Exception as e:
        log.exception(f'search_knowledge_bases error: {e}')
        return json.dumps({'error': str(e)})


async def search_knowledge_files(
    query: str,
    knowledge_id: Optional[str] = None,
    count: int = 5,
    skip: int = 0,
    __request__: Request = None,
    __user__: dict = None,
    __model_knowledge__: Optional[list[dict]] = None,
) -> str:
    """
    Search files by filename across knowledge bases the user has access to.
    When the model has attached knowledge, searches only within attached KBs and files.

    :param query: The search query to find matching files by filename
    :param knowledge_id: Optional KB id to limit search to a specific knowledge base
    :param count: Maximum number of results to return (default: 5)
    :param skip: Number of results to skip for pagination (default: 0)
    :return: JSON with matching files containing id, filename, and updated_at
    """
    if __request__ is None:
        return json.dumps({'error': 'Request context not available'})

    if not __user__:
        return json.dumps({'error': 'User context not available'})

    try:
        from open_webui.models.knowledge import Knowledges
        from open_webui.models.files import Files
        from open_webui.models.access_grants import AccessGrants

        user_id = __user__.get('id')
        user_role = __user__.get('role', 'user')
        user_group_ids = [group.id for group in Groups.get_groups_by_member_id(user_id)]

        # When model has attached knowledge, scope to attached KBs/files only
        if __model_knowledge__:
            attached_kb_ids = set()
            attached_file_ids = set()

            for item in __model_knowledge__:
                item_type = item.get('type')
                item_id = item.get('id')
                if item_type == 'collection':
                    attached_kb_ids.add(item_id)
                elif item_type == 'file':
                    attached_file_ids.add(item_id)

            # If knowledge_id specified, verify it's in the attached set
            if knowledge_id:
                if knowledge_id not in attached_kb_ids:
                    return json.dumps({'error': f'Knowledge base {knowledge_id} is not attached to this model'})
                attached_kb_ids = {knowledge_id}

            all_files = []

            # Search within attached KBs
            for kb_id in attached_kb_ids:
                knowledge = Knowledges.get_knowledge_by_id(kb_id)
                if not knowledge:
                    continue

                if not (
                    user_role == 'admin'
                    or knowledge.user_id == user_id
                    or AccessGrants.has_access(
                        user_id=user_id,
                        resource_type='knowledge',
                        resource_id=knowledge.id,
                        permission='read',
                        user_group_ids=set(user_group_ids),
                    )
                ):
                    continue

                result = Knowledges.search_files_by_id(
                    knowledge_id=kb_id,
                    user_id=user_id,
                    filter={'query': query},
                    skip=0,
                    limit=count + skip,
                )

                for file in result.items:
                    all_files.append(
                        {
                            'id': file.id,
                            'filename': file.filename,
                            'knowledge_id': knowledge.id,
                            'knowledge_name': knowledge.name,
                            'updated_at': file.updated_at,
                        }
                    )

            # Search within directly attached files (filename match)
            if not knowledge_id and attached_file_ids:
                query_lower = query.lower() if query else ''
                for file_id in attached_file_ids:
                    file = Files.get_file_by_id(file_id)
                    if file and (not query_lower or query_lower in file.filename.lower()):
                        all_files.append(
                            {
                                'id': file.id,
                                'filename': file.filename,
                                'updated_at': file.updated_at,
                            }
                        )

            # Apply pagination across combined results
            all_files = all_files[skip : skip + count]
            return json.dumps(all_files, ensure_ascii=False)

        # No attached knowledge - search all accessible KBs
        if knowledge_id:
            result = Knowledges.search_files_by_id(
                knowledge_id=knowledge_id,
                user_id=user_id,
                filter={'query': query},
                skip=skip,
                limit=count,
            )
        else:
            result = Knowledges.search_knowledge_files(
                filter={
                    'query': query,
                    'user_id': user_id,
                    'group_ids': user_group_ids,
                },
                skip=skip,
                limit=count,
            )

        files = []
        for file in result.items:
            file_info = {
                'id': file.id,
                'filename': file.filename,
                'updated_at': file.updated_at,
            }
            if hasattr(file, 'collection') and file.collection:
                file_info['knowledge_id'] = file.collection.get('id', '')
                file_info['knowledge_name'] = file.collection.get('name', '')
            files.append(file_info)

        return json.dumps(files, ensure_ascii=False)
    except Exception as e:
        log.exception(f'search_knowledge_files error: {e}')
        return json.dumps({'error': str(e)})


# Hard cap for view_file / view_knowledge_file output
MAX_VIEW_FILE_CHARS = 100_000
DEFAULT_VIEW_FILE_MAX_CHARS = 10_000


async def view_file(
    file_id: str,
    offset: int = 0,
    max_chars: int = DEFAULT_VIEW_FILE_MAX_CHARS,
    __request__: Request = None,
    __user__: dict = None,
    __model_knowledge__: Optional[list[dict]] = None,
) -> str:
    """
    Get the content of a file by its ID. Supports pagination for large files.

    :param file_id: The ID of the file to retrieve
    :param offset: Character offset to start reading from (default: 0)
    :param max_chars: Maximum characters to return (default: 10000, hard cap: 100000)
    :return: JSON with the file's id, filename, content, and pagination metadata if truncated
    """
    if __request__ is None:
        return json.dumps({'error': 'Request context not available'})

    if not __user__:
        return json.dumps({'error': 'User context not available'})

    # Coerce parameters from LLM tool calls (may come as strings)
    if isinstance(offset, str):
        try:
            offset = int(offset)
        except ValueError:
            offset = 0
    if isinstance(max_chars, str):
        try:
            max_chars = int(max_chars)
        except ValueError:
            max_chars = DEFAULT_VIEW_FILE_MAX_CHARS

    # Enforce hard cap
    max_chars = min(max(max_chars, 1), MAX_VIEW_FILE_CHARS)
    offset = max(offset, 0)

    try:
        from open_webui.models.files import Files
        from open_webui.utils.access_control.files import has_access_to_file

        user_id = __user__.get('id')
        user_role = __user__.get('role', 'user')

        file = Files.get_file_by_id(file_id)
        if not file:
            return json.dumps({'error': 'File not found'})

        if (
            file.user_id != user_id
            and user_role != 'admin'
            and not any(
                item.get('type') == 'file' and item.get('id') == file_id for item in (__model_knowledge__ or [])
            )
            and not has_access_to_file(
                file_id=file_id,
                access_type='read',
                user=UserModel(**__user__),
            )
        ):
            return json.dumps({'error': 'File not found'})

        content = ''
        if file.data:
            content = file.data.get('content', '')

        total_chars = len(content)
        sliced = content[offset : offset + max_chars]
        is_truncated = (offset + len(sliced)) < total_chars

        result = {
            'id': file.id,
            'filename': file.filename,
            'content': sliced,
            'updated_at': file.updated_at,
            'created_at': file.created_at,
        }

        if is_truncated or offset > 0:
            result['truncated'] = is_truncated
            result['total_chars'] = total_chars
            result['returned_chars'] = len(sliced)
            result['offset'] = offset
            if is_truncated:
                result['next_offset'] = offset + len(sliced)

        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        log.exception(f'view_file error: {e}')
        return json.dumps({'error': str(e)})


async def view_knowledge_file(
    file_id: str,
    offset: int = 0,
    max_chars: int = DEFAULT_VIEW_FILE_MAX_CHARS,
    __request__: Request = None,
    __user__: dict = None,
) -> str:
    """
    Get the content of a file from a knowledge base. Supports pagination for large files.

    :param file_id: The ID of the file to retrieve
    :param offset: Character offset to start reading from (default: 0)
    :param max_chars: Maximum characters to return (default: 10000, hard cap: 100000)
    :return: JSON with the file's id, filename, content, and pagination metadata if truncated
    """
    if __request__ is None:
        return json.dumps({'error': 'Request context not available'})

    if not __user__:
        return json.dumps({'error': 'User context not available'})

    # Coerce parameters from LLM tool calls (may come as strings)
    if isinstance(offset, str):
        try:
            offset = int(offset)
        except ValueError:
            offset = 0
    if isinstance(max_chars, str):
        try:
            max_chars = int(max_chars)
        except ValueError:
            max_chars = DEFAULT_VIEW_FILE_MAX_CHARS

    # Enforce hard cap
    max_chars = min(max(max_chars, 1), MAX_VIEW_FILE_CHARS)
    offset = max(offset, 0)

    try:
        from open_webui.models.files import Files
        from open_webui.models.knowledge import Knowledges
        from open_webui.models.access_grants import AccessGrants

        user_id = __user__.get('id')
        user_role = __user__.get('role', 'user')
        user_group_ids = [group.id for group in Groups.get_groups_by_member_id(user_id)]

        file = Files.get_file_by_id(file_id)
        if not file:
            return json.dumps({'error': 'File not found'})

        # Check access via any KB containing this file
        knowledges = Knowledges.get_knowledges_by_file_id(file_id)
        has_knowledge_access = False
        knowledge_info = None

        for knowledge_base in knowledges:
            if (
                user_role == 'admin'
                or knowledge_base.user_id == user_id
                or AccessGrants.has_access(
                    user_id=user_id,
                    resource_type='knowledge',
                    resource_id=knowledge_base.id,
                    permission='read',
                    user_group_ids=set(user_group_ids),
                )
            ):
                has_knowledge_access = True
                knowledge_info = {'id': knowledge_base.id, 'name': knowledge_base.name}
                break

        if not has_knowledge_access:
            if file.user_id != user_id and user_role != 'admin':
                return json.dumps({'error': 'Access denied'})

        content = ''
        if file.data:
            content = file.data.get('content', '')

        total_chars = len(content)
        sliced = content[offset : offset + max_chars]
        is_truncated = (offset + len(sliced)) < total_chars

        result = {
            'id': file.id,
            'filename': file.filename,
            'content': sliced,
            'updated_at': file.updated_at,
            'created_at': file.created_at,
        }
        if knowledge_info:
            result['knowledge_id'] = knowledge_info['id']
            result['knowledge_name'] = knowledge_info['name']

        if is_truncated or offset > 0:
            result['truncated'] = is_truncated
            result['total_chars'] = total_chars
            result['returned_chars'] = len(sliced)
            result['offset'] = offset
            if is_truncated:
                result['next_offset'] = offset + len(sliced)

        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        log.exception(f'view_knowledge_file error: {e}')
        return json.dumps({'error': str(e)})


async def list_knowledge(
    __request__: Request = None,
    __user__: dict = None,
    __model_knowledge__: Optional[list[dict]] = None,
) -> str:
    """
    List all knowledge bases and files attached to the current model.
    Use this first to discover what knowledge is available before querying or reading files.

    :return: JSON with knowledge_bases and files attached to this model
    """
    if __request__ is None:
        return json.dumps({'error': 'Request context not available'})

    if not __user__:
        return json.dumps({'error': 'User context not available'})

    if not __model_knowledge__:
        return json.dumps({'knowledge_bases': [], 'files': []})

    try:
        from open_webui.models.knowledge import Knowledges
        from open_webui.models.files import Files
        from open_webui.models.access_grants import AccessGrants

        user_id = __user__.get('id')
        user_role = __user__.get('role', 'user')
        user_group_ids = [group.id for group in Groups.get_groups_by_member_id(user_id)]

        knowledge_bases = []
        files = []

        for item in __model_knowledge__:
            item_type = item.get('type')
            item_id = item.get('id')

            if item_type == 'collection':
                knowledge = Knowledges.get_knowledge_by_id(item_id)
                if knowledge and (
                    user_role == 'admin'
                    or knowledge.user_id == user_id
                    or AccessGrants.has_access(
                        user_id=user_id,
                        resource_type='knowledge',
                        resource_id=knowledge.id,
                        permission='read',
                        user_group_ids=set(user_group_ids),
                    )
                ):
                    kb_files = Knowledges.get_files_by_id(knowledge.id)
                    file_count = len(kb_files) if kb_files else 0

                    kb_entry = {
                        'id': knowledge.id,
                        'name': knowledge.name,
                        'description': knowledge.description or '',
                        'file_count': file_count,
                    }

                    # Include file listing for each KB
                    if kb_files:
                        kb_entry['files'] = [{'id': f.id, 'filename': f.filename} for f in kb_files]

                    knowledge_bases.append(kb_entry)

            elif item_type == 'file':
                file = Files.get_file_by_id(item_id)
                if file:
                    files.append(
                        {
                            'id': file.id,
                            'filename': file.filename,
                            'updated_at': file.updated_at,
                        }
                    )

        return json.dumps(
            {
                'knowledge_bases': knowledge_bases,
                'files': files,
            },
            ensure_ascii=False,
        )
    except Exception as e:
        log.exception(f'list_knowledge error: {e}')
        return json.dumps({'error': str(e)})


async def query_knowledge_files(
    query: str,
    knowledge_ids: Optional[list[str]] = None,
    count: int = 5,
    __request__: Request = None,
    __user__: dict = None,
    __model_knowledge__: list[dict] = None,
) -> str:
    """
    Search knowledge base files using semantic/vector search. Searches across collections (KBs)
    and individual files that the user has access to.

    :param query: The search query to find semantically relevant content
    :param knowledge_ids: Optional list of KB ids to limit search to specific knowledge bases
    :param count: Maximum number of results to return (default: 5)
    :return: JSON with relevant chunks containing content, source filename, and relevance score
    """
    if __request__ is None:
        return json.dumps({'error': 'Request context not available'})

    if not __user__:
        return json.dumps({'error': 'User context not available'})

    # Coerce parameters from LLM tool calls (may come as strings)
    if isinstance(count, str):
        try:
            count = int(count)
        except ValueError:
            count = 5  # Default fallback

    # Handle knowledge_ids being string "None", "null", or empty
    if isinstance(knowledge_ids, str):
        if knowledge_ids.lower() in ('none', 'null', ''):
            knowledge_ids = None
        else:
            # Try to parse as JSON array if it looks like one
            try:
                knowledge_ids = json.loads(knowledge_ids)
            except json.JSONDecodeError:
                # Treat as single ID
                knowledge_ids = [knowledge_ids]

    try:
        from open_webui.models.knowledge import Knowledges
        from open_webui.models.files import Files
        from open_webui.retrieval.utils import query_collection
        from open_webui.models.access_grants import AccessGrants

        user_id = __user__.get('id')
        user_role = __user__.get('role', 'user')
        user_group_ids = [group.id for group in Groups.get_groups_by_member_id(user_id)]

        embedding_function = __request__.app.state.EMBEDDING_FUNCTION
        if not embedding_function:
            return json.dumps({'error': 'Embedding function not configured'})

        collection_names = []

        # If model has attached knowledge, use those
        if __model_knowledge__:
            for item in __model_knowledge__:
                item_type = item.get('type')
                item_id = item.get('id')

                if item_type == 'collection':
                    # Knowledge base - use KB ID as collection name
                    knowledge = Knowledges.get_knowledge_by_id(item_id)
                    if knowledge and (
                        user_role == 'admin'
                        or knowledge.user_id == user_id
                        or AccessGrants.has_access(
                            user_id=user_id,
                            resource_type='knowledge',
                            resource_id=knowledge.id,
                            permission='read',
                            user_group_ids=set(user_group_ids),
                        )
                    ):
                        collection_names.append(item_id)

                elif item_type == 'file':
                    # Individual file - use file-{id} as collection name
                    file = Files.get_file_by_id(item_id)
                    if file:
                        collection_names.append(f'file-{item_id}')

        elif knowledge_ids:
            # User specified specific KBs
            for knowledge_id in knowledge_ids:
                knowledge = Knowledges.get_knowledge_by_id(knowledge_id)
                if knowledge and (
                    user_role == 'admin'
                    or knowledge.user_id == user_id
                    or AccessGrants.has_access(
                        user_id=user_id,
                        resource_type='knowledge',
                        resource_id=knowledge.id,
                        permission='read',
                        user_group_ids=set(user_group_ids),
                    )
                ):
                    collection_names.append(knowledge_id)
        else:
            # No model knowledge and no specific IDs - search all accessible KBs
            result = Knowledges.search_knowledge_bases(
                user_id,
                filter={
                    'query': '',
                    'user_id': user_id,
                    'group_ids': user_group_ids,
                },
                skip=0,
                limit=50,
            )
            collection_names = [knowledge_base.id for knowledge_base in result.items]

        chunks = []

        # Query vector collections if any
        if collection_names:
            query_results = await query_collection(
                __request__,
                collection_names=collection_names,
                queries=[query],
                embedding_function=embedding_function,
                k=count,
            )

            if query_results and 'documents' in query_results:
                documents = query_results.get('documents', [[]])[0]
                metadatas = query_results.get('metadatas', [[]])[0]
                distances = query_results.get('distances', [[]])[0]

                for idx, doc in enumerate(documents):
                    chunk_info = {
                        'content': doc,
                        'source': metadatas[idx].get('source', metadatas[idx].get('name', 'Unknown')),
                        'file_id': metadatas[idx].get('file_id', ''),
                    }
                    if idx < len(distances):
                        chunk_info['distance'] = distances[idx]
                    chunks.append(chunk_info)

        # Limit to requested count
        chunks = chunks[:count]

        return json.dumps(chunks, ensure_ascii=False)
    except Exception as e:
        log.exception(f'query_knowledge_files error: {e}')
        return json.dumps({'error': str(e)})


async def query_knowledge_bases(
    query: str,
    count: int = 5,
    __request__: Request = None,
    __user__: dict = None,
) -> str:
    """
    Search knowledge bases by semantic similarity to query.
    Finds KBs whose name/description match the meaning of your query.
    Use this to discover relevant knowledge bases before querying their files.

    :param query: Natural language query describing what you're looking for
    :param count: Maximum results (default: 5)
    :return: JSON with matching KBs (id, name, description, similarity)
    """
    if __request__ is None:
        return json.dumps({'error': 'Request context not available'})

    if not __user__:
        return json.dumps({'error': 'User context not available'})

    try:
        import heapq
        from open_webui.models.knowledge import Knowledges
        from open_webui.routers.knowledge import KNOWLEDGE_BASES_COLLECTION
        from open_webui.retrieval.vector.factory import VECTOR_DB_CLIENT

        user_id = __user__.get('id')
        user_group_ids = [group.id for group in Groups.get_groups_by_member_id(user_id)]
        query_embedding = await __request__.app.state.EMBEDDING_FUNCTION(query)

        # Min-heap of (distance, knowledge_base_id) - only holds top `count` results
        top_results_heap = []
        seen_ids = set()
        page_offset = 0
        page_size = 100

        while True:
            accessible_knowledge_bases = Knowledges.search_knowledge_bases(
                user_id,
                filter={'user_id': user_id, 'group_ids': user_group_ids},
                skip=page_offset,
                limit=page_size,
            )

            if not accessible_knowledge_bases.items:
                break

            accessible_ids = [kb.id for kb in accessible_knowledge_bases.items]

            search_results = VECTOR_DB_CLIENT.search(
                collection_name=KNOWLEDGE_BASES_COLLECTION,
                vectors=[query_embedding],
                filter={'knowledge_base_id': {'$in': accessible_ids}},
                limit=count,
            )

            if search_results and search_results.ids and search_results.ids[0]:
                result_ids = search_results.ids[0]
                result_distances = search_results.distances[0] if search_results.distances else [0] * len(result_ids)

                for knowledge_base_id, distance in zip(result_ids, result_distances):
                    if knowledge_base_id in seen_ids:
                        continue
                    seen_ids.add(knowledge_base_id)

                    if len(top_results_heap) < count:
                        heapq.heappush(top_results_heap, (distance, knowledge_base_id))
                    elif distance > top_results_heap[0][0]:
                        heapq.heapreplace(top_results_heap, (distance, knowledge_base_id))

            page_offset += page_size
            if len(accessible_knowledge_bases.items) < page_size:
                break
            if page_offset >= MAX_KNOWLEDGE_BASE_SEARCH_ITEMS:
                break

        # Sort by distance descending (best first) and fetch KB details
        sorted_results = sorted(top_results_heap, key=lambda x: x[0], reverse=True)

        matching_knowledge_bases = []
        for distance, knowledge_base_id in sorted_results:
            knowledge_base = Knowledges.get_knowledge_by_id(knowledge_base_id)
            if knowledge_base:
                matching_knowledge_bases.append(
                    {
                        'id': knowledge_base.id,
                        'name': knowledge_base.name,
                        'description': knowledge_base.description or '',
                        'similarity': round(distance, 4),
                    }
                )

        return json.dumps(matching_knowledge_bases, ensure_ascii=False)

    except Exception as e:
        log.exception(f'query_knowledge_bases error: {e}')
        return json.dumps({'error': str(e)})


# =============================================================================
# SKILLS TOOLS
# =============================================================================


async def view_skill(
    name: str,
    __request__: Request = None,
    __user__: dict = None,
) -> str:
    """
    Load the full instructions of a skill by its name from the available skills manifest.
    Use this when you need detailed instructions for a skill listed in <available_skills>.

    :param name: The name of the skill to load (as shown in the manifest)
    :return: The full skill instructions as markdown content
    """
    if __request__ is None:
        return json.dumps({'error': 'Request context not available'})

    if not __user__:
        return json.dumps({'error': 'User context not available'})

    try:
        from open_webui.models.skills import Skills
        from open_webui.models.access_grants import AccessGrants

        user_id = __user__.get('id')

        # Direct DB lookup by unique name
        skill = Skills.get_skill_by_name(name)

        if not skill or not skill.is_active:
            return json.dumps({'error': f"Skill '{name}' not found"})

        # Check user access
        user_role = __user__.get('role', 'user')
        if user_role != 'admin' and skill.user_id != user_id:
            user_group_ids = [group.id for group in Groups.get_groups_by_member_id(user_id)]
            if not AccessGrants.has_access(
                user_id=user_id,
                resource_type='skill',
                resource_id=skill.id,
                permission='read',
                user_group_ids=set(user_group_ids),
            ):
                return json.dumps({'error': 'Access denied'})

        return json.dumps(
            {
                'name': skill.name,
                'content': skill.content,
            },
            ensure_ascii=False,
        )
    except Exception as e:
        log.exception(f'view_skill error: {e}')
        return json.dumps({'error': str(e)})
