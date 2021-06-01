# -*- coding: utf-8 -*-
# cython: language_level=3
# Copyright (c) 2020 Nekokatt
# Copyright (c) 2021 davfsa
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
"""A base implementation for an event manager."""

from __future__ import annotations

__all__: typing.List[str] = ["as_listener", "EventManagerBase"]

import asyncio
import inspect
import logging
import typing
import warnings

import attr

from hikari import config
from hikari import errors
from hikari import event_stream
from hikari import traits
from hikari import undefined
from hikari.api import event_manager
from hikari.events import base_events
from hikari.internal import aio
from hikari.internal import data_binding
from hikari.internal import reflect

if typing.TYPE_CHECKING:
    from hikari.api import shard as gateway_shard

_LOGGER: typing.Final[logging.Logger] = logging.getLogger("hikari.event_manager")

if typing.TYPE_CHECKING:
    ConsumerT = typing.Callable[
        [gateway_shard.GatewayShard, data_binding.JSONObject], typing.Coroutine[typing.Any, typing.Any, None]
    ]
    ListenerMapT = typing.Dict[
        typing.Type[event_manager.EventT_co],
        typing.List[event_manager.CallbackT[event_manager.EventT_co]],
    ]
    WaiterT = typing.Tuple[event_manager.PredicateT[event_manager.EventT_co], asyncio.Future[event_manager.EventT_co]]
    WaiterMapT = typing.Dict[typing.Type[event_manager.EventT_co], typing.Set[WaiterT[event_manager.EventT_co]]]

    EventManagerBaseT = typing.TypeVar("EventManagerBaseT", bound="EventManagerBase")
    UnboundMethodT = typing.Callable[
        [EventManagerBaseT, gateway_shard.GatewayShard, data_binding.JSONObject],
        typing.Coroutine[typing.Any, typing.Any, None],
    ]
    MethodT = typing.Callable[
        [gateway_shard.GatewayShard, data_binding.JSONObject],
        typing.Coroutine[typing.Any, typing.Any, None],
    ]


def _default_predicate(_: event_manager.EventT_inv) -> bool:
    return True


_CACHE_RESOURCE_ATTRIBUTE = "__CACHE_RESOURCE__"
_EVENT_TYPES_ATTRIBUTE = "__EVENT_TYPES__"


def as_listener(
    event_types: typing.Union[typing.Type[base_events.Event], typing.Sequence[typing.Type[base_events.Event]]],
    cache_resource: config.CacheComponents = config.CacheComponents.NONE,
    /,
) -> typing.Callable[[UnboundMethodT[EventManagerBaseT]], UnboundMethodT[EventManagerBaseT]]:
    """Add metadata to a listener method to indicate when it should be unmarshalled and dispatched."""
    event_types = event_types if isinstance(event_types, typing.Sequence) else (event_types,)

    def decorator(method: UnboundMethodT[EventManagerBaseT], /) -> UnboundMethodT[EventManagerBaseT]:
        setattr(method, _CACHE_RESOURCE_ATTRIBUTE, cache_resource)
        setattr(method, _EVENT_TYPES_ATTRIBUTE, event_types)
        return method

    return decorator


@attr.define()
class _Consumer:
    callback: ConsumerT
    cache: undefined.UndefinedOr[config.CacheComponents]
    event_types: undefined.UndefinedOr[typing.Sequence[typing.Type[base_events.Event]]]


class EventManagerBase(event_manager.EventManager):
    """Provides functionality to consume and dispatch events.

    Specific event handlers should be in functions named `on_xxx` where `xxx`
    is the raw event name being dispatched in lower-case.
    """

    __slots__: typing.Sequence[str] = ("_app", "_listeners", "_listeners_non_poly", "_consumers", "_waiters")

    def __init__(self, app: traits.BotAware) -> None:
        self._app = app
        self._consumers: typing.Dict[str, _Consumer] = {}
        self._listeners: ListenerMapT[base_events.Event] = {}
        self._listeners_non_poly: ListenerMapT[base_events.Event] = {}
        self._waiters: WaiterMapT[base_events.Event] = {}

        for name, member in inspect.getmembers(self):
            if name.startswith("on_"):
                member = typing.cast("MethodT", member)
                cache_resource = getattr(member, _CACHE_RESOURCE_ATTRIBUTE, undefined.UNDEFINED)
                event_types = getattr(member, _EVENT_TYPES_ATTRIBUTE, undefined.UNDEFINED)

                cache_resource = typing.cast("undefined.UndefinedOr[config.CacheComponents]", cache_resource)
                event_types = typing.cast(
                    "undefined.UndefinedOr[typing.Sequence[typing.Type[base_events.Event]]]", event_types
                )
                self._consumers[name[3:]] = _Consumer(member, cache_resource, event_types)

        base_events.Event.on_new_subclass(self._on_new_event_cls)

    def _on_new_event_cls(self, event_type: typing.Type[base_events.Event], /) -> None:
        parent_cls = event_type.mro()[1]
        if issubclass(parent_cls, base_events.Event):
            if listeners := self._listeners.get(parent_cls):
                self._listeners[event_type] = listeners.copy()

            if waiters := self._waiters.get(parent_cls):
                self._waiters[event_type] = waiters.copy()

    def _cache_enabled_for_any(self, components: config.CacheComponents, /) -> bool:
        return bool(self._app.cache.settings.components & components)

    def _enabled_for(self, event_type: typing.Type[base_events.Event], /) -> bool:
        return event_type in self._listeners or event_type in self._waiters

    def consume_raw_event(
        self, event_name: str, shard: gateway_shard.GatewayShard, payload: data_binding.JSONObject
    ) -> None:
        payload_event = self._app.event_factory.deserialize_shard_payload_event(shard, payload, name=event_name)
        self.dispatch(payload_event)
        consumer = self._consumers[event_name.lower()]

        # If undefined then we can only safely assume that this does link to registered listeners.
        if consumer.event_types is not undefined.UNDEFINED:
            for event_type in consumer.event_types:
                if self._enabled_for(event_type):
                    break

            else:
                # None here indicates that the function doesn't do any cache altering.
                if consumer.cache == config.CacheComponents.NONE:
                    return

                # Whereas UNDEFINED indicates that it wasn't specified and we should therefore assume it does to be safe
                if consumer.cache is not undefined.UNDEFINED and not self._cache_enabled_for_any(consumer.cache):
                    return

        asyncio.create_task(self._handle_dispatch(consumer.callback, shard, payload), name=f"dispatch {event_name}")

    def subscribe(
        self,
        event_type: typing.Type[event_manager.EventT_co],
        callback: event_manager.CallbackT[event_manager.EventT_co],
        *,
        _nested: int = 0,
    ) -> event_manager.CallbackT[event_manager.EventT_co]:
        if not issubclass(event_type, base_events.Event):
            raise TypeError("Cannot subscribe to a non-Event type")

        if not inspect.iscoroutinefunction(callback):
            raise TypeError("Cannot subscribe a non-coroutine function callback")

        # `_nested` is used to show the correct source code snippet if an intent
        # warning is triggered.
        self._check_intents(event_type, _nested)

        _LOGGER.debug(
            "subscribing callback 'async def %s%s' to event-type %s.%s",
            getattr(callback, "__name__", "<anon>"),
            inspect.signature(callback),
            event_type.__module__,
            event_type.__qualname__,
        )

        try:
            self._listeners_non_poly[event_type].append(callback)  # type: ignore[arg-type]
        except KeyError:
            self._listeners_non_poly[event_type] = [callback]  # type: ignore[list-item]

        for cls in event_type.subclasses():
            try:
                self._listeners[cls].append(callback)  # type: ignore[arg-type]
            except KeyError:
                self._listeners[cls] = [callback]  # type: ignore[list-item]

        return callback

    def _check_intents(self, event_type: typing.Type[event_manager.EventT_co], nested: int) -> None:
        # Collection of combined bitfield combinations of intents that
        # could be enabled to receive this event.
        expected_intent_groups = base_events.get_required_intents_for(event_type)

        if expected_intent_groups:
            for expected_intent_group in expected_intent_groups:
                if (self._app.intents & expected_intent_group) == expected_intent_group:
                    break
            else:
                expected_intents_str = ", ".join(map(str, expected_intent_groups))

                warnings.warn(
                    f"You have tried to listen to {event_type.__name__}, but this will only ever be triggered if "
                    f"you enable one of the following intents: {expected_intents_str}.",
                    category=errors.MissingIntentWarning,
                    stacklevel=nested + 3,
                )

    def get_listeners(
        self,
        event_type: typing.Type[event_manager.EventT_co],
        /,
        *,
        polymorphic: bool = True,
    ) -> typing.Collection[event_manager.CallbackT[event_manager.EventT_co]]:
        if polymorphic:
            items = self._listeners.get(event_type)
            if items is not None:
                return items.copy()

        else:
            items = self._listeners_non_poly.get(event_type)
            if items is not None:
                return items.copy()

        return []

    def unsubscribe(
        self,
        event_type: typing.Type[event_manager.EventT_co],
        callback: event_manager.CallbackT[event_manager.EventT_co],
    ) -> None:
        if event_type in self._listeners and (listeners := self._listeners_non_poly.get(event_type)):
            _LOGGER.debug(
                "unsubscribing callback %s%s from event-type %s.%s",
                getattr(callback, "__name__", "<anon>"),
                inspect.signature(callback),
                event_type.__module__,
                event_type.__qualname__,
            )
            listeners.remove(callback)  # type: ignore[arg-type]
            if not listeners:
                del self._listeners_non_poly[event_type]

            for cls in event_type.subclasses():
                if listeners := self._listeners.get(cls):
                    listeners.remove(callback)  # type: ignore[arg-type]

                    if not listeners:
                        del self._listeners[cls]

    def listen(
        self,
        event_type: typing.Optional[typing.Type[event_manager.EventT_co]] = None,
    ) -> typing.Callable[
        [event_manager.CallbackT[event_manager.EventT_co]], event_manager.CallbackT[event_manager.EventT_co]
    ]:
        def decorator(
            callback: event_manager.CallbackT[event_manager.EventT_co],
        ) -> event_manager.CallbackT[event_manager.EventT_co]:
            nonlocal event_type

            signature = reflect.resolve_signature(callback)
            params = signature.parameters.values()

            if len(params) != 1:
                raise TypeError("Event listener must have exactly one parameter, the event object.")

            event_param = next(iter(params))

            if event_type is None:
                if event_param.annotation is event_param.empty:
                    raise TypeError("Must provide the event type in the @listen decorator or as a type hint!")

                event_type = event_param.annotation

            self.subscribe(event_type, callback, _nested=1)
            return callback

        return decorator

    def dispatch(self, event: event_manager.EventT_inv) -> asyncio.Future[typing.Any]:
        if not isinstance(event, base_events.Event):
            raise TypeError(f"Events must be subclasses of {base_events.Event.__name__}, not {type(event).__name__}")

        event_type = type(event)
        tasks: typing.List[typing.Coroutine[None, typing.Any, None]] = []

        if listeners := self._listeners.get(event_type):
            for callback in listeners:
                tasks.append(self._invoke_callback(callback, event))

        if waiter_set := self._waiters.get(event_type):
            for waiter in tuple(waiter_set):
                predicate, future = waiter
                if not future.done():
                    try:
                        result = predicate(event)
                    except Exception as ex:
                        future.set_exception(ex)
                    else:
                        if result:
                            future.set_result(event)

                # The future was probably cancelled meaning we need to remove it here.
                else:
                    waiter_set.remove(waiter)

        return asyncio.gather(*tasks) if tasks else aio.completed_future()

    def stream(
        self,
        event_type: typing.Type[event_manager.EventT_co],
        /,
        timeout: typing.Union[float, int, None],
        limit: typing.Optional[int] = None,
    ) -> event_stream.Streamer[event_manager.EventT_co]:
        self._check_intents(event_type, 1)
        return event_stream.EventStream(self._app, event_type, timeout=timeout, limit=limit)

    async def wait_for(
        self,
        event_type: typing.Type[event_manager.EventT_co],
        /,
        timeout: typing.Union[float, int, None],
        predicate: typing.Optional[event_manager.PredicateT[event_manager.EventT_co]] = None,
    ) -> event_manager.EventT_co:

        if predicate is None:
            predicate = _default_predicate

        self._check_intents(event_type, 1)

        future: asyncio.Future[event_manager.EventT_co] = asyncio.get_event_loop().create_future()
        pair = (predicate, future)
        subclasses = event_type.subclasses()

        for cls in subclasses:
            try:
                self._waiters[cls].add(pair)  # type: ignore[arg-type]
            except KeyError:
                self._waiters[cls] = {pair}  # type: ignore[arg-type]

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        finally:
            for cls in subclasses:
                try:
                    self._waiters[cls].remove(pair)  # type: ignore[arg-type]
                except KeyError:
                    pass

            raise

    @staticmethod
    async def _handle_dispatch(
        callback: ConsumerT,
        shard: gateway_shard.GatewayShard,
        payload: data_binding.JSONObject,
    ) -> None:
        try:
            await callback(shard, payload)
        except asyncio.CancelledError:
            # Skip cancelled errors, likely caused by the event loop being shut down.
            pass
        except errors.UnrecognisedEntityError:
            _LOGGER.debug("Event referenced an unrecognised entity, discarding")
        except BaseException as ex:
            asyncio.get_running_loop().call_exception_handler(
                {
                    "message": "Exception occurred in raw event dispatch conduit",
                    "exception": ex,
                    "task": asyncio.current_task(),
                }
            )

    async def _invoke_callback(
        self, callback: event_manager.CallbackT[event_manager.EventT_inv], event: event_manager.EventT_inv
    ) -> None:
        try:
            await callback(event)
        except Exception as ex:
            # Skip the first frame in logs, we don't care for it.
            trio = type(ex), ex, ex.__traceback__.tb_next if ex.__traceback__ is not None else None

            if base_events.is_no_recursive_throw_event(event):
                _LOGGER.error(
                    "an exception occurred handling an event (%s), but it has been ignored",
                    type(event).__name__,
                    exc_info=trio,
                )
            else:
                exception_event = base_events.ExceptionEvent(
                    exception=ex,
                    failed_event=event,
                    failed_callback=callback,
                )

                log = _LOGGER.debug if self.get_listeners(type(exception_event), polymorphic=True) else _LOGGER.error
                log("an exception occurred handling an event (%s)", type(event).__name__, exc_info=trio)
                await self.dispatch(exception_event)
