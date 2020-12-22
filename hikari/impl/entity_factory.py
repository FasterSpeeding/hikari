# -*- coding: utf-8 -*-
# cython: language_level=3
# Copyright (c) 2020 Nekokatt
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""Basic implementation of an entity factory for general bots and HTTP apps."""

from __future__ import annotations

__all__: typing.List[str] = ["EntityFactoryImpl"]

import datetime
import typing

import marshie

from hikari import applications as application_models
from hikari import audit_logs as audit_log_models
from hikari import channels as channel_models
from hikari import colors as color_models
from hikari import embeds as embed_models
from hikari import emojis as emoji_models
from hikari import files
from hikari import guilds as guild_models
from hikari import invites as invite_models
from hikari import messages as message_models
from hikari import permissions as permission_models
from hikari import presences as presence_models
from hikari import sessions as gateway_models
from hikari import snowflakes
from hikari import templates as template_models
from hikari import traits
from hikari import undefined
from hikari import users as user_models
from hikari import voices as voice_models
from hikari import webhooks as webhook_models
from hikari.api import entity_factory
from hikari.internal import data_binding
from hikari.internal import time

_DEFAULT_MAX_PRESENCES: typing.Final[int] = 25000


def _deserialize_seconds_timedelta(seconds: typing.Union[str, int]) -> datetime.timedelta:
    return datetime.timedelta(seconds=int(seconds))


def _deserialize_day_timedelta(days: typing.Union[str, int]) -> datetime.timedelta:
    return datetime.timedelta(days=int(days))


def _deserialize_max_uses(age: int) -> typing.Optional[int]:
    return age if age > 0 else None


def _deserialize_max_age(seconds: int) -> typing.Optional[datetime.timedelta]:
    return datetime.timedelta(seconds=seconds) if seconds > 0 else None


class EntityFactoryImpl(entity_factory.EntityFactory):
    """Standard implementation for a serializer/deserializer.

    This will convert objects to/from JSON compatible representations.
    """

    __slots__: typing.Sequence[str] = (
        "_app",
        "_marshaller",
        "_audit_log_entry_converters",
        "_audit_log_event_mapping",
        "_dm_channel_type_mapping",
        "_guild_channel_type_mapping",
    )

    def __init__(self, app: traits.RESTAware) -> None:
        self._app = app
        self._marshaller = marshie.MapMarshaller(constants={"app": self._app})
        self._audit_log_entry_converters: typing.Mapping[str, typing.Callable[[typing.Any], typing.Any]] = {
            audit_log_models.AuditLogChangeKey.OWNER_ID: snowflakes.Snowflake,
            audit_log_models.AuditLogChangeKey.AFK_CHANNEL_ID: snowflakes.Snowflake,
            audit_log_models.AuditLogChangeKey.AFK_TIMEOUT: _deserialize_seconds_timedelta,
            audit_log_models.AuditLogChangeKey.MFA_LEVEL: guild_models.GuildMFALevel,
            audit_log_models.AuditLogChangeKey.VERIFICATION_LEVEL: guild_models.GuildVerificationLevel,
            audit_log_models.AuditLogChangeKey.EXPLICIT_CONTENT_FILTER: guild_models.GuildExplicitContentFilterLevel,
            audit_log_models.AuditLogChangeKey.DEFAULT_MESSAGE_NOTIFICATIONS: guild_models.GuildMessageNotificationsLevel,
            # noqa: E501 - Line too long
            audit_log_models.AuditLogChangeKey.PRUNE_DELETE_DAYS: _deserialize_day_timedelta,
            audit_log_models.AuditLogChangeKey.WIDGET_CHANNEL_ID: snowflakes.Snowflake,
            audit_log_models.AuditLogChangeKey.POSITION: int,
            audit_log_models.AuditLogChangeKey.BITRATE: int,
            audit_log_models.AuditLogChangeKey.APPLICATION_ID: snowflakes.Snowflake,
            audit_log_models.AuditLogChangeKey.PERMISSIONS: permission_models.Permissions,
            audit_log_models.AuditLogChangeKey.COLOR: color_models.Color,
            audit_log_models.AuditLogChangeKey.ALLOW: permission_models.Permissions,
            audit_log_models.AuditLogChangeKey.DENY: permission_models.Permissions,
            audit_log_models.AuditLogChangeKey.CHANNEL_ID: snowflakes.Snowflake,
            audit_log_models.AuditLogChangeKey.INVITER_ID: snowflakes.Snowflake,
            audit_log_models.AuditLogChangeKey.MAX_USES: _deserialize_max_uses,
            audit_log_models.AuditLogChangeKey.USES: int,
            audit_log_models.AuditLogChangeKey.MAX_AGE: _deserialize_max_age,
            audit_log_models.AuditLogChangeKey.ID: snowflakes.Snowflake,
            audit_log_models.AuditLogChangeKey.TYPE: str,
            audit_log_models.AuditLogChangeKey.ENABLE_EMOTICONS: bool,
            audit_log_models.AuditLogChangeKey.EXPIRE_BEHAVIOR: guild_models.IntegrationExpireBehaviour,
            audit_log_models.AuditLogChangeKey.EXPIRE_GRACE_PERIOD: _deserialize_day_timedelta,
            audit_log_models.AuditLogChangeKey.RATE_LIMIT_PER_USER: _deserialize_seconds_timedelta,
            audit_log_models.AuditLogChangeKey.SYSTEM_CHANNEL_ID: snowflakes.Snowflake,
            audit_log_models.AuditLogChangeKey.ADD_ROLE_TO_MEMBER: self._deserialize_audit_log_change_roles,
            audit_log_models.AuditLogChangeKey.REMOVE_ROLE_FROM_MEMBER: self._deserialize_audit_log_change_roles,
            audit_log_models.AuditLogChangeKey.PERMISSION_OVERWRITES: self._deserialize_audit_log_overwrites,
        }
        self._audit_log_event_mapping: typing.Mapping[
            typing.Union[int, audit_log_models.AuditLogEventType],
            typing.Callable[[data_binding.JSONObject], audit_log_models.BaseAuditLogEntryInfo],
        ] = {
            audit_log_models.AuditLogEventType.CHANNEL_OVERWRITE_CREATE: self._deserialize_channel_overwrite_entry_info,
            audit_log_models.AuditLogEventType.CHANNEL_OVERWRITE_UPDATE: self._deserialize_channel_overwrite_entry_info,
            audit_log_models.AuditLogEventType.CHANNEL_OVERWRITE_DELETE: self._deserialize_channel_overwrite_entry_info,
            audit_log_models.AuditLogEventType.MESSAGE_PIN: self._deserialize_message_pin_entry_info,
            audit_log_models.AuditLogEventType.MESSAGE_UNPIN: self._deserialize_message_pin_entry_info,
            audit_log_models.AuditLogEventType.MEMBER_PRUNE: self._deserialize_member_prune_entry_info,
            audit_log_models.AuditLogEventType.MESSAGE_BULK_DELETE: self._deserialize_message_bulk_delete_entry_info,
            audit_log_models.AuditLogEventType.MESSAGE_DELETE: self._deserialize_message_delete_entry_info,
            audit_log_models.AuditLogEventType.MEMBER_DISCONNECT: self._deserialize_member_disconnect_entry_info,
            audit_log_models.AuditLogEventType.MEMBER_MOVE: self._deserialize_member_move_entry_info,
        }
        self._dm_channel_type_mapping = {
            channel_models.ChannelType.DM: self.deserialize_dm,
            channel_models.ChannelType.GROUP_DM: self.deserialize_group_dm,
        }
        self._guild_channel_type_mapping = {
            channel_models.ChannelType.GUILD_CATEGORY: self.deserialize_guild_category,
            channel_models.ChannelType.GUILD_TEXT: self.deserialize_guild_text_channel,
            channel_models.ChannelType.GUILD_NEWS: self.deserialize_guild_news_channel,
            channel_models.ChannelType.GUILD_STORE: self.deserialize_guild_store_channel,
            channel_models.ChannelType.GUILD_VOICE: self.deserialize_guild_voice_channel,
        }

    ######################
    # APPLICATION MODELS #
    ######################

    def deserialize_own_connection(self, payload: data_binding.JSONObject) -> application_models.OwnConnection:
        return self._marshaller.decode(application_models.OwnConnection, payload)

    def deserialize_own_guild(self, payload: data_binding.JSONObject) -> application_models.OwnGuild:
        return self._marshaller.decode(application_models.OwnGuild, payload)

    def deserialize_application(self, payload: data_binding.JSONObject) -> application_models.Application:
        return self._marshaller.decode(application_models.Application, payload)

    #####################
    # AUDIT LOGS MODELS #
    #####################

    def _deserialize_audit_log_change_roles(
        self, payload: data_binding.JSONArray
    ) -> typing.Mapping[snowflakes.Snowflake, guild_models.PartialRole]:
        roles = {}
        for role_payload in payload:
            role = guild_models.PartialRole(
                app=self._app, id=snowflakes.Snowflake(role_payload["id"]), name=role_payload["name"]
            )
            roles[role.id] = role

        return roles

    def _deserialize_audit_log_overwrites(
        self, payload: data_binding.JSONArray
    ) -> typing.Mapping[snowflakes.Snowflake, channel_models.PermissionOverwrite]:
        return {
            snowflakes.Snowflake(overwrite["id"]): self.deserialize_permission_overwrite(overwrite)
            for overwrite in payload
        }

    def _deserialize_channel_overwrite_entry_info(
        self,
        payload: data_binding.JSONObject,
    ) -> audit_log_models.ChannelOverwriteEntryInfo:
        return audit_log_models.ChannelOverwriteEntryInfo(
            app=self._app,
            id=snowflakes.Snowflake(payload["id"]),
            type=channel_models.PermissionOverwriteType(payload["type"]),
            role_name=payload.get("role_name"),
        )

    def _deserialize_message_pin_entry_info(
        self, payload: data_binding.JSONObject
    ) -> audit_log_models.MessagePinEntryInfo:
        return audit_log_models.MessagePinEntryInfo(
            app=self._app,
            channel_id=snowflakes.Snowflake(payload["channel_id"]),
            message_id=snowflakes.Snowflake(payload["message_id"]),
        )

    def _deserialize_member_prune_entry_info(
        self, payload: data_binding.JSONObject
    ) -> audit_log_models.MemberPruneEntryInfo:
        return audit_log_models.MemberPruneEntryInfo(
            app=self._app,
            delete_member_days=datetime.timedelta(days=int(payload["delete_member_days"])),
            members_removed=int(payload["members_removed"]),
        )

    def _deserialize_message_bulk_delete_entry_info(
        self,
        payload: data_binding.JSONObject,
    ) -> audit_log_models.MessageBulkDeleteEntryInfo:
        return audit_log_models.MessageBulkDeleteEntryInfo(app=self._app, count=int(payload["count"]))

    def _deserialize_message_delete_entry_info(
        self,
        payload: data_binding.JSONObject,
    ) -> audit_log_models.MessageDeleteEntryInfo:
        return audit_log_models.MessageDeleteEntryInfo(
            app=self._app, channel_id=snowflakes.Snowflake(payload["channel_id"]), count=int(payload["count"])
        )

    def _deserialize_member_disconnect_entry_info(
        self,
        payload: data_binding.JSONObject,
    ) -> audit_log_models.MemberDisconnectEntryInfo:
        return audit_log_models.MemberDisconnectEntryInfo(app=self._app, count=int(payload["count"]))

    def _deserialize_member_move_entry_info(
        self, payload: data_binding.JSONObject
    ) -> audit_log_models.MemberMoveEntryInfo:
        return audit_log_models.MemberMoveEntryInfo(
            app=self._app, channel_id=snowflakes.Snowflake(payload["channel_id"]), count=int(payload["count"])
        )

    def _deserialize_unrecognised_audit_log_entry_info(
        self,
        payload: data_binding.JSONObject,
    ) -> audit_log_models.UnrecognisedAuditLogEntryInfo:
        return audit_log_models.UnrecognisedAuditLogEntryInfo(payload=payload)

    def deserialize_audit_log(self, payload: data_binding.JSONObject) -> audit_log_models.AuditLog:
        entries = {}
        for entry_payload in payload["audit_log_entries"]:
            entry_id = snowflakes.Snowflake(entry_payload["id"])

            changes = []
            if (change_payloads := entry_payload.get("changes")) is not None:
                for change_payload in change_payloads:
                    key: typing.Union[audit_log_models.AuditLogChangeKey, str]
                    key = audit_log_models.AuditLogChangeKey(change_payload["key"])

                    new_value: typing.Any = change_payload.get("new_value")
                    old_value: typing.Any = change_payload.get("old_value")
                    if value_converter := self._audit_log_entry_converters.get(key):
                        new_value = value_converter(new_value) if new_value is not None else None
                        old_value = value_converter(old_value) if old_value is not None else None

                    changes.append(audit_log_models.AuditLogChange(key=key, new_value=new_value, old_value=old_value))

            target_id: typing.Optional[snowflakes.Snowflake] = None
            if (raw_target_id := entry_payload["target_id"]) is not None:
                target_id = snowflakes.Snowflake(raw_target_id)

            user_id: typing.Optional[snowflakes.Snowflake] = None
            if (raw_user_id := entry_payload["user_id"]) is not None:
                user_id = snowflakes.Snowflake(raw_user_id)

            action_type: typing.Union[audit_log_models.AuditLogEventType, int]
            action_type = audit_log_models.AuditLogEventType(entry_payload["action_type"])

            options: typing.Optional[audit_log_models.BaseAuditLogEntryInfo] = None
            if (raw_option := entry_payload.get("options")) is not None:
                option_converter = (
                    self._audit_log_event_mapping.get(action_type)
                    or self._deserialize_unrecognised_audit_log_entry_info  # noqa: W503
                )
                options = option_converter(raw_option)

            entries[entry_id] = audit_log_models.AuditLogEntry(
                app=self._app,
                id=entry_id,
                target_id=target_id,
                changes=changes,
                user_id=user_id,
                action_type=action_type,
                options=options,
                reason=entry_payload.get("reason"),
            )

        integrations = {
            snowflakes.Snowflake(integration["id"]): self.deserialize_partial_integration(integration)
            for integration in payload["integrations"]
        }
        users = {snowflakes.Snowflake(user["id"]): self.deserialize_user(user) for user in payload["users"]}
        webhooks = {
            snowflakes.Snowflake(webhook["id"]): self.deserialize_webhook(webhook) for webhook in payload["webhooks"]
        }
        return audit_log_models.AuditLog(entries=entries, integrations=integrations, users=users, webhooks=webhooks)

    ##################
    # CHANNEL MODELS #
    ##################

    def deserialize_channel_follow(self, payload: data_binding.JSONObject) -> channel_models.ChannelFollow:
        return self._marshaller.decode(channel_models.ChannelFollow, payload)

    def deserialize_permission_overwrite(self, payload: data_binding.JSONObject) -> channel_models.PermissionOverwrite:
        return self._marshaller.decode(channel_models.PermissionOverwrite, payload)

    def serialize_permission_overwrite(self, overwrite: channel_models.PermissionOverwrite) -> data_binding.JSONObject:
        # https://github.com/discord/discord-api-docs/pull/1843/commits/470677363ba88fbc1fe79228821146c6d6b488b9
        # allow and deny can be strings instead now.
        # TODO: typing lol
        return self._marshaller.encode(overwrite)

    def deserialize_partial_channel(self, payload: data_binding.JSONObject) -> channel_models.PartialChannel:
        return self._marshaller.decode(channel_models.PartialChannel, payload)

    def deserialize_dm(self, payload: data_binding.JSONObject) -> channel_models.DMChannel:
        return self._marshaller.decode(channel_models.DMChannel, payload)

    def deserialize_group_dm(self, payload: data_binding.JSONObject) -> channel_models.GroupDMChannel:
        return self._marshaller.decode(channel_models.GroupDMChannel, payload)

    def deserialize_guild_category(
        self,
        payload: data_binding.JSONObject,
        *,
        guild_id: undefined.UndefinedOr[snowflakes.Snowflake] = undefined.UNDEFINED,
    ) -> channel_models.GuildCategory:
        if guild_id is undefined.UNDEFINED:
            guild_id = snowflakes.Snowflake(payload["guild_id"])

        return self._marshaller.decode(channel_models.GuildCategory, payload, guild_id=guild_id)

    def deserialize_guild_text_channel(
        self,
        payload: data_binding.JSONObject,
        *,
        guild_id: undefined.UndefinedOr[snowflakes.Snowflake] = undefined.UNDEFINED,
    ) -> channel_models.GuildTextChannel:
        if guild_id is undefined.UNDEFINED:
            guild_id = snowflakes.Snowflake(payload["guild_id"])

        return self._marshaller.decode(channel_models.GuildTextChannel, payload, guild_id=guild_id)

    def deserialize_guild_news_channel(
        self,
        payload: data_binding.JSONObject,
        *,
        guild_id: undefined.UndefinedOr[snowflakes.Snowflake] = undefined.UNDEFINED,
    ) -> channel_models.GuildNewsChannel:
        if guild_id is undefined.UNDEFINED:
            guild_id = snowflakes.Snowflake(payload["guild_id"])

        return self._marshaller.decode(channel_models.GuildNewsChannel, payload, guild_id=guild_id)

    def deserialize_guild_store_channel(
        self,
        payload: data_binding.JSONObject,
        *,
        guild_id: undefined.UndefinedOr[snowflakes.Snowflake] = undefined.UNDEFINED,
    ) -> channel_models.GuildStoreChannel:
        if guild_id is undefined.UNDEFINED:
            guild_id = snowflakes.Snowflake(payload["guild_id"])

        return self._marshaller.decode(channel_models.GuildStoreChannel, payload, guild_id=guild_id)

    def deserialize_guild_voice_channel(
        self,
        payload: data_binding.JSONObject,
        *,
        guild_id: undefined.UndefinedOr[snowflakes.Snowflake] = undefined.UNDEFINED,
    ) -> channel_models.GuildVoiceChannel:
        if guild_id is undefined.UNDEFINED:
            guild_id = snowflakes.Snowflake(payload["guild_id"])

        return self._marshaller.decode(channel_models.GuildVoiceChannel, payload, guild_id=guild_id)

    def deserialize_channel(
        self,
        payload: data_binding.JSONObject,
        *,
        guild_id: undefined.UndefinedOr[snowflakes.Snowflake] = undefined.UNDEFINED,
    ) -> channel_models.PartialChannel:
        channel_type = payload["type"]
        if channel_model := self._guild_channel_type_mapping.get(channel_type):
            return channel_model(payload, guild_id=guild_id)

        return self._dm_channel_type_mapping[channel_type](payload)

    ################
    # EMBED MODELS #
    ################

    def deserialize_embed(self, payload: data_binding.JSONObject) -> embed_models.Embed:
        # Keep these separate to aid debugging later.
        title = payload.get("title")
        description = payload.get("description")
        url = payload.get("url")
        color = color_models.Color(payload["color"]) if "color" in payload else None
        timestamp = time.iso8601_datetime_string_to_datetime(payload["timestamp"]) if "timestamp" in payload else None
        fields: typing.Optional[typing.MutableSequence[embed_models.EmbedField]] = None

        image: typing.Optional[embed_models.EmbedImage[files.AsyncReader]] = None
        if image_payload := payload.get("image"):
            image = embed_models.EmbedImage(
                resource=files.ensure_resource(image_payload.get("url")),
                proxy_resource=files.ensure_resource(image_payload.get("proxy_url")),
                height=image_payload.get("height"),
                width=image_payload.get("width"),
            )

        thumbnail: typing.Optional[embed_models.EmbedImage[files.AsyncReader]] = None
        if thumbnail_payload := payload.get("thumbnail"):
            thumbnail = embed_models.EmbedImage(
                resource=files.ensure_resource(thumbnail_payload.get("url")),
                proxy_resource=files.ensure_resource(thumbnail_payload.get("proxy_url")),
                height=thumbnail_payload.get("height"),
                width=thumbnail_payload.get("width"),
            )

        video: typing.Optional[embed_models.EmbedVideo[files.AsyncReader]] = None
        if video_payload := payload.get("video"):
            video = embed_models.EmbedVideo(
                resource=files.ensure_resource(video_payload.get("url")),
                height=video_payload.get("height"),
                width=video_payload.get("width"),
            )

        provider: typing.Optional[embed_models.EmbedProvider] = None
        if provider_payload := payload.get("provider"):
            provider = embed_models.EmbedProvider(name=provider_payload.get("name"), url=provider_payload.get("url"))

        icon: typing.Optional[embed_models.EmbedResourceWithProxy[files.AsyncReader]]
        author: typing.Optional[embed_models.EmbedAuthor] = None
        if author_payload := payload.get("author"):
            icon = None
            if "icon_url" in author_payload:
                icon = embed_models.EmbedResourceWithProxy(
                    resource=files.ensure_resource(author_payload.get("icon_url")),
                    proxy_resource=files.ensure_resource(author_payload.get("proxy_icon_url")),
                )

            author = embed_models.EmbedAuthor(
                name=author_payload.get("name"),
                url=author_payload.get("url"),
                icon=icon,
            )

        footer: typing.Optional[embed_models.EmbedFooter] = None
        if footer_payload := payload.get("footer"):
            icon = None
            if "icon_url" in footer_payload:
                icon = embed_models.EmbedResourceWithProxy(
                    resource=files.ensure_resource(footer_payload.get("icon_url")),
                    proxy_resource=files.ensure_resource(footer_payload.get("proxy_icon_url")),
                )

            footer = embed_models.EmbedFooter(text=footer_payload.get("text"), icon=icon)

        if fields_array := payload.get("fields"):
            fields = []
            for field_payload in fields_array:
                field = embed_models.EmbedField(
                    name=field_payload["name"],
                    value=field_payload["value"],
                    inline=field_payload.get("inline", False),
                )
                fields.append(field)

        return embed_models.Embed.from_received_embed(
            title=title,
            description=description,
            url=url,
            color=color,
            timestamp=timestamp,
            image=image,
            thumbnail=thumbnail,
            video=video,
            provider=provider,
            author=author,
            footer=footer,
            fields=fields,
        )

    def serialize_embed(  # noqa: C901
        self,
        embed: embed_models.Embed,
    ) -> typing.Tuple[data_binding.JSONObject, typing.List[files.Resource[files.AsyncReader]]]:

        payload: data_binding.JSONObject = {}
        uploads: typing.List[files.Resource[files.AsyncReader]] = []

        if embed.title is not None:
            payload["title"] = embed.title

        if embed.description is not None:
            payload["description"] = embed.description

        if embed.url is not None:
            payload["url"] = embed.url

        if embed.timestamp is not None:
            payload["timestamp"] = embed.timestamp.isoformat()

        if embed.color is not None:
            payload["color"] = int(embed.color)

        if embed.footer is not None:
            footer_payload: data_binding.JSONObject = {}

            if embed.footer.text is not None:
                footer_payload["text"] = embed.footer.text

            if embed.footer.icon is not None:
                if not isinstance(embed.footer.icon.resource, files.WebResource):
                    uploads.append(embed.footer.icon.resource)

                footer_payload["icon_url"] = embed.footer.icon.url

            payload["footer"] = footer_payload

        if embed.image is not None:
            image_payload: data_binding.JSONObject = {}

            if not isinstance(embed.image.resource, files.WebResource):
                uploads.append(embed.image.resource)

            image_payload["url"] = embed.image.url
            payload["image"] = image_payload

        if embed.thumbnail is not None:
            thumbnail_payload: data_binding.JSONObject = {}

            if not isinstance(embed.thumbnail.resource, files.WebResource):
                uploads.append(embed.thumbnail.resource)

            thumbnail_payload["url"] = embed.thumbnail.url
            payload["thumbnail"] = thumbnail_payload

        if embed.author is not None:
            author_payload: data_binding.JSONObject = {}

            if embed.author.name is not None:
                author_payload["name"] = embed.author.name

            if embed.author.url is not None:
                author_payload["url"] = embed.author.url

            if embed.author.icon is not None:
                if not isinstance(embed.author.icon.resource, files.WebResource):
                    uploads.append(embed.author.icon.resource)
                author_payload["icon_url"] = embed.author.icon.url

            payload["author"] = author_payload

        if embed.fields:
            field_payloads: data_binding.JSONArray = []
            for i, field in enumerate(embed.fields):

                # Yep, this is technically two unreachable branches. However, this is an incredibly
                # common mistake to make when working with embeds and not using a static type
                # checker, so I have added these as additional safeguards for UX and ease
                # of debugging. The case that there are `None` should be detected immediately by
                # static type checkers, regardless.

                name = str(field.name) if field.name is not None else None  # type: ignore[unreachable]
                value = str(field.value) if field.value is not None else None  # type: ignore[unreachable]

                if name is None:
                    raise TypeError(f"in embed.fields[{i}].name - cannot have `None`")
                if not name:
                    raise TypeError(f"in embed.fields[{i}].name - cannot have empty string")
                if not name.strip():
                    raise TypeError(f"in embed.fields[{i}].name - cannot have only whitespace")

                if value is None:
                    raise TypeError(f"in embed.fields[{i}].value - cannot have `None`")
                if not value:
                    raise TypeError(f"in embed.fields[{i}].value - cannot have empty string")
                if not value.strip():
                    raise TypeError(f"in embed.fields[{i}].value - cannot have only whitespace")

                # Name and value always have to be specified; we can always
                # send a default `inline` value also just to keep this simpler.
                field_payloads.append({"name": name, "value": value, "inline": field.is_inline})
            payload["fields"] = field_payloads

        return payload, uploads

    ################
    # EMOJI MODELS #
    ################

    def deserialize_unicode_emoji(self, payload: data_binding.JSONObject) -> emoji_models.UnicodeEmoji:
        return self._marshaller.decode(emoji_models.UnicodeEmoji, payload)

    def deserialize_custom_emoji(self, payload: data_binding.JSONObject) -> emoji_models.CustomEmoji:
        return self._marshaller.decode(emoji_models.CustomEmoji, payload)

    def deserialize_known_custom_emoji(
        self, payload: data_binding.JSONObject, *, guild_id: snowflakes.Snowflake
    ) -> emoji_models.KnownCustomEmoji:
        return self._marshaller.decode(emoji_models.KnownCustomEmoji, payload, guild_id=guild_id)

    def deserialize_emoji(
        self, payload: data_binding.JSONObject
    ) -> typing.Union[emoji_models.UnicodeEmoji, emoji_models.CustomEmoji]:
        if payload.get("id") is not None:
            return self.deserialize_custom_emoji(payload)

        return self.deserialize_unicode_emoji(payload)

    ##################
    # GATEWAY MODELS #
    ##################

    def deserialize_gateway_bot(self, payload: data_binding.JSONObject) -> gateway_models.GatewayBot:
        return self._marshaller.decode(gateway_models.GatewayBot, payload)

    ################
    # GUILD MODELS #
    ################

    def deserialize_guild_widget(self, payload: data_binding.JSONObject) -> guild_models.GuildWidget:
        return self._marshaller.decode(guild_models.GuildWidget, payload)

    def deserialize_member(
        self,
        payload: data_binding.JSONObject,
        *,
        user: undefined.UndefinedOr[user_models.User] = undefined.UNDEFINED,
        guild_id: undefined.UndefinedOr[snowflakes.Snowflake] = undefined.UNDEFINED,
    ) -> guild_models.Member:

        if user is undefined.UNDEFINED:
            user = self.deserialize_user(payload["user"])

        if guild_id is undefined.UNDEFINED:
            guild_id = snowflakes.Snowflake(payload["guild_id"])

        # If Discord ever does start including this here without warning we don't want to duplicate the entry.
        raw_guild_id = str(guild_id)
        if raw_guild_id not in payload["roles"]:
            payload["roles"].append(raw_guild_id)

        member = self._marshaller.decode(guild_models.Member, payload, user=user, guild_id=guild_id)
        return member

    def deserialize_role(
        self,
        payload: data_binding.JSONObject,
        *,
        guild_id: snowflakes.Snowflake,
    ) -> guild_models.Role:
        return self._marshaller.decode(guild_models.Role, payload, guild_id=guild_id)

    def deserialize_partial_integration(self, payload: data_binding.JSONObject) -> guild_models.PartialIntegration:
        return self._marshaller.decode(guild_models.PartialIntegration, payload)

    def deserialize_integration(
        self,
        payload: data_binding.JSONObject,
        *,
        guild_id: undefined.UndefinedOr[snowflakes.Snowflake] = undefined.UNDEFINED,
    ) -> guild_models.Integration:
        if guild_id is undefined.UNDEFINED:
            guild_id = snowflakes.Snowflake(payload["guild_id"])

        return self._marshaller.decode(guild_models.Integration, payload, guild_id=guild_id)

    def deserialize_guild_member_ban(self, payload: data_binding.JSONObject) -> guild_models.GuildMemberBan:
        return guild_models.GuildMemberBan(reason=payload["reason"], user=self.deserialize_user(payload["user"]))

    def deserialize_guild_preview(self, payload: data_binding.JSONObject) -> guild_models.GuildPreview:
        guild_id = snowflakes.Snowflake(payload["id"])
        return self._marshaller.decode(guild_models.GuildPreview, payload, emojis_guild_id=guild_id)

    def deserialize_rest_guild(self, payload: data_binding.JSONObject) -> guild_models.RESTGuild:
        guild_id = snowflakes.Snowflake(payload["id"])
        return self._marshaller.decode(
            guild_models.RESTGuild, payload, _emojis_guild_id=guild_id, _roles_guild_id=guild_id
        )

    def deserialize_gateway_guild(self, payload: data_binding.JSONObject) -> entity_factory.GatewayGuildDefinition:
        guild_id = snowflakes.Snowflake(payload["id"])

        members: typing.Optional[typing.MutableMapping[snowflakes.Snowflake, guild_models.Member]] = None
        if "members" in payload:
            members = {}

            for member_payload in payload["members"]:
                member = self.deserialize_member(member_payload, guild_id=guild_id)
                members[member.user.id] = member

        channels: typing.Optional[typing.MutableMapping[snowflakes.Snowflake, channel_models.GuildChannel]] = None
        if "channels" in payload:
            channels = {}

            for channel_payload in payload["channels"]:
                channel = typing.cast(
                    "channel_models.GuildChannel", self.deserialize_channel(channel_payload, guild_id=guild_id)
                )
                channels[channel.id] = channel

        voice_states: typing.Optional[typing.MutableMapping[snowflakes.Snowflake, voice_models.VoiceState]] = None
        if "voice_states" in payload:
            voice_states = {}
            assert members is not None

            for voice_state_payload in payload["voice_states"]:
                member = members[snowflakes.Snowflake(voice_state_payload["user_id"])]
                voice_state = self.deserialize_voice_state(voice_state_payload, guild_id=guild_id, member=member)
                voice_states[voice_state.user_id] = voice_state

        return self._marshaller.decode(
            entity_factory.GatewayGuildDefinition,
            payload,
            channels=channels,
            members=members,
            voice_states=voice_states,
            presences_guild_id=guild_id,
            roles_guild_id=guild_id,
            emojis_guild_id=guild_id,
        )

    #################
    # INVITE MODELS #
    #################

    def deserialize_vanity_url(self, payload: data_binding.JSONObject) -> invite_models.VanityURL:
        return self._marshaller.decode(invite_models.VanityURL, payload)

    _InviteT = typing.TypeVar("_InviteT", bound=invite_models.Invite)

    def _deserialize_invite(self, cls: typing.Type[_InviteT], payload: data_binding.JSONObject) -> _InviteT:
        channel_id = payload.get("channel_id") or (payload["channel"]["id"] if "channel" in payload else None)

        if channel_id is not None:
            channel_id = snowflakes.Snowflake(channel_id)

        invite = self._marshaller.decode(cls, payload, channel_id=channel_id)

        if invite.guild:
            invite.guild_id = invite.guild.id

        return invite

    def deserialize_invite(self, payload: data_binding.JSONObject) -> invite_models.Invite:
        return self._deserialize_invite(invite_models.Invite, payload)

    def deserialize_invite_with_metadata(self, payload: data_binding.JSONObject) -> invite_models.InviteWithMetadata:
        return self._deserialize_invite(invite_models.InviteWithMetadata, payload)

    ##################
    # MESSAGE MODELS #
    ##################

    def deserialize_partial_message(  # noqa CFQ001 - Function too long
        self, payload: data_binding.JSONObject
    ) -> message_models.PartialMessage:
        author: typing.Optional[user_models.User] = None
        if author_pl := payload.get("author"):
            author = self.deserialize_user(author_pl)

        member: typing.Optional[guild_models.Member] = None
        if "guild_id" in payload:
            guild_id = snowflakes.Snowflake(payload["guild_id"])

            member_pl = payload.get("member")
            if author and member_pl:
                member = self.deserialize_member(member_pl, user=author, guild_id=guild_id)

        embeds: undefined.UndefinedOr[typing.Sequence[embed_models.Embed]] = undefined.UNDEFINED
        if "embeds" in payload:
            embeds = [self.deserialize_embed(embed) for embed in payload["embeds"]]

        reactions: undefined.UndefinedOr[typing.MutableSequence[message_models.Reaction]] = undefined.UNDEFINED
        if "reactions" in payload:
            reactions = []
            for reaction_payload in payload["reactions"]:
                reaction = self._marshaller.decode(
                    message_models.Reaction, reaction_payload, emoji=self.deserialize_emoji(reaction_payload["emoji"])
                )
                reactions.append(reaction)

        message = self._marshaller.decode(
            message_models.PartialMessage, payload, author=author, member=member, embeds=embeds, reactions=reactions
        )

        channels: undefined.UndefinedOr[typing.Mapping[snowflakes.Snowflake, channel_models.PartialChannel]]
        channels = undefined.UNDEFINED
        if raw_channels := payload.get("mention_channels"):
            channels = {c.id: c for c in map(self.deserialize_partial_channel, raw_channels)}

        users: undefined.UndefinedOr[typing.Mapping[snowflakes.Snowflake, user_models.User]]
        users = undefined.UNDEFINED
        if raw_users := payload.get("mentions"):
            users = {u.id: u for u in map(self.deserialize_user, raw_users)}

        role_ids: undefined.UndefinedOr[typing.Sequence[snowflakes.Snowflake]] = undefined.UNDEFINED
        if raw_role_ids := payload.get("mention_roles"):
            role_ids = [snowflakes.Snowflake(i) for i in raw_role_ids]

        everyone = payload.get("mention_everyone", undefined.UNDEFINED)

        message.mentions = message_models.Mentions(
            message=message,
            users=users,
            role_ids=role_ids,
            channels=channels,
            everyone=everyone,
        )

        return message

    def deserialize_message(  # noqa CFQ001 - Function too long
        self, payload: data_binding.JSONObject
    ) -> message_models.Message:
        author = self.deserialize_user(payload["author"])
        member: typing.Optional[guild_models.Member] = None

        if "guild_id" in payload:
            guild_id = snowflakes.Snowflake(payload["guild_id"])

            member_pl = payload.get("member")
            if member_pl:
                member = self.deserialize_member(member_pl, user=author, guild_id=guild_id)

        embeds = [self.deserialize_embed(embed) for embed in payload["embeds"]]

        reactions: typing.MutableSequence[message_models.Reaction] = []
        if "reactions" in payload:
            for reaction_payload in payload["reactions"]:
                reaction = self._marshaller.decode(
                    message_models.Reaction, reaction_payload, emoji=self.deserialize_emoji(reaction_payload["emoji"])
                )
                reactions.append(reaction)

        message = self._marshaller.decode(
            message_models.Message, payload, author=author, member=member, embeds=embeds, reactions=reactions
        )

        channels: typing.Mapping[snowflakes.Snowflake, channel_models.PartialChannel] = {}
        if raw_channels := payload.get("mention_channels"):
            channels = {c.id: c for c in map(self.deserialize_partial_channel, raw_channels)}

        users: typing.Mapping[snowflakes.Snowflake, user_models.User] = {}
        if raw_users := payload.get("mentions"):
            users = {u.id: u for u in map(self.deserialize_user, raw_users)}

        role_ids: typing.Sequence[snowflakes.Snowflake] = []
        if raw_role_ids := payload.get("mention_roles"):
            role_ids = [snowflakes.Snowflake(i) for i in raw_role_ids]

        everyone = payload.get("mention_everyone", False)

        message.mentions = message_models.Mentions(
            message=message,
            users=users,
            role_ids=role_ids,
            channels=channels,
            everyone=everyone,
        )

        return message

    ###################
    # PRESENCE MODELS #
    ###################

    def deserialize_member_presence(  # noqa: CFQ001 - Max function length
        self,
        payload: data_binding.JSONObject,
        *,
        guild_id: undefined.UndefinedOr[snowflakes.Snowflake] = undefined.UNDEFINED,
    ) -> presence_models.MemberPresence:
        if guild_id is undefined.UNDEFINED:
            guild_id = snowflakes.Snowflake(payload["guild_id"])

        activities: typing.List[presence_models.RichActivity] = []
        for activity_payload in payload["activities"]:
            emoji = self.deserialize_emoji(activity_payload["emoji"]) if "emoji" in activity_payload else None
            activities.append(self._marshaller.decode(presence_models.RichActivity, activity_payload, emoji=emoji))

        return self._marshaller.decode(
            presence_models.MemberPresence,
            payload,
            activities=activities,
            guild_id=guild_id,
        )

    ###################
    # TEMPLATE MODELS #
    ###################

    def deserialize_template(self, payload: data_binding.JSONObject) -> template_models.Template:
        source_guild_payload = payload["serialized_source_guild"]
        # For some reason the guild ID isn't on the actual guild object in this special case.
        guild_id = snowflakes.Snowflake(payload["source_guild_id"])
        channels = {}
        for channel_payload in source_guild_payload["channels"]:
            channel = typing.cast(
                "channel_models.GuildChannel", self.deserialize_channel(channel_payload, guild_id=guild_id)
            )
            channels[channel.id] = channel

        return self._marshaller.decode(
            template_models.Template, payload, source_guild_channels=channels, source_guild_id=guild_id
        )

    ###############
    # USER MODELS #
    ###############

    def deserialize_user(self, payload: data_binding.JSONObject) -> user_models.User:
        return self._marshaller.decode(user_models.UserImpl, payload)

    def deserialize_my_user(self, payload: data_binding.JSONObject) -> user_models.OwnUser:
        return self._marshaller.decode(user_models.OwnUser, payload)

    ################
    # VOICE MODELS #
    ################

    def deserialize_voice_state(
        self,
        payload: data_binding.JSONObject,
        *,
        guild_id: undefined.UndefinedOr[snowflakes.Snowflake] = undefined.UNDEFINED,
        member: undefined.UndefinedOr[guild_models.Member] = undefined.UNDEFINED,
    ) -> voice_models.VoiceState:
        if guild_id is undefined.UNDEFINED:
            guild_id = snowflakes.Snowflake(payload["guild_id"])

        if member is undefined.UNDEFINED:
            member = self.deserialize_member(payload["member"], guild_id=guild_id)

        return self._marshaller.decode(voice_models.VoiceState, payload, guild_id=guild_id, member=member)

    def deserialize_voice_region(self, payload: data_binding.JSONObject) -> voice_models.VoiceRegion:
        return self._marshaller.decode(voice_models.VoiceRegion, payload)

    ##################
    # WEBHOOK MODELS #
    ##################

    def deserialize_webhook(self, payload: data_binding.JSONObject) -> webhook_models.Webhook:
        if "source_channel" in payload:
            # In this case the channel type isn't provided as we can safely
            # assume it's a news channel.
            payload["source_channel"]["type"] = channel_models.ChannelType.GUILD_NEWS

        return self._marshaller.decode(webhook_models.Webhook, payload)
