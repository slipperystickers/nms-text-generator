"""Native-part compatibility; no dependency registration or monkey-patching.

The old combined add-on exposes builder_v2. The split release delegates HD
placement to Charon Forge while Base Builder owns the active builder/Part API.
Resolve that active instance at call time so re-enabling either dependency
does not leave text generation/export using a stale builder.
"""
import importlib
from pathlib import Path

HOST_NAMES = ('no_mans_sky_base_builder', 'official_nms_builder')
_split_cache = {}
_standard_cache = {}


def dependency_name(enabled):
    for suffix in HOST_NAMES:
        for name in enabled:
            if name.rsplit('.', 1)[-1] == suffix:
                return name
    return None


class SplitBackend:
    requires_high_res = True
    def __init__(self, host_name, forge, assets, bridge):
        self.host_name = host_name
        self.forge = forge
        self.assets = assets
        self.bridge = bridge

    @property
    def BUILDER(self):
        # Forge's public bridge also handles dependency enable order/reloads.
        if self.bridge.get_addon_module_name() != self.host_name:
            raise ValueError('Charon Forge is not connected to the enabled Base Builder. Restart Blender with both add-ons enabled.')
        builder = self.bridge.get_builder()
        if builder is None or not callable(getattr(builder, 'get_part_class', None)):
            raise ValueError('Base Builder has no active native-part builder.')
        return builder

    @property
    def Part(self):
        return self.BUILDER.get_part_class('')

    def add_part(self, object_id, **kwargs):
        return self.forge.add_part(object_id, builder_object=self.BUILDER, **kwargs)

    def get_asset_index(self):
        return self.assets.get_asset_index()


class StandardBackend:
    """The official Base Builder works without the optional HD extension."""
    requires_high_res = False

    def __init__(self, hooks):
        self.hooks = hooks

    @property
    def BUILDER(self):
        return self.hooks.get_builder()

    @property
    def Part(self):
        return self.BUILDER.get_part_class('')

    def add_part(self, object_id, high_res=True, **kwargs):
        # The standard factory has no high_res parameter. Do not patch it or
        # change the native object transform/mesh to imitate an HD preview.
        return self.BUILDER.add_part(object_id, **kwargs)

    def get_asset_index(self):
        index = {}
        for part_id in ('BUILDFLATPANEL', 'STORAGEPANEL'):
            path = self.BUILDER.get_obj_path(part_id)
            if path and Path(path).is_file():
                index[part_id] = path
        return index


def resolve(enabled):
    enabled = tuple(enabled)
    host = dependency_name(enabled)
    if not host:
        raise ValueError("Enable No Man's Sky Base Builder in Preferences > Add-ons first.")
    legacy_name = host + '.builder_v2'
    try:
        legacy = importlib.import_module(legacy_name)
    except ModuleNotFoundError as exc:
        # A broken dependency inside builder_v2 is not the new split API.
        if exc.name != legacy_name:
            raise ValueError('Base Builder could not load its native-part API: ' + str(exc)) from exc
    except ImportError as exc:
        raise ValueError('Base Builder could not load its native-part API: ' + str(exc)) from exc
    else:
        if not all(hasattr(legacy, key) for key in ('add_part', 'Part', 'BUILDER', 'get_asset_index')):
            raise ValueError('This Base Builder version lacks the required native-part API.')
        return legacy

    forge_name = next((n for n in enabled if n.rsplit('.', 1)[-1] == 'charon_forge'), None)
    if not forge_name:
        try:
            hooks = importlib.import_module(host + '.builder')
        except ImportError as exc:
            raise ValueError('Base Builder could not load its native-part API: ' + str(exc)) from exc
        if not callable(getattr(hooks, 'get_builder', None)):
            raise ValueError('This Base Builder lacks both the legacy HD API and the standard builder hooks. Use a supported Base Builder version.')
        backend = _standard_cache.get(host)
        if backend is None or backend.hooks is not hooks:
            backend = _standard_cache[host] = StandardBackend(hooks)
        instance = backend.BUILDER
        if not all(callable(getattr(instance, key, None)) for key in ('get_part_class', 'get_obj_path', 'add_part')):
            raise ValueError('Base Builder lacks the required standard-part API.')
        if not all(callable(getattr(backend.Part, key, None)) for key in ('create_matrix_from_vectors', 'deserialise_from_object')):
            raise ValueError('Base Builder lacks the required native-part transform/export API.')
        return backend
    try:
        forge = importlib.import_module(forge_name + '.builder')
        assets = importlib.import_module(forge_name + '.builder.asset_library')
        bridge = importlib.import_module(forge_name + '.utils.base_builder_utils')
    except ImportError as exc:
        raise ValueError('Charon Forge could not load its native-part API: ' + str(exc)) from exc
    for module, names in ((forge, ('add_part',)), (assets, ('get_asset_index',)),
                          (bridge, ('get_builder', 'get_addon_module_name'))):
        if not all(callable(getattr(module, name, None)) for name in names):
            raise ValueError('This Charon Forge version lacks the required native-part API.')
    # Cache only the facade, not the host instance; invalidate on module reload.
    key = (host, forge_name)
    backend = _split_cache.get(key)
    if backend is None or (backend.forge, backend.assets, backend.bridge) != (forge, assets, bridge):
        backend = _split_cache[key] = SplitBackend(host, forge, assets, bridge)
    part = backend.Part
    if not all(callable(getattr(part, name, None)) for name in ('create_matrix_from_vectors', 'deserialise_from_object')):
        raise ValueError('Base Builder lacks the required native-part transform/export API.')
    return backend
