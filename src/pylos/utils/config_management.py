import logging

logger = logging.getLogger(__name__)


def dict_replace_by_key(obj: dict, replaced_key: dict, deep_copy: bool = True) -> dict:
    """Replace values in a nested dict by key name, at any depth.

    For each ``key: value`` in ``replaced_key``, the key is looked up in ``obj``
    first. If it is not there, the search goes into every nested dict, level by
    level. Every dict that contains the key gets its value replaced, so a key
    that appears in several branches is replaced in all of them. Values that are
    not dicts (str, int, None, list, ...) are never searched or modified, and a
    key that is not found anywhere is silently skipped.

    By default ``obj`` is deep-copied first, so the caller's dict is never
    changed. Pass ``deep_copy=False`` to modify ``obj`` in place and skip the
    copy cost.

    Args:
        obj: The nested dict to update.
        replaced_key: Mapping of key name to its new value. A new value that is
            a dict replaces the old value as a whole, it is not merged into it.
        deep_copy: If True (default), work on a deep copy of ``obj`` and leave
            the original untouched. If False, modify ``obj`` in place.

    Returns:
        The updated dict. A new object when ``deep_copy`` is True, otherwise the
        same ``obj`` that was passed in.

    Examples:
        >>> cfg = {"a": {"b": 1}, "c": 2}
        >>> dict_replace_by_key(cfg, {"b": 9})
        {'a': {'b': 9}, 'c': 2}
        >>> cfg
        {'a': {'b': 1}, 'c': 2}
    """

    def _replace_recursively(obj: dict, replaced_key: dict) -> dict:
        """Replace keys in ``obj`` in place, searching nested dicts for keys it lacks.

        A key found at this level is replaced here, and the search for it stops,
        so deeper copies of the same key are untouched. A key missing at this
        level is searched for in every nested dict value.
        """
        for r_key, r_value in replaced_key.items():
            if r_key in obj and isinstance(obj, dict):
                obj[r_key] = r_value
            elif r_key not in obj and isinstance(obj, dict):
                for key in obj.keys():
                    if isinstance(obj[key], dict):
                        _replace_recursively(obj=obj[key], replaced_key={r_key: r_value})

            # Base Case if the key is not in the object get back to the previous level
            elif r_key not in obj and not isinstance(obj, dict):
                logger.warning("Key '%s' not found in object and object is not a dict.", r_key)
                return obj
        return obj

    if deep_copy:
        import copy

        obj = copy.deepcopy(obj)
    return _replace_recursively(obj=obj, replaced_key=replaced_key)
