# DD2 September 2026 validation

Target: Title Update 3.2, local Steam build `24831693`, Blender 5.2.0 LTS.

The current base PAK was verified as version 4.2, flags `0x68`, 279,223 entries,
with 802 additional 16-byte entries before the 128-byte encrypted key.
Skipping this additional table correctly locates both the key and chunk table.
This format interpretation follows the community
[RE-Engine-Lib changes](https://github.com/kagenocookie/RE-Engine-Lib/commit/0096e2d202f42e6e325654e40060a94879d35ceb)
and was verified with actual installed game data.

## Executed

- Unit tests: old unencrypted PAK, new table/key/chunk layout, truncated table,
  explicit DD2 catalog migration, unrelated-field preservation, correct asset
  path resolution and refusal to modify a different game's catalog.
- Selected extraction through the production PAK reader and extractor: 29
  meshes, 33 MDFs and 34 textures; decompressed file sizes match the TOC.
- Blender registration and normal `extractFilesFromPakCache` path: a generated
  cache contains 279,255 effective entries from the installed base/patch/DLC
  PAKs. A DD2 mantle asset resolves to current MESH/MDF versions and extracts
  32 files including material and texture dependencies.
- The isolated migrated metadata contains MESH `260421070`, MDF2 `51` and
  TEX `251211553`. Reading metadata alone does not perform migration.

All game reads were read-only; extraction and test metadata use isolated
output directories. No extracted game assets or user Mods are distributed.
See the companion [mesh validation](https://github.com/miqote69/RE-Mesh-Editor/blob/main/DD2-PATCH-VALIDATION.md)
for Blender import/export evidence and its limits.

## Reproduce

```text
python -B -m unittest discover -s tests -p "test_*.py"
blender --background --factory-startup --python-exit-code 1 --python tests/blender_dd2_extract.py -- DD2_GAME_DIRECTORY TEST_OUTPUT_DIRECTORY
```

Use temporary `BLENDER_USER_CONFIG` and `BLENDER_USER_SCRIPTS` directories to
isolate addon registration from personal Blender settings. The integration
script creates a new test catalog/cache and extracts a known armor sample;
it does not change a personal catalog or a game PAK.

Interactive Asset Browser dragging, thumbnails, non-mesh asset types, PAK
writing, in-game Mod loading and rendering are **UNEXECUTED**. The patch
updates the extraction path; it does not repair or convert installed Mods.
