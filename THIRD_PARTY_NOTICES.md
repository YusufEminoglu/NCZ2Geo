# Third-Party Notices

`NCZ2Geo` bundles generated catalogs derived from public Turkish planning
standards:

- e-Plan plan gösterimleri published through `https://eplan.csb.gov.tr/`
- Mekansal Planlar Yapım Yönetmeliği / MPYY tabaka catalog data

The catalog compiler, matching code, package structure, Netcad NCZ Engine v2
reader, SDK API, CLI, and tests are authored for this package.

## No legacy NCZ parser is bundled

The `ncz_engine` here is the 02CadGis v2 engine, and it has been since this
package's first release (0.1.0, 2026-08-25). No version of `NCZ2Geo` has ever
bundled a third-party NCZ parser.

For lineage: the 02CadGis QGIS plugin shipped, in versions 0.1.0 through 4.1.2,
an NCZ decoder adapted from **Jeomatik NCZ Reader** (Copyright (C) 2026 Erdinç
Örsan ÜNAL, GPL-2.0-or-later, <https://github.com/erdincunal/Jeomatik-NCZ-Reader>).
That code is not in this package and never was; the engine here is the v2
rewrite the plugin moved to. It was written with knowledge of the upstream
implementation, not in isolation from it, and is offered as an independent
implementation of the format — not as a legal opinion on the derivative-work
status of any particular version.

The engine, the SDK packaging around it, and the catalogs' compiler are:

- Copyright (C) 2026 Yusuf Eminoğlu

`NCZ2Geo` is an independent project and is not endorsed by or affiliated with
Jeomatik. The Jeomatik name and logo remain the property of their respective
owner.
