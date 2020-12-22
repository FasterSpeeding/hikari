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
"""Application and entities that are used to describe voice state on Discord."""

from __future__ import annotations

__all__: typing.List[str] = ["VoiceRegion", "VoiceState", "VoiceRegionish"]

import typing

import attr
import marshie

from hikari import snowflakes
from hikari.internal import attr_extensions
from hikari.internal import data_binding

if typing.TYPE_CHECKING:
    from hikari import guilds
    from hikari import traits


@attr_extensions.with_copy
@attr.s(eq=True, hash=True, init=True, kw_only=True, slots=True, weakref_slot=False)
class VoiceState:
    """Represents a user's voice connection status."""

    app: traits.RESTAware = marshie.attrib(
        constant=marshie.Ref("app"), repr=False, eq=False, hash=False, metadata={attr_extensions.SKIP_DEEP_COPY: True}
    )
    """The client application that models may use for procedures."""

    channel_id: typing.Optional[snowflakes.Snowflake] = marshie.attrib(
        "channel_id", deserialize=data_binding.optional_cast(snowflakes.Snowflake), eq=False, hash=False, repr=True
    )
    """The ID of the channel this user is connected to.

    This will be `builtins.None` if they are leaving voice.
    """

    guild_id: snowflakes.Snowflake = marshie.attrib(from_kwarg=True, eq=False, hash=False, repr=True)
    """The ID of the guild this voice state is in."""

    is_guild_deafened: bool = marshie.attrib("deaf", eq=False, hash=False, repr=False)
    """Whether this user is deafened by the guild."""

    is_guild_muted: bool = marshie.attrib("mute", eq=False, hash=False, repr=False)
    """Whether this user is muted by the guild."""

    is_self_deafened: bool = marshie.attrib("self_deaf", eq=False, hash=False, repr=False)
    """Whether this user is deafened by their client."""

    is_self_muted: bool = marshie.attrib("self_mute", eq=False, hash=False, repr=False)
    """Whether this user is muted by their client."""

    is_streaming: bool = marshie.attrib("self_stream", mdefault=False, eq=False, hash=False, repr=False)
    """Whether this user is streaming using "Go Live"."""

    is_suppressed: bool = marshie.attrib("suppress", eq=False, hash=False, repr=False)
    """Whether this user is muted by the current user."""

    is_video_enabled: bool = marshie.attrib("self_video", eq=False, hash=False, repr=False)
    """Whether this user's camera is enabled."""

    user_id: snowflakes.Snowflake = marshie.attrib(
        "user_id", deserialize=snowflakes.Snowflake, eq=False, hash=False, repr=True
    )
    """The ID of the user this voice state is for."""

    member: guilds.Member = marshie.attrib(from_kwarg=True, eq=False, hash=False, repr=False)
    """The guild member this voice state is for."""

    session_id: str = marshie.attrib("session_id", eq=True, hash=True, repr=True)
    """The string ID of this voice state's session."""


@attr_extensions.with_copy
@attr.s(eq=True, hash=True, init=True, kw_only=True, slots=True, weakref_slot=False)
class VoiceRegion:
    """Represents a voice region server."""

    id: str = marshie.attrib("id", eq=True, hash=True, repr=True)
    """The string ID of this region.

    !!! note
        Unlike most parts of this API, this ID will always be a string type.
        This is intentional.
    """

    name: str = marshie.attrib("name", eq=False, hash=False, repr=True)
    """The name of this region."""

    is_vip: bool = marshie.attrib("vip", eq=False, hash=False, repr=False)
    """Whether this region is vip-only."""

    is_optimal_location: bool = marshie.attrib("optimal", eq=False, hash=False, repr=False)
    """Whether this region's server is closest to the current user's client."""

    is_deprecated: bool = marshie.attrib("deprecated", eq=False, hash=False, repr=False)
    """Whether this region is deprecated."""

    is_custom: bool = marshie.attrib("custom", eq=False, hash=False, repr=False)
    """Whether this region is custom (e.g. used for events)."""

    def __str__(self) -> str:
        return self.id


VoiceRegionish = typing.Union[str, VoiceRegion]
"""Type hint for a voice region or name of a voice region.

Must be either a `VoiceRegion` or `builtins.str`.
"""
