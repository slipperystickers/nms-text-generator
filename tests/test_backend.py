import importlib.util
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location('text_backend', Path(__file__).resolve().parents[1]/'nms_text_generator/backend.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


class BackendTests(unittest.TestCase):
    def setUp(self):
        b._split_cache.clear()
        b._standard_cache.clear()
        self.host = 'bl_ext.custom.no_mans_sky_base_builder'
        self.forge = 'bl_ext.custom.charon_forge'
        self.part = NS(create_matrix_from_vectors=Mock(), deserialise_from_object=Mock())
        self.builder = NS(get_part_class=Mock(return_value=self.part), get_obj_path=Mock(return_value=__file__), add_part=Mock())
        self.hooks = NS(get_builder=Mock(return_value=self.builder))
        self.placement = NS(add_part=Mock())
        self.assets = NS(get_asset_index=Mock(return_value={'BUILDFLATPANEL': 'mesh.blend'}))
        self.bridge = NS(get_addon_module_name=Mock(return_value=self.host), get_builder=Mock(return_value=self.builder))
        self.modules = {
            self.host+'.builder': self.hooks,
            self.forge+'.builder': self.placement,
            self.forge+'.builder.asset_library': self.assets,
            self.forge+'.utils.base_builder_utils': self.bridge,
        }
        def load(name):
            if name not in self.modules:
                raise ModuleNotFoundError('No module named '+name, name=name)
            return self.modules[name]
        self.patcher = patch.object(b.importlib, 'import_module', side_effect=load)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_missing_host(self):
        with self.assertRaisesRegex(ValueError, 'Enable No Man'):
            b.resolve([self.forge])

    def test_standard_base_without_forge(self):
        api = b.resolve([self.host])
        self.assertFalse(api.requires_high_res)
        api.add_part('BUILDFLATPANEL', high_res=True, build_rigs=False)
        self.builder.add_part.assert_called_once_with('BUILDFLATPANEL', build_rigs=False)
        self.assertEqual(set(api.get_asset_index()), {'BUILDFLATPANEL','STORAGEPANEL'})
        self.assertIs(api.Part, self.part)
        self.assertIs(api.BUILDER, self.builder)

    def test_legacy_does_not_require_forge(self):
        legacy = NS(add_part=Mock(), Part=self.part, BUILDER=self.builder, get_asset_index=Mock())
        self.modules[self.host+'.builder_v2'] = legacy
        self.assertIs(b.resolve([self.host]), legacy)

    def test_internal_import_error_is_not_treated_as_split(self):
        with patch.object(b.importlib, 'import_module', side_effect=ModuleNotFoundError('missing dependency', name='missing_dependency')):
            with self.assertRaisesRegex(ValueError, 'could not load'):
                b.resolve([self.host, self.forge])

    def test_split_uses_active_host_for_placement_and_export(self):
        api = b.resolve([self.host, self.forge])
        api.add_part('BUILDFLATPANEL', high_res=True, build_rigs=False)
        self.placement.add_part.assert_called_once_with('BUILDFLATPANEL', builder_object=self.builder, high_res=True, build_rigs=False)
        self.assertIs(api.Part, self.part)
        self.assertIs(api.BUILDER, self.builder)
        self.assertIn('BUILDFLATPANEL', api.get_asset_index())
        self.assertIs(b.resolve([self.host, self.forge]), api)

    def test_builder_replaced_without_stale_reference(self):
        api = b.resolve([self.host, self.forge])
        replacement = NS(get_part_class=Mock(return_value=self.part))
        self.bridge.get_builder.return_value = replacement
        self.assertIs(api.BUILDER, replacement)
        api.add_part('STORAGEPANEL')
        self.placement.add_part.assert_called_once_with('STORAGEPANEL', builder_object=replacement)

    def test_forge_reload_invalidates_facade(self):
        api = b.resolve([self.host, self.forge])
        self.modules[self.forge+'.builder'] = NS(add_part=Mock())
        self.assertIsNot(api, b.resolve([self.host, self.forge]))

    def test_disabled_forge_cannot_use_cache(self):
        b.resolve([self.host, self.forge])
        self.assertIsInstance(b.resolve([self.host]), b.StandardBackend)

    def test_standard_missing_assets(self):
        self.builder.get_obj_path.return_value = None
        self.assertEqual(b.resolve([self.host]).get_asset_index(), {})

    def test_standard_builder_replaced(self):
        api = b.resolve([self.host])
        replacement = NS(get_part_class=Mock(return_value=self.part))
        self.hooks.get_builder.return_value = replacement
        self.assertIs(api.BUILDER, replacement)

    def test_missing_api_has_actionable_error(self):
        self.assets.get_asset_index = None
        with self.assertRaisesRegex(ValueError, 'Charon Forge version lacks'):
            b.resolve([self.host, self.forge])

    def test_wrong_host_rejected(self):
        self.bridge.get_addon_module_name.return_value = 'another_host'
        with self.assertRaisesRegex(ValueError, 'not connected'):
            b.resolve([self.host, self.forge])

    def test_extension_names_and_alias(self):
        self.assertEqual(b.dependency_name(['bl_ext.user_default.official_nms_builder']), 'bl_ext.user_default.official_nms_builder')
        self.assertIsNone(b.dependency_name(['not_no_mans_sky_base_builder']))
