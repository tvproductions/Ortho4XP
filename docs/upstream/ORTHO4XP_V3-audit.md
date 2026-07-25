# ORTHO4XP_V3 Upstream Audit Ledger

This ledger records engineering review of the authoritative
`Ypsos/ORTHO4XP_V3` repository. The `tvproductions/ORTHO4XP_V3` repository is
observed only as a passive synchronization fork. Its normal lag is
informational and does not change the accepted author baseline.

Structured HTML comments are the machine-readable evidence. Narrative text
explains the engineering decisions but cannot advance `.github/upstream-watch.json`.

## Audit `ypsos-4ca0a8d404b0-8a25af093af7`

- Audit date: 2026-07-19
- Author range:
  `4ca0a8d404b078ad899979bafde84769a0fb235b..8a25af093af758292b4ef4c2caff93719cb1a54a`
- Relationship: fast-forward
- Commits: 7
- Changed paths: 48
- Manifest SHA-256:
  `204b30f3a175ed65d8495c0bc99a4ac6a6ddfc828d7ebdb8f9fa62bd198ece91`
- Static evidence: all changed Python blobs parsed without execution; no syntax
  failures; targeted Ruff was available and recorded 731 upstream findings.
- Compatibility signals: provider data, XP11, XP11+bathy, and XP12.
- Passive-fork state: observed separately by the detector and not included in
  the reproducible change-manifest digest.

Reviewed commits:

1. `3abebf9bf968add5f89c0aff78c7922c8ef1ec81` — coastal DDS rotation correction.
2. `17e23d0b826f892967b014a3e0393b9e47fc4ce0` — README revision.
3. `13d43923edef9e2d71389e8e85ab7b07807ea61a` — provider and source update.
4. `e21175de156872e413cf6be5d6b319b8f62e679a` — upstream branch merge.
5. `772733279f23768f9079d6188f54502d88d66424` — imagery correction workflow.
6. `c1edfafb690fd0f6265c688b626d6db2234b17c2` — altimetry workflow.
7. `8a25af093af758292b4ef4c2caff93719cb1a54a` — integration update.

<!-- upstream-watch:audit {"audit_id":"ypsos-4ca0a8d404b0-8a25af093af7","base_sha":"4ca0a8d404b078ad899979bafde84769a0fb235b","head_sha":"8a25af093af758292b4ef4c2caff93719cb1a54a","manifest_sha256":"204b30f3a175ed65d8495c0bc99a4ac6a6ddfc828d7ebdb8f9fa62bd198ece91","path_count":48} -->

### Provider definitions

Disposition: `investigate`. Provider legality, attribution, credentials,
service currency, schema conversion, and live endpoint behavior remain
unverified. TODO-041-4 and GitHub Issue #41 own the required audit. This
finding intentionally blocks author-baseline advancement.

<!-- upstream-watch:finding {"audit_id":"ypsos-4ca0a8d404b0-8a25af093af7","disposition":"investigate","finding_id":"provider-definitions","paths":["Providers/FR66EJ~G/FRANCE_Auvergne-Rhone-Alpes_01-Ain_Histo-2024_IGN.lay","Providers/FR66EJ~G/FRANCE_Auvergne-Rhone-Alpes_01-Ain_PatchFrontireSavoie_Histo-2024_CRAIG.lay","Providers/FR66EJ~G/FRANCE_Auvergne-Rhone-Alpes_03-Allier_Histo-2025_IGN.lay","Providers/FR66EJ~G/FRANCE_Auvergne-Rhone-Alpes_07-Ardeche_2023_CRAIG.lay","Providers/FR66EJ~G/FRANCE_Auvergne-Rhone-Alpes_15-Cantal_2020_CRAIG.lay","Providers/FR66EJ~G/FRANCE_Auvergne-Rhone-Alpes_26-Drome_2023_CRAIG.lay","Providers/FR66EJ~G/FRANCE_Auvergne-Rhone-Alpes_38-Isere_2024_CRAIG.lay","Providers/FR66EJ~G/FRANCE_Auvergne-Rhone-Alpes_42-Loire_Histo-2025_IGN.lay","Providers/FR66EJ~G/FRANCE_Auvergne-Rhone-Alpes_43-Haute-Loire_Histo-2019_IGN.lay","Providers/FR66EJ~G/FRANCE_Auvergne-Rhone-Alpes_43-Haute-Loire_patch-Loire_2019_CRAIG.lay","Providers/FR66EJ~G/FRANCE_Auvergne-Rhone-Alpes_63-Puy-De-Dome_2022_IGN-HR.lay","Providers/FR66EJ~G/FRANCE_Auvergne-Rhone-Alpes_69-Rhone_2023_CRAIG.lay","Providers/FR66EJ~G/FRANCE_Auvergne-Rhone-Alpes_73-Savoie_2016_CRAIG.lay","Providers/FR66EJ~G/FRANCE_Auvergne-Rhone-Alpes_73-Savoie_Histo-2022_IGN.lay","Providers/FR66EJ~G/FRANCE_Auvergne-Rhone-Alpes_74-Haute-Savoie_2023_CRAIG.lay","Providers/Global/Arc.lay","Providers/Global/Arc@.lay","Providers/Global/BI.lay","Providers/Global/EOX.lay","Providers/Global/EOX2.lay","Providers/Global/Esri_07-2022.lay","Providers/Global/Esri_clarify.lay","Providers/Global/GO2.lay","Providers/Global/Here.lay","Providers/Global/Maxar.lay","Providers/Global/OSM.lay","Providers/Global/SEA.lay","Providers/Global/USA2.lay","Providers/Global/Yandex.lay"],"rationale":"Licensing, attribution, credentials, service currency, endpoint behavior, conflicts, and conversion to the local schema-backed JSON format require a dedicated provider audit before adoption or rejection.","work_items":["TODO-041-4","https://github.com/tvproductions/Ortho4XP/issues/41"],"xp12_compatibility":"Provider definitions must be legal, current, credential-safe, schema-valid, and compatible with the local XP12-only imagery pipeline."} -->

### DEM preparation

Disposition: `reimplement`. Retain country-organized source discovery,
reprojection, controlled resolution reduction, custom-DEM output, and optional
QGIS handoff. Reject Rasterio/GUI coupling, France-specific missing-CRS
fallback, and whole-mosaic memory loading.

<!-- upstream-watch:finding {"audit_id":"ypsos-4ca0a8d404b0-8a25af093af7","disposition":"reimplement","finding_id":"dem-preparation-workbench","paths":["src/O4_Altimetrie_Utils.py"],"rationale":"The operator workflow is useful, but it must use the existing GDAL dependency, explicit CRS contracts, streamed processing, portable core/UI boundaries, and deterministic fixtures.","work_items":["TODO-041-5","https://github.com/tvproductions/Ortho4XP/issues/42"],"xp12_compatibility":"The reimplementation will produce custom_dem-compatible inputs without restoring legacy X-Plane 11 behavior."} -->

### Imagery QA and correction

Disposition: `reimplement`. Retain indexed browsing, source-image patch
handoff, manual review metadata, cache invalidation, and sea-only nodata repair
research through local provider-scoring and texture-source contracts.

<!-- upstream-watch:finding {"audit_id":"ypsos-4ca0a8d404b0-8a25af093af7","disposition":"reimplement","finding_id":"imagery-qa-correction-workbench","paths":["src/O4_Color_Check.py","src/O4_Color_Normalize.py","src/O4_Correction_Utils.py"],"rationale":"The operator workflow addresses real imagery defects, but the implementation must be cache-aware, provider-identity-safe, independently testable, and separated from GUI state.","work_items":["TODO-041-6","https://github.com/tvproductions/Ortho4XP/issues/43"],"xp12_compatibility":"Sea-aware correction must preserve land imagery and integrate with the local XP12 texture and cache lifecycle."} -->

### Airport-query and DEM failure handling

Disposition: `reimplement`, already completed locally by TODO-041-1. The local
implementation initializes DEM independently and treats airport-query failure
as explicitly reported but nonfatal.

<!-- upstream-watch:finding {"audit_id":"ypsos-4ca0a8d404b0-8a25af093af7","disposition":"reimplement","finding_id":"airport-query-dem-failure-handling","paths":["src/O4_OSM_Utils.py","src/O4_Vector_Map.py"],"rationale":"The behavior was retained through local vector-input contracts with explicit nonfatal airport-query reporting and independent DEM preparation.","work_items":["TODO-041-1","https://github.com/tvproductions/Ortho4XP/issues/38"],"xp12_compatibility":"The local implementation preserves strict XP12 behavior and does not restore legacy water or mesh modes."} -->

### XP12 coastal artifacts and texture lifecycle

Disposition: `reimplement`, already completed locally by TODO-041-2. Retain
the verified mask, cleanup, extent, naming, transaction, provider identity, and
ocean-decal behavior. Reject XP11+bathy restoration and wholesale replacement
of local sea-texture architecture.

<!-- upstream-watch:finding {"audit_id":"ypsos-4ca0a8d404b0-8a25af093af7","disposition":"reimplement","finding_id":"xp12-coastal-texture-lifecycle","paths":["src/O4_Coastal_Manager.py","src/O4_DSF_Utils.py","src/O4_File_Names.py","src/O4_Imagery_Utils.py","src/O4_Mask_Utils.py","src/O4_Sea_Texture.py"],"rationale":"The observed coastal fixes were translated into local artifact policy, validation, transaction, finalization, cleanup, failover, and DDS lifecycle contracts rather than copying the upstream modules.","work_items":["TODO-041-2","https://github.com/tvproductions/Ortho4XP/issues/39"],"xp12_compatibility":"The local implementation is XP12-only and explicitly rejects XP11+bathy restoration."} -->

### Reviewed with no direct action

The README and deleted launcher describe the sister project rather than
portable behavior. Configuration, GUI, language, and tile changes expose the
upstream workbench modules and their GUI state; TODO-041-5 and TODO-041-6 will
define local core/UI contracts instead.

<!-- upstream-watch:reviewed-no-action {"audit_id":"ypsos-4ca0a8d404b0-8a25af093af7","path":"README.md","rationale":"This change documents the sister project and does not define portable behavior for this repository."} -->
<!-- upstream-watch:reviewed-no-action {"audit_id":"ypsos-4ca0a8d404b0-8a25af093af7","path":"create_launcher_ORTHO.py","rationale":"The deletion belongs to the sister project's custom installer; this repository uses uv and its own packaging workflow."} -->
<!-- upstream-watch:reviewed-no-action {"audit_id":"ypsos-4ca0a8d404b0-8a25af093af7","path":"src/O4_Config_Utils.py","rationale":"The change exposes upstream workbench configuration; the approved local workbenches will define their own validated contracts."} -->
<!-- upstream-watch:reviewed-no-action {"audit_id":"ypsos-4ca0a8d404b0-8a25af093af7","path":"src/O4_GUI_Utils.py","rationale":"The change exposes upstream GUI state; reusable local processing cores must remain separate from GUI integration."} -->
<!-- upstream-watch:reviewed-no-action {"audit_id":"ypsos-4ca0a8d404b0-8a25af093af7","path":"src/O4_Lang_EN.py","rationale":"The language additions label upstream GUI surfaces that are not adopted directly."} -->
<!-- upstream-watch:reviewed-no-action {"audit_id":"ypsos-4ca0a8d404b0-8a25af093af7","path":"src/O4_Lang_FR.py","rationale":"The language additions label upstream GUI surfaces that are not adopted directly."} -->
<!-- upstream-watch:reviewed-no-action {"audit_id":"ypsos-4ca0a8d404b0-8a25af093af7","path":"src/O4_Tile_Utils.py","rationale":"The changes invoke upstream DEM and correction modules; local workbench orchestration will use independent core contracts."} -->

## Baseline decision

The 48 changed paths have complete, non-duplicated coverage. The
`provider-definitions` finding remains `investigate`, so this audit is valid
but the accepted author baseline must remain at
`4ca0a8d404b078ad899979bafde84769a0fb235b` until TODO-041-4 records final
provider dispositions.
