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
from unittest import mock

import pytest

import hikari.core.models.members
from hikari.core.models import overwrites
from hikari.core.models import permissions
from hikari.core.models import users


@pytest.mark.model
class TestOverwrite:
    def test_Overwrite(self):
        o = overwrites.Overwrite(
            {
                "id": "1234567890",
                "type": "role",
                "allow": int(
                    permissions.Permission.ADD_REACTIONS
                    | permissions.Permission.BAN_MEMBERS
                    | permissions.Permission.CREATE_INSTANT_INVITE
                ),
                "deny": int(permissions.Permission.MANAGE_MESSAGES | permissions.Permission.SEND_TTS_MESSAGES),
            }
        )

        assert o.id == 1234567890
        assert o.type == overwrites.OverwriteEntityType.ROLE
        assert o.allow & permissions.Permission.ADD_REACTIONS
        assert o.allow & permissions.Permission.BAN_MEMBERS
        assert o.allow & permissions.Permission.CREATE_INSTANT_INVITE
        assert o.deny & permissions.Permission.MANAGE_MESSAGES
        assert o.deny & permissions.Permission.SEND_TTS_MESSAGES

        expected_inverse = (
            permissions.Permission.NONE
            | permissions.Permission.KICK_MEMBERS
            | permissions.Permission.ADMINISTRATOR
            | permissions.Permission.MANAGE_CHANNELS
            | permissions.Permission.MANAGE_GUILD
            | permissions.Permission.VIEW_AUDIT_LOG
            | permissions.Permission.PRIORITY_SPEAKER
            | permissions.Permission.VIEW_CHANNEL
            | permissions.Permission.SEND_MESSAGES
            | permissions.Permission.EMBED_LINKS
            | permissions.Permission.ATTACH_FILES
            | permissions.Permission.READ_MESSAGE_HISTORY
            | permissions.Permission.MENTION_EVERYONE
            | permissions.Permission.USE_EXTERNAL_EMOJIS
            | permissions.Permission.CONNECT
            | permissions.Permission.SPEAK
            | permissions.Permission.MUTE_MEMBERS
            | permissions.Permission.DEAFEN_MEMBERS
            | permissions.Permission.MOVE_MEMBERS
            | permissions.Permission.USE_VAD
            | permissions.Permission.MANAGE_ROLES
            | permissions.Permission.MANAGE_WEBHOOKS
            | permissions.Permission.MANAGE_EMOJIS
        )

        assert bin(o.default) == bin(expected_inverse)


@pytest.mark.model
class TestOverwriteEntityType:
    def test_OverwriteEntityType_instancecheck(self):
        m = mock.MagicMock(spec=hikari.core.models.members.Member)

        # I wasn't sure of this, so this is just to be safe that my assumption was correct that the mocks
        # implement instancecheck and subclass check correctly.
        assert isinstance(m, hikari.core.models.members.Member)
        assert type(m) is not hikari.core.models.members.Member

        assert isinstance(m, overwrites.OverwriteEntityType.MEMBER.value)  # always should be right
        assert isinstance(m, overwrites.OverwriteEntityType.MEMBER)  # this is what i am concerned about

    def test_OverwriteEntityType_subclasscheck(self):
        assert issubclass(
            hikari.core.models.members.Member, overwrites.OverwriteEntityType.MEMBER.value
        )  # always should be right
        assert issubclass(
            hikari.core.models.members.Member, overwrites.OverwriteEntityType.MEMBER
        )  # actual thing to test