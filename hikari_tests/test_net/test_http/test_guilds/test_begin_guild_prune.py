#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright © Nekoka.tt 2019
#
# This file is part of Hikari.
#
# Hikari is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Hikari is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Hikari. If not, see <https://www.gnu.org/licenses/>.

import asynctest
import pytest

from hikari import _utils


@pytest.fixture()
async def http_client(event_loop):
    from hikari_tests.test_net.test_http import ClientMock

    return ClientMock(token="foobarsecret", loop=event_loop)


@pytest.mark.asyncio
async def test_begin_guild_prune(http_client):
    http_client.request = asynctest.CoroutineMock()
    await http_client.begin_guild_prune("424242", 10, False)
    http_client.request.assert_awaited_once_with(
        "post",
        "/guilds/{guild_id}/prune",
        guild_id="424242",
        query={"days": 10, "compute_prune_count": False},
        reason=_utils.unspecified,
    )


@pytest.mark.asyncio
async def test_with_optional_reason(http_client):
    http_client.request = asynctest.CoroutineMock()
    await http_client.begin_guild_prune("424242", 10, False, reason="baz")
    args, kwargs = http_client.request.call_args
    assert kwargs["reason"] == "baz"