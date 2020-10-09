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
"""Utility for extending and optimising the usage of attr models."""
from __future__ import annotations

__all__: typing.List[str] = [
    "with_copy",
    "with_pickle",
    "copy_attrs",
    "deep_copy_attrs",
    "get_state",
    "invalidate_deep_copy_cache",
    "invalidate_shallow_copy_cache",
    "invalidate_state_getter_cache",
    "invalidate_state_setter_cache",
    "SKIP_DEEP_COPY",
    "set_state",
    "PICKLE_OVERRIDE",
]

import copy as std_copy
import logging
import typing

import attr

from hikari import undefined
from hikari.internal import ux

ModelT = typing.TypeVar("ModelT")
SKIP_DEEP_COPY: typing.Final[str] = "skip_deep_copy"
PICKLE_OVERRIDE: typing.Final[str] = "skip_state_getter"
_UNDEFINED = object()

_DEEP_COPIERS: typing.MutableMapping[
    typing.Any, typing.Callable[[typing.Any, typing.MutableMapping[int, typing.Any]], None]
] = {}
_SHALLOW_COPIERS: typing.MutableMapping[typing.Any, typing.Callable[[typing.Any], typing.Any]] = {}
_LOGGER = logging.getLogger("hikari.models")

_STATE_GETTER_CACHE: typing.MutableMapping[
    typing.Any, typing.Callable[[typing.Any], typing.MutableMapping[str, typing.Any]]
] = {}
_STATE_SETTER_CACHE: typing.MutableMapping[
    typing.Any, typing.Callable[[typing.Any, typing.MutableMapping[str, typing.Any]], None]
] = {}


def invalidate_shallow_copy_cache() -> None:
    """Remove all the globally cached copy functions."""
    _LOGGER.debug("Invalidating attr extensions shallow copy cache")
    _SHALLOW_COPIERS.clear()


def invalidate_deep_copy_cache() -> None:
    """Remove all the globally cached generated deep copy functions."""
    _LOGGER.debug("Invalidating attr extensions deep copy cache")
    _DEEP_COPIERS.clear()


def invalidate_state_getter_cache() -> None:
    """Remove all the globally cached state getter methods used for pickling models."""
    _LOGGER.debug("Invalidating attr extensions state getter cache")
    _STATE_GETTER_CACHE.clear()


def invalidate_state_setter_cache() -> None:
    """Remove all the globally cached state setter methods used for pickling models."""
    _LOGGER.debug("Invalidating attr extensions state setter cache")
    _STATE_SETTER_CACHE.clear()


def get_fields_definition(
    cls: typing.Type[ModelT],
) -> typing.Tuple[
    typing.Sequence[typing.Tuple[attr.Attribute[typing.Any], str]], typing.Sequence[attr.Attribute[typing.Any]]
]:
    """Get a sequence of init key-words to their relative attribute.

    Parameters
    ----------
    cls : typing.Type[ModelT]
        The attrs class to get the fields definition for.

    Returns
    -------
    typing.Sequence[typing.Tuple[builtins.str, builtins.str]]
        A sequence of tuples of string attribute names to string key-word names.
    """
    init_results = []
    non_init_results = []

    for field in attr.fields(cls):
        if field.init:
            key_word = field.name[1:] if field.name.startswith("_") else field.name
            init_results.append((field, key_word))
        else:
            non_init_results.append(field)

    return init_results, non_init_results


# TODO: can we get if the init wasn't generated for the class?
def generate_shallow_copier(cls: typing.Type[ModelT]) -> typing.Callable[[ModelT], ModelT]:
    """Generate a function for shallow copying an attrs model with `init` enabled.

    Parameters
    ----------
    cls : typing.Type[ModelT]
        The attrs class to generate a shallow copying function for.

    Returns
    -------
    typing.Callable[[ModelT], ModelT]
        The generated shallow copying function.
    """
    kwargs, setters = get_fields_definition(cls)
    kwargs = ",".join(f"{kwarg}=m.{attribute.name}" for attribute, kwarg in kwargs)
    setters = ";".join(f"r.{attribute.name}=m.{attribute.name}" for attribute in setters) + ";" if setters else ""
    code = f"def copy(m):r=cls({kwargs});{setters}return r"
    globals_ = {"cls": cls}
    _LOGGER.log(ux.TRACE, "generating shallow copy function for %r: %r", cls, code)
    exec(code, globals_)  # noqa: S102 - Use of exec detected.
    return typing.cast("typing.Callable[[ModelT], ModelT]", globals_["copy"])


def get_or_generate_shallow_copier(cls: typing.Type[ModelT]) -> typing.Callable[[ModelT], ModelT]:
    """Get a cached shallow copying function for a an attrs class or generate it.

    Parameters
    ----------
    cls : typing.Type[ModelT]
        The class to get or generate and cache a shallow copying function for.

    Returns
    -------
    typing.Callable[[ModelT], ModelT]
        The cached or generated shallow copying function.
    """
    try:
        return _SHALLOW_COPIERS[cls]
    except KeyError:
        copier = generate_shallow_copier(cls)
        _SHALLOW_COPIERS[cls] = copier
        return copier


def copy_attrs(model: ModelT) -> ModelT:
    """Shallow copy an attrs model with `init` enabled.

    Parameters
    ----------
    model : ModelT
        The attrs model to shallow copy.

    Returns
    -------
    ModelT
        The new shallow copied attrs model.
    """
    return get_or_generate_shallow_copier(type(model))(model)


def _normalize_kwargs_and_setters(
    kwargs: typing.Sequence[typing.Tuple[attr.Attribute[typing.Any], str]],
    setters: typing.Sequence[attr.Attribute[typing.Any]],
) -> typing.Iterable[attr.Attribute[typing.Any]]:
    for attribute, _ in kwargs:
        yield attribute

    yield from setters


def generate_deep_copier(
    cls: typing.Type[ModelT],
) -> typing.Callable[[ModelT, typing.MutableMapping[int, typing.Any]], None]:
    """Generate a function for deep copying an attrs model with `init` enabled.

    Parameters
    ----------
    cls : typing.Type[ModelT]
        The attrs class to generate a deep copying function for.

    Returns
    -------
    typing.Callable[[ModelT], ModelT]
        The generated deep copying function.
    """
    kwargs, setters = get_fields_definition(cls)

    # Explicitly handle the case of an attrs model with no fields by returning
    # an empty lambda to avoid a SyntaxError being raised.
    if not kwargs and not setters:
        return lambda _, __: None

    setters = ";".join(
        f"m.{attribute.name}=std_copy(m.{attribute.name},memo)if(id_:=id(m.{attribute.name}))not in memo else memo[id_]"
        for attribute in _normalize_kwargs_and_setters(kwargs, setters)
        if not attribute.metadata.get(SKIP_DEEP_COPY)
    )
    code = f"def deep_copy(m,memo):{setters}"
    globals_ = {"std_copy": std_copy.deepcopy, "cls": cls}
    _LOGGER.debug("generating deep copy function for %r: %r", cls, code)
    exec(code, globals_)  # noqa: S102 - Use of exec detected.
    return typing.cast("typing.Callable[[ModelT, typing.MutableMapping[int, typing.Any]], None]", globals_["deep_copy"])


def get_or_generate_deep_copier(
    cls: typing.Type[ModelT],
) -> typing.Callable[[ModelT, typing.MutableMapping[int, typing.Any]], None]:
    """Get a cached shallow copying function for a an attrs class or generate it.

    Parameters
    ----------
    cls : typing.Type[ModelT]
        The class to get or generate and cache a shallow copying function for.

    Returns
    -------
    typing.Callable[[ModelT], ModelT]
        The cached or generated shallow copying function.
    """
    try:
        return _DEEP_COPIERS[cls]
    except KeyError:
        copier = generate_deep_copier(cls)
        _DEEP_COPIERS[cls] = copier
        return copier


def deep_copy_attrs(model: ModelT, memo: typing.Optional[typing.MutableMapping[int, typing.Any]] = None) -> ModelT:
    """Deep copy an attrs model with `init` enabled.

    Parameters
    ----------
    model : ModelT
        The attrs model to deep copy.
    memo : typing.Optional[typing.MutableMapping[builtins.int, typing.Any]]
        A memo dictionary of objects already copied during the current copying
        pass, see https://docs.python.org/3/library/copy.html for more details.

    !!! note
        This won't deep copy attributes where "skip_deep_copy" is set to
        `builtins.True` in their metadata.

    Returns
    -------
    ModelT
        The new deep copied attrs model.
    """
    if memo is None:
        memo = {}

    new_object = std_copy.copy(model)
    memo[id(model)] = new_object
    get_or_generate_deep_copier(type(model))(new_object, memo)
    return new_object


def with_copy(cls: typing.Type[ModelT]) -> typing.Type[ModelT]:
    """Add a custom implementation for copying attrs models to a class.

    !!! note
        This will only work if the class has an attrs generated init.
    """
    cls.__copy__ = copy_attrs  # type: ignore[attr-defined]
    cls.__deepcopy__ = deep_copy_attrs  # type: ignore[attr-defined]
    return cls


def generate_state_getter(
    cls: typing.Type[ModelT],
) -> typing.Callable[[ModelT], typing.MutableMapping[str, typing.Any]]:
    fields = attr.fields(cls)
    getters = ",".join(
        f"{field.name}=m.{field.name}"
        for field in fields
        if field.metadata.get(PICKLE_OVERRIDE, _UNDEFINED) is _UNDEFINED
    )

    # Explicitly handle the case of a model with no pickleable attributes by
    # returning a lambda that returns an empty dictionary to avoid a sytnax error.
    if not getters:
        return lambda _: {}

    code = f"def get_state(m): return dict({getters})"
    globals_: typing.Dict[str, typing.Any] = {"UNDEFINED": undefined.UNDEFINED}
    _LOGGER.debug("generating state getter function for %r: %r", cls, code)
    exec(code, globals_)  # noqa: S102 - Use of exec detected.
    return typing.cast("typing.Callable[[ModelT], typing.MutableMapping[str, typing.Any]]", globals_["get_state"])


def get_or_generate_state_getter(
    cls: typing.Type[ModelT],
) -> typing.Callable[[ModelT], typing.MutableMapping[str, typing.Any]]:
    try:
        return _STATE_GETTER_CACHE[cls]
    except KeyError:
        state_getter = generate_state_getter(cls)
        _STATE_GETTER_CACHE[cls] = state_getter
        return state_getter


def get_state(model: ModelT) -> typing.MutableMapping[str, typing.Any]:
    return get_or_generate_state_getter(type(model))(model)


def generate_state_setter(
    cls: typing.Type[ModelT],
) -> typing.Callable[[typing.Any, typing.MutableMapping[str, typing.Any]], None]:
    fields = attr.fields(cls)

    # Handle the case of a model with no fields by returning an empty lambda
    # to avoid a syntax error being raised.
    if not fields:
        return lambda _, __: None

    globals_ = {"UNDEFINED": undefined.UNDEFINED}
    setters = []

    for field in fields:
        override = field.metadata.get(PICKLE_OVERRIDE, _UNDEFINED)
        if override is not _UNDEFINED:
            globals_[field.name] = override
            setters.append(f"m.{field.name}={field.name}")
        else:
            setters.append(f"m.{field.name}=state[{field.name!r}]")

    code = "def set_state(m, state):" + ";".join(setters)
    _LOGGER.debug("generating state setter function for %r: %r", cls, code)
    exec(code, globals_)  # noqa: S102 - Use of exec detected.
    return typing.cast(
        "typing.Callable[[typing.Any, typing.MutableMapping[str, typing.Any]], None]", globals_["set_state"]
    )


def get_or_generate_state_setter(
    cls: typing.Type[ModelT],
) -> typing.Callable[[typing.Any, typing.MutableMapping[str, typing.Any]], None]:
    try:
        return _STATE_SETTER_CACHE[cls]
    except KeyError:
        state_setter = generate_state_setter(cls)
        _STATE_SETTER_CACHE[cls] = state_setter
        return state_setter


def set_state(model: ModelT, state: typing.MutableMapping[str, typing.Any]) -> None:
    get_or_generate_state_setter(type(model))(model, state)


# Unlike copy and deepcopy implementations, state getters and setters aren't inherited.
def with_pickle(cls: typing.Type[ModelT]) -> typing.Type[ModelT]:
    cls.__getstate__ = get_state  # type: ignore[attr-defined]
    cls.__setstate__ = set_state  # type: ignore[attr-defined]
    return cls
