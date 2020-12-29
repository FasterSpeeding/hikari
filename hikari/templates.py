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
"""Application and entities that are used to describe guild templates on Discord."""

from __future__ import annotations

__all__: typing.List[str] = ["Template", "TemplateGuild", "TemplateRole", "Templateish"]

import datetime
import typing

import attr
import marshie

from hikari import colors
from hikari import guilds
from hikari import permissions as permissions_
from hikari import snowflakes
from hikari.internal import attr_extensions
from hikari.internal import data_binding
from hikari.internal import time

if typing.TYPE_CHECKING:

    from hikari import channels as channels_
    from hikari import users


@attr_extensions.with_copy
@attr.s(eq=True, hash=True, init=True, kw_only=True, slots=True, weakref_slot=False)
class TemplateRole(guilds.PartialRole):
    """The partial role object attached to `Template`."""

    permissions: permissions_.Permissions = marshie.attrib(
        deserialize=lambda value: snowflakes.Snowflake(int(value)), eq=False, hash=False, repr=False
    )
    """The guild wide permissions this role gives to the members it's attached to,

    This may be overridden by channel overwrites.
    """

    color: colors.Color = marshie.attrib(deserialize=colors.Color, eq=False, hash=False, repr=True)
    """The colour of this role.

    This will be applied to a member's name in chat if it's their top coloured role.
    """

    is_hoisted: bool = marshie.attrib("hoist", eq=False, hash=False, repr=True)
    """Whether this role is hoisting the members it's attached to in the member list.

    members will be hoisted under their highest role where this is set to `builtins.True`.
    """

    is_mentionable: bool = marshie.attrib("mentionable", eq=False, hash=False, repr=False)
    """Whether this role can be mentioned by all regardless of permissions."""


@attr_extensions.with_copy
@attr.s(eq=True, hash=True, init=True, kw_only=True, slots=True, weakref_slot=False)
class TemplateGuild(guilds.PartialGuild):
    """The partial guild object attached to `Template`."""

    # This special case ID field isn't included in the template guild's payload.
    id: snowflakes.Snowflake = marshie.attrib(from_kwarg=True, eq=True, hash=True, repr=True)

    # For some reason in this case they use the key "icon_hash" rather than "icon".
    # Cause Discord:TM:
    icon_hash: typing.Optional[str] = marshie.attrib("icon_hash", eq=False, hash=False, repr=False)

    description: typing.Optional[str] = marshie.attrib(eq=False, hash=False, repr=False)
    """The guild's description, if set."""

    region: str = marshie.attrib(eq=False, hash=False, repr=False)
    """The voice region for the guild."""

    verification_level: typing.Union[guilds.GuildVerificationLevel, int] = marshie.attrib(
        deserialize=guilds.GuildVerificationLevel, eq=False, hash=False, repr=False
    )
    """The verification level needed for a user to participate in this guild."""

    default_message_notifications: typing.Union[guilds.GuildMessageNotificationsLevel, int] = marshie.attrib(
        deserialize=guilds.GuildMessageNotificationsLevel,
        eq=False,
        hash=False,
        repr=False,
    )
    """The default setting for message notifications in this guild."""

    explicit_content_filter: typing.Union[guilds.GuildExplicitContentFilterLevel, int] = marshie.attrib(
        deserialize=guilds.GuildExplicitContentFilterLevel, eq=False, hash=False, repr=False
    )
    """The setting for the explicit content filter in this guild."""

    preferred_locale: str = marshie.attrib(eq=False, hash=False, repr=False)
    """The preferred locale to use for this guild.

    This can only be change if `GuildFeature.COMMUNITY` is in `Guild.features`
    for this guild and will otherwise default to `en-US`.
    """

    afk_timeout: datetime.timedelta = marshie.attrib(
        deserialize=lambda value: datetime.timedelta(seconds=value), eq=False, hash=False, repr=False
    )
    """Timeout for activity before a member is classed as AFK.

    How long a voice user has to be AFK for before they are classed as being
    AFK and are moved to the AFK channel (`Guild.afk_channel_id`).
    """

    roles: typing.Mapping[snowflakes.Snowflake, TemplateRole] = marshie.attrib(
        deserialize=marshie.Ref(TemplateRole, lambda cast: data_binding.seq_to_map(lambda r: r.id, cast)),
        eq=False,
        hash=False,
        repr=False,
    )
    """The roles in the guild.

    !!! note
        `hikari.guilds.Role.id` will be a unique placeholder on all the role
        objects found attached this template guild.
    """

    channels: typing.Mapping[snowflakes.Snowflake, channels_.GuildChannel] = marshie.attrib(
        from_kwarg=True, eq=False, hash=False, repr=False
    )
    """The channels for the guild.

    !!! note
        `hikari.channels.GuildChannel.id` will be a unique placeholder on all
        the channel objects found attached this template guild.
    """

    afk_channel_id: typing.Optional[snowflakes.Snowflake] = marshie.attrib(
        deserialize=data_binding.optional_cast(snowflakes.Snowflake), eq=False, hash=False, repr=False
    )
    """The ID for the channel that AFK voice users get sent to.

    If `builtins.None`, then no AFK channel is set up for this guild.
    """

    system_channel_id: typing.Optional[snowflakes.Snowflake] = marshie.attrib(
        deserialize=data_binding.optional_cast(snowflakes.Snowflake),
        eq=False,
        hash=False,
        repr=False,
    )
    """The ID of the system channel or `builtins.None` if it is not enabled.

    Welcome messages and Nitro boost messages may be sent to this channel.
    """

    system_channel_flags: guilds.GuildSystemChannelFlag = marshie.attrib(
        deserialize=guilds.GuildSystemChannelFlag, eq=False, hash=False, repr=False
    )
    """Return flags for the guild system channel.

    These are used to describe which notifications are suppressed.
    """


@attr_extensions.with_copy
@attr.s(eq=True, hash=True, init=True, kw_only=True, slots=True, weakref_slot=False)
class Template:
    """Represents a template used for creating guilds."""

    code: str = marshie.attrib(eq=True, hash=True, repr=True)
    """The template's unique ID."""

    name: str = marshie.attrib(eq=False, hash=False, repr=True)
    """The template's name."""

    description: typing.Optional[str] = marshie.attrib("description", eq=False, hash=False, repr=False)
    """The template's description."""

    usage_count: int = marshie.attrib(eq=False, hash=False, repr=True)
    """The number of times the template has been used to create a guild."""

    creator: users.User = marshie.attrib(deserialize="UserImpl", eq=False, hash=False, repr=False)
    """The user who created the template."""

    created_at: datetime.datetime = marshie.attrib(
        deserialize=time.iso8601_datetime_string_to_datetime, eq=False, hash=False, repr=True
    )
    """When the template was created."""

    updated_at: datetime.datetime = marshie.attrib(
        deserialize=time.iso8601_datetime_string_to_datetime, eq=False, hash=False, repr=True
    )
    """When the template was last synced with the source guild."""

    source_guild: TemplateGuild = marshie.attrib(
        "serialized_source_guild",
        deserialize=marshie.Ref(TemplateGuild),
        pass_kwargs=("channels", "id"),
        eq=False,
        hash=False,
        repr=True,
    )
    """The partial object of the guild this template is based on."""

    is_unsynced: bool = marshie.attrib("is_dirty", deserialize=bool, eq=False, hash=False, repr=False)
    """Whether this template is missing changes from it's source guild."""

    def __str__(self) -> str:
        return f"https://discord.new/{self.code}"


Templateish = typing.Union[str, Template]
"""Type hint for a `Template` object or `builtin.str` template code."""
