# -*- coding: utf-8 -*-
# cython: language_level=3
# Copyright (c) 2020 Nekokatt
# Copyright (c) 2021-present davfsa
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
from __future__ import annotations

__all__: typing.Sequence[str] = ()

import typing

from hikari import traits

if typing.TYPE_CHECKING:
    from hikari import channels
    from hikari import guilds
    from hikari import snowflakes

_T = typing.TypeVar("_T")
_CoroT = typing.Coroutine[typing.Any, typing.Any, _T]
_TypesT = typing.Union[typing.Type[_T], typing.Tuple[type[_T], ...]]
_PartialChannelT = typing.TypeVar("_PartialChannelT", bound="channels.PartialChannel")
_GuildChannelT = typing.TypeVar("_GuildChannelT", bound="channels.GuildChannel")


class _AppBoundProto(typing.Protocol):
    @property
    def app(self) -> traits.RESTAware:
        raise NotImplementedError


class _ChannelBoundProto(_AppBoundProto, typing.Protocol):
    @property
    def channel_id(self) -> snowflakes.Snowflake:
        raise NotImplementedError


_ChannelBoundT = typing.TypeVar("_ChannelBoundT", bound=_ChannelBoundProto)
GetChannelSig = typing.Callable[[_ChannelBoundT], typing.Optional[_GuildChannelT]]
FetchChannelSig = typing.Callable[[_ChannelBoundT], typing.Coroutine[typing.Any, typing.Any, _PartialChannelT]]


@typing.overload
def make_get_channel() -> GetChannelSig[_ChannelBoundProto, channels.GuildChannel]:
    ...


@typing.overload
def make_get_channel(*, types: _TypesT[_GuildChannelT]) -> GetChannelSig[_ChannelBoundProto, _GuildChannelT]:
    ...


def make_get_channel(
    *, types: typing.Optional[_TypesT[channels.PartialChannel]] = None
) -> GetChannelSig[_ChannelBoundProto, channels.GuildChannel]:
    if types is None:
        try_threads = False

    elif isinstance(types, tuple):
        try_threads = any(issubclass(cls, channels.GuildThreadChannel) for cls in types)

    else:
        try_threads = issubclass(types, channels.GuildThreadChannel)

    def get_channel(self: _ChannelBoundProto) -> typing.Optional[channels.GuildChannel]:
        if isinstance(self.app, traits.CacheAware):
            channel = self.app.cache.get_guild_channel(self.channel_id)
            if not channel and try_threads:
                channel = self.app.cache.get_thread(self.channel_id)

            if channel and types is not None:
                assert isinstance(channel, types)

            return channel

        return None

    return get_channel


@typing.overload
def make_fetch_channel() -> FetchChannelSig[_ChannelBoundProto, channels.GuildChannel]:
    ...


@typing.overload
def make_fetch_channel(*, types: _TypesT[_PartialChannelT]) -> FetchChannelSig[_ChannelBoundProto, _PartialChannelT]:
    ...


def make_fetch_channel(
    *, types: typing.Optional[_TypesT[channels.PartialChannel]] = None
) -> FetchChannelSig[_ChannelBoundProto, channels.PartialChannel]:
    async def fetch_channel(self: _ChannelBoundProto) -> channels.PartialChannel:
        channel = await self.app.rest.fetch_channel(self.channel_id)

        if types is not None:
            assert isinstance(channel, types)

        return channel

    return fetch_channel


class _GuildBoundProto(_AppBoundProto, typing.Protocol):
    @property
    def guild_id(self) -> typing.Optional[snowflakes.Snowflake]:
        raise NotImplementedError


_GuildBoundT = typing.TypeVar("_GuildBoundT", bound=_GuildBoundProto)
GetGuildSig = typing.Callable[[_GuildBoundT], typing.Optional["guilds.GatewayGuild"]]
FetchGuildSig = typing.Callable[[_GuildBoundT], _CoroT[typing.Optional["guilds.RESTGuild"]]]


def get_guild(self: _GuildBoundProto) -> typing.Optional[guilds.GatewayGuild]:
    if self.guild_id and isinstance(self.app, traits.CacheAware):
        return self.app.cache.get_guild(self.guild_id)

    return None


async def fetch_guild(self: _GuildBoundProto) -> typing.Optional[guilds.RESTGuild]:
    if self.guild_id is None:
        return None

    return await self.app.rest.fetch_guild(self.guild_id)
