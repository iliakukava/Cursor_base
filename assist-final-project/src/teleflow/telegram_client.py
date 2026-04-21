from __future__ import annotations

import asyncio
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

import socks
from telethon import TelegramClient, utils
from telethon.errors.rpcerrorlist import FloodWaitError, PeerFloodError
from telethon.network.connection.tcpmtproxy import ConnectionTcpMTProxyRandomizedIntermediate
from telethon.tl.functions.messages import GetDialogFiltersRequest, GetPeerDialogsRequest
from telethon.tl.types import DialogFilter, InputDialogPeer, InputPeerChannel

from .models import AppConfig

LOGGER = logging.getLogger(__name__)
TELEGRAM_MAX_MESSAGE_LEN = 3900


def _flush_log_handlers() -> None:
    for handler in logging.root.handlers:
        flush = getattr(handler, "flush", None)
        if flush is not None:
            flush()


def _normalized_channel_id(value: int) -> int:
    return int(str(int(value)).replace("-100", ""))


def _folder_title_str(title: object | None) -> str:
    if title is None:
        return ""
    if isinstance(title, str):
        return title.strip()
    text = getattr(title, "text", None)
    if isinstance(text, str):
        return text.strip()
    return str(title).strip()


@dataclass(slots=True)
class SourceChannel:
    channel_id: int
    title: str
    username: str | None
    folder_id: int
    folder_name: str
    entity: object


@dataclass(slots=True)
class ChannelInboxSnapshot:
    channel_id: int
    folder_id: int
    unread_count: int
    read_inbox_max_id: int
    top_message_id: int


class TgUserClient:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        client_kwargs = self._build_client_kwargs()
        self.client = TelegramClient(
            config.session_name,
            config.api_id,
            config.api_hash,
            **client_kwargs,
        )

    def _build_client_kwargs(self) -> dict:
        bounded = {
            "timeout": self.config.tg_connect_timeout_sec,
            "connection_retries": self.config.tg_connection_retries,
            "retry_delay": self.config.tg_retry_delay_sec,
        }
        if not self.config.tg_proxy_enabled:
            return bounded
        if not self.config.tg_proxy_host or not self.config.tg_proxy_port:
            raise ValueError(
                "TG_PROXY_ENABLED=true, но TG_PROXY_HOST или TG_PROXY_PORT не заполнены."
            )
        if self.config.tg_proxy_type == "socks5":
            return {
                **bounded,
                "proxy": (
                    socks.SOCKS5,
                    self.config.tg_proxy_host,
                    self.config.tg_proxy_port,
                    self.config.tg_proxy_rdns,
                    self.config.tg_proxy_username,
                    self.config.tg_proxy_password,
                ),
            }
        if self.config.tg_proxy_type == "mtproto":
            if not self.config.tg_proxy_secret:
                raise ValueError("Для MTProto заполните TG_PROXY_SECRET.")
            return {
                **bounded,
                "connection": ConnectionTcpMTProxyRandomizedIntermediate,
                "proxy": (
                    self.config.tg_proxy_host,
                    self.config.tg_proxy_port,
                    self.config.tg_proxy_secret,
                ),
            }
        raise ValueError("Поддерживаются TG_PROXY_TYPE=socks5 или mtproto.")

    async def connect(self) -> None:
        total = float(self.config.tg_connect_total_sec)
        LOGGER.info(
            "Telethon: client.connect() (полный цикл до %ss; после TCP идёт обмен с DC через прокси)…",
            int(total),
        )
        _flush_log_handlers()
        try:
            await asyncio.wait_for(self.client.connect(), timeout=total)
        except asyncio.TimeoutError as exc:
            try:
                await self.client.disconnect()
            except Exception:
                LOGGER.exception("Telethon: disconnect после таймаута connect()")
            raise RuntimeError(
                f"client.connect() не завершился за {int(total)}s (часто зависает на этапе после "
                f"«Connection complete»). Проверьте MTProxy/сеть/секрет, попробуйте SOCKS5 или "
                f"увеличьте TG_CONNECT_TOTAL_SEC."
            ) from exc
        LOGGER.info("Telethon: connect() завершён, RPC-проверка авторизации (до %ss)…", self.config.tg_rpc_timeout_sec)
        _flush_log_handlers()
        rpc = float(self.config.tg_rpc_timeout_sec)
        try:
            authorized = await asyncio.wait_for(self.client.is_user_authorized(), timeout=rpc)
        except asyncio.TimeoutError as exc:
            raise RuntimeError(
                f"Telegram не ответил на is_user_authorized за {int(rpc)}s. "
                "Проверьте MTProxy/сеть или увеличьте TG_RPC_TIMEOUT_SEC."
            ) from exc
        if not authorized:
            if not sys.stdin.isatty():
                raise RuntimeError(
                    "Сессия не авторизована, но запуск неинтерактивный. "
                    "Запустите один раз в терминале и введите код Telegram."
                )
            LOGGER.info("Сессия пуста — запрос кода входа (код нужно ввести в этом терминале).")
            await asyncio.wait_for(
                self.client.send_code_request(self.config.phone_number),
                timeout=rpc,
            )
            code = input("Введите код из Telegram: ").strip()
            await asyncio.wait_for(
                self.client.sign_in(self.config.phone_number, code),
                timeout=rpc,
            )
        LOGGER.info("Userbot авторизован")

    async def disconnect(self) -> None:
        await self.client.disconnect()

    async def get_channels_from_folders(self, folder_names: Iterable[str]) -> list[SourceChannel]:
        response = await self.client(GetDialogFiltersRequest())
        filters = getattr(response, "filters", None) or []
        target = {name.strip().lower() for name in folder_names}
        result: dict[int, SourceChannel] = {}

        for item in filters:
            if not isinstance(item, DialogFilter):
                continue
            title = _folder_title_str(item.title).lower()
            if title not in target:
                continue
            include_peers = item.include_peers or []
            folder_id = int(getattr(item, "id", 0) or 0)
            folder_name = _folder_title_str(item.title) or f"folder_{folder_id}"
            for peer in include_peers:
                if not isinstance(peer, InputPeerChannel):
                    continue
                entity = await self.client.get_entity(peer)
                channel_id = getattr(entity, "id", None)
                if channel_id is None:
                    continue
                result[channel_id] = SourceChannel(
                    channel_id=channel_id,
                    title=getattr(entity, "title", str(channel_id)),
                    username=getattr(entity, "username", None),
                    folder_id=folder_id,
                    folder_name=folder_name,
                    entity=entity,
                )

        if not result:
            LOGGER.warning("Каналы по папкам %s не найдены", list(folder_names))
        else:
            LOGGER.info("Найдено каналов в папках: %d", len(result))
        return list(result.values())

    async def get_inbox_snapshots(
        self, channels: list[SourceChannel]
    ) -> dict[int, ChannelInboxSnapshot]:
        if not channels:
            return {}

        channels_by_id = {_normalized_channel_id(item.channel_id): item for item in channels}
        channel_ids = set(channels_by_id.keys())
        snapshots: dict[int, ChannelInboxSnapshot] = {}

        peers: list[InputDialogPeer] = []
        for item in channels:
            inp = await self.client.get_input_entity(item.entity)
            peers.append(InputDialogPeer(peer=inp))

        batch_size = 50
        for off in range(0, len(peers), batch_size):
            batch = peers[off : off + batch_size]
            result = await self.client(GetPeerDialogsRequest(peers=batch))
            for raw in result.dialogs:
                if not hasattr(raw, "peer"):
                    continue
                try:
                    dialog_id = _normalized_channel_id(utils.get_peer_id(raw.peer))
                except (TypeError, ValueError):
                    continue
                if dialog_id not in channel_ids:
                    continue
                source = channels_by_id[dialog_id]
                snapshots[dialog_id] = ChannelInboxSnapshot(
                    channel_id=dialog_id,
                    folder_id=source.folder_id,
                    unread_count=int(getattr(raw, "unread_count", 0) or 0),
                    read_inbox_max_id=int(getattr(raw, "read_inbox_max_id", 0) or 0),
                    top_message_id=int(getattr(raw, "top_message", 0) or 0),
                )

        missing_channels = channel_ids - snapshots.keys()
        if missing_channels:
            LOGGER.warning(
                "Не удалось получить snapshot диалогов для %d каналов",
                len(missing_channels),
            )
        return snapshots

    async def iter_unread_messages(
        self,
        entity: object,
        read_inbox_max_id: int,
        since_dt: datetime,
        max_messages: int,
    ):
        since_utc = since_dt.astimezone(timezone.utc)
        if read_inbox_max_id <= 0:
            LOGGER.warning("read_inbox_max_id пуст или 0, ограничиваемся max_messages=%d", max_messages)
        async for msg in self.client.iter_messages(
            entity,
            reverse=False,
            min_id=max(0, read_inbox_max_id),
            limit=max_messages,
        ):
            if not msg.date:
                continue
            if msg.date.astimezone(timezone.utc) < since_utc:
                break
            if not msg.message:
                continue
            yield msg

    async def mark_channel_read_upto(self, entity: object, max_id: int) -> None:
        if max_id <= 0:
            return
        await self.client.send_read_acknowledge(entity, max_id=max_id)

    async def send_text(self, target: str | int, text: str) -> None:
        chunks = _split_for_telegram(text, TELEGRAM_MAX_MESSAGE_LEN)
        total = len(chunks)
        for idx, chunk in enumerate(chunks, start=1):
            if idx > 1:
                await asyncio.sleep(0.55)
            prefix = f"[{idx}/{total}]\n" if total > 1 else ""
            body = f"{prefix}{chunk}"
            try:
                await self.client.send_message(target, body, link_preview=False)
            except FloodWaitError as exc:
                wait = int(getattr(exc, "seconds", 5)) + 2
                LOGGER.warning(
                    "Telegram FloodWait %ss, пауза перед куском %s/%s…",
                    wait,
                    idx,
                    total,
                )
                await asyncio.sleep(wait)
                await self.client.send_message(target, body, link_preview=False)
            except PeerFloodError:
                LOGGER.error(
                    "Telegram PeerFlood: лимит отправки в этот чат (часто после серии сообщений). "
                    "Подождите или отправьте дайджест в канал (DRY_RUN=false)."
                )
                raise

    async def __aenter__(self) -> "TgUserClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.disconnect()
        await asyncio.sleep(0)


def _split_for_telegram(text: str, max_len: int) -> list[str]:
    if len(text) <= max_len:
        return [text]

    parts: list[str] = []
    remaining = text.strip()
    while remaining:
        if len(remaining) <= max_len:
            parts.append(remaining)
            break

        split_at = remaining.rfind("\n\n", 0, max_len)
        if split_at == -1:
            split_at = remaining.rfind("\n", 0, max_len)
        if split_at == -1:
            split_at = max_len

        chunk = remaining[:split_at].strip()
        if not chunk:
            chunk = remaining[:max_len].strip()
            split_at = max_len

        parts.append(chunk)
        remaining = remaining[split_at:].strip()

    return parts

